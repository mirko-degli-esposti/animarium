#!/usr/bin/env python3
"""
build_riferimenti.py — Animarium, F4
=====================================

Estrae i **conteggi censuari** dal constraint set e li mette nel bundle.

L'idea che semplifica F4: non serve procurarsi tavole di zona da fonti
esterne, perche' sono gia' in `cs_K9C.json`. Ogni `alpha` moltiplicato per N
e' un conteggio del censimento, e i blocchi disponibili includono
`zona × sesso × eta`, `zona × sesso × istruzione`, `zona × sesso × background`
e `zona × sesso × eta × cittadinanza`. Filtrando un quartiere si puo' quindi
affiancare il dato reale a quello sintetico, su parecchi attributi.

Come il pannello lo usa
-----------------------
Dato un filtro F (insieme di attributi con modalita' selezionate) e un
attributo mostrato A, esiste un riferimento se e solo se **un blocco contiene
tutti gli attributi di F piu' A**. Allora si marginalizza il blocco sulle
celle compatibili con F e si raggruppa per A.

Se non esiste, il pannello lo dichiara: e' l'informazione piu' onesta che
possa dare, perche' dice esattamente quali incroci sono osservati e quali
sono modello.

Blocchi parziali
----------------
Alcuni blocchi coprono solo un sottoinsieme di celle: `eta × istruzione` ha
una cella sola (l'universo sotto i 9 anni), `zona × sesso × eta × condizione`
solo gli occupati fra 15 e 64 anni. Le celle non elencate **non sono vietate,
sono libere**, e un riferimento parziale non si puo' normalizzare come una
distribuzione. Vengono marcati `completo: false` e il pannello li tratta
diversamente.

Uso
---
    python build/build_riferimenti.py 036023
"""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import itertools
import json
import os
import sys

GSP = os.path.expanduser("~/progetti/gsp/data/comuni")

# attributi che il pannello mostra; la copertura si riporta su questi
MOSTRATI = ["zona", "sesso", "eta", "stato_civile", "cittadinanza",
            "istruzione", "condizione", "background", "origine_genitori"]


def riga(t):
    print()
    print(t)
    print("-" * len(t))


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("comune")
    ap.add_argument("--anno", default="2024")
    ap.add_argument("--cs", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--tol", type=float, default=1e-6,
                    help="tolleranza per considerare completo un blocco")
    args = ap.parse_args()

    f_cs = args.cs or os.path.join(GSP, args.comune, f"constraints_{args.anno}",
                                   "cs_K9C.json")
    if not os.path.exists(f_cs):
        sys.exit(f"errore: constraint set non trovato: {f_cs}")
    out = args.out or os.path.join("bundle", "comuni", args.comune,
                                   "riferimenti.json")

    with open(f_cs, encoding="utf-8") as h:
        cs = json.load(h)
    V, C, N = cs["vars"], cs["categories"], cs["pop_size"]
    print(f"[info] {f_cs}")
    print(f"[info] livello {cs.get('livello')} · N = {N:,}".replace(",", "."))

    raw = collections.defaultdict(list)
    for c in cs["constraints"]:
        raw[tuple(c["attrs"])].append(c)

    blocchi = []
    for attrs in sorted(raw, key=lambda a: (len(a), a)):
        nomi = [V[i] for i in attrs]
        voci = raw[attrs]
        massa = sum(c["alpha"] for c in voci)
        celle = [{"k": [C[V[a]][v] for a, v in zip(attrs, c["vals"])],
          "n": round(c["alpha"] * N, 2)}
         for c in voci]
        blocchi.append({"vars": nomi,
                        "completo": abs(massa - 1.0) < args.tol,
                        "massa": round(massa, 8),
                        "n_celle": len(celle),
                        "celle": celle})

    rif = {
        "generato": dt.datetime.now().isoformat(timespec="seconds"),
        "fonte": os.path.basename(f_cs),
        "nota": ("Conteggi censuari estratti dal constraint set: n = alpha × N. "
                 "Un riferimento esiste per (filtro F, attributo A) se e solo "
                 "se un blocco contiene F ∪ {A}. I blocchi non completi "
                 "coprono solo un sottoinsieme di celle: le altre non sono "
                 "vietate, sono libere."),
        "N": N,
        "blocchi": blocchi,
    }

    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(rif, f, ensure_ascii=False, separators=(",", ":"))
    print(f"[info] scritto {out} "
          f"({os.path.getsize(out) / 1024:.1f} KB, "
          f"{sum(b['n_celle'] for b in blocchi)} celle)")

    riga("Blocchi")
    print(f"{'variabili':<48}{'celle':>7}{'massa':>9}  stato")
    print("-" * 76)
    for b in blocchi:
        print(f"{' × '.join(b['vars'])[:47]:<48}{b['n_celle']:>7}"
              f"{b['massa']:>9.4f}  "
              f"{'completo' if b['completo'] else 'parziale'}")

    # --- copertura: dato un filtro, quali attributi hanno un riferimento? ---
    completi = [set(b["vars"]) for b in blocchi if b["completo"]]

    def coperto(F, A):
        want = set(F) | {A}
        return any(want <= v for v in completi)

    riga("Copertura — filtro sulle righe, attributo mostrato sulle colonne")
    filtri = [(), ("zona",), ("sesso",), ("zona", "sesso"),
              ("sesso", "eta"), ("cittadinanza",), ("zona", "sesso", "eta")]
    intest = [a[:6] for a in MOSTRATI]
    print(f"{'filtro':<26}" + "".join(f"{h:>8}" for h in intest))
    print("-" * (26 + 8 * len(MOSTRATI)))
    for F in filtri:
        et = " × ".join(F) if F else "(nessuno)"
        celle = ["" if a in F else ("  ✔" if coperto(F, a) else "  ·")
                 for a in MOSTRATI]
        print(f"{et[:25]:<26}" + "".join(f"{c:>8}" for c in celle))
    print("\n  ✔ = esiste un blocco completo che contiene filtro e attributo,")
    print("      quindi il conteggio censuario si puo' affiancare al sintetico")
    print("  · = incrocio non osservato: e' modello, e il pannello lo dichiara")
    print("      (vuoto = l'attributo e' nel filtro)")

    # --- quante coppie sono coperte, in generale ---------------------------
    tot = cop = 0
    for r in range(0, 3):
        for F in itertools.combinations(MOSTRATI, r):
            for A in MOSTRATI:
                if A in F:
                    continue
                tot += 1
                cop += coperto(F, A)
    print(f"\nSu tutte le combinazioni con al piu' 2 attributi di filtro: "
          f"{cop}/{tot} coperte ({cop / tot:.0%}).")


if __name__ == "__main__":
    main()
