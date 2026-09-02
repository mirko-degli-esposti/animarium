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

import numpy as np
import pyarrow.parquet as pq

# Variabile di riferimento per il rapporto n/n_eff riportato nell'indice.
# PUNTIFI10 e' la fiducia nel governo comunale: universo 15+ standard, ed e'
# la voce piu' rilevante per il lavoro sulla comunicazione istituzionale.
VAR_RIF = "PUNTIFI10_num"

# Etichette come stanno nel parquet, verificate su Bologna (2/9/2026):
# cittadinanza ITL/FRG (codici, non decodificati); istruzione con le
# etichette del collasso di cs_build. Se cambiano, i marcatori escono
# sbagliati SENZA errore (l'except e' muto): il sintomo e' una coropleta
# uniforme o al 100%.
ITALIANA = "ITL"
LAUREA = ("laurea_o_its", "post_laurea")

def geometria_e_neff(par):
    """Baricentro del comune, numerosita' efficace su VAR_RIF, e i
    marcatori demografici per la coropleta dell'atlante.

    Il baricentro si ricava dagli individui: non serve alcuna geometria
    esterna, ed e' il centro di massa della popolazione, non del territorio —
    che per una mappa di navigazione e' anche piu' onesto.
    """
    fuori = {}
    try:
        t = pq.read_table(par, columns=["lon", "lat"]).to_pandas()
        lon, lat = float(t.lon.mean()), float(t.lat.mean())
        # NaN non e' JSON valido (json.dump lo scrive comunque, e il
        # viewer muore su .json()): un comune senza civici geolocalizzati
        # semplicemente non ha baricentro, e preparaAtlante lo salta gia'
        # col suo filtro `c.lon`.
        if lon == lon and lat == lat:          # NaN != NaN
            fuori["lon"] = round(lon, 5)
            fuori["lat"] = round(lat, 5)
    except Exception:
        pass

    try:
        t = pq.read_table(par, columns=["donor_id", VAR_RIF]).to_pandas()
        v = t[t[VAR_RIF].notna()]
        m = v.donor_id.value_counts().to_numpy(float)
        ne = float(m.sum() ** 2 / (m ** 2).sum())
        fuori["neff"] = {"var": VAR_RIF.replace("_num", ""),
                         "n": int(len(v)), "donatori": int(len(m)),
                         "n_eff": round(ne),
                         "rapporto": round(len(v) / ne, 1),
                         "banda": round((len(v) / ne) ** 0.5, 1)}
    except Exception:          # <-- questo mancava
        pass

    # Marcatori per la coropleta (design §4.8): la mappa colora la
    # popolazione SINTETICA aggregata, non i dati ISTAT — se la geografia
    # sociale che ne esce e' riconoscibile (Appennino vecchio, via Emilia
    # istruita), la figura argomenta da sola. Stessa lettura a colonne
    # degli altri blocchi: costo marginale trascurabile.
    try:
        t = pq.read_table(par, columns=["eta_anni", "cittadinanza",
                                        "istruzione"]).to_pandas()
        adulti = t[t.eta_anni >= 25]
        fuori["marcatori"] = {
            "pct_stranieri": round(100 * (t.cittadinanza != ITALIANA).mean(), 1),
            "eta_mediana": round(float(t.eta_anni.median()), 1),
            # denominatore 25+: la quota di laureati sulla popolazione
            # totale confonde istruzione e struttura per eta'
            "pct_laureati": round(100 * adulti.istruzione.isin(LAUREA).mean(), 1)
                            if len(adulti) else None,
        }
    except Exception:
        pass

    return fuori


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

        f_par = os.path.join(d, c["parquet"])
        geo = geometria_e_neff(f_par) if os.path.exists(f_par) else {}

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
            **geo,
            "riferimenti": os.path.exists(f_rif),
            "parquet_mb": round(os.path.getsize(
                os.path.join(d, c["parquet"])) / 1024 / 1024, 2)
            if os.path.exists(os.path.join(d, c["parquet"])) else None,
        })

    comuni.sort(key=lambda x: -x["individui"])
    out = os.path.join(args.bundle, "comuni.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"generato": dt.datetime.now().isoformat(timespec="seconds"),
                   "comuni": comuni}, f, ensure_ascii=False, indent=1,allow_nan=False)

         # allow_nan=False: NaN non e' JSON valido, ma json.dump lo scrive
        # comunque per default — e il viewer muore su .json() con un errore
        # che sembra tutt'altro (2/9/2026: 13 comuni senza baricentro hanno
        # rotto l'indice intero). Meglio fallire QUI, dove si capisce.

    print(f"[info] scritto {out}")
    print()
    print(f"{'codice':<9}{'nome':<20}{'individui':>11}  {'livello':<15}"
          f"{'zone':>5}{'tier':>5}{'attr':>6}{'copertura':>13}"
          f"{'banda':>7}{'MB':>7}")
    print("-" * 103)
    for c in comuni:
        cp = c.get("copertura")
        cs = (f"{cp['coperte']}/{cp['totali']} {cp['coperte'] / cp['totali']:.0%}"
              if cp else "—")
        n_ind = f"{c['individui']:,}".replace(",", ".")
        ne = c.get("neff")
        bd = f"×{ne['banda']:.1f}" if ne else "—"
        print(f"{c['codice']:<9}{c['nome'][:19]:<20}{n_ind:>11}  "
              f"{(c.get('livello') or '—'):<15}"
              f"{c['zone'] or '—':>5}{c.get('tier', '—'):>5}"
              f"{c.get('attributi', '—'):>6}{cs:>13}{bd:>7}"
              f"{c['parquet_mb'] or 0:>7.2f}")
    print()
    print("  I CONTEGGI di copertura non sono confrontabili fra livelli: il")
    print("  denominatore e' il numero di combinazioni interrogabili, che con")
    print("  sei variabili vale 96 e con nove 333. Le PERCENTUALI si', e su un")
    print("  comune non articolato escono piu' alte perche' ci sono meno")
    print("  incroci non vincolati.")
    print()
    print(f"  `banda` e' sqrt(n/n_eff) su {VAR_RIF.replace('_num','')}: quante")
    print("  volte l'intervallo di confidenza onesto e' piu' largo di quello")
    print("  ingenuo. Cresce con la popolazione, non con la qualita': un")
    print("  comune piccolo non satura il pool di donatori, quindi ogni")
    print("  donatore porta ancora informazione quasi indipendente.")
    manca = [c["nome"] for c in comuni if not c["riferimenti"]]
    if manca:
        print(f"\n[avviso] senza riferimenti censuari: {manca}")
        print("         i rombi non compariranno. build_riferimenti.py")


if __name__ == "__main__":
    main()
