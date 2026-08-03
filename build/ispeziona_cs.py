#!/usr/bin/env python3
"""
ispeziona_cs.py — Animarium / GSP
==================================

Legge `cs_K9C.json` e risponde a una domanda sola: **le combinazioni
logicamente impossibili sono vincolate a zero, o semplicemente non sono mai
state vincolate?**

La differenza conta. Se un blocco copre la coppia e il target e' esattamente
zero, un vincolo hard e' stato violato dall'arrotondamento a interi del
largest remainder: e' un fatto sul fit. Se il blocco non esiste, la cella sta
nel supporto per default e non doveva esserci: benigno, e si chiude
aggiungendola alle esclusioni alpha=0.

Struttura del file
------------------
    vars        i 9 attributi, in ordine; gli indici di `attrs` puntano qui
    categories  le modalita' di ciascuno; gli indici di `vals` puntano qui
    constraints tavole marginali sparse: attrs (quali variabili),
                vals (quale cella), alpha (probabilita' target)

Attenzione: le categorie **non sono in ordine naturale**. In `eta`, "0-8" e'
l'indice 0 ma "9-14" e' l'ultimo. Questo script lavora sempre per nome.

Uso
---
    python build/ispeziona_cs.py 036023
    python build/ispeziona_cs.py 034027 --anno 2024
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import sys

GSP = os.path.expanduser("~/progetti/gsp/data/comuni")

# combinazioni logicamente impossibili, per nome.
# (variabile A, valori A, variabile B, valori B, motivo)
import gsp.common as G

IMPOSSIBILI = G.IMPOSSIBILI


def carica(comune, anno, percorso):
    f = percorso or os.path.join(GSP, comune, f"constraints_{anno}",
                                 "cs_K9C.json")
    if not os.path.exists(f):
        sys.exit(f"errore: non trovato {f}")
    print(f"[info] {f}")
    with open(f, encoding="utf-8") as h:
        return json.load(h)


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
    args = ap.parse_args()

    cs = carica(args.comune, args.anno, args.cs)
    vars_ = cs["vars"]
    cats = cs["categories"]
    ivar = {v: i for i, v in enumerate(vars_)}
    icat = {v: {c: i for i, c in enumerate(cats[v])} for v in vars_}

    print(f"[info] livello {cs.get('livello')} · "
          f"popolazione {cs.get('pop_size'):,}".replace(",", "."))

    # --- blocchi ----------------------------------------------------------
    blocchi = collections.defaultdict(list)
    for c in cs["constraints"]:
        blocchi[tuple(c["attrs"])].append(c)

    riga("Blocchi del constraint set")
    print(f"{'variabili':<58}{'celle':>7}{'zeri':>7}{'somma α':>10}")
    print("-" * 82)
    for attrs in sorted(blocchi, key=lambda a: (len(a), a)):
        voci = blocchi[attrs]
        nomi = " × ".join(vars_[i] for i in attrs)
        zeri = sum(1 for c in voci if c["alpha"] == 0.0)
        tot = sum(c["alpha"] for c in voci)
        print(f"{nomi[:57]:<58}{len(voci):>7}{zeri:>7}{tot:>10.6f}")
    n_zero = sum(1 for c in cs["constraints"] if c["alpha"] == 0.0)
    print(f"\ntotale: {len(blocchi)} blocchi, {len(cs['constraints'])} celle, "
          f"{n_zero} con α esattamente 0")
    print("La somma α per blocco deve fare 1 solo se il blocco e' una")
    print("distribuzione completa. Blocchi complementari si sommano a coppie")
    print("(eta × X e sesso × eta × X), e le tavole parziali stanno sotto 1")
    print("per costruzione: vincolano un sottoinsieme di celle, il resto")
    print("resta libero.")

    # --- il test ----------------------------------------------------------
    riga("Le combinazioni impossibili sono vincolate?")

    for va, valsA, vb, valsB, motivo in IMPOSSIBILI:
        if va not in ivar or vb not in ivar:
            continue
        ia, ib = ivar[va], ivar[vb]
        coinvolti = [a for a in blocchi if ia in a and ib in a]
        etichetta = f"{va} ∈ {valsA[:2]}{'…' if len(valsA) > 2 else ''}  ×  " \
                    f"{vb} ∈ {valsB[:2]}{'…' if len(valsB) > 2 else ''}"
        print(f"\n{etichetta}")
        print(f"  motivo: {motivo}")

        if not coinvolti:
            print(f"  -> NESSUN BLOCCO copre insieme {va} e {vb}.")
            print(f"     La coppia non e' mai stata vincolata: le celle stanno")
            print(f"     nel supporto per default. Benigno, si chiude con")
            print(f"     l'esclusione α=0.")
            continue

        for attrs in coinvolti:
            nomi = " × ".join(vars_[i] for i in attrs)
            pa = attrs.index(ia)
            pb = attrs.index(ib)
            codA = {icat[va][v] for v in valsA if v in icat[va]}
            codB = {icat[vb][v] for v in valsB if v in icat[vb]}
            sel = [c for c in blocchi[attrs]
                   if c["vals"][pa] in codA and c["vals"][pb] in codB]
            tot = sum(c["alpha"] for c in sel)
            nz = [c for c in sel if c["alpha"] > 0.0]
            print(f"  blocco {nomi}")
            print(f"    celle impossibili nel blocco: {len(sel)}")
            print(f"    somma dei target:             {tot:.10g}")
            if not sel:
                print("    -> il blocco non contiene quelle celle")
            elif tot == 0.0:
                print("    -> VINCOLATE A ZERO. Un vincolo hard e' stato")
                print("       violato: e' l'arrotondamento del largest")
                print("       remainder, ed e' un fatto sul fit.")
            else:
                print(f"    -> TARGET POSITIVO su {len(nz)} celle. Il "
                      f"censimento\n       stesso riporta qualcuno li'.")
                for c in sorted(nz, key=lambda x: -x["alpha"])[:5]:
                    cella = ", ".join(
                        f"{vars_[a]}={cats[vars_[a]][v]}"
                        for a, v in zip(attrs, c["vals"]))
                    print(f"       α={c['alpha']:.3e}  ({cella})")

    # --- promemoria -------------------------------------------------------
    riga("Esclusioni α=0 da aggiungere")
    tot = 0
    for va, valsA, vb, valsB, _ in IMPOSSIBILI:
        n = len(valsA) * len(valsB)
        tot += n
        print(f"  {va} × {vb}: {len(valsA)} × {len(valsB)} = {n:>3}")
    print(f"  {'totale':<28}{tot:>3}")
    print("\nAggiungerle cambia il conteggio delle celle escluse, quindi la")
    print("formula di controllo di §12 del riferimento va aggiornata.")


if __name__ == "__main__":
    main()
