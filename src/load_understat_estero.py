"""
load_understat_estero.py — FUTDRAFT27

Scarica una lega estera da Understat (via understatapi) per una singola
stagione, filtra sui soli giocatori target (i trasferimenti esteri
classificati in player_provenienza per quella lega), li matcha ai
player_id esistenti riusando trova_corrispondenza di name_matching.py
(la stessa funzione gia' usata per Understat Serie A <-> Fantagazzetta),
e carica in understat_player_season agganciato al season_id corretto.

Non crea nuovi player_id: questi giocatori esistono gia' (creati come
orfani durante il carico FantaLab), lo scopo qui e' solo aggiungere
il loro storico Understat dalla lega di provenienza.

Uso:
    python3 src/load_understat_estero.py --lega "La Liga" --season-label "La_Liga_24_25" --understat-league "La_Liga" --understat-season 2024
"""

import os
import re
import argparse

import psycopg2
from dotenv import load_dotenv
from understatapi import UnderstatClient

from name_matching import rimuovi_accenti, estrai_cognome_iniziale
from fantalab_matching import _strip_iniziale, _ha_iniziale

load_dotenv()

DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "dbname": os.environ.get("DB_NAME", "futdraft27"),
    "user": os.environ.get("DB_USER", "weez"),
    "password": os.environ.get("DB_PASSWORD"),
}


def carica_target(conn, lega):
    """Giocatori classificati come 'Trasferimento estero' per questa lega,
    con il loro player_id e nome_canonico gia' in DB."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT p.player_id, p.nome_canonico
            FROM player_provenienza pp
            JOIN players p ON p.player_id = pp.player_id
            WHERE pp.categoria = 'Trasferimento estero'
              AND pp.lega_provenienza_norm ILIKE %s
            """,
            (f"%{lega}%",),
        )
        return cur.fetchall()

def trova_corrispondenza_target(player_name_understat, target_list):
    """Confronta il nome Understat (Nome Cognome) contro la lista dei
    nostri nome_canonico. Gestisce tre formati diversi che FantaLab usa
    per gli orfani: 'Cognome', 'Cognome I.', e (raro ma presente,
    scoperto su Unai Gomez/Correia) 'Nome Cognome' completo."""
    pulito = rimuovi_accenti(player_name_understat).replace("'", "")
    cognome_us, iniziale_us = estrai_cognome_iniziale(pulito)

    # Primo giro: formato standard Cognome / Cognome I.
    for player_id, nome_canonico in target_list:
        nome_pulito = rimuovi_accenti(nome_canonico).replace("'", "")
        cognome_noi = _strip_iniziale(nome_pulito)
        ha_iniziale_noi = _ha_iniziale(nome_pulito)
        iniziale_noi = nome_pulito.split()[-1][0] if ha_iniziale_noi else None

        if cognome_noi.lower() != cognome_us.lower():
            continue
        if iniziale_noi is None or iniziale_us is None:
            return player_id, nome_canonico
        if iniziale_noi.lower() == iniziale_us[0].lower():
            return player_id, nome_canonico

    # Secondo giro: fallback per 'Nome Cognome' completo -- confronto
    # sull'ultima parola come cognome, solo se produce un candidato unico
    candidati = []
    for player_id, nome_canonico in target_list:
        nome_pulito = rimuovi_accenti(nome_canonico).replace("'", "")
        parti = nome_pulito.split()
        if len(parti) >= 2 and parti[-1].lower() == cognome_us.lower():
            candidati.append((player_id, nome_canonico))

    if len(candidati) == 1:
        return candidati[0]

    return None, None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--lega", required=True, help="Nome lega come in player_provenienza.lega_provenienza_norm, es. 'La Liga'")
    parser.add_argument("--season-label", required=True, help="Label da inserire in seasons, es. La_Liga_24_25")
    parser.add_argument("--understat-league", required=True, help="Nome lega per la chiamata understatapi, es. La_Liga")
    parser.add_argument("--understat-season", required=True, help="Anno stagione understat, es. 2024")
    args = parser.parse_args()

    conn = psycopg2.connect(**DB_CONFIG)

    target_list = carica_target(conn, args.lega)
    print(f"Giocatori target per '{args.lega}': {len(target_list)}")
    for pid, nome in target_list:
        print(f"  {nome} (player_id {pid})")

    with conn.cursor() as cur:
        cur.execute("SELECT season_id FROM seasons WHERE label = %s", (args.season_label,))
        row = cur.fetchone()
        if row is None:
            print(f"\nERRORE: season_id non trovato per label '{args.season_label}'. Crealo prima con la migrazione SQL.")
            conn.close()
            return
        season_id = row[0]

    with UnderstatClient() as understat:
        dati_lega = understat.league(league=args.understat_league).get_player_data(season=args.understat_season)

    print(f"\nGiocatori scaricati da Understat ({args.understat_league} {args.understat_season}): {len(dati_lega)}")

    trovati = []
    non_trovati = list(target_list)

    with conn.cursor() as cur:
        for riga in dati_lega:
            player_id, nome_canonico = trova_corrispondenza_target(riga["player_name"], target_list)
            if player_id is None:
                continue

            cur.execute(
                """
                INSERT INTO understat_player_season
                    (season_id, player_id, player_name_raw, team_raw, apps, minutes, goals, assists, xg, xa, xg90, xa90)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (season_id, player_name_raw, team_raw) DO NOTHING
                """,
                (
                    season_id,
                    player_id,
                    riga["player_name"],
                    riga["team_title"],
                    int(riga["games"]) if riga["games"] else None,
                    int(riga["time"]) if riga["time"] else None,
                    int(riga["goals"]) if riga["goals"] else None,
                    int(riga["assists"]) if riga["assists"] else None,
                    float(riga["xG"]) if riga["xG"] else None,
                    float(riga["xA"]) if riga["xA"] else None,
                    (float(riga["xG"]) / int(riga["time"]) * 90) if riga["xG"] and riga["time"] and int(riga["time"]) > 0 else None,
                    (float(riga["xA"]) / int(riga["time"]) * 90) if riga["xA"] and riga["time"] and int(riga["time"]) > 0 else None,
                ),
            )
            trovati.append((nome_canonico, riga["player_name"], riga["team_title"]))
            if (player_id, nome_canonico) in non_trovati:
                non_trovati.remove((player_id, nome_canonico))

    conn.commit()
    conn.close()

    print(f"\n--- Matchati e caricati: {len(trovati)} ---")
    for nome_canonico, nome_understat, team in trovati:
        print(f"  {nome_canonico:20s} <- {nome_understat} ({team})")

    print(f"\n--- NON trovati in Understat {args.understat_league} {args.understat_season}: {len(non_trovati)} ---")
    for pid, nome in non_trovati:
        print(f"  {nome} (player_id {pid})")


if __name__ == "__main__":
    main()
