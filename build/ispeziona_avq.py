#!/usr/bin/env python3
"""
ispeziona_avq.py — Animarium / GSP
===================================

Guarda i microdati AVQ grezzi invece del tracciato, per rispondere a tre
domande che il tracciato non chiude.

1. **Quante annate ci sono e quanti record per regione?** Il prospetto 1
   della nota metodologica ISTAT 2024 da' 2.486 individui per l'Emilia-Romagna
   e 45.005 per l'Italia. Il pool GSP emiliano ne ha 4.629: sono 1,86 annate,
   non 3. O il documento di riferimento sbaglia sul numero di annate impilate,
   o manca il 38% dei record.

2. **Qual e' la variabile di regione?** Nell'elenco delle variabili estratto
   dal tracciato mancano undici posizioni, tutte fra la 6 e la 24 — cioe'
   proprio dove stanno le variabili di classificazione. Lo script le cerca nel
   dato, per forma: una colonna con ~20 valori distinti fra 1 e 20.

3. **Quanto sono correlati i componenti della stessa famiglia?** L'AVQ
   campiona **famiglie** e intervista tutti i componenti (§3.1 della nota),
   2,28 a famiglia. I donatori dell'hot-deck non sono quindi indipendenti, e
   `n_eff` di Kish — che li tratta come tali — e' un limite superiore. La
   correlazione intrafamiliare `rho` da' il fattore di grappolo
   `1 + (b-1)·rho` per cui `n_eff` va diviso.

Uso
---
    python build/ispeziona_avq.py ~/progetti/gsp/data/avq/anni/*/MICRODATI/*.txt
    python build/ispeziona_avq.py file.txt --reg REG --icc
"""

from __future__ import annotations

import argparse
import collections
import glob
import os
import sys

import numpy as np
import pandas as pd

FIDUCIA = ["PUNTIFI1", "PUNTIFI2", "PUNTIFI3", "PUNTIFI4", "PUNTIFI5",
           "PUNTIFI6", "PUNTIFI7", "PUNTIFI8", "PUNTIFI10", "PUNTIFI12",
           "PUNTIFI13", "VOTOUSL", "FORZE_ARMATE", "AMBIENTE", "MH"]

# prospetto 1 della nota metodologica ISTAT, campione effettivo 2024
ISTAT_2024 = {"Italia": 45005, "Emilia-Romagna": 2486, "Lombardia": 4155,
              "famiglie Italia": 19775, "comuni": 800}


def riga(t):
    print()
    print(t)
    print("-" * len(t))


def sniffa(percorso, n=3):
    """Riporta com'e' fatto il file, senza assumere niente."""
    with open(percorso, "r", encoding="utf-8", errors="replace") as f:
        prime = [f.readline().rstrip("\n") for _ in range(n)]
    print(f"  lunghezza delle prime righe: {[len(r) for r in prime]}")
    for sep, nome in ((",", "virgola"), (";", "punto e virgola"),
                      ("\t", "tab"), ("|", "pipe")):
        c = [r.count(sep) for r in prime]
        if c[0] and len(set(c)) == 1:
            print(f"  separatore plausibile: {nome} ({c[0] + 1} campi)")
    print(f"  prima riga: {prime[0][:150]}")
    if len(prime) > 1:
        print(f"  seconda:    {prime[1][:150]}")
    return prime


def carica(percorso, cols=None):
    """Sceglie il separatore che produce piu' colonne, invece di fidarsi di
    una soglia arbitraria: il file AVQ ne ha 700+, ma la stessa funzione deve
    funzionare su un file di prova a quattro."""
    migliore, ncol = None, 1
    for sep in (",", ";", "\t", "|"):
        try:
            d = pd.read_csv(percorso, sep=sep, nrows=5, low_memory=False)
            if d.shape[1] > ncol:
                migliore, ncol = sep, d.shape[1]
        except Exception:
            continue
    if migliore is None:
        return None
    try:
        return pd.read_csv(percorso, sep=migliore, low_memory=False,
                           usecols=cols)
    except Exception:
        return pd.read_csv(percorso, sep=migliore, low_memory=False)


def candidate_regione(d):
    """Cerca la regione per forma: ~20 valori distinti, interi fra 1 e 21."""
    out = []
    for c in d.columns[:60]:
        v = pd.to_numeric(d[c], errors="coerce").dropna()
        if len(v) < len(d) * .9:
            continue
        u = v.unique()
        if 15 <= len(u) <= 23 and u.min() >= 1 and u.max() <= 210:
            out.append((c, len(u), int(u.min()), int(u.max())))
    return out


def icc(d, var, fam):
    """ICC a effetti casuali a una via, da ANOVA. Restituisce (rho, k, n)."""
    x = pd.to_numeric(d[var], errors="coerce")
    m = pd.DataFrame({"f": d[fam], "x": x}).dropna()
    if len(m) < 50:
        return None
    g = m.groupby("f")["x"]
    ni = g.size()
    if ni.max() < 2:
        return None
    N, k = len(m), ni.nunique()
    a = ni.shape[0]
    media = m["x"].mean()
    msb = (ni * (g.mean() - media) ** 2).sum() / max(a - 1, 1)
    msw = ((m["x"] - m["f"].map(g.mean())) ** 2).sum() / max(N - a, 1)
    n0 = (N - (ni ** 2).sum() / N) / max(a - 1, 1)
    rho = (msb - msw) / (msb + (n0 - 1) * msw) if (msb + (n0 - 1) * msw) else 0
    return float(max(0, rho)), float(n0), N


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file", nargs="+")
    ap.add_argument("--reg", default=None, help="colonna della regione")
    ap.add_argument("--fam", default="PROFAM")
    ap.add_argument("--icc", action="store_true",
                    help="stima la correlazione intrafamiliare")
    args = ap.parse_args()

    percorsi = []
    for f in args.file:
        percorsi.extend(sorted(glob.glob(os.path.expanduser(f))))
    if not percorsi:
        sys.exit("errore: nessun file")

    totali = {}
    for p in percorsi:
        riga(os.path.basename(p))
        print(f"  {os.path.getsize(p) / 1024 / 1024:.1f} MB")
        sniffa(p)
        d = carica(p)
        if d is None:
            print("  -> formato non riconosciuto: probabilmente larghezza fissa.")
            print("     Serve il tracciato con le posizioni dei campi.")
            continue
        print(f"  righe {len(d):,} · colonne {d.shape[1]}".replace(",", "."))
        totali[os.path.basename(p)] = d

        if "ANNO" in d.columns:
            print(f"  ANNO: {dict(d['ANNO'].value_counts().sort_index())}")
        if args.fam in d.columns:
            nf = d[args.fam].nunique()
            print(f"  {args.fam}: {nf:,} famiglie · "
                  f"{len(d) / nf:.2f} componenti per famiglia"
                  .replace(",", "."))

        cand = [args.reg] if args.reg and args.reg in d.columns \
            else [c for c, *_ in candidate_regione(d)]
        if cand:
            print(f"  candidati per la regione: {cand}")
            c = cand[0]
            vc = d[c].value_counts().sort_index()
            print(f"  distribuzione di {c}: {dict(vc)}")
        else:
            print("  nessun candidato ovvio per la regione fra le prime 60 colonne")

    # --- confronto col prospetto 1 ----------------------------------------
    if totali:
        riga("Confronto con il prospetto 1 della nota metodologica ISTAT 2024")
        print(f"  Italia, campione effettivo 2024   {ISTAT_2024['Italia']:>8,}"
              .replace(",", "."))
        print(f"  Emilia-Romagna                     {ISTAT_2024['Emilia-Romagna']:>8,}"
              .replace(",", "."))
        print(f"  Lombardia                          {ISTAT_2024['Lombardia']:>8,}"
              .replace(",", "."))
        print(f"  pool GSP Emilia-Romagna            {4629:>8,}".replace(",", "."))
        print(f"  pool GSP Lombardia                 {8111:>8,}".replace(",", "."))
        print()
        print("  Se il pool impila tre annate, l'Emilia-Romagna dovrebbe")
        print("  avvicinarsi a 7.400 e la Lombardia a 12.400. Se invece sono")
        print("  ~4.600 e ~8.100, le annate impilate sono due, e il documento")
        print("  di riferimento va corretto.")

    # --- ICC ---------------------------------------------------------------
    if args.icc:
        riga("Correlazione intrafamiliare — il fattore di grappolo")
        d = pd.concat(totali.values(), ignore_index=True) if totali else None

        if "ANNO" in d.columns:
            d = d.assign(_fam=d["ANNO"].astype(str) + "|" +
                              d[args.fam].astype(str))
            args.fam = "_fam"      # PROFAM riparte da 1 ogni annata
            print("  chiave di famiglia: ANNO|PROFAM\n")

        if d is None or args.fam not in d.columns:
            print(f"  serve la colonna {args.fam}")
            return
        print(f"{'variabile':<14}{'rho':>8}{'k':>7}{'n':>9}{'fattore':>9}")
        print("-" * 47)
        for v in FIDUCIA:
            if v not in d.columns:
                continue
            r = icc(d, v, args.fam)
            if not r:
                continue
            rho, k, n = r
            print(f"{v:<14}{rho:>8.3f}{k:>7.2f}{n:>9,}"
                  f"{1 + (k - 1) * rho:>9.2f}".replace(",", "."))
        print()
        print("  `fattore` = 1 + (k-1)·rho e' quanto n_eff di Kish va DIVISO")
        print("  per tenere conto del fatto che l'AVQ campiona famiglie e")
        print("  intervista tutti i componenti. Kish conta i donatori come")
        print("  indipendenti: e' un limite superiore.")


if __name__ == "__main__":
    main()
