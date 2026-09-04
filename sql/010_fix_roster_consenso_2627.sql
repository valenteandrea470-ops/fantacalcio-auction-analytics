-- ============================================================
-- Fix v_quotazioni_consenso_2627: parte dal roster ufficiale
-- 26/27 (fantagazzetta_listino filtrato su season 26/27) invece
-- che da players (tutto lo storico multi-stagione + orfani
-- FantaLab) — la versione precedente mostrava giocatori non
-- piu' in Serie A (es. Dzeko). Vedi SESSION_LOG.
-- ============================================================
DROP VIEW IF EXISTS v_quotazioni_consenso_2627;

CREATE VIEW v_quotazioni_consenso_2627 AS
WITH prezzi_fantalab AS (
    SELECT
        player_id,
        count(NULLIF(prezzo, 0)) AS n_prezzi_validi,
        percentile_cont(0.5) WITHIN GROUP (ORDER BY NULLIF(prezzo, 0)) AS prezzo_mediano,
        min(NULLIF(prezzo, 0)) AS prezzo_min,
        max(NULLIF(prezzo, 0)) AS prezzo_max
    FROM v_fantalab_ultimo_snapshot
    GROUP BY player_id
),
roster_2627 AS (
    SELECT fl.player_id, fl.nome_raw AS nome_roster, fl.squadra, fl.ruolo AS ruolo_roster
    FROM fantagazzetta_listino fl
    JOIN seasons s ON s.season_id = fl.season_id
    WHERE s.label = '26_27' AND fl.player_id IS NOT NULL
)
SELECT
    r.player_id,
    p.nome_canonico,
    r.squadra,
    COALESCE(r.ruolo_roster, p.ruolo) AS ruolo,
    pf.n_prezzi_validi,
    round(pf.prezzo_mediano::numeric, 1) AS prezzo_mediano,
    pf.prezzo_min,
    pf.prezzo_max,
    fl_2526.quot AS quot_2526_fallback,
    COALESCE(round(pf.prezzo_mediano::numeric, 1), fl_2526.quot) AS quot_consenso_2627,
    (pf.prezzo_mediano IS NULL) AS dato_stimato
FROM roster_2627 r
JOIN players p ON p.player_id = r.player_id
LEFT JOIN prezzi_fantalab pf ON pf.player_id = r.player_id
LEFT JOIN fantagazzetta_listino fl_2526
    ON fl_2526.player_id = r.player_id
    AND fl_2526.season_id = (SELECT season_id FROM seasons WHERE label = '25_26')
ORDER BY quot_consenso_2627 DESC NULLS LAST;
