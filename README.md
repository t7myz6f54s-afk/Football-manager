# TOUCHLINE — a football management simulation

A complete, persistent Football-Manager-style career simulation that runs in your browser.
Take charge of any club in the world — from Real Madrid to Wrexham in League One — and play
season after season: tactics, training, transfers, contracts, scouting, youth, media, board
pressure, injuries, fixture congestion and a fully simulated world around you.

**Simulation first, narration second.** Every result, injury, morale swing and transfer is
computed by the engine; the UI only presents what already happened. No railroading, no perfect
information, no artificial drama.

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
