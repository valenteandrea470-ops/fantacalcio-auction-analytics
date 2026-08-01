-- ============================================================
-- FUTDRAFT27 — migrazione: integrazione FantaLab
-- Aggiunge fantalab_valutazioni, player_tags, ed estende
-- player_name_matches.match_method per i player_id creati da
-- righe FantaLab senza corrispondenza nel listino ufficiale.
-- ============================================================

-- Estende il CHECK esistente per tracciare esplicitamente i player_id
-- "orfani" creati da fantalab_matching.py (Caso B: nessun match reale,
-- ma vogliamo lasciare traccia invece di un ramo silenzioso)
ALTER TABLE player_name_matches
    DROP CONSTRAINT player_name_matches_match_method_check;

ALTER TABLE player_name_matches
    ADD CONSTRAINT player_name_matches_match_method_check
    CHECK (match_method IN ('exact', 'fuzzy', 'manual', 'orphan_created'));

-- ------------------------------------------------------------
-- Valutazioni FantaLab, uno snapshot per download (versione
-- rigida: constraint univoco su player_id+fonte+data, niente
-- sovrascritture silenziose di uno snapshot precedente)
-- ------------------------------------------------------------
CREATE TABLE fantalab_valutazioni (
    id                  SERIAL PRIMARY KEY,
    player_id           INT NOT NULL REFERENCES players(player_id),
    fonte               TEXT NOT NULL DEFAULT 'fantalab',
    strategia           TEXT,               -- es. 'CarmySpecial'
    scaricato_il        DATE NOT NULL,
    nome_raw            TEXT NOT NULL,
    ruolo_fantalab      TEXT,               -- puo' divergere da players.ruolo
    squadra_fantalab    TEXT,
    obiettivo           BOOLEAN,
    fascia              TEXT,
    prezzo              NUMERIC(6,2),
    budget_pct          NUMERIC(6,4),
    pma_pct             NUMERIC(6,4),
    quo                 NUMERIC(6,2),
    titolarita          SMALLINT,
    affidabilita        SMALLINT,
    integrita           SMALLINT,
    commento            TEXT,
    mv                  NUMERIC(5,2),
    fmv                 NUMERIC(5,2),
    fmv_exp             NUMERIC(5,2),
    presenze            INT,
    pt_titolare         INT,
    minuti              INT,
    pt_infortunio       INT,
    gol                 INT,
    assist              INT,
    ammonizioni         INT,
    espulsioni          INT,
    rig_segnati         INT,
    rig_sbagliati       INT,
    gol_subiti          INT,
    rig_parati          INT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (player_id, fonte, scaricato_il)
);

-- ------------------------------------------------------------
-- Tag qualitativi (da Nota 1-5 di FantaLab, o altre fonti future)
-- ------------------------------------------------------------
CREATE TABLE player_tags (
    id             SERIAL PRIMARY KEY,
    player_id      INT NOT NULL REFERENCES players(player_id),
    tag            TEXT NOT NULL,
    fonte          TEXT NOT NULL,
    scaricato_il   DATE,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (player_id, tag, fonte, scaricato_il)
);

CREATE INDEX idx_fantalab_player ON fantalab_valutazioni(player_id);
CREATE INDEX idx_tags_player     ON player_tags(player_id);
