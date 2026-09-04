"""
fondi_duplicati_2627.py — FUTDRAFT27

Corregge il bug di carica_roster_2627_match.py: 160 giocatori sono
stati duplicati (player_id nuovo creato oggi, invece di riusare quello
gia' esistente da FantaLab) perche' il matching cercava solo dentro il
listino 25/26, non dentro gli orfani FantaLab gia' presenti. Vedi
SESSION_LOG.

Fonde ogni coppia (id_basso gia' esistente, id_alto creato oggi) su
id_basso: riassegna fantagazzetta_listino.player_id, elimina il
player_id duplicato. Verificato prima con query manuale che id_alto
non porti nessun dato in fantalab_valutazioni/tags/provenienza/
metrics/understat/listino altre stagioni - sicuro da rimuovere.

Esclude 'Forson O.' (3 id, caso diverso, gestito a parte).

Uso:
    python3 src/fondi_duplicati_2627.py
"""

import os

import psycopg2
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "dbname": os.environ.get("DB_NAME", "futdraft27"),
    "user": os.environ.get("DB_USER", "weez"),
    "password": os.environ.get("DB_PASSWORD"),
}


def main():
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT nome_canonico, array_agg(player_id ORDER BY player_id) AS ids
                FROM players
                GROUP BY nome_canonico
                HAVING count(*) = 2
            """)
            coppie = cur.fetchall()

        print(f"Coppie da fondere: {len(coppie)}")

        fusi = 0
        with conn:
            with conn.cursor() as cur:
                for nome, ids in coppie:
                    id_basso, id_alto = ids

                    # Verifica di sicurezza ripetuta anche qui, non solo
                    # a mano prima: se id_alto porta dati reali, salta e
                    # segnala invece di cancellare alla cieca.
                    cur.execute("""
                        SELECT
                            (SELECT count(*) FROM fantalab_valutazioni WHERE player_id=%(id)s) +
                            (SELECT count(*) FROM player_tags WHERE player_id=%(id)s) +
                            (SELECT count(*) FROM player_provenienza WHERE player_id=%(id)s) +
                            (SELECT count(*) FROM player_metrics_snapshot WHERE player_id=%(id)s) +
                            (SELECT count(*) FROM understat_player_season WHERE player_id=%(id)s)
                    """, {"id": id_alto})
                    dati_id_alto = cur.fetchone()[0]

                    if dati_id_alto > 0:
                        print(f"[SALTATO] {nome}: id_alto={id_alto} porta {dati_id_alto} righe di dati, non fondo automaticamente")
                        continue

                    cur.execute(
                        "UPDATE fantagazzetta_listino SET player_id = %s WHERE player_id = %s",
                        (id_basso, id_alto),
                    )
                    cur.execute(
                        "UPDATE player_name_matches SET player_id = %s WHERE player_id = %s",
                        (id_basso, id_alto),
                    )
                    cur.execute("DELETE FROM players WHERE player_id = %s", (id_alto,))
                    fusi += 1

        print(f"\nFusi con successo: {fusi}/{len(coppie)}")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
