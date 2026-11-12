# Dedalo — Roadmap sensori, anomalie e notifiche (Fasi 2-5)

Tracce di alto livello, **non** un piano di implementazione. Estratte da `update.md` il 12 novembre 2026: dipendono da un banco prova (trapano a colonna), da dati reali e da un cliente, quindi vanno dettagliate solo quando la Fase 1 di `update.md` è completata.

Valgono gli invarianti di `update.md` (sezione 0.2), in particolare: nessuna scrittura verso la macchina, nessuna azione automatica senza regole deterministiche, collegamento sensori → knowledge base solo tramite mappatura esplicita (mai ricerca semantica).

Queste fasi hanno senso solo sulla **versione server**, non sul desktop.

---

## Fase 2 — Acquisizione dati dai sensori

Obiettivo: raccogliere dati puliti da una centralina indipendente, senza interferire con la linea. Si sviluppa e si valida prima sul banco prova.

- **Servizio separato da Dedalo** (cartella o repository dedicato, es. `acquisition/`): acquisizione, salvataggio dei dati grezzi, calcolo delle feature. Dedalo non deve dipendere dal fatto che l'acquisizione sia attiva. Flusso a senso unico: centralina → acquisizione → (eventi) → Dedalo.
- Dati grezzi ad alta frequenza **fuori dal database di Dedalo**: file per ciclo (es. Parquet) più un indice. Nel database solo cicli, feature ed eventi.
- Tabelle proposte: `sensors` (`asset_id`, `component_id`, `sensor_type`, `unit`, `sample_rate_hz`), `cycles` (`asset_id`, inizio/fine, `context_json`, `raw_file_path`, `is_valid`), `cycle_features` (`cycle_id`, `sensor_id`, `phase`, `feature_name`, `value`).
- Ogni ciclo ha inizio e fine certi e il contesto operativo (prodotto, variante, velocità, utensile). Orari in UTC, orologio sincronizzato.
- Feature di base: RMS, picco, fattore di cresta, kurtosis, energia per bande, ampiezza alla frequenza di rotazione; per la corrente RMS medio/massimo e durata della fase. NumPy/SciPy, funzioni pure testate con segnali sintetici (sinusoide: RMS = ampiezza/√2).
- Accettazione: un ciclo sul banco prova produce file grezzo, riga in `cycles` e feature; frequenza di campionamento effettiva verificata e campioni persi rilevati.

## Fase 3 — Rilevazione delle anomalie ed eventi

1. Soglie fisse e carte di controllo sulla baseline della singola macchina (spiegabili al manutentore).
2. Rilevazione di anomalie addestrata solo sul normale (es. Isolation Forest), per contesto operativo.
3. Riconoscimento del tipo di guasto solo per i modi con abbastanza esempi confermati.

Validazione: divisione dei dati per tempo o sessione (mai casuale); valutazione per evento e falsi allarmi a settimana. ISO 20816-3: solo macchine > 15 kW e 120-30 000 giri/min; altrimenti soglie dalla baseline della macchina.

- Tabelle proposte: `anomaly_events` (con `rule_id`/versione modello, `evidence_json`, `status`, feedback) e `event_diagnostic_map` (`event_type`, `component_id`, `diagnostic_id`, compilata dall'esperto).
- `POST /events` con credenziale di servizio; pagina *Eventi* con le diagnosi collegate.
- Feedback sull'evento solo da elenco: guasto confermato (con modo di guasto) / falso allarme / altro.

## Fase 4 — Notifiche e agente

- Regole di instradamento deterministiche (`notification_rules`), coda in uscita (`notifications`: `pending`/`sent`/`failed`, tentativi), raggruppamento degli eventi ripetuti e pausa minima per componente.
- Canali: email SMTP come base; adattatore `TicketProvider` per il sistema di ticket del cliente (stesso schema di `AIProvider`); riepilogo periodico per la direzione.
- LLM solo per redigere il testo del ticket da dati strutturati, mai per scegliere destinatario, gravità o diagnosi; testo validato con ripiego su modello fisso. Segnalazioni alla qualità come ipotesi da verificare.
- Conferma umana prima dell'invio; invio automatico attivato per singola regola quando i falsi allarmi sono sotto la soglia concordata.
- Accettazione: con `AI_PROVIDER=none` le notifiche partono comunque; nessuna notifica senza una regola tracciata; canali testati con trasporto simulato.

## Fase 5 — Feedback e riaddestramento

- Dati di addestramento da: eventi con feedback, esiti delle consultazioni (`update.md` 1.3), guasti indotti sul banco.
- Riaddestramento manuale e documentato; rilascio solo se il modello migliora sugli stessi dati di verifica; versionamento di modelli e soglie per macchina con ritorno alla versione precedente.
- Controllo della deriva della baseline (nuova variante, utensile, stagione).
- Libreria di firme di guasto riusabile tra clienti **solo se il contratto consente il riuso anonimo dei dati**.

---

## Fuori ambito per ora

- Scrittura verso PLC o fermata automatica della linea.
- Diagnosi generate da LLM.
- Knowledge base condivisa tra clienti diversi.
- Stima della vita residua dei componenti (mancano storici di guasto).
