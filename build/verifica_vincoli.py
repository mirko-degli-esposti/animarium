#!/usr/bin/env python3
"""
verifica_vincoli.py — Animarium / GSP   (v2)
=============================================

Verifica cella per cella il rispetto del constraint set, **contro il pavimento
di rumore** invece che in valore assoluto.

Perche' la v1 era inutilizzabile
--------------------------------
La v1 ordinava per errore relativo e trovava celle sbagliate del 132%. Ma
quelle celle avevano valore atteso 1,3 individui: un errore di due unita' su
1,3 non significa niente. L'errore relativo su conteggi piccoli e' una
statistica senza contenuto, e la classifica che ne usciva era semplicemente la
classifica delle celle piu' piccole.

La conferma stava gia' nei numeri: Parma aveva MRE piu' alto di Modena (5,4%
contro 4,5%) pur avendo piu' abitanti — perche' ha 13 zone invece di 4, quindi
celle piu' piccole. Se fosse errore di fit andrebbe nella direzione opposta.

La metrica giusta
-----------------
La popolazione e' un campione dalla distribuzione fittata, non la sua media.
Per una cella con probabilita' target alpha su N individui, la deviazione
standard multinomiale e' sqrt(N*alpha*(1-alpha)), quindi:

    z = (osservato - atteso) / sqrt(N*alpha*(1-alpha))

Se il pool e' un campione pulito, gli z sono ~N(0,1):

    |z| medio  ->  0,798   (= sqrt(2/pi))
    sd(z)      ->  1,000
    |z| > 2    ->  4,55%
    |z| > 3    ->  0,27%

**sd(z) e' anche una misura dell'autocorrelazione della catena**: un pool
sovradisperso e' meno informativo di un campione indipendente della stessa
taglia, ed e' esattamente il fenomeno che rende il mixing (n_gibbs_sweeps) il
vincolo stringente a K alto.

Lo script stampa anche il MRE atteso dalla formula del documento di
riferimento, mean(sqrt((1-alpha)/(alpha*N))), accanto a quello osservato: se
coincidono, l'errore osservato E' il pavimento di rumore e non c'e' nulla da
spiegare.

Uso
---
    python build/verifica_vincoli.py 036023 --out celle_modena.csv
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import sys

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

GSP = os.path.expanduser("~/progetti/gsp/data/comuni")

ATTESO_ABS_Z = np.sqrt(2 / np.pi)   # 0,7979


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
    ap.add_argument("--cs", default=None)
    ap.add_argument("--parquet", default=None)
    ap.add_argument("--top", type=int, default=20)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    f_cs = args.cs or os.path.join(GSP, args.comune, f"constraints_{args.anno}",
                                   "cs_K9C.json")
    f_par = args.parquet or os.path.join("bundle", "comuni", args.comune,
                                         "pop.parquet")
    for f, che in ((f_cs, "constraint set"), (f_par, "Parquet")):
        if not os.path.exists(f):
            sys.exit(f"errore: {che} non trovato: {f}")
    print(f"[info] vincoli:     {f_cs}")
    print(f"[info] popolazione: {f_par}")

    with open(f_cs, encoding="utf-8") as h:
        cs = json.load(h)
    V, C = cs["vars"], cs["categories"]

    disponibili = set(pq.ParquetFile(f_par).schema_arrow.names)
    mancanti = [v for v in V if v not in disponibili]
    if mancanti:
        sys.exit(f"errore: attributi assenti dal Parquet: {mancanti}")
    pop = pq.read_table(f_par, columns=V).to_pandas()
    for v in V:
        pop[v] = pop[v].astype("string")
    N = len(pop)
    print(f"[info] {fmt(N)} individui · {len(V)} attributi")

    blocchi = collections.defaultdict(list)
    for c in cs["constraints"]:
        blocchi[tuple(c["attrs"])].append(c)

    tutte, sommario = [], []

    for attrs in sorted(blocchi, key=lambda a: (len(a), a)):
        nomi = [V[i] for i in attrs]
        oss = pop.groupby(nomi, observed=True).size()
        voci = blocchi[attrs]

        chiavi = [tuple(C[V[a]][v] for a, v in zip(attrs, c["vals"]))
                  for c in voci]
        alpha = np.array([c["alpha"] for c in voci], dtype="float64")
        att = alpha * N
        rea = np.array([float(oss.get(k if len(k) > 1 else k[0], 0))
                        for k in chiavi])

        pos = alpha > 0
        sd = np.where(pos, np.sqrt(N * alpha * (1 - alpha)), np.nan)
        z = np.where(pos, (rea - att) / np.maximum(sd, 1e-12), np.nan)
        rel = np.where(pos, np.abs(rea - att) / np.maximum(att, 1e-12), np.nan)
        # pavimento di rumore atteso, formula del documento di riferimento
        floor = np.where(pos, np.sqrt((1 - alpha) / np.maximum(alpha * N, 1e-12)),
                         np.nan)

        for k, a, r, zz, e, fl in zip(chiavi, att, rea, z, rel, floor):
            tutte.append({"blocco": " × ".join(nomi),
                          "cella": ", ".join(f"{n}={x}" for n, x in zip(nomi, k)),
                          "atteso": a, "osservato": r, "scarto": r - a,
                          "z": zz, "err_rel": e, "rumore_atteso": fl})

        zz = z[pos]
        sommario.append({
            "blocco": " × ".join(nomi),
            "celle": len(voci),
            "zeri_violati": int(((~pos) & (rea > 0)).sum()),
            "fuori": (N - rea.sum()) / N,
            "MRE_oss": float(np.nanmean(rel)),
            "MRE_att": float(np.nanmean(floor)),
            "z_med": float(np.mean(np.abs(zz))) if zz.size else np.nan,
            "z_max": float(np.max(np.abs(zz))) if zz.size else np.nan,
            "n_z3": int((np.abs(zz) > 3).sum()) if zz.size else 0,
        })

    S = pd.DataFrame(sommario)
    T = pd.DataFrame(tutte)

    riga("Per blocco")
    print(f"{'blocco':<40}{'celle':>6}{'fuori':>8}"
          f"{'MRE oss':>9}{'MRE att':>9}{'|z| med':>9}{'|z| max':>9}{'z>3':>5}")
    print("-" * 95)
    for _, r in S.iterrows():
        print(f"{r.blocco[:39]:<40}{r.celle:>6}{r.fuori:>8.4f}"
              f"{r.MRE_oss:>9.2%}{r.MRE_att:>9.2%}"
              f"{r.z_med:>9.2f}{r.z_max:>9.2f}{r.n_z3:>5}")

    riga("Il pool e' un campione pulito?")
    val = T.dropna(subset=["z"])
    z = val["z"].to_numpy()
    print(f"celle con target positivo    {fmt(len(z)):>10}")
    print()
    print(f"{'':<22}{'osservato':>12}{'atteso':>12}")
    print("-" * 46)
    print(f"{'MRE':<22}{val.err_rel.mean():>12.2%}"
          f"{val.rumore_atteso.mean():>12.2%}")
    print(f"{'|z| medio':<22}{np.abs(z).mean():>12.3f}{ATTESO_ABS_Z:>12.3f}")
    print(f"{'sd(z)':<22}{z.std(ddof=1):>12.3f}{1.0:>12.3f}")
    print(f"{'media(z)':<22}{z.mean():>12.3f}{0.0:>12.3f}")
    print(f"{'|z| > 2':<22}{(np.abs(z) > 2).mean():>12.2%}{0.0455:>12.2%}")
    print(f"{'|z| > 3':<22}{(np.abs(z) > 3).mean():>12.2%}{0.0027:>12.2%}")
    print()
    print("  Se MRE osservato e atteso coincidono, l'errore per cella E' il")
    print("  pavimento di rumore e non c'e' niente da spiegare.")
    print("  sd(z) sopra 1 = pool sovradisperso, cioe' catena autocorrelata:")
    print("  meno informativo di un campione indipendente della stessa taglia.")

    riga(f"Le {args.top} celle piu' lontane dal rumore (|z|)")
    peg = val.reindex(val.z.abs().sort_values(ascending=False).index).head(args.top)
    print(f"{'cella':<58}{'atteso':>9}{'oss':>7}{'z':>8}")
    print("-" * 82)
    for _, r in peg.iterrows():
        print(f"{r.cella[:57]:<58}{r.atteso:>9.1f}{r.osservato:>7.0f}"
              f"{r.z:>+8.2f}")

    viol = T[(T.atteso == 0) & (T.osservato > 0)]
    riga("Zeri hard violati")
    if len(viol) == 0:
        print("nessuno: ogni cella dichiarata impossibile e' vuota.")
    else:
        for _, r in viol.iterrows():
            print(f"  {r.cella[:69]:<70}{r.osservato:>8.0f}")

    if args.out:
        T.reindex(T.z.abs().sort_values(ascending=False).index).to_csv(
            args.out, index=False)
        print(f"\n[info] {fmt(len(T))} celle scritte in {args.out}")


if __name__ == "__main__":
    main()
