# TOUCHLINE — a football management simulation

A complete, persistent Football-Manager-style career simulation that runs in your browser.
Take charge of any club in the world — from Real Madrid to Wrexham in League One — and play
season after season: tactics, training, transfers, contracts, scouting, youth, media, board
pressure, injuries, fixture congestion and a fully simulated world around you.

**Simulation first, narration second.** Every result, injury, morale swing and transfer is
computed by the engine; the UI only presents what already happened. No railroading, no perfect
information, no artificial drama.

---

## What changed in 1.6 — "kill the clunk"

A ground-up interface rebuild on a single design system (tokens for colour, type, spacing,
radii and motion; compact rows, dividers and tables instead of card walls):

- **Design system** — one dark palette, one accent, 4px spacing grid, tabular numerals,
  120–180 ms motion only where it means something.
- **Club crests** — procedural shields in real club colours for 100+ clubs (stripes, halves,
  sashes, hoops), consistent in the top bar, tables, fixtures, matchday, hubs and news.
- **Dashboard = command centre** — next-match hero, status strip (position, points, form,
  board, fans, cash), squad readiness, board objectives, mini table and inbox preview.
- **Matchday** — competition-branded pre-match hero (crests, form, venue, XI, bench),
  an animated live clock with event graphics (goal + scorer + running score, cards, subs),
  half-time with stats and team talk, full-time with MOTM, stats duo and player ratings.
- **Competition identities** — UCL, Europa, Premier League, La Liga, Serie A, Bundesliga,
  Ligue 1 and cups each carry a colour + monogram through headers, hubs and brackets.
- **Navigation** — Dashboard / Squad / Tactics / Matches / Competitions on the bar,
  everything else one tap away in the sheet (phone) or sidebar (desktop).
- **Player profiles** — avatar header, ability/potential/condition/form strip, attribute
  bars, season record, cards, recent performances with ratings, contract and man-management.
- **Squad screen** — availability strip (fit/injured/suspended/unfit), form & weak-spot
  notes, compact rows on phones, full table on desktop, live name filter.

Everything else from 1.5 remains: real 2025/26 squads for 96 big-five clubs, Godfather Mode
advisor, and the full simulation beneath it.

---

## Quick start

Zero dependencies — Python 3 standard library only (no pip install, no framework, no database server).

```bash
./run.sh          # or: python3 fm/app.py
```

Then open **http://localhost:8000**

First launch builds the world (~3 s): 402 clubs, 402 managers, 15,135 players, 5,628 staff,
9,213 fixtures and 37 competitions across 21 divisions and the three UEFA tournaments.

To play from your phone, run the server on your PC and open `http://<your-pc-ip>:8000`.

### Starting a career

1. **NEW CAREER** → search any club (name, country or division)
2. **Manager profile** → name, nationality, age, reputation, coaching style, 11 coaching attributes
3. **10-step club load** → stadium, board, facilities, squad, finances, objectives, captain, calendar, inbox
4. **First management meeting** → chairman's welcome, objectives, budgets, assistant's assessment
5. **CONTINUE** (or press `Space`) → the world advances and stops at the next meaningful event:
   a match day, urgent mail, a transfer deadline or the season end

> Starting a new career replaces the existing save. One save slot: `data/saves/career1.json`.

---

## What you can do

| Screen | Contents |
|---|---|
| **HOME** | dashboard: date, finances, board confidence, fan sentiment, league position, form, next fixture, assistant's briefing |
| **INBOX** | URGENT / IMPORTANT / ROUTINE mail, filterable by category, read-tracking |
| **SQUAD** | senior squad + reserves + youth, attributes, condition, fitness, fatigue, sharpness, morale, happiness, promises, list/release, team talks, squad meetings |
| **TACTICS** | 12 formations, 6 mentalities, player roles & duties per slot, 15 team instructions, familiarity, predicted XI, tactical rating breakdown |
| **TRAINING** | weekly schedule of 14 session types, positional focus, squad load, coaching staff |
| **MATCH** | pre-match briefing, team selection, opposition report (knowledge-limited), live key-event or full match modes, **half-time team talk + 3 substitutions**, full post-match stats, ratings, xG |
| **TRANSFERS** | world search, free agents, asking prices, bids, counter-offers, loans, wage negotiation, incoming bids, deadline-day windows |
| **SCOUTING** | assign scouts to regions or players, knowledge accumulates, hidden attributes revealed over time, shortlist |
| **FINANCES** | monthly ledger, cash/balance, wage bill vs budget, transfer budget, debt, top earners, cash history |
| **BOARD** | objectives with live progress tracking, confidence, sack risk, club vision, chairman patience |
| **MEDIA** | press conferences, narrative, media pressure, news feed |
| **YOUTH** | academy rating, facilities, intake each season, promote players |
| **TABLE / COMPS** | league tables, form, all competitions, continental league phases and knockouts |
| **CAREER** | manager reputation, career history, trophy room, records, job market when sacked or resigned |

### Match modes

- **Instant** — simulate and show the result
- **Key events** — goals, cards, injuries, substitutions, half-time
- **Full** — every meaningful event, then the half-time break where you talk and substitute

The match engine is deterministic per seed: the same fixture, tactics and half-time decisions
produce the same result, whether played in one go or in two phases.

---

## Architecture

```
fm/
├── app.py        presentation layer — HTTP API (38 endpoints), no framework
├── mini.py       zero-dependency HTTP server + router (stdlib only)
├── engine.py     simulation: day tick, matches, transfers, contracts, finances,
│                 board, morale, injuries, training, scouting, seasons, world AI
├── match.py      MatchRunner — minute-by-minute match simulation (two-phase capable)
├── view.py       read models: turns engine state into screen payloads
├── world.py      world builder: clubs, players, staff, fixtures, competitions
├── constants.py  attributes, positions, roles, duties, formations, sessions, leagues, clubs
├── names.py      name pools for ~110 nationalities
└── static/       the game UI: index.html, app.js (vanilla JS SPA), style.css
tests/
├── smoke.py        end-to-end test (rebuilds the world, plays matches, advances 30 days)
└── season_test.py  full multi-season integration test
run.sh              start the server
```

**Strict separation of layers:** `engine.py` simulates and writes state; `view.py` shapes it for
display; `app.py` exposes it over HTTP; `static/app.js` renders it. The UI never invents facts.

### Persistence

- `data/world.db` — SQLite world (generated; rebuilt on each new career)
- `data/saves/career1.json` — your career: dates, board, fans, media, scouting knowledge,
  targets, flags, career history, trophies

Multi-season careers persist and remember everything: promotions, relegations, trophies,
records, past clubs, sacked managers, player development and ageing.

### Tests

```bash
python3 tests/smoke.py                    # ~20 s
python3 tests/season_test.py WXC 3        # 3 full seasons, ~290 s
```

---

## Requirements

- Python 3.8+ (standard library only)
- A modern browser

No Android Studio, no Node, no npm, no database server, no cloud service.

---

## What changed in 1.8 — GAME "not a browser"

Massive overhaul addressing **"It still feels like a browser trying to act like a game"**:

**Find the GOOD and don't touch it:**
- Elite realism 1.12x per point, ratio**1.35, 40+ rivalry blocks (Haaland won't join United), friendly rotation, transfer negotiation realism, VAR/card/goal cinematic, international breaks, Godfather mode — all kept

**Find the BAD and make it GOOD:**
- **Browser shell killed**: No more max-width 920 centered website, flat chips, line indicator tabbar, flat cards
- **Game shell**: Animated mesh gradient background (green .12 + blue + violet) + vignette overlay, HUD topbar with crest glow + stat icons (not chips), floating dock tabbar (pill active with translateY -2px + gradient), 3D tactile buttons with shine animation, 165deg gradient cards with inset highlight + float shadow + hover -2px
- **Transitions**: Slide left/right by nav direction (cubic-bezier .2,.9,.3,1.2), game-rise 0.34s stagger, logo-float splash, shimmer derby banners

**Find the UGLY and turn it into GEM:**
- **Start screen**: Was website hero → Now game launcher: 96px glowing crest with v8 badge, gradient title, pill badge PREMIUM · OFFLINE · 402 CLUBS, primary CTA 56px with glow, feature cards
- **Home = Manager Office**: Was browser dashboard with strip + tables → Now game HUD: circular SVG gauges (position/board/fans/fit) with drop-shadow glow, 3 quick-stat cards (points/form/cash), dressing-room style squad card + board card with 3D, league mini-cards not table rows, news as social feed with dot pulse
- **Squad = Dressing Room**: Was browser table + list → Now jersey locker cards: 44px avatar, pos + status pill (FIT/INJ/BAN/UNFIT with color), CA glow, goals/assists pill, grid 158px min, physio room card
- **Inbox = Social Feed**: Icons + previews kept but now with game dot pulse + gradient unread + NEW pill
- **Transfers = Marketplace**: Ticker + glass cards + negotiation realism kept, now with floating dock context
- **Matchday = Stadium**: Full takeover with shimmer, live-bar 165deg, confetti on win, haptics everywhere

**Game juice:**
- `navigator.vibrate` patterns: tap 12ms, nav 10ms, heavy 35ms, goal [30,40,80], card 25ms, VAR [15,20,15,20,40], success [15,30,40]
- Web Audio API sounds: tap 800Hz sine, nav 600Hz, success 660→880Hz, goal 440→660Hz triangle, card sawtooth 220Hz
- Confetti 28 particles on win, shake on goal, badge-bounce 1.8s infinite
- Every button: haptic + sound + scale .92 on active, 3D tactile

---

## Android (offline APK)

A standalone build of the same game is published as a release asset:

**[Touchline-1.13.0-arm64.apk](https://github.com/t7myz6f54s-afk/Football-manager/releases/download/v1.13.0/Touchline-1.13.0-arm64.apk)** — ~14 MB, Android 7.0+, 64-bit ARM, versionCode 16.

### What changed in 1.13 — SAVE SLOTS & BACKUP
- **Three careers at once** — each slot is a fully separate world+career; switching loads exactly the right one (verified by test)
- **Slot picker** on the launcher (your old career is migrated automatically on first launch of this version)
- **Saves manager** (launcher + Career screen): switch, delete, export, import
- **Export** — one tap produces a single backup file; on Android it opens the system share sheet (save to Drive, send to yourself on WhatsApp, anything). In a browser it downloads as a .zip
- **Import** — restore a backup into a free slot; the career comes back exactly as it left (state-verified round trip)
- Small print: "New career" now only wipes the *selected slot*; paused matches block slot switching (finish the match first)

v1.12.0 was Stats Center + the interface declutter. v1.11.0 was Match Day Live+.

### What changed in 1.12 — STATS CENTER + the declutter
**New: Stats Center** (its own tab):
- Golden boot race with goal bars, assists and clean-sheets leaderboards for your league
- **Expected goals vs actual** — per-club xG for/against from every played match, with over/under-performance deltas (who's finishing above their xG?)
- Your squad leaders (goals / assists / avg rating) and a form guide (last 5 with results)

**Interface rebuilt — every element must justify its space:**
- Removed every emoji icon in the interface (108 of them) — clean text labels instead
- **Grouped navigation**: the "More" wall of 13 tiles is now four labelled sections — Club / Market / World / Office — each item with a one-line description
- Tabs that matter: Home · Squad · Match · Stats (+ grouped More). News unread badge now lives on the More tile too
- Launcher is a launcher: no floating logo, no version bubble, no marketing badges
- Home lost the animated gauges for a compact season strip (position, points, board, fans, form)
- Flat buttons, no decorative glows or marketing strips ("cinematic VAR cards goals" line is gone), quieter Godfather card

v1.11.0 remains Match Day Live+ (live stepping, touchline shouts, momentum, live subs).

### What changed in 1.11 — MATCH DAY LIVE+
You're on the touchline now, not in the stands:
- **True live stepping** — the server simulates the match in small chunks while you watch; nothing is pre-computed anymore.
- **Momentum bar** — real per-minute pressure data, sliding 12-minute window, club colours.
- **⚡ Touchline shouts that matter** — ALL-OUT ATTACK, SIT DEEP, PRESS HARD, KILL THE GAME, GO LONG, CALM IT DOWN. Each mutates the live tactical model (mentality/tempo/press/risk), max 3 per match, 10-minute cooldown, context rules ("you can't kill a game you're not winning"). Statistically verified to change outcomes.
- **🔁 Live substitutions** — up to 5 total (3 at the break + 2 in play), fatigue read live.
- **Live commentary feed** — grounded colour lines between real events (possession reads, tired-player callouts, crowd tension) — the narration never invents facts.
- **85'+ drama mode** — tension vignette + haptics when it's still all to play for.
- **FAST forward** toggle and match recovery after an app restart mid-match.

v1.10.0 remains the boot-fix release (v1.9 shipped a JS syntax error that stuck the app on the loading screen; also fixed two transfer-engine crashes).

Previous: [v1.10.0](https://github.com/t7myz6f54s-afk/Football-manager/releases/download/v1.10.0/Touchline-1.10.0-arm64.apk) · [v1.9.0-ULTRA](https://github.com/t7myz6f54s-afk/Football-manager/releases/download/v1.9.0-ULTRA/Touchline-1.9.0-ULTRA-arm64.apk) (broken — do not use)

It embeds CPython (Chaquopy) and runs `fm/` unmodified on `127.0.0.1` inside a WebView, so the
whole simulation works with no internet connection. Career saves live in app-private storage.
Build it yourself with `cd android && ./make_apk.sh` — see [android/README.md](android/README.md).
