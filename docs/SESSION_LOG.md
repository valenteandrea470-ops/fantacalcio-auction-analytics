# Session Log — FUTDRAFT27

Log delle decisioni prese sessione per sessione. Aggiornato a fine di
ogni sessione di lavoro. Serve a ricostruire il "perché" delle scelte,
non solo il "cosa" — quello lo vede chiunque leggendo il codice.

---

## 2026-07-30 — Schema DB, migrazione dati, name matching

**Fatto:**
- Definito e creato lo schema Postgres (`sql/schema.sql`): 6 tabelle
  (`seasons`, `players`, `understat_player_season`,
  `fantagazzetta_listino`, `player_name_matches`,
  `player_metrics_snapshot`)
- `src/migrate_data.py`: carica 5 CSV Understat (21/22→25/26) +
  listino xlsx grezzi, senza matching. Idempotente (ON CONFLICT DO
  NOTHING).
- `src/name_matching.py`: porta 1:1 la logica del notebook
  (`rimuovi_accenti`, `estrai_cognome_iniziale`, `trova_corrispondenza`,
  `mappatura_manuale`). Ogni riga del listino 25/26 diventa un
  `player_id` canonico.
- `src/matching_diagnostics.py`: controllo sospetti (non-match in una
  stagione che matchano in un'altra) — 0 sospetti confermati.

**Decisioni chiave:**
- `lista_2526_Leghe.xlsx` NON è un listino pre-asta vuoto — è uno
  snapshot di fine stagione 25/26 con FM/MV/PGv reali e
  FantaSquadra/Costo per i 250 giocatori già assegnati nella tua lega.
  Per l'asta 26/27 servirà un file diverso (listino vuoto pre-stagione).
- Colonna `Under` del listino non è booleana come inizialmente
  ipotizzato — sono età reali (17-36) → rinominata `age`.
- Aggiunte `fantasquadra`/`costo` allo schema, nullable, per supportare
  backtest su stagioni concluse.
- Mantra escluso ovunque — si gioca solo classico.
- `indice_convenienza` da ricalcolare come scarto percentuale
  `(FM/QUOT - 1) * 100` invece della formula originale del notebook
  `FM/(QUOT+1)` — scelta di leggibilità in dashboard, a costo di perdere
  lo smoothing anti-esplosione per QUOT. molto basse. Da monitorare se
  crea valori estremi per giocatori a costo 1-2 crediti.

**Risultati matching (per stagione, vs listino 25/26):**
| Stagione | Match rate |
|---|---|
| 21_22 | 27.1% |
| 22_23 | 36.6% |
| 23_24 | 49.2% |
| 24_25 | 63.3% |
| 25_26 | 90.1% |

Trend decrescente coerente con turnover reale di rosa (giocatori usciti
dal giro Serie A nelle stagioni più vecchie), confermato dal controllo
sospetti a zero falsi negativi.

**Soglie arbitrarie identificate, da rivedere in fase di backtest con
regressione (insieme ai pesi 30/70 e 50/50):**
- `SOGLIA_MINUTI = 450` — pavimento minimo per dato per-90 affidabile
- `MINUTI_RIFERIMENTO = 1500` — soglia piena fiducia per shrinkage
  (nota: il commento originale nel notebook diceva "~1 stagione da
  titolare", ma 1500 min corrisponde piuttosto a un giocatore di
  rotazione — titolare vero è 2250-3000 min. Commento corretto nel
  codice portato)
- `SOGLIA_PGV = 10` — presenze minime con voto per FM affidabile

**Non ancora fatto (prossima sessione):**
- `src/features.py`: per-90, medie pesate, trend, indice_affidabilita,
  shrinkage estimator, indice_convenienza (versione % rivista)
- Popolare `player_metrics_snapshot` con `model_version = 'v1_notebook_port'`
