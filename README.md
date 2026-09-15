# Dedalo

Assistente di troubleshooting guidato per impianti e linee produttive ad alta complessità meccatronica (**Proof of Concept**).

L'operatore sceglie la **famiglia di prodotto** (e la **fase del ciclo**, se la conosce) e descrive il sintomo **con parole sue**. Dedalo cerca per significato nella knowledge base scritta dagli esperti e restituisce **una lista di ipotesi con la probabilità stimata**: componente, causa e soluzione. Quando le ipotesi sono vicine fa una domanda per restringerle.

Cause e soluzioni vengono **sempre dalla knowledge base**, mai generate. Se nulla è compatibile, l'app dice esplicitamente che non ci sono dati. Un assistente AI (LLM) può guidare la conversazione, ma è **facoltativo**: senza, l'app funziona offline e gratis.

> 📐 Decisioni di design, calibrazione, alternative scartate e limiti conosciuti sono in **[workflow_sviluppo.md](workflow_sviluppo.md)**. Questo README spiega come installare, avviare e usare il progetto.

---

## Indice

- [Funzionalità](#funzionalità)
- [Stack](#stack)
- [Struttura del progetto](#struttura-del-progetto)
- [Requisiti](#requisiti)
- [Installazione](#installazione)
- [Aggiornamento da v1](#aggiornamento-da-v1)
- [Avvio](#avvio)
- [Utenti di test](#utenti-di-test)
- [Uso](#uso)
- [Guida al CSV per l'esperto](#guida-al-csv-per-lesperto)
- [Configurazione](#configurazione)
- [Assistente AI (opzionale)](#assistente-ai-opzionale)
- [API](#api)
- [Test e calibrazione](#test-e-calibrazione)
- [Risoluzione dei problemi](#risoluzione-dei-problemi)

---

## Funzionalità

- **Ricerca semantica in locale**: modello di embedding italiano (sentence-transformers) più somiglianza fuzzy per i refusi. "La cella si pianta a metà ciclo" trova "La cella di saldatura non completa il ciclo ed entra in allarme".
- **Ipotesi con probabilità stimata**, compresa la quota "*nessuna di queste ipotesi*", così un'ipotesi debole non appare mai al 100%.
- **Tre esiti**: ipotesi sicure, ipotesi incerte (con avviso), nessun dato.
- **Domande di scelta deterministiche** costruite dai dati (sintomo o componente); "*Nessuna di queste*" esclude le opzioni proposte.
- **Regola sulla negazione**: "la pinza chiude completamente" non restituisce "la pinza non chiude completamente".
- **Fasi facoltative**: una diagnosi può valere per tutte le famiglie, per una famiglia o per una sola fase.
- **Assistente AI facoltativo** (OpenAI o Ollama): pone domande e restringe le ipotesi, ma non scrive mai cause o soluzioni; se sbaglia o non risponde, subentra il flusso deterministico.
- **Interfaccia esperto**: elenco con filtri e ricerca, creazione, modifica, eliminazione.
- **Import/export CSV** compatibile con Excel, con anteprima e salvataggio tutto-o-niente.
- **Due ruoli (RBAC)**: `expert` gestisce la knowledge base, `operator` consulta soltanto.

## Stack

| Livello | Tecnologia |
|---|---|
| Backend | Python 3.11+ (sviluppato con 3.12), FastAPI, Uvicorn |
| Database | MySQL 8.0.16+ / MariaDB 10.2+, accesso con SQLAlchemy Core + PyMySQL |
| Ricerca | sentence-transformers + PyTorch CPU, modello `nickprock/sentence-bert-base-italian-xxl-uncased` (licenza MIT), rapidfuzz |
| Autenticazione | JWT (PyJWT) + bcrypt |
| AI (opzionale) | httpx verso API compatibili OpenAI oppure Ollama |
| Frontend | React 19 + Vite, JavaScript, react-router-dom |
| Test | pytest, pytest-cov, pytest-mock |

## Struttura del progetto

```
dedalo/
├── database/
│   ├── schema.sql                  # tabelle, vincoli, indici (ricrea tutto da zero)
│   └── seed.sql                    # 3 famiglie, 36 diagnosi di esempio, utenti demo
├── backend/
│   ├── app/
│   │   ├── main.py                 # create_app(): assembla l'applicazione
│   │   ├── config.py               # lettura centralizzata di .env
│   │   ├── db.py / dependencies.py / logging_config.py
│   │   ├── routes/                 # endpoint HTTP (sottili)
│   │   ├── schemas/                # validazione input/output (Pydantic)
│   │   ├── services/
│   │   │   ├── embeddings/         # interfaccia Embedder, modello locale, cache per testo
│   │   │   ├── matching/           # matcher semantico, fuzzy (baseline v1), regola negazione
│   │   │   ├── ai/                 # interfaccia AIProvider + backend none/api/local
│   │   │   ├── diagnosis_service.py        # conversazione
│   │   │   ├── disambiguation_service.py   # domanda di scelta deterministica
│   │   │   ├── llm_advisor_service.py      # passo LLM con validazione
│   │   │   ├── probability_service.py      # percentuali
│   │   │   ├── knowledge_base_service.py   # CRUD ed export
│   │   │   ├── csv_service.py / import_service.py
│   │   │   └── ...
│   │   ├── repositories/           # query SQL
│   │   └── utils/                  # funzioni generiche copiate da function_archive
│   ├── scripts/evaluate_matching.py  # calibrazione di modello e soglie
│   ├── tests/                      # suite pytest + fixtures/operator_queries.json
│   ├── run.py                      # unico punto di avvio del server
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── services/api.js         # unico ponte verso il backend
│   │   ├── components/             # TopBar, ContextSelector, ChatInput, ChatMessageList, DiagnosisResult,
│   │   │                           # ChoiceOptions, DiagnosticsTable, DiagnosticForm, CsvGuide, CsvImportPanel, LoginForm
│   │   ├── pages/                  # LoginPage, ChatPage, KnowledgeBasePage
│   │   ├── utils/saveFile.js       # download di file dal browser
│   │   ├── styles/app.css
│   │   ├── App.jsx                 # routing e sessione
│   │   └── main.jsx
│   └── package.json
├── README.md
└── workflow_sviluppo.md
```

## Requisiti

- **Python 3.11+** con il modulo `venv` (su Ubuntu: `python3.12-venv`).
- **MySQL 8.0.16+** oppure **MariaDB 10.2+**: servono i vincoli `CHECK`.
- **Node.js `^20.19` oppure `>=22.12`** (sviluppato con Node 24 LTS installato con [nvm](https://github.com/nvm-sh/nvm); il `nodejs` di Ubuntu 24.04 è troppo vecchio).
- **Circa 2 GB di disco** per PyTorch CPU e il modello, e **almeno 2 GB di RAM libera** per il backend. La GPU non serve.
- **Internet solo al primo avvio**, per scaricare il modello (~450 MB) da Hugging Face. Poi tutto funziona offline.

## Installazione

Tutti i comandi partono dalla root del progetto, se non indicato diversamente.

### 1. Database

```bash
sudo mysql
```

```sql
CREATE DATABASE dedalo      CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE dedalo_test CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'dedalo'@'localhost' IDENTIFIED BY 'scegli_una_password';
GRANT ALL PRIVILEGES ON dedalo.*      TO 'dedalo'@'localhost';
GRANT ALL PRIVILEGES ON dedalo_test.* TO 'dedalo'@'localhost';
FLUSH PRIVILEGES;
```

```bash
mysql -u dedalo -p dedalo < database/schema.sql
mysql -u dedalo -p dedalo < database/seed.sql
```

> ⚠️ `schema.sql` **elimina e ricrea** tutte le tabelle: rieseguirlo cancella i dati. Il database `dedalo_test` non va popolato a mano: i test lo ricreano a ogni esecuzione.

Per controllare che i vincoli siano stati applicati: `SHOW CREATE TABLE diagnostics;` deve mostrare `chk_diagnostics_phase_requires_family` e `fk_diagnostics_phase_family`.

### 2. Backend

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install torch --index-url https://download.pytorch.org/whl/cpu
.venv/bin/pip install -r requirements.txt
cp .env.example .env
```

**PyTorch va installato per primo, dall'indice CPU.** Il pacchetto di default include CUDA e pesa diversi GB, inutili senza una GPU compatibile. `requirements.txt` fissa `torch==2.14.0+cpu`, versione che esiste solo in quell'indice: se lo salti, il secondo comando fallisce.

Poi apri `backend/.env` e imposta almeno:

- `DB_USER` e `DB_PASSWORD`;
- `JWT_SECRET_KEY`, generata con `python3 -c "import secrets; print(secrets.token_hex(32))"`.

Il file `.env` è ignorato da Git e **non va mai committato**.

### 3. Frontend

```bash
cd frontend
npm ci
```

`frontend/.env` serve solo se il backend non è su `http://127.0.0.1:8000` (vedi `frontend/.env.example`).

## Aggiornamento da v1

La v2 sostituisce le tabelle `base_diagnostics` e `diagnostic_exceptions` con un'unica tabella `diagnostics`. Non esiste una migrazione automatica: il PoC contiene solo dati di esempio.

1. Se hai inserito diagnosi a mano in v1, annotale prima di procedere.
2. Ricrea il database: `mysql -u dedalo -p dedalo < database/schema.sql` e poi `seed.sql`.
3. Installa le nuove dipendenze (sezione [Backend](#2-backend), comandi `pip`).
4. In `backend/.env` elimina `MATCH_SCORE_THRESHOLD` (non più usata) e, se vuoi, copia le nuove variabili da `.env.example`. Senza, valgono i default calibrati.

## Avvio

**Backend:**

```bash
cd backend
.venv/bin/python run.py
```

Al primo avvio il modello viene scaricato (qualche minuto). Agli avvii successivi il backend carica il modello e calcola i vettori di tutti i sintomi in pochi secondi, prima di accettare richieste.

- API: http://127.0.0.1:8000
- Swagger: http://127.0.0.1:8000/docs

Per garantire che non parta nessuna connessione verso Hugging Face (dopo il primo download): `HF_HUB_OFFLINE=1 .venv/bin/python run.py`.

**Frontend (sviluppo):**

```bash
cd frontend
npm run dev
```

Apri **http://localhost:5173**. Build di produzione: `npm run build` (file in `frontend/dist/`), prova con `npm run preview`.

## Utenti di test

| Ruolo | Username | Password | Cosa può fare |
|---|---|---|---|
| `expert` | `expert_demo` | `expert123` | chat, gestione della knowledge base, import/export CSV |
| `operator` | `operator_demo` | `operator123` | solo chat |

⚠️ Credenziali **solo per lo sviluppo locale**: vanno rimosse prima di qualsiasi uso reale.

## Uso

### Chat di diagnosi (entrambi i ruoli)

1. Scegli la **famiglia di prodotto**. La **fase** è facoltativa: se la cella si ferma e non sai dove sta il guasto, lascia "*Non so / tutte le fasi*".
2. Descrivi il sintomo con parole tue e premi Invio (Shift+Invio va a capo).
3. Leggi la risposta:
   - **ipotesi**, ordinate per probabilità stimata. Per ognuna: componente, ambito (tutte le famiglie, tutta la famiglia, una fase), barra della probabilità, sintomo registrato, causa e soluzione. In fondo, la quota "*Nessuna di queste ipotesi*";
   - **"Nessuna corrispondenza sicura"** (riquadro giallo): le ipotesi sono solo simili al sintomo, da verificare con attenzione;
   - **"Nessun dato disponibile"**: nulla di compatibile, nessuna procedura suggerita.
4. Se compare una **domanda di scelta**, tocca l'opzione giusta: le ipotesi delle altre opzioni vengono escluse. "*Nessuna di queste*" le esclude tutte.
5. Con l'assistente AI attivo può comparire una **domanda aperta**: rispondi nella casella di testo.
6. "*Nuova conversazione*" azzera la chat. Anche cambiare famiglia o fase avvia una nuova conversazione.

Esempi con i dati del seed (modalità offline):

| Famiglia / fase | Testo | Risultato |
|---|---|---|
| Cella di saldatura robotizzata / non indicata | `la cella si pianta e va in allarme a metà ciclo` | 3 ipotesi a pari probabilità (nastro pallet, barriera, torcia) e domanda sul componente |
| stessa, dopo aver scelto "Nastro trasportatore pallet" | — | l'ipotesi del nastro pallet in cima |
| Confezionatrice flow-pack / 1. Svolgimento film | `il nastro ogni tanto si stoppa` | ipotesi incerte con domanda di scelta tra i sintomi |
| Cella di assemblaggio robotizzata / 2. Serraggio in pinza | `La pinza del robot chiude completamente` | non propone "la pinza non chiude completamente" |
| Cella di saldatura robotizzata / 3. Saldatura | `l'arco non si accende` | ipotesi sul generatore di saldatura |
| Cella di saldatura robotizzata / non indicata | `il muletto ha una ruota bucata` | ipotesi incerta, quasi tutta la probabilità a "nessuna di queste" |
| qualsiasi | `il caffè della macchinetta è freddo` | Nessun dato disponibile |

### Knowledge base (solo `expert`)

Link **Knowledge base** nella barra in alto.

- **Filtri** per famiglia e fase, **ricerca** su sintomo, componente, causa e soluzione. Il filtro famiglia mostra solo le diagnosi scritte per quella famiglia, non quelle generiche.
- **Nuova diagnosi** / **Modifica**: sintomo, componente, causa, soluzione e ambito. Famiglia vuota = tutte le famiglie; fase vuota = tutta la famiglia.
- **Elimina** chiede conferma: l'operazione non si annulla.
- **Import ed export CSV**: vedi la guida qui sotto, riportata anche nella pagina.

Ogni modifica è visibile subito in chat, senza riavvii.

## Guida al CSV per l'esperto

### Procedura

1. Premi **Scarica modello** (righe di esempio con famiglie e fasi reali) oppure **Esporta dati attuali** per modificare quelli esistenti.
2. Apri il file con Excel e scrivi una riga per diagnosi. Cancella le righe di esempio.
3. Salva con *File → Salva con nome → CSV UTF-8*.
4. Carica il file e premi **Controlla file**: non viene salvato nulla, vedi quante righe verranno aggiunte, modificate o lasciate invariate, e gli errori riga per riga.
5. Se non ci sono errori, premi **Importa**.

### Colonne

| Colonna | Obbligatoria | Cosa scrivere |
|---|---|---|
| `id` | no | vuota = **nuova** diagnosi; un numero = **modifica** la diagnosi con quell'id (lo trovi nell'export). Un id inesistente è un errore |
| `family_name` | no | vuota = valida per **tutte le famiglie**; altrimenti il nome esatto di una famiglia (maiuscole e minuscole non contano) |
| `phase_number` | no | vuota = valida per **tutta la famiglia**; altrimenti il numero della fase (richiede `family_name`) |
| `phase_name` | no | solo informativa: l'export la riempie, l'import la **ignora** |
| `symptom_description` | sì | il sintomo come lo descriverebbe un operatore, massimo 500 caratteri |
| `affected_component` | sì | il componente, massimo 150 caratteri |
| `probable_cause` | sì | la causa probabile |
| `recommended_solution` | sì | la procedura da seguire |

### Regole

- Le diagnosi **assenti dal file restano invariate**: il CSV non cancella mai nulla.
- **Un solo errore blocca tutto il file**: non viene salvata nessuna riga.
- Stesso sintomo su più righe = **cause alternative**: usa sempre la stessa dicitura.
- Separatore `;` o `,`, codifica UTF-8 (accettato anche il CSV di Excel per Windows), massimo 2 MB e 5000 righe.
- Un testo che inizia con `=`, `+`, `-` o `@` viene esportato con un apostrofo davanti, così Excel non lo esegue come formula. In import l'apostrofo viene tolto.

### Esempio

```csv
id;family_name;phase_number;phase_name;symptom_description;affected_component;probable_cause;recommended_solution
;;;;La macchina non si avvia e il pulsante di marcia non risponde;Circuito di sicurezza;Catena di sicurezza aperta.;Controllare emergenze e ripari, poi resettare il modulo di sicurezza.
;Cella di saldatura robotizzata;;;La cella di saldatura non completa il ciclo ed entra in allarme;Nastro trasportatore pallet;Il nastro pallet è guasto e manda in allarme tutta la cella.;Ricercare il guasto nel nastro e nella sua logica.
;Cella di saldatura robotizzata;3;;L'arco di saldatura non si innesca;Generatore di saldatura;Cavo di massa scollegato.;Verificare il collegamento del cavo di massa.
26;Cella di saldatura robotizzata;;;La cella di saldatura non completa il ciclo ed entra in allarme;Motore nastro pallet;Motore del nastro pallet in protezione termica.;Verificare l'inverter del nastro pallet.
```

Le prime tre righe creano diagnosi con i tre ambiti (generica, famiglia, fase). L'ultima modifica la diagnosi 26.

## Configurazione

### Backend: `backend/.env`

Template commentato in [backend/.env.example](backend/.env.example). Le variabili d'ambiente del sistema hanno la precedenza sul file.

| Variabile | Default | Descrizione |
|---|---|---|
| `DB_HOST` / `DB_PORT` | `localhost` / `3306` | server MySQL |
| `DB_USER` / `DB_PASSWORD` | — (obbligatorie) | credenziali MySQL |
| `DB_NAME` | `dedalo` | database dell'applicazione |
| `DB_TEST_NAME` | `dedalo_test` | database dei test; **deve** essere diverso da `DB_NAME` |
| `JWT_SECRET_KEY` | — (obbligatoria) | chiave di firma dei token |
| `JWT_ALGORITHM` / `JWT_EXPIRE_MINUTES` | `HS256` / `480` | firma e durata del token |
| `EMBEDDING_MODEL` | `nickprock/sentence-bert-base-italian-xxl-uncased` | modello di embedding locale |
| `EMBEDDING_QUERY_PREFIX` / `EMBEDDING_DOCUMENT_PREFIX` | vuote | prefissi richiesti da alcuni modelli (es. e5: `query: ` / `passage: `) |
| `SEMANTIC_USE_FUZZY` | `true` | usa anche la somiglianza fuzzy (aiuta con i refusi) |
| `SEMANTIC_RECALL_THRESHOLD` | `0.50` | sotto questo punteggio un'ipotesi non viene mostrata |
| `SEMANTIC_MATCH_THRESHOLD` | `0.65` | da qui in su la risposta è "sicura"; tra le due soglie è "incerta" |
| `DISAMBIGUATION_SCORE_GAP` | `0.05` | due ipotesi più vicine di così provocano una domanda di scelta |
| `PROBABILITY_TEMPERATURE` | `0.03` | quanto la probabilità premia il punteggio migliore |
| `PROBABILITY_UNKNOWN_SCORE` | `0.60` | punteggio della quota "nessuna di queste ipotesi" |
| `MAX_CANDIDATES` | `5` | ipotesi mostrate al massimo |
| `AI_PROVIDER` | `none` | `none`, `api` oppure `local` |
| `MAX_LLM_QUESTIONS` | `3` | domande che l'assistente AI può fare in una conversazione |
| `AI_TIMEOUT_SECONDS` | `30` | oltre questo tempo la risposta passa al flusso offline |
| `AI_API_URL` / `AI_API_KEY` / `AI_API_MODEL` | vuote | solo con `AI_PROVIDER=api` |
| `OLLAMA_BASE_URL` / `OLLAMA_MODEL` | `http://localhost:11434` / vuota | solo con `AI_PROVIDER=local` |
| `CORS_ORIGINS` | `http://localhost:5173` | indirizzi del frontend autorizzati, separati da virgola |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `APP_HOST` / `APP_PORT` / `APP_RELOAD` | `127.0.0.1` / `8000` / `false` | server |

> Le soglie sono calibrate sui dati di esempio. Con dati reali, prima di cambiarle rilancia lo script di calibrazione (vedi [Test e calibrazione](#test-e-calibrazione)).

### Frontend: `frontend/.env`

| Variabile | Default | Descrizione |
|---|---|---|
| `VITE_API_URL` | `http://127.0.0.1:8000` | indirizzo del backend (pubblico: mai segreti qui) |

## Assistente AI (opzionale)

Con `AI_PROVIDER=none` (default) la chat è **completamente deterministica e offline**. Con un provider attivo, a ogni turno il modello riceve le ipotesi già trovate nel database e la conversazione, e può soltanto:

- **fare una domanda** all'operatore (al massimo `MAX_LLM_QUESTIONS`);
- **restringere** le ipotesi a quelle compatibili con le risposte;
- **dichiarare** che nessuna ipotesi è compatibile.

Il backend valida ogni risposta: un id inventato, una domanda oltre il limite, un JSON malformato, un timeout o un errore fanno scattare la **risposta offline**, e l'interfaccia lo segnala. Ordine e probabilità delle ipotesi sono sempre calcolati dai punteggi, mai dal modello.

| `AI_PROVIDER` | Cosa fa | Note |
|---|---|---|
| `none` (default) | nessuna AI | nessun testo lascia la macchina, nessun costo |
| `api` | API compatibile OpenAI (`POST {AI_API_URL}/chat/completions`, JSON mode) | ⚠️ **a pagamento**, e la conversazione con cause e soluzioni candidate **esce dalla rete aziendale**: solo per la demo, mai con dati di produzione |
| `local` | modello servito da [Ollama](https://ollama.com) | gratuito, i dati restano in azienda; su CPU le risposte richiedono diversi secondi |

OpenAI per la demo:

```ini
AI_PROVIDER=api
AI_API_URL=https://api.openai.com/v1
AI_API_KEY=sk-...
AI_API_MODEL=gpt-4o-mini
```

Ollama:

```bash
ollama pull qwen2.5:3b
```

```ini
AI_PROVIDER=local
OLLAMA_MODEL=qwen2.5:3b
AI_TIMEOUT_SECONDS=60
```

Se manca una variabile obbligatoria per il provider scelto, il backend **non si avvia** e indica quale.

## API

Documentazione interattiva su http://127.0.0.1:8000/docs. Tutti gli endpoint tranne il login richiedono `Authorization: Bearer <token>`.

| Metodo | Endpoint | Ruolo | Descrizione |
|---|---|---|---|
| POST | `/auth/login` | pubblico | login con form `username` e `password` |
| GET | `/auth/me` | tutti | utente corrente |
| GET | `/families` | tutti | famiglie di prodotto |
| GET | `/families/{family_id}/phases` | tutti | fasi di una famiglia |
| POST | `/diagnosis` | tutti | un turno della conversazione di diagnosi |
| GET | `/diagnostics?family_id=&cycle_phase_id=&search=` | tutti | elenco delle diagnosi, filtri facoltativi |
| GET | `/diagnostics/{diagnostic_id}` | tutti | dettaglio |
| POST | `/diagnostics` | expert | crea |
| PUT | `/diagnostics/{diagnostic_id}` | expert | sostituisce |
| DELETE | `/diagnostics/{diagnostic_id}` | expert | elimina |
| GET | `/diagnostics/export` | expert | tutte le diagnosi in CSV |
| GET | `/diagnostics/import-template` | expert | modello CSV con esempi |
| POST | `/diagnostics/import?dry_run=true` | expert | import CSV (`multipart/form-data`, campo `file`); `dry_run=false` scrive |

Richiesta di diagnosi. Il server non conserva la conversazione: il client invia ogni volta tutti i messaggi e gli id esclusi dalle scelte.

```json
POST /diagnosis
{
  "family_id": 3,
  "cycle_phase_id": null,
  "messages": [{ "role": "operator", "content": "la cella si pianta e va in allarme a metà ciclo" }],
  "excluded_diagnostic_ids": []
}
```

Risposta (abbreviata):

```json
{
  "status": "hypotheses",
  "confidence": "high",
  "mode": "deterministic",
  "ai_fallback": false,
  "hypotheses": [
    { "diagnostic_id": 26, "affected_component": "Nastro trasportatore pallet", "scope": "family", "score": 0.732, "probability": 33, "cause": "...", "solution": "..." }
  ],
  "unknown_probability": 1,
  "follow_up": {
    "type": "choice",
    "question": "Quale di queste descrive meglio la situazione?",
    "options": [{ "label": "Nastro trasportatore pallet", "diagnostic_ids": [26] }]
  }
}
```

- `status`: `hypotheses` oppure `no_match`. Chi usa l'API deve sempre decidere in base a questo campo.
- `confidence`: `high` o `low`. `mode`: `deterministic` o `llm`.
- Le `probability` delle ipotesi più `unknown_probability` sommano a 100.
- `follow_up.type`: `choice` (opzioni; scegliere un'opzione = aggiungere gli id delle altre a `excluded_diagnostic_ids`) oppure `question` (domanda del modello, da rimandare come messaggio `assistant` insieme alla risposta dell'operatore).

**Codici di stato:**

| Codice | Significato |
|---|---|
| `200` | ok, anche per `no_match` e per l'anteprima dell'import |
| `201` | risorsa creata |
| `400` | richiesta non valida: body malformato, fase senza famiglia o di un'altra famiglia, CSV con errori (il report è in `detail`) |
| `401` | token mancante, scaduto o non valido |
| `403` | ruolo insufficiente |
| `404` | risorsa, famiglia o fase non trovata |

## Test e calibrazione

### Backend

I test usano `dedalo_test`, ricreato da `schema.sql` + `seed.sql` a ogni esecuzione; `dedalo` non viene mai toccato. L'app di test usa un embedder finto, quindi la suite è veloce. Solo i test marcati `model` caricano il modello vero.

```bash
cd backend
.venv/bin/python -m pytest                                      # tutta la suite (~30 s)
.venv/bin/python -m pytest -m "not model"                       # senza il modello vero
.venv/bin/python -m pytest --cov=app --cov-report=term-missing  # con copertura
```

Nessun test chiama servizi esterni: i provider AI sono testati con un trasporto HTTP simulato.

### Calibrazione del matching

`tests/fixtures/operator_queries.json` contiene 60 frasi scritte come un operatore, con l'esito atteso. Lo script misura il modello su quelle frasi:

```bash
cd backend
.venv/bin/python -m scripts.evaluate_matching                   # modello configurato
.venv/bin/python -m scripts.evaluate_matching --models intfloat/multilingual-e5-base --details
```

Stampa il confronto con il motore v1, la tabella soglia per soglia, la distribuzione nelle tre fasce, la calibrazione delle probabilità e i distacchi tra le prime ipotesi. Con dati reali: aggiungi frasi alla fixture, rilancia e aggiorna le soglie in `.env`.

### Frontend

```bash
cd frontend
npm run lint
npm run build
```

## Risoluzione dei problemi

| Problema | Soluzione |
|---|---|
| `No matching distribution found for torch==2.14.0+cpu` | installa prima PyTorch dall'indice CPU (vedi [Backend](#2-backend)) |
| Il download di PyTorch pesa diversi GB | stai installando la versione CUDA: annulla e usa `--index-url https://download.pytorch.org/whl/cpu` |
| Il primo avvio resta fermo per minuti | è il download del modello da Hugging Face: succede solo la prima volta |
| `We couldn't connect to 'https://huggingface.co'` all'avvio | il modello non è ancora in cache e manca internet: avvia una volta con la rete |
| Il backend occupa ~1-2 GB di RAM | normale: è il modello di embedding caricato in memoria |
| `ensurepip is not available` | `sudo apt install python3.12-venv`, poi `python3 -m venv --clear .venv` |
| `node: command not found` in un nuovo terminale | riapri il terminale oppure `source ~/.nvm/nvm.sh` |
| "Server non raggiungibile" nel frontend | backend spento, oppure `VITE_API_URL` sbagliato |
| Errore CORS nel browser | aggiungi l'indirizzo del frontend a `CORS_ORIGINS` e riavvia |
| `Unknown column` / `Table 'diagnostics' doesn't exist` | database ancora in schema v1: vedi [Aggiornamento da v1](#aggiornamento-da-v1) |
| `AI_PROVIDER=... requires these variables in .env` | imposta le variabili indicate oppure `AI_PROVIDER=none` |
| Le risposte riportano "Assistente AI non disponibile" | provider irraggiungibile, lento (`AI_TIMEOUT_SECONDS`) o risposta non valida: il motivo è nel log del backend |
| `DB_TEST_NAME must differ from DB_NAME` nei test | protezione voluta |
| Warning `StarletteDeprecationWarning ... httpx2` nei test | viene da una libreria, per ora non serve fare nulla |
