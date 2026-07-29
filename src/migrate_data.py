"""
migrate_data.py — FUTDRAFT27

Carica i dati grezzi (CSV Understat + listino Fantagazzetta xlsx) nel
database Postgres, senza fare alcun matching tra le fonti. Il matching
Understat <-> Fantagazzetta e' uno step separato (fase 3).

Idempotente: si puo' rilanciare piu' volte senza duplicare righe,
grazie ai vincoli UNIQUE definiti in sql/schema.sql (ON CONFLICT DO NOTHING).
Se correggi un dato alla fonte e vuoi ricaricarlo, tronca la tabella
interessata prima di rilanciare lo script (vedi note in fondo al file).

Uso:
    python src/migrate_data.py
"""

import os
from pathlib import Path

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

load_dotenv()

# ------------------------------------------------------------------
# Configurazione
# ------------------------------------------------------------------

DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "dbname": os.environ.get("DB_NAME", "futdraft27"),
    "user": os.environ.get("DB_USER", "weez"),
    "password": os.environ.get("DB_PASSWORD"),
}

DATA_ROOT = Path(os.environ.get("DATA_ROOT", "/media/sf_FUTDRAFT27"))
UNDERSTAT_DIR = DATA_ROOT / "Understats"
LISTINO_PATH = DATA_ROOT / "lista_2526_Leghe.xlsx"

# Mappa: file CSV Understat -> label stagione (deve combaciare con seasons.label)
UNDERSTAT_FILES = {
    "leagueplayers_21_22.csv": "21_22",
    "leagueplayers_22_23.csv": "22_23",
    "leagueplayers_23_24.csv": "23_24",
    "leagueplayers_24_25.csv": "24_25",
    "leagueplayers_25_26.csv": "25_26",
}

# La stagione a cui appartiene il listino xlsx (vedi nota: e' uno
# snapshot di fine stagione 25/26, non un listino pre-asta vuoto)
LISTINO_SEASON_LABEL = "25_26"


# ------------------------------------------------------------------
# Step 1 — popola seasons (idempotente)
# ------------------------------------------------------------------

def load_seasons(conn):
    labels = sorted(set(UNDERSTAT_FILES.values()) | {LISTINO_SEASON_LABEL})
    rows = []
    for label in labels:
        start_str, end_str = label.split("_")
        start_year = 2000 + int(start_str)
        end_year = 2000 + int(end_str)
        rows.append((label, start_year, end_year))

    with conn.cursor() as cur:
        execute_values(
            cur,
            """
            INSERT INTO seasons (label, start_year, end_year)
            VALUES %s
            ON CONFLICT (label) DO NOTHING
            """,
            rows,
        )
    conn.commit()
    print(f"[seasons] {len(rows)} stagioni verificate/inserite: {labels}")


def get_season_id_map(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT label, season_id FROM seasons")
        return dict(cur.fetchall())


# ------------------------------------------------------------------
# Step 2 — carica i CSV Understat grezzi
# ------------------------------------------------------------------

def load_understat_csv(conn, filepath: Path, season_id: int, season_label: str):
    df = pd.read_csv(filepath, sep=";", quotechar='"')

    # Le colonne CSV sono: number;player;team;apps;min;goals;a;xG;xA;xG90;xA90
    rows = [
        (
            season_id,
            int(r["number"]) if pd.notna(r["number"]) else None,
            r["player"],
            r["team"] if pd.notna(r["team"]) else None,
            int(r["apps"]) if pd.notna(r["apps"]) else None,
            int(r["min"]) if pd.notna(r["min"]) else None,
            int(r["goals"]) if pd.notna(r["goals"]) else None,
            int(r["a"]) if pd.notna(r["a"]) else None,
            float(r["xG"]) if pd.notna(r["xG"]) else None,
            float(r["xA"]) if pd.notna(r["xA"]) else None,
            float(r["xG90"]) if pd.notna(r["xG90"]) else None,
            float(r["xA90"]) if pd.notna(r["xA90"]) else None,
        )
        for _, r in df.iterrows()
    ]

    with conn.cursor() as cur:
        execute_values(
            cur,
            """
            INSERT INTO understat_player_season
                (season_id, understat_number, player_name_raw, team_raw,
                 apps, minutes, goals, assists, xg, xa, xg90, xa90)
            VALUES %s
            ON CONFLICT (season_id, player_name_raw, team_raw) DO NOTHING
            """,
            rows,
        )
    conn.commit()
    print(f"[understat] {season_label}: {len(rows)} righe lette da {filepath.name}")


# ------------------------------------------------------------------
# Step 3 — carica il listino xlsx
# ------------------------------------------------------------------

def load_listino(conn, filepath: Path, season_id: int):
    df = pd.read_excel(filepath)

    rows = []
    for _, r in df.iterrows():
        fuori_lista = r["Fuori lista"] == "*" if pd.notna(r["Fuori lista"]) else False
        rows.append((
            season_id,
            r["Nome"],
            r["Sq."] if pd.notna(r["Sq."]) else None,
            r["R."] if pd.notna(r["R."]) else None,
            float(r["PGv"]) if pd.notna(r["PGv"]) else None,
            float(r["MV"]) if pd.notna(r["MV"]) else None,
            float(r["FM"]) if pd.notna(r["FM"]) else None,
            float(r["FVM/1000"]) if pd.notna(r["FVM/1000"]) else None,
            float(r["QUOT."]) if pd.notna(r["QUOT."]) else None,
            fuori_lista,
            int(r["Under"]) if pd.notna(r["Under"]) else None,
            r["FantaSquadra"] if pd.notna(r["FantaSquadra"]) else None,
            float(r["Costo"]) if pd.notna(r["Costo"]) else None,
        ))

    with conn.cursor() as cur:
        execute_values(
            cur,
            """
            INSERT INTO fantagazzetta_listino
                (season_id, nome_raw, squadra, ruolo, pgv, mv, fm, fvm_1000,
                 quot, fuori_lista, age, fantasquadra, costo)
            VALUES %s
            ON CONFLICT (season_id, nome_raw) DO NOTHING
            """,
            rows,
        )
    conn.commit()
    print(f"[listino] {len(rows)} righe lette da {filepath.name}")


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------

def main():
    if not DB_CONFIG["password"]:
        raise SystemExit(
            "Manca DB_PASSWORD. Crea un file .env nella root del repo "
            "(vedi .env.example) prima di rilanciare lo script."
        )
    if not UNDERSTAT_DIR.exists():
        raise SystemExit(f"Cartella non trovata: {UNDERSTAT_DIR}")
    if not LISTINO_PATH.exists():
        raise SystemExit(f"File non trovato: {LISTINO_PATH}")

    conn = psycopg2.connect(**DB_CONFIG)
    try:
        load_seasons(conn)
        season_ids = get_season_id_map(conn)

        for filename, label in UNDERSTAT_FILES.items():
            filepath = UNDERSTAT_DIR / filename
            if not filepath.exists():
                print(f"[ATTENZIONE] file mancante, salto: {filepath}")
                continue
            load_understat_csv(conn, filepath, season_ids[label], label)

        load_listino(conn, LISTINO_PATH, season_ids[LISTINO_SEASON_LABEL])

    finally:
        conn.close()

    print("\nMigrazione completata.")


if __name__ == "__main__":
    main()


# ------------------------------------------------------------------
# Note: come ricaricare da zero una tabella dopo una correzione
# ------------------------------------------------------------------
# TRUNCATE TABLE understat_player_season RESTART IDENTITY CASCADE;
# TRUNCATE TABLE fantagazzetta_listino RESTART IDENTITY CASCADE;
# (CASCADE serve perche' altre tabelle referenziano player_id;
#  in questa fase non c'e' ancora nulla collegato, quindi e' sicuro)
