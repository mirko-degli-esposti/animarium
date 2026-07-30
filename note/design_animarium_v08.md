# Animarium — documento di design

**Synthetic populations of Italian cities**
**v0.8 — 30 luglio 2026**
Riferimento dati: `GSP_popolazioni_full_riferimento_v16.md` (§ citati sotto).

*Rispetto alla v0.7: il pannello della fiducia istituzionale esiste, e con
esso `n_eff` per universo di variabile — che corregge di un fattore 2,1 il
numero della v0.6, calcolato sull'universo sbagliato. Nuova §2.2, materiale
per il paper su come riportare l'incertezza di una popolazione hot-deck.
Nuove §4.7 e §13.5.*

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
| **D — donato** | ▨ | le 21 AVQ | **nessuna informazione geografica** (assunzione 6) |

### 2.1 Numerosita' efficace — i numeri veri

`n_eff` di Kish, `n²/Σm²`, dove `m_d` e' il numero di individui che ricevono
le AVQ dal donatore `d`.

**Sull'intera popolazione**, misurato in §13.3:

| | individui | firme | `n_eff` | efficienza |
|---|---|---|---|---|
| Brescia | 198.259 | 7.287 | 2.007 | 0,28 |
| Modena | 184.597 | 4.199 | 1.520 | 0,36 |
| Parma | 198.121 | 4.200 | 1.478 | 0,35 |
| Bologna | 390.098 | 4.207 | 1.599 | 0,38 |

Quattro citta' da 184.000 a 390.000 individui, e `n_eff` fra 1.478 e 2.007.
Bologna ha 2,1 volte gli abitanti di Modena e `n_eff` piu' grande del 5%;
**Parma ha piu' individui di Modena e `n_eff` piu' basso.** La dimensione del
comune non entra: il tetto e' il pool regionale, e Brescia sta meglio solo
perche' la Lombardia ne ha 8.111 contro i 4.629 emiliani.

> **Correzione della v0.6.** Quei numeri, e i fattori di banda ×11,0 e ×15,6
> che ne derivavano, sono calcolati **sull'universo sbagliato**. Le firme dei
> minori collassano su quattro valori — per un bambino `BMI`, le `PUNTIFI` e
> `VOTOUSL` sono non applicabili — e producono classi enormi che dominano
> `Σm²`. Ma quegli individui **non partecipano** alla fiducia istituzionale.

**Per universo di variabile** (Modena, `PUNTIFI10`, universo 15 anni e piu'):

```
popolazione intera     n = 184.597    n_eff = 1.520    banda × 11,0
PUNTIFI10, 15 e piu'   n = 157.974    n_eff = 3.220    banda ×  7,0
                                      donatori 4.006   efficienza 0,80
```

**Calcolare `n_eff` sull'universo della variabile lo raddoppia**, e
l'efficienza di Kish passa da 0,36 a 0,80: tolti i minori, il riuso e' molto
piu' uniforme. Restano ×7,0, che non e' poco — ma e' un numero difendibile
invece che uno gonfiato.

**Regola**: `n_eff` si calcola **per variabile, sul suo universo**. Un solo
`n_eff` per il blocco AVQ non esiste, perche' gli universi vanno dal 100% di
`SALUTE` al 13% di `BMIMIN`.

**Corollario per il badge** (correzione della v0.4): l'allarme va acceso su
**`n/n_eff` alto**, non su `n_eff` basso. `n_eff` satura e non scende quasi
mai, mentre il rapporto esplode proprio sulle sottopopolazioni grandi.

### 2.2 Come riportare l'incertezza — materiale per il paper

Il punto e' generale e non riguarda solo GSP: **qualunque popolazione
sintetica che imputi attributi da un'indagine donatrice eredita la
numerosita' di quella indagine come tetto, indipendentemente da quanti
individui contiene.**

**La formula.** Sia `x̄` la media di una variabile donata su `n` individui
sintetici, provenienti da `D` donatori con molteplicita' `m_d`. Poiche' tutti
gli individui che condividono un donatore hanno lo stesso valore,

```
x̄ = (1/n) Σ_d m_d x_d        Var(x̄) = σ² Σ_d m_d² / n² = σ² / n_eff
```

con `n_eff = n² / Σ_d m_d²`, che e' esattamente la formula di Kish. Il
conteggio dei donatori distinti **non basta**: sopravvaluta `n_eff` di un
fattore 2,8 quando il riuso e' diseguale (§13.3), perche' Kish e' una
statistica di secondo momento e vive nella coda della distribuzione dei
riusi.

**L'interpretazione.** Condizionatamente al pool, i valori AVQ sintetici sono
una funzione deterministica dell'assegnazione. L'incertezza che conta per
un'inferenza sulla popolazione reale e' quella di campionamento **del pool
stesso**: `n_eff` misura quanti rispondenti indipendenti stanno davvero sotto
la statistica.

**Tre limiti da dichiarare.**

1. **Gli effetti di disegno si compongono.** L'AVQ e' un campione stratificato
   a piu' stadi, quindi ha un proprio *design effect*. L'`n_eff` calcolato qui
   e' relativo ai rispondenti, non a un campione casuale semplice: la
   numerosita' realmente efficace e' `n_eff / deff(AVQ)`, e `deff` andrebbe
   preso dalla documentazione ISTAT.
2. **La firma sottostima i donatori del 9-10%.** Nel pool emiliano 418
   donatori e in quello lombardo 821 hanno 21-uple indistinguibili (§13.3).
   L'errore va nella direzione prudente — `n_eff` esce basso, le bande larghe
   — ma va dichiarato.
3. **L'universo va dichiarato, non la copertura.** `MH` copre lo 0,876 su
   Modena, e la quota di 15 anni e piu' vale 0,8763: coincidono alla terza
   cifra. Non e' mancanza, e' universo. Scrivere «copertura 87,6%» descrive un
   sintomo; scrivere «universo: 15 anni e piu'» descrive il dato.

**Il caso che non e' ignorabile.** `VOTOUSL` ha copertura crescente con
l'eta' — 0,12 a 15-24 anni, 0,30 a 65-74 — perche' e' un giudizio su un
servizio ricevuto. Chi risponde e' sistematicamente piu' anziano e piu'
malato di chi non risponde: la media non e' «il giudizio dei modenesi
sull'ASL», e' «il giudizio di chi c'e' stato». Va tenuta fuori dalla batteria
e dichiarata a parte.

---

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

Fuori dal repo git. Quattro citta': **18,1 MB**.

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

Ogni `alpha × N` di `cs_K9C.json` e' un conteggio censuario. Il riferimento
per (filtro F, attributo A) esiste se e solo se **un blocco completo contiene
F ∪ {A}**.

**Copertura**: **67 coppie su 333, il 20%**, identica nelle quattro citta' —
e' una proprieta' del template di `build_constraints.py`, non del comune.

| filtro | riferimento disponibile per |
|---|---|
| nessuno | tutti e nove gli attributi |
| **`zona`** | `sesso`, `eta`, `istruzione`, `background`, `cittadinanza` |
| `zona` | **non** per `stato_civile`, `condizione`, `origine_genitori` |
| `sesso × eta` | `stato_civile`, `cittadinanza` |
| qualunque | mai `paese`, `area` |

Le **fonti comunali anagrafiche** restano l'unica *validazione esterna* e non
sono ancora nel bundle.

---

## 4. Le viste

### 4.1 Esplora — i filtri

Si filtra cliccando le barre; i filtri attivi sono pillole rimovibili.
**Ogni pannello applica tutti i filtri tranne il proprio.** Ordine delle
modalita' stabile fra citta'.

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

Dodici righe su asse comune 0–10, ordinate per media, con la **media come
linea** e **due bande sovrapposte**:

- **sottile e chiara**: intervallo al 95% calcolato su `n`;
- **spessa e scura**: calcolato su `n_eff` di Kish.

La distanza fra le due e' la ragione per cui `n_eff` esiste, e mostrarla e'
piu' efficace di qualunque nota. Su Modena senza filtro il rapporto e' 7,0:
la banda ingenua e' un trattino, quella vera un blocco largo.

**Tacche punteggiate** per le medie nazionali, disponibili su cinque righe
su dodici — un'altra istanza di «dove il riferimento c'e' e dove no».

**`VOTOUSL` sta in fondo, fuori batteria**: giudizio su un servizio ricevuto,
universo per esperienza, mancanza non ignorabile (§2.2).

**Nota fissa in cima**: le AVQ non hanno informazione geografica
(assunzione 6), quindi filtrando una zona ogni differenza e' compositiva per
costruzione. E' cio' che rende il pannello utilizzabile su Caffaro senza
produrre l'affermazione falsa.

**La corrispondenza `PUNTIFI{n}` → istituzione viene dal codebook**, non
dalle medie: dedurla dalle medie e appaiare poi quelle stesse medie come
riferimento sarebbe circolare. I dati sono il controllo, e lo passano su
cinque ancore (§13.5).

---

## 5. Interazione e stato

Crossfilter completo; stato interamente nell'URL, fiducia e mappa incluse:

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
to_parquet.py {C} --drop-avq-raw → manifest_min.py {C}
                                 → build_riferimenti.py {C} → build_indice.py
```

Provato su quattro citta' senza toccare l'interfaccia. Dieci capoluoghi
emiliani ≈ 1,8 milioni di individui e ~33 MB di bundle.

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
**F6** ◧ **fiducia istituzionale fatta**, con `n_eff` per variabile.
Restano le altre AVQ — `SALUTE`, `AMBIENTE`, `CPESO`, `FUMO`, `BMI`/`BMIMIN`
(da unire, sono la stessa cosa su due universi), `MH`, e le binarie
`FIDUCIA`/`CRONI`.

**Pubblicazione** ✔ provvisoria (§15).

**Prossime:**

**F7 — le altre AVQ**, con la stessa disciplina: universo dichiarato, banda su
`n_eff` della variabile, riga di scomposizione compositiva.
**F8 — Confronta** fra citta'.
**F9 — Metodo**: la pagina che rende l'app difendibile.
**F10 — grafica** e pubblicazione definitiva.

---

## 11. Questioni aperte

1. **Fonte delle medie nazionali AVQ 2024.** Le cinque tacche — vigili del
   fuoco 8,10, forze dell'ordine 6,70, ASL 6,34, Comune 5,13, Regione 4,65 —
   sono entrate nel design alla v0.1 **senza citazione**. Vanno verificate
   prima di finire in una figura, o tolte.
2. **`FORZE_ARMATE` manca dalla popolazione** (§13.5): e' la dodicesima voce
   della batteria, pubblicata col nome dell'istituzione invece che col
   progressivo, e sfuggita alla lista di `assign_avq.py` che seleziona per
   prefisso `PUNTIFI`. Da aggiungere alla prossima rigenerazione.
3. **Design effect dell'AVQ**: serve per comporre `n_eff` (§2.2).
4. **Definizione di MRE in `fit_cs.py`**: differisce da quella dello strumento
   per un fattore `√(2/π)`.
5. **`sesso × background × origine_genitori`**: |z| fino a 4,0, replicato.
6. **Definizioni di `macroeta` e `istr4`** in `assign_avq.py`, per `cella_avq`.
7. **Fonti comunali di zona** come validazione esterna.
8. **Le riparazioni della pipeline**: permutazione di `istruzione` entro
   (zona, sesso, bin), e le 26 esclusioni α=0.
9. **Campionamento degli agenti per firma** invece che per individuo (§14).
10. **Configurazione per arXiv**: codice pubblico, dati degradati. Richiede
    `--pubblico`, da scrivere prima della prossima pubblicazione.

---

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

### 13.1 F0 — i due diagnostici (Modena e Parma)

**(a) Seam quinquennale.** Normalizzando per dimensione di classe, le due
classi del seam finiscono nei primi tre posti su sedici in entrambe le citta'
(p ≈ 6·10⁻⁴), ma l'eccesso e' del 40%: **non e' una sorgente dominante**.

*Sistematico e non previsto*: dentro ciascuno dei cinque bin veri il sintetico
pende verso il **giovane**, **dieci prove su dieci**. La distribuzione dentro
il bin non e' vincolata da niente, quindi l'indiziato e' l'assunzione (9).

> **Ritirato**: la discrepanza «fra prodotti censuari» era rumore di
> campionamento (z = 0,24 e 0,64).

**(b) Coerenza eta'–istruzione**: 2,64% e 2,74%, nei bin `9-14` e `15-24`.

**(c) Tre record impossibili** su 970.000.

### 13.2 F1 — smoke test DuckDB-WASM

Sette misure su otto entro il 20% del modello di costo. **Q3/Q3N = 10,7%**,
**Q6/Q2 = 21,8%**.

### 13.3 F2 — `donor_id` dalla firma AVQ

Firme distinte contro donatori dichiarati: **−418 in tutte e tre le citta'
emiliane**, −821 a Brescia. Circa un donatore su dieci ha un gemello
indistinguibile, in entrambi i pool. L'errore va nella direzione prudente.

### 13.4 Anatomia del constraint set e stato del pool

Sedici blocchi, identici nelle quattro citta'. I cinque parziali sono i
**complementi fuori universo**.

> **Materiale da paper GibbsPCD.** Quando l'ISTAT **esclude per universo**, la
> cella non compare. Quando il censimento **osserva zero**, la cella compare
> con valore zero. Per MaxEnt le due cose sono **opposte**: assente significa
> *non vincolata*, zero significa *vietata*. Le 26 coppie logicamente
> impossibili non sono vincolate da nessun blocco.

**Il pool e' un campione pulito**: `sd(z)` 1,030 e 1,031, media(z) ≈ 0, nessun
zero hard violato. `sd(z)² = 1,06` e' il **fattore di inflazione della
varianza**: 184.597 individui valgono ~174.000 estrazioni indipendenti.

**Un blocco anomalo**, replicato: `sesso × background × origine_genitori`, con
picchi da −3,90 a +4,00 e le celle a genitori misti che perdono massa.

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

Il fattore 2,1 viene dall'eliminazione dei minori, le cui firme collassano su
quattro valori e producono classi enormi che dominavano `Σm²` — pur non
partecipando alla variabile. **Conferma quantitativa dell'ipotesi di §2.1
della v0.6.**

---

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
