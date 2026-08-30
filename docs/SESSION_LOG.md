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


---

## 2026-08-02 — Integrazione FantaLab: tabelle, matching, primo carico completo

**Fatto:**
- Migrazione `sql/002_fantalab_tables.sql`: tabelle `fantalab_valutazioni`
  (33 colonne, ispezionate dal file reale — 8 non erano nel backlog
  originale: `Obiett.`, `Fascia`, `Ruolo`, `Team`, `Pt. Tit.`, `Pt. Inf.`,
  `Ammonizioni`, `Espulsioni`) e `player_tags`. `match_method` esteso
  con `'orphan_created'` per i player_id creati senza corrispondenza —
  poi scoperto inutilizzato (vedi decisione lineage sotto), lasciato
  comunque nel CHECK, innocuo.
- Migrazione `sql/003_fantalab_multi_strategia.sql`: `UNIQUE` su
  `fantalab_valutazioni` esteso da `(player_id, fonte, scaricato_il)` a
  `(player_id, fonte, strategia, scaricato_il)` — il constraint
  originale non reggeva due fantallenatori scaricati lo stesso giorno.
- Migrazione `sql/004_fantalab_match_lineage.sql`: `match_method` e
  `match_confidence` spostati dentro `fantalab_valutazioni` stessa,
  invece di riusare `player_name_matches` (le cui colonne
  `understat_name_raw`/`fantagazzetta_name_raw` sono nominate per
  Understat specificamente — riusarla per FantaLab avrebbe scritto
  nomi FantaLab in una colonna che dichiara di contenere nomi Understat).
- `src/fantalab_matching.py`: carica le 4 sheet (P/D/C/A) di
  `VCAF_Ep__3.xlsx`, matcha su `fantagazzetta_listino` (match esatto,
  poi fallback fuzzy per-cognome), crea player_id orfani per i
  non-match, popola `fantalab_valutazioni` + `player_tags` (da Nota
  1-5). Flag `--sheets` per rilanciare sheet singole in caso di errore
  a metà carico.

**Decisioni chiave:**
- `strategia` = `'CarmySpecial'`, `scaricato_il` = `'2026-07-31'` per
  questo primo carico di test.
- Fallback fuzzy per FantaLab **diverso** da `trova_corrispondenza` di
  Understat: i nomi FantaLab sono gia' in formato Fantagazzetta
  (cognome, o "Cognome I."), non nome-completo — non serve
  `estrai_cognome_iniziale` ne' `MAPPATURA_MANUALE` (quella e'
  Understat-specifica).
- Player_id orfani: nessuna riga in `player_name_matches` per loro
  (quella tabella resta Understat-only), il lineage FantaLab vive
  interamente in `fantalab_valutazioni.match_method`.

**Bug trovato e corretto:**
- Il primo fallback fuzzy staccava l'iniziale finale del nome FantaLab
  prima di cercare match per cognome (`"El Azzouzi A."` -> cerca
  `"El Azzouzi"`). Su un listino con **un solo** omonimo per cognome,
  questo faceva collassare due giocatori diversi sullo stesso player_id
  quando FantaLab li disambiguava con l'iniziale proprio perche' erano
  omonimi: **Anouar El Azzouzi** (Frosinone) e **Oussama El Azzouzi**
  (Bologna) sullo stesso player_id; poi lo stesso pattern su
  **Robinho Vaz** (attaccante, Roma) vs **Marcelo Vaz** (terzino,
  Genoa) collassati su un player_id "Vaz M." gia' presente nel listino
  come Marius Marin — scoperto perche' il `ruolo_fantalab` (D) non
  coincideva col ruolo del player_id trovato (C), incongruenza notata
  durante il debug, non dal codice.
  Lezione generale: **un'iniziale scritta dalla fonte non e' rumore da
  ripulire, e' disambiguazione intenzionale** — se la fonte la mette,
  significa che sa che esiste un omonimo, e toglierla annulla proprio
  l'informazione che serviva. Fix: il fallback fuzzy ora si attiva SOLO
  se il nome FantaLab **non** porta gia' un'iniziale finale; se la
  porta e il match esatto fallisce, va orfano invece che tentare
  il fallback.
- Conseguenza pratica: la sheet D e' stata cancellata e ricaricata
  interamente (invece di correggere le 2 righe sbagliate a mano) dopo
  il fix — piu' sicuro di un cherry-pick manuale su dati gia' sporchi.
  `DELETE` a cascata su `player_tags` -> `fantalab_valutazioni` ->
  `players` (solo orfani senza altri riferimenti), verificato via
  conteggio righe cancellate prima di rilanciare.

**Sanity check fatti:**
- Percentuale di match totale (436/641 = 68.0%) combacia esattamente
  con la ricognizione manuale del 31/07 — buon segno di non aver
  introdotto regressioni sistemiche.
- 203/206 orfani hanno `Fascia = 'Non Impostata'` (98.5%), coerente
  con l'ipotesi "riserve/giovani non quotati" gia' verificata a mano
  in precedenza. I 2 rimanenti (Terza/Quarta categoria) verosimilmente
  legittimi.
- Query di controllo sistemico introdotta: confronto tra
  `players.ruolo` e `fantalab_valutazioni.ruolo_fantalab` per ogni riga
  matchata — 0 discrepanze su tutte le 436 righe exact dopo il fix.
  Questa query e' quella che avrebbe intercettato il bug El
  Azzouzi/Vaz se fosse stata pensata PRIMA invece che durante il
  debug — da rilanciare come check di routine ad ogni futuro carico
  FantaLab, non solo quando qualcosa sembra gia' rotto.
- **Nota**: dopo il fix, `fuzzy: 0` su tutte e 4 le sheet — il
  fallback per-cognome (attivo solo quando FantaLab NON scrive
  un'iniziale) non ha mai trovato un candidato unico. Possibile che
  esistano match fuzzy legittimi persi per eccesso di prudenza — non
  investigato oltre in questa sessione, il trade-off (nessun falso
  positivo tipo Vaz/El Azzouzi) e' stato giudicato preferibile per ora.

**Non ancora fatto (prossima sessione):**
- Lo script `fantalab_matching.py` non e' idempotente sui player_id
  orfani: un secondo carico della stessa sheet ricrea player_id
  duplicati per gli stessi orfani invece di riconoscerli. Non bloccante
  ora (si e' rilanciato solo sheet singole dopo cancellazione pulita),
  ma va risolto prima di un futuro re-carico completo.
- Investigare se il fallback fuzzy (fuzzy: 0 su tutto il carico) e'
  davvero troppo conservativo o se e' corretto cosi'.
- Dashboard HTML, README repo, fase 2 backtest (invariato dalle
  sessioni precedenti).

---

## 2026-08-02 (continua) — Idempotenza sugli orfani FantaLab

**Fatto:**
- `src/fantalab_matching.py`: aggiunta `load_orfani_esistenti()`, chiamata
  una volta in `main()` prima di processare le sheet. Costruisce una mappa
  `(nome_pulito, ruolo_fantalab) -> player_id` leggendo tutti gli orfani
  gia' creati in carichi precedenti (qualsiasi strategia/data).
- In `process_sheet`, la creazione di un player_id orfano ora controlla
  prima questa mappa: se la chiave esiste gia', riusa il player_id invece
  di inserirne uno nuovo. La mappa viene aggiornata anche a runtime
  (visibile tra una sheet e l'altra nello stesso carico), non solo tra
  carichi diversi.
- Riepilogo di stampa aggiornato: distingue `orphan nuovi` da
  `orphan riusati`.

**Bug incontrato durante l'edit (non nel codice, in nano):**
- Incollare un blocco di codice gia' indentato dentro `nano` fa scattare
  l'auto-indent: nano somma l'indentazione della riga precedente a quella
  incollata, che si accumula riga dopo riga finche' il file non ha piu'
  un'indentazione coerente (`IndentationError: unindent does not match
  any outer indentation level`). Non e' un errore di distrazione, e'
  comportamento di default di nano su incolli multi-riga gia' indentati.
  Fix per il futuro: per sostituire blocchi grossi di codice Python,
  usare `cat > file << 'EOF' ... EOF` invece di `nano` — riscrive il file
  intero senza toccare l'indentazione di quello che viene incollato.

**Test fatto:**
- Ricaricata la sola sheet P con data diversa (`2026-08-02`, di test,
  non un vero scarico) sugli stessi 70 giocatori gia' presenti dal
  31/07: risultato `orphan nuovi: 0, orphan riusati: 20` — i 20 orfani
  di P riconosciuti correttamente, zero player_id duplicati creati.
- Carico di test cancellato subito dopo (`DELETE FROM fantalab_valutazioni
  WHERE scaricato_il = '2026-08-02'`) per non sporcare i dati reali del
  31/07 — nessuna riga toccata in `player_tags` o `players` (i tag erano
  identici, bloccati da `ON CONFLICT DO NOTHING`; i player_id erano tutti
  riusati, nessuno nuovo da ripulire).

**Non ancora fatto:**
- Investigare se il fallback fuzzy (fuzzy: 0 su tutto il carico del
  31/07) e' troppo conservativo o corretto cosi' — invariato dalla nota
  precedente.
- Dashboard HTML, README repo, fase 2 backtest (invariato dalle sessioni
  precedenti).

---

## 2026-08-02 (continua) — Idempotenza sugli orfani FantaLab

**Fatto:**
- `src/fantalab_matching.py`: aggiunta `load_orfani_esistenti()`, chiamata
  una volta in `main()` prima di processare le sheet. Costruisce una mappa
  `(nome_pulito, ruolo_fantalab) -> player_id` leggendo tutti gli orfani
  gia' creati in carichi precedenti (qualsiasi strategia/data).
- In `process_sheet`, la creazione di un player_id orfano ora controlla
  prima questa mappa: se la chiave esiste gia', riusa il player_id invece
  di inserirne uno nuovo. La mappa viene aggiornata anche a runtime
  (visibile tra una sheet e l'altra nello stesso carico), non solo tra
  carichi diversi.
- Riepilogo di stampa aggiornato: distingue `orphan nuovi` da
  `orphan riusati`.

**Bug incontrato durante l'edit (non nel codice, in nano):**
- Incollare un blocco di codice gia' indentato dentro `nano` fa scattare
  l'auto-indent: nano somma l'indentazione della riga precedente a quella
  incollata, che si accumula riga dopo riga finche' il file non ha piu'
  un'indentazione coerente (`IndentationError: unindent does not match
  any outer indentation level`). Non e' un errore di distrazione, e'
  comportamento di default di nano su incolli multi-riga gia' indentati.
  Fix per il futuro: per sostituire blocchi grossi di codice Python,
  usare `cat > file << 'EOF' ... EOF` invece di `nano` — riscrive il file
  intero senza toccare l'indentazione di quello che viene incollato.

**Test fatto:**
- Ricaricata la sola sheet P con data diversa (`2026-08-02`, di test,
  non un vero scarico) sugli stessi 70 giocatori gia' presenti dal
  31/07: risultato `orphan nuovi: 0, orphan riusati: 20` — i 20 orfani
  di P riconosciuti correttamente, zero player_id duplicati creati.
- Carico di test cancellato subito dopo (`DELETE FROM fantalab_valutazioni
  WHERE scaricato_il = '2026-08-02'`) per non sporcare i dati reali del
  31/07 — nessuna riga toccata in `player_tags` o `players` (i tag erano
  identici, bloccati da `ON CONFLICT DO NOTHING`; i player_id erano tutti
  riusati, nessuno nuovo da ripulire).

**Non ancora fatto:**
- Investigare se il fallback fuzzy (fuzzy: 0 su tutto il carico del
  31/07) e' troppo conservativo o corretto cosi' — invariato dalla nota
  precedente.
- Dashboard HTML, README repo, fase 2 backtest (invariato dalle sessioni
  precedenti).

---

## 2026-08-06 — Verifica fallback fuzzy: fuzzy=0 confermato corretto

**Investigato:** se `fuzzy: 0` su tutto il carico FantaLab del 31/07 fosse
un fallback troppo prudente che perde match legittimi.

**Metodo:** confronto dei 205 orfani (senza iniziale, quelli che tentano
il fallback per-cognome) contro tutti i nomi in `understat_player_season`
su tutte le 5 stagioni — se un orfano non esiste nemmeno li', e' quasi
certamente un giocatore mai passato per la Serie A prima, non un errore
di matching.

**Risultato:** 125/205 assenti da tutte le 5 stagioni Understat —
candidati genuini a "mai in Serie A" (es. Akor Adam, arrivi dall'estero).
Gli altri 80, apparsi come "cognome presente in Understat" nello script
diagnostico, erano quasi tutti falsi positivi dello script stesso (bug:
prendeva la prima parola del nome pulito come cognome, sbagliato per
`nome+cognome` tipo "Arthur Melo" invece di "Cognome I."). Verificati a
campione (Arthur Melo, Pessina): nessuno dei due e' nel listino 25_26,
quindi il fallback fuzzy non ha perso nessun match reale — erano
correttamente orfani.

**Conclusione:** fuzzy=0 confermato corretto, non e' un difetto del
fallback. Chiuso il dubbio aperto in sessione precedente.

**Scoperte collaterali (fuori scope, solo segnate):**
- Understat ha ambiguita' sui nomi-arte brasiliani/stile-singolo (es.
  "Arthur" da solo compare per almeno 2-3 giocatori diversi: Arthur
  Melo, Arthur Cabral, Arthur Theate — solo "Arthur Atta" ha un
  player_id assegnato). MAPPATURA_MANUALE di `name_matching.py` non
  copre questi casi. Da investigare in una sessione dedicata al
  matching Understat, non FantaLab.
- Massimo/Matteo Pessina: presente in Understat su tutte e 5 le
  stagioni (21_22 -> 25_26), mai agganciato a nessun player_id, non
  presente nel listino 25_26. Causa non ancora capita (prestito?
  categoria inferiore? bug nel matching originale?) — da verificare.

**Prossimo passo proposto da Andrea:** costruire un modello di
valutazione per giocatori provenienti da leghe estere (es. Akor Adam,
Bundesliga) con pesi per lega proporzionati alla Serie A — estensione
naturale del modello xFMV gia' pensato per "QUOT. debole o assente".
Non ancora iniziato: serve prima capire (1) quante leghe coprire, (2)
se Understat copre quelle leghe con formato compatibile, (3) come si
inserisce nella fase di regressione per-ruolo gia' pianificata (stessi
pesi arbitrari da calibrare).

**Non ancora fatto (invariato):**
- Dashboard HTML, README repo (invariato dalle sessioni precedenti).

---

## 2026-08-09 — Secondo e terzo fantallenatore: Classicfantavirus, profeta

**Fatto:**
- `src/fantalab_matching.py`: aggiunta `_parse_fascia()` — normalizza
  maiuscole incoerenti tra fonti (`'top'` su un export, `'Top'` su un
  altro, stesso significato) con `.title()`. Nessun'altra modifica al
  codice.
- Caricati `Classicfantavirus.xlsx` (strategia `Classicfantavirus`) e
  `profeta.xlsx` (strategia `profeta`), entrambi `scaricato_il =
  '2026-08-09'`. Entrambi mancano della colonna `Budget` (solo `PMA`
  presente) — gestito da `.get()`, `budget_pct` risulta NULL per
  queste due fonti senza errori.

**Verifica numerica:**
- Classicfantavirus: 497 righe (60+176+174+87), 383 exact, 114 orfani.
- profeta: 497 righe, 383 exact, 114 orfani — **identici** a
  Classicfantavirus su tutti e tre i numeri. Conferma che i due
  fantallenatori valutano lo stesso identico pool di giocatori (stesso
  universo Serie A), solo con giudizi diversi (prezzo, fascia, tag) —
  presupposto necessario per il confronto comparativo pianificato.
- `orphan nuovi: 0` su tutte le sheet del secondo carico (profeta) —
  idempotenza cross-strategia confermata: gli orfani creati da
  Classicfantavirus sono stati riconosciuti e riusati, non duplicati.
- CarmySpecial resta a parte con 641 righe (pool piu' ampio,
  probabilmente include piu' Serie C/giovani) — differenza di
  dimensione del dataset gia' notata prima del caricamento, non
  un'anomalia.
- Falso allarme durante la verifica: lettura errata di uno screenshot
  del terminale (sheet A di Classicfantavirus, sembrava mancassero 4
  righe nel conteggio) — risolto con query diretta al DB invece di
  fidarsi del testo del terminale, tutto quadrava. Nota per il futuro:
  in caso di dubbio aritmetico, sempre verificare via query, non a
  occhio sullo screenshot.

**Non ancora fatto:**
- Analisi comparativa tra le tre strategie (CarmySpecial,
  Classicfantavirus, profeta) — prossimo step esplicito richiesto da
  Andrea, non ancora iniziato.
- Investigare la differenza di pool tra CarmySpecial (641 righe) e gli
  altri due (497 righe ciascuno) — probabile solo dimensione export
  diversa, non verificato a fondo.
- Ambiguita' Understat nomi-arte (Arthur), Pessina non agganciato,
  modello leghe estere per giocatori tipo Akor Adam — invariati dalla
  sessione precedente.
- Dashboard HTML, README repo (invariato dalle sessioni precedenti).

---

## 2026-08-09 (continua) — Verifica differenza pool tra le tre fonti FantaLab

**Investigato:** perche' CarmySpecial (641 righe) e Classicfantavirus/
profeta (497 righe ciascuno) hanno numeri diversi — se fosse solo
dimensione export (CarmySpecial superset) o rose realmente diverse.

**Risultato:** NON e' un superset. 73 giocatori sono presenti in
Classicfantavirus/profeta ma assenti da CarmySpecial (verificato anche
il senso inverso di striscia). Ipotesi testata e scartata: non e' un
problema di ruolo_fantalab diverso tra fonti che spezza il
riconoscimento orfani (query su nome_raw esatto con ruolo diverso: 0
righe). I tre fantallenatori tracciano semplicemente rose diverse per
scelta personale — non esiste un "listino FantaLab unico" dietro,
ogni fantallenatore segue/traccia la propria selezione di giocatori
(profondita' diversa su Serie C/giovani di prospettiva).

**Nota metodologica per prossima analisi comparativa:** confronti
aggregati (prezzo medio, fascia media) tra le tre fonti vanno fatti
SOLO sull'intersezione dei player_id tracciati da tutte e tre,
altrimenti chi segue piu' giovani a basso prezzo risulta
artificialmente "piu' economico" per composizione del campione, non
per giudizio reale sui giocatori in comune.

**Non ancora fatto:**
- Analisi comparativa tra le tre strategie (con la nota sopra
  applicata) — prossimo step.
- Resto invariato dalla sessione precedente.

---

## 2026-08-09 (continua 2) — Prima vista di confronto tra fantallenatori

**Fatto:**
- `sql/005_fantalab_confronto_views.sql`: due viste.
  - `v_fantalab_ultimo_snapshot`: prende sempre l'ultimo `scaricato_il`
    per ciascuna strategia — un ricarico futuro con data piu' recente
    sostituisce automaticamente quello vecchio nel confronto, senza
    bisogno di toccare la query.
  - `v_fantalab_confronto`: una riga per giocatore, SOLO
    sull'intersezione delle fonti attive (tutte le strategie presenti
    devono tracciare quel giocatore — vedi nota metodologica gia'
    scritta in sessione precedente). Calcola prezzo_min/max/delta,
    stddev, media, conteggio obiettivo, e due colonne jsonb
    (prezzi_per_fonte, fasce_per_fonte) che si espandono da sole
    quando si aggiunge una nuova strategia — nessuna colonna fissa
    per fantallenatore, design pensato esplicitamente per il quarto
    fantallenatore che Andrea integrera' quando la sua strategia
    sara' pubblicata.

**Decisione chiave — Prezzo = 0 trattato come "non ancora valutato":**
- Scoperto (sanity check sui primi risultati: tutti i big-name con
  CarmySpecial a 0.00) che CarmySpecial ha un placeholder 0 su gran
  parte dei giocatori non ancora prezzati — confermato da Andrea:
  compilazione in corso, si completera' solo a mercato chiuso
  (1-3/09), non un giudizio di valore reale.
- Fix: `NULLIF(prezzo, 0)` in tutte le aggregazioni (MIN/MAX/AVG/
  STDDEV) — un prezzo 0 viene escluso dal calcolo invece di essere
  trattato come valutazione vera, altrimenti ogni big-name non ancora
  prezzato da una fonte avrebbe dominato la classifica dei disaccordi
  con rumore, non segnale.
- Aggiunta colonna `n_prezzi_validi` per trasparenza: un delta
  calcolato su 2 fonti reali (su 3 presenti) e' meno solido di uno
  calcolato su 3/3 — visibile a chi legge la vista, non nascosto.

**Incidente minore:** `CREATE OR REPLACE VIEW` fallisce se si prova a
inserire una colonna in mezzo (Postgres permette solo append in fondo)
— serve DROP + CREATE esplicito in quel caso. Corretto al volo.

**Stato attuale (parziale, atteso):** la classifica dei delta_prezzo
piu' alti oggi riflette quasi solo "profeta vs Classicfantavirus"
(CarmySpecial ancora in gran parte a placeholder 0) — cambiera'
sostanzialmente quando CarmySpecial verra' ricaricato aggiornato.
Deciso di procedere comunque: la logica della vista e' corretta e
gia' pronta a recepire dati aggiornati senza modifiche, solo i dati
sottostanti sono provvisori.

**Non ancora fatto (prossima, in ordine):**
1. Indice di aggressivita' per fantallenatore (prezzo medio vs QUOT.
   per ruolo) — secondo pezzo del report comparativo, non ancora
   iniziato.
2. Problema aperto discusso con Andrea: come recuperare dati/statistiche
   per gli orfani che sono NUOVI arrivi in Serie A quest'anno (es.
   Akor Adam da Bundesliga) — spesso coincidono con "giocatori mai
   visti in 5 stagioni Understat" gia' isolati nella sessione del
   06/08 (125 dei 205 orfani di CarmySpecial). Necessita di dati da
   altre leghe estere e un modello di pesatura — collegato alla nota
   gia' presente su xFMV/leghe estere.
3. Dashboard HTML, README, fase 2 backtest, ambiguita' Understat
   nomi-arte, Pessina — invariati.

---

## 2026-08-28 — Supporto multi-lega per Understat, orfani classificati

**Fatto:**
- `player_provenienza` (migrazione 006): classificazione manuale dei
  205 orfani FantaLab in 4 categorie (Giovanile/Primavera 93,
  Trasferimento estero 64, Serie B/C italiana 41, Altro/Non so 7),
  con lega di provenienza normalizzata (club/paese -> lega) dove
  applicabile, e presenze/gol/assist da fonte esterna dove disponibili.
  Compilazione manuale, non riproducibile automaticamente — file
  sorgente versionato in `data/orfani_classificati_20260828.xlsx`.
- `seasons` esteso con colonna `lega` (default 'Serie A' per le righe
  esistenti, nessun dato toccato) — permette di agganciare stagioni
  di leghe estere a `understat_player_season` senza modificarne lo
  schema (migrazione 007).
- Confermato via `understatapi` (libreria pip, wrapper degli endpoint
  JSON di Understat) che le 4 leghe piu' rappresentate tra i
  trasferimenti esteri (La Liga 12, Premier League 5, Bundesliga 4,
  Ligue 1 4 — su 46 con lega nota) sono tutte coperte nativamente da
  Understat, stesso schema dati gia' in uso per la Serie A.

**Lezioni sul matching Understat <-> orfani esteri:**
- Il matching automatico per cognome (riuso di `trova_corrispondenza`
  stile Understat<->listino) non regge sui trasferimenti esteri: i
  `nome_canonico` degli orfani FantaLab hanno formati misti (Cognome,
  Cognome+Iniziale, Cognome-composto+Iniziale, e in alcuni casi
  Nome+Cognome completo) che un'unica euristica non gestisce senza
  falsi positivi — in particolare su cognomi comuni (es. "Gomez": 5
  giocatori diversi in una sola lega) il rischio di agganciare il
  player_id sbagliato e' concreto e silenzioso.
- Approccio adottato: `find_candidati_understat.py` mostra i
  candidati plausibili per ogni giocatore ancora senza match (ricerca
  larga per sottostringa di cognome), la conferma finale resta umana.
  Piu' lento ma zero rischio di corruzione silenziosa del dato — dato
  il volume piccolo (10-15 giocatori per lega), il costo e'
  accettabile.
- **Attenzione stagione**: i trasferimenti verso la Serie A per la
  26/27 vanno cercati nella stagione Understat 25/26
  (`season='2025'`), quella appena conclusa — non 24/25. Le prime
  verifiche fatte sulla stagione sbagliata vanno rifatte da capo,
  nessun dato del genere e' stato consolidato.
- Alcuni club appartenenti a `lega_provenienza_norm='La Liga'` nella
  classificazione manuale giocavano in realta' in Segunda Division
  nella stagione di riferimento (es. club promossi solo per la
  stagione successiva) — la normalizzazione lega fatta su base
  "squadra attuale" non basta, va verificata la divisione nella
  stagione specifica.

**Non ancora fatto:**
- Ricaricare i trasferimenti esteri con la stagione corretta (25/26)
  per tutte e 4 le leghe principali, con il flusso a conferma umana.
- Estendere la classificazione (Serie B/C italiana, Giovanile/
  Primavera) — nessuna fonte dati individuata finora per queste due
  categorie.
- Indice di aggressivita' per fantallenatore (prezzo medio vs QUOT.
  per ruolo) — secondo pezzo del report comparativo, ancora non
  iniziato.
- Dashboard pubblica, README, fase 2 backtest — invariati.

**Idee aperte per prossimi capitoli (non ancora iniziate):**
- Dashboard ispirata nello stile a un progetto di riferimento esterno
  (fishertiger, github.com/Zannael/fishertiger) ma costruita sui dati
  propri del progetto — copiare il tipo di visualizzazione, non la
  struttura dati.
- Sistema di suggerimento coppie d'attacco basato sul calendario di
  campionato (facilita' incroci in base al calendario stagionale).
- Report FantaLab per squadra (formato diverso dalle valutazioni per
  giocatore gia' integrate) e aggiornamento delle tre strategie
  fantallenatore atteso per il 1 settembre, a mercato chiuso.
