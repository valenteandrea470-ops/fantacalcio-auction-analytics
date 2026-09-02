"""
export_data.py — FUTDRAFT27

Esporta i dati aggregati (QUOT. consenso 26/27, affidabilita'/per-90,
confronto FantaLab, tag) in dashboard/data.js — una singola variabile
JS incorporata nel file, cosi' la dashboard si apre offline via
doppio click senza bisogno di server o fetch() (bloccato da CORS su
file://). Vedi SESSION_LOG per la decisione.

Uso:
    python3 src/export_data.py
"""

import json
import os

import pandas as pd
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "dbname": os.environ.get("DB_NAME", "futdraft27"),
    "user": os.environ.get("DB_USER", "weez"),
    "password": os.environ.get("DB_PASSWORD"),
}

TARGET_MODEL_VERSION = "v1_2627_consenso"
OUTPUT_PATH = "dashboard/data.js"


def carica_base(conn):
    query = """
        SELECT player_id, nome_canonico, ruolo,
               n_prezzi_validi, prezzo_mediano, prezzo_min, prezzo_max,
               quot_2526_fallback, quot_consenso_2627, dato_stimato
        FROM v_quotazioni_consenso_2627
    """
    return pd.read_sql(query, conn)


def carica_affidabilita(conn):
    query = """
        SELECT player_id, n_stagioni_valide, minuti_totali,
               goals_90, assists_90, xg90, xa90,
               indice_affidabilita, dato_stimato AS metriche_stimate
        FROM player_metrics_snapshot
        WHERE model_version = %s
    """
    return pd.read_sql(query, conn, params=(TARGET_MODEL_VERSION,))


def carica_confronto(conn):
    query = """
        SELECT player_id, n_fonti_totali, prezzo_min AS confronto_min,
               prezzo_max AS confronto_max, stddev_prezzo,
               prezzi_per_fonte, fasce_per_fonte
        FROM v_fantalab_confronto
    """
    df = pd.read_sql(query, conn)
    for col in ("prezzi_per_fonte", "fasce_per_fonte"):
        df[col] = df[col].apply(lambda v: v if v is not None else {})
    return df


def carica_tag(conn):
    query = """
        SELECT DISTINCT ON (player_id, tag) player_id, tag
        FROM player_tags
        WHERE scaricato_il = (SELECT max(scaricato_il) FROM player_tags)
        ORDER BY player_id, tag
    """
    df = pd.read_sql(query, conn)
    return df.groupby("player_id")["tag"].apply(list).reset_index()


def costruisci_dataset(conn):
    base = carica_base(conn)
    affidabilita = carica_affidabilita(conn)
    confronto = carica_confronto(conn)
    tag = carica_tag(conn)

    df = base.merge(affidabilita, on="player_id", how="left")
    df = df.merge(confronto, on="player_id", how="left")
    df = df.merge(tag, on="player_id", how="left")
    df["tag"] = df["tag"].apply(lambda v: v if isinstance(v, list) else [])

    df = df.where(pd.notnull(df), None)
    return df.to_dict(orient="records")


def scrivi_output(records):
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write("// Generato da export_data.py — non modificare a mano\n")
        f.write("const PLAYERS_DATA = ")
        json.dump(records, f, ensure_ascii=False, indent=2, default=str)
        f.write(";\n")
    print(f"[export] {len(records)} giocatori scritti in {OUTPUT_PATH}")


def main():
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        records = costruisci_dataset(conn)
        scrivi_output(records)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
