# Dedalo

Assistente di troubleshooting guidato per impianti e linee produttive ad alta complessità meccatronica (**Proof of Concept**).

L'operatore sceglie **famiglia di prodotto** e **fase del ciclo di lavoro**, poi descrive il sintomo in una chat. Dedalo cerca nella knowledge base scritta dagli esperti e restituisce le diagnosi compatibili: componente coinvolto, causa probabile e soluzione. Se esiste una procedura specifica per quella fase, usa quella.

Il matching è **deterministico** e non genera mai testo. Se non c'è una corrispondenza certa, l'app dice esplicitamente che per quel sintomo non ci sono dati.

> 📐 Decisioni di design, alternative scartate, limiti conosciuti e prossimi passi sono in **[workflow_sviluppo.md](workflow_sviluppo.md)**. Questo README spiega solo come installare, avviare e usare il progetto.

---

## Indice

- [Funzionalità](#funzionalità)
- [Stack](#stack)
- [Struttura del progetto](#struttura-del-progetto)
- [Requisiti](#requisiti)
- [Installazione](#installazione)
- [Avvio](#avvio)
- [Utenti di test](#utenti-di-test)
- [Uso](#uso)
- [Configurazione](#configurazione)
- [Provider AI (opzionale)](#provider-ai-opzionale)
- [API](#api)
- [Test](#test)
- [Risoluzione dei problemi](#risoluzione-dei-problemi)

---

## Funzionalità

- **Chat di diagnosi** per l'operatore: scelta di famiglia e fase, poi descrizione libera del sintomo.
- **Matching fuzzy deterministico** (rapidfuzz): regge refusi, parole in ordine diverso, maiuscole, accenti e punteggiatura.
- **Più ipotesi per lo stesso sintomo**, ordinate per somiglianza.
- **Eccezioni per contesto**: per una combinazione famiglia + fase, causa e soluzione specifiche sostituiscono quelle generiche.
- **Risposta esplicita "nessun dato"** quando non c'è una corrispondenza certa: nessuna procedura inventata.
- **Due ruoli (RBAC)**: `expert` gestisce la knowledge base, `operator` può solo consultarla.
- **Provider AI intercambiabile e spento di default**: `none`, `api` (esterna, compatibile OpenAI) oppure `local` (Ollama). Si sceglie con una variabile in `.env`.

## Stack

| Livello | Tecnologia |
|---|---|
| Backend | Python 3.11+ (sviluppato con 3.12), FastAPI, Uvicorn |
| Database | MySQL 8 / MariaDB, accesso con SQLAlchemy Core + PyMySQL |
| Matching | rapidfuzz |
| Autenticazione | JWT (PyJWT) + bcrypt |
| AI (opzionale) | httpx verso API compatibili OpenAI oppure Ollama |
| Frontend | React 19 + Vite, JavaScript, react-router-dom |
| Test | pytest, pytest-cov, pytest-mock |

## Struttura del progetto

```
dedalo/
├── database/
│   ├── schema.sql              # tabelle, vincoli, indici (ricrea tutto da zero)
│   └── seed.sql                # dati di esempio + utenti demo
├── backend/
│   ├── app/
│   │   ├── main.py             # create_app(): assembla l'applicazione
│   │   ├── config.py           # lettura centralizzata di .env
│   │   ├── db.py               # engine e transazione per richiesta
│   │   ├── dependencies.py     # utente corrente, controllo ruoli
│   │   ├── logging_config.py
│   │   ├── routes/             # endpoint HTTP (sottili)
│   │   ├── schemas/            # validazione input/output (Pydantic)
│   │   ├── services/           # logica di business
│   │   │   ├── matching/       # motore di matching deterministico
│   │   │   └── ai/             # interfaccia AIProvider + backend none/api/local
│   │   ├── repositories/       # query SQL
│   │   └── utils/              # funzioni generiche copiate da function_archive
│   ├── tests/
│   ├── run.py                  # unico punto di avvio del server
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── services/api.js     # unico ponte verso il backend
│   │   ├── components/         # LoginForm, ContextSelector, ChatInput, ChatMessageList, DiagnosisResult
│   │   ├── pages/              # LoginPage, ChatPage
│   │   ├── styles/app.css
│   │   ├── App.jsx             # routing e sessione
│   │   └── main.jsx
│   ├── package.json
│   └── .env.example
├── README.md
└── workflow_sviluppo.md
```

## Requisiti

- **Python 3.11+**, con il modulo `venv`. Su Ubuntu serve il pacchetto `python3.12-venv`.
- **MySQL 8** oppure **MariaDB**.
- **Node.js `^20.19` oppure `>=22.12`**, richiesto da Vite. Il progetto è sviluppato con Node 24 LTS installato tramite [nvm](https://github.com/nvm-sh/nvm). Il pacchetto `nodejs` di Ubuntu 24.04 è la versione 18, troppo vecchia.

## Installazione

Tutti i comandi partono dalla root del progetto, se non indicato diversamente.

### 1. Database

Crea i due database (applicazione e test) e un utente con permessi su entrambi:

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

Crea le tabelle e carica i dati di esempio:

```bash
mysql -u dedalo -p dedalo < database/schema.sql
mysql -u dedalo -p dedalo < database/seed.sql
```

> ⚠️ `schema.sql` **elimina e ricrea** tutte le tabelle: rieseguirlo cancella i dati presenti. Allo stesso modo, modificare `schema.sql` non aggiorna un database già creato: bisogna rieseguirlo da capo oppure applicare a mano un `ALTER TABLE`.

Il database `dedalo_test` non va popolato a mano: i test lo ricreano da soli a ogni esecuzione.

### 2. Backend

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
```

Poi apri `backend/.env` e imposta almeno:

- `DB_USER` e `DB_PASSWORD`, con le credenziali create al passo 1;
- `JWT_SECRET_KEY`, con una chiave casuale generata così:

  ```bash
  python3 -c "import secrets; print(secrets.token_hex(32))"
  ```

Il file `.env` è ignorato da Git e **non va mai committato**.

### 3. Frontend

```bash
cd frontend
npm ci
```

`npm ci` installa esattamente le versioni fissate in `package-lock.json`. Il file `frontend/.env` serve solo se il backend non è su `http://127.0.0.1:8000`: in quel caso crealo da `frontend/.env.example`.

## Avvio

Servono due terminali.

**Backend:**

```bash
cd backend
.venv/bin/python run.py
```

- API: http://127.0.0.1:8000
- Documentazione interattiva (Swagger): http://127.0.0.1:8000/docs

**Frontend (sviluppo):**

```bash
cd frontend
npm run dev
```

Apri **http://localhost:5173**.

Per una build di produzione: `npm run build` genera i file statici in `frontend/dist/`, e `npm run preview` li serve in locale per una prova.

## Utenti di test

Il seed crea due utenti demo, uno per ruolo:

| Ruolo | Username | Password | Cosa può fare |
|---|---|---|---|
| `expert` | `expert_demo` | `expert123` | consulta e modifica la knowledge base (sintomi, cause, soluzioni, eccezioni) |
| `operator` | `operator_demo` | `operator123` | consulta tramite chat, nessuna scrittura |

⚠️ Queste credenziali servono **solo per lo sviluppo locale**. Prima di qualsiasi uso su una linea reale gli utenti demo vanno rimossi o le loro password cambiate.

## Uso

### Chat di diagnosi (entrambi i ruoli)

1. Fai login su http://localhost:5173.
2. Scegli **famiglia di prodotto** e **fase del ciclo**. La casella del messaggio si attiva solo dopo.
3. Descrivi il sintomo e premi Invio. Shift+Invio va a capo.

La risposta può essere:

- **una o più ipotesi**, ordinate per somiglianza. Ognuna mostra componente, causa e soluzione, più il badge *"Specifica per questa fase"* se è intervenuta un'eccezione;
- **"Nessun dato disponibile"**: la knowledge base non ha una diagnosi certa per quel sintomo in quel contesto, e nessuna procedura viene suggerita.

Esempi con i dati del seed:

| Famiglia / fase | Sintomo | Risultato atteso |
|---|---|---|
| Cella di assemblaggio robotizzata / 1. Carico pezzo | `il nastro trasportatore si ferma a intermittenza` | 2 ipotesi generiche |
| Confezionatrice flow-pack / 1. Svolgimento film | `nastro trasportatre si ferma a intermitenza` (con refusi) | 2 ipotesi, la seconda specifica per la fase |
| Cella di assemblaggio robotizzata / 2. Serraggio in pinza | `la pinza del robot non chiude completamente` | 1 ipotesi specifica (sensore di finecorsa) |
| Cella di assemblaggio robotizzata / 3. Avvitatura | `la pinza del robot non chiude completamente` | 1 ipotesi generica (pressione aria) |
| qualsiasi | `il motore fa fumo` | Nessun dato disponibile |

### Gestione della knowledge base (solo `expert`)

Per il PoC non esiste un'interfaccia grafica per l'esperto: la knowledge base si gestisce da **Swagger**.

1. Apri http://127.0.0.1:8000/docs e clicca **Authorize**.
2. Fai login con `expert_demo` / `expert123`.
3. Usa gli endpoint della sezione *knowledge base*:
   - `POST /diagnostics` crea una diagnosi generica;
   - `POST /diagnostics/{diagnostic_id}/exceptions` aggiunge causa e soluzione specifiche per una famiglia e una fase.

Le modifiche sono visibili subito in chat, senza riavviare nulla.

### Ripristinare i dati di esempio

```bash
mysql -u dedalo -p dedalo < database/schema.sql
mysql -u dedalo -p dedalo < database/seed.sql
```

## Configurazione

### Backend: `backend/.env`

Il template completo, commentato, è in [backend/.env.example](backend/.env.example). Le variabili d'ambiente del sistema hanno la precedenza su quelle scritte nel file.

| Variabile | Default | Descrizione |
|---|---|---|
| `DB_HOST` / `DB_PORT` | `localhost` / `3306` | server MySQL |
| `DB_USER` / `DB_PASSWORD` | — (obbligatorie) | credenziali MySQL |
| `DB_NAME` | `dedalo` | database dell'applicazione |
| `DB_TEST_NAME` | `dedalo_test` | database dei test; **deve** essere diverso da `DB_NAME` |
| `JWT_SECRET_KEY` | — (obbligatoria) | chiave di firma dei token; se la cambi, tutti gli utenti devono rifare login |
| `JWT_ALGORITHM` | `HS256` | algoritmo di firma |
| `JWT_EXPIRE_MINUTES` | `480` | durata del token (8 ore, un turno) |
| `MATCH_SCORE_THRESHOLD` | `80` | punteggio minimo (0-100) perché un sintomo sia considerato corrispondente |
| `AI_PROVIDER` | `none` | `none`, `api` oppure `local` (vedi sotto) |
| `AI_API_URL` / `AI_API_KEY` / `AI_API_MODEL` | vuote | solo con `AI_PROVIDER=api` |
| `OLLAMA_BASE_URL` / `OLLAMA_MODEL` | `http://localhost:11434` / vuota | solo con `AI_PROVIDER=local` |
| `CORS_ORIGINS` | `http://localhost:5173` | indirizzi del frontend autorizzati, separati da virgola |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `APP_HOST` | `127.0.0.1` | `0.0.0.0` per rendere il server raggiungibile dalla rete locale |
| `APP_PORT` | `8000` | porta del backend |
| `APP_RELOAD` | `false` | `true` riavvia il server a ogni modifica del codice (solo sviluppo) |

### Frontend: `frontend/.env`

| Variabile | Default | Descrizione |
|---|---|---|
| `VITE_API_URL` | `http://127.0.0.1:8000` | indirizzo del backend |

Le variabili `VITE_*` finiscono dentro il JavaScript scaricato dal browser, quindi sono pubbliche: non metterci mai segreti.

> Se cambi la porta del backend (`APP_PORT`), aggiorna `VITE_API_URL`. Se il frontend gira su un altro indirizzo, aggiungilo a `CORS_ORIGINS`.

## Provider AI (opzionale)

L'AI **non produce mai diagnosi**. Viene usata solo se il testo originale dell'operatore non trova corrispondenze: in quel caso riscrive il sintomo in forma pulita e il matching deterministico viene ripetuto sul testo riscritto. Se l'AI non risponde, l'app dà comunque la risposta deterministica.

| `AI_PROVIDER` | Cosa fa | Note |
|---|---|---|
| `none` (default) | nessuna AI | tutto resta sulla macchina |
| `api` | API esterna compatibile OpenAI (`POST {AI_API_URL}/chat/completions`) | ⚠️ **a pagamento** e il testo dell'operatore **esce dalla rete aziendale**: solo per validare il PoC, mai con dati di produzione |
| `local` | modello servito da [Ollama](https://ollama.com) sull'infrastruttura interna | gratuito, i dati restano in azienda |

Esempio con Ollama in locale:

```bash
ollama pull llama3.2
```

```ini
# backend/.env
AI_PROVIDER=local
OLLAMA_MODEL=llama3.2
```

Esempio con un'API esterna:

```ini
AI_PROVIDER=api
AI_API_URL=https://api.openai.com/v1
AI_API_KEY=...
AI_API_MODEL=...
```

Se manca una variabile obbligatoria per il provider scelto, il backend **non si avvia** e indica quale variabile manca.

## API

Documentazione completa e interattiva su http://127.0.0.1:8000/docs. Tutti gli endpoint, tranne il login, richiedono l'header `Authorization: Bearer <token>`.

| Metodo | Endpoint | Ruolo | Descrizione |
|---|---|---|---|
| POST | `/auth/login` | pubblico | login con form `username` e `password`, restituisce il token |
| GET | `/auth/me` | tutti | utente corrente con il suo ruolo |
| GET | `/families` | tutti | famiglie di prodotto |
| GET | `/families/{family_id}/phases` | tutti | fasi del ciclo di una famiglia |
| POST | `/diagnosis` | tutti | diagnosi di un sintomo in una famiglia e una fase |
| GET | `/diagnostics` | tutti | elenco delle diagnosi generiche |
| GET | `/diagnostics/{diagnostic_id}` | tutti | dettaglio di una diagnosi |
| POST | `/diagnostics` | expert | crea una diagnosi |
| PUT | `/diagnostics/{diagnostic_id}` | expert | sostituisce una diagnosi |
| DELETE | `/diagnostics/{diagnostic_id}` | expert | elimina una diagnosi e le sue eccezioni |
| GET | `/diagnostics/{diagnostic_id}/exceptions` | tutti | eccezioni di una diagnosi |
| POST | `/diagnostics/{diagnostic_id}/exceptions` | expert | crea un'eccezione per famiglia + fase |
| PUT | `/diagnostics/{diagnostic_id}/exceptions/{exception_id}` | expert | sostituisce un'eccezione |
| DELETE | `/diagnostics/{diagnostic_id}/exceptions/{exception_id}` | expert | elimina un'eccezione |

Esempio di richiesta di diagnosi:

```json
POST /diagnosis
{ "symptom": "la pinza del robot non chiude completamente", "family_id": 1, "cycle_phase_id": 2 }
```

Il campo `status` della risposta vale `match` oppure `no_match`. Chi usa l'API deve sempre decidere cosa fare in base a questo campo.

**Codici di stato:**

| Codice | Significato |
|---|---|
| `200` | ok, anche per `no_match`: è una risposta prevista, non un errore |
| `201` | risorsa creata |
| `400` | richiesta non valida: body malformato, credenziali errate, fase che non appartiene alla famiglia |
| `401` | token mancante, scaduto o non valido |
| `403` | ruolo insufficiente (es. un `operator` che prova a scrivere) |
| `404` | risorsa non trovata |
| `409` | conflitto: esiste già un'eccezione per quella diagnosi in quella fase |

## Test

### Backend

I test usano il database `dedalo_test`, che deve esistere (vedi [Installazione](#1-database)). Viene ricreato da `schema.sql` + `seed.sql` a ogni esecuzione, e ogni test annulla le proprie modifiche alla fine. `dedalo` non viene mai toccato.

```bash
cd backend
.venv/bin/python -m pytest                                          # tutta la suite
.venv/bin/python -m pytest --cov=app --cov-report=term-missing      # con copertura
.venv/bin/python -m pytest tests/test_fuzzy_matcher.py tests/test_text_normalizer.py   # solo matching, senza database
```

Nessun test chiama servizi esterni: i provider AI sono testati con un trasporto HTTP simulato.

### Frontend

```bash
cd frontend
npm run lint     # oxlint
npm run build    # verifica che l'app compili
```

## Risoluzione dei problemi

| Problema | Soluzione |
|---|---|
| `ensurepip is not available` alla creazione del venv | `sudo apt install python3.12-venv`, poi `python3 -m venv --clear .venv` |
| `node: command not found` in un nuovo terminale | chiudi e riapri il terminale, oppure esegui `source ~/.nvm/nvm.sh` |
| Il frontend mostra "Server non raggiungibile" | il backend non è avviato, oppure `VITE_API_URL` punta all'indirizzo sbagliato |
| Errore CORS nella console del browser | aggiungi l'indirizzo del frontend a `CORS_ORIGINS` e riavvia il backend |
| `address already in use` sulla porta 8000 | c'è già un backend avviato: chiudilo oppure cambia `APP_PORT` (e `VITE_API_URL`) |
| `AI_PROVIDER=... requires these variables in .env` all'avvio | imposta le variabili indicate oppure torna a `AI_PROVIDER=none` |
| `DB_TEST_NAME must differ from DB_NAME` nei test | protezione voluta: i test non devono mai girare sul database dell'applicazione |
| `Access denied for user 'dedalo'@'localhost'` | controlla `DB_USER` e `DB_PASSWORD` in `backend/.env` e i `GRANT` del passo 1 |
| Tutti gli utenti vengono disconnessi | è cambiata `JWT_SECRET_KEY` oppure il token è scaduto (`JWT_EXPIRE_MINUTES`): basta rifare login |
| Warning `StarletteDeprecationWarning ... install httpx2` nei test | viene da una libreria, non dal progetto: per ora non serve fare nulla (vedi [workflow_sviluppo.md](workflow_sviluppo.md#limiti-conosciuti)) |
