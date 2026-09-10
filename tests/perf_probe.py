"""Lightweight perf probe: measures the on-device hot paths through the real
HTTP API (same calls the WebView makes) on a temp DB.

Measures:
  - world build + boot
  - career creation
  - /api/continue  (the main "advance the world" tap)
  - /api/match/live_step (per-chunk live simulation during a full match)

Run:  python3 tests/perf_probe.py
"""
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request

PORT = 8333
BASE = f"http://127.0.0.1:{PORT}"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP = "/tmp/fmperf"


def req(method, path, body=None, timeout=300):
    t0 = time.time()
    data = json.dumps(body or {}).encode() if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, method=method,
                               headers={"Content-Type": "application/json"} if data else {})
    with urllib.request.urlopen(r, timeout=timeout) as resp:
        out = json.loads(resp.read().decode())
    return out, time.time() - t0


def pct(xs, p):
    xs = sorted(xs)
    if not xs:
        return 0.0
    k = (len(xs) - 1) * p / 100.0
    f = int(k)
    c = min(f + 1, len(xs) - 1)
    return xs[f] + (xs[c] - xs[f]) * (k - f)


def report(name, xs):
    if xs:
        print(f"  {name:14s} n={len(xs):3d}  p50={pct(xs,50)*1000:7.0f}ms  "
              f"p95={pct(xs,95)*1000:7.0f}ms  max={max(xs)*1000:7.0f}ms  "
              f"total={sum(xs):6.1f}s")


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
        boot, t_boot = None, None
        for _ in range(120):
            try:
                boot, t_boot = req("GET", "/api/boot")
                break
            except Exception:
                time.sleep(0.5)
        else:
            raise SystemExit("server did not boot")
        print(f"boot (incl. world build): {t_boot*1000:.0f}ms  clubs={boot.get('clubs')}")

        search, _ = req("GET", "/api/clubs/search?q=Arsenal")
        club = (search.get("results") or search.get("clubs") or search)[0]
        made, t_new = req("POST", "/api/career/new", {
            "club_code": club["code"], "difficulty": "normal",
            "manager": {"name": "Perf Probe", "nat": "England", "age": 40,
                        "reputation": 60, "style": "balanced", "attrs": {}}})
        assert made.get("ok") is not False, f"career create failed: {made}"
        print(f"career new (Arsenal): {t_new*1000:.0f}ms")

        # --- continue taps until a match is reached, then 10 more world advances ---
        cont = []
        for i in range(14):
            out, dt = req("POST", "/api/continue", {})
            cont.append(dt)
            if i == 9:
                print(f"  sample continue -> {out.get('stop_reason')} @ {out.get('date')}")
        report("continue", cont)

        # --- full live match: time every step ---
        play, t_play = req("POST", "/api/match/play", {"mode": "full"})
        if not play.get("ok"):
            print("no match to play:", play.get("msg"))
            return
        steps = [t_play]
        pm_state = play
        for _ in range(200):
            if pm_state.get("live_done"):
                break
            if not pm_state.get("live"):
                break
            out, dt = req("POST", "/api/match/live_step", {"mode": "full"})
            steps.append(dt)
            if out.get("halftime") and not out.get("live"):
                out, dt = req("POST", "/api/match/live_step", {"mode": "full"})  # resume 2H
                steps.append(dt)
            pm_state = out
        report("live_step", steps)
        print(f"  match final: {pm_state.get('score','')} live_done={pm_state.get('live_done')}")

        # --- screen payload cost (largest screens) ---
        screens = {}
        for name in ("home", "squad", "table", "stats", "transfers", "match"):
            try:
                _, dt = req("GET", f"/api/screen/{name}")
                screens[name] = dt
            except Exception:
                pass
        for n, dt in screens.items():
            print(f"  screen {n:10s} {dt*1000:7.0f}ms")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
        shutil.rmtree(TMP, ignore_errors=True)


if __name__ == "__main__":
    main()
