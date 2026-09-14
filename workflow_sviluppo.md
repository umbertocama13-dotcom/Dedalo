# Dedalo — Workflow di sviluppo

Questo documento raccoglie **perché** il PoC è fatto così: le decisioni di design, le alternative scartate, i tentativi che non hanno funzionato, i limiti conosciuti e i prossimi passi.

Per installazione, avvio e uso vedi il [README.md](README.md).

Stato al 14/09/2026: PoC v1 completo. Backend testato (copertura ~99%), frontend verificato con build, lint e prove manuali.

---

## Indice

1. [Obiettivo e vincoli del brief](#1-obiettivo-e-vincoli-del-brief)
2. [Architettura](#2-architettura)
3. [Ordine di sviluppo](#3-ordine-di-sviluppo)
4. [Decisioni di design e alternative scartate](#4-decisioni-di-design-e-alternative-scartate)
5. [Tentativi che non hanno funzionato](#5-tentativi-che-non-hanno-funzionato)
6. [Limiti conosciuti](#limiti-conosciuti)
7. [Prossimi passi pianificati](#prossimi-passi-pianificati)
8. [Migliorie possibili (non pianificate)](#migliorie-possibili-non-pianificate)

---

## 1. Obiettivo e vincoli del brief

Dedalo aiuta operatori e manutentori a diagnosticare guasti partendo dalla conoscenza reale della fabbrica, contestualizzata per **famiglia di prodotto** e **fase del ciclo**. L'obiettivo è ridurre i tempi di diagnosi e riparazione (MTTD/MTTR) e la dipendenza dai tecnici specializzati.

Vincoli che hanno guidato ogni scelta:

| Vincolo | Come è stato rispettato |
|---|---|
| **Offline-first**: niente dipendenze da servizi cloud | tutto gira in locale; l'AI è spenta di default e l'unico backend esterno (`api`) è opzionale e documentato come adatto solo alla validazione |
| **Determinismo prima dell'NLP** | matching a regole con rapidfuzz; l'AI non produce mai una diagnosi |
| **RBAC** `expert` / `operator` | controllo del ruolo sul server a ogni richiesta, con test su ogni endpoint di scrittura |
| **Fallback anti-allucinazione** | sotto la soglia di somiglianza la risposta è `no_match` con un messaggio fisso |
| **Provider AI intercambiabile** con una sola variabile in `.env` | interfaccia `AIProvider` più factory; il resto dell'app non conosce l'implementazione concreta |

## 2. Architettura

```
Browser (React)
   │  fetch + Bearer token
   ▼
routes/          ← riceve e valida la richiesta, controlla il ruolo (dependencies.py)
   │
services/        ← logica di business
   │   ├── matching/     motore deterministico (funzione pura, senza database)
   │   └── ai/           AIProvider: none | api | local
   ▼
repositories/    ← SQL esplicito (SQLAlchemy Core)
   │
MySQL
```

La dipendenza va sempre in un solo verso, dall'alto verso il basso: una route non chiama mai un repository direttamente, e un service non sa nulla di HTTP, tranne sollevare `HTTPException`.

### Flusso di una richiesta di diagnosi

1. `POST /diagnosis` riceve sintomo, famiglia e fase. Pydantic li valida: toglie gli spazi, rifiuta i testi vuoti o più lunghi di 500 caratteri e gli ID non positivi.
2. `get_current_user` verifica il token e **rilegge il ruolo dal database**.
3. `catalog_service.validate_family_phase` verifica il contesto: famiglia o fase inesistente → `404`, fase di un'altra famiglia → `400`.
4. `diagnostics_repository.list_match_candidates` carica **tutte** le diagnosi generiche, ciascuna con l'eventuale eccezione per quella famiglia e quella fase, in un'unica query con `LEFT JOIN`.
5. `FuzzyMatcher` confronta il testo dell'operatore con ogni sintomo e tiene quelli con punteggio ≥ soglia. Dove c'è un'eccezione, sostituisce causa e soluzione generiche con quelle specifiche.
6. Se il testo originale non trova nulla, l'`AIProvider` riscrive il sintomo e il matching viene ripetuto sul testo riscritto. Con `none` il testo resta identico e il secondo tentativo non parte.
7. La risposta ha `status: "match"`, con le ipotesi ordinate, oppure `status: "no_match"`, con il messaggio fisso.

## 3. Ordine di sviluppo

Bottom-up, dal livello più isolato a quello più assemblato, con una branch `feature/*` per ogni step.

| Step | Contenuto | Branch |
|---|---|---|
| 0 | `.gitignore` (`.env`, `node_modules/`), venv, `.env.example` | `feature/project-setup` |
| 1 | `schema.sql`, `seed.sql` | `feature/database` |
| 2 | config, engine del database, logging | `feature/backend-core` |
| 3 | repository | `feature/repositories` |
| 4 | motore di matching (TDD) | `feature/matching-engine` |
| 5 | hashing delle password, JWT, `auth_service` (TDD); spostamento del normalizzatore in `utils/` | `feature/auth` |
| 6 | `AIProvider` e i backend `none`/`api`/`local` (TDD) | `feature/ai-provider` |
| 7 | schemas, `catalog_service`, `diagnosis_service`, `knowledge_base_service` (TDD) | `feature/services` |
| 8 | route, dipendenze, `create_app()`, `run.py` | `feature/api-routes` |
| 9 | test delle API e dei permessi | `feature/api-tests` |
| 10 | frontend React | `feature/frontend` |
| 11 | documentazione | `feature/docs` |

Il TDD è stato usato dove il comportamento era ben definito: matching, autenticazione, provider AI e service. Per ognuno i test sono stati visti fallire prima di scrivere il codice. Le route (step 8) sono state verificate prima a mano con `curl` e poi coperte dai test dello step 9.

## 4. Decisioni di design e alternative scartate

### 4.1 Database

**MySQL 8 invece di MariaDB.** Il brief ammette entrambi. MySQL 8 era già installato e attivo, e supporta tutto quello che serve: FK composite, FULLTEXT su InnoDB, `ENUM`. Installare MariaDB non avrebbe portato vantaggi.

**Coerenza famiglia ↔ fase con una FK composita invece di un trigger.**
`cycle_phases` ha `UNIQUE (id, family_id)`, e `diagnostic_exceptions` ha `FOREIGN KEY (cycle_phase_id, family_id) REFERENCES cycle_phases (id, family_id)`. Il database rifiuta così un'eccezione che associa una fase a una famiglia a cui non appartiene.
- *Scartato: trigger `BEFORE INSERT/UPDATE` con `SIGNAL`.* Funzionerebbe, ma è logica nascosta, più difficile da leggere e da testare, e va scritta due volte (insert e update). La FK composita è dichiarativa e si vede con `SHOW CREATE TABLE`.
- Il vincolo `UNIQUE (id, family_id)` sembra ridondante, perché `id` è già unico. Serve solo come destinazione della FK composita, ed è commentato nello schema.

**Altri vincoli:**
- `UNIQUE (family_id, phase_number)`: nessuna famiglia ha due "fase 3".
- `UNIQUE (base_diagnostic_id, cycle_phase_id)`: al massimo un'eccezione per diagnosi in ogni fase. Garantisce anche che il `LEFT JOIN` del matching non duplichi le righe.
- Nessun `UNIQUE` su `symptom_description`: lo stesso sintomo può avere più cause alternative, come richiesto dal brief.
- `ON DELETE CASCADE` solo da `base_diagnostics` verso le sue eccezioni, perché un'eccezione non ha senso senza la diagnosi. Tutte le altre FK sono `RESTRICT`: non si cancella per sbaglio una famiglia o un utente che ha scritto dati.

**Le eccezioni sostituiscono sempre sia la causa sia la soluzione** (`NOT NULL`).
- *Alternativa:* colonne nullable, con ripiego sul valore generico. Più flessibile, ma aggiunge casi al motore. Si può introdurre in seguito rendendo le colonne `NULL`, senza cambiare la struttura delle tabelle.

**L'indice FULLTEXT c'è ma non viene usato.** Il brief lo richiede, ed è pronto come pre-filtro per quando la knowledge base sarà grande (vedi 4.3 e i limiti).

**Seed con ID espliciti**, così i test possono riferirsi a righe precise.

### 4.2 Accesso al database

**SQLAlchemy Core** con query `text()` e parametri `:nome`.
- *Scartato: SQLAlchemy ORM.* Avrebbe creato una seconda definizione dello schema (classi Python) da tenere allineata a mano con `schema.sql`.
- *Scartato: solo PyMySQL.* Connessioni, pool e transazioni andrebbero gestiti a mano, con molto codice ripetuto.

Dettagli non ovvi:
- **`pool_pre_ping` + `pool_recycle=3600`**: MySQL chiude le connessioni inattive dopo `wait_timeout` (8 ore). Senza queste opzioni, la prima richiesta dopo una notte fallirebbe.
- **Una transazione per richiesta** (`get_connection`): commit se tutto va bene, rollback se c'è un errore.
- **`rowcount` degli update**: MySQL conta di default le righe *modificate*, quindi un update con valori identici darebbe 0 e sembrerebbe un 404. Il dialetto PyMySQL di SQLAlchemy attiva invece il conteggio delle righe *trovate*. È stato verificato.
- **Pacchetto `cryptography`**: MySQL 8 usa l'autenticazione `caching_sha2_password`, e senza questo pacchetto PyMySQL può fallire il login in modo intermittente.

### 4.3 Motore di matching

**rapidfuzz in Python invece del FULLTEXT di MySQL come motore.**
Misurato sui dati del seed: la ricerca FULLTEXT `nastro trasportatore` trova 2 righe, mentre `nastor trasportatre` (con refusi) ne trova **0**. Il FULLTEXT lavora a parole intere, ha stopword inglesi e ignora le parole sotto i 3 caratteri. Scrivere il matcher come funzione pura (candidati in ingresso, risultati in uscita) permette anche di testarlo senza database.

**Normalizzazione (`normalize_text_ita`):**
1. tutto in minuscolo;
2. accenti rimossi con la scomposizione Unicode NFKD;
3. punteggiatura e simboli sostituiti da spazi;
4. stopword italiane rimosse.

**"non" non è una stopword**, perché inverte il senso del sintomo. Vedi però il limite sulla negazione.

**Scorer: `token_sort_ratio`, soglia 80.** Il piano iniziale prevedeva `token_set_ratio`. Prima di scrivere i test sono stati misurati quattro scorer sulle frasi del seed già normalizzate:

| Caso | `token_set_ratio` | `token_sort_ratio` | `ratio` | `WRatio` |
|---|---|---|---|---|
| OK: testo esatto | 100 | 100 | 100 | 100 |
| OK: refusi | 97.4 | 97.4 | 97.4 | 97.4 |
| OK: parole in ordine diverso | 100 | 100 | **50** | 95 |
| OK: frase più lunga ("linea 3") | 100 | 90.9 | 90.9 | 95 |
| OK?: descrizione parziale ("pinza non chiude") | 100 | **61.5** | 61.5 | 85.5 |
| NO: stesso componente, sintomo diverso ("nastro trasportatore rumoroso") | **81.6** | 58 | 69.6 | 77.6 |
| NO: una parola sola ("nastro") | **100** | 26.1 | 26.1 | **90** |
| NO: "film strappato" contro "saldatura film irregolare grinze" | 44.4 | 39.1 | 30.4 | **85.5** |
| NO: sintomo non correlato | 40.7 | 40.7 | 37 | 51.4 |

- `token_set_ratio` è stato **scartato**: dà un punteggio alto quando le parole della richiesta sono un sottoinsieme di quelle del sintomo, e quindi produrrebbe diagnosi sbagliate con una parola sola o con un sintomo diverso sullo stesso componente.
- `WRatio` è stato scartato per lo stesso motivo; `ratio` perché non regge le parole in ordine diverso.
- `token_sort_ratio` separa bene i casi: tutti quelli corretti stanno a 90.9 o più, tutti quelli sbagliati a 58 o meno. Il prezzo è che una descrizione molto parziale non trova nulla. È una scelta voluta: per il brief "nessun dato" è sempre meglio di una diagnosi sbagliata.

**Ordinamento stabile:** per punteggio decrescente, poi per ID della diagnosi, così a parità di input l'ordine è sempre lo stesso.

**Interfaccia `Matcher`**: `diagnosis_service` dipende dall'interfaccia, non da `FuzzyMatcher`. Un futuro `SemanticMatcher` (ad esempio con sentence-transformers in locale) si aggiunge senza toccare route e repository.

**Carico di tutte le diagnosi a ogni richiesta.** Con centinaia o poche migliaia di righe è istantaneo e semplice. Per volumi maggiori vedi i limiti.

### 4.4 Fallback anti-allucinazione

- `no_match` è una risposta **`200`**, non un errore: è un esito previsto.
- Il messaggio è fisso nel backend e il frontend mostra un riquadro dedicato. Nessun testo viene generato.
- Il frontend (`DiagnosisResult`) sceglie cosa mostrare in base a `status`. Uno stato sconosciuto **non viene mai mostrato come diagnosi**: compare "Risposta non riconosciuta".

### 4.5 Provider AI

**Spento di default** (`AI_PROVIDER=none`): il PoC funziona e si testa senza costi e senza far uscire dati dalla macchina.

**L'AI interviene solo se il testo originale non trova nulla.**
- *Scartato: passare sempre dall'AI prima del matching.* Una riscrittura del modello potrebbe trasformare un sintomo che il matching avrebbe trovato correttamente in uno sbagliato. Manderebbe inoltre fuori dalla macchina anche testi che non ne avevano bisogno, con costi e latenza per ogni richiesta.
- La risposta indica `matched_on: "original" | "ai_normalized"`. Nel secondo caso il frontend mostra "Sintomo interpretato come: …", così l'operatore vede su quale testo è avvenuto il match.
- Se il provider fallisce, l'errore viene intercettato: avviso nel log e risposta deterministica comunque. Un Ollama spento non blocca la diagnosi.

**Formato OpenAI-compatibile per `ApiAIProvider`.**
- *Scartato: API nativa Anthropic.* È valida se la chiave di test è Anthropic, ma il formato `/v1/chat/completions` è quello accettato anche dai server che un'azienda usa per ospitare modelli in casa (vLLM, LM Studio, Ollama stesso). Lo stesso client può quindi puntare a un server interno cambiando solo `AI_API_URL`.

**httpx diretto, senza SDK dei vendor**: un solo client HTTP per entrambi i backend, nessuna dipendenza da un fornitore specifico.

**Protezioni:**
- temperatura 0, per risposte il più ripetibili possibile;
- prompt che vieta di aggiungere cause, soluzioni o dettagli;
- output scartato se vuoto o più lungo di 500 caratteri (la stessa lunghezza massima del sintomo);
- errori che riportano solo il codice HTTP, mai il corpo della risposta, che potrebbe contenere la chiave (verificato da un test).

**Configurazione controllata all'avvio**: se manca una variabile obbligatoria per il provider scelto, `create_app()` si ferma e indica quale manca.

### 4.6 Autenticazione e permessi

**JWT Bearer invece delle sessioni lato server.** È supportato in modo nativo da FastAPI (`OAuth2PasswordBearer`, pulsante *Authorize* di Swagger), non richiede una tabella o uno store per le sessioni ed è semplice da usare con un frontend su un'altra porta.
- *Scartato: sessioni con cookie.* La revoca immediata è più semplice, ma servono uno store e una gestione CORS/cookie più delicata. Il vantaggio della revoca è in gran parte recuperato dal punto successivo.

**Il ruolo viene riletto dal database a ogni richiesta**, invece di fidarsi di quello scritto nel token. Se un expert viene declassato o un account eliminato, l'effetto è immediato e non alla scadenza del token. È testato in entrambe le direzioni.

**Login:**
- bcrypt con salt casuale: la stessa password produce hash diversi;
- **bcrypt accetta al massimo 72 byte** e la versione 5 dà errore oltre quel limite. Senza un controllo esplicito, una password lunga causerebbe un `500`. Ora la verifica restituisce `False` e la creazione dell'hash dà un errore esplicito;
- username inesistente e password sbagliata danno **lo stesso `400` con lo stesso messaggio**. Nel primo caso bcrypt viene eseguito comunque su un hash fittizio, così il tempo di risposta non rivela quali username esistono;
- l'algoritmo di firma è una lista fissa nel codice e non viene mai letto dall'header del token.

**Codici `401` e `403`**: non sono nella tabella dei codici standard del progetto (200/201/400/404/409/500), ma sono gli unici corretti per "non autenticato" e "ruolo insufficiente". Sono stati aggiunti.

### 4.7 API

- **`422` → `400`**: FastAPI risponde `422` quando l'input non è valido, ma la convenzione del progetto usa `400` per ogni richiesta invalida. Un handler in `create_app()` converte il codice.
- **Regole dei codici**: `404` per una risorsa indicata nell'URL o un riferimento (famiglia/fase) che non esiste; `400` per una combinazione incoerente; `409` per un duplicato. Le regole sono le stesse per diagnosi ed eccezioni.
- **Un'eccezione si raggiunge solo dalla sua diagnosi**: `/diagnostics/4/exceptions/1` risponde `404` se l'eccezione 1 appartiene a un'altra diagnosi.
- **Ogni scrittura gira in un savepoint** (`_guarded_write`). Se il database rifiuta la scrittura, si annulla solo quella e la transazione della richiesta resta utilizzabile. L'errore MySQL 1062 (duplicato) diventa `409`.
- **`catalog_service` aggiunto rispetto al piano**, così anche le route del catalogo passano da un service e non chiamano direttamente un repository.
- **Route `def`, non `async def`**: SQLAlchemy qui è sincrono. Con `def` FastAPI esegue ogni richiesta in un thread separato; con `async def` una query lenta bloccherebbe tutte le altre richieste.
- **Oggetti di avvio su `app.state`** invece che in variabili globali: settings, engine, matcher e provider sono creati dentro `create_app()`. Nessuna inizializzazione pesante all'import, e i test possono creare app isolate.
- **`run.py` con `uvicorn.run("app.main:create_app", factory=True)`**: è uvicorn a chiamare la factory. Host, porta e reload arrivano da `.env`.
- **Login con form OAuth2** invece che con JSON, così il pulsante *Authorize* di Swagger funziona senza configurazioni. Richiede il pacchetto `python-multipart`.

### 4.8 Test

- **pytest su un database MySQL reale e separato** (`dedalo_test`), ricreato da `schema.sql` + `seed.sql` una volta per sessione. Ogni test gira in una transazione annullata alla fine.
  - *Scartato: SQLite per i test.* Non supporta allo stesso modo `ENUM`, FULLTEXT e FK composite, quindi i test non rappresenterebbero il database reale.
- **Protezione**: se `DB_TEST_NAME` coincide con `DB_NAME` i test si rifiutano di partire, perché `schema.sql` cancellerebbe i dati veri.
- **Nessun mock di componenti interni.** Si simulano solo i confini del sistema:
  - l'HTTP dei provider AI, con `httpx.MockTransport` e un client passato al costruttore. Questa è una differenza dal piano, che prevedeva `mocker`: non serve sostituire nessun modulo e nessuna chiamata a pagamento può partire;
  - il modello AI nei test dei service, con piccoli sostituti che implementano `AIProvider`.
- **Test delle API**: l'unica cosa sostituita è `get_connection`, che nei test usa la connessione della transazione annullata. Route, service, SQL e vincoli restano quelli veri. Un test separato usa la `get_connection` reale, in sola lettura.
- **Nei test delle API i token vengono generati direttamente**, perché bcrypt costa circa 0,25 secondi a ogni login. Il login vero ha i suoi test dedicati.
- **I test dei permessi confrontano il contenuto del database** prima e dopo ogni tentativo di scrittura di un operator, per dimostrare che non cambia nulla.
- **Fixture componibili**: `settings → test_engine → db_connection → client`, più gli header dei due ruoli.

### 4.9 Frontend

- **React + Vite in JavaScript** (niente TypeScript per ora), come da standard del progetto. Il template di Vite porta con sé il linter `oxlint`.
- **Struttura bottom-up**: `services/api.js` → componenti → pagine → `App.jsx`. Solo `api.js` conosce il backend.
- **Token in `sessionStorage` invece che in `localStorage`.** Su un terminale condiviso in reparto il token si cancella quando si chiude la scheda, così chi arriva dopo non si ritrova loggato con l'account di qualcun altro. Il costo è rifare il login a ogni nuova scheda.
- **Componente `DiagnosisResult` separato** da `ChatMessageList`, così il modo in cui si mostra una risposta è isolato dall'elenco dei messaggi. Non era nel piano.
- **Testi dell'interfaccia in italiano**, codice e commenti in inglese.
- **Pulsanti e campi alti almeno 44px**, pensati per l'uso con le dita su tablet.
- **Nessuna interfaccia per la gestione della knowledge base**: nel PoC l'esperto usa Swagger.

### 4.10 Archivio funzioni

La normalizzazione del testo è generica. È stata aggiunta a `function_archive/strings/normalize_text_ita.py` e copiata in `backend/app/utils/` con lo stesso nome, per tracciabilità.

## 5. Tentativi che non hanno funzionato

| Tentativo | Cosa è successo | Come è stato risolto |
|---|---|---|
| `token_set_ratio` come scorer (previsto nel piano) | la misura sui dati del seed ha mostrato diagnosi sbagliate: 81.6 per un sintomo diverso sullo stesso componente, 100 per una parola sola | sostituito da `token_sort_ratio` (vedi 4.3) |
| FULLTEXT di MySQL come motore di matching | 0 risultati con un refuso | rapidfuzz; l'indice resta come futuro pre-filtro |
| Creazione del venv su Ubuntu | `ensurepip is not available` | installato `python3.12-venv`, poi `python3 -m venv --clear` |
| Installazione di MariaDB | non necessaria: MySQL 8 era già attivo | usato MySQL 8 |
| Node.js dai pacchetti di Ubuntu | versione 18, troppo vecchia per Vite (richiede `^20.19` o `>=22.12`) | Node 24 LTS installato con nvm, senza `sudo` |
| `python -c "..."` con molte virgolette annidate nelle verifiche da terminale | errori di interpretazione della shell | script passati con heredoc (`python - <<'EOF'`) |

## Limiti conosciuti

### Matching

1. **⚠️ La negazione pesa pochissimo.** "non" viene conservato, ma è una sola parola di differenza. Misurato: "La pinza del robot **chiude** completamente" prende **94.1** contro "…**non** chiude completamente", e quindi trova la diagnosi del sintomo opposto. È il limite più rilevante rispetto al principio anti-allucinazione (vedi le migliorie possibili).
2. **Una parola diversa su poche pesa poco anche in generale.** "si blocca a intermittenza" prende 88.9 contro "si ferma a intermittenza". Qui l'effetto è utile, perché i due verbi sono quasi sinonimi, ma il meccanismo è lo stesso del punto 1.
3. **Le descrizioni molto più corte del sintomo registrato non trovano nulla.** "pinza non chiude" prende 61.5; "nastro fermo" contro "si ferma a intermittenza" prende 75.8. Risultato: `no_match`. È voluto (vedi 4.3), ma obbliga l'operatore a descrizioni abbastanza complete.
4. **Nessuna gestione di sinonimi o radici delle parole** ("fermo" / "ferma" / "arresto"). Le stopword sono una lista scritta a mano.
5. **Soglia unica e globale** (`MATCH_SCORE_THRESHOLD`), calibrata solo sulle frasi del seed e non su dati reali di linea. Non varia per famiglia.
6. **Tutte le diagnosi vengono confrontate a ogni richiesta.** Va bene per centinaia o poche migliaia di righe; oltre serve un pre-filtro, per esempio con l'indice FULLTEXT già presente.
7. **Una sola risposta per richiesta**: con più ipotesi vicine l'operatore riceve la lista e deve scegliere da solo (vedi i prossimi passi).

### AI

8. **Il fallback AI può riscrivere il sintomo in uno sbagliato** che poi trova corrispondenza. Le mitigazioni sono l'AI spenta di default, l'uso solo quando il testo originale non trova nulla e l'indicazione "interpretato come". Il rischio però resta.
9. **`LocalAIProvider` è testato solo con HTTP simulato**, non con un vero modello Ollama. Qualità del prompt e comportamento dei modelli reali sono da validare.
10. **`AI_PROVIDER=api` manda il testo dell'operatore fuori dalla rete aziendale.** Va bene per il PoC, non per dati di produzione.

### Sicurezza e gestione

11. **Il singolo token non si può revocare** prima della scadenza (8 ore), anche se ruolo ed esistenza dell'utente vengono riverificati a ogni richiesta.
12. **Il token in `sessionStorage` è leggibile da JavaScript**, quindi esposto a eventuali vulnerabilità XSS. Un cookie `HttpOnly` sarebbe più sicuro, ma più complesso con CORS.
13. **Nessun limite ai tentativi di login** (rate limiting) e nessuna configurazione HTTPS: il PoC è pensato per l'uso in locale.
14. **Credenziali demo nel seed**, documentate nel README e da rimuovere prima di un uso reale.
15. **Nessun registro delle consultazioni** e nessun feedback dell'operatore ("la soluzione ha funzionato?"): oggi non si può misurare l'efficacia della knowledge base.

### Frontend e manutenzione

16. **Nessuna interfaccia per l'esperto**: la knowledge base si gestisce da Swagger.
17. **Nessun test automatico del frontend**: verificato con build, lint e prove manuali.
18. **Alcuni messaggi di errore del backend sono in inglese** e compaiono così nell'interfaccia italiana, per esempio "Product family not found". I casi principali (login errato, `no_match`, server non raggiungibile) sono tradotti nel frontend.
19. **Warning di deprecazione nei test**: Starlette avvisa che in una versione futura il `TestClient` richiederà il pacchetto `httpx2` al posto di `httpx`. Oggi non ha effetti; se un aggiornamento delle dipendenze rompe i test, la causa è questa.
20. **Nel repository restano, non tracciati, alcuni file del template di Vite non usati** (`src/App.css`, `src/index.css`, `src/assets/`, `public/icons.svg`, `frontend/README.md`), in attesa di essere eliminati. L'icona della scheda del browser (`favicon.svg`) è ancora il logo di Vite.

## Prossimi passi pianificati

### v2 — Domanda di disambiguazione (un solo livello)

**Cosa.** Quando due o più candidati superano la soglia con punteggi **vicini tra loro** (distanza ≤ `DISAMBIGUATION_SCORE_GAP`, configurabile, indicativamente 5-10 punti), il sistema non restituisce più l'elenco delle ipotesi. Propone invece **una sola domanda** scritta dall'esperto, con **risposte a scelta chiusa**. Ogni risposta punta a uno dei candidati (`base_diagnostic_id`). Dopo la risposta si mostra la diagnosi di quel candidato, con le eventuali eccezioni applicate come oggi.

Caratteristiche:
- **deterministica**: nessun testo generato, domanda e risposte sono scritte dall'esperto;
- **un solo livello**: niente grafo di domande, niente ricorsione, profondità massima 1;
- **opzionale**: se per quel gruppo di candidati non esiste una domanda, il comportamento resta quello della v1 (elenco ordinato per punteggio).

**Perché non è nella v1.**
- **Rischio di esplosione combinatoria.** Un vero albero decisionale multi-livello obbligherebbe l'esperto a prevedere e scrivere ogni ramo, con uno sforzo di mappatura che cresce molto in fretta e che è difficile tenere aggiornato.
- **Prima va validato il matching di base.** Bisogna capire nella pratica quanto spesso si verificano pareggi e su quali sintomi. Sono proprio questi dati a indicare dove vale la pena scrivere una domanda.
- **Si aggiunge senza toccare il motore esistente**: è un livello sopra il matching, non un suo sostituto.

**Modifiche previste al database (solo tabelle nuove, nessun `ALTER` su quelle esistenti):**

```sql
disambiguation_questions (
    id, question_text,
    family_id       FK → product_families  NULL,   -- NULL = valida per tutte le famiglie
    cycle_phase_id  NULL,                          -- NULL = valida per tutte le fasi
    created_by      FK → users,
    created_at, updated_at
    -- coerenza fase/famiglia: stessa FK composita su cycle_phases (id, family_id)
)

disambiguation_options (
    id,
    question_id         FK → disambiguation_questions  ON DELETE CASCADE,
    option_text,
    base_diagnostic_id  FK → base_diagnostics          ON DELETE CASCADE,
    UNIQUE (question_id, base_diagnostic_id)
)
```

A runtime: dato l'insieme S dei candidati con punteggi vicini, si sceglie la domanda del contesto più specifico (famiglia + fase, poi solo famiglia, poi generica) le cui opzioni coprono **tutti** i candidati di S. Le opzioni puntano alla diagnosi generica, quindi l'eventuale eccezione della fase si applica da sola, dopo la scelta.

**Predisposizioni già presenti nella v1**, grazie alle quali non servirà un refactor:
- ✅ ogni risultato del matcher è identificato da `base_diagnostic_id` e conserva il proprio punteggio. Le righe non vengono mai raggruppate per testo del sintomo, perché le opzioni della v2 puntano a righe precise;
- ✅ la risposta di `/diagnosis` ha il campo `status`: `disambiguation` diventerà un terzo valore senza rompere il formato della risposta;
- ✅ l'eccezione viene applicata sul candidato già identificato, quindi funzionerà allo stesso modo dopo la scelta dell'operatore;
- ✅ il frontend (`DiagnosisResult`) sceglie cosa mostrare in base a `status` e ha un ramo di default per gli stati sconosciuti.

Da aggiungere nella v2:
- le due tabelle;
- il CRUD delle domande per l'expert;
- la logica di selezione della domanda nel `diagnosis_service`;
- un endpoint o un campo per inviare la risposta scelta;
- il componente che mostra la domanda nel frontend.

## Migliorie possibili (non pianificate)

Idee emerse durante lo sviluppo, da valutare dopo la validazione del PoC:

- **Controllo di coerenza della negazione** (limite 1): regola deterministica che scarta un candidato quando la richiesta e il sintomo non concordano sulla presenza di "non". È semplice e resta a regole.
- **Calibrare la soglia su dati reali**, raccogliendo richieste degli operatori e l'esito atteso.
- **Sinonimi e radici delle parole** gestiti a regole (dizionario di dominio scritto dagli esperti), prima di passare a un livello semantico.
- **`SemanticMatcher` locale** (sentence-transformers eseguito in azienda) dietro l'interfaccia `Matcher` già esistente.
- **Pre-filtro FULLTEXT** quando la knowledge base diventerà grande.
- **Interfaccia per l'esperto** per gestire la knowledge base senza Swagger.
- **Registro delle consultazioni e feedback dell'operatore**, per misurare MTTD/MTTR e trovare i sintomi senza copertura (`no_match` frequenti).
- **Test automatici del frontend** (per esempio Vitest + React Testing Library).
- **Messaggi di errore del backend tradotti** o gestiti con codici invece che con testo.
- **Rate limiting sul login, HTTPS, cookie `HttpOnly`** prima di un uso fuori dalla rete locale.
- **Docker e CI** (GitHub Actions per test e lint) quando servirà distribuire il sistema.
