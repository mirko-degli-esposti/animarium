#!/usr/bin/env python3
"""
build_indice.py — Animarium
============================

Scandisce `bundle/comuni/*/manifest.json` e scrive `bundle/comuni.json`, che
alimenta il menu a tendina del pannello.

E' l'unico file del bundle che non appartiene a una citta' sola, e va
rigenerato dopo aver aggiunto un comune. Non contiene niente che non stia gia'
nei manifest: e' un indice, non una fonte.

Uso
---
    python build/build_indice.py
    python build/build_indice.py --bundle /altro/percorso
"""

from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import sys


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bundle", default="bundle")
    args = ap.parse_args()

    patt = os.path.join(args.bundle, "comuni", "*", "manifest.json")
    trovati = sorted(glob.glob(patt))
    if not trovati:
        sys.exit(f"errore: nessun manifest sotto {patt}\n"
                 f"       esegui prima manifest_min.py su almeno un comune")

    comuni = []
    for f in trovati:
        with open(f, encoding="utf-8") as h:
            m = json.load(h)
        c = m["comune"]
        d = os.path.dirname(f)
        comuni.append({
            "codice": c["codice"],
            "nome": c["nome"],
            "individui": c["individui"],
            "zone": next((a["n_modalita"] for a in m["attributi"]
                          if a["nome"] == "zona"), None),
            "riferimenti": os.path.exists(os.path.join(d, "riferimenti.json")),
            "parquet_mb": round(os.path.getsize(
                os.path.join(d, c["parquet"])) / 1024 / 1024, 2)
            if os.path.exists(os.path.join(d, c["parquet"])) else None,
        })

    comuni.sort(key=lambda x: -x["individui"])
    out = os.path.join(args.bundle, "comuni.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"generato": dt.datetime.now().isoformat(timespec="seconds"),
                   "comuni": comuni}, f, ensure_ascii=False, indent=1)

    print(f"[info] scritto {out}")
    print()
    print(f"{'codice':<9}{'nome':<12}{'individui':>11}{'zone':>6}"
          f"{'MB':>7}  riferimenti")
    print("-" * 56)
    for c in comuni:
        print(f"{c['codice']:<9}{c['nome']:<12}"
              f"{c['individui']:>11,}".replace(",", ".")
              + f"{c['zone'] or '—':>6}{c['parquet_mb'] or 0:>7.2f}"
              f"  {'si' if c['riferimenti'] else 'NO'}")
    manca = [c["nome"] for c in comuni if not c["riferimenti"]]
    if manca:
        print(f"\n[avviso] senza riferimenti censuari: {manca}")
        print("         i rombi non compariranno. build_riferimenti.py")


if __name__ == "__main__":
    main()
