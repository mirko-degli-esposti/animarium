#!/usr/bin/env python3
"""
manifest_min.py — Animarium, F3   (v2)
=======================================

Il manifest minimo che serve a un pannello solo: etichette leggibili, ordine
stabile delle modalita', conteggi non filtrati.

Deliberatamente **non** contiene riferimenti censuari, stati di garanzia,
geometrie o aggregati: quelli arrivano in F4, quando il pannello avra' detto
cosa serve davvero invece di indovinarlo adesso.

Tre correzioni della v2, tutte emerse guardando i manifest delle quattro citta'
--------------------------------------------------------------------------
1. **`zona` etichettata coi nomi di quartiere**, invece di due pannelli
   gemelli (uno coi codici, uno coi nomi). E' la struttura che il manifest
   gia' prevedeva: un attributo, modalita' con etichetta leggibile. Effetto
   collaterale: `quartiere` serve solo alla build, quindi si puo' togliere
   dal Parquet (§12 del design).

2. **Troncamento per attributo, non per soglia globale.** La soglia a 25
   modalita' era pensata per `paese` (100-151) ma tagliava anche i 33
   quartieri di Brescia, cioe' il filtro spaziale proprio nella citta' che ha
   piu' struttura. Ora si tronca solo cio' che e' elencato in TRONCA.

3. **Ordine stabile fra citta'.** L'ordine per frequenza cambia da comune a
   comune, quindi due pannelli affiancati hanno le righe in ordine diverso e
   il confronto diventa illeggibile. Il default e' ora alfabetico — arbitrario
   ma stabile — con la frequenza riservata a `paese`. Gli ordini veri si
   dichiarano in ORDINI man mano che si conoscono.

Lo script stampa le modalita' degli attributi senza ordine dichiarato, cosi'
si possono aggiungere a ORDINI senza andarle a cercare.

Uso
---
    python build/manifest_min.py 036023
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys

import pandas as pd
import pyarrow.parquet as pq

# nome · etichetta · tipo
ATTRIBUTI = [
    ("zona",             "Quartiere",                  "nominale"),
    ("sesso",            "Sesso",                      "nominale"),
    ("eta",              "Classe d'eta'",              "ordinale"),
    ("stato_civile",     "Stato civile",               "nominale"),
    ("cittadinanza",     "Cittadinanza",               "nominale"),
    ("istruzione",       "Titolo di studio",           "ordinale"),
    ("condizione",       "Condizione professionale",   "nominale"),
    ("background",       "Background migratorio",      "nominale"),
    ("origine_genitori", "Origine dei genitori",       "nominale"),
    ("area",             "Area geografica di origine", "nominale"),
    ("paese",            "Paese di cittadinanza",      "nominale"),
]

# `zona` prende le etichette da questa colonna, che non diventa un attributo
COLONNA_ETICHETTE = {"zona": "quartiere"}

ORDINI = {
    "sesso": ["M", "F"],
    "eta": ["0-8", "9-14", "15-24", "25-34", "35-49", "50-64", "65-74", "75+"],
    "istruzione": ["nessun_titolo", "elementare", "media", "diploma",
                   "laurea_o_its", "post_laurea"],
    "cittadinanza": ["ITL", "FRG"],
    # corso di vita
    "stato_civile": ["celibe_nubile", "coniugato_unito",
                     "divorziato_sciolto", "vedovo"],
    # rapporto col mercato del lavoro, dalle forze di lavoro in fuori
    "condizione": ["occupato", "in_cerca", "studente", "casalinga",
                   "percettore_pensioni", "altra_condizione",
                   "non_applicabile"],
    # gradiente di background migratorio: dentro ogni gruppo di cittadinanza,
    # prima chi e' nato in Italia
    "background": ["italiano_nativo", "italiano_rientrato",
                   "naturalizzato_g2", "naturalizzato_immigrato",
                   "straniero_g2", "straniero_immigrato"],
    # da entrambi italiani a entrambi stranieri, misti in mezzo
    "origine_genitori": ["entrambi_italiani",
                         "madre_italiana_padre_straniero",
                         "madre_straniera_padre_italiano",
                         "entrambi_stranieri", "non_applicabile"],
    "area": ["UE", "EXTRA_UE", "(mancante)"],
}

ETICHETTE_MOD = {
    "sesso": {"M": "Maschi", "F": "Femmine"},
    "cittadinanza": {"ITL": "Italiana", "FRG": "Straniera"},
    "istruzione": {
        "nessun_titolo": "Nessun titolo",
        "elementare": "Licenza elementare",
        "media": "Licenza media",
        "diploma": "Diploma",
        "laurea_o_its": "Laurea o ITS",
        "post_laurea": "Post-laurea",
    },
    "stato_civile": {
        "celibe_nubile": "Celibe o nubile",
        "coniugato_unito": "Coniugato/a o unito/a",
        "divorziato_sciolto": "Divorziato/a o sciolto/a",
        "vedovo": "Vedovo/a",
    },
    "condizione": {
        "occupato": "Occupato/a",
        "in_cerca": "In cerca di occupazione",
        "studente": "Studente",
        "casalinga": "Casalinga",
        "percettore_pensioni": "Percettore di pensione",
        "altra_condizione": "Altra condizione",
        "non_applicabile": "Meno di 15 anni",
    },
    "background": {
        "italiano_nativo": "Italiano nativo",
        "italiano_rientrato": "Italiano rientrato",
        "naturalizzato_g2": "Naturalizzato, nato in Italia",
        "naturalizzato_immigrato": "Naturalizzato immigrato",
        "straniero_g2": "Straniero, nato in Italia",
        "straniero_immigrato": "Straniero immigrato",
    },
    "origine_genitori": {
        "entrambi_italiani": "Entrambi italiani",
        "madre_italiana_padre_straniero": "Solo madre italiana",
        "madre_straniera_padre_italiano": "Solo padre italiano",
        "entrambi_stranieri": "Entrambi stranieri",
        "non_applicabile": "Non applicabile",
    },
    "area": {
        "UE": "Unione Europea",
        "EXTRA_UE": "Fuori dall'Unione Europea",
        "(mancante)": "Non applicabile",
    },
}

# senza ordine dichiarato: alfabetico (stabile fra citta'), salvo questi
PER_FREQUENZA = {"paese"}
# `zona` per codice, che e' stabile e segue la numerazione comunale
PER_CODICE = {"zona"}

# solo questi si troncano nel pannello
TRONCA = {"paese": 15}
# vanno sempre in coda, qualunque sia il criterio di ordinamento
CODA = {"(mancante)", "non_applicabile"}

ETICHETTE_MOD = {
    "sesso": {"M": "Maschi", "F": "Femmine"},
    "cittadinanza": {"ITL": "Italiana", "FRG": "Straniera"},
    "istruzione": {
        "nessun_titolo": "Nessun titolo",
        "elementare": "Licenza elementare",
        "media": "Licenza media",
        "diploma": "Diploma",
        "laurea_o_its": "Laurea o ITS",
        "post_laurea": "Post-laurea",
    },
}


# Etichetta del filtro spaziale: dipende dal comune, non e' sempre
# "Quartiere". Brescia ha quartieri, Bologna zone, Ravenna aree, Reggio
# circoscrizioni — e il registro lo sa gia'.
ETICHETTA_LIVELLO = {"quartieri": "Quartiere", "zone": "Zona",
                     "aree": "Area", "circoscrizioni": "Circoscrizione"}


def carica_gsp():
    try:
        import gsp.common as G  # type: ignore
        return G
    except Exception as e:
        sys.exit(f"errore: gsp.common non importabile ({e})")


def etichetta_default(v):
    s = str(v).replace("_", " ").strip()
    return s[:1].upper() + s[1:] if s else s


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("comune")
    ap.add_argument("--parquet", default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    par = args.parquet or os.path.join("bundle", "comuni", args.comune,
                                       "pop.parquet")
    if not os.path.exists(par):
        sys.exit(f"errore: Parquet non trovato: {par}\n"
                 f"       esegui prima: python build/to_parquet.py "
                 f"{args.comune} --drop-avq-raw")
    out = args.out or os.path.join("bundle", "comuni", args.comune,
                                   "manifest.json")

    G = carica_gsp()
    i_reg = G.info(args.comune)
    livello = i_reg["livello"]
    n_zone = i_reg["livelli"][livello]["n"] if livello else 0

    disponibili = set(pq.ParquetFile(par).schema_arrow.names)

    # `zona` degenere: nei comuni senza articolazione sub-comunale la
    # colonna esiste ma ha un valore solo ('0'). Mostrarla darebbe un
    # pannello con una barra al 100%, che e' peggio di non averlo.
    zona_degenere = False
    if "zona" in disponibili:
        nz = pq.read_table(par, columns=["zona"]).column(0).unique()
        zona_degenere = len(nz) <= 1
        if zona_degenere:
            disponibili.discard("zona")
            print(f"[info] {i_reg['nome']}: `zona` degenere "
                  f"(valore unico {nz[0]}), esclusa dagli attributi")

    voluti = [a for a in ATTRIBUTI if a[0] in disponibili]
    mancanti = [a[0] for a in ATTRIBUTI if a[0] not in disponibili]
    if mancanti:
        print(f"[avviso] attributi assenti dal Parquet: {mancanti}")

    cols = [a[0] for a in voluti]
    extra = [c for c in COLONNA_ETICHETTE.values()
             if c in disponibili and c not in cols]
    df = pq.read_table(par, columns=cols + extra).to_pandas()
    n_tot = len(df)
    print(f"[info] {par}: {n_tot:,} individui, {len(cols)} attributi"
          .replace(",", "."))
    print()

    da_dichiarare = {}
    attributi = []

    for nome, etichetta, tipo in voluti:
        vc = df[nome].astype("string").value_counts(dropna=False)
        vc.index = vc.index.fillna("(mancante)")

        # etichette delle modalita': esplicite, oppure da una colonna gemella
        et = dict(ETICHETTE_MOD.get(nome, {}))
        gemella = COLONNA_ETICHETTE.get(nome)
        if gemella and gemella in df.columns:
            moda = (df.groupby(nome, observed=True)[gemella]
                      .agg(lambda s: s.mode().iat[0] if len(s.mode()) else ""))
            ambigui = (df.groupby(nome, observed=True)[gemella]
                         .nunique().gt(1).sum())
            if ambigui:
                print(f"[avviso] {nome}: {ambigui} codici con piu' di un "
                      f"valore di '{gemella}'; presa la moda")
            for k, v in moda.items():
                if v:
                    et.setdefault(str(k), str(v))

        # ordine
        ordine = ORDINI.get(nome)
        if ordine:
            noti = [m for m in ordine if m in vc.index]
            ignoti = [m for m in vc.index if m not in ordine]
            if ignoti:
                print(f"[avviso] {nome}: modalita' fuori dall'ordine "
                      f"dichiarato, messe in coda: {ignoti}")
            sequenza, marca = noti + sorted(ignoti), "dichiarato"
        elif nome in PER_FREQUENZA:
            sequenza, marca = list(vc.index), "frequenza"
        elif nome in PER_CODICE:
            sequenza, marca = sorted(vc.index), "codice"
        else:
            sequenza, marca = sorted(vc.index), "alfabetico"
            da_dichiarare[nome] = list(sequenza)

        coda = [m for m in sequenza if str(m) in CODA]
        if coda:
            sequenza = [m for m in sequenza if str(m) not in CODA] + coda

        modalita = [{"v": str(m),
                     "etichetta": et.get(str(m), etichetta_default(m)),
                     "n": int(vc[m])} for m in sequenza]

        if nome == "zona" and livello:
            etichetta = ETICHETTA_LIVELLO.get(livello, livello.capitalize())

        voce = {"nome": nome, "etichetta": etichetta, "tipo": tipo,
                "ordinamento": marca, "n_modalita": len(modalita),
                "modalita": modalita}
        if nome in TRONCA and len(modalita) > TRONCA[nome]:
            voce["mostra_prime"] = TRONCA[nome]
        attributi.append(voce)

        tag = "  TRONCATO a %d" % voce["mostra_prime"] if "mostra_prime" in voce else ""
        print(f"  {nome:<18} {len(modalita):>4} modalita'  "
              f"[{marca[:4]}]{tag}")

    manifest = {
        "generato": dt.datetime.now().isoformat(timespec="seconds"),
        "nota": ("Etichette, ordini e conteggi non filtrati. Gli attributi "
                 "elencati sono SOLO quelli presenti nel Parquet: i comuni "
                 "senza articolazione sub-comunale (livello K6C) non hanno "
                 "zona, background e origine_genitori, e il pannello si "
                 "costruisce da questa lista, quindi non li nomina mai."),
        "comune": {"codice": args.comune,
                   "nome": i_reg["nome"],
                   "regione": i_reg["regione"],
                   "individui": n_tot,
                   "parquet": "pop.parquet",
                   "livello": livello,
                   "livello_etichetta": (ETICHETTA_LIVELLO.get(livello, livello)
                                         if livello else None),
                   "zone": n_zone,
                   "zona_degenere": zona_degenere,
                   # tier del condizionale geografico per `paese`, derivato
                   # da opendata_paese. Con tier 0 `paese` non ha struttura
                   # sub-comunale: si comporta come le AVQ, quindi la sua
                   # classe di garanzia degrada da C a D.
                   "tier": G.tier(args.comune),
                   "paese_classe": "D" if G.tier(args.comune) == 0 else "C"},
        "riferimento": {
            "tipo": "citta_intera",
            "spiegazione": ("La popolazione non filtrata riproduce il "
                            "censimento comunale a 4e-4, quindi la stessa "
                            "serie e' insieme il dato reale comunale e il "
                            "valore atteso sotto indipendenza fra attributo "
                            "mostrato e filtro: lo scarto e' l'associazione."),
        },
        "attributi": attributi,
    }

    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    print(f"\n[info] scritto {out} ({os.path.getsize(out) / 1024:.1f} KB)")

    if da_dichiarare:
        print("\nModalita' senza ordine dichiarato — ora alfabetiche, quindi")
        print("stabili fra citta' ma arbitrarie. Da incollare in ORDINI:")
        print()
        for k, v in da_dichiarare.items():
            print(f'    "{k}": {v},')


if __name__ == "__main__":
    main()
