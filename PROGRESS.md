# TOUCHLINE — 7-HOUR SPRINT PROGRESS

- **Start:** 2026-09-09 23:27 UTC
- **Target end:** 2026-09-10 06:27 UTC (420 min)
- **Baseline:** v1.5.0 @ commit 9b31797 (real squads, Godfather Mode, inbox rows, game-feel motion)
- **Rule:** inspect → improve → test → review → fix → commit → push → continue

## Phase plan
| # | Phase | Est | Status |
|---|-------|-----|--------|
| 0 | Inspect + baseline shots | 20m | DONE |
| 1 | Design tokens + CSS system rewrite + nav restructure | 60m | … |
| 2 | Club crest/badge system (procedural SVG, real colours) | 60m | … |
| 3 | Dashboard = command centre redesign | 45m | … |
| 4 | Matchday: pre-match hero, live presentation, event graphics, HT/FT | 75m | … |
| 5 | Competition identities (UCL/PL/etc) + comp hub + brackets | 60m | … |
| 6 | Player profile + squad screen depth | 45m | … |
| 7 | Gameplay: tactics effect check, transfer AI needs, event news | 45m | … |
| 8 | Performance + mobile UX pass | 30m | … |
| 9 | Regression: season sim, player flows, screenshots | 30m | … |
| 10 | FINAL HOUR: freeze, test, APK 1.6.0, release, report | 30m | … |

## Completed work
- (v1.5.0 shipped before sprint: 96 real squads, real managers, Godfather Mode, inbox rows)

## Current task
Phase 0 → 1: inspect UI code, then design-system rewrite.

## Bugs / regressions
- none open

## Next priority
Design tokens in style.css; nav restructure (bottom bar: Home/Squad/Tactics/Match/More + bell inbox).

## Update 2026-09-10 ~00:40 UTC
- Phase 1 DONE: style.css rewritten as token design system (all legacy classes kept + aliases).
- Phase 2 DONE: procedural crest system (crest(code)) w/ real colours for 96+ clubs, fallback initials; wired topbar/home/table/matchday. engine.table + view._fixture_brief now carry club codes.
- Phase 3 DONE: dashboard = command centre (match hero, status strip, readiness/board, mini table+inbox).
- Phase 4 DONE: matchday premium: pre-match hero (comp band/crests/form/venue/XI/bench), animated live clock w/ event feed + skip, HT (stats duo, incidents, talk, subs), FT full-screen (score hero, MOTM, stats, events, player ratings, aftermath).
- Bugs fixed: stroke icons, topbar <small>, g2 mobile stacking, HT/FT stat key aliases (poss/possession).
- Next: Phase 5 competition identities + hubs.

## Update ~00:15 UTC
- Phases 5-8 DONE: comp hubs+identities, club hub, nav restructure (Dashboard/Squad/Tactics/Matches/Comps tabs + More sheet), profile redesign (avatar/strip/attr bars/recent perfs), squad overview+compact list, tactics effect notes, transfers/training/career/finances rebuilds, global input/select styling, tcard label fix.
- Audits: 16 screens @393px zero JS errors zero h-overflow; season_test passed post engine changes.
- Next: APK dry-run, desktop pass, inbox detail polish, final regression, then final-hour APK v1.6.0 code 8 + release.

## Update ~00:15-00:20 UTC
- Start screen redesigned (shield logo, wordmark, stat strip, feature cards).
- Tactics pitch CSS restored + slot spacing tuned; mentality effect notes live.
- Transfers/training/career/finances heads+strips; global input/select/a styling; tcard labels fixed.
- Goal event graphics now carry running score chips; shot commentary humanised.
- APK v1.6.0 versionCode 8 dry-run BUILT+SIGNED+VERIFIED (assets include new app.js).
- Next: final regression sweep, hold, final-hour rebuild+release+report.

## Update ~00:30 UTC
- Calendar rebuilt as fixture rows (crests/score/result tags/next highlight).
- Table zone cues (blue promo / red relegation inset) on league + hub tables.
- Status chips tappable (budget→finances, board→board, next→match, club→club hub).
- Squad live name filter.
- tests/multiseason.py: TWO-SEASON proof passed (trophies 26 La Liga; 27 Copa+La Liga; ageing/rep/finances carry).
- Remaining hold cycles: godfather-on visual, key-mode HT, desktop inbox; final hour 05:27 freeze→APK→release→report.

## Incident ~00:18 UTC (resolved)
- A range-based edit (staff/youth commit 950d768) used an end-anchor that sat BEFORE its start anchor, duplicating then deleting renderCalendar/renderTable/renderComps/renderCompHub/renderClub. Detected via missing-function grep; restored verbatim from commit 292ccce; audit2 re-run clean; pushed.
- GUARD ADDED: tests/ui_sanity.js fails if any go() screen lacks a definition, any onclick handler is undefined, or key CSS hooks vanish. Run before every commit from now on.

## Update ~02:30 UTC (hold cycle 3)
- Six-matchday API playthrough (now Oct 30): La Liga table live (RMA 1st, 28pts), world clubs diverge; dashboard/media/calendar verified mid-season; CONTINUE stress avg 118ms, save 3KB.
- README gained "What changed in 1.6" section + APK link bump (v1.6.0 tag).
- Harness lesson: pass screen names verbatim to go(); 'name'.split('-')[1] yielded undefined → "Loading..." false alarm.
- Pushed: README + mh commits.

## Update ~03:40 UTC (hold cycles 4-6)
- REGRESSION FIXED: audit2 16/16 screens clean @393 (was tactics/training/transfers overflow). Causes: select intrinsic min-width in fr tracks (global `select{min-width:0}` + `.grid>*{min-width:0}`), `.kv span{flex:none}` blocking shrink (phone override), negotiation action row now own line.
- INCIDENT (00:18) fully closed: restored renderCalendar/Table/Comps/CompHub/Club from 292ccce; ui_sanity guard prevents recurrence; league/hub tables now stay tables on phones (.mc/.mh/.mp column sets).
- NEW-CAREER FLOW tested end-to-end in UI: splash -> search/pick club (rich club card) -> manager name -> onboarding checklist (step-list CSS was missing, fixed) -> dashboard w/ explainer card. Arsenal career now live in dev server.
- Tablet 768 pass: pitch/bench stack below 980px (label collisions fixed).
- Pushed: overflow fixes + step-list.

## Update ~04:15 UTC (pre-freeze)
- New-career Arsenal flow verified: splash, club search/pick card, onboarding checklist (step-list CSS added), dashboard explainer, friendly FT graphic (MOTM/stats/events), HT team-talk screen.
- Live/HT scoreboard names now wrap instead of truncating ("Nottingham Forest").
- Engine 1-season test PASSED (temp DB): finances/inbox/progression sane.
- audit2 16/16 clean; ui_sanity green; make_apk.sh re-stages fm/ + static at build time (final build will include everything).
- FREEZE 05:27: no more feature edits; final regression -> APK -> release -> report.

## FINAL HOUR (05:27-06:27 UTC)
- Freeze regression: node --check, ui_sanity (20 screens/43 handlers/12 css hooks), audit2 16/16 clean @393px, zero page errors; engine 1-season test passed earlier; two-season proof stands (tests/multiseason.py).
- P0 FIXED at 05:20: reopening a match paused at half-time after reload showed a dead screen (halftime state was client-memory only). Added HT recovery card ("Send them back out" no-changes resume / "Auto-finish") + guarded full-mode second-half render. Verified: pending clears, second half completes.
- APK REBUILT 05:24: release/Touchline-1.6.0-arm64.apk, 14 MB (14,265,227 B), versionCode 8 / 1.6.0, arm64-v8a, apksigner-verified; packaged assets confirmed to contain today's fixes (HT recovery card, step-list, restored hub funcs).
- Workspace build caches removed (android/app/build, staged fm copies, local.properties).
- GITHUB RELEASE v1.6.0 published with APK attached; release is repo latest.
  Release: https://github.com/t7myz6f54s-afk/Football-manager/releases/tag/v1.6.0
  APK:     https://github.com/t7myz6f54s-afk/Football-manager/releases/download/v1.6.0/Touchline-1.6.0-arm64.apk
- README APK link already points at v1.6.0 tag.

## SPRINT END STATE
All P0/P1 closed; 16/16 screens clean at 393px; tablet + desktop passes clean; new-career,
matchday (full/key/instant), HT resume, transfers, season progression and world simulation
verified in-browser; repo pushed; release shipped.

## Post-sprint update (user feedback round) — v1.6.1
- REAL BADGES: 94/96 big-five clubs mapped to actual crests (Wikimedia thumbs, verified 200+image,
  filename-curated to reject stadium photos / maps / constituency arms); fm/static/crests.json;
  crest() wraps crestSVG() with <img onerror=fallback>; unified light badge plate for dark crests.
  LEC + VER keep procedural shields (non-free, no commons asset).
- GODFATHER: engine.godfather_plan() — best XI by slot fit/CA/availability, per-opponent mentality
  + instruction plan with reasoning (strength diff of best-XI CA), 3 affordable sign targets w/ need
  reasoning; /api/advice returns plan; dashboard card gains Select-XI / Apply-plan / Bid buttons.
- NO SWIPE: phone league tables form→dots + tighter cells (table 363px = container); stat strips
  3-col grid; inbox tabs wrap. audit2: 16/16 screens, zero overflow, zero page errors.
- MATCHDAY: goal flash overlay (crest/scorer/minute/score), club-colour live bar tint, FT diagonal
  club-colour split; app-feel CSS (overscroll, tap-highlight, select-none, transitions, safe areas).
- APK 1.6.1 (code 9) rebuilt after /usr/local wipe (JDK17+gradle8.9+SDK34 reinstalled); signed,
  crests.json(94)+godPlan verified inside assets; release v1.6.1 published w/ APK.

## v1.10.0 hotfix — takeover session (2026-09-10)
- P0 FIXED: v1.9.0 shipped a broken app.js (syntax error, line 762 renderTabbar template literal — missing closing backtick+brace). Entire JS file failed to parse in WebView → app stuck on splash forever. Confirmed inside the released APK. One-line fix; file now parses 100%.
- P0 FIXED: engine.py would_sell() crashed on sqlite3.Row .get() (transfer market day) — killed CONTINUE during windows. Row-safe access now.
- P0 FIXED: engine.py player_willing() crashed the same way on loyalty/ambition — killed every accepted transfer bid path.
- ui_sanity: stale CSS hooks (.stf-k, .zdot) replaced with hooks the ULTRA UI actually uses; guard green (20 screens / 44 handlers / 11 hooks).
- Verification: smoke PASS, season_test (WXC, 1 season) PASS, headless-browser boot test PASS (splash→launcher→career→6 screens→CONTINUE→transfer bid; zero console errors).
- v1.10.0 (versionCode 13), make_apk.sh now emits a single correctly-named APK (was copying one APK under two version names).
- android/setup_toolchain.sh added: one-shot JDK17+Gradle 8.9+SDK34 installer for reproducible builds on any fresh machine.

## v1.11.0 — FEATURE #1: Match Day Live+ (2026-09-10)
- Live stepping: server simulates in chunks (live_step API); first half is no longer pre-computed before the UI shows it.
- Momentum bar from a real per-minute pressure log (progressions + 2.5·xG), 12-min sliding window.
- Touchline orders (all_out_attack / sit_deep / press_hard / time_waste / go_long / calm_down): mutate the live tactical model; max 3 + 10' cooldown + context rules; chance rates now computed live each minute (was cached at kickoff — orders could not affect volume before this change).
- Live subs (5 total incl. HT 3). Match recovery after restart (/api/match/live_state + boot pending_phase).
- Tests: tests/live_match_test.py (black-box API, end-to-end PASS), tests/order_effect_test.py (paired-seed statistical proof: +0.71 shots / +0.12 xG for ALL-OUT ATTACK, PASS), browser walkthrough (live HUD → HT → mid-half order → FT, zero errors, PASS), smoke + season PASS.

## v1.12.0 — FEATURE #2: Stats Center + declutter pass (2026-09-10)
- Stats Center (/api/screen/stats + tab): golden boot w/ bars, assists, clean sheets, xG-vs-actual league table (aggregated from fixture reports, over/under-performance deltas), squad leaders, form guide. clubs.league is a CODE — resolve comps by code (bug fixed during build).
- Declutter: 108 emoji stripped from UI chrome and headings; nav = Home/Squad/Match/Stats + grouped More (Club/Market/World/Office with descriptions); launcher cleaned (no float/bubble/badges); home gauges → compact season strip; marketing strips removed; flat primary buttons; fixed broken \U escape that rendered "U0001F501 SUB" in the live HUD.
- Browser walkthrough extended (stats + grouped menu assertions): all green, zero console errors. smoke PASS.

## v1.13.0 — FEATURE #3: Save Slots & Backup (2026-09-10)
- fm/slots.py: slot registry + paths (slot1 honours legacy FM_DB/FM_SAVE; slots 2-3 under base/slots/), legacy one-time migration, meta summaries.
- Slot-aware app.py: boot init, commit/persist, career new/load/reset; world.DB_PATH repointed per slot; switching refused while a match is paused.
- API: GET /api/slots, POST /api/slots/switch (auto-materialises empty slots), /api/slots/delete, GET /api/slots/export (zip, WAL-checkpointed, Content-Disposition), POST /api/slots/import (zip base64 → free slot, validated).
- mini.py: Binary response passthrough for raw downloads.
- UI: slot strip on launcher, Saves manager modal (switch/delete/export/import), Career screen entry, TLAndroid JS bridge hooks.
- Android: bootstrap → FM_DATA model (auto-migrates old installs); MainActivity bridge — export via share sheet (FileProvider), import via system file picker; androidx.core dep + manifest provider.
- Tests: tests/slots_test.py — 3 careers isolated, switching returns right world every time, export→delete→import→identical state: ALL PASS. Browser walkthrough extended (saves modal, switch both ways, back in-game verified via MATCH CENTRE): all green, zero errors. live_match + smoke PASS.

## v1.13.1 — MATCHDAY SPEED + WORKFLOW RESTRUCTURE (2026-09-11)

**Task:** stop the heavy-in-workspace build loop; make the game itself run smoothly.

**Environment reality check:** no separate 20 GB-RAM environment exists here — the "20 GB"
is this box's free disk (1.9 GB RAM, 2 vCPUs). Workflow restructured around that:
- 3 GB swapfile added (`/swapfile`) → OOM kills during build peaks are gone (the old
  kill-Java/rebuild loop was the symptom; this is the fix)
- `android/gradle.properties`: build cache ON (disk-backed), workers.max=1, 900m heap,
  daemon OFF (memory returns after each build) — warm rebuilds reuse .so/dex/aapt outputs
- `setup_toolchain.sh` fresh-machine bug fixed: JAVA_HOME export happened BEFORE the JDK
  download, so sdkmanager ran on Java 11 and died (class file 61 vs 55); export moved
  after the install
- full phase map + rationale in **WORKFLOW.md**

**In-game lag — found and fixed (no rewrites, no UI changes):**
- Profiling: `tests/perf_probe.py` (real HTTP, temp DB) + cProfile on `tick_day`.
  Live match steps: 8 ms p50 (fine). Screen payloads: 1–8 ms (fine). The clunk = the
  matchday CONTINUE tick: 350–420 ms desktop / ~1.2–2 s on a mid-range phone.
- Causes: (1) global `bump()` at end of every tick_day invalidated all 430 clubs'
  cached squads+strengths daily even though each club plays once a week; (2) goal
  distribution re-SELECTed each scoring team's squad and re-parsed attrs per goal
  (23,794 unpacks/matchday); (3) `unpack_attrs` re-parsed the same strings; (4)
  redundant best-XI re-sorts; (5) `complete_transfer` (called ~3×/day by world transfer
  activity) did a global cache bust.
- Fixes: per-club structural content hash (ca/pos/squad/condition) verified with ONE
  batched query per matchday — catches every structural mutation by construction
  (no invalidation call sites to audit); goal distribution reuses cached squad rows with
  precomputed weight vectors (RNG call sequence byte-identical); unpack memoized
  (fresh dict per call = mutation-safe); targeted `bump_clubs()` for transfers/releases;
  daily global bump removed. Fatigue/fitness drift deliberately excluded from the hash
  (<1% shift in AI expected goals, below Poisson noise — documented in WORKFLOW.md).
- Result: warm matchday tick 350–420 ms → 100–129 ms; cold ~350 ms; 3-season run
  283 s → 250 s; league goal-rates drift ≤ ±0.08/match; ALL tests pass (season_test 3
  seasons, smoke, live_match e2e, order_effect statistical, ui_sanity 21/52/17).
- `tests/perf_probe.py` added to the repo for future regressions.

## v1.14.0–v1.16.0 — recap (shipped 2026-09-10/11, changelog here for completeness)
- v1.14.0 (+1.14.1): FEATURE #1 Facilities — stadium/training/youth-akaademi levels, cash + balance cost model, condition/training/development effects, UI screen.
- v1.15.0: FEATURE #2 Staff management — hire/sack/renew coaching staff, wages, effects on training/condition/pressing, board reactions.
- v1.16.0: FEATURE #3 Transfer market — AI approaches to listed players (FIFA/EA-style accept/counter), incoming-bid inbox, outgoing offers with budget checks, market-day world transfer activity.

## v1.17.0 — FINAL GAMEPLAY INTELLIGENCE + FOOTBALL-WORLD SIMULATION UPDATE (2026-09-11)
Single approved 19-item batch. All items verified in the playable build before shipping.

### 1. Global calendar (one world, many competitions)
- 23 leagues / 444 clubs in the world (was 21/402): +24 MLS, +18 Saudi Pro League, with
  real club names, nationalities, brand multipliers (world.py GLOBAL_BRAND) and positional squads.
- Season lifecycle is competition-aware: the season now rolls over only AFTER the last
  fixture in the world (UCL final 29 May, leagues end 8 May) — backstop `date(season+1, 7, 5)`;
  every competition ends with its final played (no orphaned fixtures), comp_state tracks KO stages.
- `tests/competition_test.py`: 11/11 (lifecycle, double-header ordering, cup finals, KO ranks).

### 2–5. Persistent stats, Golden Boot, Ballon d'Or, permanent records
- New tables: season_player_stats (per competition, apps/starts/goals/assists/mins/clean sheets/
  rating), career_player_stats (per season totals, permanent), awards (permanent, never overwritten).
- Written on every simulated match — AI and player — via the existing match-report path.
- Season end: Golden Boot per competition (top scorer, real numbers in detail) + Ballon d'Or
  (weighted goals/assists/rating formula).
- New **History** screen ("Seasons & records", grouped nav → World): completed-season list
  (seasons stay browsable forever), per-season champions, promotion/relegation, awards, my club's
  final league positions. Player card shows the permanent career record (per-season table) and
  career awards.
- Full-season probe on the new 23-league world: 9,294 season rows / 6,158 career rows /
  40 awards / 16 comp_state rows; MCI rows split PL/UCL/FA Cup correctly.

### 6. US + Saudi transfer eligibility (logic level, not UI)
- MLS (24) + Saudi Pro (18) clubs get real club_ids, brand multipliers and appear in every
  market path: search, offers (negotiate/accept — price-based, not blocked), buyer pool for
  listed players, career starts. Database audited: no other league accidentally excluded.

### 7–16. Godfather Mode — decisive football-intelligence system (existing toggle kept)
`godfather_plan` rewritten as a VERDICT object (one decisive line that answers the current
priority: matchday → market → contracts → depth → season), all data-driven from actual state:
- **Best XI**: 11 picks with per-pick reasons ("beats X by n", "only fit option", "in form");
  one-tap selection into the tactics screen (selected XI persisted in save flags, used by match sim).
- **Tactics vs opponent**: mentality/instructions/formation chosen from CA differential,
  opponent's stored mentality+instructions, home/away — each instruction carries a why.
- **Transfer intelligence**: targets with real fees/wages + one-click bids; explicitly REJECTS
  famous players when the arithmetic says so (over budget, fee ≥60% of budget, wage >25% of wage
  headroom, or a cheaper same-position fit covers the slot — names both players + prices).
  Verified: Haaland rejected for MIA (€30.5m vs €16.1m Thuram, same slot) and SBA (entire budget);
  Haaland pursued for RMA (€99.8m budget).
- **Squad building**: depth gaps per position group, contracts expiring within a season,
  overpaid-low-CA sell candidates, high-potential youth to develop (PA ≥ CA+1.2).
- **Fixture management**: next 5 fixtures with congestion verdict (rotation advice when ≥3 league
  games in ≤8 days across competitions).
- **Financial intelligence**: budget, wage headroom, projected spend and why-lines.
- **Pre-match** (`/api/match/next` preview.godfather): plan vs the actual opponent, threats
  (top 3 by CA + season scoring), selected-XI quality check vs best fit.
- **Live guidance** (`live_guidance` → `/api/match/live_step` → `#lv-god` banner):
  priority-ordered rules on score/xG/fatigue/momentum/minute — time_waste, all_out_attack,
  press_high, sit_deep, patience — with a one-line reason and a concrete sub hint
  (tired XI player → same-position bench player, named). "DO IT ▶" button sends the order
  through the normal instruction API. Verified in a real live match (0-2 at m60 →
  all_out_attack applied mid-game).

### 17–19. React-to-state, preservation, testing
- No hardcoded advice: every verdict line, why, target and reject is computed from DB state
  (squad, contracts, finances, fixtures, opponent DB rows, market DB).
- No existing feature, data, screen, graphic or save path removed; Godfather toggle unchanged.
- 9-scenario verification matrix (all PASS in the playable build):
  1. Global calendar lifecycle (competition_test 11/11)  2. per-competition persistent stats
  3. Golden Boot + Ballon d'Or  4. History screen permanence  5. player permanent career
  6. MLS/Saudi transfer eligibility  7. Godfather verdict + rejects  8. Godfather live guidance
     in a real live match  9. regression sweep (19 API screens, transfers, tactics, save, nav,
     toggle round-trip, instant match, version/wiring).

## v1.18.0 — Premium Trophy Room + Smart Simulation (2026-09-11)
Two systems, added on top of v1.17.0 (nothing previously shipped was removed).

### Premium Trophy Room (3D club museum)
- Real 3D environment built with Three.js (r128, bundled locally — no network needed,
  works offline in the APK): polished reflective floor, dark museum walls, gilded cove
  lighting, IBL studio environment for metallic reflections, dust-in-the-light particles,
  slow camera drift + full drag/pinch/wheel orbit.
- Trophies are procedurally modelled per competition with recognisable designs:
  UCL "Big Ears" (large ear handles), Premier League (gold cup, black lid + lion),
  FA Cup profile, UEL/UECL with competition-colour ribbons, top-flight league cups
  (gold + star), domestic cups with country accent ribbons. Silver/gold PBR materials.
- Each win gets a pedestal + glass display case + engraved nameplate (competition,
  ×N, years). Most recent win is the hero pedestal; new wins animate in with a glow.
- Competition result → trophy → history record: source of truth is the permanent
  `history` table (cup finals + league champions), enriched with the manager's career
  list ("won under you" + manager name). Multiple wins preserved (year list on plate
  and detail panel). Details only from data that exists: final opponent + score +
  date + venue (cups/continental), final season record (leagues).
- Per-save rooms (filter by club), previous trophies never disappear, new career =
  own room. Won a final → "TROPHY ROOM — IT'S YOURS" button on the full-time screen.
- Performance: lazy-loads three.min.js + trophy.js only on first open, shared
  geometry/materials, capped pixel ratio, render loop paused when the tab is hidden,
  full dispose on screen exit. No WebGL → elegant 2D "shelf" fallback (tested in jsdom).

### Smart Simulation ("take me there")
- New SIM control bar on the home screen: 1D / 7D / NEXT EVENT / NEXT MATCH /
  NEXT COMP / SEASON END / NEXT SEASON (existing Continue untouched).
- Engine `fast_sim`: one HTTP call = one bounded chunk (≤14 in-game days) so the UI
  never freezes; the client loops with a live progress overlay (date ticker, progress
  bar, scrolling event log, STOP button).
- Intelligent stopping (item: "do not skip important events"):
  * NEXT EVENT — stops at the next own match or any urgent news
  * NEXT MATCH — stops the day before the next own match (any competition)
  * NEXT COMP — auto-plays league on the way; stops at the next own cup/continental
    match (league-only clubs: next league match)
  * SEASON END — auto-plays everything (instant mode) to the season rollover
  * NEXT SEASON — auto-plays league only; stops at own cup/continental matches,
    actionable urgent news (incoming bids, board decisions); pure-news urgents and
    injuries are auto-processed; otherwise fast-forwards the whole offseason to the
    new season in one button
- Auto-played results appear as one-line log entries (W 2-1 v X — Premier League)
  and are recorded normally (tables, stats, history, finances).
- Verified: MCI 2026/27+2027/28 via the API — 87 chunks, worst chunk 13.7 s (UCL
  knockout week), 26 cup/continental stops, both rollovers clean; 4 trophies
  (UCL×2, PL×2, EFL Cup) with full final details in /api/trophies.

### Regression
competition_test 11/11, smoke, ui_sanity (24 screens / 61 handlers), node --check
on app.js + trophy.js + three.min.js, jsdom 2D fallback test, asset serving check.

## v1.18.1 — Hotfix: matches stuck on old saves + Trophy Room lock (2026-09-11)
Bug reported from device (v1.18.0): live matches got stuck near full-time with
"Match feed lost", and the Trophy Room was inaccessible / looked empty.

### Root cause (reproduced exactly in the sandbox)
- v1.17.0 added the per-competition stats tables (`season_player_stats`,
  `career_player_stats`, `awards`) — but existing save files keep their pre-1.17.0
  `world.db` (the schema was never migrated in place). Any competitive match on
  an upgraded save died with `sqlite3.OperationalError: no such table:
  season_player_stats` during match finish (and on any day where another
  competitive match is simulated). The pending-match guard then locked the whole
  UI (Continue / Smart Sim / Trophy Room all rejected while the match "hung").
- Repro: v1.16.0-era world + save, v1.18.0 code → crash at `_bump_season_stats`;
  with the hotfix the same save plays the match through and continues cleanly.

### Fixes
- `fm/world.py`: new `migrate_world()` (idempotent CREATE TABLE IF NOT EXISTS for
  the three v1.17.0 tables, exact same DDL) now runs on every DB connect —
  upgrading saves self-heal on first launch, no data touched, no rebuild.
- `fm/engine.py`: human-match finish now runs in a guarded transaction — any
  failure rolls back the whole finish instead of leaving the fixture half-applied
  (previously a crash before `apply_result` left partial stats in the world).
- `fm/match.py`: `finalize()` is now idempotent (early exit if already finished)
  so a retried finish can never re-roll the result.
- `fm/app.py`: `/api/trophies` no longer blocked while a match is pending — the
  Trophy Room is reachable at any time (read-only; match state untouched).
- `fm/static/app.js`: live-feed and Smart-Sim error toasts now surface the real
  server error message instead of a generic one.
- Verified end-to-end: old save boots, live competitive match completes,
  Continue + Trophy Room work mid-match and after FT.

### Note to player
Force-stop Touchline once after updating (clears the stuck match from memory),
then reopen — the upgrade repairs your save automatically and the stuck match
can be replayed from the Match Centre.

## v1.19.0 — Trophy Dynasty: organised museum, poaching, prize money, fast sim (2026-09-11)
Four additions on top of v1.18.1 (nothing previously shipped was removed).

### 1. Trophy Room reorganised ("unorganized" feedback)
- 3D room is now a real museum gallery: trophies are grouped by section in
  order of prestige — Continental (UCL/UEL/UECL) → Top-flight leagues → Other
  leagues → Domestic cups — within a section by number of wins, then recency.
- The most prestigious win is the hero pedestal (centre); the rest stand on a
  tidy, evenly spaced wall arc with a gap left for the branding wall. More
  than 12 trophies get a second inner ring so sections never crowd.
- Each wall display gets an engraved section plaque above it (competition,
  ×N, years). 2D fallback is sectioned with labelled shelves (verified in a
  DOM-mock test: 13/13 layout assertions).

### 2. The market knows your name (manager poaching)
- Winning trophies raises manager reputation: +4.0 (prestige ≥90: top league
  / UCL), +2.5 (≥70: major domestic cup / strong league), +1.5 (≥50), +1.0 —
  synced to the managers table and recorded in the season review.
- While employed, recent success (reputation + trophies in the last two
  seasons) sets "poach heat"; each week a clearly bigger top-flight club
  (rep +6 above you, or — if you are already at the summit — an elite rival
  abroad) may make a poaching approach: URGENT inbox + career-screen offer
  card with Accept / Decline (new /api/career/reject). Gossip news is
  published. Offers expire after 14 days.
- Accepting a poach moves the manager mid-career: old club is backfilled
  with an AI manager (world stays consistent), departure news is published,
  the career chapter closes as "left", the new board starts at fresh
  confidence. Verified end-to-end (33-assertion dynasty test).

### 3. Competition prize money funds the transfer market
- League-position + continental prize money (existing values, unchanged
  scale) is now paid out in full AND added to the transfer budget at season
  end; the season review says so.
- Cup finals pay the winner and 40% to the runner-up into cash, balance and
  transfer budget (message updated). Success funds the next window.

### 4. Simulation no longer takes hours (performance)
Profiled a full season (cProfile): 75% of time was 583K tiny SQL calls.
- League table re-sort after every match → lazy once-per-read dirty set
  (table() / _league_position / weekly AI sackings flush it; season end
  always fresh). ~200K calls removed.
- Cup/continental stage processing: previously every finished stage was
  re-scanned and re-queried on every single day of the season (10.9K no-op
  calls). Now a stage is processed exactly once, the first tick after its
  last match (pending queue), plus a one-per-season catch-up scan for legacy
  saves; persisted cup_advanced flags make it idempotent across restarts.
  RNG draw order preserved.
- Per-goal player writes in the daily AI match sim: one UPDATE per player
  and one batched per-competition stats upsert (was: per goal and per
  assist).
- advance() no longer rewrites the whole save file on every simulated day
  (that per-day JSON rewrite + flash write dominated sim time on phones);
  it commits daily and persists once at the end. `played` flags make a
  restart mid-sim safe.
- Result: desktop full-season fast_sim 55.6s → 17.3s (3.2×; 583K → 275K
  SQL calls). On phone storage the per-day rewrite removal adds a further
  large margin — Next Season is minutes, not hours.

### Regression
competition_test 11/11, live_match, smoke, order_effect, multiseason
(2 seasons; 2-season transfer budget now correctly reflects prize money),
dynasty_test 33/33, ui_sanity (24 screens / 62 handlers), node --check.

## v1.20.0 — Transfer market realism: caps, lockout, hijacks, trophy magnetism (2026-09-11)

Player feedback: counters were always accepted no matter how high, a player
could be bought and flipped in the same window, winning trophies attracted
no interest, and deals could quietly be stolen — "realism please".

### 1. The AI has a budget — counters are capped
- Every AI buyer now computes a real valuation: market value ×1.45, with a
  hard cap at their transfer budget (never less than €0.5m of face value).
- When YOU counter an incoming bid: at/under their ceiling it's accepted;
  within 12% they push back at their ceiling; beyond that they walk away and
  the offer is closed (no more "counter 100× value, instant accept").
- When a buyer counters your outgoing bid: the same budget logic now applies
  to their number too — a counter above their budget is refused outright,
  and after four rounds the talks end (final word).
- Funding guard on accept: a deal can no longer close above your cash.

### 2. No same-window flipping
- A player you signed during the current transfer window is locked until it
  closes: he cannot be listed, the AI refuses to sell him to you this
  window, and incoming bids for him are withdrawn on arrival.
- Related realism: buyers discount players who were bought recently at
  their current club (a ~15% haircut for under-90-days of service) — flip
  buyers exist, but they know what they're doing.

### 3. Winning brings suitors
- A club with trophies in the last two seasons attracts elite players:
  once a season a top player (CA ≥ ~16) from a rival sends an URGENT
  "Transfer enquiry" — he wants to join a winning project. The offer card
  carries his terms; willing players accept easier (willingness +2.5).
  Enquiries lapse after 30 days if you do nothing.
- Trophies already raised reputation (v1.19.0); now they move people.

### 4. Transfer hijacks (both directions)
- Outgoing: while your talks drag on, a richer rival with a higher
  reputation may outbid you on the player — the deal is marked hijacked,
  the player signs elsewhere, news is published. Bid earlier, bid higher.
- Incoming: while you negotiate an incoming bid, a bigger club can open a
  bidding war — the old bid is marked hijacked and the rival's higher
  offer arrives (URGENT inbox). A chance to sell for more — or to lose the
  deal if you stall.
- Bids are perishable: an ignored incoming bid lapses after 14 days (inbox
  items carry the full action payload, including asking price and value).

### Regression
market_test 16/16 (new: counter caps, lockout, flip haircut, final round,
both hijack directions, trophy enquiries + willingness), transfer_test
10/10, dynasty_test 33/33, competition_test 11/11, order_effect,
multiseason (2 seasons), staff 10/10, slots, facilities 11/11,
android_paths (EROFS emulation), live_match, smoke, ui_sanity
(24 screens / 62 handlers / 17 hooks).
