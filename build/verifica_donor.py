#!/usr/bin/env python3
"""
verifica_donor.py — Animarium, sblocco di F2
=============================================

Il file `_full` conserva i valori AVQ ma non l'identita' del donatore. Senza
quella, ogni banda di incertezza sulle AVQ e' calcolata su `n` invece che su
`n_eff` = donatori distinti, e con riusi di 24-84x sottostima la larghezza di
un fattore `sqrt(n/n_eff)`, cioe' 5-9 volte.

**Ipotesi da verificare**: non serve l'identita' del donatore, serve
un'etichetta di classe di equivalenza. Siccome l'hot-deck copia tutte e 21 le
variabili **in blocco dallo stesso donatore**, la 21-upla di valori e' la
firma del donatore. Se le firme distinte sono tante quanti i donatori
dichiarati usati (§10 del riferimento), `donor_id` si ricostruisce dai file
esistenti e non serve rilanciare `assign_avq.py`.

Cosa controlla
--------------
1. firme distinte contro donatori dichiarati usati;
2. distribuzione del riuso, contro il riuso medio dichiarato;
3. quante firme attraversano piu' di una cella di condizionamento — proxy del
   collasso gerarchico, cioe' della colonna `cella_avq` anch'essa mancante;
4. `n_eff` su sottopopolazioni tipiche, e il fattore di sottostima della
   banda che si avrebbe ignorandolo.

Uso
---
    python verifica_donor.py 036023
    python verifica_donor.py 017029 --out donor_017029.csv
"""

from __future__ import annotations

import argparse
import os
import sys

import numpy as np
import pandas as pd

AVQ = ["AMBIENTE", "FIDUCIA", "SALUTE", "CRONI", "FUMO", "MH",
       "BMI", "BMIMIN", "CPESO",
       "PUNTIFI1", "PUNTIFI2", "PUNTIFI3", "PUNTIFI4", "PUNTIFI5",
       "PUNTIFI6", "PUNTIFI7", "PUNTIFI8", "PUNTIFI10", "PUNTIFI12",
       "PUNTIFI13", "VOTOUSL"]

# §10 del documento di riferimento, esecuzioni del 29/07/2026
ATTESI = {
    "017029": {"nome": "Brescia", "pool": 8111, "usati": 8108, "riuso": 24.5,
               "pop": 198259, "regione": "Lombardia"},
    "034027": {"nome": "Parma", "pool": 4629, "usati": 4618, "riuso": 42.9,
               "pop": 198121, "regione": "Emilia-Romagna"},
    "037006": {"nome": "Bologna", "pool": 4629, "usati": 4625, "riuso": 84.3,
               "pop": 390098, "regione": "Emilia-Romagna"},
    "036023": {"nome": "Modena", "pool": 4629, "usati": 4617, "riuso": 40.0,
               "pop": 184597, "regione": "Emilia-Romagna"},
}

MACROETA = {"0-8": "0-14", "9-14": "0-14", "15-24": "15-34", "25-34": "15-34",
            "35-49": "35-54", "50-64": "55-74", "65-74": "55-74",
            "75+": "75+"}

ISTR4 = {"nessun_titolo": 1, "elementare": 1, "media": 2, "diploma": 3,
         "laurea_o_its": 4, "post_laurea": 4}



def risolvi(comune, anno, pop_file):
    if pop_file is not None:
        if not os.path.exists(pop_file):
            sys.exit(f"errore: file non trovato: {pop_file}")
        return pop_file
    try:
        import gsp.common as G  # type: ignore
        f = os.path.join(G.path_comune(comune), f"constraints_{anno}",
                         "popolazione_K9C_avq_full.csv")
    except Exception as e:
        sys.exit(f"errore: gsp.common non importabile ({e}); usa --pop-file")
    if not os.path.exists(f):
        sys.exit(f"errore: file non trovato: {f}")
    return f


def riga(t):
    print()
    print(t)
    print("-" * len(t))


def fmt(n):
    return f"{n:,}".replace(",", ".")


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("comune")
    ap.add_argument("--anno", default="2024")
    ap.add_argument("--pop-file", default=None)
    ap.add_argument("--out", default=None,
                    help="CSV con id riga e donor_id ricostruito")
    args = ap.parse_args()

    f = risolvi(args.comune, args.anno, args.pop_file)
    print(f"[info] popolazione: {f}")

    voluti = set(AVQ) | {"sesso", "eta", "istruzione", "zona", "quartiere",
                         "cittadinanza"}
    p = pd.read_csv(f, low_memory=False,
                    dtype={c: "string" for c in AVQ} |
                          {"zona": "string"},
                    usecols=lambda c: c in voluti)

    presenti = [c for c in AVQ if c in p.columns]
    assenti = [c for c in AVQ if c not in p.columns]
    if assenti:
        print(f"[avviso] AVQ assenti dal file: {assenti}")
    print(f"[info] individui {fmt(len(p))} · variabili AVQ usate "
          f"per la firma: {len(presenti)}")

    att = ATTESI.get(args.comune)

    # --- 1. la firma ------------------------------------------------------
    firma = p[presenti].fillna("~").agg("|".join, axis=1)
    codici, _ = pd.factorize(firma)
    p["donor_id"] = codici
    n_firme = int(p["donor_id"].nunique())

    riga("1. Le firme sono i donatori?")
    print(f"firme distinte                {fmt(n_firme):>12}")
    if att:
        print(f"donatori dichiarati usati     {fmt(att['usati']):>12}   "
              f"(pool {fmt(att['pool'])}, {att['regione']})")
        d = n_firme - att["usati"]
        print(f"differenza                    {d:>+12}   "
              f"({d / att['usati']:+.3%})")
        if abs(d) <= max(5, 0.005 * att["usati"]):
            print("\n  -> COINCIDONO. La firma identifica il donatore, "
                  "donor_id e' ricostruibile\n     dai file esistenti e non "
                  "serve rilanciare assign_avq.py.")
        elif d < 0:
            print("\n  -> MENO firme che donatori: alcune coppie di donatori "
                  "hanno 21-uple\n     identiche. Sono informativamente "
                  "equivalenti, quindi n_eff sulle firme\n     resta la "
                  "quantita' giusta, ma va dichiarato.")
        else:
            print("\n  -> PIU' firme che donatori: qualcosa non torna. "
                  "Forse le AVQ non\n     vengono da un solo donatore, "
                  "o il file e' di un'esecuzione diversa.")

    # --- 2. il riuso ------------------------------------------------------
    riuso = p["donor_id"].value_counts()
    riga("2. Distribuzione del riuso")
    print(f"riuso medio                   {riuso.mean():>12.1f}"
          + (f"   (dichiarato {att['riuso']})" if att else ""))
    print(f"mediana                       {riuso.median():>12.0f}")
    print(f"minimo                        {riuso.min():>12}")
    print(f"massimo                       {riuso.max():>12}")
    print(f"donatori usati una volta sola {fmt(int((riuso == 1).sum())):>12}")
    q = riuso.quantile([.05, .25, .5, .75, .95])
    print("\nquantili del riuso: " +
          "  ".join(f"p{int(k*100)}={int(v)}" for k, v in q.items()))

    # --- 3. collasso gerarchico -------------------------------------------
    riga("3. Quanto collasso gerarchico (proxy di cella_avq)")
    if {"sesso", "eta", "istruzione"} <= set(p.columns):
        p["macroeta"] = p["eta"].map(MACROETA)
        p["istr4"] = p["istruzione"].map(ISTR4)
        g = p.groupby("donor_id").agg(
            n=("donor_id", "size"),
            sessi=("sesso", "nunique"),
            macro=("macroeta", "nunique"),
            istr=("istr4", "nunique"))
        tot = len(g)
        print(f"firme che servono un solo sesso        "
              f"{fmt(int((g.sessi == 1).sum())):>10}  "
              f"{(g.sessi == 1).mean():6.2%}")
        print(f"firme su una sola macroeta'            "
              f"{fmt(int((g.macro == 1).sum())):>10}  "
              f"{(g.macro == 1).mean():6.2%}")
        print(f"firme su una sola classe istr4         "
              f"{fmt(int((g.istr == 1).sum())):>10}  "
              f"{(g.istr == 1).mean():6.2%}")
        pieno = ((g.sessi == 1) & (g.macro == 1) & (g.istr == 1))
        print(f"\nfirme confinate alla cella piena       "
              f"{fmt(int(pieno.sum())):>10}  {pieno.mean():6.2%}")
        quota_ind = p["donor_id"].map(pieno).mean()
        print(f"individui serviti da firme confinate   "
              f"{quota_ind:>10.2%}")
        print("\n  La cella di condizionamento e' sesso x macroeta' x istr4. "
              "Una firma che\n  attraversa piu' celle e' passata per il "
              "collasso gerarchico: il resto\n  della popolazione ha ricevuto "
              "le AVQ da una cella meno specifica.")
    else:
        print("colonne sesso/eta/istruzione assenti: salto")

    # --- 4. n_eff in pratica ----------------------------------------------
    riga("4. n_eff su sottopopolazioni tipiche")
    print(f"{'sottopopolazione':<34}{'n':>9}{'distinti':>9}{'n_eff':>9}"
          f"{'n/n_eff':>9}{'banda x':>9}")
    print("-" * 79)

    def n_eff(s):
        """n_eff di Kish. Il conteggio dei distinti va bene solo se i
        riusi sono uguali; qui vanno da 1 a 1511."""
        m = s["donor_id"].value_counts().to_numpy(dtype="float64")
        return float(m.sum() ** 2 / (m ** 2).sum())

    def mostra(nome, sel):
        s = p.loc[sel]
        if len(s) == 0:
            return
        n = len(s)
        nd = s["donor_id"].nunique()
        ne = n_eff(s)
        print(f"{nome[:33]:<34}{fmt(n):>9}{fmt(nd):>7}{ne:>9.0f}"
              f"{n / ne:>9.1f}{np.sqrt(n / ne):>9.1f}")

    # --- 5. n_eff per variabile -------------------------------------------
    riga("5. n_eff per variabile — l'universo giusto")
    print(f"{'variabile':<12}{'copertura':>11}{'n':>10}{'distinti':>10}"
          f"{'n_eff':>9}{'banda x':>9}")
    print("-" * 61)
    for v in ["SALUTE", "AMBIENTE", "FIDUCIA", "CRONI", "MH", "BMI",
              "BMIMIN", "PUNTIFI10", "PUNTIFI8", "PUNTIFI13", "VOTOUSL"]:
        if v not in p.columns:
            continue
        sel = pd.to_numeric(p[v], errors="coerce").notna()
        if not sel.any():
            continue
        s = p.loc[sel]
        n, nd, ne = len(s), s["donor_id"].nunique(), n_eff(s)
        print(f"{v:<12}{sel.mean():>11.1%}{fmt(n):>10}{fmt(nd):>10}"
              f"{ne:>9.0f}{np.sqrt(n / ne):>9.1f}")
    print("\n  Le 21 variabili hanno universi diversi: un solo n_eff per "
          "tutto il blocco\n  AVQ non esiste. La banda va calcolata "
          "sull'universo della variabile.")

    # --- 6. la firma piu' riusata -----------------------------------------
    riga("6. La firma piu' riusata — chi e'?")
    top = riuso.index[0]
    s = p[p["donor_id"] == top]
    print(f"individui                     {fmt(len(s)):>12}   "
          f"({len(s) / len(p):.2%} della citta')")
    print(f"peso in Sigma m^2             "
          f"{len(s) ** 2 / (riuso.to_numpy(dtype='float64') ** 2).sum():>12.1%}")
    noti = [v for v in presenti
            if pd.to_numeric(s[v], errors="coerce").notna().any()]
    print(f"variabili con valore          {len(noti):>12} su {len(presenti)}")
    print(f"  {noti}")
    if "eta" in p.columns:
        print("\ncomposizione per bin d'eta':")
        print(s["eta"].value_counts().to_string())   

    mostra("comune intero", p.index == p.index)
    col_geo = "quartiere" if "quartiere" in p.columns else "zona"
    if col_geo in p.columns:
        conteggi = p[col_geo].value_counts()
        for z in list(conteggi.index[:3]) + list(conteggi.index[-2:]):
            mostra(f"{col_geo}: {z}", p[col_geo] == z)
        z0 = conteggi.index[0]
        if "sesso" in p.columns:
            mostra(f"{z0} · donne", (p[col_geo] == z0) & (p["sesso"] == "F"))
        if "istruzione" in p.columns:
            mostra(f"{z0} · laurea",
                   (p[col_geo] == z0) & (p["istruzione"] == "laurea_o_its"))
        if "cittadinanza" in p.columns:
            mostra(f"{z0} · stranieri",
                   (p[col_geo] == z0) & (p["cittadinanza"] == "FRG"))

    print("\n  'banda x' e' sqrt(n/n_eff): quante volte troppo stretta "
          "sarebbe la banda\n  di confidenza calcolata ignorando i donatori. "
          "E' il numero che il\n  pannello AVQ deve usare, non n.")

    # --- output -----------------------------------------------------------
    if args.out:
        p[["donor_id"]].to_csv(args.out, index_label="riga")
        print(f"\n[info] donor_id scritto in {args.out} "
              f"({fmt(len(p))} righe)")
        print("       L'ordine delle righe e' quello del CSV sorgente, "
              "quindi si\n       riattacca al _full con un merge posizionale.")


if __name__ == "__main__":
    main()
