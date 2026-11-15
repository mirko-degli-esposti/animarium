#!/usr/bin/env python3
"""
esporta_repliche.py — Animarium
================================

Esporta in regime PUBBLICO le repliche della release (semi 1..10) dalle corse
del banco di GSP, per l'archivio facoltativo del deposito Zenodo.

    python build/esporta_repliche.py --tag release-v2.1 [-P 8] [--semi 1 2 ...]

La release principale resta il seme di produzione (il bundle). Qui ogni
comune della release viene riesportato, per ciascun seme, con lo stesso
comando del bundle (`to_parquet.py --drop-avq-raw`): stesso regime, stesse
colonne, stesso ordinamento. Il seme delle coordinate resta derivato dal
comune, come nella release.

Dove stanno le repliche (campagne del 5/11/2026, gsp `c972091`, catena
identica al tag `release-v2.1`):

    rep_s{S}    quattro anelli, tutti i semi = S (319 comuni, Castenaso,
                Brescia);
    rep4_s{S}   le 10 citta' di riferimento: anelli 1-3 ereditati da
                rep13_s{S}, anello 4 con nucleo.seme = S.

Uscita, in `deposito/_repliche_<tag>/`:

    s01/comuni/<COD>/pop.parquet ... s10/comuni/<COD>/pop.parquet
    provenienza.csv     una riga per comune x seme: corsa del banco, commit,
                        albero pulito, individui, nuclei, SHA-256

Controlli, per ogni file: la corsa e' finita, su albero pulito; le colonne
sono quelle del Parquet di produzione, nello stesso ordine; il numero di
individui e' quello di produzione; nessuna colonna riservata. Un controllo
fallito ferma tutto alla fine, con l'elenco.

Idempotente: i file gia' esportati non si rifanno (`--forza` per rifarli).
`deposito_zenodo.py pack` trova questa cartella e ne fa il secondo archivio.
"""
from __future__ import annotations

import argparse
import csv
import glob
import hashlib
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pyarrow.parquet as pq

RADICE = Path(__file__).resolve().parent.parent
GSP = Path(os.environ.get("GSP_ROOT", RADICE.parent / "gsp"))
CORSE = Path(os.environ.get("GSP_LAB", RADICE.parent / "laboratorio")) / "corse"
RISERVATE = {"uid", "via", "civico", "indirizzo_fonte", "nome", "cognome"}


def flotta() -> list[str]:
    import yaml
    d = yaml.safe_load(open(GSP / "flotta" / "comuni.yaml"))
    return sorted(k for k, v in d.items() if v.get("stato") in ("flotta", "v2"))


def corsa(cod: str, s: int) -> tuple[Path, dict]:
    """La corsa finita che porta la replica `s` di `cod`, e il suo manifesto."""
    import yaml
    for etich in (f"rep_s{s}", f"rep4_s{s}"):
        for d in sorted(glob.glob(str(CORSE / f"{cod}_{etich}_2*"))):
            m = yaml.safe_load(open(Path(d) / "esperimento.yaml"))
            if m.get("esito", {}).get("stato") == "finita":
                return Path(d), m
    raise RuntimeError(f"{cod}: nessuna corsa finita per il seme {s}")


def trova(d: dict, chiave: str):
    """Prima occorrenza di `chiave` nel manifesto, a qualunque profondita'."""
    if chiave in d:
        return d[chiave]
    for v in d.values():
        if isinstance(v, dict) and (r := trova(v, chiave)) is not None:
            return r
    return None


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while b := f.read(1 << 20):
            h.update(b)
    return h.hexdigest()


def esporta(cod: str, s: int, out: Path, forza: bool) -> dict:
    d, m = corsa(cod, s)
    pop = [p for p in glob.glob(str(d / "comuni" / cod / "constraints_2024"
                                    / "popolazione_K*C_avq_full.csv"))
           if not re.search(r"K10C", p)]
    if len(pop) != 1:
        raise RuntimeError(f"{d.name}: {len(pop)} popolazioni complete")
    dest = out / f"s{s:02d}" / "comuni" / cod / "pop.parquet"
    if forza or not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(".tmp")
        r = subprocess.run(
            [sys.executable, str(RADICE / "build" / "to_parquet.py"), cod,
             "--pop-file", pop[0], "--nuclei-dir", str(d / "nuclei"),
             "--out", str(tmp), "--drop-avq-raw"],
            cwd=RADICE, capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(f"{d.name}: to_parquet fallito\n{r.stdout[-600:]}{r.stderr[-600:]}")
        tmp.rename(dest)

    # controlli contro il Parquet di produzione
    rif = pq.ParquetFile(RADICE / "bundle" / "comuni" / cod / "pop.parquet")
    f = pq.ParquetFile(dest)
    errori = []
    if f.schema_arrow.names != rif.schema_arrow.names:
        errori.append("colonne diverse dalla produzione")
    if f.metadata.num_rows != rif.metadata.num_rows:
        errori.append(f"individui {f.metadata.num_rows} contro {rif.metadata.num_rows}")
    if RISERVATE & set(f.schema_arrow.names):
        errori.append("colonne riservate")
    if trova(m, "git_pulito") is not True:
        errori.append("albero non pulito")
    t = f.read(columns=["sezione", "nucleo"]).to_pandas()
    nuclei = int(t[t["nucleo"] >= 0].drop_duplicates().shape[0])
    return {"cod": cod, "seme": s, "corsa": d.name, "base": m.get("base") or "",
            "commit_gsp": trova(m, "commit_gsp"), "git_pulito": trova(m, "git_pulito"),
            "individui": f.metadata.num_rows, "nuclei": nuclei,
            "sha256": sha256(dest), "errori": "; ".join(errori)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--semi", nargs="*", type=int, default=list(range(1, 11)))
    ap.add_argument("--comuni", nargs="*", default=None)
    ap.add_argument("-P", type=int, default=8)
    ap.add_argument("--forza", action="store_true")
    a = ap.parse_args()

    out = RADICE / "deposito" / f"_repliche_{a.tag}"
    comuni = a.comuni or flotta()
    lavori = [(c, s) for s in a.semi for c in comuni]
    print(f"{len(comuni)} comuni x {len(a.semi)} semi = {len(lavori)} file -> {out}")

    righe, guasti = [], []

    def uno(cs):
        try:
            return esporta(cs[0], cs[1], out, a.forza)
        except Exception as e:                      # si raccoglie, si elenca alla fine
            return {"cod": cs[0], "seme": cs[1], "errori": str(e)}

    with ThreadPoolExecutor(a.P) as ex:
        for i, r in enumerate(ex.map(uno, lavori), 1):
            righe.append(r)
            if r.get("errori"):
                guasti.append(r)
            if i % 200 == 0 or i == len(lavori):
                print(f"  {i}/{len(lavori)}  guasti {len(guasti)}", flush=True)

    campi = ["cod", "seme", "corsa", "base", "commit_gsp", "git_pulito",
             "individui", "nuclei", "sha256", "errori"]
    righe.sort(key=lambda r: (r["seme"], r["cod"]))
    completo = not a.comuni and sorted(a.semi) == list(range(1, 11))
    if completo:
        with open(out / "provenienza.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=campi[:-1], extrasaction="ignore")
            w.writeheader()
            w.writerows(r for r in righe if not r.get("errori"))
    if guasti:
        for r in guasti[:30]:
            print(f"  GUASTO {r['cod']} s{r['seme']}: {r['errori']}")
        sys.exit(f"{len(guasti)} guasti su {len(lavori)}")
    commit = sorted({str(r["commit_gsp"]) for r in righe})
    print(f"ok: {len(righe)} file, commit {' '.join(commit)}"
          + ("" if completo else "  (corsa parziale: provenienza.csv non scritta)"))


if __name__ == "__main__":
    main()
