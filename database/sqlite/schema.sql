-- Dedalo — database schema for SQLite (desktop app).
--
-- Same tables and constraints as ../schema.sql (MySQL). Differences:
--   * INTEGER PRIMARY KEY AUTOINCREMENT instead of AUTO_INCREMENT (ids are never reused, as in MySQL);
--   * CHECK (role IN (...)) instead of ENUM;
--   * COLLATE NOCASE on the names that MySQL compares case-insensitively (utf8mb4_unicode_ci);
--     NOCASE only ignores case for unaccented letters;
--   * no ON UPDATE CURRENT_TIMESTAMP: the repository sets updated_at in every UPDATE;
--   * VARCHAR lengths are not enforced by SQLite: the API validates them.
--
-- SQLite enforces FOREIGN KEY constraints only with PRAGMA foreign_keys=ON, which
-- app/db.py sets on every connection.
--
-- WARNING: tables are dropped and recreated. Re-running this file wipes all data.

DROP TABLE IF EXISTS diagnostics;
DROP TABLE IF EXISTS cycle_phases;
DROP TABLE IF EXISTS product_families;
DROP TABLE IF EXISTS users;

CREATE TABLE users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      VARCHAR(50)  NOT NULL COLLATE NOCASE,
    password_hash VARCHAR(255) NOT NULL,
    role          VARCHAR(10)  NOT NULL CHECK (role IN ('expert', 'operator')),
    created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_users_username UNIQUE (username)
);

CREATE TABLE product_families (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    family_name VARCHAR(100) NOT NULL COLLATE NOCASE,
    description TEXT         NULL,
    CONSTRAINT uq_product_families_name UNIQUE (family_name)
);

CREATE TABLE cycle_phases (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    family_id    INTEGER      NOT NULL,
    phase_number SMALLINT     NOT NULL CHECK (phase_number >= 0),
    phase_name   VARCHAR(100) NOT NULL,
    CONSTRAINT uq_cycle_phases_family_number UNIQUE (family_id, phase_number),
    -- Target of the composite FK in diagnostics, as in the MySQL schema.
    CONSTRAINT uq_cycle_phases_id_family UNIQUE (id, family_id),
    CONSTRAINT fk_cycle_phases_family
        FOREIGN KEY (family_id) REFERENCES product_families (id)
        ON DELETE RESTRICT ON UPDATE CASCADE
);

CREATE TABLE diagnostics (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    symptom_description  VARCHAR(500) NOT NULL,
    affected_component   VARCHAR(150) NOT NULL,
    probable_cause       TEXT         NOT NULL,
    recommended_solution TEXT         NOT NULL,
    family_id            INTEGER      NULL,
    cycle_phase_id       INTEGER      NULL,
    created_by           INTEGER      NOT NULL,
    created_at           DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at           DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_diagnostics_phase_requires_family
        CHECK (cycle_phase_id IS NULL OR family_id IS NOT NULL),
    CONSTRAINT fk_diagnostics_family
        FOREIGN KEY (family_id) REFERENCES product_families (id)
        ON DELETE RESTRICT ON UPDATE RESTRICT,
    -- Like MySQL, SQLite skips the check when any column is NULL: this allows family-only rows.
    CONSTRAINT fk_diagnostics_phase_family
        FOREIGN KEY (cycle_phase_id, family_id) REFERENCES cycle_phases (id, family_id)
        ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_diagnostics_created_by
        FOREIGN KEY (created_by) REFERENCES users (id)
        ON DELETE RESTRICT ON UPDATE CASCADE
);

CREATE INDEX idx_diagnostics_context ON diagnostics (family_id, cycle_phase_id);
CREATE INDEX idx_diagnostics_phase_family ON diagnostics (cycle_phase_id, family_id);
CREATE INDEX idx_diagnostics_created_by ON diagnostics (created_by);
