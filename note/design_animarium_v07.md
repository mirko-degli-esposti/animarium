# Animarium — documento di design

**Synthetic populations of Italian cities**
**v0.7 — 30 luglio 2026**
Riferimento dati: `GSP_popolazioni_full_riferimento_v16.md` (§ citati sotto).

*Rispetto alla v0.6: il sito e' online. Nuova §15 con la procedura di
pubblicazione, cosa e' esposto e perche', e la configurazione rovesciata che
servira' per arXiv. Aggiornate §0, §7.3, §10 e §11 di conseguenza.*

---

## 0. Decisioni prese

| | scelta | stato |
|---|---|---|
| **nome** | **Animarium** — *Synthetic populations of Italian cities* | fissato |
| **stack** | pagina statica + DuckDB-WASM, senza scaffold | verificato (§7.2) |
| **riferimento** | censimento estratto da `cs_K9C.json` | fatto (§3.4) |
| **disposizione del file** | tre blocchi di colonne, righe per `zona, sezione` | verificata (§3.2) |
| **`donor_id`** | ricostruito dalla firma AVQ | verificato, **non ancora nel Parquet** |
| **mappa** | griglia da `lon`/`lat`, nessuna geometria | fatta (§4.3) |
| **pubblicazione** | Cloudflare Pages da cartella, repo privato | **fatta**, provvisoria (§15) |

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
| target del blocco A contro quello del blocco B | ipotesi di incoerenza cross-blocco **falsificata** |

**Corollario**: nessun numero entra nel design senza il suo confronto.

*Bilancio delle previsioni.* Circa meta' delle previsioni quantitative fatte
finora sono state falsificate dalla misura. Due ritrattazioni sono registrate
qui: la discrepanza «fra prodotti censuari» di §13.1, che era rumore di
campionamento (z = 0,24), e l'incoerenza cross-blocco, che non esiste. Questo
documento va letto come una lista di ipotesi da falsificare.

---

## 1. Scopo, utenti, non-obiettivi

Tre utenti in ordine temporale: **tu adesso**, i **collaboratori** (Tarantino,
Pachet, Zucker, PRISM), il **pubblico** in seguito — che con §15 e' arrivato
prima del previsto, in forma provvisoria.

**Non-obiettivi**, da scrivere nella pagina Metodo:

- non e' uno strumento di stima locale: nessun numero e' una misura del
  quartiere reale;
- non genera popolazioni: consuma i `_full` gia' prodotti;
- non fa inferenza causale ne' previsione.

---

## 2. Livello di garanzia

| classe | segno | attributi | cosa garantisce |
|---|---|---|---|
| **V — vincolato** | ■ | anello 1 | riprodotto entro il rumore di campionamento |
| **A — allocato** | ◧ | `sezione`, `eta_anni`, indirizzo, coordinate | esatto per sezione, sotto le assunzioni (8)–(10) |
| **C — condizionato** | □ | `paese`, `area` | margini censuari, geografia secondo il tier |
| **D — donato** | ▨ | le 21 AVQ | **nessuna informazione geografica** (assunzione 6) |

I quattro segni compaiono nella scheda individuo (§4.4), che e' il posto dove
la classificazione smette di essere un badge astratto.

### 2.1 Numerosita' efficace

`n_eff` di Kish, `n²/Σm²`, misurato in §13.3:

| | individui | firme distinte | `n_eff` | banda × |
|---|---|---|---|---|
| Modena | 184.597 | 4.199 | **1.520** | **11,0** |
| Bologna | 390.098 | 4.207 | **1.599** | **15,6** |

**`n_eff` non cresce con la popolazione** — il tetto e' il pool regionale — e
**satura anche filtrando**, quindi `n/n_eff` e' massimo per la citta' intera.
La correzione serve di piu' dove il numero sembra piu' autorevole.

> **Regola** (correzione della v0.4): il badge di allarme va acceso su
> **`n/n_eff` alto**, non su `n_eff` basso.

**Un solo `n_eff` per il blocco AVQ non esiste**: le 21 variabili hanno
universi dal 100% al 13,6%, e la firma piu' riusata (1511 individui) e' quella
dei minori, per cui la 21-upla si riduce a quattro valori. `n_eff` va
calcolato **per variabile, sul suo universo**.

*Stato*: nessuna AVQ e' ancora mostrata nel pannello, quindi la regola non e'
implementata. Diventa vincolante appena si aggiunge il pannello fiducia (F6).

---

## 3. Modello dei dati

### 3.1 Il bundle

```
bundle/
  comuni.json                   indice per il menu delle citta'
  comuni/036023/
    pop.parquet                 42 colonne, 10 row group, 3,12 MB
    manifest.json               etichette, ordini, conteggi non filtrati
    riferimenti.json            conteggi censuari da cs_K9C.json
```

Fuori dal repo git, ricostruibile in quattro comandi. Quattro citta':
**16,65 MB**.

### 3.2 Disposizione fisica del file

DuckDB-WASM legge **intervalli di byte contigui, non colonne**: chiedere tre
colonne o cinque dello stesso blocco costa identico. I blocchi li definiamo noi.

```
A  filtri e marginali   zona, quartiere, sesso, eta, stato_civile, cittadinanza,
                        istruzione, condizione, background, origine_genitori,
                        paese, area, eta_anni, quinq, sezione
B  AVQ                  le 21 _num
C  pesanti (mappa)      id, indirizzo_fonte, via, civico, lon, lat
```

Righe per `zona, sezione` (il filtro di zona legge il 22%); row group da
20.000; `id` in `DELTA_BINARY_PACKED` (0,79 → <0,09 MB); `lon`/`lat` in
`BYTE_STREAM_SPLIT`; AVQ grezze eliminate.

**Modena**: CSV 57,76 MB → Parquet **3,123 MB (5,4%)**. Blocchi: A 0,675 ·
B 1,411 · C 0,980 · footer 0,073. **Scala linearmente**: Bologna ha 2,11 volte
le righe e il blocco A pesa 2,10 volte.

### 3.3 Colonne aggiunte

| colonna | stato |
|---|---|
| `id` int32 | fatto, delta-encoded, e serve al clic sulla mappa |
| `quinq` int8 | fatto, candidato alla rimozione (§12) |
| **`donor_id`** | ricostruibile dalla firma AVQ, **da aggiungere all'export** |
| `donor_anno`, `cella_avq`, `macroeta`, `istr4` | desiderabili, non bloccanti |
| `lon_j`, `lat_j` | **non servono**: il jitter e' deterministico a runtime |

### 3.4 Il riferimento censuario — dal constraint set

**L'idea che ha semplificato F4**: non servono tavole di zona da fonti esterne,
perche' sono gia' in `cs_K9C.json`. Ogni `alpha × N` e' un conteggio censuario.

**Regola**: dato un filtro F e un attributo mostrato A, il riferimento esiste
se e solo se **un blocco completo contiene F ∪ {A}**. Si marginalizza il
blocco sulle celle compatibili con F e si raggruppa per A. Fra i candidati si
sceglie il piu' piccolo.

**Copertura misurata**: **67 coppie su 333, il 20%**, e — fatto non ovvio —
**identica in tutte e quattro le citta'**. E' una proprieta' del template di
`build_constraints.py`, non del comune.

| filtro | riferimento disponibile per |
|---|---|
| nessuno | tutti e nove gli attributi |
| **`zona`** | `sesso`, `eta`, `istruzione`, `background`, `cittadinanza` |
| `zona` | **non** per `stato_civile`, `condizione`, `origine_genitori` |
| `sesso × eta` | `stato_civile`, `cittadinanza` |
| qualunque | mai `paese`, `area`: non stanno nel constraint set |

**Blocchi parziali.** `eta × istruzione` ha una cella sola, `zona × sesso ×
eta × condizione` solo gli occupati 15–64. Le celle non elencate **non sono
vietate, sono libere**: un riferimento parziale non si normalizza come una
distribuzione e non viene mostrato.

**Le fonti comunali anagrafiche** restano l'unica *validazione esterna* — mai
usate come livelli — e non sono ancora nel bundle. Modena 0,982–1,007 sulla
popolazione per quartiere; Primo Maggio 0,329 contro 0,293.

---

## 4. Le viste

### 4.1 Esplora — i filtri

**Non c'e' una colonna di controlli**: si filtra cliccando le barre. I filtri
attivi sono pillole rimovibili.

**Ogni pannello applica tutti i filtri tranne il proprio** — correzione emersa
usandolo: senza, cliccando «Femmine» il pannello Sesso mostrava 100% Femmine.
Conseguenza da spiegare: filtrando un quartiere, il pannello Quartiere torna a
mostrare tutta la citta'.

Undici attributi. `paese` troncato alle prime 15 modalita' su 100–151; tutti
gli altri interi, **inclusi i 33 quartieri di Brescia**.

**Ordine delle modalita' stabile fra citta'**: dichiarato dove esiste una
progressione naturale, alfabetico altrove. L'ordine per frequenza rendeva i
pannelli di due citta' non affiancabili.

**Barra di stato**: sintetici · censuari con lo scarto · % della citta'.

### 4.2 Marginali — tre marcatori

| | cos'e' | come si legge lo scarto |
|---|---|---|
| **barra** | la sottopopolazione filtrata | — |
| **tacca** (linea con testa) | la citta' intera | **associazione**: e' il valore atteso sotto indipendenza fra attributo e filtro |
| **rombo** | il censimento **al livello del filtro** | **errore del modello**: per gli incroci vincolati ci si aspetta rumore |

> **Correzione della v0.5.** Il design diceva che il riferimento «si sposta al
> livello della zona» sotto filtro spaziale. E' sbagliato: i marginali di zona
> dell'anello 1 stanno nel constraint set, quindi il rombo si incollerebbe
> alla barra e non si vedrebbe mai niente muoversi. La tacca **non si sposta**;
> il rombo si **aggiunge**.

**Dove il rombo non c'e'**, il pannello sbiadisce il titolo e dichiara
*«nessun dato censuario per questo incrocio»*: e' la distinzione fra osservato
e modello, resa visibile filtro per filtro.

Ogni pannello riporta **lo scarto massimo fra sintetico e censimento**: e' lo
stato *verifica* con un numero, calcolato dal vivo.

**Modalita' Δ** con banda `√(p(1−p)/n)` al 95%. Per le AVQ dovra' usare
`n_eff` della variabile (§2.1), quando ci saranno.

**Export**: CSV e LaTeX (`booktabs`) di tutte e tre le serie; SVG per pannello,
costruito a mano senza librerie.

### 4.3 Mappa

**Nessuna geometria.** La griglia si calcola aggregando `lon`/`lat` al volo.
Era la parte che sembrava piu' costosa di F5 ed e' sparita.

**Proiezione Web Mercator**, necessaria per allineare le tiles.

**Quota** — frazione del filtro sul totale locale, celle di ~150 m regolabili
su tre livelli, sotto 25 abitanti in grigio. E' l'unico modo informativo.

**Punti** — individui campionati (tetto 10k–120k), jitter **deterministico
dall'`id`** di ±7 m, sopra uno strato grigio della citta' intera. Il jitter
deve essere deterministico o il clic non puo' colpire quello che si vede.

> **Modo densita' rimosso**: contava gli individui per cella, quindi
> riproduceva la densita' di popolazione.

**Navigazione**: rotella, trascinamento, `adatta`. Il clic apre la scheda solo
se il puntatore si e' mosso meno di 4 px.

**Base cartografica opzionale** — CARTO chiaro (default), OpenStreetMap,
nessuna, con un velo chiaro al 42% sopra.

> **Debito verso §7.3.** OSM e CARTO non chiedono chiavi API ma sono servizi
> esterni: violano la condizione che tiene il progetto pubblicabile senza
> dipendenze. Per la rete la strada e' un estratto `.pmtiles` di Protomaps
> servito da noi (§12). L'opzione «nessuna» resta in elenco perche' si veda
> sempre che i dati stanno in piedi da soli.

**Costo**: la mappa legge il blocco C, ~1 MB, solo su richiesta.

### 4.4 Scheda individuo

Si apre cliccando un punto. Quaranta campi per anello, **ciascuno col proprio
segno di garanzia**, e le AVQ col conteggio di quante sono presenti sulle 21 —
che su un minore crolla a quattro o cinque, ed e' la spiegazione visiva del
collasso delle firme in §13.3.

Costo: `WHERE id = N` pota fino a un row group. **~0,15 MB la prima volta,
zero dopo.**

In fondo, **il rendering testuale della persona**, che e' il materiale da cui
SimComm costruisce il prompt: affiancato ai segni di garanzia rende visibile
quanta parte di quella persona e' dato.

Banner fisso e non chiudibile: **INDIVIDUO SINTETICO — NON ESISTE**.

### 4.5 Confronta — da fare

**A — comune** (sicuro). **B — distribuzione fra sezioni** (il livello
giusto), con la decomposizione della varianza 5,9× → 43,5×. **C — zone**, con
avviso.

**Avviso obbligatorio sulle AVQ**: Parma, Bologna e Modena condividono lo
stesso pool di 4.629 donatori, quindi ogni differenza AVQ fra le tre e'
integralmente compositiva.

### 4.6 Metodo e qualita' — da fare

MRE e z-score per blocco (§13.4) · copertura AVQ · riuso dei donatori e
`n_eff` per variabile · le sette assunzioni cliccabili · tier del paese ·
l'incidente dei nomi di zona di Bologna · i diagnostici di §13.1 · **la
tabella di copertura di §3.4** · **l'avviso di §15** in forma estesa.

---

## 5. Interazione e stato

Crossfilter completo; stato interamente nell'URL, mappa e modo inclusi:

```
?comune=017029&zona=17029012&istruzione=laurea_o_its&mappa=1&modo=punti
```

---

## 6. Grafica

**Estetica dell'anagrafe.** Serif per titoli, monospaziato con cifre tabulari
per tutte le cifre, un solo accento per il sintetico. I riferimenti in neutro
scuro distinti per **forma** — tacca con testa triangolare contro rombo — cosi'
la distinzione sopravvive alla stampa in bianco e nero.

---

## 7. Architettura

### 7.1 Strumenti

Nessuno scaffold. Pagina singola, DuckDB-WASM da CDN, nessuna libreria di
grafici: barre in HTML/CSS, SVG d'export a mano, mappa in canvas.
**Observable Framework resta rimandato.**

### 7.2 Il modello di costo

```
costo(query) = footer + Σ  peso(blocco) × (row group non potati / totale)
```

**Tre corollari verificati**: il numero di colonne richieste e' irrilevante;
la potatura per riga costa il 10,7%; quella spaziale il 22%, ma solo grazie
all'ordinamento per `zona`.

Init 0,7 s · prima query 0,79 MB e ~1,3 s · **filtri successivi 0 byte e
100–220 ms** · sessione piena ~2,5 MB.

### 7.3 Cosa costa zero adesso e molto dopo

1. interruttore `--pubblico` in `to_parquet.py` — **ancora non scritto, e ora
   serve davvero** (§15);
2. etichettatura: banner, watermark, provenienza nei CSV — **fatto** per la
   scheda individuo e per l'avviso globale;
3. **nessuna dipendenza da servizi esterni** — oggi violato dalla base
   cartografica, con la via d'uscita nota (`.pmtiles`, §12);
4. **il sito e' online** (§15): la decisione sugli indirizzi e' stata presa,
   non piu' rimandata.

---

## 8. Estensibilita'

```
to_parquet.py {C} --drop-avq-raw → manifest_min.py {C}
                                 → build_riferimenti.py {C} → build_indice.py
```

**Provato**: le quattro citta' girano con lo stesso codice e la tabella di
copertura esce identica. L'interfaccia non e' mai stata toccata per aggiungere
un comune — che era la prova richiesta.

Dieci capoluoghi emiliani ≈ 1,8 milioni di individui e **~30 MB di bundle**.

---

## 9. Prestazioni — misurate

| operazione | misurato |
|---|---|
| init DuckDB-WASM | 0,69–0,77 s |
| prima query, marginali | 0,79 MB · ~1,3 s |
| filtri successivi | **0 byte** · 100–220 ms |
| filtro su una zona | 0,23 MB |
| mappa (blocco C, su richiesta) | ~1 MB |
| scheda individuo | ~0,15 MB la prima, 0 dopo |
| sessione piena | ~2,5 MB |

---

## 10. Fasi

**F0** ✔ i due diagnostici, su Modena e Parma (§13.1).
**F1** ✔ smoke test dello stack (§13.2).
**F2** ✔ `donor_id` dalla firma AVQ (§13.3).
**F3** ✔ bundle minimo e pannello dei marginali.
**F4** ✔ riferimento censuario dal constraint set.
**F5** ◧ mappa: quota, punti, navigazione, base cartografica.

**Pubblicazione** ✔ fatta in anticipo su F9, in forma provvisoria: Cloudflare
Pages da cartella, bundle completo, avviso esplicito (§15).

**Prossime, in ordine di dipendenza:**

**F6 — `donor_id` nel Parquet** e pannello AVQ con `n_eff` per variabile. E'
il pezzo mancante della catena dell'onesta': oggi le AVQ compaiono solo nella
scheda individuo, dove il problema non si pone. E' anche cio' che serve al
lavoro su Caffaro, perche' `AMBIENTE` e le `PUNTIFI` sono le variabili su cui
il pannello non deve mentire.

**F7 — Confronta** fra citta', livelli A e B.
**F8 — Metodo**: la pagina che rende l'app difendibile.
**F9 — grafica** in senso proprio, e pubblicazione definitiva.

---

## 11. Questioni aperte

1. **Definizioni vere di `macroeta` e `istr4`** in `assign_avq.py`. Senza,
   `cella_avq` non e' stimabile. *Non blocca F6*: le AVQ dipendono dalla cella,
   che e' funzione di `(sesso, eta, istruzione)`, quindi condizionare su quella
   tripletta — un raffinamento della cella vera — da' la scomposizione esatta.
2. **`n_eff` per universo di variabile** (blocchi 5 e 6 di
   `verifica_donor.py`).
3. **Definizione di MRE in `fit_cs.py`.** La formula del riferimento e' la
   **deviazione standard** dell'errore relativo; il valore assoluto medio vale
   `√(2/π) = 0,798` volte tanto. Strumento e paper devono coincidere.
4. **`sesso × background × origine_genitori`**: |z| fino a 4,0, replicato
   (§13.4). Ipotesi: l'esclusione α=0 post-hoc sposta massa.
5. **Fonti comunali di zona**: quali disponibili come *livelli*? Sono l'unica
   validazione esterna.
6. **Emilia-Romagna**: quanti capoluoghi, e la vista regionale?
7. **Le riparazioni della pipeline** (§13.1): permutazione di `istruzione`
   entro (zona, sesso, bin), e le **26 esclusioni α=0**. Post-hoc entrambe.
8. **Campionamento degli agenti per firma** invece che per individuo (§14).
9. **Configurazione per arXiv**: rovesciata rispetto a oggi — codice pubblico
   e citabile, dati degradati o su richiesta. Richiede `--pubblico`, che va
   scritto **prima** della prossima pubblicazione e non dopo (§15).

---

## 12. Registro dei miglioramenti

### Fatti

| | effetto |
|---|---|
| colonne in tre blocchi per uso | Q5 da 2,297 a 0,915 MB |
| righe per `zona, sezione` | filtro di zona al 22% |
| `id` DELTA_BINARY_PACKED | 0,79 → <0,09 MB |
| AVQ grezze eliminate | blocco B 2,659 → 1,411 MB |
| `donor_id` dalla firma | sblocca `n_eff` senza rilanciare la pipeline |
| `n_eff` di Kish | il numero cambia di un fattore 2,8 |
| z-score invece dell'errore relativo | il MRE per cella era tutto rumore |
| riferimento da `cs_K9C.json` | F4 senza fonti esterne |
| `zona` etichettata coi quartieri | un pannello invece di due gemelli |
| troncamento per attributo | Brescia non perde 18 quartieri su 33 |
| ordine stabile fra citta' | pannelli affiancabili |
| crossfilter che esclude la propria dimensione | il pannello non collassa su se' stesso |
| jitter deterministico | punti fermi, e quindi cliccabili |
| percorso del bundle risolto a runtime | lo stesso file funziona in locale e online |
| | **file 5,22 → 3,12 MB** |

### Proposti

- **`--pubblico` in `to_parquet.py`**: toglie `via` e `civico`, aggancia i
  punti al centroide dell'edificio. Previsto dalla v0.3, mai scritto, e ora
  necessario (§15);
- **base cartografica `.pmtiles`**: estratto Protomaps di Emilia-Romagna e
  Lombardia orientale, servito dal bundle. Toglie l'unica dipendenza esterna.
  Qualche decina di MB per regione, cioe' **piu' di tutti i Parquet messi
  insieme** — quindi host separato;
- **rimuovere `quinq`** (0,089 MB, 13% del blocco caldo): e' `least(eta_anni
  // 5, 15)` in SQL;
- **rimuovere `quartiere`**: e' l'etichetta di `zona` e ora sta nel manifest;
- **`donor_id` e `donor_anno`** nell'export;
- sostituire la riga «aggregazione tipica» in `to_parquet.py`;
- correggere `MRE att` in `verifica_vincoli.py` col fattore `√(2/π)`, e
  stampare `sd(z)` per blocco al posto di `z_max`.

### Scartati, col motivo

- **spezzare il blocco AVQ**: Q4 ha la sovralettura peggiore ma **non e' una
  query realistica** — il pannello fiducia legge tutte e dodici le `PUNTIFI`;
- **AVQ in int8**: il dizionario e' gia' a 4 bit, all'ottimo teorico;
- **`agg_sezioni.parquet` come requisito**: mascherava un costo d'ingresso che
  non esiste;
- **modo densita' nella mappa**: riproduce la densita' di popolazione;
- **geometrie per la mappa**: la griglia da `lon`/`lat` basta;
- **`lon_j`/`lat_j` nel Parquet**: il jitter si calcola a runtime;
- **rigenerare le popolazioni** per i 3 record impossibili: sono 3 su 970.000,
  la correzione e' post-hoc, e rigenerare invaliderebbe misure e `donor_id`;
- **GitHub Pages per la prova** (§15): avrebbe richiesto di rendere pubblico
  il repo, decisione da prendere con calma e non per far vedere una prova.

---

## 13. Diario delle misure

### 13.1 F0 — i due diagnostici (Modena e Parma)

**(a) Seam quinquennale.** MAE grezzo indistinguibile; normalizzando per
dimensione di classe le due classi del seam finiscono **nei primi tre posti su
sedici in entrambe le citta'** (p ≈ 6·10⁻⁴). Ma l'eccesso e' del 40%:
**l'ipotesi di uniformita' non e' dominante.**

*Sistematico e non previsto*: dentro ciascuno dei cinque bin veri il sintetico
pende verso il **giovane**, **dieci prove su dieci**, 0,10–0,44 pp. La
distribuzione dentro il bin non e' vincolata da niente, quindi l'indiziato e'
l'assunzione (9). Nella regione infantile il verso si inverte: `10-14`
sovrarappresentata di +0,37 e +0,35, e li' opera la frazione 4/5–1/5.

> **Ritirato.** La v0.5 riportava una discrepanza «fino a 1,42% fra due
> prodotti censuari». Era **rumore di campionamento**: il target del constraint
> set e le colonne P coincidono, e lo scarto della popolazione dal proprio
> target vale z = 0,24 su Modena e 0,64 su Parma.

**(b) Coerenza eta'–istruzione**: 2,64% a Modena, 2,74% a Parma, concentrate
nei bin `9-14` e `15-24`. *Riparazione*: permutare `istruzione` entro
(zona, sesso, bin).

**(c) Combinazioni impossibili**: `diploma` a 2 anni e `post_laurea` a 13
(Parma), `altra_condizione` a 0 anni (Modena). Tre record su 970.000.

### 13.2 F1 — smoke test DuckDB-WASM

Otto query isolate; sette su otto entro il 20% del modello di costo.
**Q3/Q3N = 10,7%**, **Q6/Q2 = 21,8%**. Tempi a caldo 100–220 ms.

*Errore di metodo corretto*: la prima misura di Q3 era contaminata, perche' le
query di una sessione si scaldano a vicenda. La contaminazione, letta come
fenomeno invece che come errore, e' cio' che ha rivelato la struttura a blocchi.

### 13.3 F2 — `donor_id` dalla firma AVQ

Firme distinte: Modena 4.199 contro 4.617 donatori, Bologna 4.207 contro
4.625. **Differenza identica, −418**: proprieta' del pool emiliano, e l'errore
va nella **direzione prudente**.

`n_eff` di Kish 1.520 e 1.599 — il conteggio dei distinti sbagliava di 2,8×.
La firma piu' riusata vale da sola **~10% del peso statistico della citta'**.

*Limite*: quella firma e' dei minori, per cui la 21-upla si riduce a quattro
valori. I numeri ×11,0 e ×15,6 sono calcolati sull'universo sbagliato.

### 13.4 Anatomia del constraint set e stato del pool

**Sedici blocchi**, identici nelle quattro citta'. Undici completi, cinque
parziali. I parziali sono i **complementi fuori universo**.

> **Il punto metodologico, materiale da paper GibbsPCD.** Quando l'ISTAT
> **esclude per universo**, la cella non compare nella tavola. Quando il
> censimento **osserva zero**, la cella compare con valore zero. Per MaxEnt le
> due cose sono **opposte**: una cella assente e' *non vincolata*, una cella a
> zero e' *vietata*. La prova che il meccanismo funziona quando il dato c'e':
> `cittadinanza × background` ha 6 zeri espliciti e `sesso × eta ×
> stato_civile` ne ha 2, e nessuno e' violato. Le **26 coppie** logicamente
> impossibili di eta' × condizione ed eta' × istruzione **non sono vincolate
> da nessun blocco**, ed e' per questo che tre record ci sono finiti dentro.

**Il pool e' un campione pulito.**

| | Modena | Parma | atteso |
|---|---|---|---|
| `sd(z)` | 1,030 | 1,031 | 1,000 |
| media(z) | −0,021 | +0,005 | 0 |
| `\|z\|` medio | 0,829 | 0,810 | 0,798 |
| `\|z\| > 2` | 4,45% | 5,49% | 4,55% |
| zeri hard violati | 0 | 0 | 0 |

`sd(z)² = 1,06` e' il **fattore di inflazione della varianza**: il pool di
184.597 individui vale ~174.000 estrazioni indipendenti. E' la prima
quantificazione del mixing della catena.

**Un blocco anomalo**, replicato: `sesso × background × origine_genitori`, con
`|z|` medio 1,16 e 1,05 contro 0,80 dei blocchi demografici, e picchi da −3,90
a +4,00. Le celle a **genitori misti perdono massa**, quelle a genitori
omogenei la guadagnano.

---

## 14. Cosa significa per SimComm

**La diversita' psicologica effettiva di una popolazione di agenti non e'
quella dei suoi individui: e' quella di ~1.500 donatori**, e non cresce
prendendo una citta' piu' grande.

**Il secondo ordine e' piu' insidioso.** Due agenti che condividono la firma
hanno profili **identici**, non simili: in una simulazione LLM le loro
risposte sono correlate per costruzione e non sono evidenza indipendente. Con
riusi medi di 40–93, in un campione di 120 agenti da Bologna le collisioni non
sono trascurabili.

**Domanda di disegno sperimentale**: conviene campionare gli agenti **per
firma** invece che per individuo? Garantirebbe profili distinti al prezzo di
distorcere le quote demografiche — che sono cio' che il tier 1 esiste per
garantire. Va deciso e dichiarato nel paper.

*La scheda individuo di §4.4 rende questa sezione tangibile: due punti vicini
sulla mappa con la stessa fiducia, la stessa salute e lo stesso BMI sono due
individui che condividono il donatore.*

---

## 15. Pubblicazione

**Stato**: online su Cloudflare Pages, `animarium.pages.dev`. Repo `Animarium`
privato. Il sito nasce da una cartella, non da git: nessun ramo lo descrive.

### Perche' Cloudflare e non GitHub Pages

Pages su repo privati richiede un piano a pagamento, quindi l'alternativa era
rendere pubblico il repo — codice, note e storia insieme — che e' una
decisione da prendere con calma e non per far vedere una prova. Cloudflare da
cartella non lascia niente da ripulire, si spegne davvero, e consente di
mettere un accesso ristretto (Access, gratuito fino a 50 persone) se serve.

Il rovescio: **il deploy non e' versionato**. Non esiste un ramo che dica cosa
e' pubblicato e quando. Per una prova va bene; per qualcosa di stabile si torna
al ramo `gh-pages`, che `deploy.py --push` sa gia' fare.

### Cosa e' esposto

`index.html`, `smoke.html`, e il **bundle completo**. Quindi chiunque abbia
l'URL puo' scaricare `pop.parquet` — 198.259 individui con via, civico e
coordinate. E' deliberato, e regge su tre argomenti.

**Nessuna divulgazione statistica.** Tutti gli ingressi sono gia' pubblici:
ANNCSU e' un archivio aperto di indirizzi, i microdati AVQ sono *public use* e
anonimizzati, le tavole censuarie sono pubblicate. La popolazione e' una
ricombinazione di cose pubbliche e non rivela nulla su nessuna persona reale.

**Il rischio e' di interpretazione, non di privacy**: qualcuno scarica il file,
lo tratta come dato reale, e produce una mappa della sfiducia nel Comune via
per via da un dataset che sulla sfiducia non ha *nessuna* informazione
geografica. Su Caffaro non e' un'ipotesi di scuola.

**Da cui la forma dell'avviso.** Non dice «e' sintetico» e basta: dice **a
quale risoluzione il dato ha contenuto**. La posizione dentro la sezione e'
arbitraria per l'assunzione (10) — niente lega quella persona a quell'edificio
— quindi la mappa a punti al livello del civico e' *precisione spuria*.
Dichiararlo e' piu' onesto che togliere la via lasciando le coordinate esatte,
che sarebbe una privacy di facciata.

Nel `<head>` c'e' `noindex, noarchive`. Non e' un lucchetto, e **spegnere il
sito non ritira quello che e' gia' stato scaricato**.

### Procedura

```
python build/deploy.py
npx wrangler pages deploy deploy/ --project-name animarium --branch main
```

`--branch main` deve coincidere col *production branch* del progetto: se non
coincide, Cloudflare tratta il caricamento come anteprima e i file finiscono
su un URL con prefisso mentre quello principale resta vuoto.

Alternativa senza Cloudflare, su ramo `gh-pages` del repo (che pero' dev'essere
pubblico): `python build/deploy.py --push`.

Il pannello cerca il bundle prima in `bundle/` e poi in `../bundle/`, quindi lo
stesso file funziona in locale e pubblicato — anche sotto un sottopercorso,
dove `../` uscirebbe dal sito.

### Cosa manca

- **`--pubblico`**: toglie `via` e `civico` e aggancia i punti al centroide
  dell'edificio. Previsto da §7.3 fin dalla v0.3, mai scritto;
- **accesso ristretto**: Cloudflare Access non attivato;
- **versionamento del deploy**: oggi non si sa cosa c'e' online se non
  guardandolo.

### Per arXiv, la configurazione si rovescia

Oggi pubblichiamo i dati e teniamo privato il codice. Per un paper e'
l'opposto: **il codice e' cio' che rende i dati interpretabili e il lavoro
riproducibile**, i dati con indirizzi veri sono la parte da maneggiare.

Il compromesso da preparare e' codice pubblico e citabile, piu' un bundle
**degradato** di una citta' sola per riprodurre le figure, con i dati completi
su richiesta. Un referee ragionevole chiedera' di poter rifare almeno una
figura, e «il codice senza dati» non basta.
