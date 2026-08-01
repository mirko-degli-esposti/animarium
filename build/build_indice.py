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
        # copertura del riferimento censuario, se build_riferimenti l'ha
        # gia' calcolata: il denominatore dipende dal livello, quindi va
        # trasportato insieme al numeratore o il confronto fra comuni
        # diventa privo di senso (67/333 contro 26/96).
        f_rif = os.path.join(d, "riferimenti.json")
        cop = None
        if os.path.exists(f_rif):
            try:
                with open(f_rif, encoding="utf-8") as h:
                    cop = json.load(h).get("copertura")
            except Exception:
                cop = None

        comuni.append({
            "codice": c["codice"],
            "nome": c["nome"],
            "regione": c.get("regione"),
            "individui": c["individui"],
            "livello": c.get("livello"),
            "livello_etichetta": c.get("livello_etichetta"),
            "tier": c.get("tier"),
            "paese_classe": c.get("paese_classe"),
            "zone": next((a["n_modalita"] for a in m["attributi"]
                          if a["nome"] == "zona"), None),
            "attributi": len(m["attributi"]),
            "copertura": cop,
            "riferimenti": os.path.exists(f_rif),
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
    print(f"{'codice':<9}{'nome':<20}{'individui':>11}  {'livello':<15}"
          f"{'zone':>5}{'tier':>5}{'attr':>6}{'copertura':>13}{'MB':>7}")
    print("-" * 96)
    for c in comuni:
        cp = c.get("copertura")
        cs = (f"{cp['coperte']}/{cp['totali']} {cp['coperte'] / cp['totali']:.0%}"
              if cp else "—")
        n_ind = f"{c['individui']:,}".replace(",", ".")
        print(f"{c['codice']:<9}{c['nome'][:19]:<20}{n_ind:>11}  "
              f"{(c.get('livello') or '—'):<15}"
              f"{c['zone'] or '—':>5}{c.get('tier', '—'):>5}"
              f"{c.get('attributi', '—'):>6}{cs:>13}"
              f"{c['parquet_mb'] or 0:>7.2f}")
    print()
    print("  I CONTEGGI di copertura non sono confrontabili fra livelli: il")
    print("  denominatore e' il numero di combinazioni interrogabili, che con")
    print("  sei variabili vale 96 e con nove 333. Le PERCENTUALI si', e su un")
    print("  comune non articolato escono piu' alte perche' ci sono meno")
    print("  incroci non vincolati.")
    manca = [c["nome"] for c in comuni if not c["riferimenti"]]
    if manca:
        print(f"\n[avviso] senza riferimenti censuari: {manca}")
        print("         i rombi non compariranno. build_riferimenti.py")


if __name__ == "__main__":
    main()
