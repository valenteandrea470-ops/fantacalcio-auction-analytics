let ordinamento = { chiave: "quot_consenso_2627", asc: false };
let filtroRuolo = "TUTTI";
let filtroTesto = "";

function formatta(valore, decimali = 1) {
  if (valore === null || valore === undefined) return "—";
  return typeof valore === "number" ? valore.toFixed(decimali) : valore;
}

function datiFiltrati() {
  return PLAYERS_DATA
    .filter(g => filtroRuolo === "TUTTI" || g.ruolo === filtroRuolo)
    .filter(g => g.nome_canonico.toLowerCase().includes(filtroTesto))
    .sort((a, b) => {
      const va = a[ordinamento.chiave], vb = b[ordinamento.chiave];
      const na = va === null || va === undefined;
      const nb = vb === null || vb === undefined;
      if (na && nb) return 0;
      if (na) return 1;
      if (nb) return -1;
      if (va < vb) return ordinamento.asc ? -1 : 1;
      if (va > vb) return ordinamento.asc ? 1 : -1;
      return 0;
    });
}

function renderTabella() {
  const corpo = document.getElementById("corpo-tabella");
  corpo.innerHTML = "";
  datiFiltrati().forEach(g => {
    const riga = document.createElement("tr");
    riga.innerHTML = `
      <td>${g.nome_canonico}</td>
      <td><span class="badge-ruolo ${g.ruolo ?? ""}">${g.ruolo ?? "—"}</span></td>
      <td class="num">${formatta(g.quot_consenso_2627)}${g.dato_stimato ? ' <span class="stimato">*</span>' : ""}</td>
      <td class="num">${formatta(g.indice_affidabilita)}</td>
      <td class="num">${formatta(g.goals_90, 2)}</td>
      <td class="num">${formatta(g.assists_90, 2)}</td>
    `;
    riga.addEventListener("click", () => apriPannello(g.player_id));
    corpo.appendChild(riga);
  });
}

function renderTopListe() {
  const contenitore = document.getElementById("top-liste");
  const liste = [
    { titolo: "Top 5 xG/90", chiave: "xg90", decimali: 2 },
    { titolo: "Top 5 xA/90", chiave: "xa90", decimali: 2 },
    { titolo: "Top 5 Affidabilità", chiave: "indice_affidabilita", decimali: 0 },
  ];
  contenitore.innerHTML = liste.map(l => {
    const top5 = [...PLAYERS_DATA]
      .filter(g => g[l.chiave] !== null && g[l.chiave] !== undefined)
      .sort((a, b) => b[l.chiave] - a[l.chiave])
      .slice(0, 5);
    const righe = top5.map(g =>
      `<li>${g.nome_canonico} <span class="val">${formatta(g[l.chiave], l.decimali)}</span></li>`
    ).join("");
    return `<div class="card-top"><h3>${l.titolo}</h3><ol>${righe}</ol></div>`;
  }).join("");
}

function avatarSvg(nome) {
  let hash = 0;
  for (let i = 0; i < nome.length; i++) hash = nome.charCodeAt(i) + ((hash << 5) - hash);
  const tinta = Math.abs(hash) % 360;
  const iniziali = nome.replace(/[^A-Za-z ]/g, "").split(" ").map(p => p[0]).join("").slice(0, 2).toUpperCase();
  return `<svg width="28" height="28" viewBox="0 0 28 28">
    <circle cx="14" cy="14" r="14" fill="hsl(${tinta}, 45%, 32%)"/>
    <text x="14" y="19" text-anchor="middle" font-size="11" font-weight="700" fill="#EDEAE0" font-family="system-ui">${iniziali}</text>
  </svg>`;
}

function trendIcona(valore) {
  if (valore === null || valore === undefined) return "";
  if (valore > 0.02) return '<span class="trend su">▲</span>';
  if (valore < -0.02) return '<span class="trend giu">▼</span>';
  return "";
}

const TAG_ICONS = {
  'bonus': 'Bonus.png',
  'titolarissimo': 'Titolarissimo.png',
  'costante': 'Costante.png',
  'subentrante': 'SUbentrante.png',
  'modificatore': 'Modificatore.png',
  'cartellini': 'Cartellini.png',
  'assistman': 'AssistMan.png',
  'affare nascosto': 'Affare Nascosto.png',
  'rigorista': 'Rigorista.png',
  'tiratore': 'Tiratore.png',
  'esca': 'Esca.png',
  'rischio infortuni': 'Infortuni.png',
  'imbattibilità': "Imbattibilita'.png",
  'coppa africa': 'africa.png',
  'tanti gol': 'goals.png',
  'jolly': 'Jolly.png',
  'pararigori': 'Pararigori.png',
  'scommessa': 'Scommessa.png'
};

const TAG_ICONS_MONO = new Set(['costante', 'titolarissimo', 'tanti gol', 'Tiratore', 'Infortuni', 'Modificatore', 'AssistMan']);
const TAG_ICONS_BASE_PATH = 'assets/tags/';

function renderTagIcon(tagName) {
  const key = tagName.toLowerCase();
  const file = TAG_ICONS[key];
  if (!file) {
    return `<span class="tag">${tagName}</span>`;
  }
  const monoClass = TAG_ICONS_MONO.has(key) ? ' tag-icon--mono' : '';
  return `<img class="tag-icon${monoClass}" src="${TAG_ICONS_BASE_PATH}${encodeURIComponent(file)}" alt="${tagName}" title="${tagName}">`;
}

function apriPannello(playerId) {
  const g = PLAYERS_DATA.find(p => p.player_id === playerId);
  if (!g) return;

  const tag = (g.tag || []).map(t => renderTagIcon(t)).join("");
  const confronto = g.prezzi_per_fonte
    ? Object.entries(g.prezzi_per_fonte).map(([fonte, prezzo]) =>
        `<div class="riga-dato">
          <span class="avatar-fonte">${avatarSvg(fonte)} ${fonte}</span>
          <span class="val">${formatta(prezzo)}</span>
        </div>`
      ).join("")
    : '<p class="stimato">Non presente in tutte le fonti FantaLab</p>';

  const badgeObiettivo = g.obiettivo_count
    ? `<div class="obiettivo-badge">Obiettivo per ${g.obiettivo_count}/${g.n_fonti_totali ?? 4} fantallenatori</div>`
    : "";

  document.getElementById("pannello-contenuto").innerHTML = `
    <h2>${g.nome_canonico}</h2>
    <div class="sottotitolo">${g.ruolo ?? "—"} · ${g.dato_stimato ? "QUOT. stimata da 25/26" : "QUOT. da consenso FantaLab"}</div>
    ${badgeObiettivo}

    <div class="riga-dato"><span>QUOT. consenso</span><span class="val">${formatta(g.quot_consenso_2627)}</span></div>
    <div class="riga-dato"><span>Range fonti</span><span class="val">${formatta(g.prezzo_min)} – ${formatta(g.prezzo_max)}</span></div>
    <div class="riga-dato"><span>Affidabilità</span><span class="val">${formatta(g.indice_affidabilita)}</span></div>
    <div class="riga-dato"><span>Gol/90</span><span class="val">${formatta(g.goals_90, 2)}${trendIcona(g.goals_90_trend)}</span></div>
    <div class="riga-dato"><span>Assist/90</span><span class="val">${formatta(g.assists_90, 2)}</span></div>
    <div class="riga-dato"><span>xG/90</span><span class="val">${formatta(g.xg90, 2)}${trendIcona(g.xg90_trend)}</span></div>
    <div class="riga-dato"><span>xA/90</span><span class="val">${formatta(g.xa90, 2)}</span></div>
    <div class="riga-dato"><span>Stagioni valide</span><span class="val">${formatta(g.n_stagioni_valide, 0)}</span></div>

    <h3 style="margin-top:1rem; font-size:0.85rem; color:var(--testo-muto);">Prezzo per fonte FantaLab</h3>
    ${confronto}

    <div style="margin-top:0.8rem;">${tag}</div>
  `;

  document.getElementById("pannello").classList.add("aperto");
  document.getElementById("pannello").setAttribute("aria-hidden", "false");
  document.getElementById("pannello-backdrop").classList.add("aperto");
}


function chiudiPannello() {
  document.getElementById("pannello").classList.remove("aperto");
  document.getElementById("pannello").setAttribute("aria-hidden", "true");
  document.getElementById("pannello-backdrop").classList.remove("aperto");
}

document.getElementById("chiudi-pannello").addEventListener("click", chiudiPannello);
document.getElementById("pannello-backdrop").addEventListener("click", chiudiPannello);

document.getElementById("ricerca").addEventListener("input", e => {
  filtroTesto = e.target.value.toLowerCase();
  renderTabella();
});

document.querySelectorAll("#filtri-ruolo button").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll("#filtri-ruolo button").forEach(b => b.classList.remove("attivo"));
    btn.classList.add("attivo");
    filtroRuolo = btn.dataset.ruolo;
    if (filtroRuolo !== "TUTTI") {
      ordinamento = { chiave: "nome_canonico", asc: true };
    }
    renderTabella();
  });
});

document.querySelectorAll("thead th").forEach(th => {
  th.addEventListener("click", () => {
    const chiave = th.dataset.key;
    ordinamento.asc = ordinamento.chiave === chiave ? !ordinamento.asc : false;
    ordinamento.chiave = chiave;
    renderTabella();
  });
});

renderTopListe();
renderTabella();
