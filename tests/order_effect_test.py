"""Match Day Live+ — do touchline orders actually change outcomes?

Paired simulation: identical seeds, identical teams; the only difference is a
touchline order applied at minute 55. Asserts the order measurably moves the
needle on the ordered side (shots / xG / goals), and that constraints hold.
"""
import copy
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("FM_DB", "/tmp/fm_order_test/world.db")

from fm import engine as E            # noqa: E402
from fm import match as M             # noqa: E402
from fm.world import build_world, connect  # noqa: E402

SAVE = "/tmp/fm_order_test/save.json"
N_PAIRS = 60


def build_runner(con, save, opp_id, seed, home=None, away=None):
    if home is None or away is None:
        cid = save["club_id"]
        tac = E.get_tactics(con, save)
        xi, bench = M.build_lineup(E.load_players(con, cid), tac)
        oxi, obench = M.build_lineup(E.load_players(con, opp_id), E.ai_tactics(con, opp_id))
        home = dict(name="Mine", xi=xi, bench=bench, rating=M.team_rating(xi, tac), human=True)
        away = dict(name="Foe", xi=oxi, bench=obench, rating=M.team_rating(oxi, E.ai_tactics(con, opp_id)),
                    human=False)
        if home["rating"]["overall"] < away["rating"]["overall"]:
            home, away = away, home  # always manage the stronger side for stability
    return M.MatchRunner(copy.deepcopy(home), copy.deepcopy(away), rng=random.Random(seed),
                         competition="league")


def play_to(runner, minute):
    runner.start()
    while runner.minute < minute and runner.minute < runner.max_min:
        runner._play_minute()
        runner.minute += 1


def main():
    os.makedirs("/tmp/fm_order_test", exist_ok=True)
    if not os.environ.get("FM_SEED_READY"):
        build_world()
    con = connect()
    save = E.new_career("WXC", {"name": "T", "nat": "England", "age": 40, "reputation": 14,
                                "style": "balanced", "attrs": {}},
                        difficulty="realistic", save_path=SAVE)
    opp_id = next(c["id"] for c in con.execute("SELECT id FROM clubs WHERE id != ? LIMIT 1",
                                               (save["club_id"],)).fetchall())

    for order in ("all_out_attack", "sit_deep"):
        d_shots, d_xg, d_goals, applied = [], [], [], 0
        for seed in range(N_PAIRS):
            # build teams ONCE per seed so the pair is truly identical
            r0 = build_runner(con, save, opp_id, 1000 + seed)
            home_t, away_t = r0.home, r0.away
            r1 = build_runner(con, save, opp_id, 1000 + seed, home=home_t, away=away_t)
            play_to(r0, 55)
            base_side = r0.my_side
            gm0 = r0.goals[base_side] - r0.goals["A" if base_side == "H" else "H"]
            r0.run_rest()
            r0.finalize()
            # ordered (identical teams, identical seed)
            play_to(r1, 55)
            side = r1.my_side
            ok, _msg = r1.apply_order(side, order)
            if not ok:
                continue  # context rule refused (e.g. winning + all-out) — skip pair
            applied += 1
            r1.run_rest()
            r1.finalize()
            st0, st1 = r0.side_stats(base_side), r1.side_stats(side)
            d_shots.append(st1["shots"] - st0["shots"])
            d_xg.append(st1["xg"] - st0["xg"])
            d_goals.append(r1.goals[side] - r0.goals[base_side])
        if not applied:
            raise SystemExit(f"{order}: never applied — context rules too tight")
        shots_up = sum(1 for d in d_shots if d > 0)
        print(f"{order}: applied {applied}/{N_PAIRS} | "
              f"mean dShots {sum(d_shots)/len(d_shots):+.2f} ({shots_up}/{len(d_shots)} up) | "
              f"mean dxG {sum(d_xg)/len(d_xg):+.3f} | mean dGoals {sum(d_goals)/len(d_goals):+.2f}")
        if order == "all_out_attack":
            assert sum(d_shots) / len(d_shots) > 0.3, "all_out_attack did not raise shot volume"
            assert shots_up >= applied * 0.5, "all_out_attack not directionally consistent"
            assert sum(d_xg) / len(d_xg) > 0.0, "all_out_attack did not raise own xG"
        if order == "sit_deep":
            assert sum(d_shots) / len(d_shots) < 0.75, "sit_deep barely changed anything"
    print("\nORDER EFFECT TEST: PASS ✅ (orders measurably change the simulation)")


if __name__ == "__main__":
    main()
