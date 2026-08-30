-- ============================================================
-- FUTDRAFT27 — supporto multi-lega per Understat (trasferimenti esteri)
-- Le righe esistenti restano 'Serie A' di default, nessun dato
-- toccato. Nuove leghe = nuove righe in seasons, understat_player_season
-- riusata cosi' com'e', nessuna modifica strutturale.
-- ============================================================

ALTER TABLE seasons ADD COLUMN lega TEXT NOT NULL DEFAULT 'Serie A';

INSERT INTO seasons (label, start_year, end_year, lega)
VALUES ('La_Liga_24_25', 2024, 2025, 'La Liga');
