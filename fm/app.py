"""HTTP presentation layer for the football management simulation.

Simulation lives in fm/engine.py + fm/match.py; projections in fm/view.py.
This module only wires them to HTTP. It uses fm/mini.py, a tiny stdlib-only
router, so the game has no third-party dependencies.
"""
import json
import os
import random
import shutil
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fm import constants as C
from fm import engine as E
from fm import view as V
from fm.mini import HTTPError, MiniApp, serve
from fm.world import DB_PATH, build_world, connect

# Optional pristine world shipped with the app (Android assets). Copying a
# prebuilt database is instant; building from scratch is the fallback.
SEED_DB = os.environ.get("FM_SEED_DB", "")


def seed_or_build():
    if SEED_DB and os.path.exists(SEED_DB):
        for suffix in ("", "-wal", "-shm"):
            p = DB_PATH + suffix
            if os.path.exists(p):
                os.remove(p)
        shutil.copyfile(SEED_DB, DB_PATH)
        return True
    build_world()
    return False

# All three can be overridden by environment variables so the same code runs
# unchanged on a desktop and inside the Android WebView wrapper (see android/).
BASE_DIR = os.environ.get("FM_BASE", "/home/user")
SAVE_DIR = os.environ.get("FM_SAVE_DIR", os.path.join(BASE_DIR, "data", "saves"))
SAVE_PATH = os.environ.get("FM_SAVE", os.path.join(SAVE_DIR, "career1.json"))
STATIC = os.environ.get("FM_STATIC", os.path.join(BASE_DIR, "fm", "static"))
HOST = os.environ.get("FM_HOST", "0.0.0.0")

app = MiniApp(static_dir=STATIC, static_prefix="/static")


class HTTPException(HTTPError):
    """Same call signature the handlers were written against."""


def Body(default=None):          # noqa: N802 - mirrors the declarative style
    return default if default is not Ellipsis else None


S = {"con": None, "save": None, "rng": random.Random(), "pending_match": None, "seed": 20260701}


# --------------------------------------------------------------------- helpers
def con():
    if S["con"] is None:
        if not os.path.exists(DB_PATH):
            seed_or_build()
        S["con"] = connect()
    return S["con"]


def save():
    if S["save"] is None and os.path.exists(SAVE_PATH):
        try:
            S["save"] = E.load(SAVE_PATH)
        except Exception:
            S["save"] = None
    return S["save"]


def need_save():
    s = save()
    if not s:
        raise HTTPException(400, "No active career. Start a new career first.")
    return s


def need_club():
    s = need_save()
    if not s.get("club_id") or s["flags"].get("unemployed"):
        raise HTTPException(409, "You are without a club.")
    return s


def no_pending():
    if S["pending_match"]:
        raise HTTPException(409, "A match is paused at half-time. Resolve it first "
                                 "(POST /api/match/halftime).")


def commit():
    c = con()
    c.commit()
    if S["save"]:
        E.persist(c, S["save"])


def _captain_name(s):
    pid = s["flags"].get("captain")
    if not pid:
        return "—"
    r = S["con"].execute("SELECT name FROM players WHERE id=?", (pid,)).fetchone()
    return r["name"] if r else "—"


def err(e):
    traceback.print_exc()
    return {"ok": False, "error": str(e)}


def brief_log(res, limit=60):
    """Compress an advance() log into UI-friendly items."""
    out = []
    for e in res.get("log", [])[:400]:
        kind = e.get("event") or e.get("kind")
        if kind == "match_scheduled":
            out.append({"type": "match_scheduled", "date": e.get("date"),
                        "fixtures": e.get("fixtures", [])})
        elif kind == "urgent_mail":
            out.append({"type": "urgent_mail", "date": e.get("date"), "items": e.get("items", [])})
        elif kind == "world":
            continue
        elif e.get("text"):
            out.append({"type": kind or "event", "date": e.get("date"),
                        "text": e["text"], "priority": e.get("priority", "ROUTINE")})
    return out[-limit:]


# --------------------------------------------------------------------- screens
@app.get("/api/boot")
def api_boot():
    s = save()
    return {"static": V.boot(), "has_save": bool(s),
            "save_info": ({"date": s["date"], "season": s["season"], "club_id": s["club_id"],
                           "unemployed": bool(s["flags"].get("unemployed")),
                           "manager": s["career"]["manager"]} if s else None)}


@app.get("/api/clubs/search")
def api_club_search(q: str = "", country: str = "", tier: int = 0):
    return {"clubs": V.club_search(con(), q=q, country=country, tier=tier or None)}


@app.get("/api/clubs/countries")
def api_club_countries():
    return {"countries": V.club_countries(con())}


@app.post("/api/career/new")
def api_career_new(payload: dict = Body(...)):
    try:
        code = payload.get("club_code")
        mgr = payload.get("manager") or {}
        if not code:
            raise HTTPException(400, "club_code required")
        if not mgr.get("name"):
            raise HTTPException(400, "manager name required")
        # a brand-new career starts from a pristine world
        if S["con"]:
            S["con"].close()
        S["con"] = None
        for suffix in ("", "-wal", "-shm"):
            p = DB_PATH + suffix
            if os.path.exists(p):
                os.remove(p)
        if os.path.exists(SAVE_PATH):
            os.remove(SAVE_PATH)
        seed_or_build()
        S["con"] = connect()
        S["seed"] = random.randrange(1, 10 ** 9)
        S["rng"] = random.Random(S["seed"])
        s = E.new_career(code, mgr, difficulty=payload.get("difficulty", "realistic"),
                         save_path=SAVE_PATH)
        S["save"] = s
        commit()
        c = E.club(S["con"], s["club_id"])
        lg = S["con"].execute("SELECT name FROM competitions WHERE code=?", (c["league"],)).fetchone()
        steps = [
            ("Club loaded", f"{c['name']} — {lg['name'] if lg else c['league']}"),
            ("Stadium", f"{c['stadium']}, capacity {c['capacity']:,}"),
            ("Board", f"Chairman {c['chairman']} · vision: {c['vision']}"),
            ("Facilities", f"Training {c['facilities']}/20 · Coaching {c['coaching']}/20 · "
                           f"Youth {c['youth']}/20 · Scouting {c['scouting']}/20"),
            ("Squad", f"{len([p for p in E.load_players(S['con'], c['id']) if p['squad'] in ('First Team','Reserve')])} senior players loaded"),
            ("Finances", f"Transfer budget {E.money(c['transfer_budget'])} · "
                         f"Wage budget {E.money(c['wage_budget'])} · Cash {E.money(c['cash'])}"),
            ("Objectives", " · ".join(o["text"] for o in s["board"]["objectives"][:2])),
            ("Captain", f"{_captain_name(s)} appointed captain"),
            ("Calendar", f"Season {s['season']}/{str(s['season']+1)[2:]} · pre-season from {s['date']}"),
            ("Inbox", f"{S['con'].execute('SELECT COUNT(*) FROM inbox').fetchone()[0]} messages waiting"),
        ]
        meeting = {
            "chairman": c["chairman"],
            "welcome": f"Welcome to {c['name']}. The board has agreed a {s['career']['difficulty']} "
                       f"mandate and expects you to work within the club's means.",
            "objectives": s["board"]["objectives"],
            "budget": {"transfer": c["transfer_budget"], "wage": c["wage_budget"],
                       "wage_bill": c["wage_bill"], "cash": c["cash"], "debt": c["debt"]},
            "assistant": E.assistant_assessment(S["con"], s),
            "squad": V.squad(S["con"], s, "First Team")[:12],
            "window": {"opens": str(E.season_windows(s["season"])["open"]),
                       "closes": str(E.season_windows(s["season"])["close"])},
            "next_fixture": V.upcoming(S["con"], s, 3),
        }
        return {"ok": True, "steps": steps, "meeting": meeting,
                "club": {"name": c["name"], "league": lg["name"] if lg else c["league"],
                         "tier": c["tier"], "rep": c["rep"]}}
    except HTTPException:
        raise
    except Exception as e:
        return err(e)


@app.post("/api/career/load")
def api_career_load(payload: dict = Body(default={})):
    path = payload.get("path") or SAVE_PATH
    if not os.path.exists(path):
        raise HTTPException(404, "No saved career found")
    S["save"] = E.load(path)
    S["con"] = con()
    S["rng"] = random.Random(S["seed"])
    return {"ok": True, "date": S["save"]["date"], "season": S["save"]["season"]}


@app.post("/api/career/reset")
def api_career_reset():
    S["save"] = None
    S["pending_match"] = None
    if os.path.exists(SAVE_PATH):
        os.remove(SAVE_PATH)
    return {"ok": True}


# ------------------------------------------------------------------ game views
@app.get("/api/state")
def api_state():
    s = need_save()
    return {"home": V.home(con(), s), "inbox_preview": V.inbox(con(), s, limit=6)["items"],
            "pending_match": bool(S["pending_match"]),
            "pending_mode": (S["pending_match"] or {}).get("mode"),
            "pending_phase": (S["pending_match"] or {}).get("phase")}


@app.get("/api/screen/{name}")
def api_screen(name: str, id: int = 0):
    s = need_save()
    c = con()
    if name in ("home", "dashboard"):
        return V.home(c, s)
    if name == "squad":
        return {"players": V.squad(c, s)}
    if name == "tactics":
        return V.tactics(c, s) if s["club_id"] else {"error": "no club"}
    if name == "training":
        return V.training(c, s) if s["club_id"] else {"error": "no club"}
    if name == "transfers":
        club_row = E.club(c, s["club_id"]) if s["club_id"] else None
        squad_cnt = c.execute("SELECT COUNT(*) FROM players WHERE club_id=?", (s["club_id"],)).fetchone()[0] if s["club_id"] else 0
        listed_cnt = c.execute("SELECT COUNT(*) FROM players WHERE club_id=? AND listed=1", (s["club_id"],)).fetchone()[0] if s["club_id"] else 0
        return {"window": E.window_state(E.d(s["date"]), s["season"]),
                "windows": {k: str(v) if not isinstance(v, tuple) else [str(x) for x in v]
                            for k, v in E.season_windows(s["season"]).items()},
                "offers": V.incoming_offers(c, s) if s["club_id"] else [],
                "my_offers": V.my_offers(c, s) if s["club_id"] else [],
                "shortlist_ids": list(s.get("targets", [])),
                "shortlist": V.scouting(c, s)["targets"] if s["club_id"] else [],
                "budget": club_row["transfer_budget"] if club_row else 0,
                "wage_budget": club_row["wage_budget"] if club_row else 0,
                "wage_bill": club_row["wage_bill"] if club_row else 0,
                "squad_count": squad_cnt,
                "listed_count": listed_cnt}
    if name == "scouting":
        return V.scouting(c, s) if s["club_id"] else {"error": "no club"}
    if name == "finances":
        return V.finances(c, s) if s["club_id"] else {"error": "no club"}
    if name == "board":
        return V.board_screen(c, s) if s["club_id"] else {"unemployed": True}
    if name == "media":
        return V.media(c, s)
    if name == "staff":
        return V.staff_screen(c, s) if s["club_id"] else {"error": "no club"}
    if name == "youth":
        return V.youth(c, s) if s["club_id"] else {"error": "no club"}
    if name == "career":
        return V.career(c, s)
    if name == "calendar":
        return {"fixtures": V.fixtures_screen(c, s), "upcoming": V.upcoming(c, s, 12)}
    if name == "comps":
        return {"comps": V.comps(c, s)}
    if name == "comp":
        return V.comp_detail(c, s, id) if id else {"error": "no comp"}
    if name == "table":
        return V.league_table(c, s) or {"rows": []}
    if name == "inbox":
        return V.inbox(c, s)
    raise HTTPException(404, f"unknown screen {name}")


@app.get("/api/inbox")
def api_inbox(cat: str = "", unread: bool = False):
    s = need_save()
    return V.inbox(con(), s, cat=cat or None, unread_only=unread)


@app.get("/api/advice")
def api_advice():
    s = need_save()
    on = bool(s["flags"].get("godfather"))
    out = {"ok": True, "on": on, "items": E.advise(con(), s) if on else []}
    if on:
        out["plan"] = E.godfather_plan(con(), s)
    return out


@app.post("/api/godfather")
def api_godfather(payload: dict = Body(...)):
    s = need_save()
    s["flags"]["godfather"] = bool(payload.get("on"))
    E.persist(con(), s)
    return {"ok": True, "on": s["flags"]["godfather"]}


@app.post("/api/inbox/read")
def api_inbox_read(payload: dict = Body(...)):
    s = need_save()
    ids = payload.get("ids") or []
    if payload.get("all"):
        con().execute("UPDATE inbox SET read=1")
    elif ids:
        con().executemany("UPDATE inbox SET read=1 WHERE id=?", [(int(i),) for i in ids])
    commit()
    return {"ok": True}


@app.get("/api/player/{pid}")
def api_player(pid: int):
    s = need_save()
    card = V.player_card(con(), s, pid)
    if not card:
        raise HTTPException(404, "player not found")
    return card


# ------------------------------------------------------------------- advancing
@app.post("/api/continue")
def api_continue(payload: dict = Body(default={})):
    s = need_save()
    no_pending()
    until = payload.get("until") or ("match" if s["club_id"] and not s["flags"].get("unemployed")
                                     else "week")
    stop_for = payload.get("stop_for")
    if stop_for is None:
        stop_for = ("match", "urgent") if until == "match" else ("urgent",)
    days = int(payload.get("days", 7))
    seen = [u["id"] for u in E.unread_urgent(con(), s)]
    auto_h = (until == "season_end")
    res = E.advance(con(), s, days=days, until=until, stop_for=tuple(stop_for),
                    rng=S["rng"], ignore_ids=seen, auto_human=auto_h)
    commit()
    nf = E.next_fixture(con(), s) if s["club_id"] else None
    return {"ok": True, "date": s["date"], "season": s["season"],
            "stop_reason": res["stop_reason"], "days_advanced": res["days_advanced"],
            "log": brief_log(res), "urgent": E.unread_urgent(con(), s),
            "next_fixture": V._fixture_brief(con(), s, nf) if nf else None,
            "unemployed": bool(s["flags"].get("unemployed")),
            "job_offers": s["flags"].get("job_offers", [])}


@app.post("/api/advance")
def api_advance(payload: dict = Body(default={})):
    s = need_save()
    no_pending()
    until = payload.get("until")
    auto_h = (until == "season_end")
    res = E.advance(con(), s, days=int(payload.get("days", 1)),
                    until=until, rng=S["rng"], auto_human=auto_h,
                    stop_for=tuple(payload.get("stop_for") or ()))
    commit()
    return {"ok": True, "date": s["date"], "stop_reason": res["stop_reason"],
            "log": brief_log(res)}


# ---------------------------------------------------------------------- match
@app.get("/api/match/next")
def api_match_next():
    s = need_club()
    nf = E.next_fixture(con(), s)
    if not nf:
        return {"ok": False, "msg": "No upcoming fixture."}
    row = con().execute("""SELECT f.*, k.name AS comp_name, k.code AS comp_code, k.ctype
        FROM fixtures f LEFT JOIN competitions k ON k.id=f.comp_id WHERE f.id=?""",
                        (nf["id"],)).fetchone()
    return {"ok": True, "preview": V.match_preview(con(), s, dict(row)), "fixture": dict(row)}


@app.post("/api/match/select")
def api_match_select(payload: dict = Body(...)):
    s = need_club()
    res = E.select_xi(con(), s, payload.get("ids") or [])
    commit()
    return res


@app.post("/api/match/auto")
def api_match_auto():
    s = need_club()
    res = E.auto_pick(con(), s)
    commit()
    return res


@app.post("/api/match/play")
def api_match_play(payload: dict = Body(default={})):
    """Kick the next match off. Instant mode plays it through in one call; the
    other modes pause at half-time so the manager can talk and substitute."""
    try:
        s = need_club()
        if S["pending_match"]:
            return {"ok": False, "msg": "A match is already paused at half-time."}
        mode = payload.get("mode", "key")
        lineup = payload.get("lineup") or None
        nf = E.next_fixture(con(), s)
        if not nf:
            return {"ok": False, "msg": "No upcoming fixture."}
        if nf["match_date"] > s["date"]:
            E.advance(con(), s, until="date", days=nf["match_date"], rng=S["rng"], stop_for=(), auto_human=False)
        nf = E.next_fixture(con(), s)
        row = con().execute("""SELECT f.*, k.name AS comp_name, k.code AS comp_code, k.ctype
            FROM fixtures f LEFT JOIN competitions k ON k.id=f.comp_id WHERE f.id=?""",
                            (nf["id"],)).fetchone()
        fx = dict(row)
        if mode == "instant":
            runner, ctx, ht = E.begin_human_match(con(), s, fx, rng=S["rng"], custom_lineup=lineup)
            if runner is None:
                return {"ok": False, "msg": "That fixture cannot be played (already played, "
                                           "or not enough fit players)."}
            data = E.finish_human_match(con(), s, fx, runner, ctx,
                                        halftime={"talk": payload.get("talk")})
            return _match_response(s, fx, data, mode)
        # Match Day Live+: the match is stepped minute-chunks server-side, so
        # touchline instructions genuinely change what happens next.
        runner, ctx = E._setup_human_match(con(), s, fx, rng=S["rng"], custom_lineup=lineup, live=True)
        if runner is None:
            return {"ok": False, "msg": "That fixture cannot be played (already played, "
                                       "or not enough fit players)."}
        S["pending_match"] = {"runner": runner, "ctx": ctx, "fx": fx, "mode": mode,
                              "phase": "live1", "ev_i": 0}
        return {"ok": True, "live": True, "mode": mode,
                "fixture": V._fixture_brief(con(), s, fx),
                "state": _live_view(s, runner, 0)}
    except HTTPException:
        raise
    except Exception as e:
        S["pending_match"] = None
        return err(e)


MENTALITY_LABELS = ((1.5, "Very Attacking"), (0.75, "Attacking"), (0.25, "Positive"),
                    (-0.25, "Balanced"), (-0.75, "Cautious"), (-1.5, "Defensive"), (-99, "Very Defensive"))


def _mentality_label(mshift):
    for cut, label in MENTALITY_LABELS:
        if mshift >= cut:
            return label
    return "Very Defensive"


def _live_stats(side_stats, all_stats):
    """Live stat lines for one side (possession as % of minutes played)."""
    total = all_stats["home"].get("poss", 0) + all_stats["away"].get("poss", 0)
    out = {k: side_stats.get(k, 0) for k in ("shots", "sot", "corners", "fouls", "yellow", "red", "big")}
    out["xg"] = round(side_stats.get("xg", 0.0), 2)
    out["poss"] = round(100 * side_stats.get("poss", 0) / total) if total else 50
    return out


def _live_view(s, runner, ev_i, new_events=None, colour=None, extra=None):
    """Snapshot of a live match, shaped for the UI."""
    fx = V._fixture_brief(con(), s, S["pending_match"]["fx"]) if S.get("pending_match") else {}
    my_tr, opp_tr, side = runner.live_sides()
    is_home = side == "H"
    allst = runner._stats_snapshot()
    me = allst["home" if is_home else "away"]
    opp = allst["away" if is_home else "home"]
    view = {
        "phase": (S["pending_match"] or {}).get("phase", "live1"),
        "minute": runner.minute, "half": runner.half,
        "score": {"home": runner.goals["H"], "away": runner.goals["A"]},
        "my_score": runner.goals[side], "opp_score": runner.goals["A" if side == "H" else "H"],
        "is_home": is_home,
        "home_name": fx.get("home", runner.home["name"]), "away_name": fx.get("away", runner.away["name"]),
        "home_code": fx.get("home_code", ""), "away_code": fx.get("away_code", ""),
        "momentum": runner.momentum_pct(),            # share for the HOME side
        "stats": {"me": _live_stats(me, allst), "opp": _live_stats(opp, allst)},
        "xi": runner.live_my_xi(), "bench": runner.live_bench(),
        "orders": runner.live_orders(),
        "subs_left": max(0, 5 - len(runner.subs[side])),
        "mentality": _mentality_label(my_tr.get("mshift", 0)),
        "tempo": round(my_tr.get("tempo", 0.5), 2), "press": round(my_tr.get("press", 0.6), 2),
        "new_events": new_events or [], "colour": colour or [],
        "ev_i": ev_i, "talks": ["praise", "encourage", "neutral", "firm", "aggressive", "defensive", "attacking"],
        "fixture": fx,
    }
    if extra:
        view.update(extra)
    return view


@app.post("/api/match/live_step")
def api_match_live_step(payload: dict = Body(default={})):
    """Advance the live match by a chunk (full=~2min, key=to next event, fast=bulk)."""
    try:
        s = need_club()
        pm = S["pending_match"]
        if not pm:
            return {"ok": False, "msg": "No match is in progress."}
        if pm.get("phase") not in ("live1", "live2"):
            # at half-time: hand back the HT state (idempotent)
            preview = V.match_preview(con(), s, pm["fx"])
            return {"ok": True, "live": True, "halftime": True,
                    "state": _halftime_view(s, pm["runner"].halftime_state(), preview)}
        mode = payload.get("mode", "full")
        ev_i = int(payload.get("ev_i", pm.get("ev_i", 0)))
        step = pm["runner"].live_step(ev_i=ev_i, mode=mode)
        pm["ev_i"] = step["ev_i"]
        extra = {}
        if step["boundary"] and step["half"] == 1:
            pm["phase"] = "halftime"
            preview = V.match_preview(con(), s, pm["fx"])
            extra["halftime_state"] = _halftime_view(s, pm["runner"].halftime_state(), preview)
        if step["boundary"] and step["half"] == 2:
            data = E._finish_human_match(con(), s, pm["fx"], pm["ctx"], pm["runner"].finalize())
            resp = _match_response(s, pm["fx"], data, pm["mode"])
            resp["live_done"] = True
            return resp
        return {"ok": True, "live": True,
                "state": _live_view(s, pm["runner"], step["ev_i"],
                                    new_events=step["new_events"], colour=step.get("colour"),
                                    extra=extra)}
    except HTTPException:
        raise
    except Exception as e:
        return err(e)


@app.post("/api/match/instruction")
def api_match_instruction(payload: dict = Body(default={})):
    """Bark a touchline instruction at the live match."""
    try:
        s = need_club()
        pm = S["pending_match"]
        if not pm or pm.get("phase") not in ("live1", "live2"):
            return {"ok": False, "msg": "No live match to instruct."}
        order = payload.get("order", "")
        ok, msg = pm["runner"].apply_order(pm["runner"].my_side, order)
        pm["ev_i"] = len(pm["runner"].events)
        return {"ok": ok, "msg": msg,
                "state": _live_view(s, pm["runner"], pm["ev_i"])}
    except HTTPException:
        raise
    except Exception as e:
        return err(e)


@app.post("/api/match/sub")
def api_match_sub(payload: dict = Body(default={})):
    """Make a substitution during a live match (max 5 total incl. half-time)."""
    try:
        s = need_club()
        pm = S["pending_match"]
        if not pm or pm.get("phase") not in ("live1", "live2"):
            return {"ok": False, "msg": "No live match for a substitution."}
        try:
            off_id, on_id = int(payload["off"]), int(payload["on"])
        except Exception:
            return {"ok": False, "msg": "Pick a player off and a player on."}
        runner = pm["runner"]
        if len(runner.subs[runner.my_side]) >= 5:
            return {"ok": False, "msg": "All five substitutions used."}
        made = runner.manual_sub(runner.my_side, runner.minute, off_id, on_id)
        if not made:
            return {"ok": False, "msg": "That substitution is not possible (player off/on not available)."}
        pm["ev_i"] = len(runner.events)
        return {"ok": True, "msg": "Substitution made.",
                "state": _live_view(s, runner, pm["ev_i"])}
    except HTTPException:
        raise
    except Exception as e:
        return err(e)


@app.get("/api/match/live_state")
def api_match_live_state():
    """Current live/HT state without advancing (used after app restart)."""
    try:
        s = need_club()
        pm = S["pending_match"]
        if not pm:
            return {"ok": False, "msg": "No match is in progress."}
        if pm.get("phase") in ("live1", "live2"):
            return {"ok": True, "live": True,
                    "mode": pm["mode"],
                    "state": _live_view(s, pm["runner"], pm.get("ev_i", 0))}
        preview = V.match_preview(con(), s, pm["fx"])
        return {"ok": True, "live": True, "halftime": True, "mode": pm["mode"],
                "state": _halftime_view(s, pm["runner"].halftime_state(), preview)}
    except HTTPException:
        raise
    except Exception as e:
        return err(e)


def _ht_stats(side, allstats, which):
    """Half-time stats with possession expressed as a share of the half."""
    keys = ("shots", "sot", "xg", "poss", "corners", "fouls", "big")
    out = {k: side.get(k, 0) for k in keys if k in side}
    total = allstats["home"].get("poss", 0) + allstats["away"].get("poss", 0)
    out["poss"] = round(100 * side.get("poss", 0) / total) if total else 50
    out["xg"] = round(side.get("xg", 0.0), 2)
    return out


def _halftime_view(s, ht, preview):
    """Half-time snapshot shaped for the UI."""
    is_home = s["club_id"] == ht.get("home_id", s["club_id"])
    me = "home" if preview["fixture"]["is_home"] else "away"
    opp = "away" if me == "home" else "home"
    names = {p["pid"]: p["name"] for p in ht["my_bench"]}
    return {
        "minute": 45,
        "score": {"home": ht["goals_home"], "away": ht["goals_away"]},
        "my_score": ht["goals_home"] if me == "home" else ht["goals_away"],
        "opp_score": ht["goals_away"] if me == "home" else ht["goals_home"],
        "home_name": preview["fixture"]["home"], "away_name": preview["fixture"]["away"],
        "is_home": preview["fixture"]["is_home"],
        "stats": {"me": _ht_stats(ht["stats"][me], ht["stats"], me),
                  "opp": _ht_stats(ht["stats"][opp], ht["stats"], opp)},
        "xi": ht["my_xi"], "bench": ht["my_bench"],
        "events": [e for e in ht["events"] if e["type"] in ("goal", "red", "injury", "sub")],
        "talks": ["praise", "encourage", "neutral", "firm", "aggressive", "defensive", "attacking"],
    }


def _match_response(s, fx, data, mode):
    S["pending_match"] = None
    if not data:
        return {"ok": False, "msg": "That fixture has already been played."}
    commit()
    view = V.match_result_view(con(), s, data, fx)
    view["mode"] = mode
    view["board"] = {"confidence": round(s["board"]["confidence"], 1),
                     "objectives": s["board"]["objectives"]}
    return {"ok": True, "result": view}


@app.post("/api/match/halftime")
def api_match_halftime(payload: dict = Body(default={})):
    """Resume the paused match after the manager's half-time decisions."""
    try:
        s = need_club()
        pm = S["pending_match"]
        if not pm:
            return {"ok": False, "msg": "No match is paused at half-time."}
        talk = payload.get("talk") or None
        subs = [tuple(x) for x in (payload.get("subs") or [])][:3]
        if pm.get("phase") in ("live1", "halftime"):
            # Match Day Live+: apply decisions, kick off the second half live
            pm["runner"].begin_second_half({"talk": talk, "subs": subs})
            pm["phase"] = "live2"
            pm["ev_i"] = len(pm["runner"].events)
            return {"ok": True, "live": True,
                    "state": _live_view(s, pm["runner"], pm["ev_i"])}
        data = E.finish_human_match(con(), s, pm["fx"], pm["runner"], pm["ctx"],
                                    halftime={"talk": talk, "subs": subs})
        return _match_response(s, pm["fx"], data, pm["mode"])
    except HTTPException:
        raise
    except Exception as e:
        S["pending_match"] = None
        return err(e)


@app.post("/api/match/abandon")
def api_match_abandon():
    """Finish the paused match with no half-time input (assistant handles it)."""
    try:
        s = need_club()
        pm = S["pending_match"]
        if not pm:
            return {"ok": False, "msg": "No match is paused at half-time."}
        if pm.get("phase") in ("live1", "live2", "halftime"):
            pm["runner"].run_rest()
            data = E._finish_human_match(con(), s, pm["fx"], pm["ctx"], pm["runner"].finalize())
        else:
            data = E.finish_human_match(con(), s, pm["fx"], pm["runner"], pm["ctx"], halftime={})
        return _match_response(s, pm["fx"], data, pm["mode"])
    except HTTPException:
        raise
    except Exception as e:
        S["pending_match"] = None
        return err(e)


# --------------------------------------------------------------------- squad
@app.post("/api/squad/promise")
def api_promise(payload: dict = Body(...)):
    s = need_club()
    res = E.player_talk(con(), s, int(payload["pid"]), "promise",
                        text=payload.get("promise", ""), rng=S["rng"])
    commit()
    return res


@app.post("/api/squad/talk")
def api_talk(payload: dict = Body(...)):
    s = need_club()
    res = E.player_talk(con(), s, int(payload["pid"]), payload.get("kind", "praise"),
                        text=payload.get("text", ""), rng=S["rng"])
    commit()
    return res


@app.post("/api/squad/meeting")
def api_meeting(payload: dict = Body(default={})):
    s = need_club()
    res = E.squad_meeting(con(), s, payload.get("tone", "balanced"), rng=S["rng"])
    commit()
    return res


@app.post("/api/squad/list")
def api_list(payload: dict = Body(...)):
    s = need_club()
    res = E.list_player(con(), s, int(payload["pid"]), bool(payload.get("listed", True)))
    commit()
    return res


@app.post("/api/squad/release")
def api_release(payload: dict = Body(...)):
    s = need_club()
    res = E.release_player(con(), s, int(payload["pid"]))
    commit()
    return res


# ------------------------------------------------------------------- tactics
@app.post("/api/tactics")
def api_tactics(payload: dict = Body(...)):
    s = need_club()
    roles = payload.get("roles")
    if roles is not None:
        clean = {}
        for k, v in roles.items():
            if isinstance(v, (list, tuple)) and len(v) == 2:
                clean[str(k)] = [v[0], v[1]]
            elif isinstance(v, str):
                cur = (E.get_tactics(con(), s)["roles"] or {}).get(str(k))
                duty = cur[1] if isinstance(cur, (list, tuple)) and len(cur) == 2 else "Support"
                clean[str(k)] = [v, duty]
        roles = clean
    instr = payload.get("instr")
    if payload.get("reset_instr"):
        instr = dict(C.INSTR_DEFAULT)
    res = E.set_tactics(con(), s, formation=payload.get("formation"),
                        mentality=payload.get("mentality"), instr=instr,
                        roles=roles, name=payload.get("name"))
    commit()
    res["tactic"] = V.tactics(con(), s)["tactic"]
    return res


@app.post("/api/training")
def api_training(payload: dict = Body(...)):
    s = need_club()
    res = E.set_training(con(), s, int(payload["day"]), payload["session"],
                         payload.get("focus", ""))
    commit()
    return res


# ----------------------------------------------------------------- transfers
@app.get("/api/transfer/search")
def api_transfer_search(pos: str = "", q: str = "", max_fee: float = 0, age_max: int = 0,
                        free: bool = False, affordable: bool = True):
    s = need_club()
    if free:
        return {"players": V.free_agents(con(), s)}
    budget = E.club(con(), s["club_id"])["transfer_budget"]
    cap = max_fee or None
    if cap is None and affordable:
        # by default only show players the club could realistically buy
        cap = max(1.5, round(budget * 1.35, 2))
    return {"players": V.transfers(con(), s, pos=pos, q=q, max_fee=cap, age_max=age_max or None),
            "cap": cap, "budget": budget}


@app.post("/api/transfer/offer")
def api_transfer_offer(payload: dict = Body(...)):
    s = need_club()
    res = E.make_offer(con(), s, int(payload["pid"]), float(payload.get("fee", 0)),
                       float(payload.get("wage", 0)), int(payload.get("years", 3)),
                       payload.get("promise", "Squad Rotation"),
                       is_loan=bool(payload.get("is_loan")), loan_end=payload.get("loan_end"),
                       rng=S["rng"])
    commit()
    return res


@app.post("/api/transfer/respond")
def api_transfer_respond(payload: dict = Body(...)):
    s = need_club()
    res = E.respond_counter(con(), int(payload["offer_id"]), bool(payload["accept"]),
                            new_fee=payload.get("new_fee"), rng=S["rng"])
    commit()
    return res


@app.post("/api/transfer/bid")
def api_transfer_bid(payload: dict = Body(...)):
    s = need_club()
    res = E.handle_incoming_bid(con(), s, int(payload["offer_id"]), payload["decision"],
                                counter_fee=payload.get("counter_fee"), rng=S["rng"])
    commit()
    return res


@app.post("/api/contract/renew")
def api_contract_renew(payload: dict = Body(...)):
    s = need_club()
    res = E.renew_contract(con(), s, int(payload["pid"]), float(payload.get("wage", 0)),
                           int(payload.get("years", 2)), payload.get("promise", "Squad Rotation"),
                           rng=S["rng"])
    commit()
    return res


@app.post("/api/scout/assign")
def api_scout_assign(payload: dict = Body(...)):
    s = need_club()
    res = E.assign_scout(s, region=payload.get("region"), pid=payload.get("pid"))
    commit()
    return res


@app.post("/api/scout/shortlist")
def api_shortlist(payload: dict = Body(...)):
    s = need_club()
    pid = int(payload["pid"])
    targets = s.setdefault("targets", [])
    if pid in targets:
        targets.remove(pid)
        added = False
    else:
        targets.append(pid)
        added = True
    commit()
    return {"ok": True, "added": added, "targets": targets}


# --------------------------------------------------------------------- career
@app.post("/api/career/resign")
def api_resign():
    s = need_club()
    res = E.resign(con(), s, rng=S["rng"])
    commit()
    return res


@app.post("/api/career/apply")
def api_apply(payload: dict = Body(...)):
    s = need_save()
    res = E.accept_job(con(), s, int(payload["club_id"]), rng=S["rng"])
    commit()
    return res


@app.get("/api/career/jobs")
def api_jobs():
    s = need_save()
    return {"jobs": E.list_jobs(con(), s), "offers": s["flags"].get("job_offers", [])}


# ------------------------------------------------------------------ news/media
@app.post("/api/media/press")
def api_press(payload: dict = Body(default={})):
    s = need_save()
    ans = payload.get("answer", "balanced")
    effects = {"confident": (2.5, -1.5, 3.0), "balanced": (1.0, 0.0, 1.0),
               "defensive": (-0.5, 1.5, -1.0), "critical": (-2.0, 2.5, -2.5)}
    board, fans, media = effects.get(ans, (1.0, 0.0, 1.0))
    s["board"]["confidence"] = max(0, min(100, s["board"]["confidence"] + board))
    s["fans"]["sentiment"] = max(0, min(100, s["fans"]["sentiment"] + fans))
    s["media"]["pressure"] = max(0, min(100, s["media"].get("pressure", 0) + media))
    E.add_news(con(), s, "MEDIA", f"Press conference: you took a {ans} line with the media.")
    commit()
    return {"ok": True, "board": round(s["board"]["confidence"], 1),
            "fans": round(s["fans"]["sentiment"], 1), "media_pressure": round(s["media"]["pressure"], 1)}


def main():
    os.makedirs(STATIC, exist_ok=True)
    os.makedirs(SAVE_DIR, exist_ok=True)
    if not os.path.exists(DB_PATH):
        print("Building the world database (first run)…", flush=True)
        seed_or_build()
    port = int(os.environ.get("PORT", 8000))
    serve(app, host=HOST, port=port)


if __name__ == "__main__":
    main()
