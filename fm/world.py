"""World database generation: clubs, players, staff, finances, competitions, fixtures."""
import json
import os
import random
import sqlite3
import hashlib
from datetime import date, timedelta

from . import constants as C
from .names import make_name, make_manager_name, make_staff_name, NATIONALITY_POOL

DB_PATH = os.environ.get("FM_DB", "/home/user/data/world.db")

# position attribute weight profiles (higher = more important)
PROFILES = {
    "GK":  {"gk_handling": 3, "gk_reflexes": 3, "gk_positioning": 3, "gk_one_on_ones": 2.6,
            "gk_aerial": 2, "gk_distribution": 1.8, "gk_communication": 2, "gk_rushing_out": 2.2,
            "concentration": 2, "composure": 1.6, "decisions": 1.6, "anticipation": 1.6,
            "positioning": 1.8, "strength": 1.4, "jumping": 1.6, "agility": 1.4,
            "leadership": 1.2, "determination": 1.2, "stamina": 0.4, "finishing": 0.2},
    "DC":  {"marking": 2.8, "tackling": 2.8, "heading": 2.6, "positioning": 2.6, "strength": 2.4,
            "jumping": 2.4, "concentration": 2.2, "anticipation": 2, "aggression": 1.8,
            "bravery": 1.8, "decisions": 1.6, "composure": 1.4, "passing": 1.4, "first_touch": 1.2,
            "teamwork": 1.6, "work_rate": 1.4, "stamina": 1.4, "determination": 1.6,
            "leadership": 1.3, "balance": 1.2, "pace": 1.2, "acceleration": 1.0},
    "DL":  {"tackling": 2.2, "marking": 2, "positioning": 2, "pace": 2.6, "acceleration": 2.6,
            "stamina": 2.4, "crossing": 2, "dribbling": 1.6, "first_touch": 1.6, "passing": 1.6,
            "teamwork": 1.8, "work_rate": 2, "agility": 1.8, "strength": 1.4, "heading": 1.2,
            "anticipation": 1.6, "concentration": 1.6, "decisions": 1.4, "technique": 1.4,
            "off_the_ball": 1.2, "jumping": 1.0, "determination": 1.3},
    "DR":  {"tackling": 2.2, "marking": 2, "positioning": 2, "pace": 2.6, "acceleration": 2.6,
            "stamina": 2.4, "crossing": 2, "dribbling": 1.6, "first_touch": 1.6, "passing": 1.6,
            "teamwork": 1.8, "work_rate": 2, "agility": 1.8, "strength": 1.4, "heading": 1.2,
            "anticipation": 1.6, "concentration": 1.6, "decisions": 1.4, "technique": 1.4,
            "off_the_ball": 1.2, "jumping": 1.0, "determination": 1.3},
    "DM":  {"tackling": 2.4, "positioning": 2.6, "marking": 2, "passing": 2.2, "first_touch": 2,
            "decisions": 2.4, "concentration": 2.2, "anticipation": 2.2, "teamwork": 2.4,
            "work_rate": 2.2, "composure": 2, "vision": 1.8, "stamina": 2, "strength": 1.8,
            "technique": 1.6, "aggression": 1.6, "leadership": 1.4, "heading": 1.2,
            "determination": 1.5, "agility": 1.2, "long_shots": 1.0},
    "MC":  {"passing": 2.8, "first_touch": 2.6, "technique": 2.4, "vision": 2.6, "decisions": 2.6,
            "composure": 2.2, "teamwork": 2.2, "work_rate": 2, "stamina": 2.2, "positioning": 1.8,
            "tackling": 1.6, "off_the_ball": 1.8, "long_shots": 1.6, "concentration": 1.8,
            "anticipation": 1.8, "dribbling": 1.4, "strength": 1.4, "leadership": 1.4,
            "determination": 1.5, "heading": 1.0, "crossing": 1.2},
    "AMC": {"passing": 2.6, "first_touch": 2.8, "technique": 2.8, "vision": 2.8, "dribbling": 2.4,
            "off_the_ball": 2.4, "composure": 2.4, "decisions": 2.4, "finishing": 2, "flair": 2,
            "long_shots": 1.8, "set_pieces": 1.6, "agility": 2, "balance": 1.8, "acceleration": 1.8,
            "teamwork": 1.4, "work_rate": 1.2, "stamina": 1.4, "concentration": 1.4,
            "crossing": 1.6, "determination": 1.3, "anticipation": 1.4},
    "AML": {"dribbling": 3, "pace": 2.8, "acceleration": 2.8, "agility": 2.6, "technique": 2.6,
            "first_touch": 2.4, "crossing": 2.2, "off_the_ball": 2.2, "flair": 2.2,
            "finishing": 1.8, "balance": 2, "composure": 2, "decisions": 1.8, "vision": 1.8,
            "stamina": 1.8, "work_rate": 1.4, "teamwork": 1.4, "long_shots": 1.4, "passing": 1.6,
            "strength": 1.0, "determination": 1.3, "concentration": 1.2},
    "AMR": {"dribbling": 3, "pace": 2.8, "acceleration": 2.8, "agility": 2.6, "technique": 2.6,
            "first_touch": 2.4, "crossing": 2.2, "off_the_ball": 2.2, "flair": 2.2,
            "finishing": 1.8, "balance": 2, "composure": 2, "decisions": 1.8, "vision": 1.8,
            "stamina": 1.8, "work_rate": 1.4, "teamwork": 1.4, "long_shots": 1.4, "passing": 1.6,
            "strength": 1.0, "determination": 1.3, "concentration": 1.2},
    "ST":  {"finishing": 3.2, "off_the_ball": 3, "composure": 2.8, "first_touch": 2.4,
            "technique": 2.2, "heading": 2.2, "pace": 2, "acceleration": 2, "strength": 2,
            "anticipation": 2.2, "decisions": 2, "dribbling": 1.8, "flair": 1.6, "vision": 1.4,
            "passing": 1.4, "aggression": 1.6, "determination": 1.8, "work_rate": 1.4,
            "stamina": 1.6, "long_shots": 1.4, "jumping": 1.6, "teamwork": 1.2},
}
PROFILE_KEYS = {k: list(v.keys()) for k, v in PROFILES.items()}
ALL_WEIGHTED = set()
for v in PROFILES.values():
    ALL_WEIGHTED |= set(v.keys())
BASE_ATTRS = [a for a in C.ATTRS if a not in ALL_WEIGHTED and a != "flair"]


def _seed(s):
    return int(hashlib.md5(s.encode()).hexdigest()[:12], 16)


# --------------------------------------------------------------------- schema
SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT);
CREATE TABLE IF NOT EXISTS clubs (
  id INTEGER PRIMARY KEY, code TEXT UNIQUE, name TEXT, short TEXT, country TEXT,
  league TEXT, tier INT, rep INT, profile TEXT, stadium TEXT, capacity INT,
  youth INT, facilities INT, coaching INT, scouting INT,
  cash REAL, transfer_budget REAL, wage_budget REAL, wage_bill REAL,
  balance REAL, debt REAL, prestige INT,
  season_income REAL, season_costs REAL, board_patience REAL,
  vision TEXT, chairman TEXT, reputation REAL
);
CREATE TABLE IF NOT EXISTS players (
  id INTEGER PRIMARY KEY, name TEXT, nat TEXT, nat2 TEXT, age INT, dob TEXT,
  pos TEXT, pos2 TEXT, foot TEXT, height INT, club_id INT, squad TEXT,
  attrs TEXT, ca REAL, pa REAL,
  value REAL, wage REAL, contract_end TEXT, agent TEXT,
  personality TEXT, professionalism INT, ambition INT, loyalty INT,
  pressure INT, consistency INT, big_games INT, injury_prone INT,
  fitness REAL, sharpness REAL, fatigue REAL, morale REAL, confidence REAL,
  form REAL, condition TEXT, return_date TEXT, injury_name TEXT,
  suspended INT, happiness REAL, promise TEXT, minutes_expected INT,
  familiar REAL, int_apps INT, int_goals INT,
  goals INT, assists INT, apps INT, minutes INT, conceded INT, clean_sheets INT,
  avg_rating REAL, yellow INT, red INT, injured_weeks INT,
  wanted_out INT, listed INT, loaned_to INT, loan_end TEXT, loan_wage_split REAL,
  hidden_seed INT, reputation REAL, preferred_moves TEXT, languages TEXT
);
CREATE TABLE IF NOT EXISTS staff (
  id INTEGER PRIMARY KEY, name TEXT, nat TEXT, role TEXT, club_id INT,
  attacking INT, defending INT, fitness INT, goalkeeping INT, mental INT,
  tactical INT, technical INT, youth INT, man_mgmt INT, judging INT,
  judging_pot INT, discipline INT, motivator INT, adaptability INT,
  wage REAL, contract_end TEXT, reputation INT, personality TEXT, age INT
);
CREATE TABLE IF NOT EXISTS competitions (
  id INTEGER PRIMARY KEY, code TEXT, name TEXT, country TEXT, ctype TEXT,
  tier INT, prestige INT, ucl_slots INT, uel_slots INT, uecl_slots INT,
  prom INT, rel INT, playoff INT
);
CREATE TABLE IF NOT EXISTS entries (comp_id INT, club_id INT, season INT);
CREATE TABLE IF NOT EXISTS fixtures (
  id INTEGER PRIMARY KEY, comp_id INT, season INT, round INT, stage TEXT,
  match_date TEXT, home_id INT, away_id INT, hg INT, aw INT, played INT,
  agg_h INT, agg_a INT, leg INT, venue TEXT, attendance INT,
  rating_h REAL, rating_a REAL, report TEXT, motm INT
);
CREATE TABLE IF NOT EXISTS finances (
  id INTEGER PRIMARY KEY, club_id INT, season INT, month TEXT,
  income REAL, wages REAL, other REAL, interest REAL, net REAL, cash REAL
);
CREATE TABLE IF NOT EXISTS standings (
  comp_id INT, season INT, club_id INT, stage TEXT, p INT, w INT, d INT, l INT,
  gf INT, ga INT, pts INT, form TEXT, pos INT, PRIMARY KEY(comp_id, season, club_id, stage)
);
CREATE TABLE IF NOT EXISTS transfers (
  id INTEGER PRIMARY KEY, player_id INT, from_id INT, to_id INT, fee REAL,
  wage REAL, date TEXT, season INT, ctype TEXT, addons TEXT, clause REAL,
  loan_end TEXT, split REAL
);
CREATE TABLE IF NOT EXISTS offers (
  id INTEGER PRIMARY KEY, player_id INT, from_id INT, to_id INT, fee REAL,
  addons TEXT, wage REAL, status TEXT, date TEXT, round INT, clause REAL,
  is_loan INT, loan_end TEXT, split REAL, human INT, note TEXT
);
CREATE TABLE IF NOT EXISTS inbox (
  id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, cat TEXT, priority TEXT,
  subject TEXT, body TEXT, read INT DEFAULT 0, payload TEXT, season INT
);
CREATE TABLE IF NOT EXISTS tactics (
  id INTEGER PRIMARY KEY, club_id INT, is_human INT, name TEXT, formation TEXT,
  mentality TEXT, instr TEXT, roles TEXT, familiarity REAL, identity TEXT,
  active INT DEFAULT 1
);
CREATE TABLE IF NOT EXISTS training (
  id INTEGER KEY, club_id INT, day INT, session TEXT, focus TEXT,
  PRIMARY KEY(club_id, day)
);
CREATE TABLE IF NOT EXISTS news (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, cat TEXT, text TEXT, club_id INT, player_id INT);
CREATE TABLE IF NOT EXISTS promises (id INTEGER PRIMARY KEY AUTOINCREMENT, player_id INT, ptype TEXT, value TEXT, date TEXT, deadline TEXT, status TEXT, note TEXT);
CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY AUTOINCREMENT, season INT, comp_id INT, club_id INT, pos INT, note TEXT, trophy TEXT);
CREATE TABLE IF NOT EXISTS managers (id INTEGER PRIMARY KEY, name TEXT, nat TEXT, age INT, club_id INT, reputation REAL, style TEXT, hired TEXT, human INT, attrs TEXT);
CREATE TABLE IF NOT EXISTS matches_log (id INTEGER PRIMARY KEY AUTOINCREMENT, fixture_id INT, date TEXT, home TEXT, away TEXT, hs INT, as_away INT, comp TEXT, data TEXT);
CREATE INDEX IF NOT EXISTS ix_players_club ON players(club_id);
CREATE INDEX IF NOT EXISTS ix_fix_date ON fixtures(match_date);
CREATE INDEX IF NOT EXISTS ix_fix_clubs ON fixtures(home_id, away_id);
CREATE INDEX IF NOT EXISTS ix_news_date ON news(date);
"""

SEASON_START = "2026-07-01"
SEASON = 2026


def connect():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=NORMAL")
    return con


# -------------------------------------------------------------- player making
def _attr_vector(rng, pos, ca, age, pa=None):
    """Build a realistic attribute vector for given position/ability."""
    prof = PROFILES[pos]
    w = 1.15 if age < 20 else 1.0
    vec = {}
    keys = list(prof.keys())
    # key attributes cluster around ca
    base = ca + rng.gauss(0, 0.6)
    for k in keys:
        if k == "flair":
            continue
        wt = prof[k] / 3.2
        v = ca * (0.86 + 0.24 * wt) + rng.gauss(0, 1.05)
        vec[k] = v
    for k in BASE_ATTRS:
        vec[k] = ca * 0.88 + rng.gauss(0, 1.35)
    if pos == "GK":
        for k in ("concentration", "composure", "decisions", "anticipation", "positioning",
                  "leadership", "strength", "jumping", "agility", "balance"):
            vec[k] = ca * rng.uniform(0.88, 1.02) + rng.gauss(0, 0.9)
    # age effects: physical peaks 24-29, mental improves to ~30
    if age <= 19:
        for k in ("decisions", "positioning", "concentration", "anticipation",
                  "composure", "leadership", "vision", "marking", "teamwork"):
            if k in vec:
                vec[k] -= rng.uniform(0.8, 2.4)
        for k in ("pace", "acceleration", "agility", "stamina"):
            if k in vec:
                vec[k] += rng.uniform(0.4, 1.2)
    elif age >= 33:
        d = (age - 32) * 0.85
        for k in ("pace", "acceleration", "agility", "stamina", "strength", "jumping"):
            if k in vec:
                vec[k] -= d * rng.uniform(0.8, 1.5)
        for k in ("decisions", "positioning", "anticipation", "leadership", "composure"):
            if k in vec:
                vec[k] += rng.uniform(0.3, 1.2)
    elif age >= 30:
        for k in ("pace", "acceleration", "agility"):
            if k in vec:
                vec[k] -= (age - 29) * 0.5
    if vec.get("flair") is None:
        vec["flair"] = base + rng.gauss(0, 1.5)
    # one signature strength, one weakness
    strong = rng.choice(keys)
    if strong in vec:
        vec[strong] += rng.uniform(1.5, 3.2)
    weak = rng.choice(BASE_ATTRS)
    vec[weak] -= rng.uniform(1.5, 3.5)
    # clamp
    out = {}
    for k, v in vec.items():
        out[k] = max(1, min(20, int(round(v))))
    # ensure GK attributes low for outfield and vice versa
    if pos != "GK":
        for k in C.GK:
            out[k] = max(1, min(6, rng.randint(1, 5)))
    else:
        for k in ("finishing", "crossing", "dribbling", "long_shots", "heading"):
            out[k] = max(1, min(9, rng.randint(2, 8)))
    return out


def pack_attrs(vec):
    return ",".join(str(vec.get(a, 5)) for a in C.ATTRS)


def unpack_attrs(s):
    vals = [int(x) for x in s.split(",")]
    return dict(zip(C.ATTRS, vals))


def compute_ca(vec):
    """Effective current ability from attribute vector (1-20 scale)."""
    vals = sorted(vec.values(), reverse=True)
    return round(sum(vals[:12]) / 12.0, 2)



def fit_ca(vec, target, max_iter=60):
    """Additively shift attributes so compute_ca(vec) ~= target (integer, clamped 1..20)."""
    for _ in range(max_iter):
        cur = compute_ca(vec)
        diff = target - cur
        if abs(diff) < 0.15:
            break
        step = 1 if diff > 0 else -1
        keys = sorted(vec, key=lambda k: -vec[k]) if step < 0 else sorted(vec, key=lambda k: vec[k])
        changed = False
        for k in keys:
            nv = vec[k] + step
            if 1 <= nv <= 20:
                vec[k] = nv
                changed = True
                if abs(compute_ca(vec) - target) < abs(diff):
                    diff = target - compute_ca(vec)
            if abs(target - compute_ca(vec)) < 0.15:
                break
        if not changed:
            break
    return vec


def value_of(ca, pa, age, pos, rep, contract_years, league_coef):
    base = 3.0e-7 * (max(ca, 1.0) ** 6.0)  # millions EUR
    base *= (0.55 + 0.45 * (pa / max(ca, 1)))
    if age < 23:
        base *= 1.0 + (23 - age) * 0.13
    elif age > 30:
        base *= max(0.05, 1.0 - (age - 30) * 0.22)
    if pos in ("ST", "AMC"):
        base *= 1.18
    elif pos == "GK":
        base *= 0.62
    elif pos in ("DC", "DM"):
        base *= 0.95
    base *= (0.6 + rep / 100.0) * (0.55 + 0.45 * league_coef)
    base *= (0.75 + 0.1 * min(contract_years, 5))
    return round(max(0.02, base), 2)


TIER_WAGE = {1: 1.0, 2: 0.55, 3: 0.32, 4: 0.21, 5: 0.13}


def wage_of(ca, age, league_coef, rep, tier=1):
    w = 0.0032 * (max(ca, 1.0) ** 3.7)  # €k per week
    w *= (0.42 + 0.72 * league_coef)
    w *= TIER_WAGE.get(tier, 1.0)
    if age > 33:
        w *= 0.8
    if age < 21:
        w *= 0.62
    return round(max(0.05, w), 2)


POS_COUNTS = {  # first-team squad composition by club level
    1: {"GK": 3, "DC": 5, "DL": 2, "DR": 2, "DM": 3, "MC": 4, "AMC": 2, "AML": 2, "AMR": 2, "ST": 3},
    2: {"GK": 3, "DC": 5, "DL": 2, "DR": 2, "DM": 2, "MC": 4, "AMC": 2, "AML": 2, "AMR": 2, "ST": 3},
    3: {"GK": 2, "DC": 4, "DL": 2, "DR": 2, "DM": 2, "MC": 4, "AMC": 2, "AML": 2, "AMR": 2, "ST": 3},
    4: {"GK": 2, "DC": 4, "DL": 2, "DR": 2, "DM": 2, "MC": 3, "AMC": 2, "AML": 2, "AMR": 2, "ST": 3},
    5: {"GK": 2, "DC": 4, "DL": 2, "DR": 2, "DM": 2, "MC": 3, "AMC": 1, "AML": 2, "AMR": 2, "ST": 2},
}


def ca_band(rep, tier, coef):
    """Average player CA for a club."""
    lvl = {"elite": 2.6, "ucl": 1.9, "dev": 1.6, "trad": 1.2, "mid": 0.9,
           "sell": 1.1, "yo-yo": 0.7, "minnow": 0.0}
    base = 8.2 + coef * 7.4 + (rep - 50) / 22.0
    base += lvl.get("mid", 0)
    return base



PLAYER_COLS = [c[0] for c in [
    ("id",0),("name",0),("nat",0),("nat2",0),("age",0),("dob",0),("pos",0),("pos2",0),
    ("foot",0),("height",0),("club_id",0),("squad",0),("attrs",0),("ca",0),("pa",0),
    ("value",0),("wage",0),("contract_end",0),("agent",0),("personality",0),
    ("professionalism",0),("ambition",0),("loyalty",0),("pressure",0),("consistency",0),
    ("big_games",0),("injury_prone",0),("fitness",0),("sharpness",0),("fatigue",0),
    ("morale",0),("confidence",0),("form",0),("condition",0),("return_date",0),
    ("injury_name",0),("suspended",0),("happiness",0),("promise",0),("minutes_expected",0),
    ("familiar",0),("int_apps",0),("int_goals",0),("goals",0),("assists",0),("apps",0),
    ("minutes",0),("conceded",0),("clean_sheets",0),("avg_rating",0),("yellow",0),("red",0),
    ("injured_weeks",0),("wanted_out",0),("listed",0),("loaned_to",0),("loan_end",0),
    ("loan_wage_split",0),("hidden_seed",0),("reputation",0),("preferred_moves",0),
    ("languages",0)]]

PLAYER_DEFAULTS = {
    "nat2": "", "pos2": "", "foot": "R", "height": 180, "squad": "First Team",
    "agent": "", "personality": "Balanced", "professionalism": 10, "ambition": 10,
    "loyalty": 10, "pressure": 10, "consistency": 10, "big_games": 10, "injury_prone": 5,
    "fitness": 95.0, "sharpness": 70.0, "fatigue": 0.0, "morale": 65.0, "confidence": 60.0,
    "form": 0.0, "condition": "fit", "return_date": "", "injury_name": "", "suspended": 0,
    "happiness": 65.0, "promise": "", "minutes_expected": 0, "familiar": 0.0, "int_apps": 0,
    "int_goals": 0, "goals": 0, "assists": 0, "apps": 0, "minutes": 0, "conceded": 0,
    "clean_sheets": 0, "avg_rating": 0.0, "yellow": 0, "red": 0, "injured_weeks": 0,
    "wanted_out": 0, "listed": 0, "loaned_to": None, "loan_end": None, "loan_wage_split": 0.0,
    "hidden_seed": 0, "reputation": 10.0, "preferred_moves": "", "languages": "",
}


def _player_row(d):
    row = []
    for c in PLAYER_COLS:
        if c in d:
            row.append(d[c])
        else:
            row.append(PLAYER_DEFAULTS[c])
    return tuple(row)


PLAYER_INSERT = "INSERT INTO players (%s) VALUES (%s)" % (
    ",".join(PLAYER_COLS), ",".join("?" * len(PLAYER_COLS)))


GLOBAL_BRAND = {
    "RMA": 1.95, "BAR": 1.90, "MUN": 1.85, "LIV": 1.80, "BAY": 1.70, "MCI": 1.65,
    "PSG": 1.65, "JUV": 1.55, "CHE": 1.50, "ARS": 1.45, "ACM": 1.40, "INT": 1.40,
    "BVB": 1.35, "ATM": 1.25, "TOT": 1.25, "NAP": 1.20, "LEV1": 1.10, "AJA1": 1.00,
    "SLB": 0.95, "FCP": 0.95, "SPORT": 0.95, "CEL": 0.90, "RAN": 0.85, "GAL": 0.95,
    "FEN": 0.95, "BJK": 0.85, "BOCA": 1.00, "RIV": 1.00, "FLA": 1.10, "PALM": 1.00,
    "NEW": 0.95, "AVL": 0.90, "WHU": 0.85, "EVE": 0.80, "OM": 0.90, "OL": 0.85,
    "ASM": 0.85, "FEY": 0.85, "PSV": 0.85, "RBL": 0.85, "SGE": 0.80, "VFB": 0.80,
    "ROM": 0.95, "LAZ": 0.80, "SEV": 0.85, "ATH": 0.80, "VAL": 0.85, "SCH": 0.80,
    "HSVI": 0.75, "LEI": 0.80, "SOU": 0.75, "NOT": 0.80, "LEE": 0.80, "LOSC": 0.75,
    "FCN1": 0.75, "KOE": 0.75, "ASSE": 0.80, "GIR": 0.80, "SHE": 0.70, "SUN": 0.70,
    "BRI": 0.65, "WOL": 0.70, "CRY": 0.70, "FUL": 0.65, "BRE": 0.60, "AFC": 0.60,
    "BUR": 0.60, "RSC": 0.75, "VIL": 0.75, "BET": 0.75, "FIO": 0.70, "BOL": 0.70,
    "TOR": 0.70, "ATA": 0.70, "TSG": 0.60, "SCF": 0.60, "WOB": 0.65, "BMG": 0.70,
    "CLU": 0.75, "AND": 0.80, "GENK": 0.65, "TRA": 0.70, "SAO": 0.85, "COR1": 0.85,
    "GRE": 0.75, "INT1": 0.75, "CRU": 0.80, "ATM1": 0.80, "FLU": 0.75, "BOTF": 0.75,
}


def build_world(seed=20260701):
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    for extra in (DB_PATH + "-wal", DB_PATH + "-shm"):
        if os.path.exists(extra):
            os.remove(extra)
    con = connect()
    con.executescript(SCHEMA)
    rng = random.Random(seed)

    league_info = {code: dict(code=code, name=name, country=country, tier=tier,
                              size=size, coef=coef, prestige=prestige)
                   for code, name, country, tier, size, coef, prestige in C.LEAGUES}

    # ---------------------------------------------------------------- clubs
    clubs = {}
    cid = 0
    for tup in C.CLUBS:
        code, name, short, rep, stadium, cap, country, profile = tup
        cid += 1
        clubs[code] = dict(id=cid, code=code, name=name, short=short, rep=rep,
                           stadium=stadium, capacity=cap, country=country,
                           profile=profile, league=None, tier=1)

    # assign leagues in the order clubs are listed
    order = list(clubs.keys())
    idx = 0
    for code, name, country, tier, size, coef, prestige in C.LEAGUES:
        for i in range(size):
            if idx >= len(order):
                break
            c = clubs[order[idx]]
            c["league"] = code
            c["tier"] = tier
            c["coef"] = coef
            idx += 1
    # any leftovers -> lowest league of their country
    while idx < len(order):
        c = clubs[order[idx]]
        for code, name, country, tier, size, coef, prestige in reversed(C.LEAGUES):
            if country == c["country"]:
                c["league"], c["tier"], c["coef"] = code, tier, coef
                break
        idx += 1

    prof_adj = {"elite": 4.2, "ucl": 2.4, "dev": 1.4, "trad": 0.6, "mid": 0.0,
                "sell": 0.4, "yo-yo": -0.4, "minnow": -1.2}

    con.execute("BEGIN")
    for code in order:
        c = clubs[code]
        r = random.Random(_seed(code + "club"))
        lg = league_info[c["league"]]
        coef = lg["coef"]
        tier = lg["tier"]
        squad_ca = 5.4 + coef * 8.4 + prof_adj.get(c["profile"], 0) * 0.85 + (c["rep"] - 50) / 44.0
        squad_ca = max(3.5, min(17.4, squad_ca))
        facilities = int(max(1, min(20, round(3 + coef * 12 + prof_adj.get(c["profile"], 0) * 0.9 + r.gauss(0, 1.6)))))
        coaching = int(max(1, min(20, round(3 + coef * 12 + prof_adj.get(c["profile"], 0) * 0.8 + r.gauss(0, 1.8)))))
        youth = int(max(1, min(20, round(3 + coef * 11 + prof_adj.get(c["profile"], 0) * 0.7 + r.gauss(0, 2.2)))))
        scouting = int(max(1, min(20, round(3 + coef * 11 + prof_adj.get(c["profile"], 0) * 0.7 + r.gauss(0, 2.0)))))
        # finances in €m
        rev_coef = {1: 1.0, 2: 0.15, 3: 0.05, 4: 0.032, 5: 0.011}[tier]
        brand = GLOBAL_BRAND.get(code, 1.0)
        tv = (46 + 9.2 * (c["rep"] - 50) / 10.0) * rev_coef * brand * (0.55 + 0.45 * coef)
        # matchday: capacity x fill x ticket price x home games (real money, not tier-scaled)
        fill = 0.94 - 0.011 * max(0, 5 - c["rep"] / 12.0) - 0.02 * (tier - 1)
        fill = max(0.35, min(0.99, fill))
        ticket = {1: 62.0, 2: 36.0, 3: 26.0, 4: 21.0, 5: 14.0}[tier] * (0.85 + 0.3 * brand)
        home_games = 19 + (4 if tier <= 2 else 3)
        md = c["capacity"] * fill * ticket * home_games / 1.0e6
        comm = (12 + 0.62 * (c["rep"] - 40)) * rev_coef * brand
        revenue = tv + md + comm
        revenue = round(max(0.28, revenue * (0.85 + r.random() * 0.32)), 2)
        wage_budget = round(revenue * (0.52 + r.uniform(-0.08, 0.18)), 2)
        tb_mult = {"elite": (0.16, 0.46), "ucl": (0.10, 0.30), "dev": (0.08, 0.26),
                   "sell": (0.06, 0.22), "trad": (0.02, 0.14), "mid": (0.02, 0.14),
                   "yo-yo": (0.01, 0.10), "minnow": (0.0, 0.06)}[c["profile"]]
        transfer_budget = round(max(0.0, revenue * r.uniform(*tb_mult)), 2)
        cash = round(revenue * (0.08 + r.uniform(0, 0.2)), 2)
        debt = round(revenue * (0.9 if c["profile"] in ("trad", "yo-yo") else 0.35) * r.uniform(0.2, 1.5), 2)
        balance = round(revenue * r.uniform(-0.14, 0.12), 2)
        visions = ["Attacking football", "Youth development", "Financial sustainability",
                   "Domestic success", "European success", "Develop and sell players",
                   "Establish in division", "Nothing specific"]
        vision = r.choice(visions if tier > 1 else ["Attacking football", "Youth development",
                                                    "Domestic success", "European success",
                                                    "Financial sustainability", "Develop and sell players"])
        chairman = make_staff_name(r, c["country"])
        con.execute("""INSERT INTO clubs (id,code,name,short,country,league,tier,rep,profile,stadium,
            capacity,youth,facilities,coaching,scouting,cash,transfer_budget,wage_budget,wage_bill,
            balance,debt,prestige,season_income,season_costs,board_patience,vision,chairman,reputation)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (c["id"], code, c["name"], c["short"], c["country"], c["league"], tier, c["rep"],
             c["profile"], c["stadium"], c["capacity"], youth, facilities, coaching, scouting,
             cash, transfer_budget, wage_budget, 0.0, balance, debt, c["rep"], revenue,
             revenue * 1.02, 45 + r.randint(-15, 25), vision, chairman, float(c["rep"])))
        c["squad_ca"] = squad_ca
        c["tier"] = tier
        c["coef"] = coef
        c["facilities"] = facilities
        c["coaching"] = coaching
        c["youth"] = youth

    # ------------------------------------------------------------- players
    pid = 0
    players_rows = []
    foreign_quota = {1: 0.55, 2: 0.32, 3: 0.16, 4: 0.09, 5: 0.04}
    for code in order:
        c = clubs[code]
        r = random.Random(_seed(code + "squad"))
        tier = c["tier"]
        counts = POS_COUNTS[min(tier, 5)]
        squad_ca = c["squad_ca"]
        foreign_p = foreign_quota[tier]
        # ability tiers inside squad: best -> fringe
        n = sum(counts.values())
        for pi, (pos, cnt) in enumerate(counts.items()):
            for k in range(cnt):
                pid += 1
                rank = (pi * 1.0 + k) / max(1, n - 1)
                ca = squad_ca + (1.35 - 3.1 * rank) + r.gauss(0, 0.8)
                ca = max(2.2, min(19.8, ca))
                # age distribution
                roll = r.random()
                if roll < 0.22:
                    age = r.randint(17, 21)
                elif roll < 0.78:
                    age = r.randint(22, 29)
                else:
                    age = r.randint(30, 36)
                if k == 0 and pos == "GK" and tier <= 2 and age < 22:
                    age = r.randint(23, 32)
                pa = ca
                if age < 24:
                    pa = ca + abs(r.gauss(0, 1.5)) * (1.0 if age < 20 else 0.7)
                    pa = min(20, max(ca, pa + (0.4 if r.random() < 0.5 else 0)))
                else:
                    pa = ca
                nat = c["country"] if r.random() > foreign_p else r.choice(NATIONALITY_POOL)
                vec = fit_ca(_attr_vector(r, pos, ca, age, pa), min(20, ca))
                real_ca = compute_ca(vec)
                contract_years = r.choice([1, 1, 2, 2, 3, 3, 4, 5])
                if age < 21:
                    contract_years = r.choice([2, 3, 3, 4])
                if age > 33:
                    contract_years = r.choice([1, 1, 2])
                cend = date(2027, 6, 30) if contract_years == 1 else date(2027 + contract_years - 1, 6, 30)
                pos2 = ""
                near = {"DC": ["DM"], "DM": ["MC"], "MC": ["DM", "AMC"], "AMC": ["MC", "ST"],
                        "AML": ["ST", "AMR"], "AMR": ["ST", "AML"], "ST": ["AMC", "AML"],
                        "DL": ["AML"], "DR": ["AMR"], "GK": []}
                if near.get(pos) and r.random() < 0.42:
                    pos2 = r.choice(near[pos])
                foot = r.choice(["R", "R", "R", "L", "L", "B"]) if r.random() < 0.9 else "B"
                height = int(r.gauss({"GK": 190, "DC": 187, "ST": 183, "DM": 181}.get(pos, 178), 6))
                val = value_of(real_ca, pa, age, pos, c["rep"], contract_years, c["coef"])
                wg = wage_of(real_ca, age, c["coef"], c["rep"], tier)
                pers = r.choice(C.PERSONALITIES)
                players_rows.append(_player_row(dict(
                    id=pid, name=make_name(r, nat), nat=nat,
                    nat2="" if nat == c["country"] else c["country"],
                    age=age, dob=str(date(2026 - age, r.randint(1, 12), r.randint(1, 28))),
                    pos=pos, pos2=pos2, foot=foot, height=height, club_id=c["id"],
                    squad="First Team" if rank < 0.72 else "Reserve",
                    attrs=pack_attrs(vec), ca=round(real_ca, 2), pa=round(pa, 2),
                    value=val, wage=wg, contract_end=cend.isoformat(),
                    agent=make_staff_name(r, nat), personality=pers,
                    professionalism=r.randint(6, 20), ambition=r.randint(5, 20),
                    loyalty=r.randint(4, 18), pressure=r.randint(5, 18),
                    consistency=r.randint(5, 18), big_games=r.randint(5, 18),
                    injury_prone=r.randint(1, 12),
                    fitness=round(r.uniform(88, 100), 1), sharpness=round(r.uniform(60, 95), 1),
                    morale=round(r.uniform(45, 85), 1), confidence=round(r.uniform(40, 80), 1),
                    form=round(r.gauss(0, 1.2), 2), happiness=round(r.uniform(50, 80), 1),
                    int_apps=r.randint(0, 90), int_goals=r.randint(0, 25),
                    hidden_seed=_seed(code + str(pid)),
                    reputation=round(min(95, c["rep"] * (0.4 + real_ca / 28.0)), 1),
                    languages=nat,
                )))
    con.executemany(PLAYER_INSERT, players_rows)

    # hand-seeded stars
    for st in C.STARS:
        code, nm, nat, age, pos, pos2, ca, pa, foot, wg, val = st
        if code not in clubs:
            continue
        c = clubs[code]
        r = random.Random(_seed(nm))
        vec = fit_ca(_attr_vector(r, pos, ca, age), min(20, ca + 0.5))
        pid += 1
        cy = r.choice([2, 3, 4])
        real_ca = compute_ca(vec)
        con.execute(PLAYER_INSERT, _player_row(dict(
            id=pid, name=nm, nat=nat, age=age, dob=str(date(2026 - age, 6, 15)),
            pos=pos, pos2=pos2, foot=foot, height=r.randint(172, 192), club_id=c["id"],
            squad="First Team", attrs=pack_attrs(vec), ca=round(real_ca, 2), pa=float(pa),
            value=round(max(value_of(real_ca, float(pa), age, pos, c["rep"], cy, c["coef"]), float(val)), 2),
            wage=round(max(wg * 1000.0,
                           wage_of(real_ca, age, c["coef"], c["rep"], c.get("tier", 1))), 2),
            contract_end=date(2026 + cy, 6, 30).isoformat(),
            agent=make_staff_name(r, nat), personality=r.choice(C.PERSONALITIES),
            professionalism=r.randint(12, 20), ambition=r.randint(12, 20),
            loyalty=r.randint(8, 18), pressure=r.randint(10, 20), consistency=r.randint(12, 20),
            big_games=r.randint(14, 20), injury_prone=r.randint(1, 6),
            fitness=97.0, sharpness=90.0, morale=85.0, confidence=85.0,
            form=round(r.gauss(0.5, 1), 2), happiness=70.0,
            int_apps=r.randint(30, 130), int_goals=r.randint(0, 40),
            hidden_seed=_seed(nm), reputation=min(95.0, 20 + ca * 3.4), languages=nat)))

    # youth academies
    for code in order:
        c = clubs[code]
        r = random.Random(_seed(code + "youth"))
        tier = c["tier"]
        n_y = {1: 12, 2: 10, 3: 8, 4: 7, 5: 6}[tier]
        yq = c["youth"]
        for k in range(n_y):
            pid += 1
            pos = r.choice(["GK", "DC", "DC", "DL", "DR", "DM", "MC", "MC", "AMC", "AML", "AMR", "ST", "ST"])
            age = r.choice([15, 16, 16, 17, 17, 18, 18, 19])
            base = c["squad_ca"] * (0.44 + 0.13 * (yq / 20.0)) + r.gauss(0, 1.1)
            ca = max(2.0, min(c["squad_ca"] + 0.5, base * (0.60 + 0.42 * (age / 18.0))))
            pa = min(20.0, ca + abs(r.gauss(2.2, 1.8)) * (0.6 + yq / 28.0))
            vec = fit_ca(_attr_vector(r, pos, ca, age), min(20, ca))
            rca = compute_ca(vec)
            nat = c["country"] if r.random() < 0.85 else r.choice(NATIONALITY_POOL)
            cy = r.choice([1, 2, 3])
            con.execute(PLAYER_INSERT, _player_row(dict(
                id=pid, name=make_name(r, nat), nat=nat, age=age,
                dob=str(date(2026 - age, 5, 1)), pos=pos, foot=r.choice(["R", "L"]),
                height=r.randint(165, 188), club_id=c["id"],
                squad="U21" if age >= 18 else "Youth",
                attrs=pack_attrs(vec), ca=round(rca, 2), pa=round(pa, 2),
                value=round(value_of(rca, pa, age, pos, c["rep"], cy, c["coef"]), 2),
                wage=round(wage_of(ca, age, c["coef"], c["rep"], tier) * 0.06, 2),
                contract_end=date(2026 + cy, 6, 30).isoformat(),
                personality=r.choice(C.PERSONALITIES),
                professionalism=r.randint(6, 20), ambition=r.randint(5, 20),
                loyalty=r.randint(4, 18), pressure=r.randint(5, 15),
                consistency=r.randint(5, 15), big_games=r.randint(6, 18),
                injury_prone=r.randint(1, 10), fitness=100.0, sharpness=70.0,
                morale=70.0, confidence=60.0, happiness=60.0,
                hidden_seed=_seed(nat + str(pid)),
                reputation=round(c["rep"] * 0.2, 1), languages=nat)))

    # ---------------------------------------------------------------- staff
    sid = 0
    staff_roles = [("Assistant Manager", 1), ("First-Team Coach", 2), ("First-Team Coach", 2),
                   ("Fitness Coach", 1), ("Goalkeeping Coach", 1), ("Head of Youth Development", 1),
                   ("Chief Scout", 1), ("Scout", 2), ("Physio", 2), ("Data Analyst", 1)]
    for code in order:
        c = clubs[code]
        r = random.Random(_seed(code + "staff"))
        q = c["coef"]
        base = 6 + q * 11 + prof_adj.get(c["profile"], 0) * 0.5
        for role, cnt in staff_roles:
            for k in range(cnt):
                sid += 1
                lvl = max(2, min(20, int(round(base + r.gauss(0, 2.2)))))
                spec = {}
                if role == "Fitness Coach":
                    spec = dict(fitness=lvl + 2, technical=lvl - 3, tactical=lvl - 3)
                elif role == "Goalkeeping Coach":
                    spec = dict(goalkeeping=lvl + 2, technical=lvl - 1)
                elif role == "Head of Youth Development":
                    spec = dict(youth=lvl + 3)
                elif role in ("Chief Scout", "Scout"):
                    spec = dict(judging=lvl + 1, judging_pot=lvl + 1, tactical=lvl - 2)
                elif role == "Physio":
                    spec = dict(fitness=lvl, mental=lvl - 4)
                elif role == "Data Analyst":
                    spec = dict(tactical=lvl + 1, judging=lvl + 1)
                else:
                    spec = {}
                con.execute("""INSERT INTO staff VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (sid, make_staff_name(r, c["country"]), c["country"] if r.random() < 0.75
                     else r.choice(NATIONALITY_POOL), role, c["id"],
                     spec.get("attacking", lvl), spec.get("defending", lvl),
                     spec.get("fitness", lvl), spec.get("goalkeeping", max(2, lvl - 4)),
                     spec.get("mental", lvl), spec.get("tactical", lvl),
                     spec.get("technical", lvl), spec.get("youth", max(2, lvl - 3)),
                     spec.get("man_mgmt", lvl), spec.get("judging", max(2, lvl - 2)),
                     spec.get("judging_pot", max(2, lvl - 2)), spec.get("discipline", lvl),
                     spec.get("motivator", lvl), spec.get("adaptability", lvl),
                     round(lvl * 0.55 * (0.4 + c["coef"]) * (0.45 + c["rep"] / 110.0), 2),
                     date(2026 + r.randint(1, 4), 6, 30).isoformat(),
                     lvl * 3, r.choice(C.PERSONALITIES), r.randint(30, 62)))
    # ------------------------------------------------------------- managers
    mid = 0
    all_club_rows = con.execute("""SELECT c.id, c.code, c.name, c.country, c.rep, c.profile, c.league
        FROM clubs c""").fetchall()
    for crow in all_club_rows:
        code = crow["code"]
        _li = league_info.get(crow["league"])
        c = {"id": crow["id"], "code": code, "name": crow["name"], "country": crow["country"],
             "rep": crow["rep"], "coef": (_li["coef"] if _li else 0.4), "profile": crow["profile"]}
        r = random.Random(_seed(code + "manager"))
        rep = min(95.0, c["rep"] * 0.72 + r.uniform(-4, 8))
        styles = ["Possession", "High press", "Counter-attack", "Direct", "Balanced",
                  "Defensive solidity", "Wing play", "Youth-focused"]
        attrs = {}
        lvl = 6 + c["coef"] * 11 + prof_adj.get(c["profile"], 0) * 0.4
        for k in ("attacking", "defending", "fitness", "tactical", "mental", "technical",
                  "youth", "man_mgmt", "motivation", "adaptability", "judging"):
            attrs[k] = max(3, min(20, int(round(lvl + r.gauss(0, 2.4)))))
        con.execute("INSERT INTO managers VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (mid + 1, make_manager_name(r), c["country"] if r.random() < 0.6
                     else r.choice(NATIONALITY_POOL), r.randint(33, 66), c["id"], rep,
                     r.choice(styles), "2024-07-01", 0, json.dumps(attrs)))
        mid += 1

    con.execute("COMMIT")

    # ------------------------------------------- wage bills & budget sanity
    for crow in all_club_rows:
        code = crow["code"]
        c = {"id": crow["id"], "code": code}
        bill = con.execute(
            "SELECT COALESCE(SUM(wage),0) AS b FROM players WHERE club_id=? AND squad IN ('First Team','Reserve')",
            (c["id"],)).fetchone()["b"]
        bill = bill * 52.0 / 1000.0  # weekly EURk -> annual EURm
        row = con.execute("SELECT wage_budget, transfer_budget, cash, season_income FROM clubs WHERE id=?",
                          (c["id"],)).fetchone()
        wb = max(row["season_income"] * 0.60, bill * 1.02)
        tb = max(row["transfer_budget"], wb * 0.42, bill * 0.18)
        con.execute("UPDATE clubs SET wage_bill=?, wage_budget=?, transfer_budget=?, cash=? WHERE id=?",
                    (round(bill, 2), round(wb, 2), round(tb, 2),
                     round(max(row["cash"], tb * 0.5), 2), c["id"]))
    con.commit()

    # --------------------------------------------------------- competitions
    comps = []
    comp_id = 0
    for code, name, country, tier, size, coef, prestige in C.LEAGUES:
        comp_id += 1
        ucl = uel = uecl = prom = rel = po = 0
        if tier == 1:
            if prestige >= 88:
                ucl, uel, uecl = 4, 2, 1
            elif prestige >= 70:
                ucl, uel, uecl = 3, 2, 1
            elif prestige >= 55:
                ucl, uel, uecl = 2, 1, 1
            else:
                ucl, uel, uecl = 1, 1, 0
            prom = 0
            rel = 3 if size >= 18 else 2
            po = 1
            if country in ("Netherlands", "Scotland", "Belgium", "Portugal", "Turkey"):
                rel = 2 if size >= 16 else 1
        else:
            prom = 3 if tier < 5 else 2
            rel = 4 if size >= 22 else (3 if size >= 18 else 2)
            if tier == 2:
                po = 1
        comps.append((comp_id, code, name, country, "league", tier, prestige,
                      ucl, uel, uecl, prom, rel, po))
    # domestic cups
    for country, cname, ccode in [("England", "FA Cup", "FACUP"), ("England", "EFL Cup", "EFLCUP"),
                                  ("Spain", "Copa del Rey", "COPADELREY"), ("Italy", "Coppa Italia", "COPPAITALIA"),
                                  ("Germany", "DFB-Pokal", "DFBPOKAL"), ("France", "Coupe de France", "COUPEFRANCE"),
                                  ("Netherlands", "KNVB Cup", "KNVB"), ("Portugal", "Taca de Portugal", "TACAPOR"),
                                  ("Scotland", "Scottish Cup", "SCOCUP"), ("Belgium", "Belgian Cup", "BELCUP"),
                                  ("Turkey", "Turkish Cup", "TURCUP"), ("Argentina", "Copa Argentina", "COPARG"),
                                  ("Brazil", "Copa do Brasil", "COPBRA")]:
        comp_id += 1
        comps.append((comp_id, ccode, cname, country, "cup", 1, 70, 0, 1, 0, 0, 0, 0))
    comp_id += 1
    comps.append((comp_id, "UCL", "UEFA Champions League", "Europe", "continental", 0, 98, 0, 0, 0, 0, 0, 0))
    comp_id += 1
    comps.append((comp_id, "UEL", "UEFA Europa League", "Europe", "continental", 0, 82, 0, 0, 0, 0, 0, 0))
    comp_id += 1
    comps.append((comp_id, "UECL", "UEFA Conference League", "Europe", "continental", 0, 70, 0, 0, 0, 0, 0, 0))
    con.executemany("INSERT INTO competitions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", comps)
    comp_by_code = {c[1]: c for c in comps}

    # entries
    entries = []
    for code, name, country, tier, size, coef, prestige in C.LEAGUES:
        cidc = comp_by_code[code][0]
        for k, ccode in enumerate(order):
            if clubs[ccode]["league"] == code:
                entries.append((cidc, clubs[ccode]["id"], SEASON))
    con.executemany("INSERT INTO entries VALUES (?,?,?)", entries)

    # cup + continental entries
    # league codes belonging to each nation (Welsh clubs in the English pyramid and
    # Monaco in France must enter the domestic cups of the league they play in)
    leagues_by_country = {}
    for code, name, lcountry, tier, size, coef, prestige in C.LEAGUES:
        leagues_by_country.setdefault(lcountry, []).append(code)

    def league_clubs(country, tiers):
        codes = set(leagues_by_country.get(country, []))
        out = []
        for ccode in order:
            c = clubs[ccode]
            if c["league"] in codes and c["tier"] in tiers:
                out.append(c["id"])
        return out

    cup_entries = {}
    for ccode_name, tiers in [("FACUP", (1, 2, 3, 4, 5)), ("EFLCUP", (1, 2, 3, 4)),
                              ("COPADELREY", (1, 2)), ("COPPAITALIA", (1, 2)),
                              ("DFBPOKAL", (1, 2)), ("COUPEFRANCE", (1, 2)),
                              ("KNVB", (1,)), ("TACAPOR", (1,)), ("SCOCUP", (1, 2)),
                              ("BELCUP", (1,)), ("TURCUP", (1,)), ("COPARG", (1,)),
                              ("COPBRA", (1,))]:
        country = comp_by_code[ccode_name][3]
        cup_entries[ccode_name] = league_clubs(country, tiers)

    # continental qualification (based on rep)
    def top_clubs(countries, n):
        pool = []
        for ccode in order:
            c = clubs[ccode]
            if c["country"] in countries and c["tier"] == 1:
                pool.append((c["rep"] + (10 if c["profile"] in ("elite", "ucl") else 0), c["id"]))
        pool.sort(reverse=True)
        return [p[1] for p in pool[:n]]

    euro_countries = {"England", "Spain", "Italy", "Germany", "France", "Netherlands",
                      "Portugal", "Scotland", "Belgium", "Turkey"}
    ucl_teams = top_clubs(euro_countries, 36)
    rest = top_clubs(euro_countries, 36 + 36)[36:]
    uel_teams = rest[:36]
    uecl_pool = top_clubs(euro_countries, 36 + 36 + 36)[72:]
    uecl_teams = uecl_pool[:36]
    for code, teams in [("UCL", ucl_teams), ("UEL", uel_teams), ("UECL", uecl_teams)]:
        for t in teams:
            entries.append((comp_by_code[code][0], t, SEASON))
    for code, teams in cup_entries.items():
        for t in teams:
            entries.append((comp_by_code[code][0], t, SEASON))
    con.executemany("INSERT INTO entries VALUES (?,?,?)", entries)

    # ------------------------------------------------------------- fixtures
    fixtures = []
    fid = 0

    def daterange_weeks(start, weeks, skip=None):
        out = []
        d = start
        while len(out) < weeks:
            if not (skip and d.isocalendar()[1] in skip):
                out.append(d)
            d += timedelta(days=7)
        return out

    winter = {2}  # ISO week 2 of 2027 = winter break (Jan 4-10)
    for code, name, country, tier, size, coef, prestige in C.LEAGUES:
        cidc = comp_by_code[code][0]
        members = [clubs[x]["id"] for x in order if clubs[x]["league"] == code]
        rng2 = random.Random(_seed(code + "fix"))
        rng2.shuffle(members)
        rounds = double_round_robin(members, rng2)
        n_rounds = len(rounds)
        start = date(2026, 8, 15) if tier == 1 else date(2026, 8, 8)
        if country in ("Brazil", "Argentina"):
            start = date(2026, 7, 11)
        # midweek rounds for big leagues
        midweeks = []
        if size >= 22 and country != "Scotland":
            midweeks = [date(2026, 8, 25), date(2026, 9, 22), date(2026, 12, 15),
                        date(2027, 1, 19), date(2027, 2, 23), date(2027, 4, 6)]
        slots = []
        wi = 0
        base_weeks = daterange_weeks(start, n_rounds + len(midweeks) + 4, skip=winter if tier <= 2 else None)
        bi = 0
        for i in range(n_rounds):
            while bi < len(base_weeks) and base_weeks[bi] <= (slots[-1] if slots else date(2020, 1, 1)):
                bi += 1
            if midweeks and i in (4, 9, 17, 22, 27, 33) and wi < len(midweeks) and midweeks[wi] > (slots[-1] if slots else date(2020, 1, 1)):
                slots.append(midweeks[wi]); wi += 1
            else:
                slots.append(base_weeks[bi]); bi += 1
        for i, rnd in enumerate(rounds):
            d = slots[i] if i < len(slots) else slots[-1] + timedelta(days=7 * (i - len(slots) + 1))
            for h, a in rnd:
                fid += 1
                fixtures.append((fid, cidc, SEASON, i + 1, "league", d.isoformat(), h, a,
                                 None, None, 0, None, None, 1, None, None, None, None, None))
        con.executemany("INSERT INTO standings (comp_id,season,club_id,stage,p,w,d,l,gf,ga,pts,form,pos) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        [(cidc, SEASON, m, "league", 0, 0, 0, 0, 0, 0, 0, "", 0) for m in members])

    # cup fixtures: first rounds only (draws generated as reached)
    cup_round_dates = {
        "FACUP": [("R1", date(2026, 11, 7)), ("R2", date(2026, 12, 5)), ("R3", date(2027, 1, 9)),
                  ("R4", date(2027, 1, 30)), ("R5", date(2027, 3, 2)), ("QF", date(2027, 3, 20)),
                  ("SF", date(2027, 4, 24)), ("F", date(2027, 5, 15))],
        "EFLCUP": [("R1", date(2026, 8, 11)), ("R2", date(2026, 8, 25)), ("R3", date(2026, 9, 15)),
                   ("R4", date(2026, 10, 27)), ("QF", date(2026, 12, 15)), ("SF", date(2027, 1, 12)),
                   ("F", date(2027, 2, 28))],
        "COPADELREY": [("R1", date(2026, 11, 4)), ("R32", date(2027, 1, 6)), ("R16", date(2027, 1, 20)),
                       ("QF", date(2027, 2, 3)), ("SF", date(2027, 3, 3)), ("F", date(2027, 4, 24))],
        "COPPAITALIA": [("R1", date(2026, 8, 15)), ("R16", date(2026, 12, 9)), ("QF", date(2027, 1, 27)),
                        ("SF", date(2027, 3, 3)), ("F", date(2027, 5, 12))],
        "DFBPOKAL": [("R1", date(2026, 8, 21)), ("R2", date(2026, 10, 27)), ("R16", date(2027, 2, 2)),
                     ("QF", date(2027, 3, 2)), ("SF", date(2027, 4, 20)), ("F", date(2027, 5, 22))],
        "COUPEFRANCE": [("R7", date(2026, 11, 14)), ("R64", date(2027, 1, 2)), ("R32", date(2027, 1, 23)),
                        ("R16", date(2027, 2, 6)), ("QF", date(2027, 3, 6)), ("SF", date(2027, 4, 17)),
                        ("F", date(2027, 5, 8))],
        "KNVB": [("R1", date(2026, 10, 20)), ("R16", date(2027, 1, 19)), ("QF", date(2027, 2, 9)),
                 ("SF", date(2027, 3, 9)), ("F", date(2027, 4, 25))],
        "TACAPOR": [("R3", date(2026, 10, 17)), ("R4", date(2026, 11, 21)), ("R16", date(2027, 1, 16)),
                    ("QF", date(2027, 2, 13)), ("SF", date(2027, 3, 13)), ("F", date(2027, 5, 23))],
        "SCOCUP": [("R3", date(2026, 11, 28)), ("R4", date(2027, 1, 23)), ("R5", date(2027, 2, 20)),
                   ("QF", date(2027, 3, 20)), ("SF", date(2027, 4, 24)), ("F", date(2027, 5, 22))],
        "BELCUP": [("R6", date(2026, 9, 23)), ("R7", date(2026, 12, 2)), ("QF", date(2027, 1, 20)),
                   ("SF", date(2027, 2, 10)), ("F", date(2027, 5, 1))],
        "TURCUP": [("R3", date(2026, 10, 28)), ("R4", date(2026, 12, 16)), ("R16", date(2027, 2, 10)),
                   ("QF", date(2027, 3, 10)), ("SF", date(2027, 4, 21)), ("F", date(2027, 5, 19))],
        "COPARG": [("R64", date(2027, 2, 10)), ("R32", date(2027, 3, 18)), ("R16", date(2027, 4, 15)),
                   ("QF", date(2027, 5, 6)), ("SF", date(2027, 5, 20)), ("F", date(2027, 5, 30))],
        "COPBRA": [("R1", date(2027, 2, 17)), ("R2", date(2027, 3, 3)), ("R32", date(2027, 4, 14)),
                   ("R16", date(2027, 5, 12)), ("QF", date(2027, 5, 26)), ("SF", date(2027, 6, 9)),
                   ("F", date(2027, 6, 23))],
    }
    for ccode, rounds in cup_round_dates.items():
        cidc = comp_by_code[ccode][0]
        teams = cup_entries.get(ccode, [])
        if not teams:
            continue
        rng3 = random.Random(_seed(ccode))
        rng3.shuffle(teams)
        stage, d = rounds[0]
        n = len(teams)
        # pair up
        for i in range(0, n - 1, 2):
            fid += 1
            fixtures.append((fid, cidc, SEASON, 1, stage, d.isoformat(), teams[i], teams[i + 1],
                             None, None, 0, None, None, 1, None, None, None, None, None))
        if n % 2:
            # odd number of entrants: the last team receives a bye into the next round
            con.execute("""INSERT OR IGNORE INTO standings
                (comp_id,season,club_id,stage,p,w,d,l,gf,ga,pts,form,pos)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (cidc, SEASON, teams[-1], stage, 1, 1, 0, 0, 0, 0, 3, "", 1))

    # continental league phase (8 matchdays, Swiss model)
    for ccode in ("UCL", "UEL", "UECL"):
        cidc = comp_by_code[ccode][0]
        teams = {"UCL": ucl_teams, "UEL": uel_teams, "UECL": uecl_teams}[ccode]
        rng4 = random.Random(_seed(ccode + "lg"))
        md_dates = [date(2026, 9, 15), date(2026, 9, 29), date(2026, 10, 20), date(2026, 11, 3),
                    date(2026, 11, 24), date(2026, 12, 8), date(2027, 1, 19), date(2027, 1, 26)]
        pool = teams[:]
        rng4.shuffle(pool)
        # each team plays 8 different opponents (4 home, 4 away) - approximate pairing
        played = {t: set() for t in teams}
        for md, d in enumerate(md_dates):
            order2 = teams[:]
            rng4.shuffle(order2)
            used = set()
            for t in order2:
                if t in used:
                    continue
                # find opponent
                opp = None
                cands = [x for x in order2 if x != t and x not in used and x not in played[t]]
                if not cands:
                    continue
                opp = cands[0]
                used.add(t); used.add(opp)
                played[t].add(opp); played[opp].add(t)
                if md % 2 == 0:
                    h, a = t, opp
                else:
                    h, a = opp, t
                fid += 1
                fixtures.append((fid, cidc, SEASON, md + 1, "league", d.isoformat(), h, a,
                                 None, None, 0, None, None, 1, None, None, None, None, None))
        con.executemany("INSERT INTO standings (comp_id,season,club_id,stage,p,w,d,l,gf,ga,pts,form,pos) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        [(cidc, SEASON, m, "league", 0, 0, 0, 0, 0, 0, 0, "", 0) for m in teams])

    # friendlies for pre-season (unique pairings, one per date per club)
    seen_pair = set()
    busy = {}
    for code in order:
        c = clubs[code]
        r = random.Random(_seed(code + "friend"))
        cands = [x for x in order if clubs[x]["id"] != c["id"] and
                 abs(clubs[x]["rep"] - c["rep"]) < 25 and clubs[x]["country"] == c["country"]]
        r.shuffle(cands)
        for k, d in enumerate([date(2026, 7, 11), date(2026, 7, 18), date(2026, 7, 25),
                               date(2026, 8, 1), date(2026, 8, 8)]):
            if busy.get((c["id"], d)):
                continue
            opp = None
            for o in cands:
                oid = clubs[o]["id"]
                key = tuple(sorted((c["id"], oid))) + (d,)
                if key in seen_pair or busy.get((oid, d)):
                    continue
                opp = oid
                seen_pair.add(key)
                break
            if opp is None:
                continue
            busy[(c["id"], d)] = True
            busy[(opp, d)] = True
            fid += 1
            h, a = (c["id"], opp) if k % 2 == 0 else (opp, c["id"])
            fixtures.append((fid, 0, SEASON, 0, "friendly", d.isoformat(), h, a,
                             None, None, 0, None, None, 1, None, None, None, None, None))
    con.executemany("""INSERT INTO fixtures (id,comp_id,season,round,stage,match_date,home_id,away_id,hg,aw,played,agg_h,agg_a,leg,venue,attendance,rating_h,rating_a,report) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", fixtures)
    con.execute("INSERT INTO meta VALUES ('built','1') ON CONFLICT(k) DO UPDATE SET v='1'")
    con.execute("INSERT INTO meta VALUES ('season_start',?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", (SEASON_START,))
    con.commit()
    con.close()
    return DB_PATH


def double_round_robin(teams, rng):
    """Circle method -> list of rounds of (home, away)."""
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
            if (i + r) % 2 == 0:
                rnd.append((a, b))
            else:
                rnd.append((b, a))
        rounds.append(rnd)
        t = [t[0]] + [t[-1]] + t[1:-1]
    second = [[(a, b) for (b, a) in rnd] for rnd in rounds]
    all_r = rounds + second
    rng.shuffle(all_r)
    return all_r


if __name__ == "__main__":
    import time
    t0 = time.time()
    p = build_world()
    con = connect()
    print("built", p, "in %.1fs" % (time.time() - t0))
    for q in ("SELECT COUNT(*) FROM clubs", "SELECT COUNT(*) FROM players",
              "SELECT COUNT(*) FROM staff", "SELECT COUNT(*) FROM fixtures",
              "SELECT COUNT(*) FROM competitions"):
        print(q, con.execute(q).fetchone()[0])
    con.close()
