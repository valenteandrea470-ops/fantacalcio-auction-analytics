"""
matching_diagnostics.py — FUTDRAFT27

Controllo "sospetti": per ogni giocatore NON matchato in una stagione,
verifica se lo stesso nome (pulito, senza accenti) ha trovato match in
ALMENO un'altra stagione. Se si' -> probabile problema di matching
localizzato a quell'anno, da investigare. Se no in nessuna stagione ->
probabile giocatore davvero fuori dal giro Serie A in quel periodo.

Porta 1:1 la logica del notebook originale, solo letta da Postgres
invece che da dati_stagioni in memoria.

Uso (dopo aver lanciato name_matching.py):
    python src/matching_diagnostics.py
"""

import os

import pandas as pd
import psycopg2
from dotenv import load_dotenv

from name_matching import rimuovi_accenti

load_dotenv()

DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "dbname": os.environ.get("DB_NAME", "futdraft27"),
    "user": os.environ.get("DB_USER", "weez"),
    "password": os.environ.get("DB_PASSWORD"),
}


def main():
    conn = psycopg2.connect(**DB_CONFIG)

    df = pd.read_sql(
        """
        SELECT s.label AS stagione, u.player_name_raw AS player, u.player_id
        FROM understat_player_season u
        JOIN seasons s ON s.season_id = u.season_id
        """,
        conn,
    )
    conn.close()

    # Insieme di tutti i nomi "puliti" che hanno fatto match, in qualunque stagione
    nomi_puliti_con_match = set()
    for stagione, gruppo in df.groupby("stagione"):
        matchati = gruppo[gruppo["player_id"].notna()]
        nomi_puliti_con_match.update(matchati["player"].apply(rimuovi_accenti))

    print(f"Totale nomi puliti distinti con match (in almeno una stagione): {len(nomi_puliti_con_match)}\n")

    # Per ogni stagione, quanti non-match sono "sospetti"
    for stagione, gruppo in df.groupby("stagione"):
        non_match = gruppo[gruppo["player_id"].isna()].copy()
        non_match["nome_pulito"] = non_match["player"].apply(rimuovi_accenti)
        sospetti = non_match[non_match["nome_pulito"].isin(nomi_puliti_con_match)]

        print(f"Stagione {stagione}: {len(non_match)} non-match totali, "
              f"di cui {len(sospetti)} SOSPETTI (matchano in altre stagioni)")


if __name__ == "__main__":
    main()
