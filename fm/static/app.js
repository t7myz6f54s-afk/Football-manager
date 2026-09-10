/* Touchline — front end. GAME EDITION v1.8 — feels like native game, not browser */
"use strict";

const $ = (s, r) => (r || document).querySelector(s);
const $$ = (s, r) => Array.from((r || document).querySelectorAll(s));
const api = {
  async get(p) {
    let r;
    try { r = await fetch(p); } catch (e) { deadScreen(); throw e; }
    if (!r.ok) {
      const j = await r.json().catch(() => ({}));
      const e = new Error(j.error || j.detail || ("HTTP " + r.status));
      e.status = r.status; throw e;
    }
    return r.json();
  },
  async post(p, b) {
    let r;
    try {
      r = await fetch(p, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(b || {}) });
    } catch (e) { deadScreen(); throw e; }
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(j.detail || j.error || r.status);
    return j;
  }
};

const VERSION = "1.8.0-GAME";
let DEAD = false;
function deadScreen() {
  if (DEAD) return; DEAD = true;
  const d = $("#dead"); if (d) d.classList.remove("hidden");
}
const G = { boot: null, home: null, screen: "home", sub: null, static: null, busy: false, prevScreen: null };

/* -------------------------------------------------------------- GAME JUICE — haptics, sounds, confetti */
const Juice = {
  haptic(type) {
    try {
      if (!navigator.vibrate) return;
      const patterns = {
        tap: [12],
        light: [8],
        medium: [20],
        heavy: [35],
        success: [15, 30, 40],
        warning: [20, 20, 20],
        error: [40, 30, 60],
        goal: [30, 40, 80],
        card: [25],
        var: [15, 20, 15, 20, 40],
        nav: [10]
      };
      navigator.vibrate(patterns[type] || patterns.tap);
    } catch(e) {}
  },
  play(type) {
    // Web Audio API — subtle game sounds, no external files
    try {
      const ctx = Juice._ctx || (Juice._ctx = new (window.AudioContext || window.webkitAudioContext)());
      if (ctx.state === "suspended") ctx.resume();
      const o = ctx.createOscillator();
      const g = ctx.createGain();
      o.connect(g); g.connect(ctx.destination);
      const now = ctx.currentTime;
      const sounds = {
        tap: { f: 800, d: 0.06, t: "sine", v: 0.08 },
        nav: { f: 600, d: 0.08, t: "sine", v: 0.07 },
        success: { f: 660, d: 0.18, t: "sine", v: 0.12, f2: 880 },
        goal: { f: 440, d: 0.35, t: "triangle", v: 0.15, f2: 660 },
        card: { f: 220, d: 0.12, t: "sawtooth", v: 0.08 },
        var: { f: 300, d: 0.22, t: "square", v: 0.06 },
        error: { f: 180, d: 0.2, t: "sawtooth", v: 0.09 }
      };
      const s = sounds[type] || sounds.tap;
      o.type = s.t; o.frequency.setValueAtTime(s.f, now);
      if (s.f2) o.frequency.linearRampToValueAtTime(s.f2, now + s.d * 0.6);
      g.gain.setValueAtTime(0, now);
      g.gain.linearRampToValueAtTime(s.v, now + 0.01);
      g.gain.exponentialRampToValueAtTime(0.001, now + s.d);
      o.start(now); o.stop(now + s.d);
    } catch(e) {}
  },
  confetti() {
    try {
      const colors = ["#35e08a", "#4ded9c", "#5a9eff", "#ffcc33", "#a78bfa"];
      for (let i = 0; i < 28; i++) {
        const el = document.createElement("div");
        el.style.position = "fixed";
        el.style.left = (Math.random() * 100) + "vw";
        el.style.top = "-10px";
        el.style.width = (6 + Math.random() * 8) + "px";
        el.style.height = (6 + Math.random() * 6) + "px";
        el.style.background = colors[Math.floor(Math.random() * colors.length)];
        el.style.borderRadius = Math.random() > 0.5 ? "50%" : "3px";
        el.style.pointerEvents = "none";
        el.style.zIndex = "95";
        el.style.transform = `rotate(${Math.random() * 360}deg)`;
        document.body.appendChild(el);
        const anim = el.animate([
          { transform: `translateY(0) rotate(0deg) scale(1)`, opacity: 1 },
          { transform: `translateY(${60 + Math.random() * 40}vh) rotate(${360 + Math.random() * 720}deg) translateX(${(Math.random() - 0.5) * 120}px) scale(.8)`, opacity: 0 }
        ], { duration: 1200 + Math.random() * 800, easing: "cubic-bezier(.2,.8,.2,1)", delay: Math.random() * 200 });
        anim.onfinish = () => el.remove();
      }
    } catch(e) {}
  },
  shake() {
    try {
      document.body.animate([
        { transform: "translateX(0)" },
        { transform: "translateX(-4px)" },
        { transform: "translateX(4px)" },
        { transform: "translateX(-3px)" },
        { transform: "translateX(3px)" },
        { transform: "translateX(0)" }
      ], { duration: 380, easing: "ease-out" });
    } catch(e) {}
  }
};

/* ------------------------------------------------------------------ helpers */
const esc = s => String(s == null ? "" : s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
function money(m) {
  if (m == null) return "—";
  const a = Math.abs(m);
  if (a >= 1000) return (m < 0 ? "-" : "") + "€" + (a / 1000).toFixed(a >= 10000 ? 0 : 1) + "bn";
  if (a >= 1) return (m < 0 ? "-" : "") + "€" + a.toFixed(a >= 100 ? 0 : 1) + "m";
  return (m < 0 ? "-" : "") + "€" + (a * 1000).toFixed(0) + "k";
}
const wk = w => w == null ? "—" : "€" + Number(w).toFixed(w >= 100 ? 0 : 1) + "k/wk";
function stars(n) {
  if (n == null) return '<span class="muted">—</span>';
  const full = Math.floor(n), half = n - full >= 0.5;
  return `<span class="stars">${"★".repeat(full)}${half ? "½" : ""}${"☆".repeat(Math.max(0, 5 - full - (half ? 1 : 0)))}</span>`;
}
const pct = n => Math.max(0, Math.min(100, Math.round(n || 0)));
function condClass(v) { return v > 1.02 ? "W" : v < 0.92 ? "L" : "D"; }
function fmtDate(s) {
  if (!s) return "—";
  const d = new Date(s + (s.length === 10 ? "T12:00:00" : ""));
  return d.toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short", year: "numeric" });
}
function daysTo(a, b) { return Math.round((new Date(a) - new Date(b)) / 86400000); }
function toast(msg, ms) {
  Juice.haptic("light");
  const t = document.createElement("div");
  t.className = "toast";
  t.style.cssText = "background:linear-gradient(135deg,#1a231f,#151a27);border:1px solid rgba(53,224,138,.25);box-shadow:0 12px 32px rgba(0,0,0,.5),0 0 0 1px rgba(53,224,138,.08) inset;border-radius:14px;padding:12px 16px;font-weight:700;font-size:13px;backdrop-filter:blur(16px)";
  t.innerHTML = `<div style="display:flex;align-items:center;gap:10px"><div style="width:28px;height:28px;border-radius:9px;background:linear-gradient(135deg,var(--acc),var(--acc2));display:grid;place-items:center;color:#06120c;font-weight:900">✓</div><div style="flex:1">${msg}</div></div>`;
  $("#toast-wrap").appendChild(t);
  // animate in
  t.animate([{ transform: "translateY(16px) scale(.96)", opacity: 0 }, { transform: "translateY(0) scale(1)", opacity: 1 }], { duration: 340, easing: "cubic-bezier(.2,.9,.3,1.2)" });
  setTimeout(() => {
    t.animate([{ transform: "translateY(0) scale(1)", opacity: 1 }, { transform: "translateY(-8px) scale(.96)", opacity: 0 }], { duration: 260 }).onfinish = () => t.remove();
  }, ms || 3200);
}
function modal(html, wide) {
  Juice.haptic("medium");
  const box = $("#modal-box");
  box.className = "box" + (wide ? " wide" : "");
  box.style.cssText = "background:linear-gradient(165deg,#151a27,#10131a);border:1px solid rgba(255,255,255,.1);box-shadow:0 24px 64px rgba(0,0,0,.6),inset 0 1px 0 rgba(255,255,255,.08);border-radius:20px;animation:modal-in .36s cubic-bezier(.2,.9,.3,1.2)";
  if (!document.getElementById("modal-kf")) {
    const s = document.createElement("style"); s.id = "modal-kf";
    s.textContent = "@keyframes modal-in{from{opacity:0;transform:translateY(24px) scale(.94)}to{opacity:1;transform:translateY(0) scale(1)}}";
    document.head.appendChild(s);
  }
  box.innerHTML = `<button class="close" onclick="closeModal()" style="width:32px;height:32px;border-radius:10px;background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.08);color:var(--tx)">✕</button>` + html;
  polish(box);
  $("#modal").classList.add("open");
  $("#modal").style.backdropFilter = "blur(18px)";
  $("#modal").style.background = "rgba(6,8,12,.72)";
}
function closeModal() {
  Juice.haptic("light");
  const box = $("#modal-box");
  box.animate([{ transform: "scale(1)", opacity: 1 }, { transform: "scale(.96)", opacity: 0 }], { duration: 180 }).onfinish = () => {
    $("#modal").classList.remove("open");
  };
}
function setBusy(on) { const b = $("#busybar"); if (b) b.classList.toggle("on", !!on); }
$("#modal").addEventListener("click", e => { if (e.target.id === "modal") closeModal(); });
const bar = (v, cls) => `<div class="bar ${cls || ""}"><i style="width:${pct(v)}%"></i></div>`;

/* --------------------------------------------------------------------- boot */
async function boot() {
  try {
    const v = $("#ver"); if (v) v.textContent = "v" + VERSION;
    [["#tb-budget", "finances"], ["#tb-board", "board"], ["#tb-next", "match"], ["#tb-club", "club"]].forEach(([sel, sc]) => {
      const el = $(sel); if (!el) return;
      el.classList.add("tap"); el.onclick = () => { if (!document.body.classList.contains("pregame")) go(sc); };
    });
    $("#splash-msg").textContent = "Loading engine data…";
    G.boot = await api.get("/api/boot");
    G.static = G.boot.static;
  try { REAL_CRESTS = await (await fetch("static/crests.json", { cache: "force-cache" })).json(); } catch (e) { REAL_CRESTS = {}; }
  try { REAL_COMPS = await (await fetch("static/comps.json", { cache: "force-cache" })).json(); } catch (e) { REAL_COMPS = {}; }
    if (G.boot.has_save) {
      $("#splash-msg").textContent = "Loading career…";
      await enterGame();
    } else {
      $("#splash").classList.add("hidden");
      $("#app").classList.remove("hidden");
      showStartScreen();
    }
  } catch (e) {
    $("#splash-msg").innerHTML = `<span style="color:#ff9b9b">Failed to start: ${esc(e.message)}</span>`;
  }
}

/* --------------------------------------------------------- new career flow */
const NAV_START = [];
function showStartScreen() {
  renderNav(NAV_START);
  $("#content").innerHTML = `
    <div style="min-height:72vh;display:grid;place-items:center;padding:20px 14px">
      <div style="width:100%;max-width:520px;text-align:center">
        <div style="position:relative;width:96px;height:96px;margin:0 auto 18px;border-radius:28px;background:linear-gradient(135deg,#0d2818,#123a22);border:1.5px solid rgba(53,224,138,.35);box-shadow:0 18px 48px rgba(53,224,138,.25),inset 0 1px 0 rgba(255,255,255,.08);display:grid;place-items:center;animation:logo-float 3s ease-in-out infinite">
          <svg viewBox="0 0 40 40" style="width:54px;height:54px;filter:drop-shadow(0 0 12px rgba(53,224,138,.6))"><path d="M20 2 L36 8 V20 C36 30 29 36 20 38 C11 36 4 30 4 20 V8 Z" fill="#0d3b26"/><path d="M20 2 L36 8 V20 C36 30 29 36 20 38 C11 36 4 30 4 20 V8 Z" fill="none" stroke="#35e08a" stroke-width="1.6"/><circle cx="20" cy="19" r="7" fill="none" stroke="#35e08a" stroke-width="1.3"/><path d="M20 12v14M13 19h14M15 14.5l10 9M25 14.5l-10 9" stroke="#35e08a" stroke-width=".9" opacity=".8"/></svg>
          <div style="position:absolute;top:-6px;right:-6px;width:22px;height:22px;border-radius:50%;background:linear-gradient(135deg,#35e08a,#4ded9c);display:grid;place-items:center;font-size:11px;font-weight:900;color:#06120c;box-shadow:0 4px 12px rgba(53,224,138,.5)">v8</div>
        </div>
        <h1 style="font-size:38px;letter-spacing:-.04em;margin:0 0 6px;background:linear-gradient(180deg,#eaf5ef 10%,#a7d7be);-webkit-background-clip:text;background-clip:text;color:transparent">TOUCHLINE</h1>
        <div style="display:inline-flex;align-items:center;gap:8px;padding:6px 14px;border-radius:999px;background:rgba(53,224,138,.1);border:1px solid rgba(53,224,138,.18);font-size:11px;letter-spacing:.14em;font-weight:800;color:var(--acc);margin-bottom:14px">● PREMIUM EDITION · OFFLINE · 402 CLUBS</div>
        <p style="color:var(--tx2);font-size:14px;line-height:1.55;margin:0 auto;max-width:380px">A permanent football world. Elite clubs feel elite. Rivals never join rivals. Every window, every sacking, every derby — lives without you.</p>

        <div style="margin:22px auto 0;display:grid;gap:10px;max-width:360px">
          <button class="btn primary" style="min-height:56px;border-radius:16px;font-size:16px;letter-spacing:.02em;box-shadow:0 10px 28px rgba(53,224,138,.35),inset 0 1px 0 rgba(255,255,255,.2)" onclick="Juice.haptic('heavy');Juice.play('success');stepChooseClub()">▶ NEW CAREER</button>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">
            <div style="padding:12px;border-radius:14px;background:linear-gradient(165deg,#151a27,#10131a);border:1px solid var(--line2);text-align:left"><div style="font-size:20px">🌍</div><div style="font-weight:800;font-size:12px;margin-top:4px">Living world</div><div style="font-size:11px;color:var(--tx3);margin-top:2px">Clubs buy, sell, sack — without you</div></div>
            <div style="padding:12px;border-radius:14px;background:linear-gradient(165deg,#151a27,#10131a);border:1px solid var(--line2);text-align:left"><div style="font-size:20px">⚔️</div><div style="font-weight:800;font-size:12px;margin-top:4px">Realism</div><div style="font-size:11px;color:var(--tx3);margin-top:2px">Haaland won't join United. Ever.</div></div>
          </div>
        </div>

        <div style="margin-top:22px;display:flex;justify-content:center;gap:14px;flex-wrap:wrap">
          <div style="text-align:center"><div style="font-size:22px;font-weight:900;letter-spacing:-.03em">402</div><div style="font-size:10px;letter-spacing:.14em;color:var(--tx3);font-weight:700">CLUBS</div></div>
          <div style="width:1px;background:var(--line2)"></div>
          <div style="text-align:center"><div style="font-size:22px;font-weight:900;letter-spacing:-.03em">21</div><div style="font-size:10px;letter-spacing:.14em;color:var(--tx3);font-weight:700">LEAGUES</div></div>
          <div style="width:1px;background:var(--line2)"></div>
          <div style="text-align:center"><div style="font-size:22px;font-weight:900;letter-spacing:-.03em">9K+</div><div style="font-size:10px;letter-spacing:.14em;color:var(--tx3);font-weight:700">PLAYERS</div></div>
          <div style="width:1px;background:var(--line2)"></div>
          <div style="text-align:center"><div style="font-size:22px;font-weight:900;letter-spacing:-.03em">∞</div><div style="font-size:10px;letter-spacing:.14em;color:var(--tx3);font-weight:700">SEASONS</div></div>
        </div>
        <p class="small muted" style="margin-top:18px;opacity:.6">v${VERSION} · Arm64 · Offline · No ads · No IAP</p>
      </div>
    </div>`;
}
let CLUB_PICK = null;
async function stepChooseClub() {
  renderNav(NAV_START);
  let countries = [];
  try { countries = (await api.get("/api/clubs/countries")).countries; } catch (e) {}
  $("#content").innerHTML = `
    <h1>Choose your club</h1>
    <p class="sub">Any club, any nation, any level — from Real Madrid to Wrexham to semi-league minnows.</p>
    <div class="row" style="margin-bottom:12px">
      <input id="cs-q" placeholder="Search club name…" style="width:260px" oninput="debounceSearch()">
      <select id="cs-country" onchange="searchClubs()"><option value="">All nations</option>
        ${countries.map(c => `<option value="${esc(c.country)}">${esc(c.country)} (${c.n})</option>`).join("")}</select>
      <select id="cs-tier" onchange="searchClubs()">
        <option value="0">All levels</option><option value="1">Top division</option>
        <option value="2">2nd tier</option><option value="3">3rd tier</option>
        <option value="4">4th tier</option><option value="5">5th tier</option></select>
      <span class="spacer"></span><span class="muted small" id="cs-count"></span>
    </div>
    <div class="card" id="cs-host" style="padding:10px;max-height:62vh;overflow:auto"></div>`;
  searchClubs();
}

async function searchClubs() {
  const q = encodeURIComponent($("#cs-q")?.value || "");
  const country = encodeURIComponent($("#cs-country")?.value || "");
  const tier = $("#cs-tier")?.value || 0;
  const j = await api.get(`/api/clubs/search?q=${q}&country=${country}&tier=${tier}`);
  $("#cs-count").textContent = j.clubs.length + " clubs";
  const pick = c => `pickClub(${JSON.stringify(c).replace(/'/g, "&#39;")})`;
  if (window.innerWidth < 900) {
    $("#cs-host").innerHTML = j.clubs.length ? `<div class="cards">` + j.clubs.map(c => `
      <div class="tcard">
        <div class="tcard-h"><b>${esc(c.name)}</b><span class="tag">${esc(c.country)} · T${c.tier}</span></div>
        <div class="tcard-g">
          <div class="tcell"><span class="tl">League</span><span class="tv">${esc(c.league_name || c.league)}</span></div>
          <div class="tcell"><span class="tl">Rep</span><span class="tv">${c.rep}</span></div>
          <div class="tcell"><span class="tl">Stadium</span><span class="tv">${(c.capacity || 0).toLocaleString()}</span></div>
          <div class="tcell"><span class="tl">Budget</span><span class="tv">${money(c.transfer_budget)}</span></div>
          <div class="tcell"><span class="tl">Wages</span><span class="tv">${money(c.wage_budget)}</span></div>
        </div>
        <div class="small muted" style="margin:6px 0 8px">${esc(c.stadium)} · ${esc(c.vision || "")}</div>
        <button class="btn sm primary" onclick='${pick(c)}'>SELECT ▸</button>
      </div>`).join("") + `</div>`
      : `<div class="tmsg">No clubs match — try a different search.</div>`;
    return;
  }
  $("#cs-host").innerHTML = `<div class="tw"><table><thead><tr><th>Club</th><th>Nation</th><th>League</th><th class="num">Rep</th>
    <th class="num">Stadium</th><th class="num">Budget</th><th class="num">Wages</th><th></th></tr></thead>
    <tbody id="cs-rows">` + j.clubs.map(c => `
    <tr>
      <td><b>${esc(c.name)}</b><div class="muted small">${esc(c.stadium)} · ${esc(c.vision || "")}</div></td>
      <td>${esc(c.country)}</td>
      <td>${esc(c.league_name || c.league)}<div class="muted small">Tier ${c.tier}</div></td>
      <td class="num">${c.rep}</td>
      <td class="num">${(c.capacity || 0).toLocaleString()}</td>
      <td class="num">${money(c.transfer_budget)}</td>
      <td class="num">${money(c.wage_budget)}</td>
      <td><button class="btn sm primary" onclick='${pick(c)}'>SELECT</button></td>
    </tr>`).join("") + `</tbody></table></div>`;
}

let SEARCH_T = null;
function debounceSearch() { clearTimeout(SEARCH_T); SEARCH_T = setTimeout(searchClubs, 260); }
function pickClub(c) { CLUB_PICK = c; stepManagerProfile(); }

function stepManagerProfile() {
  const c = CLUB_PICK;
  const nations = G.static.nations || [];
  $("#content").innerHTML = `
    <h1>Create your manager</h1>
    <p class="sub">You are about to take charge of <b>${esc(c.name)}</b> — ${esc(c.league_name || c.league)}, ${esc(c.country)}.</p>
    <div class="grid g2" style="max-width:900px">
      <div class="card">
        <h3>Profile</h3>
        <label>Manager name</label><input id="mp-name" style="width:100%" placeholder="e.g. Alex Ferguson" value="">
        <div style="height:8px"></div>
        <label>Nationality</label>
        <select id="mp-nat" style="width:100%"><option>England</option>
          ${nations.filter(n => n !== "England").map(n => `<option>${esc(n)}</option>`).join("")}</select>
        <div style="height:8px"></div>
        <div class="row"><div style="flex:1"><label>Age</label><input id="mp-age" type="number" value="38" min="24" max="75" style="width:100%"></div>
        <div style="flex:1"><label>Reputation (1–95)</label><input id="mp-rep" type="number" value="${Math.max(3, Math.round(c.rep * 0.28))}" min="1" max="95" style="width:100%"></div></div>
        <div style="height:8px"></div>
        <label>Managerial style</label>
        <select id="mp-style" style="width:100%">
          ${["Balanced", "Possession", "High press", "Counter-attack", "Direct", "Defensive solidity", "Wing play", "Youth-focused"]
            .map(s => `<option>${s}</option>`).join("")}</select>
        <div style="height:8px"></div>
        <label>Difficulty</label>
        <select id="mp-diff" style="width:100%">
          ${G.static.difficulties.map(d => `<option value="${d.id}" ${d.id === "realistic" ? "selected" : ""}>${d.name} — ${d.desc}</option>`).join("")}
        </select>
      </div>
      <div class="card">
        <h3>Coaching attributes</h3>
        <p class="small muted">Points left: <b id="mp-left">0</b>. These shape training, man-management, scouting and how quickly players develop under you.</p>
        <div id="mp-attrs"></div>
      </div>
    </div>
    <div class="row" style="margin-top:14px">
      <button class="btn" onclick="stepChooseClub()">◂ Back</button>
      <button class="btn primary" id="mp-go" onclick="createCareer()">TAKE CHARGE ▸</button>
    </div>`;
  const keys = ["attacking", "defending", "fitness", "tactical", "mental", "technical", "youth", "man_mgmt", "motivation", "adaptability", "judging"];
  const names = { attacking: "Attacking", defending: "Defending", fitness: "Fitness", tactical: "Tactical", mental: "Mental", technical: "Technical", youth: "Youth", man_mgmt: "Man management", motivation: "Motivation", adaptability: "Adaptability", judging: "Judging ability" };
  const budget = 132;
  $("#mp-attrs").innerHTML = keys.map(k => `
    <div class="row" style="margin-bottom:4px">
      <div style="width:130px" class="small">${names[k]}</div>
      <input type="range" min="1" max="20" value="12" data-k="${k}" style="flex:1" oninput="attrChanged()">
      <div class="small mono" style="width:22px;text-align:right" id="av-${k}">12</div>
    </div>`).join("");
  window._attrBudget = budget;
  attrChanged();
}
function attrChanged() {
  let used = 0;
  $$('#mp-attrs input[type=range]').forEach(i => { used += +i.value; $("#av-" + i.dataset.k).textContent = i.value; });
  const left = window._attrBudget - used;
  $("#mp-left").textContent = left;
  $("#mp-left").style.color = left < 0 ? "var(--bad)" : "var(--accent)";
  $("#mp-go").disabled = left < 0;
}
async function createCareer() {
  const attrs = {};
  $$('#mp-attrs input[type=range]').forEach(i => attrs[i.dataset.k] = +i.value);
  const body = {
    club_code: CLUB_PICK.code,
    difficulty: $("#mp-diff").value,
    manager: { name: $("#mp-name").value.trim() || "The Manager", nat: $("#mp-nat").value,
               age: +$("#mp-age").value, reputation: +$("#mp-rep").value,
               style: $("#mp-style").value, attrs }
  };
  $("#mp-go").disabled = true; $("#mp-go").textContent = "Building world…"; setBusy(true);
  try {
    const j = await api.post("/api/career/new", body);
    if (!j.ok) throw new Error(j.error || "The engine refused to start this career.");
    onboarding(j);
  } catch (e) { toast("Could not create career: " + esc(e.message), 6000); $("#mp-go").disabled = false; $("#mp-go").textContent = "TAKE CHARGE ▸"; }
  setBusy(false);
}

function onboarding(j) {
  renderNav(NAV_START);
  const m = j.meeting;
  $("#content").innerHTML = `
    <h1>${esc(j.club.name)}</h1>
    <p class="sub">${esc(j.club.league)} · tier ${j.club.tier} · reputation ${j.club.rep}</p>
    <div class="grid g2">
      <div class="card">
        <h3>Club load</h3>
        <ul class="step-list">${j.steps.map((s, i) => `<li><span class="n">${i + 1}</span>
          <div><b>${esc(s[0])}</b><div class="small muted">${esc(s[1])}</div></div></li>`).join("")}</ul>
      </div>
      <div class="card">
        <h3>First management meeting</h3>
        <p class="small">${esc(m.welcome)}</p>
        <div class="kv"><span>Chairman</span><b>${esc(m.chairman)}</b></div>
        <div class="kv"><span>Transfer budget</span><b>${money(m.budget.transfer)}</b></div>
        <div class="kv"><span>Wage budget</span><b>${money(m.budget.wage)} (bill ${money(m.budget.wage_bill)})</b></div>
        <div class="kv"><span>Cash</span><b>${money(m.budget.cash)}</b></div>
        <div class="kv"><span>Debt</span><b>${money(m.budget.debt)}</b></div>
        <div class="kv"><span>Transfer window</span><b>${fmtDate(m.window.opens)} → ${fmtDate(m.window.closes)}</b></div>
        <h2 style="margin-top:14px">Board objectives</h2>
        ${m.objectives.map(o => `<div class="obj"><div class="t">${esc(o.text)}</div>
          <div class="small muted">${esc(o.comp || "")} ${o.target_pos ? "· target position " + o.target_pos : ""} ${o.critical ? "· <b style='color:var(--warn)'>CRITICAL</b>" : ""}</div></div>`).join("")}
        <h2 style="margin-top:14px">Next fixtures</h2>
        ${m.next_fixture.map(f => `<div class="kv"><span>${fmtDate(f.date)} · ${esc(f.comp)}</span>
          <b>${esc(f.home)} v ${esc(f.away)}</b></div>`).join("") || '<div class="muted small">None scheduled</div>'}
      </div>
    </div>
    <div class="card" style="margin-top:12px">
      <h3>Assistant manager's briefing</h3>
      <div class="pre">${esc(m.assistant)}</div>
    </div>
    <div class="row" style="margin-top:14px">
      <button class="btn primary" onclick="enterGame()">GO TO OFFICE ▸</button>
    </div>`;
}

/* ------------------------------------------------------------------- the game */
const NAV = [
  ["home", "", "Dashboard"], ["squad", "", "Squad"], ["tactics", "", "Tactics"],
  ["match", "", "Matches"], ["comps", "", "Competitions"],
  ["sep"], ["transfers", "", "Transfers"], ["scouting", "", "Scouting"],
  ["finances", "", "Finances"], ["inbox", "", "News"],
  ["sep"], ["club", "", "Club"], ["calendar", "", "Calendar"], ["table", "", "League Table"],
  ["training", "", "Training"], ["career", "", "Career"],
];
function renderNav(items) {
  const real = items.filter(n => n[0] !== "sep");
  document.body.classList.toggle("pregame", real.length === 0);
  $("#nav").innerHTML = items.map(n => n[0] === "sep" ? '<div class="sep"></div>' :
    `<button data-s="${n[0]}" onclick="go('${n[0]}')">${svg(n[0])}<span>${n[2]}</span><span class="badge hidden" id="nb-${n[0]}"></span></button>`).join("");
  renderTabbar(real);
  renderSheet(real);
}
async function enterGame() {
  $("#splash").classList.add("hidden");
  $("#app").classList.remove("hidden");
  renderNav(NAV);
  await go("home");
  coachHint();
}
function coachHint() {
  try { if (localStorage.getItem("tl_coach_done")) return; } catch (e) { return; }
  const host = $("#content"); if (!host) return;
  const d = document.createElement("div");
  d.className = "coach";
  d.innerHTML = `<div class="coach-t">${svg("board")}<b>How a season runs</b></div>
    <p><b>CONTINUE</b> advances time to the next meaningful event — mail, deadlines, match days.
    On match days the button becomes <b>MATCH DAY</b>. The red badge is unread inbox;
    everything else lives under <b>More</b>.</p>
    <button class="btn sm primary" onclick="dismissCoach(this)">GOT IT ▸</button>`;
  host.prepend(d);
}
function dismissCoach(btn) {
  btn.closest(".coach").remove();
  try { localStorage.setItem("tl_coach_done", "1"); } catch (e) {}
}
async function resumeMatch() {
  const r = await api.post("/api/match/abandon", {});
  if (r && r.ok) { G.pendingMatch = false; await refreshState(); showResult(r.result); }
  else toast(esc((r && r.msg) || "No paused match."), 4000);
}
const SCREEN_ORDER = ["home","inbox","squad","tactics","match","comps","transfers","scouting","finances","calendar","table","club","board","training","career"];
function getNavDir(newScreen, oldScreen) {
  const a = SCREEN_ORDER.indexOf(oldScreen||"home");
  const b = SCREEN_ORDER.indexOf(newScreen||"home");
  if (a === -1 || b === -1) return 0;
  return b > a ? 1 : b < a ? -1 : 0;
}
async function go(screen, sub) {
  const prev = G.screen;
  G.prevScreen = prev;
  G.screen = screen; G.sub = sub || null;
  $$("#nav button").forEach(b => b.classList.toggle("active", b.dataset.s === screen));
  $$("#tabbar button").forEach(b => b.classList.toggle("active", b.dataset.s === screen));
  $$("#sheet-grid button").forEach(b => b.classList.toggle("active", b.dataset.s === screen));
  $$("#tabbar button[data-s=__more]").forEach(b => b.classList.toggle("active", !TAB_IDS.includes(screen)));
  closeSheet();
  Juice.haptic("nav");
  Juice.play("nav");
  const _c = $("#content");
  if (_c) {
    const dir = getNavDir(screen, prev);
    _c.classList.remove("in","slide-left","slide-right");
    _c.style.animation = "none";
    void _c.offsetWidth;
    _c.style.animation = "";
    if (dir !== 0) {
      _c.classList.add(dir > 0 ? "slide-left" : "slide-right");
      // inject keyframes dynamically if not exist
      if (!document.getElementById("slide-kf")) {
        const s = document.createElement("style");
        s.id = "slide-kf";
        s.textContent = `@keyframes slide-left-in{from{opacity:0;transform:translateX(24px) scale(.98)}to{opacity:1;transform:translateX(0) scale(1)}}@keyframes slide-right-in{from{opacity:0;transform:translateX(-24px) scale(.98)}to{opacity:1;transform:translateX(0) scale(1)}}.slide-left{animation:slide-left-in .34s cubic-bezier(.2,.9,.3,1.2)}.slide-right{animation:slide-right-in .34s cubic-bezier(.2,.9,.3,1.2)}`;
        document.head.appendChild(s);
      }
    } else {
      _c.classList.add("in");
    }
  }
  $("#content").innerHTML = '<div style="display:grid;place-items:center;padding:48px 20px;gap:16px"><div style="width:42px;height:42px;border-radius:14px;background:linear-gradient(135deg,var(--acc),var(--acc2));display:grid;place-items:center;animation:logo-float 1.8s infinite"><div style="width:22px;height:22px;border:2px solid white;border-radius:50%;border-top-color:transparent;animation:spin 0.8s linear infinite"></div></div><div class="small muted" style="font-weight:800;letter-spacing:.12em">LOADING</div></div><style>@keyframes spin{to{transform:rotate(360deg)}}</style>';
  try {
    if (screen === "home") await renderHome();
    else if (screen === "inbox") await renderInbox();
    else if (screen === "squad") await renderSquad();
    else if (screen === "player") await renderPlayer(sub);
    else if (screen === "tactics") await renderTactics();
    else if (screen === "training") await renderTraining();
    else if (screen === "match") await renderMatch();
    else if (screen === "transfers") await renderTransfers();
    else if (screen === "scouting") await renderScouting();
    else if (screen === "finances") await renderFinances();
    else if (screen === "staff") await renderStaff();
    else if (screen === "youth") await renderYouth();
    else if (screen === "calendar") await renderCalendar();
    else if (screen === "table") await renderTable();
    else if (screen === "comps") await renderComps();
    else if (screen === "club") await renderClub();
    else if (screen === "board") await renderBoard();
    else if (screen === "media") await renderMedia();
    else if (screen === "career") await renderCareer();
    else if (screen === "jobs") await renderJobs();
  } catch (e) {
    if (e.status === 400 && /no active career/i.test(e.message || "")) { showStartScreen(); return; }
    $("#content").innerHTML = `<div class="card" style="border-color:#5b2b2b">
      <h3 style="color:var(--bad)">Something went wrong</h3>
      <p class="small muted">${esc(e.message)}</p>
      <div class="row"><button class="btn sm" onclick="go('${screen}')">Retry</button>
      <button class="btn sm primary" onclick="go('home')">Back to home</button></div></div>`;
  }
  $("#content").scrollTop = 0;
  polish($("#content"));
  refreshBadges();
}
async function refreshState() {
  const j = await api.get("/api/state");
  G.home = j.home;
  const wasPending = G.pendingMatch;
  G.pendingMatch = !!j.pending_match;
  if (wasPending && !G.pendingMatch && G.halftimeState) {
    G.halftimeState = null;
    toast("The paused match was abandoned when the server restarted.");
  }
  paintTop();
  return j;
}
function continueLabel() {
  const nf = G.home && G.home.next_fixture;
  if (G.pendingMatch || (nf && G.home && nf.date === G.home.date)) return "MATCH DAY";
  return "CONTINUE";
}
function paintTop() {
  const h = G.home; if (!h) return;
  const _pl0 = $("#btn-continue .pl"); if (_pl0 && !G.busy) _pl0.textContent = continueLabel();
  if (h.unemployed) {
    $("#tb-club").innerHTML = `<span style="font-weight:900">UNEMPLOYED</span><small>Available</small>`;
    $("#tb-budget").innerHTML = `<span class="ico">💼</span><span>—</span>`;
    $("#tb-board").innerHTML = `<span class="ico">🛡️</span><span>—</span>`;
    paintCrest("");
  } else {
    $("#tb-club").innerHTML = `<span style="font-weight:900;letter-spacing:-.02em">${esc(h.club.name)}</span><small>${esc(h.club.league)}</small>`;
    $("#tb-budget").innerHTML = `<span class="ico">💰</span><span>${money(h.finances.transfer_budget)}</span>`;
    const conf = Math.round(h.board.confidence);
    const confColor = conf < 30 ? "color:var(--red)" : conf < 55 ? "color:var(--amber)" : "color:var(--acc)";
    $("#tb-board").innerHTML = `<span class="ico">🛡️</span><span style="${confColor};font-weight:900">${conf}</span>`;
    paintCrest(h.club.code);
  }
  // Game HUD date with icon
  $("#tb-date").innerHTML = `<span style="opacity:.6">📅</span> ${fmtDate(h.date).replace(/, \d{4}$/,"")}`;
  const nf = h.next_fixture;
  if (nf) {
    const isRival = isRivalry(nf.home_code, nf.away_code);
    $("#tb-next").innerHTML = `${isRival ? '🔥 ' : ''}<b>${esc(nf.home_short)} v ${esc(nf.away_short)}</b> <span style="opacity:.6">${fmtDate(nf.date).split(",")[0]}</span>`;
  } else {
    $("#tb-next").innerHTML = `No fixture`;
  }
  $("#btn-continue").disabled = G.busy;
  $("#btn-continue").classList.toggle("busy", G.busy);
}
async function refreshBadges() {
  try {
    const j = await api.get("/api/inbox?unread=true");
    const n = j.items.length;
    const spots = [...document.querySelectorAll('[data-badge="inbox"]')];
    const b = $("#nb-inbox"); if (b) spots.push(b);
    spots.forEach(el => {
      el.textContent = n;
      el.classList.toggle("hidden", !n);
    });
  } catch (e) {}
}

/* ------------------------------------------------------------------- CONTINUE */
$("#btn-continue").addEventListener("click", doContinue);
async function doContinue() {
  if (G.busy) return;
  if (G.pendingMatch) {
    toast("A match is paused at half-time — finish it first.", 4000);
    go("match");
    return;
  }
  G.busy = true; $("#btn-continue").disabled = true; setBusy(true);
  const _pl = $("#btn-continue .pl"); if (_pl) _pl.textContent = "SIMULATING…";
  try {
    const j = await api.post("/api/continue", {});
    await refreshState();
    // anything flagged urgent has now been shown: mark it read so it does not halt us again
    if ((j.urgent || []).length) {
      await api.post("/api/inbox/read", { ids: j.urgent.map(u => u.id) }).catch(() => {});
    }
    showContinueModal(j);
  } catch (e) { toast("Continue failed: " + esc(e.message), 6000); }
  G.busy = false; $("#btn-continue").disabled = false; setBusy(false);
  const _pl2 = $("#btn-continue .pl"); if (_pl2) _pl2.textContent = continueLabel();
}
function showContinueModal(j) {
  const nf = j.next_fixture;
  const items = j.log || [];
  const urg = j.urgent || [];
  modal(`
    <h2>${fmtDate(j.date)} <span class="muted small">· season ${j.season}/${String(j.season + 1).slice(2)} · advanced ${j.days_advanced} day(s)</span></h2>
    ${j.unemployed ? `<p class="sub">You are without a club. <a href="#" onclick="closeModal();go('jobs')">View vacancies →</a></p>` : ""}
    ${nf ? `<div class="card tight" style="margin-bottom:10px">
      <div class="row"><b>Next match:</b> ${esc(nf.home)} v ${esc(nf.away)}
      <span class="muted small">${esc(nf.comp || "")} ${esc(nf.stage !== "league" ? nf.stage : "")} · ${fmtDate(nf.date)}</span>
      <span class="spacer"></span>
      <button class="btn primary sm" onclick="closeModal();go('match')">MATCH CENTRE ▸</button></div></div>` : ""}
    ${urg.length ? `<h3>Urgent</h3>${urg.map(u => `<div class="list-item unread" onclick="closeModal();go('inbox')"><span class="tag URGENT">${esc(u.cat)}</span><div><b>${esc(u.subject)}</b></div></div>`).join("")}` : ""}
    <h3>What happened</h3>
    <div style="max-height:40vh;overflow:auto">
      ${items.length ? items.slice().reverse().map(e => e.type === "match_scheduled"
        ? `<div class="list-item"><span class="muted small">${esc(e.date)}</span><b>Match day: ${e.fixtures.map(f => `${esc(f.home)} v ${esc(f.away)}`).join(", ")}</b></div>`
        : `<div class="list-item"><span class="muted small">${esc(e.date || "")}</span><div>${esc(e.text || "")}</div></div>`).join("")
      : '<p class="muted">Nothing notable happened.</p>'}
    </div>
    <div class="row" style="margin-top:12px"><span class="spacer"></span>
      <button class="btn" onclick="closeModal()">Close</button>
      <button class="btn primary" onclick="closeModal();doContinue()">CONTINUE ▸</button></div>`, true);
}

/* --------------------------------------------------------------------- HOME */
function compLabel(f) {
  return f.comp || (f.stage && f.stage !== "league" ? f.stage : "") || "Match";
}
function compColor(code) {
  code = code || "";
  if (code === "UCL") return "#2a5bd7";
  if (code === "UEL") return "#ff6900";
  if (code === "UECL") return "#00b050";
  if (code === "FACUP") return "#ff4444";
  if (code === "EFLCUP") return "#00c851";
  if (code.includes("CUP") || code.includes("POKAL") || code.includes("COUPE")) return "#ffb454";
  if (code === "ENG1") return "#37003c";
  if (code.startsWith("ENG")) return "#37003c";
  if (code.startsWith("ESP")) return "#ff4b44";
  if (code.startsWith("ITA")) return "#008c99";
  if (code.startsWith("GER")) return "#d20515";
  if (code.startsWith("FRA")) return "#091c3e";
  return "#35e08a";
}
function compClass(code) {
  code = code || "";
  if (code === "UCL") return "comp-UCL";
  if (code === "UEL") return "comp-UEL";
  if (code === "UECL") return "comp-UECL";
  if (code === "FACUP") return "comp-FACUP";
  if (code === "EFLCUP") return "comp-EFLCUP";
  if (code === "ENG1") return "comp-ENG1";
  if (code.startsWith("ENG")) return "comp-ENG1";
  if (code.startsWith("ESP")) return "comp-ESP1";
  if (code.startsWith("ITA")) return "comp-ITA1";
  if (code.startsWith("GER")) return "comp-GER1";
  if (code.startsWith("FRA")) return "comp-FRA1";
  return "";
}
function formPills(form, n) {
  return (form || []).slice(0, n || 6).map(x =>
    `<i class="fm-i ${x.res}" title="${esc(x.score || "")}">${x.res}</i>`).join("");
}
/* Premium helpers for rivalries and press */
function isRivalry(homeCode, awayCode) {
  try {
    const r = (G.static && G.static.rivalries) || {};
    if (!r) return null;
    const rivals = r[homeCode] || [];
    if (rivals.includes(awayCode)) return { type: "derby", name: (G.static.derby_names && G.static.derby_names[homeCode + "-" + awayCode]) || (G.static.derby_names && G.static.derby_names[awayCode + "-" + homeCode]) || "Derby" };
    // Check reverse
    const rivals2 = r[awayCode] || [];
    if (rivals2.includes(homeCode)) return { type: "derby", name: (G.static.derby_names && G.static.derby_names[awayCode + "-" + homeCode]) || "Derby" };
    return null;
  } catch(e) { return null; }
}
function pressHypeForFixture(f) {
  if (!f) return "";
  const rivalry = isRivalry(f.home_code, f.away_code);
  const isBig = (f.code === "UCL" || f.code === "ENG1" || (f.stage && f.stage !== "league"));
  const isFriendly = f.code === "friendly" || (f.comp||"").toLowerCase().includes("friendly");
  if (isFriendly) {
    return `<div class="int-break" style="background:linear-gradient(135deg, #1a2e1a, #162a16);border-color:#2a4a2a">
      <h3 style="color:#35e08a">🤝 Friendly — experimentation time</h3>
      <p style="color:#8ab88a">Real teams rotate heavily in friendlies. Expect youth, reserves, low intensity. Perfect to test tactics and give minutes to fringe players without risking injuries in competitive games.</p>
    </div>`;
  }
  if (rivalry) {
    return `<div class="derby-banner">🔥 ${esc(rivalry.name.toUpperCase())} — THIS IS MORE THAN 3 POINTS 🔥</div>
    <div class="press-hype">
      <h4>🎤 Press conference — derby hype building</h4>
      <p>"The atmosphere will be electric. ${esc(f.home)} vs ${esc(f.away)} is not just a game, it's pride, history, bragging rights for months. The board expects passion, the fans demand a result."</p>
      <div class="press-actions">
        <button class="btn sm" onclick="press('confident')">“We’ll crush them” 🔥</button>
        <button class="btn sm" onclick="press('balanced')">“Respect, but we want to win” 🤝</button>
        <button class="btn sm" onclick="press('defensive')">“Focus on our game” 🧘</button>
      </div>
    </div>`;
  }
  if (isBig) {
    const quotes = [
      `“Big game under the lights. ${esc(f.home)} vs ${esc(f.away)} — this is why we love football.”`,
      `“Pressure? What pressure? These are the games you live for.”`,
      `“The fans have been talking about this all week. Time to deliver.”`
    ];
    return `<div class="press-hype">
      <h4>🎤 Matchday hype — the build-up</h4>
      <p>${esc(quotes[Math.floor(Math.random()*quotes.length)])}</p>
      <div class="press-actions">
        <button class="btn sm" onclick="press('confident')">Back the boys 💪</button>
        <button class="btn sm" onclick="press('balanced')">Stay grounded ⚖️</button>
      </div>
    </div>`;
  }
  return "";
}

/* GAME HUD helpers */
function gaugeSVG(value, max, color, label, icon) {
  const pct = Math.max(0, Math.min(1, value / max));
  const circ = 2 * Math.PI * 34;
  const dash = circ * pct;
  return `<div style="text-align:center;flex:1"><div style="position:relative;width:76px;height:76px;margin:0 auto"><svg viewBox="0 0 80 80" style="width:100%;height:100%;transform:rotate(-90deg)"><circle cx="40" cy="40" r="34" fill="none" stroke="rgba(255,255,255,.08)" stroke-width="6"/><circle cx="40" cy="40" r="34" fill="none" stroke="${color}" stroke-width="6" stroke-linecap="round" stroke-dasharray="${dash} ${circ - dash}" style="filter:drop-shadow(0 0 6px ${color});transition:stroke-dasharray .9s cubic-bezier(.2,.9,.3,1.2)"/></svg><div style="position:absolute;inset:0;display:grid;place-items:center"><div><div style="font-size:18px">${icon}</div><div style="font-weight:900;font-size:15px;letter-spacing:-.02em">${Math.round(value)}${max===100?"":""}</div></div></div></div><div style="font-size:10px;letter-spacing:.12em;font-weight:800;color:var(--tx3);margin-top:6px">${label}</div></div>`;
}

async function renderHome() {
  await refreshState();
  const h = G.home;
  if (h.unemployed) return renderJobs();
  let adv = null;
  try { adv = await api.get("/api/advice"); } catch (e) {}
  const pos = h.position, f = h.next_fixture, ss = h.squad_summary;
  const ft = (ss.groups.find(g => g.squad === "First Team") || { n: 0 }).n;
  const pills = formPills(h.form, 6);
  const avail = Math.max(0, ft - ss.injured - ss.suspended - ss.unfit);
  const tbl = h.table || [];
  const mine = tbl.find(r => r.club_id === h.club.id);
  const top = tbl.slice(0, 5);
  const rowHtml = r => `<div style="display:flex;align-items:center;gap:8px;padding:8px 10px;border-radius:10px;${r.club_id === h.club.id ? "background:linear-gradient(90deg,rgba(53,224,138,.15),transparent);border:1px solid rgba(53,224,138,.2)" : "background:rgba(255,255,255,.03);border:1px solid transparent"}"><span style="font-size:11px;font-weight:800;min-width:18px;text-align:center;color:${r.club_id===h.club.id?"var(--acc)":"var(--tx3)"}">${r.pos||"–"}</span>${crest(r.code)}<span style="flex:1;font-weight:700;font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(r.name)}</span><span style="font-size:11px;color:var(--tx3)">${r.p}</span><b style="font-size:13px;min-width:22px;text-align:right">${r.pts}</b></div>`;
  const rivalry = f ? isRivalry(f.home_code, f.away_code) : null;
  const intBreak = (() => { try { const d = new Date(h.date); const m = d.getMonth(); if ([2,5,8,9,10].includes(m) && d.getDate() <= 14) return true; return false; } catch(e){ return false; } })();

  $("#content").innerHTML = `
    ${intBreak ? `<div style="margin-bottom:12px;padding:14px;border-radius:16px;background:linear-gradient(135deg,#1a2e1a,#162a16);border:1px solid #2a4a2a;box-shadow:0 8px 24px rgba(0,0,0,.3)"><div style="display:flex;align-items:center;gap:10px"><div style="width:40px;height:40px;border-radius:12px;background:rgba(53,224,138,.15);display:grid;place-items:center;font-size:20px">🌍</div><div style="flex:1"><b style="font-size:13px;color:#35e08a">International break — squad depleted</b><div class="small muted" style="font-size:11px;margin-top:2px">Youth & reserves training with first team. Prime scouting time.</div></div><button class="btn sm" style="border-radius:10px" onclick="go('squad')">Squad</button></div></div>` : ""}

    ${f ? `
      ${rivalry ? `<div style="margin-bottom:10px;padding:10px 14px;border-radius:14px;background:linear-gradient(90deg,#ff3b30,#ff6b35);color:white;font-weight:900;letter-spacing:.08em;font-size:12px;text-align:center;box-shadow:0 6px 20px rgba(255,59,48,.4);animation:shimmer 2s infinite">🔥 ${esc(rivalry.name.toUpperCase())} — DERBY — BRAGGING RIGHTS 🔥</div>` : ""}
      <div style="position:relative;border-radius:20px;overflow:hidden;background:linear-gradient(165deg,#151a27,#10131a);border:1px solid var(--line2);box-shadow:0 16px 48px rgba(0,0,0,.4),inset 0 1px 0 rgba(255,255,255,.08)">
        <div style="position:absolute;top:0;left:0;right:0;height:2px;background:linear-gradient(90deg,${compColor(f.code)},var(--acc2))"></div>
        <div style="padding:10px 14px;display:flex;align-items:center;gap:8px;background:linear-gradient(90deg,rgba(0,0,0,.25),transparent);border-bottom:1px solid var(--line2)">${compLogo(f.code)}<span style="font-size:11px;letter-spacing:.12em;font-weight:800;color:var(--tx2)">${esc(compLabel(f))}${f.stage && f.stage!=="league"?" · "+esc(f.stage):""}</span><span class="spacer"></span><span style="font-size:11px;color:var(--tx3)">${fmtDate(f.date)}</span></div>
        <div style="padding:16px 14px;display:grid;grid-template-columns:1fr auto 1fr;gap:12px;align-items:center">
          <div style="text-align:center"><div style="width:64px;height:64px;margin:0 auto 8px;border-radius:18px;background:linear-gradient(135deg,#1a2132,#151a27);border:1px solid rgba(255,255,255,.08);display:grid;place-items:center;box-shadow:0 6px 18px rgba(0,0,0,.3)">${crest(f.home_code,"xl")}</div><div style="font-weight:900;font-size:13px;letter-spacing:-.02em">${esc(f.home)}</div><div style="font-size:10px;color:var(--tx3);margin-top:2px">${f.is_home?"HOME":"AWAY"}</div><div style="margin-top:6px;display:flex;justify-content:center;gap:3px">${formPills(f.is_home?(G.home.form||[]):[],3)}</div></div>
          <div style="text-align:center"><div style="width:48px;height:48px;border-radius:50%;background:linear-gradient(135deg,var(--acc),var(--acc2));display:grid;place-items:center;font-weight:900;font-size:14px;color:#06120c;box-shadow:0 6px 18px rgba(53,224,138,.4)">VS</div><div style="font-size:11px;font-weight:800;letter-spacing:.12em;color:var(--tx3);margin-top:8px">${f.is_home?"AT HOME":"AWAY"}</div><div style="font-size:10px;color:var(--tx3);margin-top:2px;max-width:100px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(f.venue||"")}</div></div>
          <div style="text-align:center"><div style="width:64px;height:64px;margin:0 auto 8px;border-radius:18px;background:linear-gradient(135deg,#1a2132,#151a27);border:1px solid rgba(255,255,255,.08);display:grid;place-items:center;box-shadow:0 6px 18px rgba(0,0,0,.3)">${crest(f.away_code,"xl")}</div><div style="font-weight:900;font-size:13px;letter-spacing:-.02em">${esc(f.away)}</div><div style="font-size:10px;color:var(--tx3);margin-top:2px">${!f.is_home?"HOME":"AWAY"}</div><div style="margin-top:6px;display:flex;justify-content:center;gap:3px">${formPills(!f.is_home?(G.home.form||[]):[],3)}</div></div>
        </div>
        <div style="padding:0 12px 12px;display:flex;gap:8px">
          <button class="btn primary" style="flex:1;min-height:48px;border-radius:14px;font-size:14px;box-shadow:0 8px 24px rgba(53,224,138,.35)" onclick="Juice.haptic('heavy');go('match')">▶ MATCH CENTRE</button>
          <button class="btn" style="min-height:48px;border-radius:14px;min-width:54px" onclick="Juice.haptic('medium');quickPlay()">⚡</button>
        </div>
      </div>
      <div style="margin-top:10px">${pressHypeForFixture(f)}</div>
    ` : `<div style="padding:24px;border-radius:20px;background:linear-gradient(165deg,#151a27,#10131a);border:1px solid var(--line2);text-align:center"><div style="font-size:32px">🏁</div><h3 style="margin:8px 0 4px">Season complete</h3><p class="small muted">No fixtures left — continue for awards & new season.</p><button class="btn primary sm" style="margin-top:10px;border-radius:12px" onclick="doContinue()">Continue ▸</button></div>`}

    <!-- MANAGER OFFICE HUD — circular gauges like a game -->
    <div style="margin-top:14px;padding:14px;border-radius:20px;background:linear-gradient(165deg,#151a27,#10131a);border:1px solid var(--line2);box-shadow:var(--shadow-float)">
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px"><b style="font-size:13px;letter-spacing:.06em">MANAGER OFFICE</b><span style="font-size:10px;letter-spacing:.14em;color:var(--tx3);font-weight:800">SEASON ${G.home.season_label}</span></div>
      <div style="display:flex;gap:6px;justify-content:space-around">
        ${gaugeSVG(pos?pos.pos:10, pos?pos.size:20, pos && pos.pos<=4 ? "#35e08a" : pos && pos.pos>= (pos?pos.size:20)-2 ? "#ff5d6b" : "#5a9eff", "POSITION", "📊")}
        ${gaugeSVG(h.board.confidence, 100, h.board.confidence<30?"#ff5d6b":h.board.confidence<55?"#ffb454":"#35e08a", "BOARD", "🏛️")}
        ${gaugeSVG(h.fans.sentiment, 100, h.fans.sentiment<30?"#ff5d6b":"#ffb454", "FANS", "🔥")}
        ${gaugeSVG(avail, ft||22, avail<12?"#ff5d6b":avail<16?"#ffb454":"#35e08a", "FIT", "🩺")}
      </div>
      <div style="margin-top:12px;display:grid;grid-template-columns:repeat(3,1fr);gap:8px">
        <div style="padding:10px;border-radius:12px;background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.06);text-align:center"><div style="font-size:11px;color:var(--tx3);font-weight:700;letter-spacing:.08em">POINTS</div><div style="font-weight:900;font-size:18px;margin-top:2px">${pos?pos.pts:0}<span style="font-size:11px;color:var(--tx3);font-weight:700"> · ${pos&&pos.gd? (pos.gd>0?"+":"")+pos.gd+" GD":""}</span></div></div>
        <div style="padding:10px;border-radius:12px;background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.06);text-align:center"><div style="font-size:11px;color:var(--tx3);font-weight:700;letter-spacing:.08em">FORM</div><div style="margin-top:4px;display:flex;justify-content:center;gap:3px">${pills||"<span class='small muted'>—</span>"}</div></div>
        <div style="padding:10px;border-radius:12px;background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.06);text-align:center"><div style="font-size:11px;color:var(--tx3);font-weight:700;letter-spacing:.08em">CASH</div><div style="font-weight:900;font-size:14px;margin-top:2px;color:var(--acc)">${money(h.finances.cash)}</div></div>
      </div>
    </div>

    <!-- Quick actions — game cards -->
    <div style="margin-top:12px;display:grid;grid-template-columns:1fr 1fr;gap:10px">
      <button onclick="Juice.haptic('tap');go('squad')" style="text-align:left;padding:14px;border-radius:16px;background:linear-gradient(165deg,#1b2334,#151a27);border:1px solid rgba(255,255,255,.08);color:var(--tx);box-shadow:0 8px 24px rgba(0,0,0,.25)"><div style="display:flex;align-items:center;gap:10px"><div style="width:40px;height:40px;border-radius:12px;background:linear-gradient(135deg,#1e3a5f,#162a45);display:grid;place-items:center;font-size:18px">🩺</div><div style="flex:1"><div style="font-weight:800;font-size:13px">Squad</div><div style="font-size:11px;color:var(--tx3)">${avail} fit · ${ss.injured} injured · ${ss.suspended} banned</div></div><span style="opacity:.4">▸</span></div>${avail<14?`<div style="margin-top:8px;padding:6px 8px;border-radius:8px;background:rgba(255,93,107,.12);border:1px solid rgba(255,93,107,.18);font-size:11px;color:#ff8a94">⚠️ Thin squad — promote youth?</div>`:""}</button>
      <button onclick="Juice.haptic('tap');go('board')" style="text-align:left;padding:14px;border-radius:16px;background:linear-gradient(165deg,#1f2937,#151a27);border:1px solid rgba(255,255,255,.08);color:var(--tx);box-shadow:0 8px 24px rgba(0,0,0,.25)"><div style="display:flex;align-items:center;gap:10px"><div style="width:40px;height:40px;border-radius:12px;background:${h.board.warning?"linear-gradient(135deg,#3d1a1e,#2a1214)":"linear-gradient(135deg,#1a2e1a,#162a16)"};display:grid;place-items:center;font-size:18px">${h.board.warning?"⚠️":"🏛️"}</div><div style="flex:1"><div style="font-weight:800;font-size:13px">Board</div><div style="font-size:11px;color:var(--tx3)">${h.board.objectives[0]?esc(h.board.objectives[0].text).slice(0,36):"Stable"}</div></div><span style="opacity:.4">▸</span></div><div style="margin-top:8px;display:flex;gap:6px"><span style="font-size:10px;padding:3px 8px;border-radius:999px;background:${h.board.warning?"rgba(255,93,107,.15)":"rgba(53,224,138,.12)"};color:${h.board.warning?"#ff8a94":"var(--acc)"};font-weight:800">${h.board.warning?"WARNING":"STABLE"}</span><span style="font-size:10px;color:var(--tx3)">${Math.round(h.board.confidence)}/100 confidence</span></div></button>
    </div>

    ${godCard(adv)}

    <div style="margin-top:12px;display:grid;grid-template-columns:1fr 1fr;gap:10px">
      <div style="padding:0;border-radius:16px;background:linear-gradient(165deg,#151a27,#10131a);border:1px solid var(--line2);overflow:hidden;box-shadow:var(--shadow-float)">
        <div style="padding:12px 14px 8px;display:flex;align-items:center;justify-content:space-between"><b style="font-size:12px;letter-spacing:.06em">📊 ${esc(h.club.league)}</b><button class="btn sm" style="border-radius:10px;font-size:11px" onclick="go('table')">Full ▸</button></div>
        <div style="padding:0 8px 8px;display:grid;gap:4px">${top.map(rowHtml).join("")}${mine && mine.pos>5 ? `<div style="text-align:center;padding:6px;font-size:10px;color:var(--tx3);letter-spacing:.1em">··· YOU ${mine.pos}TH ···</div>${rowHtml(mine)}`:""}</div>
      </div>
      <div style="padding:0;border-radius:16px;background:linear-gradient(165deg,#151a27,#10131a);border:1px solid var(--line2);overflow:hidden;box-shadow:var(--shadow-float)">
        <div style="padding:12px 14px 8px;display:flex;align-items:center;justify-content:space-between"><b style="font-size:12px;letter-spacing:.06em">📰 News</b><div style="display:flex;gap:6px;align-items:center">${h.unread?`<span style="min-width:18px;height:18px;padding:0 5px;border-radius:999px;background:#ff3b30;color:white;font-size:10px;font-weight:900;display:grid;place-items:center">${h.unread}</span>`:""}<button class="btn sm" style="border-radius:10px;font-size:11px" onclick="go('inbox')">Open ▸</button></div></div>
        <div id="home-inbox" style="padding:0 8px 8px;display:grid;gap:4px"></div>
      </div>
    </div>`;
  const ib = await api.get("/api/inbox");
  $("#home-inbox").innerHTML = ib.items.slice(0, 3).map(m => `
    <button onclick="Juice.haptic('tap');openMail(${m.id})" style="text-align:left;width:100%;padding:10px;border-radius:12px;background:${m.read?"rgba(255,255,255,.03)":"linear-gradient(90deg,rgba(53,224,138,.12),rgba(255,255,255,.03))"};border:1px solid ${m.read?"rgba(255,255,255,.06)":"rgba(53,224,138,.18)"};color:var(--tx);display:flex;gap:8px;align-items:flex-start">
      <span style="width:6px;height:6px;border-radius:50%;background:${m.priority==="URGENT"?"#ff3b30":m.priority==="IMPORTANT"?"#ffb454":"var(--acc)"};margin-top:6px;flex:none;box-shadow:0 0 8px ${m.priority==="URGENT"?"rgba(255,59,48,.6)":"rgba(53,224,138,.4)"};opacity:${m.read?".3":"1"}"></span>
      <span style="flex:1;min-width:0"><span style="font-weight:800;font-size:12px;display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(m.subject)}</span><span style="font-size:10px;color:var(--tx3)">${esc(m.cat)} · ${fmtDate(m.date).split(",")[0]}</span></span>
    </button>`).join("") || '<div style="padding:16px;text-align:center"><div class="small muted">Quiet day at the office ☕</div></div>';
}
function godCard(adv) {
  if (!adv || !adv.ok) return "";
  const items = adv.on ? (adv.items || []).map(it => `
    <div class="god-it">
      <span class="tag ${it.tag === "INBOX" || it.tag === "BOARD" ? "URGENT" : ""}">${esc(it.tag)}</span>
      <div style="flex:1"><b>${esc(it.t)}</b><div class="small muted">${esc(it.b)}</div></div>
      ${it.go ? `<button class="btn sm" onclick="go('${it.go}')">OPEN ▸</button>` : ""}
    </div>`).join("") :
    '<p class="small muted" style="margin:10px 0 2px">Off. You are on your own, boss — every decision yours, no whispers.</p>';
  return `
  <div class="card god ${adv.on ? "on" : ""}" style="margin-top:12px">
    <div class="row" style="align-items:center;gap:12px">
      <div class="god-m">GF</div>
      <div style="flex:1">
        <div class="stat-l" style="letter-spacing:.14em">GODFATHER MODE</div>
        <div class="small muted">Your consigliere reads the room and tells you exactly what to do next.</div>
      </div>
      <label class="sw"><input type="checkbox" ${adv.on ? "checked" : ""} onchange="toggleGod(this.checked)"><span></span></label>
    </div>
    ${adv.on ? `<div class="god-list">${items || '<p class="small muted" style="margin:10px 0 2px">Nothing needs you right now. Continue and let the world turn.</p>'}</div>${godPlan(adv.plan)}` : items}
  </div>`;
}

function godPlan(pl) {
  if (!pl) return "";
  const t = pl.tactics;
  return `
    <div class="god-plan">
      <div class="gp-b">
        <div class="gp-h">Best XI right now</div>
        <div class="gp-x">${(pl.xi_names || []).map(n => `<span>${esc(n)}</span>`).join("") || '<i class="muted">No fit players.</i>'}</div>
        <button class="btn sm primary" onclick="godXI()">Select this XI ▸</button>
      </div>
      ${t ? `<div class="gp-b">
        <div class="gp-h">Plan v ${esc((pl.opp || {}).name || "next opponent")}</div>
        <p class="small muted" style="margin:2px 0 8px">${esc(t.mentality)} · ${esc(t.formation)} — ${esc(t.why)}
          (our XI ${(pl.opp || {}).my || "?"} v their ${(pl.opp || {}).their || "?"})</p>
        <button class="btn sm primary" onclick="godTactics()">Apply tactic plan ▸</button>
      </div>` : ""}
      ${(pl.sign || []).length ? `<div class="gp-b">
        <div class="gp-h">Sign these players</div>
        ${pl.sign.map(g => `<div class="gp-s">
          <div style="flex:1;min-width:0"><b>${esc(g.name)}</b> <span class="muted small">${esc(g.pos)} · ${g.age}y · CA ${g.ca} / PA ${g.pa}</span>
            <div class="small muted">${esc(g.club)} · ~${money(g.value)} · ${esc(g.why)}</div></div>
          <button class="btn sm" onclick="go('player',${g.pid})">Profile</button>
          <button class="btn sm primary" onclick="godBid(${g.pid},${Math.round(g.value)},${Math.round(g.wage)})">Bid</button>
        </div>`).join("")}
      </div>` : ""}
    </div>`;
}
async function godXI() {
  const adv = await api.get("/api/advice");
  const ids = (adv.plan || {}).xi || [];
  if (!ids.length) return toast("No XI available.", 4000);
  const r = await api.post("/api/match/select", { ids });
  toast(r.ok ? "Godfather's XI selected — check the match centre." : (r.msg || "Selection failed"), 5000);
  if (r.ok) go("match");
}
async function godTactics() {
  const adv = await api.get("/api/advice");
  const t = (adv.plan || {}).tactics;
  if (!t) return toast("No tactic plan available.", 4000);
  const r = await api.post("/api/tactics", { mentality: t.mentality, instr: t.instr });
  toast(r.ok ? "Tactic plan applied: " + t.mentality : (r.msg || "Failed"), 5000);
  if (r.ok) renderHome();
}
async function godBid(pid, fee, wage) {
  const r = await api.post("/api/transfer/offer", { pid, fee, wage: Math.max(wage, 1), years: 3 });
  toast(r.ok ? "Offer sent. The club will respond." : (r.msg || r.error || "Offer refused"), 6000);
  if (r.ok) renderHome();
}
async function toggleGod(on) {
  await api.post("/api/godfather", { on });
  toast(on ? "Godfather mode: ON — he whispers, you decide." : "Godfather mode: off.");
  renderHome();
}
async function quickPlay() {
  await playMatch("instant");
}

/* -------------------------------------------------------------------- INBOX - PREMIUM NO MORE CLUNK */
let INBOX_CAT = "";
async function renderInbox() {
  await refreshState();
  const j = await api.get("/api/inbox" + (INBOX_CAT ? "?cat=" + INBOX_CAT : ""));
  const unread = j.items.filter(x => !x.read).length;
  const urgent = j.items.filter(x => x.priority === "URGENT" && !x.read).length;
  $("#content").innerHTML = `
    <div class="sec-h">
      <h3>News Centre</h3>
      <span class="spacer"></span>
      ${unread ? `<span class="tag NEW">${unread} new</span>` : ""}
      ${urgent ? `<span class="tag URGENT">${urgent} urgent</span>` : ""}
    </div>
    <div class="card tight" style="margin-bottom:12px;background:linear-gradient(135deg, #10131a, #171b26)">
      <div style="display:flex;align-items:center;gap:12px">
        <div style="width:40px;height:40px;border-radius:12px;background:linear-gradient(135deg, #1a2a4a, #16213e);display:grid;place-items:center;font-size:18px">📰</div>
        <div style="flex:1">
          <b style="font-size:14px">Stay in the loop</b>
          <div class="small muted">Tap any story to read the full briefing. Your assistant highlights what needs action.</div>
        </div>
        <button class="btn sm" onclick="markAllRead()">Mark all read</button>
      </div>
    </div>
    <div class="tabs">
      <button class="${!INBOX_CAT ? "active" : ""}" onclick="INBOX_CAT='';renderInbox()">All ${j.items.length ? `<span style="opacity:.6">(${j.items.length})</span>` : ""}</button>
      ${j.cats.map(c => `<button class="${INBOX_CAT === c ? "active" : ""}" onclick="INBOX_CAT='${c}';renderInbox()">${esc(c)}${j.unread_by_cat[c] ? ` <b style="color:var(--acc)">(${j.unread_by_cat[c]})</b>` : ""}</button>`).join("")}
    </div>
    <div class="card" style="padding:0;overflow:hidden">
      ${j.items.length ? j.items.map(m => {
        const isIntBreak = (m.cat||"").toLowerCase().includes("international") || (m.subject||"").toLowerCase().includes("international break");
        const isPress = (m.cat||"").toLowerCase().includes("media") || (m.subject||"").toLowerCase().includes("press");
        const icon = m.priority === "URGENT" ? "🚨" : m.priority === "IMPORTANT" ? "⚡" : isIntBreak ? "🌍" : isPress ? "🎤" : "📩";
        return `
        <button class="mrow p-${(m.priority || "").toLowerCase()} ${m.read ? "" : "unread"}" onclick="openMail(${m.id})" style="position:relative">
          <span class="mdot"></span>
          <div style="width:36px;height:36px;border-radius:10px;background:linear-gradient(135deg, ${m.priority === "URGENT" ? "#3d1a1e, #2a1214" : m.priority === "IMPORTANT" ? "#3a2c17, #2a1e0f" : "var(--sf3), var(--sf2)"});border:1px solid var(--line);display:grid;place-items:center;font-size:16px;flex:none">${icon}</div>
          <div class="mmain">
            <div class="msub">${esc(m.subject)}</div>
            <div style="font-size:12px;color:var(--tx2);margin-top:2px;line-height:1.4;display:-webkit-box;-webkit-line-clamp:1;-webkit-box-orient:vertical;overflow:hidden">${esc((m.body||"").slice(0,120))}</div>
            <div class="mmeta"><span class="mcat">${esc(m.cat)}</span><span>${fmtDate(m.date)}</span>${!m.read ? '<span class="tag NEW" style="font-size:9px;padding:2px 6px">NEW</span>' : ""}</div>
          </div>
          <span class="mpri">${esc(m.priority === "URGENT" ? "!" : m.priority === "IMPORTANT" ? "•" : "")}</span>
        </button>`;
      }).join("") : `
        <div class="inbox-empty">
          <div class="ie-icon">📭</div>
          <h3>All caught up</h3>
          <p>No new messages. The football world is quiet — for now. Continue to advance time and stories will appear.</p>
          <button class="btn sm primary" style="margin-top:14px" onclick="doContinue()">Continue world ▸</button>
        </div>`}
    </div>`;
}
async function markAllRead() { await api.post("/api/inbox/read", { all: true }); renderInbox(); refreshBadges(); toast("All messages marked as read ✓", 2000); }
async function openMail(id) {
  const j = await api.get("/api/inbox");
  const m = j.items.find(x => x.id === id);
  if (!m) return;
  await api.post("/api/inbox/read", { ids: [id] });
  const p = m.payload || {};
  const isIntBreak = (m.cat||"").toLowerCase().includes("international") || (m.subject||"").toLowerCase().includes("international break");
  const isDerby = (m.subject||"").toLowerCase().includes("derby") || (m.body||"").toLowerCase().includes("derby") || (m.body||"").toLowerCase().includes("rival");
  const extra = isIntBreak ? `
    <div class="int-break" style="margin-top:14px">
      <h3>🌍 International Break Briefing</h3>
      <p>Your players on international duty: check fitness on return. This is prime scouting time — other leagues continue and youth players get a chance. Use the break to arrange friendlies or rest the squad.</p>
      <div class="row" style="margin-top:10px">
        <button class="btn sm" onclick="closeModal();go('squad')">Check squad fitness</button>
        <button class="btn sm" onclick="closeModal();go('scouting')">Scout abroad</button>
      </div>
    </div>` : isDerby ? `
    <div class="derby-banner" style="margin-top:12px;border-radius:10px">🔥 DERBY DAY — BRAGGING RIGHTS ON THE LINE 🔥</div>
    <div class="press-hype" style="margin-top:10px">
      <h4>🎤 Press asks: How do you handle derby pressure?</h4>
      <p>"These games define seasons. Form goes out the window. The fans demand passion, but we need cool heads. One moment can make you a hero — or the villain."</p>
      <div class="press-actions">
        <button class="btn sm" onclick="press('confident');closeModal();">“We fear no one” 💪</button>
        <button class="btn sm" onclick="press('balanced');closeModal();">“Respect the rivalry” 🤝</button>
        <button class="btn sm" onclick="press('defensive');closeModal();">“Just another game” 😐</button>
      </div>
    </div>` : "";
  modal(`
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:12px">
      <span class="tag ${m.priority}">${esc(m.priority)}</span>
      <span class="tag">${esc(m.cat)}</span>
      <span class="spacer"></span>
      <span class="small muted">${fmtDate(m.date)}</span>
    </div>
    <h2 style="font-size:20px;line-height:1.25;margin-bottom:10px">${esc(m.subject)}</h2>
    <div class="pre" style="margin-top:10px;font-size:13.5px;line-height:1.65;background:linear-gradient(135deg, var(--sf), var(--sf2));border:1px solid var(--line2)">${esc(m.body)}</div>
    ${extra}
    <div class="row" style="margin-top:18px"><span class="spacer"></span>
      ${p.screen ? `<button class="btn" onclick="closeModal();go('${esc(p.screen)}'${p.pid ? ",'" + p.pid + "'" : ""})">Open ${esc(p.screen)} ▸</button>` : ""}
      <button class="btn primary" onclick="closeModal();renderInbox()">Done ✓</button></div>`, true);
  refreshBadges();
}

/* -------------------------------------------------------------------- SQUAD */
let SQUAD_FILTER = "First Team", SQUAD_SORT = "ca", SQUAD_Q = "";
function filterSquadList() {
  const q = (SQUAD_Q || "").toLowerCase();
  $$(".sq-list .sqr").forEach(r => {
    const nm = (r.querySelector(".sqr-n b") || {}).textContent || "";
    r.style.display = !q || nm.toLowerCase().includes(q) ? "" : "none";
  });
  $$(".sq-table tbody tr").forEach(r => {
    const nm = r.children[1] ? r.children[1].textContent : "";
    r.style.display = !q || nm.toLowerCase().includes(q) ? "" : "none";
  });
}
async function renderSquad() {
  await refreshState();
  const j = await api.get("/api/screen/squad");
  const players = j.players.filter(p => SQUAD_FILTER === "All" || p.squad === SQUAD_FILTER)
    .filter(p => !SQUAD_Q || p.name.toLowerCase().includes(SQUAD_Q.toLowerCase()));
  const groups = ["All", "First Team", "Reserve", "U21", "Youth"];
  const sortFn = {
    ca: (a, b) => b.ca - a.ca, pos: (a, b) => a.pos.localeCompare(b.pos) || b.ca - a.ca,
    age: (a, b) => a.age - b.age, value: (a, b) => b.value - a.value, wage: (a, b) => b.wage - a.wage,
    goals: (a, b) => b.goals - a.goals, condition: (a, b) => b.condition - a.condition,
    name: (a, b) => a.name.localeCompare(b.name)
  }[SQUAD_SORT];
  players.sort(sortFn);
  const all = j.players;
  const injured = all.filter(p => p.injured), susp = all.filter(p => p.suspended > 0);
  const unfit = all.filter(p => !p.injured && !p.suspended && p.condition < 0.9);
  const fit = all.filter(p => !p.injured && !p.suspended && p.condition >= 0.9);

  $("#content").innerHTML = `
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px"><b style="font-size:15px;letter-spacing:.04em">👕 DRESSING ROOM</b><span class="small muted">${G.home.club.name} · ${fit.length} fit · ${injured.length} injured</span></div>

    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:14px">
      <div style="padding:12px;border-radius:14px;background:linear-gradient(135deg,#1a2e1a,#162a16);border:1px solid #2a4a2a;text-align:center"><div style="font-weight:900;font-size:20px;color:#35e08a">${fit.length}</div><div style="font-size:10px;letter-spacing:.12em;color:#8ab88a;font-weight:800">FIT</div></div>
      <div style="padding:12px;border-radius:14px;background:linear-gradient(135deg,#3d1a1e,#2a1214);border:1px solid #5a2226;text-align:center"><div style="font-weight:900;font-size:20px;color:#ff5d6b">${injured.length}</div><div style="font-size:10px;letter-spacing:.12em;color:#ff8a94;font-weight:800">INJURED</div></div>
      <div style="padding:12px;border-radius:14px;background:linear-gradient(135deg,#3a2c17,#2a1e0f);border:1px solid #5a4222;text-align:center"><div style="font-weight:900;font-size:20px;color:#ffb454">${susp.length}</div><div style="font-size:10px;letter-spacing:.12em;color:#ffcc8a;font-weight:800">BANNED</div></div>
      <div style="padding:12px;border-radius:14px;background:linear-gradient(135deg,#1a2132,#151a27);border:1px solid var(--line2);text-align:center"><div style="font-weight:900;font-size:20px">${(all.reduce((a,b)=>a+b.age,0)/(all.length||1)).toFixed(1)}</div><div style="font-size:10px;letter-spacing:.12em;color:var(--tx3);font-weight:800">AVG AGE</div></div>
    </div>

    <div style="display:flex;gap:6px;overflow-x:auto;padding-bottom:8px;margin-bottom:10px;scrollbar-width:none">
      ${groups.map(g => `<button onclick="Juice.haptic('tap');SQUAD_FILTER='${g}';renderSquad()" style="flex:none;padding:8px 14px;border-radius:12px;font-weight:800;font-size:12px;letter-spacing:.02em;border:1px solid ${SQUAD_FILTER===g?"rgba(53,224,138,.4)":"rgba(255,255,255,.08)"};background:${SQUAD_FILTER===g?"linear-gradient(135deg,var(--acc),var(--acc2))":"rgba(255,255,255,.05)"};color:${SQUAD_FILTER===g?"#06120c":"var(--tx2)"}">${g}</button>`).join("")}
      <input id="sq-q" placeholder="Search…" value="${esc(SQUAD_Q||"")}" oninput="SQUAD_Q=this.value;filterSquadList()" style="flex:none;width:120px;min-height:36px;border-radius:12px;background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.1);color:var(--tx);padding:0 12px">
    </div>

    <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(158px,1fr));gap:10px">
      ${players.map(p => {
        const ini = p.name.split(" ").map(w=>w[0]).slice(0,2).join("").toUpperCase();
        const condColor = p.condition>1.02 ? "#35e08a" : p.condition<0.92 ? "#ff5d6b" : "#ffb454";
        const status = p.injured ? "INJ" : p.suspended ? "BAN" : p.condition<0.9 ? "UNFIT" : "FIT";
        const statusColor = p.injured ? "#ff5d6b" : p.suspended ? "#ffb454" : p.condition<0.9 ? "#ffb454" : "#35e08a";
        return `<button onclick="Juice.haptic('tap');go('player',${p.id})" style="text-align:left;padding:12px;border-radius:16px;background:linear-gradient(165deg,#1a2132,#151a27);border:1px solid ${p.listed?"rgba(255,93,107,.35)":"rgba(255,255,255,.08)"};color:var(--tx);position:relative;overflow:hidden;box-shadow:0 6px 20px rgba(0,0,0,.25);transition:transform .18s">
          <div style="position:absolute;top:0;left:0;right:0;height:2px;background:${condColor}"></div>
          <div style="display:flex;align-items:flex-start;gap:10px">
            <div style="width:44px;height:44px;border-radius:12px;background:linear-gradient(135deg,#242d44,#1a2132);border:1px solid rgba(255,255,255,.08);display:grid;place-items:center;font-weight:900;font-size:13px">${ini}</div>
            <div style="flex:1;min-width:0"><div style="font-weight:900;font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(p.name)}</div><div style="display:flex;gap:4px;margin-top:3px"><span style="font-size:10px;padding:2px 6px;border-radius:6px;background:rgba(255,255,255,.08);font-weight:800">${esc(p.pos)}</span><span style="font-size:10px;padding:2px 6px;border-radius:6px;background:${statusColor}20;color:${statusColor};font-weight:800">${status}</span></div></div>
            <div style="text-align:right"><div style="font-weight:900;font-size:13px;color:${condColor}">${p.ca.toFixed(1)}</div><div style="font-size:10px;color:var(--tx3)">${p.age}y</div></div>
          </div>
          <div style="margin-top:10px;display:flex;justify-content:space-between;align-items:center"><span style="font-size:11px;color:var(--tx3)">${stars(p.stars)} · ${money(p.value)}</span><span style="font-size:10px;padding:3px 8px;border-radius:999px;background:rgba(255,255,255,.06);font-weight:700">${p.goals}G ${p.assists}A</span></div>
          ${p.listed?`<div style="margin-top:8px;padding:4px 8px;border-radius:8px;background:rgba(255,93,107,.12);border:1px solid rgba(255,93,107,.18);font-size:10px;font-weight:800;color:#ff8a94;text-align:center">💸 LISTED</div>`:""}
        </button>`;
      }).join("")}
    </div>

    ${injured.length||susp.length?`<div style="margin-top:14px;padding:12px;border-radius:14px;background:linear-gradient(135deg,#1a1a2e,#16213e);border:1px solid #0f3460"><b style="font-size:12px">🩺 Physio room</b><div style="margin-top:8px;display:grid;gap:6px">${injured.map(p=>`<div style="display:flex;justify-content:space-between;font-size:12px"><span style="color:#ff8a94">${esc(p.name)}</span><span class="small muted">${esc(p.injury)} · ${p.return_date?fmtDate(p.return_date):"—"}</span></div>`).join("")}${susp.map(p=>`<div style="display:flex;justify-content:space-between;font-size:12px"><span style="color:#ffcc8a">${esc(p.name)}</span><span class="small muted">suspended ${p.suspended}</span></div>`).join("")}</div></div>`:""}
  `;
}

/* ------------------------------------------------------------------- PLAYER */
async function renderPlayer(pid) {
  const p = await api.get("/api/player/" + pid);
  await refreshState();
  const groups = p.attr_groups || null;
  const ini = String(p.name).split(/\s+/).map(w => w[0]).slice(0, 2).join("").toUpperCase();
  const ratingCls = r => r >= 7.5 ? "good" : r >= 6.8 ? "" : r >= 6.2 ? "warn" : "bad";
  $("#content").innerHTML = `
    <div class="card tight">
      <div class="p-head">
        <div class="p-ava">${ini}</div>
        <div style="min-width:0;flex:1">
          <h2 style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(p.name)}</h2>
          <p class="small muted" style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">
            ${esc(p.club)} · ${esc(p.nat)} · ${p.age}y · ${esc(p.foot)} · ${p.height}cm</p>
        </div>
        <span class="pos">${esc(p.pos)}</span>${p.pos2 ? `<span class="pos" style="opacity:.6">${esc(p.pos2)}</span>` : ""}
      </div>
      <div class="strip" style="margin:12px -10px -10px;border-radius:0;border-left:0;border-right:0;border-bottom:0">
        <div class="st"><span class="st-l">Ability</span><span class="st-v">${p.ca != null ? p.ca.toFixed(1) : "?"}</span>
          ${p.stars != null ? `<div class="small">${stars(p.stars)}</div>` : '<div class="small muted">unscouted</div>'}</div>
        <div class="st"><span class="st-l">Potential</span><span class="st-v">${p.pa != null ? p.pa.toFixed(1) : "?"}</span>
          <div class="small muted">${p.age < 24 ? "developing" : p.age > 30 ? "declining" : "peak"}</div></div>
        <div class="st"><span class="st-l">Condition</span><span class="st-v">${p.condition.toFixed(2)}</span>
          <div class="small muted">fit ${Math.round(p.fitness)}</div></div>
        <div class="st"><span class="st-l">Form</span><span class="st-v ${p.form > 0.5 ? "good" : p.form < -0.5 ? "bad" : ""}">${p.form > 0 ? "+" : ""}${p.form.toFixed(1)}</span>
          <div class="small muted">morale ${Math.round(p.morale)}</div></div>
        <div class="st"><span class="st-l">Value</span><span class="st-v small" style="font-size:14px">${money(p.value)}</span>
          <div class="small muted">${wk(p.wage)}</div></div>
      </div>
    </div>
    ${p.injury ? `<div class="card tight" style="margin-top:10px;border-color:#5b2b2b"><b class="bad">Injured:</b> <span class="small">${esc(p.injury)} — back ${fmtDate(p.return_date)}</span></div>` : ""}
    ${p.suspended ? `<div class="card tight" style="margin-top:10px;border-color:#6b5522"><b class="warn">Suspended</b> <span class="small">${p.suspended} match(es)</span></div>` : ""}

    ${groups ? `<div class="card tight" style="margin-top:10px">
      <div class="sec-h"><h3>Attributes</h3></div>
      ${Object.entries(groups).filter(([g, a]) => a.length).map(([g, a]) => `<div class="attr-g">
        <h4>${esc(g)}</h4>
        ${a.map(x => `<div class="attr-r"><span class="k">${esc(x.k.replace(/_/g, " "))}</span>
          <span class="b"><i style="width:${Math.min(100, x.v / 20 * 100)}%;background:${x.c === "good" || x.v >= 15 ? "var(--acc)" : x.v >= 11 ? "var(--blue)" : x.v >= 8 ? "var(--amber)" : "var(--red)"}"></i></span>
          <span class="v">${x.v}</span></div>`).join("")}</div>`).join("")}
    </div>` : (p.scout ? `<div class="card tight" style="margin-top:10px"><div class="sec-h"><h3>Scout report</h3><span class="spacer"></span><span class="small muted">${p.known}% known</span></div>
        <div class="pre">${esc(typeof p.scout === "string" ? p.scout : JSON.stringify(p.scout, null, 2))}</div></div>`
      : `<div class="card tight" style="margin-top:10px"><div class="sec-h"><h3>Scouting</h3></div>
        <p class="small muted">Knowledge of this player: ${p.known}%. Attributes stay hidden until scouted.</p>
        <button class="btn sm" style="margin-top:8px" onclick="assignScout(${p.id})">Assign scout</button></div>`)}

    <div class="grid g2" style="margin-top:10px">
      <div class="card tight">
        <div class="sec-h"><h3>Season record</h3></div>
        <div class="kv"><span>Apps · mins</span><b>${p.apps} · ${p.minutes}</b></div>
        <div class="kv"><span>Goals · assists</span><b>${p.goals} · ${p.assists}</b></div>
        <div class="kv"><span>Yellow · red</span><b>${p.yellow} · ${p.red}</b></div>
        <div class="kv"><span>Avg rating</span><b>${p.avg_rating ? p.avg_rating.toFixed(2) : "—"}</b></div>
        <div class="kv"><span>Intl caps</span><b>${p.int_apps} (${p.int_goals}g)</b></div>
      </div>
      <div class="card tight">
        <div class="sec-h"><h3>Recent performances</h3></div>
        ${(p.recent || []).length ? (p.recent || []).map(r => `<div class="kv">
            <span style="min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${fmtDate(r.date)} · ${r.home ? "v" : "@"} ${esc(r.opp)} <i class="muted small">${r.score}</i></span>
            <b class="${ratingCls(r.rating)}">${r.rating.toFixed(2)} <i class="muted small" style="font-style:normal">${r.mins}'${r.goals ? " · " + r.goals + "g" : ""}${r.assists ? " · " + r.assists + "a" : ""}</i></b>
          </div>`).join("") : '<p class="muted small">No matches yet this season.</p>'}
      </div>
    </div>

    ${p.mine ? `
      <div class="grid g2" style="margin-top:10px">
        <div class="card tight" style="background:linear-gradient(135deg, var(--sf), var(--sf2))">
          <div class="sec-h"><h3>📝 Contract & value</h3><span class="spacer"></span><span class="tag" style="font-size:11px">${money(p.value)} market value</span></div>
          <div class="kv"><span>Wage</span><b>${wk(p.wage)}</b></div>
          <div class="kv"><span>Expires</span><b>${esc(p.contract_end)} ${(() => { try { const y = parseInt((p.contract_end||"").slice(0,4)); return y ? `· ${y-2026}y left` : ""; } catch(e){ return ""; } })()}</b></div>
          <div class="kv"><span>Promise</span><b>${esc(p.promise)}</b></div>
          <div class="kv"><span>Happiness</span><b>${Math.round(p.happiness)} ${p.happiness < 30 ? "😡 wants out" : p.happiness > 80 ? "😊 happy" : "😐 ok"}</b></div>
          <div class="kv"><span>Status</span><b>${p.listed ? '<span class="tag URGENT">💸 LISTED FOR SALE</span>' : '<span class="tag ROUTINE">Not for sale</span>'}</b></div>
          <div style="margin-top:14px;display:grid;gap:8px">
            <div class="row" style="gap:8px">
              <button class="btn sm" style="flex:1" onclick="renewTalk(${p.id},'${esc(p.name).replace(/'/g, "\\'")}',${p.wage})">📝 New contract</button>
              <button class="btn sm ${p.listed ? "" : "primary"}" style="flex:1" onclick="${p.listed ? `toggleList(${p.id},false)` : `quickSell(${p.id},'${esc(p.name).replace(/'/g, "\\'")}')`}">${p.listed ? "❌ Unlist" : "💸 Sell player — one tap"}</button>
            </div>
            <div class="row" style="gap:8px">
              <button class="btn sm" style="flex:1" onclick="openPromise(${p.id},'${esc(p.name).replace(/'/g, "\\'")}','${esc(p.promise)}')">⏱️ Playing time</button>
              <button class="btn sm danger" style="flex:1" onclick="releasePlayer(${p.id},'${esc(p.name).replace(/'/g, "\\'")}')">Release 🗑️</button>
            </div>
          </div>
          <div class="small muted" style="margin-top:10px;background:var(--sf2);padding:8px 10px;border-radius:8px">💡 Selling is now easy: one tap lists player, clubs bid automatically. Set asking price and watch offers come in.</div>
        </div>
        <div class="card tight">
          <div class="sec-h"><h3>💬 Man-management</h3></div>
          <p class="small muted">Morale ${Math.round(p.morale)} · happiness ${Math.round(p.happiness)} · ${esc(p.personality)} · loyalty ${p.loyalty||"?"} · ambition ${p.ambition||"?"}</p>
          <div class="row" style="margin-top:12px;gap:8px">
            <button class="btn sm" onclick="talkTo(${p.id},'praise')">👍 Praise</button>
            <button class="btn sm" onclick="talkTo(${p.id},'criticise')">👎 Criticise</button>
            <button class="btn sm" onclick="talkTo(${p.id},'chat')">💬 Chat</button>
          </div>
          <div class="card tight" style="margin-top:12px;background:linear-gradient(135deg, #1a1a2e, #16213e);border-color:#0f3460">
            <div class="small" style="color:#7fb2ff;font-weight:700">🎯 Transfer realism</div>
            <div class="small muted" style="margin-top:4px;line-height:1.5">Players consider: club reputation gap, wage rise, rivalry (won't join rivals), loyalty (stars stay), ambition. Haaland won't join United from City — superstars have loyalty 14+ and refuse smaller clubs.</div>
          </div>
        </div>
      </div>` : `<div class="card tight" style="margin-top:10px;background:linear-gradient(135deg, var(--sf), var(--sf2))">
        <div class="sec-h"><h3>💸 Make an offer</h3><span class="spacer"></span><span class="tag gold">Asking ${money(p.asking || 0)}</span></div>
        <p class="small muted">Realistic negotiation: rivalry blocks (won't sell to rivals), superstar protection (CA 18.5+ at rep 85+ clubs), loyalty matters, contract length affects price.</p>
        <div class="row" style="margin-top:12px">
          <button class="btn primary" style="flex:1;min-height:48px" onclick="openOffer(${p.id},'${esc(p.name).replace(/'/g, "\\'")}',${p.asking || 0},${p.wage || 0})">💸 Bid ${money(p.asking || 0)} — realistic negotiation</button>
          <button class="btn sm" onclick="toggleShortlist(${p.id})">☆ Shortlist</button>
        </div>
      </div>`}
    <div class="row" style="margin-top:10px"><button class="btn sm" onclick="go('squad')">◂ Squad</button></div>`;
}
async function talkTo(pid, kind) {
  const r = await api.post("/api/squad/talk", { pid, kind });
  toast(esc(r.msg || "Done")); go("player", pid);
}
async function openPromise(pid, name, cur) {
  const opts = G.static.promises;
  modal(`<h2>Playing time — ${esc(name)}</h2>
    <p class="small muted">Current promise: <b>${esc(cur)}</b>. Promises affect morale, happiness and how players react when they are not selected. Breaking one damages trust.</p>
    <div class="row" style="margin-top:10px">
      ${opts.map(o => `<button class="btn" onclick="setPromise(${pid},'${esc(o)}')">${esc(o)}</button>`).join("")}
    </div>
    <div class="row" style="margin-top:14px"><span class="spacer"></span><button class="btn" onclick="closeModal()">Cancel</button></div>`);
}
async function setPromise(pid, promise) {
  const r = await api.post("/api/squad/promise", { pid, promise });
  closeModal(); toast(esc(r.msg || "Promise updated")); go("player", pid);
}
async function renewTalk(pid, name, wage) {
  const w = prompt(`New weekly wage for ${name} (current €${wage}k/week):`, Math.round(wage * 1.15));
  if (!w) return;
  const y = prompt("Contract length in years:", "2"); if (!y) return;
  const promise = prompt("Playing-time promise:", "Regular Starter"); if (!promise) return;
  const r = await api.post("/api/contract/renew", { pid, wage: +w, years: +y, promise });
  toast(esc(r.msg || (r.ok ? "Contract agreed" : "Negotiation failed")), 5000); go("player", pid);
}
async function toggleList(pid, listed) { const r = await api.post("/api/squad/list", { pid, listed }); toast(esc(r.msg || "Done")); go("player", pid); }
async function releasePlayer(pid, name) {
  if (!confirm(`Release ${name}? He will leave immediately and become a free agent.`)) return;
  const r = await api.post("/api/squad/release", { pid }); toast(esc(r.msg || "Released")); go("squad");
}
async function assignScout(pid) { const r = await api.post("/api/scout/assign", { pid }); toast(esc(r.msg || "Scout assigned")); }

/* ------------------------------------------------------------------ TACTICS */
const POS_COORDS = {
  GK: [50, 92], DC: [35, 74], DL: [14, 70], DR: [86, 70], DM: [50, 60], MC: [38, 48],
  AMC: [50, 36], AML: [14, 38], AMR: [86, 38], ST: [50, 18]
};
function pitchHTML(xi, clickable) {
  const byPos = {};
  xi.forEach((x, i) => (byPos[x.pos] = byPos[x.pos] || []).push(i));
  return `<div class="pitch"><div class="lines"></div>${xi.map((x, i) => {
    const c = POS_COORDS[x.pos] || [50, 50];
    const off = byPos[x.pos].indexOf(i) - (byPos[x.pos].length - 1) / 2;
    const left = Math.max(6, Math.min(94, c[0] + off * 19));
    const p = x.player;
    return `<div class="slot ${p ? "" : "empty"}" style="left:${left}%;top:${c[1]}%"
      ${clickable ? `onclick="pickSlot(${i},'${x.pos}')"` : ""}>
      <div class="dot">${esc(x.pos)}</div>
      <div class="nm">${p ? esc(p.name.split(" ").slice(-1)[0]) + " " + p.ca.toFixed(1) : "empty"}</div>
      ${p ? `<div class="nm muted" style="font-size:9.5px">${Math.round(p.condition * 100)}%${p.injured ? " INJ" : ""}${p.suspended ? " SUS" : ""}</div>` : ""}
      ${p && x.role ? `<div class="nm muted" style="font-size:9px">${esc(x.role.split(" ").map(w => w[0]).join(""))} ${esc(x.duty || "")}${x.auto ? " ·auto" : ""}</div>` : ""}
    </div>`;
  }).join("")}</div>`;
}
const MENTALITY_NOTE = {
  "Very Defensive": "Deep block, low line, counter-attacks only — concedes little, creates little.",
  "Defensive": "Compact and cautious: fewer chances at both ends, protects leads.",
  "Cautious": "Slightly reserved: solid shape, measured build-up.",
  "Balanced": "Even risk: neither suppresses nor boosts chance quality.",
  "Positive": "Higher line and tempo: more chances created and conceded.",
  "Attacking": "Commits bodies forward: clear scoring edge, exposure at the back.",
  "All-Out Attack": "Everything forward: maximum chance volume, fragile defensively.",
};
async function renderTactics() {
  const t = await api.get("/api/screen/tactics");
  await refreshState();
  if (t.error) { $("#content").innerHTML = `<h1>Tactics</h1><p class="muted">${esc(t.error)}</p>`; return; }
  window._tactics = t;
  const IOPT = G.static.instruction_options || {};
  const instr = t.tactic.instr || {};
  $("#content").innerHTML = `
    <div class="sec-h"><h3>Tactics</h3></div>
    <p class="sub">Familiarity <b>${Math.round(t.tactic.familiarity)}%</b> · attack ${t.rating.attack} ·
      defence ${t.rating.defence} · condition ${t.rating.condition} · press ${t.rating.press} ·
      tempo ${t.rating.tempo} · width ${t.rating.width}</p>
    <div class="grid" style="grid-template-columns:1.1fr .9fr;gap:12px">
      <div>
        <div class="card">
          <h3>Shape & mentality</h3>
          <div class="row">
            <select id="tac-formation" onchange="changeFormation(this.value)">
              ${G.static.formations.map(f => `<option ${f === t.tactic.formation ? "selected" : ""}>${f}</option>`).join("")}
            </select>
            <select id="tac-mentality" onchange="saveTactics()">
              ${G.static.mentalities.map(m => `<option ${m === t.tactic.mentality ? "selected" : ""}>${m}</option>`).join("")}
            </select>
            <span class="spacer"></span>
            <button class="btn sm" onclick="autoPickXI()">Assistant picks XI</button>
          </div>
          <div class="small" style="margin-top:6px;color:var(--acc)">${MENTALITY_NOTE[t.tactic.mentality] || ""}</div>
          <div class="small muted" style="margin-top:4px">Changing shape or mentality costs familiarity — the team needs matches to learn it.
            Slots marked <b>auto</b> are the assistant's pick: click any slot on the pitch to choose your own XI.</div>
        </div>
        ${pitchHTML(t.xi, true)}
        <div class="card tight"><h3>Bench <span class="muted small">(click to fill an empty slot)</span></h3>
          <div class="row">${t.bench.map(b => `<button class="btn sm" onclick="swapIn(${b.id})"
            title="${esc(b.name)} · CA ${b.ca} · ${esc(b.pos)}">${esc(b.name.split(" ").slice(-1)[0])}
            <span class="muted">${esc(b.pos)} ${b.ca.toFixed(1)}</span></button>`).join("")}</div>
        </div>
      </div>
      <div>
        <div class="card"><h3>Roles & duties</h3>
          ${t.xi.map((x, i) => `
            <div class="row" style="margin-bottom:4px">
              <div style="width:40px"><span class="pos">${esc(x.pos)}</span></div>
              <div style="flex:1" class="small">${x.player ? esc(x.player.name) : '<span class="muted">empty</span>'}</div>
              <select data-slot="${i}" data-kind="role" class="rd-sel" style="width:150px" onchange="saveTactics()">
                ${(G.static.roles[x.pos] || []).map(r => `<option ${x.role === r ? "selected" : ""}>${r}</option>`).join("")}
              </select>
              <select data-slot="${i}" data-kind="duty" class="rd-sel" style="width:88px" onchange="saveTactics()">
                ${(G.static.duties[x.pos] || []).map(d => `<option ${x.duty === d ? "selected" : ""}>${d}</option>`).join("")}
              </select>
            </div>`).join("")}
        </div>
        <div class="card" style="margin-top:12px"><h3>Team instructions</h3>
          ${Object.keys(IOPT).map(k => {
            const opts = IOPT[k] || [];
            const cur = instr[k];
            const label = k.replace(/_/g, " ");
            if (opts.length === 2 && (opts[0] === false || opts[0] === true))
              return `<div class="row" style="margin-bottom:5px">
                <div style="flex:1" class="small">${esc(label)}</div>
                <label class="row" style="margin:0"><input type="checkbox" data-i="${k}" class="instr-c"
                  ${cur ? "checked" : ""} onchange="saveTactics()"> on</label></div>`;
            return `<div class="row" style="margin-bottom:5px">
              <div style="width:140px" class="small">${esc(label)}</div>
              <select data-i="${k}" class="instr-s" style="flex:1" onchange="saveTactics()">
                ${opts.map(o => `<option ${cur === o ? "selected" : ""}>${o}</option>`).join("")}
              </select></div>`;
          }).join("")}
          <div class="row" style="margin-top:8px"><button class="btn sm" onclick="resetInstructions()">Reset to default</button></div>
        </div>
      </div>
    </div>`;
}
async function changeFormation(f) { const r = await saveTactics({ formation: f }); if (r && r.msg) toast(esc(r.msg)); renderTactics(); }
async function resetInstructions() { const r = await saveTactics({ reset_instr: true }); if (r && r.msg) toast(esc(r.msg)); renderTactics(); }
async function saveTactics(extra) {
  const t = window._tactics || {};
  const roles = {};
  $$(".rd-sel").forEach(s => {
    const i = s.dataset.slot;
    roles[i] = roles[i] || [(t.xi[i] || {}).role, (t.xi[i] || {}).duty];
    roles[i][s.dataset.kind === "role" ? 0 : 1] = s.value;
  });
  const instr = {};
  $$(".instr-s").forEach(i => instr[i.dataset.i] = i.value);
  $$(".instr-c").forEach(i => instr[i.dataset.i] = i.checked);
  const body = { roles: Object.keys(roles).length ? roles : null,
                 instr: Object.keys(instr).length ? instr : null, ...(extra || {}) };
  if (body.reset_instr) body.instr = null;
  if ($("#tac-formation") && !body.formation) body.formation = $("#tac-formation").value;
  if ($("#tac-mentality") && !body.mentality) body.mentality = $("#tac-mentality").value;
  try {
    const r = await api.post("/api/tactics", body);
    if (r && r.ok === false) toast(esc(r.msg || "Could not save tactics"), 4000);
    return r;
  } catch (e) { toast("Tactics error: " + esc(e.message), 5000); }
}
async function autoPickXI() {
  const r = await api.post("/api/match/auto", {});
  toast(esc(r.msg || "Done")); renderTactics();
}
let PICK_SLOT = null;
function pickSlot(i, pos) { PICK_SLOT = { i, pos }; showSlotPicker(pos); }
async function showSlotPicker(pos) {
  const j = await api.get("/api/screen/squad");
  const t = window._tactics;
  const used = new Set(t.xi.filter(x => x.player).map(x => x.player.id));
  const rank = p => p.pos === pos ? 0 : (p.pos2 === pos ? 1 : 2);
  const cands = j.players.filter(p => p.squad !== "Youth" && !used.has(p.id))
    .sort((a, b) => rank(a) - rank(b) || b.ca - a.ca).slice(0, 22);
  modal(`<h2>Pick a player for ${esc(pos)}</h2>
    <div class="card" style="padding:0;max-height:52vh;overflow:auto">
    <table><thead><tr><th>Pos</th><th>Name</th><th class="num">CA</th><th class="num">Stars</th>
      <th class="num">Cond</th><th class="num">Fit</th><th>Status</th><th></th></tr></thead>
    <tbody>${cands.map(p => `<tr><td><span class="pos">${esc(p.pos)}</span>${p.pos2 ? '<span class="muted small">/' + esc(p.pos2) + "</span>" : ""}</td>
      <td><b>${esc(p.name)}</b></td>
      <td class="num">${p.ca.toFixed(1)}</td><td class="num">${stars(p.stars)}</td>
      <td class="num">${p.condition.toFixed(2)}</td><td class="num">${Math.round(p.fitness)}</td>
      <td class="small">${p.injured ? '<span class="tag L">' + esc(p.injury) + "</span>" : p.suspended ? '<span class="tag L">susp</span>' : '<span class="tag W">fit</span>'}</td>
      <td><button class="btn sm primary" onclick="applySlot(${p.id})">Select</button></td></tr>`).join("")}</tbody></table></div>`, true);
}
async function applySlot(pid) {
  const t = window._tactics;
  const ids = t.xi.map(x => x.player ? x.player.id : 0);
  const at = ids.indexOf(pid);
  if (at >= 0) ids[at] = ids[PICK_SLOT.i];
  ids[PICK_SLOT.i] = pid;
  const clean = ids.filter(x => x);
  if (clean.length !== 11) { toast(`Fill all 11 slots first (${clean.length}/11).`, 4000); return; }
  try {
    const r = await api.post("/api/match/select", { ids: clean });
    closeModal();
    toast(esc(r.msg || (r.ok ? "Team selected" : "Failed")), 4000);
    renderTactics();
  } catch (e) { closeModal(); toast(esc(e.message), 5000); }
}
function swapIn(pid) {
  const empty = window._tactics.xi.findIndex(x => !x.player);
  if (empty >= 0) { PICK_SLOT = { i: empty, pos: window._tactics.xi[empty].pos }; applySlot(pid); }
  else toast("All slots are filled — click a slot on the pitch to replace that player.", 4000);
}

/* ----------------------------------------------------------------- TRAINING */
async function renderTraining() {
  const t = await api.get("/api/screen/training");
  await refreshState();
  const days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
  $("#content").innerHTML = `
    <div class="sec-h"><h3>Training</h3></div>
    <div class="strip">
      <div class="st"><span class="st-l">Fatigue</span><span class="st-v ${t.squad_load.fatigue > 55 ? "warn" : ""}">${t.squad_load.fatigue}</span></div>
      <div class="st"><span class="st-l">Fitness</span><span class="st-v">${t.squad_load.fitness}</span></div>
      <div class="st"><span class="st-l">Sharpness</span><span class="st-v">${t.squad_load.sharpness}</span></div>
      <div class="st"><span class="st-l">Injured</span><span class="st-v ${t.squad_load.injured ? "bad" : ""}">${t.squad_load.injured}</span></div>
    </div>
    <div class="card tight" style="padding:0">
      ${t.week.map(w => {
        const s = t.sessions.find(x => x.name === w.session) || {};
        const sg = v => v == null ? "—" : (v > 0 ? "+" : "") + v;
        return `<div class="trn">
          <div class="trn-d"><b>${days[w.day]}</b><span>${(s.attrs || []).slice(0, 3).join(", ") || "—"}</span></div>
          <select onchange="setTraining(${w.day},this.value,'${esc(w.focus || "")}')">
            ${t.sessions.map(x => `<option ${x.name === w.session ? "selected" : ""}>${x.name}</option>`).join("")}</select>
          <select onchange="setTraining(${w.day},'${esc(w.session)}',this.value)">
            <option value="">— none —</option>
            ${t.focus_options.map(p => `<option ${w.focus === p ? "selected" : ""}>${p}</option>`).join("")}</select>
          <div class="trn-e"><span class="tag ${s.fatigue >= 8 ? "URGENT" : s.fatigue <= -20 ? "ROUTINE" : ""}">fat ${sg(s.fatigue)}</span>
            <span class="tag ${s.fitness > 0 ? "ROUTINE" : ""}">fit ${sg(s.fitness)}</span>
            <span class="tag">shp ${sg(s.sharpness)}</span></div>
        </div>`;
      }).join("")}
    </div>
    <div class="grid g2" style="margin-top:12px">
      <div class="card"><h3>Coaching staff</h3>
        <table><thead><tr><th>Role</th><th class="num">n</th><th class="num">Att</th><th class="num">Def</th>
          <th class="num">Fit</th><th class="num">Tac</th><th class="num">Tec</th><th class="num">Wages</th></tr></thead>
        <tbody>${t.coaching.map(c => `<tr><td>${esc(c.role)}</td><td class="num">${c.n}</td>
          <td class="num">${Math.round(c.att || 0)}</td><td class="num">${Math.round(c.dfn || 0)}</td>
          <td class="num">${Math.round(c.fit || 0)}</td><td class="num">${Math.round(c.tac || 0)}</td>
          <td class="num">${Math.round(c.tec || 0)}</td><td class="num small">${wk(c.wage)}</td></tr>`).join("")}</tbody></table>
      </div>
      <div class="card"><h3>How training works</h3>
        <div class="small muted pre">Sessions add fatigue and sharpness, build fitness, and give a daily chance to improve specific attributes — weighted by your coaching quality and facilities.

Match Preparation the day before a game and Recovery the day after are applied automatically. During international breaks the squad rests.

High fatigue raises injury risk and lowers match condition. Young players develop fastest with match minutes.</div>
      </div>
    </div>`;
}
async function setTraining(day, session, focus) {
  const r = await api.post("/api/training", { day, session, focus });
  if (r && r.ok === false) toast(esc(r.msg || "Failed"));
  else renderTraining();
}

/* -------------------------------------------------------------------- MATCH */
let MATCH = null;
/* ------------------------------------------------------------------ MATCHDAY */
function evIcon(t, e) {
  if (t === "goal") return ["ev-goal", "G"];
  if (t === "yellow") return ["ev-card", "Y"];
  if (t === "red") return ["ev-red", "R"];
  if (t === "var") {
    if (e && e.stage === "overturn" && e.decision === "disallowed") return ["ev-var disallow", "✕"];
    if (e && e.stage === "confirmed") return ["ev-var confirm", "✓"];
    return ["ev-var", "VAR"];
  }
  if (t === "var_disallowed") return ["ev-var disallow", "✕"];
  if (t === "sub") return ["ev-sub", "S"];
  if (t === "injury") return ["ev-info", "+"];
  if (t === "penalties") return ["ev-info", "P"];
  return ["ev-info", "•"];
}
function scoreEvents(evs, base) {
  let h = base ? base[0] : 0, a = base ? base[1] : 0;
  return (evs || []).map(e => {
    const o = Object.assign({}, e);
    if (e.type === "goal") {
      if (e.side === "H") h++; else if (e.side === "A") a++;
      o._sc = h + "–" + a;
    }
    return o;
  });
}
function evRow(e) {
  const [cls, ic] = evIcon(e.type, e);
  return `<div class="ev ${cls}"><span class="min">${e.minute}'</span><span class="ei">${ic}</span>
    <div class="et">${esc(e.text || (e.type === "shot" ? `${e.player || ""} — ${e.outcome || "chance"}${e.xg != null ? " (xG " + e.xg + ")" : ""}` : e.type))}${e._sc ? ` <span class="escore">${e._sc}</span>` : ""}</div></div>`;
}
function hexA(c, a) {
  if (!c || c[0] !== "#") return "rgba(120,140,160," + a + ")";
  const n = parseInt(c.slice(1), 16);
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
}
function clubCol(code, i) {
  const c = CREST[code || ""]; return c ? c[i] : null;
}
function goalFlash(e) {
  const C = G.codes || {};
  const code = e.side === "H" ? C.home : C.away;
  const el = document.createElement("div");
  el.className = "gflash";
  el.style.setProperty("--gc", compColor(C.comp));
  el.innerHTML = `<div class="gf-in">${crest(code, "lg")}
    <div style="flex:1;min-width:0"><div class="gf-t">GOAL · ${e.minute}'</div>
    <div class="gf-n">${esc(e.player || "")}</div></div>
    <div class="gf-s">${esc(e._sc || "")}</div></div>`;
  document.body.appendChild(el);
  setTimeout(() => el.classList.add("out"), 2200);
  setTimeout(() => el.remove(), 2700);
}
function varFlash(e) {
  const stage = e.stage || "check";
  const isConfirm = stage === "confirmed" || e.decision === "goal";
  const isDisallow = stage === "overturn" || e.decision === "disallowed" || e.type === "var_disallowed";
  const el = document.createElement("div");
  el.className = "varflash";
  const boxCls = isConfirm ? "confirm" : isDisallow ? "disallow" : "";
  const iconTxt = isConfirm ? "✓" : isDisallow ? "✕" : "VAR";
  const title = stage === "check" ? "VAR CHECK" : isConfirm ? "GOAL CONFIRMED" : "GOAL DISALLOWED";
  el.innerHTML = `<div class="varbox ${boxCls}"><div class="var-icon">${iconTxt}</div>
    <div class="var-t">${title}</div>
    <div class="var-sub">${esc(e.player || "")}${e.reason ? " · " + esc(e.reason) : ""}</div>
    ${e.text ? `<div class="var-reason">${esc(e.text)}</div>` : ""}</div>`;
  document.body.appendChild(el);
  setTimeout(() => el.classList.add("out"), stage === "check" ? 1600 : 2200);
  setTimeout(() => el.remove(), stage === "check" ? 2000 : 2700);
}
function cardFlash(e) {
  const isRed = e.type === "red";
  const el = document.createElement("div");
  el.className = "cardflash";
  el.innerHTML = `<div class="cf-card ${isRed ? "red" : "yellow"}">${isRed ? "🟥" : "🟨"}</div>
    <div class="cf-info"><b>${esc(e.player || "")}</b><br><span class="small muted">${esc(e.text || (isRed ? "RED CARD" : "YELLOW CARD"))}</span></div>`;
  document.body.appendChild(el);
  setTimeout(() => el.classList.add("out"), 1800);
  setTimeout(() => el.remove(), 2300);
}
function statDuo(a, b, label, fmt) {
  const f = fmt || (x => x);
  const an = Number(a) || 0, bn = Number(b) || 0;
  const tot = an + bn || 1;
  return `<div class="stat-duo"><span class="v">${f(a)}</span>
    <span class="lb">${label}<span class="sb"><i style="width:${an / tot * 100}%"></i></span>
    <span class="sb r"><i style="width:${bn / tot * 100}%"></i></span></span>
    <span class="v r">${f(b)}</span></div>`;
}
function sv(S, side, k) {
  const o = (S || {})[side] || {};
  let v = o[k];
  if (v == null) v = o[k === "possession" ? "poss" : k === "poss" ? "possession" : k];
  return v;
}
function statsBlock(S, meFirst) {
  const A = meFirst ? "me" : "home", B = meFirst ? "opp" : "away";
  const rows = [["possession", "Possession %"], ["shots", "Shots"], ["sot", "On target"],
    ["xg", "xG", x => Number(x || 0).toFixed(2)], ["big", "Big chances"], ["corners", "Corners"],
    ["fouls", "Fouls"], ["saves", "Saves"]];
  return rows.map(([k, label, f]) => {
    const a = sv(S, A, k), b = sv(S, B, k);
    if (a == null && b == null) return "";
    return statDuo(a == null ? "—" : a, b == null ? "—" : b, label, f);
  }).join("");
}
/* Quick sell - premium easy selling */
async function quickSell(pid, name) {
  modal(`<h2>Sell ${esc(name)} — quick sale</h2>
    <p class="small muted">List this player for transfer. Other clubs will bid if interested. You can also set asking price.</p>
    <div class="grid g2" style="margin-top:12px">
      <div><label>Asking price (€m)</label><input id="qs-price" type="number" step="0.5" value="5" style="width:100%"></div>
      <div><label>Reason</label><select id="qs-reason" style="width:100%"><option>Surplus to requirements</option><option>Needs first-team football</option><option>Financial reasons</option><option>Disruptive influence</option></select></div>
    </div>
    <div class="row" style="margin-top:16px"><span class="spacer"></span>
      <button class="btn" onclick="closeModal()">Cancel</button>
      <button class="btn primary" onclick="doQuickSell(${pid})">List for ${esc(name)} sale 💸</button>
    </div>`);
}
async function doQuickSell(pid) {
  const price = +$("#qs-price").value || 0;
  closeModal();
  const r = await api.post("/api/squad/list", { pid, listed: true, asking: price });
  toast(r.msg || `Listed for sale — asking ${money(price)}`, 4000);
  if (G.screen === "squad") renderSquad();
  else if (G.screen === "player") go("player", pid);
}

async function renderMatch() {
  await refreshState();
  if (G.pendingMatch) { showHalftime(G.halftimeState); return; }
  const j = await api.get("/api/match/next");
  if (!j.ok) { $("#content").innerHTML = `<div class="card" style="text-align:center;padding:32px"><h3>No upcoming match</h3><p class="muted small" style="margin-top:8px">${esc(j.msg)}</p><button class="btn primary sm" style="margin-top:12px" onclick="doContinue()">Continue world ▸</button></div>`; return; }
  MATCH = j;
  const p = j.preview, f = p.fixture;
  G.codes = { home: f.home_code, away: f.away_code, comp: f.code, compName: compLabel(f), stage: f.stage, venue: f.venue, date: f.date };
  const myForm = p.my.form || [], opForm = p.opp.form || [];
  const hForm = f.is_home ? myForm : opForm, aForm = f.is_home ? opForm : myForm;
  const rivalry = isRivalry(f.home_code, f.away_code);
  const isFriendly = f.code === "friendly" || (f.comp||"").toLowerCase().includes("friendly");
  $("#content").innerHTML = `
    ${rivalry ? `<div class="derby-banner">🔥 ${esc(rivalry.name.toUpperCase())} — DERBY DAY — ATMOSPHERE ELECTRIC 🔥</div>` : ""}
    <div class="mhero ${compClass(f.code)}" style="--comp:${compColor(f.code)}">
      <div class="mhero-top">${compLogo(f.code)}<span class="comp-dot"></span><span>${esc(compLabel(f))}${f.stage && f.stage !== "league" && f.comp ? " · " + esc(f.stage) : ""} ${rivalry ? `· <span style="color:#ff6b6b;font-weight:900">🔥 ${esc(rivalry.name)}</span>` : ""} ${isFriendly ? '· <span class="tag" style="background:rgba(53,224,138,.15);color:var(--acc)">FRIENDLY — ROTATED SQUADS</span>' : ""}</span><span class="spacer"></span><span>${fmtDate(f.date)}</span></div>
      <div class="mhero-body">
        <div class="mhero-club">${crest(f.home_code, "xl")}<div class="nm">${esc(f.home)}</div>
          <div class="fm">${formPills(hForm, 5)}</div>
          <div class="small muted" style="margin-top:4px;font-size:10px">Form: ${hForm.map(x=>x.res).join("")||"—"}</div>
        </div>
        <div class="mhero-mid">
          <div class="vs">VS</div>
          <div class="when" style="font-weight:800">${fmtDate(f.date)}</div>
          <div class="venue">${esc(f.venue || "")}</div>
          ${rivalry ? `<div class="rivalry-tag" style="margin-top:8px">⚔️ Rivalry match — high stakes</div>` : ""}
        </div>
        <div class="mhero-club">${crest(f.away_code, "xl")}<div class="nm">${esc(f.away)}</div>
          <div class="fm">${formPills(aForm, 5)}</div>
          <div class="small muted" style="margin-top:4px;font-size:10px">Form: ${aForm.map(x=>x.res).join("")||"—"}</div>
        </div>
      </div>
      <div class="mhero-foot" style="gap:12px">
        <button class="btn primary" style="min-height:48px;padding:0 24px;font-size:14.5px;box-shadow:0 6px 20px var(--acc-glow)" onclick="playMatch('full')">▶️ Watch full match — LIVE animations</button>
        <button class="btn" style="min-height:44px" onclick="playMatch('key')">⚡ Key moments</button>
        <button class="btn" style="min-height:44px" onclick="playMatch('instant')">⏩ Instant result</button>
      </div>
      <div style="padding:8px 16px;background:rgba(0,0,0,.2);border-top:1px solid var(--line);display:flex;gap:8px;align-items:center;flex-wrap:wrap">
        <span class="small muted">🎬 Premium match experience:</span>
        <span class="tag" style="font-size:10px">🎥 VAR checks visible</span>
        <span class="tag" style="font-size:10px">🟨🟥 Card animations</span>
        <span class="tag" style="font-size:10px">⚽ Goal flashes</span>
        <span class="tag" style="font-size:10px">📊 Live stats</span>
      </div>
    </div>

    ${pressHypeForFixture(f)}

    <div class="grid g2" style="margin-top:14px">
      <div class="card tight">
        <div class="sec-h"><h3>Your team — ${esc(p.tactic.formation)}</h3><span class="spacer"></span><button class="btn sm" onclick="go('tactics')">Tactics ▸</button></div>
        <div class="kv"><span>Mentality</span><b>${esc(p.tactic.mentality)}</b></div>
        <div class="kv"><span>Squad strength</span><b style="font-size:16px">${p.my.ca.toFixed(1)} <span class="small muted">/ 20</span></b></div>
        <div class="kv"><span>Attack / defence</span><b>${p.my.attack} / ${p.my.defence}</b></div>
        <div class="kv"><span>Avg condition</span><b>${p.my.condition}</b></div>
        <div class="kv"><span>Familiarity</span><b>${Math.round(p.tactic.familiarity||0)}%</b></div>
        ${isFriendly ? `<div class="card tight" style="margin-top:10px;background:linear-gradient(135deg, #1a2e1a, #162a16);border-color:#2a4a2a"><span class="small" style="color:#8ab88a">🤝 Friendly realism: Youth and rotation expected. Top players rested, fringe players get chance. Low intensity — good for fitness without injury risk.</span></div>` : ""}
      </div>
      <div class="card tight">
        <div class="sec-h"><h3>Opposition — ${esc(p.opp.name)}</h3><span class="spacer"></span><span class="small muted">${p.opposition_report.known}% scouted</span></div>
        <div class="kv"><span>Strength</span><b>${p.opp.ca ? p.opp.ca.toFixed(1) + " / 20" : "unknown"}</b></div>
        <div class="kv"><span>Reputation · league</span><b>${p.opp.rep} · ${esc(p.opp.league)}</b></div>
        <div class="kv"><span>Manager style</span><b class="small">${esc(p.opp.style||"Balanced")}</b></div>
        ${p.opposition_report.key_players.slice(0, 3).map(k => `<div class="kv"><span>⚠️ ${esc(k.name)} <i class="muted small">${esc(k.pos)}</i></span><b>${k.goals}g${k.ca ? " · CA " + k.ca : ""}</b></div>`).join("") || '<div class="small muted" style="padding:8px 0">No scouting report — assign scout to learn weaknesses.</div>'}
        <button class="btn sm" style="margin-top:8px" onclick="go('scouting')">Scout report ▸</button>
      </div>
    </div>

    <div class="grid g2 pitchwide" style="margin-top:14px">
      <div class="card tight"><div class="sec-h"><h3>Selected XI — ${esc(p.tactic.formation)}</h3><span class="spacer"></span><span class="small muted">Tap pitch to change</span></div>${pitchHTML(p.xi, false)}</div>
      <div class="card tight" style="padding:0">
        <div class="sec-h" style="padding:12px 14px 6px"><h3>Bench — ${p.bench.length} available</h3></div>
        <div style="padding:0 12px 12px;display:grid;gap:6px">
          ${p.bench.map(b => `<div class="sqr" style="min-height:44px;padding:8px 12px;background:var(--sf2);border-radius:10px"><span class="pos">${esc(b.pos)}</span><span class="sqr-n"><b>${esc(b.name)}</b><i>CA ${b.ca.toFixed(1)} · ${Math.round(b.condition*100)}% fit</i></span><span class="tag ${condClass(b.condition)}" style="font-size:10px">${b.condition.toFixed(2)}</span></div>`).join("") || '<div class="small muted" style="padding:12px">No bench — thin squad</div>'}
        </div>
      </div>
    </div>`;
}

/* live presentation: PREMIUM CINEMATIC - animations impossible to miss */
function liveScreen(cfg, onDone) {
  const C = G.codes || {};
  const evs = scoreEvents((cfg.events || []).slice().sort((a, b) => a.minute - b.minute), cfg.base);
  const end = cfg.endMin || Math.max(45, ...evs.map(e => e.minute), 1);
  const isSecondHalf = (cfg.startMin || 0) >= 45;
  $("#content").innerHTML = `
    <div class="mhero ${compClass(C.comp)}" style="--comp:${compColor(C.comp)}">
      <div class="mhero-top">${compLogo(C.comp)}<span class="comp-dot" style="animation:dot-glow 1s infinite"></span><span>${esc(C.compName || "Match")}${C.stage && C.stage !== "league" ? " · " + esc(C.stage) : ""}</span><span class="spacer"></span><span class="tag" style="background:#ff3b30;color:white;animation:dot-pulse 1s infinite">● LIVE ${cfg.startMin}'-${end}'</span></div>
      <div class="live-bar" style="border:0;border-radius:0;background:linear-gradient(90deg, ${hexA(clubCol(G.codes.home,0),.22)}, rgba(0,0,0,0) 35%, rgba(0,0,0,0) 65%, ${hexA(clubCol(G.codes.away,0),.22)});padding:18px 16px">
        <span class="lb-team" style="font-size:15px">${crest(C.home, "lg")}<b>${esc(cfg.homeShort || "")}</b></span>
        <span class="lb-mid"><span class="lscore" id="lv-score" style="font-size:32px;text-shadow:0 2px 12px rgba(0,0,0,.5)">${cfg.base[0]} – ${cfg.base[1]}</span>
          <span class="clock" id="lv-clock" style="font-size:18px;padding:6px 14px">${cfg.startMin}'</span>
          <span class="small muted" style="font-size:10px;letter-spacing:.1em">${isSecondHalf ? "SECOND HALF" : "FIRST HALF"}</span></span>
        <span class="lb-team r" style="font-size:15px"><b>${esc(cfg.awayShort || "")}</b>${crest(C.away, "lg")}</span>
      </div>
      <div id="lv-feed" style="padding:8px 16px 16px;min-height:40dvh;max-height:58dvh;overflow-y:auto;background:linear-gradient(180deg, transparent, rgba(0,0,0,.15))">
        <div class="lv-empty" style="text-align:center;padding:40px 20px">
          <div style="width:56px;height:56px;margin:0 auto 12px;border-radius:16px;background:var(--sf2);display:grid;place-items:center;font-size:24px;animation:dot-pulse 2s infinite">⚽</div>
          <div style="font-weight:700;font-size:14px">Live match in progress</div>
          <div class="small muted" style="margin-top:4px">Goals, cards, VAR checks will appear here with cinematic animations<br>🎥 Watch for: <span class="tag" style="font-size:10px">VAR</span> <span class="tag" style="font-size:10px">GOAL FLASH</span> <span class="tag" style="font-size:10px">CARD 3D</span></div>
        </div>
      </div>
      <div class="mhero-foot" style="background:rgba(0,0,0,.25);padding:12px 16px">
        <button class="btn sm" id="lv-skip" style="background:var(--sf3)">Skip to ${cfg.label} ⏩</button>
        <span class="spacer"></span>
        <span class="small muted">💡 Tip: Full match shows every chance. Key moments only big events.</span>
      </div>
    </div>
    <div class="card tight" style="margin-top:12px;background:linear-gradient(135deg, #10131a, #171b26)">
      <div style="display:flex;align-items:center;gap:10px">
        <div style="width:32px;height:32px;border-radius:10px;background:linear-gradient(135deg, #1a2a4a, #16213e);display:grid;place-items:center">🎬</div>
        <div><b style="font-size:13px">Premium live experience</b><div class="small muted">Cinematic VAR overlays, 3D card flips, goal flashes with club crests — you won't miss a moment</div></div>
      </div>
    </div>`;
  let min = cfg.startMin || 0, i = 0, sc = cfg.base.slice();
  const feed = $("#lv-feed"), clock = $("#lv-clock"), scoreEl = $("#lv-score");
  const push = e => {
    const em = feed.querySelector(".lv-empty"); if (em) em.remove();
    feed.insertAdjacentHTML("afterbegin", evRow(e));
    // PREMIUM: Ensure animations are VISIBLE and dramatic
    if (e.type === "goal") {
      goalFlash(e);
      // Extra screen shake for goals
      document.body.animate([{ transform: "translateX(0)" }, { transform: "translateX(2px)" }, { transform: "translateX(-2px)" }, { transform: "translateX(0)" }], { duration: 300 });
      // Haptic if available
      try { if (navigator.vibrate) navigator.vibrate([100, 50, 100]); } catch(e) {}
    }
    if (e.type === "var" || e.type === "var_disallowed") {
      varFlash(e);
      try { if (navigator.vibrate) navigator.vibrate([50, 30, 50, 30, 100]); } catch(e2) {}
    }
    if (e.type === "yellow" || e.type === "red") {
      cardFlash(e);
      try { if (navigator.vibrate) navigator.vibrate(e.type === "red" ? [200] : [100]); } catch(e2) {}
    }
    if (e.type === "goal") {
      if (e._sc) scoreEl.textContent = e._sc.replace("–", " – ");
      else { if ((e.side === "H") === true) sc[0]++; else if (e.side === "A") sc[1]++; scoreEl.textContent = sc[0] + " – " + sc[1]; }
      scoreEl.animate([{ transform: "scale(1.4)", color: "#35e08a" }, { transform: "scale(1)", color: "var(--tx)" }], { duration: 400, easing: "cubic-bezier(.2,.8,.2,1)" });
    }
    if (e.type === "var_disallowed") {
      if (e.side === "H" && sc[0] > cfg.base[0]) sc[0]--; else if (e.side === "A" && sc[1] > cfg.base[1]) sc[1]--;
      scoreEl.textContent = sc[0] + " – " + sc[1];
      scoreEl.animate([{ transform: "scale(.9)", color: "#ff5d6b" }, { transform: "scale(1)" }], { duration: 400 });
    }
  };
  const finish = () => { clearInterval(timer); while (i < evs.length) push(evs[i++]); clock.textContent = end + "'"; setTimeout(onDone, 600); };
  $("#lv-skip").onclick = finish;
  const timer = setInterval(() => {
    min++;
    clock.textContent = min + "'";
    while (i < evs.length && evs[i].minute <= min) push(evs[i++]);
    if (min >= end) finish();
  }, 90);
}

async function playMatch(mode) {
  G.matchMode = mode;
  G.busy = true; setBusy(true);
  try {
    const j = await api.post("/api/match/play", { mode });
    if (!j.ok) { toast(esc(j.msg || "Could not play the match"), 5000); G.busy = false; setBusy(false); return; }
    if (j.halftime) {
      G.pendingMatch = true; G.halftimeState = j.state; G.matchFixture = j.fixture;
      if (mode === "full") {
        const st = j.state;
        liveScreen({ events: st.events, base: [0, 0], startMin: 0, endMin: 45, label: "half-time",
          homeShort: st.home_short || st.home_name, awayShort: st.away_short || st.away_name },
          () => showHalftime(st));
      } else showHalftime(j.state);
    } else {
      await refreshState();
      showResult(j.result);
    }
  } catch (e) { toast("Match failed: " + esc(e.message), 6000); }
  G.busy = false; setBusy(false);
}
function showHalftime(st) {
  if (!st) {
    const C = G.codes || {};
    $("#content").innerHTML = `
      <div class="mhero ${compClass(C.comp)}" style="--comp:${compColor(C.comp)}">
        <div class="mhero-top">${compLogo(C.comp)}<span class="comp-dot"></span><span>${esc(C.compName || "Match")}</span>
          <span class="spacer"></span><span>HALF-TIME</span></div>
        <div style="padding:16px 14px 18px">
          <h2 style="margin:0 0 6px">Match paused at half-time</h2>
          <p class="small muted" style="margin:0 0 14px">The break survived, but your notes did not.
            Resume with no changes, or let the engine finish it.</p>
          <div class="row">
            <button class="btn primary" onclick="submitHalftime(true)">Send them back out ▸</button>
            <button class="btn" onclick="resumeMatch()">Auto-finish</button>
          </div>
        </div>
      </div>`;
    return;
  }
  window._ht = st;
  const C = G.codes || {};
  $("#content").innerHTML = `
    <div class="mhero" style="--comp:${compColor(C.comp)}">
      <div class="mhero-top"><span class="comp-dot"></span><span>${esc(C.compName || "Match")}</span><span class="spacer"></span><span>HALF-TIME</span></div>
      <div class="live-bar" style="border:0;border-radius:0;background:linear-gradient(90deg, ${hexA(clubCol(G.codes.home,0),.18)}, rgba(0,0,0,0) 38%, rgba(0,0,0,0) 62%, ${hexA(clubCol(G.codes.away,0),.18)})">
        <span class="lb-team">${crest(C.home)}<b>${esc(st.home_name)}</b></span>
        <span class="lb-mid"><span class="lscore">${st.score.home} – ${st.score.away}</span><span class="clock ht">HT</span></span>
        <span class="lb-team r"><b>${esc(st.away_name)}</b>${crest(C.away)}</span>
      </div>
      <div style="padding:6px 14px 14px">${statsBlock(st.stats, true)}</div>
    </div>
    <div class="card tight" style="margin-top:12px">
      <div class="sec-h"><h3>First-half incidents</h3></div>
      ${st.events.length ? scoreEvents(st.events.slice(), [0, 0]).reverse().map(evRow).join("") : '<p class="muted small">A quiet first half.</p>'}
    </div>
    <div class="grid g2" style="margin-top:12px">
      <div class="card tight">
        <div class="sec-h"><h3>Team talk</h3></div>
        <select id="ht-talk" style="width:100%;min-height:38px;background:var(--sf2);color:var(--tx);border:1px solid var(--line2);border-radius:8px;padding:0 10px">
          ${st.talks.map(t => `<option value="${t}" ${t === "neutral" ? "selected" : ""}>${esc(t[0].toUpperCase() + t.slice(1))}</option>`).join("")}
        </select>
        <div class="small muted" style="margin-top:6px" id="ht-hint">${esc(talkHint("neutral", st))}</div>
        <div class="sec-h" style="margin-top:12px"><h3>Substitutions</h3><span class="spacer"></span><span class="small muted">max 3</span></div>
        <div id="ht-subs"></div>
        <button class="btn sm" onclick="addSubRow()" style="margin-top:6px">+ Add substitution</button>
        <div class="row" style="margin-top:12px">
          <button class="btn primary" onclick="submitHalftime()">Send them back out ▸</button>
          <button class="btn" onclick="submitHalftime(true)">No changes</button>
        </div>
      </div>
      <div class="card tight" style="padding:0">
        <div class="sec-h" style="padding:10px 12px 4px"><h3>Your players at the break</h3></div>
        <table class="mc"><thead><tr><th>Pos</th><th>Name</th><th class="num">Rating</th><th class="num">Fatigue</th></tr></thead>
        <tbody>${st.xi.map(p => `<tr><td><span class="pos">${esc(p.pos)}</span></td><td>${esc(p.name)}</td>
          <td class="num"><b>${p.rating.toFixed(2)}</b></td><td class="num">${Math.round(p.fatigue)}</td></tr>`).join("")}</tbody></table>
      </div>
    </div>`;
  $("#ht-talk").addEventListener("change", e => $("#ht-hint").textContent = talkHint(e.target.value, st));
  SUB_ROWS = 0; addSubRow();
  polish($("#content"));
}
function talkHint(talk, st) {
  const diff = st.my_score - st.opp_score;
  const notes = {
    praise: "Lifts morale. Works best when the team is already on top.",
    encourage: "Steady morale boost and a small attacking lift.",
    neutral: "No effect on morale or tactics.",
    firm: "Sharper reaction when you are behind; can unsettle players who are already winning.",
    aggressive: "Biggest push — more pressing and attacking intent, more fatigue and card risk.",
    defensive: "Drops the line and eases the press. Protects a lead.",
    attacking: "Raises the tempo and pushes the line up. Chases a goal."
  };
  let s = notes[talk] || "";
  if (diff < 0 && talk === "praise") s += " You are losing — praise may read as complacency.";
  if (diff > 0 && (talk === "firm" || talk === "aggressive")) s += " You are winning — harsh words can dent confidence.";
  return s;
}
let SUB_ROWS = 0;
function addSubRow() {
  const st = window._ht; if (!st) return;
  if (SUB_ROWS >= 3) { toast("Maximum three substitutions at half-time."); return; }
  SUB_ROWS++;
  const wrap = document.createElement("div");
  wrap.className = "row ht-sub";
  wrap.style.marginBottom = "6px";
  wrap.innerHTML = `
    <select class="sub-off" style="flex:1;min-height:36px;background:var(--sf2);color:var(--tx);border:1px solid var(--line2);border-radius:8px"><option value="">Off…</option>
      ${st.xi.map(p => `<option value="${p.pid}">${esc(p.name)} (${esc(p.pos)} ${p.rating.toFixed(2)})</option>`).join("")}</select>
    <select class="sub-on" style="flex:1;min-height:36px;background:var(--sf2);color:var(--tx);border:1px solid var(--line2);border-radius:8px"><option value="">On…</option>
      ${st.bench.map(b => `<option value="${b.pid}">${esc(b.name)} (${esc(b.pos)} ${b.ca.toFixed(1)})</option>`).join("")}</select>
    <button class="btn sm" onclick="this.parentNode.remove()">✕</button>`;
  $("#ht-subs").appendChild(wrap);
}
async function submitHalftime(noChange) {
  const talk = noChange ? null : ($("#ht-talk") ? $("#ht-talk").value : null);
  const subs = noChange ? [] : $$(".ht-sub").map(r => {
    const off = $(".sub-off", r).value, on = $(".sub-on", r).value;
    return off && on ? [+off, +on] : null;
  }).filter(x => x);
  G.busy = true; setBusy(true);
  try {
    const j = await api.post("/api/match/halftime", { talk, subs });
    G.pendingMatch = false; G.halftimeState = null; SUB_ROWS = 0;
    if (!j.ok) { toast(esc(j.msg || "Could not resume the match"), 5000); G.busy = false; setBusy(false); return; }
    await refreshState();
    if (G.matchMode === "full") {
      const st = window._ht;
      if (st) {
        const second = (j.result.events || []).filter(e => e.minute > 45);
        liveScreen({ events: second, base: [st.score.home, st.score.away], startMin: 45, endMin: 90,
          label: "full-time", homeShort: st.home_short || st.home_name, awayShort: st.away_short || st.away_name },
          () => showResult(j.result));
      } else showResult(j.result);
    } else showResult(j.result);
  } catch (e) { toast("Match failed: " + esc(e.message), 6000); }
  G.busy = false; setBusy(false);
}
function showResult(r) {
  const isH = r.is_home;
  const my = isH ? r.hg : r.ag, opp = isH ? r.ag : r.hg;
  const res = r.result || (my > opp ? "W" : my === opp ? "D" : "L");
  const mySide = isH ? "H" : "A";
  const all = (r.events || []).slice().sort((a, b) => a.minute - b.minute);
  const relevant = all.filter(e => e.type === "goal" || e.type === "red" || e.type === "injury" ||
    e.type === "sub" || e.type === "halftime" || e.type === "kickoff" || e.type === "team_talk" ||
    e.type === "penalties" || e.side === mySide);
  const shown = r.mode === "instant" ? all.filter(e => ["goal", "red", "penalties", "halftime", "kickoff"].includes(e.type))
    : r.mode === "key" ? relevant.filter(e => ["goal", "red", "injury", "sub", "halftime", "kickoff", "team_talk", "penalties"].includes(e.type))
    : relevant;
  const C = G.codes || {};
  const hCode = r.home_code || C.home || "", aCode = r.away_code || C.away || "";
  // update G.codes to match actual result to prevent stale cache
  G.codes = { home: hCode, away: aCode, comp: r.comp_code || r.code || C.comp, compName: r.comp || C.compName, stage: C.stage, venue: C.venue, date: C.date };
  const motm = (r.players || []).find(p => p.pid === r.motm);
  $("#content").innerHTML = `
    <div class="mhero ${compClass(C.comp || r.code)}" style="--comp:${compColor(C.comp)};background:linear-gradient(103deg, ${hexA(clubCol(hCode,0),.15)}, rgba(0,0,0,0) 45%, rgba(0,0,0,0) 55%, ${hexA(clubCol(aCode,1),.15)})">
      <div class="mhero-top">${compLogo(C.comp || r.code)}<span class="comp-dot"></span><span>${esc(r.comp || C.compName || "Match")}${C.stage && C.stage !== "league" && r.comp ? " · " + esc(C.stage) : ""}</span><span class="spacer"></span><span>FULL-TIME</span></div>
      <div class="mhero-body">
        <div class="mhero-club">${crest(hCode, "xl")}<div class="nm">${esc(r.home)}</div></div>
        <div class="mhero-mid"><div class="score" style="font-size:34px">${r.hg} – ${r.ag}</div>
          <div class="row" style="justify-content:center"><span class="tag ${res}">${res === "W" ? "WIN" : res === "D" ? "DRAW" : "LOSS"}</span></div>
          ${r.penalties ? `<div class="when">pens ${esc(JSON.stringify(r.penalties.home))}–${esc(JSON.stringify(r.penalties.away))}</div>` : ""}</div>
        <div class="mhero-club">${crest(aCode, "xl")}<div class="nm">${esc(r.away)}</div></div>
      </div>
      ${motm ? `<div style="padding:0 14px 14px"><div class="motm"><div><div class="lbl">MAN OF THE MATCH</div>
        <b>${esc(motm.name)}</b> <span class="muted small">${esc(motm.pos)} · rating ${motm.rating.toFixed(2)}${motm.goals ? " · " + motm.goals + "g" : ""}${motm.assists ? " · " + motm.assists + "a" : ""}</span></div></div></div>` : ""}
    </div>

    <div class="grid g2" style="margin-top:12px">
      <div class="card tight">
        <div class="sec-h"><h3>Match stats</h3></div>
        ${statsBlock(r.stats, false)}
      </div>
      <div class="card tight">
        <div class="sec-h"><h3>Key events</h3><span class="spacer"></span><span class="small muted">${esc(r.mode)} view</span></div>
        <div style="max-height:300px;overflow-y:auto">${scoreEvents(shown.slice(), [0, 0]).reverse().map(evRow).join("") || '<p class="muted small">Nothing notable.</p>'}</div>
      </div>
    </div>

    <div class="card tight" style="margin-top:12px;padding:0">
      <div class="sec-h" style="padding:10px 12px 4px"><h3>Your players</h3></div>
      <div class="tw"><table class="mc mp"><thead><tr><th>Pos</th><th>Name</th><th class="num">Min</th><th class="num">G</th>
        <th class="num">A</th><th class="num">Sh</th><th class="num">xG</th><th class="num">Rating</th></tr></thead>
      <tbody>${(r.players || []).map(p => `<tr class="${p.pid === r.motm ? "me" : ""}">
        <td><span class="pos">${esc(p.pos)}</span></td>
        <td>${esc(p.name)}${p.pid === r.motm ? ' <span class="tag" style="color:var(--gold)">MOTM</span>' : ""}</td>
        <td class="num">${p.mins}</td><td class="num">${p.goals || ""}</td><td class="num">${p.assists || ""}</td>
        <td class="num">${p.shots || ""}</td><td class="num">${p.xg || ""}</td>
        <td class="num"><b>${p.rating.toFixed(2)}</b></td></tr>`).join("")}</tbody></table></div>
    </div>

    <div class="grid g2" style="margin-top:12px">
      <div class="card tight">
        <div class="sec-h"><h3>Aftermath</h3></div>
        <div class="kv"><span>Board confidence</span><b>${r.board_confidence}</b></div>
        <div class="kv"><span>Fan sentiment</span><b>${r.fan_sentiment}</b></div>
        <div class="kv"><span>Conditions</span><b class="small">${esc(r.weather || "—")} · ${esc(r.referee || "—")}</b></div>
        ${r.injuries && r.injuries.length ? r.injuries.map(i => `<div class="kv"><span class="bad">${esc(i.name)}</span><b class="small">${esc(i.injury)} · ${i.days}d</b></div>`).join("") : ""}
      </div>
      <div class="card tight">
        <div class="sec-h"><h3>Continue</h3></div>
        <p class="small muted">The result is recorded across league tables, cups, finances, morale and the news cycle.</p>
        <div class="row" style="margin-top:10px;flex-direction:column;align-items:stretch">
          <button class="btn primary" onclick="go('home')">Back to office ▸</button>
          <button class="btn" onclick="go('inbox')">Check inbox</button>
        </div>
      </div>
    </div>`;
}
function fmtStat(v, k) {
  if (v == null) return "—";
  return k === "xg" ? Number(v).toFixed(2) : v;
}

/* ---------------------------------------------------------------- TRANSFERS - PREMIUM NO MORE JOKE */
let TR = { pos: "", q: "", max_fee: 0, age_max: 0, free: false, aff: true, sort: "value" };
async function renderTransfers() {
  await refreshState();
  const j = await api.get("/api/screen/transfers");
  const shortlisted = new Set(j.shortlist_ids || []);
  const s = await api.get(`/api/transfer/search?pos=${TR.pos}&q=${encodeURIComponent(TR.q)}&max_fee=${TR.max_fee}&age_max=${TR.age_max}&free=${TR.free}&affordable=${TR.aff !== false}`);
  const win = j.window && j.window !== "closed";
  let players = (s.players || []).slice();
  const sortFns = {
    value: (a,b) => (b.value||0)-(a.value||0),
    ca: (a,b) => (b.ca||0)-(a.ca||0),
    age: (a,b) => (a.age||0)-(b.age||0),
    name: (a,b) => (a.name||"").localeCompare(b.name||"")
  };
  players.sort(sortFns[TR.sort] || sortFns.value);
  $("#content").innerHTML = `
    <div class="sec-h">
      <h3>Transfer Market</h3>
      <span class="spacer"></span>
      <span class="tag ${win ? "ROUTINE" : "URGENT"}" style="font-size:11px;padding:6px 12px">${win ? `🔥 ${String(j.window).toUpperCase()} WINDOW OPEN` : "🔒 WINDOW CLOSED"}</span>
    </div>

    <div class="transfer-hub">
      <div class="transfer-filters">
        <div class="row" style="justify-content:space-between;margin-bottom:12px">
          <h3 style="margin:0;display:flex;align-items:center;gap:8px">💰 Your war chest <span class="tag" style="font-size:12px">${money(j.budget)} available</span></h3>
          <div class="small muted">${fmtDate(j.windows.open)} → ${fmtDate(j.windows.close)} · Winter: ${fmtDate(j.windows.winter[0])} → ${fmtDate(j.windows.winter[1])}</div>
        </div>
        <div class="strip" style="margin:0 0 14px">
          <div class="st"><span class="st-l">Budget</span><span class="st-v" style="font-size:16px;color:var(--acc)">${money(j.budget)}</span></div>
          <div class="st"><span class="st-l">Wage room</span><span class="st-v small" style="font-size:13px">${money((j.wage_budget||0) - (j.wage_bill||0))}/yr free</span></div>
          <div class="st"><span class="st-l">Squad size</span><span class="st-v">${(j.squad_count||0)} players</span></div>
          <div class="st"><span class="st-l">Listed</span><span class="st-v">${(j.listed_count||0)} for sale</span></div>
        </div>
        ${!win ? `<div class="card tight" style="background:linear-gradient(135deg, #3d1a1e, #2a1214);border-color:#5a2226">
          <b style="color:var(--red)">Window closed</b> <span class="small muted">— you can still scout and shortlist, but bids will wait until it opens. Selling is always possible.</span>
        </div>` : ""}
      </div>

      ${j.offers.length ? `<div class="card tight" style="border-color:#6b5522;background:linear-gradient(135deg, #2a1e0a, #1e1608);box-shadow:0 4px 20px rgba(255,190,74,.15)">
        <div class="sec-h"><h3>📥 Incoming bids — action required</h3><span class="spacer"></span><span class="tag URGENT" style="animation:dot-pulse 1.5s infinite">${j.offers.length} bid${j.offers.length>1?'s':''}</span></div>
        <div style="display:grid;gap:10px">
        ${j.offers.map(o => `<div class="card tight" style="background:var(--sf);border-color:#5a4222;display:flex;align-items:center;gap:12px;flex-wrap:wrap">
          <div style="width:44px;height:44px;border-radius:12px;background:linear-gradient(135deg, var(--sf3), var(--sf2));display:grid;place-items:center;font-weight:900">${esc((o.player||"?").split(" ").map(w=>w[0]).slice(0,2).join(""))}</div>
          <div style="flex:1;min-width:160px"><b style="font-size:14px">${esc(o.player)}</b> <span class="pos" style="margin-left:6px">${esc(o.pos)}</span>
            <div class="small muted">${o.age}y · from ${esc(o.from_club||"—")} · value ${money(o.value)} · wage ${wk(o.wage)}</div>
            <div style="margin-top:4px"><span class="tag gold" style="font-size:12px">${money(o.fee)} offered</span> ${o.fee < (o.value||0)*0.8 ? '<span class="tag URGENT" style="font-size:10px">LOWBALL</span>' : o.fee > (o.value||0)*1.3 ? '<span class="tag ROUTINE" style="font-size:10px">GREAT DEAL</span>' : ''}</div>
          </div>
          <div class="row" style="gap:8px;margin-left:auto">
            <button class="btn sm primary" onclick="bid(${o.id},'accept')">Accept ${money(o.fee)} ✓</button>
            <button class="btn sm" onclick="bid(${o.id},'reject')">Reject ✕</button>
            <button class="btn sm" onclick="bidCounter(${o.id},${o.fee})">Counter ↕</button>
          </div></div>`).join("")}
        </div>
      </div>` : ""}

      ${(j.my_offers || []).length ? `<div class="card tight" style="margin-top:4px">
        <div class="sec-h"><h3>🤝 Negotiations in progress</h3><span class="spacer"></span><span class="tag">${j.my_offers.length}</span></div>
        <div style="display:grid;gap:8px">
        ${j.my_offers.map(o => `<div class="kv" style="align-items:center;flex-wrap:wrap;background:${o.awaiting_you ? 'rgba(53,224,138,.06)' : 'transparent'};border:${o.awaiting_you ? '1px solid rgba(53,224,138,.15)' : '0'};border-radius:10px;padding:10px;margin:0 -4px">
          <span style="min-width:0;flex:1"><a href="#" onclick="go('player',${o.player_id});return false" style="font-weight:800">${esc(o.player)}</a>
            <span class="tag" style="margin-left:6px;font-size:10px">${o.direction === "in" ? "BUYING" : "SELLING"}</span>
            <div class="small muted">${esc(o.from_club||"—")} → ${esc(o.to_club||"—")} · ${o.direction === "out" ? "you are selling" : "you are buying"}</div>
          </span>
          <b class="small"><span class="tag ${o.awaiting_you ? "ROUTINE" : ""}" style="${o.awaiting_you ? 'animation:dot-pulse 1.5s infinite' : ''}">${esc(o.status)}${o.awaiting_you ? " — YOUR MOVE" : ""}</span> ${money(o.fee)} · ${wk(o.wage)}</b>
          <span class="row" style="gap:6px;margin-left:auto">${o.direction === "out" && o.status === "counter" ? `
            <button class="btn sm primary" onclick="respondCounter(${o.id},true,${o.fee})">Accept ✓</button>
            <button class="btn sm" onclick="respondCounter(${o.id},false)">Walk away</button>
            <button class="btn sm" onclick="respondCounterNew(${o.id},${o.fee})">Re-bid ↕</button>`
            : (o.direction === "in" && o.status === "pending" ? `
            <button class="btn sm primary" onclick="bid(${o.id},'accept')">Accept ✓</button>
            <button class="btn sm" onclick="bid(${o.id},'reject')">Reject</button>` : "")}</span>
          ${o.note ? `<span class="small" style="width:100%;background:var(--sf2);padding:8px 10px;border-radius:8px;margin-top:6px;border-left:3px solid var(--amber)">💬 ${esc(o.note)}</span>` : ""}</div>`).join("")}
        </div>
      </div>` : ""}

      <div class="transfer-filters">
        <div class="sec-h"><h3>🔍 Find your next star</h3><span class="spacer"></span><span class="small muted">Showing ${players.length} of ~${money(s.cap)} budget</span></div>
        <div class="grid g2" style="gap:10px">
          <div class="row" style="gap:8px">
            <input id="tr-q" placeholder="Search name, club…" value="${esc(TR.q)}" style="flex:1;min-width:160px" oninput="TR.q=this.value;renderTransfersDebounced()">
            <select id="tr-pos" title="Position" onchange="TR.pos=this.value;renderTransfers()"><option value="">Any pos</option>${G.static.positions.map(p => `<option ${TR.pos === p ? "selected" : ""}>${p}</option>`).join("")}</select>
          </div>
          <div class="row" style="gap:8px">
            <input id="tr-fee" type="number" placeholder="Max €m" value="${TR.max_fee || ""}" style="width:90px" onchange="TR.max_fee=+this.value||0;renderTransfers()">
            <input id="tr-age" type="number" placeholder="Age ≤" value="${TR.age_max || ""}" style="width:80px" onchange="TR.age_max=+this.value||0;renderTransfers()">
            <select id="tr-sort" onchange="TR.sort=this.value;renderTransfers()"><option value="value" ${TR.sort==="value"?"selected":""}>Sort: Value</option><option value="ca" ${TR.sort==="ca"?"selected":""}>Sort: Ability</option><option value="age" ${TR.sort==="age"?"selected":""}>Sort: Age</option><option value="name" ${TR.sort==="name"?"selected":""}>Sort: Name</option></select>
            <button class="btn primary sm" onclick="doSearch()">Search 🔍</button>
          </div>
        </div>
        <div class="row" style="margin-top:10px;gap:8px">
          <select id="tr-free" title="Free agents" onchange="TR.free=this.value==='true';renderTransfers()"><option value="false" ${!TR.free ? "selected" : ""}>🏟️ Contracted</option><option value="true" ${TR.free ? "selected" : ""}>🆓 Free agents</option></select>
          <select id="tr-aff" title="Affordable" onchange="TR.aff=this.value==='true';renderTransfers()"><option value="true" ${TR.aff !== false ? "selected" : ""}>💰 Affordable only</option><option value="false" ${TR.aff === false ? "selected" : ""}>🌍 Any price</option></select>
          <span class="spacer"></span>
          <span class="small muted">💡 Tip: Loyalty matters — rivals reject, stars stay unless unsettled</span>
        </div>
      </div>

      <div class="transfer-grid">
        ${players.map(p => {
          const ini = (p.name||"?").split(" ").map(w=>w[0]).slice(0,2).join("").toUpperCase();
          const isRival = false; // could check but keep simple
          const valueColor = (p.value||0) > (j.budget||0) ? "var(--red)" : "var(--acc)";
          return `<div class="transfer-card" onclick="go('player',${p.id})">
            <div class="transfer-card-header">
              <div class="transfer-card-ava">${ini}</div>
              <div class="transfer-card-info">
                <div class="transfer-card-name">${esc(p.name)} ${p.known < 60 ? `<span class="tag" style="font-size:9px">SCOUT ${p.known}%</span>` : ""} ${shortlisted.has(p.id) ? "★" : ""}</div>
                <div class="transfer-card-meta">
                  <span><span class="pos">${esc(p.pos)}</span> ${p.age}y</span>
                  <span>${esc(p.club||"Free agent")}</span>
                  <span>${stars(p.stars||2)}</span>
                </div>
              </div>
              <div style="text-align:right">
                <div style="font-weight:900;font-size:14px;color:${valueColor}">${money(p.value)}</div>
                <div class="small muted">${wk(p.wage)}</div>
                ${p.ca ? `<div class="small" style="margin-top:2px"><span class="tag" style="font-size:10px">CA ${p.ca.toFixed(1)}</span></div>` : ""}
              </div>
            </div>
            <div class="transfer-card-stats">
              <div class="transfer-card-stat"><span class="label">Asking</span><span class="value" style="color:var(--amber)">${money(p.asking||p.value)}</span></div>
              <div class="transfer-card-stat"><span class="label">Wage</span><span class="value">${wk(p.wage)}</span></div>
              <div class="transfer-card-stat"><span class="label">Potential</span><span class="value">${p.pa ? p.pa.toFixed(1) : "?"}</span></div>
            </div>
            <div class="transfer-card-actions" onclick="event.stopPropagation()">
              <button class="btn sm primary" onclick='openOffer(${p.id}, ${JSON.stringify(p.name)}, ${p.asking || 0}, ${p.wage || 0})'>💸 Bid</button>
              <button class="btn sm" onclick="toggleShortlist(${p.id})" title="Shortlist">${shortlisted.has(p.id) ? "★ Shortlisted" : "☆ Shortlist"}</button>
              <button class="btn sm" onclick="go('player',${p.id})">Profile 👤</button>
            </div>
            ${isRival ? '<div class="rivalry-tag" style="margin-top:8px">⚠️ Rival club — hard to deal</div>' : ""}
          </div>`;
        }).join("") || `
          <div class="card" style="grid-column:1/-1;text-align:center;padding:32px">
            <div style="font-size:40px;margin-bottom:12px">🔍</div>
            <h3>No players found</h3>
            <p class="small muted" style="margin-top:6px">Try widening your search — lower max fee, any position, or check free agents. The market is huge, 9000+ players.</p>
            <button class="btn sm primary" style="margin-top:12px" onclick="TR={pos:'',q:'',max_fee:0,age_max:0,free:false,aff:false,sort:'value'};renderTransfers()">Clear filters & show all</button>
          </div>`}
      </div>
    </div>`;
}
let TR_DEBOUNCE = null;
function renderTransfersDebounced() { clearTimeout(TR_DEBOUNCE); TR_DEBOUNCE = setTimeout(renderTransfers, 400); }
function doSearch() {
  TR = { pos: $("#tr-pos").value, q: $("#tr-q").value, max_fee: +$("#tr-fee").value || 0,
         age_max: +$("#tr-age").value || 0, free: $("#tr-free").value === "true",
         aff: $("#tr-aff").value === "true" };
  renderTransfers();
}
function openOffer(pid, name, asking, wage) {
  modal(`<h2>Make an offer — ${esc(name)}</h2>
    <div class="grid g2">
      <div><label>Transfer fee (€m)</label><input id="of-fee" type="number" step="0.1" value="${Math.max(0, (asking || 0)).toFixed(1)}" style="width:100%"></div>
      <div><label>Weekly wage (€k)</label><input id="of-wage" type="number" step="0.1" value="${Math.max(0.1, (wage || 1) * 1.1).toFixed(1)}" style="width:100%"></div>
      <div><label>Contract years</label><input id="of-years" type="number" value="3" min="1" max="6" style="width:100%"></div>
      <div><label>Playing-time promise</label><select id="of-promise" style="width:100%">
        ${G.static.promises.map(p => `<option ${p === "Squad Rotation" ? "selected" : ""}>${p}</option>`).join("")}</select></div>
    </div>
    <label class="row" style="margin-top:10px"><input type="checkbox" id="of-loan"> Loan deal instead</label>
    <div class="row" style="margin-top:14px"><span class="spacer"></span>
      <button class="btn" onclick="closeModal()">Cancel</button>
      <button class="btn primary" onclick="submitOffer(${pid})">Submit offer</button></div>`);
}
async function submitOffer(pid) {
  const body = { pid, fee: +$("#of-fee").value, wage: +$("#of-wage").value, years: +$("#of-years").value,
                 promise: $("#of-promise").value, is_loan: $("#of-loan").checked };
  closeModal();
  const r = await api.post("/api/transfer/offer", body);
  toast(esc(r.msg || (r.ok ? "Offer submitted" : "Offer rejected")), 5000);
  if (G.screen === "transfers") renderTransfers();
}
async function toggleShortlist(pid) {
  const r = await api.post("/api/scout/shortlist", { pid });
  toast(r.added ? "Added to shortlist" : "Removed from shortlist", 2200);
  if (G.screen === "transfers") renderTransfers(); else if (G.screen === "scouting") renderScouting();
}
async function respondCounter(id, accept, fee) {
  const r = await api.post("/api/transfer/respond", { offer_id: id, accept });
  toast(esc(r.msg || "Done"), 5000); renderTransfers();
}
async function respondCounterNew(id, fee) {
  const v = prompt("Your new fee (€m):", (fee * 0.9).toFixed(1));
  if (!v) return;
  const r = await api.post("/api/transfer/respond", { offer_id: id, accept: false, new_fee: +v });
  toast(esc(r.msg || "Done"), 5000); renderTransfers();
}
async function bid(id, decision) {
  const r = await api.post("/api/transfer/bid", { offer_id: id, decision });
  toast(esc(r.msg || "Done"), 4500); renderTransfers();
}
async function bidCounter(id, fee) {
  const v = prompt("Counter-offer fee (€m):", (fee * 1.25).toFixed(1));
  if (!v) return;
  const r = await api.post("/api/transfer/bid", { offer_id: id, decision: "counter", counter_fee: +v });
  toast(esc(r.msg || "Done"), 4500); renderTransfers();
}

/* ----------------------------------------------------------------- SCOUTING */
async function renderScouting() {
  const j = await api.get("/api/screen/scouting");
  await refreshState();
  $("#content").innerHTML = `
    <div class="sec-h"><h3>Scouting</h3></div>
    <p class="sub">Knowledge accumulates over time. Assign scouts to regions or individual players to reduce uncertainty — estimated attributes and values come with error bars until knowledge is high.</p>
    <div class="grid g2">
      <div class="card"><h3>Scouts</h3>
        <table><thead><tr><th>Name</th><th>Role</th><th class="num">Judging</th><th class="num">Potential</th><th class="num">Wage</th></tr></thead>
        <tbody>${j.scouts.map(s => `<tr><td>${esc(s.name)}</td><td>${esc(s.role)}</td>
          <td class="num">${s.judging}</td><td class="num">${s.judging_pot}</td><td class="num small">${wk(s.wage)}</td></tr>`).join("")
          || '<tr><td colspan="5" class="muted">No scouts employed.</td></tr>'}</tbody></table>
        <div class="row" style="margin-top:10px">
          <input id="sc-region" placeholder="Region or nation, e.g. Brazil" style="flex:1">
          <button class="btn sm primary" onclick="assignRegion()">Assign scout</button>
        </div>
      </div>
      <div class="card"><h3>Knowledge by region</h3>
        ${Object.keys(j.knowledge || {}).length ? Object.entries(j.knowledge).map(([k, v]) =>
          `<div class="kv"><span>${esc(k)}</span><b>${Math.round(v)}%</b></div>${bar(v)}`).join("")
        : '<p class="muted small">No regions scouted yet.</p>'}
      </div>
    </div>
    <div class="card" style="margin-top:12px"><h3>Shortlist</h3>
      ${j.targets.length ? `<table><thead><tr><th>Name</th><th class="num">Age</th><th>Pos</th><th>Club</th>
        <th class="num">Known</th><th class="num">Value</th><th></th></tr></thead><tbody>
        ${j.targets.map(t => `<tr><td><a href="#" onclick="go('player',${t.id});return false"><b>${esc(t.name)}</b></a></td>
          <td class="num">${t.age}</td><td><span class="pos">${esc(t.pos)}</span></td><td>${esc(t.club)}</td>
          <td class="num">${Math.round(t.known || 0)}%</td><td class="num">${money(t.value)}</td>
          <td><button class="btn sm" onclick="openOffer(${t.id},'${esc(t.name).replace(/'/g, "\\'")}',${t.value},${t.wage || 1})">Bid</button></td></tr>`).join("")}
        </tbody></table>` : '<p class="muted small">No players shortlisted. Add players from the transfer search.</p>'}
    </div>
    <div class="card" style="margin-top:12px"><h3>Active offers & negotiations</h3>
      ${j.offers.length ? `<table><thead><tr><th>Player</th><th>Direction</th><th class="num">Fee</th>
        <th class="num">Wage</th><th>Status</th><th class="small">Note</th></tr></thead><tbody>
        ${j.offers.map(o => `<tr><td><b>${esc(o.player)}</b></td><td>${o.to_id === G.home.club.id ? "In" : "Out"}</td>
          <td class="num">${money(o.fee)}</td><td class="num small">${wk(o.wage)}</td>
          <td><span class="tag">${esc(o.status)}</span></td><td class="small muted">${esc(o.note || "")}</td></tr>`).join("")}
        </tbody></table>` : '<p class="muted small">No offers in progress.</p>'}
    </div>`;
}
async function assignRegion() {
  const region = $("#sc-region").value.trim();
  if (!region) return;
  const r = await api.post("/api/scout/assign", { region });
  toast(esc(r.msg || "Scout assigned")); renderScouting();
}

/* ----------------------------------------------------------------- FINANCES */
async function renderFinances() {
  const f = await api.get("/api/screen/finances");
  await refreshState();
  const c = f.club;
  $("#content").innerHTML = `
    <div class="sec-h"><h3>Finances</h3></div>
    <div class="strip">
      <div class="st"><span class="st-l">Cash</span><span class="st-v ${c.cash < 0 ? "bad" : ""}">${money(c.cash)}</span></div>
      <div class="st"><span class="st-l">Season balance</span><span class="st-v ${c.balance < 0 ? "bad" : "good"}">${money(c.balance)}</span></div>
      <div class="st"><span class="st-l">Debt</span><span class="st-v">${money(c.debt)}</span></div>
      <div class="st"><span class="st-l">Transfer budget</span><span class="st-v">${money(c.transfer_budget)}</span></div>
      <div class="st"><span class="st-l">Wage budget</span><span class="st-v small" style="font-size:13px">${money(c.wage_budget)}/yr</span></div>
    </div>
    <div class="grid g2" style="margin-top:12px">
      <div class="card"><h3>Monthly accounts</h3>
        <div class="kv"><span>Revenue</span><b>${money(f.monthly.revenue)}</b></div>
        <div class="kv"><span>Wages (players + staff)</span><b style="color:#ff9b9b">-${money(f.monthly.wages)}</b></div>
        <div class="kv"><span>Running costs</span><b style="color:#ff9b9b">-${money(f.monthly.running)}</b></div>
        <div class="kv"><span>Interest</span><b style="color:#ff9b9b">-${money(f.monthly.interest)}</b></div>
        <div class="kv" style="border-top:1px solid var(--line);margin-top:6px;padding-top:6px"><span>Net per month</span>
          <b style="color:${f.monthly.revenue - f.monthly.wages - f.monthly.running - f.monthly.interest < 0 ? "var(--bad)" : "var(--good)"}">
          ${money(f.monthly.revenue - f.monthly.wages - f.monthly.running - f.monthly.interest)}</b></div>
        <h3 style="margin-top:14px">Season</h3>
        <div class="kv"><span>Projected revenue</span><b>${money(c.season_income)}</b></div>
        <div class="kv"><span>Annual wage bill</span><b>${money(f.annual_wages)}</b></div>
        <div class="kv"><span>Projected net</span><b style="color:${f.projected_net < 0 ? "var(--bad)" : "var(--good)"}">${money(f.projected_net)}</b></div>
        <div class="kv"><span>Wage budget</span><b>${money(c.wage_budget)}</b></div>
        <div class="kv"><span>Stadium capacity</span><b>${(c.capacity || 0).toLocaleString()}</b></div>
      </div>
      <div class="card"><h3>Top earners</h3>
        <table><thead><tr><th>Name</th><th>Pos</th><th class="num">Age</th><th class="num">Wage</th><th class="num">Contract</th></tr></thead>
        <tbody>${f.top_earners.map(p => `<tr><td>${esc(p.name)}</td><td><span class="pos">${esc(p.pos)}</span></td>
          <td class="num">${p.age}</td><td class="num small">${wk(p.wage)}</td><td class="num small">${esc(p.contract_end)}</td></tr>`).join("")}</tbody></table>
        <div class="kv" style="margin-top:10px"><span>Gate receipts booked this season</span><b>${money(f.matchday_income || 0)}</b></div>
      </div>
    </div>
    <div class="card" style="margin-top:12px"><h3>Ledger — last ${(f.history || []).length} months</h3>
      ${cashSpark(f.history || [])}
      ${(f.history || []).length ? `<table style="margin-top:10px"><thead><tr><th>Month</th>
        <th class="num">Revenue</th><th class="num">Wages</th><th class="num">Running</th>
        <th class="num">Interest</th><th class="num">Net</th><th class="num">Cash</th></tr></thead>
        <tbody>${f.history.slice().reverse().map(h => `<tr><td>${esc(h.month)}</td>
          <td class="num">${money(h.income)}</td><td class="num" style="color:#ff9b9b">-${money(h.wages)}</td>
          <td class="num" style="color:#ff9b9b">-${money(h.other)}</td>
          <td class="num" style="color:#ff9b9b">-${money(h.interest || 0)}</td>
          <td class="num" style="color:${h.net < 0 ? "var(--bad)" : "var(--good)"}">${h.net >= 0 ? "+" : ""}${money(h.net)}</td>
          <td class="num">${money(h.cash)}</td></tr>`).join("")}</tbody></table>`
        : '<p class="muted small">No accounts yet — the first statement arrives on the 1st of next month.</p>'}
    </div>`;
}
function cashSpark(hist) {
  if (!hist || hist.length < 2) return "";
  const w = 720, h = 64, pad = 4;
  const vals = hist.map(x => x.cash);
  const min = Math.min(...vals), max = Math.max(...vals);
  const span = (max - min) || 1;
  const pts = vals.map((v, i) => {
    const x = pad + (w - pad * 2) * (i / (vals.length - 1));
    const y = h - pad - (h - pad * 2) * ((v - min) / span);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
  return `<svg viewBox="0 0 ${w} ${h}" style="width:100%;height:${h}px" preserveAspectRatio="none">
    <polyline points="${pts}" fill="none" stroke="#39d98a" stroke-width="2"/>
    <text x="${pad}" y="12" fill="#8a93a6" font-size="10">cash ${money(max)} … ${money(min)}</text></svg>`;
}

/* -------------------------------------------------------------------- STAFF */
function staffAbbr(role) {
  const r = role || "";
  if (/Assistant/.test(r)) return "AM";
  if (/Chief/.test(r)) return "CS";
  if (/Scout/.test(r)) return "SC";
  if (/Physio|Medical/.test(r)) return "PH";
  if (/Coach/.test(r)) return "CO";
  return "ST";
}
function staffKey(s) {
  const r = s.role || "";
  if (/Scout/.test(r)) return [["judge", Math.round(s.judging || 0)], ["pot", Math.round(s.judging_pot || 0)]];
  if (/Physio|Medical/.test(r)) return [["fit", Math.round(s.fitness || 0)], ["men", Math.round(s.mental || 0)]];
  return [["att", Math.round(s.attacking || 0)], ["tac", Math.round(s.tactical || 0)], ["fit", Math.round(s.fitness || 0)]];
}
async function renderStaff() {
  const j = await api.get("/api/screen/staff");
  await refreshState();
  $("#content").innerHTML = `
    <div class="sec-h"><h3>Backroom staff</h3><span class="spacer"></span>
      <span class="hint">${j.length} staff · wages ${money(j.reduce((a, b) => a + (b.wage || 0) * 52 / 1000, 0))}/yr</span></div>
    <p class="small muted">Coaching drives training gains · scouting drives knowledge · physios cut injury time.</p>
    <div class="sq-list" style="margin-top:10px;display:flex">
      ${j.map(s => `<div class="sqr" style="cursor:default;flex-wrap:wrap">
        <span class="tag">${staffAbbr(s.role)}</span>
        <span class="sqr-n"><b>${esc(s.name)}</b><i>${esc(s.role)} · ${esc(s.nat)} · ${s.age}y</i></span>
        <span class="sqr-r"><span class="small muted">${wk(s.wage)}</span></span>
        <span class="stf-k">${staffKey(s).map(([k, v]) => `${k} <b>${v}</b>`).join(" · ")}</span>
      </div>`).join("")}
    </div>`;
}
/* -------------------------------------------------------------------- YOUTH */
async function renderYouth() {
  const j = await api.get("/api/screen/youth");
  await refreshState();
  $("#content").innerHTML = `
    <div class="sec-h"><h3>Academy</h3><span class="spacer"></span>
      <span class="hint">recruitment ${j.rating}/20 · facilities ${j.facilities}/20</span></div>
    <p class="small muted">A new intake signs each summer; best prospects first.</p>
    <div class="sq-list" style="margin-top:10px;display:flex">
      ${j.players.map(p => `<button class="sqr" onclick="go('player',${p.id})">
        <span class="pos">${esc(p.pos)}</span>
        <span class="sqr-n"><b>${esc(p.name)}</b><i>${p.age}y · ${esc(p.personality)} · CA ${p.ca.toFixed(1)} / PA ${p.pa.toFixed(1)}</i></span>
        <span class="sqr-r"><span class="small muted">now</span> ${stars(p.stars)}
          <span class="small muted">pot</span> ${stars(p.stars_pa)}</span>
      </button>`).join("") || '<p class="muted small" style="padding:12px">No youth players yet.</p>'}
    </div>`;
}
async function renderCalendar() {
  const j = await api.get("/api/screen/calendar");
  await refreshState();
  const nextDate = (G.home.next_fixture || {}).date;
  $("#content").innerHTML = `
    <div class="sec-h"><h3>Calendar</h3><span class="spacer"></span><span class="hint">season ${G.home.season_label}</span></div>
    <div class="sq-list" style="display:flex">
      ${j.fixtures.map(f => {
        const next = !f.played && f.date === nextDate;
        return `<div class="fxr ${next ? "next" : ""} ${compClass(f.code)}">
          <span class="fx-d"><b>${fmtDate(f.date).replace(/, \d{4}$/, "")}</b><i>${compLogo(f.code)} ${esc(compLabel(f))}${f.stage && f.stage !== "league" && f.comp ? " · " + esc(f.stage) : ""}</i></span>
          <span class="fx-m">${crest(f.home_code)}<b>${esc(f.home_short || f.home)}</b>
            <span class="fx-s">${f.played ? (f.hg != null ? f.hg + "–" + f.aw : "—") : "v"}</span>
            <b>${esc(f.away_short || f.away)}</b>${crest(f.away_code)}</span>
          <span class="fx-r">${f.res ? `<span class="tag ${f.res}">${f.res}</span>` : next ? '<span class="tag NEW">next</span>' : ""}</span>
        </div>`;
      }).join("")}
    </div>`;
}
/* -------------------------------------------------------------------- TABLE */
async function renderTable() {
  const j = await api.get("/api/screen/table");
  await refreshState();
  if (!j.comp) { $("#content").innerHTML = "<h1>League</h1><p class='muted'>No league.</p>"; return; }
  $("#content").innerHTML = `
    <div class="sec-h"><h3>${esc(j.comp.name)}</h3><span class="spacer"></span><span class="hint">${G.home.season_label} · ${j.prom_spots} up / ${j.rel_spots} down</span></div>
    <div class="card" style="padding:0;overflow:auto">
      <table class="mc"><thead><tr><th class="num">#</th><th>Club</th><th class="num">P</th><th class="num">W</th>
        <th class="num">D</th><th class="num">L</th><th class="num">GF</th><th class="num">GA</th>
        <th class="num">GD</th><th class="num">Pts</th><th>Form</th></tr></thead>
      <tbody>${j.rows.map(r => `<tr class="${r.club_id === j.my_club ? "me" : ""} ${r.zone === "promotion" ? "zp" : r.zone === "relegation" ? "zr" : ""}">
        <td class="num">${r.pos || "–"}${r.zone === "promotion" ? ' <span style="color:var(--good)">▲</span>' : r.zone === "relegation" ? ' <span style="color:var(--bad)">▼</span>' : ""}</td>
        <td><span class="cellclub">${crest(r.code)}<span>${esc(r.name)} <i class="muted small">${r.rep}</i></span></span></td>
        <td class="num">${r.p}</td><td class="num">${r.w}</td><td class="num">${r.d}</td><td class="num">${r.l}</td>
        <td class="num">${r.gf}</td><td class="num">${r.ga}</td>
        <td class="num">${r.gf - r.ga > 0 ? "+" : ""}${r.gf - r.ga}</td><td class="num"><b>${r.pts}</b></td>
        <td><span class="frm">${(r.form || "").split("").map(x => `<i class="fm-i ${x}">${x}</i>`).join("")}</span></td></tr>`).join("")}</tbody></table>
    </div>
      <div class="small muted" style="padding:8px 12px;display:flex;gap:14px">
        <span><i class="zdot zp"></i>promotion</span><span><i class="zdot zr"></i>relegation</span>
        <span class="spacer"></span><span>${j.prom_spots} up · ${j.rel_spots} down</span></div>
    `;
}

/* -------------------------------------------------------------------- COMPS */
function compMono(code) {
  const m = { UCL: "UCL", UEL: "UEL", UECL: "UECL", ENG1: "PL", ESP1: "LaL", ITA1: "SA",
    GER1: "BL", FRA1: "L1", FACUP: "FA", EFLCUP: "EFL", COPADELREY: "CdR", COPPAITALIA: "CI",
    DFBPOKAL: "DFB", COUPEDEFRANCE: "CdF" };
  if (m[code]) return m[code];
  return String(code || "?").slice(0, 3);
}
function compBand(c, right) {
  const logo = compLogo(c.code, "lg");
  return `<div class="comp-band" style="--comp:${compColor(c.code)}">
    ${logo}
    <span style="min-width:0"><b>${esc(c.name)}</b><br><span class="sub">${esc(c.ctype === "continental" ? "Europe" : c.ctype === "cup" ? "Knockout cup" : "League")}${c.tier ? " · tier " + c.tier : ""}</span></span>
    <span class="spacer"></span>${right || ""}</div>`;
}
async function renderComps() {
  const j = await api.get("/api/screen/comps");
  await refreshState();
  const my = G.home && G.home.club ? G.home.club.id : 0;
  $("#content").innerHTML = `
    <div class="sec-h"><h3>Competitions</h3><span class="spacer"></span><span class="hint">season ${G.home ? G.home.season_label : ""}</span></div>
    <div style="display:grid;gap:8px">
    ${j.comps.map(c => {
      let status = "";
      if (c.table && c.table.length) {
        const r = c.table.find(x => x.club_id === my);
        status = r && r.pos ? `<span class="tag">${r.pos}${ord(r.pos)}</span>` : "";
      } else status = '<span class="tag">KO</span>';
      return `<button class="comp-head" style="text-align:left;width:100%" onclick="renderCompHub(${c.comp.id})">
        ${compBand(c.comp, status + '<span class="muted" style="font-size:16px"> ▸</span>')}</button>`;
    }).join("")}
    </div>`;
}
function ord(n) {
  if (n % 100 >= 11 && n % 100 <= 13) return "th";
  return ["th", "st", "nd", "rd"][n % 10] || "th";
}
async function renderCompHub(id) {
  const j = await api.get("/api/screen/comp?id=" + id);
  if (!j || j.error) { toast("Competition not found"); return; }
  const k = j.comp, my = G.home && G.home.club ? G.home.club.id : 0;
  const tbl = j.table || [];
  const me = tbl.find(r => r.club_id === my);
  const played = j.fixtures.filter(f => f.played), todo = j.fixtures.filter(f => !f.played);
  const rowHtml = r => `<tr class="${r.club_id === my ? "me" : ""} ${r.zone === "promotion" ? "zp" : r.zone === "relegation" ? "zr" : ""}">
      <td class="num muted">${r.pos || "–"}</td>
      <td><span class="cellclub">${crest(r.code)}<span>${esc(r.name)}</span></span></td>
      <td class="num">${r.p}</td><td class="num">${r.w}</td><td class="num">${r.d}</td><td class="num">${r.l}</td>
      <td class="num">${r.gf - r.ga > 0 ? "+" : ""}${r.gf - r.ga}</td><td class="num"><b>${r.pts}</b></td></tr>`;
  const fxRow = f => {
    const myW = f.played && ((f.home_id === my && f.hg > f.ag) || (f.away_id === my && f.ag > f.hg));
    const myD = f.played && f.hg === f.ag;
    return `<div class="kv"><span class="cellclub" style="flex:1;min-width:0">${f.played
      ? `<span class="tag ${myW ? "W" : myD ? "D" : "L"}">${f.hg}–${f.ag}</span>`
      : `<span class="muted small">${fmtDate(f.date)}</span>`}
      <span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${crest(f.home_code)}&nbsp;${esc(f.home_short || f.home)} v ${esc(f.away_short || f.away)}&nbsp;${crest(f.away_code)}</span></span>
      <b class="small muted">${f.stage !== "league" ? esc(f.stage) : ""}</b></div>`;
  };
  $("#content").innerHTML = `
    <button class="btn sm" onclick="renderComps()" style="margin-bottom:10px">◂ All competitions</button>
    <div class="comp-head">${compBand(k, me && me.pos ? `<span class="tag">${me.pos}${ord(me.pos)}</span>` : "")}</div>
    ${tbl.length ? `<div class="card tight" style="padding:0;margin-top:10px">
      <div class="sec-h" style="padding:10px 12px 4px"><h3>${k.ctype === "continental" ? "League phase" : "Standings"}</h3>
        <span class="spacer"></span>${k.code === (G.home.club && G.home.club.league_code) ? '<button class="btn sm" onclick="go(\'table\')">Full</button>' : ""}</div>
      <div class="tw"><table class="mc mh"><thead><tr><th class="num">#</th><th>Club</th><th class="num">P</th><th class="num">W</th>
        <th class="num">D</th><th class="num">L</th><th class="num">GD</th><th class="num">Pts</th></tr></thead>
        <tbody>${tbl.map(rowHtml).join("")}</tbody></table></div>
    </div>` : ""}
    ${(j.ko || []).length ? `<div class="card tight" style="margin-top:10px">
      <div class="sec-h"><h3>Knockout progression</h3></div>
      <div class="brk">${j.ko.map(r => `<div class="brk-r">
        <div class="stat-l">${esc(r.stage === "F" ? "Final" : r.stage === "SF" ? "Semi-finals" : r.stage === "QF" ? "Quarter-finals" : r.stage === "R16" ? "Round of 16" : r.stage === "R32" ? "Round of 32" : r.stage)}</div>
        ${r.ties.map(t => {
          const hw = t.played && t.hg > t.ag, aw = t.played && t.ag > t.hg;
          return `<div class="brk-m"><span class="${hw ? "w" : ""}">${crest(t.home_code)} ${esc(t.home_short || t.home)}</span>
            <span class="sc">${t.played ? t.hg + "–" + t.ag : fmtDate(t.date)}</span>
            <span class="${aw ? "w" : ""}" style="text-align:right">${esc(t.away_short || t.away)} ${crest(t.away_code)}</span></div>`;
        }).join("")}</div>`).join("")}</div>
    </div>` : ""}
    <div class="grid g2" style="margin-top:10px">
      <div class="card tight">
        <div class="sec-h"><h3>Results</h3></div>
        ${played.length ? played.slice().reverse().slice(0, 8).map(fxRow).join("") : '<p class="muted small">No results yet.</p>'}
      </div>
      <div class="card tight">
        <div class="sec-h"><h3>Fixtures</h3></div>
        ${todo.length ? todo.slice(0, 8).map(fxRow).join("") : '<p class="muted small">No fixtures left.</p>'}
      </div>
    </div>`;
}
async function renderClub() {
  await refreshState();
  const c = G.home.club;
  $("#content").innerHTML = `
    <div class="card tight">
      <div class="p-head">${crest(c.code, "xl")}
        <div style="min-width:0"><h2>${esc(c.name)}</h2>
          <p class="small muted">${esc(c.league)} · tier ${c.tier} · reputation ${c.rep}</p></div>
      </div>
      <div class="divider"></div>
      <div class="kv"><span>Stadium</span><b>${esc(c.stadium)}</b></div>
      <div class="kv"><span>Capacity</span><b>${(c.capacity || 0).toLocaleString()}</b></div>
      <div class="kv"><span>Season</span><b>${G.home.season_label}</b></div>
    </div>
    <div class="grid g2" style="margin-top:10px">
      ${[["board", "Board & objectives", "Confidence, warnings and what the hierarchy expects."],
         ["media", "Media", "Press conferences and headlines."],
         ["staff", "Backroom staff", "Coaches, scouts, medical — roles and wages."],
         ["youth", "Academy", "Intake, prospects and development."],
         ["career", "Career & trophies", "Your record, honours and history."],
         ["finances", "Finances", "Budgets, wages, commercial and matchday."]]
        .map(([id, t, d]) => `<button class="card tight" style="text-align:left" onclick="go('${id}')">
          <div class="row" style="gap:8px">${svg(id)}<b style="font-size:13.5px">${t}</b></div>
          <p class="small muted" style="margin-top:4px">${d}</p></button>`).join("")}
    </div>`;
}
/* -------------------------------------------------------------------- BOARD */
async function renderBoard() {
  const j = await api.get("/api/screen/board");
  await refreshState();
  if (j.unemployed) return renderJobs();
  $("#content").innerHTML = `
    <div class="sec-h"><h3>Board</h3></div>
    <p class="sub">Job security: <b>${esc(j.job_security)}</b></p>
    <div class="grid g2">
      <div class="card"><h3>Confidence</h3>
        <div class="stat">${Math.round(j.confidence)}<span class="muted" style="font-size:14px">/100</span></div>
        ${bar(j.confidence, j.confidence < 30 ? "red" : j.confidence < 55 ? "amber" : "")}
        <div class="kv" style="margin-top:10px"><span>Chairman</span><b>${esc(j.chairman)}</b></div>
        <div class="kv"><span>Board patience</span><b>${j.patience}</b></div>
        <div class="kv"><span>Club vision</span><b>${esc(j.vision)}</b></div>
        ${j.warning ? '<div class="card tight" style="margin-top:10px;border-color:#6b2b2b"><b style="color:var(--bad)">You are on an official warning.</b></div>' : ""}
        ${j.sack_risk > 0 ? `<div class="small muted" style="margin-top:8px">Sack risk: ${Math.round(j.sack_risk)}</div>` : ""}
      </div>
      <div class="card"><h3>Fans & media</h3>
        <div class="kv"><span>Fan sentiment</span><b>${Math.round(j.fans.sentiment)}</b></div>${bar(j.fans.sentiment)}
        <div class="kv" style="margin-top:8px"><span>Support level</span><b>${Math.round(j.fans.support)}</b></div>${bar(j.fans.support)}
        <div class="kv" style="margin-top:8px"><span>Media pressure</span><b>${Math.round(j.media.pressure || 0)}</b></div>${bar(j.media.pressure || 0, "amber")}
        <div class="kv" style="margin-top:8px"><span>Narrative</span><b>${esc(j.media.narrative || "—")}</b></div>
      </div>
    </div>
    <div class="card" style="margin-top:12px"><h3>Objectives</h3>
      ${j.objectives.map(o => `<div class="obj"><div class="t">${esc(o.text)} ${o.critical ? '<span class="tag URGENT">CRITICAL</span>' : ""}</div>
        <div class="small muted">${esc(o.comp || "")} ${o.target_pos ? "· target " + o.target_pos + "th place" : ""} · ${esc(o.status)}</div></div>`).join("")}
    </div>
    <div class="card" style="margin-top:12px"><h3>Position</h3>
      ${j.position ? `<div class="kv"><span>League</span><b>${j.position.pos} of ${j.position.size}</b></div>
        <div class="kv"><span>Points</span><b>${j.position.pts} from ${j.position.played}</b></div>
        <div class="kv"><span>Goal difference</span><b>${j.position.gd > 0 ? "+" : ""}${j.position.gd}</b></div>`
      : '<p class="muted small">No league record yet.</p>'}
    </div>
    <div class="row" style="margin-top:12px">
      <button class="btn danger" onclick="resignJob()">Resign from the club</button>
    </div>`;
}
async function resignJob() {
  if (!confirm("Resign? You will become unemployed and must find a new job.")) return;
  const r = await api.post("/api/career/resign", {});
  toast(esc(r.msg || "Resigned")); await refreshState(); go("jobs");
}

/* -------------------------------------------------------------------- MEDIA */
async function renderMedia() {
  const j = await api.get("/api/screen/media");
  await refreshState();
  const h = G.home;
  const f = h ? h.next_fixture : null;
  const rivalry = f ? isRivalry(f.home_code, f.away_code) : null;
  $("#content").innerHTML = `
    <div class="sec-h"><h3>Media Centre — press conferences & hype</h3></div>
    <div class="strip">
      <div class="st"><span class="st-l">Narrative</span><span class="st-v small" style="font-size:13px">${esc(j.narrative || "—")}</span></div>
      <div class="st"><span class="st-l">Pressure</span><span class="st-v">${Math.round(j.pressure || 0)}<i>/100</i></span>${bar(j.pressure||0, (j.pressure||0)>70 ? "red" : (j.pressure||0)>40 ? "amber" : "")}</div>
      <div class="st"><span class="st-l">Board</span><span class="st-v">${Math.round(h ? h.board.confidence : 0)}</span></div>
      <div class="st"><span class="st-l">Fans</span><span class="st-v">${Math.round(h ? h.fans.sentiment : 0)}</span></div>
    </div>

    ${f ? `<div class="card" style="margin-bottom:12px;background:linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);border-color:#0f3460;box-shadow:0 8px 32px rgba(0,0,0,.4)">
      <div class="sec-h"><h3 style="color:#e94560">🎤 Pre-match press conference — ${esc(f.home)} vs ${esc(f.away)}</h3><span class="spacer"></span><span class="tag" style="background:#0f3460;color:#7fb2ff">${esc(compLabel(f))}</span></div>
      ${rivalry ? `<div class="derby-banner" style="border-radius:10px;margin-bottom:12px">🔥 ${esc(rivalry.name.toUpperCase())} — PRESS ROOM PACKED — EVERY WORD MATTERS 🔥</div>` : ""}
      <div class="pre" style="background:rgba(0,0,0,.25);border-color:#0f3460;color:#cbd5e0;font-style:italic">
        Reporter: "${rivalry ? `This ${esc(rivalry.name)} means everything to the fans. How do you handle that pressure?` : f.code === "UCL" ? "Champions League nights are special — what's your message to the fans?" : `Next up: ${esc(f.away)} away. Tough place to go. How do you approach it?`}"
      </div>
      <p class="small" style="margin-top:10px;color:#9aa8bd">Your answer affects board confidence, fan sentiment, and player morale. Choose wisely — media twists everything.</p>
      <div class="grid g2" style="margin-top:12px;gap:8px">
        <button class="btn primary" onclick="press('confident')">💪 “We fear no one — we’ll win”<br><span class="small" style="font-weight:500;opacity:.8">Fans +++, Board ++, Pressure +</span></button>
        <button class="btn" onclick="press('balanced')">⚖️ “Respect the opponent, focus on us”<br><span class="small muted">Balanced — safe option</span></button>
        <button class="btn" onclick="press('defensive')">🛡️ “We’ll set up to be solid”<br><span class="small muted">Board ++ if underdog, Fans -</span></button>
        <button class="btn danger" onclick="press('critical')">🔥 “Some players need to step up”<br><span class="small muted">High risk — can fire up or destroy morale</span></button>
      </div>
    </div>` : `<div class="card" style="margin-bottom:12px"><h3>Press conference</h3>
      <p class="small muted">No upcoming match — press room quiet. When you have a fixture, hype builds here with rivalry context and meaningful choices.</p>
      <div class="row" style="margin-top:10px">
        <button class="btn" onclick="press('confident')">Back the players publicly</button>
        <button class="btn" onclick="press('balanced')">Stay balanced</button>
        <button class="btn" onclick="press('defensive')">Deflect questions</button>
        <button class="btn danger" onclick="press('critical')">Be critical</button>
      </div>
    </div>`}

    <div class="card tight" style="padding:0">
      <div class="sec-h" style="padding:14px 16px 8px"><h3>🌍 World news feed — living world</h3><span class="spacer"></span><span class="small muted">Other clubs buy, sell, sack managers</span></div>
      <div style="max-height:62vh;overflow:auto">
      ${j.news.map(n => {
        const isTransfer = (n.cat||"").toLowerCase().includes("transfer") || (n.text||"").toLowerCase().includes("joins") || (n.text||"").toLowerCase().includes("signs");
        const icon = isTransfer ? "💸" : (n.cat||"").includes("MANAGER") ? "👔" : "📰";
        return `<div class="mrow slim" style="cursor:default;min-height:56px">
          <div style="width:32px;height:32px;border-radius:10px;background:linear-gradient(135deg, var(--sf3), var(--sf2));display:grid;place-items:center;font-size:14px;flex:none">${icon}</div>
          <div class="mmain"><div class="msub" style="white-space:normal;font-size:13.5px;line-height:1.4">${esc(n.text).replace("for €0k on loan", "on loan")}</div>
          <div class="mmeta"><span class="mcat">${esc(n.cat)}</span><span>${fmtDate(n.date)}</span></div></div></div>`;
      }).join("") || '<div class="inbox-empty" style="padding:24px"><div class="small muted">No news yet — world is just starting</div></div>'}
      </div>
    </div>`;
}
async function press(answer) {
  const r = await api.post("/api/media/press", { answer });
  toast(`Board ${r.board} · Fans ${r.fans} · Media pressure ${r.media_pressure}`, 4500);
  renderMedia();
}

/* ------------------------------------------------------------------- CAREER */
async function renderCareer() {
  const j = await api.get("/api/screen/career");
  await refreshState();
  $("#content").innerHTML = `
    <div class="sec-h"><h3>Career</h3></div>
    <p class="sub">${esc(j.manager.name)} · ${esc(j.manager.nat)} · reputation ${j.reputation}/95 · ${esc(j.difficulty)} difficulty</p>
    <div class="strip">
      <div class="st"><span class="st-l">Club</span><span class="st-v small" style="font-size:14px">${j.club ? esc(j.club.name) : "Unemployed"}</span>
        <div class="small muted">${j.club ? esc(j.club.league) : "available"}</div></div>
      <div class="st"><span class="st-l">Trophies</span><span class="st-v">${j.trophies.length}</span>
        <div class="small muted">${j.trophies.slice(0, 2).map(t => esc(t.comp)).join(", ") || "none yet"}</div></div>
      <div class="st"><span class="st-l">Seasons</span><span class="st-v">${j.season - 2026 + 1}</span>
        <div class="small muted">since ${fmtDate(j.created)}</div></div>
      <div class="st"><span class="st-l">Reputation</span><span class="st-v">${j.reputation}</span>
        <div class="small muted">of 95</div></div>
    </div>
    <div class="grid g2" style="margin-top:12px">
      <div class="card"><h3>Club history</h3>
        <table><thead><tr><th>Club</th><th>From</th><th>To</th><th>Reason</th></tr></thead>
        <tbody>${j.clubs.map(c => `<tr><td><b>${esc(c.name)}</b></td><td>${fmtDate(c.from)}</td>
          <td>${c.to ? fmtDate(c.to) : "—"}</td><td class="small muted">${esc(c.reason || "")}</td></tr>`).join("")}</tbody></table>
        ${j.unemployed ? `<div class="row" style="margin-top:10px"><button class="btn primary" onclick="go('jobs')">Find a job</button></div>` : ""}
      </div>
      <div class="card"><h3>Trophy room</h3>
        ${j.trophies.length ? j.trophies.map(t => `<div class="obj"><div class="t" style="color:var(--gold);display:flex;align-items:center;gap:6px"><span class="icn">${svg("table")}</span>${esc(t.comp)}</div>
          <div class="small muted">${t.season}/${String(t.season + 1).slice(2)} · ${esc(t.type || "")}</div></div>`).join("")
        : '<p class="muted small">No trophies yet.</p>'}
      </div>
    </div>
    <div class="card" style="margin-top:12px"><h3>Season-by-season record</h3>
      <table><thead><tr><th class="num">Season</th><th>Competition</th><th>Club</th><th class="num">Pos</th><th>Note</th></tr></thead>
      <tbody>${j.history.map(h => `<tr><td class="num">${h.season}</td><td>${esc(h.comp || "")}</td>
        <td>${esc(h.club || "")}</td><td class="num">${h.pos || ""}</td><td class="small">${esc(h.note || "")}
        ${h.trophy ? ` <span class="icn" style="color:var(--gold)">${svg("table")}</span>` : ""}</td></tr>`).join("")
        || '<tr><td colspan="5" class="muted">No history yet.</td></tr>'}</tbody></table>
    </div>
    <div class="card" style="margin-top:12px;border-color:#5b2b2b">
      <h3 style="color:var(--bad)">Danger zone</h3>
      <p class="small muted">Starting a new career rebuilds the world and permanently replaces this save.</p>
      <button class="btn danger" onclick="confirmNewCareer()">Start a new career</button>
    </div>`;
}
function confirmNewCareer() {
  modal(`<h2>Start a new career?</h2>
    <p class="sub">Your current career — every season, trophy and record in this save — will be
    permanently deleted. The world is rebuilt from scratch.</p>
    <div class="row"><button class="btn danger" onclick="doResetCareer()">Yes, erase and start over</button>
    <button class="btn" onclick="closeModal()">Cancel</button></div>`);
}
async function doResetCareer() {
  closeModal(); setBusy(true);
  try {
    await api.post("/api/career/reset", {});
    G.home = null; G.boot.has_save = false; G.pendingMatch = false;
    $("#crest").textContent = "TL";
    showStartScreen();
    toast("Save erased. Build a new career.");
  } catch (e) { toast("Reset failed: " + esc(e.message), 6000); }
  setBusy(false);
}

/* --------------------------------------------------------------------- JOBS */
async function renderJobs() {
  const j = await api.get("/api/career/jobs");
  await refreshState();
  $("#content").innerHTML = `
    <div class="sec-h"><h3>Job market</h3><span class="spacer"></span><span class="hint">unemployed</span></div>
    <p class="small muted">Offers arrive in your inbox, or apply directly — reputation decides who says yes.</p>
    ${j.offers.length ? `<div class="card" style="margin-bottom:12px;border-color:#1d5a45"><h3>Offers received</h3>
      ${j.offers.map(o => `<div class="list-item"><div style="flex:1"><b>${esc(o.name)}</b>
        <div class="small muted">${esc(o.league)} · tier ${o.tier} · rep ${Math.round(o.rep)} · offered ${fmtDate(o.date)}</div></div>
        <button class="btn primary sm" onclick="acceptJob(${o.club_id})">Accept</button></div>`).join("")}</div>` : ""}
    <div class="sq-list" style="margin-top:10px;display:flex">
      ${j.jobs.map(v => `<div class="sqr" style="cursor:default">
        <span class="tag">T${v.tier}</span>
        <span class="sqr-n"><b>${esc(v.name)}</b><i>${esc(v.league)} · rep ${Math.round(v.rep)} · ${money(v.season_income || 0)}/yr</i></span>
        <span class="sqr-r"><span class="tag ${v.interest === "high" ? "W" : v.interest === "medium" ? "D" : "L"}">${esc(v.interest)}</span>
          <b class="small">${Math.round(v.chance * 100)}%</b>
          <button class="btn sm" onclick="acceptJob(${v.id})">Apply</button></span>
      </div>`).join("") || '<p class="muted small" style="padding:12px">No vacancies right now. Keep advancing time.</p>'}
    </div>
    <div class="row" style="margin-top:12px"><button class="btn primary" onclick="doContinue()">Advance time ▸</button></div>`;
}
async function acceptJob(clubId) {
  const r = await api.post("/api/career/apply", { club_id: clubId });
  toast(esc(r.msg || (r.ok ? "Appointed!" : "Rejected")), 5000);
  if (r.ok) { await refreshState(); go("home"); }
}

/* -------------------------------------------------------------- global keys */
document.addEventListener("keydown", e => {
  if (e.key === "Escape") closeModal();
  if (e.key === " " && !$("#modal").classList.contains("open") &&
      !["INPUT", "SELECT", "TEXTAREA"].includes(document.activeElement.tagName)) {
    e.preventDefault(); doContinue();
  }
});

boot();

/* ================================================================
   GAME SHELL — icons, bottom tab bar, "more" sheet, mobile tables
   ================================================================ */
const ICONS = {
  home: '<path d="M3 10.5 12 3l9 7.5"/><path d="M5.5 9.5V20a1 1 0 0 0 1 1H10v-6h4v6h3.5a1 1 0 0 0 1-1V9.5"/>',
  inbox: '<path d="M3 13h4l2 3h6l2-3h4"/><path d="M5 5h14l2 8v6H3v-6z"/>',
  squad: '<circle cx="9" cy="8" r="3.2"/><path d="M3.5 20c.6-3.6 2.8-5.5 5.5-5.5S13.9 16.4 14.5 20"/><circle cx="17" cy="9" r="2.6"/><path d="M15.5 14.8c2.6.2 4.4 1.9 5 5.2"/>',
  tactics: '<rect x="4" y="3" width="16" height="18" rx="2"/><path d="M8 3v4M16 3v4M8 21v-3M16 21v-3"/><circle cx="9.5" cy="12" r="1.4"/><circle cx="14.5" cy="15.5" r="1.4"/><path d="M9.5 12l5 3.5"/>',
  training: '<path d="M4 9v6M7 7v10M17 7v10M20 9v6M7 12h10"/>',
  match: '<circle cx="12" cy="12" r="9"/><path d="M12 7.5l4 3-1.5 4.6h-5L8 10.5z"/><path d="M12 3v4.5M4 9.5l4 1M20 9.5l-4 1M7 19.5l2.5-4.4M17 19.5l-2.5-4.4"/>',
  transfers: '<path d="M4 8h13l-3-3M20 16H7l3 3"/>',
  scouting: '<circle cx="10.5" cy="10.5" r="6"/><path d="M15 15l5.5 5.5"/><path d="M10.5 7.5v6M7.5 10.5h6"/>',
  finances: '<path d="M3 9.5 12 4l9 5.5"/><path d="M5 10v8M9.5 10v8M14.5 10v8M19 10v8M3 20h18"/>',
  staff: '<rect x="3" y="7" width="18" height="13" rx="2"/><path d="M9 7V5a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2M3 12h18"/><circle cx="12" cy="15" r="1.6"/>',
  youth: '<path d="M12 21v-8"/><path d="M12 13c0-4 3-7 7-7 0 4-3 7-7 7z"/><path d="M12 16c0-3-2.5-5-5.5-5 0 3 2.5 5 5.5 5z"/>',
  calendar: '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M8 3v4M16 3v4M3 10h18"/><path d="M8 14h3M8 17.5h6"/>',
  table: '<path d="M8 4h8v5a4 4 0 0 1-8 0z"/><path d="M8 5H5a3 3 0 0 0 3 4M16 5h3a3 3 0 0 1-3 4"/><path d="M12 13v4M9 20h6M10 17h4"/>',
  comps: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c2.6 2.6 3.8 5.6 3.8 9S14.6 18.4 12 21c-2.6-2.6-3.8-5.6-3.8-9S9.4 5.6 12 3z"/>',
  board: '<circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="4.5"/><circle cx="12" cy="12" r="1"/>',
  media: '<rect x="3" y="5" width="15" height="15" rx="2"/><path d="M18 9h3v9a2 2 0 0 1-2 2H5"/><path d="M6.5 9h8M6.5 12.5h8M6.5 16h5"/>',
  career: '<path d="M4 20V6M4 20h16"/><path d="M7 16l4-5 3 3 5-7"/><path d="M16 7h3v3"/>',
  more: '<circle cx="6" cy="12" r="1.6"/><circle cx="12" cy="12" r="1.6"/><circle cx="18" cy="12" r="1.6"/>',
  club: '<path d="M4 20V9l4-3 4 3 4-3 4 3v11"/><path d="M4 20h16"/><path d="M9 20v-5h6v5"/><path d="M12 6V3"/>',
};
function svg(id) {
  return `<svg class="ic" viewBox="0 0 24 24" aria-hidden="true">${ICONS[id] || ICONS.more}</svg>`;
}
const TAB_IDS = ["home", "inbox", "squad", "match", "comps"];

const TAB_LABEL = { home: "Home", inbox: "News", squad: "Squad", match: "Match", comps: "Comps" };
const TAB_ICON_EMOJI = { home: "🏠", inbox: "📰", squad: "👥", match: "⚽", comps: "🏆" };
function renderTabbar(items) {
  const el = $("#tabbar"); if (!el) return;
  const tabs = TAB_IDS.map(id => items.find(i => i[0] === id)).filter(Boolean);
  // Floating dock game style
  el.innerHTML = `<div class="dock">${tabs.map(n =>
    `<button data-s="${n[0]}" onclick="Juice.haptic('tap');go('${n[0]}')"><span style="font-size:18px">${TAB_ICON_EMOJI[n[0]]||""}</span><span>${TAB_LABEL[n[0]] || n[2].split(" ")[0]}</span>` +
    `<span class="tbadge hidden" data-badge="${n[0]}"></span></button>`).join("") +
    `<button data-s="__more" onclick="Juice.haptic('tap');openSheet()"><span style="font-size:18px">⋯</span><span>More</span></button></div>`;
  // add dock style if not present
  if (!document.getElementById("dock-style")) {
    const s = document.createElement("style"); s.id = "dock-style";
    s.textContent = `#tabbar{position:fixed;left:0;right:0;bottom:0;z-index:40;padding:0 10px 10px;pointer-events:none;display:flex;justify-content:center}#tabbar .dock{pointer-events:auto;display:flex;gap:4px;padding:6px;background:linear-gradient(180deg,rgba(22,28,42,.92),rgba(14,18,28,.96));backdrop-filter:blur(24px) saturate(1.2);border:1px solid rgba(255,255,255,.1);border-radius:20px;box-shadow:0 12px 36px rgba(0,0,0,.5),0 0 0 1px rgba(255,255,255,.06) inset,0 1px 0 rgba(255,255,255,.08) inset}#tabbar .dock button{position:relative;min-width:62px;min-height:48px;padding:6px 10px;border-radius:14px;border:0;background:transparent;color:var(--tx3);display:flex;flex-direction:column;align-items:center;gap:2px;font-size:10px;font-weight:800;letter-spacing:.04em;transition:all .22s cubic-bezier(.2,.9,.3,1.2)}#tabbar .dock button.active{background:linear-gradient(135deg,var(--acc),var(--acc2));color:#06120c;transform:translateY(-2px);box-shadow:0 6px 18px rgba(53,224,138,.4),inset 0 1px 0 rgba(255,255,255,.3)}#tabbar .dock button:active{transform:scale(.92)}#tabbar .dock .tbadge{position:absolute;top:2px;right:6px;min-width:16px;height:16px;padding:0 4px;border-radius:999px;background:#ff3b30;color:white;font-size:10px;font-weight:900;display:grid;place-items:center;box-shadow:0 2px 8px rgba(255,59,48,.5)}#tabbar .dock .tbadge.hidden{display:none}`;
    document.head.appendChild(s);
  }
}
function renderSheet(items) {
  const el = $("#sheet-grid"); if (!el) return;
  const inBar = new Set(TAB_IDS);
  const moreItems = items.filter(i => !inBar.has(i[0]));
  const MORE_EMOJI = { transfers: "💸", scouting: "🔍", finances: "💰", club: "🏟️", calendar: "📅", table: "📊", training: "🏋️", career: "🏅", board: "🏛️", media: "🎤", staff: "👔", youth: "🌱", jobs: "💼" };
  el.innerHTML = moreItems.map(n =>
    `<button data-s="${n[0]}" onclick="Juice.haptic('tap');go('${n[0]}')" style="position:relative;display:flex;flex-direction:column;align-items:center;gap:6px;padding:14px 8px;border-radius:16px;background:linear-gradient(165deg,#1a2132,#151a27);border:1px solid rgba(255,255,255,.08);color:var(--tx);font-weight:700;font-size:12px"><span style="font-size:24px">${MORE_EMOJI[n[0]]||"📦"}</span><span>${n[2]}</span>` +
    `<span class="tbadge hidden" data-badge="${n[0]}" style="position:absolute;top:6px;right:6px;min-width:18px;height:18px;border-radius:999px;background:#ff3b30;color:white;font-size:10px;display:grid;place-items:center"></span></button>`).join("");
  // sheet styling
  const sheet = $("#sheet");
  if (sheet && !document.getElementById("sheet-game-style")) {
    const s = document.createElement("style"); s.id = "sheet-game-style";
    s.textContent = `#sheet{position:fixed;inset:0;z-index:50;background:rgba(6,8,12,.72);backdrop-filter:blur(18px);display:none}#sheet.open{display:grid;place-items:end center}#sheet.vis{animation:sheet-in .32s cubic-bezier(.2,.9,.3,1.2)}@keyframes sheet-in{from{opacity:0}to{opacity:1}}#sheet .sheet-box{width:100%;max-width:520px;background:linear-gradient(180deg,#1a2132,#10131a);border-radius:24px 24px 0 0;border:1px solid rgba(255,255,255,.1);border-bottom:0;box-shadow:0 -12px 48px rgba(0,0,0,.6);padding:12px 12px calc(20px + env(safe-area-inset-bottom));transform:translateY(100%);transition:transform .34s cubic-bezier(.2,.9,.3,1.2)}#sheet.vis .sheet-box{transform:translateY(0)}#sheet-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}`;
    document.head.appendChild(s);
    if (!sheet.querySelector(".sheet-box")) {
      const inner = sheet.innerHTML;
      sheet.innerHTML = `<div class="sheet-box"><div style="width:36px;height:4px;border-radius:999px;background:rgba(255,255,255,.18);margin:0 auto 12px"></div><div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px"><b style="font-size:15px">More</b><button onclick="closeSheet()" style="width:32px;height:32px;border-radius:10px;background:rgba(255,255,255,.08);border:0;color:var(--tx)">✕</button></div><div id="sheet-grid">${inner}</div></div>`;
    }
  }
}
function openSheet() {
  Juice.haptic("light");
  const s = $("#sheet"); if (!s) return;
  // ensure sheet-box exists
  if (!s.querySelector(".sheet-box")) renderSheet(NAV);
  s.classList.add("open");
  requestAnimationFrame(() => s.classList.add("vis"));
}
function closeSheet() {
  const s = $("#sheet"); if (!s || !s.classList.contains("open")) return;
  s.classList.remove("vis");
  setTimeout(() => s.classList.remove("open"), 260);
}

/* ---------------- club crests: procedural shields in real club colours -------- */
const CREST = {
  MCI:["#6CABDD","#1C2C5B","plain"], ARS:["#EF0107","#FFFFFF","halves"], LIV:["#C8102E","#00B2A9","plain"],
  CHE:["#034694","#FFFFFF","plain"], MUN:["#DA291C","#FBE122","plain"], TOT:["#FFFFFF","#132257","plain"],
  NEW:["#241F20","#FFFFFF","stripes"], AVL:["#670E36","#95BFE5","halves"], WHU:["#7A263A","#1BB1E7","sash"],
  BRI:["#0057B8","#FFCD00","stripes"], BRE:["#E30613","#FFFFFF","plain"], CRY:["#1B458F","#C4122E","stripes"],
  FUL:["#FFFFFF","#000000","plain"], EVE:["#003399","#FFFFFF","plain"], WOL:["#FDB913","#231F20","plain"],
  NOT:["#DD0000","#FFFFFF","plain"], AFC:["#DA291C","#000000","stripes"], SUN:["#EB172B","#FFFFFF","stripes"],
  LEE:["#FFFFFF","#FFCD00","plain"], BUR:["#6C1D45","#99D6F0","halves"],
  RMA:["#FFFFFF","#FEBE10","plain"], BAR:["#A50044","#004D98","stripes"], ATM:["#CB3524","#FFFFFF","stripes"],
  ATH:["#EE2523","#FFFFFF","stripes"], RSC:["#0067B1","#FFFFFF","stripes"], VIL:["#FFE667","#005187","plain"],
  BET:["#00954C","#FFFFFF","stripes"], SEV:["#FFFFFF","#D4021D","plain"], VAL:["#FFFFFF","#F18E00","halves"],
  CELT:["#8AC3EE","#FFFFFF","stripes"], GIR:["#CD2534","#FFFFFF","stripes"], RAY:["#FFFFFF","#E53027","sash"],
  OSA:["#D91A21","#00282E","plain"], GET:["#005999","#FFFFFF","plain"], ALA:["#0066B3","#FFFFFF","stripes"],
  ESP:["#007FC8","#FFFFFF","stripes"], RCD:["#007DC3","#FFFFFF","stripes"], MLL:["#E20613","#000000","halves"],
  ELC:["#00A94F","#FFFFFF","stripes"], LEV:["#A52316","#004C99","halves"],
  INT:["#0068A8","#000000","stripes"], JUV:["#FFFFFF","#000000","stripes"], ACM:["#FB090B","#000000","stripes"],
  NAP:["#12A0D7","#FFFFFF","plain"], ROM:["#8E1F2F","#F0BC42","plain"], LAZ:["#87D8F7","#FFFFFF","plain"],
  ATA:["#1E71B8","#000000","stripes"], FIO:["#582C83","#FFFFFF","plain"], BOL:["#1A2F3F","#D4021D","plain"],
  TOR:["#8B0000","#FFFFFF","plain"], UDI:["#000000","#FFFFFF","stripes"], GEN:["#00204B","#FF0000","halves"],
  CAG:["#A2162B","#0A2B6B","plain"], LEC:["#F0C803","#D4021D","halves"], EMP:["#003058","#FFFFFF","plain"],
  PAR:["#F8E850","#000000","stripes"], COM:["#00204B","#FFFFFF","plain"], VER:["#F2CE2C","#003058","plain"],
  SAS:["#00A650","#000000","stripes"], PIS:["#00275C","#FFFFFF","plain"],
  BAY:["#DC052D","#0066B2","plain"], BVB:["#FDE100","#000000","plain"], LEV1:["#E32221","#000000","halves"],
  RBL:["#FFFFFF","#DD0741","plain"], SGE:["#000000","#E1000F","stripes"], VFB:["#FFFFFF","#E32219","sash"],
  BMG:["#000000","#FFFFFF","stripes"], WOB:["#65B32E","#FFFFFF","plain"], TSG:["#1961B7","#FFFFFF","plain"],
  SCF:["#000000","#ED2219","plain"], FCU:["#EB1923","#FFFFFF","plain"], FCSP:["#654E30","#FFFFFF","stripes"],
  WER:["#1E9053","#FFFFFF","plain"], FCA:["#BA3733","#FFFFFF","plain"], MAI1:["#C3141E","#FFFFFF","plain"],
  HAI:["#003080","#E30613","plain"], FCN1:["#000000","#FF0000","plain"], KOE:["#ED1C24","#FFFFFF","plain"],
  PSG:["#004170","#DA291C","sash"], OM:["#2FAEE0","#FFFFFF","plain"], ASM:["#E4032E","#FFFFFF","sash"],
  LOSC:["#D00027","#003383","halves"], OL:["#FFFFFF","#D20500","plain"], NIC:["#CC0000","#000000","stripes"],
  REN:["#E32219","#000000","plain"], RCL:["#FFDD00","#E32219","halves"], STR:["#0076C0","#FFFFFF","stripes"],
  TFC:["#3B1E5C","#FFFFFF","plain"], BRE1F:["#E32219","#FFFFFF","plain"], NAN:["#FCD405","#009850","halves"],
  SR:["#D3062B","#FFFFFF","stripes"], HAV:["#00A0E0","#002545","stripes"], AJA:["#FFFFFF","#005CA9","stripes"],
  ANG:["#000000","#FFFFFF","stripes"], MET:["#6C1E3A","#FFFFFF","plain"], LOR:["#F26722","#000000","stripes"],
  CEL:["#00A14E","#FFFFFF","hoops"], RAN:["#0033A0","#D4021D","plain"], AJA1:["#D2122E","#FFFFFF","stripes"],
  PSV:["#ED1C24","#FFFFFF","stripes"], FEY:["#D2122E","#FFFFFF","halves"], SLB:["#E0001B","#FFFFFF","plain"],
  FCP:["#0033A0","#FFFFFF","stripes"], SPORT:["#008050","#FFFFFF","stripes"], GAL:["#FDB912","#A90432","halves"],
  FEN:["#FFED00","#003050","stripes"], BOC:["#0033A0","#FFB800","sash"], RIV:["#FFFFFF","#E32219","sash"],
};
let CREST_N = 0;
let REAL_CRESTS = {};
let REAL_COMPS = {};
function compLogo(code, cls) {
  const u = REAL_COMPS[code || ""];
  if (u) return `<img class="comp-logo${cls ? " " + cls : ""}" src="${u}" alt="" loading="lazy">`;
  return `<span class="ci">${esc(compMono(code))}</span>`;
}
function crest(code, cls) {
  const u = REAL_CRESTS[code || ""];
  if (u) return `<img class="crest${cls ? " " + cls : ""}" src="${u}" alt="" loading="lazy" onerror="this.outerHTML=crestSVG('${code}','${cls || ''}')">`;
  return crestSVG(code, cls);
}
function crestSVG(code, cls) {
  code = code || "";
  const c = CREST[code];
  let c1, c2, pat, txt = "";
  if (c) { c1 = c[0]; c2 = c[1]; pat = c[2]; }
  else {
    let h = 7; for (const ch of code || "?") h = (h * 31 + ch.charCodeAt(0)) >>> 0;
    const hue = h % 360;
    c1 = "hsl(" + hue + " 45% 34%)"; c2 = "hsl(" + ((hue + 40) % 360) + " 60% 66%)"; pat = "plain";
    txt = (code || "?").slice(0, 2);
  }
  const id = "cr" + (CREST_N++);
  const sh = "M20 2 L36 8 V20 C36 30 29 36 20 38 C11 36 4 30 4 20 V8 Z";
  let inner = "";
  if (pat === "stripes") inner = '<rect x="8" y="0" width="4.6" height="40" fill="' + c2 + '"/><rect x="17.2" y="0" width="4.6" height="40" fill="' + c2 + '"/><rect x="26.4" y="0" width="4.6" height="40" fill="' + c2 + '"/>';
  else if (pat === "hoops") inner = '<rect x="0" y="9" width="40" height="5" fill="' + c2 + '"/><rect x="0" y="19" width="40" height="5" fill="' + c2 + '"/><rect x="0" y="29" width="40" height="5" fill="' + c2 + '"/>';
  else if (pat === "halves") inner = '<rect x="20" y="0" width="20" height="40" fill="' + c2 + '"/>';
  else if (pat === "sash") inner = '<path d="M0 30 L40 6 L40 16 L0 40 Z" fill="' + c2 + '"/>';
  else inner = '<path d="M4 8 H36 V14 H4 Z" fill="' + c2 + '"/>';
  const t = txt ? '<text x="20" y="26" text-anchor="middle" font-size="12" font-weight="800" fill="' + c2 + '" font-family="Arial,sans-serif">' + txt + '</text>' : "";
  return '<svg class="crest ' + (cls || "") + '" viewBox="0 0 40 40" aria-hidden="true"><defs><clipPath id="' + id + '"><path d="' + sh + '"/></clipPath></defs><path d="' + sh + '" fill="' + c1 + '"/><g clip-path="url(#' + id + ')">' + inner + '</g><path d="' + sh + '" fill="none" stroke="rgba(255,255,255,.25)" stroke-width="1.2"/>' + t + '</svg>';
}
function paintCrest(code) {
  const el = $("#crest"); if (!el) return;
  el.innerHTML = crest(code || "TL");
}

/* ------------------- tables: scroll on desktop, cards on phones ------------------- */
function wrapTw(t) {
  if (t.closest(".tw")) return;
  const w = document.createElement("div"); w.className = "tw";
  t.replaceWith(w); w.appendChild(t);
}
function tableToCards(t) {
  const heads = [...t.querySelectorAll("thead th")].map(th => th.textContent.trim());
  const rows = [...t.querySelectorAll("tbody tr")];
  if (!rows.length) { wrapTw(t); return; }
  const host = document.createElement("div"); host.className = "cards";
  rows.forEach(tr => {
    if (tr.children.length <= 1) {
      const d = document.createElement("div"); d.className = "tmsg"; d.innerHTML = tr.innerHTML;
      host.appendChild(d); return;
    }
    const cells = [...tr.children];
    const card = document.createElement("div");
    card.className = "tcard" + (tr.classList.contains("me") ? " me" : "");
    const oc = tr.getAttribute("onclick");
    if (oc) { card.setAttribute("onclick", oc); card.classList.add("tap"); }
    let ti = cells.findIndex(td => !td.classList.contains("num") && td.textContent.trim() &&
                                 td.querySelector("b,strong"));
    if (ti < 0) ti = cells.findIndex(td => !td.classList.contains("num") && td.textContent.trim().length > 6);
    if (ti < 0) {
      let best = -1;
      cells.forEach((td, i) => {
        if (td.querySelector("b,strong")) {
          const len = td.textContent.trim().length;
          if (len > best) { best = len; ti = i; }
        }
      });
    }
    if (ti < 0) ti = cells.findIndex(td => !td.classList.contains("num"));
    if (ti < 0) ti = 0;
    const hd = document.createElement("div"); hd.className = "tcard-h"; hd.innerHTML = cells[ti].innerHTML;
    card.appendChild(hd);
    const grid = document.createElement("div"); grid.className = "tcard-g";
    cells.forEach((td, i) => {
      if (i === ti) return;
      if (!td.textContent.trim() && !td.querySelector(".bar,.tag,svg,img,input,select")) return;
      const c = document.createElement("div"); c.className = "tcell";
      c.innerHTML = `<span class="tl">${esc(heads[i] || "")}</span><span class="tv">${td.innerHTML}</span>`;
      grid.appendChild(c);
    });
    card.appendChild(grid);
    host.appendChild(card);
  });
  t.replaceWith(host);
  let p = host.parentElement;
  while (p && p !== document.body) {
    if (p.classList.contains("card") || p.classList.contains("tight")) {
      p.style.cssText += ";padding:0;border:0;background:none;box-shadow:none;overflow:visible;max-height:none";
      break;
    }
    if (p.tagName === "DIV" && /overflow|max-height/.test(p.getAttribute("style") || "")) {
      p.style.overflow = "visible"; p.style.maxHeight = "none"; p.style.padding = "8px";
    }
    p = p.parentElement;
  }
}
function polish(root) {
  root = root || document;
  const tables = $$("table", root);
  if (window.innerWidth >= 900) { tables.forEach(wrapTw); return; }
  tables.forEach(t => {
    if (t.closest(".tw")) return;
    if (t.querySelector("tbody[id]")) { wrapTw(t); return; }   // live-updated tables stay tables
    if (t.classList.contains("mc")) { wrapTw(t); return; }     // explicit: keep as table
    const cols = t.querySelectorAll("thead th").length;
    if (cols >= 4) tableToCards(t); else wrapTw(t);
  });
}
window.addEventListener("resize", () => { /* re-layout on rotate happens on next render */ });
document.addEventListener("DOMContentLoaded", () => {
  const s = $("#sheet");
  if (s) s.addEventListener("click", e => { if (e.target.id === "sheet") closeSheet(); });
});
