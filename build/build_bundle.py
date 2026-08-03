#!/usr/bin/env python3
"""
build_bundle.py — Animarium
============================

Orchestra i quattro passi della costruzione del bundle su tutti i comuni del
registro, e stampa un riepilogo unico.

    to_parquet.py  →  manifest_min.py  →  build_riferimenti.py  →  build_indice.py

Non fonde gli script: li richiama. Restano tutti usabili singolarmente, che e'
quello che serve quando si sta indagando un comune solo.

Perche' serve
-------------
Con undici comuni i comandi a mano diventano 44, e la probabilita' di
dimenticarne uno o di eseguirli fuori ordine tende a uno. Peggio: `deploy.py`
copia il bundle da disco, quindi un comune rigenerato a meta' finisce online
senza che nulla lo segnali.

Cosa fa in piu' rispetto a lanciarli in sequenza
------------------------------------------------
1. **Salta chi e' gia' aggiornato.** Se `pop.parquet` e' piu' recente del CSV
   sorgente, il passo pesante non si rifa'. Con `--forza` si rifa' comunque.

2. **Stampa il livello risolto per comune.** `resolve_pop_file` esclude K10C
   su richiesta, ma l'esclusione e' silenziosa: se un giorno comparisse un
   residuo K11C nessuno se ne accorgerebbe. Il riepilogo lo rende visibile.

3. **Non si ferma al primo errore.** Un comune che fallisce viene segnato e
   si prosegue: e' il comportamento giusto quando si aggiunge una citta' e
   non si sa ancora se i suoi dati sono completi.

Uso
---
    python build/build_bundle.py                  # tutti i comuni del registro
    python build/build_bundle.py 038008 039014    # solo alcuni
    python build/build_bundle.py --forza          # rifa' anche il Parquet
    python build/build_bundle.py --salta-parquet  # solo manifest e riferimenti
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time

QUI = os.path.dirname(os.path.abspath(__file__))
RADICE = os.path.dirname(QUI)


def carica_gsp():
    try:
        import gsp.common as G  # type: ignore
        return G
    except Exception as e:
        sys.exit(f"errore: gsp.common non importabile ({e})")


def esegui(script, argomenti, silenzioso=True):
    """Esegue uno script di build. Restituisce (ok, output)."""
    cmd = [sys.executable, os.path.join(QUI, script)] + argomenti
    p = subprocess.run(cmd, cwd=RADICE, capture_output=True, text=True)
    return p.returncode == 0, (p.stdout or "") + (p.stderr or "")


def da_rifare(comune, anno, G, forza):
    """Il Parquet e' piu' vecchio del CSV sorgente?"""
    par = os.path.join(RADICE, "bundle", "comuni", comune, "pop.parquet")
    if forza or not os.path.exists(par):
        return True, None
    try:
        cdir = G.path_constraints(comune, anno)
        nome = G.resolve_pop_file(cdir, suffisso="_avq_full", escludi=["K10C"])
        src = os.path.join(cdir, nome)
    except SystemExit:
        return False, "sorgente assente"
    if not os.path.exists(src):
        return False, "sorgente assente"
    return os.path.getmtime(src) > os.path.getmtime(par), None


def livello_di(comune, anno, G):
    try:
        nome = G.resolve_pop_file(G.path_constraints(comune, anno),
                                  suffisso="_avq_full", escludi=["K10C"])
    except SystemExit:
        return None
    import re
    m = re.search(r"popolazione_(K\d+C)_", nome)
    return m.group(1) if m else "?"


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("comuni", nargs="*", help="default: tutti quelli del registro")
    ap.add_argument("--anno", default="2024")
    ap.add_argument("--forza", action="store_true",
                    help="rifa' il Parquet anche se e' aggiornato")
    ap.add_argument("--salta-parquet", action="store_true",
                    help="solo manifest e riferimenti")
    ap.add_argument("--verboso", action="store_true",
                    help="mostra l'output di ogni script")
    args = ap.parse_args()

    G = carica_gsp()
    comuni = args.comuni or sorted(G.COMUNI)
    print(f"[bundle] {len(comuni)} comuni · anno {args.anno} · radice {RADICE}")
    print()

    esiti = []
    t0 = time.time()

    for c in comuni:
        try:
            nome = G.info(c)["nome"]
        except KeyError:
            print(f"  {c:<8} NON nel registro, saltato")
            esiti.append({"codice": c, "nome": "?", "stato": "non in registro"})
            continue

        liv = livello_di(c, args.anno, G)
        if liv is None:
            print(f"  {c:<8} {nome:<20} nessuna popolazione _avq_full, saltato")
            esiti.append({"codice": c, "nome": nome, "livello": None,
                          "stato": "sorgente assente"})
            continue

        rifare, motivo = da_rifare(c, args.anno, G, args.forza)
        passi, guasto = [], None

        if not args.salta_parquet and rifare:
            ok, out = esegui("to_parquet.py", [c, "--drop-avq-raw"])
            passi.append("parquet")
            if args.verboso or not ok:
                print(out)
            if not ok:
                guasto = "to_parquet"
        elif not args.salta_parquet:
            passi.append("parquet aggiornato")

        if not guasto:
            ok, out = esegui("manifest_min.py", [c])
            passi.append("manifest")
            if args.verboso or not ok:
                print(out)
            if not ok:
                guasto = "manifest_min"

        if not guasto:
            ok, out = esegui("build_riferimenti.py", [c, "--anno", args.anno])
            passi.append("riferimenti")
            if args.verboso or not ok:
                print(out)
            if not ok:
                guasto = "build_riferimenti"

        stato = "ok" if not guasto else f"errore in {guasto}"
        print(f"  {c:<8} {nome:<20} {liv:<5} {stato:<22} "
              f"{' · '.join(passi)}")
        esiti.append({"codice": c, "nome": nome, "livello": liv,
                      "stato": stato})

    # --- indice, una volta sola -------------------------------------------
    print()
    ok, out = esegui("build_indice.py", [])
    if not ok:
        print(out)
        sys.exit("errore: build_indice fallito")
    print(out.rstrip())

    # --- riepilogo ---------------------------------------------------------
    falliti = [e for e in esiti if e["stato"] != "ok"]
    print()
    print(f"[bundle] {len(esiti) - len(falliti)}/{len(esiti)} comuni in "
          f"{time.time() - t0:.0f} s")
    if falliti:
        print()
        for e in falliti:
            print(f"  {e['codice']:<8} {e['nome']:<20} {e['stato']}")
        print()
        print("  Un comune che fallisce non blocca gli altri: il bundle e'")
        print("  parziale ma coerente, e l'indice elenca solo cio' che c'e'.")

    livelli = {}
    for e in esiti:
        if e["stato"] == "ok":
            livelli[e["livello"]] = livelli.get(e["livello"], 0) + 1
    if len(livelli) > 1:
        print()
        print(f"  Livelli presenti nel bundle: "
              f"{', '.join(f'{k} ×{v}' for k, v in sorted(livelli.items()))}")
        print("  Il pannello si costruisce dal manifest, quindi non nomina mai")
        print("  gli attributi che un livello non ha.")

    print()
    print("  Per pubblicare:  python build/deploy.py  &&  npx wrangler pages "
          "deploy deploy/ --project-name animarium --branch main")
    print("  I due comandi vanno in coppia: deploy.py copia il bundle da disco.")


if __name__ == "__main__":
    main()
