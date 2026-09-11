"""Transfer market — AI approaches to listed players + negotiation flows.

Run:  python3 tests/transfer_test.py
"""
import os
import random
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
TMP = "/tmp/fmtrans_test"

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
        "name": "Trans Test", "nat": "England", "age": 40, "reputation": 14.0,
        "style": "High press",
        "attrs": {k: 12 for k in ("attacking", "defending", "fitness", "tactical",
                                  "mental", "technical", "youth", "man_mgmt",
                                  "motivation", "adaptability", "judging")},
    }, difficulty="realistic", save_path=os.environ["FM_SAVE"])
    return save


def main():
    from fm import engine as E

    # ---------- 1. listed players attract bids ----------
    print("[1] approaches to listed players")
    con = fresh_world("t1")
    save = make_career(con)
    cid = save["club_id"]
    assert E.window_state(E.d(save["date"]), save["season"]) == "summer"
    listed = con.execute("""SELECT id FROM players WHERE club_id=? AND squad='First Team'
        ORDER BY ca DESC LIMIT 3""", (cid,)).fetchall()
    for r in listed:
        con.execute("UPDATE players SET listed=1 WHERE id=?", (r["id"],))
    con.commit()
    # Bids are perishable: an ignored bid lapses after 14 days (or is superseded
    # in a bidding war), so record each bid as it appears rather than snapshotting.
    rng = random.Random(2026)
    seen = {}
    for i in range(90):
        E.tick_day(con, save, rng, auto_human=False)
        con.commit()
        for b in con.execute("""SELECT o.*, p.name, p.value FROM offers o
            JOIN players p ON p.id=o.player_id WHERE o.from_id=? AND o.id>?""",
                             (cid, max(seen) if seen else 0)).fetchall():
            seen[b["id"]] = b
        dup = con.execute("""SELECT player_id, COUNT(*) n FROM offers WHERE from_id=?
            AND status='incoming' GROUP BY player_id HAVING n>1""", (cid,)).fetchall()
        assert not dup, f"duplicate pending bids on tick {i}: {dup}"
    bids = list(seen.values())
    assert len(bids) >= 1, "no bids after 90 ticks with 3 listed players"
    ok(f"{len(bids)} bid(s) arrived in 90 ticks with 3 listed players (window open)")
    for b in bids:
        assert b["fee"] > 0 and b["human"] == 0 and b["round"] == 1
        assert b["fee"] >= b["value"] * 0.39, f"bid below value floor: {dict(b)}"
    ok("every bid is AI-originated, round 1, and at/above the value floor")
    ok("at most one pending approach per player (checked every tick)")
    # inbox: dedicated BID category with actionable payload
    bids_inbox = con.execute("SELECT * FROM inbox WHERE cat='BID' ORDER BY id DESC LIMIT 1").fetchone()
    assert bids_inbox, "no BID inbox item"
    import json
    pl = json.loads(bids_inbox["payload"])
    for key in ("action", "offer_id", "fee", "asking", "value"):
        assert key in pl, f"payload missing {key}: {pl}"
    ok(f"BID inbox item actionable (action={pl['action']}, offer_id={pl['offer_id']})")

    # determinism of the approach mechanism
    con.close()
    con_b = fresh_world("t2")
    save_b = make_career(con_b)
    cid_b = save_b["club_id"]
    for r in con_b.execute("""SELECT id FROM players WHERE club_id=? AND squad='First Team'
        ORDER BY ca DESC LIMIT 3""", (cid_b,)):
        con_b.execute("UPDATE players SET listed=1 WHERE id=?", (r["id"],))
    con_b.commit()
    rng_b = random.Random(2026)
    for i in range(90):
        E.tick_day(con_b, save_b, rng_b, auto_human=False)
        con_b.commit()
    # full offer history (bids lapse/get superseded, so compare every row)
    bids_b = con_b.execute("""SELECT o.id, o.player_id, o.to_id, o.fee, o.date, o.status FROM offers o
        WHERE o.from_id=? ORDER BY o.id""", (cid_b,)).fetchall()
    # re-read from t1 is gone; instead compare t2 with a third identical run
    ok(f"second identical world: {len(bids_b)} bid(s) — comparing with third run")
    con_b.close()
    con_c = fresh_world("t3")
    save_c = make_career(con_c)
    cid_c = save_c["club_id"]
    for r in con_c.execute("""SELECT id FROM players WHERE club_id=? AND squad='First Team'
        ORDER BY ca DESC LIMIT 3""", (cid_c,)):
        con_c.execute("UPDATE players SET listed=1 WHERE id=?", (r["id"],))
    con_c.commit()
    rng_c = random.Random(2026)
    for i in range(90):
        E.tick_day(con_c, save_c, rng_c, auto_human=False)
        con_c.commit()
    bids_c = con_c.execute("""SELECT o.id, o.player_id, o.to_id, o.fee, o.date, o.status FROM offers o
        WHERE o.from_id=? ORDER BY o.id""", (cid_c,)).fetchall()
    ka = [(r["player_id"], r["to_id"], r["fee"], r["date"], r["status"]) for r in bids_b]
    kb = [(r["player_id"], r["to_id"], r["fee"], r["date"], r["status"]) for r in bids_c]
    assert ka == kb and len(ka) >= 1, f"approach mechanism not deterministic: {ka} vs {kb}"
    ok("approach outcomes are deterministic per seed+date")

    # ---------- 2. zero drift when nobody is listed ----------
    print("[2] zero drift with nothing listed")
    def snapshot(con):
        fx = con.execute("SELECT hg,aw FROM fixtures WHERE played=1 ORDER BY id").fetchall()
        pl = con.execute("SELECT id,ca,condition FROM players ORDER BY id").fetchall()
        of = con.execute("SELECT id,player_id,fee,status FROM offers ORDER BY id").fetchall()
        return (tuple(fx), tuple(pl), tuple(of))

    con_d = fresh_world("t4")
    save_d = make_career(con_d)
    rng_d = random.Random(31337)
    for i in range(20):
        E.tick_day(con_d, save_d, rng_d, auto_human=False)
        con_d.commit()
    snap_real = snapshot(con_d)
    n_offers_real = con_d.execute("SELECT COUNT(*) n FROM offers WHERE from_id=?", (save_d["club_id"],)).fetchone()["n"]
    assert n_offers_real == 0, "unexpected bids with nothing listed"
    con_d.close()

    con_e = fresh_world("t5")
    save_e = make_career(con_e)
    E._approach_human_players = lambda *a, **k: None  # no-op: pre-feature behaviour
    rng_e = random.Random(31337)
    for i in range(20):
        E.tick_day(con_e, save_e, rng_e, auto_human=False)
        con_e.commit()
    snap_noop = snapshot(con_e)
    assert snap_real == snap_noop, "world drifts when nobody is listed (rng stream or state touched)"
    ok("20-tick world bit-identical to pre-feature code when nothing is listed")
    con_e.close()

    # ---------- 3. negotiation flows ----------
    print("[3] negotiation flows")

    def incoming(con, save, pid, buyer_id):
        """Fabricate a realistic AI bid for our player, return its id."""
        ask = E.asking_price(con, save, pid)
        fee = round(ask * 1.05, 2)
        oid = con.execute("SELECT COALESCE(MAX(id),0)+1 FROM offers").fetchone()[0]
        con.execute("""INSERT INTO offers (id,player_id,from_id,to_id,fee,addons,wage,status,date,round,
            clause,is_loan,loan_end,split,human,note) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,0,?)""",
            (oid, pid, save["club_id"], buyer_id, fee, "{}", round(1.0, 2),
             "incoming", save["date"], 1, 0, 0, None, 0, "pending"))
        con.commit()
        return oid, fee

    # 3a. counter: exactly one of the three documented outcomes, state consistent
    con_f = fresh_world("t6")
    save_f = make_career(con_f)
    cid_f = save_f["club_id"]
    victim = con_f.execute("""SELECT * FROM players WHERE club_id=? AND squad='First Team'
        ORDER BY ca DESC LIMIT 1""", (cid_f,)).fetchone()
    buyer = con_f.execute("SELECT * FROM clubs WHERE rep>=85 AND id!=? ORDER BY rep DESC LIMIT 1",
                          (cid_f,)).fetchone()
    oid, fee = incoming(con_f, save_f, victim["id"], buyer["id"])
    r = E.handle_incoming_bid(con_f, save_f, oid, "counter", counter_fee=round(fee * 1.6, 2),
                              rng=random.Random(5))
    con_f.commit()
    o = con_f.execute("SELECT * FROM offers WHERE id=?", (oid,)).fetchone()
    moved = con_f.execute("SELECT club_id FROM players WHERE id=?", (victim["id"],)).fetchone()["club_id"]
    new_offer = con_f.execute("SELECT id, fee, status FROM offers WHERE from_id=? AND status='incoming' AND id!=?",
                              (cid_f, oid)).fetchone()
    if r.get("ok") is True and "accepted" in r.get("msg", ""):
        assert moved == buyer["id"], "counter-accept did not move the player"
        ok(f"counter {fee * 1.6:.2f}m accepted by buyer — deal done")
    elif r.get("ok") == "counter":
        assert new_offer and o["status"] == "countered", "counter outcome inconsistent"
        ok(f"counter met with counter-offer {fee:.2f} → {new_offer['fee']}m (new offer {new_offer['id']})")
    elif r.get("ok") is False:
        assert "walked away" in r.get("msg", ""), f"unexpected counter failure: {r}"
        assert o["status"] in ("countered", "rejected"), "old offer left pending after walk-away"
        ok("buyer walked away (counter above their ceiling) — offer closed cleanly")
    else:
        raise AssertionError(f"undocumented counter outcome: {r}")

    # 3b. accept: player moves, offer accepted, cash up
    con_g = fresh_world("t7")
    save_g = make_career(con_g)
    cid_g = save_g["club_id"]
    victim2 = con_g.execute("""SELECT * FROM players WHERE club_id=? AND squad='First Team'
        ORDER BY ca DESC LIMIT 1""", (cid_g,)).fetchone()
    buyer2 = con_g.execute("SELECT * FROM clubs WHERE rep>=85 AND id!=? ORDER BY rep DESC LIMIT 1",
                           (cid_g,)).fetchone()
    oid2, fee2 = incoming(con_g, save_g, victim2["id"], buyer2["id"])
    cash_before = con_g.execute("SELECT cash FROM clubs WHERE id=?", (cid_g,)).fetchone()["cash"]
    r2 = E.handle_incoming_bid(con_g, save_g, oid2, "accept", rng=random.Random(6))
    con_g.commit()
    assert r2.get("ok") is True, f"accept failed: {r2}"
    o2 = con_g.execute("SELECT status FROM offers WHERE id=?", (oid2,)).fetchone()
    pnow = con_g.execute("SELECT club_id, wage FROM players WHERE id=?", (victim2["id"],)).fetchone()
    cash_after = con_g.execute("SELECT cash FROM clubs WHERE id=?", (cid_g,)).fetchone()["cash"]
    assert o2["status"] == "accepted", f"offer status {o2['status']}"
    assert pnow["club_id"] == buyer2["id"], "accept did not move the player"
    assert cash_after > cash_before + fee2 * 0.9, f"cash {cash_before} → {cash_after}, expected +~{fee2}"
    ok(f"accept closed the deal — {victim2['name']} now at {buyer2['name']}, cash {cash_before:.1f} → {cash_after:.1f}m")

    # 3c. reject: offer rejected, no state leak
    con_h = fresh_world("t8")
    save_h = make_career(con_h)
    cid_h = save_h["club_id"]
    victim3 = con_h.execute("""SELECT * FROM players WHERE club_id=? AND squad='First Team'
        ORDER BY ca DESC LIMIT 1""", (cid_h,)).fetchone()
    buyer3 = con_h.execute("SELECT * FROM clubs WHERE rep>=85 AND id!=? ORDER BY rep DESC LIMIT 1",
                           (cid_h,)).fetchone()
    oid3, fee3 = incoming(con_h, save_h, victim3["id"], buyer3["id"])
    r3 = E.handle_incoming_bid(con_h, save_h, oid3, "reject", rng=random.Random(9))
    con_h.commit()
    o3 = con_h.execute("SELECT status FROM offers WHERE id=?", (oid3,)).fetchone()
    p3 = con_h.execute("SELECT club_id FROM players WHERE id=?", (victim3["id"],)).fetchone()
    assert r3.get("ok") is True and o3["status"] == "rejected", f"reject failed: {r3} / {o3['status']}"
    assert p3["club_id"] == cid_h, "player moved on a rejected bid"
    if r3.get("new_offer"):
        oi = con_h.execute("SELECT fee, status FROM offers WHERE id=?", (r3["new_offer"],)).fetchone()
        assert oi["fee"] > fee3 and oi["status"] == "incoming"
        ok(f"reject → improved bid {fee3} → {oi['fee']}m came back (30% mechanic)")
    else:
        ok("reject → negotiation closed")
    con_h.close()
    con_f.close()
    con_g.close()

    print(f"\nTRANSFER TEST: ALL {PASS} PASS ✅")
    shutil.rmtree(TMP, ignore_errors=True)


if __name__ == "__main__":
    main()
