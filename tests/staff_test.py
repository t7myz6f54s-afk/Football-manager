"""Staff management (hire/sack/renew/expiry) — black-box engine tests.

Run:  python3 tests/staff_test.py
"""
import os
import random
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
TMP = "/tmp/fmstaff_test"

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


def make_career(con, code="WXC"):
    from fm import engine as E
    save = E.new_career(code, {
        "name": "Staff Test", "nat": "England", "age": 40, "reputation": 14.0,
        "style": "High press",
        "attrs": {k: 12 for k in ("attacking", "defending", "fitness", "tactical",
                                  "mental", "technical", "youth", "man_mgmt",
                                  "motivation", "adaptability", "judging")},
    }, difficulty="realistic", save_path=os.environ["FM_SAVE"])
    return save


def main():
    # ---------- 1. free-coaches market ----------
    print("[1] market generation")
    con = fresh_world("w1")
    npool = con.execute("SELECT COUNT(*) n FROM staff WHERE club_id IS NULL").fetchone()["n"]
    nclub = con.execute("SELECT COUNT(*) n FROM staff WHERE club_id IS NOT NULL").fetchone()["n"]
    nclubs = con.execute("SELECT COUNT(*) n FROM clubs WHERE code!='FREE'").fetchone()["n"]
    assert npool == 160, f"pool size {npool}"
    assert nclub == nclubs * 14, f"club staff {nclub} != {nclubs}*14"
    ok(f"160 free coaches + {nclubs*14} club staff intact")

    # determinism: second build must produce the identical pool
    con.close()
    con2 = fresh_world("w2")
    a = [(r["name"], r["role"], r["wage"], r["reputation"]) for r in
         con2.execute("SELECT * FROM staff WHERE club_id IS NULL ORDER BY id")]
    con2b = fresh_world("w3")
    b = [(r["name"], r["role"], r["wage"], r["reputation"]) for r in
         con2b.execute("SELECT * FROM staff WHERE club_id IS NULL ORDER BY id")]
    assert a == b and len(a) == 160, "pool not deterministic across builds"
    ok("pool is bit-identical across fresh builds")

    from fm import engine as E
    con2.close()
    con = con2b
    save = make_career(con)
    cid = save["club_id"]
    # controlled wage budget so cost guards are tested independently of club size
    con.execute("UPDATE clubs SET wage_budget=40.0 WHERE id=?", (cid,))
    con.commit()

    pool = con.execute("SELECT * FROM staff WHERE club_id IS NULL ORDER BY reputation DESC LIMIT 5").fetchall()
    top = pool[0]

    # ---------- 2. hire ----------
    print("[2] hire")
    before = E.coaching_ratings(con, cid)
    c0 = E.club(con, cid)
    r = E.hire_staff(con, save, top["id"])
    assert r["ok"] is True, r
    con.commit()
    srow = con.execute("SELECT * FROM staff WHERE id=?", (top["id"],)).fetchone()
    assert srow["club_id"] == cid and srow["contract_end"], "not attached to club"
    after = E.coaching_ratings(con, cid)
    assert after != before, "coaching ratings unchanged after hire"
    n = con.execute("SELECT COUNT(*) n FROM staff WHERE club_id=?", (cid,)).fetchone()["n"]
    assert n == 15, f"club staff count {n}"
    inbox = con.execute("SELECT COUNT(*) n FROM inbox WHERE read=0 AND subject LIKE '%signs%'").fetchone()["n"]
    assert inbox >= 1, "hire inbox missing"
    ok(f"signed {top['name']} ({top['role']}) — coaching {before['training']} → {after['training']}, {n} staff")

    # ---------- 3. wage budget guard ----------
    print("[3] wage budget guard")
    nxt = pool[1]
    orig_budget = E.club(con, cid)["wage_budget"]
    con.execute("UPDATE clubs SET wage_budget=0.01 WHERE id=?", (cid,))
    con.commit()
    r2 = E.hire_staff(con, save, nxt["id"])
    assert r2["ok"] is False and "wage budget" in r2["msg"].lower(), r2
    assert con.execute("SELECT club_id FROM staff WHERE id=?", (nxt["id"],)).fetchone()["club_id"] is None
    con.execute("UPDATE clubs SET wage_budget=? WHERE id=?", (orig_budget, cid))
    con.commit()
    ok(f"over-budget hire refused: {r2['msg']}")

    # ---------- 4. cap guard ----------
    print("[4] cap guard")
    while con.execute("SELECT COUNT(*) n FROM staff WHERE club_id=?", (cid,)).fetchone()["n"] < E.STAFF_CAP:
        p = con.execute("SELECT * FROM staff WHERE club_id IS NULL ORDER BY reputation DESC LIMIT 1").fetchone()
        rr = E.hire_staff(con, save, p["id"])
        assert rr["ok"] is True, rr
    con.commit()
    n = con.execute("SELECT COUNT(*) n FROM staff WHERE club_id=?", (cid,)).fetchone()["n"]
    assert n == E.STAFF_CAP, n
    p_extra = con.execute("SELECT * FROM staff WHERE club_id IS NULL ORDER BY reputation DESC LIMIT 1").fetchone()
    r3 = E.hire_staff(con, save, p_extra["id"])
    assert r3["ok"] is False and "full" in r3["msg"].lower(), r3
    ok(f"cap {E.STAFF_CAP} enforced: {r3['msg']}")

    # ---------- 5. sack ----------
    print("[5] sack")
    victim = con.execute("SELECT * FROM staff WHERE club_id=? ORDER BY reputation ASC", (cid,)).fetchone()
    c_before = E.club(con, cid)
    sev = round(victim["wage"] * E.STAFF_SEVERANCE_WEEKS / 1000.0, 2)
    cb = E.coaching_ratings(con, cid)
    r4 = E.sack_staff(con, save, victim["id"])
    assert r4["ok"] is True, r4
    assert abs(r4["severance"] - sev) < 0.011
    con.commit()
    c_after = E.club(con, cid)
    assert abs(c_after["cash"] - (c_before["cash"] - sev)) < 0.011, "severance not paid"
    assert con.execute("SELECT club_id FROM staff WHERE id=?", (victim["id"],)).fetchone()["club_id"] is None
    assert E.coaching_ratings(con, cid) != cb, "coaching unchanged after sack"
    ok(f"released {victim['name']}: severance {sev}m, cash {c_before['cash']:.2f} → {c_after['cash']:.2f}")

    # cash guard
    con.execute("UPDATE clubs SET cash=0 WHERE id=?", (cid,))
    con.commit()
    v2 = con.execute("SELECT * FROM staff WHERE club_id=? LIMIT 1", (cid,)).fetchone()
    r5 = E.sack_staff(con, save, v2["id"])
    assert r5["ok"] is False and "severance" in r5["msg"].lower(), r5
    con.execute("UPDATE clubs SET cash=? WHERE id=?", (c_after["cash"], cid))
    con.commit()
    ok(f"poor-club sack refused: {r5['msg']}")

    # ---------- 6. renew ----------
    print("[6] renew")
    v3 = con.execute("SELECT * FROM staff WHERE club_id=? ORDER BY reputation DESC LIMIT 1", (cid,)).fetchone()
    old_end, old_wage = v3["contract_end"], v3["wage"]
    r6 = E.renew_staff(con, save, v3["id"])
    assert r6["ok"] is True, r6
    con.commit()
    v3n = con.execute("SELECT * FROM staff WHERE id=?", (v3["id"],)).fetchone()
    assert v3n["contract_end"] > old_end, "contract not extended"
    assert abs(v3n["wage"] - round(old_wage * 1.05, 2)) < 0.011, "wage not raised 5%"
    ok(f"renewed {v3['name']}: {old_end} → {v3n['contract_end']}, wage {old_wage} → {v3n['wage']}")

    # ---------- 7. contract expiry in tick ----------
    print("[7] expiry")
    v4 = con.execute("SELECT * FROM staff WHERE club_id=? ORDER BY id LIMIT 1", (cid,)).fetchone()
    con.execute("UPDATE staff SET contract_end=? WHERE id=?", ("2026-06-01", v4["id"]))
    con.commit()
    n_free_before = con.execute("SELECT COUNT(*) n FROM staff WHERE club_id IS NULL").fetchone()["n"]
    world_counts_before = {r["club_id"]: r["n"] for r in con.execute(
        "SELECT club_id, COUNT(*) n FROM staff WHERE club_id IS NOT NULL AND club_id!=? GROUP BY club_id", (cid,))}
    rng = random.Random(7)
    E.tick_day(con, save, rng, auto_human=False)
    con.commit()
    assert con.execute("SELECT club_id FROM staff WHERE id=?", (v4["id"],)).fetchone()["club_id"] is None, \
        "expired staff not released"
    n_free_after = con.execute("SELECT COUNT(*) n FROM staff WHERE club_id IS NULL").fetchone()["n"]
    assert n_free_after == n_free_before + 1, "pool not replenished by expiry"
    world_counts_after = {r["club_id"]: r["n"] for r in con.execute(
        "SELECT club_id, COUNT(*) n FROM staff WHERE club_id IS NOT NULL AND club_id!=? GROUP BY club_id", (cid,))}
    assert world_counts_before == world_counts_after, "world clubs lost/gained staff"
    exp_msg = con.execute("SELECT COUNT(*) n FROM inbox WHERE read=0 AND subject LIKE '%contract expired%'").fetchone()["n"]
    assert exp_msg >= 1, "expiry inbox missing"
    ok(f"expired {v4['name']} released to market on expiry day; all {len(world_counts_before)} world clubs untouched")

    # ---------- 8. no hire for foreign/missing ids ----------
    print("[8] guards")
    other = con.execute("SELECT id FROM staff WHERE club_id IS NOT NULL AND club_id!=? LIMIT 1", (cid,)).fetchone()["id"]
    assert E.hire_staff(con, save, other)["ok"] is False
    assert E.sack_staff(con, save, other)["ok"] is False
    assert E.hire_staff(con, save, 99999999)["ok"] is False
    ok("foreign/missing staff rejected across all actions")

    print(f"\nSTAFF TEST: ALL {PASS} PASS ✅")
    con.close()
    shutil.rmtree(TMP, ignore_errors=True)


if __name__ == "__main__":
    main()
