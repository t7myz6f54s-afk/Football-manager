"""Facilities & infrastructure investment — black-box engine tests.

Covers: migration/backfill, upgrade cost+state, budget guard, one-project-per-area,
completion timing, stadium revenue delta, youth intake quality bonus, medical
recovery bonus, and that an un-upgraded club behaves like the legacy formula.

Run:  python3 tests/facilities_test.py
"""
import os
import random
import shutil
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
TMP = "/tmp/fmfac_test"

PASS = 0


def ok(label):
    global PASS
    PASS += 1
    print(f"  PASS: {label}")


def fresh_world(tag):
    d = f"{TMP}/{tag}"
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d + "/saves", exist_ok=True)
    os.environ["FM_DB"] = d + "/world.db"
    os.environ["FM_SAVE_DIR"] = d + "/saves"
    os.environ["FM_SAVE"] = d + "/saves/career1.json"
    for m in list(sys.modules):
        if m.startswith("fm"):
            del sys.modules[m]
    from fm.world import connect, build_world
    build_world()
    return connect()


def make_career(con):
    from fm import engine as E
    save = E.new_career("WXC", {
        "name": "Fac Test", "nat": "England", "age": 40, "reputation": 14.0,
        "style": "High press",
        "attrs": {k: 12 for k in ("attacking", "defending", "fitness", "tactical",
                                  "mental", "technical", "youth", "man_mgmt",
                                  "motivation", "adaptability", "judging")},
    }, difficulty="realistic", save_path=os.environ["FM_SAVE"])
    # controlled finances so cost/budget assertions are deterministic
    con.execute("UPDATE clubs SET cash=10.0, balance=0.0 WHERE id=?", (save["club_id"],))
    con.commit()
    return save


def main():
    # ---------- 1. migration + backfill ----------
    print("[1] migration & backfill")
    con = fresh_world("w1")
    rows = con.execute("SELECT COUNT(*) n FROM club_facilities").fetchone()["n"]
    nclubs = con.execute("SELECT COUNT(*) n FROM clubs").fetchone()["n"]
    assert rows == nclubs, f"backfill missing: {rows}/{nclubs}"
    bad = 0
    for r in con.execute("SELECT c.id, c.facilities, f.training, f.train_base FROM clubs c JOIN club_facilities f ON f.club_id=c.id"):
        want = max(1, min(10, int(r["facilities"] / 2 + 0.5)))
        if r["training"] != want or r["train_base"] != want:
            bad += 1
    assert bad == 0, f"{bad} clubs with wrong derived level"
    ok(f"all {nclubs} clubs backfilled (level == derived baseline)")

    # legacy-behaviour parity: level*2 approximates the old rating
    off = con.execute("""SELECT COUNT(*) n FROM clubs c JOIN club_facilities f ON f.club_id=c.id
        WHERE ABS(f.training*2 - c.facilities) > 2""").fetchone()["n"]
    assert off == 0, f"{off} clubs deviate >2 from legacy rating scale"
    ok("un-upgraded clubs sit exactly on the legacy scale (±rounding)")

    # ---------- 2. upgrade flow ----------
    print("[2] upgrade flow")
    from fm import engine as E
    save = make_career(con)
    cid = save["club_id"]
    c0 = E.club(con, cid)
    f0 = E.facility_levels(con, cid)
    cost = E.facility_cost(con, c0, "training")
    cash_before = c0["cash"]
    r = E.upgrade_facility(con, save, "training")
    assert r["ok"] is True, r
    con.commit()
    c1 = E.club(con, cid)
    f1 = E.facility_levels(con, cid)
    assert abs(c1["cash"] - (cash_before - cost)) < 0.01, "cash not deducted"
    assert f1["train_done"] is not None, "no completion date set"
    assert f1["training"] == f0["training"], "level changed before completion"
    ok(f"started training upgrade: {cost}m deducted, pending until {f1['train_done']}")

    # one project per area; other areas independent
    r2 = E.upgrade_facility(con, save, "training")
    assert r2["ok"] is False and "already under way" in r2["msg"].lower(), r2
    r3 = E.upgrade_facility(con, save, "medical")
    assert r3["ok"] is True, r3
    con.commit()
    ok("duplicate project refused; second area starts independently")

    # unknown facility
    assert E.upgrade_facility(con, save, "heliport")["ok"] is False
    ok("unknown facility rejected")

    # ---------- 3. budget guard ----------
    print("[3] budget guard")
    con.execute("UPDATE clubs SET cash=0.0 WHERE id=?", (cid,))
    con.commit()
    r4 = E.upgrade_facility(con, save, "youth")
    assert r4["ok"] is False and "cash" in r4["msg"].lower(), r4
    assert E.facility_levels(con, cid)["youth_done"] is None
    con.execute("UPDATE clubs SET cash=? WHERE id=?", (cash_before - cost, cid))
    con.commit()
    ok(f"insufficient cash refused: {r4['msg']}")

    # max level guard
    con.execute("UPDATE club_facilities SET training=?, train_done=NULL WHERE club_id=?", (10, cid))
    con.commit()
    r5 = E.upgrade_facility(con, save, "training")
    assert r5["ok"] is False and "highest" in r5["msg"].lower(), r5
    con.execute("UPDATE club_facilities SET training=?, train_done=? WHERE club_id=?",
                (f0["training"], f1["train_done"], cid))  # restore original level + pending project
    con.commit()
    ok("max level refused")

    # ---------- 4. completion timing + effects ----------
    print("[4] completion")
    f_before = E.facility_levels(con, cid)
    c_before = E.club(con, cid)
    # training finishes in 28 days; walk days until it completes
    done_date = f_before["train_done"]
    from fm.engine import d as d_, ds as ds_
    steps = (d_(done_date) - d_(save["date"])).days
    assert steps == 28, f"expected 28-day build, got {steps}"
    rng = random.Random(3)
    for i in range(steps):
        E.tick_day(con, save, rng, auto_human=False)
        con.commit()
    f_after = E.facility_levels(con, cid)
    c_after = E.club(con, cid)
    assert f_after["training"] == f_before["training"] + 1, "level not incremented"
    assert f_after["train_done"] is None, "pending flag not cleared"
    assert c_after["facilities"] == E.facility_overall(f_after), "overall rating not recomputed"
    unread = con.execute("SELECT subject FROM inbox WHERE read=0 AND subject LIKE '%Training ground upgraded%'").fetchone()
    assert unread, "completion inbox message missing"
    ok(f"completed after {steps} days: level {f_before['training']}->{f_after['training']}, overall {c_after['facilities']}/20")

    # ---------- 5. stadium revenue delta ----------
    print("[5] stadium revenue")
    E.upgrade_facility(con, save, "stadium")
    con.commit()
    f_s = E.facility_levels(con, cid)
    c_s = E.club(con, cid)
    delta_expected = round(E._stadium_md(c_s, f_s["stadium"] + 1) - E._stadium_md(c_s, f_s["stadium"]), 3)
    steps = (d_(f_s["stadium_done"]) - d_(save["date"])).days
    assert steps == 56, f"expected 56-day stadium build, got {steps}"
    for i in range(steps):
        E.tick_day(con, save, rng, auto_human=False)
        con.commit()
    c_e = E.club(con, cid)
    f_e = E.facility_levels(con, cid)
    assert f_e["stadium"] == f_s["stadium"] + 1
    got_delta = round(c_e["season_income"] - c_s["season_income"], 3)
    assert abs(got_delta - delta_expected) < 0.011, f"revenue delta {got_delta} != expected {delta_expected}"
    ok(f"stadium complete: season_income +{got_delta}m (expected +{delta_expected}m)")

    # ---------- 6. youth intake quality bonus ----------
    print("[6] youth intake bonus")
    # paired comparison: identical rng seeds, only the facility level differs
    fl = E.facility_levels(con, cid)
    orig_y, orig_yb = fl["youth"], fl["youth_base"]
    con.execute("UPDATE club_facilities SET youth=? WHERE club_id=?", (orig_y, cid)); con.commit()
    rA = E.youth_intake(con, save, random.Random(42))
    con.execute("UPDATE club_facilities SET youth=? WHERE club_id=?", (min(10, orig_y + 5), cid)); con.commit()
    rB = E.youth_intake(con, save, random.Random(42))
    a = sum(p["ca"] for p in rA) / len(rA)
    b = sum(p["ca"] for p in rB) / len(rB)
    assert b - a > 0.8, f"youth bonus not effective: base {a:.2f} vs upgraded {b:.2f}"
    ok(f"intake CA {a:.2f} -> {b:.2f} at +5 academy levels (expected +1.10)")
    con.execute("UPDATE club_facilities SET youth=? WHERE club_id=?", (orig_y, cid)); con.commit()

    # ---------- 7. medical recovery bonus ----------
    print("[7] medical recovery bonus")
    base_days, up_days = [], []
    for seed in range(200):
        r = random.Random(seed)
        nm, d0 = E._roll_injury(r, {"name": "x"}, save, 0)
        r = random.Random(seed)
        nm2, d1 = E._roll_injury(r, {"name": "x"}, save, 9)
        assert nm == nm2, "rng sequence changed by the bonus (must be byte-identical draws)"
        base_days.append(d0)
        up_days.append(d1)
    strict = sum(1 for x, y in zip(base_days, up_days) if y < x)
    assert all(y <= x for x, y in zip(base_days, up_days))
    assert strict >= 150, f"too few strict improvements: {strict}/200"
    assert sum(up_days) / 200 < sum(base_days) / 200 * 0.97, "no mean reduction"
    ok(f"recovery: mean {sum(base_days)/200:.1f}d -> {sum(up_days)/200:.1f}d at max medical (+9); RNG draws unchanged")

    print(f"\nFACILITIES TEST: ALL {PASS} PASS ✅")
    con.close()
    shutil.rmtree(TMP, ignore_errors=True)


if __name__ == "__main__":
    main()
