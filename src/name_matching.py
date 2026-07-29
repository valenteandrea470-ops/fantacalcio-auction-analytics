"""
name_matching.py — FUTDRAFT27

Collega i giocatori Understat (storico multi-stagione) ai giocatori del
listino Fantagazzetta 25/26, riusando la logica di matching gia'
validata nel notebook originale (rimuovi_accenti, estrai_cognome_iniziale,
trova_corrispondenza, mappatura_manuale) — non riscritta, solo portata
a scrivere su Postgres invece che su un DataFrame in-memory.

Ogni riga del listino 25/26 diventa un player_id canonico. Le stagioni
Understat storiche si agganciano a quel player_id quando il matching
va a buon fine; il metodo e l'eventuale confidenza vengono salvati in
player_name_matches per trasparenza (e per poterli filtrare in dashboard).

Idempotente: righe gia' matchate (player_id NOT NULL) vengono saltate.

Uso:
    python src/migrate_data.py   # se non gia' fatto
    python src/name_matching.py
"""

import os
import unicodedata

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

LISTINO_SEASON_LABEL = "25_26"


# ------------------------------------------------------------------
# Funzioni di matching — portate 1:1 dal notebook, non riscritte
# ------------------------------------------------------------------

def rimuovi_accenti(testo):
    if pd.isna(testo):
        return testo
    sostituzioni_speciali = {
        "ø": "o", "Ø": "O", "æ": "ae", "Æ": "AE", "å": "a", "Å": "A",
        "ł": "l", "Ł": "L", "đ": "d", "Đ": "D", "ð": "d", "Ð": "D",
        "ß": "ss", "ı": "i",
    }
    for carattere, sostituto in sostituzioni_speciali.items():
        testo = testo.replace(carattere, sostituto)
    return ''.join(
        c for c in unicodedata.normalize('NFD', testo)
        if unicodedata.category(c) != 'Mn'
    )


def estrai_cognome_iniziale(nome_completo):
    parti = nome_completo.split()
    cognome = parti[-1]
    iniziale = parti[0][0] if parti else ""
    return cognome, iniziale


MAPPATURA_MANUALE = {
    "Francesco Pio Esposito": "Esposito F.P.",
    "Sebastiano Esposito": "Esposito Se.",
    "Lucas Da Cunha": "Da Cunha",
    "Kevin De Bruyne": "De Bruyne",
    "Charles De Ketelaere": "De Ketelaere",
    "Stephan El Shaarawy": "El Shaarawy",
    "Enrico Del Prato": "Delprato",
    "Giovanni Di Lorenzo": "Di Lorenzo",
    "Manuel De Luca": "De Luca",
    "Marten de Roon": "De Roon",
    "Mehmet Zeki Çelik": "Celik",
    "Koni de Winter": "De Winter",
    "Neil El Aynaoui": "El Aynaoui",
    "David de Gea": "De Gea",
    "Lorenzo De Silvestri": "De Silvestri",
    "Franco Ezequiel Carboni": "Carboni F.",
    "Alessandro Di Pardo": "Di Pardo",
    "Michele Di Gregorio": "Di Gregorio",
    "Raffaele Di Gennaro": "Di Gennaro",
    "Ignace Van der Brempt": None,
    "Matías Soulé Malvano": None,
    "Thomas Thiesson Kristensen": "Kristensen T.",
    "Pierre Kalulu Kyatengwa": "Kalulu",
    "Andréa Le Borgne": None,
    "Simone Lottici Tessardi": None,
    "Hans Nicolussi Caviglia": "Nicolussi Caviglia",
    "Armel Bella Kotchap": "Bella-Kotchap",
    "Carlos Augusto": "Carlos Augusto",
    "Luis Henrique": "Luis Henrique",
    "Vitinha": "Vitinha O.",
    "Kouadio Koné": "Konè M.",
    "Ismaël Koné": "Konè I.",
    "Lorenzo Pellegrini": "Pellegrini Lo.",
}


def trova_corrispondenza(nome_completo_stats, listino_df):
    """Ritorna (nome_raw_matchato, match_method, confidence_score) oppure (None, None, None)."""
    if nome_completo_stats in MAPPATURA_MANUALE:
        nome_target = MAPPATURA_MANUALE[nome_completo_stats]
        if nome_target is None:
            return None, None, None
        match = listino_df[listino_df["nome_raw"] == nome_target]
        if not match.empty:
            return match.iloc[0]["nome_raw"], "manual", None

    nome_pulito = rimuovi_accenti(nome_completo_stats).replace("'", "")
    cognome, iniziale = estrai_cognome_iniziale(nome_pulito)

    nome_con_iniziale = f"{cognome} {iniziale}."
    match_iniziale = listino_df[listino_df["nome_pulito"].str.lower() == nome_con_iniziale.lower()]
    if len(match_iniziale) == 1:
        return match_iniziale.iloc[0]["nome_raw"], "fuzzy", 0.90

    match_diretto = listino_df[listino_df["nome_pulito"].str.lower() == cognome.lower()]
    if len(match_diretto) == 1:
        return match_diretto.iloc[0]["nome_raw"], "fuzzy", 0.70

    return None, None, None


# ------------------------------------------------------------------
# Step 1 — crea un player_id per ogni riga del listino 25/26
# ------------------------------------------------------------------

def ensure_players_from_listino(conn, season_label):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT fl.id, fl.nome_raw, fl.ruolo
            FROM fantagazzetta_listino fl
            JOIN seasons s ON s.season_id = fl.season_id
            WHERE s.label = %s AND fl.player_id IS NULL
            """,
            (season_label,),
        )
        righe_da_collegare = cur.fetchall()

        for listino_id, nome_raw, ruolo in righe_da_collegare:
            cur.execute(
                "INSERT INTO players (nome_canonico, ruolo) VALUES (%s, %s) RETURNING player_id",
                (nome_raw, ruolo),
            )
            player_id = cur.fetchone()[0]
            cur.execute(
                "UPDATE fantagazzetta_listino SET player_id = %s WHERE id = %s",
                (player_id, listino_id),
            )
    conn.commit()
    print(f"[players] {len(righe_da_collegare)} nuovi player creati dal listino {season_label}")


def load_listino_df(conn, season_label):
    query = """
        SELECT fl.player_id, fl.nome_raw
        FROM fantagazzetta_listino fl
        JOIN seasons s ON s.season_id = fl.season_id
        WHERE s.label = %s
    """
    df = pd.read_sql(query, conn, params=(season_label,))
    df["nome_pulito"] = df["nome_raw"].apply(rimuovi_accenti).str.replace("'", "", regex=False)
    return df


# ------------------------------------------------------------------
# Step 2 — matching per ogni stagione Understat
# ------------------------------------------------------------------

def match_season(conn, season_label, listino_df):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT u.id, u.player_name_raw
            FROM understat_player_season u
            JOIN seasons s ON s.season_id = u.season_id
            WHERE s.label = %s AND u.player_id IS NULL
            """,
            (season_label,),
        )
        righe = cur.fetchall()

    aggiornamenti = []
    lineage = []
    for understat_id, nome_stats in righe:
        nome_matchato, metodo, confidenza = trova_corrispondenza(nome_stats, listino_df)
        if nome_matchato is None:
            continue
        player_id = int(listino_df.loc[listino_df["nome_raw"] == nome_matchato, "player_id"].iloc[0])
        aggiornamenti.append((player_id, understat_id))
        lineage.append((player_id, nome_stats, nome_matchato, metodo, confidenza))

    with conn.cursor() as cur:
        cur.executemany(
            "UPDATE understat_player_season SET player_id = %s WHERE id = %s",
            aggiornamenti,
        )
        if lineage:
            execute_values(
                cur,
                """
                INSERT INTO player_name_matches
                    (player_id, understat_name_raw, fantagazzetta_name_raw, match_method, confidence_score)
                VALUES %s
                """,
                lineage,
            )
    conn.commit()

    totale = len(righe)
    trovati = len(aggiornamenti)
    pct = round(trovati / totale * 100, 1) if totale else 0.0
    print(f"[match] {season_label}: {trovati}/{totale} corrispondenze ({pct}%)")


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------

def main():
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        ensure_players_from_listino(conn, LISTINO_SEASON_LABEL)
        listino_df = load_listino_df(conn, LISTINO_SEASON_LABEL)

        with conn.cursor() as cur:
            cur.execute("SELECT label FROM seasons ORDER BY label")
            tutte_le_stagioni = [r[0] for r in cur.fetchall()]

        for label in tutte_le_stagioni:
            match_season(conn, label, listino_df)

    finally:
        conn.close()

    print("\nMatching completato.")


if __name__ == "__main__":
    main()
