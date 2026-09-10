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
