-- ============================================================
-- FUTDRAFT27 — schema database PostgreSQL
-- Fase 1: ricostruzione architettura modulare
-- Grain: un giocatore reale = un player_id canonico, indipendente
-- dalla fonte (Understat o Fantagazzetta) e dalla stagione.
-- ============================================================

-- ------------------------------------------------------------
-- Stagioni (lookup)
-- ------------------------------------------------------------
CREATE TABLE seasons (
    season_id       SERIAL PRIMARY KEY,
    label           TEXT NOT NULL UNIQUE,   -- '21_22', '22_23', ... '25_26'
    start_year      INT NOT NULL,
    end_year        INT NOT NULL
);

-- ------------------------------------------------------------
-- Anagrafica giocatori (entità canonica, popolata dal matching)
-- nome_canonico viene dal listino Fantagazzetta corrente (fonte di
-- verità sul nome); nome_override è un layer manuale opzionale per
-- i pochi casi limite che vuoi forzare senza toccare il dato origine.
-- ------------------------------------------------------------
CREATE TABLE players (
    player_id       SERIAL PRIMARY KEY,
    nome_canonico   TEXT NOT NULL,
    nome_override   TEXT,                   -- NULL = usa nome_canonico
    ruolo           TEXT,                   -- P / D / C / A (classico)
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------
-- Dati grezzi Understat, per stagione (mai sovrascritti)
-- player_id nullable: popolato solo dopo il matching (fase 2)
-- ------------------------------------------------------------
CREATE TABLE understat_player_season (
    id                  SERIAL PRIMARY KEY,
    season_id           INT NOT NULL REFERENCES seasons(season_id),
    player_id           INT REFERENCES players(player_id),
    understat_number    INT,
    player_name_raw     TEXT NOT NULL,
    team_raw            TEXT,               -- puo' contenere piu' squadre separate da virgola
    apps                INT,
    minutes             INT,
    goals               INT,
    assists             INT,
    xg                  NUMERIC(6,3),
    xa                  NUMERIC(6,3),
    xg90                NUMERIC(6,3),
    xa90                NUMERIC(6,3),
    UNIQUE (season_id, player_name_raw, team_raw)
);

-- ------------------------------------------------------------
-- Listino ufficiale Fantagazzetta, per stagione
-- ------------------------------------------------------------
CREATE TABLE fantagazzetta_listino (
    id              SERIAL PRIMARY KEY,
    season_id       INT NOT NULL REFERENCES seasons(season_id),
    player_id       INT REFERENCES players(player_id),
    nome_raw        TEXT NOT NULL,
    nome_pulito     TEXT,
    squadra         TEXT,
    ruolo           TEXT,
    pgv             NUMERIC(6,2),
    mv              NUMERIC(5,2),
    fm              NUMERIC(5,2),
    fvm_1000        NUMERIC(8,2),
    quot            NUMERIC(6,2),
    fuori_lista     BOOLEAN DEFAULT FALSE,
    under           BOOLEAN DEFAULT FALSE,
    UNIQUE (season_id, nome_raw)
);

-- ------------------------------------------------------------
-- Lineage del matching Understat <-> Fantagazzetta
-- Sostituisce mappatura_manuale{} hardcoded nel notebook: stesso
-- contenuto, ma persistito e riusabile anche per il listino 26/27.
-- ------------------------------------------------------------
CREATE TABLE player_name_matches (
    id                      SERIAL PRIMARY KEY,
    player_id               INT NOT NULL REFERENCES players(player_id),
    understat_name_raw      TEXT NOT NULL,
    fantagazzetta_name_raw  TEXT NOT NULL,
    match_method            TEXT NOT NULL CHECK (match_method IN ('exact','fuzzy','manual')),
    confidence_score        NUMERIC(4,3),   -- solo per 'fuzzy'; NULL per exact/manual
    matched_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------
-- Metriche derivate, versionate per riproducibilita' del backtest.
-- target_season_id = per quale asta e' calcolato lo snapshot (es. 25_26).
-- model_version distingue le iterazioni del modello (es. pesi
-- arbitrari v1 vs regressione per ruolo v2), cosi' i backtest restano
-- confrontabili nel tempo.
-- ------------------------------------------------------------
CREATE TABLE player_metrics_snapshot (
    id                      SERIAL PRIMARY KEY,
    player_id               INT NOT NULL REFERENCES players(player_id),
    target_season_id        INT NOT NULL REFERENCES seasons(season_id),
    model_version            TEXT NOT NULL,
    n_stagioni_valide         INT,
    minuti_totali             INT,
    goals_90_pesata           NUMERIC(6,3),
    a_90_pesata               NUMERIC(6,3),
    score_storico              NUMERIC(5,2),   -- scala 0-100
    score_costanza             NUMERIC(5,2),   -- scala 0-100
    indice_affidabilita         NUMERIC(5,2),   -- scala 0-100
    indice_convenienza_pct      NUMERIC(6,2),   -- scarto % vs QUOT. (es. +50.00 = FM rende il 50% in piu' della quota)
    peso_dati                  NUMERIC(4,3),   -- 0-1, peso shrinkage (min_totali/1500 cappato a 1)
    dato_stimato                BOOLEAN DEFAULT FALSE,  -- TRUE se le metriche sono state riempite via shrinkage per scarsita' di dati reali
    computed_at                 TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (player_id, target_season_id, model_version)
);

-- ------------------------------------------------------------
-- Indici per le query tipiche della dashboard
-- (ricerca giocatore, filtro per ruolo, ordinamento per convenienza)
-- ------------------------------------------------------------
CREATE INDEX idx_understat_player   ON understat_player_season(player_id);
CREATE INDEX idx_listino_player     ON fantagazzetta_listino(player_id);
CREATE INDEX idx_metrics_target     ON player_metrics_snapshot(target_season_id, model_version);
CREATE INDEX idx_players_ruolo      ON players(ruolo);
