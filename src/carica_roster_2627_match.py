"""
carica_roster_2627_match.py — FUTDRAFT27

Fase 2 di 2 (dopo carica_roster_2627.py): collega le righe del roster
26/27 caricate con player_id NULL ai player_id gia' esistenti, riusando
trova_corrispondenza_fantalab (fantalab_matching.py) — stesso formato
nome corto (es. "Martinez Jo."), non i nomi completi di name_matching.py
(quello e' per Understat).

Chi non trova corrispondenza nel listino 25/26 e' probabilmente
neopromosso/nuovo trasferimento mai visto prima: diventa un player_id
nuovo, stesso pattern degli orfani FantaLab.

Uso:
    python3 src/carica_roster_2627_match.py
"""

import os

import pandas as pd
import psycopg2
from dotenv import load_dotenv

from name_matching import rimuovi_accenti, load_listino_df
from fantalab_matching import trova_corrispondenza_fantalab

load_dotenv()

DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "dbname": os.environ.get("DB_NAME", "futdraft27"),
    "user": os.environ.get("DB_USER", "weez"),
    "password": os.environ.get("DB_PASSWORD"),
}

SEASON_LABEL_26_27 = "26_27"
SEASON_LABEL_25_26 = "25_26"


def main():
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        listino_2526 = load_listino_df(conn, SEASON_LABEL_25_26)

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT fl.id, fl.nome_raw, fl.ruolo
                FROM fantagazzetta_listino fl
                JOIN seasons s ON s.season_id = fl.season_id
                WHERE s.label = %s AND fl.player_id IS NULL
                """,
                (SEASON_LABEL_26_27,),
            )
            righe = cur.fetchall()

        stats = {"exact": 0, "fuzzy": 0, "nuovi": 0}

        for listino_id, nome_raw, ruolo in righe:
            nome_matchato, metodo, confidenza = trova_corrispondenza_fantalab(nome_raw, listino_2526)

            if nome_matchato is not None:
                player_id = int(listino_2526.loc[listino_2526["nome_raw"] == nome_matchato, "player_id"].iloc[0])
                stats[metodo] = stats.get(metodo, 0) + 1
            else:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO players (nome_canonico, ruolo) VALUES (%s, %s) RETURNING player_id",
                        (nome_raw, ruolo),
                    )
                    player_id = cur.fetchone()[0]
                stats["nuovi"] += 1
                metodo = "orphan_created"
                confidenza = None
                nome_matchato = nome_raw  # nessuna fonte da abbinare, il nome e' la fonte stessa

            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE fantagazzetta_listino SET player_id = %s WHERE id = %s",
                    (player_id, listino_id),
                )
                cur.execute(
                    """
                    INSERT INTO player_name_matches
                        (player_id, understat_name_raw, fantagazzetta_name_raw, match_method, confidence_score)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (player_id, nome_raw, nome_matchato, metodo, confidenza),
                )

        conn.commit()
        print(
            f"[roster 26/27 match] {len(righe)} righe processate — "
            f"exact: {stats.get('exact', 0)}, fuzzy: {stats.get('fuzzy', 0)}, "
            f"nuovi (neopromossi/trasferimenti): {stats['nuovi']}"
        )

    finally:
        conn.close()


if __name__ == "__main__":
    main()


if __name__ == "__main__":
    main()
