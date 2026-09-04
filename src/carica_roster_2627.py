"""
carica_roster_2627.py — FUTDRAFT27

Carica il roster ufficiale 26/27 (Id/Ruolo/Nome/Squadra da
Statistiche_Fantacalcio_Stagione_2026_27.xlsx — le colonne di
statistiche sono ignorate, tutte a zero perche' la stagione non e'
ancora iniziata) in fantagazzetta_listino, con player_id NULL.

Fase 1 di 2 — stesso pattern a due fasi di migrate_data.py +
name_matching.py: prima carico grezzo, poi matching separato
(carica_roster_2627_match.py) per collegare i player_id esistenti.

Questo file diventa il roster di riferimento per filtrare la
dashboard: solo chi e' in Serie A 26/27 compare, non tutto lo
storico multi-stagione (vedi SESSION_LOG — bug Dzeko).

Uso:
    python3 src/carica_roster_2627.py
"""

import os
from pathlib import Path

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "dbname": os.environ.get("DB_NAME", "futdraft27"),
    "user": os.environ.get("DB_USER", "weez"),
    "password": os.environ.get("DB_PASSWORD"),
}

ROSTER_PATH = Path("/media/sf_FUTDRAFT27/Fantacalcio.it/Statistiche_Fantacalcio_Stagione_2026_27.xlsx")
SEASON_LABEL = "26_27"


def main():
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT season_id FROM seasons WHERE label = %s", (SEASON_LABEL,))
            row = cur.fetchone()
            if row is None:
                raise SystemExit(f"Season '{SEASON_LABEL}' non trovata in seasons — controlla che esista.")
            season_id = row[0]

        df = pd.read_excel(ROSTER_PATH, sheet_name="Tutti", header=1)

        rows = []
        for _, r in df.iterrows():
            nome = r.get("Nome")
            if pd.isna(nome) or not str(nome).strip():
                continue
            rows.append((
                season_id,
                str(nome).strip(),
                r["Squadra"] if pd.notna(r.get("Squadra")) else None,
                r["R"] if pd.notna(r.get("R")) else None,
            ))

        with conn.cursor() as cur:
            execute_values(
                cur,
                """
                INSERT INTO fantagazzetta_listino (season_id, nome_raw, squadra, ruolo)
                VALUES %s
                ON CONFLICT (season_id, nome_raw) DO NOTHING
                """,
                rows,
            )
        conn.commit()
        print(f"[roster 26/27] {len(rows)} righe lette dal file, inserite (o gia' presenti) in fantagazzetta_listino")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
