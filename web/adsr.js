/* ADSR in the browser.
 *
 * The rules and the computer players are ADSR's own Python (app/cards.py,
 * app/engine.py, app/ai.py), run unchanged by Pyodide; web/bridge.py links them
 * to this page.  This file only draws the game and collects the player's moves,
 * following the desktop version's screen (app/gui.py).
 */
"use strict";

const TYPE_NAMES = { A: "Attack", S: "Sustain", D: "Decay", R: "Release" };
const CARD_FACE = "#fbf8f0";
const GOLD = "#f2c14e";
const COMPUTER_DELAY = 750;           // ms between computer moves, so they can be followed

let py = null;                        // the Pyodide runtime
let bridge = null;                    // web/bridge.py
let manifest = null;
let glyphs = {};
let session = null;                   // bridge.Session
let seats = [];                       // [{name, kind, level}]
let view = null;                      // engine view for the player at the screen
let viewer = 0;                       // whose hand is on screen
let selected = new Set();
let target = null;
let busy = false;
let lastHuman = null;                 // for "pass the device"

const $ = (id) => document.getElementById(id);

/* Narrow screens (phones; or any window under 600 px wide) get the compact layout:
   simpler cards, a folded prompt, the buttons pinned at the bottom.  Wider screens
   (tablets and up) are not affected.  Measured live, so turning or resizing works. */
const NARROW = window.matchMedia("(max-width: 600px)");
const narrow = () => NARROW.matches;
NARROW.addEventListener("change", () => { if (view) render(); });
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

/* ------------------------------------------------------------------ storage */
function remember(key, value) { try { localStorage.setItem("adsr." + key, JSON.stringify(value)); } catch (e) { /* private mode */ } }
function recall(key, fallback) {
  try { const v = localStorage.getItem("adsr." + key); return v ? JSON.parse(v) : fallback; } catch (e) { return fallback; }
}

/* ------------------------------------------------------------------ loading */
async function boot() {
  try {
    $("loading-text").textContent = "Loading the game engine… (the first time takes a little while)";
    py = await loadPyodide();
    manifest = await (await fetch("manifest.json")).json();
    glyphs = await (await fetch("glyphs.json")).json();
    const fs = py.FS;
    fs.mkdirTree("/adsr/app");
    fs.mkdirTree("/adsr/decks");
    const files = [...manifest.python, ...manifest.decks.map((d) => d.file), "web/bridge.py"];
    for (const f of files) {
      const r = await fetch("../" + f);
      if (!r.ok) throw new Error(`could not load ${f}`);
      const dest = f === "web/bridge.py" ? "/adsr/bridge.py" : "/adsr/" + f;
      fs.writeFile(dest, await r.text());
    }
    py.runPython("import sys, os; sys.path.insert(0, '/adsr'); os.chdir('/adsr')");
    bridge = py.pyimport("bridge");
    showSetup();
  } catch (e) {
    $("loading-text").textContent = "ADSR could not start: " + e.message +
      ". Check the internet connection and reload the page.";
    document.querySelector(".spinner").hidden = true;
  }
}

/* ------------------------------------------------------------------ setup */
const LEVELS = [["human", "Person"], ["easy", "Computer · Easy"], ["normal", "Computer · Normal"], ["hard", "Computer · Hard"]];

function showSetup() {
  $("loading").hidden = true;
  $("game").hidden = true;
  $("setup").hidden = false;
  $("btn-new").hidden = true;
  $("btn-log").hidden = true;
  $("status").textContent = "";
  const sel = $("deck");
  sel.innerHTML = manifest.decks.map((d, i) => `<option value="${i}">${esc(d.name)}</option>`).join("");
  sel.value = String(Math.min(recall("deck", 0), manifest.decks.length - 1));
  const saved = recall("seats", null);
  renderSeats(saved || [
    { name: "You", kind: "human" },
    { name: "Ada", kind: "normal" },
    { name: "Basil", kind: "normal" },
    { name: "Cleo", kind: "normal" },
  ]);
  deckNote();
}

function deckNote() {
  const d = manifest.decks[+$("deck").value];
  const info = JSON.parse(bridge.deck_info(d.file));
  $("deck-note").textContent = info.error ||
    `${info.kinds.length} Kinds · ${info.rules.start_hp} HP each · hand of ${info.rules.hand_size} · 2–${info.max_players} players`;
  $("add-seat").disabled = $("seats").children.length >= d.max_players;
}

function renderSeats(list) {
  $("seats").innerHTML = "";
  list.forEach((s) => addSeatRow(s));
}

function addSeatRow(s) {
  const row = document.createElement("div");
  row.className = "seat";
  row.innerHTML = `<input aria-label="Player name" maxlength="16" value="${esc(s.name)}">
    <select aria-label="Who plays">${LEVELS.map(([v, t]) => `<option value="${v}">${t}</option>`).join("")}</select>
    <button type="button" aria-label="Remove this player">✕</button>`;
  row.querySelector("select").value = s.kind;
  row.querySelector("button").onclick = () => { row.remove(); deckNote(); };
  $("seats").appendChild(row);
}

$("add-seat").onclick = () => {
  const names = ["Ada", "Basil", "Cleo", "Dov", "Esme", "Finn", "Gus"];
  const used = new Set([...$("seats").querySelectorAll("input")].map((i) => i.value));
  addSeatRow({ name: names.find((n) => !used.has(n)) || "Player", kind: "normal" });
  deckNote();
};
$("deck").onchange = deckNote;

$("start").onclick = () => {
  const rows = [...$("seats").children];
  const d = manifest.decks[+$("deck").value];
  const list = rows.map((r, i) => ({
    name: r.querySelector("input").value.trim() || `Player ${i + 1}`,
    kind: r.querySelector("select").value,
  }));
  if (list.length < 2 || list.length > d.max_players) {
    $("setup-error").textContent = `Choose 2–${d.max_players} players.`;
    return;
  }
  if (new Set(list.map((s) => s.name)).size !== list.length) {
    $("setup-error").textContent = "Give each player a different name.";
    return;
  }
  $("setup-error").textContent = "";
  remember("deck", +$("deck").value);
  remember("seats", list);
  seats = list.map((s) => s.kind === "human" ? { name: s.name, kind: "human" }
    : { name: s.name, kind: "computer", level: s.kind });
  try {
    if (session) session.destroy();
    session = bridge.Session(d.file, JSON.stringify(seats));
  } catch (e) {
    $("setup-error").textContent = String(e.message || e).split("\n").filter(Boolean).pop();
    return;
  }
  const humans = seats.map((s, i) => s.kind === "human" ? i : -1).filter((i) => i >= 0);
  viewer = humans.length ? humans[0] : -1;
  lastHuman = humans.length === 1 ? humans[0] : null;
  selected.clear();
  target = null;
  $("setup").hidden = true;
  $("game").hidden = false;
  $("btn-new").hidden = false;
  $("btn-log").hidden = false;
  step();
};

/* ------------------------------------------------------------------ game loop */
function refresh() {
  view = JSON.parse(session.view(viewer));
  render();
}

async function step() {
  if (busy) return;
  busy = true;
  try {
    refresh();
    while (session.pending() >= 0 && session.is_computer(session.pending())) {
      await new Promise((r) => setTimeout(r, COMPUTER_DELAY));
      session.computer_step();
      refresh();
    }
    const p = session.pending();
    if (p >= 0 && p !== viewer) {             // another person's move on this device
      viewer = p;
      selected.clear();
      target = null;
      refresh();
    }
    if (p >= 0 && seats.filter((s) => s.kind === "human").length > 1 && p !== lastHuman) {
      lastHuman = p;
      $("pass-text").innerHTML = `Pass the device to <b>${esc(seats[p].name)}</b>.`;
      $("pass").hidden = false;
    }
  } finally {
    busy = false;
  }
}

$("pass-ok").onclick = () => { $("pass").hidden = true; };
$("prompt").onclick = () => { if (narrow()) $("prompt").classList.toggle("open"); };

function send(action) {
  const err = session.act(viewer, JSON.stringify(action));
  if (err) {
    $("hint").textContent = err.charAt(0).toUpperCase() + err.slice(1) + ".";
    return;
  }
  selected.clear();
  target = null;
  step();
}

/* ------------------------------------------------------------------ helpers */
const hand = () => Object.fromEntries((view.hand || []).map((c) => [c.id, c]));
const mine = () => view.pending === view.you && view.you !== null && view.you >= 0;
const kinds = () => view.deck.kinds;
const wild = (typ) => kinds().length && (kinds()[0].wild || "").includes(typ);
const hasFamilies = () => new Set(kinds().map((k) => k.family || k.name)).size < kinds().length;

function isSet(ids, typ) {
  const want = [...ids].sort((a, b) => a - b).join(",");
  return (view.legal[typ] || []).some((s) => [...s].sort((a, b) => a - b).join(",") === want);
}

function split() {
  const h = hand();
  const parts = {};
  for (const id of selected) (parts[h[id].type] ||= []).push(id);
  return parts;
}

function usable() {
  const u = new Set();
  for (const sets of Object.values(view.legal || {})) for (const s of sets) for (const id of s) u.add(id);
  return u;
}

function orList(items, word = "or") {
  return items.length === 1 ? items[0] : `${items.slice(0, -1).join(", ")} ${word} ${items[items.length - 1]}`;
}

function kindHtml(k) {
  const kd = kinds()[k];
  return `<span style="color:${kd.color}"><b>${esc(kd.name)}</b></span>`;
}

function matchPhrase(k) {
  if (!hasFamilies()) return `the ${kindHtml(k)} Kind`;
  const fam = kinds()[k].family;
  const members = kinds().filter((x) => x.family === fam).map((x) => `<span style="color:${x.color}">${esc(x.name)}</span>`);
  return `the <b>${esc(fam)}</b> family (${orList(members)})`;
}

function wildPhrase(k, typ, what) {
  return wild(typ) ? `${what} of <b>any Kind</b>` : `${what} from ${matchPhrase(k)}`;
}

function beatPhrase(k, types, bonus) {
  const fam = kinds()[k].family;
  const fams = [...new Set(kinds().filter((x) => fam in (x.beats || {})).map((x) => x.family))].sort();
  if (!fams.length) return "";
  return ` — or ${types} from <b>${esc(orList(fams))}</b>, which beat ${esc(fam)} (+${bonus}%)`;
}

/* ------------------------------------------------------------------ cards */
function darker(hex, factor) {
  const n = parseInt(hex.slice(1), 16);
  const f = (v) => Math.max(0, Math.min(255, Math.round(v * 100 / factor)));
  return "#" + [f(n >> 16), f((n >> 8) & 255), f(n & 255)].map((v) => v.toString(16).padStart(2, "0")).join("");
}

/* One card as SVG, laid out like gui.paint_card on a 108 x 156 card. */
function cardSvg(card, opt = {}) {
  const W = 108, H = 156, small = !!opt.small;
  const kd = kinds()[card.kind];
  const col = kd.color;
  const rad = W * 0.09;
  const inset = small ? 3 : 4;
  const bandH = H * (small ? 0.25 : 0.22);
  const bandBottom = inset + bandH;
  const out = [];
  out.push(`<svg viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="${esc(kd.name + " " + TYPE_NAMES[card.type] + " " + card.value + "%")}">`);
  out.push(`<rect x="1.5" y="1.5" width="${W - 3}" height="${H - 3}" rx="${rad}" fill="${CARD_FACE}" stroke="${opt.selected ? GOLD : darker(col, 140)}" stroke-width="${opt.selected ? 5 : 1.6}"/>`);
  out.push(`<rect x="${inset}" y="${inset}" width="${W - 2 * inset}" height="${bandH}" rx="${rad * 0.7}" fill="${col}"/>`);
  const tf = `font-family="system-ui,sans-serif" font-weight="700" fill="#fff"`;
  out.push(`<text x="${inset + (W - 2 * inset) * 0.08}" y="${inset + bandH * 0.73}" font-size="${bandH * 0.68}" ${tf}>${card.type}</text>`);
  if (kd.head) out.push(`<text x="${W / 2}" y="${inset + bandH * 0.72}" font-size="${bandH * 0.6}" text-anchor="middle" ${tf}>★</text>`);
  else if ((kd.wild || "").includes(card.type)) out.push(`<text x="${W / 2}" y="${inset + bandH * 0.66}" font-size="${bandH * (small ? 0.5 : 0.42)}" text-anchor="middle" ${tf}>${small ? "✱" : "WILD"}</text>`);
  if (card.need > 1) out.push(`<text x="${W - inset - (W - 2 * inset) * 0.08}" y="${inset + bandH * 0.66}" font-size="${bandH * 0.42}" text-anchor="end" ${tf}>×${card.need}</text>`);
  const gx = W * 0.2, gy = bandBottom + H * (small ? 0.07 : 0.05), gh = H * 0.15;
  const g = glyphs[kd.glyph];
  if (kd.glyph === "letter" || !g) {
    out.push(`<text x="${W / 2}" y="${gy + gh * 0.9}" font-size="${gh * 1.2}" text-anchor="middle" font-weight="700" fill="${col}" font-family="system-ui,sans-serif">${esc(kd.name.charAt(0).toUpperCase())}</text>`);
  } else {
    const sw = Math.max(g.icon ? 1.4 : 1.6, W * (g.icon ? 0.024 : 0.035));
    out.push(`<path d="${g.d}" transform="translate(${gx} ${gy})" fill="none" stroke="${col}" stroke-width="${sw}" stroke-linecap="round" stroke-linejoin="round"/>`);
  }
  let y = gy + gh + H * (small ? 0.05 : 0.03);
  const ink = darker(col, 165);
  if (!small) {
    const room = W - 8;
    let fs = H * 0.082;
    const est = kd.name.length * fs * 0.6;                 // rough width of bold text
    if (est > room) fs *= room / est;
    out.push(`<text x="${W / 2}" y="${y + H * 0.075}" font-size="${fs}" text-anchor="middle" font-weight="700" fill="${ink}" font-family="system-ui,sans-serif">${esc(kd.name)}</text>`);
    out.push(`<text x="${W / 2}" y="${y + H * 0.16}" font-size="${H * 0.075}" text-anchor="middle" fill="${ink}" font-family="system-ui,sans-serif">${TYPE_NAMES[card.type]}</text>`);
    y += H * 0.17;
  }
  const vh = H * (small ? 0.19 : 0.16);
  out.push(`<text x="${W / 2}" y="${y + vh * 0.8}" font-size="${H * (small ? 0.17 : 0.14)}" text-anchor="middle" font-weight="700" fill="#26241f" font-family="system-ui,sans-serif">${card.value}%</text>`);
  if (card.type === "A") {
    out.push(`<text x="${W / 2}" y="${y + vh + H * (small ? 0.08 : 0.07)}" font-size="${H * (small ? 0.11 : 0.09)}" text-anchor="middle" font-weight="700" fill="#a8322a" font-family="system-ui,sans-serif">${card.damage} dmg</text>`);
  }
  out.push("</svg>");
  return out.join("");
}

function cardTip(card) {
  const kd = kinds()[card.kind];
  const bits = [`${kd.name} ${TYPE_NAMES[card.type]} — ${card.value}%`];
  if (card.type === "A") bits.push(`${card.damage} damage`);
  bits.push(card.need > 1 ? `played in a set of exactly ${card.need}` : "can be played alone");
  if (hasFamilies()) bits.push(`${kd.family} family`);
  if ((kd.wild || "").includes(card.type)) bits.push("Wild: works on an Attack of any Kind");
  return bits.join(" · ");
}

/* ------------------------------------------------------------------ rendering */
function render() {
  const v = view;
  const names = v.players.map((p) => p.name);
  $("status").textContent = `${v.deck.name} · Turn ${v.turn_no}`;
  renderPlayers(names);
  renderTable(names);
  renderControls(names);
  renderHand();
  $("log").innerHTML = v.log.map((l) => `<li>${esc(l)}</li>`).join("");
  const lp = $("log");
  lp.scrollTop = lp.scrollHeight;
}

function renderPlayers(names) {
  const v = view;
  const ex = v.exchange;
  const choosing = mine() && v.phase === "turn";
  $("players").innerHTML = v.players.map((p) => {
    const cls = ["player"];
    if (p.id === v.current && v.phase !== "over") cls.push("current");
    if (ex && p.id === ex.target) cls.push("target");
    if (!p.alive) cls.push("out");
    if (p.hp <= p.max_hp * 0.3) cls.push("low");
    const can = choosing && p.alive && p.id !== v.you;
    if (can) cls.push("choosable");
    if (can && p.id === target) cls.push("chosen");
    const tag = p.id === v.you ? ` <span class="you"><span class="wide-only">your hand</span><span class="narrow-only">you</span></span>` : "";
    return `<button type="button" class="${cls.join(" ")}" data-pid="${p.id}" ${can ? "" : "tabindex=-1"}>
      <span class="name"><span>${esc(p.name)}${tag}</span><span>${p.alive ? p.hp + " HP" : "out"}</span></span>
      <span class="hp"><span style="width:${Math.max(0, 100 * p.hp / p.max_hp)}%"></span></span>
      <span class="meta">${p.hand_count} cards${p.id === v.current && v.phase !== "over" ? " · to play" : ""}</span>
    </button>`;
  }).join("");
  for (const b of $("players").querySelectorAll(".choosable")) {
    b.onclick = () => { target = +b.dataset.pid; render(); };
  }
}

function groupHtml(cards, label) {
  return `<div class="group"><div class="cards">${cards.map((c) => `<div class="card mini" title="${esc(cardTip(c))}">${cardSvg(c, { small: true })}</div>`).join("")}</div><div class="label">${label}</div></div>`;
}

function renderTable(names) {
  const v = view;
  const ex = v.exchange || v.last;
  if (!ex) {
    $("table").innerHTML = `<div class="empty">No Attack yet. ${v.draw_count} cards in the draw pile.</div>`;
    return;
  }
  const live = !!v.exchange;
  const parts = [groupHtml(ex.cards, `<b>${esc(names[ex.attacker])}</b> attacks <b>${esc(names[ex.target])}</b> · ${ex.damage} dmg`)];
  for (const p of ex.plays) {
    const sign = p.type === "S" ? `+${p.shift}` : p.type === "D" ? `−${p.shift}` : `${p.value}% roll`;
    parts.push(groupHtml(p.cards, `${esc(names[p.player])}: ${TYPE_NAMES[p.type]} ${sign}`));
  }
  let odds = `<div class="odds">${ex.percent}%<small>${live ? "to hit" : "was the chance"}</small></div>`;
  let result = "";
  if (!live && ex.result) {
    const r = ex.result;
    result = r.released ? "Released — the Attack failed."
      : r.hit ? `Hit (roll ${r.attack_roll}): ${names[ex.target]} took ${r.damage}${r.extras.length ? " + " + r.extras.map((e) => e.amount).join(" + ") : ""} damage.`
        : `Missed (roll ${r.attack_roll}).`;
    if (r.eliminated) result += ` ${names[ex.target]} is out!`;
    result = `<p class="result">${esc(result)}</p>`;
  }
  $("table").innerHTML = `<p class="who">${live ? "Now:" : "Last Attack:"}</p><div class="plays">${parts.join("")}${odds}</div>${result}`;
}

function renderControls(names) {
  const v = view;
  const P = $("primary"), S = $("secondary"), W = $("swap");
  const prompt = $("prompt"), hint = $("hint");
  W.hidden = true;
  hint.textContent = "";
  P.hidden = false; S.hidden = false;
  const n = selected.size;
  if (v.phase === "over") {
    const w = v.winners;
    prompt.innerHTML = w.length ? `★ <b>${esc(w.map((i) => names[i]).join(" & "))}</b> win${w.length === 1 ? "s" : ""}! ★` : "Game over.";
    P.textContent = "New game"; P.disabled = false; P.onclick = showSetup;
    S.hidden = true;
    return;
  }
  if (!mine()) {
    const verb = { turn: "take a turn", defend: "respond", assist: "decide whether to join in", sustain: "decide on a Sustain" }[v.phase];
    prompt.innerHTML = `Waiting for <b>${esc(names[v.pending])}</b> to ${verb}…`;
    P.hidden = true; S.hidden = true;
    return;
  }
  const ex = v.exchange;
  const parts = split();
  const bonus = v.deck.rules.beat_bonus || 0;
  if (v.phase === "turn") {
    const md = v.deck.rules.max_discard;
    prompt.innerHTML = "<b>Your turn.</b> Select an Attack set — same Kind, and exactly as many cards as the largest ×N among them — tap the player to attack, then Attack. " +
      `Or discard up to ${md} cards (none = pass). Double-tap a card to pick its best set.` +
      (v.swap ? ` First you may <b>swap</b> up to ${v.swap} dimmed card${v.swap > 1 ? "s" : ""} for new ones.` : "");
    const alive = v.players.filter((p) => p.alive && p.id !== v.you);
    if (target === null || !alive.some((p) => p.id === target)) target = alive.length === 1 ? alive[0].id : target;
    const ok = n > 0 && isSet(selected, "A");
    P.textContent = target !== null ? `Attack ${names[target]}` : "Attack";
    P.disabled = !(ok && target !== null);
    P.onclick = () => send({ type: "attack", cards: [...selected], target });
    if (ok) {
      const h = hand();
      const ids = [...selected];
      const val = Math.round(ids.reduce((a, i) => a + h[i].value, 0) / n + 1e-9);
      hint.textContent = `${val}% to hit · ${ids.reduce((a, i) => a + h[i].damage, 0)} damage` + (target === null ? " · now tap a player to attack" : "");
    } else if (n && parts.A && Object.keys(parts).length === 1) {
      hint.textContent = "Not a complete Attack set yet.";
    }
    S.textContent = n ? `Discard ${n}` : "Pass";
    S.disabled = n > md;
    S.onclick = () => send({ type: "discard", cards: [...selected] });
    if (n > md) hint.textContent = `You can discard at most ${md}.`;
    if (v.swap) {
      const u = usable();
      const dimmed = ![...selected].some((i) => u.has(i));
      W.hidden = false;
      W.textContent = n ? `Swap ${n}` : "Swap…";
      W.disabled = !(n > 0 && n <= v.swap && dimmed);
      W.onclick = () => send({ type: "swap", cards: [...selected] });
      if (n && !dimmed) hint.textContent = "Only dimmed cards can be swapped.";
      else if (n > v.swap) hint.textContent = `You can swap at most ${v.swap}.`;
    }
  } else if (v.phase === "defend") {
    const k = ex.kind;
    prompt.innerHTML = `<b>${esc(names[ex.attacker])}</b> attacks you with ${kindHtml(k)} — ${ex.percent}% to hit, ${ex.damage} damage. ` +
      ((wild("D") || wild("R"))
        ? `Answer with ${wildPhrase(k, "D", "a Decay set")} (lowers the chance) and/or ${wildPhrase(k, "R", "a Release set")} (a roll to cancel it)`
        : `Answer with a Decay set (lowers the chance) and/or a Release set (a roll to cancel it) from ${matchPhrase(k)}`) +
      beatPhrase(k, "Decay/Release", bonus) + ".";
    const keys = Object.keys(parts);
    const ok = keys.length > 0 && keys.every((t) => (t === "D" || t === "R") && isSet(parts[t], t));
    P.textContent = "Respond"; P.disabled = !ok;
    P.onclick = () => send({ type: "respond", cards: [...selected] });
    S.textContent = "No response"; S.disabled = false;
    S.onclick = () => send({ type: "respond", cards: [] });
  } else if (v.phase === "assist") {
    const k = ex.kind;
    prompt.innerHTML = `<b>${esc(names[ex.attacker])}</b> attacks <b>${esc(names[ex.target])}</b> with ${kindHtml(k)} (${ex.percent}% to hit). ` +
      ((wild("S") || wild("D"))
        ? `Join in with ${wildPhrase(k, "S", "one Sustain set")} — if it hits you deal a share of the damage — or ${wildPhrase(k, "D", "one Decay set")} — if it fails you heal`
        : `Join in with one Sustain set — if it hits you deal a share of the damage — or one Decay set — if it fails you heal — from ${matchPhrase(k)}`) +
      beatPhrase(k, "a Decay", bonus) + ".";
    const keys = Object.keys(parts);
    const typ = keys.length === 1 ? keys[0] : null;
    const ok = (typ === "S" || typ === "D") && isSet(selected, typ);
    P.textContent = typ === "S" || typ === "D" ? `Play ${TYPE_NAMES[typ]}` : "Play"; P.disabled = !ok;
    P.onclick = () => send({ type: "assist", cards: [...selected] });
    S.textContent = "Stay out"; S.disabled = false;
    S.onclick = () => send({ type: "assist", cards: [] });
  } else {
    prompt.innerHTML = `Your Attack on <b>${esc(names[ex.target])}</b> stands at ${ex.percent}%. Add ${wildPhrase(ex.kind, "S", "a Sustain set")} to raise it, or resolve now.`;
    const ok = n > 0 && isSet(selected, "S");
    P.textContent = "Play Sustain"; P.disabled = !ok;
    P.onclick = () => send({ type: "sustain", cards: [...selected] });
    S.textContent = "Resolve"; S.disabled = false;
    S.onclick = () => send({ type: "sustain", cards: [] });
  }
}

function renderHand() {
  const v = view;
  const u = usable();
  const my = mine();
  const box = $("hand");
  if (v.you === null || v.you < 0) { box.innerHTML = ""; return; }
  box.innerHTML = v.hand.map((c) => {
    const dim = my && !u.has(c.id) && !selected.has(c.id);       // not in any set you can play now
    const style = dim ? ' style="opacity:.42"' : "";
    return `<div class="card${selected.has(c.id) ? " sel" : ""}" data-id="${c.id}" title="${esc(cardTip(c))}"${style}>${cardSvg(c, { selected: selected.has(c.id), small: narrow() })}</div>`;
  }).join("");
  if (!my) return;
  for (const el of box.querySelectorAll(".card")) {
    const id = +el.dataset.id;
    let lastTap = 0;
    el.onclick = () => {
      const now = Date.now();
      if (now - lastTap < 350) { autoset(id); lastTap = 0; return; }
      lastTap = now;
      if (selected.has(id)) selected.delete(id); else selected.add(id);
      render();
    };
  }
}

/* Double-tap: the strongest legal set containing that card (as on the desktop). */
function autoset(id) {
  const h = hand();
  const typ = h[id].type;
  const sets = (view.legal[typ] || []).filter((s) => s.includes(id));
  if (!sets.length) return;
  const score = (s) => [s.reduce((a, i) => a + h[i].value + 3 * h[i].damage, 0) / s.length, s.length];
  const best = sets.reduce((a, b) => { const x = score(a), y = score(b); return (y[0] > x[0] || (y[0] === x[0] && y[1] > x[1])) ? b : a; });
  if (view.phase === "defend") {
    const keep = [...selected].filter((i) => h[i].type !== typ);
    selected = new Set([...keep, ...best]);
  } else {
    selected = new Set(best);
  }
  render();
}

/* ------------------------------------------------------------------ panels */
function openPanel(id) { $(id).hidden = false; }
for (const b of document.querySelectorAll("[data-close]")) b.onclick = () => { $(b.dataset.close).hidden = true; };
$("btn-log").onclick = () => openPanel("log-panel");
$("btn-new").onclick = () => { if (confirm("Leave this game and start a new one?")) showSetup(); };
$("btn-rules").onclick = async () => {
  openPanel("rules-panel");
  if ($("rules").dataset.done) return;
  try {
    const md = await (await fetch("../RULES.md")).text();
    $("rules").innerHTML = markdown(md);
    $("rules").dataset.done = "1";
  } catch (e) {
    $("rules").textContent = "The rules could not be loaded.";
  }
};

/* A small Markdown reader for RULES.md: headings, paragraphs, lists, tables, emphasis. */
function markdown(src) {
  const inline = (s) => esc(s)
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>")
    .replace(/\*([^*]+)\*/g, "<i>$1</i>")
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2">$1</a>');
  const out = [];
  let list = null, table = null, para = [];
  const flush = () => {
    if (para.length) { out.push(`<p>${inline(para.join(" "))}</p>`); para = []; }
    if (list) { out.push(`<${list.tag}>${list.items.map((i) => `<li>${inline(i)}</li>`).join("")}</${list.tag}>`); list = null; }
    if (table) {
      const rows = table.filter((r) => !/^\s*\|?\s*:?-{2,}/.test(r));
      out.push("<table>" + rows.map((r, i) => "<tr>" + r.replace(/^\s*\||\|\s*$/g, "").split("|")
        .map((c) => `<${i ? "td" : "th"}>${inline(c.trim())}</${i ? "td" : "th"}>`).join("") + "</tr>").join("") + "</table>");
      table = null;
    }
  };
  for (const line of src.split("\n")) {
    let m;
    if ((m = line.match(/^(#{1,4})\s+(.*)/))) { flush(); out.push(`<h${m[1].length + 1}>${inline(m[2])}</h${m[1].length + 1}>`); }
    else if (/^\s*\|/.test(line)) { if (!table) { flush(); table = []; } table.push(line); }
    else if ((m = line.match(/^\s*[-*]\s+(.*)/))) { if (!list || list.tag !== "ul") { flush(); list = { tag: "ul", items: [] }; } list.items.push(m[1]); }
    else if ((m = line.match(/^\s*\d+[.)]\s+(.*)/))) { if (!list || list.tag !== "ol") { flush(); list = { tag: "ol", items: [] }; } list.items.push(m[1]); }
    else if (!line.trim()) flush();
    else if (list && /^\s{2,}/.test(line)) list.items[list.items.length - 1] += " " + line.trim();
    else { if (list || table) flush(); para.push(line.trim()); }
  }
  flush();
  return out.join("\n");
}

boot();
