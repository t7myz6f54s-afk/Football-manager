"""Competition lifecycles: leagues, cups and continental tournaments finish
independently. A league ending must never terminate a live Champions League.

Run:  python3 tests/competition_test.py
"""
import os
import random
import shutil
import sys

sys.path.insert(0, "/home/user")
from fm import engine as E
from fm.world import connect, build_world

TMP = "/tmp/fm_comp_test"
PASS = 0


def ok(label):
    global PASS
    PASS += 1
    print(f"  PASS: {label}")


def fresh(tag, club="MCI"):
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
    con = connect()
    from fm import engine as E
    save = E.new_career(club, {
        "name": "Comp Test", "nat": "England", "age": 41, "reputation": 15.0,
        "style": "High press",
        "attrs": {k: 12 for k in ("attacking", "defending", "fitness", "tactical",
                                  "mental", "technical", "youth", "man_mgmt",
                                  "motivation", "adaptability", "judging")},
    }, difficulty="realistic", save_path=os.environ["FM_SAVE"])
    return con, save, E


def main():
    # ---------- 1. unit: the season-end trigger is per-competition ----------
    print("[1] season-end trigger is independent per competition")
    con, save, E = fresh("t1")
    season = save["season"]
    dt = E.d(save["date"])
    assert not E._season_end_due(con, save, dt), "fresh season should not be due"
    ok("fresh season: not due")
    # complete everything except the UCL
    ucl = con.execute("SELECT id FROM competitions WHERE code='UCL'").fetchone()["id"]
    for r in con.execute("SELECT id, ctype FROM competitions").fetchall():
        if r["ctype"] == "league":
            con.execute("UPDATE fixtures SET played=1, hg=1, aw=0 WHERE comp_id=? AND season=?",
                        (r["id"], season))
        elif r["id"] != ucl:
            E.mark_comp_complete(con, season, r["id"], None, "test")
    con.commit()
    assert not E._season_end_due(con, save, dt), \
        "season must NOT be due while the UCL is still active"
    ok("all competitions complete except the UCL: season NOT due (independent lifecycles)")
    # the UCL has a final scheduled and unplayed — the calendar must keep running
    E.mark_comp_complete(con, season, ucl, 1, dt.isoformat())
    con.commit()
    assert E._season_end_due(con, save, dt)
    ok("UCL completed: season now due")
    # backstop works even if something is stuck
    con.execute("DELETE FROM comp_state WHERE comp_id=? AND season=?", (ucl, season))
    con.commit()
    stuck = E.d("2027-07-06")  # one day past the backstop
    assert E._season_end_due(con, save, stuck)
    ok("calendar backstop (5 July) forces the rollover for stuck competitions")
    con.close()

    # ---------- 2. integration: UCL survives the league ending (TEST 1) ----------
    print("[2] full season: UCL continues past the Premier League final")
    con, save, E = fresh("t2")
    season0 = save["season"]
    rng = random.Random(777)
    ucl_id = con.execute("SELECT id FROM competitions WHERE code='UCL'").fetchone()["id"]
    eng1_id = con.execute("SELECT id FROM competitions WHERE code='ENG1'").fetchone()["id"]
    rollover_date = None
    guard = 0
    while save["season"] == season0 and guard < 4000:
        guard += 1
        seen = [u["id"] for u in E.unread_urgent(con, save)]
        r = E.advance(con, save, until="match", rng=rng, stop_for=("match", "urgent"),
                      ignore_ids=seen)
        if r["stop_reason"] == "match":
            res = E.play_next_match(con, save, mode="key", rng=rng)
            if not res.get("data"):
                E.advance(con, save, days=1, rng=rng, stop_for=(),
                          ignore_ids=seen)
        else:
            E.advance(con, save, days=1, rng=rng, stop_for=(), ignore_ids=seen)
        if save["season"] != season0 and rollover_date is None:
            rollover_date = save["date"]
    assert save["season"] == season0 + 1, f"season did not roll over: {save['date']} (guard {guard})"
    ok(f"season {season0} rolled over on {rollover_date}")

    ucl_name = con.execute("SELECT name FROM competitions WHERE id=?", (ucl_id,)).fetchone()["name"]
    # the UCL final was actually played (real result, not a forced 0-0 cancellation)
    fin = con.execute("""SELECT * FROM fixtures WHERE comp_id=? AND season=? AND stage='F' AND played=1""",
                      (ucl_id, season0)).fetchall()
    assert fin, "UCL final missing or unplayed"
    f = fin[-1]
    assert f["hg"] is not None and f["aw"] is not None, f"UCL final has no score: {dict(f)}"
    ok(f"UCL final played with a real result: {f['hg']}-{f['aw']} on {f['match_date']}")

    # winner recorded in history + comp_state
    hs = con.execute("""SELECT h.*, c.name club FROM history h JOIN clubs c ON c.id=h.club_id
        WHERE h.season=? AND h.comp_id=? AND h.trophy!=''""", (season0, ucl_id)).fetchall()
    assert hs, "no UCL winner in history"
    cs = con.execute("SELECT * FROM comp_state WHERE comp_id=? AND season=?", (ucl_id, season0)).fetchone()
    assert cs and cs["status"] == "complete" and cs["winner_id"], f"UCL comp_state: {cs}"
    ok(f"UCL winner recorded: {hs[0]['club']} (history + comp_state agree: "
       f"{hs[0]['club_id'] == cs['winner_id']})")

    # the league finished earlier and was recorded independently
    lg = con.execute("""SELECT h.*, c.name club FROM history h JOIN clubs c ON c.id=h.club_id
        WHERE h.season=? AND h.comp_id=? AND h.trophy!=''""", (season0, eng1_id)).fetchall()
    assert lg, "no league winner in history"
    ok(f"league winner recorded independently: {lg[0]['club']}")

    # the rollover waited for the continental final (not the league's last matchday)
    last_league = con.execute("""SELECT MAX(match_date) m FROM fixtures
        WHERE comp_id=? AND season=? AND stage='league'""", (eng1_id, season0)).fetchone()["m"]
    assert f["match_date"] > last_league, "test premise: UCL final is after the league's last matchday"
    assert rollover_date >= f["match_date"], \
        f"season rolled over on {rollover_date}, before the UCL final ({f['match_date']}) — lifecycles NOT independent"
    ok(f"season waited for the UCL final (league ended {last_league}, final {f['match_date']}, "
       f"rollover {rollover_date})")

    # new season fixtures exist
    nfx = con.execute("SELECT COUNT(*) n FROM fixtures WHERE season=?", (season0 + 1,)).fetchone()["n"]
    assert nfx > 1000, f"new season fixtures missing: {nfx}"
    ok(f"season {season0 + 1} fixtures built ({nfx})")

    # integrity: no non-friendly played fixture without a score
    bad = con.execute("SELECT COUNT(*) c FROM fixtures WHERE played=1 AND (hg IS NULL OR aw IS NULL) AND comp_id>0").fetchone()["c"]
    assert bad == 0, f"{bad} played competitive fixtures without scores"
    ok("integrity: no scoreless competitive fixtures")
    con.close()

    print(f"\nCOMPETITION TEST: ALL {PASS} PASS ✅")
    shutil.rmtree(TMP, ignore_errors=True)


if __name__ == "__main__":
    main()
