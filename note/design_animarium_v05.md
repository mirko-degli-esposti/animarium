# Animarium — documento di design

**Synthetic populations of Italian cities**
**v0.5 — 29 luglio 2026**
Riferimento dati: `GSP_popolazioni_full_riferimento_v16.md` (§ citati sotto).

*Rispetto alla v0.4: `donor_id` risolta e non piu' bloccante (§3.3, §13.3).
`n_eff` ricalcolato con la formula di Kish e per universo di variabile: i
numeri sono molto peggiori e la regola di allarme era rovesciata (§2, §4.1).
Aggiunta §0.1, il metodo di lavoro. Aggiunta §14, cosa tutto questo significa
per SimComm. Invertite F2 e F3 (§10).*

---

## 0. Decisioni prese

| | scelta | stato |
|---|---|---|
| **nome** | **Animarium** — *Synthetic populations of Italian cities* | fissato |
| **stack** | Observable Framework + DuckDB-WASM, statico | verificato (§7.2) |
| **destinazione** | solo interna per ora | `--pubblico` predisposto |
| **riferimento** | una serie, valutata al livello spaziale del filtro | §3.4 |
| **disposizione del file** | tre blocchi di colonne, righe per `zona, sezione` | verificata (§3.2) |
| **`donor_id`** | ricostruito dalla firma AVQ, senza rilanciare la pipeline | verificato (§13.3) |

`Albo Pretorio`, scartato come nome del viewer, resta riservato al corpus di
comunicazioni istituzionali di SimComm/Caffaro, dove nomina l'oggetto giusto.

### 0.1 Il metodo, che si e' rivelato piu' importante del piano

Ogni errore scoperto in questo progetto e' venuto a galla nello stesso modo:
**confrontando con una configurazione in cui la risposta e' nota**. E' la
§11.1 del documento di riferimento, e vale come regola di ingegneria oltre che
di statistica.

| confronto | cosa ha rivelato |
|---|---|
| Q5 contro Q0 | la potatura delle colonne esiste (fattore 47) |
| Q3 contro Q3N | la potatura per riga, a colonne pari |
| Q6 contro Q2 | l'ordinamento per zona serve (22% invece di 100%) |
| MAE grezzo contro MAE normalizzato | il seam e' elevato, ma non dominante |
| distinti contro Kish | `n_eff` sbagliato di un fattore 2,8 |
| ramo tier contro ramo comunale (§11.2 rif.) | due bug latenti, invisibili su un ramo solo |

**Corollario operativo**: nessun numero entra nel design senza il suo
confronto. Un valore assoluto senza termine di paragone non e' una misura, e'
un'impressione.

*Nota di onesta'.* Delle previsioni quantitative fatte in questa sessione,
circa meta' sono state falsificate dalla misura: il seam come sorgente d'errore
dominante, il guadagno di `BYTE_STREAM_SPLIT`, Q5 a 2,1 MB, Kish a 3.000, la
soglia d'allarme su `n_eff` basso. Questo documento va letto come una lista di
ipotesi da falsificare, non come specifiche.

---

## 1. Scopo, utenti, non-obiettivi

**Tre utenti**, in ordine di priorita' temporale: tu adesso, i collaboratori
(Tarantino, Pachet, Zucker, PRISM), il pubblico in seguito.

**Non-obiettivi**, da scrivere nella pagina Metodo:

- non e' uno strumento di stima locale: nessun numero e' una misura del
  quartiere reale;
- non genera popolazioni: consuma i `_full` gia' prodotti;
- non fa inferenza causale ne' previsione.

---

## 2. Il principio guida: livello di garanzia

Quattro classi, visibili sempre.

| classe | badge | attributi | cosa garantisce |
|---|---|---|---|
| **V — vincolato** | pieno | anello 1 | MRE ≈ 4·10⁻⁴ sul constraint set |
| **A — allocato** | mezzo pieno | `sezione`, `eta_anni`, indirizzo, coordinate | MAE 0,74–1,58 per sezione, sotto le assunzioni (8)–(10) |
| **C — condizionato** | contorno | `paese`, `area` | margini censuari, geografia secondo il tier |
| **D — donato** | tratteggiato | le 21 AVQ | **nessuna informazione geografica** (assunzione 6) |

> Qualunque variazione spaziale di una variabile di classe **D** e'
> **interamente compositiva per costruzione**.

### 2.1 Numerosita' efficace — i numeri veri

Misurati (§13.3), non piu' stimati. `n_eff` di Kish, `n²/Σm²`:

| | individui | firme distinte | `n_eff` | banda ×|
|---|---|---|---|---|
| Modena, comune | 184.597 | 4.199 | **1.520** | **11,0** |
| Bologna, comune | 390.098 | 4.207 | **1.599** | **15,6** |

Tre fatti che cambiano il design:

**(a) `n_eff` non cresce con la popolazione.** Bologna ha il doppio degli
abitanti di Modena e lo stesso `n_eff`: il tetto e' il pool regionale, non la
citta'. La banda di confidenza su una media AVQ comunale e' **11–16 volte**
piu' larga di quella ingenua.

**(b) `n_eff` satura anche filtrando.** A Modena passa da 1.520 sull'intera
citta' a 1.514 sul quartiere piu' grande a 1.442 sul terzo. Filtrare riduce
`n` e quasi mai i donatori, quindi **il rapporto `n/n_eff` e' massimo per la
citta' intera** e cala stringendo. La correzione serve di piu' dove il numero
sembra piu' autorevole, e quasi per niente sulle fette piccole.

**(c) Un solo `n_eff` per il blocco AVQ non esiste.** Le 21 variabili hanno
universi che vanno dal 100% di `SALUTE` al 13,6% di `BMIMIN`. La firma piu'
riusata (1511 individui a Modena, 2900 a Bologna) e' quasi certamente quella
dei minori, per i quali `BMI`, le dodici `PUNTIFI` e `VOTOUSL` sono non
applicabili: la 21-upla si riduce a quattro o cinque valori e donatori
realmente diversi diventano indistinguibili. Quegli individui **non
partecipano** al calcolo di `PUNTIFI10`, quindi penalizzarne la banda con la
loro coda e' un errore di universo.

**Regola**: `n_eff` si calcola **per variabile, sui soli individui che quella
variabile ce l'hanno**. Da verificare col blocco 5 di `verifica_donor.py`
(§11, punto 2).

---

## 3. Modello dei dati

### 3.1 Un bundle, non l'albero di lavoro

Il viewer non legge mai `~/progetti/gsp/data/comuni/...`, legge un bundle
versionato prodotto da uno script di export. E' cio' che rende l'app
pubblicabile senza modifiche.

```
bundle/                          fuori dal repo git, ricostruibile
  manifest.json
  qualita.json
  comuni/036023/
    pop.parquet                  42 colonne, 10 row group, 3,12 MB
    rif_comune.parquet · rif_zona.parquet · rif_sezione.parquet
    sezioni.topojson · zone.topojson
  regioni/emilia_romagna.topojson
```

### 3.2 Disposizione fisica del file — e' una scelta di progetto

DuckDB-WASM legge **intervalli di byte contigui**, non colonne: chiedere tre
colonne o cinque dello stesso blocco costa identico. I blocchi li definiamo
noi. Cinque decisioni, tutte verificate:

**(a) Colonne in tre blocchi per uso.**

```
A  filtri e marginali   zona, quartiere, sesso, eta, stato_civile,
                        cittadinanza, istruzione, condizione, background,
                        origine_genitori, paese, area, eta_anni, quinq, sezione
B  AVQ                  le 21 _num
C  pesanti (mappa)      id, indirizzo_fonte, via, civico, lon, lat
```

**(b) Righe per `zona, sezione`**: il filtro su una zona legge il **22%** di
quanto legge la stessa query senza filtro. Le sezioni restano contigue dentro
la zona, quindi il lazo continua a potare.

**(c) Row group da 20.000 righe** — dieci per Modena, footer 0,073 MB.

**(d) `id` in `DELTA_BINARY_PACKED`**: da 0,79 MB (la colonna piu' pesante del
file) a meno di 0,09.

**(e) `lon`/`lat` in `BYTE_STREAM_SPLIT`**: 0,65 → 0,59 MB. Guadagno modesto
perche' le coordinate sono al piu' 60.488 valori distinti e il dizionario ne
stava gia' sfruttando la ripetizione. Si tiene, ma la motivazione originale
era sbagliata.

**Risultato su Modena**: CSV 57,76 MB → Parquet **3,123 MB (5,4%)**.

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
| `quinq` int8 | fatto, candidato alla rimozione (§12) |
| **`donor_id`** | **risolto**: ricostruito dalla firma AVQ (§13.3) |
| `donor_anno` int16 | desiderabile, non bloccante — ricostruirebbe il *planned missing* |
| `cella_avq` | desiderabile — stimabile in parte dal blocco 3 di `verifica_donor.py`, appena si leggono le definizioni vere di `macroeta` e `istr4` |
| `lon_j`, `lat_j` | da fare in `build_bundle` |

**`donor_id` non richiede di rilanciare `assign_avq.py`.** L'hot-deck copia
tutte e 21 le variabili in blocco dallo stesso donatore, quindi **la 21-upla
di valori e' la firma del donatore**. Nel pool emiliano 418 donatori (il 9%)
hanno 21-uple indistinguibili — differenza identica a Modena e Bologna, quindi
proprieta' del pool e non della citta'. L'errore va nella **direzione
prudente**: `n_eff` esce sottostimato, quindi le bande escono ~5% troppo
larghe.

Le **AVQ grezze sono state eliminate** dal Parquet: `non_applicabile` contro
mancante non serve riga per riga, perche' il *planned missing* dipende
dall'annata del donatore. Blocco B da 2,659 a 1,411 MB.

### 3.4 Il riferimento — una serie, tre livelli, tre stati

**Regola del livello**: riferimento valutato al livello spaziale piu' fine
compatibile col filtro — comune, zona, sezione — con ricaduta **dichiarata**.

**Regola dello stato**:

| stato | significato | come si legge lo scarto |
|---|---|---|
| **verifica** | il valore reale a quel livello **e' entrato nella pipeline** | uno scarto e' un bug, non un risultato |
| **validazione esterna** | esiste e **non e' stato usato** | informativo, linea di base 1–2% (anagrafe contro censimento) |
| **assente** | nessun dato osservato | dichiarato, ricaduta al livello superiore |

Lo stato si **deriva** da `constraints_2024/manifest.json` e dalle colonne che
`enrich.py` usa come pesi. Non si mantiene a mano.

**Dove la validazione esterna c'e'**: solo nelle fonti comunali anagrafiche di
zona, mai usate come *livelli*. Modena 0,982–1,007 sulla popolazione per
quartiere; Primo Maggio 0,329 contro 0,293.

**Dove non c'e'**: a livello di sezione tutto l'osservato e' usato.
`P30–P45`/`P67–P82` sono il **peso stesso** dell'allocazione. Non esiste alcun
test out-of-sample dell'assunzione (8).

**Sorgenti non spaziali**: censimento comunale per l'anello 1, `paese`,
`area`; ISTAT eta' singola per `eta_anni`; **AVQ regionale pesata** per le 21
di classe D. Per queste ultime la marginale sintetica comunale e la stima
regionale differiscono esattamente per composizione: la riga di scomposizione
lo spiega per intero, su ogni pannello.

---

## 4. Le viste

Cinque pagine: **Citta'**, **Esplora**, **Individuo**, **Confronta**,
**Metodo**.

### 4.1 Esplora — i filtri

**Dodici filtri in v1**: `zona`, `sezione` (solo via lazo), `sesso`, `eta`,
`stato_civile`, `cittadinanza`, `istruzione`, `condizione`, `background`,
`origine_genitori`, `paese`, `area`, `eta_anni`.

**Le AVQ non sono filtri in v1**, sono variabili mostrate.

**Barra di stato**: `n` · % della citta' · sezioni toccate · livello del
riferimento attivo · **`n/n_eff` e il fattore di banda per la variabile AVQ
mostrata**.

> **Correzione rispetto alla v0.4.** Avevo previsto un badge rosso su
> `n_eff < 30`. E' la regola sbagliata: `n_eff` satura e non scende quasi mai,
> mentre il rapporto `n/n_eff` esplode proprio sulle sottopopolazioni grandi
> (Bologna comune: 244). **Il badge va acceso su `n/n_eff` alto, non su
> `n_eff` basso.** Resta utile una soglia su `n` piccolo, ma per la ragione
> diversa del rumore campionario.

### 4.2 Marginali

Una serie sintetica, fino a due marcatori: **rombo pieno** per il censimento
(stato *verifica*, scarto atteso zero, ogni deviazione e' un guasto), **rombo
vuoto** per la fonte comunale (stato *validazione esterna*, scarto atteso
1–2%, cio' che eccede e' segnale).

Senza filtro spaziale il riferimento comunale e' anche **il valore atteso
sotto indipendenza**, quindi lo scarto *e* l'associazione. Con filtro spaziale
diventa un confronto quartiere per quartiere.

**Modalita' Δ** con banda `√(p(1−p)/n)`, e per la classe D con `n_eff`
**della variabile mostrata** (§2.1c).

**Riga di scomposizione** (classi C e D):

```
AMBIENTE, Fiumicello vs riferimento:  Δ = −0,07
   spiegato dalla composizione:  −0,07  (100%)
   residuo areale:                0,00
```

**Pannello fiducia istituzionale**: dodici medie su asse 0–10, riferimenti
nazionali AVQ 2024 come tacche fisse (vigili del fuoco 8,10 · forze
dell'ordine 6,70 · ASL 6,34 · Comune 5,13 · Regione 4,65), fasce di copertura
come tratteggio, matrice di correlazione con `min_periods` sotto.

### 4.3 Mappa

**Individui** (punti con jitter), **Sezioni** (default analitico), **Zone**,
**Esagoni** H3.

**La metrica di default non e' il conteggio**: in ordine **quota**, **lift**,
**z**, conteggio. Shrinkage empirico-bayesiano, o almeno sbiadimento sotto ~30
individui filtrati.

**Affiancamento sintetico/reale**: sulle sezioni e' **verifica**; sulle zone
contro fonte comunale e' validazione vera.

**Da gestire**: convivenze al centroide di zona escluse dai punti per default;
`indirizzo_fonte = "zona"` idem; jitter radiale deterministico ~8 m; tiles
Protomaps self-hosted, nessuna chiave API.

### 4.4 Individuo

Quaranta campi per anello col badge di garanzia, catena di provenienza inclusa
la colonna `P` che ha determinato la sezione, e **la firma AVQ con quanti
altri individui la condividono** — che rende visibile in un caso concreto cio'
che §2.1 dice in aggregato. E' gia' il prompt della persona per il tier 2.

### 4.5 Confronta

**A — comune** (sicuro). **B — distribuzione fra sezioni** (il livello
giusto: unita' ISTAT omogenee, mentre 4 quartieri di Modena e 33 di Brescia
non sono confrontabili), con la decomposizione della varianza 5,9× → 43,5× in
forma grafica. **C — zone**, con avviso.

**Avviso obbligatorio sulle AVQ**: Parma, Bologna e Modena condividono lo
stesso pool di 4.629 donatori, quindi ogni differenza AVQ fra le tre e'
integralmente compositiva. Brescia attinge a un pool diverso, e un confronto
Brescia–Bologna mescola composizione e differenza di pool.

### 4.6 Metodo e qualita'

MRE per comune · MAE per sezione come scatter · copertura AVQ nelle tre fasce
· **riuso dei donatori e `n_eff` per variabile** · le sette assunzioni in
elenco cliccabile che illumina gli attributi dipendenti · tier del paese coi
numeri di §6 · provenienza dei nomi di zona e l'incidente di Bologna · i
diagnostici di §13.1.

---

## 5. Interazione e stato

Crossfilter completo, stato interamente nell'URL:

```
/esplora/017029?zona=17029012&sesso=F&istruzione=laurea_o_its
               &mostra=AMBIENTE,PUNTIFI10&mappa=sezioni&metrica=lift
```

Esportazioni con provenienza incorporata.

---

## 6. Grafica

**Estetica dell'anagrafe**: serif per titoli e numeri grandi, sans neutro per
l'interfaccia, monospaziato con cifre tabulari per tutte le cifre. Un accento
per il sintetico; riferimenti in neutro scuro distinti per **forma** (rombo
pieno o vuoto), cosi' la distinzione verifica/validazione sopravvive alla
stampa in bianco e nero. Densita' alta, small multiples. Base chiara per le
coropleti, scura per i punti.

---

## 7. Architettura

### 7.1 Gli strumenti

| strato | strumento | stato |
|---|---|---|
| bundle | Python: pandas, geopandas, duckdb, pyarrow, mapshaper | `to_parquet.py` fatto |
| impalcatura | Observable Framework | da avviare |
| query | DuckDB-WASM 1.29 | verificato |
| grafici | Observable Plot | |
| mappa | MapLibre GL + deck.gl | |
| hosting | nessuno; `serve_range.py` in locale | |

### 7.2 Il modello di costo

```
costo(query) = footer + Σ  peso(blocco toccato) × (row group non potati / totale)
```

Footer 0,073 · A 0,675 · B 1,411 · C 0,980. Sette misure su otto entro il 20%
(§13.2).

**Tre corollari verificati:**

1. **Il numero di colonne richieste e' irrilevante.** Tre colonne o cinque
   dello stesso blocco costano identico (0,792 MB). L'unita' e' il blocco.
2. **Potatura per riga pulita**: un row group su dieci costa il 10,7%.
3. **Potatura spaziale**, ma solo grazie all'ordinamento per `zona`: 22%.

**Conseguenza**: il vincolo previsto in v0.3 — «serve `agg_sezioni.parquet`
per la prima schermata» — **e' sparito**. La prima schermata costa 0,79 MB.

### 7.3 Cosa costa zero adesso e molto dopo

1. interruttore `--pubblico` in `build_bundle.py` (toglie `via` e `civico`,
   aggancia i punti al centroide dell'edificio);
2. etichettatura: banner «individuo sintetico», watermark negli export, campo
   di provenienza in ogni CSV;
3. nessuna dipendenza da servizi con chiave API.

Ogni individuo sta a un civico ANNCSU esistente, e su Brescia il contesto
Caffaro rende la prima cosa meno teorica che altrove.

---

## 8. Estensibilita'

Tutto cio' che varia sta in `manifest.json`, generato da `G.COMUNI`.

```
to_parquet.py {CODICE} → build_bundle.py {CODICE} → verifica_bundle.py {CODICE}
```

Controlli obbligatori: totali coincidenti col censimento; `nomi_verificati:
[metodo_a, metodo_b]` **obbligatorio**; poligoni pari alle zone attese;
nessun individuo fuori dal poligono comunale; copertura AVQ nelle fasce; stato
di ogni riferimento derivato e non scritto a mano.

**Emilia-Romagna**: i prerequisiti regionali sono pagati, ogni capoluogo costa
la mezz'ora di §12 del riferimento. Dieci comuni ≈ 1,8 milioni di individui e
**~30 MB di bundle**.

---

## 9. Prestazioni — misurate

Modena, 184.597 individui, Parquet 3,123 MB, server locale.

| operazione | misurato |
|---|---|
| init DuckDB-WASM (a caldo) | 0,69–0,77 s |
| footer, una volta per sessione | 0,073 MB |
| esplorazione demografica, prima query | 0,79 MB · ~1,3 s |
| ogni filtro successivo sullo stesso blocco | **0 byte** · 100–220 ms |
| filtro su una zona | 0,23 MB · ~0,6 s |
| pannello fiducia istituzionale | 0,82 MB |
| mappa a punti | 0,92 MB |
| **sessione piena** | **~2,5 MB** |

Il vincolo non e' piu' la banda ma il tempo di inizializzazione, fisso e
indipendente dai dati.

---

## 10. Fasi

**F0 — i due diagnostici.** ✔ Modena e Parma (§13.1). Restano Bologna e
Brescia.

**F1 — smoke test dello stack.** ✔ Tutte e tre le domande risolte (§13.2).

**F2 — `donor_id`.** ✔ Risolto senza toccare la pipeline (§13.3).

**F3 — bundle minimo + primo pannello.** ← **invertito rispetto alla v0.4.**

Invece di scrivere `build_bundle.py` completo — manifest, tre tavole di
riferimento, geometrie, tre stati — costruire il **bundle minimo che serve a
un pannello solo**: il Parquet che gia' esiste, piu' un manifest ridotto a
etichette e ordini delle modalita'. Poi fare il pannello dei marginali su
Modena.

*Ragione*: abbiamo quattro versioni di design, un modello di costo, quattro
script diagnostici e **zero grafici**. L'apparato epistemico e' cresciuto piu'
della cosa che deve annotare. Sara' il pannello a dire cosa serve davvero nel
manifest, invece di indovinarlo adesso. Il rischio dell'ordine precedente era
scrivere lo schema alla cieca e riscriverlo tre volte; il rischio di questo e'
rifare un po' di lavoro sul bundle, che costa molto meno.

**F4 — bundle completo**: riferimenti coi tre stati, geometrie, aggregati.

**F5 — mappa.**

**F6 — le altre citta' e il manifest.** L'estensibilita' va provata
aggiungendo il quarto comune senza toccare l'interfaccia.

**F7 — Individuo, Metodo, Confronta**, e la grafica in senso proprio.

---

## 11. Questioni aperte

1. **Definizioni vere di `macroeta` e `istr4`** in `assign_avq.py`. Senza,
   il blocco 3 di `verifica_donor.py` e' illeggibile — le mappature usate sono
   mie invenzioni — e `cella_avq` non e' stimabile. **Blocca l'unica cosa che
   resta da capire sulle AVQ.**
2. **Blocchi 5 e 6 di `verifica_donor.py`**: `n_eff` per universo di variabile,
   e identita' della firma piu' riusata. Danno i numeri veri per §2.1.
3. **AVQ filtrabili**: solo mostrate in v1, o filtrabili dietro interruttore?
4. **Fonti comunali di zona**: quali disponibili come *livelli*? Determina
   quanta validazione esterna l'app puo' offrire.
5. **Emilia-Romagna**: quanti capoluoghi, e la vista regionale entra in v1?
6. **Modena e i 37 rioni**: se entrassero in pipeline, la vista Zone di Modena
   passerebbe da inutile a interessante.
7. **Le due riparazioni di §13.1** — permutazione di `istruzione` entro
   (zona, sesso, bin), ed esclusioni α=0 sulle coppie impossibili — vanno fatte
   e in che ordine rispetto al viewer?
8. **Campionamento degli agenti per firma** invece che per individuo (§14).

---

## 12. Registro dei miglioramenti

### Fatti, con effetto misurato

| | effetto |
|---|---|
| colonne in tre blocchi per uso | Q5 da 2,297 a 0,915 MB |
| righe per `zona, sezione` | filtro di zona al 22% invece del 100% |
| `id` DELTA_BINARY_PACKED | 0,79 MB → <0,09 MB |
| `lon`/`lat` BYTE_STREAM_SPLIT | 0,65 → 0,59 MB (motivazione originale sbagliata) |
| AVQ grezze eliminate | blocco B 2,659 → 1,411 MB |
| row group 50k → 20k | potatura piu' fine, footer 0,049 → 0,073 MB |
| `donor_id` dalla firma | sblocca `n_eff` senza rilanciare la pipeline |
| `n_eff` di Kish invece dei distinti | il numero cambia di un fattore 2,8 |
| | **file 5,22 → 3,12 MB** |

### Proposti

- **rimuovere `quinq`** (0,089 MB, il 13% del blocco caldo): e'
  `least(eta_anni // 5, 15)` in SQL;
- **rimuovere `quartiere`**: e' l'etichetta di `zona`, sta nel manifest. Con
  `quinq`, porta A da 0,675 a ~0,55 MB;
- **`donor_anno`** per ricostruire la distinzione fra `non_applicabile` e
  *planned missing*;
- **sostituire la riga «aggregazione tipica»** in `to_parquet.py`: suggerisce
  che il costo sia la somma delle colonne richieste, mentre e' il blocco.

### Scartati, col motivo — per non ripensarci

- **spezzare il blocco AVQ** in fiducia e sanita'. Q4 ha la sovralettura
  peggiore, ma **non e' una query realistica**: il pannello fiducia mostra
  tutte e dodici le `PUNTIFI` insieme e leggerebbe il sotto-blocco comunque;
- **AVQ in int8 con sentinelle**: ogni `PUNTIFI` pesa gia' mezzo byte a riga,
  il dizionario e' a 4 bit, praticamente all'ottimo teorico;
- **`agg_sezioni.parquet` come requisito strutturale**: mascherava un costo
  d'ingresso che non esiste. Resta come comodita';
- **coordinate in float64**: float32 da ~0,4 m basta per la resa cartografica;
- **rilanciare `assign_avq.py` per `donor_id`**: la firma lo ricostruisce.

---

## 13. Diario delle misure

### 13.1 F0 — i due diagnostici (Modena e Parma)

**(a) Il seam quinquennale.** MAE grezzo indistinguibile dalle altre classi;
normalizzando per dimensione di classe le due classi del seam finiscono **nei
primi tre posti su sedici in entrambe le citta'** (per caso ~6·10⁻⁴). Ma
l'eccesso e' del 40%: **l'ipotesi di uniformita' non e' una sorgente d'errore
dominante.**

*Risultato sistematico non previsto*: dentro ciascuno dei cinque bin veri il
sintetico pende verso il **giovane**, prima classe in positivo e ultima in
negativo, **dieci prove su dieci**, 0,10–0,44 pp.

```
            Modena              Parma
15-24   +0,158 / −0,158    +0,186 / −0,186
25-34   +0,110 / −0,110    +0,278 / −0,278
35-49   +0,351 / −0,438    +0,234 / −0,260
50-64   +0,101 / −0,097    +0,201 / −0,131
65-74   +0,199 / −0,199    +0,209 / −0,209
```

Nella regione infantile il verso **si inverte**: `10-14` sovrarappresentata di
+0,37 e +0,35. E' l'unico posto dove opera la frazione 4/5–1/5, e ha una
direzione precisa — **il sintetico mette troppo pochi novenni**. Indiziato per
il resto: l'assunzione (9).

*Terzo fatto*: i totali di bin SDMX non coincidono con gli stessi bin
aggregati dalle colonne P — fino a +1,42% (Parma `15-24`) e −1,02% (Modena
`75+`). **Non replica in segno**, quindi rumore fra due prodotti censuari, non
calendario. Il controllo «totale SDMX = `P1`» e' esatto e non puo' vederlo.

**(b) Coerenza eta'–istruzione**: 4.867 violazioni a Modena (2,64%), 5.434 a
Parma (2,74%), concentrate nei bin `9-14` e `15-24`, zero altrove.
*Riparazione*: permutare `istruzione` entro (zona, sesso, bin).

**(c) Due record impossibili gia' al livello del bin**, entrambi a Parma, zero
a Modena: `diploma` a 2 anni e `post_laurea` a 13. Sono 10⁻⁵, massa residua
del fit. *Riparazione*: otto coppie `(bin, istruzione)` fra le esclusioni α=0.

*Previsione da raccogliere*: se e' massa residua, il numero scala col supporto
(Modena 645.120 → 0; Parma 2.096.640 → 2; Bologna 2.903.040 → ?; Brescia
5.322.240 → ?).

### 13.2 F1 — smoke test DuckDB-WASM (Modena, file riordinato)

| | misurato | modello | scarto |
|---|---|---|---|
| Q0 `count(*)` | 0,073 | 0,073 | esatto |
| Q1 3 colonne di A | 0,792 | 0,748 | +6% |
| Q2 5 colonne di A | 0,792 | 0,748 | +6% |
| Q3 A+id, 1 rg su 10 | 0,167 | 0,141 | +18% |
| Q3N A+id, tutti | 0,948 | 0,748 | +27% |
| Q4 zona + `PUNTIFI10_num` | 0,823 | 0,600 | +37% |
| Q5 `lon`, `lat` | 0,915 | 1,053 | −13% |
| Q6 filtro su una zona | 0,230 | 0,208 | +11% |

**Q3/Q3N = 10,7%** · **Q6/Q2 = 21,8%**. Tempi a caldo 100–220 ms.

*Errore di metodo commesso e corretto*: la prima misura di Q3 era contaminata,
perche' le query di una sessione si scaldano a vicenda — Q1 aveva gia' letto
il blocco A, quindi Q2 e' costata **zero byte**. Da qui la modalita' isolata e
la query di controllo a colonne pari. La contaminazione, letta come fenomeno
invece che come errore, e' cio' che ha rivelato la struttura a blocchi.

### 13.3 F2 — `donor_id` dalla firma AVQ

**Firme distinte**: Modena 4.199 contro 4.617 donatori dichiarati, Bologna
4.207 contro 4.625. **Differenza identica, −418**: proprieta' del pool
emiliano, non delle citta'. Verificabile contando le 21-uple distinte nel pool
AVQ, che dovrebbe dare ~4.211.

Coerenza interna: 4.617/4.199 = 1,0995 e riuso 44,0/40,0 = 1,100.

**`n_eff` di Kish** (`n²/Σm²`), contro il conteggio dei distinti:

| | individui | distinti | Kish | banda × |
|---|---|---|---|---|
| Modena, comune | 184.597 | 4.199 | **1.520** | **11,0** |
| Bologna, comune | 390.098 | 4.207 | **1.599** | **15,6** |

Il conteggio dei distinti sbagliava di un fattore 2,8. La ragione: Kish e' una
statistica di secondo momento e vive nella coda che i quantili non vedono. La
firma piu' riusata — 1511 individui a Modena, 2900 a Bologna — vale da sola
**circa il 10% del peso statistico dell'intera citta'**.

*Limite noto*: quella firma e' quasi certamente quella dei minori, per i quali
la 21-upla si riduce a quattro o cinque valori. I numeri ×11,0 e ×15,6 sono
quindi calcolati sull'universo sbagliato: vanno rifatti per variabile
(§11, punto 2) prima di entrare in §2.1 come definitivi.

---

## 14. Cosa significa per SimComm

Il risultato di §13.3 pesa piu' sul tier 2 che su Animarium, e vale la pena
annotarlo qui perche' e' emerso da qui.

**La diversita' psicologica effettiva di una popolazione di agenti non e'
quella dei suoi individui: e' quella di ~1.500 donatori**, e non cresce
prendendo una citta' piu' grande. Per una campagna da 120 agenti probabilmente
non morde. Ma qualunque affermazione sulla *distribuzione* — «in questa
popolazione sintetica il 23% diffida del Comune» — ha errore standard fissato
da 1.500, non da 184.597.

**Il secondo ordine e' piu' insidioso.** Due agenti che condividono la firma
hanno profili psicologici **identici**, non simili: stessa fiducia
istituzionale, stessa percezione ambientale, stessa salute percepita. In una
simulazione LLM le loro risposte sono correlate per costruzione e non sono
evidenza indipendente. Con riusi medi di 40–93, in un campione casuale di 120
agenti da Bologna la probabilita' di collisioni non e' trascurabile.

**Domanda di disegno sperimentale**, non di implementazione: **conviene
campionare gli agenti per firma invece che per individuo?** Garantirebbe
profili distinti al prezzo di distorcere le quote demografiche — che sono
esattamente cio' che il tier 1 esiste per garantire. Il compromesso fra
rappresentativita' demografica e indipendenza psicologica va deciso, e
dichiarato nel paper.

Se non altro, va misurato: in una campagna gia' eseguita, quante coppie di
agenti condividevano la firma?
