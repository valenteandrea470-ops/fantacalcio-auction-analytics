# Dashboard — requisiti raccolti (da implementare quando ci arriviamo)

Questo file raccoglie le richieste per la dashboard finale, discusse
il 31/07 ma NON ancora implementate. Prima ci sono altri step nella
roadmap (vedi docs/SESSION_LOG.md per lo stato attuale). Ogni voce qui
sotto avra' bisogno di una sua sessione dedicata — molte richiedono
nuove fonti dati o estensioni allo schema, non solo lavoro sulla UI.

---

## 1. Grafici (il piu' possibile, entro il ragionevole)

Da decidere quali quando ci arriviamo: trend multi-stagione per
giocatore, distribuzione affidabilita/convenienza per ruolo, confronto
rose (gia' abbozzato nel notebook, cella 47). Nota per allora: troppi
grafici in una dashboard da consultare velocemente in asta live sono
un rischio di rallentare la lettura sotto pressione — quando ci
arriviamo, discutiamo cosa serve DAVVERO sott'asta vs cosa e' solo
"bello da vedere" per il portfolio (potrebbero essere due viste
diverse: dashboard live minimale + report analitico piu ricco).

## 2. Statistiche portiere (clean sheet)

**Attenzione — gap di dati da verificare prima di iniziare**: i CSV
Understat attuali (number, player, team, apps, min, goals, a, xG, xA,
xG90, xA90) non contengono clean sheet ne' altre metriche specifiche
da portiere. Va verificato se Understat le espone in un export diverso
o se serve una fonte dati aggiuntiva solo per i portieri.

## 3. Quotazione "piu' reale" — merge con storico prezzi reali della lega

Serve un nuovo dataset: quanto hanno speso REALMENTE i tuoi amici per
ogni giocatore nelle aste passate (probabilmente gia' presente nei
file leagueplayers_XX_YY.csv originali, o da recuperare altrove — DA
CHIARIRE quando ci arriviamo). Implica una nuova tabella tipo
`prezzi_storici_lega` collegata a player_id, e un'aggregazione
(media/scostamento) da mostrare vs QUOT. ufficiale.

## 4. Cambi di ruolo

Segnalare quando un giocatore cambia ruolo da una stagione all'altra
(es. difensore riadattato a centrocampista). Nel notebook attuale il
ruolo viene preso una sola volta dal listino 25/26 corrente — quando
uscira' il listino 26/27, andra' confrontato ruolo vecchio vs nuovo.
Per ora lo schema non traccia lo storico dei ruoli per stagione, solo
quello attuale in `players.ruolo` — da rivedere quando arriva il
listino 26/27 (probabilmente serve spostare `ruolo` da `players` a
una tabella collegata a season, invece che un unico valore fisso).

## 5. Merge con dataset esterni (FantaLab / FantaGoat, e simili — 3 fonti)

**AGGIORNAMENTO 31/07 — struttura confermata da un file reale (VCAF_Ep__3.xlsx,
strategia CarmySpecial, stagione corrente, 4 fogli P/D/C/A, 641 giocatori
totali, 33 colonne):**

Colonne chiave: `Prezzo` (prezzo suggerito), `Budget`/`PMA` (% budget),
`Quo` (loro quotazione — torna coerente con QUOT. Fantagazzetta, nessun
riscalaggio necessario), `Titolarità`/`Affidabilità`/`Integrità` (rating
1-5), `Commento`, `Nota 1`-`Nota 5` (fino a 5 tag per giocatore, vedi
elenco tag sotto), `MV`/`FMV`/`FMV Exp.`, `Presenze`, `Minuti`,
`Gol`/`Assist`, `Rig. Segnati`/`Rig. Sbagliati` (permette di derivare
NPG = Gol − Rig. Segnati, senza dover riscaricare Understat), `Gol
Subiti`/`Rig. Parati` (dati portiere — CHIUDE il gap del punto 2 sopra,
Understat non serve per i portieri).

**Vincolo importante**: FantaLab permette di scaricare solo la strategia
del fantallenatore per la stagione CORRENTE, non storico multi-stagione
di altri fantallenatori (limite del servizio, non nostro). La strategia
di un singolo fantallenatore (es. CarmySpecial) viene aggiornata nel
tempo man mano che arrivano notizie/mercato — quindi se vogliamo uno
snapshot "vicino all'asta", va riscaricata a ridosso della data, non
mesi prima.

Solo dopo aver valutato se questa fonte basta, considerare FantaGoat
come fonte aggiuntiva (non ancora provata).

**20 tag rilevati** (da icone allegate, mappano ai valori in Nota 1-5):
Titolarissimo, Modificatore, Costante, Rigorista, Tiratore, Pararigori,
Bonus, Tanti Gol, Assistman, Imbattibilità, Scommessa, Affare Nascosto,
Jolly, Esca, Rischio Infortuni, Cartellini, Incostante, Subentrante,
Contratto in Scadenza, Coppa Africa.

**Icone**: quelle di FantaLab sono asset grafici loro — non riusarle
direttamente nella dashboard se questa verra' mostrata pubblicamente.
Ricreare un set equivalente concettualmente (stessa idea, design
nostro) quando arriviamo alla UI.

## 5b. Giocatori da campionati esteri (nuovo, 31/07)

Idea di Andrea: per neo-acquisti da campionati esteri, recuperare lo
storico da Understat (che copre anche Premier/Liga/Bundesliga/Ligue 1
etc., non solo Serie A) e "pesare" il campionato di provenienza con un
coefficiente di difficoltà, per stimare la produzione attesa in Serie A.
Sotto-progetto a se': serve scegliere/validare un indice di forza
campionati (esiste letteratura, da cercare quando ci arriviamo). Non
un'estensione veloce di name_matching.py — richiede la sua analisi.

## 6. Tag qualitativi (Rigorista, Low Hype, Esca, Craque, ecc.)

Da conservare come colonna/tabella collegata a player_id, probabilmente
proveniente dallo stesso merge FantaLab/FantaGoat del punto 5. Servira'
una tabella tipo `player_tags` (player_id, tag, fonte) — un giocatore
puo' avere piu' tag da fonti diverse, quindi non un singolo campo in
`players`.

## 7. Budget suggerito — range in crediti e % sul budget (500 cr)

Combina il punto 3 (prezzi storici reali) con QUOT./convenienza gia'
calcolati, per suggerire un range di spesa per giocatore, sia in
crediti assoluti sia come percentuale del budget totale di lega (500
crediti). Dipende dal punto 3 per avere dati reali su cui basare il
range, non solo QUOT. ufficiale.

## 8. Prezzo modificabile dopo "aggiungi" alla rosa

Attualmente (nel vecchio notebook/dashboard) il tracker prende QUOT.
come prezzo di default quando aggiungi un giocatore alla rosa in
costruzione. Da rendere modificabile a mano (il prezzo pagato realmente
in asta puo' differire, anche di molto, da QUOT.). Implementazione
probabile: campo editabile in HTML/JS nella card del tracker, salvato
in memoria di sessione (o persistito con window.storage se vogliamo
che sopravviva a un refresh — da decidere quando ci arriviamo).

---

## Nota generale

Quasi tutte le voci sopra richiedono NUOVE fonti dati che non abbiamo
ancora acquisito o ispezionato (prezzi storici amici, FantaLab/
FantaGoat, eventuali dati portiere). Prima di scrivere codice per
ciascuna, andra' fatto lo stesso lavoro di ispezione che abbiamo fatto
per lista_2526_Leghe.xlsx: guardare la struttura reale del dato prima
di assumere come si integra nello schema.
