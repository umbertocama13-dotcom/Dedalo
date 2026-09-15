# Dedalo — Workflow di sviluppo

Questo documento raccoglie **perché** il PoC è fatto così: decisioni di design, alternative scartate, tentativi che non hanno funzionato, limiti conosciuti e prossimi passi.

Per installazione, avvio e uso vedi il [README.md](README.md).

Stato al 15/09/2026: **v2 completa** e **app desktop per Windows pronta per la build**. Backend testato su MySQL e SQLite (604 test, compresi quelli con i modelli veri), launcher verificato su Linux con il modello ONNX e il server reale. L'installer Windows non è ancora stato costruito e provato su Windows. La modalità LLM è testata solo con provider simulati.

---

## Indice

- [Parte 0 — App desktop per Windows](#parte-0--app-desktop-per-windows)

- [Parte 1 — v2: ricerca semantica, conversazione, interfaccia esperto, CSV](#parte-1--v2)
  1. [Perché la v2](#1-perché-la-v2)
  2. [Architettura v2](#2-architettura-v2)
  3. [Modello dati](#3-modello-dati)
  4. [Ricerca semantica e calibrazione](#4-ricerca-semantica-e-calibrazione)
  5. [Conversazione, probabilità e domande](#5-conversazione-probabilità-e-domande)
  6. [Assistente LLM facoltativo](#6-assistente-llm-facoltativo)
  7. [Interfaccia esperto e CSV](#7-interfaccia-esperto-e-csv)
  8. [Test](#8-test)
  9. [Tentativi che non hanno funzionato (v2)](#9-tentativi-che-non-hanno-funzionato-v2)
  10. [Limiti conosciuti](#10-limiti-conosciuti)
  11. [Migliorie possibili](#11-migliorie-possibili)
- [Parte 2 — v1: decisioni ancora valide e storia](#parte-2--v1)

---

# Parte 0 — App desktop per Windows

## D1. Obiettivo

La v2 richiedeva MySQL, Python, Node e due terminali. L'obiettivo era un `Dedalo-Setup.exe` che crea un'icona sul desktop: doppio clic e l'app si apre, senza installare altro. Scelte fatte insieme: **PC singolo** con database integrato, **PyInstaller + pywebview**, **installer Inno Setup**, **ONNX Runtime** al posto di PyTorch, **primo esperto creato al primo avvio**, build su una VM Windows 10.

## D2. Architettura

```
Dedalo.exe (PyInstaller onedir, senza console)
 └─ desktop/launcher.py
     1. lock di istanza singola          → seconda apertura: messaggio e uscita
     2. %LOCALAPPDATA%\Dedalo            → dedalo.env (JWT casuale), logs\
     3. primo avvio                      → dedalo.db creato da schema SQLite + catalogo
     4. porta libera su 127.0.0.1         → uvicorn in un thread, create_app(static_dir=frontend)
     5. finestra pywebview                → "Avvio in corso…" poi l'app
     6. chiusura finestra                 → stop del server
```

Lo sviluppo non è cambiato: il desktop è una **seconda configurazione** dello stesso codice (`DB_BACKEND=sqlite`, `EMBEDDING_BACKEND=onnx`, `static_dir`).

## D3. Decisioni

### SQLite per il PC singolo, MySQL resta per server e sviluppo

- **Quando serve MySQL invece di SQLite**: non per la quantità di dati (la knowledge base è di pochi MB) né per la velocità su un PC. Serve quando **più postazioni devono vedere la stessa knowledge base**. SQLite è un file senza server, e **non va messo su una cartella di rete condivisa**: su SMB il locking non è affidabile e il file si corrompe. Altri segnali: molte scritture contemporanee (SQLite ne accetta una alla volta), backup e permessi gestiti dall'IT, altri sistemi aziendali che leggono i dati.
- **Stesso SQL per entrambi**. Differenze gestite:
  - `ENUM` → `CHECK (role IN (...))`;
  - collation `utf8mb4_unicode_ci` → `COLLATE NOCASE` su username e famiglie;
  - `ON UPDATE CURRENT_TIMESTAMP` → `updated_at` impostato nell'`UPDATE` del repository;
  - `LIKE` con `ESCAPE '!'` esplicito (MySQL usa la backslash di default, SQLite non ha un default);
  - `PRAGMA foreign_keys=ON` a ogni connessione: **senza, SQLite ignora le foreign key**;
  - `SET NAMES utf8mb4` tolto dai seed (non valido in SQLite): la connessione dei test imposta già il charset e il README usa `--default-character-set=utf8mb4`.
- **Seed diviso**: `seed_catalog.sql` (famiglie e fasi, usato anche dal desktop) e `seed.sql` (utenti demo e diagnosi, solo sviluppo). Le diagnosi di esempio del desktop arrivano da `sample_diagnostics.csv`, generato dal seed; un test verifica che coincidano.
- **Test su entrambi i database**: la fixture `settings` è parametrizzata, quindi ogni test d'integrazione gira su MySQL e su SQLite.

*Scartato: MySQL installato sul PC.* Non sarebbe stato "clicca e parte".
*Scartato per ora: server centrale + client.* È la strada per una knowledge base condivisa, ma richiede un server sempre acceso in rete.

### pywebview invece di Electron

Electron non esegue Python: servirebbe comunque PyInstaller per il backend, più Node ed electron-builder, più il codice per avviare e chiudere il processo Python. pywebview apre una finestra nativa con Edge WebView2 (già presente su Windows 10/11 aggiornati; l'installer lo installa se manca) nello stesso processo, con una sola toolchain e circa 150 MB in meno.

### ONNX Runtime invece di PyTorch

- `scripts/export_onnx_model.py` esporta il modello con `optimum-onnx` e **si ferma** se il modello usa moduli che `OnnxEmbedder` non replica (per esempio un layer `Dense` o un pooling diverso dalla media). Il modello italiano usa *mean pooling* e `max_seq_length` 512.
- `OnnxEmbedder` replica sentence-transformers: tokenizer (`tokenizers`, senza PyTorch), ONNX Runtime, media dei vettori dei token pesata con l'attention mask, normalizzazione L2.
- **Misure**:

  | | PyTorch | ONNX |
  |---|---|---|
  | coseno tra i vettori delle due versioni (62 frasi) | — | ≥ 0,999 |
  | frasi da trovare: prime 5 / prima / fasce sicura-incerta-nessuno | 47/48, 40/48, 39/8/1 | **identico** |
  | frasi fuori tema: sicura / incerta / nessun dato | 0/6/3 | **identico** |
  | NLL della probabilità (T 0,03, "nessuna" 0,60) | 0,403 | 0,398 |
  | tempo per richiesta | ~56 ms | **~23 ms** |
  | dipendenze | PyTorch ~1 GB | onnxruntime ~50 MB |

  L'export segnala una differenza massima di 5·10⁻⁵ sui vettori dei singoli token (tolleranza dello strumento 10⁻⁵): è rumore numerico, e il test di parità conferma che non incide.
- Le soglie calibrate restano valide: nessuna ricalibrazione.
- *Scartata per ora: quantizzazione int8* (modello da ~110 MB invece di 422 MB). Cambierebbe i punteggi e richiederebbe una nuova calibrazione.

### Installer con cartella (onedir) invece di un solo .exe

Un eseguibile unico (onefile) dovrebbe estrarre centinaia di MB in una cartella temporanea **a ogni avvio**: decine di secondi di attesa e più segnalazioni degli antivirus. Con onedir l'installer copia i file una volta, e l'avvio richiede pochi secondi (misurato su Linux: server pronto in 3,3 s col modello ONNX).

### Primo avvio senza credenziali preimpostate

- L'installer non contiene utenti: chi apre l'app la prima volta crea l'**esperto**. `POST /setup` funziona **solo finché la tabella utenti è vuota**, poi risponde `409`.
- Le diagnosi di esempio passano da `import_service`, cioè dalle stesse regole di un import CSV manuale.
- L'esperto crea gli operatori dalla nuova pagina **Utenti** (`GET/POST /users`, solo expert, username unico senza distinguere maiuscole e minuscole).

### Dettagli del launcher

- **Porta libera scelta dal sistema** (bind sulla porta 0): una porta fissa potrebbe essere occupata da un altro programma. Il server ascolta **solo su 127.0.0.1**.
- **Istanza singola** con un lock del sistema operativo su file (`msvcrt` su Windows, `fcntl` su Linux). Se l'app va in crash il sistema lo rilascia da solo: nessun lock orfano da togliere a mano.
- **`sys.stdout`/`stderr` rediretti sul log**: in un eseguibile PyInstaller senza console valgono `None`, e uvicorn e il logging fallirebbero alla prima scrittura.
- **Database creato in un file temporaneo e rinominato** solo a fine creazione: un primo avvio interrotto non lascia un database a metà.
- **Impostazioni desktop forzate nel codice**: `dedalo.env` contiene solo ciò che l'utente può cambiare (chiave JWT, AI, soglie). Scrivere `DB_BACKEND=mysql` nel file non ha effetto, perché gli argomenti passati a `Settings` hanno la precedenza sul file.
- **Download abilitati in WebView2** (`ALLOW_DOWNLOADS`): senza, export CSV e modello non funzionerebbero.
- **Frontend servito dal backend** sullo stesso indirizzo (niente CORS): i file della build come file statici, e una route finale che restituisce `index.html` per le route di React Router (un ricaricamento di `/chat` non dà 404), con controllo che blocca i percorsi `../`.
- **La disinstallazione non cancella i dati** in `%LOCALAPPDATA%\Dedalo`.

## D4. Tentativi che non hanno funzionato

| Tentativo | Cosa è successo | Come è stato risolto |
|---|---|---|
| `optimum-onnx` installato nel venv di sviluppo | pip ha retrocesso `transformers` (5.17 → 4.57) e `huggingface-hub`, incompatibili con sentence-transformers | versioni di sviluppo ripristinate; export in un venv separato (anche in `build.ps1`) |
| Test "vincolo violato → `IntegrityError`" | su MySQL PyMySQL segnala la violazione di un `CHECK` (errore 3819) come `OperationalError` | il test accetta entrambe le classi: il database rifiuta comunque la riga |
| `SET NAMES utf8mb4` nei seed condivisi | sintassi solo MySQL, SQLite la rifiuta | tolto dai seed; charset impostato dalla connessione e dal comando `mysql` |
| SQLite in modalità WAL (più letture durante una scrittura) | provando il pacchetto: alla chiusura le ultime modifiche restavano in `dedalo.db-wal`, e una copia del solo `dedalo.db` conteneva 0 utenti e 0 diagnosi. Il backup indicato nella documentazione avrebbe perso tutto | `journal_mode=DELETE` (il default di SQLite): ogni scrittura confermata finisce subito in `dedalo.db`. Con un solo utente WAL non serviva; test di regressione sulla copia del file |
| Prova del pacchetto che attendeva la riga con l'indirizzo | la `print` del launcher non svuotava il buffer: con l'output in pipe la riga non arrivava mai e la prova andava in timeout | `flush=True` sulle `print` del launcher |

## D5. Limiti conosciuti

1. **Knowledge base separata per ogni PC**: nessuna sincronizzazione, solo export/import CSV.
2. **Famiglie e fasi** sono quelle del catalogo di esempio: non si gestiscono dall'interfaccia né dal CSV.
3. **Utenti**: si possono solo creare. Niente modifica del ruolo, disattivazione o reset della password da interfaccia; una password dimenticata dell'unico esperto non si recupera.
4. **Eseguibile non firmato**: SmartScreen mostra un avviso al primo avvio, e alcuni antivirus segnalano i pacchetti PyInstaller come falsi positivi.
5. **Installer non ancora provato su Windows reale**: spec, launcher e server sono verificati su Linux, ma finestra WebView2, download e installer vanno controllati sulla VM (checklist in `packaging/windows/BUILD.md`).
6. **Primo avvio in contemporanea**: due richieste di setup nello stesso istante potrebbero creare due esperti. Su un PC singolo c'è una sola schermata aperta.
7. **SQLite**: `NOCASE` ignora maiuscole e minuscole solo per le lettere senza accento.
8. **Porta locale**: mentre l'app è aperta, un altro utente dello stesso PC potrebbe raggiungere il server (serve comunque il login).
9. **Nessun aggiornamento automatico**: una nuova versione va reinstallata sopra la precedente (i dati restano).
10. Dimensione dell'installer dominata dal modello (422 MB).

## D6. Migliorie possibili

- Gestione di famiglie e fasi (interfaccia o CSV) e gestione completa degli utenti.
- Modalità **server** con MySQL per più postazioni, riusando lo stesso codice.
- Firma del codice, aggiornamento automatico, quantizzazione int8 del modello dopo una ricalibrazione.
- Build automatica su GitHub Actions (runner Windows) invece della VM.

---

# Parte 1 — v2

## 1. Perché la v2

Provando la v1 è emerso il limite decisivo: **non faceva quello per cui era pensata**. Il matching `token_sort_ratio` con soglia 80 trovava una diagnosi solo se l'operatore scriveva una frase quasi identica al sintomo registrato. Doveva quindi conoscere a memoria la colonna dei sintomi.

Misurato sulle stesse 60 frasi da operatore usate per calibrare la v2 (sezione 4):

| | diagnosi giusta tra le prime 5 | frasi fuori tema respinte | negazioni gestite |
|---|---|---|---|
| **v1** (fuzzy, soglia 0,80) | **3 / 48** | 9 / 9 | 0 / 3 |
| **v2** (modello italiano + fuzzy) | **47 / 48** | nessuna mostrata come sicura; 3 / 9 senza ipotesi, 6 / 9 come incerte | 3 / 3 |

Richieste di `update.md`, tutte implementate:

1. ricerca per significato (vector search);
2. chat guidata, con LLM **attivabile e disattivabile**: l'app deve restare utile anche offline e senza costi;
3. mai una risposta univoca, ma **una lista di possibilità con la probabilità**;
4. interfaccia per l'esperto (inserimento, consultazione, modifica);
5. revisione delle tabelle (unificazione, eccezioni, utilità delle fasi);
6. import/export CSV, con una spiegazione per l'esperto su come compilare il file.

## 2. Architettura v2

```
Browser (React)
   │  fetch + Bearer token, conversazione inviata per intero a ogni turno
   ▼
routes/            ← validazione, ruolo (dependencies.py)
   │
services/
   │   diagnosis_service      orchestrazione del turno
   │   ├── matching/          SemanticMatcher (embedding + fuzzy + regola negazione)
   │   │     └── embeddings/  Embedder locale + cache per testo
   │   ├── probability_service    percentuali con quota "nessuna di queste"
   │   ├── disambiguation_service domanda di scelta deterministica
   │   └── llm_advisor_service    passo LLM facoltativo, risposta validata
   │   knowledge_base_service / csv_service / import_service
   ▼
repositories/      ← SQL esplicito
   │
MySQL
```

### Cosa è deterministico e cosa no

| Parte | Deterministica? |
|---|---|
| Candidati (contesto SQL, embedding, fuzzy, negazione, soglie) | ✅ a parità di modello e dati |
| Componente, causa, soluzione mostrati | ✅ sempre letti dal DB, mai generati |
| Ordine e probabilità delle ipotesi | ✅ calcolati dai punteggi, anche in modalità LLM |
| Domande di scelta offline | ✅ costruite dai dati |
| Domande in modalità LLM | ❌ generate, ma possono solo restringere i candidati |
| Scelta di quali ipotesi tenere in modalità LLM | ❌ proposta dal modello, validata dal server |

### Flusso di un turno (`POST /diagnosis`)

1. Pydantic valida contesto, messaggi (massimo 20 da 1000 caratteri, almeno uno dell'operatore) e id esclusi.
2. `validate_family_phase`: famiglia inesistente → `404`; fase senza famiglia o di un'altra famiglia → `400`.
3. `list_candidates` carica le diagnosi applicabili: generiche, della famiglia e, se la fase è indicata, solo di quella fase. Senza fase entrano tutte quelle della famiglia. Gli id esclusi vengono tolti.
4. Ogni messaggio dell'operatore passa dal matcher; per ogni diagnosi si tiene il punteggio migliore (sezione 5).
5. Nessun candidato sopra `SEMANTIC_RECALL_THRESHOLD` → `no_match`.
6. Senza AI: ipotesi con probabilità ed eventuale domanda di scelta. Con AI: il modello decide tra domanda, restringimento o `no_match`; se la risposta non è valida si torna al punto precedente con `ai_fallback: true`.

## 3. Modello dati

### Una tabella `diagnostics` al posto di `base_diagnostics` + `diagnostic_exceptions`

**Il dubbio di `update.md`**: le tabelle erano separate per le prestazioni? **No.** Il motivo era la normalizzazione, e con qualche migliaio di righe una JOIN costa pochi millisecondi. Si è quindi unito ciò che non aveva motivo di stare separato.

```sql
diagnostics (id, symptom_description, affected_component, probable_cause, recommended_solution,
             family_id NULL, cycle_phase_id NULL, created_by, created_at, updated_at)
```

| `family_id` | `cycle_phase_id` | Ambito |
|---|---|---|
| NULL | NULL | tutte le famiglie |
| valorizzato | NULL | tutta la famiglia |
| valorizzato | valorizzato | solo quella fase |

- **Eliminate le eccezioni.** Una "procedura specifica per fase" è ora una riga normale con la fase valorizzata. In chat compare accanto alle generiche, con il suo badge, e a parità di punteggio viene prima (sezione 5). Motore, API, CSV e interfaccia hanno un concetto in meno.
- **Restano separate `product_families`, `cycle_phases` e `users`.** Alimentano i menu, un nome si corregge in un solo punto, e la FK impedisce che "Cella saldatura" e "Cella di saldatura" diventino due famiglie. È esattamente l'errore che l'import CSV intercetta.
- **FK composita** `(cycle_phase_id, family_id) → cycle_phases (id, family_id)`, come in v1. MySQL non la controlla se una delle colonne è NULL, ed è ciò che permette le righe "tutta la famiglia".
- **`CHECK (cycle_phase_id IS NULL OR family_id IS NOT NULL)`**: una fase senza famiglia non ha senso. Richiede MySQL 8.0.16+ (verificato su 8.0.46).
- **FK di contesto con `RESTRICT`, non `CASCADE`**: MySQL vieta azioni referenziali sulle colonne usate in un `CHECK` (errore 3823).
- **Rimosso l'indice FULLTEXT**: in v1 non era usato, e la ricerca semantica ne prende il posto anche come futuro pre-filtro.
- Verificato sul database reale: la fase senza famiglia viene rifiutata (3819), la fase di un'altra famiglia (1452), la famiglia inesistente (1452).

*Scartato: tabella `symptoms` separata con le diagnosi collegate.* Il testo del sintomo sarebbe salvato una volta sola, ma l'import CSV dovrebbe riconoscere i sintomi esistenti e anche l'interfaccia diventerebbe più complessa. Con una riga per diagnosi il CSV corrisponde 1:1 a una riga di Excel. La ripetizione del testo non pesa: la cache degli embedding lavora per testo, quindi un sintomo ripetuto viene calcolato una volta sola.

### Le fasi: facoltative, non eliminate

L'esempio di `update.md`: la cella di saldatura non completa il ciclo, ma il guasto è sul nastro pallet. La fase in cui l'allarme appare non dice dove sta il guasto. D'altra parte alcune procedure valgono davvero solo in una fase (per esempio dopo un cambio formato).

- **L'operatore** può non indicare la fase ("*Non so / tutte le fasi*"): entrano tutte le diagnosi della famiglia.
- **L'esperto** scrive una diagnosi a livello di famiglia quando il sintomo riguarda tutta la cella, come nel seed (id 26-28), e a livello di fase solo quando serve.
- Con la fase indicata restano esclusi solo i sintomi scritti per altre fasi.

*Scartato: eliminare le fasi.* Più semplice, ma si perderebbe la procedura specifica per fase.
*Scartato: fasi obbligatorie come in v1.* Resterebbe il limite dell'esempio.

### Seed

3 famiglie, tra cui una **cella di saldatura robotizzata** con nastro pallet, e 36 diagnosi: 10 generiche, 16 per famiglia, 10 per fase. Coprono sintomo ripetuto con cause diverse, il caso del fermo cella, coppie di sintomi opposti per la negazione, sintomi simili su componenti diversi.

## 4. Ricerca semantica e calibrazione

### sentence-transformers direttamente, senza LlamaIndex

- Le righe sono frasi corte: nessun chunking, nessun loader, nessuna persistenza su disco. LlamaIndex avrebbe portato molte dipendenze per una funzione di due righe (embedding e prodotto scalare).
- Nell'esempio di `update.md`, `as_query_engine().query()` avrebbe anche **chiamato un LLM** per sintetizzare una risposta, e con le impostazioni di default usa OpenAI sia per gli embedding sia per il testo. È l'opposto del requisito "cause e soluzioni solo dal DB".
- Il nuovo matcher implementa l'interfaccia `Matcher` già prevista in v1: route e repository non sono cambiati per questo.

### Cache per testo invece di un indice vettoriale

`EmbeddingCache` ricorda il vettore di ogni testo già visto. A ogni richiesta i candidati si leggono dal DB e si calcolano solo i testi nuovi; all'avvio parte un *warm-up* su tutti i sintomi.

- Il **DB resta l'unica fonte di verità**: dopo una modifica o un import non c'è nessun indice da aggiornare, e la modifica è visibile subito.
- *Scartato: FAISS / Chroma / indice persistente.* Andrebbe sincronizzato a ogni scrittura, con un guadagno nullo a questi volumi.
- Thread-safe (`threading.Lock`), perché FastAPI esegue le route sincrone in un pool di thread. Il calcolo avviene fuori dal lock, così una richiesta lenta non blocca le altre.

### Scelta del modello: misurata, non stimata

`tests/fixtures/operator_queries.json` contiene 60 frasi scritte come un operatore: sinonimi, frasi corte, refusi, gergo, negazioni, frasi fuori tema, sintomi di un'altra famiglia. 48 devono trovare una diagnosi, 9 no, 3 sono negazioni. Lo script `scripts/evaluate_matching.py` le misura.

Primo confronto, tra soglia assoluta e criterio relativo (primo punteggio meno media o mediana dei candidati), accuratezza bilanciata tra "diagnosi trovata tra le prime 5" e "frase fuori tema respinta":

| Modello | Dimensione | Soglia assoluta | Relativo (miglior criterio) | Note |
|---|---|---|---|---|
| paraphrase-multilingual-MiniLM-L12-v2 | 470 MB | 80% (+fuzzy 84%) | 82-88% | ranking discreto, punteggi alti anche per frasi fuori tema ("muletto" 0,67) |
| paraphrase-multilingual-mpnet-base-v2 | 1,1 GB | 77% (+fuzzy 81%) | 83-86% | peggiore del previsto sul primo risultato |
| intfloat/multilingual-e5-base | 1,1 GB | 82% | 87-89% | **ranking migliore** (100% tra i primi 5), ma punteggi compressi 0,79-0,95: nessuna soglia assoluta separa le frasi fuori tema |
| **nickprock/sentence-bert-base-italian-xxl-uncased** | 440 MB | **90% (+fuzzy 91%)** | 91-92% | **unico con il 100% di frasi fuori tema respinte** a soglia assoluta; licenza MIT |

**Scelto il modello italiano con il fuzzy.** Separa meglio, è leggero (55-60 ms a richiesta su CPU) e permette una soglia assoluta. È addestrato solo sull'italiano, e questo è un limite (sezione 10).

**Criteri relativi scartati.** Guadagnano solo un punto e dipendono da quali e quante righe ci sono nel contesto: aggiungere diagnosi cambierebbe l'esito per le stesse frasi.

### Soglie finali (output di `scripts/evaluate_matching.py`)

Modello italiano con fuzzy, soglia per soglia:

| soglia | trovata tra le prime 5 | trovata per prima | fuori tema senza ipotesi | negazione |
|---|---|---|---|---|
| 0,45 | 48/48 | 41/48 | 0/9 | 3/3 |
| **0,50** | **47/48** | **40/48** | 3/9 | 3/3 |
| 0,55 | 44/48 | 40/48 | 5/9 | 3/3 |
| 0,60 | 40/48 | 36/48 | 8/9 | 3/3 |
| **0,65** | 39/48 | 35/48 | **9/9** | 3/3 |
| 0,70 | 31/48 | 27/48 | 9/9 | 3/3 |

Una soglia sola avrebbe obbligato a scegliere tra perdere diagnosi giuste (0,65) e mostrare ipotesi per frasi fuori tema (0,50). Da qui le **tre fasce**:

- sotto **0,50** (`SEMANTIC_RECALL_THRESHOLD`) → nessun dato;
- tra 0,50 e **0,65** (`SEMANTIC_MATCH_THRESHOLD`) → ipotesi **incerte**, con avviso e domanda di scelta;
- da 0,65 → ipotesi.

| Frasi | sicure | incerte | nessun dato |
|---|---|---|---|
| da trovare (48) | 39 | 8 | 1 |
| fuori tema (9) | **0** | 6 | 3 |

Nessuna frase fuori tema viene mai presentata come sicura. Quelle che finiscono tra le incerte hanno anche quasi tutta la probabilità assegnata a "nessuna di queste" (sezione 5).

### Fuzzy insieme agli embedding

Punteggio = massimo tra similarità del coseno e `token_sort_ratio / 100`. Gli embedding reggono male i refusi ("nastor trasportatre"), il fuzzy li regge bene. Con il modello scelto il fuzzy porta "trovata tra le prime 5" da 46 a 47 su 48 a parità di soglia, senza peggiorare le frasi fuori tema nella fascia sicura.

### Regola sulla negazione

Gli embedding danno quasi lo stesso vettore a "la pinza chiude completamente" e "la pinza non chiude completamente". `negation_guard.contradicts` scarta un candidato **solo se** una sola delle due frasi contiene una negazione (`non`, `mai`, `nessun*`, `niente`, `nulla`) e, tolte le negazioni, le frasi sono quasi identiche (`token_sort_ratio ≥ 85`).

*Scartata la versione larga* ("una frase ha 'non' e l'altra no"): avrebbe eliminato parafrasi corrette come "la pinza chiude male" → "la pinza non chiude completamente". "senza" è escluso di proposito: descrive più spesso una condizione ("anche senza pezzo") che una negazione.

## 5. Conversazione, probabilità e domande

### Conversazione stateless

A ogni turno il client invia contesto, tutti i messaggi e gli id esclusi. Il server non salva nulla.

- *Scartato per ora: conversazioni salvate su DB.* Servirebbero per registro e feedback, ma aggiungono tabelle, identificativi e pulizia delle sessioni scadute.
- **Scegliere un'opzione = escludere gli id delle altre opzioni.** Nel piano c'era un `selected_diagnostic_id`, sostituito perché non reggeva più turni di scelta di fila: con le sole esclusioni il server ricostruisce sempre lo stesso stato dagli stessi dati.
- **Più messaggi dell'operatore**: si tiene il punteggio migliore per diagnosi. Le risposte successive ("sì", "dopo il cambio formato") da sole non corrispondono a nulla, e ricalcolare solo sull'ultimo messaggio farebbe perdere la descrizione iniziale.

### Probabilità con la quota "nessuna di queste"

Il punteggio del coseno non è una probabilità: 0,62 non vuol dire 62%, e 0,61 contro 0,59 non dice all'operatore da quale ipotesi partire. Una **softmax** trasforma i punteggi in quote che sommano a 100.

**Primo tentativo (poi corretto):** softmax sulle sole ipotesi. Nello smoke test "il muletto ha una ruota bucata" usciva con **una sola ipotesi al 100%**: formalmente corretto, perché era l'unica, ma letto da un operatore significa certezza.

**Soluzione:** "nessuna di queste" partecipa alla softmax come un candidato in più con punteggio fisso (`PROBABILITY_UNKNOWN_SCORE`). Un'ipotesi molto sopra quel valore gli lascia quasi nulla, una debole gli lascia quasi tutto.

Calibrazione con la NLL media della risposta giusta (per le frasi da trovare le ipotesi attese, per quelle fuori tema "nessuna di queste"):

| T | senza quota | nessuna = 0,55 | **nessuna = 0,60** | nessuna = 0,65 |
|---|---|---|---|---|
| 0,02 | 2,531 | 0,418 | 0,453 | 0,762 |
| **0,03** | 2,531 | **0,385** | **0,403** | 0,603 |
| 0,05 | 2,567 | 0,415 | 0,436 | 0,555 |

Scelti **T = 0,03** e **0,60**, anche se 0,55 ha una NLL leggermente migliore. Con 0,55 le frasi fuori tema lasciavano a "nessuna" spesso meno del 30%, cioè il problema del muletto restava. Con 0,60 le ipotesi giuste nella fascia sicura tengono in media l'89%, e sulle frasi fuori tema "nessuna" va dal 32% al 90%.

Le percentuali intere sommano sempre esattamente a 100 grazie al metodo dei resti maggiori. L'interfaccia mostra "<1%" invece di "0%".

### Domanda di scelta deterministica

`disambiguation_service.build_choice` confronta le ipotesi "in gara", cioè entro `DISAMBIGUATION_SCORE_GAP` dalla migliore, oppure tutte se la confidenza è bassa:

- sintomi diversi → un'opzione per sintomo;
- stesso sintomo, componenti diversi (il fermo cella) → un'opzione per componente;
- stesso sintomo e stesso componente (cause alternative dello stesso guasto) → nessuna domanda: l'operatore non può distinguerle, le verifica in ordine di probabilità.

Distacco tra le prime due ipotesi con sintomi diversi, sulle frasi della fixture:

- prima ipotesi **sbagliata**: 0,003 · 0,008 · 0,009 · 0,043 · 0,047 · 0,193
- prima ipotesi **giusta**: da 0,021 in su; 4 casi su 30 sotto 0,05

**Gap = 0,05**: la domanda compare in 5 dei 6 casi in cui servirebbe, e inutilmente in 4 casi su 30.

*Superata la "v2 — domanda di disambiguazione" pianificata in v1* (tabelle `disambiguation_questions/options` scritte dall'esperto). Le opzioni costruite dai dati coprono lo stesso bisogno senza lavoro di mappatura. Le tabelle restano un'idea per le domande che i dati non possono esprimere (vedi migliorie).

## 6. Assistente LLM facoltativo

- **Stessa interfaccia `AIProvider` della v1**, con un nuovo metodo `complete_json`. Si cambia provider con `AI_PROVIDER`, come prima. Il `NoopAIProvider` è rimasto come *null object* (`enabled = False`), così il resto del codice riceve sempre un `AIProvider` e non deve controllare `None`.
- **Il modello riceve** le ipotesi già trovate (id, sintomo, componente, fase, causa, soluzione) e la conversazione, **in un unico documento JSON nel messaggio utente**. Il testo dell'operatore resta dato e non si mescola alle istruzioni del prompt di sistema: è una mitigazione, non una garanzia, contro frasi come "ignora le istruzioni".
- **Tre azioni ammesse**: `ask`, `narrow`, `no_match`. `parse_decision` rifiuta id non candidati, id booleani (`true` in Python è un `int`), domande vuote, troppo lunghe o oltre `MAX_LLM_QUESTIONS`, azioni sconosciute.
- **JSON mode**: `response_format: json_object` (OpenAI), `format: json` (Ollama), temperatura 0.
- **Il modello decide quali ipotesi restano, non l'ordine né le percentuali**: così i numeri restano confrontabili con la modalità offline.
- **Fallback**: errore HTTP, timeout (`AI_TIMEOUT_SECONDS`), JSON non valido o decisione rifiutata → risposta deterministica con `ai_fallback: true`, motivo nel log.
- **Non chiamato** se non ci sono candidati: nessun costo e nessun dato inviato per una frase fuori tema.
- *Scartata la riscrittura del sintomo della v1* (`normalize_symptom`): la ricerca semantica ne ha preso il posto, e un modello che riscrive il testo può trasformarlo in un sintomo sbagliato.

## 7. Interfaccia esperto e CSV

### Interfaccia

- Pagina `/knowledge-base` visibile solo agli `expert`. Nasconderla è una comodità: il controllo vero resta sul backend, testato su ogni endpoint.
- I componenti non chiamano mai le API: la pagina passa le callback (`services → components → pages`).
- Ricerca con attesa di 300 ms dopo l'ultimo tasto, per non inviare una richiesta per lettera.
- `ContextSelector` con etichette configurabili, riusato in chat, nei filtri e nel form invece di tre select duplicate.
- Eliminazione con `window.confirm`: per un PoC basta, una finestra personalizzata aggiungerebbe un componente senza nuovo comportamento.
- `utils/saveFile.js` è la prima cartella `utils/` del frontend: far salvare un file al browser non è né un componente né un servizio.

### Formato CSV

- **Separatore `;` e UTF-8 con BOM in export**: senza BOM Excel mostra le lettere accentate come caratteri illeggibili, e con le impostazioni italiane usa `;`.
- **Import tollerante**: `;` o `,` riconosciuti dall'intestazione, UTF-8 con o senza BOM, ripiego su Windows-1252 (il "CSV" normale di Excel per Windows).
- **Famiglia per nome, fase per numero**: leggibili in Excel. `phase_name` è esportata ma ignorata in import: due colonne per la stessa informazione potrebbero contraddirsi.
- **Nomi di famiglia confrontati senza distinguere maiuscole e minuscole**, coerenti con la collation `utf8mb4_unicode_ci` che rende unico il nome.
- **Protezione CSV injection**: le celle che iniziano con `= + - @` sono esportate con un apostrofo, che l'import toglie. Un ciclo export → Excel → import non altera i dati (testato).

### Regole di import

- **Upsert per `id`**: `id` vuoto crea, `id` esistente aggiorna, `id` inesistente è un errore. *Scartato* creare silenziosamente l'id: un numero sbagliato produrrebbe duplicati invisibili.
- **Nessuna cancellazione da CSV**: una riga dimenticata nel file non deve eliminare una diagnosi.
- **Anteprima di default** (`dry_run=true`): conta le righe da aggiungere, da modificare e **invariate** (confrontando i valori reali, così un export reimportato dà 0 modifiche).
- **Tutto o niente**: con un errore, `400` con il report e nessuna scrittura. Le scritture usano la transazione della richiesta, quindi un errore a metà annulla anche le righe già scritte.
- **Errori in italiano con riga e colonna** (compresa la riga di inizio quando una cella va a capo): li legge direttamente l'esperto. La famiglia sbagliata elenca le famiglie valide.
- Limiti: 2 MB e 5000 righe.
- *Scartato: "sostituisci tutto".* Comodo al primo caricamento, ma un file sbagliato cancellerebbe la knowledge base.

## 8. Test

- **338 test, copertura 99%.** La riga non coperta è la creazione del modello vero dentro `create_app()`, che i test sostituiscono.
- **Embedder finto (bag of words con hashing)** nell'app di test: la suite non carica il modello e dura circa 30 secondi. I punteggi dipendono solo dalle parole in comune, quindi i casi del seed sono stabili. Prima di scrivere i test di conversazione ho misurato i punteggi reali dell'embedder finto sul seed, per scrivere le aspettative consapevolmente e non adattarle ai risultati.
- **Test `model`** (`tests/test_model_quality.py`): modello vero sulla fixture, con minimi poco sotto i valori misurati (trovate ≥ 46/48, prime ≥ 38/48, nessuna frase fuori tema sicura, negazioni 3/3). Un cambio di modello o di soglia che peggiora il matching fa fallire la suite.
- **Il fixture `settings` fissa le soglie calibrate**, così una taratura locale del `.env` non cambia l'esito dei test.
- **Il passo LLM** è testato con provider sostitutivi e con `httpx.MockTransport`, per i casi: domanda, restringimento, `no_match`, id inventato, provider giù, limite di domande, nessuna chiamata senza candidati.
- **RBAC**: un operatore riceve 403 su creazione, modifica, eliminazione, import, export e modello, e il contenuto della tabella non cambia.
- **Smoke test HTTP** sul backend reale (DB di test, modello vero): fermo cella, esclusione, negazione, frase fuori tema, export, modello, anteprima, import, file con errori, 403, diagnosi importata ritrovata con una parafrasi. Tempi di risposta 90-150 ms.

## 9. Tentativi che non hanno funzionato (v2)

| Tentativo | Cosa è successo | Come è stato risolto |
|---|---|---|
| Installazione di torch in background con percorsi relativi | la shell non trovava `.venv/bin/pip`, ma l'esito era 0 perché l'ultimo comando della pipe era `tail` | percorsi assoluti e `set -o pipefail` |
| MiniLM, mpnet ed e5 con soglia assoluta | nessuna soglia separava le frasi fuori tema da quelle giuste (sezione 4) | modello italiano |
| Soglia relativa (primo punteggio meno media o mediana) | +1 punto, ma dipende dalla composizione della knowledge base | scartata, soglia assoluta a due livelli |
| Regola larga sulla negazione | avrebbe scartato parafrasi corrette | scarto solo se le frasi, senza negazioni, sono quasi identiche |
| Domanda di scelta basata sul primo sintomo diverso | con tre cause dello stesso fermo cella e un sintomo più lontano in fondo, raggruppava per sintomo e non chiedeva nulla, proprio nel caso di `update.md` | domanda solo sulle ipotesi "in gara", raggruppate per sintomo o componente |
| Softmax sulle sole ipotesi | un'ipotesi incerta e unica appariva al 100% (smoke test) | quota "nessuna di queste" calibrata |
| `selected_diagnostic_id` nella richiesta (piano) | non reggeva più turni di scelta senza stato sul server | solo `excluded_diagnostic_ids` |
| `caplog` nel test del warm-up senza database | nessun messaggio catturato: `dictConfig` in `create_app()` rimuove l'handler di pytest dal logger root | handler riaggiunto nel test |
| Cancellazione dei file v1 non più usati (piano) | il vincolo di progetto vieta di cancellare file senza permesso esplicito | file riusati: `diagnosis_service.py` contiene la conversazione, `fuzzy_matcher.py` è la baseline v1 dello script, `NoopAIProvider` è un null object |

## 10. Limiti conosciuti

### Matching e probabilità

1. **Calibrato su 60 frasi sintetiche** scritte durante lo sviluppo, non su richieste reali di operatori. Soglie, temperatura e quota "nessuna" vanno ricalibrate con dati veri: aggiungere frasi alla fixture e rilanciare lo script.
2. **Modello solo italiano**, mantenuto da un singolo autore (MIT, circa 2.300 download). In un reparto multilingue servirebbe e5 (ranking migliore, ma senza soglia assoluta affidabile) o un altro modello da calibrare.
3. **Il lessico di reparto** (sigle, nomi interni di macchine) non è noto al modello: i sinonimi aziendali possono non essere riconosciuti.
4. **Negazione**: la regola copre solo frasi quasi identiche. Una negazione espressa con parole diverse può ancora avvicinare il sintomo opposto.
5. **Frasi fuori tema nella fascia incerta**: 6 su 9 mostrano ipotesi, con avviso e quota "nessuna" alta. Non vengono mai presentate come sicure, ma compaiono.
6. **Probabilità stimate**: la quota "nessuna" è una stima calibrata, non la frequenza reale delle cause mancanti.
7. **Tutti i candidati del contesto** vengono letti e confrontati a ogni richiesta, e la cache non libera mai i testi modificati. Va bene fino a qualche migliaio di righe.
8. **Download del modello** da Hugging Face al primo avvio: serve internet una volta, oppure copiare la cache su una macchina offline.

### Assistente AI

9. **Mai provato con OpenAI reale**: prompt e qualità delle domande sono da validare. Costi a consumo.
10. **`AI_PROVIDER=api` invia fuori dalla rete aziendale** conversazione, cause e soluzioni candidate.
11. **Ollama su CPU** è lento (secondi per risposta) e un modello piccolo segue le istruzioni peggio. Il fallback evita il blocco, ma la conversazione AI diventa di fatto offline.

### Gestione e sicurezza

12. **Conversazione non salvata**: nessun registro e nessun feedback ("la soluzione ha funzionato?"). Non si possono misurare MTTD/MTTR né trovare i sintomi scoperti.
13. **Famiglie, fasi e utenti** non si gestiscono dall'interfaccia (SQL o Swagger). Eliminare una famiglia usata è bloccato dalle FK.
14. **Nessuna cronologia delle modifiche** alla knowledge base: una diagnosi modificata o eliminata non si recupera.
15. **Token non revocabile** prima della scadenza, **token in `sessionStorage`** leggibile da JavaScript, **nessun rate limiting** sul login, **credenziali demo** nel seed (invariati dalla v1).
16. **Messaggi di errore del backend in inglese**, tranne l'import CSV.
17. **Nessun test automatico del frontend**: build, lint e prove manuali.
18. **`requirements.txt` fissa `torch==2.14.0+cpu`**, che richiede l'installazione preventiva dall'indice CPU.
19. Warning di deprecazione `httpx2` di Starlette nei test; file del template Vite non tracciati e favicon di Vite ancora presenti.

## 11. Migliorie possibili

- **Registro delle conversazioni e feedback**, per calibrare le soglie sulle frasi reali e trovare i sintomi senza copertura.
- **Dizionario di sinonimi di reparto** scritto dagli esperti, applicato prima dell'embedding (deterministico).
- **Domande scritte dall'esperto** per i casi che le opzioni automatiche non esprimono (per esempio "si sente un rumore?").
- **Fine-tuning del modello** su coppie (frase dell'operatore, sintomo) raccolte dal registro.
- **Gestione di famiglie, fasi e utenti** dall'interfaccia, e **cronologia delle modifiche**.
- **Pre-filtro** (per esempio indice vettoriale o FULLTEXT) quando la knowledge base supererà qualche migliaio di righe.
- **Test del frontend** (Vitest + React Testing Library) e **CI** con GitHub Actions.
- **Rate limiting, HTTPS e cookie `HttpOnly`** prima di un uso fuori dalla rete locale.

---

# Parte 2 — v1

Stato al 14/09/2026: PoC v1 completo (matching fuzzy deterministico, eccezioni per fase, AI facoltativa di sola riscrittura del sintomo). Qui restano le decisioni **ancora valide** e la storia di quelle superate.

## Vincoli del brief (validi in v2)

| Vincolo | Come è rispettato |
|---|---|
| **Offline-first** | embedding in locale; AI spenta di default; `api` documentata come adatta solo alla validazione |
| **Determinismo prima dell'NLP** | candidati, ordine, probabilità e domande offline sono deterministici; l'LLM non scrive mai cause o soluzioni |
| **RBAC** `expert` / `operator` | ruolo riletto dal DB a ogni richiesta, test su ogni endpoint di scrittura |
| **Fallback anti-allucinazione** | tre fasce con avviso, quota "nessuna di queste", `no_match` con messaggio fisso |
| **Provider AI intercambiabile** | interfaccia `AIProvider` e factory, una variabile in `.env` |

## Decisioni v1 ancora valide

**Accesso al database: SQLAlchemy Core** con `text()` e parametri.
- *Scartato ORM*: seconda definizione dello schema da tenere allineata con `schema.sql`. *Scartato solo PyMySQL*: connessioni e transazioni a mano.
- `pool_pre_ping` + `pool_recycle=3600`: MySQL chiude le connessioni inattive dopo 8 ore.
- Una transazione per richiesta (`get_connection`).
- `rowcount` degli update conta le righe *trovate* (flag del dialetto PyMySQL), non quelle *modificate*.
- Pacchetto `cryptography` necessario per `caching_sha2_password` di MySQL 8.

**Normalizzazione del testo** (`normalize_text_ita`, copiata da `function_archive`): minuscolo, accenti rimossi con NFKD, punteggiatura in spazi, stopword italiane rimosse, **"non" conservato**. In v2 serve al punteggio fuzzy e alla regola sulla negazione.

**Scorer fuzzy `token_sort_ratio`** (misurato in v1 contro `token_set_ratio`, `ratio`, `WRatio`): `token_set_ratio` e `WRatio` davano punteggi alti con una parola sola o con un sintomo diverso sullo stesso componente; `ratio` non reggeva le parole in ordine diverso. In v2 resta come componente del punteggio e come baseline dello script.

**Autenticazione:**
- JWT Bearer invece delle sessioni lato server (supporto nativo FastAPI e Swagger, nessuno store di sessione). *Scartati i cookie di sessione*: revoca più semplice, ma serve uno store e CORS più delicato.
- Ruolo **riletto dal database a ogni richiesta**: un declassamento vale subito.
- bcrypt con limite di 72 byte gestito esplicitamente (niente `500`).
- Utente inesistente e password sbagliata: stesso `400`, stesso messaggio, bcrypt eseguito comunque (niente user enumeration né timing attack).
- Algoritmo di firma fisso nel codice.

**API:**
- `422` → `400` con un handler, per coerenza con la convenzione del progetto.
- Route `def`, non `async def`: SQLAlchemy qui è sincrono.
- Oggetti di avvio su `app.state` dentro `create_app()`, nessuna inizializzazione pesante all'import. In v2 anche il modello di embedding, caricato **dopo** il controllo della configurazione AI, così un errore di configurazione si vede subito.
- `run.py` con `uvicorn.run("app.main:create_app", factory=True)`.
- Login con form OAuth2, per il pulsante *Authorize* di Swagger.

**Test:** MySQL reale e separato (`dedalo_test`, *scartato SQLite*: non supporta allo stesso modo FK composite, `CHECK`, `ENUM`); rifiuto di partire se `DB_TEST_NAME == DB_NAME`; transazione annullata per test; mock solo ai confini (HTTP dei provider).

**Frontend:** React + Vite in JavaScript; token in `sessionStorage` (terminali condivisi); pulsanti e campi alti almeno 44 px (tablet); testi in italiano, codice in inglese.

## Decisioni v1 superate in v2

| v1 | v2 | Perché |
|---|---|---|
| fuzzy rapidfuzz come motore, soglia 80 | embedding italiano + fuzzy, soglie 0,50 / 0,65 | 3/48 contro 47/48 sulle frasi da operatore |
| `base_diagnostics` + `diagnostic_exceptions` | `diagnostics` con famiglia e fase facoltative | un concetto in meno, CSV 1:1 con Excel, fasi facoltative |
| famiglia e fase obbligatorie | fase facoltativa | il fermo cella non dice in quale fase sta il guasto |
| indice FULLTEXT pronto come pre-filtro | rimosso | mai usato; la ricerca semantica ne prende il posto |
| lista di ipotesi con "somiglianza %" | ipotesi con probabilità stimata e quota "nessuna" | il punteggio non è una probabilità |
| AI che riscrive il sintomo se non c'è match | AI facoltativa che fa domande e restringe | una riscrittura può produrre un sintomo sbagliato |
| v2 pianificata: domande scritte dall'esperto in tabelle | opzioni costruite dai dati | nessun lavoro di mappatura, stesso bisogno coperto |
| knowledge base gestita da Swagger | interfaccia esperto + CSV | richiesta di `update.md` |

## Tentativi che non hanno funzionato (v1)

| Tentativo | Cosa è successo | Come è stato risolto |
|---|---|---|
| `token_set_ratio` come scorer | 81,6 per un sintomo diverso sullo stesso componente, 100 per una parola sola | `token_sort_ratio` |
| FULLTEXT di MySQL come motore | 0 risultati con un refuso | rapidfuzz (oggi embedding + fuzzy) |
| Creazione del venv su Ubuntu | `ensurepip is not available` | `python3.12-venv` |
| Installazione di MariaDB | non necessaria | MySQL 8 già attivo |
| Node.js dai pacchetti di Ubuntu | versione 18, troppo vecchia per Vite | Node 24 LTS con nvm |
| `python -c "..."` con virgolette annidate | errori della shell | heredoc (`python - <<'EOF'`) |
