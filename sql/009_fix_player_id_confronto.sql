-- ============================================================
-- Fix v_fantalab_confronto: player_id mancante dalla SELECT finale
-- (presente nel join interno ma mai esposto in output) — necessario
-- per joinare in modo sicuro su player_id invece che su nome_canonico
-- in export_data.py. Vedi SESSION_LOG 01/09.
-- ============================================================
CREATE OR REPLACE VIEW v_fantalab_confronto AS
WITH totale_fonti AS (
        SELECT count(DISTINCT v_fantalab_ultimo_snapshot.strategia) AS n_strategie
           FROM v_fantalab_ultimo_snapshot
        ), per_giocatore AS (
         SELECT v_fantalab_ultimo_snapshot.player_id,
            count(DISTINCT v_fantalab_ultimo_snapshot.strategia) AS n_fonti_presente,
            count(NULLIF(v_fantalab_ultimo_snapshot.prezzo, 0::numeric)) AS n_prezzi_validi,
            min(NULLIF(v_fantalab_ultimo_snapshot.prezzo, 0::numeric)) AS prezzo_min,
            max(NULLIF(v_fantalab_ultimo_snapshot.prezzo, 0::numeric)) AS prezzo_max,
            max(NULLIF(v_fantalab_ultimo_snapshot.prezzo, 0::numeric)) - min(NULLIF(v_fantalab_ultimo_snapshot.prezzo, 0::numeric)) AS delta_prezzo,
            round(stddev_samp(NULLIF(v_fantalab_ultimo_snapshot.prezzo, 0::numeric)), 2) AS stddev_prezzo,
            round(avg(NULLIF(v_fantalab_ultimo_snapshot.prezzo, 0::numeric)), 2) AS prezzo_medio,
            count(*) FILTER (WHERE v_fantalab_ultimo_snapshot.obiettivo IS TRUE) AS obiettivo_count,
            jsonb_object_agg(v_fantalab_ultimo_snapshot.strategia, v_fantalab_ultimo_snapshot.prezzo) AS prezzi_per_fonte,
            jsonb_object_agg(v_fantalab_ultimo_snapshot.strategia, v_fantalab_ultimo_snapshot.fascia) AS fasce_per_fonte
           FROM v_fantalab_ultimo_snapshot
          GROUP BY v_fantalab_ultimo_snapshot.player_id
        )
 SELECT p.player_id,
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
