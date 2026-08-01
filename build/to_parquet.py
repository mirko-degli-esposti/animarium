#!/usr/bin/env python3
"""
to_parquet.py — Animarium, passo 1 (v2)
========================================

Converte `popolazione_K9C_avq_full.csv` in un Parquet ottimizzato per query
filtrate dal browser, e riporta il peso compresso colonna per colonna.

Novita' della v2, tutte dettate dalle misure dello smoke test
-------------------------------------------------------------
Lo smoke test su Modena ha mostrato che DuckDB-WASM **legge a blocchi
contigui, non a colonne**: richieste da 40-110 KB, e un fattore di
sovralettura di 1,8-3,5x. Q2 e' costata zero byte perche' Q1 si era gia'
portata dietro le colonne vicine. Da qui quattro scelte:

1. **Colonne ordinate per uso**, non nell'ordine del CSV. Tre blocchi:
   filtri e marginali · AVQ · pesanti da mappa. Chi filtra e guarda i
   marginali paga una lettura sola; chi apre la mappa a punti paga la
   seconda; le AVQ non vengono mai raccolte per sbaglio.

2. **Righe ordinate per `zona, sezione`** invece che per sola `sezione`.
   Il filtro piu' frequente dell'interfaccia e' la zona, e con
   l'ordinamento per sola sezione non pota nulla. Le sezioni restano
   contigue dentro la zona, quindi la selezione a lazo continua a potare.
   Con `--sort sezione` si torna al comportamento della v1.

3. **`id` in DELTA_BINARY_PACKED.** Era la colonna piu' pesante del file
   (0,79 MB, il 15%): una successione strettamente crescente su cui il
   dictionary encoding fallisce e zstd non morde.

4. **`lon`/`lat` in BYTE_STREAM_SPLIT**, la codifica pensata per i float.
   Sono il costo dominante della vista a punti.

Le codifiche si disattivano con `--no-encodings` se la versione di pyarrow
non le accetta.

Colonne aggiunte
----------------
    id      int32   progressivo dopo l'ordinamento, per i permalink
    quinq   int8    classe quinquennale ISTAT (0..15), da eta_anni

Ancora attese dalla pipeline (design §3.2):
    donor_id, cella_avq, macroeta, istr4

Uso
---
    python to_parquet.py 036023
    python to_parquet.py 036023 --row-group 20000
    python to_parquet.py 034027 --sort sezione --no-encodings
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

# Il set AVQ NON e' cablato qui: viene da gsp_common, che e' la sola fonte
# di verita'. Cablarlo significa che aggiungere una variabile alla pipeline
# non la fa comparire nel viewer, e nessuno se ne accorge — e' lo stesso
# schema per cui FORZE_ARMATE era sfuggita alla lista di assign_avq.py.
AVQ = None          # popolato in main() da G.AVQ_TARGETS + G.AVQ_OPZIONALI
LIVELLO = None      # livello del constraint set risolto (K9C, K6C, ...)

# Blocco A — filtri e marginali. E' la lettura che l'interfaccia fa sempre.
BLOCCO_A = ["zona", "quartiere", "sesso", "eta", "stato_civile",
            "cittadinanza", "istruzione", "condizione", "background",
            "origine_genitori", "paese", "area", "eta_anni", "quinq",
            "sezione"]

# Blocco C — pesanti, servono solo alla mappa a punti e alla scheda individuo.
BLOCCO_C = ["id", "indirizzo_fonte", "via", "civico", "lon", "lat"]

STRINGHE = ["zona", "sezione", "civico"]

GSP_SCRIPTS = os.path.expanduser("~/progetti/gsp/scripts")


# --------------------------------------------------------------------------

def carica_gsp():
    if GSP_SCRIPTS not in sys.path:
        sys.path.insert(0, GSP_SCRIPTS)
    try:
        import gsp_common as G  # type: ignore
        return G
    except Exception as e:
        sys.exit(f"errore: gsp_common non importabile ({e})")


def risolvi(comune, anno, pop_file, out):
    """Risolve il file popolazione senza cablare il livello.

    K10C e' escluso di proposito: su Brescia e' materiale sperimentale
    residuo, e il viewer non deve mai mostrarlo. Se un giorno diventasse il
    livello di produzione, questa riga va cambiata consapevolmente.
    """
    livello = None
    if pop_file is None:
        G = carica_gsp()
        cdir = G.path_constraints(comune, anno)
        nome = G.resolve_pop_file(cdir, suffisso="_avq_full",
                                  escludi=["K10C"])
        pop_file = os.path.join(cdir, nome)
        m = re.search(r"popolazione_(K\d+C)_", nome)
        livello = m.group(1) if m else "?"
    if not os.path.exists(pop_file):
        sys.exit(f"errore: file non trovato: {pop_file}")
    if out is None:
        out = os.path.join("bundle", "comuni", comune, "pop.parquet")
    globals()["LIVELLO"] = livello
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    return pop_file, out


def mb(n):
    return f"{n / 1024 / 1024:7.3f} MB"


def ordina_colonne(cols):
    """Tre blocchi: filtri · AVQ · pesanti. Le sconosciute finiscono fra
    le AVQ e le pesanti, cosi' non inquinano la lettura dei marginali."""
    a = [c for c in BLOCCO_A if c in cols]
    b = ([c + "_num" for c in AVQ if c + "_num" in cols]
         + [c for c in AVQ if c in cols]
         + (["donor_id"] if "donor_id" in cols else []))
    c = [c for c in BLOCCO_C if c in cols]
    noti = set(a) | set(b) | set(c)
    resto = [x for x in cols if x not in noti]
    return a + b + resto + c, (len(a), len(b), len(resto), len(c))


# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("comune")
    ap.add_argument("--anno", default="2024")
    ap.add_argument("--pop-file", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--row-group", type=int, default=20_000,
                    help="righe per row group (default 20.000; la v1 usava "
                         "50.000)")
    ap.add_argument("--compression", default="zstd",
                    choices=["zstd", "snappy", "gzip", "brotli", "none"])
    ap.add_argument("--sort", default="zona,sezione",
                    help="chiave di ordinamento delle righe "
                         "(default 'zona,sezione'; la v1 usava 'sezione')")
    ap.add_argument("--no-encodings", action="store_true",
                    help="niente DELTA_BINARY_PACKED / BYTE_STREAM_SPLIT")
    ap.add_argument("--no-avq-num", action="store_true")
    ap.add_argument("--no-reorder", action="store_true",
                    help="mantieni l'ordine di colonne del CSV")
    ap.add_argument("--drop-avq-raw", action="store_true",
                    help="tieni solo le AVQ numeriche: le grezze sono "
                         "ricostruibili da donor_anno (design §3.2)")
    args = ap.parse_args()

    global AVQ
    G = carica_gsp()
    AVQ = list(G.AVQ_TARGETS) + list(G.AVQ_OPZIONALI)

    src, out = risolvi(args.comune, args.anno, args.pop_file, args.out)
    print(f"[info] sorgente: {src}")
    if LIVELLO:
        print(f"[info] livello risolto: {LIVELLO} · "
              f"{len(AVQ)} variabili AVQ dal registro")
    print(f"[info] destinazione: {out}")

    # --- lettura ----------------------------------------------------------
    t0 = time.time()
    dtypes = {c: "string" for c in STRINGHE}
    dtypes.update({c: "string" for c in AVQ})
    p = pd.read_csv(src, low_memory=False, dtype=dtypes)
    print(f"[info] lette {len(p):,} righe x {len(p.columns)} colonne "
          f"in {time.time() - t0:.1f}s".replace(",", "."))
    csv_bytes = os.path.getsize(src)

    # --- colonne derivate -------------------------------------------------
    if "eta_anni" not in p.columns:
        sys.exit("errore: manca eta_anni")
    p["eta_anni"] = pd.to_numeric(p["eta_anni"], errors="coerce")
    q = np.minimum((p["eta_anni"].fillna(-5) // 5), 15)
    p["quinq"] = np.where(p["eta_anni"].isna(), -1, q).astype("int8")
    p["eta_anni"] = p["eta_anni"].astype("Int16")

    if not args.no_avq_num:
        presenti = [c for c in AVQ if c in p.columns]
        assenti = [c for c in AVQ if c not in p.columns]
        if assenti:
            print(f"[avviso] AVQ assenti: {assenti}")
        for c in presenti:
            p[c + "_num"] = pd.to_numeric(p[c], errors="coerce").astype("float32")
        print(f"[info] aggiunte {len(presenti)} colonne AVQ numeriche")

        firma = p[presenti].fillna("~").agg("|".join, axis=1)
        n_firme = int(pd.factorize(firma)[0].max()) + 1
        assert n_firme < 32000, f"troppe firme per int16: {n_firme}"
        p["donor_id"] = pd.factorize(firma)[0].astype("int16")
        m = p["donor_id"].value_counts().to_numpy(dtype="float64")
        print(f"[info] donor_id: {p['donor_id'].nunique():,} firme · "
              f"riuso medio {m.mean():.1f} · "
              f"n_eff di Kish {m.sum() ** 2 / (m ** 2).sum():,.0f}"
              .replace(",", "."))

        if args.drop_avq_raw:
            p = p.drop(columns=presenti)
            print(f"[info] rimosse {len(presenti)} colonne AVQ grezze")

    for c in ("lon", "lat"):
        if c in p.columns:
            p[c] = pd.to_numeric(p[c], errors="coerce").astype("float32")

    if "sezione" not in p.columns:
        sys.exit("errore: manca sezione")
    p["sezione"] = p["sezione"].astype("string").str.strip().str.zfill(12)

    # --- ordinamento righe + id -------------------------------------------
    chiave = [c.strip() for c in args.sort.split(",") if c.strip()]
    # Degrada invece di fallire: i comuni senza articolazione sub-comunale
    # (K6C) non hanno `zona`, e li' l'ordinamento per sola sezione e' quello
    # giusto — la potatura spaziale per zona non serve perche' la zona non
    # esiste.
    assenti = [c for c in chiave if c not in p.columns]
    chiave = [c for c in chiave if c in p.columns]
    if assenti:
        print(f"[info] chiave di ordinamento ridotta: {assenti} assenti "
              f"-> ordino per {chiave or ['(nessuna)']}")
    if not chiave:
        sys.exit("errore: nessuna colonna della chiave di ordinamento esiste")
    p = p.sort_values(chiave, kind="stable").reset_index(drop=True)
    p["id"] = np.arange(len(p), dtype="int32")
    print(f"[info] righe ordinate per {' , '.join(chiave)}")

    # --- ordinamento colonne ----------------------------------------------
    if args.no_reorder:
        ordine = list(p.columns)
        conta = None
    else:
        ordine, conta = ordina_colonne(list(p.columns))
        print(f"[info] colonne riordinate: blocco A (filtri) {conta[0]} · "
              f"AVQ {conta[1]} · altro {conta[2]} · pesanti {conta[3]}")
    p = p[ordine]

    # --- scrittura --------------------------------------------------------
    tab = pa.Table.from_pandas(p, preserve_index=False)

    kw = dict(
        compression=None if args.compression == "none" else args.compression,
        row_group_size=args.row_group,
        write_statistics=True,
        version="2.6",
    )
    if args.no_encodings:
        kw["use_dictionary"] = True
    else:
        enc = {}
        if "id" in tab.column_names:
            enc["id"] = "DELTA_BINARY_PACKED"
        for c in ("lon", "lat"):
            if c in tab.column_names:
                enc[c] = "BYTE_STREAM_SPLIT"
        kw["column_encoding"] = enc
        # le colonne con codifica esplicita non possono anche essere in
        # dizionario: si elencano tutte le altre
        kw["use_dictionary"] = [c for c in tab.column_names if c not in enc]

    t0 = time.time()
    try:
        pq.write_table(tab, out, **kw)
    except Exception as e:
        print(f"[avviso] scrittura con codifiche esplicite fallita ({e});"
              f" riprovo senza")
        kw.pop("column_encoding", None)
        kw["use_dictionary"] = True
        pq.write_table(tab, out, **kw)
    dt = time.time() - t0
    par_bytes = os.path.getsize(out)

    # --- report -----------------------------------------------------------
    md = pq.ParquetFile(out).metadata
    print()
    print("Scrittura")
    print("---------")
    print(f"tempo                  {dt:8.1f} s")
    print(f"CSV sorgente          {mb(csv_bytes)}")
    print(f"Parquet               {mb(par_bytes)}   "
          f"({par_bytes / csv_bytes:.1%} del CSV)")
    print(f"righe                 {md.num_rows:>11,}".replace(",", "."))
    print(f"colonne               {md.num_columns:>11}")
    print(f"row group             {md.num_row_groups:>11}   "
          f"({args.row_group:,} righe)".replace(",", "."))

    sizes = {}
    for i in range(md.num_row_groups):
        rg = md.row_group(i)
        for j in range(rg.num_columns):
            col = rg.column(j)
            sizes[col.path_in_schema] = (sizes.get(col.path_in_schema, 0)
                                         + col.total_compressed_size)
    s = pd.Series(sizes)

    print()
    print("Peso per blocco")
    print("---------------")
    if conta:
        blocchi = {"A filtri e marginali": ordine[:conta[0]],
                   "B AVQ": ordine[conta[0]:conta[0] + conta[1]],
                   "altro": ordine[conta[0] + conta[1]:
                                   conta[0] + conta[1] + conta[2]],
                   "C pesanti (mappa)": ordine[-conta[3]:] if conta[3] else []}
        for nome, cols in blocchi.items():
            cols = [c for c in cols if c in s.index]
            if not cols:
                continue
            v = s[cols].sum()
            print(f"  {nome:<24} {mb(v)}  {v / par_bytes:6.1%}  "
                  f"({len(cols)} colonne)")

    print()
    print("Prime 12 colonne per peso")
    print("-------------------------")
    for nome, v in s.sort_values(ascending=False).head(12).items():
        print(f"  {nome:<22} {mb(v)}  {v / par_bytes:6.1%}")

    # La tabella per blocco qui sopra E' la tabella dei costi: DuckDB legge
    # intervalli di byte contigui, quindi il costo di una query e' il peso
    # dei blocchi che tocca, non la somma delle colonne che chiede. Misurato:
    # tre colonne o cinque dello stesso blocco costano identico.
    print()
    print(f"  footer, pagato una volta per sessione   {mb(par_bytes - s.sum())}")

    # --- verifica ---------------------------------------------------------
    ver = pq.read_table(out, columns=["id"] + chiave).to_pandas()
    ordinato = ver[chiave].apply(tuple, axis=1).is_monotonic_increasing
    print()
    print(f"[verifica] righe {len(ver):,} · ordinamento {ordinato} · "
          f"id unico {ver['id'].is_unique} · "
          f"{'ok' if (len(ver) == len(p) and ordinato) else 'PROBLEMA'}"
          .replace(",", "."))


if __name__ == "__main__":
    main()
