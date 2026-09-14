# Dedalo — Brief di progetto (PoC)
 
## Contesto e obiettivo
 
Dedalo è un assistente di troubleshooting guidato per impianti e linee produttive ad alta complessità meccatronica. Aiuta operatori e manutentori a diagnosticare guasti tramite una diagnostica incrementale (stile albero decisionale), contestualizzata su **Famiglia di Prodotto** e **Fase del Ciclo di Lavoro**.
 
Obiettivo: colmare il gap tra le AI generaliste (che non conoscono l'impianto specifico) e la conoscenza reale di fabbrica, riducendo MTTD/MTTR e la dipendenza dai tecnici specializzati.

 
## Vincoli architetturali fondamentali
 
- **Offline-first**: l'applicazione deve girare interamente in locale, senza dipendenze da API cloud esterne. Se in futuro si aggiungerà un componente AI per il matching semantico, dovrà essere un modello eseguito localmente (es. Ollama, sentence-transformers) ospitabile sull'infrastruttura interna dell'azienda — mai un servizio SaaS esterno. I dati di una linea produttiva non devono lasciare la rete aziendale.
- **Determinismo prima della complessità NLP**: il motore di matching sintomo→diagnosi parte da un approccio a regole/fuzzy matching (nessun LLM in questa fase), per validare l'utilità del sistema prima di introdurre complessità semantica. L'architettura deve restare estendibile per aggiungere in futuro un livello semantico locale, senza richiedere un refactor totale.
- **RBAC**: due ruoli.
  - `expert`: può creare/modificare sintomi, cause, soluzioni (popola la knowledge base).
  - `operator`: solo consultazione tramite chat, nessuna scrittura.
- **Fallback anti-allucinazione**: se una combinazione sintomo/fase non trova corrispondenze certe nel DB, il sistema deve dichiarare l'assenza di dati, mai inventare una procedura.


## Livello di astrazione per il provider AI
 
Ad oggi non è disponibile un modello locale: nella fase di test/validazione si useranno API esterne (es. OpenAI, Anthropic). In produzione su linea, l'obiettivo è passare a un modello ospitato sull'infrastruttura interna dell'azienda. Lo switch tra le due modalità deve richiedere **solo una modifica di configurazione** (una variabile in `.env`), non un refactor del codice: il resto dell'applicazione non deve mai dipendere direttamente da quale backend AI è attivo.
 
- Definire un'interfaccia comune (es. `AIProvider`, classe base astratta) con un metodo per l'operazione richiesta (es. interpretare/normalizzare il testo libero dell'operatore, o generare la prossima domanda di disambiguazione).
- Implementare almeno due backend concreti dietro questa interfaccia:
  - `ApiAIProvider`: chiama un'API esterna (chiave letta da `.env`, mai committata).
  - `LocalAIProvider`: predisposto per un modello locale (es. via Ollama) — anche solo come stub/placeholder funzionante per ora, da completare quando il modello locale sarà disponibile.
- La selezione del provider avviene tramite una variabile in `.env` (es. `AI_PROVIDER=api` oppure `AI_PROVIDER=local`), letta da una funzione factory che istanzia l'implementazione corretta. Il resto dell'applicazione lavora sempre contro l'interfaccia `AIProvider`, mai contro l'implementazione concreta.
- Nota per la fase di test: usare un'API esterna significa inviare fuori dall'azienda i testi inseriti dagli operatori. Va bene per validare il PoC, ma è proprio per questo che lo switch a locale deve essere pronto prima di un utilizzo reale in linea con dati di produzione sensibili.


## Stack tecnologico
 
- Backend: Python 3.11+, FastAPI
- Database: MySQL/MariaDB
- Matching engine: fuzzy/keyword matching (es. `rapidfuzz`, o full-text search nativo MySQL) — nessuna dipendenza da LLM in questa fase
- Frontend: React (con Vite), interfaccia semplice tipo chat — l'estetica non è prioritaria, la priorità è la funzionalità
- Test: pytest


## Schema del database
 
Tabelle richieste (nomi in inglese, coerenti con lo standard del codice), con chiavi esterne e indici opportuni:
 
- `users` (id, username, password_hash, role ENUM('expert','operator'), created_at)
- `product_families` (id, family_name, description)
- `cycle_phases` (id, family_id FK, phase_number, phase_name)
- `base_diagnostics` (id, symptom_description, affected_component, probable_cause, recommended_solution, created_by FK → users, created_at, updated_at)
  - può esistere più di una riga con lo stesso `symptom_description` associata a cause/soluzioni diverse
  - indice FULLTEXT su `symptom_description` per supportare il matching
- `diagnostic_exceptions` (id, base_diagnostic_id FK, family_id FK, cycle_phase_id FK, specific_cause, specific_solution, created_by FK → users, created_at, updated_at)
  - valutare un vincolo/trigger che garantisca coerenza tra `family_id` e la famiglia effettiva di `cycle_phase_id` (una fase appartiene già a una famiglia specifica in `cycle_phases`)


## Dati di esempio (seed.sql)
 
- 2 famiglie di prodotto con relative fasi del ciclo
- 3 scenari di guasto meccatronico (con almeno un caso che mostra due righe con stesso sintomo e causa/soluzione diverse)
- 1 utente `expert` e 1 utente `operator` di esempio


## Test
 
- Suite pytest per il motore di matching, usando i dati di seed come casi di test noti (dato un sintomo + famiglia + fase, verificare che venga restituita la diagnosi attesa, o l'assenza di match quando previsto)
- Test per i controlli RBAC (un `operator` non deve poter scrivere sulla knowledge base)
- Non serve una coverage estesa in questa fase esplorativa: priorità a matching engine e permessi, che sono la logica di business core


## Cosa devi fare ora
 
1. Proponi la struttura delle cartelle del progetto (backend FastAPI + frontend React separati)
2. Genera `schema.sql` e `seed.sql` secondo le specifiche sopra
3. Genera `requirements.txt` (backend) e la configurazione base del progetto React (frontend)
4. Scrivi il modulo di matching sintomo→diagnosi con relativa suite di test pytest
5. Definisci l'interfaccia `AIProvider` e le due implementazioni (`ApiAIProvider`, `LocalAIProvider`), con la factory per la selezione via `.env`
6. Scrivi gli endpoint FastAPI necessari (matching per l'operatore, gestione knowledge base per l'utente `expert`, autenticazione/ruoli)
7. Scrivi lo scaffolding base del frontend React (interfaccia chat minimale, senza cura estetica particolare in questa fase)
8. Procedi in modo modulare: commenta solo la logica non standard, type hints ovunque, docstring Google-style in inglese
