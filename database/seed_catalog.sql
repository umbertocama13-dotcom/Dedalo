-- Dedalo — product families and cycle phases. Valid for MySQL and SQLite.
-- Run after the schema and before seed.sql:
--   mysql --default-character-set=utf8mb4 dedalo < database/seed_catalog.sql
--
-- The desktop app loads only this file on first start: users are created by the
-- expert at first launch, and the sample diagnostics come from sample_diagnostics.csv.

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
