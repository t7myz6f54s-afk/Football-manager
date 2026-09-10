"""Presentation layer: read-only projections of the simulation state for the UI.

Every function here reads the world DB + save and returns plain JSON-friendly
dicts. No simulation happens in this module.
"""
import json

from . import constants as C
from . import match as M
from . import engine as E

ATTR_GROUPS = {
    "Technical": ["corners", "crossing", "dribbling", "finishing", "first_touch", "free_kicks",
                  "heading", "long_shots", "long_throws", "marking", "passing", "penalty_taking",
                  "tackling", "technique"],
    "Mental": ["aggression", "anticipation", "bravery", "composure", "concentration", "decisions",
               "determination", "flair", "leadership", "off_the_ball", "positioning", "teamwork",
               "vision", "work_rate"],
    "Physical": ["acceleration", "agility", "balance", "jumping_reach", "natural_fitness", "pace",
                 "stamina", "strength"],
    "Goalkeeping": ["aerial_ability", "command_of_area", "communication", "eccentricity",
                    "handling", "kicking", "one_on_ones", "reflexes", "rushing_out",
                    "tendency_to_punch", "throwing"],
}


def _attr_colour(v):
    if v >= 17:
        return "elite"
    if v >= 14:
        return "good"
    if v >= 11:
        return "avg"
    if v >= 8:
        return "poor"
    return "bad"


def star_rating(ca, club_ca):
    diff = ca - club_ca
    stars = 2.5 + diff * 0.42
    return round(max(0.5, min(5.0, stars)) * 2) / 2


def boot():
    return {
        "formations": list(C.FORMATIONS),
        "mentalities": list(C.MENTALITIES),
        "roles": {k: v for k, v in C.ROLES.items()},
        "duties": C.DUTIES,
        "instructions": dict(C.INSTR_DEFAULT),
        "instruction_options": {k: list(v) for k, v in C.INSTRUCTIONS.items()},
        "training_sessions": list(C.TRAINING_SESSIONS),
        "promises": list(C.PLAYING_TIME_PROMISES),
        "positions": list(C.POSITIONS),
        "attr_groups": ATTR_GROUPS,
        "nations": sorted(set(C.NATIONS)) if isinstance(C.NATIONS, dict) else list(C.NATIONS),
        "difficulties": [
            {"id": "casual", "name": "Casual", "desc": "Forgiving board, fewer injuries, bigger budgets."},
            {"id": "realistic", "name": "Realistic", "desc": "The intended Football Manager experience."},
            {"id": "hardcore", "name": "Hardcore", "desc": "Brutal board patience, injuries and finances."},
        ],
        "rivalries": getattr(C, "RIVALRIES", {}),
        "derby_names": getattr(C, "DERBY_NAMES", {}),
        "elite_clubs": getattr(C, "ELITE_CLUBS", []),
    }


def club_search(con, q="", country="", tier=None, limit=60):
    sql = """SELECT c.id, c.code, c.name, c.short, c.country, c.league, c.tier, c.rep, c.stadium,
        c.capacity, c.profile, c.vision, c.chairman, c.season_income, c.transfer_budget,
        c.wage_budget, c.cash, c.debt, k.name AS league_name,
        (SELECT COUNT(*) FROM players p WHERE p.club_id=c.id) AS squad_size
        FROM clubs c LEFT JOIN competitions k ON k.code=c.league WHERE c.id>0"""
    args = []
    if q:
        sql += " AND (c.name LIKE ? OR c.code LIKE ? OR c.short LIKE ?)"
        args += [f"%{q}%"] * 3
    if country:
        sql += " AND c.country=?"
        args.append(country)
    if tier:
        sql += " AND c.tier=?"
        args.append(int(tier))
    sql += " ORDER BY c.rep DESC LIMIT ?"
    args.append(limit)
    return [dict(r) for r in con.execute(sql, args).fetchall()]


def club_countries(con):
    rows = con.execute("""SELECT country, COUNT(*) n, MIN(tier) best FROM clubs WHERE id>0
        GROUP BY country ORDER BY n DESC""").fetchall()
    return [dict(r) for r in rows]


def squad(con, save, filter_squad=None):
    cid = save["club_id"]
    if not cid:
        return []
    rows = con.execute("SELECT * FROM players WHERE club_id=? ORDER BY ca DESC", (cid,)).fetchall()
    team_ca = E.club_strength(con, cid, save)["overall"] if cid else 10.0
    out = []
    for p in rows:
        if filter_squad and p["squad"] != filter_squad:
            continue
        vec = E.unpack_attrs(p["attrs"])
        out.append({
            "id": p["id"], "name": p["name"], "nat": p["nat"], "age": p["age"], "pos": p["pos"],
            "pos2": p["pos2"] or "", "squad": p["squad"], "ca": round(p["ca"], 2), "pa": round(p["pa"], 2),
            "stars": star_rating(p["ca"], team_ca), "stars_pa": star_rating(p["pa"], team_ca),
            "value": p["value"], "wage": p["wage"], "contract_end": p["contract_end"],
            "fitness": p["fitness"], "sharpness": p["sharpness"], "fatigue": p["fatigue"],
            "condition": round(_condition(p), 2),
            "morale": p["morale"], "form": p["form"], "happiness": p["happiness"],
            "apps": p["apps"], "goals": p["goals"], "assists": p["assists"], "minutes": p["minutes"],
            "avg_rating": p["avg_rating"], "yellow": p["yellow"], "red": p["red"],
            "injured": p["condition"] != "fit", "injury": p["injury_name"] or "",
            "return_date": p["return_date"] or "", "suspended": p["suspended"],
            "promise": p["promise"] or "—", "listed": p["listed"], "wanted_out": p["wanted_out"],
            "personality": p["personality"], "foot": p["foot"], "height": p["height"],
            "attrs": {k: int(round(v)) for k, v in vec.items()},
        })
    return out


def _condition(p):
    fit = (p["fitness"] - 88.0) / 22.0
    sharp = (p["sharpness"] - 62.0) / 55.0
    fat = p["fatigue"] / 100.0
    mor = (p["morale"] - 55.0) / 55.0
    frm = max(-2.5, min(2.5, p["form"] or 0)) / 2.5
    m = 1.0 + 0.07 * fit + 0.11 * sharp - 0.14 * fat + 0.06 * mor + 0.07 * frm
    return max(0.78, min(1.12, m))


def player_card(con, save, pid):
    p = con.execute("SELECT * FROM players WHERE id=?", (pid,)).fetchone()
    if not p:
        return None
    p = dict(p)
    mine = p["club_id"] == save["club_id"]
    vec = E.unpack_attrs(p["attrs"])
    known = save["known"].get(str(pid), 100 if mine else 0)
    est = None
    if not mine and known < 100:
        est = E.estimate_player(con, save, pid)
    club_row = E.club(con, p["club_id"]) if p["club_id"] and p["club_id"] > 0 else None
    out = {
        "id": pid, "name": p["name"], "nat": p["nat"], "age": p["age"], "pos": p["pos"],
        "pos2": p["pos2"] or "", "foot": p["foot"], "height": p["height"],
        "club": club_row["name"] if club_row else "Free agent",
        "club_id": p["club_id"], "squad": p["squad"], "mine": mine, "known": known,
        "value": p["value"], "wage": p["wage"], "contract_end": p["contract_end"],
        "personality": p["personality"] if known > 40 else "Unknown",
        "fitness": p["fitness"], "sharpness": p["sharpness"], "fatigue": p["fatigue"],
        "condition": round(_condition(p), 2), "morale": p["morale"], "form": p["form"],
        "happiness": p["happiness"], "apps": p["apps"], "goals": p["goals"], "assists": p["assists"],
        "minutes": p["minutes"], "avg_rating": p["avg_rating"], "promise": p["promise"] or "—",
        "injury": p["injury_name"] or "", "return_date": p["return_date"] or "",
        "suspended": p["suspended"], "listed": p["listed"], "wanted_out": p["wanted_out"],
        "int_apps": p["int_apps"], "int_goals": p["int_goals"], "reputation": p["reputation"],
        "ca": round(p["ca"], 2) if mine else None,
        "pa": round(p["pa"], 2) if mine else None,
        "stars": star_rating(p["ca"], E.club_strength(con, save["club_id"], save)["overall"]) if mine and save["club_id"] else None,
        "attrs": {k: int(round(v)) for k, v in vec.items()} if (mine or known >= 100) else None,
        "scout": est,
        "asking": round(E.asking_price(con, save, pid), 2) if not mine else None,
    }
    if out["attrs"]:
        out["attr_groups"] = {g: [{"k": k, "v": out["attrs"].get(k, 0),
                                  "c": _attr_colour(out["attrs"].get(k, 0))} for k in keys
                                  if k in out["attrs"]] for g, keys in ATTR_GROUPS.items()}
    out["yellow"] = p["yellow"]; out["red"] = p["red"]
    recent = []
    if p["club_id"] and p["club_id"] > 0:
        rows = con.execute("""SELECT f.match_date, f.hg, f.aw, f.home_id, f.away_id, f.report,
                k.name AS comp FROM fixtures f LEFT JOIN competitions k ON k.id=f.comp_id
                WHERE f.played=1 AND f.season=? AND (f.home_id=? OR f.away_id=?) AND f.report IS NOT NULL
                ORDER BY f.match_date DESC LIMIT 6""",
            (save["season"], p["club_id"], p["club_id"])).fetchall()
        for r in rows:
            try:
                rep = json.loads(r["report"])
            except Exception:
                continue
            pl = [x for x in (rep.get("players") or []) if x.get("pid") == pid]
            if not pl:
                continue
            pl = pl[0]
            opp_id = r["away_id"] if r["home_id"] == p["club_id"] else r["home_id"]
            oc = con.execute("SELECT short FROM clubs WHERE id=?", (opp_id,)).fetchone()
            recent.append({"date": r["match_date"], "comp": r["comp"] or "",
                           "opp": oc["short"] if oc else "?",
                           "home": r["home_id"] == p["club_id"],
                           "score": f"{r['hg']}-{r['aw']}",
                           "rating": round(pl.get("rating", 0), 2), "mins": pl.get("mins", 0),
                           "goals": pl.get("goals", 0), "assists": pl.get("assists", 0)})
    out["recent"] = recent
    return out


def home(con, save):
    cid = save["club_id"]
    out = {
        "date": save["date"], "season": save["season"],
        "season_label": f"{save['season']}/{str(save['season'] + 1)[2:]}",
        "unemployed": bool(save["flags"].get("unemployed")) or not cid,
        "unread": con.execute("SELECT COUNT(*) FROM inbox WHERE read=0").fetchone()[0],
        "urgent": len(E.unread_urgent(con, save)),
        "window": E.window_state(E.d(save["date"]), save["season"]),
        "int_break": E.in_int_break(E.d(save["date"]), save["season"]),
        "last_result": save.get("last_result"),
        "job_offers": save["flags"].get("job_offers", []),
    }
    if not cid:
        out["jobs"] = E.list_jobs(con, save)
        return out
    c = E.club(con, cid)
    lg = con.execute("SELECT * FROM competitions WHERE code=?", (c["league"],)).fetchone()
    pos = E._league_position(con, save)
    nf = E.next_fixture(con, save)
    out.update({
        "club": {"id": c["id"], "name": c["name"], "short": c["short"], "code": c["code"],
                 "league": lg["name"] if lg else c["league"], "league_code": c["league"],
                 "tier": c["tier"], "rep": c["rep"], "stadium": c["stadium"],
                 "capacity": c["capacity"],
                 "capacity": c["capacity"], "vision": c["vision"], "chairman": c["chairman"],
                 "facilities": c["facilities"], "coaching": c["coaching"], "youth": c["youth"],
                 "scouting": c["scouting"]},
        "finances": {"cash": round(c["cash"], 2), "balance": round(c["balance"], 2),
                     "wage_bill": round(c["wage_bill"], 2), "wage_budget": round(c["wage_budget"], 2),
                     "transfer_budget": round(c["transfer_budget"], 2), "debt": round(c["debt"], 2),
                     "season_income": round(c["season_income"], 2)},
        "board": {"confidence": round(save["board"]["confidence"], 1),
                  "objectives": save["board"]["objectives"], "warning": save["board"].get("warning", False)},
        "fans": {"sentiment": round(save["fans"]["sentiment"], 1),
                 "support": round(save["fans"]["support"], 1)},
        "position": pos,
        "season_stats": save["season_stats"],
        "next_fixture": _fixture_brief(con, save, nf) if nf else None,
        "form": _form(con, save, cid, 6),
        "squad_summary": _squad_summary(con, save),
        "manager": save["career"]["manager"],
        "reputation": round(save["career"]["reputation"], 1),
        "assistant": E.assistant_assessment(con, save),
    })
    tbl = E.table(con, save, lg["id"], limit=0) if lg else []
    out["table"] = tbl[:26]
    out["fixtures"] = upcoming(con, save, 6)
    out["results"] = recent_results(con, save, 6)
    return out


def _squad_summary(con, save):
    cid = save["club_id"]
    rows = con.execute("""SELECT squad, COUNT(*) n, AVG(age) age, SUM(wage) wage FROM players
        WHERE club_id=? GROUP BY squad""", (cid,)).fetchall()
    injured = con.execute("""SELECT COUNT(*) n FROM players WHERE club_id=? AND condition!='fit'""",
                          (cid,)).fetchone()[0]
    unfit = con.execute("""SELECT COUNT(*) n FROM players WHERE club_id=? AND fitness<85""",
                        (cid,)).fetchone()[0]
    susp = con.execute("""SELECT COUNT(*) n FROM players WHERE club_id=? AND suspended>0""",
                       (cid,)).fetchone()[0]
    return {"groups": [dict(r) for r in rows], "injured": injured, "unfit": unfit, "suspended": susp}


def _form(con, save, cid, n=6):
    rows = con.execute("""SELECT f.hg, f.aw, f.home_id, f.match_date, k.code FROM fixtures f
        JOIN competitions k ON k.id=f.comp_id
        WHERE (f.home_id=? OR f.away_id=?) AND f.played=1 AND k.ctype!='friendly'
          AND f.season=? AND f.hg IS NOT NULL
        ORDER BY f.match_date DESC LIMIT ?""", (cid, cid, save["season"], n)).fetchall()
    out = []
    for r in reversed(rows):
        mine = r["hg"] if r["home_id"] == cid else r["aw"]
        theirs = r["aw"] if r["home_id"] == cid else r["hg"]
        out.append({"res": "W" if mine > theirs else ("D" if mine == theirs else "L"),
                    "score": f"{mine}-{theirs}", "date": r["match_date"]})
    return out


def _fixture_brief(con, save, f):
    if not f:
        return None
    home = E.club(con, f["home_id"])
    away = E.club(con, f["away_id"])
    return {"id": f["id"], "date": f["match_date"], "comp": f.get("comp_name"),
            "code": f.get("comp_code"), "ctype": f.get("ctype"), "stage": f.get("stage"),
            "home": home["name"] if home else "?", "away": away["name"] if away else "?",
            "home_code": home["code"] if home else "", "away_code": away["code"] if away else "",
            "home_short": home["short"] if home else "?", "away_short": away["short"] if away else "?",
            "is_home": f["home_id"] == save["club_id"], "venue": f.get("venue") or
            (home["stadium"] if home else ""), "home_id": f["home_id"], "away_id": f["away_id"]}


def upcoming(con, save, n=8):
    cid = save["club_id"]
    if not cid:
        return []
    rows = con.execute("""SELECT f.*, k.name AS comp_name, k.code AS comp_code, k.ctype FROM fixtures f
        LEFT JOIN competitions k ON k.id=f.comp_id
        WHERE (f.home_id=? OR f.away_id=?) AND f.played=0 AND f.match_date>=?
        ORDER BY f.match_date LIMIT ?""", (cid, cid, save["date"], n)).fetchall()
    return [_fixture_brief(con, save, dict(r)) for r in rows]


def recent_results(con, save, n=8):
    cid = save["club_id"]
    if not cid:
        return []
    rows = con.execute("""SELECT f.*, k.name AS comp_name, k.code AS comp_code, k.ctype FROM fixtures f
        LEFT JOIN competitions k ON k.id=f.comp_id
        WHERE (f.home_id=? OR f.away_id=?) AND f.played=1
        ORDER BY f.match_date DESC, f.id DESC LIMIT ?""", (cid, cid, n)).fetchall()
    out = []
    for r in rows:
        b = _fixture_brief(con, save, dict(r))
        b["hg"], b["aw"] = r["hg"], r["aw"]
        mine = r["hg"] if r["home_id"] == cid else r["aw"]
        theirs = r["aw"] if r["home_id"] == cid else r["hg"]
        b["res"] = "W" if mine > theirs else ("D" if mine == theirs else "L")
        b["played"] = 1
        out.append(b)
    return out


def inbox(con, save, cat=None, unread_only=False, limit=80):
    sql = "SELECT * FROM inbox WHERE 1=1"
    args = []
    if cat:
        sql += " AND cat=?"
        args.append(cat)
    if unread_only:
        sql += " AND read=0"
    sql += " ORDER BY id DESC LIMIT ?"
    args.append(limit)
    rows = con.execute(sql, args).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        try:
            d["payload"] = json.loads(d.get("payload") or "{}")
        except Exception:
            d["payload"] = {}
        out.append(d)
    counts = {r["cat"]: r["n"] for r in con.execute(
        "SELECT cat, COUNT(*) n FROM inbox WHERE read=0 GROUP BY cat").fetchall()}
    return {"items": out, "unread_by_cat": counts,
            "cats": ["BOARD", "TRANSFER", "MEDICAL", "CONTRACT", "COMPETITION", "FINANCE",
                     "SQUAD", "STAFF", "MEDIA", "YOUTH", "CAREER"]}


def league_table(con, save, code=None):
    cid = save["club_id"]
    c = E.club(con, cid) if cid else None
    code = code or (c["league"] if c else None)
    if not code:
        return None
    lg = con.execute("SELECT * FROM competitions WHERE code=?", (code,)).fetchone()
    if not lg:
        return None
    rows = E.table(con, save, lg["id"], limit=0)
    lower = con.execute("SELECT code FROM competitions WHERE country=? AND tier=?",
                        (lg["country"], lg["tier"] + 1)).fetchone()
    in_n = E.league_moves(con, lower["code"]) if lower else 0
    out_n = E.league_moves(con, code)
    for i, r in enumerate(rows):
        r["zone"] = ("promotion" if i < in_n else
                     "relegation" if i >= len(rows) - out_n and out_n else "")
    return {"comp": dict(lg), "rows": rows, "my_club": cid, "prom_spots": in_n,
            "rel_spots": out_n}


def comps(con, save):
    cid = save["club_id"]
    out = []
    if cid:
        rows = con.execute("""SELECT DISTINCT k.id, k.code, k.name, k.ctype, k.tier, k.prestige
            FROM standings s JOIN competitions k ON k.id=s.comp_id
            WHERE s.club_id=? AND s.season=? ORDER BY k.prestige DESC""", (cid, save["season"])).fetchall()
    else:
        rows = con.execute("SELECT id, code, name, ctype, tier, prestige FROM competitions "
                           "ORDER BY prestige DESC").fetchall()
    for r in rows:
        tbl = E.table(con, save, r["id"], limit=6) if r["ctype"] in ("league", "continental") else []
        out.append({"comp": dict(r), "table": tbl})
    return out


def comp_detail(con, save, comp_id):
    k = con.execute("SELECT * FROM competitions WHERE id=?", (comp_id,)).fetchone()
    if not k:
        return {"error": "not found"}
    out = {"comp": dict(k)}
    cid = save["club_id"]
    if k["ctype"] in ("league", "continental"):
        out["table"] = E.table(con, save, comp_id, limit=0)
    rows = con.execute("""SELECT f.* FROM fixtures f WHERE f.comp_id=? AND f.season=?
        AND (? = 0 OR f.home_id=? OR f.away_id=?) ORDER BY f.match_date""",
        (comp_id, save["season"], cid or 0, cid or 0, cid or 0)).fetchall()
    fx = []
    for r in rows:
        b = _fixture_brief(con, save, dict(r))
        b.update({"played": r["played"], "hg": r["hg"], "ag": r["aw"]})
        fx.append(b)
    out["fixtures"] = fx
    ko = [f for f in fx if f.get("stage") not in ("league", None, "")]
    order = ["R64", "R32", "R16", "QF", "SF", "F", "R1", "R2", "R3", "R4", "R5", "R6", "R7"]
    stages = []
    for f in ko:
        if f["stage"] not in stages:
            stages.append(f["stage"])
    stages.sort(key=lambda x: order.index(x) if x in order else 99)
    out["ko"] = [{"stage": st, "ties": [f for f in ko if f["stage"] == st]} for st in stages]
    return out


def fixtures_screen(con, save):
    cid = save["club_id"]
    rows = con.execute("""SELECT f.*, k.name AS comp_name, k.code AS comp_code, k.ctype FROM fixtures f
        LEFT JOIN competitions k ON k.id=f.comp_id
        WHERE (f.home_id=? OR f.away_id=?) AND f.season=?
        ORDER BY f.match_date""", (cid, cid, save["season"])).fetchall() if cid else []
    out = []
    for r in rows:
        b = _fixture_brief(con, save, dict(r))
        b["hg"], b["aw"], b["played"] = r["hg"], r["aw"], r["played"]
        if r["played"] and cid:
            mine = r["hg"] if r["home_id"] == cid else r["aw"]
            theirs = r["aw"] if r["home_id"] == cid else r["hg"]
            b["res"] = "W" if mine > theirs else ("D" if mine == theirs else "L")
        out.append(b)
    return out


def _role_duty(roles_map, i, slot):
    rd = (roles_map or {}).get(str(i))
    if isinstance(rd, dict):
        role, duty = rd.get("role"), rd.get("duty")
    elif isinstance(rd, (list, tuple)) and len(rd) == 2:
        role, duty = rd[0], rd[1]
    elif isinstance(rd, str):
        role, duty = rd, None
    else:
        role, duty = None, None
    if not role or role not in C.ROLES.get(slot, []):
        role = (C.ROLES.get(slot) or ["Central Midfielder"])[0]
    if not duty or duty not in C.DUTIES.get(slot, []):
        duty = (C.DUTIES.get(slot) or ["Support"])[0]
    return role, duty


def _fill_xi(players, slots, sel_ids, team_ca, roles_map):
    """The selected XI, with empty slots filled by the best available player.

    Returns (xi, used_ids). Players placed by the assistant are flagged "auto".
    """
    byid = {p["id"]: p for p in players}
    xi = []
    used = set()
    for i, slot in enumerate(slots):
        pid = sel_ids[i] if i < len(sel_ids) else None
        p = byid.get(pid)
        auto = False
        if p and (p["condition"] != "fit" or p["suspended"] or p["id"] in used):
            p = None
        if not p:
            auto = True
            def _fit(x):
                return 0 if x["pos"] == slot else (1 if x["pos2"] == slot else 2)
            cands = [x for x in players
                     if x["squad"] in ("First Team", "Reserve") and x["condition"] == "fit"
                     and not x["suspended"] and x["id"] not in used]
            cands.sort(key=lambda x: (_fit(x), -x["ca"]))
            p = cands[0] if cands else None
        if p:
            used.add(p["id"])
        role, duty = _role_duty(roles_map, i, slot)
        item = {"slot": i, "pos": slot, "role": role, "duty": duty,
                "player": _mini(p, team_ca) if p else None}
        item["auto"] = auto
        xi.append(item)
    return xi, used


def _rating_dict(con, save):
    """Human team rating as a plain dict (E.human_rating returns a 4-tuple)."""
    try:
        xi, bench, rating, tac = E.human_rating(con, save)
        return {k: (round(v, 2) if isinstance(v, float) else v) for k, v in rating.items()}
    except Exception:
        return {"attack": 0.0, "defence": 0.0, "condition": 0.0}


def tactics(con, save):
    t = E.get_tactics(con, save)
    cid = save["club_id"]
    players = E.load_players(con, cid)
    slots = C.FORMATIONS.get(t["formation"], C.FORMATIONS["4-2-3-1 Wide"])
    sel = t.get("selected") or save["flags"].get("selected_xi")
    sel_ids = json.loads(sel) if isinstance(sel, str) else (sel or [])
    byid = {p["id"]: p for p in players}
    team_ca = E.club_strength(con, cid, save)["overall"]
    all_players = E.load_players(con, cid)
    xi, used = _fill_xi(all_players, slots, sel_ids, team_ca, t["roles"] or {})
    bench = [_mini(p, team_ca) for p in all_players
             if p["squad"] in ("First Team", "Reserve") and p["id"] not in used]
    bench.sort(key=lambda x: -x["ca"])
    rating = _rating_dict(con, save)
    return {"tactic": {"name": t["name"], "formation": t["formation"], "mentality": t["mentality"],
                       "instr": t["instr"], "roles": t["roles"], "familiarity": t["familiarity"],
                       "identity": t["identity"]},
            "xi": xi, "bench": bench[:14], "rating": rating,
            "selected_xi": [x["player"]["id"] for x in xi if x["player"]],
            "formation_slots": slots,
            "role_options": {k: v for k, v in C.ROLES.items()},
            "duties": C.DUTIES,
            "instruction_defaults": dict(C.INSTR_DEFAULT)}


def _mini(p, team_ca=10.0):
    if not p:
        return None
    return {"id": p["id"], "name": p["name"], "pos": p["pos"], "pos2": p["pos2"] or "",
            "age": p["age"], "ca": round(p["ca"], 2), "stars": star_rating(p["ca"], team_ca),
            "fitness": p["fitness"], "fatigue": p["fatigue"], "sharpness": p["sharpness"],
            "condition": round(_condition(p), 2), "morale": p["morale"], "form": p["form"],
            "injured": p["condition"] != "fit", "injury": p["injury_name"] or "",
            "suspended": p["suspended"], "squad": p["squad"], "nat": p["nat"],
            "promise": p["promise"] or "—", "apps": p["apps"], "goals": p["goals"]}


def training(con, save):
    rows = con.execute("SELECT day, session, focus FROM training WHERE club_id=? ORDER BY day",
                       (save["club_id"],)).fetchall()
    week = [{"day": r["day"], "session": r["session"], "focus": r["focus"]} for r in rows]
    sessions = []
    for name, sdef in C.TRAINING_SESSIONS.items():
        sessions.append({"name": name, **{k: sdef[k] for k in sdef if k != "attrs"},
                         "attrs": list((sdef.get("attrs") or {}).keys())})
    focus_options = list(C.POSITIONS)
    load = con.execute("""SELECT AVG(fatigue) f, AVG(fitness) fit, AVG(sharpness) s,
        SUM(CASE WHEN condition!='fit' THEN 1 ELSE 0 END) inj FROM players
        WHERE club_id=? AND squad IN ('First Team','Reserve')""", (save["club_id"],)).fetchone()
    return {"week": week, "sessions": sessions, "focus_options": focus_options,
            "squad_load": {"fatigue": round(load["f"] or 0, 1), "fitness": round(load["fit"] or 0, 1),
                           "sharpness": round(load["s"] or 0, 1), "injured": load["inj"] or 0},
            "coaching": _coaching(con, save)}


def _coaching(con, save):
    rows = con.execute("""SELECT role, COUNT(*) n, AVG(attacking) att, AVG(defending) dfn,
        AVG(fitness) fit, AVG(tactical) tac, AVG(technical) tec, AVG(mental) men,
        AVG(youth) you, AVG(man_mgmt) mm, AVG(judging) jd, SUM(wage) wage FROM staff
        WHERE club_id=? GROUP BY role""", (save["club_id"],)).fetchall()
    return [dict(r) for r in rows]


def staff_screen(con, save):
    cid = save["club_id"]
    today = save["date"]
    current = []
    for r in con.execute("SELECT * FROM staff WHERE club_id=? ORDER BY role, reputation DESC", (cid,)):
        d = dict(r)
        d["key"] = {k: d[k] for k in E.STAFF_ROLE_ATTRS.get(d["role"], ("tactical",))}
        d["quality"] = E.staff_quality(d)
        d["contract_days"] = int((E.d(d["contract_end"]) - E.d(today)).days) if d["contract_end"] else None
        current.append(d)
    pool_rows = con.execute("SELECT * FROM staff WHERE club_id IS NULL").fetchall()
    pool = sorted((dict(r) for r in pool_rows), key=lambda x: -E.staff_quality(x))
    pool_out = []
    for d in pool[:60]:
        d["key"] = {k: d[k] for k in E.STAFF_ROLE_ATTRS.get(d["role"], ("tactical",))}
        d["quality"] = E.staff_quality(d)
        pool_out.append(d)
    pbill = con.execute("SELECT COALESCE(SUM(wage),0) w FROM players WHERE club_id=?", (cid,)).fetchone()["w"]
    sbill = con.execute("SELECT COALESCE(SUM(wage),0) w FROM staff WHERE club_id=?", (cid,)).fetchone()["w"]
    c = E.club(con, cid)
    return {
        "current": current,
        "pool": pool_out,
        "coaching": E.coaching_ratings(con, cid),
        "wage": {"players": round(pbill * 52 / 1000, 2), "staff": round(sbill * 52 / 1000, 2),
                 "budget": c["wage_budget"], "cash": c["cash"]},
        "cap": E.STAFF_CAP,
        "roles": list(E.STAFF_ROLE_ATTRS.keys()),
    }


def _nonwage(c):
    """Non-wage running costs, matching the engine's monthly accounting."""
    return max(c["season_income"] * 0.18, (c["season_costs"] or 0) - (c["wage_budget"] or 0))


def finances(con, save):
    c = E.club(con, save["club_id"])
    rows = []
    if con.execute("SELECT name FROM sqlite_master WHERE name='finances'").fetchone():
        rows = con.execute("""SELECT season, month, income, wages, other, interest, net, cash
            FROM finances WHERE club_id=? ORDER BY id DESC LIMIT 24""",
            (save["club_id"],)).fetchall()
        rows = [dict(r) for r in reversed(rows)]
    wages = con.execute("SELECT SUM(wage) w FROM players WHERE club_id=?",
                        (save["club_id"],)).fetchone()["w"] or 0
    staff_w = con.execute("SELECT SUM(wage) w FROM staff WHERE club_id=?",
                          (save["club_id"],)).fetchone()["w"] or 0
    return {"club": {k: c[k] for k in ("cash", "balance", "debt", "wage_bill", "wage_budget",
                                       "transfer_budget", "season_income", "season_costs", "capacity")},
            "weekly_wages": round(wages, 1), "weekly_staff": round(staff_w, 1),
            "annual_wages": round((wages + staff_w) * 52 / 1000.0, 2),
            "projected_net": round(c["season_income"] - (wages + staff_w) * 52 / 1000.0
                                   - _nonwage(c) - c["debt"] * 0.048, 2),
            "monthly": {"revenue": round(c["season_income"] / 12.0, 2),
                        "wages": round((wages + staff_w) * 52 / 12 / 1000.0, 2),
                        "running": round(_nonwage(c) / 12.0, 2),
                        "interest": round(c["debt"] * 0.004, 2)},
            "matchday_income": round(save["flags"].get("matchday_income", 0.0), 2),
            "history": rows,
            "top_earners": [dict(r) for r in con.execute(
                """SELECT name, pos, age, wage, contract_end FROM players WHERE club_id=?
                   ORDER BY wage DESC LIMIT 10""", (save["club_id"],)).fetchall()]}


def board_screen(con, save):
    c = E.club(con, save["club_id"])
    pos = E._league_position(con, save)
    return {"confidence": round(save["board"]["confidence"], 1),
            "objectives": save["board"]["objectives"],
            "warning": save["board"].get("warning", False),
            "sack_risk": save["board"].get("sack_risk", 0),
            "vision": c["vision"], "chairman": c["chairman"], "patience": c["board_patience"],
            "fans": save["fans"], "media": save["media"],
            "position": pos,
            "job_security": ("Safe" if save["board"]["confidence"] > 55 else
                             "Under pressure" if save["board"]["confidence"] > 30 else
                             "In danger" if save["board"]["confidence"] > 15 else "On the brink")}


def media(con, save):
    rows = con.execute("SELECT * FROM news ORDER BY id DESC LIMIT 60").fetchall()
    return {"narrative": save["media"].get("narrative"), "pressure": save["media"].get("pressure"),
            "news": [dict(r) for r in rows],
            "conferences": save["flags"].get("press_pending", [])}


def scouting(con, save):
    tasks = save.get("scout_tasks", [])
    regions = save.get("scouting", {})
    targets = []
    for pid in save.get("targets", []):
        p = con.execute("SELECT id,name,age,pos,club_id,value,ca,wage,contract_end FROM players WHERE id=?",
                        (pid,)).fetchone()
        if p:
            d = dict(p)
            cl = E.club(con, p["club_id"]) if p["club_id"] else None
            d["club"] = cl["name"] if cl else "Free agent"
            d["known"] = save["known"].get(str(pid), 0)
            targets.append(d)
    offers = my_offers(con, save)
    return {"knowledge": regions, "tasks": tasks, "targets": targets, "offers": offers,
            "scouts": [dict(r) for r in con.execute(
                """SELECT id, name, nat, role, judging, judging_pot, reputation, wage FROM staff
                   WHERE club_id=? AND role IN ('Chief Scout','Scout')""",
                (save["club_id"],)).fetchall()],
            "budget": E.club(con, save["club_id"])["transfer_budget"]}


def transfers(con, save, pos="", q="", max_fee=None, age_max=None, limit=80):
    sql = """SELECT p.id, p.name, p.age, p.pos, p.pos2, p.nat, p.ca, p.pa, p.value, p.wage,
        p.contract_end, p.club_id, c.name club, c.rep club_rep, c.league FROM players p
        LEFT JOIN clubs c ON c.id=p.club_id
        WHERE p.club_id IS NOT NULL AND p.club_id!=? AND p.squad IN ('First Team','Reserve')
          AND p.age BETWEEN 16 AND 38 AND COALESCE(c.code,'')!='FREE'"""
    args = [save["club_id"]]
    if pos:
        sql += " AND (p.pos=? OR p.pos2=?)"
        args += [pos, pos]
    if q:
        sql += " AND p.name LIKE ?"
        args.append(f"%{q}%")
    if max_fee:
        sql += " AND p.value<=?"
        args.append(float(max_fee))
    if age_max:
        sql += " AND p.age<=?"
        args.append(int(age_max))
    sql += " ORDER BY p.value DESC LIMIT ?"
    args.append(limit)
    team_ca = E.club_strength(con, save["club_id"], save)["overall"]
    out = []
    for r in con.execute(sql, args).fetchall():
        d = dict(r)
        d["stars"] = star_rating(d["ca"], team_ca)
        d["known"] = save["known"].get(str(d["id"]), 0)
        d["asking"] = round(E.asking_price(con, save, d["id"]), 2)
        if d["known"] < 60:
            for k in ("ca", "pa"):
                d[k] = None
        out.append(d)
    return out


def free_agents(con, save, limit=60):
    fa = con.execute("SELECT id FROM clubs WHERE code='FREE'").fetchone()
    fa_id = fa["id"] if fa else -1
    rows = con.execute("""SELECT id, name, age, pos, pos2, nat, ca, pa, value, wage, contract_end
        FROM players WHERE club_id=? OR club_id IS NULL ORDER BY value DESC LIMIT ?""",
                       (fa_id, limit)).fetchall()
    team_ca = E.club_strength(con, save["club_id"], save)["overall"]
    out = []
    for r in rows:
        d = dict(r)
        d["stars"] = star_rating(d["ca"], team_ca)
        d["club"] = "Free agent"
        d["known"] = save["known"].get(str(d["id"]), 0)
        d["asking"] = 0.0
        d.setdefault("contract_end", "")
        if d["known"] < 60:
            d["ca"] = None
            d["pa"] = None
        out.append(d)
    return out


def my_offers(con, save, limit=30):
    """Every negotiation the club is involved in, newest first."""
    rows = con.execute("""SELECT o.*, p.name player, p.age, p.pos, p.value,
        cf.name from_club, ct.name to_club FROM offers o
        JOIN players p ON p.id=o.player_id
        LEFT JOIN clubs cf ON cf.id=o.from_id LEFT JOIN clubs ct ON ct.id=o.to_id
        WHERE o.to_id=? OR o.from_id=? ORDER BY o.id DESC LIMIT ?""",
        (save["club_id"], save["club_id"], limit)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["direction"] = "in" if d["to_id"] == save["club_id"] else "out"
        d["awaiting_you"] = (d["direction"] == "in" and d["status"] == "pending") or \
                            (d["direction"] == "out" and d["status"] == "counter")
        out.append(d)
    return out


def incoming_offers(con, save):
    rows = con.execute("""SELECT o.*, p.name player, p.age, p.pos, p.ca, p.value, p.wage,
        c.name from_club FROM offers o JOIN players p ON p.id=o.player_id
        LEFT JOIN clubs c ON c.id=o.from_id WHERE o.to_id=? AND o.status='pending'
        ORDER BY o.id DESC""", (save["club_id"],)).fetchall()
    return [dict(r) for r in rows]


def youth(con, save):
    cid = save["club_id"]
    c = E.club(con, cid)
    rows = con.execute("""SELECT id, name, age, pos, ca, pa, personality, ambition, professionalism
        FROM players WHERE club_id=? AND squad IN ('Youth','U21')
        ORDER BY pa DESC""", (cid,)).fetchall() if cid else []
    team_ca = E.club_strength(con, cid, save)["overall"] if cid else 10
    return {"rating": c["youth"], "facilities": c["facilities"],
            "players": [{"id": r["id"], "name": r["name"], "age": r["age"], "pos": r["pos"],
                         "ca": round(r["ca"], 2), "pa": round(r["pa"], 2),
                         "stars": star_rating(r["ca"], team_ca),
                         "stars_pa": star_rating(r["pa"], team_ca),
                         "personality": r["personality"]} for r in rows]}


def facilities(con, save):
    cid = save["club_id"]
    if not cid:
        return {"error": "no club"}
    c = E.club(con, cid)
    f = E.facility_levels(con, cid)
    _base_col = {"training": "train_base", "medical": "med_base",
                 "youth": "youth_base", "stadium": "stad_base"}
    items = []
    for key, meta in E.FACILITY_DEFS.items():
        level = f[key] if f else 1
        base = f[_base_col[key]] if f else 1
        done = f[meta["col"]] if f else None
        items.append({
            "key": key,
            "label": meta["label"],
            "effect": meta["effect"],
            "level": level,
            "base": base,
            "building": bool(done),
            "done_date": str(done) if done else None,
            "days": meta["days"],
            "next_cost": E.facility_cost(con, c, key),
            "max": E._FAC_LEVEL_MAX,
        })
    return {
        "overall": c["facilities"],
        "cash": round(c["cash"], 2),
        "stadium": c["stadium"],
        "capacity": c["capacity"],
        "season_income": round(c["season_income"], 2),
        "items": items,
    }


def career(con, save):
    cid = save["club_id"]
    c = E.club(con, cid) if cid else None
    trophies = save["career"]["trophies"]
    hist = [dict(r) for r in con.execute("""SELECT h.season, k.name comp, c2.name club, h.pos, h.note,
        h.trophy FROM history h LEFT JOIN competitions k ON k.id=h.comp_id
        LEFT JOIN clubs c2 ON c2.id=h.club_id WHERE h.club_id=? ORDER BY h.season DESC, h.pos LIMIT 60""",
                                         (cid,)).fetchall()] if cid else []
    records = con.execute("""SELECT COUNT(*) apps, SUM(goals) goals FROM players WHERE club_id=?""",
                          (cid,)).fetchone() if cid else None
    return {"manager": save["career"]["manager"], "reputation": round(save["career"]["reputation"], 1),
            "clubs": save["career"]["clubs"], "trophies": trophies,
            "created": save["career"]["created"], "difficulty": save["career"]["difficulty"],
            "club": {"name": c["name"], "league": c["league"]} if c else None,
            "season": save["season"], "date": save["date"],
            "unemployed": bool(save["flags"].get("unemployed")) or not cid,
            "jobs": E.list_jobs(con, save) if (save["flags"].get("unemployed") or not cid) else [],
            "job_offers": save["flags"].get("job_offers", []),
            "history": hist,
            "records": {"top_scorer": con.execute(
                """SELECT name, goals FROM players WHERE club_id=? ORDER BY goals DESC LIMIT 1""",
                (cid,)).fetchone() and dict(con.execute(
                    """SELECT name, goals FROM players WHERE club_id=? ORDER BY goals DESC LIMIT 1""",
                    (cid,)).fetchone() or {}) or None}}


def match_preview(con, save, fx):
    cid = save["club_id"]
    opp_id = fx["away_id"] if fx["home_id"] == cid else fx["home_id"]
    mine = E.club_strength(con, cid, save)
    theirs = E.club_strength(con, opp_id, save)
    opp = E.club(con, opp_id)
    t = E.get_tactics(con, save)
    hr = _rating_dict(con, save)
    slots = C.FORMATIONS.get(t["formation"], C.FORMATIONS["4-2-3-1 Wide"])
    sel = save["flags"].get("selected_xi")
    sel_ids = json.loads(sel) if isinstance(sel, str) and sel else []
    players = {p["id"]: p for p in E.load_players(con, cid)}
    team_ca = mine["overall"]
    xi, used = _fill_xi(list(players.values()), slots, sel_ids, team_ca, t["roles"] or {})
    bench = [_mini(p, team_ca) for p in players.values()
             if p["squad"] in ("First Team", "Reserve") and p["id"] not in used]
    bench.sort(key=lambda x: -x["ca"])
    form_them = _form(con, save, opp_id, 5)
    return {"fixture": _fixture_brief(con, save, fx),
            "my": {"name": E.club(con, cid)["name"], "ca": round(mine["overall"], 2),
                   "attack": round(hr["attack"], 1), "defence": round(hr["defence"], 1),
                   "condition": round(hr["condition"], 2), "form": _form(con, save, cid, 5)},
            "opp": {"id": opp_id, "name": opp["name"], "ca": round(theirs["overall"], 2),
                    "rep": opp["rep"], "league": opp["league"], "form": form_them,
                    "scouted": save["known"].get(f"club_{opp_id}", 0)},
            "xi": xi, "bench": bench[:9], "tactic": {"formation": t["formation"],
                                                     "mentality": t["mentality"]},
            "opposition_report": _opposition_report(con, save, opp_id)}


def _opposition_report(con, save, opp_id):
    known = save["flags"].get(f"scouted_{opp_id}", 0)
    players = E.load_players(con, opp_id)
    first = [p for p in players if p["squad"] in ("First Team", "Reserve")]
    first.sort(key=lambda p: -p["ca"])
    out = {"known": known, "strength": None, "key_players": [], "formation": None}
    if known <= 0:
        return out
    out["formation"] = "Unknown" if known < 60 else E.ai_tactics(con, opp_id).get("formation")
    n = 3 if known < 60 else 6
    for p in first[:n]:
        out["key_players"].append({"name": p["name"], "pos": p["pos"], "age": p["age"],
                                   "goals": p["goals"], "ca": round(p["ca"], 1) if known >= 60 else None})
    out["strength"] = round(sum(p["ca"] for p in first[:11]) / 11.0, 1) if known >= 40 else None
    return out


def match_result_view(con, save, data, fx):
    if not data:
        return None
    cid = save["club_id"]
    is_home = fx["home_id"] == cid
    mine = "home" if is_home else "away"
    theirs = "away" if is_home else "home"
    players = {p["id"]: p for p in E.load_players(con, cid)}
    xi = data.get(f"xi_{mine}", [])
    ratings = data.get(f"ratings_{mine}", [])
    mins = data.get(f"mins_{mine}", [])
    goals = data.get(f"goals_{mine}", {})
    assists = data.get(f"assists_{mine}", {})
    xgp = data.get(f"xg_players_{mine}", {})
    shp = data.get(f"shots_players_{mine}", {})
    def _at(seq, i, pid):
        """Per-player match stats come back as lists indexed by slot (or dicts)."""
        if isinstance(seq, dict):
            return seq.get(str(pid), seq.get(pid, 0))
        try:
            return seq[i] if i < len(seq) else 0
        except Exception:
            return 0

    rows = []
    for i, item in enumerate(xi):
        pid = item["pid"] if isinstance(item, dict) else item
        p = players.get(pid)
        slot = item.get("slot") if isinstance(item, dict) else None
        nm = (item or {}).get("name") if isinstance(item, dict) else None
        if not p:
            if not nm:
                continue
            p = {"name": nm, "pos": slot or "?"}
        rows.append({"pid": pid, "name": p["name"], "pos": slot or p["pos"],
                     "rating": round(ratings[i], 2) if i < len(ratings) else 6.0,
                     "mins": mins[i] if i < len(mins) else 90,
                     "goals": _at(goals, i, pid),
                     "assists": _at(assists, i, pid),
                     "xg": round(float(_at(xgp, i, pid) or 0), 2),
                     "shots": _at(shp, i, pid)})
    rows.sort(key=lambda r: -r["rating"])
    return {"home": data["home_name"], "away": data["away_name"],
            "home_code": data.get("home_code") or fx.get("home_code"),
            "away_code": data.get("away_code") or fx.get("away_code"),
            "hg": data.get("hg", data.get("goals_home", 0)),
            "ag": data.get("ag", data.get("goals_away", 0)),
            "result": data.get("result") or save.get("last_result", {}).get("result"),
            "mode": data.get("mode", "key"),
            "ht_score": data.get("ht_score"),
            "is_home": is_home,
            "stats": {"home": {k: data.get(f"{k}_home") for k in
                               ("xg", "shots", "sot", "big", "possession", "corners", "fouls",
                                "yellow", "red", "saves")},
                      "away": {k: data.get(f"{k}_away") for k in
                               ("xg", "shots", "sot", "big", "possession", "corners", "fouls",
                                "yellow", "red", "saves")}},
            "events": data.get("events", []), "players": rows,
            "subs": data.get(f"subs_{mine}", []),
            "motm": data.get("motm"), "injuries": data.get("injuries", []),
            "weather": data.get("weather"), "referee": data.get("referee"),
            "penalties": data.get("penalties"),
            "comp": data.get("comp") or fx.get("comp_name"), "code": data.get("comp_code") or data.get("code") or fx.get("comp_code") or fx.get("code"),
            "comp_code": data.get("comp_code") or data.get("code") or fx.get("comp_code") or fx.get("code"),
            "date": save["date"],
            "board_confidence": round(save["board"]["confidence"], 1),
            "fan_sentiment": round(save["fans"]["sentiment"], 1)}


# ---------------------------------------------------------------- statistics
def stats_screen(con, save):
    """Stats Center: golden races, xG-vs-actual, squad leaders, form guide."""
    cid = save["club_id"]
    me = E.club(con, cid)
    season = save["season"]
    # clubs.league stores the competition CODE (e.g. "ENG1"); resolve the row
    comp = None
    if me and me["league"]:
        comp = con.execute("SELECT id, name, code FROM competitions WHERE code=?",
                           (me["league"],)).fetchone()
    comp_id = comp["id"] if comp else None

    def club_brief(row):
        c = E.club(con, row["club_id"]) if "club_id" in row.keys() else None
        return {"code": c["code"] if c else "", "club": c["name"] if c else ""}

    scorers = []
    assists = []
    csheets = []
    if comp_id:
        q = """SELECT p.id pid, p.name, p.pos, p.goals g, p.assists a, p.apps ap,
                      p.clean_sheets cs, c.code ccode, c.name club
               FROM players p JOIN clubs c ON c.id = p.club_id
               WHERE c.league = ? AND p.club_id IS NOT NULL AND (? IS NULL OR 1=1)"""
        rows = con.execute(q + " AND p.goals > 0 ORDER BY p.goals DESC, p.assists DESC LIMIT 15",
                           (comp_id, None)).fetchall()
        scorers = [dict(pid=r["pid"], name=r["name"], pos=r["pos"], goals=r["g"],
                        assists=r["a"], code=r["ccode"], club=r["club"]) for r in rows]
        rows = con.execute(q + " AND p.assists > 0 ORDER BY p.assists DESC, p.goals DESC LIMIT 10",
                           (comp_id, None)).fetchall()
        assists = [dict(pid=r["pid"], name=r["name"], pos=r["pos"], assists=r["a"],
                        goals=r["g"], code=r["ccode"], club=r["club"]) for r in rows]
        rows = con.execute(q + " AND p.clean_sheets > 0 ORDER BY p.clean_sheets DESC LIMIT 10",
                           (comp_id, None)).fetchall()
        csheets = [dict(pid=r["pid"], name=r["name"], pos=r["pos"], cs=r["cs"],
                        code=r["ccode"], club=r["club"]) for r in rows]

    # xG vs actual for the league, aggregated from played fixture reports
    xg = {}
    if comp_id:
        fxs = con.execute("""SELECT home_id, away_id, hg, aw, report FROM fixtures
                             WHERE comp_id=? AND season=? AND played=1 AND report IS NOT NULL""",
                          (comp_id, season)).fetchall()
        for f in fxs:
            try:
                rep = json.loads(f["report"]) if isinstance(f["report"], str) else (f["report"] or {})
            except Exception:
                continue
            for side, opp in (("home", "away"), ("away", "home")):
                cid_s = f["home_id"] if side == "home" else f["away_id"]
                d = xg.setdefault(cid_s, dict(p=0, gf=0, ga=0, xgf=0.0, xga=0.0))
                d["p"] += 1
                d["gf"] += f["hg"] if side == "home" else f["aw"]
                d["ga"] += f["aw"] if side == "home" else f["hg"]
                d["xgf"] += float(rep.get("xg_" + side) or 0.0)
                d["xga"] += float(rep.get("xg_" + opp) or 0.0)
    xg_rows = []
    if xg:
        names = {c["id"]: c for c in
                 con.execute("SELECT id, name, code FROM clubs WHERE league=?",
                             (comp["code"],)).fetchall()}
        for cid_s, d in xg.items():
            n = names.get(cid_s)
            if not n:
                continue
            xg_rows.append(dict(code=n["code"], name=n["name"], p=d["p"], gf=d["gf"], ga=d["ga"],
                                xgf=round(d["xgf"], 1), xga=round(d["xga"], 1),
                                delta=round(d["gf"] - d["xgf"], 1)))
        xg_rows.sort(key=lambda r: -r["delta"])

    # my squad leaders
    leaders = dict(goals=[], assists=[], rating=[])
    rows = con.execute("""SELECT id pid, name, pos, goals g, assists a, apps ap, avg_rating ar
                          FROM players WHERE club_id=? AND (goals>0 OR assists>0 OR apps>0)
                          ORDER BY goals DESC LIMIT 5""", (cid,)).fetchall()
    leaders["goals"] = [dict(pid=r["pid"], name=r["name"], pos=r["pos"], v=r["g"]) for r in rows]
    rows = con.execute("""SELECT id pid, name, pos, assists a FROM players WHERE club_id=?
                          AND assists>0 ORDER BY assists DESC LIMIT 5""", (cid,)).fetchall()
    leaders["assists"] = [dict(pid=r["pid"], name=r["name"], pos=r["pos"], v=r["a"]) for r in rows]
    rows = con.execute("""SELECT id pid, name, pos, avg_rating ar, apps ap FROM players
                          WHERE club_id=? AND apps>=3 AND avg_rating>0
                          ORDER BY avg_rating DESC LIMIT 5""", (cid,)).fetchall()
    leaders["rating"] = [dict(pid=r["pid"], name=r["name"], pos=r["pos"],
                              v=round(r["ar"], 2), apps=r["ap"]) for r in rows]

    # form guide: last 5 played, my perspective
    form = []
    rows = con.execute("""SELECT f.*, k.name comp_name, k.code comp_code FROM fixtures f
                          LEFT JOIN competitions k ON k.id=f.comp_id
                          WHERE f.played=1 AND (f.home_id=? OR f.away_id=?)
                          ORDER BY f.match_date DESC LIMIT 5""", (cid, cid)).fetchall()
    for f in reversed(rows):
        home = (f["home_id"] == cid)
        gf, ga = (f["hg"], f["aw"]) if home else (f["aw"], f["hg"])
        opp = E.club(con, f["away_id"] if home else f["home_id"])
        form.append(dict(opp=opp["name"] if opp else "?", code=opp["code"] if opp else "",
                         home=home, gf=gf, ga=ga,
                         res="W" if gf > ga else ("D" if gf == ga else "L"),
                         comp=f["comp_code"] or "", date=f["match_date"]))

    return dict(comp=comp["name"] if comp else "", code=comp["code"] if comp else "",
                my_code=me["code"] if me else "", my_name=me["name"] if me else "",
                season=season, scorers=scorers, assists=assists, csheets=csheets,
                xg=xg_rows[:20], leaders=leaders, form=form)
