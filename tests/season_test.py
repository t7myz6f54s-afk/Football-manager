"""Full-season integration test: plays a whole season with the human club."""
import json
import os
import random
import sys
import time

sys.path.insert(0, "/home/user")
from fm import engine as E
from fm.world import connect, build_world

SAVE = "/home/user/data/saves/season_test.json"


def run(club="WXC", seasons=1):
    build_world()
    if os.path.exists(SAVE):
        os.remove(SAVE)
    con = connect()
    save = E.new_career(club, {
        "name": "A. Ferguson", "nat": "Scotland", "age": 41, "reputation": 15.0,
        "style": "High press",
        "attrs": {"attacking": 13, "defending": 11, "fitness": 12, "tactical": 15,
                  "mental": 12, "technical": 13, "youth": 14, "man_mgmt": 13,
                  "motivation": 14, "adaptability": 12, "judging": 12},
    }, difficulty="realistic", save_path=SAVE)
    rng = random.Random(2026)
    t0 = time.time()
    matches = 0
    for s in range(seasons):
        guard = 0
        while guard < 60:
            guard += 1
            r = E.advance(con, save, until="match", rng=rng, stop_for=("match",))
            if r["stop_reason"] != "match":
                break
            res = E.play_next_match(con, save, mode="key", rng=rng)
            if not res.get("data"):
                break
            matches += 1
            if matches % 10 == 0:
                pos = E._league_position(con, save)
                print(f"  [{save['date']}] {matches} matches, table {pos['pos']}/{pos['size']} "
                      f"{pos['pts']}pts, board {save['board']['confidence']:.0f}, "
                      f"{time.time()-t0:.0f}s")
        # run to season end
        r = E.advance(con, save, until="season_end", rng=rng, stop_for=())
        print(f"  season end reached: {save['date']} season={save['season']} ({time.time()-t0:.0f}s)")
    print(f"TOTAL {matches} matches in {time.time()-t0:.1f}s -> date {save['date']} season {save['season']}")
    # checks
    q = lambda s, *a: con.execute(s, a).fetchall()
    print("\n--- integrity checks ---")
    bad = q("SELECT COUNT(*) c FROM fixtures WHERE played=1 AND (hg IS NULL OR aw IS NULL) AND comp_id>0")
    print("played fixtures with NULL score:", bad[0]["c"])
    dup = q("""SELECT home_id, away_id, match_date, COUNT(*) c FROM fixtures
               WHERE comp_id>0 GROUP BY 1,2,3 HAVING c>1""")
    print("duplicate fixtures:", len(dup))
    neg = q("SELECT COUNT(*) c FROM players WHERE fitness<0 OR fitness>100 OR fatigue<0 OR fatigue>100")
    print("players with out-of-range condition:", neg[0]["c"])
    nosquad = q("SELECT COUNT(*) c FROM clubs WHERE id NOT IN (SELECT DISTINCT club_id FROM players WHERE club_id IS NOT NULL)")
    print("clubs without players:", nosquad[0]["c"])
    print("\n--- world goals ---")
    for r in q("""SELECT k.code, COUNT(*) n, ROUND(AVG(f.hg+f.aw),2) g FROM fixtures f
        JOIN competitions k ON k.id=f.comp_id WHERE f.played=1 AND k.ctype='league'
        AND k.code IN ('ENG1','ENG2','ENG3','ENG5','ESP1','UCL') GROUP BY k.code"""):
        print(dict(r))
    print("\n--- human club table ---")
    print("employed:", not save["flags"].get("unemployed"), "| club_id:", save["club_id"],
          "| career:", [(x["name"], x["from"], x["to"]) for x in save["career"]["clubs"]])
    pos = E._league_position(con, save, season=save["season"] - 1)
    print(pos)
    print("season stats:", save["season_stats"])
    print("trophies:", save["career"]["trophies"])
    print("reputation:", round(save["career"]["reputation"], 1))
    rows = q("""SELECT name, age, pos, ca, pa, goals, assists, apps, avg_rating FROM players
        WHERE club_id=? AND squad IN ('First Team','Reserve') ORDER BY goals DESC LIMIT 5""",
        save["club_id"] or -1)
    for r in rows:
        print(" ", dict(r))
    if save["club_id"]:
        fin = q("SELECT cash, balance, wage_bill, transfer_budget, wage_budget FROM clubs WHERE id=?", save["club_id"])
        print("finances:", dict(fin[0]))
    else:
        print("finances: n/a (unemployed)")
    inbox = q("SELECT cat, COUNT(*) c FROM inbox GROUP BY cat")
    print("inbox by cat:", [(r["cat"], r["c"]) for r in inbox])
    con.close()


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "WXC", int(sys.argv[2]) if len(sys.argv) > 2 else 1)
