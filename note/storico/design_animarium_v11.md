# Animarium — documento di design

**Synthetic populations of Italian cities**
**v0.11 — 2 agosto 2026**
Riferimento dati: `GSP_popolazioni_full_riferimento_v21.md`, **v2.1**.
I rimandi a §13, §14 e §15 senza altra indicazione sono a quel documento.

*Rispetto alla v0.9: undici comuni invece di quattro, e due livelli di
constraint set. La copertura del riferimento non e' identica fra citta' ma
**fra livelli** (§3.4). Il tier fa degradare `paese` da C a D su cinque comuni
(§2). Batteria della fiducia a quattordici voci (§4.7). `n_eff` misurato su
undici comuni, con Castenaso come caso di contrasto (§2.1). `build_bundle.py`
orchestra la costruzione (§8). Nuova §4.8, l'atlante regionale.*

*v0.11: le medie nazionali della batteria non sono piu' cablate ma calcolate
dai microdati e lette dal bundle — la fonte che cercavamo non esisteva.*

---

## 0. Decisioni prese

| | scelta | stato |
|---|---|---|
| **nome** | **Animarium** — *Synthetic populations of Italian cities* | fissato |
| **stack** | pagina statica + DuckDB-WASM, senza scaffold | verificato (§7.2) |
| **riferimento** | censimento estratto da `cs_K9C.json` | fatto (§3.4) |
| **disposizione del file** | tre blocchi di colonne, righe per `zona, sezione` | verificata (§3.2) |
| **`donor_id`** | ricostruito dalla firma AVQ | **nel Parquet** (§3.3) |
| **mappa** | griglia da `lon`/`lat`, nessuna geometria | fatta (§4.3) |
| **pubblicazione** | Cloudflare Pages da cartella, repo privato | fatta, provvisoria (§15) |

### 0.1 Il metodo

Ogni errore di questo progetto e' emerso **confrontando con una
configurazione a risposta nota** — la §11.1 del riferimento, che si e'
rivelata una regola di ingegneria oltre che di statistica.

| confronto | esito |
|---|---|
| Q5 contro Q0 | la potatura delle colonne esiste (fattore 47) |
| Q3 contro Q3N | potatura per riga, a colonne pari: 10,7% |
| Q6 contro Q2 | l'ordinamento per zona serve: 22% invece di 100% |
| MAE grezzo contro normalizzato | il seam e' elevato, non dominante |
| distinti contro Kish | `n_eff` sbagliato di un fattore 2,8 |
| errore relativo contro z-score | il MRE per cella era **tutto** pavimento di rumore |
| target del blocco A contro quello del blocco B | incoerenza cross-blocco **falsificata** |
| `n_eff` sull'universo giusto contro quello sbagliato | fattore 2,1, in meglio |

**Corollario**: nessun numero entra nel design senza il suo confronto.

*Bilancio delle previsioni.* Circa meta' delle previsioni quantitative sono
state falsificate dalla misura. Due ritrattazioni e una correzione sono
registrate qui: la discrepanza «fra prodotti censuari» era rumore (z = 0,24);
l'incoerenza cross-blocco non esiste; `n_eff` della v0.6 era calcolato
sull'universo sbagliato.

---

## 1. Scopo, utenti, non-obiettivi

Tre utenti in ordine temporale: **tu adesso**, i **collaboratori**, il
**pubblico** — arrivato prima del previsto e in forma provvisoria (§15).

**Non-obiettivi**: non e' uno strumento di stima locale; non genera
popolazioni; non fa inferenza causale ne' previsione.

---

## 2. Livello di garanzia

| classe | segno | attributi | cosa garantisce |
|---|---|---|---|
| **V — vincolato** | ■ | anello 1 | riprodotto entro il rumore di campionamento |
| **A — allocato** | ◧ | `sezione`, `eta_anni`, indirizzo, coordinate | esatto per sezione, sotto le assunzioni (8)–(10) |
| **C — condizionato** | □ | `paese`, `area` | margini censuari, geografia secondo il tier |
| **D — donato** | ▨ | le 23 AVQ | **nessuna informazione geografica** (assunzione 6) |

> **Il tier fa degradare C a D.** Con tier 0 non esiste fonte locale per
> `paese`, quindi non ha **alcuna** informazione sub-comunale: si comporta
> esattamente come le AVQ. Non serve un badge nuovo — serve che la classe
> degradi, e il manifest porta `paese_classe` derivato da `G.tier()`.
> Riguarda cinque comuni su undici: Modena, Rimini, Piacenza, Ferrara,
> Castenaso.

### 2.1 Numerosita' efficace — i numeri veri

`n_eff` di Kish, `n²/Σm²`, dove `m_d` e' il numero di individui che ricevono
le AVQ dal donatore `d`.

**Misurato su undici comuni**, riferimento §13.3. La regola e' una sola:

> **`n_eff` si calcola per variabile, sul suo universo.** Sull'intera
> popolazione non e' una misura di niente.

Il perche' e' quantificato nel riferimento; qui bastano i due numeri che
governano il pannello. Su `PUNTIFI10`, universo 15 anni e piu':

| | individui | `n_eff` | `n/n_eff` | banda × |
|---|---|---|---|---|
| Bologna | 338.890 | 2.845 | 119 | **10,9** |
| Modena | 157.973 | 3.220 | 49 | 7,0 |
| Brescia | 170.704 | 5.655 | 30 | 5,5 |
| **Castenaso** | **13.910** | 2.770 | **5,0** | **2,2** |

`n_eff` sta fra 2.770 e 3.347 su nove comuni su undici — **e' il pool
regionale**, e Brescia sta a 5.655 perche' attinge a quello lombardo.

**Castenaso e' il caso da tenere a mente disegnando il pannello.** Ha 1/24
degli abitanti di Bologna e una banda **cinque volte piu' stretta** sulla
stessa statistica, perche' non satura il pool: ogni donatore porta ancora
informazione quasi indipendente. Sulle variabili donate, una popolazione
sintetica piccola e' piu' affidabile di una grande — e il pannello lo deve
far vedere, non spiegare.

**Corollario per il badge** (correzione della v0.4): l'allarme va acceso su
**`n/n_eff` alto**, non su `n_eff` basso. `n_eff` satura e non scende quasi
mai, mentre il rapporto esplode proprio sulle sottopopolazioni grandi.

### 2.2 Come riportare l'incertezza → **riferimento §13.3**

La derivazione di `n_eff`, l'interpretazione, la correzione per grappolo
familiare e i limiti da dichiarare stanno nel documento di riferimento, §13.3.
Qui restano le tre regole che governano il pannello:

1. **`n_eff` si calcola per variabile, sul suo universo.** Un solo `n_eff`
   per il blocco AVQ non esiste: gli universi vanno dal 100% di `SALUTE` al
   13% di `BMIMIN`.
2. **L'universo si dichiara, non la copertura.** «Universo: 15 anni e piu'»
   descrive il dato; «copertura 87,6%» ne descrive un sintomo.
3. **`VOTOUSL` sta fuori dalla batteria**: e' un giudizio su un servizio
   ricevuto, con universo per esperienza e mancanza **non ignorabile**.

E il numero che serve al disegno: su Modena la banda onesta e' **7,0 volte**
quella ingenua, e sale a **9,0** correggendo per il grappolo familiare.
## 3. Modello dei dati

### 3.1 Il bundle

```
bundle/
  comuni.json
  comuni/036023/
    pop.parquet        43 colonne, 10 row group, 3,47 MB
    manifest.json      etichette, ordini, conteggi non filtrati
    riferimenti.json   conteggi censuari da cs_K9C.json
```

Fuori dal repo git, ricostruibile con **`build_bundle.py`**, che orchestra i
quattro passi su tutti i comuni del registro e stampa un riepilogo unico.
Undici citta': **35,7 MB**.

### 3.2 Disposizione fisica del file

DuckDB-WASM legge **intervalli di byte contigui, non colonne**: chiedere tre
colonne o cinque dello stesso blocco costa identico.

```
A  filtri e marginali   zona, quartiere, sesso, eta, stato_civile, cittadinanza,
                        istruzione, condizione, background, origine_genitori,
                        paese, area, eta_anni, quinq, sezione
B  AVQ                  le 21 _num + donor_id
C  pesanti (mappa)      id, indirizzo_fonte, via, civico, lon, lat
```

Righe per `zona, sezione`; row group da 20.000; `id` in
`DELTA_BINARY_PACKED`; `lon`/`lat` in `BYTE_STREAM_SPLIT`; AVQ grezze
eliminate.

**Modena**: CSV 57,76 MB → Parquet **3,469 MB (6,0%)**. Blocchi: A 0,675 ·
B 1,757 · C 0,980. **Scala linearmente** col numero di righe.

`donor_id` pesa 0,346 MB, il 10% del file: 4.199 valori quasi equiprobabili
non si comprimono, e il passaggio a `int16` non cambia nulla perche' il
dizionario stava gia' lavorando. Sta nel blocco B, quindi lo paga solo chi
apre le AVQ.

### 3.3 Colonne aggiunte

| colonna | stato |
|---|---|
| `id` int32 | fatto, delta-encoded, serve al clic sulla mappa |
| **`donor_id`** int16 | **fatto**: firma AVQ, calcolata prima del drop delle grezze |
| `quinq` int8 | fatto, candidato alla rimozione (§12) |
| `donor_anno`, `cella_avq`, `macroeta`, `istr4` | desiderabili, non bloccanti |

`donor_id` si calcola in `to_parquet.py` **prima** di `--drop-avq-raw`, perche'
la firma e' la 21-upla dei valori grezzi. La verifica e' che riproduca i
numeri di `verifica_donor.py`: Modena 4.199 firme e `n_eff` 1.520, Bologna
4.207 e 1.599. Coincidono.

### 3.4 Il riferimento censuario — dal constraint set

Ogni `alpha × N` del constraint set e' un conteggio censuario. Il riferimento
per (filtro F, attributo A) esiste se e solo se **un blocco completo contiene
F ∪ {A}**. Il livello **non e' cablato**: si risolve per glob, con K10C
escluso perche' e' materiale sperimentale e il viewer non deve mostrarlo.

**La copertura dipende dal livello, non dal comune** (misurato su undici):

| | attributi | combinazioni | coperte | |
|---|---|---|---|---|
| K9C — nove comuni | 9 | 333 | 67 | **20%** |
| K6C — Ferrara, Castenaso | 6 | 96 | 26 | **27%** |

Identica dentro ciascun livello: e' una proprieta' del template di
`build_constraints.py`. Nella v0.9 era descritta come identica *fra le quattro
citta'* — vero allora, perche' erano tutte K9C, e nessuno l'aveva scritto.

> **I conteggi non sono confrontabili, le percentuali si'.** Su un comune non
> articolato 237 delle 333 combinazioni non sono «non coperte»: sono **non
> interrogabili**, perche' `zona`, `background` e `origine_genitori` non
> esistono. E la percentuale esce piu' alta proprio perche' ci sono meno
> attributi, quindi meno incroci non vincolati.

Su un K9C, filtrando la zona:

| filtro | riferimento disponibile per |
|---|---|
| nessuno | tutti e nove gli attributi |
| **`zona`** | `sesso`, `eta`, `istruzione`, `background`, `cittadinanza` |
| `zona` | **non** per `stato_civile`, `condizione`, `origine_genitori` |
| `sesso × eta` | `stato_civile`, `cittadinanza` |
| qualunque | mai `paese`, `area` |

La copertura compare **in barra di stato** in forma breve — *riferimento 20%
degli incroci* — perche' dice, prima ancora di aprire un pannello, che quattro
incroci su cinque sono modello.

Le **fonti comunali anagrafiche** restano l'unica *validazione esterna* e non
sono ancora nel bundle.

---

## 4. Le viste

### 4.1 Esplora — i filtri

Si filtra cliccando le barre; i filtri attivi sono pillole rimovibili.
**Ogni pannello applica tutti i filtri tranne il proprio.** Ordine delle
modalita' stabile fra citta'.

**Gli attributi non sono gli stessi ovunque, e il pannello non lo sa.** Si
costruisce da `manifest.attributi`, quindi la SQL non nomina mai una colonna
che non esiste: undici pannelli sui K9C, otto sui K6C. Nessun caso speciale
nel codice.

L'etichetta del filtro spaziale segue il livello del comune — **Quartiere**
a Brescia, **Zona** a Bologna, **Area** a Ravenna, **Circoscrizione** a
Reggio. Dove `zona` esiste ma e' degenere (un valore solo, `'0'`) il manifest
la esclude: un pannello con una barra al 100% e' peggio che non averlo.

### 4.2 Marginali — tre marcatori

| | cos'e' | lo scarto misura |
|---|---|---|
| **barra** | la sottopopolazione filtrata | — |
| **tacca** | la citta' intera | l'**associazione** |
| **rombo** | il censimento al livello del filtro | l'**errore del modello** |

> **Correzione della v0.5**: la tacca **non si sposta** sotto filtro
> spaziale, il rombo si **aggiunge**. Spostarla incollerebbe il riferimento
> alla barra, perche' i marginali di zona stanno nel constraint set.

Dove il rombo non c'e', il pannello lo dichiara. Ogni pannello riporta lo
**scarto massimo fra sintetico e censimento**.

### 4.3 Mappa

**Nessuna geometria**: griglia da `lon`/`lat`, Web Mercator. Due modi —
**quota** (l'unico informativo) e **punti** con jitter deterministico e
strato grigio della citta' intera. Zoom, pan, base cartografica opzionale.

> **Debito verso §7.3**: la base cartografica e' l'unica dipendenza esterna.
> Via d'uscita: estratto `.pmtiles` di Protomaps servito da noi (§12).

### 4.4 Scheda individuo

Quaranta campi per anello col segno di garanzia, le AVQ con **i nomi delle
istituzioni** e la firma del donatore, e il rendering testuale della persona
— che e' il materiale del prompt per il tier 2. Banner **INDIVIDUO SINTETICO
— NON ESISTE**.

Cliccando due punti vicini si vede se condividono la firma: e' `n_eff` a
occhio nudo.

### 4.5 Confronta — da fare

**A — comune** · **B — distribuzione fra sezioni** (il livello giusto) ·
**C — zone**, con avviso. Avviso obbligatorio: Parma, Bologna e Modena
condividono lo stesso pool di donatori, quindi ogni differenza AVQ fra le tre
e' integralmente compositiva.

### 4.6 Metodo e qualita' — da fare

MRE e z-score per blocco · universi AVQ · riuso e `n_eff` per variabile · le
sette assunzioni cliccabili · tier del paese · l'incidente dei nomi di zona ·
i diagnostici di §13.1 · la tabella di copertura di §3.4 · l'avviso di §15.

### 4.7 Fiducia istituzionale

**Quattordici righe** su asse comune 0–10, ordinate per media, con la **media
come linea** e **due bande sovrapposte**:

- **sottile e chiara**: intervallo al 95% calcolato su `n`;
- **spessa e scura**: calcolato su `n_eff` di Kish.

La distanza fra le due e' la ragione per cui `n_eff` esiste, e mostrarla e'
piu' efficace di qualunque nota. Su Modena senza filtro il rapporto e' 7,0:
la banda ingenua e' un trattino, quella vera un blocco largo.

**Tacche punteggiate** per le medie nazionali, ora su **tutte** le righe: non
sono piu' cablate ma calcolate da `medie_nazionali.py` sui microdati AVQ e
lette da `bundle/medie_nazionali.json`.

> Cinque valori circolavano nelle note **senza citazione**, e cercandone la
> fonte si scopre che non esiste in quella forma: l'ISTAT pubblica
> percentuali, non medie. Ricalcolati, risultano corretti entro 0,045 — ma
> ora sono verificati, riproducibili, coerenti col nostro universo e completi.
> Il pannello lo dichiara: *«elaborazione propria sui microdati AVQ, non una
> cifra pubblicata dall'ISTAT»*.

Il tooltip di ogni riga riporta **lo scarto dall'Italia**, e il CSV esportato
ha la colonna corrispondente. Per Caffaro serve quello: la domanda non e'
quanto Brescia si fida del Comune, ma **quanto se ne fida rispetto al resto
del paese**.

`FIDMED` e `FIDINF` — medici e infermieri del SSN — sono le due voci piu'
rilevanti per Caffaro: fiducia nel personale sanitario in un contesto di
comunicazione del rischio.

**Copertura bassa e mancanza non ignorabile sono cose diverse**, e il pannello
le tratta diversamente:

- **`FORZE_ARMATE` resta nella batteria** pur coprendo ~21%: e' a rotazione
  *dentro* l'annata 2024, quindi il sottocampione con valore e' casuale e la
  mancanza e' ignorabile. La riga porta un avviso — *«21% del campione:
  modulo a rotazione»* — perche' `n_eff` crolla e la banda si allarga, il che
  e' corretto ma va spiegato;
- **`VOTOUSL` sta in fondo, fuori batteria**: giudizio su un servizio
  ricevuto, con universo per **esperienza** — la copertura cresce con l'eta',
  0,12 a 15-24 e 0,30 a 65-74. Chi risponde e' sistematicamente piu' anziano
  e piu' malato: la mancanza **non e' ignorabile**, e la media non e' «il
  giudizio dei modenesi sull'ASL» ma «il giudizio di chi c'e' stato».

**Nota fissa in cima**: le AVQ non hanno informazione geografica
(assunzione 6), quindi filtrando una zona ogni differenza e' compositiva per
costruzione. E' cio' che rende il pannello utilizzabile su Caffaro senza
produrre l'affermazione falsa.

**La corrispondenza `PUNTIFI{n}` → istituzione viene dal codebook**, non
dalle medie: dedurla dalle medie e appaiare poi quelle stesse medie come
riferimento sarebbe circolare. I dati sono il controllo, e lo passano su
cinque ancore (§13.5).

### 4.8 Atlante regionale

Una striscia opzionale sotto l'intestazione con gli undici comuni sulla
mappa. Serve a navigare, ma soprattutto a **dire cosa non copriamo**: dieci
capoluoghi emiliani e un comune da 16.357 abitanti, su un territorio che ne
ha 328. L'assenza e' informazione quanto la presenza, e in una tabella non si
vede.

**Nessuna geometria esterna.** Le posizioni sono i **baricentri della
popolazione**, calcolati da `build_indice.py` sui `lon`/`lat` degli individui.
Per una mappa di navigazione e' anche piu' onesto del centroide territoriale:
indica dove sta la gente, non dove passa il confine. La base cartografica e'
quella scelta nel menu della mappa — `disegnaFondo` e' parametrizzata sulla
vista e serve entrambe.

**Area del cerchio proporzionale alla popolazione**, 4–17 px. La dimensione
NON usa `n/n_eff`: sarebbe la scelta piu' interessante — Castenaso apparirebbe
il piu' solido — ma e' criptica senza spiegazione, e una mappa deve essere
leggibile prima che argomentativa. `n/n_eff` sta nella scheda, dove c'e' spazio
per dirlo.

**Repulsione invece di casi speciali.** Castenaso dista 10 km da Bologna e
nella proiezione le cade sopra. I dischi che si sovrapporrebbero si scostano
quel tanto che basta, e **una lineetta grigia li ricollega alla posizione
vera**. Funziona per qualunque comune si aggiunga, e la nota sotto la mappa
dichiara che lo spostamento c'e':

> una mappa che sposta un punto senza dirlo e' peggio di una che si
> sovrappone.

**Brescia a margine, non esclusa.** Sta fuori dall'inquadratura regionale e
compare come pastiglia tratteggiata nell'angolo, con l'etichetta «fuori
regione». Escluderla sarebbe stato piu' semplice e sbagliato: e' **l'unica
col pool AVQ lombardo**, quindi `n_eff` 5.655 contro i ~3.200 emiliani, ed e'
il caso piu' diverso che il bundle contenga. Nasconderlo lo appiattirebbe.

**Il clic apre una scheda** prima di cambiare citta': individui,
articolazione, tier, copertura col suo denominatore, e la banda con
`n/n_eff`, piu' una riga che traduce il numero — *«157.973 individui poggiano
su 3.220 osservazioni efficaci»*. Poi il pulsante per entrare.

E' anche mezzo «Confronta» (§4.5) arrivato in anticipo: due schede aperte in
successione mettono a fianco Bologna e Castenaso senza costruire una vista
nuova.

---

## 5. Interazione e stato

Crossfilter completo; stato interamente nell'URL, atlante, fiducia e mappa
inclusi:

```
?comune=017029&zona=17029012&istruzione=laurea_o_its&fiducia=1&mappa=1&modo=punti
```

---

## 6. Grafica

**Estetica dell'anagrafe.** Serif per titoli, monospaziato con cifre tabulari,
un solo accento. Riferimenti in neutro scuro distinti per **forma** — tacca
con testa triangolare, rombo, linea punteggiata — cosi' la distinzione
sopravvive alla stampa in bianco e nero.

---

## 7. Architettura

### 7.1 Strumenti

Nessuno scaffold: pagina singola, DuckDB-WASM da CDN, barre in HTML/CSS, SVG
d'export a mano, mappa in canvas. **Observable Framework resta rimandato.**

### 7.2 Il modello di costo

```
costo(query) = footer + Σ  peso(blocco) × (row group non potati / totale)
```

Init 0,7 s · prima query 0,79 MB · **filtri successivi 0 byte e 100–220 ms** ·
mappa ~1 MB su richiesta · fiducia ~1,8 MB su richiesta · scheda individuo
~0,15 MB la prima volta.

### 7.3 Cosa costa zero adesso e molto dopo

1. **`--pubblico` in `to_parquet.py`** — ancora non scritto, e ora serve (§15);
2. etichettatura — **fatta**: banner globale, avvertenza nella scheda,
   `noindex`;
3. **nessuna dipendenza da servizi esterni** — violato dalla base cartografica;
4. il sito e' online (§15).

---

## 8. Estensibilita'

```
python build/build_bundle.py                  # tutti i comuni del registro
python build/build_bundle.py 038008 039014    # solo alcuni
```

Orchestra i quattro passi, **salta chi e' gia' aggiornato** confrontando le
date di Parquet e sorgente, **non si ferma al primo errore** e stampa un
riepilogo unico con livello, tier, zone, attributi e copertura.

**Provato su undici comuni senza toccare l'interfaccia**, ed era la prova
richiesta. Fra loro due livelli diversi (K9C e K6C), quattro denominazioni di
zona, quattro tier e un comune da 16.357 abitanti: il pannello si adatta dal
manifest. San Vito dei Normanni e' segnalato come sorgente assente e non
blocca gli altri.

Undici citta' ≈ 1,9 milioni di individui e **35,7 MB** di bundle, di cui
~2,5 scaricati per sessione.

> **Il riepilogo stampa il livello risolto per comune**, ed e' una
> contromisura: `resolve_pop_file` esclude K10C su richiesta, ma
> l'esclusione e' silenziosa. Se comparisse un residuo di livello ignoto,
> si vedrebbe in tabella.

---

## 9. Prestazioni — misurate

| operazione | misurato |
|---|---|
| init DuckDB-WASM | 0,69–0,77 s |
| prima query, marginali | 0,79 MB · ~1,3 s |
| filtri successivi | **0 byte** · 100–220 ms |
| filtro su una zona | 0,23 MB |
| mappa (blocco C) | ~1 MB, su richiesta |
| fiducia (blocco B) | ~1,8 MB, su richiesta |
| scheda individuo | ~0,15 MB la prima, 0 dopo |

---

## 10. Fasi

**F0** ✔ diagnostici, Modena e Parma (§13.1) — mancano Bologna e Brescia.
**F1** ✔ smoke test dello stack (§13.2).
**F2** ✔ `donor_id` dalla firma AVQ (§13.3), **ora nel Parquet**.
**F3** ✔ pannello dei marginali.
**F4** ✔ riferimento censuario dal constraint set.
**F5** ◧ mappa: quota, punti, navigazione, base cartografica.
**F6** ✔ fiducia istituzionale, a quattordici voci, con `n_eff` per variabile.

**Undici comuni** ✔ due livelli, quattro tier, `build_bundle.py`. Il pannello
non e' stato toccato per adattarsi: si costruisce dal manifest.

**Pubblicazione** ✔ provvisoria (§15).

**Prossime:**

**F7 — le altre AVQ**, con la stessa disciplina: universo dichiarato, banda su
`n_eff` della variabile, riga di scomposizione compositiva. `BMI` e `BMIMIN`
vanno unite — stessa misura su due universi — e `BMIMIN` non e' nemmeno nel
set attuale, che il registro esclude di proposito. Non serve rigenerare: le
23 AVQ sono gia' nel Parquet.
**F8 — Confronta** fra citta'.
**F9 — Metodo**: la pagina che rende l'app difendibile.
**F10 — grafica** e pubblicazione definitiva.

---

## 11. Questioni aperte

**Sul viewer:**

1. **Le altre nove AVQ** nel pannello, con la disciplina di §4.7: universo
   dichiarato, banda su `n_eff` della variabile, riga di scomposizione
   compositiva. `BMI` e `BMIMIN` vanno unite — sono la stessa misura su due
   universi. **Non serve rigenerare niente**: sono gia' nel Parquet.
2. ~~Fonte delle medie nazionali AVQ 2024~~ — **risolta** il 2/8/2026, ma non
   trovandola: non esiste. Ricalcolate da `medie_nazionali.py` sui microdati,
   coincidono entro 0,045 con quelle cablate e ora coprono tutte e ventitre
   le variabili (§4.7, riferimento §2.2).
3. **`--pubblico` in `to_parquet.py`**: toglie `via` e `civico`. Necessario
   prima della pubblicazione per arXiv, dove la configurazione si rovescia
   (§15).
4. **Fonti comunali di zona** come *validazione esterna*: quali sono
   disponibili come livelli? Determina quanti rombi vuoti il pannello puo'
   mostrare (§3.4).
5. **Emilia-Romagna**: quanti capoluoghi, e la vista regionale entra o resta
   predisposta?

**Sulla pipeline**, tutte migrate al documento di riferimento:

| | dove |
|---|---|
| `CRONI` fra le opzionali, `FORZE_ARMATE`, `ISTRMi`=99, ICC, deff | §13.6 |
| 26 esclusioni α=0, blocco `background × origine_genitori`, MRE in `fit_cs.py` | §14 |
| permutazione di `istruzione`, assunzione (9), diagnostici su Bologna e Brescia | §15.4 |

**Su SimComm**: campionamento degli agenti per firma invece che per
individuo (§14 di questo documento).

## 12. Registro dei miglioramenti

### Fatti

| | effetto |
|---|---|
| colonne in tre blocchi per uso | Q5 da 2,297 a 0,915 MB |
| righe per `zona, sezione` | filtro di zona al 22% |
| `id` DELTA_BINARY_PACKED | 0,79 → <0,09 MB |
| AVQ grezze eliminate | blocco B 2,659 → 1,411 MB |
| `donor_id` dalla firma, nel Parquet | sblocca `n_eff` senza rilanciare la pipeline |
| `n_eff` di Kish invece dei distinti | fattore 2,8 |
| **`n_eff` per universo di variabile** | **fattore 2,1, in meglio** |
| z-score invece dell'errore relativo | il MRE per cella era tutto rumore |
| riferimento da `cs_K9C.json` | F4 senza fonti esterne |
| crossfilter che esclude la propria dimensione | il pannello non collassa |
| jitter deterministico | punti fermi, e quindi cliccabili |
| percorso del bundle risolto a runtime | stesso file in locale e online |
| due bande sovrapposte nel pannello fiducia | `n_eff` diventa visibile |

### Proposti

- **`--pubblico` in `to_parquet.py`** (§15);
- **base cartografica `.pmtiles`**: toglie l'unica dipendenza esterna. Qualche
  decina di MB per regione, **piu' di tutti i Parquet insieme** → host separato;
- **`FORZE_ARMATE`** nella lista AVQ;
- rimuovere `quinq` e `quartiere` dal Parquet;
- `donor_anno` per ricostruire il *planned missing*;
- correggere `MRE att` in `verifica_vincoli.py` col fattore `√(2/π)`.

### Scartati, col motivo

- **spezzare il blocco AVQ**: il pannello fiducia legge tutte le `PUNTIFI`
  insieme, quindi Q4 non era una query realistica;
- **AVQ in int8**: il dizionario e' gia' a 4 bit;
- **`donor_id` in int16 per risparmiare**: il dizionario stava gia' lavorando,
  il peso non cambia;
- **modo densita' nella mappa**: riproduce la densita' di popolazione;
- **geometrie per la mappa**: la griglia da `lon`/`lat` basta;
- **rigenerare le popolazioni** per i 3 record impossibili;
- **GitHub Pages per la prova**: avrebbe richiesto di rendere pubblico il repo.

---

## 13. Diario delle misure

### 13.1 Diagnostici sull'anello 3 → **riferimento §15**

Il seam quinquennale, lo scarto entro bin verso il giovane (dieci prove su
dieci) e l'incoerenza eta'–istruzione (2,64% e 2,74%) sono risultati sulla
pipeline e stanno nel documento di riferimento, §15 — insieme alla
ritrattazione di una discrepanza che si era rivelata rumore di campionamento.

Quel che ricade sul viewer: la pagina Metodo dovra' mostrarli, e la mappa del
residuo per sezione e' la resa naturale del primo (§4.6).
### 13.2 F1 — smoke test DuckDB-WASM

Sette misure su otto entro il 20% del modello di costo. **Q3/Q3N = 10,7%**,
**Q6/Q2 = 21,8%**.

### 13.3 F2 — `donor_id` dalla firma AVQ

Firme distinte contro donatori dichiarati: **−418 in tutte e tre le citta'
emiliane**, −821 a Brescia. Circa un donatore su dieci ha un gemello
indistinguibile, in entrambi i pool. L'errore va nella direzione prudente.

### 13.4 Constraint set e stato del pool → **riferimento §14**

L'anatomia dei sedici blocchi, la distinzione fra cella *assente* e cella *a
zero*, le 26 coppie impossibili non vincolate e lo stato del pool
(`sd(z)` = 1,030, fattore di inflazione della varianza 1,06) sono risultati
sulla pipeline e stanno nel documento di riferimento, §14.

Quel che ricade sul viewer e' solo questo: **lo stato di verifica non puo'
appoggiarsi al MRE aggregato**, che media su centinaia di celle e nasconde
scarti per cella dell'ordine dell'1%. Il pannello usa lo scarto massimo sulla
distribuzione mostrata, calcolato dal vivo (§4.2).
### 13.5 F6 — la batteria della fiducia

**La corrispondenza viene dal codebook**; i dati sono il controllo e lo
passano su cinque ancore nazionali:

| | Modena | Italia |
|---|---|---|
| `PUNTIFI12` vigili del fuoco | 8,26 | 8,10 |
| `PUNTIFI3` forze dell'ordine | 6,71 | 6,70 |
| `VOTOUSL` ASL | 6,80 | 6,34 |
| `PUNTIFI10` governo comunale | 5,48 | 5,13 |
| `PUNTIFI8` governo regionale | 5,28 | 4,65 |

Tutte nel verso giusto, con Modena sopra la media nazionale. E `PUNTIFI4`
partiti politici e' **il minimo assoluto** a 3,40.

**Una voce manca.** Nel tracciato la batteria occupa dodici posizioni
consecutive (525–536) con la stessa scala e la stessa formulazione. Undici si
chiamano `PUNTIFI{n}`; **la dodicesima si chiama `FORZE_ARMATE`**, alla
posizione 534, ed e' sfuggita alla lista di `assign_avq.py`, che seleziona per
prefisso. La numerazione salta il 9 e l'11 perche' una delle due e' stata
pubblicata col nome dell'istituzione.

Nella popolazione la batteria e' quindi **incompleta di una voce su dodici**.
Non cambia niente per il pannello; cambia per un paper che dichiara cosa
contiene la popolazione sintetica.

> **Corollario di metodo**: una lista di variabili compilata su un prefisso e'
> fragile a un rinomino della fonte. Le altre liste della pipeline che
> funzionano per pattern meritano lo stesso controllo.

**Universi misurati** (Modena, per classe d'eta'):

- **universo 15 anni e piu'**: tutte le `PUNTIFI`, `MH`, `AMBIENTE`, `FIDUCIA`
  — zero nei primi due bin, ~0,98 dopo;
- **planned missing**: `PUNTIFI6`, `PUNTIFI7`, `PUNTIFI13` a **0,49 costante
  in ogni classe**. Una mancanza che non dipende da nulla dell'individuo e'
  per disegno: chieste in una annata su due;
- **filtro per esperienza**: `VOTOUSL` cresce con l'eta' (0,12 → 0,30). Non
  ignorabile (§2.2);
- **`BMI` e `BMIMIN` sono complementari** — la stessa misura su due universi,
  adulti e minori. Nel pannello vanno unite;
- **`SALUTE`** e' l'unica a 1,00 ovunque: chiesta davvero a tutti.

### 13.6 `n_eff` per universo di variabile

```
Modena, popolazione intera   n = 184.597   n_eff = 1.520   efficienza 0,36
Modena, PUNTIFI10 (15+)      n = 157.974   n_eff = 3.220   efficienza 0,80
                                           donatori 4.006   banda × 7,0
```

Il fattore 2,1 viene dalle firme dei minori, che collassano su quattro valori
e dominavano `Σm²` pur non partecipando alla variabile. Derivazione, limiti e
correzione per grappolo familiare: **riferimento §13.3**.
## 14. Cosa significa per SimComm

**La diversita' psicologica effettiva di una popolazione di agenti e' quella
di alcune migliaia di donatori**, non dei suoi individui, e non cresce
prendendo una citta' piu' grande. Col numero corretto per universo, su una
variabile di fiducia sono ~3.200 a Modena.

**Il secondo ordine e' piu' insidioso.** Due agenti che condividono la firma
hanno profili **identici**, non simili: in una simulazione LLM le loro
risposte sono correlate per costruzione e non sono evidenza indipendente.

**Domanda di disegno sperimentale**: conviene campionare gli agenti **per
firma** invece che per individuo? Garantirebbe profili distinti al prezzo di
distorcere le quote demografiche — che sono cio' che il tier 1 esiste per
garantire. Va deciso e dichiarato nel paper. E va misurato: in una campagna
gia' eseguita, quante coppie di agenti condividevano la firma?

---

## 15. Pubblicazione

**Stato**: online su Cloudflare Pages, `animarium.pages.dev`. Repo privato.
Il sito nasce da una cartella, non da git: nessun ramo lo descrive.

**Perche' non GitHub Pages**: su repo privati richiede un piano a pagamento, e
rendere pubblico il repo era una decisione da prendere con calma. Cloudflare
da cartella non lascia niente da ripulire, si spegne davvero, e consente un
accesso ristretto (Access, gratuito fino a 50 persone).

Il rovescio: **il deploy non e' versionato**.

**Cosa e' esposto**: `index.html`, `smoke.html` e il **bundle completo**.
Chiunque abbia l'URL puo' scaricare `pop.parquet`. E' deliberato:

- **nessuna divulgazione statistica** — ANNCSU, microdati AVQ *public use* e
  tavole censuarie sono gia' pubblici, e la popolazione e' una ricombinazione
  di cose pubbliche;
- **il rischio e' di interpretazione**: qualcuno produce una mappa della
  sfiducia nel Comune via per via da un dataset che sulla sfiducia non ha
  *nessuna* informazione geografica. Su Caffaro non e' un'ipotesi di scuola;
- **da cui la forma dell'avviso**: non dice «e' sintetico» ma **a quale
  risoluzione il dato ha contenuto**. La posizione dentro la sezione e'
  arbitraria per l'assunzione (10), quindi la mappa a punti al livello del
  civico e' *precisione spuria*.

`noindex, noarchive` nel `<head>`. **Spegnere il sito non ritira quello che e'
gia' stato scaricato.**

**Procedura**:

```
python build/deploy.py
npx wrangler pages deploy deploy/ --project-name animarium --branch main
```

I due comandi vanno **sempre in coppia**: `deploy.py` copia il bundle da
disco, quindi rigenerare i Parquet senza rifare `deploy.py` pubblicherebbe la
versione precedente.

**Cosa manca**: `--pubblico`, accesso ristretto, versionamento del deploy.

**Per arXiv la configurazione si rovescia**: codice pubblico e citabile, piu'
un bundle **degradato** di una citta' sola per riprodurre le figure, con i
dati completi su richiesta. Un referee ragionevole chiedera' di poter rifare
almeno una figura, e «il codice senza dati» non basta.
