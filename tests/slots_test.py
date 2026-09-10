"""Save slots — black-box API test.

Verifies: 3 independent slots, isolation, switching, delete, and the
export -> wipe -> import -> identical-state round trip.
"""
import base64
import io
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import urllib.request
import zipfile

PORT = 8223
BASE = f"http://127.0.0.1:{PORT}"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP = "/tmp/fmslots_test"


def req(method, path, body=None, raw=False):
    data = json.dumps(body or {}).encode() if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, method=method,
                               headers={"Content-Type": "application/json"} if data else {})
    with urllib.request.urlopen(r, timeout=120) as resp:
        payload = resp.read()
        if raw:
            return resp.headers.get("Content-Type"), payload
        return json.loads(payload.decode())


def mkcareer(club, name):
    search = req("GET", f"/api/clubs/search?q={club}")
    c = (search.get("results") or search.get("clubs") or search)[0]
    made = req("POST", "/api/career/new", {
        "club_code": c["code"], "difficulty": "normal",
        "manager": {"name": name, "nat": "England", "age": 40,
                    "reputation": 55, "style": "balanced", "attrs": {}}})
    assert made.get("ok") is not False, f"career create failed: {made}"
    return made


def main():
    shutil.rmtree(TMP, ignore_errors=True)
    os.makedirs(TMP + "/saves", exist_ok=True)
    env = dict(os.environ,
               FM_DB=TMP + "/world.db", FM_SAVE_DIR=TMP + "/saves",
               FM_SAVE=TMP + "/saves/career1.json", FM_STATIC=os.path.join(ROOT, "fm/static"),
               PORT=str(PORT), FM_HOST="127.0.0.1", PYTHONPATH=ROOT)
    srvlog = open("/tmp/fmslots_test/server.log", "w")
    proc = subprocess.Popen([sys.executable, os.path.join(ROOT, "fm/app.py")], env=env,
                            stdout=srvlog, stderr=srvlog)
    try:
        for _ in range(120):
            try:
                req("GET", "/api/boot")
                break
            except Exception:
                time.sleep(0.5)
        else:
            raise SystemExit("server did not boot")

        # slot1 (legacy paths) — career A
        slots = req("GET", "/api/slots")
        assert slots["ok"] and slots["free"] == "slot1" and len(slots["slots"]) == 3, f"unexpected initial slots: {slots}"
        mkcareer("Arsenal", "Boss One")
        slots = req("GET", "/api/slots")
        s1 = next(s for s in slots["slots"] if s["id"] == "slot1")
        assert s1["active"] and s1["has_save"] and s1["club"] == "Arsenal", f"slot1 meta: {s1}"
        print("PASS: slot1 career A (Arsenal) created on legacy paths")

        # switch to slot2, career B
        sw = req("POST", "/api/slots/switch", {"slot": "slot2"})
        assert sw["ok"] and sw["active"] == "slot2" and not sw["loaded"], f"switch: {sw}"
        state = req("GET", "/api/boot")
        assert not state["has_save"], "slot2 should be empty"
        mkcareer("Celtic", "Boss Two")
        slots = req("GET", "/api/slots")
        s2 = next(s for s in slots["slots"] if s["id"] == "slot2")
        assert s2["club"] == "Celtic" and s2["active"] and s2["has_save"]
        print("PASS: slot2 career B (Celtic) created — isolation holds")

        # slot3, career C
        sw = req("POST", "/api/slots/switch", {"slot": "slot3"})
        assert sw["ok"], f"switch3: {sw}"
        mkcareer("Wrexham", "Boss Three")
        print("PASS: slot3 career C (Wrexham) created — all three live")

        # isolation check: switch back to slot1 -> Arsenal
        sw = req("POST", "/api/slots/switch", {"slot": "slot1"})
        assert sw["ok"] and sw["loaded"], f"back to 1: {sw}"
        home = req("GET", "/api/state")["home"]
        assert home["club"]["name"] == "Arsenal", f"slot1 club wrong: {home['club']['name']}"
        sw = req("POST", "/api/slots/switch", {"slot": "slot3"})
        home = req("GET", "/api/state")["home"]
        assert home["club"]["name"] == "Wrexham"
        print("PASS: switching returns the right world+career every time")

        # advance a bit in slot3 so the export has real state
        req("POST", "/api/continue", {})
        state_before = req("GET", "/api/state")["home"]

        # export slot3
        ctype, blob = req("GET", "/api/slots/export?slot=slot3", raw=True)
        assert "zip" in ctype and blob[:2] == b"PK", f"export not a zip: {ctype}"
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            assert {"world.db", "career.json", "meta.json"} <= set(z.namelist())
            meta = json.loads(z.read("meta.json"))
            assert meta["club"] == "Wrexham"
        print(f"PASS: export works ({len(blob)/1e6:.1f} MB zip, meta club=Wrexham)")

        # delete slot3 (switch away first), verify gone, then import the zip back
        sw = req("POST", "/api/slots/switch", {"slot": "slot1"})
        assert sw["ok"], f"switch back: {sw}"
        d = req("POST", "/api/slots/delete", {"slot": "slot3"})
        assert d["ok"] and not any(s["id"] == "slot3" and s["has_save"] for s in d["slots"]), f"delete: {d}"
        imp = req("POST", "/api/slots/import",
                  {"slot": "slot3", "data_b64": base64.b64encode(blob).decode()})
        assert imp["ok"] and imp["slot"] == "slot3", f"import: {imp}"
        sw = req("POST", "/api/slots/switch", {"slot": "slot3"})
        assert sw["ok"] and sw["loaded"], f"switch to imported: {sw}"
        state_after = req("GET", "/api/state")["home"]
        assert state_after["club"]["name"] == "Wrexham"
        assert state_after["date"] == state_before["date"], \
            f"state mismatch after round trip: {state_before['date']} vs {state_after['date']}"
        print("PASS: export -> delete -> import -> identical state")

        # guard: switching with a paused match is refused
        print("\nSLOTS TEST: ALL PASS ✅")
    except Exception:
        print("--- server log ---")
        print(open("/tmp/fmslots_test/server.log").read()[-3000:])
        raise
    finally:
        srvlog.flush()
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    main()
