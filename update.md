# Dedalo — Piano di sviluppo Fase 1 (update.md)

Piano di modifica del software per rendere Dedalo utilizzabile da un cliente reale, partendo dallo stato v2 descritto nel `README.md`. Le fasi successive (sensori, anomalie, notifiche, riaddestramento) sono in `roadmap_sensori.md` e si dettagliano solo a Fase 1 conclusa.

Data: 12 novembre 2026. Verificato sul codice il 12 novembre 2026.

---

## 0. Come leggere questo documento

- Ogni punto ha: **perché**, **stato attuale** (verificato nel codice), **cosa fare**, **decisioni prese**, **criteri di accettazione**.
- Gli schemi di tabella sono proposte logiche: i tipi reali seguono `schema.sql` (MySQL: `INT UNSIGNED`, `ENGINE=InnoDB`, `utf8mb4`) e `sqlite/schema.sql` (`INTEGER PRIMARY KEY AUTOINCREMENT`). Dopo il punto 1.1 vivono solo nelle migrazioni.
- Convenzioni di progetto da rispettare: nomi in inglese `snake_case`, relazioni molti-a-molti con tabella ponte, codici HTTP coerenti (200/201/400/404/409/500).

### 0.1 Decisioni già prese (da te, 12 novembre 2026)

| Tema | Decisione |
|---|---|
| Migrazioni | **Alembic**, con modalità batch per SQLite |
| Fonte di verità dello schema | **Solo le migrazioni**: `schema.sql` (MySQL e SQLite) viene eliminato |
| Ambito del documento | Solo Fase 1; Fasi 2-5 in `roadmap_sensori.md` |
| Validazione diagnosi | **Qualsiasi `expert`, anche l'autore** |
| Registro consultazioni | `user_id` salvato, **disattivabile con variabile `.env`** |
| Esito di una consultazione | Modificabile, **sovrascrive** (con `updated_at`) |
| Impianti | **Gerarchia** con `parent_id`: `plant` → `line` → `station` → `machine`. La **macchina è figlia di una stazione** (una stazione contiene più macchine: pressa, robot, assemblaggio, convogliatore). La **linea è impostata all'installazione** (flusso `/setup`) e non si cambia dall'interfaccia. **Stazione e macchina le seleziona l'operatore** in chat (obbligatorio) |
| Linea e stabilimento: correzione futura | Oltre al `/setup`, **variabili `.env`** (`LINE_CODE`, `LINE_NAME`, `PLANT_CODE`, `PLANT_NAME`) lette all'avvio: se presenti e diverse dal database **aggiornano la riga esistente** (stesso `id`, contatori validi) e il cambio va nel log. **Solo server**, non desktop. Stabilimento impostato nel `/setup` insieme alla linea, può non essere unico nel mondo (stesso stabilimento su più installazioni). Il cambio del codice della linea non invalida i CSV già esportati |
| Regola sugli impianti | Una macchina non esiste senza stazione, una stazione non senza linea (vincolo nel service e nel form). Le diagnosi restano come oggi, con componente facoltativo |
| Selezione in chat | La scelta di stazione e macchina **restringe i candidati**: entrano le diagnosi collegate alla macchina scelta e quelle senza componente o con componente generico; sono escluse quelle collegate a un'altra macchina. Tolta la colonna `assets.family_id`, ridondante con la famiglia scelta a mano |
| Compatibilità di `/diagnosis` | `station_asset_id`, `machine_asset_id` e `family_id` sono **facoltativi nell'API** (senza, nessun filtro, come oggi); sono obbligatori solo nell'interfaccia (salvo "all" per la famiglia) |
| Database già esistenti | La chat **resta bloccata** finché la linea non è impostata |
| Famiglia in chat | **Scelta a mano**, con valore predefinito **"all"** = solo diagnosi **generiche** (`family_id` vuoto, come oggi). Con "all" la fase non è selezionabile. `family_id` di `/diagnosis` diventa facoltativo |
| Contatori | La dimensione **linea resta** (dà il totale degli eventi) |
| Utenti / catalogo | Cambio password, reset da `expert`, `is_active`, limite tentativi login **e** gestione famiglie/fasi da interfaccia |
| Desktop | Valgono **tutte** le funzioni di 1.1-1.5, 1.7-1.8, **tranne** la correzione di linea e stabilimento da `.env` (solo server). Le funzioni di 1.6 (utenti, Docker, deploy) riguardano il server |
| Deploy server | **Docker Compose** (backend + MySQL + proxy) più `DEPLOY.md` |
| Colonna `role` | **Unificata** in `VARCHAR` + `CHECK` su MySQL e SQLite |
| Conservazione del registro | Nessuna pulizia automatica: i dati restano finché un `expert` li analizza e li elimina |
| Eliminazione delle sessioni | Una alla volta, solo `expert`. **Automatica** quando dalla ricerca si crea una diagnosi; con pulsante *Scarta* altrimenti |
| Statistiche d'uso | **Tabella separata di contatori aggregati** che non si elimina mai; aggiornata **al momento dell'eliminazione** della sessione; dimensioni: giorno, famiglia, fase, linea, stazione, esito, stato, confidenza, diagnosi risolutiva |
| Esportazione sessioni | Pulsante **Esporta in CSV** nella pagina Report, da usare prima di eliminare |
| Nuova diagnosi creata a mano | **Pop-up** all'`expert`: convalidare subito o lasciare in revisione (`draft`) |
| Tentativi di login falliti | **Nessun blocco account né ritardo** (LAN di produzione, rischio accettato). Contatore in memoria; dal 5° tentativo fallito compare un avviso, che si rivede anche al primo accesso riuscito (vedi 1.6) |
| Modifica di una diagnosi `validated` | Compare di nuovo il **pop-up** (convalida subito / lascia in revisione) |
| Sintomi quasi duplicati (CSV) | Confronto con gli **embedding** |
| Test frontend | **Vitest + React Testing Library** già in questa fase |
| Reverse proxy | **nginx** (confermato) |
| Ordine dei lavori | Quello della sezione 3 |

### 0.2 Invarianti (non cambiano mai)

Se un punto sembra violarne uno, vince l'invariante.

1. **Causa e soluzione arrivano sempre e solo dalla knowledge base.** Nessun testo diagnostico viene generato.
2. **La diagnosi è deterministica.** Ordine e probabilità derivano dai punteggi, mai da un LLM.
3. **L'LLM è facoltativo e validato.** Con `AI_PROVIDER=none` l'app resta completa e offline.
4. **Nessuna scrittura verso la macchina** (nessun comando a PLC o attuatori).
5. **Doppio backend database.** Ogni modifica allo schema funziona su MySQL e su SQLite, e i test che usano il database girano su entrambi.
6. **Compatibilità.** API e CSV esistenti restano validi: i nuovi campi sono facoltativi.

### 0.3 Stato attuale verificato nel codice

| Cosa | Risultato |
|---|---|
| Migrazioni | Non esistono. Alembic non è in `requirements.txt`. `schema.sql` fa `DROP TABLE` e ricrea tutto. |
| Dove si usa `schema.sql` | `backend/desktop/paths.py` (percorso `sqlite_schema`), `database/sqlite/schema.sql` nel `packaging/windows/dedalo.spec`, `backend/desktop/database.py`, `tests/test_desktop.py` (riga 127), e il README per MySQL. Tutti vanno aggiornati al punto 1.1. |
| Tabella `diagnostics` | Colonne: `symptom_description`, `affected_component`, `probable_cause`, `recommended_solution`, `family_id`, `cycle_phase_id`, `created_by`, `created_at`, `updated_at`. Mancano `updated_by`, `component_id`, `validation_status`. |
| Tabella `users` | Colonne: `username`, `password_hash`, `role`, `created_at`. **Manca `is_active`.** MySQL usa `ENUM('expert','operator')`, SQLite un `CHECK`. |
| Conversazione | `DiagnosisRequest` (`schemas/diagnosis.py`) non ha un identificativo. Lo stato sta in `ChatPage.jsx`. Nuova conversazione = cambio di contesto o pulsante dedicato. |
| Ruolo | `dependencies.py` rilegge già l'utente dal database a ogni richiesta (RBAC corretto). `is_active` va aggiunto a quel controllo. |
| Cache embedding | Lavora per testo. Il filtro `draft` non va nella cache ma nel caricamento dei candidati (`list_candidates`, `diagnostics_repository`). |
| Limiti già noti (`workflow_sviluppo.md`, sez. 10) | Nn. 12, 13, 14, 15 sono coperti da questo piano. Il n. 7 (nessun pre-filtro oltre qualche migliaio di righe) **non** lo è. |

---

## 1. Fase 1 — Dedalo come prodotto dal giorno 0

Obiettivo: il cliente installa Dedalo, gli esperti caricano le competenze, gli operatori consultano; intanto Dedalo registra ciò che servirà dopo.

### 1.1 Migrazioni dello schema (prerequisito di tutto)

**Perché.** Con dati reali di un cliente non si può ricreare lo schema da zero a ogni aggiornamento.

**Cosa fare.**
1. Aggiungere `alembic` a `backend/requirements.txt` (versione fissata) e creare `backend/migrations/` con `env.py` che legge la stessa configurazione di `app/config.py` (stesso `DB_BACKEND`).
2. Migrazione `0001_baseline` che riproduce lo schema v2 attuale (tabelle `users`, `product_families`, `cycle_phases`, `diagnostics` con tutti i vincoli e indici, anche i `CHECK` e le FK composite).
3. Modalità batch (`render_as_batch=True`) per SQLite.
4. Comando per il server, documentato nel README (es. `alembic upgrade head`). Desktop: migrazione automatica all'avvio in `desktop/database.py`, preceduta da copia di `dedalo.db` (`dedalo.db.bak-<data>`), segnalata nel log.
5. Un database v2 **già esistente** (creato da `schema.sql`) va "marcato" come `0001` (`alembic stamp`) senza rieseguire la migrazione. Il desktop deve riconoscere questo caso da solo.
6. Sostituire tutti gli usi di `schema.sql` elencati in 0.3: `paths.py`, `database.py`, `dedalo.spec` (che deve includere la cartella `migrations/`), `test_desktop.py`, `conftest.py` e README. I test e i DB nuovi partono eseguendo tutte le migrazioni.
7. Eliminare `database/schema.sql` e `database/sqlite/schema.sql` **solo dopo** che tutto il resto passa. L'eliminazione richiede la tua autorizzazione esplicita nel momento in cui viene eseguita.
8. `seed.sql` e `seed_catalog.sql` restano come script di dati (non di struttura).

**Rischi da conoscere.**
- `render_as_batch` su SQLite ricrea la tabella a ogni modifica: le FK composite di `diagnostics` vanno verificate dopo ogni migrazione (`PRAGMA foreign_key_check`).
- `role` oggi è `ENUM` su MySQL e `CHECK` su SQLite. La migrazione `0001_baseline` lo trasforma in `VARCHAR(10)` + `CHECK (role IN ('expert','operator'))` su entrambi, così le migrazioni future sono identiche. Sui database v2 già esistenti la conversione `ENUM` → `VARCHAR` va verificata su un database MySQL con dati (il valore resta lo stesso, ma si controlla che l'ordine delle colonne e le FK non cambino).

**Criteri di accettazione.**
- [ ] Un database v2 con dati passa alla versione successiva senza perdite.
- [ ] La stessa migrazione gira su MySQL e su SQLite (test dedicato su entrambi).
- [ ] L'app desktop crea il backup prima di migrare e lo scrive nel log.
- [ ] Installazione nuova (test, desktop, server) = solo migrazioni, nessun `schema.sql` nel repository.

### 1.2 Anagrafica impianti e componenti

**Perché.** `affected_component` è testo libero (150 caratteri). Un identificativo stabile serve per filtrare per macchina reale e, nelle fasi future, per collegare sensori ed eventi.

**Cosa fare.** Nuova migrazione con:

| Tabella | Colonne principali | Note |
|---|---|---|
| `assets` | `id`, `parent_id` (FK su `assets`, nullable), `asset_type`, `code` (univoco), `name`, `is_active`, `created_at`, `updated_at` | Gerarchia stabilimento (`plant`) → linea (`line`) → stazione (`station`) → macchina (`machine`): la macchina è figlia di una stazione. `asset_type` `VARCHAR` con `CHECK` (no `ENUM`). La riga di tipo `line` è unica e immutabile (vedi sotto). |
| `components` | `id`, `asset_id` (FK nullable), `code` (univoco), `name`, `is_active`, `created_at`, `updated_at` | `asset_id` vuoto = componente generico, valido per più macchine. |

- `diagnostics.component_id`: FK nullable verso `components`. **`affected_component` resta**, come testo mostrato all'operatore.
- Cicli nella gerarchia: un asset non può avere sé stesso o un suo discendente come padre (controllo nel service, errore 400).
- CSV: colonna facoltativa `component_code`. Vuota = comportamento attuale; compilata ma inesistente = errore di riga (regola "un errore blocca tutto il file").
- API (scrittura solo `expert`): `GET/POST/PUT /assets`, `GET/POST/PUT /components`. Niente `DELETE` fisico: si usa `is_active`.
- Frontend: pagina *Impianti* (albero) per l'esperto; selettore del componente accanto al testo libero nel form diagnosi; selezione di **stazione e macchina in chat** (obbligatoria nell'interfaccia; la linea non si sceglie perché è unica per installazione). Serve al registro di 1.3 **e restringe i candidati del matching** (vedi sotto).
- **Linea immutabile dall'interfaccia:** esiste una sola riga `line` per installazione, impostata all'installazione. Il servizio rifiuta ogni modifica, disattivazione o eliminazione di quella riga (errore 409), e un test lo verifica. Viene impostata nel flusso `/setup`, che si estende con codice e nome di stabilimento (`plant`) e linea (`line`): la linea è figlia dello stabilimento. Le variabili `.env` (`PLANT_CODE`, `PLANT_NAME`, `LINE_CODE`, `LINE_NAME`, in `.env.example`) servono solo allo sviluppatore per correggerle: all'avvio, se presenti e diverse dal database, aggiornano le righe esistenti (stesso `id`) e la modifica va nel log. Solo server.
- **Database già esistenti** (nessuna linea): l'`expert` la imposta al primo accesso con una schermata una tantum (stabilimento e linea) e **la chat resta bloccata finché non è impostata**. Come avviene il primo avvio sul desktop va verificato nel codice (`desktop/launcher.py`) prima di implementare.
- **Selezione in chat a cascata:** prima la stazione, poi le macchine di quella stazione. Entrambe obbligatorie nell'interfaccia. Il componente (`components.asset_id`) può puntare solo a un asset di tipo `machine` (controllo nel service, errore 400), perché il filtro lavora per macchina.
- **Creazione guidata:** l'`expert` non può creare una macchina senza stazione né una stazione senza linea (decisione presa: la regola riguarda gli impianti, non le diagnosi). Se la stazione o la macchina che serve non esiste, il form della diagnosi offre *Crea qui* (prima la stazione, poi la macchina al suo interno) senza uscire dal form. Le situazioni comuni a tutta la linea (es. il trasportatore pallet) si scrivono come diagnosi generiche (famiglia vuota), come oggi.
- **Filtro sui candidati.** Oggi `list_candidates` filtra per famiglia e fase; il piano aggiunge il filtro per macchina, che resta deterministico (invariante 2). Con una macchina selezionata:
  1. le diagnosi **collegate a quella macchina** (tramite `component_id`) entrano;
  2. le diagnosi **senza componente** o con **componente generico** (`asset_id` vuoto) entrano sempre: valgono per tutte le macchine, come oggi;
  3. le diagnosi collegate a **un'altra macchina** sono escluse, anche se della stessa stazione.
  La stazione non filtra da sola: la macchina è figlia di una stazione, quindi la stazione serve al registro. Il filtro non toglie nulla finché l'esperto non collega le diagnosi ai componenti.
- **Schema API:** `DiagnosisRequest` riceve `station_asset_id` e `machine_asset_id` **facoltativi** (senza, nessun filtro: i client e i test esistenti restano validi, invariante 6) e `family_id` diventa facoltativo (vedi sotto). L'obbligatorietà vale nell'interfaccia.
- **Famiglia "all":** con `family_id` assente restano candidate solo le diagnosi **generiche** (`family_id` vuoto), come oggi; la fase non è selezionabile (una fase appartiene sempre a una famiglia).
- Seguire l'ordine bottom-up: repository → service → route → schema → servizio frontend → componenti → pagina.

**Criteri di accettazione.**
- [ ] Le diagnosi esistenti funzionano con `component_id` vuoto.
- [ ] Una chiamata a `/diagnosis` senza `station_asset_id`, `machine_asset_id` e `family_id` si comporta come oggi (test di non regressione).
- [ ] Filtro per macchina: collegate alla macchina e senza componente entrano, collegate ad altra macchina no (test sul repository, su MySQL e SQLite).
- [ ] Con `family_id` assente entrano solo le diagnosi generiche.
- [ ] La riga `line` non si modifica, disattiva o elimina dall'API (409).
- [ ] Una macchina senza stazione o una stazione senza linea viene rifiutata (400).
- [ ] `.env` con linea o stabilimento diversi aggiorna le righe esistenti e scrive nel log.
- [ ] Senza linea la chat è bloccata e l'`expert` vede la schermata di impostazione.
- [ ] Import/export CSV funzionano con e senza la colonna (test su file v2 esistenti).
- [ ] Un codice di componente o asset non si riusa dopo la disattivazione.
- [ ] Un ciclo nella gerarchia viene rifiutato con 400.

### 1.3 Registro delle consultazioni e degli esiti

**Perché.** Primo ciclo di feedback: quali guasti capitano, quali diagnosi funzionano, dove la knowledge base ha buchi. Chiude il limite 12 di `workflow_sviluppo.md`.

**Stato attuale.** `POST /diagnosis` è senza stato e senza identificativo di conversazione.

**Cosa fare.**
- Il frontend genera un `conversation_id` (UUID) a ogni *Nuova conversazione* e lo invia in `/diagnosis`. Campo **facoltativo**: senza, il comportamento è identico a oggi e non si registra nulla.
- Tabelle (nuova migrazione):

| Tabella | Colonne principali |
|---|---|
| `diagnosis_sessions` | `id`, `conversation_id` (univoco), `user_id` (nullable), `family_id` (nullable: "all"), `cycle_phase_id` (nullable), `machine_asset_id` (nullable), `station_asset_id` (nullable), `started_at`, `last_status`, `last_confidence`, `outcome`, `resolved_diagnostic_id` (nullable), `outcome_note`, `outcome_updated_at`, `closed_at` |
| `diagnosis_turns` | `id`, `session_id`, `turn_index`, `operator_text`, `status`, `confidence`, `mode`, `ai_fallback`, `hypotheses_json`, `unknown_probability`, `created_at` |

- `outcome` da elenco chiuso (`open`, `resolved`, `not_resolved`, `escalated`) con `CHECK`.
- `POST /diagnosis/sessions/{conversation_id}/outcome`: l'esito è **modificabile e sovrascrive** (aggiorna `outcome_updated_at`). Se la sessione non esiste: 404.
- Il `conversation_id` e gli id di stazione e macchina si salvano sulla sessione solo se inviati dal client.
- Frontend: tre pulsanti sotto le ipotesi (*Risolto con questa ipotesi* / *Non risolto* / *Ho chiamato l'esperto*), nota facoltativa.
- Il salvataggio del log **non deve mai far fallire la diagnosi**: errore di scrittura → si registra nel log applicativo e si risponde comunque.
- Privacy: variabile `.env` (nome da definire, es. `LOG_USER_ID`, default attivo) per salvare `user_id` oppure `NULL`. Va in `.env.example`, nella tabella del README e nella guida di deploy. Non è un parere legale: il cliente valuta con i suoi referenti.
- Conservazione: nessuna pulizia automatica. I dati restano finché un `expert` li analizza ed elimina. Servono quindi `DELETE /diagnosis/sessions/{conversation_id}` (solo `expert`, elimina anche i turni collegati) e, nella pagina *Report* (1.4), un pulsante *Elimina* per sessione. L'eliminazione è **solo manuale, una sessione alla volta, in mano all'`expert`**: nessuna eliminazione in blocco né segno "già analizzata" (decisione presa). Una sessione analizzata viene eliminata in uno di due modi: l'`expert` ne ricava una diagnosi (*Crea diagnosi da questa ricerca*, 1.4) oppure la scarta. Le statistiche non dipendono dalle sessioni eliminate perché vivono in una tabella separata di contatori aggregati (decisione presa, opzione C). Gli indicatori d'uso (1.4) sono la somma dei contatori e delle sessioni ancora presenti.
- **Tabella `usage_counters`** (nella stessa migrazione di 1.3), una riga per combinazione di: `stat_date` (giorno di inizio della sessione), `family_id`, `cycle_phase_id`, `line_asset_id`, `station_asset_id`, `outcome`, `last_status` (`hypotheses`/`no_match`), `last_confidence` (`high`/`low`/nessuna), `resolved_diagnostic_id`, più il campo `session_count`. Chiave `UNIQUE` su tutte le dimensioni.
- **Valore al posto di `NULL`:** in MySQL e SQLite un `UNIQUE` non considera uguali due `NULL`, quindi le dimensioni opzionali (fase, linea, stazione, diagnosi risolutiva, confidenza) si memorizzano con `0` (o testo `none`) quando mancano, e non hanno FK. Questo permette l'upsert (`INSERT … ON DUPLICATE KEY UPDATE` su MySQL, `INSERT … ON CONFLICT` su SQLite: due sintassi, da isolare in un solo punto del repository).
- **Quando si scrive (decisione presa):** solo quando la sessione viene eliminata (*Scarta*, o creazione di una diagnosi dalla ricerca). La sessione viene "versata" nei contatori nella stessa transazione dell'eliminazione. L'esito modificabile non crea problemi: conta l'ultimo valore.
- **Linea e stazione:** la stazione è presa direttamente da `station_asset_id` della sessione. La linea è quella unica dell'installazione (non cambia mai); resta tra le dimensioni dei contatori (decisione presa) e dà il totale degli eventi. Gli id restano nei contatori anche se l'asset viene poi disattivato (mai eliminato, 1.2). La macchina non è una dimensione dei contatori (decisione presa), ma è salvata nella sessione.
- **Esportazione:** `GET /diagnosis/sessions/export` (solo `expert`) restituisce le sessioni ancora presenti in CSV (testi, ipotesi, esito, famiglia, fase, linea, stazione, data), filtrabili per periodo, con il pulsante *Esporta in CSV* nella pagina Report. È pensato per essere usato **prima** di eliminare, per conservare i testi utili alla calibrazione (1.7).
- Eliminazione alla creazione della diagnosi: il form di creazione (1.5) riceve il campo facoltativo `source_conversation_id`. Il backend crea la diagnosi e elimina la sessione (e i suoi turni) **nella stessa transazione**: se la creazione fallisce non si elimina nulla. Se l'`expert` sceglie *Lascia in revisione* nel pop-up, la diagnosi viene creata `draft` e la sessione viene comunque eliminata (la ricerca è già stata trasformata in una voce). Se l'`expert` annulla il form, la sessione resta.
- Pulsante *Scarta* sulla sessione (con conferma): elimina senza creare nulla. Anche questa eliminazione aggiorna i contatori.
- Dato che i testi restano a tempo indeterminato, `DEPLOY.md` e il README devono dirlo chiaramente (il cliente può averne bisogno per le proprie valutazioni sulla privacy).

**Criteri di accettazione.**
- [ ] Senza `conversation_id` la risposta di `/diagnosis` è identica a oggi (test di non regressione).
- [ ] Ogni turno salva testo, esito e ipotesi mostrate.
- [ ] Con l'opzione privacy disattivata `user_id` è sempre `NULL`.
- [ ] Un errore di scrittura del log non produce un 500 su `/diagnosis`.
- [ ] Test su MySQL e SQLite.

### 1.4 Report dei buchi della knowledge base e indicatori d'uso

**Perché.** Le ricerche finite in `no_match` o `confidence=low` sono l'elenco di ciò che gli esperti devono ancora scrivere.

**Cosa fare.**
- `GET /reports/unanswered` (solo `expert`): ricerche con `status=no_match` o `confidence=low`, filtri per periodo, famiglia, macchina.
- `GET /reports/usage`: consultazioni, quota per esito, diagnosi più usate, diagnosi mai usate, quota `no_match`. I dati vengono dalla tabella `usage_counters` di 1.3 (sessioni già eliminate) più le sessioni ancora presenti; filtri anche per stazione e linea.
- Pulsante *Crea diagnosi da questa ricerca* che apre il form con il sintomo precompilato; al salvataggio la sessione di origine viene eliminata (vedi 1.3). Accanto, il pulsante *Scarta*.
- Pagina *Report* (solo `expert`) con esportazione CSV.

**Criteri di accettazione.**
- [ ] Il report si basa solo sui dati di 1.3 (sessioni e contatori).
- [ ] Dopo l'eliminazione di una sessione gli indicatori d'uso non cambiano (test dedicato).
- [ ] Creazione diagnosi + eliminazione sessione sono atomiche (test: errore nella creazione → sessione intatta).
- [ ] Gli indicatori sono calcolati con query, non nel frontend.
- [ ] Funziona su MySQL e SQLite (attenzione alle funzioni data, diverse tra i due).

### 1.5 Tracciabilità e validazione delle diagnosi

**Perché.** Con più esperti serve sapere chi ha cambiato cosa; oggi un'eliminazione non si annulla (limite 14).

**Cosa fare.**
- Su `diagnostics`: aggiungere `updated_by` (FK su `users`). `created_by`, `created_at`, `updated_at` esistono già. Valorizzare `updated_by` su ogni modifica e import.
- Tabella `diagnostics_history`: copia della riga a ogni modifica o eliminazione, con autore, data e tipo di operazione (`create`/`update`/`delete`/`import`). Nessun ripristino automatico in questa fase: lo storico si consulta.
- `validation_status` (`draft`, `validated`, con `CHECK`). Migrare le righe esistenti a `validated`.
- **Chi valida**: qualsiasi `expert`, anche l'autore (decisione presa). Alla creazione di una diagnosi dal form l'`expert` vede un **pop-up** con due scelte: *Convalida subito* (`validated`) o *Lascia in revisione* (`draft`). Le diagnosi caricate da CSV massivo entrano come `draft`. Lo stesso pop-up compare anche alla **modifica** di una diagnosi già `validated`: se l'`expert` sceglie *Lascia in revisione*, la diagnosi torna `draft` e sparisce dalla chat fino alla riconvalida.
- Gli operatori vedono in chat solo le `validated`: filtro in `list_candidates`. Ogni modifica resta visibile subito in chat (comportamento attuale).
- API: `POST /knowledge-base/{id}/validate` (solo `expert`).
- Frontend: stato e filtro "da validare" nella tabella; pulsante *Valida*; vista dello storico di una diagnosi.

**Criteri di accettazione.**
- [ ] Ogni creazione, modifica, eliminazione e import lascia una riga nello storico.
- [ ] Una diagnosi `draft` non compare mai nelle ipotesi (test dedicato sul servizio di diagnosi).
- [ ] L'export CSV include lo stato; l'import lo accetta come colonna facoltativa.
- [ ] Un file CSV v2 senza la colonna importa tutto come `draft`.

### 1.6 Installazione server multiutente

**Perché.** L'app desktop ha una knowledge base per PC; il valore per il cliente è una base condivisa.

**Cosa fare.**
- **Utenti** (migrazione): `users.is_active` (default vero); il controllo in `dependencies.py` rifiuta un utente disattivato (401/403 coerente con gli altri casi). Endpoint: cambio password dell'utente, reset da `expert`, disattivazione/riattivazione (mai eliminazione). Sicurezza: la password resta bcrypt con il controllo dei 72 byte.
- **Avviso sui tentativi di accesso falliti** (nessun blocco dell'account, decisione presa):
  - Contatore dei tentativi falliti **in memoria**, per username. Il contatore conta anche gli username inesistenti, così l'avviso compare allo stesso modo e non rivela quali utenti esistono (regola anti-enumerazione).
  - Dal **5° tentativo fallito** la risposta di login (stesso codice HTTP di "password errata") include un campo di avviso, e il frontend mostra "sono stati effettuati diversi tentativi di accesso non riusciti".
  - Quando l'utente corretto accede, la risposta di login riuscito include lo stesso avviso (con il numero dei tentativi) e il frontend lo mostra **una sola volta**; subito dopo il contatore si azzera, quindi l'avviso non viene più riproposto.
  - Nessuna colonna nuova su `users`, nessun endpoint di sblocco. Soglia `LOGIN_WARN_THRESHOLD` (default 5) in `.env.example`.
  - Limiti noti, accettati e da scrivere nel README: il contatore si azzera al riavvio del backend e non è condiviso tra più processi. Non c'è blocco né ritardo: l'avviso è solo un messaggio dissuasivo, non vincolante per il funzionamento. La scelta si basa sul fatto che Dedalo gira su una **LAN di produzione** senza esposizione esterna; se un'installazione fosse esposta fuori dalla LAN, la scelta va rivista.
- **Gestione famiglie e fasi da interfaccia** (limite 13): CRUD di `product_families` e `cycle_phases` per l'`expert`, con eliminazione bloccata se usate (le FK già lo impongono: tradurre l'errore in 409). Pagina dedicata.
- **Pagina utenti** estesa: elenco, attiva/disattiva, reset password.
- **Docker Compose**: servizi backend, MySQL e reverse proxy con HTTPS; frontend servito dalla build (`npm run build`); `CORS_ORIGINS` e `VITE_API_URL` sugli indirizzi reali; volume del database; migrazioni all'avvio del backend. Proxy: **nginx**, con certificato e chiave del cliente montati come file (scelto perché funziona offline e senza dominio pubblico, a differenza di Traefik con Let's Encrypt). Se il cliente non ha un certificato, la guida descrive come generarne uno interno.
- **`DEPLOY.md`**: installazione da zero, backup e ripristino MySQL con script, `JWT_EXPIRE_MINUTES` (default 480) da adeguare ai turni del cliente, nota che `AI_PROVIDER=api` invia conversazione, cause e soluzioni **fuori dalla rete aziendale** (in produzione `none` o `local`).
- Niente credenziali demo in produzione: `seed.sql` solo per sviluppo; il primo esperto nasce dal flusso `/setup` (esteso in 1.2 con stabilimento e linea).

**Criteri di accettazione.**
- [ ] Installazione da zero su un server pulito seguendo solo `DEPLOY.md`.
- [ ] Nessun utente demo dopo l'installazione di produzione.
- [ ] Un utente disattivato perde l'accesso alla richiesta successiva (anche con token valido).
- [ ] Ripristino da backup provato almeno una volta.
- [ ] Famiglia o fase in uso: l'eliminazione restituisce 409 con messaggio chiaro.

### 1.7 Calibrazione sui dati reali

**Perché.** Le soglie (`SEMANTIC_RECALL_THRESHOLD`, `SEMANTIC_MATCH_THRESHOLD`, `DISAMBIGUATION_SCORE_GAP`, `PROBABILITY_TEMPERATURE`, `PROBABILITY_UNKNOWN_SCORE`) sono calibrate su 60 frasi sintetiche (limite 1).

**Cosa fare.**
- **Attenzione:** le sessioni eliminate non hanno più i testi. La calibrazione usa le sessioni ancora presenti o i CSV esportati prima dell'eliminazione (1.3); lo script di calibrazione accetta quindi anche un CSV di sessioni.
- Script che esporta dal registro (1.3) le ricerche con esito noto nel formato di `tests/fixtures/operator_queries.json`, in un file separato per cliente.
- `scripts/evaluate_matching.py` accetta una fixture esterna.
- Procedura scritta di ricalibrazione e documentazione della data dell'ultima calibrazione per installazione.

**Criteri di accettazione.**
- [ ] La calibrazione gira su una fixture del cliente senza toccare quella di esempio.
- [ ] Le soglie di ogni installazione sono documentate con la data.

### 1.8 Caricamento iniziale assistito della knowledge base

**Perché.** Il rischio principale è una knowledge base vuota.

**Cosa fare.**
- Modello di intervista per componente (sintomo con le parole dell'operatore, componente, causa, soluzione, ambito).
- Anteprima dell'import CSV che segnala i sintomi quasi duplicati senza bloccare. Confronto con gli **embedding** già usati nel matching (decisione presa). Poiché la cache lavora per testo, i sintomi già noti non vengono ricalcolati; sui file grandi l'anteprima calcola gli embedding in batch e mostra l'avanzamento. Soglia di somiglianza da calibrare su esempi veri: va in `.env`.
- Caricamento in blocco come `draft` (1.5).

**Criteri di accettazione.**
- [ ] L'anteprima segnala i sintomi quasi duplicati senza bloccare l'import.

---

## 2. Regole trasversali

- **Test.** Ogni nuova tabella e ogni nuovo servizio ha test su MySQL e SQLite. Nessun test chiama servizi esterni. Suite leggera (`-m "not model"`) sempre veloce. Mock solo ai confini del sistema. Nei test il database ha nome diverso dalla produzione e la suite rifiuta di partire se coincidono.
- **Test del frontend.** Si introducono Vitest e React Testing Library (versioni fissate in `package.json`) **prima** di scrivere le nuove pagine, e si scrivono test per servizi (`services/`), componenti e pagine nuove. Il frontend non chiama mai il backend reale nei test (si simula `fetch`, che è il confine del sistema). Comando di test documentato nel README.
- **Configurazione.** Ogni nuova variabile va in `.env.example` (con commento) e nella tabella del README. Se manca una variabile obbligatoria il backend non parte e dice quale. `.env` non viene mai modificato senza il tuo permesso.
- **Documentazione.** A ogni punto completato: `README.md` (uso) e `workflow_sviluppo.md` (decisioni, alternative scartate, tentativi falliti, limiti).
- **Git.** Una branch `feature/<punto>` per ogni punto (es. `feature/migrazioni-alembic`), commit Conventional Commits. I commit e i push li esegui tu.
- **Compatibilità.** I nuovi campi API e CSV sono facoltativi.

## 3. Ordine dei lavori

| # | Punto | Dipende da | Branch suggerita |
|---|---|---|---|
| 1 | 1.1 Migrazioni | — | `feature/migrazioni-alembic` |
| 2 | Setup Vitest + React Testing Library | — | `feature/test-frontend` |
| 3 | 1.2 Impianti e componenti (incluso filtro e setup della linea) | 1.1, test frontend | `feature/impianti-componenti` |
| 4 | 1.3 Registro consultazioni | 1.1, **1.2**, test frontend | `feature/registro-consultazioni` |
| 5 | 1.5 Tracciabilità e validazione | 1.1, test frontend | `feature/storico-validazione` |
| 6 | 1.6 Utenti, catalogo, server | 1.1 (in parallelo) | `feature/utenti-catalogo`, `feature/deploy-docker` |
| 7 | 1.4 Report | 1.3 | `feature/report` |
| 8 | 1.7 Calibrazione, 1.8 Caricamento assistito | 1.3, 1.5 | `feature/calibrazione`, `feature/caricamento-assistito` |

1.2 passa prima di 1.3 perché le sessioni salvano stazione e macchina e la chat le richiede. Il punto 1.2 viene anche prima di caricare molte diagnosi; il punto 1.5 prima del primo cliente con più esperti.

---

## 4. Domande ancora aperte

**Nessuna.** Le decisioni Q1-Q22 sono nella tabella 0.1 e nei punti 1.1-1.8.

### Da verificare nel codice all'inizio di ciascun punto (non sono decisioni)

- **1.1:** come `conftest.py` crea il database di test oggi (per sostituire `schema.sql` con le migrazioni); presenza di un `.env.example` con `DB_BACKEND`.
- **1.2:** come il desktop gestisce il primo avvio e `/setup` (`desktop/launcher.py`, `routes/setup.py`, `setup_service.py`); dove `list_candidates` costruisce il filtro per famiglia e fase.
- **1.3:** dove `ChatPage.jsx` azzera la conversazione, per generare il `conversation_id`.
- **1.5:** come `import_service.py` scrive le diagnosi, per lo storico e per lo stato `draft`.
