#!/usr/bin/env python3
"""
serve_range.py — Animarium, supporto al passo 2   (v2)
=======================================================

Server statico che fa tre cose che `python -m http.server` non fa:

1. **Supporta le richieste Range** (HTTP 206). Senza questo DuckDB-WASM
   scarica il file intero e lo smoke test darebbe un falso negativo:
   concluderemmo che la potatura non funziona, mentre e' il server a non
   collaborare.

2. **Conta i byte serviti per intervallo**, delimitato dagli hit su
   `/__mark?q=NOME`. La pagina chiama `__mark` dopo ogni query, quindi il
   server stampa da solo quanto e' costata ciascuna.

3. **Confronta con l'attesa.** Se il marcatore porta `&atteso=0.7`, la riga
   di riepilogo mostra misurato contro previsto e il rapporto. Una
   previsione scritta prima della misura vale piu' di un numero commentato
   dopo.

Uso
---
    cd ~/progetti/gsp/animarium
    python build/serve_range.py

    http://localhost:8000/build/smoke_duckdb.html
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

RANGE_RE = re.compile(r"bytes=(\d*)-(\d*)")

STATO = {"t0": time.time(), "richieste": 0, "byte": {}}
STORICO = []


def mb(n):
    return f"{n / 1024 / 1024:7.3f} MB"


def conta(path, n):
    STATO["byte"][path] = STATO["byte"].get(path, 0) + n
    STATO["richieste"] += 1


def chiudi_intervallo(nome, atteso=None):
    dt = time.time() - STATO["t0"]
    tot = sum(STATO["byte"].values())
    print()
    print(f"  ==  {nome}")
    riga = (f"      richieste {STATO['richieste']:>5}   "
            f"totale {mb(tot)}   {dt * 1000:7.0f} ms")
    print(riga)

    if atteso is not None:
        att = atteso * 1024 * 1024
        if att > 0:
            rap = tot / att
            if rap < 0.75:
                verdetto = "meglio del previsto"
            elif rap <= 1.35:
                verdetto = "come previsto"
            elif rap <= 2.5:
                verdetto = "sopra il previsto"
            else:
                verdetto = "MOLTO sopra il previsto"
            print(f"      atteso   {mb(att)}   "
                  f"rapporto {rap:5.2f}x   {verdetto}")
        STORICO.append((nome, tot, att))

    if len(STATO["byte"]) > 1:
        for p, n in sorted(STATO["byte"].items(), key=lambda kv: -kv[1]):
            print(f"      {os.path.basename(p):<28} {mb(n)}")

    sys.stdout.flush()
    STATO["t0"] = time.time()
    STATO["richieste"] = 0
    STATO["byte"] = {}


def riepilogo():
    if not STORICO:
        return
    print()
    print("  " + "=" * 62)
    print(f"  {'query':<34}{'misurato':>12}{'atteso':>12}{'rapp.':>8}")
    print("  " + "-" * 62)
    for nome, tot, att in STORICO:
        corto = nome.split(" — ")[0]
        rap = f"{tot / att:.2f}x" if att else "—"
        print(f"  {corto:<34}{mb(tot):>12}{mb(att):>12}{rap:>8}")
    print("  " + "=" * 62)
    sys.stdout.flush()


class Handler(SimpleHTTPRequestHandler):

    def log_message(self, *a):
        pass

    def end_headers(self):
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/__mark":
            qs = parse_qs(parsed.query)
            nome = qs.get("q", ["(senza nome)"])[0]
            atteso = None
            if "atteso" in qs:
                try:
                    atteso = float(qs["atteso"][0])
                except ValueError:
                    atteso = None
            chiudi_intervallo(nome, atteso)
            body = b"ok"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if parsed.path == "/__riepilogo":
            riepilogo()
            body = b"ok"
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        rng = self.headers.get("Range")
        if not rng:
            return self.get_intero()

        percorso = self.translate_path(parsed.path)
        if not os.path.isfile(percorso):
            return SimpleHTTPRequestHandler.do_GET(self)

        size = os.path.getsize(percorso)
        m = RANGE_RE.match(rng.strip())
        if not m:
            self.send_error(400, "Range malformato")
            return

        a, b = m.group(1), m.group(2)
        if a == "":                       # bytes=-N : la coda, cioe' il footer
            n = int(b)
            inizio, fine = max(0, size - n), size - 1
        else:
            inizio = int(a)
            fine = int(b) if b else size - 1
        fine = min(fine, size - 1)
        if inizio > fine:
            self.send_response(416)
            self.send_header("Content-Range", f"bytes */{size}")
            self.end_headers()
            return

        lung = fine - inizio + 1
        self.send_response(206)
        self.send_header("Content-Type", self.guess_type(percorso))
        self.send_header("Content-Range", f"bytes {inizio}-{fine}/{size}")
        self.send_header("Content-Length", str(lung))
        self.end_headers()
        with open(percorso, "rb") as f:
            f.seek(inizio)
            rimasti = lung
            while rimasti > 0:
                blocco = f.read(min(65536, rimasti))
                if not blocco:
                    break
                self.wfile.write(blocco)
                rimasti -= len(blocco)
        conta(percorso, lung)

    def get_intero(self):
        percorso = self.translate_path(urlparse(self.path).path)
        if os.path.isfile(percorso):
            conta(percorso, os.path.getsize(percorso))
        return SimpleHTTPRequestHandler.do_GET(self)

    def do_HEAD(self):
        percorso = self.translate_path(urlparse(self.path).path)
        if os.path.isfile(percorso):
            self.send_response(200)
            self.send_header("Content-Type", self.guess_type(percorso))
            self.send_header("Content-Length", str(os.path.getsize(percorso)))
            self.end_headers()
            return
        return SimpleHTTPRequestHandler.do_HEAD(self)


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--dir", default=".")
    args = ap.parse_args()

    os.chdir(args.dir)
    srv = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    base = f"http://localhost:{args.port}"

    print(f"radice   {os.getcwd()}")
    print(f"in ascolto su {base}/")
    print()
    pagine = [
        ("index.html",                    "Animarium — marginali e mappa"),
        ("build/pannello_marginali.html", "Animarium — marginali e mappa"),
        ("smoke.html",                    "smoke test DuckDB-WASM"),
        ("build/smoke_duckdb.html",       "smoke test DuckDB-WASM"),
    ]
    visti = set()
    for percorso, che in pagine:
        if che in visti or not os.path.exists(percorso):
            continue
        visti.add(che)
        print(f"    {che:<32} {base}/{percorso}")
    if not visti:
        print("  ? nessuna pagina trovata: sei nella directory giusta?")
    if not os.path.exists("bundle/comuni.json"):
        print("\n  ? bundle/comuni.json assente: il menu delle citta' "
              "restera' vuoto")
    print("\nRange: supportato. Ctrl-C stampa il riepilogo e chiude.")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        chiudi_intervallo("(chiusura)")
        riepilogo()


if __name__ == "__main__":
    main()
