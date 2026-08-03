#!/usr/bin/env python3
"""
medie_nazionali.py — Animarium
===============================

Calcola le medie nazionali pesate delle variabili AVQ e le scrive nel bundle,
invece di cablarle nel pannello.

Perche'
-------
Le cinque medie che il pannello usava come tacche di riferimento — vigili del
fuoco 8,10, forze dell'ordine 6,70, ASL 6,34, Comune 5,13, Regione 4,65 —
erano nel documento di riferimento **senza citazione**, e cercandole si scopre
che non esistono in quella forma:

- l'ISTAT pubblica **percentuali**, non medie: «il 67,5% assegna punteggi tra
  8 e 10 ai Vigili del fuoco», non «8,10 di media»;
- il BES pubblica medie, ma solo per quattro indicatori compositi, e le forze
  dell'ordine ci stanno **insieme** ai vigili del fuoco (7,4 nel 2024).
  Amministrazione comunale, regionale e ASL non ci sono affatto.

Calcolarle e' meglio che citarle, per tre ragioni: sono **verificate** invece
che ricordate; coprono **tutte** le variabili invece di cinque, quindi ogni
riga del pannello ha la sua tacca; e sono **coerenti col nostro universo** —
stesso file, stesso anno, stessa soglia d'eta' — mentre una citazione esterna
si riferisce ai 14 anni e piu' e lascia la differenza non quantificata.

Metodo
------
Media pesata con `COEFIN`, il coefficiente di riporto all'universo, calcolata
sui soli individui che hanno la variabile — cioe' **sul suo universo**, la
stessa regola che governa `n_eff` (§13.3 del riferimento).

L'errore standard tiene conto del disegno solo in parte: usa i pesi ma NON il
grappolo familiare. L'AVQ campiona famiglie e intervista tutti i componenti
(2,28 a famiglia), con correlazione intrafamiliare stimata ~0,6 sulla fiducia:
l'errore vero e' quindi piu' largo di quello riportato, di circa il 30%. E'
scritto nel file di uscita.

Uso
---
    python build/medie_nazionali.py
    python build/medie_nazionali.py --anni 2024 --out bundle/medie_nazionali.json
"""

from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import sys

import numpy as np
import pandas as pd

AVQ_DIR = os.path.expanduser("~/progetti/gsp/data/avq/anni")

# fattore di grappolo familiare, da §13.3 del riferimento:
# 1 + (k-1)*rho con k = 2,01 componenti rispondenti e rho ~ 0,65
GRAPPOLO = 1.66


def carica_gsp():
    try:
        import gsp.common as G  # type: ignore
        return G
    except Exception as e:
        sys.exit(f"errore: gsp.common non importabile ({e})")


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--anni", nargs="*", default=["2024"],
                    help="annate da usare (default: 2024, l'ultima)")
    ap.add_argument("--out", default=os.path.join("bundle",
                                                  "medie_nazionali.json"))
    ap.add_argument("--eta-min", type=int, default=5,
                    help="classe ETAMi minima; 5 = 15 anni e piu'")
    args = ap.parse_args()

    G = carica_gsp()
    AVQ = list(G.AVQ_TARGETS) + list(G.AVQ_OPZIONALI)

    frames = []
    for y in args.anni:
        f = os.path.join(AVQ_DIR, f"avq{y}", "MICRODATI",
                         f"AVQ_Microdati_{y}.txt")
        if not os.path.exists(f):
            print(f"[avviso] {y}: file assente, saltato")
            continue
        voluti = set(AVQ) | {"ETAMi", "COEFIN", "REGMf", "SESSO"}
        d = pd.read_csv(f, sep="\t", low_memory=False,
                        usecols=lambda c: c in voluti)
        d["ANNO"] = int(y)
        frames.append(d)
        print(f"[info] {y}: {len(d):,} record".replace(",", "."))
    if not frames:
        sys.exit("errore: nessuna annata caricata")

    d = pd.concat(frames, ignore_index=True)
    d["COEFIN"] = pd.to_numeric(d["COEFIN"], errors="coerce")
    d["ETAMi"] = pd.to_numeric(d["ETAMi"], errors="coerce")
    d = d[d["COEFIN"].notna()]
    n_tot = len(d)
    d = d[d["ETAMi"] >= args.eta_min]
    print(f"[info] {len(d):,} record con ETAMi >= {args.eta_min} "
          f"su {n_tot:,}".replace(",", "."))

    righe = []
    for v in AVQ:
        if v not in d.columns:
            continue
        x = pd.to_numeric(d[v], errors="coerce")
        m = x.notna()
        if m.sum() < 100:
            continue
        w = d.loc[m, "COEFIN"].to_numpy(float)
        y = x[m].to_numpy(float)
        media = float(np.average(y, weights=w))
        # varianza pesata, e errore standard con la numerosita' efficace
        # dei pesi (Kish): non e' la stessa cosa di n
        var = float(np.average((y - media) ** 2, weights=w))
        n_eff_w = float(w.sum() ** 2 / (w ** 2).sum())
        se = float(np.sqrt(var / n_eff_w))
        righe.append({
            "var": v, "media": round(media, 3),
            "n": int(m.sum()), "copertura": round(float(m.mean()), 4),
            "sd": round(float(np.sqrt(var)), 3),
            "se": round(se, 4),
            "se_grappolo": round(se * np.sqrt(GRAPPOLO), 4),
            "min": float(np.nanmin(y)), "max": float(np.nanmax(y)),
        })

    righe.sort(key=lambda r: -r["media"])

    print()
    print(f"{'variabile':<14}{'media':>8}{'sd':>7}{'se':>8}"
          f"{'se+grap':>9}{'cop':>8}{'n':>9}")
    print("-" * 63)
    for r in righe:
        print(f"{r['var']:<14}{r['media']:>8.3f}{r['sd']:>7.2f}"
              f"{r['se']:>8.4f}{r['se_grappolo']:>9.4f}"
              f"{r['copertura']:>8.1%}{r['n']:>9,}".replace(",", "."))

    fuori = {
        "generato": dt.datetime.now().isoformat(timespec="seconds"),
        "fonte": ("elaborazione propria sui microdati AVQ public use "
                  f"(mIcro.STAT), annate {', '.join(args.anni)}"),
        "metodo": (f"media pesata con COEFIN, su ETAMi >= {args.eta_min} "
                   f"(15 anni e piu'), calcolata sull'universo di ciascuna "
                   f"variabile"),
        "avvertenza": (
            "NON sono cifre pubblicate dall'ISTAT: l'Istituto diffonde "
            "percentuali di punteggi 6-10 e 8-10, non medie. Le uniche medie "
            "pubblicate sono nel BES e riguardano quattro indicatori "
            "compositi, con forze dell'ordine e vigili del fuoco insieme. "
            "L'errore standard qui riportato usa i pesi ma non il grappolo "
            "familiare: `se_grappolo` lo corregge con il fattore 1,66 di "
            "§13.3 del riferimento, ed e' quello da usare."),
        "eta_min_ETAMi": args.eta_min,
        "anni": args.anni,
        "fattore_grappolo": GRAPPOLO,
        "variabili": righe,
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(fuori, f, ensure_ascii=False, indent=1)
    print(f"\n[info] scritto {args.out} ({len(righe)} variabili)")

    # --- confronto con le cinque cablate ----------------------------------
    CABLATE = {"PUNTIFI12": 8.10, "PUNTIFI3": 6.70, "VOTOUSL": 6.34,
               "PUNTIFI10": 5.13, "PUNTIFI8": 4.65}
    calc = {r["var"]: r["media"] for r in righe}
    comuni = [v for v in CABLATE if v in calc]
    if comuni:
        print()
        print("Confronto con le cinque medie cablate, di fonte ignota")
        print("-" * 54)
        print(f"{'variabile':<14}{'cablata':>9}{'calcolata':>11}{'scarto':>9}")
        for v in comuni:
            d_ = calc[v] - CABLATE[v]
            print(f"{v:<14}{CABLATE[v]:>9.2f}{calc[v]:>11.3f}{d_:>+9.3f}")
        peggio = max(abs(calc[v] - CABLATE[v]) for v in comuni)
        print()
        if peggio < 0.05:
            print("  Coincidono: le cablate erano giuste, e ora sono anche")
            print("  verificate e riproducibili.")
        elif peggio < 0.3:
            print("  Vicine ma non uguali. Le cablate vanno sostituite: la")
            print("  differenza si legge nei pannelli.")
        else:
            print("  DIVERGONO. Le cablate erano sbagliate, e sono state")
            print("  pubblicate come tacche di riferimento su undici citta'.")


if __name__ == "__main__":
    main()
