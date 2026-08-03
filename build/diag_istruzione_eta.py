#!/usr/bin/env python3
"""
diag_istruzione_eta.py — Animarium, diagnostico F0(b)
======================================================

Coerenza fra eta' esatta e titolo di studio.

L'istruzione e' assegnata al livello del bin d'eta' con soglie minime di
conseguimento; `eta_anni` e' assegnata dopo, nell'anello 3, e nulla lega le
due. Dentro il bin 9-14 puo' quindi uscire un individuo con istruzione=media
ed eta_anni=10, che e' impossibile.

Non e' un bug della pipeline: e' una conseguenza dell'ordine delle
assegnazioni. Ma e' misurabile, e il sospetto e' che sia lo stesso fenomeno
di "resta sovrastimata `media` nel bin 9-14" visto dall'altro lato. Non e' un
caso che il taglio a nove anni venga dall'universo dell'istruzione (P83) e non
dalla griglia quinquennale: le due anomalie note stanno sulla stessa giuntura.

Soglie (anni compiuti minimi per poter avere quel titolo):

    elementare     10
    media          13
    diploma        18
    laurea_o_its   20
    post_laurea    22
    nessun_titolo   -   (sempre ammissibile)

Uso
---
    python diag_istruzione_eta.py 036023
    python diag_istruzione_eta.py 036023 --out violazioni_modena.csv
    python diag_istruzione_eta.py 017029 --pop-file /percorso/pop.csv
"""

from __future__ import annotations

import argparse
import os
import sys

import numpy as np
import pandas as pd

SOGLIE = {
    "nessun_titolo": 0,
    "elementare": 10,
    "media": 13,
    "diploma": 18,
    "laurea_o_its": 20,
    "post_laurea": 22,
}

ORDINE_ISTR = list(SOGLIE.keys())

ORDINE_ETA = ["0-8", "9-14", "15-24", "25-34", "35-49", "50-64", "65-74", "75+"]



def carica_gsp_common():
    try:
        import gsp.common as G  # type: ignore
        return G
    except Exception as e:
        print(f"[avviso] gsp.common non importabile ({e}); serve --pop-file.")
        return None


def risolvi_pop(comune, anno, pop_file):
    if pop_file is not None:
        if not os.path.exists(pop_file):
            sys.exit(f"errore: file non trovato: {pop_file}")
        return pop_file
    G = carica_gsp_common()
    if G is None:
        sys.exit("errore: senza gsp_common serve --pop-file")
    f = os.path.join(G.path_comune(comune), f"constraints_{anno}",
                     "popolazione_K9C_avq_full.csv")
    if not os.path.exists(f):
        sys.exit(f"errore: file non trovato: {f}")
    return f


def carica_pop(f):
    voluti = {"sezione", "zona", "quartiere", "sesso", "eta", "eta_anni",
              "istruzione", "cittadinanza", "condizione", "background"}
    p = pd.read_csv(f, low_memory=False,
                    dtype={"zona": "string", "sezione": "string"},
                    usecols=lambda c: c in voluti)
    mancanti = {"eta_anni", "istruzione"} - set(p.columns)
    if mancanti:
        sys.exit(f"errore: colonne assenti: {mancanti}")
    p["eta_anni"] = pd.to_numeric(p["eta_anni"], errors="coerce")
    p["istruzione"] = p["istruzione"].astype(str).str.strip()
    return p


def riga(titolo):
    print()
    print(titolo)
    print("-" * len(titolo))


def fmt(n):
    return f"{n:,}".replace(",", ".")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("comune", help="codice ISTAT, es. 036023")
    ap.add_argument("--anno", default="2024")
    ap.add_argument("--pop-file", default=None)
    ap.add_argument("--out", default=None,
                    help="CSV degli individui in violazione")
    ap.add_argument("--eta-max-tab", type=int, default=25,
                    help="eta' massima nella tabella incrociata (default 25)")
    args = ap.parse_args()

    f = risolvi_pop(args.comune, args.anno, args.pop_file)
    print(f"[info] popolazione: {f}")
    p = carica_pop(f)
    print(f"[info] individui: {fmt(len(p))}")

    ignoti = sorted(set(p["istruzione"].unique()) - set(SOGLIE))
    if ignoti:
        print(f"[avviso] modalita' di istruzione non in tabella soglie, "
              f"trattate come ammissibili: {ignoti}")

    p["soglia"] = p["istruzione"].map(SOGLIE)
    noto = p["soglia"].notna() & p["eta_anni"].notna()
    p["viola"] = False
    p.loc[noto, "viola"] = p.loc[noto, "eta_anni"] < p.loc[noto, "soglia"]

    n_viol = int(p["viola"].sum())
    quota = n_viol / len(p)

    riga("Sintesi")
    print(f"individui                    {fmt(len(p)):>12}")
    print(f"in violazione                {fmt(n_viol):>12}")
    print(f"quota                        {quota:>12.4%}")
    if n_viol:
        d = p.loc[p["viola"], "soglia"] - p.loc[p["viola"], "eta_anni"]
        print(f"anni mancanti: media {d.mean():.2f}  "
              f"mediana {d.median():.0f}  max {d.max():.0f}")

    if n_viol == 0:
        print("\nNessuna incoerenza: le due assegnazioni sono gia' allineate.")
        return

    # --- per titolo -------------------------------------------------------
    riga("Per titolo di studio")
    g = (p.groupby("istruzione")
           .agg(n=("viola", "size"), viol=("viola", "sum"))
           .reset_index())
    g["quota"] = g["viol"] / g["n"]
    g["soglia"] = g["istruzione"].map(SOGLIE)
    g["ord"] = g["istruzione"].map({v: i for i, v in enumerate(ORDINE_ISTR)})
    g = g.sort_values("ord").drop(columns="ord")
    with pd.option_context("display.width", 120):
        print(g[["istruzione", "soglia", "n", "viol", "quota"]]
              .to_string(index=False,
                         formatters={"quota": lambda v: f"{v:8.4%}",
                                     "n": lambda v: f"{v:>9,}".replace(",", "."),
                                     "viol": lambda v: f"{v:>9,}".replace(",", ".")}))

    # --- per bin d'eta' ---------------------------------------------------
    if "eta" in p.columns:
        riga("Per bin d'eta' del constraint set")
        g2 = (p.groupby("eta")
                .agg(n=("viola", "size"), viol=("viola", "sum"))
                .reset_index())
        g2["quota"] = g2["viol"] / g2["n"]
        g2["ord"] = g2["eta"].map({v: i for i, v in enumerate(ORDINE_ETA)})
        g2 = g2.sort_values("ord", na_position="last").drop(columns="ord")
        with pd.option_context("display.width", 120):
            print(g2.to_string(index=False,
                               formatters={"quota": lambda v: f"{v:8.4%}",
                                           "n": lambda v: f"{v:>9,}".replace(",", "."),
                                           "viol": lambda v: f"{v:>9,}".replace(",", ".")}))
        print("\nAtteso: la concentrazione sta nel bin 9-14, sulla stessa "
              "giuntura del seam quinquennale.")

    # --- tabella incrociata ----------------------------------------------
    riga(f"Incrocio istruzione x eta_anni (0-{args.eta_max_tab}), "
         f"celle impossibili marcate con *")
    sub = p[p["eta_anni"] <= args.eta_max_tab]
    tab = pd.crosstab(sub["istruzione"], sub["eta_anni"].astype(int))
    tab = tab.reindex([i for i in ORDINE_ISTR if i in tab.index])
    righe = []
    for istr, r in tab.iterrows():
        soglia = SOGLIE.get(istr, 0)
        cells = []
        for eta, v in r.items():
            mark = "*" if (v > 0 and eta < soglia) else " "
            cells.append(f"{int(v):>6}{mark}")
        righe.append(f"{istr:>14} " + "".join(cells))
    print(f"{'eta_anni':>14} " + "".join(f"{e:>7}" for e in tab.columns))
    print("\n".join(righe))


    # --- impossibili gia' al livello del bin (falla di supporto) ----------
    BIN_MAX = {"0-8": 8, "9-14": 14, "15-24": 24, "25-34": 34,
               "35-49": 49, "50-64": 64, "65-74": 74, "75+": 200}
    if "eta" in p.columns:
        bmax = p["eta"].map(BIN_MAX)
        imposs = p["soglia"].notna() & bmax.notna() & (p["soglia"] > bmax)
        n_imp = int(imposs.sum())
        riga("Impossibili gia' al livello del bin (non e' il seam)")
        print(f"record                       {fmt(n_imp):>12}")
        if n_imp:
            col = [c for c in ["sezione", "zona", "quartiere", "sesso", "eta",
                               "eta_anni", "istruzione", "soglia", "condizione",
                               "cittadinanza", "background"] if c in p.columns]
            print(p.loc[imposs, col].to_string(index=False))
            print("\nNessuna eta' del bin puo' sostenere quel titolo: non "
                  "dipende dall'ordine delle assegnazioni. Verificare il "
                  "supporto in cs_K9C.json.")

    # --- a rischio: chi poteva violare, dato bin e titolo -----------------
    BIN_MIN = {"0-8": 0, "9-14": 9, "15-24": 15, "25-34": 25,
               "35-49": 35, "50-64": 50, "65-74": 65, "75+": 75}
    if "eta" in p.columns:
        p["bin_min"] = p["eta"].map(BIN_MIN)
        p["a_rischio"] = (p["soglia"].notna() & p["bin_min"].notna()
                          & (p["soglia"] > p["bin_min"]))
    else:
        p["a_rischio"] = p["soglia"].notna()

    riga("Tasso condizionato")
    nr = int(p["a_rischio"].sum())
    print(f"individui a rischio          {fmt(nr):>12}")
    print(f"tasso condizionato           {p.loc[p['a_rischio'],'viola'].mean():>12.4%}")

    col_geo = "quartiere" if "quartiere" in p.columns else (
        "zona" if "zona" in p.columns else None)
    if col_geo:
        riga(f"Per {col_geo} — quota grezza contro tasso condizionato")
        g3 = (p.groupby(col_geo)
                .agg(n=("viola", "size"), viol=("viola", "sum"),
                     rischio=("a_rischio", "sum")).reset_index())
        g3["quota"] = g3["viol"] / g3["n"]
        g3["tasso"] = g3["viol"] / g3["rischio"].replace(0, np.nan)
        g3 = g3.sort_values("tasso", ascending=False)
        with pd.option_context("display.width", 150):
            print(g3.to_string(index=False,
                               formatters={"quota": lambda v: f"{v:8.4%}",
                                           "tasso": lambda v: f"{v:8.4%}"}))
        print("\nSe `tasso` e' piatto e `quota` no, la variazione fra zone e' "
              "composizione per eta' e l'incoerenza e' puramente aritmetica.")
        
    # --- output -----------------------------------------------------------
    if args.out:
        col = [c for c in ["sezione", "zona", "quartiere", "sesso", "eta",
                           "eta_anni", "istruzione", "soglia"] if c in p.columns]
        p.loc[p["viola"], col].to_csv(args.out, index=False)
        print(f"\n[info] {fmt(n_viol)} righe scritte in {args.out}")


if __name__ == "__main__":
    main()
