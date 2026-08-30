"""
find_candidati_understat.py — FUTDRAFT27

Per i giocatori target ancora senza match in una lega estera, mostra
tutti i candidati plausibili trovati in Understat (ricerca larga per
sottostringa di cognome, entrambi i lati) invece di scegliere in
automatico -- dopo i falsi positivi su cognomi comuni (Gomez) e i
mismatch su cognomi composti (Milla Manzanares, Rendall Correia),
qui la conferma umana e' piu' sicura di un'altra euristica.

Uso:
    python3 src/find_candidati_understat.py --lega "La Liga" --understat-league "La_Liga" --understat-season 2024
"""

import os
import argparse

import psycopg2
from dotenv import load_dotenv
from understatapi import UnderstatClient

from name_matching import rimuovi_accenti

load_dotenv()

DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "dbname": os.environ.get("DB_NAME", "futdraft27"),
    "user": os.environ.get("DB_USER", "weez"),
    "password": os.environ.get("DB_PASSWORD"),
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--lega", required=True)
    parser.add_argument("--understat-league", required=True)
    parser.add_argument("--understat-season", required=True)
    args = parser.parse_args()

    conn = psycopg2.connect(**DB_CONFIG)
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT p.player_id, p.nome_canonico
            FROM player_provenienza pp
            JOIN players p ON p.player_id = pp.player_id
            WHERE pp.categoria = 'Trasferimento estero'
              AND pp.lega_provenienza_norm ILIKE %s
              AND NOT EXISTS (
                  SELECT 1 FROM understat_player_season u
                  WHERE u.player_id = p.player_id
              )
            """,
            (f"%{args.lega}%",),
        )
        mancanti = cur.fetchall()
    conn.close()

    print(f"Giocatori ancora senza match: {len(mancanti)}\n")

    with UnderstatClient() as understat:
        dati_lega = understat.league(league=args.understat_league).get_player_data(season=args.understat_season)

    for player_id, nome_canonico in mancanti:
        nome_pulito = rimuovi_accenti(nome_canonico).replace("'", "")
        parole = [p.strip(".") for p in nome_pulito.split() if len(p.strip(".")) > 2]

        candidati = []
        for riga in dati_lega:
            nome_us_pulito = rimuovi_accenti(riga["player_name"])
            if any(parola.lower() in nome_us_pulito.lower() for parola in parole):
                candidati.append(riga)

        print(f"=== {nome_canonico} (player_id {player_id}) ===")
        if not candidati:
            print("  nessun candidato trovato\n")
            continue
        for c in candidati:
            print(f"  [{c['id']}] {c['player_name']:30s} {c['team_title']:20s} presenze:{c['games']} minuti:{c['time']}")
        print()


if __name__ == "__main__":
    main()
