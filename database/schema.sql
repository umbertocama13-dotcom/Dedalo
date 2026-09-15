-- Dedalo — database schema (MySQL 8.0.16+ / MariaDB 10.2+).
--
-- The script does not select a database, so the same file builds both the
-- application DB and the test DB:
--   mysql dedalo      < database/schema.sql
--   mysql dedalo_test < database/schema.sql
--
-- WARNING: tables are dropped and recreated. Re-running this file wipes all data.

SET NAMES utf8mb4;

-- Drop in reverse dependency order so foreign keys never block the drop.
-- The two v1 tables are dropped too, so this file also upgrades a v1 database.
DROP TABLE IF EXISTS diagnostic_exceptions;
DROP TABLE IF EXISTS base_diagnostics;
DROP TABLE IF EXISTS diagnostics;
DROP TABLE IF EXISTS cycle_phases;
DROP TABLE IF EXISTS product_families;
DROP TABLE IF EXISTS users;

CREATE TABLE users (
    id            INT UNSIGNED NOT NULL AUTO_INCREMENT,
    username      VARCHAR(50)  NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role          ENUM('expert', 'operator') NOT NULL,
    created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_users_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE product_families (
    id          INT UNSIGNED NOT NULL AUTO_INCREMENT,
    family_name VARCHAR(100) NOT NULL,
    description TEXT         NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_product_families_name (family_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE cycle_phases (
    id           INT UNSIGNED      NOT NULL AUTO_INCREMENT,
    family_id    INT UNSIGNED      NOT NULL,
    phase_number SMALLINT UNSIGNED NOT NULL,
    phase_name   VARCHAR(100)      NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_cycle_phases_family_number (family_id, phase_number),
    -- Logically redundant (id is already unique), but required as the target of
    -- the composite FK in diagnostics that enforces phase/family coherence.
    UNIQUE KEY uq_cycle_phases_id_family (id, family_id),
    CONSTRAINT fk_cycle_phases_family
        FOREIGN KEY (family_id) REFERENCES product_families (id)
        ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- One row per diagnosis. The scope is given by two optional columns:
--   family_id NULL                          -> valid for every family
--   family_id set, cycle_phase_id NULL      -> valid for the whole family
--   family_id set, cycle_phase_id set       -> valid only in that phase
CREATE TABLE diagnostics (
    id                   INT UNSIGNED NOT NULL AUTO_INCREMENT,
    symptom_description  VARCHAR(500) NOT NULL,
    affected_component   VARCHAR(150) NOT NULL,
    probable_cause       TEXT         NOT NULL,
    recommended_solution TEXT         NOT NULL,
    family_id            INT UNSIGNED NULL,
    cycle_phase_id       INT UNSIGNED NULL,
    created_by           INT UNSIGNED NOT NULL,
    created_at           DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at           DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    -- No UNIQUE on symptom_description: the same symptom may have several
    -- alternative causes/solutions, each stored as its own row.
    KEY idx_diagnostics_context (family_id, cycle_phase_id),
    KEY idx_diagnostics_phase_family (cycle_phase_id, family_id),
    KEY idx_diagnostics_created_by (created_by),
    -- A phase always belongs to a family, so a phase-scoped row must name the family too.
    CONSTRAINT chk_diagnostics_phase_requires_family
        CHECK (cycle_phase_id IS NULL OR family_id IS NOT NULL),
    -- MySQL forbids CASCADE/SET NULL actions on columns used in a CHECK constraint
    -- (error 3823), so both context FKs use RESTRICT.
    CONSTRAINT fk_diagnostics_family
        FOREIGN KEY (family_id) REFERENCES product_families (id)
        ON DELETE RESTRICT ON UPDATE RESTRICT,
    -- Composite FK instead of a trigger: the (phase, family) pair must exist in
    -- cycle_phases, so a phase can never be linked to a family it does not belong to.
    -- MySQL skips the check when any column is NULL, which is what allows family-only rows.
    CONSTRAINT fk_diagnostics_phase_family
        FOREIGN KEY (cycle_phase_id, family_id) REFERENCES cycle_phases (id, family_id)
        ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_diagnostics_created_by
        FOREIGN KEY (created_by) REFERENCES users (id)
        ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
