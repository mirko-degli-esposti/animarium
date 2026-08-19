#!/usr/bin/env python3
"""
build_rif_nuclei.py — Animarium
================================

Estrae dal censimento permanente 2023 i conteggi di **famiglie per ampiezza**
per sezione, e li mette nel bundle come riferimento della pagina dei nuclei.

Perche' serve un file a parte
-----------------------------
`riferimenti.json` viene dal constraint set, che vincola **individui**: sesso,
eta', istruzione, condizione. Le famiglie non ci sono — sono un'altra tavola
del censimento, quella da cui `gsp.nucleo.vincoli_da_sezione` ricava le
ampiezze.

Cosa dice, e cosa NON dice
--------------------------
`PF3`..`PF8` sono i conteggi di famiglie con 1, 2, ... 6 e piu' componenti.
Sono **lo stesso vincolo** che l'anello 4 ha usato per costruire i nuclei,
quindi la barra sintetica e il rombo censuario **coincidono per
costruzione**, a ogni livello di aggregazione: un vincolo rispettato per
sezione resta rispettato sommando le sezioni.

Mostrarlo non e' un trucco, ma va etichettato per cio' che e':

> verifica che il vincolo sia stato applicato, non che il modello indovini.

E' la stessa distinzione che il pannello dei marginali fa gia' fra gli
incroci vincolati dal censimento e quelli che sono modello — solo che qui
vale per l'intera distribuzione invece che per singole celle.

**Cio' che il riferimento non copre e' piu' interessante di cio' che copre**:
la tipologia familiare (coppia con figli, monogenitore, unipersonale) NON e'
vincolata da niente. Viene dalle firme del repertorio AVQ, che e'
emiliano-lombardo e non comunale. Confrontare la quota di coppie con figli
fra due comuni e' quindi un risultato del modello, e la pagina lo dichiara.

`PF8` e' una **classe aperta** — «6 componenti e oltre» — quindi l'ultimo
conteggio non e' l'ampiezza 6 ma tutto cio' che sta da 6 in su. La pagina
deve etichettarlo «6+», o il confronto con il sintetico sembra sbagliato
dove i nuclei grandi esistono.

Uso
---
    python build/build_rif_nuclei.py 036023
    python build/build_rif_nuclei.py --tutti
"""

from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import sys

import pandas as pd

# PF3 = 1 componente, PF4 = 2, ... PF8 = «6 e oltre». PF1 e' il totale
# famiglie, PF9 sta fuori dalla serie delle ampiezze.
PF = {f"PF{k + 2}": k for k in range(1, 7)}
AMP_MAX = 6


def carica_gsp():
    try:
        import gsp.common as G  # type: ignore
        return G
    except Exception as e:
        sys.exit(f"errore: gsp.common non importabile ({e})")


def file_sezioni(G, comune):
    """Il CSV di sezione del comune, cercato per slug nel registro."""
    i = G.info(comune)
    base = os.path.join(G.DATA, "submun")
    for nome in (i.get("slug"), i["nome"].lower().replace(" ", "_"),
                 i["nome"].split()[0].lower()):
        if not nome:
            continue
        f = os.path.join(base, f"{nome}_sezioni_2023.csv")
        if os.path.exists(f):
            return f
    trovati = glob.glob(os.path.join(base, "*_sezioni_2023.csv"))
    sys.exit(f"errore: file di sezione non trovato per {comune} "
             f"({i['nome']})\n  in {base}\n"
             f"  presenti: {[os.path.basename(x) for x in trovati][:8]}")


def estrai(comune, G, out=None):
    f = file_sezioni(G, comune)
    d = pd.read_csv(f, sep=None, engine="python", dtype=str)
    mancanti = [c for c in PF if c not in d.columns]
    if mancanti:
        sys.exit(f"errore: colonne assenti in {os.path.basename(f)}: {mancanti}")

    col_sez = next((c for c in ("SEZ21_ID", "SEZ2021", "SEZ2011", "SEZ",
                                "sezione", "COD_SEZ") if c in d.columns), None)
    if col_sez is None:
        sys.exit(f"errore: nessuna colonna di sezione in "
                 f"{os.path.basename(f)}\n  colonne: {list(d.columns)[:12]}")

    righe = []
    for _, x in d.iterrows():
        sez = str(x[col_sez]).strip().zfill(12)
        conti = {a: int(pd.to_numeric(x[c], errors="coerce") or 0)
                 for c, a in PF.items()}
        if sum(conti.values()):
            righe.append({"sezione": sez, **{str(k): v
                                             for k, v in conti.items()}})

    tot = {str(k): sum(r[str(k)] for r in righe) for k in range(1, AMP_MAX + 1)}
    n_fam = sum(tot.values())
    n_ind = sum(int(k) * v for k, v in tot.items())

    rif = {
        "generato": dt.datetime.now().isoformat(timespec="seconds"),
        "fonte": os.path.basename(f),
        "nota": ("Famiglie per ampiezza dal censimento permanente 2023, "
                 "colonne PF3..PF8 per sezione. E' LO STESSO VINCOLO da cui "
                 "l'anello 4 costruisce i nuclei: barra e rombo coincidono "
                 "per costruzione, a ogni livello di aggregazione. La "
                 "coincidenza verifica che il vincolo sia stato applicato, "
                 "non che il modello indovini."),
        "classe_aperta": (f"L'ampiezza {AMP_MAX} e' la classe «{AMP_MAX} e "
                          f"oltre»: va etichettata «{AMP_MAX}+», o il "
                          f"confronto col sintetico sembra sbagliato dove i "
                          f"nuclei grandi esistono."),
        "amp_max": AMP_MAX,
        "totale": tot,
        "famiglie": n_fam,
        "individui_in_famiglia": n_ind,
        "ampiezza_media": round(n_ind / n_fam, 4) if n_fam else None,
        "sezioni": righe,
    }

    out = out or os.path.join("bundle", "comuni", comune, "rif_nuclei.json")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8") as h:
        json.dump(rif, h, ensure_ascii=False, separators=(",", ":"))

    print(f"  {G.info(comune)['nome'][:19]:<20}{len(righe):>6} sezioni"
          f"{n_fam:>9,} famiglie   ampiezza media {rif['ampiezza_media']:.2f}"
          f"   {os.path.getsize(out) / 1024:>6.0f} KB".replace(",", "."))
    return rif


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("comuni", nargs="*")
    ap.add_argument("--tutti", action="store_true")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    G = carica_gsp()
    comuni = sorted(G.COMUNI) if args.tutti else args.comuni
    if not comuni:
        sys.exit("indicare almeno un comune, o --tutti")

    print(f"{'comune':<20}{'sezioni':>8}{'famiglie':>12}"
          f"{'ampiezza media':>18}{'file':>10}")
    print("-" * 70)
    fatti = 0
    for c in comuni:
        try:
            estrai(c, G, args.out if len(comuni) == 1 else None)
            fatti += 1
        except SystemExit as e:
            print(f"  {c:<20} {e}")
    print(f"\n{fatti}/{len(comuni)} comuni")
    print("\n  PF8 e' «6 e oltre»: la pagina deve etichettare l'ultima classe")
    print("  come 6+, o il confronto col sintetico sembra sbagliato.")


if __name__ == "__main__":
    main()
