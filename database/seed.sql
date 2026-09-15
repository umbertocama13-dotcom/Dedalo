-- Dedalo — sample data. Run after schema.sql on the same database:
--   mysql dedalo < database/seed.sql
--
-- Explicit ids keep the data deterministic: the pytest suite and
-- backend/tests/fixtures/operator_queries.json rely on them as known cases.
--
-- Demo credentials (development only):
--   expert_demo   / expert123
--   operator_demo / operator123

SET NAMES utf8mb4;

INSERT INTO users (id, username, password_hash, role) VALUES
    (1, 'expert_demo',   '$2b$12$Ufrmq0TLW3un3cjpJI1EgOWXjkNcoXIQkn2iW2J1rZV1QcpUBam02', 'expert'),
    (2, 'operator_demo', '$2b$12$OYQxnobvq0uEZTbtolJBmOXE7HVK82PCdwCbqRbCjCRqXqutt2DHm', 'operator');

INSERT INTO product_families (id, family_name, description) VALUES
    (1, 'Cella di assemblaggio robotizzata', 'Cella con robot antropomorfo, pinza pneumatica, avvitatore elettrico e sistema di visione'),
    (2, 'Confezionatrice flow-pack',         'Macchina orizzontale per confezionamento in film termosaldabile'),
    (3, 'Cella di saldatura robotizzata',    'Cella MIG/MAG con robot di saldatura, staffaggi pneumatici e nastro trasportatore pallet');

INSERT INTO cycle_phases (id, family_id, phase_number, phase_name) VALUES
    (1,  1, 1, 'Carico pezzo'),
    (2,  1, 2, 'Serraggio in pinza'),
    (3,  1, 3, 'Avvitatura'),
    (4,  1, 4, 'Scarico'),
    (5,  2, 1, 'Svolgimento film'),
    (6,  2, 2, 'Formatura tubolare'),
    (7,  2, 3, 'Saldatura trasversale'),
    (8,  2, 4, 'Taglio e scarico'),
    (9,  3, 1, 'Ingresso pallet'),
    (10, 3, 2, 'Bloccaggio pezzo'),
    (11, 3, 3, 'Saldatura'),
    (12, 3, 4, 'Uscita pallet');

-- Ids 1-10: generic (valid for every family).
-- Ids 1-2: same symptom, two alternative causes.
-- Ids 9-10: similar wording, opposite behaviour of the same sensor.
INSERT INTO diagnostics (id, symptom_description, affected_component, probable_cause, recommended_solution, family_id, cycle_phase_id, created_by) VALUES
    (1, 'Il nastro trasportatore si ferma a intermittenza', 'Nastro trasportatore',
     'Fotocellula di presenza pezzo sporca o disallineata: il segnale si interrompe e il PLC arresta il nastro.',
     'Pulire la lente della fotocellula, riallinearla con il catarifrangente e verificare che il LED di segnale resti stabile.',
     NULL, NULL, 1),
    (2, 'Il nastro trasportatore si ferma a intermittenza', 'Nastro trasportatore',
     'Intervento della protezione termica dell''inverter per sovraccarico meccanico del motoriduttore.',
     'Verificare tensione della cinghia e cuscinetti dei rulli, controllare la corrente assorbita dal motore e ripristinare l''allarme inverter.',
     NULL, NULL, 1),
    (3, 'La pressione dell''aria compressa è bassa in tutta la macchina', 'Gruppo trattamento aria',
     'Cartuccia del filtro regolatore intasata oppure perdite su raccordi e tubi del circuito pneumatico.',
     'Leggere il manometro all''ingresso macchina, sostituire la cartuccia del filtro e cercare le perdite con spray cercafughe a macchina in pressione.',
     NULL, NULL, 1),
    (4, 'La macchina non si avvia e il pulsante di marcia non risponde', 'Circuito di sicurezza',
     'Catena di sicurezza aperta: pulsante di emergenza premuto, riparo aperto o modulo di sicurezza da ripristinare.',
     'Controllare tutti i pulsanti di emergenza e i ripari, poi premere il pulsante di reset del modulo di sicurezza prima della marcia.',
     NULL, NULL, 1),
    (5, 'Il pannello operatore HMI è bloccato e non risponde al tocco', 'Pannello operatore HMI',
     'Blocco del software del pannello o perdita di comunicazione con il PLC.',
     'Riavviare il pannello dall''interruttore dedicato e verificare il cavo Ethernet tra pannello e PLC.',
     NULL, NULL, 1),
    (6, 'Allarme di comunicazione persa con il PLC', 'Rete di campo Profinet',
     'Connettore di rete allentato o switch di rete guasto nel quadro elettrico.',
     'Verificare i LED di link sulle porte, reinserire i connettori e, se il LED resta spento, sostituire il cavo o lo switch.',
     NULL, NULL, 1),
    (7, 'Il motore si surriscalda e si sente odore di bruciato', 'Motore elettrico',
     'Ventola di raffreddamento ostruita dalla polvere oppure cuscinetti usurati che aumentano l''assorbimento.',
     'Arrestare la macchina, pulire ventola e alette del motore, misurare la corrente assorbita e controllare la rumorosità dei cuscinetti.',
     NULL, NULL, 1),
    (8, 'Un cilindro pneumatico si muove a scatti', 'Cilindro pneumatico',
     'Regolatori di flusso starati oppure guarnizioni del cilindro usurate o non lubrificate.',
     'Regolare i regolatori di flusso sullo scarico e, se il problema resta, sostituire il kit guarnizioni del cilindro.',
     NULL, NULL, 1),
    (9, 'Il sensore induttivo non rileva la presenza del pezzo', 'Sensore induttivo',
     'Sensore allentato o montato oltre la distanza di intervento nominale.',
     'Riposizionare il sensore alla distanza nominale indicata sulla targhetta e verificare che il LED si accenda con il pezzo davanti.',
     NULL, NULL, 1),
    (10, 'Il sensore induttivo segnala il pezzo anche quando è assente', 'Sensore induttivo',
     'Trucioli metallici depositati sulla faccia del sensore oppure sensore danneggiato da un urto.',
     'Pulire la faccia del sensore dai trucioli e sostituirlo se il LED resta acceso anche senza pezzo.',
     NULL, NULL, 1);

-- Ids 11-18: family 1 (robotic assembly cell).
-- Ids 11 and 16: same symptom, the phase-scoped row gives the cause valid after a format change.
-- Ids 14 and 17: same pattern for the screwdriver.
INSERT INTO diagnostics (id, symptom_description, affected_component, probable_cause, recommended_solution, family_id, cycle_phase_id, created_by) VALUES
    (11, 'La pinza del robot non chiude completamente', 'Pinza pneumatica end-effector',
     'Pressione dell''aria compressa insufficiente o perdite sul circuito della pinza.',
     'Verificare che il regolatore sia impostato a 6 bar e controllare raccordi e tubi della pinza alla ricerca di perdite.',
     1, NULL, 1),
    (12, 'La pinza del robot chiude ma non si apre', 'Elettrovalvola pinza',
     'Elettrovalvola bloccata in posizione o bobina guasta.',
     'Azionare l''elettrovalvola con il comando manuale: se la pinza si apre, sostituire la bobina, altrimenti sostituire la valvola.',
     1, NULL, 1),
    (13, 'Il robot si ferma con allarme di collisione', 'Robot antropomorfo',
     'Ostacolo nella zona di lavoro oppure carico utile configurato in modo errato dopo un cambio pinza.',
     'Liberare la zona di lavoro, verificare il carico utile impostato nel controllore e ripristinare l''allarme a velocità ridotta.',
     1, NULL, 1),
    (14, 'L''avvitatore non raggiunge la coppia di serraggio', 'Avvitatore elettrico',
     'Inserto usurato che slitta sulla testa della vite oppure viti di un lotto non conforme.',
     'Sostituire l''inserto e verificare con il controllo qualità il lotto delle viti in uso.',
     1, NULL, 1),
    (15, 'Le viti vengono avvitate storte', 'Maschera di centraggio',
     'Pezzo non centrato nella maschera per sporco o spine di riferimento usurate.',
     'Pulire la maschera, controllare l''usura delle spine di riferimento e verificare il centraggio con un pezzo campione.',
     1, NULL, 1),
    (16, 'La pinza del robot non chiude completamente', 'Sensore finecorsa pinza',
     'Sensore magnetico di finecorsa del cilindro spostato dopo il cambio formato: il robot riceve il consenso prima della chiusura completa.',
     'Riposizionare il sensore sul cilindro a pinza chiusa e verificare il segnale di finecorsa sul PLC.',
     1, 2, 1),
    (17, 'L''avvitatore non raggiunge la coppia di serraggio', 'Controllore avvitatore',
     'Programma di coppia sbagliato selezionato dopo il cambio formato.',
     'Selezionare sul controllore dell''avvitatore il programma di coppia del formato in produzione.',
     1, 3, 1),
    (18, 'Il robot non preleva il pezzo dal nastro', 'Sistema di visione',
     'La telecamera non riconosce il pezzo: lente sporca o illuminatore guasto.',
     'Pulire la lente della telecamera, verificare che l''illuminatore sia acceso e ripetere la calibrazione con il pezzo campione.',
     1, 1, 1);

-- Ids 19-25: family 2 (flow-pack wrapper).
-- Ids 19-20: same symptom, generic for the family and specific for the sealing phase.
-- Id 22: phase-scoped cause for the generic conveyor symptom of ids 1-2.
INSERT INTO diagnostics (id, symptom_description, affected_component, probable_cause, recommended_solution, family_id, cycle_phase_id, created_by) VALUES
    (19, 'Saldatura del film irregolare con grinze', 'Ganasce saldanti trasversali',
     'Temperatura delle ganasce sotto il setpoint a causa di una termocoppia degradata.',
     'Confrontare la lettura della termocoppia con un termometro di riferimento e sostituirla se lo scostamento supera 5 °C.',
     2, NULL, 1),
    (20, 'Saldatura del film irregolare con grinze', 'Rivestimento ganasce',
     'Usura del rivestimento in PTFE delle ganasce: il calore non si distribuisce in modo uniforme.',
     'Sostituire il nastro in PTFE delle ganasce e rimuovere i residui di film bruciato.',
     2, 7, 1),
    (21, 'Il film si strappa durante lo svolgimento', 'Svolgitore bobina',
     'Tensione del film eccessiva: ballerino bloccato o freno della bobina troppo serrato.',
     'Verificare che il ballerino si muova liberamente e ridurre la coppia del freno della bobina.',
     2, NULL, 1),
    (22, 'Il nastro trasportatore si ferma a intermittenza', 'Svolgitore bobina',
     'Freno dello svolgitore bobina troppo serrato: il traino del film sovraccarica il motore del nastro.',
     'Ridurre la coppia del freno dello svolgitore e verificare che la bobina ruoti liberamente a macchina ferma.',
     2, 5, 1),
    (23, 'Il taglio del film non è netto e le confezioni restano unite', 'Coltello di taglio',
     'Lama consumata oppure controlama disallineata.',
     'Sostituire la lama e regolare la controlama con lo spessimetro secondo il manuale.',
     2, NULL, 1),
    (24, 'La fotocellula di registro non legge la tacca di stampa', 'Fotocellula di registro',
     'Contrasto della tacca insufficiente con il nuovo film oppure sensibilità della fotocellula starata.',
     'Ripetere l''autoapprendimento della fotocellula sulla tacca e sul fondo del film in uso.',
     2, 6, 1),
    (25, 'La confezione non è sigillata sul lato lungo', 'Rulli di saldatura longitudinale',
     'Temperatura dei rulli sotto il setpoint o pressione di contatto insufficiente.',
     'Verificare temperatura reale e setpoint dei rulli e regolare la pressione di contatto.',
     2, NULL, 1);

-- Ids 26-36: family 3 (robotic welding cell).
-- Ids 26-28: the cell stops for a reason outside the welding phase (e.g. the pallet conveyor),
--            so they are family-scoped, not phase-scoped.
-- Ids 29-30: same symptom, generic for the family and specific for the pallet infeed phase.
INSERT INTO diagnostics (id, symptom_description, affected_component, probable_cause, recommended_solution, family_id, cycle_phase_id, created_by) VALUES
    (26, 'La cella di saldatura non completa il ciclo ed entra in allarme', 'Nastro trasportatore pallet',
     'Il nastro trasportatore pallet è guasto e manda in allarme tutta la cella.',
     'Ricercare il guasto nel nastro trasportatore pallet e nella sua logica sul PLC: motore, inverter, sensori di presenza pallet.',
     3, NULL, 1),
    (27, 'La cella di saldatura non completa il ciclo ed entra in allarme', 'Barriera fotoelettrica di sicurezza',
     'Barriera fotoelettrica interrotta o disallineata: il modulo di sicurezza arresta la cella.',
     'Verificare l''allineamento della barriera, pulire le ottiche e ripristinare il modulo di sicurezza.',
     3, NULL, 1),
    (28, 'La cella di saldatura non completa il ciclo ed entra in allarme', 'Torcia di saldatura',
     'Intervento del sensore anticollisione della torcia dopo un urto con il pezzo o con gli staffaggi.',
     'Controllare che la torcia non sia piegata, verificare il TCP con la punta di riferimento e ripristinare il sensore anticollisione.',
     3, NULL, 1),
    (29, 'Il pallet non arriva in posizione di lavoro', 'Fermo pallet pneumatico',
     'Il fermo pneumatico di posizionamento resta alzato o non si abbassa: elettrovalvola del fermo bloccata.',
     'Azionare manualmente l''elettrovalvola del fermo e verificare che il cilindro si muova per tutta la corsa.',
     3, NULL, 1),
    (30, 'Il pallet non arriva in posizione di lavoro', 'Sensore presenza pallet',
     'Sensore di ingresso pallet sporco o spostato: il PLC non comanda l''avanzamento verso la stazione.',
     'Pulire il sensore di ingresso, riposizionarlo secondo la dima e verificare il segnale sul PLC.',
     3, 9, 1),
    (31, 'Il cordone di saldatura presenta porosità', 'Gas di protezione',
     'Portata del gas di protezione insufficiente, bombola in esaurimento o ugello ostruito da spruzzi.',
     'Verificare con il flussimetro una portata di 12-15 l/min, controllare la pressione della bombola e pulire l''ugello.',
     3, NULL, 1),
    (32, 'Il filo di saldatura non avanza o avanza a scatti', 'Trainafilo',
     'Rulli del trainafilo usurati o con pressione errata, oppure guaina guidafilo intasata.',
     'Sostituire i rulli trainafilo, regolare la pressione dei rulli e soffiare o sostituire la guaina.',
     3, NULL, 1),
    (33, 'L''arco di saldatura non si innesca', 'Generatore di saldatura',
     'Cavo di massa scollegato o morsetto ossidato, oppure punta guidafilo consumata.',
     'Verificare il collegamento del cavo di massa al pezzo, pulire il morsetto e sostituire la punta guidafilo.',
     3, 11, 1),
    (34, 'Gli staffaggi non bloccano il pezzo', 'Staffaggi pneumatici',
     'Pressione insufficiente sulla linea degli staffaggi o elettrovalvola di comando guasta.',
     'Verificare la pressione sul manometro degli staffaggi e azionare manualmente l''elettrovalvola di comando.',
     3, 10, 1),
    (35, 'Gli staffaggi bloccano il pezzo ma il robot non parte', 'Sensori di consenso staffaggi',
     'Un sensore di staffaggio chiuso non rileva la posizione: il PLC non dà il consenso al robot.',
     'Controllare sul PLC quale consenso manca, poi regolare o sostituire il sensore di quello staffaggio.',
     3, 10, 1),
    (36, 'Spruzzi di saldatura eccessivi sul pezzo', 'Parametri di saldatura',
     'Tensione o velocità del filo non corrette per il programma in uso, oppure ugello sporco.',
     'Verificare il programma di saldatura selezionato, pulire l''ugello e applicare il liquido antispruzzo.',
     3, NULL, 1);
