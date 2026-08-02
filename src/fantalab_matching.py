"""
fantalab_matching.py — FUTDRAFT27

Carica le valutazioni FantaLab (VCAF_Ep__3.xlsx, 4 sheet P/D/C/A) e le
collega ai player_id gia' esistenti (creati da name_matching.py sul
listino 25/26). Riusa rimuovi_accenti e load_listino_df da
name_matching.py; il fallback fuzzy e' diverso perche' i nomi FantaLab
sono gia' vicini al formato Fantagazzetta (cognome, o "Cognome I."),
non nome-completo come Understat.

Righe senza match diventano player_id "orfani" (match_method =
'orphan_created') — vedi sql/004_fantalab_match_lineage.sql per il
lineage, tenuto dentro fantalab_valutazioni stessa.

Uso:
    python src/fantalab_matching.py /path/to/VCAF_Ep__3.xlsx \
        --strategia "CarmySpecial" --data 2026-07-31
"""

import os
import re
import argparse

import pandas as pd
import psycopg2
from dotenv import load_dotenv

from name_matching import rimuovi_accenti, load_listino_df

load_dotenv()

DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "dbname": os.environ.get("DB_NAME", "futdraft27"),
    "user": os.environ.get("DB_USER", "weez"),
    "password": os.environ.get("DB_PASSWORD"),
}

LISTINO_SEASON_LABEL = "25_26"

SHEET_TO_RUOLO = {"P": "P", "D": "D", "C": "C", "A": "A"}

TAG_COLUMNS = ["Nota 1", "Nota 2", "Nota 3", "Nota 4", "Nota 5"]


# ------------------------------------------------------------------
# Matching — fallback diverso da trova_corrispondenza (vedi docstring)
# ------------------------------------------------------------------
def _strip_iniziale(nome_pulito):
    """'Paz N.' -> 'Paz'; 'Dimarco' -> 'Dimarco' (nessuna iniziale da staccare)."""
    return re.sub(r"\s+[A-Za-z]\.?$", "", nome_pulito).strip()


def _ha_iniziale(nome_pulito):
    """True se il nome porta gia' un'iniziale finale (es. 'El Azzouzi A.')."""
    return bool(re.search(r"\s+[A-Za-z]\.?$", nome_pulito))


def trova_corrispondenza_fantalab(nome_fantalab_raw, listino_df):
    """Ritorna (nome_raw_matchato, match_method, confidence) oppure (None, None, None)."""
    nome_pulito = rimuovi_accenti(str(nome_fantalab_raw)).replace("'", "").strip()

    match_esatto = listino_df[listino_df["nome_pulito"].str.lower() == nome_pulito.lower()]
    if len(match_esatto) == 1:
        return match_esatto.iloc[0]["nome_raw"], "exact", None

    # Fallback SOLO se FantaLab non ha gia' scritto un'iniziale disambiguante.
    # Se ce l'ha (es. "El Azzouzi A."), toglierla rischia di far collassare
    # due giocatori diversi sullo stesso player_id (bug trovato il 02/08 su
    # El Azzouzi Bologna vs Frosinone) — meglio un orfano che un match sbagliato.
    if _ha_iniziale(nome_pulito):
        return None, None, None

    cognome = nome_pulito
    match_cognome = listino_df[
        listino_df["nome_pulito"].apply(_strip_iniziale).str.lower() == cognome.lower()
    ]
    if len(match_cognome) == 1:
        return match_cognome.iloc[0]["nome_raw"], "fuzzy", 0.75

    return None, None, None

#-------------------------------------------------------------------
# Parsing colonne FantaLab (Budget/PMA arrivano come stringhe sporche)
# ------------------------------------------------------------------
def _parse_pct(valore):
    if pd.isna(valore):
        return None
    testo = str(valore).replace("%", "").replace(",", ".").strip()
    if not testo:
        return None
    try:
        return float(testo)
    except ValueError:
        return None


def _parse_bool_si_no(valore):
    if pd.isna(valore):
        return None
    return str(valore).strip().lower() in ("si", "sí", "s")


def _parse_int(valore):
    if pd.isna(valore):
        return None
    try:
        return int(valore)
    except (ValueError, TypeError):
        return None


def _parse_num(valore):
    if pd.isna(valore):
        return None
    try:
        return float(valore)
    except (ValueError, TypeError):
        return None


# ------------------------------------------------------------------
# Caricamento di un singolo sheet
# ------------------------------------------------------------------
def process_sheet(conn, listino_df, path_xlsx, sheet_name, strategia, scaricato_il):
    ruolo = SHEET_TO_RUOLO[sheet_name]
    df = pd.read_excel(path_xlsx, sheet_name=sheet_name)

    stats = {"exact": 0, "fuzzy": 0, "orphan_created": 0, "vuote_saltate": 0}

    valutazioni_rows = []
    tag_rows = []

    for _, riga in df.iterrows():
        nome_raw_fantalab = riga.get("Nome")
        if pd.isna(nome_raw_fantalab) or not str(nome_raw_fantalab).strip():
            stats["vuote_saltate"] += 1
            continue

        nome_matchato, metodo, confidenza = trova_corrispondenza_fantalab(nome_raw_fantalab, listino_df)

        if nome_matchato is not None:
            player_id = int(listino_df.loc[listino_df["nome_raw"] == nome_matchato, "player_id"].iloc[0])
        else:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO players (nome_canonico, ruolo) VALUES (%s, %s) RETURNING player_id",
                    (str(nome_raw_fantalab).strip(), ruolo),
                )
                player_id = cur.fetchone()[0]
            metodo = "orphan_created"
            confidenza = None

        stats[metodo] += 1

        valutazioni_rows.append(
            {
                "player_id": player_id,
                "fonte": "fantalab",
                "strategia": strategia,
                "scaricato_il": scaricato_il,
                "nome_raw": str(nome_raw_fantalab).strip(),
                "ruolo_fantalab": ruolo,
                "squadra_fantalab": riga.get("Team"),
                "obiettivo": _parse_bool_si_no(riga.get("Obiett.")),
                "fascia": riga.get("Fascia"),
                "prezzo": _parse_num(riga.get("Prezzo")),
                "budget_pct": _parse_pct(riga.get("Budget")),
                "pma_pct": _parse_pct(riga.get("PMA")),
                "quo": _parse_num(riga.get("Quo")),
                "titolarita": _parse_int(riga.get("Titolarità")),
                "affidabilita": _parse_int(riga.get("Affidabilità")),
                "integrita": _parse_int(riga.get("Integrità")),
                "commento": riga.get("Commento") or None,
                "mv": _parse_num(riga.get("MV")),
                "fmv": _parse_num(riga.get("FMV")),
                "fmv_exp": _parse_num(riga.get("FMV Exp.")),
                "presenze": _parse_int(riga.get("Presenze")),
                "pt_titolare": _parse_int(riga.get("Pt. Tit.")),
                "minuti": _parse_int(riga.get("Minuti")),
                "pt_infortunio": _parse_int(riga.get("Pt. Inf.")),
                "gol": _parse_int(riga.get("Gol")),
                "assist": _parse_int(riga.get("Assist")),
                "ammonizioni": _parse_int(riga.get("Ammonizioni")),
                "espulsioni": _parse_int(riga.get("Espulsioni")),
                "rig_segnati": _parse_int(riga.get("Rig. Segnati")),
                "rig_sbagliati": _parse_int(riga.get("Rig. Sbagliati")),
                "gol_subiti": _parse_int(riga.get("Gol Subiti")),
                "rig_parati": _parse_int(riga.get("Rig. Parati")),
                "match_method": metodo,
                "match_confidence": confidenza,
            }
        )

        for col in TAG_COLUMNS:
            tag = riga.get(col)
            if pd.notna(tag) and str(tag).strip():
                tag_rows.append((player_id, str(tag).strip(), "fantalab", scaricato_il))

    colonne = list(valutazioni_rows[0].keys()) if valutazioni_rows else []
    with conn.cursor() as cur:
        for row in valutazioni_rows:
            placeholders = ", ".join(["%s"] * len(colonne))
            cur.execute(
                f"INSERT INTO fantalab_valutazioni ({', '.join(colonne)}) VALUES ({placeholders})",
                [row[c] for c in colonne],
            )
        for player_id, tag, fonte, data in tag_rows:
            cur.execute(
                """
                INSERT INTO player_tags (player_id, tag, fonte, scaricato_il)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (player_id, tag, fonte, scaricato_il) DO NOTHING
                """,
                (player_id, tag, fonte, data),
            )

    conn.commit()

    print(
        f"[{sheet_name}] {len(valutazioni_rows)} righe caricate — "
        f"exact: {stats['exact']}, fuzzy: {stats['fuzzy']}, "
        f"orphan: {stats['orphan_created']}, vuote saltate: {stats['vuote_saltate']}, "
        f"tag inseriti: {len(tag_rows)}"
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("path_xlsx")
    parser.add_argument("--strategia", required=True)
    parser.add_argument("--data", required=True, help="Formato YYYY-MM-DD")
    parser.add_argument(
        "--sheets", default="P,D,C,A",
        help="Sheet da processare, separate da virgola (default: tutte)"
    )
    args = parser.parse_args()

    conn = psycopg2.connect(**DB_CONFIG)
    try:
        listino_df = load_listino_df(conn, LISTINO_SEASON_LABEL)
        for sheet_name in args.sheets.split(","):
            process_sheet(conn, listino_df, args.path_xlsx, sheet_name, args.strategia, args.data)
    finally:
        conn.close()

    print("\nCaricamento FantaLab completato.")


if __name__ == "__main__":
    main()

