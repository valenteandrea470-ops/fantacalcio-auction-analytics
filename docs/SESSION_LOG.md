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

---

## 2026-07-31 — features.py: metriche derivate, prima esecuzione end-to-end

**Fatto:**
- Schema esteso: `player_metrics_snapshot.goals_90_pesata`→`goals_90`,
  `a_90_pesata`→`assists_90`, aggiunte `xg90`, `xa90`,
  `goals_90_trend`, `assists_90_trend`, `xg90_trend`, `xa90_trend`
  (mancavano dal design iniziale — trend e xG/xA sono il cuore del
  valore Understat, non potevano restare fuori)
- `src/features.py`: porta 1:1 media pesata (recenza x minuti), trend
  (regressione lineare), indice_affidabilita (30% storico + 70%
  costanza), shrinkage estimator. Tutte le soglie arbitrarie isolate
  in cima al file (SOGLIA_MINUTI, MINUTI_RIFERIMENTO, SOGLIA_PGV,
  SOGLIA_QUOT) — punto di intervento unico per la fase di regressione
- Pipeline end-to-end confermata: 1573 righe storico matchate, 591
  giocatori nel report finale, 105 con dato stimato via shrinkage

**Incidente:** reset della VM (riavvio, non snapshot — nessun dato
perso, confermato da `git log` e conteggio righe DB intatti dopo il
riavvio) durante il passaggio di un comando `ALTER TABLE`. Causa
probabile: incolla multi-riga nel terminale che ha inserito un
carattere di controllo (`^[[200~`) rompendo il comando. Lezione:
per comandi/file lunghi da incollare in VM, preferire scriverli prima
in un file con `nano` ed eseguirli da lì (`psql -f file.sql`) invece
di incollare blocchi lunghi direttamente su riga di comando.

**Bug trovato e corretto in `features.py`:**
- `salva_snapshot`: errore di indicizzazione (`colonne[1:]` invece di
  `colonne`) causava mismatch tra colonne dichiarate nell'INSERT e
  valori passati — corretto, nessun impatto sui calcoli a monte

**Sanity check fatti (metodo confermato utile):**
- Top 10 per `indice_affidabilita`: Pinamonti, Vlahović, Dzeko,
  Colombo, Cancellieri — tutti giocatori con storico di minutaggio
  reale e riconoscibile. Promosso.
- Top 10 per `indice_convenienza_pct` (prima versione, senza floor su
  QUOT.): valori assurdi (+465%, +464%...) tutti su giocatori con
  QUOT. bassissima (1-2 crediti) — la formula a scarto percentuale
  esplode senza lo smoothing che il notebook originale aveva
  (`FM/(QUOT+1)`). Corretto aggiungendo `SOGLIA_QUOT = 5`: sotto
  questa quotazione l'indice non viene calcolato, stesso principio
  già usato per `SOGLIA_PGV`. Dopo la correzione: top 10 in range
  16-25%, con profili credibili (difensori solidi a basso costo tipo
  Gatti, Acerbi, Bertola).

**Non ancora fatto (prossima sessione):**
- Dashboard HTML (porting dalla cella del notebook, con badge
  dato_stimato e ricerca)
- README repo per pubblicazione
- Fase 2 separata (dopo): backtest con regressione per ruolo,
  sostituzione soglie/pesi arbitrari elencati sopra

---

## 2026-07-31 (continua) — Ricognizione dati FantaLab + prezzi di lega

**Contesto**: prima di costruire la dashboard, decisa una fase di
ricognizione di tutte le fonti dati esterne desiderate (vedi
docs/DASHBOARD_REQUIREMENTS.md), invece di procedere alla cieca.

**Fatto:**
- Ispezionato file reale FantaLab (VCAF_Ep__3.xlsx, strategia
  CarmySpecial, 4 fogli P/D/C/A, 641 giocatori, 33 colonne). Struttura
  ricca: chiude il gap portieri (Gol Subiti/Rig. Parati) e permette di
  derivare NPG (Gol - Rig. Segnati) senza rifare il download Understat.
  20 tag qualitativi identificati dalle icone allegate.
- Confermato: i prezzi reali pagati dagli amici di lega sono GIA' nel
  DB (`fantagazzetta_listino.fantasquadra`/`costo`, dalla migrazione
  iniziale) — nessuna nuova fonte necessaria per quel punto del
  backlog, solo aggregazione.
- Test di matching FantaLab -> Fantagazzetta: 66.6% esatto diretto,
  68.0% dopo pulizia accenti/apostrofi. I 205 non-match residui
  verificati uno per uno: quasi tutti hanno Fascia="Non Impostata" e
  Quo=NaN — sono profondita' di rosa (riserve, giovani) non quotati,
  non giocatori esteri come inizialmente ipotizzato.
- Casi concreti verificati: Kolo Muani assente da entrambe le fonti
  (trasferimento non ancora ufficializzato); Liberali presente ma con
  squadra discordante tra le due fonti (Como vs Milan) — conferma
  pratica che il mercato aperto genera rumore, valida la scelta di
  aspettare il listino definitivo del 1-3/09.

**Decisioni prese (design confermato, NON ancora implementato):**
- Due nuove tabelle: `fantalab_valutazioni` (uno snapshot per
  download, si tengono TUTTE le versioni nel tempo per vedere come
  cambia il giudizio del fantallenatore) e `player_tags` (player_id,
  tag, fonte — un giocatore puo' avere piu' tag)
- Policy player_id: creare un player_id per OGNI riga FantaLab, anche
  quelle senza match nel listino ufficiale (matched o orfano, stesso
  percorso di codice, nessun ramo speciale)
- Punto 5b del backlog allargato: non solo campionati esteri, anche
  categorie inferiori italiane (es. Liberali dal Catanzaro/Serie C) —
  sotto-progetto a se', da affrontare DOPO il 1/09 con dati di mercato
  chiuso, non ora

**Non ancora fatto (prossima sessione, si parte da qui):**
1. Migrazione schema: CREATE TABLE fantalab_valutazioni + player_tags
2. src/fantalab_matching.py: riusa la logica fuzzy di name_matching.py
3. Test end-to-end con VCAF_Ep__3.xlsx (dati di prova, NON definitivi —
   il file vero arriva 1-3/09 a mercato chiuso)
4. Poi: dashboard HTML, README, fase 2 backtest (invariato da sopra)
