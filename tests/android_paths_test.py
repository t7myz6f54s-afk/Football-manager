"""Device-faithful regression test: Android has a READ-ONLY root filesystem.

The APK once shipped a hardcoded `/home/user/data/saves` in fm/engine.py; on a
phone, new_career() then died with `[Errno 30] Read-only file system: '/home'`
while every Linux test passed (the path exists here). This test emulates the
phone: any write below /home raises EROFS, and the full boot -> new career ->
continue flow must still succeed using only the paths bootstrap provides.

Run:  python3 tests/android_paths_test.py
"""
import builtins
import errno
import json
import os
import shutil
import sys
import threading
import time
import urllib.request

ROOT = "/tmp/android_paths_test"
_real_makedirs = os.makedirs
_real_open = open


def _ro_guard(path, *a, **k):
    if str(path).startswith("/home"):
        raise OSError(errno.EROFS, "Read-only file system", str(path))
    return _real_makedirs(path, *a, **k)


def _ro_open(file, mode="r", *a, **k):
    if str(file).startswith("/home") and any(m in mode for m in ("w", "a", "x")):
        raise OSError(errno.EROFS, "Read-only file system", str(file))
    return _real_open(file, mode, *a, **k)


os.makedirs = _ro_guard
builtins.open = _ro_open
sys.dont_write_bytecode = True   # never let imports touch /home via __pycache__

shutil.rmtree(ROOT, ignore_errors=True)
FILES = os.path.join(ROOT, "files")
WWW = os.path.join(ROOT, "www")
os.makedirs(WWW)
shutil.copytree(os.path.join(os.path.dirname(__file__), "..", "fm", "static"), WWW,
                dirs_exist_ok=True)
# pristine seed, as the APK ships one
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["FM_DB"] = "/tmp/android_paths_test/seed.db"
from fm.world import build_world
build_world()
shutil.copyfile("/tmp/android_paths_test/seed.db", os.path.join(WWW, "world.seed.db"))
for v in ("FM_DB",):
    os.environ.pop(v, None)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "android",
                                "app", "src", "main", "python"))
import bootstrap
bootstrap.start(FILES, WWW, port=8019)

BASE = "http://127.0.0.1:8019"


def call(path, data=None):
    body = json.dumps(data).encode() if data is not None else None
    r = urllib.request.Request(BASE + path, data=body, method="POST" if body else "GET")
    if body:
        r.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(r, timeout=180) as resp:
        return resp.status, json.loads(resp.read() or b"{}")


for _ in range(100):
    try:
        if call("/api/boot")[0] == 200:
            break
    except Exception:
        time.sleep(0.3)

st, j = call("/api/career/new", {"club_code": "BAR",
                                 "manager": {"name": "Erofs Checker", "nat": "Spain"}})
assert st == 200 and j.get("ok"), f"career/new failed: {st} {str(j)[:200]}"
st, j = call("/api/continue", {})
assert st == 200, f"continue failed: {st} {str(j)[:200]}"
# slot-era layout (fm/slots.py): saves live under data/slots/<slotN>/career.json
assert os.path.exists(os.path.join(FILES, "data", "slots", "slot1", "career.json"))
assert not os.path.exists("/home/user/data/saves/career1.json.tmp")
print("android_paths_test: PASS — career created and advanced with /home read-only")
