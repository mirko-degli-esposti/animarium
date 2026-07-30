# Animarium — documento di design

**Synthetic populations of Italian cities**
**v0.4 — 29 luglio 2026**
Riferimento dati: `GSP_popolazioni_full_riferimento_v16.md` (§ citati sotto).

*Rispetto alla v0.3: nome fissato. Aggiunta §3.2, la disposizione fisica del
file come scelta di progetto. Aggiunta §7.2, il modello di costo ricavato dal
passo 2. Riscritta §9 con misure invece che stime. Aggiunta §12, registro dei
miglioramenti, con annotati anche quelli scartati e il perche'. Aggiunta §13,
diario delle misure.*

---

## 0. Decisioni prese

| | scelta | stato |
|---|---|---|
| **nome** | **Animarium** — *Synthetic populations of Italian cities* | fissato |
| **stack** | Observable Framework + DuckDB-WASM, applicazione statica | **verificato sul campo** (§7.2) |
| **destinazione** | solo interna per ora | interruttore `--pubblico` predisposto |
| **riferimento** | una serie, valutata al livello spaziale del filtro | §3.4 |
| **disposizione del file** | tre blocchi di colonne, righe per `zona, sezione` | **verificata** (§3.2, §7.2) |

`Albo Pretorio`, valutato e scartato come nome del viewer, resta riservato al
corpus di comunicazioni istituzionali di SimComm/Caffaro — ordinanze comunali,
materiali ATS/ARPA — dove nomina l'oggetto giusto.

---

## 1. Scopo, utenti, non-obiettivi

**Tre utenti, in ordine di priorita' temporale.**

1. **Tu, adesso.** Ispezione, controllo qualita', ricerca di anomalie prima
   che finiscano in un paper.
2. **I collaboratori** (Tarantino, Pachet, Zucker, il consorzio PRISM).
   Devono capire *cosa possono chiedere ai dati* senza leggere mille righe di
   documentazione. Link permanenti citabili.
3. **Il pubblico.** Fuori portata per ora, ma le decisioni che lo renderebbero
   possibile costano zero adesso e molto dopo (§7.3).

**Non-obiettivi dichiarati**, da scrivere nella pagina Metodo:

- non e' uno strumento di stima locale: nessun numero e' una misura del
  quartiere reale;
- non genera popolazioni: consuma i `_full` gia' prodotti;
- non fa inferenza causale ne' previsione.

---

## 2. Il principio guida: livello di garanzia

Ogni numero mostrato appartiene a una di **quattro classi**, visibile sempre.

| classe | badge | attributi | cosa garantisce |
|---|---|---|---|
| **V — vincolato** | pieno | anello 1 | marginali e incroci del constraint set, MRE ≈ 4·10⁻⁴ |
| **A — allocato** | mezzo pieno | `sezione`, `eta_anni`, `via`, `civico`, `lon/lat` | allocazione esatta per sezione (MAE 0,74–1,58), sotto le assunzioni (8)–(10) |
| **C — condizionato** | contorno | `paese`, `area` | vincolato ai margini censuari, struttura geografica secondo il tier |
| **D — donato** | tratteggiato | le 21 AVQ | **nessuna informazione geografica** (assunzione 6) |

> Qualunque variazione spaziale di una variabile di classe **D** e'
> **interamente compositiva per costruzione**. L'app lo dice dove il numero
> appare, non altrove.

**Numerosita' efficace.** Le statistiche AVQ poggiano sui **donatori
distinti**, non sugli individui: a Bologna il riuso medio e' 84×, quindi 500
individui possono nascere da ~6 donatori. Tutte le bande di incertezza sulle
AVQ usano `n_eff`. Richiede `donor_id` nel bundle — dipendenza aperta (§11).

---

## 3. Modello dei dati

### 3.1 Un bundle, non l'albero di lavoro

Il viewer **non legge mai** `~/progetti/gsp/data/comuni/...`. Legge un bundle
versionato, prodotto da uno script di export. E' cio' che rende l'app
pubblicabile senza modifiche: in locale e in rete gira sugli stessi byte.

```
bundle/                          fuori dal repo git, ricostruibile
  manifest.json
  qualita.json
  comuni/
    036023/
      pop.parquet                42 colonne, 10 row group
      rif_comune.parquet         riferimento livello 0  (§3.4)
      rif_zona.parquet           riferimento livello 1
      rif_sezione.parquet        riferimento livello 2
      sezioni.topojson
      zone.topojson
  regioni/
    emilia_romagna.topojson
```

**Il bundle sta fuori dal repo.** Si ricostruisce in un comando; il repo
contiene codice, schema del manifest e script di build.

### 3.2 Disposizione fisica del file — e' una scelta di progetto

Misurata nel passo 2 (§7.2), non ereditata dal CSV. Cinque decisioni, tutte
verificate:

**(a) Colonne ordinate per uso, in tre blocchi.** DuckDB-WASM legge
**intervalli di byte contigui**, non colonne: chiedere tre colonne o cinque
dello stesso blocco costa identico. I blocchi li definiamo noi.

```
A  filtri e marginali   zona, quartiere, sesso, eta, stato_civile,
                        cittadinanza, istruzione, condizione, background,
                        origine_genitori, paese, area, eta_anni, quinq, sezione
B  AVQ                  le 21 _num
C  pesanti (mappa)      id, indirizzo_fonte, via, civico, lon, lat
```

Chi esplora paga A. Chi apre il pannello fiducia paga B. Chi apre la mappa a
punti paga C. Nessuno paga cio' che non guarda.

**(b) Righe ordinate per `zona, sezione`.** Il filtro piu' frequente
dell'interfaccia e' la zona; con l'ordinamento per sola sezione non potava
nulla. Misurato: il filtro su una zona legge il **22%** di quanto legge la
stessa query senza filtro. Le sezioni restano contigue dentro la zona, quindi
la selezione a lazo continua a potare.

**(c) Row group da 20.000 righe** — dieci per Modena. Compromesso fra
granularita' della potatura e peso del footer, che a dieci gruppi e' 0,073 MB.

**(d) `id` in `DELTA_BINARY_PACKED`.** Era la colonna piu' pesante del file
(0,79 MB, il 15%): successione strettamente crescente, il dizionario fallisce
e zstd non morde. Dopo la codifica sta sotto i 90 KB.

**(e) `lon`/`lat` in `BYTE_STREAM_SPLIT`.** Guadagno modesto (0,65 → 0,59 MB)
perche' le coordinate sono al piu' 60.488 valori distinti su 184.597 righe, e
il dizionario ne stava gia' sfruttando la ripetizione. Si tiene, ma la
motivazione originale era sbagliata.

**Risultato su Modena**: CSV 57,76 MB → Parquet **3,123 MB (5,4%)**.
Dieci capoluoghi emiliani stanno in una trentina di megabyte.

| blocco | peso | quota |
|---|---|---|
| A filtri e marginali | 0,675 MB | 21,6% |
| B AVQ | 1,411 MB | 45,2% |
| C pesanti | 0,980 MB | 31,4% |
| footer | 0,073 MB | 2,3% |

### 3.3 Colonne aggiunte dall'export

| colonna | stato |
|---|---|
| `id` int32 | fatto, delta-encoded |
| `quinq` int8 | fatto, ma candidato alla rimozione (§12) |
| `donor_id` | **atteso dalla pipeline** — blocca `n_eff` |
| `donor_anno` int16 | **atteso** — rende ricostruibile il *planned missing*, e ha permesso di eliminare 21 colonne AVQ grezze |
| `cella_avq` | atteso — rende ispezionabile il collasso gerarchico |
| `macroeta`, `istr4` | attesi — sono le variabili su cui girano davvero le AVQ |
| `lon_j`, `lat_j` | da fare in `build_bundle` |

Le **AVQ grezze sono state eliminate**: `non_applicabile` contro mancante e'
una distinzione che non serve riga per riga, perche' il *planned missing*
dipende dall'annata del donatore e non dall'individuo. Si recupera per intero
con `donor_anno`. Il blocco B e' sceso da 2,659 a 1,411 MB.

### 3.4 Il riferimento — una serie, tre livelli, tre stati

**Regola del livello.** Riferimento valutato al livello spaziale piu' fine
compatibile col filtro. Tre livelli e una ricaduta:

| filtro attivo | riferimento |
|---|---|
| nessuno, o solo attributi non spaziali | censimento comunale |
| un quartiere o un insieme di zone | tavole di zona (`zona_2023/`) + fonti comunali dove esistono |
| una selezione di sezioni | `P1`, `ST1`, `ST16/19`, `ST25–30`, `P30–45`/`P67–82` |
| zona ∧ attributi assenti dalla tavola | ricaduta al comune, **dichiarata** |

**Regola dello stato.** Ogni coppia (attributo × livello) sta in uno di tre
stati, mostrato come badge:

| stato | significato | come si legge lo scarto |
|---|---|---|
| **verifica** | il valore reale a quel livello **e' entrato nella pipeline** | accordo garantito. Uno scarto e' un bug, non un risultato |
| **validazione esterna** | esiste e **non e' stato usato** | informativo, con linea di base 1–2% (anagrafe contro censimento) |
| **assente** | nessun dato osservato a quel livello | dichiarato, ricaduta al livello superiore |

Lo stato **non si mantiene a mano**: `constraints_2024/manifest.json` dichiara
gia' fonte e tipo di ogni blocco, `enrich.py` dichiara le colonne usate come
pesi. `build_bundle.py` deriva la classificazione da li'.

**Dove la validazione esterna c'e'**: solo nelle fonti comunali anagrafiche di
zona, mai usate come *livelli* (il tier ne usa la forma come seed, con margini
censuari). Sono i numeri di §10 del riferimento: Modena 0,982–1,007 sulla
popolazione per quartiere; Primo Maggio 0,329 contro 0,293.

**Dove non c'e', e va detto.** A livello di sezione **tutto l'osservato e'
usato**: `P30–P45` e `P67–P82` non sono un dato accessorio, sono il **peso
stesso** dell'allocazione,

```
w(σ) = ( Σ_{k∈e} P_{s,k}(σ) ) × [ q_{s,e3}(σ) se straniero, 1−q se italiano ]
```

Non esiste quindi alcun test out-of-sample dell'assunzione (8): il dato per
farlo non c'e', che e' il motivo per cui l'assunzione e' dichiarata.

**Le tre sorgenti non spaziali**: censimento comunale per l'anello 1, `paese`,
`area`; ISTAT eta' singola per `eta_anni`; **AVQ regionale pesata** per le 21
di classe D, con intervallo di confidenza. Per queste ultime la marginale
sintetica comunale e la stima regionale differiscono **esattamente per
composizione**, quindi la riga di scomposizione di §4.2 spiega lo scarto per
intero: una verifica gratuita su ogni pannello.

---

## 4. Le viste

Cinque pagine: **Citta'**, **Esplora**, **Individuo**, **Confronta**,
**Metodo**.

### 4.1 Esplora — i filtri

Colonna sinistra filtri, corpo marginali, mappa a destra o sotto. Crossfilter.

**Filtri di v1**, dodici: `zona` (multiselezione o dalla mappa), `sezione`
(solo via lazo), `sesso`, `eta`, `stato_civile`, `cittadinanza`, `istruzione`,
`condizione`, `background`, `origine_genitori`, `paese`, `area`, `eta_anni`.

**Le AVQ non sono filtri in v1**, sono variabili mostrate: filtrare su
`FIDUCIA` e guardare la mappa produce una figura che sembra dire qualcosa
sulla geografia della fiducia e non lo dice.

**Barra di stato**: `n` · % della citta' · `n_eff` donatori · sezioni toccate
· livello del riferimento attivo · badge rosso se `n < 200` o `n_eff < 30`.

### 4.2 Marginali

Una serie sintetica, fino a due marcatori:

| elemento | resa |
|---|---|
| **sintetico** | barre piene, colore d'accento |
| **riferimento censuario** | rombo **pieno** — stato *verifica* |
| **riferimento comunale** | rombo **vuoto** — stato *validazione esterna* |

Non si leggono allo stesso modo: sul rombo pieno lo scarto atteso e' zero e
ogni deviazione e' un guasto; sul vuoto lo scarto atteso e' l'1–2% dello
sfasamento anagrafe–censimento, e cio' che eccede e' segnale.

Senza filtro spaziale il riferimento comunale e' anche **il valore atteso
sotto indipendenza** fra attributo mostrato e filtro, quindi lo scarto *e*
l'associazione. Con filtro spaziale diventa un confronto quartiere per
quartiere. Due usi dello stesso pannello, da etichettare.

**Modalita' Δ**: scarti dal riferimento con banda `√(p(1−p)/n)`, e `n_eff` per
la classe D.

**Riga di scomposizione** (classi C e D):

```
AMBIENTE, Fiumicello vs riferimento:  Δ = −0,07
   spiegato dalla composizione:  −0,07  (100%)
   residuo areale:                0,00
```

**Pannello fiducia istituzionale**: dodici medie su asse 0–10, con i
riferimenti nazionali AVQ 2024 come tacche fisse (vigili del fuoco 8,10 ·
forze dell'ordine 6,70 · ASL 6,34 · Comune 5,13 · Regione 4,65) e le fasce di
copertura come tratteggio. Sotto, la matrice di correlazione con
`min_periods`, che riproduce la struttura a due fattori.

### 4.3 Mappa

Quattro modalita': **Individui** (punti con jitter), **Sezioni** (il default
analitico), **Zone**, **Esagoni** H3.

**La metrica di default non e' il conteggio** — un conteggio filtrato
riproduce la densita' di popolazione. In ordine: **quota**, **lift**, **z**,
conteggio. Con quota e lift serve shrinkage empirico-bayesiano, o almeno lo
sbiadimento delle sezioni sotto ~30 individui filtrati.

**Affiancamento sintetico/reale**: sulle sezioni e' **verifica**, non
validazione — quelle colonne sono i pesi dell'allocazione. Sulle zone contro
fonte comunale e' validazione vera, ed e' li' che la mappa dice qualcosa di
nuovo.

**Dettagli da gestire**: convivenze (50–630) al centroide di zona, escluse dai
punti per default; `indirizzo_fonte = "zona"` idem; jitter radiale
deterministico ~8 m sui civici condivisi; tiles Protomaps self-hosted, nessuna
chiave API.

### 4.4 Individuo

Quaranta campi per anello, ciascuno col badge di garanzia, con la catena di
provenienza inclusa la colonna `P` che ha determinato la sezione. E' lo
strumento di debug piu' efficace che esista, ed **e' gia' il prompt della
persona** per il tier 2.

### 4.5 Confronta

**Livello A — comune (sicuro)**: marginali affiancati, tabella carta
d'identita' di §10.

**Livello B — distribuzione fra sezioni (il livello giusto)**: le sezioni sono
unita' ISTAT di disegno omogeneo, i 4 quartieri di Modena e i 33 di Brescia
no. ECDF o ridgeline, piu' la decomposizione della varianza (5,9× → 43,5×) in
forma grafica.

**Livello C — zone (con avviso)**: partizioni non confrontabili.

**Avviso obbligatorio sulle AVQ**: Parma, Bologna e Modena condividono lo
stesso pool di 4.629 donatori emiliani, quindi ogni differenza AVQ fra le tre
e' integralmente compositiva. Brescia attinge a un pool diverso (8.111), e un
confronto Brescia–Bologna mescola composizione e differenza di pool.

### 4.6 Metodo e qualita'

- MRE per comune; MAE per sezione come scatter osservato–sintetico;
- copertura AVQ nelle tre fasce, nota sul *planned missing*;
- riuso dei donatori, col tetto strutturale (99,7–100% del pool);
- **le sette assunzioni** in elenco cliccabile: cliccando la (8) si illuminano
  gli attributi che ne dipendono, ovunque nell'app;
- tier del paese, coi numeri di §6 (2,08–2,57 volte l'ipotesi nulla al
  quartiere; 1,01–1,04 alla sezione, cioe' nulla, correttamente);
- provenienza dei nomi di zona e l'incidente di Bologna;
- **i due diagnostici di §13**, con le mappe dei residui.

---

## 5. Interazione e stato

Crossfilter completo; stato interamente nell'URL:

```
/esplora/017029?zona=17029012,17029015&sesso=F&istruzione=laurea_o_its
               &mostra=AMBIENTE,PUNTIFI10&mappa=sezioni&metrica=lift
```

Serve a mandare una vista a Tarantino in una riga, citare una figura in un
paper con un link riproducibile, ricostruire in un secondo lo stato in cui hai
visto qualcosa di strano.

Esportazioni con provenienza incorporata: PNG/SVG, CSV dei marginali con
riferimento e stato, permalink, GeoJSON degli aggregati.

---

## 6. Grafica

**Estetica dell'anagrafe**: registro amministrativo reso in modo
contemporaneo. Serif per titoli e numeri grandi, sans neutro per
l'interfaccia, **monospaziato con cifre tabulari per tutte le cifre**. Un solo
accento per il sintetico; i riferimenti in neutro scuro, distinti per *forma*
(rombo pieno o vuoto) e non per tinta, cosi' la distinzione
verifica/validazione sopravvive alla stampa in bianco e nero. Densita' alta,
small multiples piccoli e numerosi. Base chiara per le coropleti, scura per i
punti. Transizioni brevi sui cambi di filtro; nient'altro si muove.

---

## 7. Architettura

### 7.1 Gli strumenti

| strato | strumento | stato |
|---|---|---|
| bundle | Python: pandas, geopandas, duckdb, pyarrow, mapshaper | `to_parquet.py` fatto |
| impalcatura | Observable Framework | da avviare |
| query | DuckDB-WASM 1.29 | **verificato** |
| grafici | Observable Plot | |
| mappa | MapLibre GL + deck.gl | |
| geometrie | TopoJSON + mapshaper | |
| hosting | nessuno per ora; `serve_range.py` in locale | |

### 7.2 Il modello di costo — risultato del passo 2

Le tre domande del cancello hanno tutte risposta affermativa, e la misura ha
prodotto qualcosa di piu' utile delle risposte singole: **una formula che
permette di calcolare il costo di un pannello prima di scriverlo.**

```
costo(query) = footer + Σ  peso(blocco toccato) × (row group non potati / totale)
```

Con footer 0,073 · A 0,675 · B 1,411 · C 0,980 su Modena, sette misure su otto
cadono entro il 20% della previsione (§13.2).

**Tre corollari, tutti controintuitivi e tutti verificati:**

1. **Il numero di colonne richieste e' irrilevante.** Q1 ne chiede tre e Q2
   cinque dello stesso blocco: costano **identico**, 0,792 MB. L'unita' di
   lettura e' il blocco.
2. **La potatura per riga funziona in modo pulito**: un row group su dieci
   costa il 10,7% del totale.
3. **La potatura spaziale funziona**, ma solo grazie all'ordinamento per
   `zona`: il filtro su un quartiere costa il 22% della stessa query senza
   filtro. Con l'ordinamento per sola sezione avrebbe letto tutto.

**Conseguenza per il design**: il vincolo che avevo previsto in §9 della v0.3
— «serve `agg_sezioni.parquet` per coprire la prima schermata» — **e'
sparito**. La prima schermata costa 0,79 MB e arriva in poco piu' di un
secondo. L'aggregato precalcolato resta utile ma non e' piu' strutturale.

### 7.3 Cosa costa zero adesso e molto dopo

1. **interruttore `--pubblico` in `build_bundle.py`**: rimuove `via` e
   `civico`, aggancia i punti al centroide dell'edificio. Va scritto ora anche
   se non si usera';
2. **etichettatura**: banner «individuo sintetico», watermark negli export
   PNG, campo di provenienza in ogni CSV;
3. **nessuna dipendenza da servizi con chiave API**, mappa inclusa.

Ogni individuo sintetico sta a un civico ANNCSU esistente, e su Brescia il
contesto Caffaro rende la prima cosa meno teorica che altrove.

---

## 8. Estensibilita'

**Aggiungere una citta' non deve toccare il codice dell'interfaccia.** Tutto
cio' che varia sta in `manifest.json`, generato da `G.COMUNI`: codice, nome,
slug, regione, pool AVQ regionale, livello ASC e sua etichetta, numero di
zone, tier, attributi presenti, riferimenti per livello col rispettivo stato,
numeri di qualita'.

```
to_parquet.py {CODICE}
build_bundle.py {CODICE}
verifica_bundle.py {CODICE}
```

Controlli obbligatori: totali coincidenti col censimento; campo
`nomi_verificati: [metodo_a, metodo_b]` **obbligatorio**, altrimenti il bundle
non si costruisce; poligoni pari alle zone attese; nessun individuo fuori dal
poligono comunale; copertura AVQ nelle fasce; `donor_id` presente e riuso
coerente; stato di ogni riferimento derivato e non scritto a mano.

**Emilia-Romagna.** I prerequisiti regionali sono gia' pagati: ogni capoluogo
costa la mezz'ora di §12 del riferimento. Piacenza, Reggio, Ferrara, Ravenna,
Forli', Cesena, Rimini portano la regione a dieci comuni, ~1,8 milioni di
individui e **~30 MB di bundle**.

Con dieci citta' la decomposizione tra/dentro su dieci partizioni di taglia
diversa diventa una figura che oggi non esiste in nessun paper. Non e' un
obiettivo di v1, ma la struttura del bundle la prevede.

---

## 9. Prestazioni — misurate, non stimate

Su Modena, 184.597 individui, Parquet 3,123 MB, server locale.

| operazione | misurato |
|---|---|
| inizializzazione DuckDB-WASM (a caldo) | 0,69–0,77 s |
| footer, pagato una volta per sessione | 0,073 MB |
| esplorazione demografica, prima query | 0,79 MB · ~1,3 s |
| ogni filtro successivo sullo stesso blocco | **0 byte** · 100–220 ms |
| filtro su una zona | 0,23 MB · ~0,6 s |
| pannello fiducia istituzionale | 0,82 MB |
| mappa a punti | 0,92 MB |
| **sessione piena, tutto visitato** | **~2,5 MB** |

Meno di due fotografie. Il vincolo di progetto non e' piu' la banda ma il
tempo di inizializzazione, che e' fisso e indipendente dai dati.

---

## 10. Fasi

**F0 — i due diagnostici.** ✔ fatto su Modena e Parma. Risultati in §13.1.
Restano Bologna e Brescia.

**F1 — smoke test dello stack.** ✔ fatto. Tutte e tre le domande risolte,
modello di costo in §7.2, misure in §13.2.

**F2 — bundle.** In corso. `to_parquet.py` fatto e verificato;
`build_bundle.py` da scrivere: manifest, aggregati per sezione, geometrie,
riferimenti coi tre stati. **Rischio principale**: `donor_id`.

**F3 — Esplora, senza mappa.** Filtri, marginali, regola del livello, tre
stati, modalita' Δ, scomposizione. Un comune. Qui si decidono tipografia,
badge e palette.

**F4 — mappa.** Quattro modalita', metriche, shrinkage, affiancamento,
selezione spaziale.

**F5 — le altre citta' e il manifest.** L'estensibilita' va provata
aggiungendo il quarto comune senza toccare l'interfaccia.

**F6 — Individuo, Metodo, Confronta**, e la grafica in senso proprio.

---

## 11. Questioni aperte

1. **`donor_id`**: recuperabile dai file esistenti, o richiede di rilanciare
   `assign_avq.py` sui quattro comuni? Blocca F2 e tutta la statistica su
   `n_eff`. Se va rilanciato, aggiungere nello stesso passaggio `donor_anno`,
   `cella_avq` e il livello di collasso.
2. **AVQ filtrabili**: solo mostrate in v1, o filtrabili dietro interruttore?
3. **Fonti comunali di zona**: quali sono disponibili come *livelli*, oltre a
   quelle gia' usate come seed? Determina quanta validazione esterna l'app puo'
   offrire.
4. **Emilia-Romagna**: quanti capoluoghi nei prossimi mesi, e la vista
   regionale entra o resta predisposta?
5. **Modena e i 37 rioni**: se entrassero in pipeline, la vista Zone di Modena
   passerebbe da inutile a interessante.
6. **Le due riparazioni di §13.1** vanno fatte, e in che ordine rispetto al
   viewer?

---

## 12. Registro dei miglioramenti

### Fatti, con effetto misurato

| | effetto |
|---|---|
| colonne in tre blocchi per uso | Q5 da 2,297 a 0,915 MB |
| righe per `zona, sezione` | filtro di zona al 22% invece che al 100% |
| `id` DELTA_BINARY_PACKED | 0,79 MB → <0,09 MB |
| `lon`/`lat` BYTE_STREAM_SPLIT | 0,65 → 0,59 MB (motivazione originale sbagliata) |
| AVQ grezze eliminate | blocco B 2,659 → 1,411 MB |
| row group 50k → 20k | potatura piu' fine, footer 0,049 → 0,073 MB |
| | **file 5,22 → 3,12 MB** |

### Proposti, non ancora fatti

- **rimuovere `quinq`** dal Parquet: 0,089 MB, il 13% del blocco caldo, ed e'
  `least(eta_anni // 5, 15)` in SQL. Serviva ai diagnostici, che pero' girano
  in Python sul CSV;
- **rimuovere `quartiere`**: e' l'etichetta di `zona`, un dizionario da 4–33
  voci che sta gia' nel manifest. Con `quinq`, porta A da 0,675 a ~0,55 MB,
  cioe' −18% su cio' che si legge a ogni sessione;
- **`donor_anno`** al posto delle AVQ grezze eliminate, per ricostruire la
  distinzione fra `non_applicabile` e *planned missing*;
- **riga «aggregazione tipica» in `to_parquet.py`**: e' fuorviante. Suggerisce
  che il costo sia la somma delle colonne richieste, mentre e' il blocco. Va
  sostituita dalla tabella dei tre blocchi.

### Scartati, col motivo — per non ripensarci

- **spezzare il blocco AVQ** in fiducia e sanita'. Q4 ha la sovralettura
  peggiore (0,75 MB netti per una colonna da 0,090), ma **Q4 non e' una query
  realistica**: nell'interfaccia la fiducia istituzionale e' un pannello che
  mostra tutte e dodici le `PUNTIFI` insieme, e leggerebbe il sotto-blocco
  comunque. Spezzare aiuterebbe solo chi chiede una sola variabile sanitaria,
  che e' il caso raro;
- **AVQ in int8 con sentinelle**. Ogni `PUNTIFI` pesa gia' 0,090 MB su 184.597
  righe, cioe' mezzo byte a riga: con dodici valori distinti il dizionario e'
  a 4 bit, praticamente all'ottimo teorico. Non c'e' niente da guadagnare;
- **`agg_sezioni.parquet` come requisito strutturale** per la prima schermata.
  Serviva a mascherare un costo d'ingresso che non esiste (§7.2). Resta come
  comodita', non come necessita';
- **coordinate in float64**. float32 da ~0,4 m di precisione, piu' che
  sufficiente per la resa cartografica.

---

## 13. Diario delle misure

### 13.1 F0 — i due diagnostici (Modena e Parma)

**(a) Il seam quinquennale.** Riaggregazione del sintetico alle sedici classi
ISTAT contro `P{30+k}`/`P{67+k}`, per sezione e sesso.

*Risultato negativo pulito*: il MAE grezzo del seam e' indistinguibile dagli
altri. Normalizzando per la dimensione di classe — la regola di §11.1 del
riferimento — le due classi del seam finiscono **nei primi tre posti su
sedici in entrambe le citta'** (Modena `5-9` 1° e `10-14` 3°; Parma `10-14` 1°
e `5-9` 2°). Per caso vale ~6·10⁻⁴. Ma l'eccesso e' del 40%, non di un ordine
di grandezza: **l'ipotesi di uniformita' non e' una sorgente d'errore
dominante.**

*Risultato sistematico, non previsto*: dentro ciascuno dei cinque bin veri, il
sintetico pende verso il **giovane**, con la prima classe in positivo e
l'ultima in negativo. **Dieci prove su dieci** fra le due citta', 0,10–0,44
punti percentuali.

```
            Modena              Parma
15-24   +0,158 / −0,158    +0,186 / −0,186
25-34   +0,110 / −0,110    +0,278 / −0,278
35-49   +0,351 / −0,438    +0,234 / −0,260
50-64   +0,101 / −0,097    +0,201 / −0,131
65-74   +0,199 / −0,199    +0,209 / −0,209
```

Nella regione infantile il verso **si inverte**: `10-14` sovrarappresentata di
+0,37 (Modena) e +0,35 (Parma). E' l'unico posto dove opera la frazione
4/5–1/5, e ha una direzione precisa — **il sintetico mette troppo pochi
novenni**: la quota vera dei novenni dentro il quinquennio 5–9 non e' un
quinto. Indiziato per il resto: l'assunzione (9), la forma dell'anagrafe
comunale entro il bin.

*Terzo fatto, il piu' grosso*: i totali di bin del constraint set SDMX non
coincidono con gli stessi bin aggregati dalle colonne P — fino a **+1,42%**
(Parma, `15-24`) e −1,02% (Modena, `75+`). **Non replica in segno** fra le due
citta', quindi non e' calendario ma rumore fra due prodotti censuari. Il
controllo obbligatorio «totale SDMX = `P1`» e' esatto al singolo abitante e
non puo' vederlo.

**(b) Coerenza fra eta' esatta e istruzione.**

| | violazioni | quota |
|---|---|---|
| Modena | 4.867 | 2,64% |
| Parma | 5.434 | 2,74% |

Concentrate nei bin `9-14` (18,8% e 22,2%) e `15-24` (16,5% e 16,1%), zero
altrove. Il vincolo sull'istruzione usa la classe grossa `Y9-24`, l'IPF con
soglie distribuisce i titoli su tutto l'arco, e `eta_anni` arriva dopo in modo
indipendente.

*Riparazione proposta*: **permutare `istruzione` fra individui entro
(zona, sesso, bin)**. E' esattamente cio' che e' vincolato, e l'assunzione (8)
dichiara `sezione ⊥ istruzione`, quindi non si perde nulla di garantito.

*Nota sulla variazione fra quartieri*: la quota grezza varia (Parma 2,04% a
3,19% su 13 quartieri) ma **deve** variare, perche' e' la quota di 9-24enni
moltiplicata per il tasso interno. Il test corretto e' il tasso condizionato
sugli individui a rischio, aggiunto allo script.

**(c) Due record impossibili gia' a livello di bin**, entrambi a Parma, zero a
Modena: `diploma` a 2 anni (bin `0-8`, fuori dall'universo dell'istruzione,
che parte da 9 anni) e `post_laurea` a 13 (bin `9-14`, soglia 22). Sono 10⁻⁵,
massa residua del fit, non un errore sistematico.

*Riparazione proposta*: aggiungere alle esclusioni α=0 le otto coppie
`(bin, istruzione)` impossibili — `0-8` × {elementare, media, diploma,
laurea_o_its, post_laurea} e `9-14` × {diploma, laurea_o_its, post_laurea}.
Effetto collaterale: cambia il conteggio delle celle escluse, quindi la
formula di controllo di §12 del riferimento va aggiornata.

*Previsione da raccogliere* su Bologna e Brescia: se e' massa residua del fit,
il numero scala col supporto (Modena `|X|`=645.120 → 0 record; Parma
2.096.640 → 2; Bologna 2.903.040 → ?; Brescia 5.322.240 → ?).

### 13.2 F1 — smoke test DuckDB-WASM (Modena, file riordinato)

Otto query isolate, ognuna contro un'istanza appena creata.

| | misurato | modello | scarto |
|---|---|---|---|
| Q0 `count(*)` | 0,073 | 0,073 | esatto |
| Q1 3 colonne di A | 0,792 | 0,748 | +6% |
| Q2 5 colonne di A | 0,792 | 0,748 | +6% |
| Q3 A+id, 1 row group su 10 | 0,167 | 0,141 | +18% |
| Q3N A+id, tutti | 0,948 | 0,748 | +27% |
| Q4 zona + `PUNTIFI10_num` | 0,823 | 0,600 | +37% |
| Q5 `lon`, `lat` | 0,915 | 1,053 | −13% |
| Q6 filtro su una zona | 0,230 | 0,208 | +11% |

Rapporti chiave: **Q3/Q3N = 10,7%** (un row group su dieci, esatto);
**Q6/Q2 = 21,8%** (due row group su dieci).

Tempi a caldo 100–220 ms; inizializzazione 0,69–0,77 s.

*Errore di metodo commesso e corretto*: la prima misura di Q3 era contaminata,
perche' le query di una stessa sessione si scaldano a vicenda — Q1 aveva gia'
letto il blocco A, quindi Q2 e' costata **zero byte** e Q3 misurava solo il
residuo. Da qui la modalita' isolata e la query di controllo Q3N a colonne
pari. La contaminazione, letta come fenomeno invece che come errore, e'
esattamente cio' che ha rivelato la struttura a blocchi.
