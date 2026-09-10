/* Touchline — football management simulation */
"use strict";
const $ = (s, r) => (r || document).querySelector(s);
const $$ = (s, r) => Array.from((r || document).querySelectorAll(s));
const api = {
  async get(p) {
    let r; try { r = await fetch(p); } catch (e) { deadScreen(); throw e; }
    if (!r.ok) { const j = await r.json().catch(() => ({})); const e = new Error(j.error || j.detail || ("HTTP " + r.status)); e.status = r.status; throw e; }
    return r.json();
  },
  async post(p, b) {
    let r; try { r = await fetch(p, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(b || {}) }); } catch (e) { deadScreen(); throw e; }
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(j.detail || j.error || r.status);
    return j;
  }
};
const VERSION = "1.16.0";
let DEAD = false;
function deadScreen() { if (DEAD) return; DEAD = true; const d = $("#dead"); if (d) d.classList.remove("hidden"); }
const G = { boot: null, home: null, screen: "home", sub: null, static: null, busy: false, prevScreen: null };

/* GAME JUICE — haptics, sounds, confetti, shake */
const Juice = {
  haptic(t) { try { if (!navigator.vibrate) return; const p = { tap:[12], light:[8], medium:[20], heavy:[35], success:[15,30,40], warning:[20,20,20], error:[40,30,60], goal:[30,40,80], card:[25], var:[15,20,15,20,40], nav:[10] }; navigator.vibrate(p[t]||p.tap); } catch(e) {} },
  play(t) { try { const ctx = Juice._ctx || (Juice._ctx = new (window.AudioContext||window.webkitAudioContext)()); if (ctx.state==="suspended") ctx.resume(); const o=ctx.createOscillator(), g=ctx.createGain(); o.connect(g); g.connect(ctx.destination); const now=ctx.currentTime; const s={ tap:{f:800,d:.06,t:"sine",v:.08}, nav:{f:600,d:.08,t:"sine",v:.07}, success:{f:660,d:.18,t:"sine",v:.12,f2:880}, goal:{f:440,d:.35,t:"triangle",v:.15,f2:660}, card:{f:220,d:.12,t:"sawtooth",v:.08}, var:{f:300,d:.22,t:"square",v:.06}, error:{f:180,d:.2,t:"sawtooth",v:.09} }[t]||{f:800,d:.06,t:"sine",v:.08}; o.type=s.t; o.frequency.setValueAtTime(s.f,now); if(s.f2) o.frequency.linearRampToValueAtTime(s.f2,now+s.d*.6); g.gain.setValueAtTime(0,now); g.gain.linearRampToValueAtTime(s.v,now+.01); g.gain.exponentialRampToValueAtTime(.001,now+s.d); o.start(now); o.stop(now+s.d); } catch(e) {} },
  confetti() { try { const cols=["#2cff8a","#3dff9a","#4d9eff","#ffcc33","#a78bff"]; for(let i=0;i<32;i++){ const el=document.createElement("div"); el.style.position="fixed"; el.style.left=(Math.random()*100)+"vw"; el.style.top="-10px"; el.style.width=(6+Math.random()*8)+"px"; el.style.height=(6+Math.random()*6)+"px"; el.style.background=cols[Math.floor(Math.random()*cols.length)]; el.style.borderRadius=Math.random()>.5?"50%":"3px"; el.style.pointerEvents="none"; el.style.zIndex="95"; el.style.transform=`rotate(${Math.random()*360}deg)`; document.body.appendChild(el); const anim=el.animate([{transform:`translateY(0) rotate(0deg) scale(1)`,opacity:1},{transform:`translateY(${60+Math.random()*40}vh) rotate(${360+Math.random()*720}deg) translateX(${(Math.random()-.5)*120}px) scale(.8)`,opacity:0}],{duration:1200+Math.random()*800,easing:"cubic-bezier(.2,.8,.2,1)",delay:Math.random()*200}); anim.onfinish=()=>el.remove(); } } catch(e) {} },
  shake() { try { document.body.animate([{transform:"translateX(0)"},{transform:"translateX(-4px)"},{transform:"translateX(4px)"},{transform:"translateX(-3px)"},{transform:"translateX(3px)"},{transform:"translateX(0)"}],{duration:380,easing:"ease-out"}); } catch(e) {} }
};

/* helpers */
const esc = s => String(s==null?"":s).replace(/[&<>"]/g,c=>({ "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
function money(m){ if(m==null) return "—"; const a=Math.abs(m); if(a>=1000) return (m<0?"-":"")+"€"+(a/1000).toFixed(a>=10000?0:1)+"bn"; if(a>=1) return (m<0?"-":"")+"€"+a.toFixed(a>=100?0:1)+"m"; return (m<0?"-":"")+"€"+(a*1000).toFixed(0)+"k"; }
const wk = w => w==null?"—":"€"+Number(w).toFixed(w>=100?0:1)+"k/wk";
function stars(n){ if(n==null) return '<span class="muted">—</span>'; const full=Math.floor(n), half=n-full>=.5; return `<span class="stars">${"★".repeat(full)}${half?"½":""}${"☆".repeat(Math.max(0,5-full-(half?1:0)))}</span>`; }
const pct = n => Math.max(0,Math.min(100,Math.round(n||0)));
function condClass(v){ return v>1.02?"W":v<0.92?"L":"D"; }
function fmtDate(s){ if(!s) return "—"; const d=new Date(s+(s.length===10?"T12:00:00":"")); return d.toLocaleDateString(undefined,{weekday:"short",day:"numeric",month:"short",year:"numeric"}); }
function toast(msg,ms){
  Juice.haptic("light");
  const t=document.createElement("div"); t.className="toast";
  t.innerHTML=`<div style="display:flex;align-items:center;gap:10px"><div style="width:26px;height:26px;border-radius:9px;background:linear-gradient(180deg,var(--acc2),var(--acc));display:grid;place-items:center;color:#031a0c;font-weight:950;font-size:13px">✓</div><div style="flex:1;font-weight:800">${msg}</div></div>`;
  $("#toast-wrap").appendChild(t);
  t.animate([{transform:"translateY(14px) scale(.96)",opacity:0},{transform:"translateY(0) scale(1)",opacity:1}],{duration:300,easing:"cubic-bezier(.2,.9,.3,1.15)"});
  setTimeout(()=>{ t.animate([{transform:"translateY(0) scale(1)",opacity:1},{transform:"translateY(-8px) scale(.96)",opacity:0}],{duration:220}).onfinish=()=>t.remove(); }, ms||3200);
}
function modal(html,wide){
  Juice.haptic("medium");
  const box=$("#modal-box"); box.className="box"+(wide?" wide":"");
  box.innerHTML=`<button class="close" onclick="closeModal()">✕</button>`+html;
  polish(box);
  $("#modal").classList.add("open");
}
function closeModal(){
  Juice.haptic("light");
  const box=$("#modal-box");
  try{ box.animate([{transform:"scale(1)",opacity:1},{transform:"scale(.96)",opacity:0}],{duration:160}).onfinish=()=>$("#modal").classList.remove("open"); } catch(e){ $("#modal").classList.remove("open"); }
}
function setBusy(on){ const b=$("#busybar"); if(b) b.classList.toggle("on",!!on); }
$("#modal").addEventListener("click", e=>{ if(e.target.id==="modal") closeModal(); });
const bar = (v,cls)=>`<div class="bar ${cls||""}"><i style="width:${pct(v)}%"></i></div>`;

/* boot */
async function boot(){
  try{
    const v=$("#ver"); if(v) v.textContent="v"+VERSION;
    [["#tb-budget","finances"],["#tb-board","board"],["#tb-next","match"],["#tb-club","club"],["#tb-inbox","inbox"]].forEach(([sel,sc])=>{
      const el=$(sel); if(!el) return; el.classList.add("tap"); el.onclick=()=>{ if(!document.body.classList.contains("pregame")) go(sc); };
    });
    $("#splash-msg").textContent="Loading world…";
    G.boot=await api.get("/api/boot");
    G.static=G.boot.static;
    try{ REAL_CRESTS=await (await fetch("static/crests.json",{cache:"force-cache"})).json(); } catch(e){ REAL_CRESTS={}; }
    try{ REAL_COMPS=await (await fetch("static/comps.json",{cache:"force-cache"})).json(); } catch(e){ REAL_COMPS={}; }
    if(G.boot.has_save){ $("#splash-msg").textContent="Loading career…"; await enterGame(); }
    else { $("#splash").classList.add("hidden"); $("#app").classList.remove("hidden"); showStartScreen(); }
  } catch(e){ $("#splash-msg").innerHTML=`<span style="color:#ff8a94">Failed: ${esc(e.message)}</span>`; }
}

/* new career */
const NAV_START=[];
function showStartScreen(){
  renderNav(NAV_START);
  $("#content").innerHTML=`
    <div style="min-height:78vh;display:grid;place-items:center;padding:20px 14px"> <div style="width:100%;max-width:380px;text-align:center"> <svg viewBox="0 0 40 40" style="width:56px;height:56px;color:var(--acc)"><path d="M20 2 L36 8 V20 C36 30 29 36 20 38 C11 36 4 30 4 20 V8 Z" fill="rgba(44,255,138,.08)"/><path d="M20 2 L36 8 V20 C36 30 29 36 20 38 C11 36 4 30 4 20 V8 Z" fill="none" stroke="currentColor" stroke-width="1.6"/><circle cx="20" cy="19" r="7" fill="none" stroke="currentColor" stroke-width="1.3"/><path d="M20 12v14M13 19h14M15 14.5l10 9M25 14.5l-10 9" stroke="currentColor" stroke-width=".9" opacity=".8"/></svg> <h1 style="font-size:26px;letter-spacing:.28em;text-indent:.28em;margin:14px 0 4px;color:var(--tx)">TOUCHLINE</h1> <p class="small muted" style="font-size:12px;margin:0">A football management simulation</p> <div id="slot-strip" style="margin:18px 0 0;display:grid;gap:6px"></div> <div style="margin:10px 0 0;display:grid;gap:8px"> <button class="btn primary" style="min-height:50px;border-radius:12px" onclick="Juice.haptic('light');stepChooseClub()">New career</button> <button class="btn" style="min-height:40px;border-radius:12px" onclick="openSaves()">Saved games &amp; backup</button> </div> <p class="small muted" style="margin-top:22px;font-size:11px;line-height:1.7">402 clubs · 21 leagues · 15,000 players<br>Simulated world — transfers, sackings, trophies</p> <p class="small muted" style="margin-top:10px;opacity:.45;font-size:10px">v${VERSION} · offline</p> </div> </div>`;
  renderSlotStrip();
}
/* ---------- Save slots ---------- */
async function renderSlotStrip(){
  const host=$("#slot-strip"); if(!host) return;
  let j; try{ j=await api.get("/api/slots"); }catch(e){ return; }
  host.innerHTML=j.slots.map(s=>{
    const label=s.has_save?`${esc(s.club||"Career")} · ${s.season?s.season+"/"+String(s.season+1).slice(2):""}`:"Empty";
    return `<button class="slot-chip${s.active?" on":""}" onclick="${s.active?"":`switchSlot('${s.id}')`}">
      <span class="sc-n">${s.id.replace("slot","SLOT ")}</span><span class="sc-i">${label}${s.active?" · selected":""}</span></button>`;
  }).join("")+`<p class="small muted" style="font-size:9.5px;text-align:center;margin:4px 0 0">A new career starts in the selected slot</p>`;
}
async function switchSlot(id){
  Juice.haptic("light"); setBusy(true);
  try{
    const j=await api.post("/api/slots/switch",{slot:id});
    if(!j.ok){ toast(esc(j.msg||j.error||"Could not switch"),5000); setBusy(false); return; }
    G.home=null; G.boot=null; closeModal();
    if(j.loaded){ toast("Career loaded"); await enterGame(); }
    else { toast("Slot selected — start a new career"); $("#app").classList.remove("hidden"); $("#splash").classList.add("hidden"); showStartScreen(); }
  }catch(e){ toast("Switch failed: "+esc(e.message),5000); }
  setBusy(false);
}
async function openSaves(){
  Juice.haptic("light");
  let j; try{ j=await api.get("/api/slots"); }catch(e){ toast("Could not read slots",4000); return; }
  const rows=j.slots.map(s=>{
    const label=s.has_save?`${esc(s.club||"Career")} · season ${s.season}${s.date?" · "+esc(s.date):""}`:"Empty slot";
    const btns=[];
    if(s.has_save&&!s.active) btns.push(`<button class="btn sm" onclick="switchSlot('${s.id}');openSaves()">Open</button>`);
    if(s.has_save) btns.push(`<button class="btn sm" onclick="exportSlot('${s.id}')">Export</button>`);
    if(!s.has_save) btns.push(`<button class="btn sm" onclick="switchSlot('${s.id}');closeModal();toast('Slot selected — start a new career')">Select</button>`);
    if(s.has_save&&!s.active) btns.push(`<button class="btn sm danger" onclick="deleteSlot('${s.id}')">Delete</button>`);
    return `<div class="slot-row${s.active?" on":""}">
      <div style="flex:1;min-width:0"><b style="font-size:12px">${s.id.replace("slot","SLOT ")}${s.active?" · in use":""}</b>
      <div class="small muted" style="font-size:10.5px">${label}${s.size?` · ${(s.size/1e6).toFixed(1)} MB`:""}</div></div>
      <div style="display:flex;gap:4px;flex-wrap:wrap;justify-content:flex-end">${btns.join("")}</div></div>`;
  }).join("");
  modal(`<h2>Saved games</h2>
    <p class="small muted" style="font-size:11px">Three independent careers. Export makes a backup file you can keep or share; Import restores one.</p>
    <div style="display:grid;gap:6px;margin-top:10px">${rows}</div>
    <div style="display:flex;gap:8px;margin-top:12px;align-items:center">
      <button class="btn" onclick="pickImportFile()">Import backup file…</button>
      <input type="file" id="import-file" accept=".zip" style="display:none" onchange="importFilePicked(this)">
      <span class="spacer"></span>
      <button class="btn" onclick="closeModal()">Close</button>
    </div>`);
}
async function deleteSlot(id){
  modal(`<h2>Delete slot?</h2><p class="small muted">The career in ${esc(id)} will be permanently deleted. Export it first if you want a backup.</p>
    <div style="display:flex;gap:8px;margin-top:12px"><button class="btn danger" onclick="confirmDeleteSlot('${id}')">Delete</button><button class="btn" onclick="openSaves()">Cancel</button></div>`);
}
async function confirmDeleteSlot(id){
  const j=await api.post("/api/slots/delete",{slot:id});
  if(j.ok){ toast("Slot deleted"); openSaves(); } else toast(esc(j.msg||"Could not delete"),5000);
}
async function exportSlot(id){
  Juice.haptic("light");
  try{
    if(window.TLAndroid&&window.TLAndroid.exportSlot){ window.TLAndroid.exportSlot(id); toast("Saving to your device…"); return; }
    const r=await fetch(`/api/slots/export?slot=${id}`);
    if(!r.ok){ const j=await r.json().catch(()=>({})); toast(esc(j.error||"Export failed"),5000); return; }
    const blob=await r.blob();
    const cd=r.headers.get("Content-Disposition")||"";
    const m=cd.match(/filename="?([^";]+)"?/);
    const a=document.createElement("a");
    a.href=URL.createObjectURL(blob);
    a.download=m?m[1]:`touchline-${id}.zip`;
    document.body.appendChild(a); a.click(); a.remove();
    toast("Backup downloaded");
  }catch(e){ toast("Export failed: "+esc(e.message),5000); }
}
function pickImportFile(){
  if(window.TLAndroid&&window.TLAndroid.importSlot){ window.TLAndroid.importSlot(); return; }
  const inp=$("#import-file"); if(inp) inp.click();
}
async function importFilePicked(inp){
  const f=inp.files&&inp.files[0]; if(!f) return;
  setBusy(true);
  try{
    const buf=await f.arrayBuffer();
    let bin=""; const bytes=new Uint8Array(buf);
    for(let i=0;i<bytes.length;i+=8192) bin+=String.fromCharCode.apply(null,bytes.subarray(i,i+8192));
    const j=await api.post("/api/slots/import",{data_b64:btoa(bin)});
    if(j.ok){ toast("Backup restored into "+j.slot); G.boot=null; G.home=null; closeModal(); openSaves(); }
    else toast(esc(j.error||j.msg||"Import failed"),6000);
  }catch(e){ toast("Import failed: "+esc(e.message),6000); }
  setBusy(false); inp.value="";
}
window.TLImportDone=function(ok,msg){ toast(msg||(ok?"Backup imported":"Import failed"),5000); if(ok){ G.boot=null; closeModal(); openSaves(); } };
let CLUB_PICK=null;
async function stepChooseClub(){
  renderNav(NAV_START);
  let countries=[]; try{ countries=(await api.get("/api/clubs/countries")).countries; } catch(e){}
  $("#content").innerHTML=`
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:12px"><button class="btn sm" onclick="showStartScreen()">◂</button><b style="font-size:14px">CHOOSE CLUB</b><span class="spacer"></span><span class="small muted" id="cs-count"></span></div> <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:10px"> <input id="cs-q" placeholder="Search club…" style="flex:1;min-width:160px" oninput="debounceSearch()"> <select id="cs-country" onchange="searchClubs()"><option value="">All nations</option>${countries.map(c=>`<option value="${esc(c.country)}">${esc(c.country)} (${c.n})</option>`).join("")}</select> <select id="cs-tier" onchange="searchClubs()"><option value="0">All tiers</option><option value="1">Top</option><option value="2">2nd</option><option value="3">3rd</option><option value="4">4th</option><option value="5">5th</option></select> </div> <div id="cs-host" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:8px;max-height:68vh;overflow:auto;padding-bottom:10px"></div>`;
  searchClubs();
}
async function searchClubs(){
  const q=encodeURIComponent($("#cs-q")?.value||""), country=encodeURIComponent($("#cs-country")?.value||""), tier=$("#cs-tier")?.value||0;
  const j=await api.get(`/api/clubs/search?q=${q}&country=${country}&tier=${tier}`);
  $("#cs-count").textContent=j.clubs.length+" clubs";
  const pick=c=>`pickClub(${JSON.stringify(c).replace(/'/g,"&#39;")})`;
  $("#cs-host").innerHTML=j.clubs.map(c=>`
    <button onclick='${pick(c)}' style="text-align:left;padding:12px;border-radius:14px;background:linear-gradient(165deg,var(--panel),#0f1422);border:1px solid var(--line);color:var(--tx);box-shadow:var(--shadow);transition:transform .18s"> <div style="display:flex;align-items:center;gap:8px"><div style="width:32px;height:32px;border-radius:10px;background:var(--panel3);display:grid;place-items:center;font-weight:900;font-size:11px">${esc(c.name).slice(0,2).toUpperCase()}</div><div style="flex:1;min-width:0"><b style="font-size:12px;display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(c.name)}</b><span style="font-size:10px;color:var(--tx3)">${esc(c.country)} · T${c.tier} · ${c.rep}</span></div></div> <div style="margin-top:8px;display:flex;gap:4px;flex-wrap:wrap"><span style="font-size:9px;padding:2px 6px;border-radius:6px;background:var(--panel3)">${esc(c.league_name||c.league).slice(0,14)}</span><span style="font-size:9px;padding:2px 6px;border-radius:6px;background:var(--acc-dim);color:var(--acc)">${money(c.transfer_budget)}</span></div> </button>`).join("")||`<div style="grid-column:1/-1;text-align:center;padding:24px" class="small muted">No clubs match</div>`;
}
let SEARCH_T=null; function debounceSearch(){ clearTimeout(SEARCH_T); SEARCH_T=setTimeout(searchClubs,260); }
function pickClub(c){ CLUB_PICK=c; stepManagerProfile(); }
function stepManagerProfile(){
  const c=CLUB_PICK; const nations=G.static.nations||[];
  $("#content").innerHTML=`
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:12px"><button class="btn sm" onclick="stepChooseClub()">◂</button><b>MANAGER · ${esc(c.name)}</b></div> <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;max-width:800px"> <div class="card"><h3>Profile</h3> <label style="font-size:10px;font-weight:900;letter-spacing:.08em;color:var(--tx3)">NAME</label><input id="mp-name" style="width:100%;margin-top:4px" placeholder="Alex Ferguson"> <div style="height:8px"></div> <label style="font-size:10px;font-weight:900;letter-spacing:.08em;color:var(--tx3)">NATIONALITY</label><select id="mp-nat" style="width:100%;margin-top:4px"><option>England</option>${nations.filter(n=>n!=="England").map(n=>`<option>${esc(n)}</option>`).join("")}</select> <div style="height:8px"></div> <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px"><div><label style="font-size:10px;font-weight:900;color:var(--tx3)">AGE</label><input id="mp-age" type="number" value="38" min="24" max="75" style="width:100%;margin-top:4px"></div><div><label style="font-size:10px;font-weight:900;color:var(--tx3)">REP 1-95</label><input id="mp-rep" type="number" value="${Math.max(3,Math.round(c.rep*.28))}" min="1" max="95" style="width:100%;margin-top:4px"></div></div> <div style="height:8px"></div> <label style="font-size:10px;font-weight:900;color:var(--tx3)">STYLE</label><select id="mp-style" style="width:100%;margin-top:4px">${["Balanced","Possession","High press","Counter-attack","Direct","Defensive solidity","Wing play","Youth-focused"].map(s=>`<option>${s}</option>`).join("")}</select> <div style="height:8px"></div> <label style="font-size:10px;font-weight:900;color:var(--tx3)">DIFFICULTY</label><select id="mp-diff" style="width:100%;margin-top:4px">${G.static.difficulties.map(d=>`<option value="${d.id}" ${d.id==="realistic"?"selected":""}>${d.name}</option>`).join("")}</select> </div> <div class="card"><h3>Attributes · left <b id="mp-left">0</b></h3><div id="mp-attrs" style="margin-top:8px"></div></div> </div> <div style="margin-top:12px;display:flex;gap:8px"><button class="btn" onclick="stepChooseClub()">◂ Back</button><button class="btn primary" id="mp-go" onclick="createCareer()">TAKE CHARGE ▶</button></div>`;
  const keys=["attacking","defending","fitness","tactical","mental","technical","youth","man_mgmt","motivation","adaptability","judging"];
  const names={attacking:"Attacking",defending:"Defending",fitness:"Fitness",tactical:"Tactical",mental:"Mental",technical:"Technical",youth:"Youth",man_mgmt:"Man mgmt",motivation:"Motivation",adaptability:"Adapt",judging:"Judging"};
  const budget=132;
  $("#mp-attrs").innerHTML=keys.map(k=>`<div style="display:flex;align-items:center;gap:8px;margin-bottom:4px"><div style="width:70px;font-size:11px;font-weight:800">${names[k]}</div><input type="range" min="1" max="20" value="12" data-k="${k}" style="flex:1;min-height:0;height:28px" oninput="attrChanged()"><div style="width:22px;text-align:right;font-weight:900;font-size:12px" id="av-${k}">12</div></div>`).join("");
  window._attrBudget=budget; attrChanged();
}
function attrChanged(){ let used=0; $$('#mp-attrs input[type=range]').forEach(i=>{ used+=+i.value; $("#av-"+i.dataset.k).textContent=i.value; }); const left=window._attrBudget-used; $("#mp-left").textContent=left; $("#mp-left").style.color=left<0?"var(--red)":"var(--acc)"; $("#mp-go").disabled=left<0; }
async function createCareer(){
  const attrs={}; $$('#mp-attrs input[type=range]').forEach(i=>attrs[i.dataset.k]=+i.value);
  const body={ club_code:CLUB_PICK.code, difficulty:$("#mp-diff").value, manager:{ name:$("#mp-name").value.trim()||"The Manager", nat:$("#mp-nat").value, age:+$("#mp-age").value, reputation:+$("#mp-rep").value, style:$("#mp-style").value, attrs } };
  $("#mp-go").disabled=true; $("#mp-go").textContent="Building…"; setBusy(true);
  try{ const j=await api.post("/api/career/new",body); if(!j.ok) throw new Error(j.error||"Engine refused"); onboarding(j); } catch(e){ toast("Failed: "+esc(e.message),6000); $("#mp-go").disabled=false; $("#mp-go").textContent="TAKE CHARGE ▶"; }
  setBusy(false);
}
function onboarding(j){
  renderNav(NAV_START); const m=j.meeting;
  $("#content").innerHTML=`
    <div style="display:grid;gap:10px;max-width:800px"> <div class="card"><h2>${esc(j.club.name)} — Welcome Boss</h2><p class="small muted" style="margin-top:6px">${esc(j.club.league)} · tier ${j.club.tier} · rep ${j.club.rep}</p> <div style="margin-top:10px;display:grid;gap:6px">${j.steps.map((s,i)=>`<div style="display:flex;gap:10px;align-items:flex-start"><span style="width:20px;height:20px;border-radius:8px;background:var(--panel3);display:grid;place-items:center;font-size:10px;font-weight:900;flex:none">${i+1}</span><div><b style="font-size:12px">${esc(s[0])}</b><div class="small muted">${esc(s[1])}</div></div></div>`).join("")}</div> </div> <div class="card"><h3>Board meeting</h3><p class="small" style="margin-top:8px">${esc(m.welcome)}</p> <div style="margin-top:10px;display:grid;grid-template-columns:1fr 1fr;gap:6px"> <div class="kv"><span>Chairman</span><b>${esc(m.chairman)}</b></div><div class="kv"><span>Budget</span><b>${money(m.budget.transfer)}</b></div> <div class="kv"><span>Cash</span><b>${money(m.budget.cash)}</b></div><div class="kv"><span>Window</span><b style="font-size:11px">${fmtDate(m.window.opens)} → ${fmtDate(m.window.closes)}</b></div> </div> <div style="margin-top:10px"><b style="font-size:11px;letter-spacing:.08em">OBJECTIVES</b>${m.objectives.map(o=>`<div style="padding:8px;border-radius:10px;background:var(--panel2);margin-top:6px;border:1px solid var(--line)"><b style="font-size:12px">${esc(o.text)}</b><div class="small muted">${esc(o.comp||"")} ${o.target_pos?"· target "+o.target_pos:""} ${o.critical?"· CRITICAL":""}</div></div>`).join("")}</div> </div> <div class="card"><h3>Assistant briefing</h3><div class="pre" style="margin-top:8px">${esc(m.assistant)}</div><button class="btn primary" style="margin-top:12px;width:100%" onclick="enterGame()">GO TO OFFICE ▶</button></div> </div>`;
}

/* game shell */
const NAV=[
  ["home","","Home"],["squad","","Squad"],["match","","Match"],["stats","","Stats"],
  ["sep"],["tactics","","Tactics"],["training","","Training"],["youth","","Youth"],["staff","","Staff"],
  ["sep"],["transfers","","Transfers"],["scouting","","Scouting"],["finances","","Finances"],
  ["sep"],["table","","Table"],["comps","","Competitions"],["calendar","","Calendar"],["inbox","","News"],
  ["sep"],["club","","Club"],["board","","Board"],["media","","Media"],["career","","Career"],
];
/* Grouped menu for the More sheet — every screen, organised, no emoji wall */
const MENU_GROUPS=[
  {label:"Club", items:[["tactics","Tactics","Formations & instructions"],["training","Training","Weekly schedule"],["youth","Youth","Academy & intake"],["facilities","Facilities","Invest in your ground"],["staff","Staff","Backroom team"]]},
  {label:"Market", items:[["transfers","Transfers","Targets, bids, offers"],["scouting","Scouting","Scouts & knowledge"],["finances","Finances","Budget & ledger"]]},
  {label:"World", items:[["table","Table","League standings"],["comps","Competitions","All tournaments"],["calendar","Calendar","Fixtures by date"],["inbox","News","Inbox & media"]]},
  {label:"Office", items:[["board","Board","Confidence & objectives"],["media","Media","Press & narrative"],["career","Career","History & trophies"]]},
];
function renderNav(items){
  const real=items.filter(n=>n[0]!=="sep");
  document.body.classList.toggle("pregame",real.length===0);
  $("#nav").innerHTML=items.map(n=>n[0]==="sep"?'<div class="sep"></div>':`<button data-s="${n[0]}" onclick="go('${n[0]}')"><span>${n[2]}</span><span class="badge hidden" id="nb-${n[0]}"></span></button>`).join("");
  renderTabbar(real); renderSheet(real);
}
async function enterGame(){ $("#splash").classList.add("hidden"); $("#app").classList.remove("hidden"); renderNav(NAV); await go("home"); }
async function resumeMatch(){ const r=await api.post("/api/match/abandon",{}); if(r&&r.ok){ G.pendingMatch=false; await refreshState(); showResult(r.result); } else toast(esc((r&&r.msg)||"No paused match"),4000); }
const SCREEN_ORDER=["home","inbox","squad","tactics","match","comps","transfers","scouting","finances","calendar","table","club","board","training","career"];
function getNavDir(ns,os){ const a=SCREEN_ORDER.indexOf(os||"home"), b=SCREEN_ORDER.indexOf(ns||"home"); if(a===-1||b===-1) return 0; return b>a?1:b<a?-1:0; }
async function go(screen,sub){
  const prev=G.screen; G.prevScreen=prev; G.screen=screen; G.sub=sub||null;
  $$("#nav button").forEach(b=>b.classList.toggle("active",b.dataset.s===screen));
  $$("#tabbar button").forEach(b=>b.classList.toggle("active",b.dataset.s===screen));
  $$("#sheet-grid button").forEach(b=>b.classList.toggle("active",b.dataset.s===screen));
  $$("#tabbar button[data-s=__more]").forEach(b=>b.classList.toggle("active",!TAB_IDS.includes(screen)));
  closeSheet(); Juice.haptic("nav"); Juice.play("nav");
  const _c=$("#content"); if(_c){ const dir=getNavDir(screen,prev); _c.classList.remove("in","slide-left","slide-right"); _c.style.animation="none"; void _c.offsetWidth; _c.style.animation=""; if(dir!==0){ _c.classList.add(dir>0?"slide-left":"slide-right"); if(!document.getElementById("slide-kf")){ const s=document.createElement("style"); s.id="slide-kf"; s.textContent="@keyframes slide-left-in{from{opacity:0;transform:translateX(18px) scale(.98)}to{opacity:1;transform:translateX(0) scale(1)}}@keyframes slide-right-in{from{opacity:0;transform:translateX(-18px) scale(.98)}to{opacity:1;transform:translateX(0) scale(1)}}.slide-left{animation:slide-left-in .32s cubic-bezier(.2,.9,.3,1.15)}.slide-right{animation:slide-right-in .32s cubic-bezier(.2,.9,.3,1.15)}"; document.head.appendChild(s); } } else _c.classList.add("in"); }
  $("#content").innerHTML='<div style="display:grid;place-items:center;padding:40px 18px;gap:12px"><div style="width:36px;height:36px;border-radius:12px;background:linear-gradient(180deg,var(--acc2),var(--acc));display:grid;place-items:center"><div style="width:18px;height:18px;border:2px solid #031a0c;border-radius:50%;border-top-color:transparent;animation:spin .8s linear infinite"></div></div><div style="font-size:10px;letter-spacing:.12em;font-weight:900;color:var(--tx3)">LOADING</div></div><style>@keyframes spin{to{transform:rotate(360deg)}}</style>';
  try{
    if(screen==="home") await renderHome();
    else if(screen==="inbox") await renderInbox();
    else if(screen==="squad") await renderSquad();
    else if(screen==="player") await renderPlayer(sub);
    else if(screen==="tactics") await renderTactics();
    else if(screen==="training") await renderTraining();
    else if(screen==="match") await renderMatch();
    else if(screen==="transfers") await renderTransfers();
    else if(screen==="scouting") await renderScouting();
    else if(screen==="finances") await renderFinances();
    else if(screen==="staff") await renderStaff();
    else if(screen==="youth") await renderYouth();
    else if(screen==="facilities") await renderFacilities();
    else if(screen==="calendar") await renderCalendar();
    else if(screen==="table") await renderTable();
    else if(screen==="stats") await renderStats();
    else if(screen==="comps") await renderComps();
    else if(screen==="club") await renderClub();
    else if(screen==="board") await renderBoard();
    else if(screen==="media") await renderMedia();
    else if(screen==="career") await renderCareer();
    else if(screen==="jobs") await renderJobs();
  } catch(e){ if(e.status===400 && /no active career/i.test(e.message||"")){ showStartScreen(); return; } $("#content").innerHTML=`<div class="card" style="border-color:#5a1a22"><h3 style="color:var(--red)">Error</h3><p class="small muted">${esc(e.message)}</p><div style="display:flex;gap:8px;margin-top:10px"><button class="btn sm" onclick="go('${screen}')">Retry</button><button class="btn sm primary" onclick="go('home')">Home</button></div></div>`; }
  $("#content").scrollTop=0; polish($("#content")); refreshBadges();
}
async function refreshState(){
  const j=await api.get("/api/state"); G.home=j.home;
  const was=G.pendingMatch; G.pendingMatch=!!j.pending_match;
  if(was&&!G.pendingMatch&&G.halftimeState){ G.halftimeState=null; toast("Paused match abandoned after restart"); }
  paintTop(); return j;
}
function continueLabel(){ const nf=G.home&&G.home.next_fixture; if(G.pendingMatch||(nf&&G.home&&nf.date===G.home.date)) return "MATCH DAY"; return "CONTINUE"; }
function paintTop(){
  const h=G.home; if(!h) return;
  const _pl0=$("#btn-continue .pl"); if(_pl0&&!G.busy) _pl0.textContent=continueLabel();
  if(h.unemployed){
    $("#tb-club").innerHTML=`<span style="font-weight:950">UNEMPLOYED</span><small>Available</small>`;
    $("#tb-budget").innerHTML=`<span class="chip-ic"></span><span>—</span>`;
    $("#tb-board").innerHTML=`<span class="chip-ic"></span><span>—</span>`;
    paintCrest("");
  } else {
    $("#tb-club").innerHTML=`<span style="font-weight:950">${esc(h.club.name)}</span><small>${esc(h.club.league)}</small>`;
    $("#tb-budget").innerHTML=`<span class="chip-ic"></span><span>${money(h.finances.transfer_budget)}</span>`;
    const conf=Math.round(h.board.confidence); const col=conf<30?"var(--red)":conf<55?"var(--amber)":"var(--acc)";
    $("#tb-board").innerHTML=`<span class="chip-ic"></span><span style="color:${col};font-weight:950">${conf}</span>`;
    paintCrest(h.club.code);
  }
  $("#tb-date").innerHTML=`${fmtDate(h.date).replace(/, \d{4}$/,"").split(" ").slice(0,2).join(" ")}`;
  const _ib=$("#tb-inbox"); if(_ib&&!_ib.dataset.count) _ib.innerHTML=`<span class="chip-ic"></span><span>News</span>`;
  const nf=h.next_fixture;
  if(nf){ const isRival=isRivalry(nf.home_code,nf.away_code); $("#tb-next").innerHTML=`${isRival?'':''}<b>${esc(nf.home_short)} v ${esc(nf.away_short)}</b>`; }
  else $("#tb-next").innerHTML=`—`;
  $("#btn-continue").disabled=G.busy; $("#btn-continue").classList.toggle("busy",G.busy);
}
async function refreshBadges(){ try{ const j=await api.get("/api/inbox?unread=true"); const n=j.items.length; const spots=[...document.querySelectorAll('[data-badge="inbox"],[data-badge="__more"]')]; const b=$("#nb-inbox"); if(b) spots.push(b); spots.forEach(el=>{ el.textContent=n; el.classList.toggle("hidden",!n); }); const ib=$("#tb-inbox"); if(ib){ ib.innerHTML=`<span class="chip-ic"></span><span${n?' style="color:var(--acc);font-weight:950"':""}>News${n?` · ${n}`:""}</span>`; } } catch(e){} }

/* CONTINUE */
$("#btn-continue").addEventListener("click",doContinue);
async function doContinue(){
  if(G.busy) return;
  if(G.pendingMatch){ toast("Finish paused match first",4000); go("match"); return; }
  G.busy=true; $("#btn-continue").disabled=true; setBusy(true);
  const _pl=$("#btn-continue .pl"); if(_pl) _pl.textContent="SIMULATING…";
  try{
    const j=await api.post("/api/continue",{});
    await refreshState();
    if((j.urgent||[]).length) await api.post("/api/inbox/read",{ids:j.urgent.map(u=>u.id)}).catch(()=>{});
    showContinueModal(j);
  } catch(e){ toast("Continue failed: "+esc(e.message),6000); }
  G.busy=false; $("#btn-continue").disabled=false; setBusy(false);
  const _pl2=$("#btn-continue .pl"); if(_pl2) _pl2.textContent=continueLabel();
}
function showContinueModal(j){
  const nf=j.next_fixture, items=j.log||[], urg=j.urgent||[];
  modal(`
    <h2>${fmtDate(j.date)} <span class="small muted">· ${j.season}/${String(j.season+1).slice(2)} · +${j.days_advanced}d</span></h2> ${j.unemployed?`<p class="small muted">Unemployed. <a href="#" onclick="closeModal();go('jobs')">View jobs →</a></p>`:""}
    ${nf?`<div class="card tight" style="margin:10px 0"><div style="display:flex;align-items:center;gap:8px"><b>Next:</b> ${esc(nf.home)} v ${esc(nf.away)}<span class="small muted">${esc(nf.comp||"")} ${fmtDate(nf.date)}</span><span class="spacer"></span><button class="btn primary sm" onclick="closeModal();go('match')">MATCH ▶</button></div></div>`:""}
    ${urg.length?`<h3 style="margin-top:10px">Urgent</h3>${urg.map(u=>`<div class="mrow unread" onclick="closeModal();go('inbox')"><span class="mdot"></span><div class="mmain"><b style="font-size:12px">${esc(u.subject)}</b><div class="small muted">${esc(u.cat)}</div></div></div>`).join("")}`:""}
    <h3 style="margin-top:10px">What happened</h3> <div style="max-height:38vh;overflow:auto;margin-top:6px">${items.length?items.slice().reverse().map(e=>e.type==="match_scheduled"?`<div style="padding:8px;border-radius:10px;background:var(--panel2);margin-bottom:6px"><b style="font-size:12px">Match day: ${e.fixtures.map(f=>`${esc(f.home)} v ${esc(f.away)}`).join(", ")}</b></div>`:`<div style="padding:6px 0;border-bottom:1px solid rgba(255,255,255,.04);font-size:12px"><span class="small muted">${esc(e.date||"")}</span> ${esc(e.text||"")}</div>`).join(""):'<p class="small muted">Nothing notable</p>'}</div> <div style="display:flex;gap:8px;margin-top:12px;justify-content:flex-end"><button class="btn sm" onclick="closeModal()">Close</button><button class="btn primary sm" onclick="closeModal();doContinue()">CONTINUE ▶</button></div>`, true);
}

/* comps helpers */
function compLabel(f){ return f.comp || (f.stage && f.stage!=="league"?f.stage:"") || "Match"; }
function compColor(code){ code=code||""; if(code==="UCL") return "#2a5bd7"; if(code==="UEL") return "#ff6900"; if(code==="UECL") return "#00b050"; if(code==="FACUP") return "#ff4444"; if(code==="EFLCUP") return "#00c851"; if(code.includes("CUP")||code.includes("POKAL")||code.includes("COUPE")) return "#ffb454"; if(code==="ENG1") return "#37003c"; if(code.startsWith("ENG")) return "#37003c"; if(code.startsWith("ESP")) return "#ff4b44"; if(code.startsWith("ITA")) return "#008c99"; if(code.startsWith("GER")) return "#d20515"; if(code.startsWith("FRA")) return "#091c3e"; return "#2cff8a"; }
function compClass(code){ code=code||""; if(code==="UCL") return "comp-UCL"; if(code==="UEL") return "comp-UEL"; if(code==="UECL") return "comp-UECL"; if(code==="FACUP") return "comp-FACUP"; if(code==="EFLCUP") return "comp-EFLCUP"; if(code==="ENG1") return "comp-ENG1"; if(code.startsWith("ENG")) return "comp-ENG1"; if(code.startsWith("ESP")) return "comp-ESP1"; if(code.startsWith("ITA")) return "comp-ITA1"; if(code.startsWith("GER")) return "comp-GER1"; if(code.startsWith("FRA")) return "comp-FRA1"; return ""; }
function formPills(form,n){ return (form||[]).slice(0,n||6).map(x=>`<i class="fm-i ${x.res}">${x.res}</i>`).join(""); }
function isRivalry(hc,ac){ try{ const r=(G.static&&G.static.rivalries)||{}; if(!r) return null; const rivals=r[hc]||[]; if(rivals.includes(ac)) return {type:"derby",name:(G.static.derby_names&&G.static.derby_names[hc+"-"+ac])||(G.static.derby_names&&G.static.derby_names[ac+"-"+hc])||"Derby"}; const r2=r[ac]||[]; if(r2.includes(hc)) return {type:"derby",name:(G.static.derby_names&&G.static.derby_names[ac+"-"+hc])||"Derby"}; return null; } catch(e){ return null; } }
function pressHypeForFixture(f){
  if(!f) return "";
  const rivalry=isRivalry(f.home_code,f.away_code);
  const isBig=(f.code==="UCL"||f.code==="ENG1"||(f.stage&&f.stage!=="league"));
  const isFriendly=f.code==="friendly"||(f.comp||"").toLowerCase().includes("friendly");
  if(isFriendly) return `<div class="int-break"><h3>Friendly — rotation</h3><p>Youth + reserves expected. Low intensity. Test tactics without risk.</p></div>`;
  if(rivalry) return `<div class="derby-banner">${esc(rivalry.name.toUpperCase())} — MORE THAN 3 POINTS</div><div class="press-hype"><h4>Press — derby hype</h4><p>\"Electric atmosphere. ${esc(f.home)} vs ${esc(f.away)} — pride, history, bragging rights.\"</p><div class="press-actions"><button class="btn sm" onclick="press('confident')\">Crush them</button><button class="btn sm" onclick="press('balanced')\">Respect</button><button class="btn sm" onclick="press('defensive')\">Our game</button></div></div>`;
  if(isBig){ const quotes=[`“Big game under lights. ${esc(f.home)} vs ${esc(f.away)}.”`,`“These games you live for.”`,`“Fans talking all week. Deliver.”`]; return `<div class="press-hype"><h4> Matchday hype</h4><p>${esc(quotes[Math.floor(Math.random()*quotes.length)])}</p><div class="press-actions"><button class="btn sm" onclick="press('confident')\">Back boys </button><button class="btn sm" onclick="press('balanced')\">Grounded </button></div></div>`; }
  return "";
}

/* Home */
function gaugeSVG(val,max,color,label,icon){
  const pct=Math.max(0,Math.min(1,val/max)), circ=2*Math.PI*30, dash=circ*pct;
  return `<div style="text-align:center;flex:1"><div style="position:relative;width:64px;height:64px;margin:0 auto"><svg viewBox="0 0 72 72" style="width:100%;height:100%;transform:rotate(-90deg)"><circle cx="36" cy="36" r="30" fill="none" stroke="rgba(255,255,255,.07)" stroke-width="5"/><circle cx="36" cy="36" r="30" fill="none" stroke="${color}" stroke-width="5" stroke-linecap="round" stroke-dasharray="${dash} ${circ-dash}" style="filter:drop-shadow(0 0 5px ${color})"/></svg><div style="position:absolute;inset:0;display:grid;place-items:center"><div><div style="font-size:16px">${icon}</div><div style="font-weight:950;font-size:13px;font-family:var(--ff-mono)">${Math.round(val)}</div></div></div></div><div style="font-size:9px;letter-spacing:.1em;font-weight:900;color:var(--tx3);margin-top:4px">${label}</div></div>`;
}
async function renderHome(){
  await refreshState(); const h=G.home; if(h.unemployed) return renderJobs();
  let adv=null; try{ adv=await api.get("/api/advice"); } catch(e){}
  const pos=h.position, f=h.next_fixture, ss=h.squad_summary;
  const ft=(ss.groups.find(g=>g.squad==="First Team")||{n:0}).n;
  const pills=formPills(h.form,6), avail=Math.max(0,ft-ss.injured-ss.suspended-ss.unfit);
  const tbl=h.table||[], mine=tbl.find(r=>r.club_id===h.club.id), top=tbl.slice(0,5);
  const rowHtml=r=>`<div style="display:flex;align-items:center;gap:6px;padding:6px 8px;border-radius:10px;${r.club_id===h.club.id?"background:rgba(44,255,138,.12);border:1px solid rgba(44,255,138,.18)":"background:rgba(255,255,255,.03);border:1px solid transparent"}"><span style="font-size:10px;font-weight:900;min-width:16px;text-align:center;color:${r.club_id===h.club.id?"var(--acc)":"var(--tx3)"}">${r.pos||"–"}</span>${crest(r.code)}<span style="flex:1;font-weight:800;font-size:11px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(r.name)}</span><b style="font-size:12px;min-width:18px;text-align:right;font-family:var(--ff-mono)">${r.pts}</b></div>`;
  const rivalry=f?isRivalry(f.home_code,f.away_code):null;
  const intBreak=(()=>{ try{ const d=new Date(h.date); const m=d.getMonth(); if([2,5,8,9,10].includes(m)&&d.getDate()<=14) return true; return false; } catch(e){ return false; } })();
  $("#content").innerHTML=`
    ${intBreak?`<div style="margin-bottom:10px;padding:12px;border-radius:14px;background:linear-gradient(135deg,#121e3a,#162a4a);border:1px solid #1a3a5a"><div style="display:flex;align-items:center;gap:10px"><div style="width:36px;height:36px;border-radius:10px;background:rgba(77,158,255,.15);display:grid;place-items:center"></div><div style="flex:1"><b style="font-size:12px;color:#7fb2ff">International break</b><div class="small muted" style="font-size:10px">Youth training with first team</div></div><button class="btn sm" onclick="go('squad')">Squad</button></div></div>`:""}
    ${f?`${rivalry?`<div class="derby-banner">${esc(rivalry.name.toUpperCase())} — DERBY</div>`:""}<div class="mhero ${compClass(f.code)}" style="--comp:${compColor(f.code)}"><div class="mhero-top">${compLogo(f.code)}<span class="comp-dot"></span><span>${esc(compLabel(f))}${f.stage&&f.stage!=="league"?" · "+esc(f.stage):""}</span><span class="spacer"></span><span style="font-size:10px">${fmtDate(f.date).split(",")[0]}</span></div><div class="mhero-body"><div class="mhero-club"><div style="width:56px;height:56px;border-radius:14px;background:var(--panel3);border:1px solid var(--line);display:grid;place-items:center;box-shadow:var(--shadow)">${crest(f.home_code,"lg")}</div><div class="nm">${esc(f.home)}</div><div class="small muted" style="font-size:10px">${f.is_home?"HOME":"AWAY"}</div><div style="margin-top:4px;display:flex;justify-content:center;gap:2px">${formPills(f.is_home?(G.home.form||[]):[],3)}</div></div><div class="mhero-mid"><div style="width:40px;height:40px;border-radius:50%;background:linear-gradient(180deg,var(--acc2),var(--acc));display:grid;place-items:center;font-weight:950;font-size:12px;color:#031a0c;box-shadow:0 4px 14px var(--acc-glow)">VS</div><div style="font-size:9px;font-weight:900;letter-spacing:.1em;color:var(--tx3);margin-top:6px">${f.is_home?"AT HOME":"AWAY"}</div></div><div class="mhero-club"><div style="width:56px;height:56px;border-radius:14px;background:var(--panel3);border:1px solid var(--line);display:grid;place-items:center;box-shadow:var(--shadow)">${crest(f.away_code,"lg")}</div><div class="nm">${esc(f.away)}</div><div class="small muted" style="font-size:10px">${!f.is_home?"HOME":"AWAY"}</div><div style="margin-top:4px;display:flex;justify-content:center;gap:2px">${formPills(!f.is_home?(G.home.form||[]):[],3)}</div></div></div><div class="mhero-foot"><button class="btn primary" style="flex:1;min-height:44px;border-radius:12px" onclick="Juice.haptic('heavy');go('match')">▶ MATCH CENTRE</button><button class="btn" style="min-height:44px;min-width:48px;border-radius:12px" onclick="quickPlay()">SIM</button></div></div><div style="margin-top:8px">${pressHypeForFixture(f)}</div>`: `<div style="padding:20px;border-radius:16px;background:var(--panel);border:1px solid var(--line);text-align:center"><h3 style="margin-top:6px">Season done</h3><p class="small muted">Continue for awards & new season</p><button class="btn primary sm" style="margin-top:8px" onclick="doContinue()">Continue ▶</button></div>`}
    <div class="card tight" style="margin-top:12px"> <div style="display:flex;align-items:center;justify-content:space-between"><b style="font-size:12px">Season</b><span class="small muted">${G.home.season_label}</span></div> <div class="kvgrid"> <div class="kv-c"><small>Position</small><b>${pos?pos.pos+"th":"–"}<i>of ${pos?pos.size:"–"}</i></b></div> <div class="kv-c"><small>Points</small><b>${pos?pos.pts:0}<i>${pos&&pos.gd?(pos.gd>0?"+":"")+pos.gd:""}</i></b></div> <div class="kv-c"><small>Board</small><b style="color:${h.board.confidence<35?"var(--red)":h.board.confidence<55?"var(--amber)":"var(--acc)"}">${Math.round(h.board.confidence)}</b></div> <div class="kv-c"><small>Fans</small><b style="color:${h.fans.sentiment<35?"var(--red)":h.fans.sentiment<55?"var(--amber)":"var(--acc)"}">${Math.round(h.fans.sentiment)}</b></div> </div> <div style="display:flex;align-items:center;gap:8px;margin-top:8px"><small class="muted" style="font-size:10px">Form</small>${pills||"—"}<span class="spacer"></span><button class="btn sm" onclick="go('stats')">Stats ▸</button></div> </div><div style="padding:8px;border-radius:10px;background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.05);text-align:center"><div style="font-size:9px;color:var(--tx3);font-weight:900;letter-spacing:.08em">FORM</div><div style="margin-top:4px;display:flex;justify-content:center;gap:2px">${pills||"—"}</div></div><div style="padding:8px;border-radius:10px;background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.05);text-align:center"><div style="font-size:9px;color:var(--tx3);font-weight:900;letter-spacing:.08em">CASH</div><div style="font-weight:950;font-size:13px;margin-top:2px;color:var(--acc);font-family:var(--ff-mono)">${money(h.finances.cash)}</div></div></div> </div> <div style="margin-top:10px;display:grid;grid-template-columns:1fr 1fr;gap:8px"> <button onclick="Juice.haptic('tap');go('squad')" style="text-align:left;padding:12px;border-radius:12px;background:var(--panel);border:1px solid var(--line);color:var(--tx)"><div style="font-weight:800;font-size:12px">Squad</div><div style="font-size:10.5px;color:var(--tx3);margin-top:3px">${avail} fit · ${ss.injured} injured · ${ss.suspended} banned</div>${avail<14?'<div style="margin-top:6px;font-size:10px;color:#ff8a94">Squad thin — sign or promote</div>':""}</button> <button onclick="Juice.haptic('tap');go('board')" style="text-align:left;padding:12px;border-radius:12px;background:var(--panel);border:1px solid var(--line);color:var(--tx)"><div style="font-weight:800;font-size:12px">Board</div><div style="font-size:10.5px;color:var(--tx3);margin-top:3px">${h.board.objectives[0]?esc(h.board.objectives[0].text).slice(0,40):"No objectives"}</div><div style="margin-top:6px;font-size:10px;font-weight:800;color:${h.board.warning?"#ff8a94":"var(--acc)"}">${h.board.warning?"UNDER PRESSURE":"CONFIDENT"}</div></button> </div> ${godCard(adv)}
    <div style="margin-top:10px;display:grid;grid-template-columns:1fr 1fr;gap:8px"> <div style="padding:0;border-radius:14px;background:var(--panel);border:1px solid var(--line);overflow:hidden;box-shadow:var(--shadow-float)"><div style="padding:10px 12px 6px;display:flex;align-items:center;justify-content:space-between"><b style="font-size:11px"> ${esc(h.club.league)}</b><button class="btn sm" onclick="go('table')">Full ▸</button></div><div style="padding:0 6px 6px;display:grid;gap:3px">${top.map(rowHtml).join("")}${mine&&mine.pos>5?`<div style="text-align:center;padding:4px;font-size:9px;color:var(--tx3)">you are ${mine.pos}th</div>${rowHtml(mine)}`:""}</div></div> <div style="padding:0;border-radius:14px;background:var(--panel);border:1px solid var(--line);overflow:hidden;box-shadow:var(--shadow-float)"><div style="padding:10px 12px 6px;display:flex;align-items:center;justify-content:space-between"><b style="font-size:11px"> News</b><div style="display:flex;gap:4px;align-items:center">${h.unread?`<span style="min-width:16px;height:16px;padding:0 4px;border-radius:999px;background:var(--red);color:white;font-size:10px;font-weight:900;display:grid;place-items:center">${h.unread}</span>`:""}<button class="btn sm" onclick="go('inbox')">Open ▸</button></div></div><div id="home-inbox" style="padding:0 6px 6px;display:grid;gap:3px"></div></div> </div>`;
  const ib=await api.get("/api/inbox");
  $("#home-inbox").innerHTML=ib.items.slice(0,3).map(m=>`<button onclick="Juice.haptic('tap');openMail(${m.id})" style="text-align:left;width:100%;padding:8px;border-radius:10px;background:${m.read?"rgba(255,255,255,.03)":"rgba(44,255,138,.1)"};border:1px solid ${m.read?"rgba(255,255,255,.05)":"rgba(44,255,138,.16)"};color:var(--tx);display:flex;gap:6px"><span style="width:5px;height:5px;border-radius:50%;background:${m.priority==="URGENT"?"var(--red)":m.priority==="IMPORTANT"?"var(--amber)":"var(--acc)"};margin-top:5px;flex:none;opacity:${m.read?".3":"1"}"></span><span style="flex:1;min-width:0"><span style="font-weight:800;font-size:11px;display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(m.subject)}</span><span style="font-size:9px;color:var(--tx3)">${esc(m.cat)}</span></span></button>`).join("")||'<div style="padding:12px;text-align:center" class="small muted">Quiet day </div>';
}
function godCard(adv){
  if(!adv||!adv.ok) return "";
  const items=adv.on?(adv.items||[]).map(it=>`<div class="god-it"><span class="tag ${it.tag==="INBOX"||it.tag==="BOARD"?"URGENT":""}">${esc(it.tag)}</span><div style="flex:1"><b style="font-size:11px">${esc(it.t)}</b><div class="small muted" style="font-size:10px">${esc(it.b)}</div></div>${it.go?`<button class="btn sm" onclick="go('${it.go}')">OPEN</button>`:""}</div>`).join(""):'<p class="small muted">Off.</p>';
  return `<div class="card god ${adv.on?"on":""}" style="margin-top:10px"><div style="display:flex;align-items:center;gap:10px"><div class="god-m">GF</div><div style="flex:1"><div style="font-size:9px;letter-spacing:.12em;font-weight:900;color:var(--tx3)">GODFATHER MODE</div><div class="small muted" style="font-size:10px">Suggested next moves</div></div><label class="sw"><input type="checkbox" ${adv.on?"checked":""} onchange="toggleGod(this.checked)"><span></span></label></div>${adv.on?`<div style="margin-top:10px;display:grid;gap:6px">${items||'<p class="small muted">Nothing needs you</p>'}</div>${godPlan(adv.plan)}`:items}</div>`;
}
function godPlan(pl){
  if(!pl) return ""; const t=pl.tactics;
  return `<div class="god-plan"><div class="gp-b"><div class="gp-h">Best XI</div><div class="gp-x">${(pl.xi_names||[]).map(n=>`<span>${esc(n)}</span>`).join("")||'<i class="small muted">No fit</i>'}</div><button class="btn sm primary" onclick="godXI()">Select XI ▶</button></div>${t?`<div class="gp-b"><div class="gp-h">Plan v ${esc((pl.opp||{}).name||"opp")}</div><p class="small muted" style="font-size:10px">${esc(t.mentality)} · ${esc(t.formation)} — ${esc(t.why)}</p><button class="btn sm primary" onclick="godTactics()">Apply ▶</button></div>`:""}${(pl.sign||[]).length?`<div class="gp-b"><div class="gp-h">Sign</div>${pl.sign.map(g=>`<div class="gp-s"><div style="flex:1;min-width:0"><b style="font-size:11px">${esc(g.name)}</b> <span class="small muted">${esc(g.pos)} · ${g.age}y · CA ${g.ca}</span><div class="small muted">${esc(g.club)} · ~${money(g.value)}</div></div><button class="btn sm" onclick="go('player',${g.pid})">View</button><button class="btn sm primary" onclick="godBid(${g.pid},${Math.round(g.value)},${Math.round(g.wage)})">Bid</button></div>`).join("")}</div>`:""}</div>`;
}
async function godXI(){ const adv=await api.get("/api/advice"); const ids=(adv.plan||{}).xi||[]; if(!ids.length) return toast("No XI",4000); const r=await api.post("/api/match/select",{ids}); toast(r.ok?"Godfather XI selected":"Failed",4000); if(r.ok) go("match"); }
async function godTactics(){ const adv=await api.get("/api/advice"); const t=(adv.plan||{}).tactics; if(!t) return toast("No plan",4000); const r=await api.post("/api/tactics",{mentality:t.mentality,instr:t.instr}); toast(r.ok?"Plan: "+t.mentality:"Failed",4000); if(r.ok) renderHome(); }
async function godBid(pid,fee,wage){ const r=await api.post("/api/transfer/offer",{pid,fee,wage:Math.max(wage,1),years:3}); toast(r.ok?"Offer sent":"Offer refused: "+(r.msg||""),5000); if(r.ok) renderHome(); }
async function toggleGod(on){ await api.post("/api/godfather",{on}); toast(on?"Godfather ON":"Godfather off"); renderHome(); }
async function quickPlay(){ await playMatch("instant"); }

/* INBOX — social feed */
let INBOX_CAT="";
async function renderInbox(){
  await refreshState();
  const j=await api.get("/api/inbox"+(INBOX_CAT?"?cat="+INBOX_CAT:""));
  const unread=j.items.filter(x=>!x.read).length, urgent=j.items.filter(x=>x.priority==="URGENT"&&!x.read).length;
  $("#content").innerHTML=`
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px"><b style="font-size:14px"> NEWS FEED</b><span class="spacer"></span>${unread?`<span class="tag NEW">${unread} new</span>`:""}${urgent?`<span class="tag URGENT">${urgent} urgent</span>`:""}<button class="btn sm" onclick="markAllRead()">Read all</button></div> <div style="display:flex;gap:6px;overflow-x:auto;padding-bottom:6px;margin-bottom:8px;scrollbar-width:none"><button onclick="INBOX_CAT='';renderInbox()" style="flex:none;padding:6px 12px;border-radius:999px;font-weight:900;font-size:11px;background:${!INBOX_CAT?"var(--acc-dim)":"var(--panel2)"};border:1px solid ${!INBOX_CAT?"rgba(44,255,138,.28)":"var(--line)"};color:${!INBOX_CAT?"var(--acc)":"var(--tx2)"}">All ${j.items.length?`(${j.items.length})`:""}</button>${j.cats.map(c=>`<button onclick="INBOX_CAT='${c}';renderInbox()" style="flex:none;padding:6px 12px;border-radius:999px;font-weight:800;font-size:11px;background:${INBOX_CAT===c?"var(--acc-dim)":"var(--panel2)"};border:1px solid ${INBOX_CAT===c?"rgba(44,255,138,.28)":"var(--line)"};color:${INBOX_CAT===c?"var(--acc)":"var(--tx2)"}">${esc(c)}${j.unread_by_cat[c]?` (${j.unread_by_cat[c]})`:""}</button>`).join("")}</div> <div class="card" style="padding:0;overflow:hidden">${j.items.length?j.items.map(m=>{
      const isInt=(m.cat||"").toLowerCase().includes("international"), isPress=(m.cat||"").toLowerCase().includes("media");
      const icon=m.priority==="URGENT"?"":m.priority==="IMPORTANT"?"":isInt?"":isPress?"":"";
      return `<button class="mrow p-${(m.priority||"").toLowerCase()} ${m.read?"":"unread"}" onclick="Juice.haptic('tap');openMail(${m.id})"><span class="mdot"></span><div style="width:32px;height:32px;border-radius:10px;background:var(--panel3);border:1px solid var(--line);display:grid;place-items:center;font-size:14px;flex:none">${icon}</div><div class="mmain"><div class="msub">${esc(m.subject)}</div><div style="font-size:11px;color:var(--tx2);margin-top:1px;line-height:1.3;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc((m.body||"").slice(0,90))}</div><div class="mmeta"><span class="mcat">${esc(m.cat)}</span><span>${fmtDate(m.date).split(",")[0]}</span>${!m.read?'<span class="tag NEW" style="font-size:8px;padding:1px 5px">NEW</span>':""}</div></div></button>`;
    }).join(""):`<div class="inbox-empty"><div class="ie-icon"></div><h3>All caught up</h3><p class="small muted">World quiet — continue</p><button class="btn sm primary" style="margin-top:10px" onclick="doContinue()">Continue ▶</button></div>`}</div>`;
}
async function markAllRead(){ await api.post("/api/inbox/read",{all:true}); renderInbox(); refreshBadges(); toast("All read ✓",2000); }
async function openMail(id){
  const j=await api.get("/api/inbox"); const m=j.items.find(x=>x.id===id); if(!m) return;
  await api.post("/api/inbox/read",{ids:[id]});
  const p=m.payload||{}, isInt=(m.cat||"").toLowerCase().includes("international"), isDerby=(m.subject||"").toLowerCase().includes("derby")||(m.body||"").toLowerCase().includes("derby");
  const extra=isInt?`<div class="int-break" style="margin-top:12px"><h3>International break</h3><p>Players away. Scout time. Check fitness on return.</p><div style="display:flex;gap:6px;margin-top:8px"><button class="btn sm" onclick="closeModal();go('squad')">Squad</button><button class="btn sm" onclick="closeModal();go('scouting')">Scout</button></div></div>`:isDerby?`<div class="derby-banner" style="margin-top:10px;border-radius:10px"> DERBY — BRAGGING RIGHTS </div>`:"";
  const bidAct=p.action==="incoming_bid"?`<div style="display:flex;gap:8px;margin-top:14px;flex-wrap:wrap;border-top:1px solid var(--line);padding-top:12px"><button class="btn primary sm" onclick="closeModal();bid(${p.offer_id},'accept')">Accept ${money(p.fee||0)} ✓</button><button class="btn sm" onclick="bidCounter(${p.offer_id},${p.fee||0},${p.asking||0},${p.value||0},'${esc((m.subject||"").replace(/^Transfer bid: /,"").replace(/'/g,"\\'"))}')">Counter…</button><button class="btn sm" onclick="closeModal();bid(${p.offer_id},'reject')">Reject</button></div>`:"";
  modal(`<div style="display:flex;gap:8px;align-items:center;margin-bottom:10px"><span class="tag ${m.priority}">${esc(m.priority)}</span><span class="tag">${esc(m.cat)}</span><span class="spacer"></span><span class="small muted">${fmtDate(m.date)}</span></div><h2 style="font-size:18px;line-height:1.2">${esc(m.subject)}</h2><div class="pre" style="margin-top:10px;font-size:12.5px">${esc(m.body)}</div>${extra}${bidAct}<div style="display:flex;gap:8px;margin-top:14px;justify-content:flex-end">${p.screen?`<button class="btn sm" onclick="closeModal();go('${esc(p.screen)}'${p.pid?",'"+p.pid+"'":""})">Open ${esc(p.screen)} ▶</button>`:""}<button class="btn primary sm" onclick="closeModal();renderInbox()">Done ✓</button></div>`, true);
  refreshBadges();
}

/* SQUAD — dressing room */
let SQUAD_FILTER="First Team", SQUAD_SORT="ca", SQUAD_Q="";
function filterSquadList(){
  const q=(SQUAD_Q||"").toLowerCase();
  $$("#content [data-pname]").forEach(el=>{ const nm=el.dataset.pname||""; el.style.display=!q||nm.toLowerCase().includes(q)?"":"none"; });
}
async function renderSquad(){
  await refreshState(); const j=await api.get("/api/screen/squad");
  const players=j.players.filter(p=>SQUAD_FILTER==="All"||p.squad===SQUAD_FILTER).filter(p=>!SQUAD_Q||p.name.toLowerCase().includes(SQUAD_Q.toLowerCase()));
  const groups=["All","First Team","Reserve","U21","Youth"];
  const sortFn={ca:(a,b)=>b.ca-a.ca,pos:(a,b)=>a.pos.localeCompare(b.pos)||b.ca-a.ca,age:(a,b)=>a.age-b.age,value:(a,b)=>b.value-a.value,wage:(a,b)=>b.wage-a.wage,goals:(a,b)=>b.goals-a.goals,condition:(a,b)=>b.condition-a.condition,name:(a,b)=>a.name.localeCompare(b.name)}[SQUAD_SORT];
  players.sort(sortFn);
  const all=j.players, injured=all.filter(p=>p.injured), susp=all.filter(p=>p.suspended>0), fit=all.filter(p=>!p.injured&&!p.suspended&&p.condition>=0.9);
  $("#content").innerHTML=`
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px"><b style="font-size:13px"> DRESSING ROOM</b><span class="small muted">${G.home.club.name} · ${fit.length} fit</span><span class="spacer"></span><select onchange="SQUAD_SORT=this.value;renderSquad()" style="min-height:32px;font-size:11px">${[["ca","Ability"],["pos","Position"],["age","Age"],["value","Value"],["goals","Goals"],["condition","Cond"]].map(o=>`<option value="${o[0]}" ${SQUAD_SORT===o[0]?"selected":""}>${o[1]}</option>`).join("")}</select></div> <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin-bottom:10px"><div style="padding:10px;border-radius:12px;background:linear-gradient(135deg,#0a2a18,#0f2a1c);border:1px solid rgba(44,255,138,.18);text-align:center"><div style="font-weight:950;font-size:18px;color:var(--acc)">${fit.length}</div><div style="font-size:9px;letter-spacing:.1em;color:var(--acc);font-weight:900">FIT</div></div><div style="padding:10px;border-radius:12px;background:#2a1218;border:1px solid rgba(255,59,74,.18);text-align:center"><div style="font-weight:950;font-size:18px;color:#ff6b7a">${injured.length}</div><div style="font-size:9px;letter-spacing:.1em;color:#ff8a94;font-weight:900">INJ</div></div><div style="padding:10px;border-radius:12px;background:#2a1e0a;border:1px solid rgba(255,176,46,.18);text-align:center"><div style="font-weight:950;font-size:18px;color:var(--amber)">${susp.length}</div><div style="font-size:9px;letter-spacing:.1em;color:#ffcc8a;font-weight:900">BAN</div></div><div style="padding:10px;border-radius:12px;background:var(--panel);border:1px solid var(--line);text-align:center"><div style="font-weight:950;font-size:18px;font-family:var(--ff-mono)">${(all.reduce((a,b)=>a+b.age,0)/(all.length||1)).toFixed(1)}</div><div style="font-size:9px;letter-spacing:.1em;color:var(--tx3);font-weight:900">AGE</div></div></div> <div style="display:flex;gap:5px;overflow-x:auto;padding-bottom:6px;margin-bottom:8px;scrollbar-width:none">${groups.map(g=>`<button onclick="Juice.haptic('tap');SQUAD_FILTER='${g}';renderSquad()" style="flex:none;padding:6px 12px;border-radius:10px;font-weight:900;font-size:11px;border:1px solid ${SQUAD_FILTER===g?"rgba(44,255,138,.35)":"var(--line)"};background:${SQUAD_FILTER===g?"var(--acc-dim)":"var(--panel2)"};color:${SQUAD_FILTER===g?"var(--acc)":"var(--tx2)"}">${g}</button>`).join("")}<input id="sq-q" placeholder="Search…" value="${esc(SQUAD_Q||"")}" oninput="SQUAD_Q=this.value;filterSquadList()" style="flex:none;width:110px;min-height:32px;border-radius:10px;font-size:11px"></div> <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:8px"> ${players.map(p=>{
        const ini=p.name.split(" ").map(w=>w[0]).slice(0,2).join("").toUpperCase();
        const condColor=p.condition>1.02?"#2cff8a":p.condition<0.92?"#ff3b4a":"#ffb02e";
        const status=p.injured?"INJ":p.suspended?"BAN":p.condition<0.9?"UNFIT":"FIT";
        const statusColor=p.injured?"#ff3b4a":p.suspended?"#ffb02e":p.condition<0.9?"#ffb02e":"#2cff8a";
        return `<button data-pname="${esc(p.name)}" onclick="Juice.haptic('tap');go('player',${p.id})" style="text-align:left;padding:10px;border-radius:14px;background:linear-gradient(165deg,var(--panel2),var(--panel));border:1px solid ${p.listed?"rgba(255,59,74,.28)":"var(--line)"};color:var(--tx);position:relative;overflow:hidden;box-shadow:var(--shadow)"> <div style="position:absolute;top:0;left:0;right:0;height:2px;background:${condColor}"></div> <div style="display:flex;gap:8px;align-items:flex-start"><div style="width:38px;height:38px;border-radius:10px;background:linear-gradient(180deg,var(--panel3),var(--panel2));border:1px solid var(--line);display:grid;place-items:center;font-weight:950;font-size:11px">${ini}</div><div style="flex:1;min-width:0"><div style="font-weight:900;font-size:11px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(p.name)}</div><div style="display:flex;gap:3px;margin-top:2px"><span style="font-size:9px;padding:1px 5px;border-radius:6px;background:var(--panel3);font-weight:900">${esc(p.pos)}</span><span style="font-size:9px;padding:1px 5px;border-radius:6px;background:${statusColor}18;color:${statusColor};font-weight:900">${status}</span></div></div><div style="text-align:right"><div style="font-weight:950;font-size:12px;color:${condColor};font-family:var(--ff-mono)">${p.ca.toFixed(1)}</div><div style="font-size:9px;color:var(--tx3)">${p.age}y</div></div></div> <div style="margin-top:8px;display:flex;justify-content:space-between;align-items:center"><span style="font-size:10px;color:var(--tx3)">${stars(p.stars)} · ${money(p.value)}</span><span style="font-size:9px;padding:2px 6px;border-radius:999px;background:var(--panel3);font-weight:800">${p.goals}G</span></div>${p.listed?`<div style="margin-top:6px;padding:3px;border-radius:6px;background:rgba(255,59,74,.12);font-size:9px;font-weight:900;color:#ff8a94;text-align:center"> LISTED</div>`:""}</button>`;
      }).join("")}
    </div> ${injured.length||susp.length?`<div style="margin-top:10px;padding:10px;border-radius:12px;background:linear-gradient(135deg,#1a1a30,#12182a);border:1px solid #1a2a4a"><b style="font-size:11px"> Physio</b><div style="margin-top:6px;display:grid;gap:4px">${injured.map(p=>`<div style="display:flex;justify-content:space-between;font-size:11px"><span style="color:#ff8a94">${esc(p.name)}</span><span class="small muted" style="font-size:10px">${esc(p.injury)}</span></div>`).join("")}${susp.map(p=>`<div style="display:flex;justify-content:space-between;font-size:11px"><span style="color:#ffcc8a">${esc(p.name)}</span><span class="small muted">susp ${p.suspended}</span></div>`).join("")}</div></div>`:""}`;
}

/* PLAYER */
async function renderPlayer(pid){
  const p=await api.get("/api/player/"+pid); await refreshState();
  const groups=p.attr_groups||null, ini=String(p.name).split(/\s+/).map(w=>w[0]).slice(0,2).join("").toUpperCase();
  const ratingCls=r=>r>=7.5?"good":r>=6.8?"":r>=6.2?"warn":"bad";
  $("#content").innerHTML=`
    <div style="display:flex;gap:8px;margin-bottom:10px"><button class="btn sm" onclick="go('squad')">◂ Squad</button><span class="spacer"></span><button class="btn sm" onclick="quickSell(${p.id},'${esc(p.name).replace(/'/g,"\\'")}')">Sell </button></div> <div class="card"><div class="p-head"><div class="p-ava">${ini}</div><div style="flex:1;min-width:0"><h2 style="font-size:16px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(p.name)}</h2><p class="small muted" style="font-size:11px">${esc(p.club)} · ${esc(p.nat)} · ${p.age}y · ${esc(p.foot)}</p></div><span class="pos">${esc(p.pos)}</span></div> <div style="display:grid;grid-template-columns:repeat(5,1fr);gap:6px;margin-top:12px">${[["CA",p.ca?.toFixed(1)||"?",p.stars!=null?stars(p.stars):"—"],["PA",p.pa?.toFixed(1)||"?",p.age<24?"dev":p.age>30?"dec":"peak"],["COND",p.condition.toFixed(2),`fit ${Math.round(p.fitness)}`],["FORM",`${p.form>0?"+":""}${p.form.toFixed(1)}`,`mor ${Math.round(p.morale)}`],["VALUE",money(p.value),wk(p.wage)]].map(([l,v,sub])=>`<div style="text-align:center;padding:8px;border-radius:10px;background:var(--panel2);border:1px solid var(--line)"><div style="font-size:9px;color:var(--tx3);font-weight:900;letter-spacing:.08em">${l}</div><div style="font-weight:950;font-size:13px;margin-top:2px">${v}</div><div style="font-size:10px;color:var(--tx3)">${sub}</div></div>`).join("")}</div> </div> ${p.injury?`<div class="card tight" style="margin-top:8px;border-color:rgba(255,59,74,.22);background:#2a1218"><b style="color:#ff6b7a;font-size:11px">Injured:</b> <span style="font-size:11px">${esc(p.injury)} — back ${fmtDate(p.return_date)}</span></div>`:""}
    ${p.suspended?`<div class="card tight" style="margin-top:8px;border-color:rgba(255,176,46,.22);background:#2a1e0a"><b style="color:var(--amber);font-size:11px">Suspended ${p.suspended}</b></div>`:""}
    ${groups?`<div class="card tight" style="margin-top:8px"><div style="display:flex;justify-content:space-between"><h3>Attributes</h3></div>${Object.entries(groups).filter(([g,a])=>a.length).map(([g,a])=>`<div class="attr-g"><h4>${esc(g)}</h4>${a.map(x=>`<div class="attr-r"><span class="k">${esc(x.k.replace(/_/g," "))}</span><span class="b"><i style="width:${Math.min(100,x.v/20*100)}%;background:${x.c==="good"||x.v>=15?"var(--acc)":x.v>=11?"var(--blue)":x.v>=8?"var(--amber)":"var(--red)"}"></i></span><span class="v">${x.v}</span></div>`).join("")}</div>`).join("")}</div>`:`<div class="card tight" style="margin-top:8px"><h3>Scouting ${p.known}%</h3><p class="small muted" style="margin-top:6px">Knowledge ${p.known}%. Attributes hidden until scouted.</p><button class="btn sm" style="margin-top:8px" onclick="assignScout(${p.id})">Assign scout</button></div>`}
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:8px"><div class="card tight"><h3>Season</h3><div class="kv"><span>Apps · mins</span><b>${p.apps} · ${p.minutes}</b></div><div class="kv"><span>G · A</span><b>${p.goals} · ${p.assists}</b></div><div class="kv"><span>Y · R</span><b>${p.yellow} · ${p.red}</b></div><div class="kv"><span>Rating</span><b>${p.avg_rating?p.avg_rating.toFixed(2):"—"}</b></div></div><div class="card tight"><h3>Recent</h3>${(p.recent||[]).length?(p.recent||[]).map(r=>`<div class="kv" style="font-size:11px"><span style="min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${fmtDate(r.date).split(",")[0]} · ${r.home?"v":"@"} ${esc(r.opp)} ${r.score}</span><b class="${ratingCls(r.rating)}">${r.rating.toFixed(2)}</b></div>`).join(""):'<p class="small muted">No matches</p>'}</div></div> ${p.mine?`<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:8px"><div class="card tight"><h3>Contract</h3><div class="kv"><span>Wage</span><b>${wk(p.wage)}</b></div><div class="kv"><span>Expires</span><b style="font-size:11px">${esc(p.contract_end)}</b></div><div class="kv"><span>Happiness</span><b>${Math.round(p.happiness)} ${p.happiness<30?"":p.happiness>80?"":""}</b></div><div class="kv"><span>Status</span><b>${p.listed?'<span class="tag URGENT">LISTED</span>':'<span class="tag ROUTINE">Not sale</span>'}</b></div><div style="margin-top:10px;display:grid;gap:6px"><div style="display:flex;gap:6px"><button class="btn sm" style="flex:1" onclick="renewTalk(${p.id},'${esc(p.name).replace(/'/g,"\\'")}',${p.wage})">New deal</button><button class="btn sm ${p.listed?"":"primary"}" style="flex:1" onclick="${p.listed?`toggleList(${p.id},false)`:`quickSell(${p.id},'${esc(p.name).replace(/'/g,"\\'")}')`}">${p.listed?"Unlist":"Sell "}</button></div><div style="display:flex;gap:6px"><button class="btn sm" style="flex:1" onclick="openPromise(${p.id},'${esc(p.name).replace(/'/g,"\\'")}','${esc(p.promise)}')">Time</button><button class="btn sm danger" style="flex:1" onclick="releasePlayer(${p.id},'${esc(p.name).replace(/'/g,"\\'")}')">Release</button></div></div></div><div class="card tight"><h3>Man mgmt</h3><p class="small muted" style="font-size:11px">Morale ${Math.round(p.morale)} · happy ${Math.round(p.happiness)} · ${esc(p.personality)}</p><div style="display:flex;gap:6px;margin-top:10px"><button class="btn sm" onclick="talkTo(${p.id},'praise')"> Praise</button><button class="btn sm" onclick="talkTo(${p.id},'criticise')"> Critic</button><button class="btn sm" onclick="talkTo(${p.id},'chat')"> Chat</button></div><div style="margin-top:10px;padding:8px;border-radius:10px;background:#12182a;border:1px solid #1a2a4a"><div style="font-size:10px;font-weight:900;color:#7fb2ff"> Realism</div><div class="small muted" style="font-size:10px;margin-top:2px">Rivalry blocks, loyalty 14+ stars stay, Haaland ≠ United</div></div></div></div>`: `<div class="card tight" style="margin-top:8px"><h3>Bid · Asking ${money(p.asking||0)}</h3><div style="display:flex;gap:8px;margin-top:10px"><button class="btn primary" style="flex:1" onclick="openOffer(${p.id},'${esc(p.name).replace(/'/g,"\\'")}',${p.asking||0},${p.wage||0})">Bid ${money(p.asking||0)} </button><button class="btn sm" onclick="toggleShortlist(${p.id})">☆ Shortlist</button></div></div>`}`;
}
async function talkTo(pid,kind){ const r=await api.post("/api/squad/talk",{pid,kind}); toast(esc(r.msg||"Done")); go("player",pid); }
async function openPromise(pid,name,cur){ const opts=G.static.promises; modal(`<h2>Time — ${esc(name)}</h2><p class="small muted">Current: <b>${esc(cur)}</b></p><div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:10px">${opts.map(o=>`<button class="btn sm" onclick="setPromise(${pid},'${esc(o)}')">${esc(o)}</button>`).join("")}</div><div style="display:flex;justify-content:flex-end;margin-top:12px"><button class="btn sm" onclick="closeModal()">Cancel</button></div>`); }
async function setPromise(pid,promise){ const r=await api.post("/api/squad/promise",{pid,promise}); closeModal(); toast(esc(r.msg||"Updated")); go("player",pid); }
async function renewTalk(pid,name,wage){ const w=prompt(`New wage for ${name} (cur €${wage}k):`,Math.round(wage*1.15)); if(!w) return; const y=prompt("Years:","2"); if(!y) return; const promise=prompt("Promise:","Regular Starter"); if(!promise) return; const r=await api.post("/api/contract/renew",{pid,wage:+w,years:+y,promise}); toast(esc(r.msg||(r.ok?"Agreed":"Failed")),5000); go("player",pid); }
async function toggleList(pid,listed){ const r=await api.post("/api/squad/list",{pid,listed}); toast(esc(r.msg||"Done")); go("player",pid); }
async function releasePlayer(pid,name){ if(!confirm(`Release ${name}?`)) return; const r=await api.post("/api/squad/release",{pid}); toast(esc(r.msg||"Released")); go("squad"); }
async function assignScout(pid){ const r=await api.post("/api/scout/assign",{pid}); toast(esc(r.msg||"Scout assigned")); }

/* TACTICS — chalkboard */
const POS_COORDS={ GK:[50,92], DC:[35,74], DL:[14,70], DR:[86,70], DM:[50,60], MC:[38,48], AMC:[50,36], AML:[14,38], AMR:[86,38], ST:[50,18] };
function pitchHTML(xi,clickable){
  const byPos={}; xi.forEach((x,i)=>(byPos[x.pos]=byPos[x.pos]||[]).push(i));
  return `<div class="pitch"><div class="lines"></div>${xi.map((x,i)=>{
    const c=POS_COORDS[x.pos]||[50,50], off=byPos[x.pos].indexOf(i)-(byPos[x.pos].length-1)/2, left=Math.max(6,Math.min(94,c[0]+off*19)), p=x.player;
    return `<div class="slot ${p?"":"empty"}" style="left:${left}%;top:${c[1]}%" ${clickable?`onclick="pickSlot(${i},'${x.pos}')"`:""}><div class="dot">${esc(x.pos)}</div><div class="nm">${p?esc(p.name.split(" ").slice(-1)[0])+" "+p.ca.toFixed(1):"empty"}</div>${p?`<div class="nm muted" style="font-size:9px">${Math.round(p.condition*100)}%${p.injured?" INJ":""}${p.suspended?" SUS":""}</div>`:""}${p&&x.role?`<div class="nm muted" style="font-size:8px">${esc(x.role.split(" ").map(w=>w[0]).join(""))} ${esc(x.duty||"")}${x.auto?" ·auto":""}</div>`:""}</div>`;
  }).join("")}</div>`;
}
const MENTALITY_NOTE={"Very Defensive":"Deep block — concedes little, creates little","Defensive":"Compact, cautious","Cautious":"Slightly reserved","Balanced":"Even risk","Positive":"Higher line, more chances","Attacking":"Bodies forward","All-Out Attack":"Everything forward, fragile"};
async function renderTactics(){
  const t=await api.get("/api/screen/tactics"); await refreshState();
  if(t.error){ $("#content").innerHTML=`<h1>Tactics</h1><p class="small muted">${esc(t.error)}</p>`; return; }
  window._tactics=t; const IOPT=G.static.instruction_options||{}, instr=t.tactic.instr||{};
  $("#content").innerHTML=`
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px"><b style="font-size:13px"> TACTICS · ${esc(t.tactic.formation)} · ${esc(t.tactic.mentality)}</b><span class="spacer"></span><span style="font-size:10px;padding:3px 8px;border-radius:999px;background:var(--acc-dim);color:var(--acc);font-weight:900">${Math.round(t.tactic.familiarity)}% FAM</span></div> <div style="display:grid;gap:10px"> <div class="card"><div style="display:flex;gap:6px;flex-wrap:wrap"><select id="tac-formation" onchange="changeFormation(this.value)" style="flex:1;min-width:120px">${G.static.formations.map(f=>`<option ${f===t.tactic.formation?"selected":""}>${f}</option>`).join("")}</select><select id="tac-mentality" onchange="saveTactics()" style="flex:1;min-width:120px">${G.static.mentalities.map(m=>`<option ${m===t.tactic.mentality?"selected":""}>${m}</option>`).join("")}</select><button class="btn sm" onclick="autoPickXI()">Auto XI</button></div><div class="small muted" style="margin-top:6px;font-size:11px;color:var(--acc)">${MENTALITY_NOTE[t.tactic.mentality]||""}</div></div> ${pitchHTML(t.xi,true)}
      <div class="card tight"><h3>Bench</h3><div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:8px">${t.bench.map(b=>`<button class="btn sm" onclick="swapIn(${b.id})">${esc(b.name.split(" ").slice(-1)[0])} <span class="small muted">${esc(b.pos)} ${b.ca.toFixed(1)}</span></button>`).join("")}</div></div> <div class="card"><h3>Roles & duties</h3><div style="margin-top:8px;display:grid;gap:4px">${t.xi.map((x,i)=>`<div style="display:flex;gap:6px;align-items:center"><span class="pos" style="min-width:32px">${esc(x.pos)}</span><span style="flex:1;font-size:11px;font-weight:800;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${x.player?esc(x.player.name):'<span class="muted">empty</span>'}</span><select data-slot="${i}" data-kind="role" class="rd-sel" style="width:120px;min-height:32px;font-size:11px" onchange="saveTactics()">${(G.static.roles[x.pos]||[]).map(r=>`<option ${x.role===r?"selected":""}>${r}</option>`).join("")}</select><select data-slot="${i}" data-kind="duty" class="rd-sel" style="width:70px;min-height:32px;font-size:11px" onchange="saveTactics()">${(G.static.duties[x.pos]||[]).map(d=>`<option ${x.duty===d?"selected":""}>${d}</option>`).join("")}</select></div>`).join("")}</div></div> <div class="card"><h3>Team instructions</h3><div style="margin-top:8px;display:grid;gap:4px">${Object.keys(IOPT).map(k=>{
        const opts=IOPT[k]||[], cur=instr[k], label=k.replace(/_/g," ");
        if(opts.length===2&&(opts[0]===false||opts[0]===true)) return `<div style="display:flex;gap:8px;align-items:center;padding:4px 0"><span style="flex:1;font-size:11px">${esc(label)}</span><label style="display:flex;gap:6px;align-items:center"><input type="checkbox" data-i="${k}" class="instr-c" ${cur?"checked":""} onchange="saveTactics()"> on</label></div>`;
        return `<div style="display:flex;gap:8px;align-items:center;padding:4px 0"><span style="width:110px;font-size:11px">${esc(label)}</span><select data-i="${k}" class="instr-s" style="flex:1;min-height:32px;font-size:11px" onchange="saveTactics()">${opts.map(o=>`<option ${cur===o?"selected":""}>${o}</option>`).join("")}</select></div>`;
      }).join("")}<div style="margin-top:8px"><button class="btn sm" onclick="resetInstructions()">Reset</button></div></div> </div>`;
}
async function changeFormation(f){ const r=await saveTactics({formation:f}); if(r&&r.msg) toast(esc(r.msg)); renderTactics(); }
async function resetInstructions(){ const r=await saveTactics({reset_instr:true}); if(r&&r.msg) toast(esc(r.msg)); renderTactics(); }
async function saveTactics(extra){
  const t=window._tactics||{}, roles={}; $$(".rd-sel").forEach(s=>{ const i=s.dataset.slot; roles[i]=roles[i]||[(t.xi[i]||{}).role,(t.xi[i]||{}).duty]; roles[i][s.dataset.kind==="role"?0:1]=s.value; });
  const instr={}; $$(".instr-s").forEach(i=>instr[i.dataset.i]=i.value); $$(".instr-c").forEach(i=>instr[i.dataset.i]=i.checked);
  const body={roles:Object.keys(roles).length?roles:null,instr:Object.keys(instr).length?instr:null,...(extra||{})};
  if(body.reset_instr) body.instr=null;
  if($("#tac-formation")&&!body.formation) body.formation=$("#tac-formation").value;
  if($("#tac-mentality")&&!body.mentality) body.mentality=$("#tac-mentality").value;
  try{ const r=await api.post("/api/tactics",body); if(r&&r.ok===false) toast(esc(r.msg||"Failed"),4000); return r; } catch(e){ toast("Tactics error: "+esc(e.message),5000); }
}
async function autoPickXI(){ const r=await api.post("/api/match/auto",{}); toast(esc(r.msg||"Done")); renderTactics(); }
let PICK_SLOT=null; function pickSlot(i,pos){ PICK_SLOT={i,pos}; showSlotPicker(pos); }
async function showSlotPicker(pos){
  const j=await api.get("/api/screen/squad"); const t=window._tactics;
  const used=new Set(t.xi.filter(x=>x.player).map(x=>x.player.id));
  const rank=p=>p.pos===pos?0:(p.pos2===pos?1:2);
  const cands=j.players.filter(p=>p.squad!=="Youth"&&!used.has(p.id)).sort((a,b)=>rank(a)-rank(b)||b.ca-a.ca).slice(0,20);
  modal(`<h2>Pick for ${esc(pos)}</h2><div style="display:grid;gap:6px;max-height:50vh;overflow:auto;margin-top:10px">${cands.map(p=>`<div style="display:flex;align-items:center;gap:10px;padding:10px;border-radius:12px;background:var(--panel2);border:1px solid var(--line)"><span class="pos">${esc(p.pos)}</span><span style="flex:1"><b style="font-size:12px">${esc(p.name)}</b><div class="small muted">${p.ca.toFixed(1)} · ${Math.round(p.fitness)} fit · ${p.condition.toFixed(2)}</div></span><button class="btn sm primary" onclick="applySlot(${p.id})">Select</button></div>`).join("")}</div>`, true);
}
async function applySlot(pid){
  const t=window._tactics, ids=t.xi.map(x=>x.player?x.player.id:0), at=ids.indexOf(pid);
  if(at>=0) ids[at]=ids[PICK_SLOT.i]; ids[PICK_SLOT.i]=pid;
  const clean=ids.filter(x=>x); if(clean.length!==11){ toast(`Fill 11 slots (${clean.length}/11)`,4000); return; }
  try{ const r=await api.post("/api/match/select",{ids:clean}); closeModal(); toast(esc(r.msg||(r.ok?"Selected":"Failed")),4000); renderTactics(); } catch(e){ closeModal(); toast(esc(e.message),5000); }
}
function swapIn(pid){ const empty=window._tactics.xi.findIndex(x=>!x.player); if(empty>=0){ PICK_SLOT={i:empty,pos:window._tactics.xi[empty].pos}; applySlot(pid); } else toast("All filled — tap pitch slot to replace",4000); }

/* TRAINING */
async function renderTraining(){
  const t=await api.get("/api/screen/training"); await refreshState();
  const days=["Mon","Tue","Wed","Thu","Fri","Sat","Sun"];
  $("#content").innerHTML=`
    <div style="display:flex;gap:6px;margin-bottom:10px"><div style="padding:8px 12px;border-radius:10px;background:var(--panel);border:1px solid var(--line);text-align:center;flex:1"><div style="font-size:10px;color:var(--tx3);font-weight:900">FAT</div><div style="font-weight:950;color:${t.squad_load.fatigue>55?"var(--red)":"var(--tx)"}">${t.squad_load.fatigue}</div></div><div style="padding:8px 12px;border-radius:10px;background:var(--panel);border:1px solid var(--line);text-align:center;flex:1"><div style="font-size:10px;color:var(--tx3);font-weight:900">FIT</div><div style="font-weight:950">${t.squad_load.fitness}</div></div><div style="padding:8px 12px;border-radius:10px;background:var(--panel);border:1px solid var(--line);text-align:center;flex:1"><div style="font-size:10px;color:var(--tx3);font-weight:900">SHP</div><div style="font-weight:950">${t.squad_load.sharpness}</div></div><div style="padding:8px 12px;border-radius:10px;background:var(--panel);border:1px solid var(--line);text-align:center;flex:1"><div style="font-size:10px;color:var(--tx3);font-weight:900">INJ</div><div style="font-weight:950;color:${t.squad_load.injured?"var(--red)":""}">${t.squad_load.injured}</div></div></div> <div class="card" style="padding:0;overflow:hidden">${t.week.map(w=>{
      const s=t.sessions.find(x=>x.name===w.session)||{};
      return `<div style="display:grid;grid-template-columns:56px 1fr 1fr auto;gap:8px;padding:10px 12px;border-bottom:1px solid rgba(255,255,255,.04);align-items:center"><b style="font-size:11px">${days[w.day]}</b><select onchange="setTraining(${w.day},this.value,'${esc(w.focus||"")}')" style="min-height:32px;font-size:11px"><option>${w.session}</option>${t.sessions.map(x=>`<option ${x.name===w.session?"selected":""}>${x.name}</option>`).join("")}</select><select onchange="setTraining(${w.day},'${esc(w.session)}',this.value)" style="min-height:32px;font-size:11px"><option value="">— focus —</option>${t.focus_options.map(p=>`<option ${w.focus===p?"selected":""}>${p}</option>`).join("")}</select><span style="font-size:9px;color:var(--tx3)">${s.fatigue!=null?`fat ${s.fatigue>0?"+":""}${s.fatigue}`:""}</span></div>`;
    }).join("")}</div> <div class="card" style="margin-top:10px"><h3>How training works</h3><div class="small muted" style="margin-top:6px;font-size:11px">Sessions add fatigue/sharpness, build fitness, chance to improve attributes. Match Prep day before, Recovery day after auto. High fatigue = injury risk. Youth develops with mins.</div></div>`;
}
async function setTraining(day,session,focus){ const r=await api.post("/api/training",{day,session,focus}); if(r&&r.ok===false) toast(esc(r.msg||"Failed")); else renderTraining(); }

/* MATCH */
let MATCH=null;
function evIcon(t,e){ if(t==="touchline") return ["ev-tl","T"]; if(t==="goal") return ["ev-goal","G"]; if(t==="yellow") return ["ev-card","Y"]; if(t==="red") return ["ev-red","R"]; if(t==="var"){ if(e&&e.stage==="overturn"&&e.decision==="disallowed") return ["ev-var disallow","✕"]; if(e&&e.stage==="confirmed") return ["ev-var confirm","✓"]; return ["ev-var","VAR"]; } if(t==="var_disallowed") return ["ev-var disallow","✕"]; if(t==="sub") return ["ev-sub","S"]; if(t==="injury") return ["ev-info","+"]; if(t==="penalties") return ["ev-info","P"]; return ["ev-info","•"]; }
function scoreEvents(evs,base){ let h=base?base[0]:0,a=base?base[1]:0; return (evs||[]).map(e=>{ const o=Object.assign({},e); if(e.type==="goal"){ if(e.side==="H") h++; else if(e.side==="A") a++; o._sc=h+"–"+a; } return o; }); }
function evRow(e){ const [cls,ic]=evIcon(e.type,e); return `<div class="ev ${cls}"><span class="min">${e.minute}'</span><span class="ei">${ic}</span><div class="et" style="font-size:12px">${esc(e.text||(e.type==="shot"?`${e.player||""} — ${e.outcome||"chance"}${e.xg!=null?" (xG "+e.xg+")":""}`:e.type))}${e._sc?` <span class="escore">${e._sc}</span>`:""}</div></div>`; }
function hexA(c,a){ if(!c||c[0]!=="#") return "rgba(120,140,160,"+a+")"; const n=parseInt(c.slice(1),16); return `rgba(${(n>>16)&255},${(n>>8)&255},${n&255},${a})`; }
function clubCol(code,i){ const c=CREST[code||""]; return c?c[i]:null; }
function goalFlash(e){ const C=G.codes||{}, code=e.side==="H"?C.home:C.away, el=document.createElement("div"); el.className="gflash"; el.style.setProperty("--gc",compColor(C.comp)); el.innerHTML=`<div class="gf-in">${crest(code,"lg")}<div style="flex:1;min-width:0"><div class="gf-t">GOAL · ${e.minute}'</div><div class="gf-n">${esc(e.player||"")}</div></div><div class="gf-s">${esc(e._sc||"")}</div></div>`; document.body.appendChild(el); setTimeout(()=>el.classList.add("out"),2200); setTimeout(()=>el.remove(),2700); }
function varFlash(e){ const stage=e.stage||"check", isConfirm=stage==="confirmed"||e.decision==="goal", isDisallow=stage==="overturn"||e.decision==="disallowed"||e.type==="var_disallowed", el=document.createElement("div"); el.className="varflash"; const boxCls=isConfirm?"confirm":isDisallow?"disallow":"", iconTxt=isConfirm?"✓":isDisallow?"✕":"VAR", title=stage==="check"?"VAR CHECK":isConfirm?"GOAL CONFIRMED":"GOAL DISALLOWED"; el.innerHTML=`<div class="varbox ${boxCls}"><div class="var-icon">${iconTxt}</div><div class="var-t">${title}</div><div class="var-sub">${esc(e.player||"")}${e.reason?" · "+esc(e.reason):""}</div>${e.text?`<div class="var-reason">${esc(e.text)}</div>`:""}</div>`; document.body.appendChild(el); setTimeout(()=>el.classList.add("out"),stage==="check"?1600:2200); setTimeout(()=>el.remove(),stage==="check"?2000:2700); }
function cardFlash(e){ const isRed=e.type==="red", el=document.createElement("div"); el.className="cardflash"; el.innerHTML=`<div class="cf-card ${isRed?"red":"yellow"}">${isRed?"":""}</div><div class="cf-info"><b>${esc(e.player||"")}</b><br><span class="small muted">${esc(e.text||(isRed?"RED CARD":"YELLOW CARD"))}</span></div>`; document.body.appendChild(el); setTimeout(()=>el.classList.add("out"),1800); setTimeout(()=>el.remove(),2300); }
function statDuo(a,b,label,fmt){ const f=fmt||(x=>x), an=Number(a)||0, bn=Number(b)||0, tot=an+bn||1; return `<div class="stat-duo"><span class="v">${f(a)}</span><span class="lb">${label}<span class="sb"><i style="width:${an/tot*100}%"></i></span><span class="sb r"><i style="width:${bn/tot*100}%"></i></span></span><span class="v r">${f(b)}</span></div>`; }
function sv(S,side,k){ const o=(S||{})[side]||{}; let v=o[k]; if(v==null) v=o[k==="possession"?"poss":k==="poss"?"possession":k]; return v; }
function statsBlock(S,meFirst){ const A=meFirst?"me":"home", B=meFirst?"opp":"away"; const rows=[["possession","Poss"],["shots","Shots"],["sot","OnT"],["xg","xG",x=>Number(x||0).toFixed(2)],["big","Big"],["corners","Corn"],["fouls","Fouls"],["saves","Saves"]]; return rows.map(([k,label,f])=>{ const a=sv(S,A,k), b=sv(S,B,k); if(a==null&&b==null) return ""; return statDuo(a==null?"—":a,b==null?"—":b,label,f); }).join(""); }
async function quickSell(pid,name){ modal(`<h2>Sell ${esc(name)}</h2><p class="small muted">List for transfer. Clubs bid auto.</p><div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:10px"><div><label style="font-size:10px;font-weight:900;color:var(--tx3)">ASK €m</label><input id="qs-price" type="number" step="0.5" value="5" style="width:100%;margin-top:4px"></div><div><label style="font-size:10px;font-weight:900;color:var(--tx3)">REASON</label><select id="qs-reason" style="width:100%;margin-top:4px"><option>Surplus</option><option>Needs football</option><option>Financial</option></select></div></div><div style="display:flex;gap:8px;margin-top:14px;justify-content:flex-end"><button class="btn sm" onclick="closeModal()">Cancel</button><button class="btn primary sm" onclick="doQuickSell(${pid})">List </button></div>`); }
async function doQuickSell(pid){ const price=+$("#qs-price").value||0; closeModal(); const r=await api.post("/api/squad/list",{pid,listed:true,asking:price}); toast(r.msg||`Listed ${money(price)}`,4000); if(G.screen==="squad") renderSquad(); else if(G.screen==="player") go("player",pid); }
async function renderMatch(){
  await refreshState();
  if(G.pendingMatch){
    try{
      const j=await api.get("/api/match/live_state");
      if(j.ok&&j.state){
        const f=j.state.fixture||{};
        if(f.home_code) G.codes={home:f.home_code,away:f.away_code,comp:f.code,compName:f.comp,stage:f.stage,venue:f.venue,date:f.date};
        G.matchMode=j.mode||G.matchMode||"full";
        if(j.halftime){ G.halftimeState=j.state; showHalftime(j.state); }
        else startLive(j.state);
        return;
      }
    }catch(e){}
    showHalftime(G.halftimeState); return;
  }
  const j=await api.get("/api/match/next");
  if(!j.ok){ $("#content").innerHTML=`<div class="card" style="text-align:center;padding:24px"><div style="font-size:28px"></div><h3>No match</h3><p class="small muted">${esc(j.msg)}</p><button class="btn primary sm" style="margin-top:10px" onclick="doContinue()">Continue ▶</button></div>`; return; }
  MATCH=j; const p=j.preview, f=p.fixture;
  G.codes={home:f.home_code,away:f.away_code,comp:f.code,compName:compLabel(f),stage:f.stage,venue:f.venue,date:f.date};
  const myForm=p.my.form||[], opForm=p.opp.form||[], hForm=f.is_home?myForm:opForm, aForm=f.is_home?opForm:myForm, rivalry=isRivalry(f.home_code,f.away_code), isFriendly=f.code==="friendly"||(f.comp||"").toLowerCase().includes("friendly");
  $("#content").innerHTML=`
    ${rivalry?`<div class="derby-banner">${esc(rivalry.name.toUpperCase())} — DERBY</div>`:""}
    <div class="mhero ${compClass(f.code)}" style="--comp:${compColor(f.code)}"><div class="mhero-top">${compLogo(f.code)}<span class="comp-dot"></span><span>${esc(compLabel(f))}${f.stage&&f.stage!=="league"?" · "+esc(f.stage):""} ${rivalry?`·  ${esc(rivalry.name)}`:""} ${isFriendly?'<span class="tag" style="background:rgba(44,255,138,.14);color:var(--acc)">FRIENDLY</span>':""}</span><span class="spacer"></span><span style="font-size:10px">${fmtDate(f.date).split(",")[0]}</span></div> <div class="mhero-body"><div class="mhero-club">${crest(f.home_code,"xl")}<div class="nm">${esc(f.home)}</div><div style="margin-top:4px;display:flex;justify-content:center;gap:2px">${formPills(hForm,5)}</div></div><div class="mhero-mid"><div class="vs">VS</div><div class="when" style="font-weight:900">${fmtDate(f.date).split(",")[0]}</div><div class="venue">${esc(f.venue||"")}</div>${rivalry?`<div class="rivalry-tag" style="margin-top:6px"> Rivalry</div>`:""}</div><div class="mhero-club">${crest(f.away_code,"xl")}<div class="nm">${esc(f.away)}</div><div style="margin-top:4px;display:flex;justify-content:center;gap:2px">${formPills(aForm,5)}</div></div></div> <div class="mhero-foot"><button class="btn primary" style="flex:1;min-height:44px" onclick="Juice.haptic('heavy');playMatch('full')">▶ WATCH LIVE</button><button class="btn" style="min-height:44px" onclick="playMatch('key')"> KEY</button><button class="btn" style="min-height:44px" onclick="playMatch('instant')"> INSTANT</button></div> </div> <div style="margin-top:8px">${pressHypeForFixture(f)}</div> <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:10px"><div class="card tight"><div style="display:flex;justify-content:space-between"><h3>Your team ${esc(p.tactic.formation)}</h3><button class="btn sm" onclick="go('tactics')">Tactics ▸</button></div><div class="kv"><span>Mentality</span><b>${esc(p.tactic.mentality)}</b></div><div class="kv"><span>Strength</span><b style="font-family:var(--ff-mono)">${p.my.ca.toFixed(1)}/20</b></div><div class="kv"><span>Att / Def</span><b>${p.my.attack} / ${p.my.defence}</b></div><div class="kv"><span>Familiarity</span><b>${Math.round(p.tactic.familiarity||0)}%</b></div></div><div class="card tight"><div style="display:flex;justify-content:space-between"><h3>Opp ${esc(p.opp.name)}</h3><span class="small muted">${p.opposition_report.known}% scouted</span></div><div class="kv"><span>Strength</span><b>${p.opp.ca?p.opp.ca.toFixed(1)+"/20":"?"}</b></div><div class="kv"><span>Rep · league</span><b>${p.opp.rep} · ${esc(p.opp.league)}</b></div>${p.opposition_report.key_players.slice(0,3).map(k=>`<div class="kv"><span> ${esc(k.name)} ${esc(k.pos)}</span><b>${k.goals}g</b></div>`).join("")||'<div class="small muted">No report</div>'}<button class="btn sm" style="margin-top:6px" onclick="go('scouting')">Scout ▸</button></div></div> <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:10px"><div class="card tight"><h3>XI ${esc(p.tactic.formation)}</h3>${pitchHTML(p.xi,false)}</div><div class="card tight" style="padding:0"><div style="padding:10px 12px 4px;display:flex;justify-content:space-between"><h3>Bench ${p.bench.length}</h3></div><div style="padding:0 10px 10px;display:grid;gap:4px">${p.bench.map(b=>`<div style="display:flex;gap:8px;align-items:center;padding:6px 10px;border-radius:10px;background:var(--panel2);border:1px solid var(--line)"><span class="pos" style="min-width:28px">${esc(b.pos)}</span><span style="flex:1;font-size:11px;font-weight:800">${esc(b.name)}</span><span style="font-size:10px;color:var(--tx3)">CA ${b.ca.toFixed(1)}</span></div>`).join("")||'<div class="small muted" style="padding:10px">No bench</div>'}</div></div></div>`;
}
/* ---------------- Match Day Live+ ---------------- */
let LIVE=null; // {mode,ev_i,fast,stopped,clockMin,sc,state,_base}
function stopLive(){ if(LIVE) LIVE.stopped=true; document.body.classList.remove("tension"); }
function liveColourRow(ln){ return `<div class="ev lv-colour"><span class="min">\u2022</span><span class="ei">\u{1F399}</span><div class="et" style="font-size:11.5px;opacity:.85">${esc(ln)}</div></div>`; }
function liveMomentum(pct){
  const C=G.codes||{}; const h=clubCol(C.home,0)||"#2cff8a", a=clubCol(C.away,0)||"#4d9eff";
  return `<div class="mom-wrap"><span class="mom-lb">MOMENTUM</span><div class="mom-bar"><i style="width:${pct}%;background:linear-gradient(90deg,${hexA(h,.5)},${h})"></i><i style="width:${100-pct}%;background:linear-gradient(90deg,${a},${hexA(a,.4)})"></i></div></div>`;
}
function liveChips(st){ const s=st.stats||{me:{},opp:{}};
  const el=$("#lv-chips"); if(!el) return;
  el.innerHTML=[["Poss",(s.me.poss==null?"—":s.me.poss+"%")],["Shots",(s.me.shots||0)+"\u2013"+(s.opp.shots||0)],["xG",Number(s.me.xg||0).toFixed(2)+"\u2013"+Number(s.opp.xg||0).toFixed(2)],["Corners",(s.me.corners||0)+"\u2013"+(s.opp.corners||0)]].map(([k,v])=>`<span class="tag" style="font-size:10px;background:var(--panel2)">${k} <b style="color:var(--tx)">${esc(String(v))}</b></span>`).join("");
}
function startLive(st){
  stopLive();
  LIVE={mode:G.matchMode||"full",ev_i:st.ev_i||0,fast:false,stopped:false,clockMin:st.minute||1,
        sc:[st.score.home,st.score.away],_base:[st.score.home,st.score.away],state:st};
  const C=G.codes||{};
  $("#content").innerHTML=`
    <div class="mhero ${compClass(C.comp)}" style="--comp:${compColor(C.comp)}"><div class="mhero-top">${compLogo(C.comp)}<span class="comp-dot" style="animation:dot-glow 1s infinite"></span><span>${esc(C.compName||"Match")}</span><span class="spacer"></span><span class="tag" style="background:var(--red);color:#fff;animation:dot-pulse 1s infinite">LIVE</span></div> <div class="live-bar" style="border:0;border-radius:0;padding:12px 14px 6px"><span class="lb-team">${crest(C.home,"lg")}<b>${esc((st.home_name||"").split(" ").slice(-1)[0])}</b></span><span class="lb-mid"><span class="lscore" id="lv-score" style="font-size:28px">${st.score.home} \u2013 ${st.score.away}</span><span class="clock" id="lv-clock">${st.minute}'</span><span id="lv-half" style="font-size:9px;letter-spacing:.1em;color:var(--tx3)">${st.half===2?"SECOND HALF":"FIRST HALF"}</span></span><span class="lb-team r"><b>${esc((st.away_name||"").split(" ").slice(-1)[0])}</b>${crest(C.away,"lg")}</span></div> <div id="lv-mom">${liveMomentum(st.momentum==null?50:st.momentum)}</div> <div id="lv-chips" style="display:flex;gap:6px;padding:4px 12px 8px;flex-wrap:wrap;justify-content:center"></div> <div id="lv-feed" style="padding:6px 12px 10px;min-height:32vh;max-height:42vh;overflow-y:auto"><div class="lv-empty" style="text-align:center;padding:22px 12px"><div style="font-weight:900;font-size:13px">Kick-off</div><div class="small muted" style="font-size:11px;margin-top:4px">Shout from the touchline anytime</div></div></div> <div class="mhero-foot" style="background:rgba(0,0,0,.22);padding:8px 10px;gap:6px"><button class="btn sm" id="lv-shout" >SHOUT</button><button class="btn sm" id="lv-sub">SUB</button><span class="small muted" id="lv-ment" style="font-size:10px;padding:0 4px">${esc(st.mentality||"Balanced")}</span><span class="spacer"></span><button class="btn sm" id="lv-speed">FAST</button></div> </div>`;
  liveChips(st);
  $("#lv-shout").onclick=openOrders;
  $("#lv-sub").onclick=openLiveSub;
  $("#lv-speed").onclick=()=>{ LIVE.fast=!LIVE.fast; $("#lv-speed").textContent=LIVE.fast?"NORMAL":"FAST"; };
  liveLoop();
}
function pushLiveEvent(e,feed){
  e=Object.assign({},e);
  const base=LIVE._base||[0,0];
  if(e.type==="goal"){ if(e.side==="H")LIVE.sc[0]++; else if(e.side==="A")LIVE.sc[1]++; e._sc=LIVE.sc[0]+"\u2013"+LIVE.sc[1]; }
  if(e.type==="var_disallowed"){ if(e.side==="H"&&LIVE.sc[0]>base[0])LIVE.sc[0]--; else if(e.side==="A"&&LIVE.sc[1]>base[1])LIVE.sc[1]--; }
  feed.insertAdjacentHTML("afterbegin",evRow(e));
  if(e.type==="goal"){ goalFlash(e); Juice.haptic("goal"); Juice.play("goal"); Juice.shake(); }
  else if(e.type==="var"||e.type==="var_disallowed"){ varFlash(e); Juice.haptic("var"); Juice.play("var"); }
  else if(e.type==="yellow"||e.type==="red"){ cardFlash(e); Juice.haptic("card"); Juice.play("card"); }
  else if(e.type==="touchline"){ Juice.haptic("medium"); }
}
function endChunk(st){
  LIVE.state=st; LIVE._base=[st.score.home,st.score.away];
  const m=$("#lv-mom"); if(m) m.innerHTML=liveMomentum(st.momentum==null?50:st.momentum);
  liveChips(st);
  const ment=$("#lv-ment"); if(ment) ment.textContent=st.mentality||"Balanced";
  const half=$("#lv-half"); if(half&&st.half===2) half.textContent="SECOND HALF";
  const se=$("#lv-score"); if(se) se.textContent=st.score.home+" \u2013 "+st.score.away;
  if(st.minute>=85&&Math.abs(st.my_score-st.opp_score)<=1&&!document.body.classList.contains("tension")){
    document.body.classList.add("tension"); Juice.haptic("heavy"); toast("Nothing between them — final minutes.",3000); }
}
function animateChunk(st){
  return new Promise(res=>{
    const feed=$("#lv-feed"); if(!feed){ res(); return; }
    const from=LIVE.clockMin, to=Math.max(from,st.minute);
    const evs=(st.new_events||[]).slice().sort((a,b)=>a.minute-b.minute);
    const cols=(st.colour||[]).slice();
    const per=LIVE.fast?24:165, em=feed.querySelector(".lv-empty");
    if(em&&(evs.length||cols.length)) em.remove();
    const pts=cols.length?cols.map((_,k)=>from+Math.round((k+1)*((to-from)/(cols.length+1)))):[];
    let ei=0, ci=0, m=from;
    const iv=setInterval(()=>{
      m++; LIVE.clockMin=m;
      const clock=$("#lv-clock"); if(clock) clock.textContent=m+"'";
      while(ei<evs.length&&evs[ei].minute<=m){ pushLiveEvent(evs[ei],feed); ei++; }
      while(ci<pts.length&&m>=pts[ci]){ feed.insertAdjacentHTML("afterbegin",liveColourRow(cols[ci])); ci++; }
      if(m>=to){ clearInterval(iv); endChunk(st); res(); }
    },per);
  });
}
async function liveLoop(){
  while(LIVE&&!LIVE.stopped){
    let j;
    try{ j=await api.post("/api/match/live_step",{mode:LIVE.fast?"fast":LIVE.mode,ev_i:LIVE.ev_i}); }
    catch(e){ stopLive(); return; }
    if(!j||!j.ok){ toast(esc((j&&j.msg)||"Match feed lost"),5000); stopLive(); return; }
    if(j.result){
      stopLive(); G.pendingMatch=false; G.halftimeState=null;
      try{ await refreshState(); }catch(e){}
      showResult(j.result); return; }
    const st=j.state; LIVE.ev_i=st.ev_i;
    if(st.halftime_state){
      stopLive(); await new Promise(r=>setTimeout(r,300));
      G.halftimeState=st.halftime_state; showHalftime(st.halftime_state); return; }
    await animateChunk(st);
    if(!LIVE||LIVE.stopped) return;
    await new Promise(r=>setTimeout(r,LIVE.fast?40:240));
  }
}
function applyLiveState(st){ if(!LIVE) return; LIVE.state=st; LIVE.ev_i=st.ev_i; const ment=$("#lv-ment"); if(ment) ment.textContent=st.mentality||"Balanced"; const m=$("#lv-mom"); if(m) m.innerHTML=liveMomentum(st.momentum==null?50:st.momentum); }
function openOrders(){
  const st=LIVE&&LIVE.state; if(!st) return; Juice.haptic("light");
  const left=(st.orders&&st.orders[0])?st.orders[0].left:3;
  const rows=(st.orders||[]).map(o=>{
    const dis=o.used||o.cd>0||left<=0;
    return `<button class="order-row${o.used?" used":""}" ${dis?"disabled":""} onclick="sendOrder('${o.key}')"><span class="ol">${o.label}</span><span class="od">${esc(o.desc)}${o.cd>0?" \u00b7 ready in "+o.cd+"'":o.used?" \u00b7 used":""}</span></button>`;}).join("");
  modal(`<h2>Touchline</h2><p class="small muted" style="font-size:11px">${left} instruction${left===1?"":"s"} left \u00b7 one every 10 minutes</p><div style="display:grid;gap:6px;margin-top:10px">${rows}</div>`);
}
async function sendOrder(k){
  closeModal();
  try{ const j=await api.post("/api/match/instruction",{order:k});
    if(j.state) applyLiveState(j.state);
    toast(esc(j.msg||(j.ok?"Instruction sent":"Ignored")),4200);
    Juice.haptic(j.ok?"success":"error"); Juice.play(j.ok?"success":"error");
  }catch(e){ toast("Failed: "+esc(e.message),4000); }
}
function openLiveSub(){
  const st=LIVE&&LIVE.state; if(!st) return; Juice.haptic("light");
  if(st.subs_left<=0){ toast("No substitutions left",3000); return; }
  modal(`<h2>Substitution</h2><p class="small muted" style="font-size:11px">${st.subs_left} left \u00b7 5 total (incl. half-time)</p> <div style="display:grid;gap:8px;margin-top:10px"> <select id="ls-off" style="min-height:38px">${st.xi.map(p=>`<option value="${p.pid}">${esc(p.name)} \u00b7 ${esc(p.pos)} \u00b7 ${p.rating.toFixed(2)}${p.fatigue>55?" \u00b7 legs "+Math.round(p.fatigue):""}</option>`).join("")}</select> <select id="ls-on" style="min-height:38px">${st.bench.map(b=>`<option value="${b.pid}">${esc(b.name)} \u00b7 ${esc(b.pos)} \u00b7 CA ${b.ca.toFixed(1)}</option>`).join("")}</select> </div> <div style="display:flex;gap:8px;margin-top:12px"><button class="btn primary" onclick="sendLiveSub()">Make the change</button><button class="btn" onclick="closeModal()">Cancel</button></div>`);
}
async function sendLiveSub(){
  const off=+$("#ls-off").value, on=+$("#ls-on").value; closeModal();
  try{ const j=await api.post("/api/match/sub",{off,on});
    if(j.state) applyLiveState(j.state);
    toast(esc(j.msg||(j.ok?"Sub made":"Not possible")),3600);
    Juice.haptic(j.ok?"success":"error"); if(j.ok) Juice.play("success");
  }catch(e){ toast("Failed: "+esc(e.message),4000); }
}
async function playMatch(mode){
  G.matchMode=mode; G.busy=true; setBusy(true);
  try{
    if(mode==="instant"){
      const j=await api.post("/api/match/play",{mode});
      if(!j.ok){ toast(esc(j.msg||"Could not play"),5000); G.busy=false; setBusy(false); return; }
      if(j.result){ await refreshState(); showResult(j.result); }
      G.busy=false; setBusy(false); return;
    }
    const j=await api.post("/api/match/play",{mode});
    if(!j.ok){ toast(esc(j.msg||"Could not play"),5000); G.busy=false; setBusy(false); return; }
    G.pendingMatch=true; G.halftimeState=null; G.matchFixture=j.fixture;
    const f=j.fixture||{};
    G.codes={home:f.home_code,away:f.away_code,comp:f.code,compName:f.comp||compLabel(f),stage:f.stage,venue:f.venue,date:f.date};
    startLive(j.state);
  } catch(e){ toast("Match failed: "+esc(e.message),6000); }
  G.busy=false; setBusy(false);
}
function showHalftime(st){
  if(!st){ const C=G.codes||{}; $("#content").innerHTML=`<div class="mhero ${compClass(C.comp)}" style="--comp:${compColor(C.comp)}"><div class="mhero-top"><span>${esc(C.compName||"Match")}</span><span class="spacer"></span><span>HALF-TIME</span></div><div style="padding:14px"><h2>Match paused at HT</h2><p class="small muted" style="margin-top:6px">Notes lost after restart</p><div style="display:flex;gap:8px;margin-top:12px"><button class="btn primary" onclick="submitHalftime(true)">Send out ▶</button><button class="btn" onclick="resumeMatch()">Auto-finish</button></div></div></div>`; return; }
  window._ht=st; const C=G.codes||{};
  $("#content").innerHTML=`
    <div class="mhero" style="--comp:${compColor(C.comp)}"><div class="mhero-top"><span>${esc(C.compName||"Match")}</span><span class="spacer"></span><span>HALF-TIME</span></div><div class="live-bar" style="border:0;border-radius:0"><span class="lb-team">${crest(C.home)}<b>${esc(st.home_name)}</b></span><span class="lb-mid"><span class="lscore">${st.score.home} – ${st.score.away}</span><span class="clock ht">HT</span></span><span class="lb-team r"><b>${esc(st.away_name)}</b>${crest(C.away)}</span></div><div style="padding:6px 12px 12px">${statsBlock(st.stats,true)}</div></div> <div class="card tight" style="margin-top:10px"><h3>First-half incidents</h3><div style="margin-top:8px">${st.events.length?scoreEvents(st.events.slice(),[0,0]).reverse().map(evRow).join(""):'<p class="small muted">Quiet half</p>'}</div></div> <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:10px"><div class="card tight"><h3>Team talk</h3><select id="ht-talk" style="width:100%;min-height:36px;margin-top:6px">${st.talks.map(t=>`<option value="${t}" ${t==="neutral"?"selected":""}>${esc(t[0].toUpperCase()+t.slice(1))}</option>`).join("")}</select><div class="small muted" style="margin-top:6px;font-size:11px" id="ht-hint">${esc(talkHint("neutral",st))}</div><div style="display:flex;justify-content:space-between;margin-top:10px"><h3>Subs</h3><span class="small muted">max 3</span></div><div id="ht-subs"></div><button class="btn sm" onclick="addSubRow()" style="margin-top:6px">+ Add sub</button><div style="display:flex;gap:8px;margin-top:12px"><button class="btn primary" onclick="submitHalftime()">Send out ▶</button><button class="btn" onclick="submitHalftime(true)">No changes</button></div></div><div class="card tight" style="padding:0"><div style="padding:10px 12px 4px"><h3>Your players at break</h3></div><div style="padding:0 10px 10px;display:grid;gap:4px">${st.xi.map(p=>`<div style="display:flex;gap:8px;align-items:center;padding:6px 8px;border-radius:8px;background:var(--panel2)"><span class="pos" style="min-width:28px">${esc(p.pos)}</span><span style="flex:1;font-size:11px;font-weight:800">${esc(p.name)}</span><b style="font-size:11px">${p.rating.toFixed(2)}</b><span style="font-size:10px;color:var(--tx3)">${Math.round(p.fatigue)}</span></div>`).join("")}</div></div></div>`;
  $("#ht-talk").addEventListener("change",e=>$("#ht-hint").textContent=talkHint(e.target.value,st)); SUB_ROWS=0; addSubRow(); polish($("#content"));
}
function talkHint(talk,st){ const diff=st.my_score-st.opp_score, notes={praise:"Lifts morale. Best when winning",encourage:"Steady boost + attack",neutral:"No effect",firm:"Sharper when behind",aggressive:"Biggest push, more fatigue/cards",defensive:"Drops line, protects lead",attacking:"Raises tempo, chases goal"}; let s=notes[talk]||""; if(diff<0&&talk==="praise") s+=" — losing, may be complacency"; if(diff>0&&(talk==="firm"||talk==="aggressive")) s+=" — winning, harsh can dent confidence"; return s; }
let SUB_ROWS=0;
function addSubRow(){ const st=window._ht; if(!st) return; if(SUB_ROWS>=3){ toast("Max 3 subs at HT"); return; } SUB_ROWS++; const wrap=document.createElement("div"); wrap.className="row ht-sub"; wrap.style.marginBottom="6px"; wrap.style.display="flex"; wrap.style.gap="6px"; wrap.innerHTML=`<select class="sub-off" style="flex:1;min-height:32px;font-size:11px"><option value="">Off…</option>${st.xi.map(p=>`<option value="${p.pid}">${esc(p.name)} (${esc(p.pos)} ${p.rating.toFixed(2)})</option>`).join("")}</select><select class="sub-on" style="flex:1;min-height:32px;font-size:11px"><option value="">On…</option>${st.bench.map(b=>`<option value="${b.pid}">${esc(b.name)} (${esc(b.pos)} ${b.ca.toFixed(1)})</option>`).join("")}</select><button class="btn sm" onclick="this.parentNode.remove()">✕</button>`; $("#ht-subs").appendChild(wrap); }
async function submitHalftime(noChange){
  const talk=noChange?null:($("#ht-talk")?$("#ht-talk").value:null), subs=noChange?[]:$$(".ht-sub").map(r=>{ const off=$(".sub-off",r).value, on=$(".sub-on",r).value; return off&&on?[+off,+on]:null; }).filter(x=>x);
  G.busy=true; setBusy(true);
  try{
    const j=await api.post("/api/match/halftime",{talk,subs});
    SUB_ROWS=0;
    if(!j.ok){ toast(esc(j.msg||"Could not resume"),5000); G.busy=false; setBusy(false); return; }
    if(j.live&&j.state){ G.pendingMatch=true; G.halftimeState=null; startLive(j.state); }
    else if(j.result){ G.pendingMatch=false; G.halftimeState=null; await refreshState(); showResult(j.result); }
  } catch(e){ toast("Match failed: "+esc(e.message),6000); }
  G.busy=false; setBusy(false);
}
function showResult(r){
  const isH=r.is_home, my=isH?r.hg:r.ag, opp=isH?r.ag:r.hg, res=r.result||(my>opp?"W":my===opp?"D":"L"), mySide=isH?"H":"A", all=(r.events||[]).slice().sort((a,b)=>a.minute-b.minute), relevant=all.filter(e=>e.type==="goal"||e.type==="red"||e.type==="injury"||e.type==="sub"||e.type==="halftime"||e.type==="kickoff"||e.type==="team_talk"||e.type==="penalties"||e.side===mySide), shown=r.mode==="instant"?all.filter(e=>["goal","red","penalties","halftime","kickoff"].includes(e.type)):r.mode==="key"?relevant.filter(e=>["goal","red","injury","sub","halftime","kickoff","team_talk","penalties"].includes(e.type)):relevant;
  const C=G.codes||{}, hCode=r.home_code||C.home||"", aCode=r.away_code||C.away||""; G.codes={home:hCode,away:aCode,comp:r.comp_code||r.code||C.comp,compName:r.comp||C.compName,stage:C.stage,venue:C.venue,date:C.date}; const motm=(r.players||[]).find(p=>p.pid===r.motm);
  if(res==="W"){ Juice.confetti(); Juice.haptic("success"); Juice.play("success"); }
  $("#content").innerHTML=`
    <div class="mhero ${compClass(C.comp||r.code)}" style="--comp:${compColor(C.comp)}"><div class="mhero-top">${compLogo(C.comp||r.code)}<span class="comp-dot"></span><span>${esc(r.comp||C.compName||"Match")}</span><span class="spacer"></span><span>FULL-TIME</span></div><div class="mhero-body"><div class="mhero-club">${crest(hCode,"xl")}<div class="nm">${esc(r.home)}</div></div><div class="mhero-mid"><div class="lscore" style="font-size:30px">${r.hg} – ${r.ag}</div><span class="tag ${res}" style="margin-top:6px">${res==="W"?"WIN":res==="D"?"DRAW":"LOSS"}</span>${r.penalties?`<div class="small muted" style="font-size:10px;margin-top:4px">pens ${esc(JSON.stringify(r.penalties.home))}–${esc(JSON.stringify(r.penalties.away))}</div>`:""}</div><div class="mhero-club">${crest(aCode,"xl")}<div class="nm">${esc(r.away)}</div></div></div>${motm?`<div style="padding:0 12px 12px"><div class="motm"><div><div class="lbl">MAN OF THE MATCH</div><b style="font-size:13px">${esc(motm.name)}</b> <span class="small muted">${esc(motm.pos)} · ${motm.rating.toFixed(2)}${motm.goals?" · "+motm.goals+"g":""}${motm.assists?" · "+motm.assists+"a":""}</span></div></div></div>`:""}</div> <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:10px"><div class="card tight"><h3>Stats</h3><div style="margin-top:8px">${statsBlock(r.stats,false)}</div></div><div class="card tight"><h3>Events <span class="small muted">${esc(r.mode)}</span></h3><div style="max-height:260px;overflow:auto;margin-top:8px">${scoreEvents(shown.slice(),[0,0]).reverse().map(evRow).join("")||'<p class="small muted">Nothing</p>'}</div></div></div> <div class="card tight" style="margin-top:8px;padding:0"><div style="padding:10px 12px 4px"><h3>Your players</h3></div><div style="padding:0 10px 10px;display:grid;gap:3px">${(r.players||[]).map(p=>`<div style="display:flex;gap:8px;align-items:center;padding:6px 8px;border-radius:8px;background:${p.pid===r.motm?"rgba(44,255,138,.12)":"var(--panel2)"};border:1px solid ${p.pid===r.motm?"rgba(44,255,138,.18)":"var(--line)"}"><span class="pos" style="min-width:28px">${esc(p.pos)}</span><span style="flex:1;font-size:11px;font-weight:800">${esc(p.name)}${p.pid===r.motm?' <span style="color:var(--gold)">★</span>':""}</span><span style="font-size:10px">${p.mins}'</span><span style="font-size:10px">${p.goals||""}G ${p.assists||""}A</span><b style="font-size:11px;font-family:var(--ff-mono)">${p.rating.toFixed(2)}</b></div>`).join("")}</div></div> <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:8px"><div class="card tight"><h3>Aftermath</h3><div class="kv"><span>Board</span><b>${r.board_confidence}</b></div><div class="kv"><span>Fans</span><b>${r.fan_sentiment}</b></div><div class="kv"><span>Weather</span><b style="font-size:11px">${esc(r.weather||"—")}</b></div>${r.injuries&&r.injuries.length?r.injuries.map(i=>`<div class="kv"><span style="color:#ff8a94">${esc(i.name)}</span><b style="font-size:11px">${esc(i.injury)} · ${i.days}d</b></div>`).join(""):""}</div><div class="card tight"><h3>Continue</h3><p class="small muted" style="font-size:11px">Result recorded across tables, cups, finances, morale, news</p><div style="display:grid;gap:6px;margin-top:10px"><button class="btn primary" onclick="go('home')">Office ▶</button><button class="btn" onclick="go('inbox')">Inbox</button></div></div></div>`;
}

/* TRANSFERS — marketplace */
let TR={pos:"",q:"",max_fee:0,age_max:0,free:false,aff:true,sort:"value"};
async function renderTransfers(){
  await refreshState(); const j=await api.get("/api/screen/transfers"); const shortlisted=new Set(j.shortlist_ids||[]);
  const s=await api.get(`/api/transfer/search?pos=${TR.pos}&q=${encodeURIComponent(TR.q)}&max_fee=${TR.max_fee}&age_max=${TR.age_max}&free=${TR.free}&affordable=${TR.aff!==false}`);
  const win=j.window&&j.window!=="closed"; let players=(s.players||[]).slice();
  const sortFns={value:(a,b)=>(b.value||0)-(a.value||0),ca:(a,b)=>(b.ca||0)-(a.ca||0),age:(a,b)=>(a.age||0)-(b.age||0),name:(a,b)=>(a.name||"").localeCompare(b.name||"")};
  players.sort(sortFns[TR.sort]||sortFns.value);
  $("#content").innerHTML=`
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px"><b style="font-size:13px"> MARKET</b><span class="tag ${win?"ROUTINE":"URGENT"}" style="font-size:10px">${win?` ${String(j.window).toUpperCase()} OPEN`:" CLOSED"}</span><span class="spacer"></span><span style="font-size:11px;padding:4px 10px;border-radius:999px;background:var(--acc-dim);color:var(--acc);font-weight:900">${money(j.budget)}</span></div> <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin-bottom:10px"><div style="padding:8px;border-radius:10px;background:var(--panel);border:1px solid var(--line);text-align:center"><div style="font-size:9px;color:var(--tx3);font-weight:900">BUDGET</div><div style="font-weight:950;color:var(--acc);font-size:13px">${money(j.budget)}</div></div><div style="padding:8px;border-radius:10px;background:var(--panel);border:1px solid var(--line);text-align:center"><div style="font-size:9px;color:var(--tx3);font-weight:900">WAGE FREE</div><div style="font-weight:900;font-size:11px">${money((j.wage_budget||0)-(j.wage_bill||0))}/yr</div></div><div style="padding:8px;border-radius:10px;background:var(--panel);border:1px solid var(--line);text-align:center"><div style="font-size:9px;color:var(--tx3);font-weight:900">SQUAD</div><div style="font-weight:950">${j.squad_count||0}</div></div><div style="padding:8px;border-radius:10px;background:var(--panel);border:1px solid var(--line);text-align:center"><div style="font-size:9px;color:var(--tx3);font-weight:900">LISTED</div><div style="font-weight:950">${j.listed_count||0}</div></div></div> ${!win?`<div class="card tight" style="background:#2a1218;border-color:rgba(255,59,74,.18);margin-bottom:8px"><b style="color:#ff8a94;font-size:11px">Window closed</b> <span class="small muted" style="font-size:11px">— scout & shortlist, bids wait. Selling always possible.</span></div>`:""}
    ${j.offers.length?`<div class="card tight" style="border-color:rgba(255,176,46,.22);background:#2a1e0a;margin-bottom:8px"><div style="display:flex;justify-content:space-between"><h3>Bids on your players</h3><span class="tag URGENT">${j.offers.length}</span></div><div style="display:grid;gap:8px;margin-top:8px">${j.offers.map(o=>`<div style="display:flex;gap:10px;align-items:center;padding:10px;border-radius:12px;background:var(--panel);border:1px solid #5a4222;flex-wrap:wrap"><div style="width:36px;height:36px;border-radius:10px;background:var(--panel3);display:grid;place-items:center;font-weight:900;font-size:11px">${esc((o.player||"?").split(" ").map(w=>w[0]).slice(0,2).join(""))}</div><div style="flex:1;min-width:120px"><b style="font-size:12px">${esc(o.player)}</b> <span class="pos" style="margin-left:4px">${esc(o.pos)}</span><div class="small muted" style="font-size:10px">${o.age}y · ${esc(o.from_club||"—")} · value ${money(o.value)} · asking ${money(o.asking||o.value)}</div><span class="tag" style="font-size:11px;background:var(--acc-dim);color:var(--acc)">${money(o.fee)} offered</span></div><div style="display:flex;gap:6px;margin-left:auto"><button class="btn sm primary" onclick="bid(${o.id},'accept')">Accept ✓</button><button class="btn sm" onclick="bid(${o.id},'reject')">Reject</button><button class="btn sm" onclick="bidCounter(${o.id},${o.fee},${o.asking||0},${o.value||0},'${esc(o.player).replace(/'/g,"\\'")}')">Counter</button></div></div>`).join("")}</div></div>`:
  (j.listed_count?`<div class="card tight" style="margin-bottom:8px"><div style="display:flex;gap:8px;align-items:center"><span class="tag NEW">${j.listed_count} listed</span><span class="small muted" style="font-size:11px">Clubs are watching your listed players — bids land here (and in the News feed, BID section)${win?"":" · window closed, approaches are rare"}. Watch the News feed for URGENT bids.</span></div></div>`
  :`<div class="card tight" style="margin-bottom:8px;border-style:dashed"><div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap"><b style="font-size:11.5px">No bids yet</b><span class="small muted" style="font-size:11px">List players (Squad → player → List) and real clubs start bidding — especially in a window.</span></div></div>`)}
    ${(j.my_offers||[]).length?`<div class="card tight" style="margin-bottom:8px"><h3>Negotiations ${j.my_offers.length}</h3><div style="display:grid;gap:6px;margin-top:8px">${j.my_offers.map(o=>`<div style="padding:8px;border-radius:10px;background:${o.awaiting_you?"rgba(44,255,138,.06)":"transparent"};border:${o.awaiting_you?"1px solid rgba(44,255,138,.16)":"0"}"><div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap"><a href="#" onclick="go('player',${o.player_id});return false" style="font-weight:900;font-size:12px">${esc(o.player)}</a><span class="tag" style="font-size:9px">${o.direction==="in"?"BUYING":"SELLING"}</span><span class="spacer"></span><b style="font-size:11px"><span class="tag ${o.awaiting_you?"ROUTINE":""}">${esc(o.status)}${o.awaiting_you?" — YOU":""}</span> ${money(o.fee)}</b></div>${o.note?`<div style="font-size:11px;background:var(--panel2);padding:6px 8px;border-radius:8px;margin-top:6px;border-left:2px solid var(--amber)"> ${esc(o.note)}</div>`:""}</div>`).join("")}</div></div>`:""}
    <div class="card"><div style="display:flex;justify-content:space-between;align-items:center"><h3>Find star</h3><span class="small muted">${players.length} players</span></div><div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:8px"><input id="tr-q" placeholder="Name, club…" value="${esc(TR.q)}" style="flex:1;min-width:140px;min-height:36px;font-size:12px" oninput="TR.q=this.value;renderTransfersDebounced()"><select id="tr-pos" onchange="TR.pos=this.value;renderTransfers()" style="min-height:36px;font-size:11px"><option value="">Any pos</option>${G.static.positions.map(p=>`<option ${TR.pos===p?"selected":""}>${p}</option>`).join("")}</select><input id="tr-fee" type="number" placeholder="Max €m" value="${TR.max_fee||""}" style="width:80px;min-height:36px;font-size:11px" onchange="TR.max_fee=+this.value||0;renderTransfers()"><input id="tr-age" type="number" placeholder="Age ≤" value="${TR.age_max||""}" style="width:64px;min-height:36px;font-size:11px" onchange="TR.age_max=+this.value||0;renderTransfers()"><select id="tr-sort" onchange="TR.sort=this.value;renderTransfers()" style="min-height:36px;font-size:11px"><option value="value" ${TR.sort==="value"?"selected":""}>Value</option><option value="ca" ${TR.sort==="ca"?"selected":""}>Ability</option><option value="age" ${TR.sort==="age"?"selected":""}>Age</option></select><button class="btn primary sm" onclick="doSearch()">Search</button></div><div style="display:flex;gap:6px;margin-top:8px"><select id="tr-free" onchange="TR.free=this.value==='true';renderTransfers()" style="min-height:32px;font-size:11px"><option value="false" ${!TR.free?"selected":""}>Contracted</option><option value="true" ${TR.free?"selected":""}>Free</option></select><select id="tr-aff" onchange="TR.aff=this.value==='true';renderTransfers()" style="min-height:32px;font-size:11px"><option value="true" ${TR.aff!==false?"selected":""}>Affordable</option><option value="false" ${TR.aff===false?"selected":""}>Any price</option></select><span class="small muted" style="font-size:10px">Loyalty matters — rivals reject</span></div></div> <div class="transfer-grid" style="margin-top:10px">${players.map(p=>{
      const ini=(p.name||"?").split(" ").map(w=>w[0]).slice(0,2).join("").toUpperCase(), valCol=(p.value||0)>(j.budget||0)?"var(--red)":"var(--acc)";
      const ct=p.contract_end?Math.max(0,new Date(p.contract_end).getFullYear()-(G.home?.date?+G.home.date.slice(0,4):new Date().getFullYear())):0;
      const listedTag=p.listed?`<span class="tag NEW" style="font-size:7.5px">LISTED</span>`:"";
      return `<div class="transfer-card" onclick="go('player',${p.id})"><div class="transfer-card-header"><div class="transfer-card-ava">${ini}</div><div style="flex:1;min-width:0"><div class="transfer-card-name">${esc(p.name)} ${listedTag} ${p.known<60?`<span class="tag" style="font-size:8px">SCOUT ${p.known}%</span>`:""} ${shortlisted.has(p.id)?"★":""}</div><div class="transfer-card-meta"><span class="pos">${esc(p.pos)}</span> ${p.age}y · ${esc(p.club||"Free")} · Ct ${ct}y · ${stars(p.stars||2)}</div></div><div style="text-align:right"><div style="font-weight:950;font-size:13px;color:${valCol};font-family:var(--ff-mono)">${money(p.value)}</div><div class="small muted" style="font-size:10px">${wk(p.wage)}</div></div></div><div class="transfer-card-stats"><div class="transfer-card-stat"><span class="label">Asking</span><span class="value" style="color:var(--amber)">${money(p.asking||p.value)}</span></div><div class="transfer-card-stat"><span class="label">Wage</span><span class="value">${wk(p.wage)}</span></div><div class="transfer-card-stat"><span class="label">PA</span><span class="value">${p.pa?p.pa.toFixed(1):"?"}</span></div></div><div class="transfer-card-actions" onclick="event.stopPropagation()"><button class="btn sm primary" onclick='openOffer(${p.id}, ${JSON.stringify(p.name)}, ${p.asking||0}, ${p.wage||0})'>${p.listed?"Bid":"Poach"}</button><button class="btn sm" onclick="toggleShortlist(${p.id})">${shortlisted.has(p.id)?"★":"☆"}</button><button class="btn sm" onclick="go('player',${p.id})">View</button></div></div>`;
    }).join("")||`<div class="card" style="grid-column:1/-1;text-align:center;padding:24px"><div style="font-size:32px"></div><h3>No players</h3><p class="small muted">Widen search — free agents, any pos</p><button class="btn sm primary" style="margin-top:8px" onclick="TR={pos:'',q:'',max_fee:0,age_max:0,free:false,aff:false,sort:'value'};renderTransfers()">Clear filters</button></div>`}</div>`;
}
let TR_DEBOUNCE=null; function renderTransfersDebounced(){ clearTimeout(TR_DEBOUNCE); TR_DEBOUNCE=setTimeout(renderTransfers,400); }
function doSearch(){ TR={pos:$("#tr-pos").value,q:$("#tr-q").value,max_fee:+$("#tr-fee").value||0,age_max:+$("#tr-age").value||0,free:$("#tr-free").value==="true",aff:$("#tr-aff").value==="true",sort:$("#tr-sort")?.value||"value"}; renderTransfers(); }
function openOffer(pid,name,asking,wage){ modal(`<h2>Offer — ${esc(name)}</h2><div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:10px"><div><label style="font-size:10px;font-weight:900;color:var(--tx3)">FEE €m</label><input id="of-fee" type="number" step="0.1" value="${Math.max(0,(asking||0)).toFixed(1)}" style="width:100%;margin-top:4px"></div><div><label style="font-size:10px;font-weight:900;color:var(--tx3)">WAGE €k</label><input id="of-wage" type="number" step="0.1" value="${Math.max(.1,(wage||1)*1.1).toFixed(1)}" style="width:100%;margin-top:4px"></div><div><label style="font-size:10px;font-weight:900;color:var(--tx3)">YEARS</label><input id="of-years" type="number" value="3" min="1" max="6" style="width:100%;margin-top:4px"></div><div><label style="font-size:10px;font-weight:900;color:var(--tx3)">PROMISE</label><select id="of-promise" style="width:100%;margin-top:4px">${G.static.promises.map(p=>`<option ${p==="Squad Rotation"?"selected":""}>${p}</option>`).join("")}</select></div></div><label style="display:flex;gap:8px;align-items:center;margin-top:10px;font-size:12px"><input type="checkbox" id="of-loan"> Loan instead</label><div style="display:flex;gap:8px;justify-content:flex-end;margin-top:14px"><button class="btn sm" onclick="closeModal()">Cancel</button><button class="btn primary sm" onclick="submitOffer(${pid})">Submit</button></div>`); }
async function submitOffer(pid){ const body={pid,fee:+$("#of-fee").value,wage:+$("#of-wage").value,years:+$("#of-years").value,promise:$("#of-promise").value,is_loan:$("#of-loan").checked}; closeModal(); const r=await api.post("/api/transfer/offer",body); toast(esc(r.msg||(r.ok?"Submitted":"Rejected")),5000); if(G.screen==="transfers") renderTransfers(); }
async function toggleShortlist(pid){ const r=await api.post("/api/scout/shortlist",{pid}); toast(r.added?"Shortlisted ★":"Removed",2000); if(G.screen==="transfers") renderTransfers(); else if(G.screen==="scouting") renderScouting(); }
async function respondCounter(id,accept){ const r=await api.post("/api/transfer/respond",{offer_id:id,accept}); toast(esc(r.msg||"Done"),5000); renderTransfers(); }
async function respondCounterNew(id,fee){ const v=prompt("New fee €m:",(fee*.9).toFixed(1)); if(!v) return; const r=await api.post("/api/transfer/respond",{offer_id:id,accept:false,new_fee:+v}); toast(esc(r.msg||"Done"),5000); renderTransfers(); }
async function bid(id,decision){ const r=await api.post("/api/transfer/bid",{offer_id:id,decision}); toast(esc(r.msg||"Done"),4000); refreshBadges(); if(G.screen==="transfers") renderTransfers(); else if(G.screen==="inbox") renderInbox(); else refreshState(); }
function setCounter(base,mul){ const el=document.getElementById("bc-fee"); if(el) el.value=(base*mul).toFixed(1); }
async function bidCounter(id,fee,asking,value,name){
  modal(`<h2 style="font-size:18px">Counter — ${esc(name||"player")}</h2>
  <div class="small muted" style="font-size:11px;margin-top:4px">Offered <b style="color:var(--tx)">${money(fee||0)}</b> · Your valuation ${money(value||0)} · Asking ${money(asking||0)}</div>
  <div style="margin-top:10px"><label style="font-size:10px;font-weight:900;letter-spacing:.08em;color:var(--tx3)">COUNTER OFFER €m</label>
  <input id="bc-fee" type="number" step="0.1" value="${((fee||0)*1.25).toFixed(1)}" style="width:100%;margin-top:4px">
  <div style="display:flex;gap:6px;margin-top:8px;flex-wrap:wrap">
    <button class="btn sm" onclick="setCounter(${fee||0},1.1)">+10%</button>
    <button class="btn sm" onclick="setCounter(${fee||0},1.25)">+25%</button>
    <button class="btn sm" onclick="setCounter(${fee||0},1.5)">+50%</button>
    ${asking?`<button class="btn sm" onclick="setCounter(${asking},1)">Ask ${money(asking)}</button>`:""}
  </div></div>
  <div class="small muted" style="font-size:10.5px;margin-top:8px;line-height:1.45">Countering re-opens the negotiation — they can accept, reject or counter again. Going above their valuation is the surest way to close.</div>
  <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:14px"><button class="btn sm" onclick="closeModal()">Cancel</button><button class="btn primary sm" onclick="submitCounter(${id})">Send counter</button></div>`);
}
async function submitCounter(id){ const el=document.getElementById("bc-fee"); if(!el) return; const fee=+el.value; closeModal();
  const r=await api.post("/api/transfer/bid",{offer_id:id,decision:"counter",counter_fee:fee}); toast(esc(r.msg||"Counter sent"),4500); refreshBadges();
  if(G.screen==="transfers") renderTransfers(); else if(G.screen==="inbox") renderInbox(); else refreshState(); }

/* SCOUTING */
async function renderScouting(){
  const j=await api.get("/api/screen/scouting"); await refreshState();
  $("#content").innerHTML=`
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px"><b style="font-size:13px"> SCOUTING</b><span class="small muted">Knowledge accumulates over time</span></div> <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px"><div class="card"><h3>Scouts</h3><div style="margin-top:8px;display:grid;gap:4px">${j.scouts.map(s=>`<div style="display:flex;gap:8px;align-items:center;padding:6px 8px;border-radius:8px;background:var(--panel2);border:1px solid var(--line)"><span style="flex:1;font-size:11px;font-weight:800">${esc(s.name)}</span><span style="font-size:10px">${esc(s.role)}</span><span style="font-size:10px">J${s.judging} P${s.judging_pot}</span></div>`).join("")||'<p class="small muted">No scouts</p>'}</div><div style="display:flex;gap:6px;margin-top:10px"><input id="sc-region" placeholder="Region e.g. Brazil" style="flex:1;min-height:32px;font-size:11px"><button class="btn sm primary" onclick="assignRegion()">Assign</button></div></div><div class="card"><h3>Knowledge by region</h3><div style="margin-top:8px;display:grid;gap:6px">${Object.keys(j.knowledge||{}).length?Object.entries(j.knowledge).map(([k,v])=>`<div><div style="display:flex;justify-content:space-between;font-size:11px"><span>${esc(k)}</span><b>${Math.round(v)}%</b></div>${bar(v)}</div>`).join(""):'<p class="small muted">No regions scouted</p>'}</div></div></div> <div class="card" style="margin-top:10px"><h3>Shortlist ${j.targets.length}</h3><div style="margin-top:8px;display:grid;gap:4px">${j.targets.length?j.targets.map(t=>`<div style="display:flex;gap:8px;align-items:center;padding:8px;border-radius:10px;background:var(--panel2);border:1px solid var(--line)"><b style="flex:1;font-size:11px">${esc(t.name)}</b><span style="font-size:10px">${t.age}y</span><span class="pos">${esc(t.pos)}</span><span style="font-size:10px">${esc(t.club)}</span><span style="font-size:10px">${Math.round(t.known||0)}%</span><button class="btn sm primary" onclick="openOffer(${t.id},'${esc(t.name).replace(/'/g,"\\'")}',${t.value},${t.wage||1})">Bid</button></div>`).join(""):'<p class="small muted">No shortlist — add from transfers</p>'}</div></div> <div class="card" style="margin-top:10px"><h3>Offers</h3><div style="margin-top:8px">${j.offers.length?j.offers.map(o=>`<div style="padding:8px;border-radius:8px;background:var(--panel2);margin-bottom:4px;font-size:11px"><b>${esc(o.player)}</b> ${o.to_id===G.home.club.id?"In":"Out"} · ${money(o.fee)} · ${wk(o.wage)} · <span class="tag">${esc(o.status)}</span></div>`).join(""):'<p class="small muted">No offers</p>'}</div></div>`;
}
async function assignRegion(){ const region=$("#sc-region").value.trim(); if(!region) return; const r=await api.post("/api/scout/assign",{region}); toast(esc(r.msg||"Assigned")); renderScouting(); }

/* FINANCES — game vault */
async function renderFinances(){
  const f=await api.get("/api/screen/finances"); await refreshState(); const c=f.club;
  $("#content").innerHTML=`
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px"><b style="font-size:13px"> VAULT</b><span class="small muted">Cash ${money(c.cash)} · Balance ${money(c.balance)}</span></div> <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin-bottom:10px"><div style="padding:10px;border-radius:12px;background:var(--panel);border:1px solid var(--line);text-align:center"><div style="font-size:9px;color:var(--tx3);font-weight:900">CASH</div><div style="font-weight:950;color:${c.cash<0?"var(--red)":"var(--acc)"};font-family:var(--ff-mono)">${money(c.cash)}</div></div><div style="padding:10px;border-radius:12px;background:var(--panel);border:1px solid var(--line);text-align:center"><div style="font-size:9px;color:var(--tx3);font-weight:900">BALANCE</div><div style="font-weight:950;color:${c.balance<0?"var(--red)":"var(--acc)"};font-family:var(--ff-mono)">${money(c.balance)}</div></div><div style="padding:10px;border-radius:12px;background:var(--panel);border:1px solid var(--line);text-align:center"><div style="font-size:9px;color:var(--tx3);font-weight:900">BUDGET</div><div style="font-weight:950;font-family:var(--ff-mono)">${money(c.transfer_budget)}</div></div><div style="padding:10px;border-radius:12px;background:var(--panel);border:1px solid var(--line);text-align:center"><div style="font-size:9px;color:var(--tx3);font-weight:900">WAGE</div><div style="font-weight:900;font-size:11px">${money(c.wage_budget)}/yr</div></div></div> <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px"><div class="card"><h3>Monthly</h3><div class="kv"><span>Revenue</span><b>${money(f.monthly.revenue)}</b></div><div class="kv"><span>Wages</span><b style="color:#ff8a94">-${money(f.monthly.wages)}</b></div><div class="kv"><span>Running</span><b style="color:#ff8a94">-${money(f.monthly.running)}</b></div><div class="kv"><span>Interest</span><b style="color:#ff8a94">-${money(f.monthly.interest)}</b></div><div class="kv" style="border-top:1px solid var(--line);margin-top:6px;padding-top:6px"><span>Net/mo</span><b style="color:${f.monthly.revenue-f.monthly.wages-f.monthly.running-f.monthly.interest<0?"var(--red)":"var(--acc)"}">${money(f.monthly.revenue-f.monthly.wages-f.monthly.running-f.monthly.interest)}</b></div><h3 style="margin-top:12px">Season</h3><div class="kv"><span>Proj rev</span><b>${money(c.season_income)}</b></div><div class="kv"><span>Wage bill</span><b>${money(f.annual_wages)}</b></div><div class="kv"><span>Proj net</span><b style="color:${f.projected_net<0?"var(--red)":"var(--acc)"}">${money(f.projected_net)}</b></div></div><div class="card"><h3>Top earners</h3><div style="margin-top:8px;display:grid;gap:4px">${f.top_earners.map(p=>`<div style="display:flex;gap:8px;align-items:center;padding:6px 8px;border-radius:8px;background:var(--panel2)"><span style="flex:1;font-size:11px;font-weight:800">${esc(p.name)}</span><span class="pos" style="min-width:28px">${esc(p.pos)}</span><span style="font-size:10px">${wk(p.wage)}</span></div>`).join("")}</div><div class="kv" style="margin-top:10px"><span>Gate receipts</span><b>${money(f.matchday_income||0)}</b></div></div></div> <div class="card" style="margin-top:10px"><h3>Ledger ${f.history?.length||0} months</h3>${cashSpark(f.history||[])}<div style="margin-top:8px;max-height:40vh;overflow:auto;display:grid;gap:3px">${(f.history||[]).slice().reverse().map(h=>`<div style="display:grid;grid-template-columns:60px 1fr 1fr 1fr 1fr 60px;gap:6px;padding:6px 8px;border-radius:8px;background:var(--panel2);font-size:10px"><span>${esc(h.month)}</span><span>${money(h.income)}</span><span style="color:#ff8a94">-${money(h.wages)}</span><span style="color:#ff8a94">-${money(h.other)}</span><span style="color:${h.net<0?"var(--red)":"var(--acc)"}">${h.net>=0?"+":""}${money(h.net)}</span><span>${money(h.cash)}</span></div>`).join("")||'<p class="small muted">No accounts yet</p>'}</div></div>`;
}
function cashSpark(hist){
  if(!hist||hist.length<2) return "";
  const w=720,h=56,pad=4, vals=hist.map(x=>x.cash), min=Math.min(...vals), max=Math.max(...vals), span=(max-min)||1;
  const pts=vals.map((v,i)=>{ const x=pad+(w-pad*2)*(i/(vals.length-1)), y=h-pad-(h-pad*2)*((v-min)/span); return `${x.toFixed(1)},${y.toFixed(1)}`; }).join(" ");
  return `<svg viewBox="0 0 ${w} ${h}" style="width:100%;height:${h}px" preserveAspectRatio="none"><polyline points="${pts}" fill="none" stroke="#2cff8a" stroke-width="2"/><text x="${pad}" y="12" fill="#5a7090" font-size="10">cash ${money(max)} … ${money(min)}</text></svg>`;
}

/* STAFF / YOUTH */
let _staffRoleFilter="All";
const STAFF_ROLE_LABEL={All:"All","Assistant Manager":"AM","First-Team Coach":"FT Coach","Fitness Coach":"Fitness","Goalkeeping Coach":"GK","Head of Youth Development":"Youth","Chief Scout":"Chief Scout","Scout":"Scout","Physio":"Physio","Data Analyst":"Data"};
function staffAttrChips(s){ const L={tactical:"Tac",technical:"Tec",mental:"Men",man_mgmt:"Mgr",fitness:"Fit",goalkeeping:"GK",youth:"You",judging:"Jud"}; return Object.entries(s.key).map(([k,v])=>`<span style="font-size:9.5px;padding:2px 5px;border-radius:5px;background:var(--panel3);border:1px solid var(--line);color:var(--tx2)">${L[k]||k} <b style="color:var(--tx)">${v}</b></span>`).join(""); }
function staffCard(s,actions){
  const cd=s.contract_days;
  const chip=cd==null?`<span class="small muted" style="font-size:9.5px">free agent</span>`
    :`<span style="font-size:9.5px;padding:2px 6px;border-radius:999px;font-weight:900;${cd<90?"background:rgba(255,90,110,.16);color:#ff8a94":cd<180?"background:rgba(255,200,50,.14);color:#ffcc33":"background:var(--panel3);color:var(--tx3)"}">until ${cd}d</span>`;
  return `<div style="display:flex;gap:8px;align-items:flex-start;padding:10px;border-radius:12px;background:var(--panel);border:1px solid var(--line)">
    <div style="flex:1;min-width:0"><div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap"><b style="font-size:12px">${esc(s.name)}</b><span class="tag" style="font-size:8.5px">${s.quality}</span>${chip}</div>
    <div class="small muted" style="font-size:10px;margin-top:2px">${esc(s.role)} · ${esc(s.nat)} · ${s.age}y</div>
    <div style="display:flex;gap:4px;flex-wrap:wrap;margin-top:5px">${staffAttrChips(s)}</div></div>
    <div style="text-align:right;display:flex;flex-direction:column;align-items:flex-end;gap:6px"><span style="font-size:10.5px;font-weight:900;font-family:var(--ff-mono)">${wk(s.wage)}/wk</span>${actions}</div></div>`;
}
async function renderStaff(){
  const j=await api.get("/api/screen/staff"); await refreshState();
  const w=j.wage, load=w.players+w.staff;
  const pool=(j.pool||[]).filter(s=>_staffRoleFilter==="All"||s.role===_staffRoleFilter);
  $("#content").innerHTML=`
  <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px"><b style="font-size:13px"> STAFF · ${j.current.length}/${j.cap}</b><span class="spacer"></span><span class="small muted" style="font-size:10.5px">Coaching <b style="color:var(--acc)">${j.coaching.training}</b> · Dev <b style="color:var(--acc)">${j.coaching.development}</b>${j.coaching.youth?` · Youth <b style="color:var(--acc)">${j.coaching.youth}</b>`:""}</span></div>
  <div class="small muted" style="font-size:10.5px;margin-bottom:10px">Wage load ${money(load)} of ${money(w.budget)} budget (players ${money(w.players)} + staff ${money(w.staff)}) · cash ${money(w.cash)} · coaching drives training & development</div>
  <div style="display:grid;gap:6px;margin-bottom:12px">${j.current.map(s=>staffCard(s,`<button class="btn sm" onclick="staffRenew(${s.id})">Renew</button><button class="btn sm" id="sack-${s.id}" onclick="staffSack(${s.id},'${esc(s.name)}')">Sack</button>`)).join("")||'<p class="small muted">No backroom staff — hire from the market below.</p>'}</div>
  <b style="font-size:11px;letter-spacing:.1em;color:var(--tx3)">COACHING MARKET</b>
  <div style="display:flex;gap:4px;flex-wrap:wrap;margin:8px 0">${["All",...(j.roles||[])].map(r=>`<button class="btn sm ${r===_staffRoleFilter?"primary":""}" onclick="_staffRoleFilter='${r}' ;renderStaff()">${STAFF_ROLE_LABEL[r]||r}</button>`).join("")}</div>
  <div style="display:grid;gap:6px">${pool.map(s=>staffCard(s,`<button class="btn sm primary" onclick="staffHire(${s.id},'${esc(s.name)}')">Sign · ${s.reputation>=70?"3y":"2y"}</button>`)).join("")||'<p class="small muted">No available coaches in this role.</p>'}</div>`;
}
async function staffHire(id,name){
  try{ const r=await api.post("/api/staff/hire",{id});
    if(r.ok){ toast(`${name} signs · coaching ${r.coaching_before?.training??"–"} → ${r.coaching?.training??"–"}`,4200); Juice.haptic("success"); Juice.play("success"); }
    else toast(esc(r.msg||"Cannot sign"),4200);
    await renderStaff();
  }catch(e){ toast("Failed: "+esc(e.message),4000); }
}
async function staffSack(id,name){
  const b=document.getElementById("sack-"+id);
  if(b&&!b.dataset.armed){ b.dataset.armed="1"; b.textContent="Confirm?"; b.classList.add("primary"); setTimeout(()=>{ if(b){ delete b.dataset.armed; b.textContent="Sack"; b.classList.remove("primary"); } },3000); return; }
  try{ const r=await api.post("/api/staff/sack",{id});
    if(r.ok){ toast(`${name} released · ${money(r.severance)} severance`,4200); Juice.haptic("medium"); Juice.play("nav"); }
    else toast(esc(r.msg||"Cannot release"),4200);
    await renderStaff();
  }catch(e){ toast("Failed: "+esc(e.message),4000); }
}
async function staffRenew(id){
  try{ const r=await api.post("/api/staff/renew",{id});
    if(r.ok){ toast(`${r.name} renews to ${r.contract_end}`,4000); Juice.haptic("success"); Juice.play("success"); }
    else toast(esc(r.msg||"Cannot renew"),4000);
    await renderStaff();
  }catch(e){ toast("Failed: "+esc(e.message),4000); }
}
async function renderYouth(){
  const j=await api.get("/api/screen/youth"); await refreshState();
  $("#content").innerHTML=`<div style="display:flex;align-items:center;gap:8px;margin-bottom:10px"><b style="font-size:13px"> ACADEMY · recruitment ${j.rating}/20 · facilities ${j.facilities}/20</b></div><div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:8px">${j.players.map(p=>`<button onclick="go('player',${p.id})" style="text-align:left;padding:10px;border-radius:14px;background:var(--panel);border:1px solid var(--line);color:var(--tx)"><div style="display:flex;gap:8px;align-items:center"><span class="pos">${esc(p.pos)}</span><b style="font-size:11px;flex:1">${esc(p.name)}</b><span style="font-size:10px">${p.age}y</span></div><div class="small muted" style="font-size:10px;margin-top:4px">${esc(p.personality)} · CA ${p.ca.toFixed(1)} / PA ${p.pa.toFixed(1)}</div><div style="margin-top:6px;font-size:10px">${stars(p.stars)} now · ${stars(p.stars_pa)} pot</div></button>`).join("")||'<p class="small muted">No youth yet</p>'}</div>`;
}
function facBar(lv){ return `<div style="display:flex;gap:3px;margin-top:6px">${Array.from({length:10},(_,i)=>`<span style="width:11px;height:11px;border-radius:3px;background:${i<lv?"linear-gradient(165deg,var(--acc2),var(--acc))":"var(--panel3)"};opacity:${i<lv?1:.55}"></span>`).join("")}</div>`; }
async function renderFacilities(){
  const j=await api.get("/api/screen/facilities"); await refreshState();
  $("#content").innerHTML=`<div style="display:flex;align-items:center;gap:8px;margin-bottom:4px"><b style="font-size:13px">FACILITIES · overall ${j.overall}/20</b><span class="spacer"></span><span class="small muted" style="font-size:11px">cash ${money(j.cash)}</span></div>
  <div class="small muted" style="font-size:10.5px;margin-bottom:10px">Paid from club cash · one project at a time per area · effects apply when work is done</div>
  <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:8px">${j.items.map(it=>{
    const afford=!it.next_cost||j.cash>=it.next_cost;
    return `<div class="card tight"><div style="display:flex;justify-content:space-between;align-items:baseline"><h3>${esc(it.label)}</h3><b style="font-size:11px;font-family:var(--ff-mono)">${it.level}/${it.max}</b></div>${facBar(it.level)}
    <p class="small muted" style="font-size:10.5px;margin-top:8px;line-height:1.45">${esc(it.effect)}</p>
    ${it.building?`<div style="margin-top:10px"><span class="tag NEW">WORK IN PROGRESS</span><div class="small muted" style="font-size:10px;margin-top:4px">completes ${fmtDate(it.done_date)}</div></div>`
    :it.next_cost==null?`<div class="small muted" style="margin-top:10px;font-size:10.5px">Fully modernised</div>`
    :`<div style="display:flex;justify-content:space-between;align-items:center;margin-top:10px"><div class="small muted" style="font-size:10.5px">${money(it.next_cost)} · ${it.days} days${!afford?' · <span style="color:#ff8a94">insufficient cash</span>':""}</div><button class="btn sm primary" ${afford?"":"disabled"} onclick="doFacilityUpgrade('${it.key}')">Upgrade</button></div>`}
    </div>`;
  }).join("")}</div>
  <div class="card tight" style="margin-top:10px"><h3>Stadium</h3><div class="kv"><span>Name</span><b style="font-size:11px">${esc(j.stadium)}</b></div><div class="kv"><span>Capacity</span><b>${j.capacity.toLocaleString()}</b></div><div class="kv"><span>Season revenue</span><b>${money(j.season_income)}</b></div><p class="small muted" style="font-size:10.5px;margin-top:6px">Stadium upgrades raise attendance and ticket prices — the new revenue starts with the next monthly accounts.</p></div>`;
}
async function doFacilityUpgrade(key){
  try{ const r=await api.post("/api/facilities/upgrade",{facility:key});
    if(r.ok){ toast("Work started",4000); Juice.haptic("success"); Juice.play("success"); }
    else toast(esc(r.msg||"Cannot start that project"),4200);
    await renderFacilities();
  }catch(e){ toast("Failed: "+esc(e.message),4000); }
}
async function renderCalendar(){
  const j=await api.get("/api/screen/calendar"); await refreshState(); const nextDate=(G.home.next_fixture||{}).date;
  $("#content").innerHTML=`<div style="display:flex;align-items:center;gap:8px;margin-bottom:10px"><b style="font-size:13px"> CALENDAR · ${G.home.season_label}</b></div><div style="display:grid;gap:6px">${j.fixtures.map(f=>{
    const next=!f.played&&f.date===nextDate;
    return `<div style="display:grid;grid-template-columns:70px 1fr auto;gap:10px;padding:10px 12px;border-radius:12px;background:${next?"rgba(44,255,138,.08)":f.played?"var(--panel)":"linear-gradient(165deg,var(--panel2),var(--panel))"};border:1px solid ${next?"rgba(44,255,138,.18)":"var(--line)"};align-items:center;${next?"box-shadow:inset 3px 0 0 var(--acc)":""}"><div><b style="font-size:11px">${fmtDate(f.date).replace(/, \d{4}$/,"")}</b><div style="font-size:9px;color:var(--tx3)">${esc(compLabel(f))}</div></div><div style="display:flex;align-items:center;gap:6px;min-width:0"><div style="flex:1;min-width:0;display:flex;align-items:center;gap:6px;justify-content:flex-end"><span style="font-weight:800;font-size:11px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(f.home_short||f.home)}</span>${crest(f.home_code)}</div><span style="font-weight:950;font-size:11px;min-width:32px;text-align:center;padding:2px 6px;border-radius:8px;background:var(--panel3);font-family:var(--ff-mono)">${f.played?`${f.hg}–${f.aw}`:"v"}</span><div style="flex:1;min-width:0;display:flex;align-items:center;gap:6px">${crest(f.away_code)}<span style="font-weight:800;font-size:11px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(f.away_short||f.away)}</span></div></div><span>${f.res?`<span class="tag ${f.res}">${f.res}</span>`:next?'<span class="tag NEW">next</span>':""}</span></div>`;
  }).join("")}</div>`;
}
async function renderStats(){
  const j=await api.get("/api/screen/stats");
  if(j.error){ $("#content").innerHTML='<div class="card">No club — no stats.</div>'; return; }
  const maxG=j.scorers.length?j.scorers[0].goals:1;
  const row=(o,main,val,sub,onclick)=>`<${onclick?'button onclick="'+onclick+'"':'div'} class="stat-row">${o.code?crest(o.code):""}<span class="sr-n">${esc(o.name)}<small>${esc(o.club||o.pos||"")}${sub?" · "+sub:""}</small></span><b>${val}</b></${onclick?'button':'div'}>`;
  const xgRow=r=>{
    const good=r.delta>0.5, bad=r.delta<-0.5;
    return `<div class="xgt-row${r.name===(G.home&&G.home.club&&G.home.club.name)?" me":""}"> <span class="xn">${crest(r.code)}${esc(r.name)}</span> <span class="xv">${r.p}</span><span class="xv">${r.gf}</span> <span class="xv mono">${r.xgf.toFixed(1)}</span> <span class="xv mono ${good?"pos":bad?"neg":""}" style="color:${good?"var(--acc)":bad?"var(--red)":"var(--tx2)"}">${r.delta>0?"+":""}${r.delta.toFixed(1)}</span> <span class="xv">${r.ga}</span><span class="xv mono">${r.xga.toFixed(1)}</span></div>`; };
  $("#content").innerHTML=`
    <div class="ph"><h2>Statistics</h2><span class="small muted">${esc(j.comp)} · ${j.season}/${(j.season+1)%100}</span></div> <div class="card tight"><div class="sec-h"><h3>Golden boot</h3><span class="small muted">goals</span></div> ${j.scorers.length?j.scorers.slice(0,10).map((o,i)=>`<div class="stat-row"><span class="rk">${i+1}</span>${crest(o.code)}<span class="sr-n">${esc(o.name)}<small>${esc(o.club)} · ${esc(o.pos)}</small></span><span class="bar"><i style="width:${Math.round(100*o.goals/maxG)}%"></i></span><b>${o.goals}</b></div>`).join(""):'<p class="small muted" style="padding:10px">No goals yet this season.</p>'}</div> <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:8px"> <div class="card tight"><div class="sec-h"><h3>Assists</h3></div>${j.assists.slice(0,5).map(o=>row(o,0,o.assists,o.goals+"g")).join("")||'<p class="small muted" style="padding:10px">—</p>'}</div> <div class="card tight"><div class="sec-h"><h3>Clean sheets</h3></div>${j.csheets.slice(0,5).map(o=>row(o,0,o.cs,o.pos)).join("")||'<p class="small muted" style="padding:10px">—</p>'}</div> </div> <div class="card tight" style="margin-top:8px"><div class="sec-h"><h3>Expected goals vs actual</h3><span class="small muted">finishing over/under-performance</span></div> <div class="xgt-head"><span class="xn">Club</span><span class="xv">P</span><span class="xv">GF</span><span class="xv">xG</span><span class="xv">Δ</span><span class="xv">GA</span><span class="xv">xGA</span></div> ${j.xg.length?j.xg.map(xgRow).join(""):'<p class="small muted" style="padding:10px">No league matches played yet.</p>'}</div> <div class="card tight" style="margin-top:8px"><div class="sec-h"><h3>Your squad</h3><button class="btn sm" onclick="go('squad')">Squad ▸</button></div> <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px"> <div><h4 class="mini-h">Goals</h4>${j.leaders.goals.map(o=>`<div class="stat-row sm">${crest(j.my_code)}<span class="sr-n">${esc(o.name)}</span><b>${o.v}</b></div>`).join("")||'<p class="small muted">—</p>'}</div> <div><h4 class="mini-h">Assists</h4>${j.leaders.assists.map(o=>`<div class="stat-row sm">${crest(j.my_code)}<span class="sr-n">${esc(o.name)}</span><b>${o.v}</b></div>`).join("")||'<p class="small muted">—</p>'}</div> <div><h4 class="mini-h">Avg rating</h4>${j.leaders.rating.map(o=>`<div class="stat-row sm">${crest(j.my_code)}<span class="sr-n">${esc(o.name)}<small>${o.apps} apps</small></span><b>${o.v.toFixed(2)}</b></div>`).join("")||'<p class="small muted">—</p>'}</div> </div></div> <div class="card tight" style="margin-top:8px;margin-bottom:12px"><div class="sec-h"><h3>Form guide</h3><span class="small muted">last ${j.form.length}</span></div> ${j.form.map(f=>`<div class="stat-row"><span class="res ${f.res}">${f.res}</span>${crest(f.code)}<span class="sr-n">${f.home?"vs":"at"} ${esc(f.opp)}<small>${esc(f.date)}</small></span><b class="mono">${f.gf}–${f.ga}</b></div>`).join("")||'<p class="small muted" style="padding:10px">No matches played.</p>'}</div>`;
  polish($("#content"));
}
async function renderTable(){
  const j=await api.get("/api/screen/table"); await refreshState();
  if(!j.comp){ $("#content").innerHTML="<h1>League</h1><p class='small muted'>No league</p>"; return; }
  $("#content").innerHTML=`
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px"><b style="font-size:13px"> ${esc(j.comp.name)}</b><span class="small muted">${G.home.season_label} · ${j.prom_spots} up / ${j.rel_spots} down</span></div> <div style="display:grid;gap:4px">${j.rows.map(r=>`<div style="display:grid;grid-template-columns:28px 1fr 28px 28px 28px 28px 36px 36px 40px 56px;gap:4px;padding:8px 10px;border-radius:10px;background:${r.club_id===j.my_club?"rgba(44,255,138,.1)":"var(--panel)"};border:1px solid ${r.club_id===j.my_club?"rgba(44,255,138,.18)":r.zone==="promotion"?"rgba(44,255,138,.14)":r.zone==="relegation"?"rgba(255,59,74,.14)":"var(--line)"};align-items:center;${r.club_id===j.my_club?"box-shadow:inset 3px 0 0 var(--acc)":""}"><span style="font-size:11px;font-weight:900;text-align:center">${r.pos||"–"}${r.zone==="promotion"?"<span style='color:var(--acc)'>▲</span>":r.zone==="relegation"?"<span style='color:var(--red)'>▼</span>":""}</span><span class="cellclub">${crest(r.code)}<span>${esc(r.name)}</span></span><span style="font-size:11px;text-align:center;font-family:var(--ff-mono)">${r.p}</span><span style="font-size:11px;text-align:center;font-family:var(--ff-mono)">${r.w}</span><span style="font-size:11px;text-align:center;font-family:var(--ff-mono)">${r.d}</span><span style="font-size:11px;text-align:center;font-family:var(--ff-mono)">${r.l}</span><span style="font-size:11px;text-align:center;font-family:var(--ff-mono)">${r.gf}</span><span style="font-size:11px;text-align:center;font-family:var(--ff-mono)">${r.ga}</span><span style="font-size:11px;text-align:center;font-family:var(--ff-mono)">${r.gf-r.ga>0?"+":""}${r.gf-r.ga}</span><b style="font-size:13px;text-align:center;font-family:var(--ff-mono)">${r.pts}</b></div>`).join("")}</div> <div class="small muted" style="padding:8px 10px;display:flex;gap:12px;font-size:10px"><span>▲ promotion</span><span>▼ relegation</span><span class="spacer"></span><span>${j.prom_spots} up · ${j.rel_spots} down</span></div>`;
}

/* COMPS */
function compMono(code){ const m={UCL:"UCL",UEL:"UEL",UECL:"UECL",ENG1:"PL",ESP1:"LaL",ITA1:"SA",GER1:"BL",FRA1:"L1",FACUP:"FA",EFLCUP:"EFL",COPADELREY:"CdR",COPPAITALIA:"CI",DFBPOKAL:"DFB",COUPEDEFRANCE:"CdF"}; if(m[code]) return m[code]; return String(code||"?").slice(0,3); }
function compBand(c,right){ const logo=compLogo(c.code,"lg"); return `<div class="comp-band" style="--comp:${compColor(c.code)}">${logo}<span style="min-width:0"><b>${esc(c.name)}</b><br><span style="font-size:10px;color:var(--tx2)">${esc(c.ctype==="continental"?"Europe":c.ctype==="cup"?"Knockout":"League")}${c.tier?" · tier "+c.tier:""}</span></span><span class="spacer"></span>${right||""}</div>`; }
async function renderComps(){
  const j=await api.get("/api/screen/comps"); await refreshState(); const my=G.home&&G.home.club?G.home.club.id:0;
  $("#content").innerHTML=`<div style="display:flex;align-items:center;gap:8px;margin-bottom:10px"><b style="font-size:13px"> COMPETITIONS</b><span class="small muted">${G.home?G.home.season_label:""}</span></div><div style="display:grid;gap:8px">${j.comps.map(c=>{
    let status=""; if(c.table&&c.table.length){ const r=c.table.find(x=>x.club_id===my); status=r&&r.pos?`<span class="tag">${r.pos}${ord(r.pos)}</span>`:""; } else status='<span class="tag">KO</span>';
    return `<button class="comp-head" style="width:100%;text-align:left" onclick="renderCompHub(${c.comp.id})">${compBand(c.comp,status+'<span style="opacity:.4"> ▸</span>')}</button>`;
  }).join("")}</div>`;
}
function ord(n){ if(n%100>=11&&n%100<=13) return "th"; return ["th","st","nd","rd"][n%10]||"th"; }
async function renderCompHub(id){
  const j=await api.get("/api/screen/comp?id="+id); if(!j||j.error){ toast("Competition not found"); return; }
  const k=j.comp, my=G.home&&G.home.club?G.home.club.id:0, tbl=j.table||[], me=tbl.find(r=>r.club_id===my), played=j.fixtures.filter(f=>f.played), todo=j.fixtures.filter(f=>!f.played);
  const rowHtml=r=>`<div style="display:grid;grid-template-columns:28px 1fr 24px 24px 24px 24px 32px 32px;gap:4px;padding:6px 10px;border-radius:8px;background:${r.club_id===my?"rgba(44,255,138,.1)":"var(--panel2)"};border:1px solid ${r.club_id===my?"rgba(44,255,138,.18)":"var(--line)"};align-items:center"><span style="font-size:10px;text-align:center">${r.pos||"–"}</span><span class="cellclub">${crest(r.code)}<span style="font-size:11px">${esc(r.name)}</span></span><span style="font-size:10px;text-align:center">${r.p}</span><span style="font-size:10px;text-align:center">${r.w}</span><span style="font-size:10px;text-align:center">${r.d}</span><span style="font-size:10px;text-align:center">${r.l}</span><span style="font-size:10px;text-align:center">${r.gf-r.ga>0?"+":""}${r.gf-r.ga}</span><b style="font-size:11px;text-align:center">${r.pts}</b></div>`;
  const fxRow=f=>{ const myW=f.played&&((f.home_id===my&&f.hg>f.ag)||(f.away_id===my&&f.ag>f.hg)), myD=f.played&&f.hg===f.ag; return `<div style="display:flex;gap:8px;align-items:center;padding:8px;border-radius:8px;background:var(--panel2);margin-bottom:4px"><span class="tag ${myW?"W":myD?"D":"L"}" style="min-width:32px;justify-content:center">${f.played?`${f.hg}–${f.aw}`:fmtDate(f.date).split(",")[0]}</span><span style="flex:1;min-width:0;display:flex;align-items:center;gap:6px;overflow:hidden"><span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:11px">${crest(f.home_code)} ${esc(f.home_short||f.home)} v ${esc(f.away_short||f.away)} ${crest(f.away_code)}</span></span><b style="font-size:10px;color:var(--tx3)">${f.stage!=="league"?esc(f.stage):""}</b></div>`; };
  $("#content").innerHTML=`<button class="btn sm" onclick="renderComps()" style="margin-bottom:8px">◂ All comps</button><div class="comp-head">${compBand(k,me&&me.pos?`<span class="tag">${me.pos}${ord(me.pos)}</span>`:"")}</div>${tbl.length?`<div class="card tight" style="margin-top:8px"><h3>${k.ctype==="continental"?"League phase":"Standings"}</h3><div style="margin-top:8px;display:grid;gap:3px">${tbl.map(rowHtml).join("")}</div></div>`:""}${(j.ko||[]).length?`<div class="card tight" style="margin-top:8px"><h3>Knockout</h3><div style="margin-top:8px;display:grid;gap:10px">${j.ko.map(r=>`<div><div style="font-size:10px;letter-spacing:.1em;font-weight:900;color:var(--tx3);margin-bottom:6px">${esc(r.stage==="F"?"Final":r.stage==="SF"?"Semi":r.stage==="QF"?"Quarter":r.stage)}</div>${r.ties.map(t=>{ const hw=t.played&&t.hg>t.ag, aw=t.played&&t.ag>t.hg; return `<div class="brk-m" style="margin-bottom:4px"><span style="font-weight:${hw?"900":"600"}">${crest(t.home_code)} ${esc(t.home_short||t.home)}</span><span style="font-family:var(--ff-mono);font-weight:900">${t.played?t.hg+"–"+t.ag:fmtDate(t.date).split(",")[0]}</span><span style="text-align:right;font-weight:${aw?"900":"600"}">${esc(t.away_short||t.away)} ${crest(t.away_code)}</span></div>`; }).join("")}</div>`).join("")}</div></div>`:""}<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:8px"><div class="card tight"><h3>Results</h3><div style="margin-top:8px">${played.length?played.slice().reverse().slice(0,8).map(fxRow).join(""):'<p class="small muted">No results</p>'}</div></div><div class="card tight"><h3>Fixtures</h3><div style="margin-top:8px">${todo.length?todo.slice(0,8).map(fxRow).join(""):'<p class="small muted">No fixtures</p>'}</div></div></div>`;
}
async function renderClub(){
  await refreshState(); const c=G.home.club;
  $("#content").innerHTML=`
    <div class="card"><div class="p-head">${crest(c.code,"xl")}<div style="min-width:0"><h2>${esc(c.name)}</h2><p class="small muted" style="font-size:11px">${esc(c.league)} · tier ${c.tier} · rep ${c.rep}</p></div></div><div class="divider"></div><div class="kv"><span>Stadium</span><b>${esc(c.stadium)}</b></div><div class="kv"><span>Capacity</span><b>${(c.capacity||0).toLocaleString()}</b></div><div class="kv"><span>Season</span><b>${G.home.season_label}</b></div></div> <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:10px">${[["board"," Board","Confidence & objectives"],["media"," Media","Press & headlines"],["staff"," Staff","Coaches, scouts"],["youth"," Academy","Intake & prospects"],["career"," Career","Record & trophies"],["finances"," Finances","Budgets & wages"]].map(([id,icon,t])=>`<button class="card tight" style="text-align:left" onclick="Juice.haptic('tap');go('${id}')"><b style="font-size:12px">${icon} ${t.split(" ")[0]}</b><p class="small muted" style="font-size:10px;margin-top:3px">${esc(t.split(" ").slice(1).join(" ")||id)}</p></button>`).join("")}</div>`;
}
async function renderBoard(){
  const j=await api.get("/api/screen/board"); await refreshState(); if(j.unemployed) return renderJobs();
  $("#content").innerHTML=`
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px"><b style="font-size:13px"> BOARD · ${esc(j.job_security)}</b></div> <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px"><div class="card"><h3>Confidence</h3><div class="stat">${Math.round(j.confidence)}<span style="font-size:12px;color:var(--tx3)">/100</span></div>${bar(j.confidence,j.confidence<30?"red":j.confidence<55?"amber":"")}<div class="kv" style="margin-top:8px"><span>Chairman</span><b style="font-size:11px">${esc(j.chairman)}</b></div><div class="kv"><span>Patience</span><b>${j.patience}</b></div><div class="kv"><span>Vision</span><b style="font-size:11px">${esc(j.vision)}</b></div>${j.warning?'<div style="margin-top:8px;padding:8px;border-radius:10px;background:#2a1218;border:1px solid rgba(255,59,74,.18)"><b style="color:#ff8a94;font-size:11px"> Official warning</b></div>':""}</div><div class="card"><h3>Fans & media</h3><div class="kv"><span>Fans</span><b>${Math.round(j.fans.sentiment)}</b></div>${bar(j.fans.sentiment)}<div class="kv" style="margin-top:6px"><span>Support</span><b>${Math.round(j.fans.support)}</b></div>${bar(j.fans.support)}<div class="kv" style="margin-top:6px"><span>Media press</span><b>${Math.round(j.media.pressure||0)}</b></div>${bar(j.media.pressure||0,"amber")}<div class="kv" style="margin-top:6px"><span>Narrative</span><b style="font-size:11px">${esc(j.media.narrative||"—")}</b></div></div></div> <div class="card" style="margin-top:8px"><h3>Objectives</h3><div style="margin-top:8px;display:grid;gap:6px">${j.objectives.map(o=>`<div style="padding:8px;border-radius:10px;background:var(--panel2);border:1px solid var(--line)"><div style="font-size:12px;font-weight:800">${esc(o.text)} ${o.critical?'<span class="tag URGENT">CRITICAL</span>':""}</div><div class="small muted" style="font-size:10px">${esc(o.comp||"")} ${o.target_pos?"· target "+o.target_pos:""} · ${esc(o.status)}</div></div>`).join("")}</div></div> <div class="card" style="margin-top:8px"><h3>Position</h3>${j.position?`<div class="kv"><span>League</span><b>${j.position.pos} of ${j.position.size}</b></div><div class="kv"><span>Points</span><b>${j.position.pts} from ${j.position.played}</b></div><div class="kv"><span>GD</span><b>${j.position.gd>0?"+":""}${j.position.gd}</b></div>`:'<p class="small muted">No record</p>'}</div><div style="margin-top:10px"><button class="btn danger sm" onclick="resignJob()">Resign</button></div>`;
}
async function resignJob(){ if(!confirm("Resign? You will be unemployed")) return; const r=await api.post("/api/career/resign",{}); toast(esc(r.msg||"Resigned")); await refreshState(); go("jobs"); }
async function renderMedia(){
  const j=await api.get("/api/screen/media"); await refreshState(); const h=G.home, f=h?h.next_fixture:null, rivalry=f?isRivalry(f.home_code,f.away_code):null;
  $("#content").innerHTML=`
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px"><b style="font-size:13px"> MEDIA</b><span class="small muted">Narrative ${esc(j.narrative||"—")} · Pressure ${Math.round(j.pressure||0)}</span></div> <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin-bottom:10px"><div style="padding:8px;border-radius:10px;background:var(--panel);border:1px solid var(--line);text-align:center"><div style="font-size:9px;color:var(--tx3);font-weight:900">NARRATIVE</div><div style="font-size:11px;font-weight:800">${esc(j.narrative||"—").slice(0,18)}</div></div><div style="padding:8px;border-radius:10px;background:var(--panel);border:1px solid var(--line);text-align:center"><div style="font-size:9px;color:var(--tx3);font-weight:900">PRESSURE</div><div style="font-weight:950">${Math.round(j.pressure||0)}/100</div>${bar(j.pressure||0,(j.pressure||0)>70?"red":(j.pressure||0)>40?"amber":"")}</div><div style="padding:8px;border-radius:10px;background:var(--panel);border:1px solid var(--line);text-align:center"><div style="font-size:9px;color:var(--tx3);font-weight:900">BOARD</div><div style="font-weight:950">${Math.round(h?h.board.confidence:0)}</div></div><div style="padding:8px;border-radius:10px;background:var(--panel);border:1px solid var(--line);text-align:center"><div style="font-size:9px;color:var(--tx3);font-weight:900">FANS</div><div style="font-weight:950">${Math.round(h?h.fans.sentiment:0)}</div></div></div> ${f?`<div class="card" style="background:linear-gradient(165deg,#1a1a30,#12182a);border-color:#1a2a4a;margin-bottom:8px"><div style="display:flex;justify-content:space-between"><h3 style="color:#ff6b8a"> Press — ${esc(f.home)} vs ${esc(f.away)}</h3><span class="tag">${esc(compLabel(f))}</span></div>${rivalry?`<div class="derby-banner" style="border-radius:10px;margin:8px 0"> ${esc(rivalry.name.toUpperCase())} — PACKED PRESS ROOM </div>`:""}<div class="pre" style="background:rgba(0,0,0,.25);border-color:#1a2a4a;color:#a0b8d0;font-style:italic;margin-top:8px">Reporter: \"${rivalry?`This ${esc(rivalry.name)} means everything. How handle pressure?`:f.code==="UCL"?"UCL nights special — message to fans?":`Next: ${esc(f.away)} away. How approach?`}\"</div><div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-top:10px"><button class="btn primary sm" onclick="press('confident')"> We fear no one<br><span style="font-size:9px;opacity:.8">Fans +++ Board ++</span></button><button class="btn sm" onclick="press('balanced')"> Respect opponent<br><span style="font-size:9px">Balanced</span></button><button class="btn sm" onclick="press('defensive')"> Solid<br><span style="font-size:9px">Board ++ if underdog</span></button><button class="btn danger sm" onclick="press('critical')"> Players must step up<br><span style="font-size:9px">High risk</span></button></div></div>`:`<div class="card" style="margin-bottom:8px"><h3>Press room quiet</h3><p class="small muted" style="font-size:11px">No fixture — when fixture, hype builds with rivalry context</p><div style="display:flex;gap:6px;margin-top:8px;flex-wrap:wrap"><button class="btn sm" onclick="press('confident')">Back players</button><button class="btn sm" onclick="press('balanced')">Balanced</button><button class="btn sm" onclick="press('defensive')">Deflect</button><button class="btn danger sm" onclick="press('critical')">Critical</button></div></div>`}
    <div class="card tight" style="padding:0"><div style="padding:10px 12px 6px;display:flex;justify-content:space-between"><h3>World news — living world</h3><span class="small muted" style="font-size:10px">Clubs buy/sell/sack</span></div><div style="max-height:60vh;overflow:auto">${j.news.map(n=>{
      const isTr=(n.cat||"").toLowerCase().includes("transfer")||(n.text||"").toLowerCase().includes("joins"), icon=isTr?"":(n.cat||"").includes("MANAGER")?"":"";
      return `<div style="display:flex;gap:10px;padding:10px 12px;border-bottom:1px solid rgba(255,255,255,.04);min-height:48px"><div style="width:28px;height:28px;border-radius:8px;background:var(--panel3);display:grid;place-items:center;font-size:12px;flex:none">${icon}</div><div style="flex:1;min-width:0"><div style="font-size:12px;line-height:1.3">${esc(n.text).replace("for €0k on loan","on loan")}</div><div style="display:flex;gap:6px;margin-top:2px"><span class="mcat" style="font-size:8px">${esc(n.cat)}</span><span style="font-size:9px;color:var(--tx3)">${fmtDate(n.date).split(",")[0]}</span></div></div></div>`;
    }).join("")||'<div style="padding:20px;text-align:center" class="small muted">No news yet</div>'}</div></div>`;
}
async function press(answer){ const r=await api.post("/api/media/press",{answer}); toast(`Board ${r.board} · Fans ${r.fans} · Press ${r.media_pressure}`,4000); renderMedia(); }
async function renderCareer(){
  const j=await api.get("/api/screen/career"); await refreshState();
  $("#content").innerHTML=`
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px"><b style="font-size:13px"> CAREER · ${esc(j.manager.name)} · rep ${j.reputation}/95</b></div> <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin-bottom:10px"><div style="padding:8px;border-radius:10px;background:var(--panel);border:1px solid var(--line);text-align:center"><div style="font-size:9px;color:var(--tx3);font-weight:900">CLUB</div><div style="font-weight:900;font-size:11px">${j.club?esc(j.club.name):"Unemployed"}</div></div><div style="padding:8px;border-radius:10px;background:var(--panel);border:1px solid var(--line);text-align:center"><div style="font-size:9px;color:var(--tx3);font-weight:900">TROPHIES</div><div style="font-weight:950;font-size:16px">${j.trophies.length}</div></div><div style="padding:8px;border-radius:10px;background:var(--panel);border:1px solid var(--line);text-align:center"><div style="font-size:9px;color:var(--tx3);font-weight:900">SEASONS</div><div style="font-weight:950">${j.season-2026+1}</div></div><div style="padding:8px;border-radius:10px;background:var(--panel);border:1px solid var(--line);text-align:center"><div style="font-size:9px;color:var(--tx3);font-weight:900">REP</div><div style="font-weight:950">${j.reputation}</div></div></div> <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px"><div class="card"><h3>Club history</h3><div style="margin-top:8px;display:grid;gap:4px">${j.clubs.map(c=>`<div style="display:flex;gap:8px;padding:6px 8px;border-radius:8px;background:var(--panel2);font-size:11px"><b style="flex:1">${esc(c.name)}</b><span>${fmtDate(c.from).split(",")[0]}</span><span>${c.to?fmtDate(c.to).split(",")[0]:"—"}</span><span class="small muted">${esc(c.reason||"")}</span></div>`).join("")}</div>${j.unemployed?`<button class="btn primary sm" style="margin-top:8px" onclick="go('jobs')">Find job</button>`:""}</div><div class="card"><h3>Trophy room</h3><div style="margin-top:8px;display:grid;gap:6px">${j.trophies.length?j.trophies.map(t=>`<div style="padding:8px;border-radius:10px;background:linear-gradient(135deg,#2a1e0a,#1e1608);border:1px solid #5a4222"><div style="color:var(--gold);font-weight:900;font-size:12px"> ${esc(t.comp)}</div><div class="small muted" style="font-size:10px">${t.season}/${String(t.season+1).slice(2)} · ${esc(t.type||"")}</div></div>`).join(""):'<p class="small muted">No trophies yet</p>'}</div></div></div> <div class="card" style="margin-top:8px"><h3>Season record</h3><div style="margin-top:8px;max-height:40vh;overflow:auto;display:grid;gap:3px">${j.history.map(h=>`<div style="display:grid;grid-template-columns:40px 1fr 1fr 32px 1fr;gap:6px;padding:6px 8px;border-radius:8px;background:var(--panel2);font-size:10px"><span style="font-family:var(--ff-mono)">${h.season}</span><span>${esc(h.comp||"")}</span><span>${esc(h.club||"")}</span><span>${h.pos||""}</span><span>${esc(h.note||"")} ${h.trophy?'':""}</span></div>`).join("")||'<div class="small muted">No history</div>'}</div></div> <div class="card" style="margin-top:8px"><h3>Saved games</h3><p class="small muted" style="font-size:11px">Three slots. Switch career, export a backup file, or restore one.</p><button class="btn sm" style="margin-top:8px" onclick="openSaves()">Manage saves</button></div> <div class="card" style="margin-top:8px;border-color:rgba(255,59,74,.18);background:#2a1218"><h3 style="color:#ff8a94">Danger zone</h3><p class="small muted" style="font-size:11px">New career rebuilds world and deletes save — in this slot only</p><button class="btn danger sm" style="margin-top:8px" onclick="confirmNewCareer()">Start new career</button></div>`;
}
function confirmNewCareer(){ modal(`<h2>Start new career?</h2><p class="small muted">Current career — every season, trophy, record — will be permanently deleted. World rebuilt from scratch.</p><div style="display:flex;gap:8px;margin-top:12px"><button class="btn danger" onclick="doResetCareer()">Yes, erase</button><button class="btn" onclick="closeModal()">Cancel</button></div>`); }
async function doResetCareer(){ closeModal(); setBusy(true); try{ await api.post("/api/career/reset",{}); G.home=null; G.boot.has_save=false; G.pendingMatch=false; $("#crest").textContent="TL"; showStartScreen(); toast("Save erased"); } catch(e){ toast("Reset failed: "+esc(e.message),6000); } setBusy(false); }
async function renderJobs(){
  const j=await api.get("/api/career/jobs"); await refreshState();
  $("#content").innerHTML=`
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px"><b style="font-size:13px"> JOB MARKET</b><span class="small muted">Unemployed</span></div> <p class="small muted" style="font-size:11px">Offers in inbox, or apply — reputation decides</p> ${j.offers.length?`<div class="card" style="margin:10px 0;border-color:rgba(44,255,138,.18);background:linear-gradient(135deg,#0a2a18,#0f2a1c)"><h3>Offers received</h3><div style="display:grid;gap:6px;margin-top:8px">${j.offers.map(o=>`<div style="display:flex;gap:10px;align-items:center;padding:8px;border-radius:10px;background:var(--panel)"><div style="flex:1"><b style="font-size:12px">${esc(o.name)}</b><div class="small muted" style="font-size:10px">${esc(o.league)} · tier ${o.tier} · rep ${Math.round(o.rep)}</div></div><button class="btn primary sm" onclick="acceptJob(${o.club_id})">Accept</button></div>`).join("")}</div></div>`:""}
    <div style="display:grid;gap:6px;margin-top:10px">${j.jobs.map(v=>`<div style="display:flex;gap:10px;align-items:center;padding:10px;border-radius:12px;background:var(--panel);border:1px solid var(--line)"><span class="tag">T${v.tier}</span><div style="flex:1"><b style="font-size:12px">${esc(v.name)}</b><div class="small muted" style="font-size:10px">${esc(v.league)} · rep ${Math.round(v.rep)} · ${money(v.season_income||0)}/yr</div></div><span class="tag ${v.interest==="high"?"W":v.interest==="medium"?"D":"L"}">${esc(v.interest)}</span><b style="font-size:11px">${Math.round(v.chance*100)}%</b><button class="btn sm" onclick="acceptJob(${v.id})">Apply</button></div>`).join("")||'<p class="small muted" style="padding:12px">No vacancies</p>'}</div><div style="margin-top:12px"><button class="btn primary" onclick="doContinue()">Advance time ▶</button></div>`;
}
async function acceptJob(clubId){ const r=await api.post("/api/career/apply",{club_id:clubId}); toast(esc(r.msg||(r.ok?"Appointed!":"Rejected")),5000); if(r.ok){ await refreshState(); go("home"); } }
document.addEventListener("keydown", e=>{ if(e.key==="Escape") closeModal(); if(e.key===" " && !$("#modal").classList.contains("open") && !["INPUT","SELECT","TEXTAREA"].includes(document.activeElement.tagName)){ e.preventDefault(); doContinue(); } });
boot();

/* GAME SHELL — icons, tabbar, sheet, tables */
const TAB_IDS=["home","squad","match","stats"];
const TAB_LABEL={home:"Home",squad:"Squad",match:"Match",stats:"Stats",inbox:"News",comps:"Cups",transfers:"Transfers"};
function renderTabbar(items){
  const el=$("#tabbar"); if(!el) return; const tabs=TAB_IDS.map(id=>items.find(i=>i[0]===id)).filter(Boolean);
  el.innerHTML=`<div class="dock">${tabs.map(n=>`<button data-s="${n[0]}" onclick="Juice.haptic('tap');go('${n[0]}')"><span>${TAB_LABEL[n[0]]||n[2]}</span><span class="tbadge hidden" data-badge="${n[0]}"></span></button>`).join("")+`<button data-s="__more" onclick="Juice.haptic('tap');openSheet()"><span>More</span><span class="tbadge hidden" data-badge="__more"></span></button>`}</div>`;
}
function renderSheet(items){
  const el=$("#sheet-grid"); if(!el) return;
  const have=new Set(items.map(i=>i[0])); have.add("inbox"); have.add("board"); have.add("media"); have.add("career"); have.add("staff"); have.add("youth"); have.add("facilities");
  el.innerHTML=MENU_GROUPS.map(g=>{
    const rows=g.items.filter(([id])=>have.has(id)).map(([id,label,desc])=> `<button class="menu-item" data-s="${id}" onclick="Juice.haptic('tap');go('${id}')"><span class="mi-t">${label}<small>${desc}</small></span><span class="mi-go">›</span><span class="tbadge hidden" data-badge="${id}"></span></button>`).join("");
    return `<div class="sheet-group"><h4>${g.label}</h4>${rows}</div>`;
  }).join("");
  const sheet=$("#sheet"); if(sheet&&!sheet.querySelector("#sheet-panel #sheet-grid")){ const inner=sheet.innerHTML; sheet.innerHTML=`<div id="sheet-panel"><div id="sheet-head"><h2>All sections</h2><button class="btn sm" onclick="closeSheet()">Close</button></div><div id="sheet-grid">${inner}</div></div>`; sheet.addEventListener("click",e=>{ if(e.target.id==="sheet") closeSheet(); }); }
}
function openSheet(){ Juice.haptic("light"); const s=$("#sheet"); if(!s) return; if(!s.querySelector("#sheet-panel")) renderSheet(NAV); s.classList.add("open"); requestAnimationFrame(()=>s.classList.add("vis")); }
function closeSheet(){ const s=$("#sheet"); if(!s||!s.classList.contains("open")) return; s.classList.remove("vis"); setTimeout(()=>s.classList.remove("open"),260); }

/* crests */
const CREST={
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
let CREST_N=0, REAL_CRESTS={}, REAL_COMPS={};
function compLogo(code,cls){ const u=REAL_COMPS[code||""]; if(u) return `<img class="comp-logo${cls?" "+cls:""}" src="${u}" alt="" loading="lazy">`; return `<span class="ci" style="width:22px;height:22px;border-radius:6px;display:grid;place-items:center;background:color-mix(in srgb, ${compColor(code)} 20%, #05070d);color:${compColor(code)};font-weight:900;font-size:10px">${esc(compMono(code))}</span>`; }
function crest(code,cls){ const u=REAL_CRESTS[code||""]; if(u) return `<img class="crest${cls?" "+cls:""}" src="${u}" alt="" loading="lazy" onerror="this.outerHTML=crestSVG('${code}','${cls||''}')">`; return crestSVG(code,cls); }
function crestSVG(code,cls){
  code=code||""; const c=CREST[code]; let c1,c2,pat,txt=""; if(c){ c1=c[0]; c2=c[1]; pat=c[2]; } else { let h=7; for(const ch of code||"?") h=(h*31+ch.charCodeAt(0))>>>0; const hue=h%360; c1="hsl("+hue+" 45% 34%)"; c2="hsl("+((hue+40)%360)+" 60% 66%)"; pat="plain"; txt=(code||"?").slice(0,2); }
  const id="cr"+(CREST_N++), sh="M20 2 L36 8 V20 C36 30 29 36 20 38 C11 36 4 30 4 20 V8 Z"; let inner="";
  if(pat==="stripes") inner='<rect x="8" y="0" width="4.6" height="40" fill="'+c2+'"/><rect x="17.2" y="0" width="4.6" height="40" fill="'+c2+'"/><rect x="26.4" y="0" width="4.6" height="40" fill="'+c2+'"/>';
  else if(pat==="hoops") inner='<rect x="0" y="9" width="40" height="5" fill="'+c2+'"/><rect x="0" y="19" width="40" height="5" fill="'+c2+'"/><rect x="0" y="29" width="40" height="5" fill="'+c2+'"/>';
  else if(pat==="halves") inner='<rect x="20" y="0" width="20" height="40" fill="'+c2+'"/>';
  else if(pat==="sash") inner='<path d="M0 30 L40 6 L40 16 L0 40 Z" fill="'+c2+'"/>';
  else inner='<path d="M4 8 H36 V14 H4 Z" fill="'+c2+'"/>';
  const t=txt?'<text x="20" y="26" text-anchor="middle" font-size="12" font-weight="800" fill="'+c2+'" font-family="Arial,sans-serif">'+txt+'</text>':"";
  return '<svg class="crest '+(cls||"")+'" viewBox="0 0 40 40" aria-hidden="true"><defs><clipPath id="'+id+'"><path d="'+sh+'"/></clipPath></defs><path d="'+sh+'" fill="'+c1+'"/><g clip-path="url(#'+id+')">'+inner+'</g><path d="'+sh+'" fill="none" stroke="rgba(255,255,255,.25)" stroke-width="1.2"/>'+t+'</svg>';
}
function paintCrest(code){ const el=$("#crest"); if(!el) return; el.innerHTML=crest(code||"TL"); }
function polish(root){
  root=root||document;
  // Kill all remaining browser tables on mobile — convert to game cards
  const tables=$$("table",root);
  if(window.innerWidth>=900){ tables.forEach(t=>{ if(!t.closest(".tw")){ const w=document.createElement("div"); w.className="tw"; t.replaceWith(w); w.appendChild(t); } }); return; }
  tables.forEach(t=>{
    if(t.closest(".tw")) return;
    if(t.querySelector("tbody[id]")){ const w=document.createElement("div"); w.className="tw"; t.replaceWith(w); w.appendChild(t); return; }
    if(t.classList.contains("mc")){ const w=document.createElement("div"); w.className="tw"; t.replaceWith(w); w.appendChild(t); return; }
    const cols=t.querySelectorAll("thead th").length;
    if(cols>=4){
      const heads=[...t.querySelectorAll("thead th")].map(th=>th.textContent.trim()), rows=[...t.querySelectorAll("tbody tr")];
      if(!rows.length){ const w=document.createElement("div"); w.className="tw"; t.replaceWith(w); w.appendChild(t); return; }
      const host=document.createElement("div"); host.className="cards";
      rows.forEach(tr=>{
        if(tr.children.length<=1){ const d=document.createElement("div"); d.className="tmsg"; d.innerHTML=tr.innerHTML; host.appendChild(d); return; }
        const cells=[...tr.children], card=document.createElement("div"); card.className="tcard"+(tr.classList.contains("me")?" me":""); const oc=tr.getAttribute("onclick"); if(oc){ card.setAttribute("onclick",oc); }
        let ti=cells.findIndex(td=>!td.classList.contains("num")&&td.textContent.trim()&&td.querySelector("b,strong")); if(ti<0) ti=cells.findIndex(td=>!td.classList.contains("num")&&td.textContent.trim().length>6); if(ti<0) ti=0;
        const hd=document.createElement("div"); hd.style.fontWeight="900"; hd.style.fontSize="12px"; hd.style.marginBottom="6px"; hd.innerHTML=cells[ti].innerHTML; card.appendChild(hd);
        const grid=document.createElement("div"); grid.style.display="grid"; grid.style.gridTemplateColumns="1fr 1fr"; grid.style.gap="6px";
        cells.forEach((td,i)=>{ if(i===ti) return; if(!td.textContent.trim()&&!td.querySelector(".bar,.tag")) return; const c=document.createElement("div"); c.style.display="flex"; c.style.justifyContent="space-between"; c.style.fontSize="11px"; c.innerHTML=`<span style="color:var(--tx3)">${esc(heads[i]||"")}</span><span style="font-weight:800">${td.innerHTML}</span>`; grid.appendChild(c); });
        card.appendChild(grid); host.appendChild(card);
      });
      t.replaceWith(host);
    } else { const w=document.createElement("div"); w.className="tw"; t.replaceWith(w); w.appendChild(t); }
  });
}
