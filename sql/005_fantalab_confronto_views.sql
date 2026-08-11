-- ============================================================
-- FUTDRAFT27 — viste di confronto tra fantallenatori FantaLab
-- Progettate per essere agnostiche al numero di fonti attive:
-- aggiungere un nuovo fantallenatore non richiede modifiche qui,
-- basta caricarlo con fantalab_matching.py.
-- ============================================================

-- Ultimo snapshot per ciascuna strategia (se ricarichi una fonte con
-- una data piu' recente, questa vista prende sempre l'ultima)
CREATE OR REPLACE VIEW v_fantalab_ultimo_snapshot AS
SELECT fv.*
FROM fantalab_valutazioni fv
JOIN (
    SELECT strategia, MAX(scaricato_il) AS scaricato_il
    FROM fantalab_valutazioni
    GROUP BY strategia
) ultimo ON ultimo.strategia = fv.strategia AND ultimo.scaricato_il = fv.scaricato_il;

-- Confronto per giocatore, solo sull'intersezione (tracciato da TUTTE
-- le fonti attualmente attive) -- vedi nota SESSION_LOG 09/08 sul
-- perche' l'intersezione e' necessaria per confronti onesti
CREATE OR REPLACE VIEW v_fantalab_confronto AS
WITH totale_fonti AS (
    SELECT COUNT(DISTINCT strategia) AS n_strategie
    FROM v_fantalab_ultimo_snapshot
),
per_giocatore AS (
    SELECT
        player_id,
        COUNT(DISTINCT strategia) AS n_fonti_presente,
        COUNT(NULLIF(prezzo, 0)) AS n_prezzi_validi,
        MIN(NULLIF(prezzo, 0)) AS prezzo_min,
        MAX(NULLIF(prezzo, 0)) AS prezzo_max,
        MAX(NULLIF(prezzo, 0)) - MIN(NULLIF(prezzo, 0)) AS delta_prezzo,
        ROUND(STDDEV_SAMP(NULLIF(prezzo, 0))::numeric, 2) AS stddev_prezzo,
        ROUND(AVG(NULLIF(prezzo, 0))::numeric, 2) AS prezzo_medio,
        COUNT(*) FILTER (WHERE obiettivo IS TRUE) AS obiettivo_count,
        jsonb_object_agg(strategia, prezzo) AS prezzi_per_fonte,
        jsonb_object_agg(strategia, fascia) AS fasce_per_fonte
    FROM v_fantalab_ultimo_snapshot
    GROUP BY player_id
)
SELECT
    p.nome_canonico,
    p.ruolo,
    pg.n_fonti_presente,
    pg.n_prezzi_validi,
    tf.n_strategie AS n_fonti_totali,
    pg.prezzo_min,
    pg.prezzo_max,
    pg.delta_prezzo,
    pg.stddev_prezzo,
    pg.prezzo_medio,
    pg.obiettivo_count,
    pg.prezzi_per_fonte,
    pg.fasce_per_fonte
FROM per_giocatore pg
JOIN players p ON p.player_id = pg.player_id
CROSS JOIN totale_fonti tf
WHERE pg.n_fonti_presente = tf.n_strategie
ORDER BY pg.stddev_prezzo DESC NULLS LAST;
