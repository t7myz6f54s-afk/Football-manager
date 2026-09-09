"""Smoke test: create a career, advance, play matches, run a season."""
import json
import os
import random
import sys
import time

sys.path.insert(0, "/home/user")
from fm import engine as E
from fm.world import connect

SAVE = "/home/user/data/saves/test.json"


def main(days=None, club="WXC"):
    if os.path.exists(SAVE):
        os.remove(SAVE)
    from fm.world import build_world
    build_world()
    con = connect()
    t0 = time.time()
    save = E.new_career(club, {
        "name": "Test Manager", "nat": "England", "age": 40, "reputation": 14.0,
        "style": "High press",
        "attrs": {"attacking": 12, "defending": 11, "fitness": 12, "tactical": 14,
                  "mental": 11, "technical": 12, "youth": 13, "man_mgmt": 12,
                  "motivation": 12, "adaptability": 12, "judging": 11},
    }, difficulty="realistic", save_path=SAVE)
    print(f"career created in {time.time()-t0:.2f}s at {save['date']}")
    rng = random.Random(7)
    t0 = time.time()
    # advance to first match
    r = E.advance(con, save, until="match", rng=rng)
    print("advance ->", r["stop_reason"], save["date"], f"{time.time()-t0:.2f}s")
    nmatch = 0
    t0 = time.time()
    while nmatch < 3:
        nf = E.next_fixture(con, save)
        if not nf:
            break
        res = E.play_next_match(con, save, mode="key", rng=rng)
        d = res.get("data")
        if not d:
            print("no data", res)
            break
        nmatch += 1
        print(f"MATCH {nmatch}: {d['home_name']} {d['hg']}-{d['ag']} {d['away_name']} "
              f"| xG {d['xg_home']:.2f}-{d['xg_away']:.2f} | poss {d['possession_home']}% "
              f"| shots {d['shots_home']}-{d['shots_away']} | events {len(d['events'])} "
              f"| injuries {len(d['injuries'])} | {time.time()-t0:.2f}s")
        lr = save["last_result"]
        print("   my:", lr["my_goals"], "-", lr["opp_goals"], lr["result"], "board conf",
              round(save["board"]["confidence"], 1), "fans", round(save["fans"]["sentiment"], 1))
        r = E.advance(con, save, until="match", rng=rng)
    print("3 matches done in %.2fs" % (time.time() - t0))
    # long advance
    t0 = time.time()
    r = E.advance(con, save, days=30, rng=rng, stop_for=())
    print(f"advance 30 days (auto-sim matches) in {time.time()-t0:.2f}s -> {save['date']}")
    rows = con.execute("SELECT COUNT(*) c FROM fixtures WHERE played=1").fetchone()
    print("world fixtures played:", rows["c"])
    pos = E._league_position(con, save)
    print("league position:", pos)
    print("inbox:", con.execute("SELECT COUNT(*) c FROM inbox WHERE read=0").fetchone()["c"], "unread")
    print("season stats:", save["season_stats"])
    con.close()


if __name__ == "__main__":
    main()
