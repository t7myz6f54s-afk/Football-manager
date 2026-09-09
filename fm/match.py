"""Match engine: squad rating, tactical model, and full 90-minute simulation.

Design rule: SIMULATE FIRST, NARRATE SECOND. Every match produces underlying
data (xG, shots, chances, ratings); the presentation layer only describes it.
"""
import json
import math
import random
from datetime import date

from . import constants as C
from .world import unpack_attrs

MENTALITY_SHIFT = {  # index from Balanced
    "Very Defensive": -2, "Defensive": -1, "Cautious": -0.5, "Balanced": 0,
    "Positive": 0.5, "Attacking": 1, "Very Attacking": 2,
}
LEVEL5 = {"Much Deeper": -2, "Deeper": -1, "Standard": 0, "Higher": 1, "Much Higher": 2,
          "Much Lower": -2, "Lower": -1, "Much Narrower": -2, "Narrower": -1,
          "Wider": 1, "Much Wider": 2, "Much Shorter": -2, "Shorter": -1,
          "More Direct": 1, "Much More Direct": 2, "Much Less": -2, "Less": -1,
          "More": 1, "Much More": 2, "Never": -2, "Rarely": -1, "Frequently": 1, "Always": 2}

ROLE_MODS = {
    # role: (attack_bias, defence_bias, width_bias, press_bias, risk)
    "Goalkeeper": (0, 0, 0, 0, 0),
    "Sweeper Keeper": (0.1, -0.05, 0, 0.1, 0.2),
    "Central Defender": (0, 0.1, 0, 0, 0),
    "Ball Playing Defender": (0.12, 0.02, 0.05, 0, 0.1),
    "Wide Centre-Back": (0.05, 0.05, 0.2, 0, 0.1),
    "Libero": (0.15, -0.05, 0, 0, 0.2),
    "Full Back": (0, 0.08, 0.1, 0, 0),
    "Wing Back": (0.18, -0.05, 0.35, 0.08, 0.1),
    "Inverted Full Back": (0.08, 0.05, -0.15, 0, 0.1),
    "Inverted Wing Back": (0.12, 0, -0.2, 0.05, 0.1),
    "Anchor": (-0.05, 0.2, -0.1, -0.05, -0.1),
    "Defensive Midfielder": (0, 0.15, 0, 0.05, 0),
    "Deep-Lying Playmaker": (0.12, 0.05, 0.05, -0.05, 0.05),
    "Ball-Winning Midfielder": (-0.05, 0.12, 0, 0.25, 0.05),
    "Roaming Playmaker": (0.1, 0, 0.05, 0.1, 0.1),
    "Segundo Volante": (0.2, 0.02, 0, 0.1, 0.1),
    "Central Midfielder": (0.05, 0.05, 0, 0.05, 0),
    "Box-to-Box": (0.1, 0.05, 0.05, 0.12, 0.05),
    "Mezzala": (0.18, -0.03, 0.18, 0.08, 0.1),
    "Advanced Playmaker": (0.25, -0.1, 0.05, 0, 0.15),
    "Attacking Midfielder": (0.2, -0.05, 0, 0.05, 0.1),
    "Shadow Striker": (0.3, -0.08, 0, 0.1, 0.15),
    "Trequartista": (0.3, -0.18, 0.05, -0.1, 0.2),
    "Enganche": (0.22, -0.2, 0, -0.1, 0.15),
    "Winger": (0.22, -0.05, 0.35, 0.1, 0.05),
    "Inside Forward": (0.3, -0.08, 0.1, 0.12, 0.1),
    "Inverted Winger": (0.25, -0.05, -0.05, 0.1, 0.1),
    "Wide Playmaker": (0.2, -0.08, 0.3, 0, 0.1),
    "Wide Target Forward": (0.25, -0.05, 0.3, 0.05, 0.05),
    "Advanced Forward": (0.32, -0.1, 0, 0.15, 0.1),
    "Pressing Forward": (0.25, -0.02, 0, 0.3, 0.05),
    "Complete Forward": (0.28, -0.02, 0.05, 0.18, 0.1),
    "Deep-Lying Forward": (0.18, 0.02, 0, 0.08, 0),
    "Target Forward": (0.22, 0, 0.05, 0.02, -0.05),
    "Poacher": (0.35, -0.15, 0, 0.05, 0.1),
    "False Nine": (0.2, -0.05, 0.1, 0.1, 0.1),
}
DUTY_MOD = {"Defend": (-0.08, 0.12, -0.05), "Cover": (-0.05, 0.1, 0),
            "Stopper": (0.02, 0.06, 0), "Support": (0, 0, 0), "Attack": (0.1, -0.1, 0.05)}

POS_WEIGHTS = {
    "GK":  {"gk_reflexes": 3, "gk_positioning": 3, "gk_handling": 2.4, "gk_one_on_ones": 2.2,
            "gk_aerial": 1.6, "concentration": 2, "composure": 1.6, "decisions": 1.4,
            "anticipation": 1.6, "strength": 1, "jumping": 1.2, "gk_distribution": 1.2,
            "gk_communication": 1.2, "gk_rushing_out": 1.4, "agility": 1.2},
    "DEF": {"tackling": 2.6, "marking": 2.6, "positioning": 2.6, "heading": 2.2, "strength": 2.2,
            "jumping": 2, "concentration": 2.2, "anticipation": 2, "aggression": 1.6,
            "bravery": 1.6, "decisions": 1.6, "composure": 1.2, "pace": 1.4, "acceleration": 1.2,
            "stamina": 1.4, "teamwork": 1.6, "work_rate": 1.4, "first_touch": 1, "passing": 1.2,
            "balance": 1.2, "determination": 1.4, "leadership": 1},
    "MID": {"passing": 2.6, "first_touch": 2.4, "technique": 2.2, "vision": 2.2, "decisions": 2.4,
            "composure": 2, "teamwork": 2.2, "work_rate": 2, "stamina": 2.2, "positioning": 2,
            "tackling": 1.8, "anticipation": 1.8, "concentration": 1.8, "off_the_ball": 1.6,
            "strength": 1.4, "agility": 1.4, "dribbling": 1.4, "long_shots": 1.4, "heading": 1,
            "determination": 1.4, "leadership": 1.2, "balance": 1.2, "pace": 1},
    "ATT": {"finishing": 3, "off_the_ball": 2.8, "composure": 2.6, "first_touch": 2.4,
            "technique": 2.2, "dribbling": 2, "pace": 2, "acceleration": 2, "agility": 2,
            "heading": 1.8, "anticipation": 2, "decisions": 1.8, "vision": 1.6, "passing": 1.4,
            "flair": 1.6, "balance": 1.6, "strength": 1.6, "stamina": 1.6, "work_rate": 1.2,
            "teamwork": 1.2, "crossing": 1.4, "long_shots": 1.4, "determination": 1.4},
}
POS_KEY = {"GK": "GK", "DC": "DEF", "DL": "DEF", "DR": "DEF", "DM": "MID",
           "MC": "MID", "AMC": "ATT", "AML": "ATT", "AMR": "ATT", "ST": "ATT"}

AREA_WEIGHT = {  # contribution of a player to attack/defence by pitch area
    "GK": (0.0, 0.9), "DC": (0.10, 1.05), "DL": (0.28, 0.80), "DR": (0.28, 0.80),
    "DM": (0.35, 0.95), "MC": (0.55, 0.75), "AMC": (0.85, 0.35),
    "AML": (0.95, 0.30), "AMR": (0.95, 0.30), "ST": (1.10, 0.18),
}


def player_condition(p):
    """0.55..1.12 multiplier from fitness/sharpness/fatigue/morale/form."""
    fit = (p["fitness"] - 88.0) / 22.0          # ~-1 .. +0.55
    sharp = (p["sharpness"] - 62.0) / 55.0        # ~-1 .. +0.7
    fat = p["fatigue"] / 100.0
    mor = (p["morale"] - 55.0) / 55.0
    frm = max(-2.5, min(2.5, p["form"])) / 2.5
    m = 1.0 + 0.07 * fit + 0.11 * sharp - 0.14 * fat + 0.06 * mor + 0.07 * frm
    return max(0.78, min(1.12, m))


def position_fit(p, slot):
    pos = p["pos"]
    if pos == slot:
        return 1.0
    if p.get("pos2") == slot:
        return 0.90
    fam = C.POS_GROUPS.get(slot, [])
    if pos in fam:
        return 0.80
    if slot in C.POS_GROUPS.get(pos, []):
        return 0.78
    same_line = C.LINES.get(pos) == C.LINES.get(slot)
    return 0.62 if same_line else 0.45


def player_match_quality(p, slot, role, duty, familiarity, cond_cache=None):
    """Effective 1-20 quality of a player in a specific tactical slot."""
    vec = p["_vec"]
    w = POS_WEIGHTS[POS_KEY[slot]]
    num = 0.0
    den = 0.0
    for k, wt in w.items():
        num += vec.get(k, 5) * wt
        den += wt
    base = num / max(den, 0.001)
    # secondary attributes matter a little
    sec = (p["ca"] - base) * 0.18
    base = base + sec
    cond = cond_cache or player_condition(p)
    fit = position_fit(p, slot)
    fam = 0.82 + 0.18 * min(1.0, familiarity / 100.0)
    rm = ROLE_MODS.get(role, (0, 0, 0, 0, 0))
    dm = DUTY_MOD.get(duty, (0, 0, 0))
    q = base * cond * fit * fam
    q *= 1.0 + 0.02 * (rm[0] + dm[0])
    return q


def team_rating(xi, tactics, opposition=None):
    """Compute team-level attacking/defensive/possession/pressing metrics.

    xi: list of dicts {player, slot, role, duty}
    tactics: dict(formation, mentality, instr, familiarity)
    """
    fam = tactics.get("familiarity", 60.0)
    instr = tactics.get("instr", dict(C.INSTR_DEFAULT))
    ment = tactics.get("mentality", "Balanced")
    mshift = MENTALITY_SHIFT.get(ment, 0)

    att = 0.0
    dfn = 0.0
    wk = 0.0
    atk_w = 0.0
    dfn_w = 0.0
    pace_sum = 0.0
    tech_sum = 0.0
    phys_sum = 0.0
    height_sum = 0.0
    setpiece_best = 0.0
    gk_q = 8.0
    conds = []
    for it in xi:
        p = it["player"]
        slot = it["slot"]
        cond = player_condition(p)
        conds.append(cond)
        q = player_match_quality(p, slot, it["role"], it["duty"], fam, cond)
        aw, dw = AREA_WEIGHT[slot]
        att += q * aw
        atk_w += aw
        dfn += q * dw
        dfn_w += dw
        v = p["_vec"]
        pace_sum += (v.get("pace", 8) + v.get("acceleration", 8)) / 2
        tech_sum += (v.get("technique", 8) + v.get("first_touch", 8) + v.get("passing", 8)) / 3
        phys_sum += (v.get("strength", 8) + v.get("stamina", 8)) / 2
        height_sum += p.get("height", 180)
        setpiece_best = max(setpiece_best, v.get("set_pieces", 5) * cond)
        if slot == "GK":
            gk_q = q
        wk += q
    n = max(1, len(xi))
    attack = att / max(atk_w, 0.001)
    defence = dfn / max(dfn_w, 0.001)
    overall = wk / n

    # instruction / mentality effects
    loe = LEVEL5.get(instr.get("line_of_engagement", "Standard"), 0)
    dl = LEVEL5.get(instr.get("defensive_line", "Standard"), 0)
    tempo = LEVEL5.get(instr.get("tempo", "Standard"), 0)
    direct = LEVEL5.get(instr.get("passing_directness", "Standard"), 0)
    width = LEVEL5.get(instr.get("width", "Standard"), 0)
    press = LEVEL5.get(instr.get("pressing_intensity", "Standard"), 0)

    attack *= 1 + 0.035 * mshift + 0.02 * loe + 0.012 * tempo - 0.012 * abs(direct)
    defence *= 1 - 0.030 * mshift - 0.018 * loe - 0.022 * dl + 0.010 * press
    # pressing gains defence but costs stamina
    press_level = 0.5 + 0.14 * (press + mshift * 0.6 + loe * 0.5)
    possession_bias = 0.5 * (tech_sum / n - 11.0) / 6.0 - 0.05 * direct + 0.03 * mshift * -1
    width_level = 0.5 + 0.10 * width
    # formation width
    n_wide = sum(1 for it in xi if it["slot"] in ("AML", "AMR", "DL", "DR"))
    width_level += 0.05 * (n_wide - 2)
    tempo_level = 0.5 + 0.09 * tempo + 0.03 * mshift + (pace_sum / n - 13.5) / 90.0
    height = height_sum / n
    fitness_avg = sum(p["player"]["fitness"] for p in xi) / n
    fatigue_avg = sum(p["player"]["fatigue"] for p in xi) / n
    morale_avg = sum(p["player"]["morale"] for p in xi) / n

    return dict(
        attack=max(1.0, attack), defence=max(1.0, defence), overall=overall,
        gk=max(4.0, gk_q), press=max(0.05, min(1.6, press_level)),
        possession=max(-1.2, min(1.2, possession_bias)),
        width=max(0.1, min(1.2, width_level)),
        tempo=max(0.1, min(1.6, tempo_level)),
        height=height, setpiece=max(3.0, setpiece_best),
        fitness=fitness_avg, fatigue=fatigue_avg, morale=morale_avg,
        condition=sum(conds) / max(1, len(conds)),
        mentality=ment, mshift=mshift, line=dl, loe=loe, direct=direct,
        familiar=fam, n=len(xi),
    )


def build_lineup(club_players, tactics, n=11, prefer=None, exclude=None):
    """Pick a best XI for formation slots, respecting fitness/availability."""
    formation = C.FORMATIONS.get(tactics.get("formation", "4-3-3 DM Wide"))
    if formation is None:
        formation = C.FORMATIONS["4-3-3 DM Wide"]
    roles = tactics.get("roles", {})
    exclude = exclude or set()
    avail = [p for p in club_players
             if p["id"] not in exclude and p["condition"] == "fit" and p["suspended"] <= 0
             and p["squad"] in ("First Team", "Reserve")]
    used = set()
    xi = []
    for i, slot in enumerate(formation):
        best = None
        best_q = -1
        for p in avail:
            if p["id"] in used:
                continue
            role, duty = roles.get(str(i), (C.ROLES.get(p["pos"], ["Central Midfielder"])[0],
                                            C.DUTIES.get(p["pos"], ["Support"])[0]))
            if role not in C.ROLES.get(slot, [role]):
                role = C.ROLES.get(slot, ["Central Midfielder"])[0]
            duty = duty if duty in C.DUTIES.get(slot, ["Support"]) else "Support"
            cond = player_condition(p)
            q = player_match_quality(p, slot, role, duty, tactics.get("familiarity", 60), cond)
            # small bonus for declared preference
            if prefer and p["id"] in prefer:
                q *= 1.02
            if q > best_q:
                best_q = q
                best = (p, slot, role, duty)
        if best is None:
            # nobody left: pull from youth
            rest = [p for p in club_players if p["id"] not in used and p["condition"] == "fit"]
            if not rest:
                break
            p = max(rest, key=lambda x: x["ca"])
            role = C.ROLES.get(slot, ["Central Midfielder"])[0]
            duty = C.DUTIES.get(slot, ["Support"])[0]
            best = (p, slot, role, duty)
        used.add(best[0]["id"])
        xi.append(dict(player=best[0], slot=best[1], role=best[2], duty=best[3]))
    bench = [p for p in sorted(avail, key=lambda x: -x["ca"]) if p["id"] not in used][:9]
    return xi, bench


# --------------------------------------------------------------- match engine
def _chance_type(rng, tr, opp, zone):
    """Return (label, base xG, n_shots_weight)."""
    r = rng.random()
    sp = tr["setpiece"] / max(opp["setpiece"], 1)
    if zone == "box":
        if r < 0.16:
            return "big chance", 0.42
        if r < 0.42:
            return "clear chance", 0.18
        if r < 0.62:
            return "header from a cross", 0.10
        if r < 0.72 and sp > 0.95:
            return "set piece", 0.11
        return "shot from inside the box", 0.09
    if zone == "edge":
        if r < 0.10:
            return "big chance", 0.33
        if r < 0.35:
            return "shot from the edge of the area", 0.055
        if r < 0.5:
            return "cut-back", 0.11
        return "long shot", 0.035
    # distance
    if r < 0.14:
        return "set piece", 0.08
    if r < 0.4:
        return "long shot", 0.032
    return "speculative effort", 0.022

class MatchRunner:
    """Stateful match simulation.

    A match can be paused at half-time so the human manager can give a team talk
    and make substitutions before the second half is played out.
    """

    def __init__(self, home, away, rng=None, seed=None, home_adv=True, weather=None,
                 referee=None, competition="league", neutral=False, leg=1,
                 agg=None, extra_time_allowed=True, pens_allowed=True):
        """home/away = dict(name, xi, bench, rating, human)."""
        self.home = home
        self.away = away
        self.neutral = neutral
        self.leg = leg
        self.agg = agg
        self.competition = competition
        self.extra_time_allowed = extra_time_allowed
        self.pens_allowed = pens_allowed
        self.rng = rng if rng is not None else random.Random(seed)
        # copy self.ratings: the engine mutates fatigue/state during the match
        self.H = dict(home["rating"])
        self.A = dict(away["rating"])
        self.H["fatigue"] = home["rating"].get("fatigue", 0.0)
        self.A["fatigue"] = away["rating"].get("fatigue", 0.0)
        self.my_side = "H" if home.get("human") else ("A" if away.get("human") else "H")
        self.events = []
        self.stats = {
            "home": dict(shots=0, sot=0, xg=0.0, big=0, poss=0, passes=0, pass_acc=0.0,
                         tackles=0, interceptions=0, fouls=0, corners=0, offsides=0,
                         yellow=0, red=0, saves=0, errors=0, progressive=0, duel=0),
            "away": dict(shots=0, sot=0, xg=0.0, big=0, poss=0, passes=0, pass_acc=0.0,
                         tackles=0, interceptions=0, fouls=0, corners=0, offsides=0,
                         yellow=0, red=0, saves=0, errors=0, progressive=0, duel=0),
        }
        self.adv = 1.10 if (home_adv and not neutral) else 1.0
        self.ref = referee or {"strictness": 1.0, "cards": 1.0, "name": "Referee"}
        self.weather = weather or {"desc": "clear", "tempo": 1.0, "tech": 1.0}

        # possession split
        poss_bias = (self.H["possession"] * self.H["overall"] - self.A["possession"] * self.A["overall"]) / 22.0
        self.poss_home = 0.5 + poss_bias * 0.09 + (0.018 if self.adv > 1 else 0)
        self.poss_home = max(0.28, min(0.72, self.poss_home))

        # base chance rates
        self.rate_h = self.chance_rate("H")
        self.rate_a = self.chance_rate("A")
        total_min = 90
        # fatigue decay
        self.fat_h = list(player_condition(p["player"]) for p in home["xi"])
        self.fat_a = list(player_condition(p["player"]) for p in away["xi"])

        self.goals = {"H": 0, "A": 0}
        self.reds = {"H": 0, "A": 0}
        self.subs = {"H": [], "A": []}
        self.active = {"H": [True] * len(home["xi"]), "A": [True] * len(away["xi"])}
        self.injured_out = {"H": set(), "A": set()}
        self.ratings = {"H": [6.4] * len(home["xi"]), "A": [6.4] * len(away["xi"])}
        self.shots_p = {"H": [0] * len(home["xi"]), "A": [0] * len(away["xi"])}
        self.goals_p = {"H": [0] * len(home["xi"]), "A": [0] * len(away["xi"])}
        self.assists_p = {"H": [0] * len(home["xi"]), "A": [0] * len(away["xi"])}
        self.mins_p = {"H": [0] * len(home["xi"]), "A": [0] * len(away["xi"])}
        self.xg_p = {"H": [0.0] * len(home["xi"]), "A": [0.0] * len(away["xi"])}

        # AI substitutions
        self.minute = 1
        self.half = 1
        self.started = False
        self.finished = False
        self.halftime_applied = False

    def side_stats(self, side):
            return self.stats["home" if side == "H" else "away"]

    def rating_of(self, side):
            return self.H if side == "H" else self.A

    def opp_of(self, side):
            return self.A if side == "H" else self.H

    def xi_of(self, side):
            return self.home["xi"] if side == "H" else self.away["xi"]

    def chance_rate(self, side):
            tr = self.rating_of(side)
            op = self.opp_of(side)
            r = (tr["attack"] / max(op["defence"], 1)) ** 0.85
            r *= 0.285 + 0.050 * tr["tempo"] + 0.032 * tr["mshift"]
            r *= 1.0 + 0.12 * (tr["condition"] - 1.0)
            r *= self.weather["tempo"]
            if side == "H":
                r *= self.adv * 1.04
            return max(0.03, r)

    def state_adjust(self, minute):
            """Game-state driven tactical drift (both sides)."""
            gh, ga = self.goals["H"], self.goals["A"]
            adj = {"H": 0.0, "A": 0.0}
            late = minute >= 70
            for side, mine, theirs in (("H", gh, ga), ("A", ga, gh)):
                tr = self.rating_of(side)
                diff = mine - theirs
                push = 0.0
                if diff < 0:
                    push = 0.10 * min(3, -diff) * (1.6 if late else 1.0)
                elif diff > 0:
                    push = -0.07 * min(2, diff) * (1.5 if late else 0.7)
                if late and diff == 0:
                    push += 0.02 if side == "H" else 0.0
                adj[side] = push
            return adj

    def do_attack(self, side, minute):
            tr = self.rating_of(side)
            op = self.opp_of(side)
            st = self.side_stats(side)
            # pressing duel: does the attack progress?
            pr = tr["press"] if side == "H" else op["press"]
            progress_chance = (0.58 + 0.020 * (tr["attack"] - op["defence"])
                               - 0.045 * (op["press"] - 0.6))
            progress_chance = max(0.30, min(0.82, progress_chance))
            if self.rng.random() > progress_chance:
                # turnover
                ost = self.side_stats("A" if side == "H" else "H")
                ost["tackles"] += 1
                if self.rng.random() < 0.35:
                    ost["interceptions"] += 1
                if self.rng.random() < 0.05:
                    st["errors"] += 1
                    self.events.append(dict(minute=minute, side=side, type="error",
                                       text="A sloppy pass is intercepted in a dangerous area."))
                return
            st["progressive"] += 1
            st["passes"] += self.rng.randint(3, 9)
            # zone reached
            zr = self.rng.random()
            width_bonus = 0.12 * (tr["width"] - 0.5)
            if zr < 0.34 + width_bonus:
                zone = "box"
            elif zr < 0.72:
                zone = "edge"
            else:
                zone = "distance"
            # shot or recycle
            shoot_p = {"box": 0.80, "edge": 0.45, "distance": 0.18}[zone]
            shoot_p *= 1 + 0.08 * tr["mshift"] + 0.05 * (tr["tempo"] - 0.5)
            if self.rng.random() > shoot_p:
                if zone != "distance" and self.rng.random() < 0.3:
                    st["corners"] += 1
                    self.events.append(dict(minute=minute, side=side, type="corner",
                                       text="A corner is won."))
                    # corner chance
                    if self.rng.random() < 0.10 * (tr["height"] / 182.0):
                        self.resolve_shot(side, minute, "header from a corner", 0.09, setpiece=True)
                return
            label, xg = _chance_type(self.rng, tr, op, zone)
            self.resolve_shot(side, minute, label, xg)

    def resolve_shot(self, side, minute, label, xg, setpiece=False):
            tr = self.rating_of(side)
            op = self.opp_of(side)
            st = self.side_stats(side)
            ost = self.side_stats("A" if side == "H" else "H")
            # choose shooter
            xi = self.xi_of(side)
            cands = [i for i in range(len(xi)) if self.active[side][i] and i not in self.injured_out[side]]
            if not cands:
                return
            weights = []
            for i in cands:
                it = xi[i]
                aw, _ = AREA_WEIGHT[it["slot"]]
                v = it["player"]["_vec"]
                w = (0.25 + aw) * (0.5 + v.get("finishing", 5) / 22.0) * (1.4 if setpiece and
                    v.get("heading", 5) > 13 else 1.0)
                if it["slot"] == "GK":
                    w *= 0.02
                weights.append(max(0.01, w))
            i = self.rng.choices(cands, weights=weights, k=1)[0]
            shooter = xi[i]["player"]
            xg *= (0.85 + 0.3 * player_condition(shooter))
            xg *= self.weather["tech"]
            xg = max(0.008, min(0.85, xg))
            st["shots"] += 1
            st["xg"] += xg
            self.shots_p[side][i] += 1
            self.xg_p[side][i] += xg
            if xg >= 0.30:
                st["big"] += 1
            # on target?
            vec = shooter["_vec"]
            acc = (vec.get("finishing", 6) * 0.5 + vec.get("composure", 6) * 0.3 +
                   vec.get("technique", 6) * 0.2) / 20.0
            on_target_p = 0.30 + 0.30 * acc - 0.06 * (1.2 - op["gk"] / 14.0)
            on_target_p = max(0.12, min(0.80, on_target_p))
            on_target = self.rng.random() < on_target_p
            blocked = False
            if not on_target:
                blocked = self.rng.random() < 0.42
            if on_target:
                ost["saves"] += 1
            # goal?
            gk = op["gk"]
            save_factor = max(0.72, min(1.32, 1.0 + (gk - 11.0) * 0.048))
            goal_p = xg / save_factor
            goal_p *= (0.9 + 0.2 * player_condition(shooter))
            scored = self.rng.random() < goal_p
            ev = dict(minute=minute, side=side, type="shot", label=label, xg=round(xg, 3),
                      player=shooter["name"], pid=shooter["id"],
                      outcome="goal" if scored else ("on target" if on_target else
                                                     ("blocked" if blocked else "off target")))
            if scored:
                self.goals[side] += 1
                self.goals_p[side][i] += 1
                ev["type"] = "goal"
                ev["text"] = f"GOAL — {shooter['name']} ({label}, xG {xg:.2f})"
                self.ratings[side][i] += 1.0 + xg * 0.9
                # assist
                acands = [j for j in cands if j != i and self.active[side][j]]
                if acands and self.rng.random() < 0.78:
                    aw2 = []
                    for j in acands:
                        it = xi[j]
                        v = it["player"]["_vec"]
                        aw2.append(max(0.02, (AREA_WEIGHT[it["slot"]][0] + 0.3) *
                                       (0.4 + v.get("passing", 6) / 24.0) *
                                       (1.5 if it["slot"] in ("AML", "AMR", "AMC") else 1.0)))
                    j = self.rng.choices(acands, weights=aw2, k=1)[0]
                    self.assists_p[side][j] += 1
                    self.ratings[side][j] += 0.55
                    ev["assist"] = xi[j]["player"]["name"]
                    ev["assist_id"] = xi[j]["player"]["id"]
                op_side = "A" if side == "H" else "H"
                # defensive blame
                dcands = [k for k in range(len(self.xi_of(op_side)))
                          if self.active[op_side][k] and self.xi_of(op_side)[k]["slot"] in ("DC", "DM", "GK", "DL", "DR")]
                if dcands:
                    k = self.rng.choice(dcands)
                    self.ratings[op_side][k] -= 0.30
            else:
                self.ratings[side][i] += 0.10 if on_target else -0.06
            self.events.append(ev)

    def maybe_card(self, side, minute):
            tr = self.rating_of(side)
            st = self.side_stats(side)
            xi = self.xi_of(side)
            cands = [i for i in range(len(xi)) if self.active[side][i] and xi[i]["slot"] != "GK"]
            if not cands:
                return
            i = self.rng.choices(cands, weights=[(0.4 + xi[j]["player"]["_vec"].get("aggression", 8) / 14.0)
                                            for j in cands], k=1)[0]
            p = xi[i]["player"]
            yellow_p = 0.16 * self.ref["cards"] * (0.6 + tr["press"] * 0.5)
            if self.rng.random() < yellow_p:
                st["yellow"] += 1
                p["_yellow"] = p.get("_yellow", 0) + 1
                self.ratings[side][i] -= 0.18
                ev = dict(minute=minute, side=side, type="yellow", player=p["name"], pid=p["id"],
                          text=f"Yellow card — {p['name']}")
                if p["_yellow"] >= 2:
                    ev = dict(minute=minute, side=side, type="red", player=p["name"], pid=p["id"],
                              reason="second yellow",
                              text=f"SENT OFF — {p['name']} (second yellow card)")
                    st["red"] += 1
                    st["yellow"] -= 1
                    self.active[side][i] = False
                    self.reds[side] += 1
                self.events.append(ev)
            elif self.rng.random() < 0.008 * self.ref["cards"]:
                st["red"] += 1
                self.active[side][i] = False
                self.reds[side] += 1
                self.events.append(dict(minute=minute, side=side, type="red", player=p["name"], pid=p["id"],
                                   reason="straight red",
                                   text=f"SENT OFF — {p['name']} (straight red card)"))

    def maybe_injury(self, side, minute):
            tr = self.rating_of(side)
            xi = self.xi_of(side)
            cands = [i for i in range(len(xi)) if self.active[side][i]]
            if not cands:
                return
            i = self.rng.choice(cands)
            p = xi[i]["player"]
            base = 0.0035
            base *= 1 + max(0.0, (tr["fatigue"] - 15) / 45.0)
            base *= 1 + p.get("injury_prone", 5) / 22.0
            base *= 0.7 + 0.6 * tr["press"]
            if minute > 75:
                base *= 1.35
            if self.rng.random() < base:
                self.active[side][i] = False
                self.injured_out[side].add(i)
                ev = dict(minute=minute, side=side, type="injury", player=p["name"], pid=p["id"],
                          text=f"{p['name']} goes down injured and cannot continue.")
                self.events.append(ev)

    def ai_sub(self, side, minute):
            tr = self.rating_of(side)
            bench = self.home.get("bench") if side == "H" else self.away.get("bench")
            if not bench:
                return
            xi = self.xi_of(side)
            came_on = {t[1] for t in self.subs[side]}
            cands = [i for i in range(len(xi))
                     if self.active[side][i] and xi[i]["slot"] != "GK"
                     and i < len(self.mins_p[side]) and self.mins_p[side][i] >= 15
                     and xi[i]["player"]["id"] not in came_on]
            if not cands:
                return
            # replace the most tired / worst performing
            scores = []
            for i in cands:
                p = xi[i]["player"]
                scores.append((player_condition(p) * 0.6 + self.ratings[side][i] / 12.0, i))
            scores.sort()
            i = scores[0][1]
            slot = xi[i]["slot"]
            rep = None
            for b in bench:
                if b["id"] in {x["player"]["id"] for x in xi}:
                    continue
                if b["pos"] == slot or slot in C.POS_GROUPS.get(b["pos"], []):
                    rep = b
                    break
            if rep is None:
                rep = bench[0]
            bench.remove(rep)
            newi = len(xi)
            xi.append(dict(player=rep, slot=slot, role=xi[i]["role"], duty=xi[i]["duty"]))
            self.active[side].append(True)
            self.ratings[side].append(6.2)
            self.shots_p[side].append(0); self.goals_p[side].append(0); self.assists_p[side].append(0)
            self.mins_p[side].append(0); self.xg_p[side].append(0.0)
            self.events.append(dict(minute=minute, side=side, type="sub", player=rep["name"], pid=rep["id"],
                               off=xi[i]["player"]["name"], off_id=xi[i]["player"]["id"],
                               text=f"Substitution — {rep['name']} replaces {xi[i]['player']['name']}"))
            self.active[side][i] = False
            self.subs[side].append((xi[i]["player"]["id"], rep["id"], minute))

    def manual_sub(self, side, minute, off_id, on_id):
            """Manager-chosen substitution. Returns True if it was made."""
            xi = self.xi_of(side)
            bench = self.home.get("bench") if side == "H" else self.away.get("bench")
            if not bench or len(self.subs[side]) >= 5:
                return False
            rep = next((b for b in bench if b["id"] == on_id), None)
            if rep is None:
                return False
            idx = next((i for i in range(len(xi))
                        if self.active[side][i] and xi[i]["player"]["id"] == off_id), None)
            if idx is None:
                return False
            bench.remove(rep)
            slot = xi[idx]["slot"]
            xi.append(dict(player=rep, slot=slot, role=xi[idx]["role"], duty=xi[idx]["duty"]))
            self.active[side].append(True)
            self.ratings[side].append(6.2)
            self.shots_p[side].append(0); self.goals_p[side].append(0); self.assists_p[side].append(0)
            self.mins_p[side].append(0); self.xg_p[side].append(0.0)
            self.events.append(dict(minute=minute, side=side, type="sub", player=rep["name"], pid=rep["id"],
                               off=xi[idx]["player"]["name"], off_id=off_id,
                               text=f"Substitution — {rep['name']} replaces {xi[idx]['player']['name']}"))
            self.active[side][idx] = False
            self.subs[side].append((off_id, on_id, minute))
            return True

    def apply_talk(self, side, talk):
            """Halftime team talk: morale swing + small tactical shift."""
            tr = self.rating_of(side)
            gm = (self.goals[side] - self.goals["A" if side == "H" else "H"])
            eff = {"praise": 0.030, "encourage": 0.038, "neutral": 0.0,
                   "firm": 0.050, "aggressive": 0.062, "defensive": -0.030,
                   "attacking": 0.030}.get(talk, 0.0)
            if talk == "defensive":
                tr["mshift"] = max(-2, tr["mshift"] - 1); tr["press"] = max(0.2, tr["press"] - 0.12)
            elif talk == "attacking":
                tr["mshift"] = min(2, tr["mshift"] + 1); tr["tempo"] = min(1.0, tr["tempo"] + 0.10)
            elif talk == "aggressive":
                tr["press"] = min(1.0, tr["press"] + 0.14)
            if gm < 0 and talk in ("firm", "aggressive", "encourage"):
                eff += 0.020
            if gm > 0 and talk == "praise":
                eff += 0.012
            tr["attack"] *= (1 + eff)
            tr["defence"] *= (1 + eff * 0.55)
            for side_key in (side,):
                for i in range(len(self.xi_of(side_key))):
                    if self.active[side_key][i]:
                        p = self.xi_of(side_key)[i]["player"]
                        p["morale"] = max(1, min(100, p.get("morale", 60) + (6 if eff > 0 else -2)))
            self.events.append(dict(minute=45, side=side, type="team_talk", talk=talk,
                               text=f"Half-time team talk: {talk}."))

    # ---------------------------------------------------------- run control
    def start(self):
        """Kick-off: fix stoppage time and log the opening event."""
        if self.started:
            return
        self.started = True
        self.stoppage = {1: self.rng.randint(0, 3), 2: self.rng.randint(1, 6)}
        self.max_min = 90 + self.stoppage[1] + self.stoppage[2]
        self.minute = 1
        self.events.append(dict(
            minute=0, side="H", type="kickoff",
            text="Kick-off. %s, referee %s (strictness %.1f)." % (
                self.weather["desc"].capitalize(), self.ref["name"], self.ref["strictness"])))

    def _play_minute(self):
        """One minute of football: possession, attacks, fouls, injuries and AI subs."""
        adj = self.state_adjust(self.minute)
        # possession for this self.minute
        ph = self.poss_home + adj["H"] * 0.05 - adj["A"] * 0.05
        ph *= (1 - 0.10 * self.reds["H"]) if self.reds["H"] else 1
        if self.reds["A"]:
            ph *= 1.08
        ph = max(0.15, min(0.85, ph))
        side_has = "H" if self.rng.random() < ph else "A"
        self.side_stats(side_has)["poss"] += 1
        self.side_stats("A" if side_has == "H" else "H")["poss"] += 0
        # fatigue drift
        for side in ("H", "A"):
            tr = self.rating_of(side)
            tr["fatigue"] += 0.30 + 0.06 * tr["press"] + (0.05 if tr["tempo"] > 0.6 else 0)
            if self.minute > 75:
                tr["fatigue"] += 0.10
        # attacks
        r_h = self.rate_h * (1 + adj["H"]) * (1 - 0.08 * self.reds["H"]) * (1 + 0.05 * self.reds["A"])
        r_a = self.rate_a * (1 + adj["A"]) * (1 - 0.08 * self.reds["A"]) * (1 + 0.05 * self.reds["H"])
        fat_h_mod = 1 - max(0, (self.H["fatigue"] - 34) / 320.0)
        fat_a_mod = 1 - max(0, (self.A["fatigue"] - 34) / 320.0)
        if self.rng.random() < min(0.62, r_h * fat_h_mod):
            self.do_attack("H", self.minute)
        if self.rng.random() < min(0.62, r_a * fat_a_mod):
            self.do_attack("A", self.minute)
        # fouls
        for side in ("H", "A"):
            if self.rng.random() < 0.13 * self.rating_of("A" if side == "H" else "H")["press"] * self.ref["strictness"]:
                self.side_stats(side)["fouls"] += 1
                if self.rng.random() < 0.20:
                    self.maybe_card(side, self.minute)
        # injuries
        if self.rng.random() < 0.012:
            self.maybe_injury(self.rng.choice(["H", "A"]), self.minute)
        # minutes played accumulation
        for side in ("H", "A"):
            for i in range(len(self.xi_of(side))):
                if self.active[side][i]:
                    self.mins_p[side][i] += 1
        # AI self.subs
        for side, gm in (("H", self.goals["H"] - self.goals["A"]), ("A", self.goals["A"] - self.goals["H"])):
            n_subs = len(self.subs[side])
            if n_subs < 5:
                trig = (self.minute in (58, 68, 78) and n_subs < 2) or \
                       (self.minute >= 62 and gm < 0 and n_subs < 3 and self.minute % 7 == 0) or \
                       (self.minute >= 75 and n_subs < 5 and self.rng.random() < 0.15) or \
                       (len(self.injured_out[side]) > 0 and n_subs < len(self.injured_out[side]) + 1)
                if trig and (self.home.get("bench") if side == "H" else self.away.get("bench")):
                    self.ai_sub(side, self.minute)
        # self.ratings drift from possession/game state

    def run_first_half(self):
        """Play up to and including first-half stoppage time."""
        self.start()
        while self.minute <= 45 + self.stoppage[1]:
            self._play_minute()
            self.minute += 1

    def halftime_state(self):
        """Snapshot of the match at the break, for the manager's decisions."""
        side = self.my_side
        bench = (self.home.get("bench") if side == "H" else self.away.get("bench")) or []
        return dict(
            minute=45, goals_home=self.goals["H"], goals_away=self.goals["A"],
            stats={k: dict(v) for k, v in self.stats.items()},
            events=list(self.events),
            my_xi=[{"pid": x["player"]["id"], "name": x["player"]["name"],
                    "pos": x["slot"], "rating": round(self.ratings[side][i], 2),
                    "fatigue": round(x["player"].get("fatigue", 0), 1)}
                   for i, x in enumerate(self.xi_of(side)) if self.active[side][i]],
            my_bench=[{"pid": b["id"], "name": b["name"], "pos": b["pos"],
                        "ca": round(b.get("ca", 8), 1)} for b in bench],
        )

    def apply_halftime(self, instr=None):
        """Log half-time, then apply the manager talk and up to three substitutions."""
        if self.halftime_applied:
            return 0
        self.halftime_applied = True
        self.events.append(dict(
            minute=45, side="H", type="halftime",
            text="Half-time: %s %d - %d %s" % (self.home["name"], self.goals["H"],
                                                self.goals["A"], self.away["name"])))
        instr = instr or {}
        if instr.get("talk"):
            self.apply_talk(self.my_side, instr["talk"])
        done = 0
        for pair in (instr.get("subs") or []):
            if done >= 3:
                break
            try:
                off_id, on_id = int(pair[0]), int(pair[1])
            except Exception:
                continue
            if self.manual_sub(self.my_side, 46, off_id, on_id):
                done += 1
        return done

    def run_second_half(self):
        self.apply_halftime()
        self.half = 2
        if self.minute < 46:
            self.minute = 46
        while self.minute <= self.max_min:
            self._play_minute()
            self.minute += 1

    def run(self, halftime_instr=None, halftime_hook=None):
        """Play the whole match. halftime_hook(state) may return {"talk", "subs"}."""
        self.run_first_half()
        instr = halftime_instr
        if instr is None and halftime_hook is not None:
            try:
                instr = halftime_hook(self.halftime_state()) or {}
            except Exception:
                instr = {}
        self.apply_halftime(instr)
        self.run_second_half()
        return self.finalize()

    def finalize(self):
        """Finalise ratings, then extra time and penalties if the tie needs a winner."""
        # finalise self.ratings
        for side in ("H", "A"):
            xi = self.xi_of(side)
            st = self.side_stats(side)
            opp_st = self.stats["away" if side == "H" else "home"]
            team_perf = 0.5 + 0.22 * (st["xg"] - opp_st["xg"])
            for i in range(len(xi)):
                if not self.active[side][i] and i in self.injured_out[side]:
                    self.ratings[side][i] -= 0.1
                base = 6.35 + team_perf * 0.55
                base += 0.30 * (self.shots_p[side][i] * 0.12 + self.goals_p[side][i] * 0.9 +
                                self.assists_p[side][i] * 0.55 + self.xg_p[side][i] * 0.5)
                if xi[i]["slot"] in ("DC", "DM", "GK", "DL", "DR"):
                    cs = 1 if (self.goals["A" if side == "H" else "H"] == 0) else 0
                    base += 0.42 * cs
                    base -= 0.16 * self.goals["A" if side == "H" else "H"]
                base += self.rng.gauss(0, 0.28)
                base *= (0.94 + 0.12 * min(1.0, self.mins_p[side][i] / 90.0))
                self.ratings[side][i] = round(max(3.5, min(10.0, base + (self.ratings[side][i] - 6.4) * 0.55)), 2)

        # extra time / penalties if required
        et = None
        pens = None
        need_winner = self.competition in ("cup", "continental_ko") and self.extra_time_allowed
        if need_winner and self.goals["H"] == self.goals["A"]:
            total_a = (self.agg or (0, 0))
            if self.agg is not None:
                th = self.goals["H"] + total_a[0]
                ta = self.goals["A"] + total_a[1]
                if th != ta:
                    need_winner = False
            if need_winner:
                et = _extra_time(self.home, self.away, self.rng, self.goals, self.stats,
                                 self.events, self.rating_of, self.side_stats, self.xi_of,
                                 self.active, self.ratings, self.mins_p, self.injured_out,
                                 self.subs, self.reds)
                if self.goals["H"] == self.goals["A"] and self.pens_allowed:
                    pens = _penalties(self.home, self.away, self.rng, self.events)
        self.events.sort(key=lambda e: e["minute"])
        poss_total = self.stats["home"]["poss"] + self.stats["away"]["poss"]
        poss_pct = round(100 * self.stats["home"]["poss"] / poss_total) if poss_total else 50
        self.extra_time = et
        self.pens = pens
        self.poss_pct = poss_pct
        return self.result()

    def result(self):
        """Full match data, in the shape the rest of the game expects."""
        _res = dict(
            home_goals=self.goals["H"], away_goals=self.goals["A"], events=self.events, stats=self.stats,
            possession_home=self.poss_pct, possession_away=100 - self.poss_pct,
            ratings_home=self.ratings["H"], ratings_away=self.ratings["A"],
            mins_home=self.mins_p["H"], mins_away=self.mins_p["A"],
            goals_home=self.goals_p["H"], goals_away=self.goals_p["A"],
            assists_home=self.assists_p["H"], assists_away=self.assists_p["A"],
            shots_home=self.shots_p["H"], shots_away=self.shots_p["A"],
            xg_home=self.xg_p["H"], xg_away=self.xg_p["A"],
            xi_home=[dict(pid=x["player"]["id"], name=x["player"]["name"], slot=x["slot"],
                          role=x["role"], duty=x["duty"]) for x in self.home["xi"]],
            xi_away=[dict(pid=x["player"]["id"], name=x["player"]["name"], slot=x["slot"],
                          role=x["role"], duty=x["duty"]) for x in self.away["xi"]],
            subs_home=self.subs["H"], subs_away=self.subs["A"],
            injuries_home=[self.home["xi"][i]["player"]["id"] for i in self.injured_out["H"]],
            injuries_away=[self.away["xi"][i]["player"]["id"] for i in self.injured_out["A"]],
            extra_time=self.extra_time, penalties=self.pens,
            weather=self.weather["desc"], referee=self.ref["name"],
            motm=None,
        )
        self.finished = True
        return _res


def simulate_match(home, away, rng=None, seed=None, home_adv=True, weather=None,
                   referee=None, competition="league", neutral=False, leg=1,
                   agg=None, extra_time_allowed=True, pens_allowed=True, halftime_hook=None):
    """Simulate a whole match in one call (unchanged public API)."""
    r = MatchRunner(home, away, rng=rng, seed=seed, home_adv=home_adv, weather=weather,
                    referee=referee, competition=competition, neutral=neutral, leg=leg,
                    agg=agg, extra_time_allowed=extra_time_allowed,
                    pens_allowed=pens_allowed)
    return r.run(halftime_hook=halftime_hook)

def _extra_time(home, away, rng, goals, stats, events, rating_of, side_stats, xi_of,
                active, ratings, mins_p, injured_out, subs, reds):
    et_events = []
    for minute in range(91, 121):
        for side in ("H", "A"):
            tr = rating_of(side)
            tr["fatigue"] += 0.5
            r = 0.10 * (tr["attack"] / max(rating_of("A" if side == "H" else "H")["defence"], 1))
            if rng.random() < r:
                st = side_stats(side)
                st["shots"] += 1
                xg = rng.choice([0.05, 0.08, 0.12, 0.2, 0.3])
                st["xg"] += xg
                xi = xi_of(side)
                cands = [i for i in range(len(xi)) if active[side][i] and xi[i]["slot"] != "GK"]
                if not cands:
                    continue
                i = rng.choice(cands)
                p = xi[i]["player"]
                gkq = rating_of("A" if side == "H" else "H")["gk"]
                if rng.random() < xg * (1 - (gkq - 12) * 0.05):
                    goals[side] += 1
                    ev = dict(minute=minute, side=side, type="goal", label="extra-time chance",
                              xg=xg, player=p["name"], pid=p["id"], period="ET",
                              text=f"GOAL (ET) — {p['name']}")
                    events.append(ev)
                    et_events.append(ev)
                    ratings[side][i] += 0.8
    return dict(goals_home=goals["H"], goals_away=goals["A"], events=et_events)


def _penalties(home, away, rng, events):
    def take(team, side):
        xi = team["xi"]
        takers = []
        for it in xi:
            v = it["player"]["_vec"]
            takers.append((v.get("penalty_taking", 8) * 0.6 + v.get("composure", 8) * 0.4,
                           it["player"]))
        takers.sort(key=lambda x: -x[0])
        return takers[:5]
    res = {"H": [], "A": []}
    ht = take(home, "H")
    at = take(away, "A")
    for i in range(5):
        for side, takers in (("H", ht), ("A", at)):
            if i < len(takers):
                skill, p = takers[i]
                scored = rng.random() < (0.62 + (skill - 11) * 0.035)
                res[side].append((p["name"], scored))
    hs = sum(1 for _, s in res["H"] if s)
    as_ = sum(1 for _, s in res["A"] if s)
    # sudden death
    rnd = 5
    while hs == as_ and rnd < 12:
        for side, takers in (("H", ht), ("A", at)):
            p = takers[rnd % len(takers)][1]
            scored = rng.random() < 0.66
            res[side].append((p["name"], scored))
        hs = sum(1 for _, s in res["H"] if s)
        as_ = sum(1 for _, s in res["A"] if s)
        rnd += 1
    winner = "H" if hs > as_ else ("A" if as_ > hs else None)
    events.append(dict(minute=121, side="H", type="penalties",
                       text=f"Penalty shoot-out: {home['name']} {hs} - {as_} {away['name']}",
                       home=hs, away=as_, winner=winner, detail=res))
    return dict(home=hs, away=as_, winner=winner, detail={k: v for k, v in res.items()})


def make_weather(rng, month):
    opts = [("clear", 1.0, 1.0), ("overcast", 1.0, 0.99), ("light rain", 0.97, 0.95),
            ("heavy rain", 0.92, 0.88), ("windy", 0.95, 0.9), ("hot", 0.94, 0.97),
            ("cold", 0.99, 0.98), ("snow", 0.85, 0.82)]
    if month in (6, 7, 8):
        w = rng.choices(opts, weights=[40, 25, 10, 3, 8, 12, 1, 1])[0]
    elif month in (12, 1, 2):
        w = rng.choices(opts, weights=[18, 30, 22, 8, 12, 1, 6, 3])[0]
    else:
        w = rng.choices(opts, weights=[30, 28, 18, 6, 10, 3, 4, 1])[0]
    return dict(desc=w[0], tempo=w[1], tech=w[2])


def make_referee(rng):
    names = ["M. Oliver", "A. Taylor", "C. Pawson", "P. Tierney", "S. Hooper",
             "D. Massa", "F. Letexier", "D. Siebert", "J. Gil Manzano", "D. Makkelie",
             "S. Marciniak", "I. Kovacs", "A. Madley", "T. Robinson", "S. Barrott"]
    strict = round(rng.gauss(1.0, 0.22), 2)
    return dict(name=rng.choice(names), strictness=max(0.5, min(1.6, strict)),
                cards=round(max(0.4, min(1.9, rng.gauss(1.0, 0.35))), 2),
                pens=round(max(0.4, min(1.8, rng.gauss(1.0, 0.3))), 2))
