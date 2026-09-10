"""Career engine: persistent state, simulation clock, and all club systems.

Layering: simulate (compute what happened) -> state (update world) -> present.
"""
import json
import os
import random
import math
from datetime import date, timedelta

from . import constants as C
from . import match as M
from .world import connect, unpack_attrs, value_of, wage_of, _seed, pack_attrs, compute_ca
from .names import make_name, make_manager_name, make_staff_name, NATIONALITY_POOL

SAVE_DIR = os.environ.get("FM_SAVE_DIR", "/home/user/data/saves")
DEFAULT_SAVE = os.path.join(SAVE_DIR, "career1.json")

INT_BREAKS_2026_27 = [
    (date(2026, 9, 5), date(2026, 9, 9)),
    (date(2026, 10, 10), date(2026, 10, 14)),
    (date(2026, 11, 14), date(2026, 11, 18)),
    (date(2027, 3, 27), date(2027, 3, 31)),
    (date(2027, 6, 5), date(2027, 6, 9)),
]
WINDOW_OPEN = date(2026, 6, 15)
WINDOW_CLOSE = date(2026, 9, 1)
WINTER_WINDOW = (date(2027, 1, 1), date(2027, 2, 2))

DIFFICULTY = {
    "casual": dict(neg=0.85, ai_strength=0.92, budget=1.25, injuries=0.7, board=0.75, scout_err=1.4),
    "realistic": dict(neg=1.0, ai_strength=1.0, budget=1.0, injuries=1.0, board=1.0, scout_err=1.0),
    "hardcore": dict(neg=1.2, ai_strength=1.08, budget=0.72, injuries=1.25, board=1.35, scout_err=0.75),
}


# ----------------------------------------------------------------- utilities
def d(s):
    return date.fromisoformat(s) if s else None


def ds(x):
    return x.isoformat() if isinstance(x, date) else (x or "")


def money(m):
    """€m -> display string."""
    if m is None:
        return "-"
    if abs(m) >= 1:
        return f"€{m:,.1f}m"
    return f"€{m * 1000:,.0f}k"


def week_iso(dt):
    y, w, _ = dt.isocalendar()
    return y * 100 + w


INT_BREAK_PATTERN = [((9, 1), (9, 9)), ((10, 5), (10, 13)), ((11, 9), (11, 17)),
                     ((3, 23), (3, 31)), ((6, 5), (6, 9))]


def int_breaks(season):
    """International breaks covering season S/S+1."""
    out = []
    for (a, b) in INT_BREAK_PATTERN:
        ya = season if a[0] >= 7 else season + 1
        yb = season if b[0] >= 7 else season + 1
        out.append((date(ya, a[0], a[1]), date(yb, b[0], b[1])))
    return out


def in_int_break(dt, season=None):
    brks = int_breaks(season) if season is not None else INT_BREAKS_2026_27
    return any(a <= dt <= b for a, b in brks)


def season_windows(season):
    """Transfer windows for season S/S+1."""
    return {"open": date(season, 6, 15), "close": date(season, 9, 1),
            "winter": (date(season + 1, 1, 1), date(season + 1, 2, 2))}


def window_state(dt, season=None):
    w = season_windows(season) if season is not None else {
        "open": WINDOW_OPEN, "close": WINDOW_CLOSE, "winter": WINTER_WINDOW}
    if w["open"] <= dt <= w["close"]:
        return "summer"
    if w["winter"][0] <= dt <= w["winter"][1]:
        return "winter"
    return None


# ------------------------------------------------------------------- loading
def load_players(con, club_id=None, ids=None, all_squads=True):
    if ids:
        q = "SELECT * FROM players WHERE id IN (%s)" % ",".join(str(int(i)) for i in ids)
        rows = con.execute(q).fetchall()
    elif club_id is not None:
        rows = con.execute("SELECT * FROM players WHERE club_id=?", (club_id,)).fetchall()
    else:
        rows = con.execute("SELECT * FROM players").fetchall()
    out = []
    for r in rows:
        p = dict(r)
        p["_vec"] = unpack_attrs(p["attrs"])
        out.append(p)
    return out


def club(con, club_id):
    r = con.execute("SELECT * FROM clubs WHERE id=?", (club_id,)).fetchone()
    return dict(r) if r else None


def club_by_code(con, code):
    r = con.execute("SELECT * FROM clubs WHERE code=?", (code,)).fetchone()
    return dict(r) if r else None


def comp(con, comp_id):
    r = con.execute("SELECT * FROM competitions WHERE id=?", (comp_id,)).fetchone()
    return dict(r) if r else None


# --------------------------------------------------------------- save / load
def new_career(club_code, manager, difficulty="realistic", save_path=DEFAULT_SAVE,
               start=WINDOW_OPEN):
    os.makedirs(os.path.dirname(save_path) or ".", exist_ok=True)
    con = connect()
    c = club_by_code(con, club_code)
    if not c:
        raise ValueError("unknown club")
    # manager record replaces the AI manager at this club
    con.execute("DELETE FROM managers WHERE club_id=?", (c["id"],))
    attrs = manager.get("attrs") or {k: 10 for k in (
        "attacking", "defending", "fitness", "tactical", "mental", "technical",
        "youth", "man_mgmt", "motivation", "adaptability", "judging")}
    con.execute("INSERT INTO managers (name,nat,age,club_id,reputation,style,hired,human,attrs) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (manager["name"], manager.get("nat", "England"), manager.get("age", 38),
                 c["id"], manager.get("reputation", 12.0), manager.get("style", "Balanced"),
                 ds(start), 1, json.dumps(attrs)))
    ensure_human_setup(con, c["id"], formation="4-2-3-1 Wide")
    save = {
        "career": {
            "created": ds(start),
            "difficulty": difficulty,
            "manager": dict(manager, attrs=attrs),
            "clubs": [{"club_id": c["id"], "code": c["code"], "name": c["name"],
                       "from": ds(start), "to": None, "season": 2026}],
            "trophies": [], "records": {}, "job_offers": [], "reputation": manager.get("reputation", 12.0),
        },
        "club_id": c["id"],
        "date": ds(start),
        "season": 2026,
        "inbox_seen": 0,
        "match_mode": "key",
        "delegation": {"training": False, "scouting": True, "press": False,
                       "friendlies": True, "set_pieces": False, "youth": False,
                       "opposition": True, "recruitment": False},
        "board": {"confidence": 55.0, "pressure": 0.0, "objectives": [], "last_review": ds(start),
                  "warning": False},
        "fans": {"sentiment": 55.0, "support": 70.0},
        "media": {"narrative": "appointment", "pressure": 0.0},
        "scouting": {},          # region -> knowledge 0..100
        "scout_tasks": [],       # active assignments
        "known": {},             # player_id -> knowledge level 0..100
        "targets": [],           # recruitment shortlist ids
        "tactic_history": [],
        "pending_match": None,
        "last_result": None,
        "season_stats": {"played": 0, "won": 0, "drawn": 0, "lost": 0, "gf": 0, "ga": 0},
        "_path": save_path,
        "history": [],
        "flags": {},
    }
    persist(None, save, save_path)
    con.commit()
    # initial world setup for this career
    setup_club_state(con, save)
    seed_free_agents(con, save)
    snapshot_youth(con, save)
    con.commit()
    con.close()
    return save


def load(path=DEFAULT_SAVE):
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def persist(con, save, path=None):
    path = path or save.get("_path") or DEFAULT_SAVE
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(save, f)
    os.replace(tmp, path)


# -------------------------------------------------------- club state helpers
def ensure_human_setup(con, club_id, formation="4-2-3-1 Wide"):
    """Make sure the human club has tactics + a training schedule."""
    if not con.execute("SELECT 1 FROM tactics WHERE club_id=? AND is_human=1", (club_id,)).fetchone():
        con.execute("DELETE FROM tactics WHERE club_id=? AND is_human=1", (club_id,))
        con.execute("""INSERT INTO tactics (club_id,is_human,name,formation,mentality,instr,roles,
            familiarity,identity,active) VALUES (?,?,?,?,?,?,?,?,?,1)""",
            (club_id, 1, "Main", formation, "Balanced",
             json.dumps(dict(C.INSTR_DEFAULT)), json.dumps({}), 25.0,
             json.dumps({"possession": 50, "pressing": 50, "tempo": 50, "width": 50,
                         "directness": 50})))
    if not con.execute("SELECT 1 FROM training WHERE club_id=?", (club_id,)).fetchone():
        default_week = ["Recovery", "Fitness", "Tactical Familiarity", "Possession",
                        "Attacking", "Match Preparation", "Rest"]
        con.executemany("INSERT INTO training (club_id,day,session,focus) VALUES (?,?,?,?)",
                        [(club_id, i, x, "") for i, x in enumerate(default_week)])
    con.commit()


def setup_club_state(con, save):
    """Initialise human club: objectives, promises, squad status, inbox welcome."""
    cid = save["club_id"]
    c = club(con, cid)
    lg = con.execute("SELECT * FROM competitions WHERE code=?", (c["league"],)).fetchone()
    tier = c["tier"]
    rep = c["rep"]
    board = save["board"]
    # league objective based on club stature
    if tier == 1:
        if rep >= 90:
            obj = "Win the league"
            expect_pos = 2
        elif rep >= 82:
            obj = "Qualify for Europe"
            expect_pos = 7
        elif rep >= 72:
            obj = "Mid-table finish"
            expect_pos = 12
        else:
            obj = "Avoid relegation"
            expect_pos = 17
    else:
        if rep >= 70:
            obj = "Win promotion"
            expect_pos = 2
        elif rep >= 55:
            obj = "Reach the play-offs"
            expect_pos = 6
        elif rep >= 45:
            obj = "Mid-table finish"
            expect_pos = 12
        else:
            obj = "Avoid relegation"
            expect_pos = 19
    board["objectives"] = [
        {"type": "league", "text": obj, "comp": lg["name"], "target_pos": expect_pos,
         "status": "active", "critical": tier == 1 and rep < 75},
        {"type": "cup", "text": "Reach the Third Round", "status": "active", "critical": False},
        {"type": "vision", "text": c["vision"], "status": "active", "critical": False},
        {"type": "finance", "text": "Stay within the wage budget", "status": "active",
         "critical": False},
        {"type": "youth", "text": "Give at least one academy player a first-team appearance",
         "status": "active", "critical": False},
    ]
    board["confidence"] = 52.0 + (10 if rep > 80 else 0)
    # squad status expectations
    players = load_players(con, cid)
    first = [p for p in players if p["squad"] in ("First Team", "Reserve")]
    first.sort(key=lambda p: -p["ca"])
    n = len(first)
    for i, p in enumerate(first):
        frac = i / max(1, n - 1)
        if frac < 0.06:
            promise = "Star Player"
        elif frac < 0.18:
            promise = "Important Player"
        elif frac < 0.42:
            promise = "Regular Starter"
        elif frac < 0.66:
            promise = "Squad Rotation"
        elif frac < 0.85:
            promise = "Backup"
        else:
            promise = "Development"
        if p["age"] <= 20:
            promise = "Hot Prospect" if frac < 0.5 else "Development"
        con.execute("UPDATE players SET promise=?, minutes_expected=? WHERE id=?",
                    (promise, int(C.PROMISE_LEVEL[promise] * 520), p["id"]))
    # captain / leadership group
    if first:
        cands = sorted(first, key=lambda p: -(p["_vec"].get("leadership", 5) * 0.6 +
                                              p["_vec"].get("determination", 5) * 0.4 +
                                              min(p["age"], 34) / 10.0))
        captain = cands[0]
        save["flags"]["captain"] = captain["id"]
        save["flags"]["vice_captain"] = cands[1]["id"] if len(cands) > 1 else None
        save["flags"]["leadership_group"] = [x["id"] for x in cands[:5]]
    save["flags"]["squad_cohesion"] = 55.0
    save["flags"]["identity_days"] = 0
    con.execute("""UPDATE players SET fitness=93, sharpness=58, fatigue=8, form=0, morale=62,
        confidence=58 WHERE club_id=?""", (cid,))
    # inbox
    add_inbox(con, save, "BOARD", "URGENT", "Welcome to %s" % c["name"],
              f"Chairman {c['chairman']} has confirmed your appointment.\n\n"
              f"Board expectation: {obj}.\nClub vision: {c['vision']}.\n"
              f"Transfer budget: {money(c['transfer_budget'])}\n"
              f"Wage budget: {money(c['wage_budget'])} (current bill {money(c['wage_bill'])})\n\n"
              f"Your first competitive fixture is on the calendar. Use this window to shape the squad.",
              payload={"screen": "board"})
    add_inbox(con, save, "STAFF", "IMPORTANT", "Assistant manager's initial assessment",
              assistant_assessment(con, save), payload={"screen": "squad"})
    add_inbox(con, save, "MEDIA", "ROUTINE", "Unveiling press conference",
              "The local press wants your first words. Your media style will shape "
              "early expectations.", payload={"screen": "news", "action": "press_conference"})


def assistant_assessment(con, save):
    cid = save["club_id"]
    c = club(con, cid)
    players = load_players(con, cid)
    first = [p for p in players if p["squad"] in ("First Team", "Reserve")]
    am = con.execute("SELECT * FROM staff WHERE club_id=? AND role='Assistant Manager'", (cid,)).fetchone()
    lines = [f"{am['name'] if am else 'Your assistant'} hands you a folder.", ""]
    by_pos = {}
    for p in first:
        by_pos.setdefault(p["pos"], []).append(p)
    need = {"GK": 2, "DC": 4, "DL": 2, "DR": 2, "DM": 2, "MC": 3, "AMC": 2, "AML": 2, "AMR": 2, "ST": 2}
    weak = []
    for pos, req in need.items():
        have = sorted(by_pos.get(pos, []), key=lambda p: -p["ca"])
        if len(have) < req:
            weak.append(f"{pos}: only {len(have)} senior options (need {req})")
        elif len(have) >= 1 and have[0]["ca"] < (c["tier"] == 1 and 14 or 11):
            weak.append(f"{pos}: no standout (best {have[0]['name']}, CA {have[0]['ca']:.1f})")
    strong = sorted(first, key=lambda p: -p["ca"])[:3]
    lines.append("Strongest players: " + ", ".join(f"{p['name']} ({p['pos']}, {p['ca']:.1f})" for p in strong))
    if weak:
        lines.append("\nAreas of concern:\n- " + "\n- ".join(weak[:4]))
    ages = [p["age"] for p in first]
    over30 = sum(1 for a in ages if a >= 31)
    lines.append(f"\nSquad age profile: average {sum(ages)/max(1,len(ages)):.1f}, {over30} players aged 31+.")
    exp = [p for p in first if p["contract_end"] <= _season_contract_end(save)]
    if exp:
        lines.append(f"\n{len(exp)} contracts expire next summer: " +
                     ", ".join(p["name"] for p in exp[:6]) + ("..." if len(exp) > 6 else ""))
    yth = [p for p in players if p["squad"] in ("U21", "Youth") and p["pa"] >= 13]
    if yth:
        yth.sort(key=lambda p: -p["pa"])
        lines.append("\nAcademy prospects worth watching: " +
                     ", ".join(f"{p['name']} ({p['age']}, {p['pos']})" for p in yth[:4]))
    lines.append(f"\nFacilities {c['facilities']}/20, coaching {c['coaching']}/20, "
                 f"youth {c['youth']}/20, scouting {c['scouting']}/20.")
    return "\n".join(lines)


def add_inbox(con, save, cat, priority, subject, body, payload=None):
    con.execute("INSERT INTO inbox (date,cat,priority,subject,body,read,payload,season) "
                "VALUES (?,?,?,?,?,0,?,?)",
                (save["date"], cat, priority, subject, body, json.dumps(payload or {}),
                 save["season"]))


def add_news(con, save, cat, text, club_id=None, player_id=None):
    con.execute("INSERT INTO news (date,cat,text,club_id,player_id) VALUES (?,?,?,?,?)",
                (save["date"], cat, text, club_id, player_id))


# --------------------------------------------------------------- team ratings
STRENGTH_CACHE = {}
SQUAD_CACHE = {}
_VERSION = [0]


def bump():
    _VERSION[0] += 1


def _squad_rows(con, club_id):
    """Cached lightweight squad rows (with parsed attribute vectors)."""
    v = _VERSION[0]
    key = (club_id, v)
    hit = SQUAD_CACHE.get(key)
    if hit is not None:
        return hit
    cols = ("id,name,attrs,ca,pa,pos,pos2,age,fitness,fatigue,form,morale,sharpness,condition,"
            "suspended,squad,value,wage,height,injury_prone,minutes,goals,assists,apps,avg_rating,"
            "personality,professionalism,contract_end,promise")
    rows = con.execute(f"SELECT {cols} FROM players WHERE club_id=? ORDER BY ca DESC", (club_id,)).fetchall()
    out = []
    for r in rows:
        p = dict(r)
        p["_vec"] = unpack_attrs(p["attrs"])
        out.append(p)
    if len(SQUAD_CACHE) > 60:
        SQUAD_CACHE.clear()
    SQUAD_CACHE[key] = out
    return out


def club_strength(con, club_id, save=None):
    """Fast cached team strength (attack/defence/overall) for AI matches."""
    key = (club_id, _VERSION[0])
    if key in STRENGTH_CACHE:
        return STRENGTH_CACHE[key]
    allrows = _squad_rows(con, club_id)
    rows = [p for p in allrows if p["squad"] in ("First Team", "Reserve")][:16]
    if len(rows) < 11:
        for p in allrows:
            if p not in rows:
                rows.append(p)
            if len(rows) >= 14:
                break
    # simple best-XI: 1 GK, 4 DEF, 4 MID, 2 ATT
    def pick(pred, n, taken):
        out = []
        for p in sorted(rows, key=lambda x: -x["ca"]):
            if p["id"] in taken:
                continue
            if pred(p):
                out.append(p)
                taken.add(p["id"])
            if len(out) >= n:
                break
        return out
    taken = set()
    gk = pick(lambda p: p["pos"] == "GK" and p["condition"] == "fit", 1, taken)
    df = pick(lambda p: p["pos"] in ("DC", "DL", "DR") and p["condition"] == "fit", 4, taken)
    md = pick(lambda p: p["pos"] in ("DM", "MC") and p["condition"] == "fit", 3, taken)
    at = pick(lambda p: p["pos"] in ("AMC", "AML", "AMR", "ST") and p["condition"] == "fit", 3, taken)
    xi = gk + df + md + at
    while len(xi) < 11:
        rest = [p for p in rows if p["id"] not in taken and p["condition"] == "fit"]
        if not rest:
            rest = [p for p in rows if p["id"] not in taken]
        if not rest:
            break
        p = rest[0]
        xi.append(p)
        taken.add(p["id"])
    att = sum(p["ca"] * M.AREA_WEIGHT[p["pos"]][0] for p in xi) / max(0.001, sum(M.AREA_WEIGHT[p["pos"]][0] for p in xi))
    dfn = sum(p["ca"] * M.AREA_WEIGHT[p["pos"]][1] for p in xi) / max(0.001, sum(M.AREA_WEIGHT[p["pos"]][1] for p in xi))
    cond = sum(M.player_condition(p) for p in xi) / max(1, len(xi))
    gkq = max(6.0, gk[0]["ca"] if gk else 8.0)
    height = sum(p["_vec"].get("strength", 10) for p in xi) / max(1, len(xi))
    out = dict(attack=att * (0.85 + 0.15 * cond), defence=dfn * (0.85 + 0.15 * cond),
               overall=sum(p["ca"] for p in xi) / max(1, len(xi)) * cond,
               gk=gkq, condition=cond, press=0.8, possession=0.0, width=0.5, tempo=0.5,
               height=182, setpiece=max(6.0, max((p["_vec"].get("set_pieces", 6) for p in xi), default=6)),
               fitness=sum(p["fitness"] for p in xi) / max(1, len(xi)),
               fatigue=sum(p["fatigue"] for p in xi) / max(1, len(xi)),
               morale=sum(p["morale"] for p in xi) / max(1, len(xi)),
               mentality="Balanced", mshift=0, line=0, loe=0, direct=0, familiar=70.0, n=len(xi),
               ids=[p["id"] for p in xi])
    if len(STRENGTH_CACHE) > 3000:
        STRENGTH_CACHE.clear()
    STRENGTH_CACHE[key] = out
    return out


def human_rating(con, save):
    cid = save["club_id"]
    tac = get_tactics(con, save)
    players = load_players(con, cid)
    xi, bench = M.build_lineup(players, tac)
    rating = M.team_rating(xi, tac)
    return xi, bench, rating, tac


def get_tactics(con, save):
    r = con.execute("SELECT * FROM tactics WHERE club_id=? AND is_human=1 AND active=1",
                    (save["club_id"],)).fetchone()
    if not r:
        r = con.execute("SELECT * FROM tactics WHERE club_id=? AND is_human=1", (save["club_id"],)).fetchone()
    if not r:
        ensure_human_setup(con, save["club_id"])
        r = con.execute("SELECT * FROM tactics WHERE club_id=? AND is_human=1",
                        (save["club_id"],)).fetchone()
    t = dict(r)
    t["instr"] = json.loads(t["instr"] or "{}")
    t["roles"] = json.loads(t["roles"] or "{}")
    t["identity"] = json.loads(t["identity"] or "{}")
    return t


def save_tactics(con, save, **kw):
    t = get_tactics(con, save)
    sets = []
    vals = []
    for k, v in kw.items():
        if k in ("instr", "roles", "identity"):
            v = json.dumps(v)
        sets.append(f"{k}=?")
        vals.append(v)
    if sets:
        vals.append(save["club_id"])
        con.execute(f"UPDATE tactics SET {','.join(sets)} WHERE club_id=? AND is_human=1", vals)


def ai_tactics(con, club_id):
    r = con.execute("SELECT * FROM tactics WHERE club_id=? AND is_human=0 LIMIT 1", (club_id,)).fetchone()
    if r:
        t = dict(r)
        t["instr"] = json.loads(t["instr"] or "{}")
        t["roles"] = json.loads(t["roles"] or "{}")
        return t
    mgr = con.execute("SELECT * FROM managers WHERE club_id=?", (club_id,)).fetchone()
    style = mgr["style"] if mgr else "Balanced"
    presets = {
        "Possession": ("4-3-3 DM Wide", "Positive", dict(passing_directness="Shorter", tempo="Standard", width="Wider", line_of_engagement="Higher")),
        "High press": ("4-2-3-1 Wide", "Attacking", dict(pressing_intensity="Much More", line_of_engagement="Much Higher", defensive_line="Higher", tempo="Higher")),
        "Counter-attack": ("4-4-2", "Cautious", dict(tempo="Much Higher", passing_directness="More Direct", defensive_line="Deeper")),
        "Direct": ("4-4-2", "Balanced", dict(passing_directness="Much More Direct", width="Wider")),
        "Balanced": ("4-2-3-1 Wide", "Balanced", {}),
        "Defensive solidity": ("5-3-2", "Defensive", dict(defensive_line="Deeper", line_of_engagement="Deeper", tempo="Lower")),
        "Wing play": ("4-3-3", "Positive", dict(width="Much Wider", hit_early_crosses=True)),
        "Youth-focused": ("4-3-3 DM Wide", "Positive", {}),
    }
    formation, ment, over = presets.get(style, presets["Balanced"])
    instr = dict(C.INSTR_DEFAULT)
    instr.update(over)
    t = dict(club_id=club_id, formation=formation, mentality=ment, instr=instr, roles={},
             familiarity=72.0, name="AI", identity={})
    con.execute("INSERT INTO tactics (club_id,is_human,name,formation,mentality,instr,roles,familiarity,identity,active) "
                "VALUES (?,0,?,?,?,?,?,?,?,1)",
                (club_id, t["name"], formation, ment, json.dumps(instr), "{}", 72.0,
                 json.dumps({"possession": 50, "pressing": 50, "tempo": 50, "width": 50, "directness": 50})))
    return t


# ------------------------------------------------------------------ fixtures
def fixtures_on(con, dt, club_id=None):
    iso = ds(dt)
    if club_id:
        rows = con.execute("""SELECT f.*, k.name AS comp_name, k.code AS comp_code, k.ctype
            FROM fixtures f LEFT JOIN competitions k ON k.id=f.comp_id
            WHERE f.match_date=? AND (f.home_id=? OR f.away_id=?) AND f.played=0""",
            (iso, club_id, club_id)).fetchall()
    else:
        rows = con.execute("""SELECT f.*, k.name AS comp_name, k.code AS comp_code, k.ctype
            FROM fixtures f LEFT JOIN competitions k ON k.id=f.comp_id
            WHERE f.match_date=? AND f.played=0""", (iso,)).fetchall()
    return [dict(r) for r in rows]


def next_fixture(con, save, club_id=None):
    if not (club_id or save.get("club_id")):
        return None
    cid = club_id or save["club_id"]
    r = con.execute("""SELECT f.*, k.name AS comp_name, k.code AS comp_code, k.ctype
        FROM fixtures f LEFT JOIN competitions k ON k.id=f.comp_id
        WHERE (f.home_id=? OR f.away_id=?) AND f.played=0 AND f.match_date>=?
        ORDER BY f.match_date LIMIT 1""", (cid, cid, save["date"])).fetchone()
    return dict(r) if r else None


FIXED_MOVES = {
    "ENG1": 3, "ENG2": 3, "ENG3": 3, "ENG4": 2, "ENG5": 0,
    "ESP1": 3, "ESP2": 2, "ITA1": 3, "ITA2": 3, "GER1": 2, "GER2": 2,
    "FRA1": 2, "FRA2": 2, "NED1": 1, "NED2": 1, "POR1": 2, "POR2": 2,
    "SCO1": 1, "SCO2": 1, "SCO3": 1, "SCO4": 1, "BEL1": 2, "TUR1": 3,
    "ARG1": 2, "BRA1": 4,
}


def league_moves(con, code):
    """How many clubs leave this division at season end (relegation / step-down)."""
    if code in FIXED_MOVES:
        return FIXED_MOVES[code]
    row = con.execute("SELECT tier, country, rel FROM competitions WHERE code=?", (code,)).fetchone()
    if not row:
        return 0
    lower = con.execute("SELECT code FROM competitions WHERE country=? AND tier=?",
                        (row["country"], row["tier"] + 1)).fetchone()
    if not lower:
        return 0                      # bottom division: nobody steps down
    return row["rel"] or 2


def _season_contract_end(save):
    return f"{save['season'] + 1}-06-30"


def _cup_round_date(dtstr, season, country):
    """Shift a base cup-round date into the given season, preserving month/day."""
    base = date.fromisoformat(dtstr)
    yr = season + 1 if base.month <= 6 else season
    if country in ("Brazil", "Argentina"):
        yr = season + 1
    try:
        nd = base.replace(year=yr)
    except ValueError:
        nd = base.replace(year=yr, day=28)
    return nd.isoformat()


CUP_ROUNDS = {
    "FACUP": [("R1", "2026-11-07"), ("R2", "2026-12-05"), ("R3", "2027-01-09"), ("R4", "2027-01-30"),
              ("R5", "2027-03-02"), ("QF", "2027-03-20"), ("SF", "2027-04-24"), ("F", "2027-05-15")],
    "EFLCUP": [("R1", "2026-08-11"), ("R2", "2026-08-25"), ("R3", "2026-09-15"), ("R4", "2026-10-27"),
               ("QF", "2026-12-15"), ("SF", "2027-01-12"), ("F", "2027-02-28")],
    "COPADELREY": [("R1", "2026-11-04"), ("R32", "2027-01-06"), ("R16", "2027-01-20"),
                   ("QF", "2027-02-03"), ("SF", "2027-03-03"), ("F", "2027-04-24")],
    "COPPAITALIA": [("R1", "2026-08-15"), ("R16", "2026-12-09"), ("QF", "2027-01-27"),
                    ("SF", "2027-03-03"), ("F", "2027-05-12")],
    "DFBPOKAL": [("R1", "2026-08-21"), ("R2", "2026-10-27"), ("R16", "2027-02-02"),
                 ("QF", "2027-03-02"), ("SF", "2027-04-20"), ("F", "2027-05-22")],
    "COUPEFRANCE": [("R7", "2026-11-14"), ("R64", "2027-01-02"), ("R32", "2027-01-23"),
                    ("R16", "2027-02-06"), ("QF", "2027-03-06"), ("SF", "2027-04-17"), ("F", "2027-05-08")],
    "KNVB": [("R1", "2026-10-20"), ("R16", "2027-01-19"), ("QF", "2027-02-09"), ("SF", "2027-03-09"), ("F", "2027-04-25")],
    "TACAPOR": [("R3", "2026-10-17"), ("R4", "2026-11-21"), ("R16", "2027-01-16"), ("QF", "2027-02-13"),
                ("SF", "2027-03-13"), ("F", "2027-05-23")],
    "SCOCUP": [("R3", "2026-11-28"), ("R4", "2027-01-23"), ("R5", "2027-02-20"), ("QF", "2027-03-20"),
               ("SF", "2027-04-24"), ("F", "2027-05-22")],
    "BELCUP": [("R6", "2026-09-23"), ("R7", "2026-12-02"), ("QF", "2027-01-20"), ("SF", "2027-02-10"), ("F", "2027-05-01")],
    "TURCUP": [("R3", "2026-10-28"), ("R4", "2026-12-16"), ("R16", "2027-02-10"), ("QF", "2027-03-10"),
               ("SF", "2027-04-21"), ("F", "2027-05-19")],
    "COPARG": [("R64", "2027-02-10"), ("R32", "2027-03-18"), ("R16", "2027-04-15"), ("QF", "2027-05-06"),
               ("SF", "2027-05-20"), ("F", "2027-05-30")],
    "COPBRA": [("R1", "2027-02-17"), ("R2", "2027-03-03"), ("R32", "2027-04-14"), ("R16", "2027-05-12"),
               ("QF", "2027-05-26"), ("SF", "2027-06-09"), ("F", "2027-06-23")],
}
KO_NAMES = {"R16": "Round of 16", "R32": "Round of 32", "R64": "First Round", "QF": "Quarter-final",
            "SF": "Semi-final", "F": "Final", "R1": "First Round", "R2": "Second Round",
            "R3": "Third Round", "R4": "Fourth Round", "R5": "Fifth Round", "R6": "Sixth Round",
            "R7": "Seventh Round"}


# ------------------------------------------------------------------ AI matches
def ai_sim(con, save, fx, rng, difficulty="realistic"):
    hs = club_strength(con, fx["home_id"], save)
    aws = club_strength(con, fx["away_id"], save)
    ctype = fx.get("ctype") or "league"
    comp_row = comp(con, fx["comp_id"]) if fx["comp_id"] else None
    pres = (comp_row["prestige"] / 100.0) if comp_row else 0.6
    k = 1.18
    ratio = (hs["attack"] / max(aws["defence"], 1.0))
    xratio = (aws["attack"] / max(hs["defence"], 1.0))
    eh = k * (ratio ** 0.80) * 1.06 * (0.90 + 0.18 * hs["condition"])
    ea = k * (xratio ** 0.80) * 0.92 * (0.90 + 0.18 * aws["condition"])
    if ctype == "friendly":
        eh *= 0.8; ea *= 0.8
    eh = max(0.18, min(4.4, eh)); ea = max(0.12, min(4.2, ea))
    diffmul = DIFFICULTY.get(difficulty, DIFFICULTY["realistic"])
    if save and fx["home_id"] != save["club_id"] and fx["away_id"] != save["club_id"]:
        pass
    hg = _poisson(rng, eh); ag = _poisson(rng, ea)
    xgh = round(hg * rng.uniform(0.7, 1.35) + rng.uniform(0.1, 0.6), 2)
    xga = round(ag * rng.uniform(0.7, 1.35) + rng.uniform(0.05, 0.5), 2)
    winner = None
    pens = None
    if ctype in ("cup", "continental") and fx.get("stage") not in ("league",) and hg == ag:
        # knockout: extra time then pens
        if rng.random() < 0.35:
            if rng.random() < 0.5:
                hg += 1
            else:
                ag += 1
    if ctype in ("cup", "continental") and fx.get("stage") != "league" and hg == ag and fx.get("stage") in ("SF", "F", "R16", "QF", "R32", "R64", "R1", "R2", "R3", "R4", "R5", "R6", "R7"):
        pens = "H" if rng.random() < (0.53 if True else 0.5) else "A"
        winner = pens
    data = dict(xg_home=xgh, xg_away=xga,
                shots_home=max(hg * 3, int(rng.gauss(9 + (hs["attack"] - aws["defence"]) * 1.4, 3))),
                shots_away=max(ag * 3, int(rng.gauss(8 + (aws["attack"] - hs["defence"]) * 1.4, 3))),
                possession_home=int(max(28, min(72, 50 + (hs["overall"] - aws["overall"]) * 3.2 + rng.gauss(0, 5)))),
                penalties=pens, ai=True)
    data["shots_on_target_home"] = min(data["shots_home"], int(hg + rng.randint(1, 4)))
    data["shots_on_target_away"] = min(data["shots_away"], int(ag + rng.randint(0, 3)))
    return hg, ag, data


def _poisson(rng, lam):
    L = math.exp(-lam); k = 0; p = 1.0
    while True:
        k += 1
        p *= rng.random()
        if p <= L:
            return k - 1


def apply_result(con, save, fx, hg, ag, data, rng):
    """Update standings, form, club/player state after a played fixture."""
    ctype = fx.get("ctype") or "league"
    con.execute("UPDATE fixtures SET played=1, hg=?, aw=?, report=?, rating_h=?, rating_a=? WHERE id=?",
                (hg, ag, json.dumps(data)[:200000], data.get("rating_h"), data.get("rating_a"), fx["id"]))
    hc = club(con, fx["home_id"]); ac = club(con, fx["away_id"])
    con.execute("INSERT INTO matches_log (fixture_id,date,home,away,hs,as_away,comp,data) VALUES (?,?,?,?,?,?,?,?)",
                (fx["id"], fx["match_date"], hc["name"] if hc else "?", ac["name"] if ac else "?",
                 hg, ag, fx.get("comp_code") or "", json.dumps({k: v for k, v in data.items()
                 if k in ("xg_home", "xg_away", "possession_home", "shots_home", "shots_away", "penalties", "ai")})))
    if ctype == "friendly":
        return
    stage = fx.get("stage") or "league"
    if ctype in ("league", "continental") and stage == "league" and fx["comp_id"]:
        for side, cidc, gf, ga, w, dd, l in (
                ("H", fx["home_id"], hg, ag, 1 if hg > ag else 0, 1 if hg == ag else 0, 1 if hg < ag else 0),
                ("A", fx["away_id"], ag, hg, 1 if ag > hg else 0, 1 if hg == ag else 0, 1 if ag < hg else 0)):
            row = con.execute("SELECT * FROM standings WHERE comp_id=? AND season=? AND club_id=? AND stage='league'",
                              (fx["comp_id"], save["season"], cidc)).fetchone()
            if not row:
                con.execute("INSERT INTO standings VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                            (fx["comp_id"], save["season"], cidc, "league", 0, 0, 0, 0, 0, 0, 0, "", 0))
                row = con.execute("SELECT * FROM standings WHERE comp_id=? AND season=? AND club_id=? AND stage='league'",
                                  (fx["comp_id"], save["season"], cidc)).fetchone()
            form = (row["form"] + ("W" if w else ("D" if dd else "L")))[-5:]
            con.execute("""UPDATE standings SET p=p+1, w=w+?, d=d+?, l=l+?, gf=gf+?, ga=ga+?,
                pts=pts+?, form=? WHERE comp_id=? AND season=? AND club_id=? AND stage='league'""",
                        (w, dd, l, gf, ga, (3 if w else (1 if dd else 0)), form,
                         fx["comp_id"], save["season"], cidc))
        retable(con, save, fx["comp_id"])
    # attendance / matchday income
    if hc and ctype != "friendly":
        att = int(min(hc["capacity"], hc["capacity"] * (0.72 + 0.28 * min(1, hc["rep"] / 90.0)) *
                      rng.uniform(0.9, 1.0)))
        con.execute("UPDATE fixtures SET attendance=? WHERE id=?", (att, fx["id"]))
        if save and fx["home_id"] == save["club_id"]:
            # gate receipts are already part of season_income (paid out monthly);
            # this only tracks them for the financial report
            inc = att * (18 + hc["tier"] * -1.5 + hc["rep"] * 0.35) / 1e6
            save["flags"].setdefault("matchday_income", 0.0)
            save["flags"]["matchday_income"] += inc


def retable(con, save, comp_id):
    rows = con.execute("""SELECT * FROM standings WHERE comp_id=? AND season=? AND stage='league'""",
                       (comp_id, save["season"])).fetchall()
    order = sorted(rows, key=lambda r: (-r["pts"], -(r["gf"] - r["ga"]), -r["gf"], r["club_id"]))
    for i, r in enumerate(order):
        con.execute("UPDATE standings SET pos=? WHERE comp_id=? AND season=? AND club_id=? AND stage='league'",
                    (i + 1, comp_id, save["season"], r["club_id"]))
    return order


def table(con, save, comp_id, limit=None):
    rows = con.execute("""SELECT s.*, c.name, c.short, c.rep, c.code FROM standings s JOIN clubs c ON c.id=s.club_id
        WHERE s.comp_id=? AND s.season=? AND s.stage='league' ORDER BY s.pos""",
        (comp_id, save["season"])).fetchall()
    out = [dict(r) for r in rows]
    return out[:limit] if limit else out


# ------------------------------------------------------- cup / KO progression
def check_round_complete(con, save, comp_id, stage):
    n = con.execute("SELECT COUNT(*) FROM fixtures WHERE comp_id=? AND season=? AND stage=? AND played=0",
                    (comp_id, save["season"], stage)).fetchone()[0]
    return n == 0


def pen_winner(data, rng=None):
    """Normalise the penalties field of a match report to 'H'/'A' (or None)."""
    p = (data or {}).get("penalties")
    if isinstance(p, dict):
        w = p.get("winner")
        if w in ("H", "A"):
            return w
        h, a = p.get("home", 0), p.get("away", 0)
        if h != a:
            return "H" if h > a else "A"
        return None
    if p in ("H", "A"):
        return p
    return None


def advance_cup(con, save, comp_id, rng):
    """Draw the next round of a cup competition once the current one finishes."""
    ccode = con.execute("SELECT code, name, country FROM competitions WHERE id=?", (comp_id,)).fetchone()
    if not ccode:
        return
    rounds = CUP_ROUNDS.get(ccode["code"])
    if not rounds:
        return
    done = [r for r in con.execute("SELECT DISTINCT stage FROM fixtures WHERE comp_id=? AND season=?",
                                   (comp_id, save["season"])).fetchall()]
    done_stages = {x[0] for x in done}
    cur_idx = None
    for i, (st, dt) in enumerate(rounds):
        if st in done_stages:
            cur_idx = i
    if cur_idx is None or cur_idx + 1 >= len(rounds):
        return
    # winners of current stage
    stage = rounds[cur_idx][0]
    fx = con.execute("SELECT * FROM fixtures WHERE comp_id=? AND season=? AND stage=?",
                     (comp_id, save["season"], stage)).fetchall()
    winners = []
    for f in fx:
        if not f["played"]:
            return
        hg, ag = f["hg"], f["aw"]
        data = json.loads(f["report"] or "{}") if f["report"] else {}
        if hg == ag:
            w = pen_winner(data, rng) or ("H" if rng.random() < 0.5 else "A")
            winners.append(f["home_id"] if w == "H" else f["away_id"])
        else:
            winners.append(f["home_id"] if hg > ag else f["away_id"])
    # byes already recorded in standings with w=1
    for r in con.execute("SELECT club_id FROM standings WHERE comp_id=? AND season=? AND stage=? AND w=1",
                         (comp_id, save["season"], stage)).fetchall():
        if r["club_id"] not in winners:
            winners.append(r["club_id"])
    if len(winners) < 2:
        return
    nxt_stage, nxt_base = rounds[cur_idx + 1]
    nxt_date = _cup_round_date(nxt_base, save["season"], ccode["country"])
    rng.shuffle(winners)
    newf = []
    maxid = con.execute("SELECT COALESCE(MAX(id),0) FROM fixtures").fetchone()[0]
    for i in range(0, len(winners) - 1, 2):
        maxid += 1
        newf.append((maxid, comp_id, save["season"], 1, nxt_stage, nxt_date, winners[i], winners[i + 1],
                     None, None, 0, None, None, 1, None, None, None, None, None))
    if newf:
        con.executemany("""INSERT INTO fixtures (id,comp_id,season,round,stage,match_date,home_id,away_id,
            hg,aw,played,agg_h,agg_a,leg,venue,attendance,rating_h,rating_a,report)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", newf)
    if len(winners) % 2:
        con.execute("INSERT OR IGNORE INTO standings VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (comp_id, save["season"], winners[-1], nxt_stage, 1, 1, 0, 0, 0, 0, 3, "", 1))
    if save and save["club_id"] in winners:
        cn = con.execute("SELECT name FROM competitions WHERE id=?", (comp_id,)).fetchone()["name"]
        add_inbox(con, save, "COMPETITION", "ROUTINE", f"{cn}: into the {KO_NAMES.get(nxt_stage, nxt_stage)}",
                  f"You are through to the {KO_NAMES.get(nxt_stage, nxt_stage)} of the {cn}. "
                  f"The draw has been made; fixture scheduled for {nxt_date}.")


def continental_ko(con, save, comp_id, rng):
    """Build knockout rounds from a continental league phase."""
    pend = con.execute("""SELECT COUNT(*) FROM fixtures WHERE comp_id=? AND season=?
        AND stage!='league' AND played=0""", (comp_id, save["season"])).fetchone()[0]
    if pend:
        return                      # current knockout round still to be played
    rows = retable(con, save, comp_id)
    if len(rows) < 24:
        return
    stage_now = con.execute("SELECT MAX(stage) FROM fixtures WHERE comp_id=? AND season=? AND stage!='league'",
                            (comp_id, save["season"])).fetchone()[0]
    order = [r["club_id"] for r in rows]
    maxid = con.execute("SELECT COALESCE(MAX(id),0) FROM fixtures").fetchone()[0]
    dates = {k: _cup_round_date(v, save["season"], "England") for k, v in
             (("KO", "2027-02-17"), ("R16", "2027-03-10"), ("QF", "2027-04-07"),
              ("SF", "2027-04-28"), ("F", "2027-05-29"))}
    if stage_now is None:
        # playoff round: 9-24 seeded pairs
        pairs = list(zip(order[8:16], list(reversed(order[16:24]))))
        st, dt = "KO", dates["KO"]
    elif stage_now == "KO":
        winners = _ko_winners(con, save, comp_id, "KO", rng)
        seeds = order[:8]
        pairs = list(zip(seeds, list(reversed(winners)))) if len(winners) == 8 else list(zip(winners[::2], winners[1::2]))
        st, dt = "R16", dates["R16"]
    elif stage_now == "R16":
        winners = _ko_winners(con, save, comp_id, "R16", rng)
        pairs = list(zip(winners[::2], winners[1::2]))
        st, dt = "QF", dates["QF"]
    elif stage_now == "QF":
        winners = _ko_winners(con, save, comp_id, "QF", rng)
        pairs = list(zip(winners[::2], winners[1::2]))
        st, dt = "SF", dates["SF"]
    elif stage_now == "SF":
        winners = _ko_winners(con, save, comp_id, "SF", rng)
        pairs = list(zip(winners[::2], winners[1::2]))
        st, dt = "F", dates["F"]
    else:
        return
    if not pairs:
        return
    if con.execute("SELECT COUNT(*) FROM fixtures WHERE comp_id=? AND season=? AND stage=?",
                   (comp_id, save["season"], st)).fetchone()[0]:
        return                      # this round already drawn
    newf = []
    for h, a in pairs:
        maxid += 1
        newf.append((maxid, comp_id, save["season"], 1, st, dt, h, a, None, None, 0,
                     None, None, 1, None, None, None, None, None))
    if newf:
        con.executemany("""INSERT INTO fixtures (id,comp_id,season,round,stage,match_date,home_id,away_id,
            hg,aw,played,agg_h,agg_a,leg,venue,attendance,rating_h,rating_a,report)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", newf)


# average annual revenue of a club in each division, relative to tier 3
TIER_INCOME = {1: 9.4, 2: 3.4, 3: 1.0, 4: 0.46, 5: 0.16}


def move_club_league(con, club_id, league_code):
    """Move a club to another division, keeping tier and finances in step."""
    row = con.execute("SELECT tier FROM competitions WHERE code=? AND ctype='league'",
                      (league_code,)).fetchone()
    if not row:
        con.execute("UPDATE clubs SET league=? WHERE id=?", (league_code, club_id))
        return
    c = con.execute("SELECT tier, season_income, season_costs, wage_budget FROM clubs WHERE id=?",
                    (club_id,)).fetchone()
    con.execute("UPDATE clubs SET league=?, tier=? WHERE id=?", (league_code, row["tier"], club_id))
    if not c:
        return
    scale = TIER_INCOME.get(row["tier"], 1.0) / max(0.05, TIER_INCOME.get(c["tier"], 1.0))
    if abs(scale - 1.0) < 0.02:
        return
    con.execute("""UPDATE clubs SET season_income=ROUND(season_income*?,2),
        season_costs=ROUND(season_costs*?,2), wage_budget=ROUND(wage_budget*?,2),
        transfer_budget=ROUND(transfer_budget*?,2) WHERE id=?""",
        (scale, scale, scale, max(0.5, scale * 0.8), club_id))


def _ko_winners(con, save, comp_id, stage, rng):
    fx = con.execute("SELECT * FROM fixtures WHERE comp_id=? AND season=? AND stage=?",
                     (comp_id, save["season"], stage)).fetchall()
    winners = []
    for f in fx:
        if not f["played"]:
            return []
        data = json.loads(f["report"] or "{}") if f["report"] else {}
        if f["hg"] == f["aw"]:
            w = pen_winner(data, rng) or ("H" if rng.random() < 0.5 else "A")
            winners.append(f["home_id"] if w == "H" else f["away_id"])
        else:
            winners.append(f["home_id"] if f["hg"] > f["aw"] else f["away_id"])
    return winners


# --------------------------------------------------------- human match engine
def _setup_human_match(con, save, fx, rng=None, custom_lineup=None):
    """Build both teams and start the match simulation.

    Returns (runner, ctx) or (None, None) if the fixture cannot be played.
    """
    rng = rng or random.Random()
    cid = save["club_id"]
    cur = con.execute("SELECT played FROM fixtures WHERE id=?", (fx["id"],)).fetchone()
    if cur and cur["played"]:
        return None, None
    is_home = fx["home_id"] == cid
    opp_id = fx["away_id"] if is_home else fx["home_id"]
    players = load_players(con, cid)
    tac = get_tactics(con, save)
    selected = custom_lineup or json.loads(save["flags"].get("selected_xi") or "[]")
    if selected and len(selected) == 11:
        xi, bench = _lineup_from_selection(players, selected, tac)
    else:
        xi, bench = M.build_lineup(players, tac)
    if len(xi) < 11:
        return None, None
    hrating = M.team_rating(xi, tac)
    # opposition
    opp_tac = ai_tactics(con, opp_id)
    opp_players = load_players(con, opp_id)
    oxi, obench = M.build_lineup(opp_players, opp_tac)
    if len(oxi) < 11:
        opp_rating = club_strength(con, opp_id, save)
        oxi = []
    else:
        opp_rating = M.team_rating(oxi, opp_tac)
    diff = DIFFICULTY.get(save["career"]["difficulty"], DIFFICULTY["realistic"])
    opp_rating = dict(opp_rating)
    opp_rating["attack"] *= diff["ai_strength"]
    opp_rating["defence"] *= diff["ai_strength"]
    ctype = fx.get("ctype") or "league"
    weather = M.make_weather(rng, d(save["date"]).month)
    ref = M.make_referee(rng)
    home = dict(name=(club(con, cid) or {}).get("name", "Home"), xi=xi, bench=bench, rating=hrating,
                human=is_home)
    away = dict(name=(club(con, opp_id) or {}).get("name", "Away"), xi=oxi, bench=obench,
                rating=opp_rating, human=not is_home)
    if not is_home:
        home, away = away, home
    runner = M.MatchRunner(home, away, rng=rng, home_adv=True, weather=weather, referee=ref,
                           competition=("cup" if ctype in ("cup", "continental") and
                                        (fx.get("stage") not in ("league",)) else "league"),
                           extra_time_allowed=ctype in ("cup", "continental") and fx.get("stage") != "league")
    runner.run_first_half()
    ctx = dict(cid=cid, is_home=is_home, opp_id=opp_id, players=players, tac=tac, xi=xi, bench=bench,
               hrating=hrating, oxi=oxi, ctype=ctype, rng=rng)
    return runner, ctx


def begin_human_match(con, save, fx, rng=None, custom_lineup=None):
    """Kick the match off and pause at half-time. Returns (runner, ctx, halftime_state)."""
    runner, ctx = _setup_human_match(con, save, fx, rng=rng, custom_lineup=custom_lineup)
    if runner is None:
        return None, None, None
    return runner, ctx, runner.halftime_state()


def finish_human_match(con, save, fx, runner, ctx, halftime=None):
    """Apply the half-time decisions, play the second half and process the result."""
    runner.apply_halftime(halftime or {})
    runner.run_second_half()
    return _finish_human_match(con, save, fx, ctx, runner.finalize())


def play_human_match(con, save, fx, mode="key", rng=None, custom_lineup=None, halftime=None,
                     runner=None, ctx=None):
    """Play one of the human's matches and write everything back to the world.

    Pass runner/ctx (from begin_human_match) to resume a match that was paused
    at half-time; otherwise the match is simulated in one go.
    """
    if runner is None:
        runner, ctx = _setup_human_match(con, save, fx, rng=rng, custom_lineup=custom_lineup)
        if runner is None:
            return None
        runner.apply_halftime(halftime or {})
        runner.run_second_half()
    result = runner.finalize() if runner is not None else None
    return _finish_human_match(con, save, fx, ctx, result, mode=mode)


def _finish_human_match(con, save, fx, ctx, result, mode="key"):
    """Post-match processing: player updates, cards, injuries, morale, board."""
    cid = ctx["cid"]; is_home = ctx["is_home"]; players = ctx["players"]; tac = ctx["tac"]
    hrating = ctx["hrating"]; oxi = ctx["oxi"]; ctype = ctx["ctype"]; rng = ctx["rng"]
    if ctype == "friendly":
        result["extra_time"] = None; result["penalties"] = None
    # determine final score incl. pens
    hg, ag = result["home_goals"], result["away_goals"]
    my_goals, opp_goals = (hg, ag) if is_home else (ag, hg)
    res = "W" if my_goals > opp_goals else ("D" if my_goals == opp_goals else "L")
    # ---------------------------------------------------- apply to my players
    mine = result["xi_home"] if is_home else result["xi_away"]
    ratings = result["ratings_home"] if is_home else result["ratings_away"]
    mins = result["mins_home"] if is_home else result["mins_away"]
    goals_p = result["goals_home"] if is_home else result["goals_away"]
    assists_p = result["assists_home"] if is_home else result["assists_away"]
    shots_p = result["shots_home"] if is_home else result["shots_away"]
    xg_p = result["xg_home"] if is_home else result["xg_away"]
    pmap = {p["id"]: p for p in players}
    starters = {m["pid"] for m in mine[:11]}
    # subs that came on
    subs = result["subs_home"] if is_home else result["subs_away"]
    sub_on = {s[1]: s[2] for s in subs}
    for i, m in enumerate(mine):
        p = pmap.get(m["pid"])
        if not p:
            continue
        mins_played = mins[i] if i < len(mins) else 0
        if p["id"] in sub_on:
            mins_played = max(mins_played, 90 - sub_on[p["id"]])
        rat = ratings[i] if i < len(ratings) else 6.3
        fatigue_add = 8 + mins_played * 0.30 + (6 if fx.get("stage") in ("SF", "F") else 0)
        if ctype == "friendly":
            fatigue_add *= 0.5
        sharp_add = min(14, 2 + mins_played * 0.13)
        fitness_delta = -0.8 + mins_played * 0.035
        new_fit = max(35, min(100, p["fitness"] + fitness_delta))
        morale_d = 0
        if rat >= 8.0:
            morale_d = 7
        elif rat >= 7.0:
            morale_d = 4
        elif rat >= 6.4:
            morale_d = 1
        elif rat < 5.8:
            morale_d = -3
        result_side = "W" if my_goals > opp_goals else ("D" if my_goals == opp_goals else "L")
        morale_d += {"W": 6, "D": 0, "L": -5}[result_side]
        if mins_played == 0:
            morale_d -= 3
        con.execute("""UPDATE players SET fitness=?, fatigue=?, sharpness=?,
            morale=?, form=?, apps=apps+?, minutes=minutes+?, goals=goals+?, assists=assists+?,
            avg_rating=? WHERE id=?""",
                    (round(new_fit, 1), round(min(100, p["fatigue"] + fatigue_add), 1),
                     round(min(100, p["sharpness"] + sharp_add), 1),
                     round(max(5, min(100, p["morale"] + morale_d)), 1),
                     round(max(-2.5, min(2.5, p["form"] * 0.75 +
                          (rat - 6.6) * (0.22 if ctype == "friendly" else 0.42))), 2),
                     1 if mins_played > 0 else 0, mins_played,
                     goals_p[i] if i < len(goals_p) else 0,
                     assists_p[i] if i < len(assists_p) else 0,
                     round(((p["avg_rating"] * p["apps"]) + rat) / max(1, p["apps"] + 1), 2) if p["apps"] else round(rat, 2),
                     p["id"]))
        pmap[p["id"]]["fitness"] = new_fit
    # cards & suspensions
    for ev in result["events"]:
        if ev["side"] == ("H" if is_home else "A"):
            if ev["type"] == "yellow" and ev.get("pid") in pmap:
                con.execute("UPDATE players SET yellow=yellow+1 WHERE id=?", (ev["pid"],))
            if ev["type"] == "red" and ev.get("pid") in pmap:
                ban = 3 if ev.get("reason") == "second yellow" else 4
                con.execute("UPDATE players SET red=red+1, suspended=? WHERE id=?", (ban, ev["pid"]))
    # injuries
    inj_ids = result["injuries_home"] if is_home else result["injuries_away"]
    inj_report = []
    for pid_ in inj_ids:
        p = pmap.get(pid_)
        if not p:
            continue
        sev = _roll_injury(rng, p, save)
        inj_report.append((p["name"], sev[0], sev[1]))
        con.execute("UPDATE players SET condition='injured', injury_name=?, return_date=?, injured_weeks=? WHERE id=?",
                    (sev[0], ds(d(save["date"]) + timedelta(days=sev[1])), max(1, sev[1] // 7), pid_))
    # opposition player fatigue (light touch)
    if oxi:
        other = result["xi_away"] if is_home else result["xi_home"]
        orat = result["ratings_away"] if is_home else result["ratings_home"]
        omins = result["mins_away"] if is_home else result["mins_home"]
        for i, m in enumerate(other):
            mp = omins[i] if i < len(omins) else 0
            con.execute("""UPDATE players SET fitness=MAX(35,fitness-0.7), fatigue=MIN(100,fatigue+8+?*0.28),
                sharpness=MIN(100,sharpness+2+?*0.1), goals=goals+?, assists=assists+?,
                apps=apps+?, minutes=minutes+? WHERE id=?""",
                        (mp, mp,
                         (result["goals_away"] if is_home else result["goals_home"])[i] if i < len(result["goals_away"] if is_home else result["goals_home"]) else 0,
                         (result["assists_away"] if is_home else result["assists_home"])[i] if i < len(result["assists_away"] if is_home else result["assists_home"]) else 0,
                         1 if mp > 0 else 0, mp, m["pid"]))
    # --------------------------------------------------------- team-level
    st = result["stats"]["home"] if is_home else result["stats"]["away"]
    ost = result["stats"]["away"] if is_home else result["stats"]["home"]
    xg = st["xg"]; xga = ost["xg"]
    save["flags"].setdefault("xg_season", 0.0)
    save["flags"].setdefault("xga_season", 0.0)
    save["flags"]["xg_season"] += xg
    save["flags"]["xga_season"] += xga
    # tactical familiarity grows with each match played in same setup
    fam = min(100.0, tac["familiarity"] + 3.2)
    save_tactics(con, save, familiarity=round(fam, 1))
    # identity drift
    ident = tac["identity"]
    ident["possession"] = round(0.9 * ident.get("possession", 50) + 0.1 * result["possession_home" if is_home else "possession_away"], 1)
    ident["pressing"] = round(0.9 * ident.get("pressing", 50) + 0.1 * (30 + hrating["press"] * 45), 1)
    ident["tempo"] = round(0.9 * ident.get("tempo", 50) + 0.1 * (30 + hrating["tempo"] * 45), 1)
    ident["width"] = round(0.9 * ident.get("width", 50) + 0.1 * (30 + hrating["width"] * 55), 1)
    save_tactics(con, save, identity=ident)
    # morale / cohesion
    coh_d = {"W": 3.0, "D": 0.4, "L": -2.4}[res]
    save["flags"]["squad_cohesion"] = max(5, min(100, save["flags"].get("squad_cohesion", 55) + coh_d))
    if ctype != "friendly":
        con.execute("UPDATE players SET morale=MAX(5,MIN(100,morale+?)) WHERE club_id=? AND squad IN ('First Team','Reserve')",
                    ({"W": 4, "D": 0, "L": -4}[res], cid))
    ss = save["season_stats"]
    if ctype != "friendly" and fx.get("comp_id"):
        ss["played"] += 1
        ss[{"W": "won", "D": "drawn", "L": "lost"}[res]] += 1
        ss["gf"] += my_goals; ss["ga"] += opp_goals
    # motm
    best_i = max(range(len(mine)), key=lambda i: (ratings[i] if i < len(ratings) else 0))
    motm = mine[best_i]["pid"]
    home_club = club(con, fx["home_id"]); away_club = club(con, fx["away_id"])
    data = dict(
        ai=False, mode=mode, hg=hg, ag=ag, my_goals=my_goals, opp_goals=opp_goals,
        result=res,
        xg_home=result["stats"]["home"]["xg"], xg_away=result["stats"]["away"]["xg"],
        shots_home=result["stats"]["home"]["shots"], shots_away=result["stats"]["away"]["shots"],
        sot_home=result["stats"]["home"]["sot"], sot_away=result["stats"]["away"]["sot"],
        big_home=result["stats"]["home"]["big"], big_away=result["stats"]["away"]["big"],
        possession_home=result["possession_home"], possession_away=result["possession_away"],
        corners_home=result["stats"]["home"]["corners"], corners_away=result["stats"]["away"]["corners"],
        fouls_home=result["stats"]["home"]["fouls"], fouls_away=result["stats"]["away"]["fouls"],
        yellow_home=result["stats"]["home"]["yellow"], yellow_away=result["stats"]["away"]["yellow"],
        red_home=result["stats"]["home"]["red"], red_away=result["stats"]["away"]["red"],
        saves_home=result["stats"]["home"]["saves"], saves_away=result["stats"]["away"]["saves"],
        events=result["events"], ratings_home=result["ratings_home"], ratings_away=result["ratings_away"],
        xi_home=result["xi_home"], xi_away=result["xi_away"],
        mins_home=result["mins_home"], mins_away=result["mins_away"],
        goals_home=result["goals_home"], goals_away=result["goals_away"],
        assists_home=result["assists_home"], assists_away=result["assists_away"],
        xg_players_home=result["xg_home"], xg_players_away=result["xg_away"],
        shots_players_home=result["shots_home"], shots_players_away=result["shots_away"],
        penalties=result.get("penalties"), extra_time=result.get("extra_time"),
        weather=result["weather"], referee=result["referee"], motm=motm,
        injuries=[{"name": n, "injury": i, "days": dd} for n, i, dd in inj_report],
        home_id=fx["home_id"], away_id=fx["away_id"],
        home_name=home_club["name"], away_name=away_club["name"],
        home_code=home_club["code"], away_code=away_club["code"],
        comp=fx.get("comp_name"), comp_code=fx.get("comp_code") or fx.get("code"),
        code=fx.get("comp_code") or fx.get("code"),
    )
    apply_result(con, save, fx, hg, ag, data, rng)
    save["last_result"] = dict(fixture_id=fx["id"], date=save["date"], comp=fx.get("comp_name"),
                               home=data["home_name"], away=data["away_name"], hg=hg, ag=ag,
                               my_goals=my_goals, opp_goals=opp_goals, result=res,
                               xg=round(xg, 2), xga=round(xga, 2),
                               is_home=is_home, ctype=ctype, motm=motm,
                               stage=fx.get("stage"))
    # board / fan reaction
    _react_to_result(con, save, fx, res, my_goals, opp_goals, xg, xga, ctype)
    data["mode"] = mode
    return data

def _lineup_from_selection(players, selected, tac):
    pmap = {p["id"]: p for p in players}
    formation = C.FORMATIONS.get(tac.get("formation", "4-2-3-1 Wide"), C.FORMATIONS["4-2-3-1 Wide"])
    roles = tac.get("roles", {})
    xi = []
    for i, pid_ in enumerate(selected):
        p = pmap.get(pid_)
        if not p or p["condition"] != "fit" or p["suspended"] > 0:
            continue
        slot = formation[i] if i < len(formation) else "MC"
        r = roles.get(str(i))
        role, duty = (r if isinstance(r, (list, tuple)) else (C.ROLES.get(slot, ["Central Midfielder"])[0], "Support"))
        if role not in C.ROLES.get(slot, [role]):
            role = C.ROLES.get(slot, ["Central Midfielder"])[0]
        xi.append(dict(player=p, slot=slot, role=role, duty=duty))
    used = {x["player"]["id"] for x in xi}
    bench = [p for p in sorted(players, key=lambda x: -x["ca"])
             if p["id"] not in used and p["condition"] == "fit" and p["suspended"] <= 0
             and p["squad"] in ("First Team", "Reserve")][:9]
    return xi, bench


def _roll_injury(rng, p, save):
    diff = DIFFICULTY.get(save["career"]["difficulty"], DIFFICULTY["realistic"])
    types = C.INJURY_TYPES
    weights = []
    for nm, lo, hi, _ in types:
        w = 1.0
        if nm.startswith("Cruciate"):
            w = 0.22
        elif nm.startswith("Knee ligament"):
            w = 0.6
        elif nm in ("Knock", "Muscle fatigue", "Bruised knee"):
            w = 3.2
        elif nm in ("Hamstring strain", "Calf injury", "Thigh strain"):
            w = 2.2
        weights.append(w)
    t = rng.choices(types, weights=weights, k=1)[0]
    days = int(rng.randint(t[1], t[2]) * (0.85 + 0.3 * rng.random()) * diff["injuries"])
    days = max(2, min(340, days))
    return t[0], days


def _react_to_result(con, save, fx, res, my, opp, xg, xga, ctype):
    cid = save["club_id"]
    c = club(con, cid)
    comp_row = comp(con, fx["comp_id"]) if fx["comp_id"] else None
    prestige = comp_row["prestige"] if comp_row else 40
    opp_c = club(con, fx["away_id"] if fx["home_id"] == cid else fx["home_id"])
    exp = 0.5
    if opp_c:
        exp = 0.5 + (c["rep"] - opp_c["rep"]) / 90.0
    exp = max(0.12, min(0.88, exp))
    got = {"W": 1.0, "D": 0.5, "L": 0.0}[res]
    weight = 2.3 + prestige / 90.0
    delta = (got - exp) * weight
    if ctype == "friendly":
        delta *= 0.12
    board = save["board"]
    board["confidence"] = max(0, min(100, board["confidence"] + delta))
    fans = save["fans"]
    fans["sentiment"] = max(0, min(100, fans["sentiment"] + delta * 1.5))
    # style appreciation: fans of attacking clubs dislike low-xg wins a bit less
    if ctype != "friendly":
        rep = save["career"]["reputation"]
        save["career"]["reputation"] = max(1, min(95, rep + delta * 0.16))
    save["flags"]["last_delta"] = round(delta, 2)


# ------------------------------------------------------------------ day tick
def tick_day(con, save, rng, auto_human=False):
    """Advance the world by one day. Returns list of notable events.

    auto_human: play the human club's fixtures for this day automatically instead
    of leaving them for the manager (used when advancing past match days).
    """
    dt = d(save["date"]) + timedelta(days=1)
    save["date"] = ds(dt)
    events = []
    diff = DIFFICULTY.get(save["career"]["difficulty"], DIFFICULTY["realistic"])
    cid = save["club_id"]
    if save["flags"].get("unemployed") or not cid:
        return job_market_tick(con, save, dt, rng, events)
    # ---- my squad: condition, injuries, suspensions, contracts
    my = load_players(con, cid)
    has_match = bool(fixtures_on(con, dt, cid))
    played_yesterday = bool(con.execute(
        "SELECT 1 FROM fixtures WHERE (home_id=? OR away_id=?) AND match_date=? AND played=1",
        (cid, cid, ds(dt - timedelta(days=1)))).fetchone())
    weekday = dt.weekday()
    session = con.execute("SELECT session, focus FROM training WHERE club_id=? AND day=?",
                          (cid, weekday)).fetchone()
    session = (session["session"] if session else "Rest")
    if has_match and session not in ("Match Preparation", "Rest", "Recovery"):
        session = "Match Preparation"
    if played_yesterday and session not in ("Recovery", "Rest"):
        session = "Recovery"
    if in_int_break(dt, save["season"]):
        session = "Rest"
    sdef = C.TRAINING_SESSIONS.get(session, C.TRAINING_SESSIONS["Rest"])
    coaching = con.execute("""SELECT AVG(technical) t, AVG(tactical) ta, AVG(fitness) f,
        AVG(mental) m, AVG(youth) y FROM staff WHERE club_id=? AND role IN
        ('First-Team Coach','Fitness Coach','Assistant Manager','Goalkeeping Coach')""", (cid,)).fetchone()
    cq = ((coaching["t"] or 8) + (coaching["ta"] or 8) + (coaching["f"] or 8)) / 3.0
    c = club(con, cid)
    cq *= (0.75 + c["facilities"] / 60.0)
    focus = session and con.execute("SELECT focus FROM training WHERE club_id=? AND day=?",
                                    (cid, weekday)).fetchone()
    focus_pos = (focus["focus"] if focus else "") or ""
    for p in my:
        if p["squad"] == "Youth" and rng.random() > 0.5:
            pass
        new = {}
        # fatigue & fitness
        fat = p["fatigue"] + sdef["fatigue"] * (0.6 if p["squad"] in ("U21", "Youth") else 1.0)
        fat = max(0, min(100, fat))
        # Fitness: training gain scaled by coaching quality, minus a load cost that
        # grows with the fatigue the session just produced. Resting days only cost
        # a little, so a squad in a normal week settles around 88-95.
        cqf = max(0.5, min(1.6, cq / 10.0))
        load = max(0.0, sdef["fatigue"])
        fit = (p["fitness"] + sdef["fitness"] * cqf
               - 0.075 * max(0.0, fat - 12.0) - 0.28 - 0.022 * load)
        fit = max(30, min(100, fit))
        sharp = (p["sharpness"] + sdef["sharpness"] *
                 (0.8 if p["squad"] in ("First Team", "Reserve") else 0.5))
        sharp = max(0, min(100, sharp))
        fat = max(0.0, fat - 0.16 * fat)                 # passive recovery
        if p["minutes"] == 0 and p["apps"] == 0:
            sharp = max(0.0, sharp - 0.02 * max(0.0, sharp - 55.0))
        new["fatigue"] = round(fat, 1)
        new["fitness"] = round(fit, 1)
        new["sharpness"] = round(sharp, 1)
        # injuries recover
        if p["condition"] == "injured":
            if p["return_date"] and dt >= d(p["return_date"]):
                new["condition"] = "fit"
                new["injury_name"] = ""
                new["fitness"] = max(62, fit * 0.82)
                new["sharpness"] = max(30, sharp * 0.7)
                events.append(dict(kind="medical", text=f"{p['name']} is available again after {p['injury_name']}.",
                                   pid=p["id"]))
            else:
                new["fatigue"] = max(0, fat * 0.8)
        if p["suspended"] and p["suspended"] > 0:
            new["suspended"] = max(0, p["suspended"] - 1)
        # training injuries
        if p["condition"] == "fit" and p["squad"] in ("First Team", "Reserve"):
            risk = 0.0016 * sdef["injury"] * (1 + fat / 90.0) * (1.6 - fit / 100.0) * diff["injuries"]
            if rng.random() < risk:
                nm, days = _roll_injury(rng, p, save)
                new["condition"] = "injured"
                new["injury_name"] = nm
                new["return_date"] = ds(dt + timedelta(days=days))
                new["injured_weeks"] = max(1, days // 7)
                events.append(dict(kind="medical", text=f"{p['name']} suffered a {nm} in training. Out ~{days} days.",
                                   pid=p["id"], priority="IMPORTANT"))
                add_inbox(con, save, "MEDICAL", "IMPORTANT", f"Injury: {p['name']}",
                          f"{p['name']} picked up a {nm} in {session.lower()} training.\n"
                          f"Expected return: {new['return_date']} ({days} days).")
        # morale drift toward happiness baseline
        mor = p["morale"]
        happy = p["happiness"]
        mor += (happy - mor) * 0.02 + rng.gauss(0, 0.5)
        # playing time satisfaction
        if (p["minutes_expected"] or 0) > 0 and p["squad"] == "First Team":
            got = p["minutes"] or 0
            season_weeks = max(6, (dt - d(str(save["season"]) + "-08-15")).days / 7.0)
            ratio = (got / 90.0) / season_weeks
            # a "Star Player" is expected to feature in ~78% of weeks, a backup in ~26%
            want = min(1.0, C.PROMISE_LEVEL.get(p["promise"] or "Squad Rotation", 3) / 6.0 * 0.78)
            gap = ratio - want
            happy_d = max(-0.22, min(0.22, gap * 0.8))
            new["happiness"] = round(max(12, min(100, p["happiness"] + happy_d)), 1)
            complained = save["flags"].setdefault("pt_complaints", {})
            last = complained.get(str(p["id"]))
            quiet = (not last) or (dt - d(last)).days > 35
            if quiet and new["happiness"] < 26 and gap < -0.12 and p["ca"] > 10:
                complained[str(p["id"])] = ds(dt)
                want_txt = p["promise"] or "his promised role"
                events.append(dict(kind="player",
                                   text=f"{p['name']} is unhappy with his playing time "
                                        f"({p['minutes'] or 0} mins against a {want_txt} promise).",
                                   pid=p["id"], priority="IMPORTANT"))
                add_inbox(con, save, "SQUAD", "IMPORTANT", f"Playing time: {p['name']}",
                          f"{p['name']} has asked to speak to you about his playing time.\n\n"
                          f"He was promised: {want_txt}\n"
                          f"Minutes this season: {p['minutes'] or 0} ({(p['apps'] or 0)} appearances)\n"
                          f"Happiness: {new['happiness']:.0f}/100\n\n"
                          f"Options: give him more game time, talk to him about his role, "
                          f"or accept a transfer request.",
                          payload={"screen": "squad", "pid": p["id"], "action": "promise"})
        new["morale"] = round(max(3, min(100, mor)), 1)
        con.execute("""UPDATE players SET fatigue=?, fitness=?, sharpness=?, morale=?, happiness=?,
            condition=?, injury_name=?, return_date=?, suspended=?, injured_weeks=? WHERE id=?""",
                    (new["fatigue"], new["fitness"], new["sharpness"], new["morale"],
                     new.get("happiness", p["happiness"]), new.get("condition", p["condition"]),
                     new.get("injury_name", p["injury_name"]), new.get("return_date", p["return_date"]),
                     new.get("suspended", p["suspended"]), new.get("injured_weeks", p["injured_weeks"]),
                     p["id"]))
        # attribute development from training
        if sdef["attrs"] and p["squad"] in ("First Team", "Reserve", "U21") and rng.random() < 0.35:
            _train_attrs(con, p, sdef, cq, rng, focus_pos)
    # ---- scouting tasks
    _tick_scouting(con, save, rng, events)
    # ---- transfer market AI
    if window_state(dt, save["season"]):
        _market_day(con, save, rng, events)
    _tick_offers(con, save, rng, events)
    # ---- world: AI clubs play their fixtures
    played = _simulate_day_matches(con, save, dt, rng)
    # ---- the human's own matches (only when the caller is auto-playing them)
    if auto_human and cid and not save["flags"].get("unemployed"):
        for f in fixtures_on(con, dt, cid):
            data = play_human_match(con, save, dict(f), mode="instant", rng=rng)
            if not data:
                continue
            played += 1
            comp_name = f.get("comp_name") or "Friendly"
            events.append(dict(
                kind="result",
                priority="ROUTINE" if f.get("ctype") == "friendly" else "IMPORTANT",
                text=f"{data['home_name']} {data['hg']}-{data['ag']} {data['away_name']} "
                     f"({comp_name}) — {data['result']}",
                comp=comp_name, result=data["result"], fixture_id=f["id"]))
    # ---- cup progression checks
    for r in con.execute("SELECT DISTINCT comp_id, stage FROM fixtures WHERE match_date<=? AND comp_id IN "
                         "(SELECT id FROM competitions WHERE ctype IN ('cup','continental'))",
                         (ds(dt),)).fetchall():
        pass
    _check_competitions(con, save, rng)
    # ---- weekly events
    if dt.weekday() == 0:
        _weekly(con, save, rng, events)
    # ---- monthly
    if dt.day == 1:
        _monthly(con, save, rng, events)
    # ---- season end
    if not save["flags"].get(f"season_done_{save['season']}"):
        _last = con.execute("""SELECT MAX(f.match_date) FROM fixtures f JOIN competitions k ON k.id=f.comp_id
            WHERE f.season=? AND k.ctype!='friendly'""", (save["season"],)).fetchone()[0]
        if _last and ds(dt) >= _last:
            _season_end(con, save, rng, events)
            save["flags"][f"season_done_{save['season'] - 1}"] = True
    bump()
    return events


def _train_attrs(con, p, sdef, cq, rng, focus_pos):
    """Apply a small amount of attribute development from a training session."""
    if p["age"] > 33:
        return
    vec = unpack_attrs(p["attrs"]) if isinstance(p["attrs"], str) else dict(p["_vec"])
    growth = (0.05 + (cq - 8) * 0.012) * (1.25 if p["age"] < 21 else (1.0 if p["age"] < 26 else 0.55))
    growth *= 0.5 + p["professionalism"] / 22.0
    headroom = max(0.0, p["pa"] - p["ca"])
    growth *= min(1.0, 0.25 + headroom / 2.5)
    if growth <= 0.005:
        return
    changed = False
    for attr, amt in sdef["attrs"].items():
        if attr not in vec:
            continue
        if focus_pos and p["pos"] != focus_pos:
            amt *= 0.35
        if rng.random() < amt * growth:
            if vec[attr] < 20:
                vec[attr] += 1
                changed = True
    if changed:
        new_ca = compute_ca(vec)
        con.execute("UPDATE players SET attrs=?, ca=? WHERE id=?",
                    (pack_attrs(vec), round(min(new_ca, p["pa"] + 0.5), 2), p["id"]))
        p["_vec"] = vec


def _simulate_day_matches(con, save, dt, rng, include_human=False):
    """Simulate every non-human fixture on this date."""
    cid = save["club_id"]
    rows = con.execute("""SELECT f.*, k.ctype, k.code AS comp_code, k.name AS comp_name, k.prestige
        FROM fixtures f LEFT JOIN competitions k ON k.id=f.comp_id
        WHERE f.match_date=? AND f.played=0""", (ds(dt),)).fetchall()
    n = 0
    for r in rows:
        fx = dict(r)
        if fx["home_id"] == cid or fx["away_id"] == cid:
            if not include_human:
                continue  # human match handled interactively
        ctype = fx.get("ctype") or "league"
        diff = save["career"]["difficulty"]
        if ctype == "friendly":
            if rng.random() < 0.5:
                con.execute("UPDATE fixtures SET played=1, hg=NULL, aw=NULL WHERE id=?", (fx["id"],))
                continue
        hg, ag, data = ai_sim(con, save, fx, rng, diff)
        data["rating_h"] = None
        data["rating_a"] = None
        apply_result(con, save, fx, hg, ag, data, rng)
        # distribute goals to AI players
        for side, team_id, gcount in (("H", fx["home_id"], hg), ("A", fx["away_id"], ag)):
            if gcount <= 0:
                continue
            rows2 = con.execute("""SELECT id, pos, ca, attrs FROM players WHERE club_id=?
                AND squad IN ('First Team','Reserve') AND condition='fit' ORDER BY ca DESC LIMIT 14""",
                (team_id,)).fetchall()
            if not rows2:
                continue
            ws = []
            for p in rows2:
                v = unpack_attrs(p["attrs"])
                w = (0.15 + v.get("finishing", 5) / 22.0) * (1.5 if p["pos"] in ("ST", "AMC") else 1.0)
                if p["pos"] in ("DC", "GK"):
                    w *= 0.12
                ws.append(max(0.01, w))
            for _ in range(gcount):
                idx = rng.choices(range(len(rows2)), weights=ws, k=1)[0]
                con.execute("UPDATE players SET goals=goals+1, apps=apps+1, minutes=minutes+80, form=MIN(2.5,form+0.25), sharpness=MIN(100,sharpness+6) WHERE id=?",
                            (rows2[idx]["id"],))
                # assist
                if rng.random() < 0.75:
                    j = rng.choices(range(len(rows2)), weights=[max(0.01, (0.2 + unpack_attrs(x["attrs"]).get("passing", 5) / 20.0)) if x["id"] != rows2[idx]["id"] else 0.0001 for x in rows2], k=1)[0]
                    con.execute("UPDATE players SET assists=assists+1 WHERE id=?", (rows2[j]["id"],))
        # squad-wide fatigue/sharpness for participants
        for team_id in (fx["home_id"], fx["away_id"]):
            con.execute("""UPDATE players SET fatigue=MIN(100, fatigue+18), sharpness=MIN(100,sharpness+7),
                apps=apps+CASE WHEN squad IN ('First Team','Reserve') THEN 0 ELSE 0 END
                WHERE club_id=? AND squad IN ('First Team','Reserve')""", (team_id,))
        n += 1
    return n


def _check_competitions(con, save, rng):
    dt = d(save["date"])
    rows = con.execute("""SELECT DISTINCT f.comp_id, f.stage, k.ctype, k.code
        FROM fixtures f JOIN competitions k ON k.id=f.comp_id
        WHERE k.ctype IN ('cup','continental') AND f.season=?""", (save["season"],)).fetchall()
    for r in rows:
        comp_id, stage, ctype, code = r["comp_id"], r["stage"], r["ctype"], r["code"]
        unplayed = con.execute("SELECT COUNT(*) FROM fixtures WHERE comp_id=? AND season=? AND stage=? AND played=0",
                               (comp_id, save["season"], stage)).fetchone()[0]
        if unplayed:
            continue
        if ctype == "cup":
            rounds = CUP_ROUNDS.get(code)
            if not rounds:
                continue
            idx = [i for i, (s, _) in enumerate(rounds) if s == stage]
            if not idx:
                continue
            if idx[0] == len(rounds) - 1:
                _cup_final_award(con, save, comp_id, stage, rng)
            else:
                advance_cup(con, save, comp_id, rng)
        elif ctype == "continental":
            if stage == "league":
                md = con.execute("SELECT MAX(round) FROM fixtures WHERE comp_id=? AND season=? AND stage='league'",
                                 (comp_id, save["season"])).fetchone()[0]
                played_all = con.execute("SELECT COUNT(*) FROM fixtures WHERE comp_id=? AND season=? AND stage='league' AND played=1",
                                         (comp_id, save["season"])).fetchone()[0]
                total = con.execute("SELECT COUNT(*) FROM fixtures WHERE comp_id=? AND season=? AND stage='league'",
                                    (comp_id, save["season"])).fetchone()[0]
                if played_all == total:
                    continental_ko(con, save, comp_id, rng)
            else:
                if stage == "F":
                    _cup_final_award(con, save, comp_id, stage, rng)
                else:
                    continental_ko(con, save, comp_id, stage and rng)


def _cup_final_award(con, save, comp_id, stage, rng):
    key = f"awarded_{comp_id}"
    if save["flags"].get(key):
        return
    save["flags"][key] = True
    fx = con.execute("SELECT * FROM fixtures WHERE comp_id=? AND season=? AND stage=? AND played=1",
                     (comp_id, save["season"], stage)).fetchall()
    if not fx:
        return
    f = fx[-1]
    data = json.loads(f["report"] or "{}") if f["report"] else {}
    if f["hg"] == f["aw"]:
        w = pen_winner(data, rng) or ("H" if rng.random() < 0.5 else "A")
        winner = f["home_id"] if w == "H" else f["away_id"]
    else:
        winner = f["home_id"] if f["hg"] > f["aw"] else f["away_id"]
    loser = f["away_id"] if winner == f["home_id"] else f["home_id"]
    cname = con.execute("SELECT name FROM competitions WHERE id=?", (comp_id,)).fetchone()["name"]
    wname = club(con, winner)["name"]
    con.execute("INSERT INTO history (season,comp_id,club_id,pos,note,trophy) VALUES (?,?,?,?,?,?)",
                (save["season"], comp_id, winner, 1, cname, cname))
    con.execute("INSERT INTO history (season,comp_id,club_id,pos,note,trophy) VALUES (?,?,?,?,?,?)",
                (save["season"], comp_id, loser, 2, cname + " runners-up", ""))
    add_news(con, save, "CUP", f"{wname} win the {cname}.")
    # prize money
    prize = {98: 90.0, 82: 30.0, 70: 12.0}.get(con.execute("SELECT prestige FROM competitions WHERE id=?", (comp_id,)).fetchone()["prestige"], 6.0)
    con.execute("UPDATE clubs SET cash=cash+?, balance=balance+? WHERE id=?", (prize, prize, winner))
    con.execute("UPDATE clubs SET cash=cash+?, balance=balance+? WHERE id=?", (prize * 0.4, prize * 0.4, loser))
    con.execute("UPDATE clubs SET reputation=MIN(97,reputation+?) WHERE id=?", (1.5 if prize > 40 else 0.7, winner))
    if winner == save["club_id"]:
        save["career"]["trophies"].append({"season": save["season"], "comp": cname, "type": "cup"})
        add_inbox(con, save, "BOARD", "URGENT", f"{cname} champions!",
                  f"You have won the {cname}. Prize money of {money(prize)} has been added to the club account.",
                  payload={"screen": "career"})


def _weekly(con, save, rng, events):
    """Monday: form regeneration, board/fan drift, staff, contracts."""
    cid = save["club_id"]
    # form regression
    con.execute("UPDATE players SET form=form*0.86 WHERE club_id=?", (cid,))
    # tactical familiarity slow decay if unused / grows
    tac = get_tactics(con, save)
    save["flags"]["identity_days"] = save["flags"].get("identity_days", 0) + 7
    # contracts expiring soon
    soon = con.execute("""SELECT * FROM players WHERE club_id=? AND contract_end<=? AND age>17
        AND squad IN ('First Team','Reserve')""", (cid, _season_contract_end(save))).fetchall()
    for p in soon:
        if rng.random() < 0.14 and not save["flags"].get(f"renew_asked_{p['id']}"):
            save["flags"][f"renew_asked_{p['id']}"] = True
            add_inbox(con, save, "CONTRACT", "IMPORTANT", f"Contract: {p['name']}",
                      f"{p['name']}'s contract expires in June 2027.\n"
                      f"Current wage: €{p['wage']:.1f}k/week. Estimated value: {money(p['value'])}.\n"
                      f"His agent is open to talks.",
                      payload={"screen": "player", "pid": p["id"], "action": "contract"})
    # world: manager sackings
    _world_managers(con, save, rng, events)
    # board confidence drift
    board = save["board"]
    pos_info = _league_position(con, save)
    if pos_info:
        target = None
        for o in board["objectives"]:
            if o["type"] == "league":
                target = o.get("target_pos")
        if target:
            gap = pos_info["pos"] - target
            drift = -0.30 * gap if pos_info["played"] >= 6 else 0
            board["confidence"] = max(0, min(100, board["confidence"] + drift * 0.06))
    fans = save["fans"]
    fans["sentiment"] = max(0, min(100, fans["sentiment"] + (board["confidence"] - fans["sentiment"]) * 0.04))


def _league_position(con, save, season=None):
    if not save.get("club_id"):
        return None
    season = season or save["season"]
    c = club(con, save["club_id"])
    comp_row = con.execute("SELECT id FROM competitions WHERE code=?", (c["league"],)).fetchone()
    r = None
    if comp_row:
        r = con.execute("""SELECT * FROM standings WHERE comp_id=? AND season=? AND club_id=?
            AND stage='league'""", (comp_row["id"], season, save["club_id"])).fetchone()
    if not r:
        # the club may have changed division since (promotion / relegation / new job)
        r = con.execute("""SELECT * FROM standings WHERE season=? AND club_id=? AND stage='league'
            AND comp_id IN (SELECT id FROM competitions WHERE ctype='league')
            ORDER BY p DESC, pts DESC LIMIT 1""", (season, save["club_id"])).fetchone()
    if not r:
        return None
    size = con.execute("SELECT COUNT(*) FROM standings WHERE comp_id=? AND season=? AND stage='league'",
                       (r["comp_id"], season)).fetchone()[0]
    return dict(pos=r["pos"], pts=r["pts"], played=r["p"], gd=r["gf"] - r["ga"], size=size,
                comp_id=r["comp_id"])


def _world_managers(con, save, rng, events):
    """AI clubs sack/hire managers based on results and board patience."""
    rows = con.execute("""SELECT m.id mid, m.name, m.reputation, m.club_id, c.name club_name, c.rep,
        c.league, s.pts, s.p played, s.pos, k.id league_id
        FROM managers m JOIN clubs c ON c.id=m.club_id
        LEFT JOIN competitions k ON k.code=c.league
        LEFT JOIN standings s ON s.club_id=c.id AND s.season=? AND s.stage='league'
        WHERE m.human=0""", (save["season"],)).fetchall()
    for r in rows:
        if not r["played"] or r["played"] < 10:
            continue
        r = dict(r)
        r["n"] = con.execute("SELECT COUNT(*) n FROM standings WHERE comp_id=? AND season=?",
                             (r["league_id"], save["season"])).fetchone()["n"] or 20
        pos_frac = (r["pos"] or r["n"]) / max(1, r["n"])
        elite = r["rep"] >= 75
        thresh = 0.90 if elite else 0.80
        if pos_frac < thresh:
            continue
        chance = 0.006 if elite else 0.012
        if r["played"] < 14:
            chance *= 0.4
        if rng.random() > chance:
            continue
        if True:
            con.execute("DELETE FROM managers WHERE id=?", (r["mid"],))
            con.execute("DELETE FROM tactics WHERE club_id=? AND is_human=0", (r["club_id"],))
            add_news(con, save, "MANAGERS",
                     f"{r['club_name']} have sacked {r['name']}. The club is now seeking a replacement.",
                     club_id=r["club_id"])
            _maybe_offer_job(con, save, r["club_id"], rng)


def _monthly(con, save, rng, events):
    """1st of month: finances, development, board review, market news."""
    cid = save["club_id"]
    c = club(con, cid)
    dt = d(save["date"])
    # wages paid (monthly = 13/3 of weekly)
    bill = con.execute("SELECT COALESCE(SUM(wage),0) w FROM players WHERE club_id=?", (cid,)).fetchone()["w"]
    staff_w = con.execute("SELECT COALESCE(SUM(wage),0) w FROM staff WHERE club_id=?", (cid,)).fetchone()["w"]
    wage_cost = (bill + staff_w) * 52.0 / 12.0 / 1000.0  # €m
    revenue = c["season_income"] / 12.0
    # non-wage running costs: stadium ops, travel, admin, academy — scaled to the
    # division the club plays in, floored so tiny clubs still pay their way
    nonwage = max(c["season_income"] * 0.18, (c["season_costs"] or 0) - (c["wage_budget"] or 0))
    oper = nonwage / 12.0
    interest = c["debt"] * 0.004
    net = revenue - wage_cost - oper - interest
    con.execute("UPDATE clubs SET cash=cash+?, balance=balance+?, wage_bill=? WHERE id=?",
                (round(net, 3), round(net, 3), round(bill * 52 / 1000, 2), cid))
    con.execute("""CREATE TABLE IF NOT EXISTS finances (id INTEGER PRIMARY KEY, club_id INT,
        season INT, month TEXT, income REAL, wages REAL, other REAL, interest REAL,
        net REAL, cash REAL)""")
    newcash = con.execute("SELECT cash FROM clubs WHERE id=?", (cid,)).fetchone()["cash"]
    con.execute("""INSERT INTO finances (club_id,season,month,income,wages,other,interest,net,cash)
        VALUES (?,?,?,?,?,?,?,?,?)""",
        (cid, save["season"], dt.strftime("%b %Y"), round(revenue, 3), round(wage_cost, 3),
         round(oper, 3), round(interest, 3), round(net, 3), round(newcash, 3)))
    save["flags"]["fin_history"] = (save["flags"].get("fin_history") or [])[-23:] + [
        {"month": dt.strftime("%b %Y"), "income": round(revenue, 2), "wages": round(wage_cost, 2),
         "other": round(oper, 2), "net": round(net, 2), "cash": round(newcash, 2)}]
    add_inbox(con, save, "FINANCE", "ROUTINE", f"Monthly accounts — {dt.strftime('%B %Y')}",
              f"Revenue: {money(revenue)}\nWages (players & staff): {money(wage_cost)}\n"
              f"Running costs: {money(oper)}\nInterest: {money(interest)}\nNet: {money(net)}\n"
              f"Cash: {money(c['cash'] + net)}",
              payload={"screen": "finances"})
    # player development tick
    _development_tick(con, save, rng, events)
    # board review
    _board_review(con, save, rng, events)
    # values drift with form
    con.execute("""UPDATE players SET value=ROUND(MAX(0.01, value*(1+MIN(0.14,MAX(-0.14,form*0.05)))),2)
        WHERE club_id=?""", (cid,))
    # world transfers between AI clubs
    _world_transfer_activity(con, save, rng, events, volume=6)


def _development_tick(con, save, rng, events):
    cid = save["club_id"]
    c = club(con, cid)
    coaching = con.execute("""SELECT AVG(technical) t, AVG(tactical) ta, AVG(mental) m, AVG(youth) y
        FROM staff WHERE club_id=?""", (cid,)).fetchone()
    cq = ((coaching["t"] or 8) * 0.4 + (coaching["ta"] or 8) * 0.3 + (coaching["m"] or 8) * 0.3)
    fac = c["facilities"]
    ps = load_players(con, cid)
    for p in ps:
        if p["age"] >= 30:
            # decline
            if p["age"] >= 33 and rng.random() < 0.30 * (p["age"] - 31) / 4.0:
                vec = p["_vec"]
                k = rng.choice(["pace", "acceleration", "agility", "stamina", "strength"])
                if vec.get(k, 5) > 3:
                    vec[k] -= 1
                    con.execute("UPDATE players SET attrs=?, ca=? WHERE id=?",
                                (pack_attrs(vec), round(compute_ca(vec), 2), p["id"]))
            continue
        if p["ca"] >= p["pa"] - 0.15:
            continue
        chance = 0.14
        chance *= (0.6 + cq / 16.0) * (0.7 + fac / 26.0)
        if p["age"] < 21:
            chance *= 1.5
        if p["minutes"] > 900:
            chance *= 1.35
        elif p["minutes"] < 200 and p["age"] > 20:
            chance *= 0.55
        chance *= (0.6 + p["professionalism"] / 24.0)
        if p["condition"] == "injured":
            chance *= 0.2
        if rng.random() < chance:
            vec = p["_vec"]
            n_up = rng.randint(1, 2) if p["age"] < 21 else 1
            keys = [k for k in vec if vec[k] < 20]
            prof_keys = [k for k in keys if k in M.POS_WEIGHTS[M.POS_KEY.get(p["pos"], "MID")]]
            for _ in range(n_up):
                if prof_keys and rng.random() < 0.75:
                    k = rng.choice(prof_keys)
                elif keys:
                    k = rng.choice(keys)
                else:
                    break
                vec[k] += 1
            new_ca = min(compute_ca(vec), p["pa"])
            con.execute("UPDATE players SET attrs=?, ca=?, value=? WHERE id=?",
                        (pack_attrs(vec), round(new_ca, 2),
                         round(value_of(new_ca, p["pa"], p["age"], p["pos"], c["rep"],
                                        max(1, (int(p["contract_end"][:4]) - 2026)), 1.0), 2), p["id"]))
            if p["age"] <= 20 and new_ca - p["ca"] > 0.6:
                events.append(dict(kind="development",
                                   text=f"{p['name']} ({p['age']}) has improved noticeably in training.",
                                   pid=p["id"]))


def _board_review(con, save, rng, events):
    board = save["board"]
    c = club(con, save["club_id"])
    conf = board["confidence"]
    board["sack_risk"] = max(0, board.get("sack_risk", 0) - 6)
    evaluate_objectives(con, save, rng, final=False)      # mid-season progress tracking
    # the board expects cash to be reinvested in the squad
    if c["cash"] > max(6.0, c["season_income"] * 0.9) and not save["flags"].get(f"invest_{save['season']}"):
        n_first = con.execute("""SELECT COUNT(*) FROM players WHERE club_id=?
            AND squad IN ('First Team','Reserve')""", (save["club_id"],)).fetchone()[0]
        save["flags"][f"invest_{save['season']}"] = True
        add_inbox(con, save, "BOARD", "IMPORTANT", "Board expects investment in the squad",
                  f"Chairman {c['chairman']} has noted the club is sitting on {money(c['cash'])} in cash "
                  f"with a first-team squad of only {n_first}.\n\n"
                  f"The board would like to see the balance reinvested in players, staff or facilities "
                  f"before the end of the season. Hoarding cash while the squad thins out will not be "
                  f"looked upon favourably.",
                  payload={"screen": "transfers"})
        board["confidence"] = max(0, min(100, board["confidence"] - 2.0))
    if conf < 20 and not board.get("warning"):
        board["warning"] = True
        add_inbox(con, save, "BOARD", "URGENT", "Official warning from the board",
                  f"The board has issued a formal warning.\n\nChairman {c['chairman']} is unhappy with "
                  f"results and expects an immediate improvement. Continued poor performance will "
                  f"put your position under review.",
                  payload={"screen": "board"})
    elif conf < 10:
        add_inbox(con, save, "BOARD", "URGENT", "Board meeting requested",
                  "The board has requested an urgent meeting to discuss your future.",
                  payload={"screen": "board", "action": "board_meeting"})
        board["sack_risk"] = board.get("sack_risk", 0) + 18
    elif conf > 82 and not board.get("praised"):
        board["praised"] = True
        add_inbox(con, save, "BOARD", "ROUTINE", "Board delighted with progress",
                  f"The board is delighted with your work. Confidence is high and they are open to "
                  f"discussing an improved contract or increased budget.",
                  payload={"screen": "board"})
    else:
        board["praised"] = False
        if conf > 35:
            board["warning"] = False
    # sack check
    if conf < 10 and board.get("sack_risk", 0) > 55 and rng.random() < 0.35:
        _sack_human(con, save, rng, c)


def vacant_clubs(con):
    """Clubs in the top five tiers with no manager attached."""
    rows = con.execute("""SELECT c.id, c.name, c.rep, c.tier, c.league, c.country, c.season_income
        FROM clubs c WHERE c.tier<=5 AND c.rep>=22 AND c.id>0
          AND c.id NOT IN (SELECT club_id FROM managers WHERE club_id IS NOT NULL)
        ORDER BY c.rep DESC LIMIT 40""").fetchall()
    return [dict(r) for r in rows]


def _maybe_offer_job(con, save, club_id, rng):
    """A vacant club may approach the human manager if he is available and suitable."""
    if not save["flags"].get("unemployed"):
        return False
    c = club(con, club_id)
    if not c:
        return False
    rep_gap = save["career"]["reputation"] - c["rep"] * 0.62
    if rep_gap < -7:
        return False
    if rng.random() > max(0.06, min(0.85, 0.30 + rep_gap * 0.06)):
        return False
    offer = {"club_id": club_id, "date": save["date"], "expires_days": 10,
             "rep": c["rep"], "name": c["name"], "league": c["league"], "tier": c["tier"]}
    save["flags"].setdefault("job_offers", []).append(offer)
    lg = con.execute("SELECT name FROM competitions WHERE code=?", (c["league"],)).fetchone()
    add_inbox(con, save, "CAREER", "URGENT", f"Job offer: {c['name']}",
              f"{c['name']} ({lg['name'] if lg else c['league']}) would like to talk to you about "
              f"their managerial vacancy.\n\nThe offer expires in 10 days.",
              payload={"screen": "career", "action": "job_offer", "club_id": club_id})
    return True


def job_market_tick(con, save, dt, rng, events):
    """While unemployed: the world turns, vacancies appear and offers may arrive."""
    n = _simulate_day_matches(con, save, dt, rng)
    events.append(dict(kind="world", text=f"{n} matches played around the world."))
    _check_competitions(con, save, rng)
    # expire old offers
    offers = save["flags"].get("job_offers", [])
    kept = []
    for o in offers:
        age = (dt - d(o["date"])).days
        if age <= o.get("expires_days", 10):
            kept.append(o)
    save["flags"]["job_offers"] = kept
    if dt.weekday() == 0:
        _world_managers(con, save, rng, events)
        vac = vacant_clubs(con)
        if vac and not kept:
            top = vac[:6]
            lines = "\n".join(
                f"- {v['name']} ({v['league']}, rep {v['rep']:.0f})" for v in top)
            add_inbox(con, save, "CAREER", "ROUTINE", "Managerial vacancies",
                      f"{len(vac)} club(s) are currently without a manager:\n\n{lines}\n\n"
                      f"You can apply for any of them from the Career screen.",
                      payload={"screen": "career", "action": "jobs"})
        elif vac:
            add_inbox(con, save, "CAREER", "ROUTINE", "Managerial vacancies",
                      f"{len(vac)} club(s) are currently without a manager. "
                      f"See the Career screen for the list.",
                      payload={"screen": "career", "action": "jobs"})
        # vacant clubs look for a replacement
        for v in vacant_clubs(con)[:12]:
            if rng.random() < 0.16:
                if not _maybe_offer_job(con, save, v["id"], rng):
                    newname = make_manager_name(rng)
                    con.execute("INSERT INTO managers (name,nat,age,club_id,reputation,style,hired,human,attrs) "
                                "VALUES (?,?,?,?,?,?,?,0,?)",
                                (newname, rng.choice(NATIONALITY_POOL), rng.randint(35, 62), v["id"],
                                 max(5.0, v["rep"] * 0.72), rng.choice(
                                     ["Possession", "High press", "Counter-attack", "Direct", "Balanced",
                                      "Defensive solidity", "Wing play"]),
                                 save["date"], json.dumps({k: rng.randint(6, 17) for k in
                                 ("attacking", "defending", "fitness", "tactical", "mental", "technical",
                                  "youth", "man_mgmt", "motivation", "adaptability", "judging")})))
                    add_news(con, save, "MANAGERS", f"{v['name']} have appointed {newname} as manager.",
                             club_id=v["id"])
    # season rollover still happens while unemployed
    if not save["flags"].get(f"season_done_{save['season']}"):
        _last = con.execute("""SELECT MAX(f.match_date) FROM fixtures f JOIN competitions k ON k.id=f.comp_id
            WHERE f.season=? AND k.ctype!='friendly'""", (save["season"],)).fetchone()[0]
        if _last and ds(dt) >= _last:
            _season_end_unemployed(con, save, rng, events)
            save["flags"][f"season_done_{save['season'] - 1}"] = True
    return events


def _season_end_unemployed(con, save, rng, events):
    con.execute("UPDATE players SET age=age+1, goals=0, assists=0, apps=0, minutes=0, avg_rating=0, "
                "yellow=0, red=0, form=0, injured_weeks=0, condition='fit', injury_name='', "
                "return_date='', suspended=0, fitness=92, fatigue=5, sharpness=45")
    con.execute("UPDATE players SET dob=date(dob,'-1 year')")
    for lg in con.execute("SELECT * FROM competitions WHERE ctype='league'").fetchall():
        rows = retable(con, save, lg["id"])
        if rows:
            champc = club(con, rows[0]["club_id"])
            add_news(con, save, "LEAGUE", f"{champc['name']} win the {lg['name']}.", champc["id"])
    prev_season = save["season"]
    save["season"] += 1
    new_season(con, save, rng, prev_season)
    STRENGTH_CACHE.clear()
    add_inbox(con, save, "CAREER", "ROUTINE", f"Season {prev_season}/{str(prev_season + 1)[2:]} concluded",
              "The season has ended. You are still without a club.",
              payload={"screen": "career"})


def list_jobs(con, save):
    """Vacancies the human can see, with an indication of interest."""
    out = []
    for v in vacant_clubs(con):
        gap = save["career"]["reputation"] - v["rep"] * 0.62
        out.append({**v, "interest": "high" if gap > 6 else ("medium" if gap > 0 else "low"),
                    "chance": round(max(0.03, min(0.85, 0.10 + gap * 0.05)), 2)})
    return out


def accept_job(con, save, club_id, rng=None):
    """Take a job offer (or apply for a vacancy)."""
    rng = rng or random.Random()
    c = club(con, club_id)
    if not c:
        return {"ok": False, "msg": "Unknown club."}
    offers = save["flags"].get("job_offers", [])
    offered = any(o["club_id"] == club_id for o in offers)
    if not offered:
        rep_gap = save["career"]["reputation"] - c["rep"] * 0.62
        chance = 0.10 + rep_gap * 0.05
        if rng.random() > max(0.03, min(0.8, chance)):
            add_inbox(con, save, "CAREER", "ROUTINE", f"Application rejected: {c['name']}",
                      f"{c['name']} have decided to go in another direction.",
                      payload={"screen": "career"})
            return {"ok": False, "msg": f"{c['name']} turned your application down."}
    save["flags"]["job_offers"] = [o for o in offers if o["club_id"] != club_id]
    # close the career chapter at the old club
    if save["career"]["clubs"] and save["career"]["clubs"][-1].get("to") is None:
        save["career"]["clubs"][-1]["to"] = save["date"]
        save["career"]["clubs"][-1]["reason"] = "sacked" if save["flags"].get("sacked") else "left"
    con.execute("DELETE FROM managers WHERE club_id=? AND human=1", (club_id,))
    con.execute("INSERT INTO managers (name,nat,age,club_id,reputation,style,hired,human,attrs) "
                "VALUES (?,?,?,?,?,?,?,1,?)",
                (save["career"]["manager"]["name"], save["career"]["manager"].get("nat", "England"), save["career"]["manager"].get("age", 38), club_id,
                 save["career"]["reputation"], save["career"]["manager"].get("style", "Balanced"), save["date"],
                 json.dumps(save["career"]["manager"].get("attrs", {}))))
    save["club_id"] = club_id
    save["flags"]["unemployed"] = False
    save["flags"]["sacked"] = False
    save["season_stats"] = {"played": 0, "won": 0, "drawn": 0, "lost": 0, "gf": 0, "ga": 0}
    save["career"]["clubs"].append({"club_id": club_id, "code": c["code"], "name": c["name"],
                                    "from": save["date"], "to": None, "season": save["season"],
                                    "reason": "hired"})
    ensure_human_setup(con, club_id, formation="4-2-3-1 Wide")
    setup_club_state(con, save)
    add_inbox(con, save, "CAREER", "URGENT", f"Appointed: {c['name']}",
              f"You have been appointed manager of {c['name']}.\n\n"
              f"Stadium: {c['stadium']} ({c['capacity']:,})\n"
              f"Transfer budget: {money(c['transfer_budget'])}\nWage budget: {money(c['wage_budget'])}\n\n"
              f"The board expects you to settle in quickly.",
              payload={"screen": "home"})
    bump()
    persist(con, save)
    return {"ok": True, "msg": f"You are now manager of {c['name']}.", "club": c["name"]}


def resign(con, save, rng=None):
    """Hand in your notice."""
    c = club(con, save["club_id"])
    con.execute("DELETE FROM managers WHERE club_id=? AND human=1", (save["club_id"],))
    if save["career"]["clubs"]:
        save["career"]["clubs"][-1]["to"] = save["date"]
        save["career"]["clubs"][-1]["reason"] = "resigned"
    save["flags"]["unemployed"] = True
    save["flags"]["sacked"] = False
    save["flags"]["job_offers"] = []
    save["club_id"] = None
    add_news(con, save, "MANAGERS", f"{c['name'] if c else 'The club'} manager "
                                    f"{save['career']['manager']['name']} has resigned.",
             club_id=c["id"] if c else None)
    add_inbox(con, save, "CAREER", "URGENT", "Resignation accepted",
              "You have left the club and are now available for appointment elsewhere.",
              payload={"screen": "career"})
    bump()
    persist(con, save)
    return {"ok": True, "msg": "You have resigned."}


def _sack_human(con, save, rng, c):
    cid = save["club_id"]
    save["flags"]["sacked"] = True
    save["flags"]["unemployed"] = True
    if save["career"]["clubs"]:
        save["career"]["clubs"][-1]["to"] = save["date"]
        save["career"]["clubs"][-1]["reason"] = "sacked"
    con.execute("DELETE FROM managers WHERE club_id=? AND human=1", (cid,))
    save["career"]["reputation"] = max(1.0, save["career"]["reputation"] - 1.5)
    add_news(con, save, "MANAGERS", f"{c['name']} have sacked manager {save['career']['manager']['name']}.",
             club_id=cid)
    add_inbox(con, save, "CAREER", "URGENT", "You have been sacked",
              f"The board of {c['name']} has terminated your contract with immediate effect.\n\n"
              f"You are now unemployed, but other clubs will be looking at the vacancy market. "
              f"Offers may arrive in the coming weeks — you can also apply for jobs yourself.",
              payload={"screen": "career", "action": "sacked"})
    save["club_id"] = None
    save["flags"]["job_offers"] = []
    bump()


def _tick_scouting(con, save, rng, events):
    """Progress active scouting assignments."""
    cid = save["club_id"]
    c = club(con, cid)
    scouts = con.execute("""SELECT * FROM staff WHERE club_id=? AND role IN ('Chief Scout','Scout')""",
                         (cid,)).fetchall()
    quality = max([s["judging"] for s in scouts], default=8)
    for task in list(save.get("scout_tasks", [])):
        if task.get("done"):
            continue
        task["progress"] = task.get("progress", 0) + 6 + quality * 0.7
        if task["type"] == "player":
            pid_ = task["pid"]
            know = save["known"].get(str(pid_), 0)
            know = min(100, know + 12 + quality * 1.1)
            save["known"][str(pid_)] = round(know, 1)
            if task["progress"] >= 100:
                task["done"] = True
                p = con.execute("SELECT * FROM players WHERE id=?", (pid_,)).fetchone()
                if p:
                    est = estimate_player(con, save, pid_)
                    add_inbox(con, save, "SCOUT", "IMPORTANT", f"Scouting report: {p['name']}",
                              scout_report_text(con, save, est, p),
                              payload={"screen": "player", "pid": pid_})
        else:
            region = task["region"]
            know = save["scouting"].get(region, 0)
            save["scouting"][region] = min(100, know + 5 + quality * 0.5)
            if task["progress"] >= 100:
                task["done"] = True
                add_inbox(con, save, "SCOUT", "ROUTINE", f"Scouting complete: {region}",
                          f"Knowledge of {region} is now {save['scouting'][region]:.0f}/100. "
                          f"Player searches in this region are more accurate.",
                          payload={"screen": "scouting"})
    save["scout_tasks"] = [t for t in save.get("scout_tasks", []) if not t.get("done")] or save.get("scout_tasks", [])


# ------------------------------------------------------------------- scouting
def knowledge_of(save, pid):
    return float(save["known"].get(str(pid), 0.0))


def estimate_player(con, save, pid):
    """Return what the club actually knows about a player (no perfect info)."""
    p = con.execute("SELECT * FROM players WHERE id=?", (pid,)).fetchone()
    if not p:
        return None
    p = dict(p)
    know = knowledge_of(save, pid)
    c = club(con, save["club_id"])
    same_country = (club(con, p["club_id"]) or {}).get("country") == c["country"]
    base_know = 0.0
    if same_country:
        base_know += 18 + c["scouting"] * 1.4
    base_know += c["scouting"] * 0.5
    if p["club_id"] == save["club_id"]:
        base_know = 100
    know = min(100, know + base_know)
    rng = random.Random(_seed(str(pid) + save["date"][:7]))
    err_scale = (100 - know) / 100.0
    scouts = con.execute("SELECT AVG(judging) j, AVG(judging_pot) jp FROM staff WHERE club_id=? AND role IN ('Chief Scout','Scout')",
                         (c["id"],)).fetchone()
    ja = scouts["j"] or 8
    jp = scouts["jp"] or 8
    ca_err = err_scale * (2.6 - ja * 0.09) * rng.gauss(0, 1)
    pa_err = err_scale * (3.6 - jp * 0.11) * rng.gauss(0, 1)
    est_ca = max(1, min(20, p["ca"] + ca_err))
    est_pa = max(est_ca, min(20, p["pa"] + pa_err)) if know > 25 else None
    est_value = round(max(0.01, p["value"] * (1 + ca_err * 0.16)), 2) if know > 15 else None
    attrs = None
    if know > 30:
        vec = unpack_attrs(p["attrs"])
        noise = err_scale * (2.4 - ja * 0.08)
        attrs = {}
        for k, v in vec.items():
            if know < 55 and k in ("gk_handling", "gk_reflexes", "gk_one_on_ones", "gk_positioning"):
                if p["pos"] != "GK":
                    continue
            attrs[k] = int(max(1, min(20, round(v + rng.gauss(0, noise)))))
    return dict(id=p["id"], name=p["name"], age=p["age"], nat=p["nat"], pos=p["pos"], pos2=p["pos2"],
                foot=p["foot"], height=p["height"], club_id=p["club_id"],
                squad=p["squad"], personality=p["personality"] if know > 45 else None,
                ca=round(est_ca, 1), pa=(round(est_pa, 1) if est_pa else None),
                value=est_value, wage=p["wage"] if know > 40 else None,
                contract_end=p["contract_end"] if know > 25 else None,
                attrs=attrs, knowledge=round(know, 1),
                stars=_stars(est_ca, c, con), condition=p["condition"],
                form=p["form"] if p["club_id"] == save["club_id"] or know > 60 else None,
                goals=p["goals"], assists=p["assists"], apps=p["apps"],
                injury_prone=p["injury_prone"] if know > 70 else None,
                fitness=p["fitness"] if p["club_id"] == save["club_id"] else None)


def _stars(ca, my_club, con):
    """Star rating relative to my squad level."""
    avg = con.execute("""SELECT AVG(ca) a FROM players WHERE club_id=? AND squad IN ('First Team','Reserve')""",
                      (my_club["id"],)).fetchone()["a"] or 8
    diff = ca - avg
    s = 3.0 + diff * 0.55
    return round(max(0.5, min(5.0, s)), 1)


def scout_report_text(con, save, est, p):
    c = club(con, save["club_id"])
    lines = [f"{est['name']} — {est['age']} — {est['pos']}{('/' + est['pos2']) if est['pos2'] else ''} — {est['nat']}",
             f"Club: {(club(con, p['club_id']) or {}).get('name', 'Unknown')}",
             f"Knowledge level: {est['knowledge']:.0f}/100", ""]
    lines.append(f"Ability estimate: {est['ca']:.1f}/20 ({est['stars']} stars for us)")
    if est["pa"]:
        lines.append(f"Potential estimate: {est['pa']:.1f}/20")
    else:
        lines.append("Potential: insufficient knowledge to judge")
    if est["value"]:
        lines.append(f"Estimated value: {money(est['value'])}")
    if est.get("wage") is not None:
        lines.append(f"Wage: €{est['wage']:.1f}k/week")
    if est.get("contract_end"):
        lines.append(f"Contract until: {est['contract_end']}")
    if est.get("personality"):
        lines.append(f"Personality: {est['personality']}")
    if est["attrs"]:
        best = sorted(est["attrs"].items(), key=lambda kv: -kv[1])[:6]
        worst = sorted(est["attrs"].items(), key=lambda kv: kv[1])[:3]
        lines.append("\nKey strengths: " + ", ".join(f"{k.replace('_', ' ')} {v}" for k, v in best))
        lines.append("Weaknesses: " + ", ".join(f"{k.replace('_', ' ')} {v}" for k, v in worst))
    else:
        lines.append("\nNo attribute detail available — assign a scout to build knowledge.")
    return "\n".join(lines)


def assign_scout(save, region=None, pid=None):
    task = {"type": "player" if pid else "region", "region": region, "pid": pid,
            "progress": 0.0, "started": save["date"]}
    save.setdefault("scout_tasks", []).append(task)
    return task


# ----------------------------------------------------------- transfer market
def asking_price(con, save, pid, rng=None):
    p = con.execute("SELECT * FROM players WHERE id=?", (pid,)).fetchone()
    if not p:
        return 0
    c = club(con, p["club_id"])
    base = p["value"]
    years_left = max(0, int(p["contract_end"][:4]) - 2026)
    mult = 1.0
    if years_left <= 0:
        mult = 0.35
    elif years_left == 1:
        mult = 0.72
    if c["profile"] in ("sell", "dev"):
        mult *= 1.22
    if c["profile"] in ("elite", "trad") and p["ca"] > 14:
        mult *= 1.18
    if p["listed"]:
        mult *= 0.85
    if p["wanted_out"]:
        mult *= 0.92
    return round(base * mult, 2)


def would_sell(con, save, seller_id, pid, fee, rng):
    """AI club decision on an incoming bid. Returns (decision, counter_fee, note)."""
    p = con.execute("SELECT * FROM players WHERE id=?", (pid,)).fetchone()
    sc = club(con, seller_id)
    ask = asking_price(con, save, pid)
    squad_n = con.execute("SELECT COUNT(*) n FROM players WHERE club_id=? AND squad IN ('First Team','Reserve')",
                          (seller_id,)).fetchone()["n"]
    pos_n = con.execute("SELECT COUNT(*) n FROM players WHERE club_id=? AND pos=? AND squad IN ('First Team','Reserve')",
                        (seller_id, p["pos"])).fetchone()["n"]
    need_cover = pos_n <= 2
    ratio = fee / max(ask, 0.05)
    window = window_state(d(save["date"]), save["season"])
    thresh = 0.92
    if p["listed"] or p["wanted_out"]:
        thresh -= 0.14
    if need_cover and squad_n < 22:
        thresh += 0.14
    if not window:
        thresh += 0.35
    if sc["profile"] in ("elite",) and p["ca"] > 15:
        thresh += 0.20
    if fee > sc["cash"] * 0 and ratio > 1.6:
        return ("accept", fee, "The offer is far above their valuation.")
    if ratio >= thresh:
        return ("accept", fee, "The offer meets their valuation.")
    if ratio >= thresh - 0.30:
        counter = round(max(fee * 1.12, ask * thresh * 1.02), 2)
        return ("counter", counter, f"They want closer to {money(counter)}.")
    return ("reject", 0, f"They are not interested at {money(fee)} — they value him around {money(ask)}.")


def player_willing(con, save, pid, wage, promise, rng):
    """Would the player accept personal terms?"""
    p = con.execute("SELECT * FROM players WHERE id=?", (pid,)).fetchone()
    old = club(con, p["club_id"])
    new = club(con, save["club_id"])
    score = 0.0
    score += (new["rep"] - old["rep"]) / 22.0
    score += (wage - p["wage"]) / max(p["wage"], 0.5) * 0.9
    lvl = C.PROMISE_LEVEL.get(promise, 3)
    want = C.PROMISE_LEVEL.get(p["promise"], 3)
    score += (lvl - want) * 0.28
    if p["wanted_out"]:
        score += 0.8
    if p["loyalty"] > 14 and new["rep"] < old["rep"]:
        score -= 0.5
    if p["ambition"] > 15 and new["rep"] < old["rep"] - 8:
        score -= 0.7
    score += rng.gauss(0, 0.45)
    if score > 0.35:
        return True, "He is keen on the move."
    if score > -0.1:
        return None, "He wants to think about it — better terms might convince him."
    return False, "He has turned down the approach."


def make_offer(con, save, pid, fee, wage, years, promise, is_loan=False, loan_end=None,
               split=0.0, addons=None, rng=None):
    """Human makes an offer for a player. Returns dict describing outcome."""
    rng = rng or random.Random()
    p = con.execute("SELECT * FROM players WHERE id=?", (pid,)).fetchone()
    if not p:
        return {"ok": False, "msg": "No such player."}
    if p["club_id"] == save["club_id"]:
        return {"ok": False, "msg": "He already plays for you."}
    seller = club(con, p["club_id"]) if p["club_id"] else None
    c = club(con, save["club_id"])
    if fee > c["transfer_budget"] and not is_loan:
        return {"ok": False, "msg": f"That exceeds your transfer budget ({money(c['transfer_budget'])})."}
    free_agent = (seller is None) or (seller.get("code") == "FREE")
    if free_agent:
        # no selling club: only the player's own terms matter
        fee = 0.0
        decision, counter, note = "accept", 0.0, "Free agent — no fee required."
        if seller is None:
            class _NoClub(dict):
                def __getitem__(self, k):
                    return dict.get(self, k, "Free agents")
            seller = _NoClub(name="Free agents", code="FREE")
    else:
        decision, counter, note = would_sell(con, save, p["club_id"], pid, fee, rng)
    offer_id = con.execute("SELECT COALESCE(MAX(id),0)+1 FROM offers").fetchone()[0]
    con.execute("""INSERT INTO offers (id,player_id,from_id,to_id,fee,addons,wage,status,date,round,clause,
        is_loan,loan_end,split,human,note) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,?)""",
                (offer_id, pid, p["club_id"], save["club_id"], fee, json.dumps(addons or {}), wage,
                 decision, save["date"], 1, 0, 1 if is_loan else 0, loan_end, split, note))
    if decision == "accept":
        will, pnote = player_willing(con, save, pid, wage, promise, rng)
        if will is False:
            con.execute("UPDATE offers SET status='rejected_player', note=? WHERE id=?", (pnote, offer_id))
            add_inbox(con, save, "TRANSFER", "IMPORTANT", f"Transfer collapsed: {p['name']}",
                      f"{seller['name']} accepted your bid of {money(fee)}, but {p['name']} has rejected "
                      f"the personal terms.\n\n{pnote}", payload={"screen": "transfers"})
            return {"ok": False, "msg": f"Club agreed ({note}) but the player refused. {pnote}",
                    "offer_id": offer_id}
        if will is None:
            con.execute("UPDATE offers SET status='player_thinking' WHERE id=?", (offer_id,))
            return {"ok": "pending", "msg": f"{seller['name']} accepted {money(fee)}. {pnote}",
                    "offer_id": offer_id}
        complete_transfer(con, save, pid, save["club_id"], fee, wage, years, promise, rng,
                          is_loan=is_loan, loan_end=loan_end, split=split, addons=addons)
        return {"ok": True, "msg": f"Deal agreed. {p['name']} joins for {money(fee)}.",
                "offer_id": offer_id}
    if decision == "counter":
        add_inbox(con, save, "TRANSFER", "IMPORTANT", f"Counter-offer: {p['name']}",
                  f"{seller['name']} have countered your bid of {money(fee)} for {p['name']}.\n"
                  f"They want {money(counter)}.\n\n{note}",
                  payload={"screen": "transfers", "action": "counter", "offer_id": offer_id,
                           "pid": pid, "counter": counter})
        return {"ok": "counter", "msg": f"Counter-offer of {money(counter)}.", "counter": counter,
                "offer_id": offer_id}
    add_inbox(con, save, "TRANSFER", "ROUTINE", f"Bid rejected: {p['name']}",
              f"{seller['name']} have rejected your bid of {money(fee)} for {p['name']}.\n{note}",
              payload={"screen": "transfers", "pid": pid})
    return {"ok": False, "msg": note, "offer_id": offer_id}


def respond_counter(con, save, offer_id, accept, new_fee=None, rng=None):
    rng = rng or random.Random()
    o = con.execute("SELECT * FROM offers WHERE id=?", (offer_id,)).fetchone()
    if not o:
        return {"ok": False, "msg": "No such offer."}
    p = con.execute("SELECT * FROM players WHERE id=?", (o["player_id"],)).fetchone()
    if not p:
        return {"ok": False, "msg": "No such player."}
    wage = max(o["wage"] or 0, round(p["wage"] * 1.05, 2))
    promise = o["note"] if (o["note"] or "") in C.PLAYING_TIME_PROMISES else "Squad Rotation"
    if accept:
        fee = o["fee"]
        will, pnote = player_willing(con, save, o["player_id"], wage, promise, rng)
        if will is False:
            con.execute("UPDATE offers SET status='rejected_player' WHERE id=?", (offer_id,))
            add_inbox(con, save, "TRANSFER", "IMPORTANT", f"Transfer collapsed: {p['name']}",
                      f"The club accepted {money(fee)}, but {p['name']} has turned down your terms.\n\n{pnote}",
                      payload={"screen": "transfers"})
            return {"ok": False, "msg": f"Terms accepted by the club but {pnote}"}
        if will is None:
            con.execute("UPDATE offers SET status='player_thinking' WHERE id=?", (offer_id,))
            return {"ok": "pending", "msg": f"Deal agreed at {money(fee)}; {p['name']} is considering it. {pnote}"}
        complete_transfer(con, save, o["player_id"], save["club_id"], fee, wage, 4, promise, rng,
                          is_loan=bool(o["is_loan"]), loan_end=o["loan_end"], split=o["split"] or 0)
        con.execute("UPDATE offers SET status='accepted', fee=? WHERE id=?", (fee, offer_id))
        return {"ok": True, "msg": f"Signed for {money(fee)}."}
    if new_fee:
        # put a revised bid to the selling club
        decision, counter, note = would_sell(con, save, p["club_id"], p["id"], float(new_fee), rng)
        nid = con.execute("SELECT COALESCE(MAX(id),0)+1 FROM offers").fetchone()[0]
        con.execute("""INSERT INTO offers (id,player_id,from_id,to_id,fee,addons,wage,status,date,round,
            clause,is_loan,loan_end,split,human,note) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,?)""",
            (nid, p["id"], p["club_id"], save["club_id"], float(new_fee), o["addons"] or "{}", wage,
             decision, save["date"], (o["round"] or 1) + 1, 0, o["is_loan"], o["loan_end"],
             o["split"] or 0, promise))
        con.execute("UPDATE offers SET status='withdrawn' WHERE id=?", (offer_id,))
        if decision == "accept":
            return respond_counter(con, save, nid, True, rng=rng)
        if decision == "counter":
            return {"ok": "counter", "msg": f"They countered again at {money(counter)}.",
                    "counter": counter, "offer_id": nid}
        return {"ok": False, "msg": note, "offer_id": nid}
    con.execute("UPDATE offers SET status='withdrawn' WHERE id=?", (offer_id,))
    return {"ok": True, "msg": "Offer withdrawn."}


def complete_transfer(con, save, pid, to_id, fee, wage, years, promise, rng,
                      is_loan=False, loan_end=None, split=0.0, addons=None):
    p = con.execute("SELECT * FROM players WHERE id=?", (pid,)).fetchone()
    from_id = p["club_id"]
    fc = club(con, from_id); tc = club(con, to_id)
    if is_loan:
        con.execute("""UPDATE players SET club_id=?, loaned_to=?, loan_end=?, loan_wage_split=?,
            squad='First Team', promise=? WHERE id=?""",
                    (to_id, from_id, loan_end or _season_contract_end(save), split, promise, pid))
        if from_id == save["club_id"]:
            con.execute("UPDATE clubs SET cash=cash+?, balance=balance+? WHERE id=?",
                        (-wage * 52 * split / 1000.0, -wage * 52 * split / 1000.0, from_id))
        if to_id == save["club_id"]:
            con.execute("UPDATE clubs SET cash=cash-?, balance=balance-? WHERE id=?",
                        (wage * 52 * (1 - split) / 1000.0, wage * 52 * (1 - split) / 1000.0, to_id))
        ctype = "loan"
    else:
        cend = date(save["season"] + years, 6, 30).isoformat()
        con.execute("""UPDATE players SET club_id=?, wage=?, contract_end=?, promise=?, listed=0,
            wanted_out=0, loaned_to=NULL, squad='First Team', morale=75, happiness=72 WHERE id=?""",
                    (to_id, wage, cend, promise, pid))
        con.execute("UPDATE clubs SET cash=cash-?, transfer_budget=transfer_budget-?, balance=balance-?, wage_bill=wage_bill+? WHERE id=?",
                    (fee, fee, fee, round(wage * 52 / 1000.0, 2), to_id))
        con.execute("UPDATE clubs SET cash=cash+?, transfer_budget=transfer_budget+?, balance=balance+?, wage_bill=MAX(0,wage_bill-?) WHERE id=?",
                    (fee, fee * 0.9, fee, round(p["wage"] * 52 / 1000.0, 2), from_id))
        ctype = "transfer"
    con.execute("""INSERT INTO transfers (player_id,from_id,to_id,fee,wage,date,season,ctype,addons,clause,loan_end,split)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (pid, from_id, to_id, fee, wage, save["date"], save["season"], ctype,
                 json.dumps(addons or {}), 0, loan_end, split))
    con.execute("INSERT INTO news (date,cat,text,club_id,player_id) VALUES (?,?,?,?,?)",
                (save["date"], "TRANSFER",
                 f"{p['name']} moves from {fc['name']} to {tc['name']} for {money(fee)}"
                 + (f" on loan until {loan_end}" if is_loan else ""), to_id, pid))
    if to_id == save["club_id"]:
        add_inbox(con, save, "TRANSFER", "URGENT", f"Signing complete: {p['name']}",
                  f"{p['name']} ({p['age']}, {p['pos']}) has joined from {fc['name']} for {money(fee)}.\n"
                  f"Wage: €{wage:.1f}k/week. Contract until {cend if not is_loan else loan_end}.\n"
                  f"Squad status promised: {promise}.",
                  payload={"screen": "player", "pid": pid})
        save["flags"].setdefault("record_signing", None)
        if not save["flags"]["record_signing"] or fee > save["flags"]["record_signing"]["fee"]:
            save["flags"]["record_signing"] = {"name": p["name"], "fee": fee, "season": save["season"]}
    if from_id == save["club_id"]:
        add_inbox(con, save, "TRANSFER", "IMPORTANT", f"Sale complete: {p['name']}",
                  f"{p['name']} has joined {tc['name']} for {money(fee)}.",
                  payload={"screen": "transfers"})
        if not save["flags"].get("record_sale") or fee > save["flags"]["record_sale"]["fee"]:
            save["flags"]["record_sale"] = {"name": p["name"], "fee": fee, "season": save["season"]}
    bump()
    return True


def renew_contract(con, save, pid, wage, years, promise, rng=None):
    rng = rng or random.Random()
    p = con.execute("SELECT * FROM players WHERE id=?", (pid,)).fetchone()
    if not p or p["club_id"] != save["club_id"]:
        return {"ok": False, "msg": "Not your player."}
    c = club(con, save["club_id"])
    want = p["wage"] * (1.06 + 0.10 * rng.random())
    if p["age"] < 24 and p["pa"] - p["ca"] > 1.2:
        want *= 1.35
    if p["form"] > 1:
        want *= 1.12
    if p["goals"] + p["assists"] > 12:
        want *= 1.15
    if wage >= want:
        cend = date(int(save["date"][:4]) + years, 6, 30).isoformat()
        con.execute("UPDATE players SET wage=?, contract_end=?, promise=?, morale=MIN(100,morale+8), happiness=MIN(100,happiness+10), wanted_out=0 WHERE id=?",
                    (round(wage, 2), cend, promise, pid))
        con.execute("UPDATE clubs SET wage_bill=wage_bill+? WHERE id=?",
                    (round((wage - p["wage"]) * 52 / 1000.0, 3), save["club_id"]))
        add_news(con, save, "CONTRACT", f"{p['name']} signs a new contract until {cend[:4]}.",
                 save["club_id"], pid)
        return {"ok": True, "msg": f"{p['name']} signed until {cend[:4]} on €{wage:.1f}k/week."}
    counter = round(want, 2)
    return {"ok": "counter", "msg": f"His agent wants €{counter:.1f}k/week.", "counter": counter}


def list_player(con, save, pid, listed=True):
    con.execute("UPDATE players SET listed=? WHERE id=?", (1 if listed else 0, pid))
    return True


def release_player(con, save, pid):
    p = con.execute("SELECT * FROM players WHERE id=?", (pid,)).fetchone()
    if not p or p["club_id"] != save["club_id"]:
        return {"ok": False, "msg": "Not your player."}
    comp_fee = p["wage"] * 52 * 0.5 / 1000.0 if p["age"] > 23 else p["wage"] * 52 * 0.2 / 1000.0
    con.execute("UPDATE players SET club_id=NULL, listed=0 WHERE id=?", (pid,))
    con.execute("UPDATE clubs SET cash=cash-?, balance=balance-?, wage_bill=MAX(0,wage_bill-?) WHERE id=?",
                (round(comp_fee, 3), round(comp_fee, 3), round(p["wage"] * 52 / 1000.0, 3), save["club_id"]))
    add_inbox(con, save, "SQUAD", "ROUTINE", f"Released: {p['name']}",
              f"{p['name']} has been released. Compensation paid: {money(comp_fee)}.")
    bump()
    return {"ok": True, "msg": f"{p['name']} released for {money(comp_fee)} compensation."}


def seed_free_agents(con, save, target=140, rng=None):
    """Populate the free-agent pool at career start.

    Fringe veterans and out-of-contract players from around the world become
    available on free transfers, so the manager always has a market to fish in.
    """
    rng = rng or random.Random()
    fa = ensure_free_agent_club(con)
    already = con.execute("SELECT COUNT(*) FROM players WHERE club_id=?", (fa,)).fetchone()[0]
    if already >= target:
        return already
    cid = save["club_id"]
    rows = con.execute("""SELECT p.id, p.club_id, p.age, p.ca, p.pos, c.tier, c.rep FROM players p
        JOIN clubs c ON c.id=p.club_id
        WHERE c.code!='FREE' AND p.club_id!=? AND p.squad IN ('First Team','Reserve')
          AND ((p.age>=30 AND p.ca<9.5) OR p.age>=34)
        ORDER BY RANDOM()""", (cid,)).fetchall()
    per_club = {}
    moved = already
    end = f"{save['season'] + 1}-06-30"
    for r in rows:
        if moved >= target:
            break
        if per_club.get(r["club_id"], 0) >= 2:
            continue
        squad_n = con.execute("""SELECT COUNT(*) FROM players WHERE club_id=?
            AND squad IN ('First Team','Reserve')""", (r["club_id"],)).fetchone()[0]
        if squad_n <= 16:
            continue
        con.execute("""UPDATE players SET club_id=?, contract_end=?, promise='', listed=0,
            wage=ROUND(wage*0.55,2), value=ROUND(value*0.5,2), fitness=92, fatigue=6,
            sharpness=48, condition='fit', injury_name='', return_date='', suspended=0
            WHERE id=?""", (fa, end, r["id"]))
        per_club[r["club_id"]] = per_club.get(r["club_id"], 0) + 1
        moved += 1
    con.commit()
    return moved


def ensure_free_agent_club(con):
    r = con.execute("SELECT id FROM clubs WHERE code='FREE'").fetchone()
    if r:
        return r["id"]
    nid = con.execute("SELECT COALESCE(MAX(id),0)+1 FROM clubs").fetchone()[0]
    con.execute("""INSERT INTO clubs (id,code,name,short,country,league,tier,rep,profile,stadium,capacity,
        youth,facilities,coaching,scouting,cash,transfer_budget,wage_budget,wage_bill,balance,debt,
        prestige,season_income,season_costs,board_patience,vision,chairman,reputation)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (nid, "FREE", "Free Agents", "Free Agents", "None", "ENG5", 5, 1, "minnow", "-", 0,
         1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 1, 0, 0, 50, "Nothing specific", "-", 1))
    return nid


def _world_transfer_activity(con, save, rng, events, volume=3):
    """AI clubs buy, sell and loan players from each other (and poach yours)."""
    win = window_state(d(save["date"]), save["season"])
    diff = DIFFICULTY.get(save["career"]["difficulty"], DIFFICULTY["realistic"])
    for _ in range(volume):
        r = rng.random()
        pool = con.execute("""SELECT * FROM players WHERE club_id IS NOT NULL AND club_id>0
            AND squad IN ('First Team','Reserve') AND age BETWEEN 17 AND 35
            AND value > 0.05 ORDER BY RANDOM() LIMIT 60""").fetchall()
        if not pool:
            continue
        p = rng.choice(pool)
        seller = club(con, p["club_id"])
        if not seller:
            continue
        # the human club never signs players behind the manager's back unless
        # recruitment has been delegated to the assistant
        human_id = -1 if save["delegation"].get("recruitment") else save["club_id"]
        buyers = con.execute("""SELECT * FROM clubs WHERE id!=? AND id!=? AND code!='FREE' AND rep>=?
            ORDER BY RANDOM() LIMIT 25""",
            (p["club_id"], human_id, max(20, seller["rep"] - 25))).fetchall()
        if not buyers:
            continue
        buyer = rng.choice(buyers)
        budget_ok = buyer["transfer_budget"] > p["value"] * 0.55
        if not budget_ok and rng.random() < 0.75:
            continue
        # is this one of my players?
        if p["club_id"] == save["club_id"]:
            fee = round(asking_price(con, save, p["id"], rng) * rng.uniform(0.85, 1.3) * diff["neg"], 2)
            if fee < p["value"] * 0.4:
                continue
            oid = con.execute("SELECT COALESCE(MAX(id),0)+1 FROM offers").fetchone()[0]
            con.execute("""INSERT INTO offers (id,player_id,from_id,to_id,fee,addons,wage,status,date,round,
                clause,is_loan,loan_end,split,human,note) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,0,?)""",
                (oid, p["id"], save["club_id"], buyer["id"], fee, "{}", round(p["wage"] * 1.1, 2),
                 "incoming", save["date"], 1, 0, 0, None, 0, "pending"))
            add_inbox(con, save, "TRANSFER", "URGENT", f"Bid received: {p['name']}",
                      f"{buyer['name']} have bid {money(fee)} for {p['name']} ({p['age']}, {p['pos']}).\n"
                      f"Your valuation: {money(p['value'])}. Asking price: {money(asking_price(con, save, p['id']))}.\n"
                      f"Contract until {p['contract_end']}. Wage €{p['wage']:.1f}k/week.\n\n"
                      f"Squad status promised: {p['promise'] or 'none'}.",
                      payload={"screen": "transfers", "action": "incoming_bid", "offer_id": oid,
                               "pid": p["id"], "fee": fee})
            continue
        # AI-to-AI
        if buyer["id"] == save["club_id"]:
            continue
        fee = round(asking_price(con, save, p["id"], rng) * rng.uniform(0.8, 1.15), 2)
        decision, counter, note = would_sell(con, save, seller["id"], p["id"], fee, rng)
        if decision == "counter" and rng.random() < 0.6:
            fee = counter
            decision = "accept"
        if decision != "accept":
            continue
        is_loan = rng.random() < (0.22 if p["age"] < 23 else 0.06)
        if is_loan and not win:
            continue
        years = rng.choice([2, 3, 4, 5])
        wage = round(p["wage"] * rng.uniform(1.05, 1.5) * (1 + (buyer["rep"] - seller["rep"]) / 220.0), 2)
        # affordability, squad-size and wage-structure sanity for AI buyers
        squad_n = con.execute("""SELECT COUNT(*) FROM players WHERE club_id=?
            AND squad IN ('First Team','Reserve')""", (buyer["id"],)).fetchone()[0]
        if squad_n >= 27 and not (is_loan and p["age"] <= 21):
            continue
        if not is_loan:
            if fee > buyer["transfer_budget"] * 1.05:
                continue
            if wage * 52 / 1000.0 > max(1.5, buyer["season_income"] * 0.055):
                continue
        promise = rng.choice(["Regular Starter", "Squad Rotation", "Important Player", "Backup"])
        if p["ca"] > 15:
            promise = rng.choice(["Star Player", "Important Player"])
        loan_end = _season_contract_end(save) if is_loan else None
        complete_transfer(con, save, p["id"], buyer["id"], 0.0 if is_loan else fee, wage, years,
                          promise, rng, is_loan=is_loan, loan_end=loan_end,
                          split=rng.choice([0, 0.25, 0.5, 1.0]) if is_loan else 0)
        if is_loan:
            con.execute("UPDATE transfers SET ctype='loan' WHERE player_id=? AND date=?", (p["id"], save["date"]))


def _market_day(con, save, rng, events):
    """Daily transfer-market activity while a window is open."""
    dt = d(save["date"])
    W = season_windows(save["season"])
    win = window_state(dt, save["season"])
    vol = 3 if win == "summer" else 2
    if win == "winter":
        vol = 2
    if dt in (W["close"], W["winter"][1]):
        vol = 9
    elif dt.day >= 25 and win:
        vol += 2
    _world_transfer_activity(con, save, rng, events, volume=vol)
    if dt == W["close"]:
        add_inbox(con, save, "TRANSFER", "URGENT", "Summer transfer window closed",
                  "The summer window has shut. Unregistered players cannot play until January.",
                  payload={"screen": "transfers"})
    if dt == W["winter"][1]:
        add_inbox(con, save, "TRANSFER", "URGENT", "Winter window closed",
                  "The January window has shut.", payload={"screen": "transfers"})
    if dt == W["winter"][0]:
        add_inbox(con, save, "TRANSFER", "IMPORTANT", "Winter transfer window opens",
                  _window_briefing(con, save), payload={"screen": "transfers"})


def _window_briefing(con, save):
    c = club(con, save["club_id"])
    players = load_players(con, save["club_id"])
    first = [p for p in players if p["squad"] in ("First Team", "Reserve")]
    exp = [p for p in first if p["contract_end"] <= _season_contract_end(save)]
    need = {}
    for pos, req in (("GK", 2), ("DC", 4), ("DL", 2), ("DR", 2), ("DM", 2), ("MC", 3),
                     ("AMC", 2), ("AML", 2), ("AMR", 2), ("ST", 2)):
        have = len([p for p in first if p["pos"] == pos])
        if have < req:
            need[pos] = req - have
    lines = [f"Transfer budget: {money(c['transfer_budget'])}",
             f"Wage budget: {money(c['wage_budget'])} (bill {money(c['wage_bill'])})",
             f"Cash: {money(c['cash'])}", ""]
    if need:
        lines.append("Squad gaps: " + ", ".join(f"{k} short {v}" for k, v in need.items()))
    else:
        lines.append("Squad coverage looks adequate across all positions.")
    if exp:
        lines.append(f"Contracts expiring: {len(exp)} — " + ", ".join(p["name"] for p in exp[:5]))
    unhappy = [p for p in first if p["happiness"] < 35]
    if unhappy:
        lines.append("Unhappy players: " + ", ".join(p["name"] for p in unhappy[:5]))
    return "\n".join(lines)


def _tick_offers(con, save, rng, events):
    """Resolve pending player-thinking offers and AI negotiation rounds."""
    rows = con.execute("SELECT * FROM offers WHERE status='player_thinking' AND human=1").fetchall()
    for o in rows:
        if rng.random() < 0.45:
            p = con.execute("SELECT * FROM players WHERE id=?", (o["player_id"],)).fetchone()
            will, note = player_willing(con, save, p["id"], o["wage"] * 1.12, "Regular Starter", rng)
            if will:
                complete_transfer(con, save, p["id"], save["club_id"], o["fee"], round(o["wage"] * 1.1, 2),
                                  4, "Regular Starter", rng, is_loan=bool(o["is_loan"]),
                                  loan_end=o["loan_end"], split=o["split"] or 0)
                con.execute("UPDATE offers SET status='accepted' WHERE id=?", (o["id"],))
            else:
                con.execute("UPDATE offers SET status='rejected_player' WHERE id=?", (o["id"],))
                add_inbox(con, save, "TRANSFER", "ROUTINE", f"Transfer collapsed: {p['name']}",
                          f"{p['name']} has decided against the move. {note}")


def handle_incoming_bid(con, save, offer_id, decision, counter_fee=None, rng=None):
    """Human responds to a bid for one of their players."""
    rng = rng or random.Random()
    o = con.execute("SELECT * FROM offers WHERE id=?", (offer_id,)).fetchone()
    if not o:
        return {"ok": False, "msg": "No such offer."}
    p = con.execute("SELECT * FROM players WHERE id=?", (o["player_id"],)).fetchone()
    buyer = club(con, o["to_id"])
    if decision == "accept":
        wage = round(max(p["wage"] * 1.15, o["wage"]), 2)
        years = rng.choice([3, 4, 5])
        complete_transfer(con, save, p["id"], buyer["id"], o["fee"], wage, years,
                          "Regular Starter", rng)
        con.execute("UPDATE offers SET status='accepted' WHERE id=?", (offer_id,))
        return {"ok": True, "msg": f"{p['name']} sold to {buyer['name']} for {money(o['fee'])}."}
    if decision == "reject":
        con.execute("UPDATE offers SET status='rejected', note=? WHERE id=?",
                    ("Bid rejected by the club.", offer_id))
        if rng.random() < 0.30 and o["fee"] < p["value"] * 1.4:
            new_fee = round(o["fee"] * rng.uniform(1.15, 1.4), 2)
            oid = con.execute("SELECT COALESCE(MAX(id),0)+1 FROM offers").fetchone()[0]
            con.execute("""INSERT INTO offers (id,player_id,from_id,to_id,fee,addons,wage,status,date,round,
                clause,is_loan,loan_end,split,human,note) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,0,'incoming')""",
                (oid, p["id"], save["club_id"], buyer["id"], new_fee, "{}", o["wage"], "incoming",
                 save["date"], o["round"] + 1, 0, 0, None, 0))
            add_inbox(con, save, "TRANSFER", "URGENT", f"Improved bid: {p['name']}",
                      f"{buyer['name']} have returned with an improved bid of {money(new_fee)} for {p['name']}.",
                      payload={"screen": "transfers", "action": "incoming_bid", "offer_id": oid,
                               "pid": p["id"], "fee": new_fee})
            return {"ok": True, "msg": f"Rejected. {buyer['name']} came back with {money(new_fee)}.",
                    "new_offer": oid}
        return {"ok": True, "msg": "Bid rejected."}
    if decision == "counter":
        con.execute("UPDATE offers SET status='countered' WHERE id=?", (offer_id,))
        decision2, counter2, note = would_sell(con, save, save["club_id"], p["id"], counter_fee, rng)
        accept_p = rng.random() < (0.75 if counter_fee >= p["value"] * 1.05 else
                                   (0.45 if counter_fee >= p["value"] * 0.9 else 0.15))
        if accept_p:
            wage = round(max(p["wage"] * 1.15, o["wage"]), 2)
            complete_transfer(con, save, p["id"], buyer["id"], counter_fee, wage, 4,
                              "Regular Starter", rng)
            return {"ok": True, "msg": f"{buyer['name']} accepted {money(counter_fee)}."}
        if rng.random() < 0.5:
            new_fee = round((counter_fee + o["fee"]) / 2 * rng.uniform(0.98, 1.06), 2)
            oid = con.execute("SELECT COALESCE(MAX(id),0)+1 FROM offers").fetchone()[0]
            con.execute("""INSERT INTO offers (id,player_id,from_id,to_id,fee,addons,wage,status,date,round,
                clause,is_loan,loan_end,split,human,note) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,0,'incoming')""",
                (oid, p["id"], save["club_id"], buyer["id"], new_fee, "{}", o["wage"], "incoming",
                 save["date"], o["round"] + 1, 0, 0, None, 0))
            add_inbox(con, save, "TRANSFER", "IMPORTANT", f"Counter: {p['name']}",
                      f"{buyer['name']} countered your asking price with {money(new_fee)}.",
                      payload={"screen": "transfers", "action": "incoming_bid", "offer_id": oid,
                               "pid": p["id"], "fee": new_fee})
            return {"ok": "counter", "msg": f"They countered with {money(new_fee)}.", "new_offer": oid}
        return {"ok": False, "msg": f"{buyer['name']} walked away from negotiations."}
    return {"ok": False, "msg": "Unknown decision."}


# --------------------------------------------------------------- interactions
def player_talk(con, save, pid, kind, text="", rng=None):
    """Manager-player interaction. kind: praise/criticise/promise/warn/discuss_contract/explain_role"""
    rng = rng or random.Random()
    p = con.execute("SELECT * FROM players WHERE id=?", (pid,)).fetchone()
    if not p:
        return {"ok": False, "msg": "No such player."}
    mine = p["club_id"] == save["club_id"]
    vec = unpack_attrs(p["attrs"])
    det = vec.get("determination", 10)
    pres = vec.get("pressure", 10) if "pressure" in vec else p["pressure"]
    pers = p["personality"]
    dm = 0
    reply = ""
    if kind == "praise":
        base = 4 + (p["form"] * 1.2)
        if pers in ("Reserved", "Stubborn") and p["form"] < 0:
            base -= 3
        dm = base + rng.gauss(0, 1.5)
        reply = f"{p['name']} appreciated the public support." if dm > 2 else \
                f"{p['name']} took the praise quietly."
        con.execute("UPDATE players SET morale=MIN(100,morale+?), confidence=MIN(100,confidence+?), form=MIN(3.2,form+0.15) WHERE id=?",
                    (round(max(0, dm), 1), round(max(0, dm * 0.8), 1), pid))
    elif kind == "criticise":
        base = -3 + det * 0.35 - pres * 0.12
        if pers in ("Driven", "Determined", "Professional", "Perfectionist"):
            base += 3.5
        if pers in ("Mercurial", "Light-Hearted", "Coward"):
            base -= 2
        dm = base + rng.gauss(0, 1.6)
        reply = f"{p['name']} responded well to the criticism." if dm > 0 else \
                f"{p['name']} was visibly affected by your comments."
        con.execute("UPDATE players SET morale=MAX(3,morale+?), form=MAX(-3.2,form+?) WHERE id=?",
                    (round(dm, 1), round(dm * 0.06, 2), pid))
    elif kind == "promise":
        lvl = text or "Regular Starter"
        if lvl not in C.PROMISE_LEVEL:
            return {"ok": False, "msg": "Invalid promise level."}
        if not mine:
            return {"ok": False, "msg": "You can only promise playing time to your own players."}
        old = p["promise"]
        con.execute("UPDATE players SET promise=? WHERE id=?", (lvl, pid))
        con.execute("INSERT INTO promises (player_id,ptype,value,date,deadline,status,note) VALUES (?,?,?,?,?,?,?)",
                    (pid, "playing_time", lvl, save["date"], "2027-05-31", "active",
                     f"previous: {old}"))
        dm = 6 if C.PROMISE_LEVEL[lvl] > C.PROMISE_LEVEL.get(old, 3) else -2
        reply = f"You promised {p['name']} he would be a {lvl}. It has been recorded."
        con.execute("UPDATE players SET morale=MAX(3,MIN(100,morale+?)) WHERE id=?", (dm, pid))
    elif kind == "warn":
        dm = -2 - rng.random() * 2
        reply = f"{p['name']} has been warned about his {text or 'conduct'}."
        con.execute("UPDATE players SET morale=MAX(3,morale+?) WHERE id=?", (round(dm, 1), pid))
    elif kind == "discuss_contract":
        want = p["wage"] * (1.08 + rng.random() * 0.14)
        reply = (f"{p['name']}'s agent says he wants €{want:.1f}k/week on a new deal. "
                 f"He is currently on €{p['wage']:.1f}k/week until {p['contract_end']}.")
        return {"ok": True, "msg": reply, "ask": round(want, 2)}
    elif kind == "explain_role":
        reply = (f"You explained the {text or 'tactical'} requirements to {p['name']}. "
                 f"He will work on it in training.")
        con.execute("UPDATE players SET familiar=MIN(100,familiar+6) WHERE id=?", (pid,))
    elif kind == "praise_training":
        dm = 2.5 + rng.gauss(0, 1)
        reply = f"{p['name']} was pleased you noticed his work in training."
        con.execute("UPDATE players SET morale=MIN(100,morale+?), professionalism=MIN(20,professionalism+?) WHERE id=?",
                    (round(max(0, dm), 1), 1 if rng.random() < 0.2 else 0, pid))
    else:
        return {"ok": False, "msg": "Unknown interaction."}
    if mine:
        add_inbox(con, save, "PLAYER", "ROUTINE", f"Meeting: {p['name']}", reply,
                  payload={"screen": "player", "pid": pid})
    return {"ok": True, "msg": reply}


def squad_meeting(con, save, tone, rng=None):
    rng = rng or random.Random()
    cid = save["club_id"]
    form = save["season_stats"]
    eff = {"praise": 3.5, "encourage": 2.5, "neutral": 0.5, "balanced": 0.5,
           "criticise": -1.5, "demand": -0.5, "inspire": 4.0}.get(tone, 0.5)
    man = con.execute("SELECT attrs FROM managers WHERE club_id=? AND human=1", (cid,)).fetchone()
    ma = json.loads(man["attrs"]) if man else {}
    eff += (ma.get("man_mgmt", 10) - 10) * 0.22 + (ma.get("motivation", 10) - 10) * 0.18
    if tone in ("criticise", "demand"):
        avg_det = con.execute("SELECT AVG(determination) d FROM players WHERE club_id=?", (cid,)).fetchone()["d"] or 10
        eff += (avg_det - 10) * 0.28
    eff += rng.gauss(0, 1.1)
    con.execute("UPDATE players SET morale=MAX(3,MIN(100,morale+?)) WHERE club_id=?", (round(eff, 1), cid))
    save["flags"]["squad_cohesion"] = max(5, min(100, save["flags"].get("squad_cohesion", 55) + eff * 0.5))
    return {"ok": True, "msg": f"Squad meeting held. Morale shifted by {eff:+.1f}.", "effect": round(eff, 1)}


# --------------------------------------------------------------- season end
def refresh_promises(con, save):
    """Re-assign playing-time promises from the current squad's ability ranking."""
    cid = save.get("club_id")
    if not cid:
        return
    players = load_players(con, cid)
    first = sorted([p for p in players if p["squad"] in ("First Team", "Reserve")],
                   key=lambda p: -p["ca"])
    n = len(first)
    for i, p in enumerate(first):
        frac = i / max(1, n - 1)
        if frac < 0.06:
            promise = "Star Player"
        elif frac < 0.18:
            promise = "Important Player"
        elif frac < 0.42:
            promise = "Regular Starter"
        elif frac < 0.66:
            promise = "Squad Rotation"
        elif frac < 0.85:
            promise = "Backup"
        else:
            promise = "Development"
        if p["age"] <= 20:
            promise = "Hot Prospect" if frac < 0.5 else "Development"
        con.execute("UPDATE players SET promise=?, minutes_expected=? WHERE id=? AND (promise IS NULL OR promise='')",
                    (promise, int(C.PROMISE_LEVEL[promise] * 520), p["id"]))
    con.commit()


STAGE_RANK = {"R1": 1, "R2": 2, "R3": 3, "R4": 4, "R5": 5, "R6": 6, "R7": 7,
              "R64": 8, "R32": 9, "R16": 10, "QF": 11, "SF": 12, "F": 13}
STAGE_NAME = {v: k for k, v in STAGE_RANK.items()}


def snapshot_youth(con, save):
    """Remember which players are in the academy at the start of the season."""
    if not save.get("club_id"):
        return
    save["flags"]["youth_ids"] = [r[0] for r in con.execute(
        "SELECT id FROM players WHERE club_id=? AND squad IN ('Youth','U21')",
        (save["club_id"],)).fetchall()]


def best_cup_stage(con, save, season=None):
    """Highest-ranked domestic/continental cup stage the club has played this season."""
    season = season or save["season"]
    cid = save["club_id"]
    if not cid:
        return 0, None
    rows = con.execute("""SELECT f.stage, k.name FROM fixtures f JOIN competitions k ON k.id=f.comp_id
        WHERE k.ctype IN ('cup','continental') AND f.season=? AND f.played=1
          AND (f.home_id=? OR f.away_id=?)""", (season, cid, cid)).fetchall()
    best, comp = 0, None
    for r in rows:
        rk = STAGE_RANK.get(r["stage"], 0)
        if rk > best:
            best, comp = rk, r["name"]
    return best, comp


def evaluate_objectives(con, save, rng=None, final=False):
    """Update board objective statuses. Returns (lines, confidence_delta)."""
    board = save["board"]
    objs = board.get("objectives") or []
    if not objs or not save.get("club_id"):
        return [], 0.0
    c = club(con, save["club_id"])
    pos = _league_position(con, save)
    cup_rank, cup_comp = best_cup_stage(con, save)
    lines, delta = [], 0.0
    youth_ids = save["flags"].get("youth_ids") or []
    youth_apps = 0
    if youth_ids:
        q = ",".join("?" * min(len(youth_ids), 500))
        youth_apps = con.execute(f"SELECT COUNT(*) FROM players WHERE id IN ({q}) AND apps>0",
                                 tuple(youth_ids[:500])).fetchone()[0]
    for o in objs:
        kind = o.get("type")
        if kind == "league" and pos and pos.get("played"):
            target = o.get("target_pos") or 12
            size = pos.get("size") or 24
            if final:
                met = pos["pos"] <= target
                o["status"] = "met" if met else "failed"
                d = (7.0 if met else -10.0) * (1.5 if o.get("critical") else 1.0)
                if pos["pos"] == 1:
                    d += 7.0
                elif pos["pos"] <= max(1, target // 2):
                    d += 3.0
                delta += d
                lines.append(f"{o['text']}: {'ACHIEVED' if met else 'NOT ACHIEVED'} — finished "
                             f"{pos['pos']} of {size} (target {target})")
            else:
                o["track"] = "on track" if pos["pos"] <= target + 2 else (
                    "borderline" if pos["pos"] <= target + 6 else "behind")
        elif kind == "cup":
            need = STAGE_RANK["R3"]
            if final:
                met = cup_rank >= need
                o["status"] = "met" if met else "failed"
                delta += 3.5 if met else -4.0
                if cup_rank >= STAGE_RANK["SF"]:
                    delta += 3.0
                reached = STAGE_NAME.get(cup_rank)
                lines.append(f"{o['text']}: {'ACHIEVED' if met else 'NOT ACHIEVED'} — "
                             f"best run: {cup_comp or 'no cup tie'}"
                             + (f" (round {reached})" if reached else ""))
            else:
                o["track"] = "on track" if cup_rank >= 1 else "awaiting first tie"
        elif kind == "finance":
            over = c["wage_bill"] - c["wage_budget"]
            if final:
                met = over <= max(0.02, c["wage_budget"] * 0.02)
                o["status"] = "met" if met else "failed"
                delta += 2.5 if met else -5.0
                lines.append(f"{o['text']}: {'ACHIEVED' if met else 'NOT ACHIEVED'} — wage bill "
                             f"{money(c['wage_bill'])} vs budget {money(c['wage_budget'])}")
            else:
                o["track"] = "on track" if over <= 0 else f"{money(over)} over"
        elif kind == "youth":
            if final:
                met = youth_apps > 0
                o["status"] = "met" if met else "failed"
                delta += 2.0 if met else -2.5
                lines.append(f"{o['text']}: {'ACHIEVED' if met else 'NOT ACHIEVED'} — "
                             f"{youth_apps} academy player(s) appeared for the first team")
            else:
                o["track"] = "on track" if youth_apps else "no debut yet"
        elif kind == "vision":
            if final:
                # judged on overall progress rather than a single number
                league_ok = any(x.get("type") == "league" and x.get("status") == "met" for x in objs)
                improved = (pos or {}).get("pos", 99) <= max(6, (c["rep"] // 4))
                met = bool(league_ok or improved)
                o["status"] = "met" if met else "part"
                delta += 2.0 if met else -1.5
                lines.append(f"Club vision ({o['text']}): {'on track' if met else 'needs work'}")
            else:
                o["track"] = "ongoing"
    board["objectives"] = objs
    if final:
        board["confidence"] = max(2.0, min(96.0, board["confidence"] + delta))
        board["last_review"] = save["date"]
        save["flags"]["last_objective_delta"] = round(delta, 1)
        failed_critical = [o["text"] for o in objs if o.get("critical") and o.get("status") == "failed"]
        if failed_critical:
            add_inbox(con, save, "BOARD", "URGENT", "Board furious: key objective missed",
                      f"The board considers the failure to meet a critical objective — "
                      f"{', '.join(failed_critical)} — a serious matter.\n\n"
                      f"Your position will be under review unless results improve next season.",
                      payload={"screen": "board"})
    return lines, delta


def _season_end(con, save, rng, events):
    cid = save["club_id"]
    c = club(con, cid)
    # --- play out anything still outstanding this season (incl. any human games missed)
    # play out any AI fixtures still outstanding, then call off the rest
    cid = save["club_id"]
    for _ in range(12):
        days = [r[0] for r in con.execute(
            """SELECT DISTINCT f.match_date FROM fixtures f JOIN competitions k ON k.id=f.comp_id
               WHERE f.season=? AND f.played=0 AND k.ctype!='friendly'
               ORDER BY f.match_date LIMIT 40""",
            (save["season"],)).fetchall()]
        if not days:
            break
        for dd in days:
            _simulate_day_matches(con, save, d(dd), rng)
            if cid and not save["flags"].get("unemployed"):
                for f in con.execute(
                        """SELECT f.*, k.name AS comp_name, k.code AS comp_code, k.ctype
                           FROM fixtures f LEFT JOIN competitions k ON k.id=f.comp_id
                           WHERE f.match_date=? AND f.played=0 AND (f.home_id=? OR f.away_id=?)""",
                        (dd, cid, cid)).fetchall():
                    play_human_match(con, save, dict(f), mode="instant", rng=rng)
            _check_competitions(con, save, rng)
        con.commit()
    con.execute("""UPDATE fixtures SET played=1, hg=0, aw=0, report='{}'
                   WHERE season=? AND played=0""", (save["season"],))
    con.commit()
    # --- league final positions, promotion / relegation
    leagues = con.execute("SELECT * FROM competitions WHERE ctype='league'").fetchall()
    summary = []
    for lg in leagues:
        rows = retable(con, save, lg["id"])
        if not rows:
            continue
        n = len(rows)
        champ = rows[0]
        champc = club(con, champ["club_id"])
        con.execute("INSERT INTO history (season,comp_id,club_id,pos,note,trophy) VALUES (?,?,?,?,?,?)",
                    (save["season"], lg["id"], champ["club_id"], 1, lg["name"] + " winners", lg["name"]))
        add_news(con, save, "LEAGUE", f"{champc['name']} win the {lg['name']}.", champ["club_id"])
        con.execute("UPDATE clubs SET reputation=MIN(97,reputation+?) WHERE id=?",
                    (2.0 if lg["tier"] == 1 else 0.8, champ["club_id"]))
        if champ["club_id"] == cid:
            save["career"]["trophies"].append({"season": save["season"], "comp": lg["name"],
                                               "type": "league"})
        # relegation / promotion (sizes stay constant: promoted == relegated)
        lower = con.execute("SELECT * FROM competitions WHERE country=? AND tier=?",
                            (lg["country"], lg["tier"] + 1)).fetchone()
        out_n = league_moves(con, lg["code"])
        in_n = league_moves(con, lower["code"]) if lower else 0
        relegated, promoted = [], []
        if lower and (in_n or out_n):
            lrows = retable(con, save, lower["id"])
            relegated = rows[max(0, n - out_n):]
            promoted = lrows[:min(in_n, len(lrows))]
            # play-off final for the last promotion place (does not add a slot)
            if lg["playoff"] and len(promoted) >= 2 and len(lrows) >= in_n + 4:
                po = lrows[in_n - 1:in_n + 3]
                w1 = po[0] if rng.random() < 0.58 else po[3]
                w2 = po[1] if rng.random() < 0.52 else po[2]
                final = w1 if rng.random() < 0.5 else w2
                promoted = promoted[:-1] + [final]
                add_news(con, save, "LEAGUE",
                         f"{club(con, final['club_id'])['name']} win the {lower['name']} play-off final.",
                         final["club_id"])
            if len(promoted) > len(relegated):
                promoted = promoted[:len(relegated)]
            elif len(relegated) > len(promoted):
                relegated = relegated[:len(promoted)]
            for r in relegated:
                move_club_league(con, r["club_id"], lower["code"])
                con.execute("INSERT INTO history (season,comp_id,club_id,pos,note,trophy) VALUES (?,?,?,?,?,?)",
                            (save["season"], lg["id"], r["club_id"], r["pos"], "Relegated", ""))
                add_news(con, save, "LEAGUE",
                         f"{club(con, r['club_id'])['name']} are relegated from the {lg['name']}.",
                         r["club_id"])
            for r in promoted:
                move_club_league(con, r["club_id"], lg["code"])
                con.execute("INSERT INTO history (season,comp_id,club_id,pos,note,trophy) VALUES (?,?,?,?,?,?)",
                            (save["season"], lower["id"], r["club_id"], r["pos"], "Promoted", ""))
                add_news(con, save, "LEAGUE",
                         f"{club(con, r['club_id'])['name']} are promoted to the {lg['name']}.",
                         r["club_id"])
            if cid in [r["club_id"] for r in relegated]:
                add_inbox(con, save, "BOARD", "URGENT", "Relegated",
                          f"You have been relegated from the {lg['name']}. The board will review your "
                          f"position and the squad faces a major rebuild.",
                          payload={"screen": "board"})
                save["board"]["confidence"] = max(18.0, save["board"]["confidence"] * 0.75)
                save["board"]["sack_risk"] = 0
                save["board"]["warning"] = False
            if cid in [r["club_id"] for r in promoted]:
                add_inbox(con, save, "BOARD", "URGENT", "Promotion!",
                          f"Promotion to the {lg['name']} secured. The board expects you to consolidate.",
                          payload={"screen": "board"})
                save["career"]["reputation"] = min(95, save["career"]["reputation"] + 4)
        summary.append((lg["name"], champc["name"]))
    # --- individual awards
    # --- objectives & history (must run before season stats/standings move on)
    prev_season = save["season"]
    pos = _league_position(con, save, season=prev_season)
    awards = _season_awards(con, save, rng, comp_id=(pos or {}).get("comp_id"))
    stats_snapshot = dict(save["season_stats"])
    xg_snapshot = (save["flags"].get("xg_season", 0.0), save["flags"].get("xga_season", 0.0))
    obj_lines, obj_delta = evaluate_objectives(con, save, rng, final=True)
    if pos and pos.get("played"):
        cc = club(con, cid)
        lg_row = con.execute("SELECT id, name FROM competitions WHERE id=?",
                             (pos.get("comp_id"),)).fetchone()
        lg_row = lg_row or con.execute("SELECT id, name FROM competitions WHERE code=?",
                                       (cc["league"],)).fetchone()
        note = f"{lg_row['name']} — finished {pos['pos']} of {pos['size']}"
        dup = con.execute("""SELECT COUNT(*) FROM history WHERE season=? AND club_id=? AND comp_id=?""",
                          (prev_season, cid, lg_row["id"])).fetchone()[0]
        if not dup:
            con.execute("INSERT INTO history (season,comp_id,club_id,pos,note,trophy) VALUES (?,?,?,?,?,?)",
                        (prev_season, lg_row["id"], cid, pos["pos"], note, ""))
        if not dup:
            save["history"].append({"season": prev_season, "comp": lg_row["name"], "club": cc["name"],
                                    "pos": pos["pos"],
                                    "note": f"{pos['pts']} points, GD {pos['gd']:+d}", "trophy": ""})
    for o in save["board"].get("objectives") or []:
        o.pop("track", None)
    # --- finances roll-up
    c = club(con, cid)
    prize = _prize_money(con, save, c, pos, save["season"])
    con.execute("UPDATE clubs SET cash=cash+?, balance=balance+? WHERE id=?", (prize, prize, cid))
    # --- contracts expiring
    fa_club = ensure_free_agent_club(con)
    expiring = con.execute("SELECT * FROM players WHERE contract_end<=?",
                           (_season_contract_end(save),)).fetchall()
    moved = 0
    for p in expiring:
        if p["club_id"] == cid:
            if p["age"] > 34 or p["ca"] < 8:
                con.execute("UPDATE players SET club_id=? WHERE id=?", (fa_club, p["id"]))
                add_inbox(con, save, "CONTRACT", "ROUTINE", f"Released: {p['name']}",
                          f"{p['name']}'s contract expired and he has left the club.")
                moved += 1
            else:
                # AI renewal
                con.execute("UPDATE players SET contract_end=?, wage=? WHERE id=?",
                            (f"{save['season'] + 3}-06-30", round(p["wage"] * 1.05, 2), p["id"]))
                add_inbox(con, save, "CONTRACT", "ROUTINE", f"Contract renewed: {p['name']}",
                          f"{p['name']} agreed a one-year extension on the same terms.")
            continue
        if p["club_id"] and p["club_id"] > 0 and p["club_id"] != fa_club:
            sc = club(con, p["club_id"])
            if sc and (p["age"] > 33 or p["ca"] < 7 or rng.random() < 0.35):
                # becomes a free agent, may join a new club
                if rng.random() < 0.7:
                    human_id = -1 if save["delegation"].get("recruitment") else save["club_id"]
                    buyers = con.execute("""SELECT * FROM clubs WHERE id!=? AND id!=? AND code!='FREE'
                        AND rep BETWEEN ? AND ? ORDER BY RANDOM() LIMIT 8""",
                        (p["club_id"], human_id, max(5, sc["rep"] - 25), sc["rep"] + 10)).fetchall()
                    if buyers:
                        b = rng.choice(buyers)
                        complete_transfer(con, save, p["id"], b["id"], 0,
                                          round(p["wage"] * rng.uniform(0.85, 1.2), 2),
                                          rng.choice([1, 2, 3]),
                                          rng.choice(["Squad Rotation", "Regular Starter", "Backup"]),
                                          rng)
                        moved += 1
                        continue
                con.execute("UPDATE players SET club_id=? WHERE id=?", (fa_club, p["id"]))
    # --- retirements
    old = con.execute("SELECT * FROM players WHERE age>=36").fetchall()
    for p in old:
        chance = 0.25 + (p["age"] - 36) * 0.22 - (p["ca"] - 8) * 0.03
        if rng.random() < max(0.02, min(0.95, chance)):
            con.execute("UPDATE players SET club_id=? WHERE id=?", (fa_club, p["id"]))
            if p["club_id"] == cid:
                add_inbox(con, save, "SQUAD", "ROUTINE", f"Retirement: {p['name']}",
                          f"{p['name']} ({p['age']}) has announced his retirement.")
    # --- youth intake
    intake = youth_intake(con, save, rng)
    # --- age everyone, reset stats
    con.execute("UPDATE players SET age=age+1, goals=0, assists=0, apps=0, minutes=0, avg_rating=0, "
                "yellow=0, red=0, form=0, injured_weeks=0, condition='fit', injury_name='', "
                "return_date='', suspended=0, fitness=92, fatigue=5, sharpness=45")
    con.execute("UPDATE players SET dob=date(dob,'-1 year')")
    # --- budgets reset
    _reset_budgets(con, save, rng)
    # --- roll to the new season, then build its fixtures
    prev_season = save["season"]
    save["season"] += 1
    save["season_stats"] = {"played": 0, "won": 0, "drawn": 0, "lost": 0, "gf": 0, "ga": 0}
    new_season(con, save, rng, prev_season)
    save["career"]["clubs"][-1]["season"] = save["season"]
    save["flags"]["xg_season"] = 0.0
    save["flags"]["xga_season"] = 0.0
    bump()
    add_inbox(con, save, "BOARD", "URGENT", f"Season review — {prev_season}/{str(prev_season + 1)[2:]}",
              season_review_text(con, save, awards, summary, prize, prev_season,
                                 pos=pos, ss=stats_snapshot, objectives=obj_lines,
                                 xg=xg_snapshot),
              payload={"screen": "career", "action": "season_review"})
    STRENGTH_CACHE.clear()


def _prize_money(con, save, c, pos, season=None):
    if not pos:
        return 0.0
    lg = con.execute("SELECT * FROM competitions WHERE id=?", (pos.get("comp_id"),)).fetchone() \
        or con.execute("SELECT * FROM competitions WHERE code=?", (c["league"],)).fetchone()
    tier = (lg["tier"] if lg else c["tier"]) or c["tier"]
    base = {1: 95.0, 2: 8.0, 3: 2.2, 4: 1.4, 5: 0.4}.get(tier, 1.0)
    share = base * (1.4 - pos["pos"] / max(1, pos["size"]))
    # continental bonus
    for code, bonus in (("UCL", 60.0), ("UEL", 18.0), ("UECL", 8.0)):
        cc = con.execute("SELECT id FROM competitions WHERE code=?", (code,)).fetchone()
        if cc:
            r = con.execute("SELECT pos, p FROM standings WHERE comp_id=? AND season=? AND club_id=? AND stage='league'",
                            (cc["id"], season or save["season"], save["club_id"])).fetchone()
            if r and r["p"] > 0:
                share += bonus * (1.2 - min(1.0, r["pos"] / 40.0))
    return round(max(0.1, share), 2)


def _season_awards(con, save, rng, comp_id=None):
    cid = save["club_id"]
    awards = {}
    ps = load_players(con, cid)
    ft = [p for p in ps if p["squad"] in ("First Team", "Reserve") and p["apps"] > 0]
    if ft:
        top_scorer = max(ft, key=lambda p: p["goals"])
        top_assist = max(ft, key=lambda p: p["assists"])
        poty = max(ft, key=lambda p: (p["avg_rating"] or 0) * 0.6 + (p["goals"] + p["assists"]) * 0.08)
        young = [p for p in ft if p["age"] <= 21]
        break_ = max(young, key=lambda p: p["minutes"]) if young else None
        awards = {"top_scorer": (top_scorer["name"], top_scorer["goals"]),
                  "top_assist": (top_assist["name"], top_assist["assists"]),
                  "player_of_season": (poty["name"], round(poty["avg_rating"] or 0, 2)),
                  "breakthrough": (break_["name"], break_["minutes"]) if break_ else None}
    # divisional golden boot (the league the club actually played in)
    gb = None
    if comp_id:
        gb = con.execute("""SELECT p.name, p.goals, c.name club FROM players p
            JOIN clubs c ON c.id=p.club_id
            WHERE p.goals>0 AND c.code!='FREE' AND c.id IN
              (SELECT club_id FROM standings WHERE comp_id=? AND season=? AND stage='league')
            ORDER BY p.goals DESC, p.apps ASC LIMIT 1""",
            (comp_id, save["season"])).fetchone()
    if not gb:
        gb = con.execute("""SELECT p.name, p.goals, c.name club FROM players p
            JOIN clubs c ON c.id=p.club_id
            WHERE p.goals>0 AND c.code!='FREE' ORDER BY p.goals DESC LIMIT 1""").fetchone()
    if gb:
        awards["golden_boot"] = (gb["name"], gb["club"], gb["goals"])
    return awards


def season_review_text(con, save, awards, summary, prize, season=None, pos=None, ss=None,
                       objectives=None, xg=None):
    cid = save["club_id"]
    c = club(con, cid)
    ssn = season or save["season"]
    pos = pos if pos is not None else _league_position(con, save, season=ssn)
    ss = ss or save["season_stats"]
    lines = [f"SEASON REVIEW — {ssn}/{str(ssn + 1)[2:]}", ""]
    if pos and pos.get("played"):
        lg = con.execute("SELECT name FROM competitions WHERE id=?", (pos.get("comp_id"),)).fetchone() \
            or con.execute("SELECT name FROM competitions WHERE code=?", (c["league"],)).fetchone()
        lines.append(f"League: {lg['name'] if lg else c['league']}")
        lines.append(f"Final position: {pos['pos']} of {pos['size']} — {pos['pts']} points (GD {pos['gd']:+d})")
    lines.append(f"Record (all competitions): {ss['played']} played, {ss['won']} W, {ss['drawn']} D, "
                 f"{ss['lost']} L — {ss['gf']}:{ss['ga']}")
    if xg is None:
        xg = (save["flags"].get("xg_season", 0.0), save["flags"].get("xga_season", 0.0))
    xg, xga = xg
    if ss["played"]:
        lines.append(f"Goals vs xG: scored {ss['gf']} (xG {xg:.1f}), conceded {ss['ga']} (xGA {xga:.1f})")
    if awards:
        if awards.get("top_scorer"):
            lines.append(f"Top scorer: {awards['top_scorer'][0]} ({awards['top_scorer'][1]})")
        if awards.get("top_assist"):
            lines.append(f"Top assister: {awards['top_assist'][0]} ({awards['top_assist'][1]})")
        if awards.get("player_of_season"):
            lines.append(f"Player of the season: {awards['player_of_season'][0]} (avg {awards['player_of_season'][1]})")
        if awards.get("breakthrough"):
            lines.append(f"Breakthrough player: {awards['breakthrough'][0]} ({awards['breakthrough'][1]} mins)")
    if awards.get("golden_boot"):
        lines.append(f"Divisional golden boot: {awards['golden_boot'][0]} ({awards['golden_boot'][1]}) — {awards['golden_boot'][2]} goals")
    lines.append(f"Prize money: {money(prize)}")
    fin = con.execute("SELECT cash, balance, wage_bill, transfer_budget FROM clubs WHERE id=?", (cid,)).fetchone()
    lines.append(f"Financial result: balance {money(fin['balance'])}, cash {money(fin['cash'])}")
    lines.append(f"Board confidence: {save['board']['confidence']:.0f}/100")
    lines.append(f"Fan sentiment: {save['fans']['sentiment']:.0f}/100")
    lines.append(f"Manager reputation: {save['career']['reputation']:.1f}/100")
    if objectives:
        lines.append("")
        lines.append("BOARD OBJECTIVES")
        lines.extend("  • " + x for x in objectives)
        lines.append(f"  → board confidence adjusted by {save['flags'].get('last_objective_delta', 0):+.1f}")
    tro = [t for t in save["career"]["trophies"] if t["season"] == ssn]
    if tro:
        lines.append("\nTROPHIES: " + ", ".join(t["comp"] for t in tro))
    return "\n".join(lines)


def _reset_budgets(con, save, rng):
    c = club(con, save["club_id"])
    board = save["board"]
    conf = board["confidence"]
    scale = 0.72 + conf / 180.0
    new_inc = c["season_income"] * (1.02 + (conf - 50) / 900.0)
    tb = round(max(0.0, c["transfer_budget"] * scale + (c["balance"] * 0.35 if c["balance"] > 0 else c["balance"] * 0.6)), 2)
    wb_new = round(min(c["wage_budget"] * (0.97 + conf / 700.0), max(new_inc * 0.72, c["wage_bill"] * 1.02)), 2)
    con.execute("""UPDATE clubs SET season_income=?, transfer_budget=?, wage_budget=?, reputation=reputation
        WHERE id=?""", (round(new_inc, 2), tb, wb_new, c["id"]))
    add_inbox(con, save, "FINANCE", "IMPORTANT", "New season budget",
              f"The board has set your budget for the new season.\n\n"
              f"Transfer budget: {money(tb)}\nWage budget: {money(c['wage_budget'] * (0.97 + conf / 700.0))}\n"
              f"Projected revenue: {money(new_inc)}\n\nBoard confidence: {conf:.0f}/100",
              payload={"screen": "finances"})


def youth_intake(con, save, rng):
    cid = save["club_id"]
    c = club(con, cid)
    n = rng.randint(3, 6) if c["youth"] > 12 else rng.randint(2, 4)
    out = []
    maxid = con.execute("SELECT COALESCE(MAX(id),0) FROM players").fetchone()[0]
    from .world import _attr_vector, fit_ca, pack_attrs
    for k in range(n):
        maxid += 1
        pos = rng.choice(["GK", "DC", "DC", "DL", "DR", "DM", "MC", "MC", "AMC", "AML", "AMR", "ST", "ST"])
        age = rng.choice([16, 17, 17, 18])
        base = 4.5 + c["youth"] * 0.28 + rng.gauss(0, 1.6) + (c["rep"] / 100.0)
        ca = max(3.0, min(12.5, base))
        pa = min(20.0, ca + abs(rng.gauss(2.4, 1.9)) * (0.55 + c["youth"] / 30.0))
        vec = fit_ca(_attr_vector(rng, pos, ca, age), ca)
        rca = compute_ca(vec)
        nat = c["country"] if rng.random() < 0.85 else rng.choice(NATIONALITY_POOL)
        nm = make_name(rng, nat)
        con.execute("""INSERT INTO players (id,name,nat,age,dob,pos,foot,height,club_id,squad,attrs,ca,pa,
            value,wage,contract_end,personality,professionalism,ambition,loyalty,pressure,consistency,
            big_games,injury_prone,fitness,sharpness,morale,confidence,happiness,condition,hidden_seed,
            reputation,languages) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (maxid, nm, nat, age, f"{2026 + (save['season'] - 2026) - age}-05-01", pos,
                     rng.choice(["R", "L"]), rng.randint(165, 188), cid, "Youth", pack_attrs(vec),
                     round(rca, 2), round(pa, 2),
                     round(value_of(rca, pa, age, pos, c["rep"], 3, 1.0), 2),
                     round(wage_of(ca, age, 1.0, c["rep"]) * 0.18, 2),
                     f"{2026 + (save['season'] - 2026) + 3}-06-30",
                     rng.choice(C.PERSONALITIES), rng.randint(6, 20), rng.randint(6, 20),
                     rng.randint(5, 18), rng.randint(4, 16), rng.randint(5, 16), rng.randint(5, 18),
                     rng.randint(1, 10), 100, 60, 70, 60, 60, "fit", _seed(nm + str(maxid)),
                     round(c["rep"] * 0.12, 1), nat))
        out.append(dict(name=nm, age=age, pos=pos, ca=round(rca, 1), pa=round(pa, 1)))
    out.sort(key=lambda x: -x["pa"])
    add_inbox(con, save, "YOUTH", "IMPORTANT", f"Youth intake — {save['season']}",
              f"{len(out)} youngsters have signed scholarship forms.\n\n" +
              "\n".join(f"- {o['name']}, {o['age']}, {o['pos']} — potential {o['pa']:.1f}/20" for o in out),
              payload={"screen": "squad", "filter": "Youth"})
    return out


def new_season(con, save, rng, prev_season=None):
    """Create fixtures for the new season (leagues + cup first rounds + continental)."""
    season = save["season"]
    c = club(con, save["club_id"])
    maxid = con.execute("SELECT COALESCE(MAX(id),0) FROM fixtures").fetchone()[0]
    leagues = con.execute("SELECT * FROM competitions WHERE ctype='league'").fetchall()
    new_fix = []
    for lg in leagues:
        members = [r["id"] for r in con.execute("SELECT id FROM clubs WHERE league=?", (lg["code"],)).fetchall()]
        if len(members) < 3:
            continue
        rng.shuffle(members)
        rounds = _double_rr(members, rng)
        start = date(season, 4, 4) if lg["country"] in ("Brazil", "Argentina") \
            else date(season, 8, 8)
        wk = 0
        for i, rnd in enumerate(rounds):
            dt = start + timedelta(days=7 * i)
            for h, a in rnd:
                maxid += 1
                new_fix.append((maxid, lg["id"], season, i + 1, "league", dt.isoformat(), h, a,
                                None, None, 0, None, None, 1, None, None, None, None, None))
        con.execute("DELETE FROM standings WHERE comp_id=? AND season>=?", (lg["id"], season))
        con.execute("DELETE FROM fixtures WHERE comp_id=? AND season>=?", (lg["id"], season))
        con.executemany("INSERT INTO standings VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        [(lg["id"], season, m, "league", 0, 0, 0, 0, 0, 0, 0, "", 0) for m in members])
    # cup entries reset: first round draws
    for code, rounds in CUP_ROUNDS.items():
        crow = con.execute("SELECT * FROM competitions WHERE code=?", (code,)).fetchone()
        if not crow:
            continue
        tiers = {"FACUP": (1, 2, 3, 4, 5), "EFLCUP": (1, 2, 3, 4)}.get(code, (1, 2))
        teams = [r["id"] for r in con.execute("""SELECT c.id FROM clubs c
            JOIN competitions k ON k.code=c.league
            WHERE k.country=? AND k.ctype='league' AND c.tier<=? AND c.code!='FREE' AND c.id>0""",
            (crow["country"], max(tiers))).fetchall()]
        if len(teams) < 4:
            teams = [r["id"] for r in con.execute("""SELECT c.id FROM clubs c
                JOIN competitions k ON k.code=c.league
                WHERE k.country=? AND k.ctype='league' AND c.code!='FREE' AND c.id>0""",
                (crow["country"],)).fetchall()]
        rng.shuffle(teams)
        stage, dt = rounds[0]
        nd = _cup_round_date(dt, season, crow["country"])  # str date
        con.execute("DELETE FROM standings WHERE comp_id=? AND season=?", (crow["id"], season))
        for i in range(0, len(teams) - 1, 2):
            maxid += 1
            new_fix.append((maxid, crow["id"], season, 1, stage, nd, teams[i], teams[i + 1],
                            None, None, 0, None, None, 1, None, None, None, None, None))
        if len(teams) % 2:
            con.execute("""INSERT OR IGNORE INTO standings
                (comp_id,season,club_id,stage,p,w,d,l,gf,ga,pts,form,pos)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (crow["id"], season, teams[-1], stage, 1, 1, 0, 0, 0, 0, 3, "", 1))
    # continental: re-qualify by reputation + final position
    euro = con.execute("""SELECT c.id, c.rep, c.country FROM clubs c WHERE c.country IN
        ('England','Spain','Italy','Germany','France','Netherlands','Portugal','Scotland','Belgium','Turkey')
        AND c.tier=1""").fetchall()
    # rank by league position
    ranked = []
    for cl in euro:
        lgrow = con.execute("SELECT league FROM clubs WHERE id=?", (cl["id"],)).fetchone()
        comp_id = con.execute("SELECT id FROM competitions WHERE code=?", (lgrow["league"],)).fetchone()
        st = con.execute("SELECT pos FROM standings WHERE comp_id=? AND season=? AND club_id=? AND stage='league'",
                         (comp_id["id"], prev_season or save["season"], cl["id"])).fetchone() if comp_id else None
        pos = st["pos"] if st else 99
        ranked.append((pos, -cl["rep"], cl["id"]))
    ranked.sort()
    slots = {"UCL": 36, "UEL": 36, "UECL": 36}
    idx = 0
    for code, n in slots.items():
        crow = con.execute("SELECT * FROM competitions WHERE code=?", (code,)).fetchone()
        if not crow:
            continue
        teams = [ranked[i][2] for i in range(idx, min(idx + n, len(ranked)))]
        idx += n
        con.execute("DELETE FROM entries WHERE comp_id=? AND season=?", (crow["id"], season))
        con.executemany("INSERT INTO entries VALUES (?,?,?)", [(crow["id"], t, season) for t in teams])
        con.execute("DELETE FROM standings WHERE comp_id=? AND season=?", (crow["id"], season))
        con.executemany("INSERT INTO standings VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        [(crow["id"], season, t, "league", 0, 0, 0, 0, 0, 0, 0, "", 0) for t in teams])
        rng2 = random.Random(_seed(code + str(season)))
        played = {t: set() for t in teams}
        md_dates = [date(season, 9, 14), date(season, 9, 28), date(season, 10, 19),
                    date(season, 11, 2), date(season, 11, 23), date(season, 12, 7),
                    date(season + 1, 1, 18), date(season + 1, 1, 25)]
        for md, dt in enumerate(md_dates):
            order2 = teams[:]
            rng2.shuffle(order2)
            used = set()
            for t in order2:
                if t in used:
                    continue
                opp = None
                for cand in order2:
                    if cand != t and cand not in used and cand not in played[t]:
                        opp = cand
                        break
                if opp is None:
                    used.add(t)
                    continue
                used.add(t); used.add(opp)
                played[t].add(opp); played[opp].add(t)
                h, a = (t, opp) if md % 2 == 0 else (opp, t)
                maxid += 1
                new_fix.append((maxid, crow["id"], season, md + 1, "league", dt.isoformat(), h, a,
                                None, None, 0, None, None, 1, None, None, None, None, None))
    if new_fix:
        con.executemany("""INSERT INTO fixtures (id,comp_id,season,round,stage,match_date,home_id,away_id,
            hg,aw,played,agg_h,agg_a,leg,venue,attendance,rating_h,rating_a,report)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", new_fix)
    # clear old KO fixtures/stages for the new season handled by season key
    save["flags"] = {k: v for k, v in save["flags"].items() if not k.startswith("awarded_")}
    save["flags"]["pt_complaints"] = {}
    refresh_promises(con, save)
    snapshot_youth(con, save)
    add_inbox(con, save, "COMPETITION", "ROUTINE", f"Season {season}/{str(season + 1)[2:]} fixtures released",
              "The fixtures for the new season have been released. Pre-season begins now.",
              payload={"screen": "calendar"})


def _double_rr(teams, rng):
    t = list(teams)
    if len(t) % 2:
        t.append(None)
    n = len(t)
    rounds = []
    for r in range(n - 1):
        rnd = []
        for i in range(n // 2):
            a, b = t[i], t[n - 1 - i]
            if a is None or b is None:
                continue
            rnd.append((a, b) if (i + r) % 2 == 0 else (b, a))
        rounds.append(rnd)
        t = [t[0]] + [t[-1]] + t[1:-1]
    second = [[(a, b) for (b, a) in rnd] for rnd in rounds]
    allr = rounds + second
    rng.shuffle(allr)
    return allr


# ------------------------------------------------------------------- advancing
def unread_urgent(con, save, cats=("BOARD", "MEDICAL", "TRANSFER")):
    rows = con.execute("""SELECT * FROM inbox WHERE read=0 AND priority='URGENT' AND cat IN (%s)
        ORDER BY id DESC LIMIT 6""" % ",".join("?" * len(cats)), cats).fetchall()
    return [dict(r) for r in rows]


def advance(con, save, days=1, until=None, stop_for=("match",), rng=None, ignore_ids=(), auto_human=False):
    """Advance the simulation. Stops at the next meaningful event.

    ignore_ids: unread-urgent message ids the manager has already been shown, so
    they must not halt the simulation again.
    auto_human: if True, human fixtures on the advanced days are auto-played (only
                used for season-end sweep). Defaults to False to prevent the
                '38 games played' bug where Continue auto-played competitive matches.
                set explicitly to False when advancing to a fixture that the user
                wants to play manually (prevents double-play bug).
    """
    rng = rng or random.Random()
    ignore = set(ignore_ids or ())
    start = d(save["date"])
    target = None
    mode = until or "days"
    if save["flags"].get("unemployed") and mode == "match":
        mode = "week"
    if mode == "days":
        target = start + timedelta(days=int(days))
    elif mode == "match":
        nf = next_fixture(con, save)
        target = d(nf["match_date"]) if nf else start + timedelta(days=int(days))
    elif mode == "deadline":
        W = season_windows(save["season"])
        target = W["close"] if start < W["close"] else W["winter"][1]
    elif mode == "month":
        y, m = start.year, start.month
        nm = date(y + (m // 12), (m % 12) + 1, 1)
        target = nm
    elif mode == "window_open":
        W = season_windows(save["season"])
        target = W["open"] if start < W["open"] else W["winter"][0]
    elif mode == "season_end":
        target = date(save["season"] + 1, 7, 20)
    elif mode == "date":
        target = d(days)
    elif mode == "week":
        target = start + timedelta(days=7)
    log = []
    guard = 0
    stop_reason = None
    # auto_human now defaults False; old derived logic removed to fix 38-games bug
    while d(save["date"]) < target and guard < 900:
        guard += 1
        if save["flags"].get("unemployed"):
            stop_reason = "unemployed"
        nxt = d(save["date"]) + timedelta(days=1)
        my_fix = fixtures_on(con, nxt, save["club_id"])
        competitive = [f for f in my_fix]
        if competitive and "match" in stop_for:
            stop_reason = "match"
            log.append({"date": ds(nxt), "event": "match_scheduled",
                        "fixtures": [{"id": f["id"], "comp": f.get("comp_name") or "Friendly",
                                      "home": (club(con, f["home_id"]) or {}).get("short", "?"),
                                      "away": (club(con, f["away_id"]) or {}).get("short", "?"),
                                      "is_home": f["home_id"] == save["club_id"],
                                      "stage": f.get("stage")} for f in competitive]})
            break
        evs = tick_day(con, save, rng, auto_human=auto_human)
        for e in evs:
            log.append(dict(date=save["date"], **e))
        urg = [u for u in unread_urgent(con, save) if u["id"] not in ignore]
        if urg and "urgent" in stop_for:
            stop_reason = "urgent"
            log.append({"date": save["date"], "event": "urgent_mail",
                        "items": [{"id": u["id"], "cat": u["cat"], "subject": u["subject"]} for u in urg]})
            break
        con.commit()
        persist(con, save)
    # catch any overdue human fixture that was not played — only auto-play if explicitly allowed
    # to prevent the "38 games show as played" bug where Continue with until=week/month
    # would skip matches and auto-play them.
    if auto_human:
        overdue = [] if not save.get("club_id") or save["flags"].get("unemployed") else con.execute(
            """SELECT f.*, k.name AS comp_name, k.code AS comp_code, k.ctype FROM fixtures f
            LEFT JOIN competitions k ON k.id=f.comp_id
            WHERE (f.home_id=? OR f.away_id=?) AND f.played=0 AND f.match_date<? ORDER BY f.match_date""",
            (save["club_id"], save["club_id"], save["date"])).fetchall()
        for f in overdue:
            play_human_match(con, save, dict(f), mode="instant", rng=rng)
    else:
        # if we have overdue competitive fixtures and auto_human is False, rewind date
        # to the earliest overdue fixture so user can still play it (prevents skipping)
        if save.get("club_id") and not save["flags"].get("unemployed"):
            earliest = con.execute(
                """SELECT MIN(match_date) FROM fixtures
                   WHERE (home_id=? OR away_id=?) AND played=0 AND match_date<? AND comp_id!=0""",
                (save["club_id"], save["club_id"], save["date"])).fetchone()[0]
            if earliest:
                # don't auto-play, but ensure next_fixture can still find it by rewinding date
                # we keep save["date"] at earliest-1 so next advance will stop at match
                try:
                    ed = d(earliest)
                    if d(save["date"]) > ed:
                        save["date"] = ds(ed - timedelta(days=1))
                except Exception:
                    pass
    con.commit()
    persist(con, save)
    if d(save["date"]) < start:                 # never move the clock backwards
        save["date"] = ds(start)
    return {"stop_reason": stop_reason, "log": log, "date": save["date"],
            "days_advanced": (d(save["date"]) - start).days}


def play_next_match(con, save, mode="key", rng=None, lineup=None):
    if save["flags"].get("unemployed") or not save.get("club_id"):
        return {"ok": False, "msg": "You are without a club.", "unemployed": True}
    nf = next_fixture(con, save)
    if not nf:
        return {"ok": False, "msg": "No upcoming fixture."}
    if nf["match_date"] > save["date"]:
        advance(con, save, until="date", days=nf["match_date"], rng=rng, stop_for=(), auto_human=False)
        nf = next_fixture(con, save)
        if not nf:
            return {"ok": False, "msg": "No upcoming fixture after advancing."}
    row = con.execute("""SELECT f.*, k.name AS comp_name, k.code AS comp_code, k.ctype
        FROM fixtures f LEFT JOIN competitions k ON k.id=f.comp_id WHERE f.id=?""", (nf["id"],)).fetchone()
    nf = dict(row)
    data = play_human_match(con, save, nf, mode=mode, rng=rng, custom_lineup=lineup)
    con.commit()
    persist(con, save)
    return {"ok": True, "fixture": nf, "data": data}


# ------------------------------------------------------------------ delegation
def set_training(con, save, day, session, focus=""):
    if session not in C.TRAINING_SESSIONS:
        return {"ok": False, "msg": "Unknown session."}
    con.execute("INSERT INTO training (club_id,day,session,focus) VALUES (?,?,?,?) "
                "ON CONFLICT(club_id,day) DO UPDATE SET session=excluded.session, focus=excluded.focus",
                (save["club_id"], int(day), session, focus))
    return {"ok": True}


def set_tactics(con, save, formation=None, mentality=None, instr=None, roles=None, name=None):
    t = get_tactics(con, save)
    changed_shape = False
    if formation and formation != t["formation"]:
        if formation not in C.FORMATIONS:
            return {"ok": False, "msg": "Unknown formation."}
        changed_shape = True
        save_tactics(con, save, formation=formation)
    if mentality and mentality != t["mentality"]:
        if mentality not in C.MENTALITIES:
            return {"ok": False, "msg": "Unknown mentality."}
        save_tactics(con, save, mentality=mentality)
        changed_shape = True
    if instr is not None:
        merged = dict(t["instr"])
        merged.update(instr)
        for k, v in list(merged.items()):
            if k in C.INSTRUCTIONS and v not in C.INSTRUCTIONS[k]:
                merged[k] = C.INSTR_DEFAULT[k]
        save_tactics(con, save, instr=merged)
        if any(merged.get(k) != t["instr"].get(k) for k in
               ("line_of_engagement", "defensive_line", "pressing_intensity")):
            changed_shape = True
    if roles is not None:
        merged = dict(t["roles"])
        merged.update({str(k): v for k, v in roles.items()})
        save_tactics(con, save, roles=merged)
        changed_shape = True
    if name:
        save_tactics(con, save, name=name)
    if changed_shape:
        newfam = max(8.0, t["familiarity"] * 0.62)
        save_tactics(con, save, familiarity=round(newfam, 1))
        save["tactic_history"].append({"date": save["date"], "formation": formation or t["formation"],
                                       "mentality": mentality or t["mentality"],
                                       "familiarity_before": t["familiarity"],
                                       "familiarity_after": round(newfam, 1)})
    return {"ok": True, "msg": "Tactics updated." + (" Familiarity dropped after the change." if changed_shape else "")}


def select_xi(con, save, ids):
    if len(ids) != 11:
        return {"ok": False, "msg": "Select exactly 11 players."}
    t = get_tactics(con, save)
    slots = C.FORMATIONS.get(t["formation"], C.FORMATIONS["4-2-3-1 Wide"])
    players = {p["id"]: p for p in load_players(con, save["club_id"])}
    missing = [i for i in ids if i not in players]
    if missing:
        return {"ok": False, "msg": "Some players are not in your squad."}
    for i in ids:
        p = players[i]
        if p["condition"] != "fit":
            return {"ok": False, "msg": f"{p['name']} is injured ({p['injury_name']})."}
        if p["suspended"]:
            return {"ok": False, "msg": f"{p['name']} is suspended ({p['suspended']} matches)."}
    gk = sum(1 for i in ids if players[i]["pos"] == "GK")
    if gk != 1:
        return {"ok": False, "msg": "You must select exactly one goalkeeper."}
    save["flags"]["selected_xi"] = json.dumps(ids)
    persist(con, save)
    return {"ok": True, "msg": "Team selected."}


def auto_pick(con, save):
    save["flags"]["selected_xi"] = "[]"
    persist(con, save)
    return {"ok": True, "msg": "Team selection delegated to the assistant."}


def advise(con, save):
    """Godfather mode: a short, prioritised list of actionable briefings."""
    items = []
    cid = save.get("club_id")
    if not cid or save["flags"].get("unemployed"):
        return items
    today = save["date"]
    urg = con.execute(
        "SELECT COUNT(*) FROM inbox WHERE read=0 AND priority='URGENT'").fetchone()[0]
    if urg:
        items.append(dict(tag="INBOX", t=f"{urg} urgent message(s) on your desk",
                          b="Ignored urgent mail sours the board and the press. Answer it before anything else.",
                          go="inbox"))
    nfr = con.execute("""SELECT f.match_date, f.home_id, c1.name AS hn, c2.name AS an
        FROM fixtures f JOIN clubs c1 ON c1.id=f.home_id JOIN clubs c2 ON c2.id=f.away_id
        WHERE (f.home_id=? OR f.away_id=?) AND f.played=0 AND f.match_date>=?
        ORDER BY f.match_date LIMIT 1""", (cid, cid, today)).fetchone()
    nf = dict(nfr) if nfr else None
    rows = con.execute("""SELECT name, pos, ca, fitness, contract_end FROM players
        WHERE club_id=? AND squad IN ('First Team','Reserve')""", (cid,)).fetchall()
    if nf and nf["match_date"] == today:
        opp = nf["an"] if nf["home_id"] == cid else nf["hn"]
        items.append(dict(tag="MATCH", t=f"Matchday: {nf['hn']} v {nf['an']}",
                          b=f"Pick your XI and team talk in the match centre, then kick off against {opp}.",
                          go="match"))
    if rows:
        avg = sum(r[2] for r in rows) / len(rows)
        groups = {"GK": [], "DEF": [], "MID": [], "ATT": []}
        for nm, pos, ca, fit, ce in rows:
            if fit < 85:
                continue
            g = ("GK" if pos == "GK" else "DEF" if pos in ("DC", "DL", "DR")
                 else "MID" if pos in ("DM", "MC", "AMC") else "ATT")
            groups[g].append((ca, nm))
        weak = [g for g, v in groups.items() if len(v) < 2]
        if weak:
            items.append(dict(tag="TRANSFERS", t="Thin squad: " + ", ".join(weak),
                              b="You cannot cover injuries or rotation in these areas. Scout and bid before the window shuts.",
                              go="transfers"))
        exp = sorted([nm for nm, pos, ca, fit, ce in rows
                      if ce <= "2027-06-30" and ca >= avg + 0.5])
        if exp:
            t = (f"{exp[0]} and {len(exp) - 1} more out of contract in 2027" if len(exp) > 1
                 else f"{exp[0]} is out of contract in 2027")
            items.append(dict(tag="CONTRACTS", t=t,
                              b="Open negotiations now or lose them for nothing next summer.",
                              go="squad"))
        fit_avg = sum(r[3] for r in rows) / len(rows)
        if fit_avg < 88:
            items.append(dict(tag="TRAINING", t="Squad fitness slipping",
                              b="Ease the training load or rotate: tired legs lose matches late.",
                              go="training"))
        if nf and nf["match_date"] > today:
            best = sorted(rows, key=lambda r: -r[2])[:3]
            items.append(dict(tag="PREP", t=f"Next: {nf['hn']} v {nf['an']} on {nf['match_date']}",
                              b="Lean on " + ", ".join(b[0] for b in best) +
                                " — your three best available players right now.",
                              go="match"))
    bc = save["board"]["confidence"]
    if bc < 50:
        items.append(dict(tag="BOARD", t=f"Board confidence {bc:.0f}/100 — danger zone",
                          b="Results first, then calm press answers. Two wins in a row buys you time.",
                          go="inbox"))
    fin = save.get("finances", {})
    if fin.get("wage_bill", 0) > fin.get("wage_budget", 0):
        items.append(dict(tag="FINANCE", t="Wage bill over budget",
                          b="Sell or release high earners before the board forces fire sales.",
                          go="finances"))
    return items[:5]


_GOD_GRP = {"GK": "GK", "DC": "DEF", "DL": "DEF", "DR": "DEF", "DM": "MID", "MC": "MID",
            "AMC": "AM", "AML": "AM", "AMR": "AM", "ST": "ATT"}


def godfather_plan(con, save):
    """Concrete actionable plan: best XI, match tactics, transfer targets."""
    cid = save.get("club_id")
    plan = {"xi": [], "xi_names": [], "tactics": None, "sign": [], "opp": None}
    if not cid or save["flags"].get("unemployed"):
        return plan
    tac = get_tactics(con, save)
    slots = C.FORMATIONS.get(tac["formation"], list(C.FORMATIONS.values())[0])
    rows = [dict(r) for r in con.execute(
        "SELECT id,name,pos,pos2,ca,fitness,suspended,injured_weeks FROM players "
        "WHERE club_id=? AND squad IN ('First Team','Reserve')", (cid,))]
    avail = [p for p in rows if not p["suspended"] and not p["injured_weeks"]
             and p["fitness"] >= 75]
    used, xi = set(), []

    def fits(p, slot):
        g = _GOD_GRP.get(slot)
        return (p["pos"] == slot or p["pos2"] == slot
                or _GOD_GRP.get(p["pos"]) == g or _GOD_GRP.get(p["pos2"]) == g)

    for slot in slots:
        cands = [p for p in avail if p["id"] not in used and fits(p, slot)]
        if not cands:
            cands = [p for p in avail if p["id"] not in used]
        if not cands:
            break
        pick = max(cands, key=lambda p: p["ca"])
        used.add(pick["id"])
        xi.append(pick)
    plan["xi"] = [p["id"] for p in xi]
    plan["xi_names"] = [f"{p['pos']} · {p['name']}" for p in xi]
    nf = con.execute("""SELECT f.home_id,f.away_id,c1.name hn,c2.name an FROM fixtures f
        JOIN clubs c1 ON c1.id=f.home_id JOIN clubs c2 ON c2.id=f.away_id
        WHERE (f.home_id=? OR f.away_id=?) AND f.played=0 AND f.match_date>=?
        ORDER BY f.match_date LIMIT 1""", (cid, cid, save["date"])).fetchone()
    if nf:
        opp = nf["away_id"] if nf["home_id"] == cid else nf["home_id"]
        q = ("SELECT AVG(ca) c FROM (SELECT ca FROM players WHERE club_id=? "
             "AND squad='First Team' ORDER BY ca DESC LIMIT 11)")
        my = con.execute(q, (cid,)).fetchone()["c"] or 10.0
        op = con.execute(q, (opp,)).fetchone()["c"] or 10.0
        diff = my - op
        plan["opp"] = {"name": nf["an"] if nf["home_id"] == cid else nf["hn"],
                       "my": round(my, 1), "their": round(op, 1), "diff": round(diff, 1)}
        instr = dict(C.INSTR_DEFAULT)
        if diff >= 1.2:
            ment = "Attacking"
            instr.update(line_of_engagement=3, defensive_line=3, tempo=3, width=3,
                         pressing_intensity=3, counter_press=True, work_ball_into_box=True)
            why = "we are the stronger side — press high and pin them in"
        elif diff <= -0.8:
            ment = "Cautious"
            instr.update(line_of_engagement=1, defensive_line=1, tempo=1, width=1,
                         pressing_intensity=1, counter_attack=True, counter_press=False)
            why = "they are stronger — stay compact, hurt them on the break"
        else:
            ment = "Balanced"
            instr.update(pressing_intensity=3, counter_press=True)
            why = "evenly matched — control the middle with a measured press"
        plan["tactics"] = {"mentality": ment, "instr": instr, "why": why,
                           "formation": tac["formation"]}
    fin = con.execute("SELECT transfer_budget, wage_budget - wage_bill AS head FROM clubs "
                      "WHERE id=?", (cid,)).fetchone()
    budget = (fin["transfer_budget"] if fin else 0) or 0
    head = (fin["head"] if fin else 0) or 0
    need = {}
    for p in rows:
        g = _GOD_GRP.get(p["pos"], "MID")
        need[g] = need.get(g, 0) + 1
    cands = con.execute("""SELECT p.id,p.name,p.pos,p.age,p.ca,p.pa,p.value,p.wage,c.name AS club
        FROM players p JOIN clubs c ON c.id=p.club_id
        WHERE p.club_id<>? AND p.squad='First Team' AND p.age BETWEEN 17 AND 29
          AND p.loaned_to IS NULL AND p.value <= ? ORDER BY p.ca DESC LIMIT 300""",
        (cid, max(budget * 0.6, 500.0))).fetchall()
    scored = []
    for r in cands:
        if r["value"] > budget * 0.6 or r["wage"] * 0.052 > max(head * 0.4, 1.0):
            continue
        g = _GOD_GRP.get(r["pos"], "MID")
        nb = 2.0 if need.get(g, 0) < 4 else 0.0
        scored.append((r["ca"] + 0.4 * r["pa"] + nb, dict(r), g, nb))
    scored.sort(key=lambda x: -x[0])
    for _sc, r, g, nb in scored[:3]:
        plan["sign"].append({"pid": r["id"], "name": r["name"], "pos": r["pos"],
                             "age": r["age"], "ca": round(r["ca"], 1), "pa": round(r["pa"], 1),
                             "club": r["club"], "value": r["value"], "wage": r["wage"],
                             "why": ("covers our thin " + g) if nb else "best quality we can afford"})
    return plan
