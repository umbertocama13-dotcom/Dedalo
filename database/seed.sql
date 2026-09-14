-- Dedalo — sample data. Run after schema.sql on the same database:
--   mysql dedalo < database/seed.sql
--
-- Explicit ids keep the data deterministic: the pytest suite relies on them as
-- known cases (expected match, duplicate symptom, exception override, no match).
--
-- Demo credentials (development only):
--   expert_demo   / expert123
--   operator_demo / operator123

SET NAMES utf8mb4;

INSERT INTO users (id, username, password_hash, role) VALUES
    (1, 'expert_demo',   '$2b$12$Ufrmq0TLW3un3cjpJI1EgOWXjkNcoXIQkn2iW2J1rZV1QcpUBam02', 'expert'),
    (2, 'operator_demo', '$2b$12$OYQxnobvq0uEZTbtolJBmOXE7HVK82PCdwCbqRbCjCRqXqutt2DHm', 'operator');

INSERT INTO product_families (id, family_name, description) VALUES
    (1, 'Cella di assemblaggio robotizzata', 'Cella con robot antropomorfo, pinza pneumatica e avvitatore elettrico'),
    (2, 'Confezionatrice flow-pack',         'Macchina orizzontale per confezionamento in film termosaldabile');

INSERT INTO cycle_phases (id, family_id, phase_number, phase_name) VALUES
    (1, 1, 1, 'Carico pezzo'),
    (2, 1, 2, 'Serraggio in pinza'),
    (3, 1, 3, 'Avvitatura'),
    (4, 1, 4, 'Scarico'),
    (5, 2, 1, 'Svolgimento film'),
    (6, 2, 2, 'Formatura tubolare'),
    (7, 2, 3, 'Saldatura trasversale'),
    (8, 2, 4, 'Taglio e scarico');

-- Scenario 1 (ids 1-2): same symptom, two alternative causes/solutions.
-- Scenario 2 (id 3): pneumatic gripper, overridden in family 1 / phase 2.
-- Scenario 3 (id 4): heat sealing, overridden in family 2 / phase 3.
INSERT INTO base_diagnostics (id, symptom_description, affected_component, probable_cause, recommended_solution, created_by) VALUES
    (1,
     'Il nastro trasportatore si ferma a intermittenza',
     'Nastro trasportatore di alimentazione',
     'Fotocellula di presenza pezzo sporca o disallineata: il segnale si interrompe e il PLC arresta il nastro.',
     'Pulire la lente della fotocellula, riallinearla con il catarifrangente e verificare che il LED di segnale resti stabile.',
     1),
    (2,
     'Il nastro trasportatore si ferma a intermittenza',
     'Nastro trasportatore di alimentazione',
     'Intervento della protezione termica dell''inverter per sovraccarico meccanico del motoriduttore.',
     'Verificare tensione della cinghia e cuscinetti dei rulli, controllare la corrente assorbita dal motore e ripristinare l''allarme inverter.',
     1),
    (3,
     'La pinza del robot non chiude completamente',
     'Pinza pneumatica end-effector',
     'Pressione dell''aria compressa insufficiente o perdite sul circuito pneumatico.',
     'Verificare che il regolatore sia impostato a 6 bar e controllare raccordi e tubi alla ricerca di perdite.',
     1),
    (4,
     'Saldatura del film irregolare con grinze',
     'Ganasce saldanti trasversali',
     'Temperatura delle ganasce sotto il setpoint a causa di una termocoppia degradata.',
     'Confrontare la lettura della termocoppia con un termometro di riferimento e sostituirla se lo scostamento supera 5 °C.',
     1);

INSERT INTO diagnostic_exceptions (id, base_diagnostic_id, family_id, cycle_phase_id, specific_cause, specific_solution, created_by) VALUES
    (1, 3, 1, 2,
     'Sensore magnetico di finecorsa del cilindro spostato dopo il cambio formato: il robot riceve il consenso prima della chiusura completa.',
     'Riposizionare il sensore sul cilindro a pinza chiusa e verificare il segnale di finecorsa sul PLC.',
     1),
    (2, 4, 2, 7,
     'Usura del rivestimento in PTFE delle ganasce: il calore non si distribuisce in modo uniforme.',
     'Sostituire il nastro in PTFE delle ganasce e rimuovere i residui di film bruciato.',
     1),
    -- Override on one of the two duplicate-symptom rows: the other row must stay unchanged.
    (3, 2, 2, 5,
     'Freno dello svolgitore bobina troppo serrato: il traino del film sovraccarica il motore del nastro.',
     'Ridurre la coppia del freno dello svolgitore e verificare che la bobina ruoti liberamente a macchina ferma.',
     1);
