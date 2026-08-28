-- ============================================================
-- FUTDRAFT27 — classificazione manuale degli orfani FantaLab
-- Compilata da Andrea (categoria, lega di provenienza, statistiche
-- base da Transfermarkt) per distinguere giovani di settore (nessun
-- dato recuperabile) da trasferimenti esteri veri (dati recuperabili
-- altrove) da Serie B/C italiana.
-- ============================================================

CREATE TABLE player_provenienza (
    id                  SERIAL PRIMARY KEY,
    player_id           INT NOT NULL UNIQUE REFERENCES players(player_id),
    categoria           TEXT NOT NULL CHECK (
        categoria IN ('Giovanile/Primavera', 'Trasferimento estero',
                       'Serie B/C italiana', 'Altro/Non so')
    ),
    lega_provenienza_raw    TEXT,  -- esattamente come scritto da Andrea
    lega_provenienza_norm   TEXT,  -- normalizzata (club/paese -> lega)
    lega_da_verificare      BOOLEAN NOT NULL DEFAULT FALSE,
    presenze            INT,
    gol                 INT,
    assist              INT,
    note                 TEXT,
    compilato_il         DATE NOT NULL,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_provenienza_categoria ON player_provenienza(categoria);
