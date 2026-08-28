"""
load_provenienza_orfani.py — FUTDRAFT27

Carica orfani_classificati.xlsx (compilato a mano da Andrea: categoria,
lega di provenienza, presenze/gol/assist da Transfermarkt) dentro
player_provenienza. Il match a players e' diretto (nome_canonico +
ruolo esatti), non fuzzy, perche' questi player_id sono nati da questi
stessi nomi durante il carico FantaLab orfani.

Uso:
    python3 src/load_provenienza_orfani.py /path/to/orfani_classificati.xlsx \
        --data 2026-08-28
"""

import os
import argparse

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

# Mappatura lega/club/paese di provenienza -> lega normalizzata.
# True = da verificare (incertezza segnalata ad Andrea, non confermata).
MAPPATURA_LEGA = {
    "liga": ("La Liga (Spagna)", False),
    "getafe": ("La Liga (Spagna)", False),
    "villareal": ("La Liga (Spagna)", False),
    "barca b": ("Primera RFEF / Segunda B (Spagna)", False),
    "bundes": ("Bundesliga (Germania)", False),
    "bundesliga": ("Bundesliga (Germania)", False),
    "premier": ("Premier League (Inghilterra)", False),
    "arsenal": ("Premier League (Inghilterra)", False),
    "tottenham": ("Premier League (Inghilterra)", False),
    "leicester city": ("Premier League (Inghilterra)", True),
    "ligue 1": ("Ligue 1 (Francia)", False),
    "troyes-ligue 1": ("Ligue 1 (Francia)", False),
    "psg-ligue1": ("Ligue 1 (Francia)", False),
    "francia": ("Ligue 1 (Francia)", True),
    "psg academy": (None, True),  # giovanile, non lega senior
    "ajax": ("Eredivisie (Olanda)", False),
    "benfica": ("Primeira Liga (Portogallo)", False),
    "portogallo": ("Primeira Liga (Portogallo)", False),
    "belgio": ("Jupiler Pro League (Belgio)", False),
    "polonia": ("Ekstraklasa (Polonia)", False),
    "austria": ("Bundesliga (Austria)", False),
    "norvegia": ("Eliteserien (Norvegia)", False),
    "rep. ceca": ("Fortuna Liga (Rep. Ceca)", False),
    "argentina": ("Liga Profesional (Argentina)", False),
    "cruzeiro": ("Brasileirao (Brasile)", False),
    "gremio": ("Brasileirao (Brasile)", False),
    "trabzonspor": ("Super Lig (Turchia)", False),
    "mls": ("MLS (USA/Canada)", False),
    "campionato sloveno": ("PrvaLiga (Slovenia)", False),
    "al-najma": (None, True),
    "giovanili empoli 2015": (None, True),  # percorso Italia->estero->rientro
}


def normalizza_lega(raw):
    if pd.isna(raw) or not str(raw).strip():
        return None, False
    chiave = str(raw).strip().lower()
    if chiave in MAPPATURA_LEGA:
        return MAPPATURA_LEGA[chiave]
    return None, True  # sconosciuto -> lasciato grezzo, marcato da verificare


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("path_xlsx")
    parser.add_argument("--data", required=True, help="Formato YYYY-MM-DD")
    args = parser.parse_args()

    df = pd.read_excel(args.path_xlsx, sheet_name="Orfani", header=2)
    df = df[df["note"] != "Esempio di riga compilata"]

    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    inseriti = 0
    non_trovati = []

    for _, riga in df.iterrows():
        nome_raw = str(riga["nome_raw"]).strip()
        ruolo = str(riga["ruolo_fantalab"]).strip()

        cur.execute(
            "SELECT player_id FROM players WHERE nome_canonico = %s AND ruolo = %s",
            (nome_raw, ruolo),
        )
        risultato = cur.fetchone()
        if risultato is None:
            non_trovati.append((nome_raw, ruolo))
            continue
        player_id = risultato[0]

        lega_norm, da_verificare = normalizza_lega(riga.get("lega_provenienza"))

        def pulisci_int(v):
            return None if pd.isna(v) else int(v)

        cur.execute(
            """
            INSERT INTO player_provenienza
                (player_id, categoria, lega_provenienza_raw, lega_provenienza_norm,
                 lega_da_verificare, presenze, gol, assist, note, compilato_il)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (player_id) DO UPDATE SET
                categoria = EXCLUDED.categoria,
                lega_provenienza_raw = EXCLUDED.lega_provenienza_raw,
                lega_provenienza_norm = EXCLUDED.lega_provenienza_norm,
                lega_da_verificare = EXCLUDED.lega_da_verificare,
                presenze = EXCLUDED.presenze,
                gol = EXCLUDED.gol,
                assist = EXCLUDED.assist,
                note = EXCLUDED.note,
                compilato_il = EXCLUDED.compilato_il
            """,
            (
                player_id,
                str(riga["categoria"]).strip(),
                riga.get("lega_provenienza") if pd.notna(riga.get("lega_provenienza")) else None,
                lega_norm,
                da_verificare,
                pulisci_int(riga.get("presenze")),
                pulisci_int(riga.get("gol")),
                pulisci_int(riga.get("assist")),
                riga.get("note") if pd.notna(riga.get("note")) else None,
                args.data,
            ),
        )
        inseriti += 1

    conn.commit()
    conn.close()

    print(f"Righe inserite/aggiornate: {inseriti}")
    if non_trovati:
        print(f"\nATTENZIONE — {len(non_trovati)} righe senza player_id corrispondente:")
        for nome, ruolo in non_trovati:
            print(f"  {nome} ({ruolo})")


if __name__ == "__main__":
    main()
