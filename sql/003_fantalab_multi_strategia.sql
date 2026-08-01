-- ============================================================
-- FUTDRAFT27 — migrazione: supporto multi-fantallenatore
-- Il constraint UNIQUE originale su fantalab_valutazioni non
-- includeva 'strategia', quindi due fantallenatori diversi
-- scaricati lo stesso giorno sarebbero andati in conflitto.
-- ============================================================

ALTER TABLE fantalab_valutazioni
    DROP CONSTRAINT fantalab_valutazioni_player_id_fonte_scaricato_il_key;

ALTER TABLE fantalab_valutazioni
    ALTER COLUMN strategia SET NOT NULL;

ALTER TABLE fantalab_valutazioni
    ADD CONSTRAINT fantalab_valutazioni_player_id_fonte_strategia_scaricato_il_key
    UNIQUE (player_id, fonte, strategia, scaricato_il);
