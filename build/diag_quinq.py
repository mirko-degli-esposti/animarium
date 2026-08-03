#!/usr/bin/env python3
"""
diag_quinq.py — Animarium, diagnostico F0(a): il seam quinquennale
===================================================================

Riaggrega la popolazione sintetica alle sedici classi quinquennali ISTAT e la
confronta con le colonne osservate del file sezioni:

    P{30+k}  maschi     k = 0..15
    P{67+k}  femmine    k = 0..15

    k:  0 <5   1 5-9   2 10-14  3 15-19  4 20-24  5 25-29  6 30-34  7 35-39
        8 40-44 9 45-49 10 50-54 11 55-59 12 60-64 13 65-69 14 70-74 15 >74

Sei degli otto bin del constraint set coincidono con gruppi di quinquennali; i
due infantili no, e stanno insieme sotto ipotesi di uniformita' entro il
quinquennio:

    0-8   = <5           + 4/5 di 5-9
    9-14  = 1/5 di 5-9   + 10-14

Il taglio a nove anni viene dall'universo dell'istruzione (P83, "9 anni e
piu'"), non dalla griglia quinquennale. Il diagnostico serve a vedere *dove*
quell'ipotesi di uniformita' cede: l'attenzione va su k=1 (5-9) e k=2 (10-14).

Nota sullo stato del confronto: e' **verifica**, non validazione. Le colonne P
sono i pesi con cui l'anello 3 assegna la sezione, quindi l'accordo e'
costruito. Il valore sta nella risoluzione (sezione x sesso x quinquennio,
molto piu' fine del MAE sui totali) e nella localizzazione del residuo.

Uso
---
    python diag_quinq.py 036023
    python diag_quinq.py 036023 --out residui_modena.csv
    python diag_quinq.py 017029 --pop-file /percorso/pop.csv --sezioni /percorso/sez.csv
"""

from __future__ import annotations

import argparse
import os
import sys

import numpy as np
import pandas as pd

QUINQ = ["<5", "5-9", "10-14", "15-19", "20-24", "25-29", "30-34", "35-39",
         "40-44", "45-49", "50-54", "55-59", "60-64", "65-69", "70-74", ">74"]

OFFSET = {"M": 30, "F": 67}

CAND_SEZ_ID = ["SEZ21_ID", "SEZ2021_ID", "SEZ21", "SEZ2021", "SEZIONE",
               "sezione", "sez21_id", "sez_id"]



# --------------------------------------------------------------------------
# risoluzione dei percorsi
# --------------------------------------------------------------------------

def carica_gsp():
    """Prova a importare gsp.common. Restituisce il modulo o None."""
    try:
        import gsp.common as G  # type: ignore
        return G
    except Exception as e:
        print(f"[avviso] gsp.common non importabile ({e}); "
              f"servono --pop-file e --sezioni espliciti.")
        return None


def risolvi_percorsi(comune, anno, pop_file, sezioni_file):
    G = carica_gsp()

    if pop_file is None:
        if G is None:
            sys.exit("errore: senza gsp.common serve --pop-file")
        base = G.path_comune(comune)
        pop_file = os.path.join(base, f"constraints_{anno}",
                                "popolazione_K9C_avq_full.csv")

    if sezioni_file is None:
        if G is None:
            sys.exit("errore: senza gsp.common serve --sezioni")
        try:
            sezioni_file = G.path_sezioni(comune)
        except TypeError:
            sezioni_file = G.path_sezioni(G.info(comune)["slug"])

    for f, etichetta in [(pop_file, "popolazione"), (sezioni_file, "sezioni")]:
        if not os.path.exists(f):
            sys.exit(f"errore: file {etichetta} non trovato: {f}")

    return pop_file, sezioni_file


# --------------------------------------------------------------------------
# caricamento
# --------------------------------------------------------------------------

def carica_pop(f):
    p = pd.read_csv(f, low_memory=False,
                    dtype={"zona": "string", "sezione": "string",
                           "civico": "string"},
                    usecols=lambda c: c in {"sezione", "sesso", "eta",
                                            "eta_anni", "zona", "quartiere",
                                            "indirizzo_fonte"})
    mancanti = {"sezione", "sesso", "eta_anni"} - set(p.columns)
    if mancanti:
        sys.exit(f"errore: colonne assenti nel file popolazione: {mancanti}")
    p["sezione"] = p["sezione"].astype("string").str.strip().str.zfill(12)
    p["eta_anni"] = pd.to_numeric(p["eta_anni"], errors="coerce")
    n_nan = int(p["eta_anni"].isna().sum())
    if n_nan:
        print(f"[avviso] {n_nan} individui senza eta_anni: esclusi")
        p = p[p["eta_anni"].notna()]
    return p


def trova_col_sezione(df):
    for c in CAND_SEZ_ID:
        if c in df.columns:
            return c
    sys.exit("errore: nessuna colonna identificativo di sezione riconosciuta. "
             f"Candidati cercati: {CAND_SEZ_ID}. "
             f"Presenti: {list(df.columns)[:40]}")


def carica_sezioni(f, comune):
    s = pd.read_csv(f, low_memory=False)
    idcol = trova_col_sezione(s)
    print(f"[info] colonna identificativo sezione: {idcol}")

    # se il file e' regionale/provinciale, filtra sul comune
    procom = str(int(comune[:3]) * 1000 + int(comune[3:]))  # 036023 -> 36023
    for c in ["PRO_COM", "PROCOM", "PRO_COM_T", "CODICE_ISTAT"]:
        if c in s.columns:
            v = s[c].astype(str).str.strip().str.lstrip("0")
            sel = v == procom.lstrip("0")
            if sel.any() and not sel.all():
                print(f"[info] filtro su {c} == {procom}: "
                      f"{int(sel.sum())} sezioni su {len(s)}")
                s = s[sel]
            break

    s[idcol] = s[idcol].astype(str).str.strip().str.split(".").str[0].str.zfill(12)
    s = s.rename(columns={idcol: "sezione"})
    return s


# --------------------------------------------------------------------------
# costruzione delle tavole
# --------------------------------------------------------------------------

def osservato_lungo(sez):
    """Da wide (P30..P45, P67..P82) a lungo (sezione, sesso, k, oss)."""
    pezzi = []
    for sesso, off in OFFSET.items():
        cols = [f"P{off + k}" for k in range(16)]
        mancanti = [c for c in cols if c not in sez.columns]
        if mancanti:
            sys.exit(f"errore: colonne assenti nel file sezioni per "
                     f"sesso={sesso}: {mancanti}")
        sub = sez[["sezione"] + cols].copy()
        lungo = sub.melt(id_vars="sezione", value_vars=cols,
                         var_name="col", value_name="oss")
        lungo["k"] = lungo["col"].str[1:].astype(int) - off
        lungo["sesso"] = sesso
        pezzi.append(lungo[["sezione", "sesso", "k", "oss"]])
    o = pd.concat(pezzi, ignore_index=True)
    o["oss"] = pd.to_numeric(o["oss"], errors="coerce").fillna(0.0)
    return o


def sintetico_lungo(pop):
    k = np.minimum((pop["eta_anni"] // 5).astype(int), 15)
    d = pd.DataFrame({"sezione": pop["sezione"].astype(str),
                      "sesso": pop["sesso"].astype(str),
                      "k": k})
    return (d.groupby(["sezione", "sesso", "k"])
              .size().rename("sint").reset_index())


# --------------------------------------------------------------------------
# report
# --------------------------------------------------------------------------

def riga(titolo):
    print()
    print(titolo)
    print("-" * len(titolo))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("comune", help="codice ISTAT, es. 036023")
    ap.add_argument("--anno", default="2024")
    ap.add_argument("--pop-file", default=None)
    ap.add_argument("--sezioni", default=None)
    ap.add_argument("--out", default=None,
                    help="CSV dei residui per sezione x sesso x quinquennio")
    ap.add_argument("--top", type=int, default=15)
    args = ap.parse_args()

    pop_file, sez_file = risolvi_percorsi(args.comune, args.anno,
                                          args.pop_file, args.sezioni)
    print(f"[info] popolazione: {pop_file}")
    print(f"[info] sezioni:     {sez_file}")

    pop = carica_pop(pop_file)
    sez = carica_sezioni(sez_file, args.comune)

    oss = osservato_lungo(sez)
    sint = sintetico_lungo(pop)

    d = oss.merge(sint, on=["sezione", "sesso", "k"], how="outer")
    d["oss"] = d["oss"].fillna(0.0)
    d["sint"] = d["sint"].fillna(0).astype(float)
    d["res"] = d["sint"] - d["oss"]
    d["quinq"] = d["k"].map(dict(enumerate(QUINQ)))

    # --- totali -----------------------------------------------------------
    riga("Totali")
    print(f"individui sintetici        {len(pop):>12,}".replace(",", "."))
    print(f"somma colonne P osservate  {d['oss'].sum():>12,.0f}".replace(",", "."))
    print(f"differenza                 {len(pop) - d['oss'].sum():>12,.0f}"
          .replace(",", "."))
    print(f"celle (sezione x sesso x quinq) {len(d):>7,}".replace(",", "."))

    solo_oss = d[(d["sint"] == 0) & (d["oss"] > 0)]
    solo_sint = d[(d["oss"] == 0) & (d["sint"] > 0)]
    print(f"celle osservate ma vuote nel sintetico  {len(solo_oss):>6} "
          f"({solo_oss['oss'].sum():.0f} persone)")
    print(f"celle sintetiche senza osservato        {len(solo_sint):>6} "
          f"({solo_sint['sint'].sum():.0f} persone)")

    # --- MAE globale ------------------------------------------------------
    riga("Errore su celle sezione x sesso x quinquennio")
    print(f"MAE            {d['res'].abs().mean():8.4f}")
    print(f"bias medio     {d['res'].mean():8.4f}")
    print(f"RMSE           {np.sqrt((d['res'] ** 2).mean()):8.4f}")
    print(f"max |residuo|  {d['res'].abs().max():8.0f}")

    # --- per classe quinquennale -----------------------------------------
    riga("Per classe quinquennale  (il seam e' fra k=1 e k=2)")
    g = (d.groupby(["k", "quinq"])
           .agg(oss=("oss", "sum"), sint=("sint", "sum"),
                mae=("res", lambda x: x.abs().mean()),
                bias=("res", "mean"))
           .reset_index())
    g["scarto"] = g["sint"] - g["oss"]
    g["scarto_rel"] = np.where(g["oss"] > 0, g["scarto"] / g["oss"], np.nan)
    g = g[["k", "quinq", "oss", "sint", "scarto", "scarto_rel", "mae", "bias"]]
    with pd.option_context("display.width", 120,
                           "display.float_format", lambda v: f"{v:9.4f}"):
        print(g.to_string(index=False))

    riga("Focus sul seam")
    for k in (0, 1, 2):
        r = g[g["k"] == k].iloc[0]
        print(f"k={k} {r['quinq']:>6}   oss {r['oss']:>9,.0f}   "
              f"sint {r['sint']:>9,.0f}   scarto {r['scarto']:>+8,.0f} "
              f"({r['scarto_rel']:+.3%})   MAE/cella {r['mae']:.4f}"
              .replace(",", "."))
    altri = g[~g["k"].isin([0, 1, 2])]
    print(f"\nMAE medio per cella sulle altre 13 classi: "
          f"{altri['mae'].mean():.4f}")
    print("Se il MAE su k=1 e k=2 e' nettamente sopra questo valore, "
          "l'ipotesi di uniformita' entro il quinquennio 5-9 sta cedendo.")

    # --- per sezione ------------------------------------------------------
    riga("Per sezione")
    per_sez = (d.groupby("sezione")
                 .agg(oss=("oss", "sum"), sint=("sint", "sum"),
                      abs_res=("res", lambda x: x.abs().sum()))
                 .reset_index())
    per_sez["res_tot"] = per_sez["sint"] - per_sez["oss"]
    print(f"sezioni                        {len(per_sez):>8,}".replace(",", "."))
    print(f"MAE del totale per sezione     {per_sez['res_tot'].abs().mean():8.4f}")
    print(f"correlazione oss/sint          "
          f"{per_sez['oss'].corr(per_sez['sint']):8.6f}")
    print(f"|residuo| medio per sezione    {per_sez['abs_res'].mean():8.4f}")

    seam = d[d["k"].isin([1, 2])].groupby("sezione")["res"].apply(
        lambda x: x.abs().sum()).rename("abs_res_seam").reset_index()
    per_sez = per_sez.merge(seam, on="sezione", how="left")

    riga(f"Prime {args.top} sezioni per |residuo| sul seam (k=1,2)")
    top = per_sez.sort_values("abs_res_seam", ascending=False).head(args.top)
    with pd.option_context("display.width", 120,
                           "display.float_format", lambda v: f"{v:9.2f}"):
        print(top[["sezione", "oss", "sint", "abs_res_seam", "abs_res"]]
              .to_string(index=False))

    # --- output -----------------------------------------------------------
    if args.out:
        d.sort_values(["sezione", "sesso", "k"]).to_csv(args.out, index=False)
        print(f"\n[info] residui scritti in {args.out}")


if __name__ == "__main__":
    main()
