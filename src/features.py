"""
features.py — FUTDRAFT27

Calcola le metriche derivate multi-stagione per ogni giocatore e le
scrive in player_metrics_snapshot, versionate sotto MODEL_VERSION.

Porta la logica gia' validata nel notebook (medie pesate per
recenza x minuti, trend via regressione lineare, indice_affidabilita,
shrinkage estimator per giocatori con storico scarso). Unica modifica
di sostanza: indice_convenienza calcolato come scarto percentuale
(FM/QUOT - 1) * 100 invece della formula originale FM/(QUOT+1), per
leggibilita' in dashboard (deciso il 30/07, vedi docs/SESSION_LOG.md).

Le soglie sotto sono tutte arbitrarie (euristiche da buon senso
calcistico, non da analisi statistica) e isolate qui apposta: sono il
punto di intervento quando arrivera' la fase di backtest con
regressione per ruolo, che le sostituira' con coefficienti stimati.

Uso (dopo migrate_data.py e name_matching.py):
    python src/features.py
"""

import os

import numpy as np
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

TARGET_SEASON_LABEL = "26_27"   # stagione per cui calcoliamo lo snapshot (l'asta di riferimento)
MODEL_VERSION = "v1_2627_consenso"

ORDINE_STAGIONI = ["21_22", "22_23", "23_24", "24_25", "25_26"]
METRICHE = ["goals_90", "assists_90", "xg90", "xa90"]

# --- Soglie arbitrarie, da rivedere in fase di backtest con regressione ---
SOGLIA_MINUTI = 450        # sotto questa soglia il dato per-90 di una stagione non e' affidabile (~5 partite intere)
MINUTI_RIFERIMENTO = 1500  # minutaggio a cui diamo piena fiducia ai dati grezzi del giocatore per lo shrinkage
                            # NOTA: corrisponde a un giocatore di rotazione (~16-17 partite), non a un titolare
                            # vero (che sta piu' vicino a 2250-3000 min) — commento del notebook originale era
                            # fuorviante su questo punto, corretto qui
SOGLIA_PGV = 10             # presenze minime con voto perche' l'FM sia considerato statisticamente affidabile
SOGLIA_QUOT = 5             # sotto questa QUOT. il rapporto FM/QUOT esplode ed e' poco significativo
                            # (es. QUOT=1 rende qualunque FM decente un "+400%" fuorviante)

# ------------------------------------------------------------------
# Step 1 — carica i dati grezzi (storico Understat matchato + contesto listino)
# ------------------------------------------------------------------

def carica_storico_attivi(conn):
    query = """
        SELECT u.player_id, s.label AS stagione,
               u.minutes AS min, u.goals, u.assists AS a,
               u.xg, u.xa, u.xg90, u.xa90
        FROM understat_player_season u
        JOIN seasons s ON s.season_id = u.season_id
        WHERE u.player_id IS NOT NULL
    """
    df = pd.read_sql(query, conn)
    df["goals_90"] = (df["goals"] / df["min"]) * 90
    df["assists_90"] = (df["a"] / df["min"]) * 90
    df["ordine"] = df["stagione"].apply(lambda s: ORDINE_STAGIONI.index(s))
    return df


def carica_contesto_listino(conn, season_label):
    query = """
        SELECT fl.player_id, fl.ruolo, fl.quot, fl.fm, fl.mv, fl.pgv
        FROM fantagazzetta_listino fl
        JOIN seasons s ON s.season_id = fl.season_id
        WHERE s.label = %s AND fl.player_id IS NOT NULL
    """
    return pd.read_sql(query, conn, params=(season_label,))

def carica_contesto_2627(conn):
    """Contesto per la stagione 26/27: ruolo e QUOT. dalla vista di
    consenso (nessun listino ufficiale disponibile, vedi SESSION_LOG
    01/09). fm/mv/pgv non esistono ancora (stagione non giocata) —
    NULL esplicito, non un dato mancante per errore. Conseguenza
    attesa e accettata: indice_convenienza_pct sara' NaN per tutti,
    perche' il calcolo richiede un fm reale che qui non c'e'."""
    query = """
        SELECT player_id, ruolo,
               quot_consenso_2627 AS quot,
               NULL::numeric AS fm,
               NULL::numeric AS mv,
               NULL::integer AS pgv
        FROM v_quotazioni_consenso_2627
        WHERE player_id IS NOT NULL
    """
    return pd.read_sql(query, conn)

# ------------------------------------------------------------------
# Step 2 — media pesata per recenza x minuti (solo stagioni sopra soglia)
# ------------------------------------------------------------------

def calcola_media_pesata(gruppo):
    valide = gruppo[gruppo["min"] >= SOGLIA_MINUTI].sort_values("ordine").copy()

    if len(valide) == 0:
        return pd.Series(
            {f"{m}_pesata": None for m in METRICHE}
            | {"n_stagioni_valide": 0, "minuti_totali": gruppo["min"].sum()}
        )

    valide["peso_recenza"] = range(1, len(valide) + 1)
    valide["peso_finale"] = valide["peso_recenza"] * valide["min"]

    risultato = {
        f"{m}_pesata": (valide[m] * valide["peso_finale"]).sum() / valide["peso_finale"].sum()
        for m in METRICHE
    }
    risultato["n_stagioni_valide"] = len(valide)
    risultato["minuti_totali"] = gruppo["min"].sum()
    return pd.Series(risultato)


# ------------------------------------------------------------------
# Step 3 — trend (pendenza regressione lineare sulle stagioni valide)
# ------------------------------------------------------------------

def calcola_trend(gruppo):
    valide = gruppo[gruppo["min"] >= SOGLIA_MINUTI].sort_values("ordine").copy()
    n_valide = len(valide)

    risultato = {}
    if n_valide < 2:
        for m in METRICHE:
            risultato[f"{m}_trend"] = None
    else:
        x = valide["ordine"].values
        for m in METRICHE:
            y = valide[m].values
            risultato[f"{m}_trend"] = np.polyfit(x, y, 1)[0]

    return pd.Series(risultato)


# ------------------------------------------------------------------
# Step 4 — indice di affidabilita' (30% storico + 70% costanza)
# ------------------------------------------------------------------

def calcola_affidabilita_raw(gruppo):
    valide = gruppo[gruppo["min"] >= SOGLIA_MINUTI]
    n_valide = len(valide)
    return pd.Series({
        "n_stagioni_valide": n_valide,
        "minuti_totali": gruppo["min"].sum(),
        "goals_90_std": valide["goals_90"].std() if n_valide >= 2 else None,
        "goals_90_media": valide["goals_90"].mean() if n_valide >= 1 else None,
    })


def calcola_indice_affidabilita(affidabilita_raw):
    max_stagioni = affidabilita_raw["n_stagioni_valide"].max()
    max_minuti = affidabilita_raw["minuti_totali"].max()

    affidabilita_raw["score_storico"] = (
        0.5 * (affidabilita_raw["n_stagioni_valide"] / max_stagioni)
        + 0.5 * (affidabilita_raw["minuti_totali"] / max_minuti)
    ) * 100

    def score_costanza(row):
        if row["n_stagioni_valide"] < 2 or not row["goals_90_media"]:
            return 0
        cv = row["goals_90_std"] / row["goals_90_media"]
        return max(0, (1 - cv)) * 100

    affidabilita_raw["score_costanza"] = affidabilita_raw.apply(score_costanza, axis=1)
    affidabilita_raw["indice_affidabilita"] = (
        0.30 * affidabilita_raw["score_storico"] + 0.70 * affidabilita_raw["score_costanza"]
    )
    return affidabilita_raw


# ------------------------------------------------------------------
# Step 5 — shrinkage estimator per chi ha n_stagioni_valide == 0
# ------------------------------------------------------------------

def calcola_stat_grezze(gruppo):
    min_tot = gruppo["min"].sum()
    if min_tot == 0:
        return pd.Series({f"{m}_grezza": np.nan for m in METRICHE} | {"min_tot_grezzo": 0})
    return pd.Series(
        {f"{m}_grezza": (gruppo[m] * gruppo["min"]).sum() / min_tot for m in METRICHE}
        | {"min_tot_grezzo": min_tot}
    )


def applica_shrinkage(report, storico_attivi, ruoli):
    grezze = storico_attivi.groupby("player_id").apply(calcola_stat_grezze, include_groups=False).reset_index()
    grezze = grezze.merge(ruoli, on="player_id", how="left")

    affidabili = report[report["n_stagioni_valide"] > 0].merge(ruoli, on="player_id", how="left")
    medie_ruolo = affidabili.groupby("ruolo")[[f"{m}_pesata" for m in METRICHE]].mean().reset_index()
    medie_ruolo.columns = ["ruolo"] + [f"{m}_ruolo" for m in METRICHE]

    report = report.merge(ruoli, on="player_id", how="left")
    report = report.merge(grezze.drop(columns=["ruolo"]), on="player_id", how="left")
    report = report.merge(medie_ruolo, on="ruolo", how="left")
    report["min_tot_grezzo"] = report["min_tot_grezzo"].fillna(0)
    report["peso_dati"] = (report["min_tot_grezzo"] / MINUTI_RIFERIMENTO).clip(0, 1)

    for m in METRICHE:
        stima_shrink = (
            report["peso_dati"] * report[f"{m}_grezza"].fillna(0)
            + (1 - report["peso_dati"]) * report[f"{m}_ruolo"]
        )
        report[m] = report[f"{m}_pesata"].fillna(stima_shrink)

    report["dato_stimato"] = report["n_stagioni_valide"] == 0
    return report


# ------------------------------------------------------------------
# Step 6 — indice di convenienza (scarto percentuale vs QUOT.)
# ------------------------------------------------------------------

def calcola_convenienza(report):
    quot_valida = report["quot"] >= SOGLIA_QUOT
    pgv_sufficiente = report["pgv"] >= SOGLIA_PGV
    report["indice_convenienza_pct"] = np.where(
        quot_valida & pgv_sufficiente,
        (report["fm"] / report["quot"] - 1) * 100,
        np.nan,
    )
    return report


# ------------------------------------------------------------------
# Step 7 — scrittura su player_metrics_snapshot
# ------------------------------------------------------------------

def _valore_pulito(r, colonna, tipo):
    """None se NaN, altrimenti converte al tipo Python corretto per psycopg2."""
    valore = r[colonna]
    if pd.isna(valore):
        return None
    return tipo(valore)


def salva_snapshot(conn, report, target_season_id):
    # colonna -> tipo Python atteso da Postgres
    colonne_numeriche_float = [
        "goals_90", "assists_90", "xg90", "xa90",
        "goals_90_trend", "assists_90_trend", "xg90_trend", "xa90_trend",
        "score_storico", "score_costanza", "indice_affidabilita",
        "indice_convenienza_pct", "peso_dati",
    ]

    rows = []
    for _, r in report.iterrows():
        riga = [
            int(r["player_id"]),
            target_season_id,
            MODEL_VERSION,
            _valore_pulito(r, "n_stagioni_valide", int),
            _valore_pulito(r, "minuti_totali", int),
        ]
        riga.extend(_valore_pulito(r, c, float) for c in colonne_numeriche_float)
        riga.append(bool(r["dato_stimato"]))
        rows.append(tuple(riga))

    colonne = (
        ["n_stagioni_valide", "minuti_totali"]
        + colonne_numeriche_float
        + ["dato_stimato"]
    )

    with conn.cursor() as cur:
        execute_values(
            cur,
            f"""
            INSERT INTO player_metrics_snapshot
                (player_id, target_season_id, model_version, {", ".join(colonne)})
            VALUES %s
            ON CONFLICT (player_id, target_season_id, model_version) DO UPDATE SET
                {", ".join(f"{c} = EXCLUDED.{c}" for c in colonne)},
                computed_at = now()
            """,
            rows,
        )
    conn.commit()
    print(f"[snapshot] {len(rows)} righe scritte in player_metrics_snapshot (model_version='{MODEL_VERSION}')")


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------
def main():
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT season_id FROM seasons WHERE label = %s", (TARGET_SEASON_LABEL,))
            target_season_id = cur.fetchone()[0]

        storico_attivi = carica_storico_attivi(conn)
        if TARGET_SEASON_LABEL == "26_27":
            contesto = carica_contesto_2627(conn)
        else:
            contesto = carica_contesto_listino(conn, TARGET_SEASON_LABEL)
        ruoli = contesto[["player_id", "ruolo"]]
        print(f"Righe storico attivo (matchate): {len(storico_attivi)}")
        print(f"Giocatori con contesto listino {TARGET_SEASON_LABEL}: {len(contesto)}")

        medie_pesate = storico_attivi.groupby("player_id").apply(calcola_media_pesata, include_groups=False).reset_index()
        trend = storico_attivi.groupby("player_id").apply(calcola_trend, include_groups=False).reset_index()
        affidabilita_raw = storico_attivi.groupby("player_id").apply(calcola_affidabilita_raw, include_groups=False).reset_index()
        affidabilita = calcola_indice_affidabilita(affidabilita_raw)

        report = medie_pesate.merge(trend, on="player_id", how="left")
        report = report.merge(
            affidabilita[["player_id", "score_storico", "score_costanza", "indice_affidabilita"]],
            on="player_id", how="left",
        )

        report = applica_shrinkage(report, storico_attivi, ruoli)
        report = report.merge(contesto[["player_id", "quot", "fm", "mv", "pgv"]], on="player_id", how="left")
        report = calcola_convenienza(report)

        print(f"\nGiocatori nel report finale: {len(report)}")
        print(f"Dato stimato (shrinkage): {report['dato_stimato'].sum()}")
        print(f"Indice convenienza calcolabile (PGv >= {SOGLIA_PGV}): {report['indice_convenienza_pct'].notna().sum()}")

        salva_snapshot(conn, report, target_season_id)

    finally:
        conn.close()

    print("\nFeatures completate.")


if __name__ == "__main__":
    main()
