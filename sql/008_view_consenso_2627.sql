-- ============================================================
-- v_quotazioni_consenso_2627
-- QUOT. 26/27 stimata come mediana del prezzo suggerito (campo
-- "prezzo", NON "quo" — vedi SESSION_LOG 01/09, quo e' copiato
-- identico tra fonti, prezzo e' il giudizio soggettivo reale)
-- tra le 4 strategie FantaLab attive. Fallback a QUOT. 25/26
-- ufficiale per i giocatori assenti da tutte le fonti FantaLab,
-- con flag dato_stimato per distinguerlo in dashboard.
-- ============================================================
CREATE OR REPLACE VIEW v_quotazioni_consenso_2627 AS
WITH prezzi_fantalab AS (
    SELECT
        player_id,
        count(NULLIF(prezzo, 0)) AS n_prezzi_validi,
        percentile_cont(0.5) WITHIN GROUP (ORDER BY NULLIF(prezzo, 0)) AS prezzo_mediano,
        min(NULLIF(prezzo, 0)) AS prezzo_min,
        max(NULLIF(prezzo, 0)) AS prezzo_max
    FROM v_fantalab_ultimo_snapshot
    GROUP BY player_id
)
SELECT
    p.player_id,
    p.nome_canonico,
    p.ruolo,
    pf.n_prezzi_validi,
    round(pf.prezzo_mediano::numeric, 1) AS prezzo_mediano,
    pf.prezzo_min,
    pf.prezzo_max,
    fl.quot AS quot_2526_fallback,
    COALESCE(round(pf.prezzo_mediano::numeric, 1), fl.quot) AS quot_consenso_2627,
    (pf.prezzo_mediano IS NULL) AS dato_stimato
FROM players p
LEFT JOIN prezzi_fantalab pf ON pf.player_id = p.player_id
LEFT JOIN fantagazzetta_listino fl
    ON fl.player_id = p.player_id
    AND fl.season_id = (SELECT season_id FROM seasons WHERE label = '25_26')
WHERE pf.player_id IS NOT NULL OR fl.player_id IS NOT NULL
ORDER BY quot_consenso_2627 DESC NULLS LAST;
