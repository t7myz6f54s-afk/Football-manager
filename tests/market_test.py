"""v1.20.0 Transfer-market realism:

1. Incoming counters are capped: a buyer has a board budget and a valuation
   ceiling (value-based, discounted for recently flipped players). Absurd
   counters are rejected or met at the buyer's ceiling — never blindly
   accepted.
2. No same-window flipping: a player bought during the open window cannot be
   listed, sold or re-signed elsewhere until it closes (listing, incoming
   bids, and the seller AI are all blocked).
3. Outgoing counters respect the manager's transfer budget, and negotiations
   end after a final round instead of continuing forever.
4. Trophy success makes the club a destination: top players elsewhere send
   enquiries (and want to come — personal terms are a formality).
5. Transfer hijacks: a rival outbids you on a live purchase (you lose the
   deal), or outbids a buyer on one of your players (a bidding war you can
   still win).
6. Buyer funding: a deal cannot close if the buyer cannot pay.

Run:  python3 tests/market_test.py
"""
import os
import random
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
TMP = "/tmp/fmmarket_test"

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
        "name": "Market Test", "nat": "England", "age": 40, "reputation": 14.0,
        "style": "High press",
        "attrs": {k: 12 for k in ("attacking", "defending", "fitness", "tactical",
                                  "mental", "technical", "youth", "man_mgmt",
                                  "motivation", "adaptability", "judging")},
    }, difficulty="realistic", save_path=os.environ["FM_SAVE"])
    return save


class FakeRng:
    """Deterministic rng that always takes the first/lowest outcome — used to
    force probability-gated branches to fire on the first tick."""
    def random(self):
        return 0.0

    def uniform(self, a, b):
        return a

    def choice(self, seq):
        return seq[0]

    def randrange(self, n, *a):
        return 0

    def randint(self, a, b):
        return a

    def gauss(self, m, s):
        return 0.0

    def shuffle(self, seq):
        pass

    def sample(self, seq, k):
        return list(seq)[:k]

    def choices(self, seq, weights=None, k=1):
        return [seq[0]] * k


def incoming_offer(con, save, pid, buyer_id, fee, rnd=1):
    oid = con.execute("SELECT COALESCE(MAX(id),0)+1 FROM offers").fetchone()[0]
    con.execute("""INSERT INTO offers (id,player_id,from_id,to_id,fee,addons,wage,status,date,round,
        clause,is_loan,loan_end,split,human,note) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,0,?)""",
        (oid, pid, save["club_id"], buyer_id, fee, "{}", 1.0, "incoming",
         save["date"], rnd, 0, 0, None, 0, "pending"))
    con.commit()
    return oid


def main():
    from fm import engine as E

    # =====================================================================
    print("[1] incoming counters are capped by buyer budget + valuation")
    con = fresh_world("m1")
    save = make_career(con)
    cid = save["club_id"]
    assert E.window_state(E.d(save["date"]), save["season"]) == "summer"
    vrow = con.execute("""SELECT * FROM players WHERE club_id=? AND squad='First Team'
        ORDER BY value DESC LIMIT 1""", (cid,)).fetchone()
    buyer = con.execute("SELECT * FROM clubs WHERE rep>=85 AND id!=? ORDER BY rep DESC LIMIT 1",
                        (cid,)).fetchone()
    v = float(vrow["value"])
    budget = round(v * 0.5, 2)
    con.execute("UPDATE clubs SET transfer_budget=?, cash=cash+1000 WHERE id=?", (budget, buyer["id"]))
    con.commit()

    # 1a. absurd counter (50x value) — the buyer walks, the player stays
    oid = incoming_offer(con, save, vrow["id"], buyer["id"], round(v * 0.6, 2))
    r = E.handle_incoming_bid(con, save, oid, "counter", counter_fee=round(v * 50, 2),
                              rng=random.Random(1))
    con.commit()
    pnow = con.execute("SELECT club_id FROM players WHERE id=?", (vrow["id"],)).fetchone()
    o = con.execute("SELECT status FROM offers WHERE id=?", (oid,)).fetchone()
    assert r.get("ok") is False, f"absurd counter was not rejected: {r}"
    assert "walked away" in r.get("msg", ""), f"expected walk-away, got: {r['msg']}"
    assert pnow["club_id"] == cid, "player sold on an absurd counter!"
    assert o["status"] == "rejected", f"offer status {o['status']}"
    ok(f"50x-value counter rejected — buyer walked away, player kept (cap = budget {budget}m)")

    # 1b. counter 5% over the buyer's budget — countered back AT their ceiling
    oid2 = incoming_offer(con, save, vrow["id"], buyer["id"], round(budget, 2))
    r2 = E.handle_incoming_bid(con, save, oid2, "counter", counter_fee=round(budget * 1.05, 2),
                               rng=random.Random(2))
    con.commit()
    o2 = con.execute("SELECT status FROM offers WHERE id=?", (oid2,)).fetchone()
    new2 = con.execute("""SELECT fee FROM offers WHERE from_id=? AND status='incoming' AND id!=?
        ORDER BY id DESC LIMIT 1""", (cid, oid2)).fetchone()
    assert r2.get("ok") == "counter", f"expected counter, got: {r2}"
    assert o2["status"] == "countered"
    assert new2 and new2["fee"] <= budget + 0.01, f"buyer countered above its own budget: {new2}"
    pnow = con.execute("SELECT club_id FROM players WHERE id=?", (vrow["id"],)).fetchone()
    assert pnow["club_id"] == cid
    ok(f"counter at 105% of buyer budget → countered back at {new2['fee']}m (≤ budget {budget}m)")

    # 1c. counter within the buyer's means — accepted at that fee
    oid3 = incoming_offer(con, save, vrow["id"], buyer["id"], round(budget, 2))
    r3 = E.handle_incoming_bid(con, save, oid3, "counter", counter_fee=round(v * 0.4, 2),
                               rng=random.Random(3))
    con.commit()
    assert r3.get("ok") is True, f"sanity counter was not accepted: {r3}"
    pnow = con.execute("SELECT club_id FROM players WHERE id=?", (vrow["id"],)).fetchone()
    b_after = con.execute("SELECT transfer_budget FROM clubs WHERE id=?", (buyer["id"],)).fetchone()
    assert pnow["club_id"] == buyer["id"], "within-means counter did not close the deal"
    assert b_after["transfer_budget"] >= -0.01, f"buyer budget went negative: {b_after}"
    ok(f"counter within the buyer's means accepted at {v * 0.4:.1f}m — buyer budget intact")
    con.close()

    # =====================================================================
    
    con = fresh_world("m2")
    save = make_career(con)
    cid = save["club_id"]
    assert E.window_state(E.d(save["date"]), save["season"]) == "summer"
    src = con.execute("""SELECT * FROM players p JOIN clubs c ON c.id=p.club_id
        WHERE p.squad='First Team' AND p.ca BETWEEN 10 AND 14 AND c.tier<=2
        ORDER BY p.ca DESC LIMIT 1""").fetchone()
    # buy the player directly (in-window purchase)
    con.execute("DELETE FROM transfers WHERE player_id=?", (src["id"],))
    con.execute("UPDATE players SET club_id=? WHERE id=?", (cid, src["id"]))
    con.execute("""INSERT INTO transfers (player_id,from_id,to_id,fee,wage,date,season,ctype,addons,clause,loan_end,split)
        VALUES (?,?,?,?,?,?,?, 'transfer','{}',0,NULL,0)""",
        (src["id"], src["club_id"], cid, 5.0, 1.0, save["date"], save["season"]))
    con.commit()
    assert E.transfer_locked(con, save, src["id"]) is True, "in-window purchase not locked"
    ok("player bought in the open window is transfer-locked")

    r = E.list_player(con, save, src["id"])
    assert r.get("ok") is False and "not for sale" in r.get("msg", ""), f"listing not blocked: {r}"
    ok(f"listing blocked: {r['msg']}")

    r = E.would_sell(con, save, cid, src["id"], 1000.0, random.Random(4))
    assert r[0] == "reject" and "window" in r[2], f"would_sell not locked: {r}"
    ok("the seller AI refuses to sell him this window (even at €1bn)")

    buyer = con.execute("SELECT * FROM clubs WHERE rep>=85 AND id!=? ORDER BY rep DESC LIMIT 1",
                        (cid,)).fetchone()
    oid = incoming_offer(con, save, src["id"], buyer["id"], 10.0)
    r = E.handle_incoming_bid(con, save, oid, "accept", rng=random.Random(5))
    con.commit()
    pnow = con.execute("SELECT club_id FROM players WHERE id=?", (src["id"],)).fetchone()
    assert r.get("ok") is False and pnow["club_id"] == cid, f"locked player sold: {r}"
    ok("incoming bid for the locked player cannot be accepted")

    # after the window closes, the same player can be listed
    save["date"] = "2026-10-01"
    assert E.transfer_locked(con, save, src["id"]) is False
    r = E.list_player(con, save, src["id"])
    assert r is True, f"listing after window close should work: {r}"
    con.execute("UPDATE players SET listed=0 WHERE id=?", (src["id"],))
    con.commit()
    ok("after the window closes the player can be listed again")
    con.close()

    # =====================================================================
    print("[3] recently flipped players are discounted by buyers")
    con = fresh_world("m3")
    save = make_career(con)
    cid = save["club_id"]
    p2 = con.execute("""SELECT * FROM players p JOIN clubs c ON c.id=p.club_id
        WHERE p.squad='First Team' AND p.ca BETWEEN 12 AND 16 AND p.value > 2
        ORDER BY p.ca DESC LIMIT 1""").fetchone()
    seller_id = p2["club_id"]
    big = con.execute("SELECT * FROM clubs WHERE rep>=90 AND id!=? AND id!=? ORDER BY rep DESC LIMIT 1",
                      (cid, seller_id)).fetchone()
    v2 = float(p2["value"])
    con.execute("DELETE FROM transfers WHERE player_id=?", (p2["id"],))
    con.execute("""INSERT INTO transfers (player_id,from_id,to_id,fee,wage,date,season,ctype,addons,clause,loan_end,split)
        VALUES (?,?,?,?,?,?,?, 'transfer','{}',0,NULL,0)""",
        (p2["id"], seller_id, seller_id, 4.0, 1.0, "2026-06-16", save["season"]))
    con.commit()
    fee = round(v2 * 1.3, 2)  # above the flipped ceiling (1.45*0.85=1.23x), under full value
    dec_recent, counter_recent, note_recent = E.would_buy(con, save, big["id"], p2["id"], fee,
                                                          random.Random(7))
    con.execute("UPDATE transfers SET date='2025-12-01' WHERE player_id=?", (p2["id"],))
    dec_old, counter_old, note_old = E.would_buy(con, save, big["id"], p2["id"], fee,
                                                 random.Random(7))
    con.commit()
    assert dec_recent == "counter", f"flipped player: expected counter, got {dec_recent} ({note_recent})"
    assert dec_old == "accept", f"old purchase: expected accept, got {dec_old} ({note_old})"
    assert counter_recent <= v2 * 1.45 * 0.85 * 1.01
    ok(f"same price {fee}m: recently flipped → counter at {counter_recent}m; bought last year → accepted")
    con.close()

    # =====================================================================
    print("[4] outgoing counters: budget check + final round")
    con = fresh_world("m4")
    save = make_career(con)
    cid = save["club_id"]
    c0 = E.club(con, cid)
    target = con.execute("""SELECT * FROM players p JOIN clubs c ON c.id=p.club_id
        WHERE p.squad='First Team' AND c.id!=? AND p.ca BETWEEN 11 AND 15
        AND CAST(substr(p.contract_end,1,4) AS INTEGER)-2026>=4
        ORDER BY p.ca DESC LIMIT 1""", (cid,)).fetchone()
    seller_id = target["club_id"]
    # a live counter on the table from the seller
    oid = con.execute("SELECT COALESCE(MAX(id),0)+1 FROM offers").fetchone()[0]
    con.execute("""INSERT INTO offers (id,player_id,from_id,to_id,fee,addons,wage,status,date,round,
        clause,is_loan,loan_end,split,human,note) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,?)""",
        (oid, target["id"], seller_id, cid, 5.0, "{}", 1.0, "counter", save["date"], 1,
         0, 0, None, 0, "Squad Rotation"))
    con.commit()
    # 4a. a counter above the budget is refused before it is even sent
    r = E.respond_counter(con, save, oid, accept=False, new_fee=round(c0["transfer_budget"] * 2 + 100, 2),
                          rng=random.Random(8))
    con.commit()
    o = con.execute("SELECT status FROM offers WHERE id=?", (oid,)).fetchone()
    assert r.get("ok") is False and "budget" in r.get("msg", ""), f"budget check failed: {r}"
    assert o["status"] == "withdrawn"
    ok(f"counter above the transfer budget refused: {r['msg']}")

    # 4b. final round: seller's last word ends the negotiation
    oid2 = con.execute("SELECT COALESCE(MAX(id),0)+1 FROM offers").fetchone()[0]
    con.execute("""INSERT INTO offers (id,player_id,from_id,to_id,fee,addons,wage,status,date,round,
        clause,is_loan,loan_end,split,human,note) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,?)""",
        (oid2, target["id"], seller_id, cid, 5.0, "{}", 1.0, "counter", save["date"], 3,
         0, 0, None, 0, "Squad Rotation"))
    con.commit()
    p_before = con.execute("SELECT club_id FROM players WHERE id=?", (target["id"],)).fetchone()
    r = E.respond_counter(con, save, oid2, accept=False, new_fee=round(float(target["value"]) * 0.3, 2),
                          rng=random.Random(9))
    con.commit()
    p_after = con.execute("SELECT club_id FROM players WHERE id=?", (target["id"],)).fetchone()
    assert r.get("ok") is False, f"final round should not produce another round-trip: {r}"
    assert p_after["club_id"] == p_before["club_id"], "player moved in a final-round counter"
    ok("final round: a below-their-number counter ends the talks (no fifth round)")
    con.close()

    # =====================================================================
    print("[5] outgoing hijack: a rival outbids you on a live deal")
    con = fresh_world("m5")
    save = make_career(con)
    cid = save["club_id"]
    t5 = con.execute("""SELECT * FROM players p JOIN clubs c ON c.id=p.club_id
        WHERE p.squad='First Team' AND c.id!=? AND c.rep BETWEEN 40 AND 75
        AND p.ca BETWEEN 12 AND 17 ORDER BY p.ca DESC LIMIT 1""", (cid,)).fetchone()
    seller_id = t5["club_id"]
    oid = con.execute("SELECT COALESCE(MAX(id),0)+1 FROM offers").fetchone()[0]
    con.execute("""INSERT INTO offers (id,player_id,from_id,to_id,fee,addons,wage,status,date,round,
        clause,is_loan,loan_end,split,human,note) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,?)""",
        (oid, t5["id"], seller_id, cid, 2.0, "{}", 1.0, "counter", save["date"], 1,
         0, 0, None, 0, "Squad Rotation"))
    con.commit()
    E._tick_offers(con, save, FakeRng(), [])
    con.commit()
    o = con.execute("SELECT * FROM offers WHERE id=?", (oid,)).fetchone()
    pnow = con.execute("SELECT * FROM players WHERE id=?", (t5["id"],)).fetchone()
    assert o["status"] == "hijacked", f"offer not hijacked: {o['status']}"
    assert pnow["club_id"] not in (seller_id, cid), "player did not move to the rival"
    tr = con.execute("""SELECT * FROM transfers WHERE player_id=? AND to_id=?
        ORDER BY date DESC LIMIT 1""", (t5["id"], pnow["club_id"])).fetchone()
    assert tr and tr["fee"] > 2.0 and tr["fee"] <= 2.0 * 1.3 + 0.01, f"bad hijack fee: {tr}"
    box = con.execute("""SELECT * FROM inbox WHERE cat='TRANSFER' AND priority='URGENT'
        AND subject LIKE 'Transfer hijacked%' ORDER BY id DESC LIMIT 1""").fetchone()
    assert box, "no URGENT hijack inbox message"
    news = con.execute("""SELECT * FROM news WHERE cat='TRANSFER' AND text LIKE '%hijack%'
        ORDER BY id DESC LIMIT 1""").fetchone()
    assert news, "no hijack news"
    ok(f"deal hijacked — {pnow['name']} signed by rival club {pnow['club_id']} at {tr['fee']}m (your bid was 2.0m)")
    con.close()

    # =====================================================================
    print("[6] incoming hijack: a bidding war on one of your players")
    con = fresh_world("m6")
    save = make_career(con)
    cid = save["club_id"]
    v6 = con.execute("""SELECT * FROM players WHERE club_id=? AND squad='First Team'
        ORDER BY value DESC LIMIT 1""", (cid,)).fetchone()
    b6 = con.execute("""SELECT * FROM clubs WHERE id!=? AND rep BETWEEN 70 AND 82
        AND transfer_budget > 10 ORDER BY rep DESC LIMIT 1""", (cid,)).fetchone()
    oid = incoming_offer(con, save, v6["id"], b6["id"], 5.0)
    E._tick_offers(con, save, FakeRng(), [])
    con.commit()
    o = con.execute("SELECT * FROM offers WHERE id=?", (oid,)).fetchone()
    assert o["status"] == "hijacked", f"original bid not superseded: {o['status']}"
    new6 = con.execute("""SELECT * FROM offers WHERE player_id=? AND from_id=?
        AND status='incoming' AND id!=? ORDER BY id DESC LIMIT 1""", (v6["id"], cid, oid)).fetchone()
    assert new6, "no new higher bid arrived"
    rival = E.club(con, new6["to_id"])
    assert rival and rival["rep"] > b6["rep"], "the interloper is not a bigger club"
    assert new6["fee"] > 5.0 and new6["fee"] <= 5.0 * 1.35 + 0.01, f"bidding-war fee off: {new6['fee']}"
    box = con.execute("""SELECT * FROM inbox WHERE cat='BID' AND priority='URGENT'
        AND subject LIKE 'Bidding war%' ORDER BY id DESC LIMIT 1""").fetchone()
    assert box, "no bidding-war inbox message"
    ok(f"bidding war — {rival['name']} (rep {rival['rep']:.0f}) outbid {b6['name']} at {new6['fee']}m")
    con.close()

    # =====================================================================
    print("[7] trophy success: big players want to come to a winning club")
    con = fresh_world("m7")
    save = make_career(con)
    cid = save["club_id"]
    assert E.club_success(con, save) == 0, "a fresh club should have no success"
    ok("club_success = 0 for an unproven club")
    # make the club a success: a trophy this season + league leaders
    save["career"]["trophies"].append({"season": save["season"], "comp": "FA Cup", "type": "cup"})
    lg = con.execute("SELECT id FROM competitions WHERE code=?",
                     (E.club(con, cid)["league"],)).fetchone()
    con.execute("""UPDATE standings SET pos=1, pts=100 WHERE comp_id=? AND season=? AND club_id=?
        AND stage='league'""", (lg["id"], save["season"], cid))
    con.commit()
    assert E.club_success(con, save) >= 2, f"club_success should be >=2, got {E.club_success(con, save)}"
    events = []
    E._trophy_player_interest(con, save, FakeRng(), events)
    con.commit()
    enq = con.execute("""SELECT o.*, p.name, p.ca, p.pos, c.name c FROM offers o
        JOIN players p ON p.id=o.player_id JOIN clubs c ON c.id=p.club_id
        WHERE o.status='interested' AND o.to_id=?""", (cid,)).fetchone()
    assert enq, "no transfer enquiry arrived for a successful club"
    assert enq["ca"] >= 16 and enq["c"] != E.club(con, cid)["name"]
    box = con.execute("""SELECT * FROM inbox WHERE cat='TRANSFER' AND priority='URGENT'
        AND subject LIKE 'Transfer enquiry%' ORDER BY id DESC LIMIT 1""").fetchone()
    assert box and enq["name"] in box["body"], "no URGENT enquiry inbox message"
    ok(f"enquiry: {enq['name']} ({enq['pos']}, CA {enq['ca']:.1f}) of {enq['c']} wants to join")
    # he wants to come: personal terms are a formality
    wins = 0
    for i in range(10):
        will, _note = E.player_willing(con, save, enq["id"], float(enq["wage"]) * 1.3 if enq["wage"] else 1.0,
                                       "Star Player", random.Random(100 + i))
        if will is not False:
            wins += 1
    assert wins >= 8, f"enquiring player should want the move (got {wins}/10 willing)"
    ok(f"the enquiring player accepts the terms {wins}/10 times (he wants the move)")
    con.close()

    print(f"\nMARKET TEST: ALL {PASS} PASS ✅")
    shutil.rmtree(TMP, ignore_errors=True)


if __name__ == "__main__":
    main()
