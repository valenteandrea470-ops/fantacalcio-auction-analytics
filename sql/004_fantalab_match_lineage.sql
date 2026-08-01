-- ============================================================
-- FUTDRAFT27 — migrazione: lineage del match tenuto dentro
-- fantalab_valutazioni stessa, invece di riusare
-- player_name_matches (le cui colonne sono nominate per
-- Understat specificamente — vedi nota in SESSION_LOG).
-- ============================================================

ALTER TABLE fantalab_valutazioni
    ADD COLUMN match_method TEXT NOT NULL
        CHECK (match_method IN ('exact', 'fuzzy', 'manual', 'orphan_created')),
    ADD COLUMN match_confidence NUMERIC(4,3);
