# Animarium

**Synthetic populations of Italian cities.**

Visualizzatore delle popolazioni sintetiche GSP: scelta della citta', filtro
sugli attributi, confronto dei marginali col dato censuario, mappa degli
individui, scheda del singolo.

Consuma i file `popolazione_K9C_avq_full.csv` prodotti dalla pipeline GSP.
Non li genera. Pipeline e dati stanno in `~/progetti/gsp/`, documentati in
`GSP_popolazioni_full_riferimento_v16.md`.

Citta': **Bologna** (390.098), **Brescia** (198.259), **Parma** (198.121),
**Modena** (184.597). Bundle complessivo: **16,65 MB**.

**Online, in forma provvisoria**: <https://animarium.pages.dev>
Bundle completo, con avviso esplicito sulla risoluzione dei dati. Decisioni e
limiti in `note/design_animarium_v07.md`, §15.

---

## Avvio rapido

```bash
python build/serve_range.py
```

`http://localhost:8000/build/pannello_marginali.html`

Se il bundle non c'e' ancora, o dopo aver rigenerato le popolazioni:

```bash
for C in 036023 034027 037006 017029; do
  python build/to_parquet.py        $C --drop-avq-raw
  python build/manifest_min.py      $C
  python build/build_riferimenti.py $C
done
python build/build_indice.py
```

Ripubblicare:

```bash
python build/deploy.py
npx wrangler pages deploy deploy/ --project-name animarium --branch main
```

---

## Struttura

```
animarium/
  build/            Python (bundle, diagnostici, server, deploy) + pagine HTML
  bundle/           generato, escluso da git, ricostruibile in un comando
  deploy/           generato, escluso da git, cio' che finisce online
  note/             documento di design, versionato
```

---

## Stato

| fase | | |
|---|---|---|
| F0 | diagnostici sulla pipeline | ✔ Modena e Parma — mancano Bologna e Brescia |
| F1 | smoke test DuckDB-WASM | ✔ modello di costo verificato |
| F2 | `donor_id` dalla firma AVQ | ✔ senza toccare la pipeline |
| F3 | pannello dei marginali | ✔ |
| F4 | riferimento censuario dal constraint set | ✔ copertura 20% delle coppie |
| F5 | mappa | ◧ quota, punti, navigazione, base cartografica |
| — | **pubblicazione** | ✔ provvisoria, in anticipo su F9 |
| F6 | `donor_id` nel Parquet + pannello AVQ con `n_eff` | ← **prossimo** |
| F7 | confronto fra citta' | |
| F8 | pagina Metodo | |
| F9 | grafica e pubblicazione definitiva | |

Dettagli, misure, questioni aperte e ritrattazioni:
`note/design_animarium_v07.md`.

---

## Il pannello

**Filtri**: si clicca sulle barre, non c'e' una colonna di controlli. I filtri
attivi diventano pillole rimovibili, lo stato sta interamente nell'URL —
quindi una vista si manda in una riga e si cita in un paper.

**Tre marcatori**, con tre significati distinti:

| | cos'e' | lo scarto misura |
|---|---|---|
| **barra** | la sottopopolazione filtrata | — |
| **tacca** | la citta' intera | l'**associazione** fra filtro e attributo |
| **rombo** | il censimento al livello del filtro | l'**errore del modello** |

Il rombo compare solo dove un blocco del constraint set contiene insieme gli
attributi del filtro e quello mostrato: **67 coppie su 333**. Filtrando un
quartiere c'e' per sesso, eta', istruzione, background e cittadinanza; non c'e'
per stato civile, condizione e origine dei genitori — e il pannello lo dichiara
invece di nasconderlo.

**Mappa** (pulsante `mappa`, pigra: legge il blocco C solo su richiesta):

- **quota** — frazione del filtro sul totale locale, celle di ~150 m, sotto 25
  abitanti in grigio. E' l'unico modo informativo;
- **punti** — individui campionati con jitter deterministico, sopra uno strato
  grigio della citta' intera. **Cliccabili**: si apre la scheda dell'individuo,
  con il livello di garanzia per ogni attributo.

Zoom con la rotella, trascinamento, `adatta`. Base cartografica opzionale.

**Export**: CSV e LaTeX (`booktabs`) della tabella completa, SVG per singolo
pannello — costruito a mano, senza librerie di grafici.

---

## Gli script

### Bundle

```bash
python build/to_parquet.py 036023 --drop-avq-raw
```
CSV → Parquet ottimizzato per query filtrate dal browser: colonne in tre
blocchi per uso, righe per `zona, sezione`, row group da 20.000, `id`
delta-encoded, coordinate in byte-stream-split, AVQ grezze eliminate.
Modena: 57,76 MB → **3,12 MB**.

```bash
python build/manifest_min.py 036023
```
Etichette leggibili, ordine stabile delle modalita', conteggi non filtrati.
Stampa in coda le modalita' senza ordine dichiarato, gia' formattate per
essere incollate in `ORDINI`.

```bash
python build/build_riferimenti.py 036023
```
Estrae i conteggi censuari da `cs_K9C.json` (`n = alpha × N`) e stampa la
**tabella di copertura**: per ogni filtro, quali attributi hanno un
riferimento reale e quali sono modello.

```bash
python build/build_indice.py
```
`bundle/comuni.json` per il menu delle citta'. Da rifare quando se ne aggiunge
una.

```bash
python build/deploy.py [--push]
```
Assembla `deploy/` — `index.html`, `smoke.html`, `bundle/` — pronta per
Cloudflare Pages. Con `--push` la spinge su un ramo `gh-pages` usa-e-getta,
cosi' i Parquet non entrano nella storia di `main`.

### Diagnostici sulla pipeline

```bash
python build/diag_quinq.py 036023 --out out/residui.csv
```
Riaggrega alle sedici classi quinquennali ISTAT e confronta con
`P{30+k}`/`P{67+k}` per sezione e sesso. Diagnostico del *seam* a nove anni.

```bash
python build/diag_istruzione_eta.py 036023 --out out/viol.csv
```
Coerenza fra eta' esatta e titolo di studio (~2,7% di combinazioni
impossibili), piu' il controllo delle combinazioni impossibili gia' a livello
di bin.

```bash
python build/verifica_donor.py 036023
```
Ricostruisce `donor_id` dalla 21-upla di valori AVQ — l'hot-deck copia il
blocco intero dallo stesso donatore, quindi la 21-upla e' la firma. Riporta
`n_eff` di Kish e il fattore di allargamento della banda.

```bash
python build/ispeziona_cs.py 036023
```
Anatomia del constraint set: blocchi, zeri espliciti, e se le combinazioni
logicamente impossibili sono vincolate o semplicemente non coperte.

```bash
python build/verifica_vincoli.py 036023 --out out/celle.csv
```
Verifica cella per cella **contro il pavimento di rumore**: z-score invece di
errore relativo. `sd(z)` e' anche il fattore di inflazione della varianza
dovuto all'autocorrelazione della catena.

### Misura

```bash
python build/serve_range.py [--dir deploy]
```
Server statico con supporto Range e conteggio dei byte per intervallo.
`python -m http.server` **non** supporta Range e falserebbe ogni misura.
Serve anche lo smoke test.

---

## Il modello di costo

DuckDB-WASM legge **intervalli di byte contigui, non colonne**: chiedere tre
colonne o cinque dello stesso blocco costa identico.

```
costo(query) = footer + Σ  peso(blocco) × (row group non potati / totale)
```

Su Modena: footer 0,073 MB · blocco filtri 0,675 · blocco AVQ 1,411 · blocco
mappa 0,980. Una sessione completa costa **~2,5 MB**; i filtri successivi
dentro lo stesso blocco costano **zero byte** e 100–220 ms. La potatura per
riga vale il 10,7%, quella spaziale il 22% — quest'ultima solo grazie
all'ordinamento per `zona`.

---

## Regola di lavoro

Nessun numero entra nel design senza il suo confronto. Un valore assoluto
senza termine di paragone non e' una misura, e' un'impressione.

Ogni errore trovato finora e' emerso confrontando con una configurazione a
risposta nota: Q5 contro Q0, Q3 contro Q3N, Q6 contro Q2, MAE grezzo contro
normalizzato, conteggio dei distinti contro Kish, errore relativo contro
z-score. Due risultati sono stati ritirati per questa via, e sono annotati
come tali nel documento di design.

---

## Da riprendere

1. **`donor_id` nell'export** e pannello AVQ con `n_eff` per universo di
   variabile. E' il pezzo mancante della catena dell'onesta': oggi le AVQ
   compaiono solo nella scheda individuo. E' anche cio' che serve al lavoro su
   Caffaro.
2. **`--pubblico` in `to_parquet.py`**: toglie `via` e `civico`. Previsto dal
   design fin dall'inizio, mai scritto, e necessario prima della pubblicazione
   per arXiv — dove la configurazione si rovescia: codice pubblico, dati
   degradati.
3. Definizioni vere di `macroeta` e `istr4` in `assign_avq.py`; definizione di
   MRE in `fit_cs.py`, che differisce da quella dello strumento per un fattore
   `√(2/π)`.

Sul binario della pipeline, separato: le due riparazioni post-hoc (permutazione
di `istruzione`, 26 esclusioni α=0), i diagnostici su Bologna e Brescia, e il
blocco `sesso × background × origine_genitori` che mostra |z| fino a 4,0.
