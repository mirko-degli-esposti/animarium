"""
build/geo_comuni.py — il GeoJSON dei comuni per la coropleta dell'atlante.

Dissolve le sezioni di censimento per PRO_COM, semplifica, e scrive un
GeoJSON leggero che `disegnaAtlante` disegna con la proiezione che gia'
usa per i dischi (px/py su MX/MY): nessuna libreria di mappe, nessuna
geometria esterna scaricata — la fonte e' lo shapefile ISTAT che la
pipeline ha gia' su disco.

Perche' TUTTI i comuni della regione e non solo quelli nel bundle:
l'assenza e' informazione quanto la presenza (design §4.8). I comuni
fuori dataset si disegnano in grigio, e la mappa dichiara da sola il
limite di copertura invece di nasconderlo.

TRAPPOLA (quinta apparizione dello zero iniziale): PRO_COM nello
shapefile e' INTERO (33042), i codici del bundle sono stringhe a sei
cifre ('033042'). Qui si scrive `pro_com` come stringa zero-padded, che
e' la chiave con cui il viewer fa il lookup nell'indice. Sbagliarlo non
da' errore: la regione esce tutta grigia.

Uso:
    python build/geo_comuni.py --regione emilia_romagna \\
        --out bundle/geo/er_comuni.json
    python build/geo_comuni.py --regione emilia_romagna --tolleranza 200 --dry-run
"""
import argparse
import json
from pathlib import Path

import geopandas as gpd

import gsp.common as G


def costruisci(regione, tolleranza_m, decimali):
    """Dissolve per comune, semplifica, riproietta in WGS84.

    L'ordine conta: si semplifica in metri (CRS proiettato, dove la
    tolleranza ha un significato geometrico) e SOLO DOPO si passa a
    lon/lat. Semplificare in gradi darebbe una tolleranza che varia
    con la latitudine."""
    shp = G.path_shp(regione)
    print(f"[geo] leggo {shp}")
    s = gpd.read_file(shp)
    print(f"[geo] {len(s):,} sezioni, CRS {s.crs}")

    com = s.dissolve(by="PRO_COM")[["geometry"]].reset_index()
    print(f"[geo] {len(com)} comuni dopo il dissolve")

    # semplificazione in unita' del CRS proiettato (metri per UTM/WGS84-UTM)
    prima = com.geometry.apply(lambda g: sum(len(p.exterior.coords)
                                             for p in getattr(g, "geoms", [g]))).sum()
    com["geometry"] = com.geometry.simplify(tolleranza_m, preserve_topology=True)
    dopo = com.geometry.apply(lambda g: sum(len(p.exterior.coords)
                                            for p in getattr(g, "geoms", [g]))).sum()
    print(f"[geo] vertici {prima:,} -> {dopo:,} "
          f"({dopo / prima:.1%}, tolleranza {tolleranza_m} m)")

    com = com.to_crs("EPSG:4326")
    # pro_com STRINGA a sei cifre: la chiave del lookup nel viewer
    com["pro_com"] = com["PRO_COM"].astype(int).astype(str).str.zfill(6)
    return com[["pro_com", "geometry"]]


def scrivi(com, out, decimali):
    """GeoJSON con coordinate arrotondate: 4 decimali ~ 11 m, sotto la
    tolleranza di semplificazione, e taglia il file quasi a meta'."""
    def arrotonda(coords):
        if isinstance(coords[0], (int, float)):
            return [round(coords[0], decimali), round(coords[1], decimali)]
        return [arrotonda(c) for c in coords]

    feats = []
    for _, r in com.iterrows():
        geom = json.loads(gpd.GeoSeries([r.geometry]).to_json())["features"][0]["geometry"]
        geom["coordinates"] = arrotonda(geom["coordinates"])
        feats.append({"type": "Feature",
                      "properties": {"pro_com": r.pro_com},
                      "geometry": geom})
    gj = {"type": "FeatureCollection", "features": feats}
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(gj, separators=(",", ":")), encoding="utf-8")
    kb = out.stat().st_size / 1024
    print(f"[geo] scritto {out}: {len(feats)} comuni, {kb:,.0f} KB")
    if kb > 800:
        print("[geo] ATTENZIONE: sopra 800 KB — alzare --tolleranza "
              "(la mappa e' larga ~900 px: dettagli sotto i 200 m non si vedono)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--regione", default="emilia_romagna")
    ap.add_argument("--out", default="bundle/geo/er_comuni.json")
    ap.add_argument("--tolleranza", type=float, default=150,
                    help="metri; l'atlante e' largo ~900 px per ~250 km: "
                         "un pixel vale ~280 m, quindi 150 m e' gia' sotto "
                         "la risoluzione visibile (default: 150)")
    ap.add_argument("--decimali", type=int, default=4,
                    help="decimali delle coordinate (4 ~ 11 m)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    com = costruisci(a.regione, a.tolleranza, a.decimali)
    print(f"[geo] pro_com: primi tre {list(com.pro_com[:3])}")
    if a.dry_run:
        print("[dry-run] nessun file scritto")
        return
    scrivi(com, a.out, a.decimali)


if __name__ == "__main__":
    main()
