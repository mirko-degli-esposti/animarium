#!/usr/bin/env python3
"""
i18n_check.py — Animarium
=========================

Estrae dal sorgente del pannello tutte le chiavi traducibili e le confronta
con il dizionario `build/i18n/en.json`.

Chiavi raccolte
---------------
1. markup statico (fra </style> e <script>): ogni nodo di testo con almeno
   due lettere; gli elementi marcati `data-i18n` contano come un'unica chiave
   (innerHTML intero, tag inline compresi);
2. `<title>`;
3. JavaScript: `T("...")`, `T('...')` e i tagged template `T`...``, dove ogni
   `${...}` diventa `{i}` nella chiave.

Le chiavi sono normalizzate come nel runtime: spazi e newline collassati.

Output
------
- stampa: chiavi totali, tradotte, mancanti, orfane (nel dizionario ma non
  piu' nel sorgente);
- scrive `build/i18n/pending_en.json` con le chiavi mancanti (valore "") —
  e' il file da compilare; con `--merge` le voci non vuote di pending
  vengono ricopiate in en.json e pending viene svuotato.

Uso
---
    python build/i18n_check.py            # rapporto + pending_en.json
    python build/i18n_check.py --strict   # exit 1 se ci sono mancanti
    python build/i18n_check.py --merge    # importa pending_en.json in en.json

Chiamato anche da deploy.py (funzione `verifica`).
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
from html.parser import HTMLParser

RADICE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SORGENTE = os.path.join(RADICE, "build", "pannello_marginali.html")
DIZ = os.path.join(RADICE, "build", "i18n", "en.json")
PENDING = os.path.join(RADICE, "build", "i18n", "pending_en.json")

INLINE = {"b", "i", "em", "strong", "code", "a", "span", "br", "sup", "sub", "u"}


def norm(s):
    return re.sub(r"\s+", " ", s).strip()


class _Markup(HTMLParser):
    """Nodi di testo, piu' innerHTML degli elementi data-i18n."""

    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.chiavi = []
        self._blocco = None      # (tag, profondita', pezzi) quando dentro data-i18n
        self._salta = 0          # dentro <script>/<style>

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._salta += 1
            return
        if self._blocco:
            self._blocco[2].append(self.get_starttag_text())
            if tag == self._blocco[0]:
                self._blocco[1] += 1
            return
        if any(k == "data-i18n" for k, _ in attrs):
            self._blocco = [tag, 1, []]

    def handle_startendtag(self, tag, attrs):
        if self._blocco:
            self._blocco[2].append(self.get_starttag_text())

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._salta -= 1
            return
        if self._blocco:
            if tag == self._blocco[0]:
                self._blocco[1] -= 1
                if self._blocco[1] == 0:
                    self.chiavi.append(norm("".join(self._blocco[2])))
                    self._blocco = None
                    return
            self._blocco[2].append(f"</{tag}>")

    def handle_data(self, data):
        if self._salta:
            return
        if self._blocco:
            self._blocco[2].append(data)
            return
        k = norm(html.unescape(data))
        if k and re.search(r"[A-Za-zÀ-ÿ]{2,}", k):
            self.chiavi.append(k)

    def handle_entityref(self, name):
        self.handle_data(f"&{name};")

    def handle_charref(self, name):
        self.handle_data(f"&#{name};")

    def handle_comment(self, data):
        pass


def chiavi_markup(src):
    a = src.index("</style>") + len("</style>")
    b = src.index('<script type="module">')
    p = _Markup()
    p.feed(src[a:b])
    out = list(p.chiavi)
    m = re.search(r"<title>(.*?)</title>", src, re.S)
    if m:
        out.append(norm(m.group(1)))
    return out


# --- JavaScript -------------------------------------------------------------

RE_T_STR = re.compile(r'(?<![\w$.])T\(\s*("((?:[^"\\]|\\.)*)"|\'((?:[^\'\\]|\\.)*)\')')
RE_T_TPL = re.compile(r"(?<![\w$.])T`")


def _template_da(src, i):
    """Legge un template literal a partire dal backtick in posizione i.
    Ritorna (chiave, fine). Le ${...} diventano {n}; gestisce graffe annidate
    e backtick dentro le interpolazioni."""
    assert src[i] == "`"
    j, pezzi, n = i + 1, [], 0
    while j < len(src):
        c = src[j]
        if c == "\\":
            pezzi.append(src[j:j + 2]); j += 2; continue
        if c == "`":
            return norm("".join(pezzi)), j + 1
        if src.startswith("${", j):
            prof, j2 = 1, j + 2
            while j2 < len(src) and prof:
                if src[j2] == "{": prof += 1
                elif src[j2] == "}": prof -= 1
                elif src[j2] == "`":                   # template annidato
                    _, j2 = _template_da(src, j2); continue
                j2 += 1
            pezzi.append(f"{{{n}}}"); n += 1; j = j2; continue
        pezzi.append(c); j += 1
    raise ValueError("template literal non chiuso")


def _unescape_js(s):
    return s.encode("utf-8").decode("unicode_escape").encode("latin-1").decode("utf-8") \
        if "\\" in s else s


def chiavi_js(src):
    a = src.index('<script type="module">')
    js = re.sub(r"/\*.*?\*/", "", src[a:], flags=re.S)   # via i commenti a blocco
    out = []
    for m in RE_T_STR.finditer(js):
        out.append(norm(_unescape_js(m.group(2) if m.group(2) is not None else m.group(3))))
    for m in RE_T_TPL.finditer(js):
        k, _ = _template_da(js, m.end() - 1)
        out.append(k)
    return out


# --- confronto ---------------------------------------------------------------

def carica(p):
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}


def salva(p, d):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")


def verifica(sorgente=SORGENTE, diz=DIZ, pending=PENDING, scrivi_pending=True):
    src = open(sorgente, encoding="utf-8").read()
    if "// @i18n" not in src:
        sys.exit("errore: manca la riga `const I18N = {};   // @i18n` nel sorgente")
    chiavi = sorted(set(chiavi_markup(src) + chiavi_js(src)))
    d = carica(diz)
    mancanti = [k for k in chiavi if not d.get(k)]
    orfane = sorted(k for k in d if k not in chiavi)
    print(f"i18n: {len(chiavi)} chiavi nel sorgente, "
          f"{len(chiavi) - len(mancanti)} tradotte, "
          f"{len(mancanti)} mancanti, {len(orfane)} orfane")
    if scrivi_pending:
        vecchio = carica(pending)
        salva(pending, {k: vecchio.get(k, "") for k in mancanti})
        if mancanti:
            print(f"      da tradurre: {os.path.relpath(pending, RADICE)}")
    return chiavi, mancanti, orfane


def merge(diz=DIZ, pending=PENDING):
    d, p = carica(diz), carica(pending)
    nuove = {k: v for k, v in p.items() if v.strip()}
    d.update(nuove)
    salva(diz, d)
    salva(pending, {k: "" for k in p if not p[k].strip()})
    print(f"i18n: importate {len(nuove)} traduzioni in {os.path.relpath(diz, RADICE)}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--strict", action="store_true", help="exit 1 se ci sono chiavi mancanti")
    ap.add_argument("--merge", action="store_true", help="importa pending_en.json in en.json")
    ap.add_argument("--orfane", action="store_true", help="elenca le chiavi orfane")
    ap.add_argument("--sorgente", default=SORGENTE)
    args = ap.parse_args()
    if args.merge:
        merge()
    _, mancanti, orfane = verifica(sorgente=args.sorgente)
    if args.orfane:
        for k in orfane:
            print("  orfana:", k)
    if args.strict and mancanti:
        sys.exit(1)


if __name__ == "__main__":
    main()
