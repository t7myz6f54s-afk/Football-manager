"""Match Day Live+ — black-box API test.

Boots a real server on a temp DB, creates a career, plays a match in LIVE mode:
step chunks -> half-time (talk) -> second half with touchline instruction and a
live substitution -> full-time result written.
"""
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import urllib.request

PORT = 8222
BASE = f"http://127.0.0.1:{PORT}"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP = "/tmp/fmlive_test"


def req(method, path, body=None):
    data = json.dumps(body or {}).encode() if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, method=method,
                               headers={"Content-Type": "application/json"} if data else {})
    with urllib.request.urlopen(r, timeout=180) as resp:
        return json.loads(resp.read().decode())


def main():
    shutil.rmtree(TMP, ignore_errors=True)
    os.makedirs(TMP + "/saves", exist_ok=True)
    env = dict(os.environ,
               FM_DB=TMP + "/world.db", FM_SAVE_DIR=TMP + "/saves",
               FM_SAVE=TMP + "/saves/career1.json", FM_STATIC=os.path.join(ROOT, "fm/static"),
               PORT=str(PORT), FM_HOST="127.0.0.1", PYTHONPATH=ROOT)
    proc = subprocess.Popen([sys.executable, os.path.join(ROOT, "fm/app.py")], env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    try:
        for _ in range(120):
            try:
                req("GET", "/api/boot")
                break
            except Exception:
                time.sleep(0.5)
        else:
            raise SystemExit("server did not boot")

        # --- create a career ---
        search = req("GET", "/api/clubs/search?q=Arsenal")
        club = (search.get("results") or search.get("clubs") or search)[0]
        made = req("POST", "/api/career/new", {
            "club_code": club["code"], "difficulty": "normal",
            "manager": {"name": "Live Tester", "nat": "England", "age": 40,
                        "reputation": 60, "style": "balanced", "attrs": {}}})
        assert made.get("ok") is not False, f"career create failed: {made}"
        print("PASS: career created")

        # --- kick off live match ---
        play = req("POST", "/api/match/play", {"mode": "full"})
        assert play.get("ok") and play.get("live"), f"play failed: {play}"
        st = play["state"]
        assert "momentum" in st and "orders" in st and st["subs_left"] == 5, f"bad live state: {list(st)}"
        assert len(st["orders"]) == 6, "order catalogue incomplete"
        assert st["xi"] and st["bench"], "no xi/bench in live state"
        print(f"PASS: live match started ({st['home_name']} v {st['away_name']}), momentum={st['momentum']}")

        # --- step through the first half ---
        steps, ev_i, halftime = 0, 0, None
        while True:
            j = req("POST", "/api/match/live_step", {"mode": "fast", "ev_i": ev_i})
            assert j.get("ok"), f"live_step failed: {j}"
            if j.get("result"):
                raise SystemExit("match ended before half-time?! " + json.dumps(j)[:200])
            st = j["state"]
            ev_i = st["ev_i"]
            assert 0 <= st["momentum"] <= 100
            steps += 1
            if st.get("halftime_state"):
                halftime = st["halftime_state"]
                break
            assert steps < 40, "first half never ended"
        assert halftime["minute"] == 45 and "talks" in halftime
        print(f"PASS: first half played in {steps} steps, "
              f"score {halftime['score']['home']}-{halftime['score']['away']}")

        # --- half-time: team talk, back out for the second half ---
        ht = req("POST", "/api/match/halftime", {"talk": "firm", "subs": []})
        assert ht.get("ok") and ht.get("live") and ht["state"]["half"] == 2, f"HT resume failed: {ht}"
        st = ht["state"]
        print("PASS: second half kicked off live")

        # --- live touchline instruction ---
        ins = req("POST", "/api/match/instruction", {"order": "press_hard"})
        assert ins.get("ok"), f"instruction rejected: {ins}"
        assert ins["msg"], "no assistant reaction"
        ev_i = ins["state"]["ev_i"]
        print(f"PASS: instruction applied -> {ins['msg'][:60]}")
        # duplicate order must be refused
        ins2 = req("POST", "/api/match/instruction", {"order": "press_hard"})
        assert not ins2.get("ok"), "duplicate order should be refused"

        # --- live substitution ---
        st = ins["state"]
        off, on = st["xi"][0]["pid"], st["bench"][0]["pid"]
        sub = req("POST", "/api/match/sub", {"off": off, "on": on})
        assert sub.get("ok"), f"live sub failed: {sub}"
        assert sub["state"]["subs_left"] == 4
        ev_i = sub["state"]["ev_i"]
        print("PASS: live substitution made")

        # --- play out the second half ---
        steps = 0
        while True:
            j = req("POST", "/api/match/live_step", {"mode": "fast", "ev_i": ev_i})
            assert j.get("ok"), f"live_step failed: {j}"
            if j.get("result"):
                res = j["result"]
                break
            ev_i = j["state"]["ev_i"]
            steps += 1
            assert steps < 40, "second half never ended"
        kinds = {e["type"] for e in res.get("events", [])}
        assert "touchline" in kinds, f"touchline event missing from result: {kinds}"
        assert "sub" in kinds, "live sub event missing from result"
        print(f"PASS: full-time {res['hg']}-{res['ag']} ({res['home']} v {res['away']}), "
              f"events={len(res['events'])}")

        # --- world state updated, pending cleared ---
        boot = req("GET", "/api/boot")
        assert not boot.get("pending_match"), "pending match not cleared"
        state = req("GET", "/api/state")
        assert state.get("pending_match") is not None  # key exists
        print("PASS: pending match cleared, world updated")
        print("\nLIVE MATCH TEST: ALL PASS ✅")
    finally:
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    main()
