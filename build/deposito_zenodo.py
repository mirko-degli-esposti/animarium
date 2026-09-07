#!/usr/bin/env python3
"""
deposito_zenodo.py — Animarium
================================

Prepara il deposito Zenodo del dataset e, a richiesta, lo carica come BOZZA.

Due sottocomandi
----------------
    python build/deposito_zenodo.py pack   --tag release-v2.0
    python build/deposito_zenodo.py upload --tag release-v2.0 [--sandbox]

`pack` produce in `deposito/<tag>/`:
    animarium_dataset_<tag>.zip     il bundle intero + i report per comune
    SHA256SUMS.txt                  impronta di OGNI file dentro lo zip,
                                    e dello zip stesso in coda
    ATTRIBUZIONI.md                 copia da gsp/fonti/ (obbligo CC-BY)
    LICENSE-DATA.txt                CC-BY-4.0
    README.md                       cosa c'e', come si verifica, come si cita

`upload` crea una NUOVA deposizione su Zenodo, carica i cinque file, imposta
i metadati e SI FERMA: la pubblicazione (che assegna il DOI ed e'
irreversibile) si fa a mano dalla pagina web, dopo aver riletto tutto.
Rilanciato, salta i file gia' presenti nella bozza: e' l'unica forma di
ripresa che l'API offre, ma basta con una rete che cade.

Perche' un solo archivio
------------------------
Zenodo ammette 100 file per record; il bundle ne ha ~1000. I parquet sono
gia' compressi, quindi lo zip e' in modalita' STORED: nessun guadagno da
comprimere, e l'estrazione e' istantanea.

Token
-----
`upload` legge ZENODO_TOKEN dall'ambiente (crearlo su
zenodo.org/account/settings/applications/ con scope deposit:write +
deposit:actions). Con --sandbox usa sandbox.zenodo.org e ZENODO_SANDBOX_TOKEN.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import zipfile
from datetime import date
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent          # ~/progetti/animarium
GSP = Path(os.environ.get("GSP_ROOT", RADICE.parent / "gsp"))

# ---------------------------------------------------------------- metadati --
AUTORE = {
    "name": "Degli Esposti, Mirko",
    "affiliation": "Department of Physics and Astronomy (DIFA), University of Bologna",
    "orcid": os.environ.get("ORCID", ""),        # 0000-0000-0000-0000
}
TITOLO = "Animarium — synthetic populations of {n} Italian municipalities ({tag})"
DESCRIZIONE = """\
<p>Synthetic populations of {n} Italian municipalities — every municipality of
Emilia-Romagna above 3,000 inhabitants, plus Brescia — at the reference date of
1 January 2024: {pop:,} individuals in {hh:,} households, generated from
published aggregates alone (ISTAT census and register tables, census-section
counts, the national address register, public-use survey microdata, municipal
open data) by a maximum-entropy pipeline. Individuals are placed to census
section, year of age and address; households satisfy the census size
distribution section by section.</p>
<p>The archive contains, per municipality, <code>pop.parquet</code> (the public
release regime: no names, no addresses, coordinates randomised within the
census section), <code>manifest.json</code>, <code>riferimenti.json</code>,
<code>rif_nuclei.json</code> and the per-municipality <code>report.md</code>
written by the pipeline, plus the fleet index and national reference means.
<code>SHA256SUMS.txt</code> lists the fingerprint of every file: the release is
reproducible byte for byte from the pipeline at tag <code>{tag}</code>.</p>
<p>Data under CC-BY-4.0, inheriting the attributions in
<code>ATTRIBUZIONI.md</code>. Code (MIT) and viewer: see related identifiers.
Browse the populations at <a href="https://animarium.it">animarium.it</a>.</p>
"""
KEYWORDS = ["synthetic population", "spatial microsimulation", "maximum entropy",
            "open data", "census", "Italy", "Emilia-Romagna", "agent-based modelling"]
RELATED = [   # riempire con gli URL delle release GitHub (o i loro DOI Zenodo)
    {"identifier": "https://github.com/mirko-degli-esposti/gsp/releases/tag/{tag}",
     "relation": "isCompiledBy", "resource_type": "software"},
    {"identifier": "https://github.com/mirko-degli-esposti/Animarium/releases/tag/{tag}",
     "relation": "isDescribedBy", "resource_type": "software"},
]

LICENZA_DATI = """Creative Commons Attribution 4.0 International (CC BY 4.0)

The data files in this deposit are released under CC BY 4.0
(https://creativecommons.org/licenses/by/4.0/). They are derived from
open sources and inherit the attribution requirements listed in
ATTRIBUZIONI.md, which must accompany any redistribution.

Copyright (c) 2025-2026 Mirko Degli Esposti.
"""


# ----------------------------------------------------------------- helpers --
def sha256(p: Path, buf: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while chunk := f.read(buf):
            h.update(chunk)
    return h.hexdigest()


def mb(n: int) -> str:
    return f"{n / 1024 / 1024:.1f} MB"


def comuni_del_bundle(bundle: Path, escludi=frozenset()) -> list[str]:
    return sorted(d.name for d in (bundle / "comuni").iterdir()
                  if d.is_dir() and d.name not in escludi)

def totali(bundle: Path, comuni: list[str]) -> tuple[int, int]:
    """individui dai manifest, nuclei dai diagnostici dell'anello 4."""
    pop = hh = 0
    mancanti = []
    for c in comuni:
        m = json.load(open(bundle / "comuni" / c / "manifest.json"))
        pop += int(m.get("comune", {}).get("individui")
                   or m.get("n_individui") or m.get("individui") or 0)
        dg = GSP / "data" / "nuclei" / f"nuclei_{c}_diagnostica.json"
        if dg.exists():
            hh += int(json.load(open(dg)).get("nuclei") or 0)
        else:
            mancanti.append(c)
    if mancanti:
        print(f"  [avviso] {len(mancanti)} comuni senza diagnostica nuclei: "
              f"{' '.join(mancanti[:8])}" + (" ..." if len(mancanti) > 8 else ""))
    return pop, hh

def flotta_dal_registro() -> set[str]:
    import yaml
    reg = GSP / "flotta" / "comuni.yaml"
    d = yaml.safe_load(open(reg))
    return {k for k, v in d.items() if v.get("stato") in ("flotta", "v2")}

# -------------------------------------------------------------------- pack --
def pack(args: argparse.Namespace) -> None:
    bundle = RADICE / "bundle"
    if not (bundle / "comuni.json").exists():
        sys.exit("errore: manca bundle/comuni.json — esegui build/build_bundle.py")
    ammessi = flotta_dal_registro()
    comuni = [c for c in comuni_del_bundle(bundle) if c in ammessi]
    out = RADICE / "deposito" / args.tag
    out.mkdir(parents=True, exist_ok=True)

    # 1. inventario di cosa entra nello zip: (path su disco, nome nell'archivio)
    entrate: list[tuple[Path, str]] = []
    for c in comuni:
        d = bundle / "comuni" / c
        for f in sorted(d.iterdir()):
            if f.suffix in (".parquet", ".json"):
                entrate.append((f, f"comuni/{c}/{f.name}"))
        rep = GSP / "data" / "comuni" / c / f"constraints_{args.anno}" / "report.md"
        if rep.exists():
            entrate.append((rep, f"comuni/{c}/report.md"))
        else:
            print(f"  [avviso] manca report.md per {c}")
    for nome in ("comuni.json", "medie_nazionali.json"):
        if (bundle / nome).exists():
            entrate.append((bundle / nome, nome))

    manca = [c for c in comuni if not (bundle / "comuni" / c / "rif_nuclei.json").exists()]
    if manca:
        print(f"  [avviso] {len(manca)} comuni senza rif_nuclei.json: {' '.join(manca[:8])}"
              + (" ..." if len(manca) > 8 else ""))

    # 2. impronte di ogni file (prima dello zip, cosi' SHA256SUMS descrive il contenuto)
    righe = []
    tot = 0
    for p, nome in entrate:
        righe.append(f"{sha256(p)}  {nome}")
        tot += p.stat().st_size
    print(f"assemblo {len(entrate)} file, {len(comuni)} comuni, {mb(tot)} non compressi")

    if args.dry_run:
        for _, nome in entrate[:12]:
            print("   ", nome)
        print("    ...")
        return

    # 3. lo zip, in modalita' STORED e in ordine deterministico
    zpath = out / f"animarium_dataset_{args.tag}.zip"
    with zipfile.ZipFile(zpath, "w", compression=zipfile.ZIP_STORED) as z:
        for p, nome in entrate:
            z.write(p, nome)
    righe.append(f"{sha256(zpath)}  {zpath.name}")
    (out / "SHA256SUMS.txt").write_text("\n".join(righe) + "\n")

    # 4. i file sciolti
    attr = GSP / "fonti" / "ATTRIBUZIONI.md"
    if attr.exists():
        shutil.copy(attr, out / "ATTRIBUZIONI.md")
    else:
        print("  [avviso] manca gsp/fonti/ATTRIBUZIONI.md — rigenerarlo con "
              "`python -m gsp.fonti --attribuzioni`")
    (out / "LICENSE-DATA.txt").write_text(LICENZA_DATI)

    pop, hh = totali(bundle, comuni)
    readme = f"""# Animarium — synthetic populations, {args.tag}

{len(comuni)} municipalities · {pop:,} individuals · {hh:,} households ·
reference date 1 January {args.anno}

## Contents

- `animarium_dataset_{args.tag}.zip` — one folder per municipality
  (`comuni/<ISTAT code>/`) with `pop.parquet`, `manifest.json`,
  `riferimenti.json`, `rif_nuclei.json`, `report.md`; plus `comuni.json`
  (fleet index) and `medie_nazionali.json` (national reference means).
- `SHA256SUMS.txt` — fingerprint of every file in the archive, and of the
  archive itself. Verify with `sha256sum -c SHA256SUMS.txt` after extraction.
- `ATTRIBUZIONI.md` — the attributions this data inherits (CC-BY).
- `LICENSE-DATA.txt` — CC-BY-4.0.

## Provenance

Generated by the GSP pipeline at tag `{args.tag}`
(https://github.com/mirko-degli-esposti/gsp) from published ISTAT
aggregates and municipal open data alone. Every file is reproducible byte
for byte from that tag; the pipeline's per-municipality `report.md`
records the sources, the fit and the checks for each municipality.

The populations are simulated from aggregates, not anonymised from
records: no released component derives from an identifiable person.
This deposit is the **public** regime: no names, no street addresses,
coordinates randomised within the census section.

## Browse

https://animarium.it — every view is a citable URL.

## Cite

Degli Esposti, M. ({date.today().year}). Animarium — synthetic populations of
{len(comuni)} Italian municipalities ({args.tag}) [Data set]. Zenodo.
https://doi.org/[DOI assigned on publication]
"""
    (out / "README.md").write_text(readme)

    print(f"\npronto in {out}/")
    for f in sorted(out.iterdir()):
        print(f"  {f.name:<40} {mb(f.stat().st_size):>10}")
    print("\nprossimo passo: python build/deposito_zenodo.py upload --tag", args.tag)


# ------------------------------------------------------------------ upload --
def upload(args: argparse.Namespace) -> None:
    try:
        import requests
    except ImportError:
        sys.exit("pip install requests")

    base = "https://sandbox.zenodo.org" if args.sandbox else "https://zenodo.org"
    tok = os.environ.get("ZENODO_SANDBOX_TOKEN" if args.sandbox else "ZENODO_TOKEN")
    if not tok:
        sys.exit("manca il token: export ZENODO_TOKEN=... (o ZENODO_SANDBOX_TOKEN)")
    H = {"Authorization": f"Bearer {tok}"}
    out = RADICE / "deposito" / args.tag
    if not out.exists():
        sys.exit(f"manca {out}: esegui prima `pack`")

    stato = out / ".zenodo_deposition.json"
    if stato.exists():                       # ripresa: riusa la bozza
        dep = json.load(open(stato))
        print(f"riprendo la bozza {dep['id']}")
    else:
        r = requests.post(f"{base}/api/deposit/depositions", json={}, headers=H)
        r.raise_for_status()
        dep = r.json()
        json.dump(dep, open(stato, "w"))
        print(f"creata la bozza {dep['id']}: {dep['links']['html']}")

    bucket = dep["links"]["bucket"]
    presenti = {f["filename"] for f in requests.get(
        f"{base}/api/deposit/depositions/{dep['id']}/files", headers=H).json()}

    for f in sorted(out.iterdir()):
        if f.name.startswith("."):
            continue
        if f.name in presenti:
            print(f"  gia' caricato: {f.name}")
            continue
        print(f"  carico {f.name} ({mb(f.stat().st_size)}) ...", end="", flush=True)
        with open(f, "rb") as fh:
            r = requests.put(f"{bucket}/{f.name}", data=fh, headers=H)
        r.raise_for_status()
        print(" ok")

    comuni = comuni_del_bundle(RADICE / "bundle", set(args.escludi))
    pop, hh = totali(RADICE / "bundle", comuni)
    meta = {"metadata": {
        "title": TITOLO.format(n=len(comuni), tag=args.tag),
        "upload_type": "dataset",
        "description": DESCRIZIONE.format(n=len(comuni), tag=args.tag, pop=pop, hh=hh),
        "creators": [{k: v for k, v in AUTORE.items() if v}],
        "license": "cc-by-4.0",
        "keywords": KEYWORDS,
        "version": args.tag.replace("release-v", ""),
        "language": "eng",
        "related_identifiers": [
            {**ri, "identifier": ri["identifier"].format(tag=args.tag)} for ri in RELATED],
    }}
    r = requests.put(f"{base}/api/deposit/depositions/{dep['id']}", json=meta, headers=H)
    r.raise_for_status()
    print(f"\nmetadati impostati. NON pubblicato.")
    print(f"rileggi e pubblica da: {dep['links']['html']}")
    print("la pubblicazione assegna il DOI ed e' irreversibile.")


# -------------------------------------------------------------------- main --
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pack", help="assembla deposito/<tag>/")
    p.add_argument("--tag", required=True)
    p.add_argument("--anno", type=int, default=2024)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--escludi", nargs="*", default=[],
                   help="codici ISTAT da non depositare (collaudo, pilota, sotto soglia)")
    p.set_defaults(fn=pack)
    u = sub.add_parser("upload", help="crea la BOZZA su Zenodo e carica i file")
    u.add_argument("--tag", required=True)
    u.add_argument("--sandbox", action="store_true")
    u.add_argument("--escludi", nargs="*", default=[],
                   help="codici ISTAT da non depositare (collaudo, pilota, sotto soglia)")
    u.set_defaults(fn=upload)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
