#!/usr/bin/env python3
"""
deploy.py — Animarium
======================

Assembla la cartella pubblicabile e, opzionalmente, la pubblica.

Due bersagli
------------
`--cloudflare` (canonico): consegna `deploy/` a Cloudflare Pages via
`npx wrangler`. E' la via della release: il sito vive su animarium.it,
i file restano statici, git non c'entra.

`--gh-pages` (storico, di riserva): pubblica su un ramo `gh-pages`
**usa-e-getta**. Nato prima di Cloudflare e tenuto come ripiego.

Perche' il bundle non si committa su `main`
-------------------------------------------
I Parquet non si comprimono in delta: ogni rigenerazione aggiungerebbe
~16 MB alla storia di git, per sempre. Dopo cinque cicli il repo pesa
100 MB e non si torna indietro senza riscrivere la storia. Con
`--cloudflare` il problema non si pone (i file non passano da git); con
`--gh-pages` la cartella `deploy/` viene inizializzata come repo a se'
stante, spinta con `--force`, e il suo `.git` buttato via: ogni
pubblicazione e' un commit solo che sostituisce il precedente, quindi la
storia non cresce mai e `main` resta pulito con codice e note.

Cosa finisce online
-------------------
    index.html          il pannello (rinominato)
    smoke.html          lo smoke test, per verificare che l'host supporti
                        le richieste Range: senza, DuckDB scaricherebbe i
                        file interi e l'app sarebbe lenta senza dire perche'
    bundle/             Parquet, manifest, riferimenti, indice
    .nojekyll           serve solo a GitHub Pages (ignora i file che
                        iniziano con _); su Cloudflare e' inerte

Il pannello cerca il bundle prima in `bundle/` e poi in `../bundle/`, quindi
lo stesso file funziona sia in locale sia pubblicato.

Uso
---
    python build/deploy.py                 # assembla soltanto
    python build/deploy.py --cloudflare    # assembla e pubblica (canonico)
    python build/deploy.py --gh-pages      # assembla e pubblica sul ramo
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys

RADICE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def mb(n):
    return f"{n / 1024 / 1024:.2f} MB"


def peso(percorso):
    t = 0
    for r, _, f in os.walk(percorso):
        for x in f:
            t += os.path.getsize(os.path.join(r, x))
    return t


def esegui(cmd, cwd):
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if p.returncode:
        print(p.stdout)
        print(p.stderr, file=sys.stderr)
        sys.exit(f"errore: {' '.join(cmd)}")
    return p.stdout.strip()


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cloudflare", action="store_true",
                    help="pubblica su Cloudflare Pages (via wrangler): la via canonica")
    ap.add_argument("--progetto", default="animarium",
                    help="nome del progetto Cloudflare Pages")
    ap.add_argument("--gh-pages", dest="push", action="store_true",
                    help="pubblica sul ramo gh-pages (via storica, non canonica)")
    ap.add_argument("--repo", default=None,
                    help="repo di destinazione per --gh-pages")
    ap.add_argument("--branch", default="gh-pages")
    ap.add_argument("--out", default="deploy")
    args = ap.parse_args()

    os.chdir(RADICE)
    bundle = "bundle"
    if not os.path.isdir(bundle):
        sys.exit("errore: manca bundle/. Rigeneralo prima di pubblicare.")
    if not os.path.exists(os.path.join(bundle, "comuni.json")):
        sys.exit("errore: manca bundle/comuni.json. "
                 "Esegui build/build_indice.py")

    out = args.out
    if os.path.isdir(out):
        shutil.rmtree(out)
    os.makedirs(out)

    shutil.copy("build/pannello_marginali.html", os.path.join(out, "index.html"))
    if os.path.exists("build/smoke_duckdb.html"):
        shutil.copy("build/smoke_duckdb.html", os.path.join(out, "smoke.html"))
    shutil.copytree(bundle, os.path.join(out, "bundle"))

    # medie_nazionali.jsonsta arriva da build_bundle
    # ; se manca, il pannello non mostra le tacche di riferimento e lo
    # dichiara invece di tacere.
    if not os.path.exists(os.path.join(out, "bundle", "medie_nazionali.json")):
        print("[avviso] manca bundle/medie_nazionali.json: le tacche delle "
              "medie nazionali non compariranno")
        print("         lo copia build_bundle.py da "
              "$GSP_ROOT/fonti/derivati/ (default ~/progetti/gsp)")
    open(os.path.join(out, ".nojekyll"), "w").close()

    # --- inventario -------------------------------------------------------
    print(f"assemblata {out}/")
    print()
    tot = 0
    for d in sorted(os.listdir(os.path.join(out, "bundle", "comuni"))):
        p = os.path.join(out, "bundle", "comuni", d)
        if os.path.isdir(p):
            n = peso(p)
            tot += n
            print(f"  {d:<10} {mb(n):>10}")
    print(f"  {'totale':<10} {mb(peso(out)):>10}")
    print()
    print("  Ogni visitatore ne scarica ~2,5 MB: i blocchi non toccati")
    print("  non vengono mai letti (modello di costo, §7.2 del design).")

    grossi = [(os.path.join(r, f), os.path.getsize(os.path.join(r, f)))
              for r, _, fs in os.walk(out) for f in fs
              if os.path.getsize(os.path.join(r, f)) > 50 * 1024 * 1024]
    if grossi:
        print("\n[avviso] file oltre 50 MB: GitHub ne rifiuta oltre 100")
        for p, n in grossi:
            print(f"  {p} {mb(n)}")

    if args.cloudflare:
        import subprocess
        r = subprocess.run(["npx", "wrangler", "pages", "deploy", out,
                            "--project-name", args.progetto], cwd=RADICE)
        print("\nVerifica le richieste Range sul sito pubblicato:")
        print("  <dominio>/smoke.html   — Q5 deve costare ~0,9 MB e non 3")
        if r.returncode:
            raise SystemExit("wrangler ha fallito")
        return
    
    if not args.push:
        print(f"\nPer provare in locale:")
        print(f"  python build/serve_range.py --dir {out}")
        print(f"  http://localhost:8000/index.html")
        print(f"\nPer pubblicare: python build/deploy.py --cloudflare")
        return

    # --- pubblicazione ----------------------------------------------------
    repo = args.repo or esegui(["git", "remote", "get-url", "origin"], RADICE)
    print(f"\npubblico su {repo} ramo {args.branch}")

    esegui(["git", "init", "-q", "-b", "main"], out)
    esegui(["git", "add", "-A"], out)
    esegui(["git", "-c", "user.name=animarium",
            "-c", "user.email=animarium@local",
            "commit", "-qm", "deploy"], out)
    esegui(["git", "push", "-f", repo, f"main:{args.branch}"], out)
    shutil.rmtree(os.path.join(out, ".git"))

    nome = repo.split(":")[-1].replace(".git", "")
    utente, prog = nome.split("/")
    print(f"\nfatto (via storica gh-pages). Per servirlo, in Settings → Pages:")
    print(f"  Source: Deploy from a branch · Branch: {args.branch} · / (root)")
    print(f"  indirizzo: https://{utente.lower()}.github.io/{prog}/")
    print(f"\nVerifica che l'host supporti le richieste Range, altrimenti")
    print(f"DuckDB scarichera' i file interi:")
    print(f"  https://{utente.lower()}.github.io/{prog}/smoke.html")
    print(f"Nel pannello di rete del browser, Q5 deve costare ~0,9 MB e non 3.")
    print(f"\nLa via canonica e' invece: python build/deploy.py --cloudflare")


if __name__ == "__main__":
    main()
