#!/usr/bin/env python3
"""
deposito_zenodo.py — Animarium
================================

Prepara il deposito Zenodo del dataset e, a richiesta, lo carica come BOZZA.

Due sottocomandi
----------------
    python build/deposito_zenodo.py pack   --tag release-v2.1 [--variabilita F]
    python build/deposito_zenodo.py upload --tag release-v2.1 \
                                           [--nuova-versione-di ID] [--sandbox]

`pack` produce in `deposito/<tag>/`:
    animarium_dataset_<tag>.zip     il bundle intero + i report per comune
    SHA256SUMS.txt                  impronta di OGNI file dentro lo zip,
                                    e dello zip stesso in coda
    ATTRIBUZIONI.md                 copia da gsp/fonti/ (obbligo CC-BY)
    LICENSE-DATA.txt                CC-BY-4.0
    README.md                       cosa c'e', come si verifica, come si cita
e, se ci sono (dalla v2.1):
    animarium_replicates_<tag>.zip  le repliche con altri semi, esportate da
                                    build/esporta_repliche.py: facoltativo
    SHA256SUMS-replicates.txt       impronte dei file delle repliche
    variabilita_sezioni.csv.gz      media e sd fra repliche, per sezione
                                    (--variabilita: la tabella sta nel
                                    repository del paper)

`upload` crea una deposizione su Zenodo, carica i file, imposta i metadati
e SI FERMA. Con `--nuova-versione-di ID` (l'id di una versione pubblicata,
per la v2.0 e' 22647404) la bozza e' una NUOVA VERSIONE dello stesso record:
stesso concept DOI, nuovo version DOI; i file ereditati dalla versione
precedente vengono tolti dalla bozza. Senza, e' un record nuovo. In ogni caso la pubblicazione (che assegna il DOI ed e'
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
<p>Synthetic populations of {n} Italian municipalities — all 330
municipalities of Emilia-Romagna, plus Brescia — at the reference date of
1 January 2024: {pop:,} individuals in {hh:,} households, generated from
published aggregates alone (ISTAT census and register tables, census-section
counts, the national address register, public-use survey microdata, municipal
open data) by a maximum-entropy pipeline. Individuals are placed to census
section, year of age and address; households are built section by section
against the census household-size distribution.</p>
<p><code>animarium_dataset_{tag}.zip</code> is the release. It contains, per
municipality, <code>pop.parquet</code> (the public release regime: no names,
no addresses, coordinates randomised within the census section),
<code>manifest.json</code>, <code>riferimenti.json</code>,
<code>rif_nuclei.json</code> and the per-municipality <code>report.md</code>
written by the pipeline, plus the fleet index and national reference means.
<code>SHA256SUMS.txt</code> lists the fingerprint of every file: the release is
reproducible byte for byte from the pipeline at tag <code>{tag}</code>.</p>
{repliche}<p><strong>Changes since v2.0.</strong> (1) 86 municipalities added: the
v2.0 archive held 245, this one holds all 330 municipalities of the region,
plus Brescia. Quality degrades gradually as municipalities get smaller; the
accompanying paper reports it by population band. (2) Single year of age
corrected: within each five-year class, years of age now follow the municipal
register distribution, which v2.0 distorted. Age classes, and every other
attribute of the individuals, are unchanged in the 245 municipalities of v2.0;
households were regenerated. (3) In three very small municipalities
(Montecopiolo, Casteldelci, Zerba) the fit is computed by iterative
proportional fitting, because the dual solver does not converge there.</p>
<p>Data under CC-BY-4.0, inheriting the attributions in
<code>ATTRIBUZIONI.md</code>. Code (MIT) and viewer: see related identifiers.
Browse the populations at <a href="https://animarium.it">animarium.it</a>.</p>
"""
DESCR_REPLICHE = """\
<p><code>animarium_replicates_{tag}.zip</code> is optional. The release is one
draw (production seed); this archive holds {nrep} more draws of every
municipality, generated by the same chain with seeds 1–{nrep} and exported in
the same public regime (<code>sNN/comuni/&lt;code&gt;/pop.parquet</code>, with
<code>provenienza.csv</code> recording the run, the commit and the fingerprint
of each file). <code>variabilita_sezioni.csv.gz</code> summarises them for
those who do not want to handle eleven populations: for every census section,
the count in the release and the mean and standard deviation across the eleven
draws of residents, foreign citizens, residents aged 75 and over, those aged
75 and over living alone, and those aged 75 and over with at most lower
secondary education. Counts that cross attributes or households vary by
20–40% from draw to draw at the scale of a single section, and stabilise only
when sections are aggregated.</p>
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
    # l'indice del bundle elenca anche i comuni che il viewer mostra ma il
    # deposito non contiene (collaudo): nell'archivio va solo chi c'e'
    ind = json.load(open(bundle / "comuni.json"))
    fuori = [c["nome"] for c in ind["comuni"] if c["codice"] not in comuni]
    ind["comuni"] = [c for c in ind["comuni"] if c["codice"] in comuni]
    if len(ind["comuni"]) != len(comuni):
        sys.exit("errore: l'indice del bundle non copre i comuni del deposito")
    if fuori:
        print(f"  indice: tolti {len(fuori)} comuni fuori deposito ({', '.join(fuori)})")
    f_ind = out / ".comuni.json"
    f_ind.write_text(json.dumps(ind, ensure_ascii=False, indent=1) + "\n")
    entrate.append((f_ind, "comuni.json"))
    if (bundle / "medie_nazionali.json").exists():
        entrate.append((bundle / "medie_nazionali.json", "medie_nazionali.json"))

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

    # 3b. le repliche, se esportate (build/esporta_repliche.py): archivio a parte
    rep = RADICE / "deposito" / f"_repliche_{args.tag}"
    nrep = 0
    if (rep / "provenienza.csv").exists():
        semi = sorted(d.name for d in rep.iterdir() if d.is_dir())
        nrep = len(semi)
        ent_r = [(rep / "provenienza.csv", "provenienza.csv")]
        for sd in semi:
            presenti = sorted(d.name for d in (rep / sd / "comuni").iterdir())
            if presenti != comuni:
                sys.exit(f"errore: le repliche {sd} non coprono i {len(comuni)} comuni")
            ent_r += [(rep / sd / "comuni" / c / "pop.parquet",
                       f"{sd}/comuni/{c}/pop.parquet") for c in comuni]
        righe_r = [f"{sha256(p)}  {nome}" for p, nome in ent_r]
        zrep = out / f"animarium_replicates_{args.tag}.zip"
        with zipfile.ZipFile(zrep, "w", compression=zipfile.ZIP_STORED) as z:
            for p, nome in ent_r:
                z.write(p, nome)
        righe_r.append(f"{sha256(zrep)}  {zrep.name}")
        (out / "SHA256SUMS-replicates.txt").write_text("\n".join(righe_r) + "\n")
        print(f"repliche: {nrep} semi, {len(ent_r)} file")
    else:
        print("  [avviso] nessuna replica esportata: deposito senza archivio delle repliche")
    if args.variabilita:
        shutil.copy(args.variabilita, out / "variabilita_sezioni.csv.gz")

    # 4. i file sciolti
    attr = GSP / "fonti" / "ATTRIBUZIONI.md"
    if attr.exists():
        shutil.copy(attr, out / "ATTRIBUZIONI.md")
    else:
        print("  [avviso] manca gsp/fonti/ATTRIBUZIONI.md — rigenerarlo con "
              "`python -m gsp.fonti --attribuzioni`")
    (out / "LICENSE-DATA.txt").write_text(LICENZA_DATI)

    pop, hh = totali(bundle, comuni)
    testo_repliche = "" if not nrep else f"""
## Replicates (optional)

The release is one draw of each population (production seed). Two files
say how much a different draw would change it.

- `animarium_replicates_{args.tag}.zip` — {nrep} more draws of every
  municipality (seeds 1–{nrep}), same chain, same public regime:
  `sNN/comuni/<ISTAT code>/pop.parquet`, same columns as the release.
  `provenienza.csv` gives, per file, the pipeline run, its commit, the
  number of individuals and households and the SHA-256.
  `SHA256SUMS-replicates.txt` verifies the extracted archive.
  The replicates were produced at pipeline commit `c972091` (branch
  `misure-ijm`), whose generation chain is identical to tag `{args.tag}`:
  with the production seed it reproduces the release byte for byte.
- `variabilita_sezioni.csv.gz` — one row per municipality and census
  section (`cod`, `sezione`). For each of five counts, the value in the
  release (`_seme42`) and the mean and standard deviation (`_media`,
  `_sd`) across the {nrep + 1} draws: `pop` residents; `stranieri` foreign
  citizens; `over75` aged 75 and over; `over75_soli` aged 75 and over
  living alone; `bersaglio` aged 75 and over with at most lower secondary
  education. Population and age are nearly fixed by the constraints;
  counts that cross attributes or households vary by 20–40% from draw to
  draw in a single section, and stabilise only when sections are
  aggregated. Use the release for maps and totals; use the replicates,
  or this table, before reading a small count in a single section.
"""
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
{testo_repliche}
## Provenance

Generated by the GSP pipeline at tag `{args.tag}`
(https://github.com/mirko-degli-esposti/gsp) from published ISTAT
aggregates and municipal open data alone. Every file is reproducible byte
for byte from that tag; the pipeline's per-municipality `report.md`
records the sources, the fit and the checks for each municipality.

## Changes since v2.0

- 86 municipalities added: v2.0 held 245, this release holds all 330
  municipalities of Emilia-Romagna, plus Brescia. Quality degrades
  gradually as municipalities get smaller; the accompanying paper reports
  it by population band.
- Single year of age corrected: within each five-year class, years of age
  now follow the municipal register distribution, which v2.0 distorted.
  Age classes and every other attribute of the individuals are unchanged
  in the 245 municipalities of v2.0; households were regenerated.
- In three very small municipalities (Montecopiolo, Casteldelci, Zerba)
  the fit is computed by iterative proportional fitting, because the dual
  solver does not converge there.

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
    print("\nprossimo passo: python build/deposito_zenodo.py upload --tag", args.tag,
          "[--nuova-versione-di ID]")


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
        if args.nuova_versione_di:
            r = requests.post(f"{base}/api/deposit/depositions/"
                              f"{args.nuova_versione_di}/actions/newversion", headers=H)
            r.raise_for_status()
            r = requests.get(r.json()["links"]["latest_draft"], headers=H)
            r.raise_for_status()
            dep = r.json()
            json.dump(dep, open(stato, "w"))
            # la bozza eredita i file della versione precedente: si tolgono
            for f in requests.get(f"{base}/api/deposit/depositions/{dep['id']}/files",
                                  headers=H).json():
                requests.delete(f"{base}/api/deposit/depositions/{dep['id']}/files/"
                                f"{f['id']}", headers=H).raise_for_status()
                print(f"  tolto dalla bozza (versione precedente): {f['filename']}")
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

    ammessi = flotta_dal_registro()
    comuni = [c for c in comuni_del_bundle(RADICE / "bundle", set(args.escludi))
              if c in ammessi]
    pop, hh = totali(RADICE / "bundle", comuni)
    rep = RADICE / "deposito" / f"_repliche_{args.tag}"
    nrep = (len([d for d in rep.iterdir() if d.is_dir()])
            if (out / f"animarium_replicates_{args.tag}.zip").exists() else 0)
    repliche = DESCR_REPLICHE.format(tag=args.tag, nrep=nrep) if nrep else ""
    meta = {"metadata": {
        "title": TITOLO.format(n=len(comuni), tag=args.tag),
        "upload_type": "dataset",
        "description": DESCRIZIONE.format(n=len(comuni), tag=args.tag, pop=pop, hh=hh,
                                          repliche=repliche),
        "publication_date": date.today().isoformat(),
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
    p.add_argument("--variabilita", default=None,
                   help="tabella di variabilita' per sezione (csv.gz) da allegare")
    p.set_defaults(fn=pack)
    u = sub.add_parser("upload", help="crea la BOZZA su Zenodo e carica i file")
    u.add_argument("--tag", required=True)
    u.add_argument("--sandbox", action="store_true")
    u.add_argument("--escludi", nargs="*", default=[],
                   help="codici ISTAT da non depositare (collaudo, pilota, sotto soglia)")
    u.add_argument("--nuova-versione-di", default=None, metavar="ID",
                   help="id Zenodo di una versione pubblicata: la bozza ne e' la nuova versione")
    u.set_defaults(fn=upload)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
