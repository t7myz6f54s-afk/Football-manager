"""Save slots — each slot is a self-contained career (world.db + career.json).

Up to MAX_SLOTS independent careers can coexist. Slot 1 keeps honouring the
legacy FM_DB / FM_SAVE environment variables (desktop runs, tests, older
launchers); all other slots live under <base>/slots/<id>/.

Registry (slots/registry.json): {"active": "slot1", "slots": {id: meta}}
"""
import json
import os

MAX_SLOTS = 3


def base_dir():
    b = os.environ.get("FM_DATA")
    if b:
        return b
    sd = os.environ.get("FM_SAVE_DIR")
    if sd:
        return os.path.dirname(sd) or "."
    return os.path.join(os.environ.get("FM_BASE", "/home/user"), "data")


def slots_dir():
    return os.path.join(base_dir(), "slots")


def registry_path():
    return os.path.join(slots_dir(), "registry.json")


def load_reg():
    try:
        with open(registry_path()) as f:
            r = json.load(f)
        if not isinstance(r.get("slots"), dict):
            r["slots"] = {}
    except Exception:
        r = {}
    r.setdefault("active", "slot1")
    r.setdefault("slots", {})
    return r


def save_reg(r):
    os.makedirs(slots_dir(), exist_ok=True)
    tmp = registry_path() + ".tmp"
    with open(tmp, "w") as f:
        json.dump(r, f)
    os.replace(tmp, registry_path())


def all_ids():
    r = load_reg()
    ids = set(r["slots"].keys())
    if os.path.isdir(slots_dir()):
        ids |= {d for d in os.listdir(slots_dir()) if d.startswith("slot")}
    return sorted(ids) or ["slot1"]


def active_id():
    r = load_reg()
    a = r.get("active")
    if a and os.path.isdir(os.path.join(slots_dir(), a)):
        return a
    if a and os.path.isdir(base_dir()) and a == "slot1":
        return a  # legacy slot1 (no directory of its own)
    return "slot1"


def paths(sid):
    """File paths for a slot. Slot 1 honours FM_DB / FM_SAVE overrides."""
    d = os.path.join(slots_dir(), sid)
    if sid == "slot1":
        db = os.environ.get("FM_DB") or os.path.join(d, "world.db")
        career = os.environ.get("FM_SAVE") or os.path.join(d, "career.json")
        if os.environ.get("FM_DB") and not os.environ.get("FM_DATA"):
            # pure-legacy desktop layout (run.sh): world.db next to saves/
            d = os.path.dirname(db)
        return {"dir": d, "db": db, "career": career}
    return {"dir": d, "db": os.path.join(d, "world.db"), "career": os.path.join(d, "career.json")}


def free_id(reg=None):
    r = reg or load_reg()
    taken = set(r["slots"].keys()) | (set(all_ids()) if os.path.isdir(slots_dir()) else set())
    for i in range(1, MAX_SLOTS + 1):
        sid = "slot%d" % i
        if sid not in taken:
            return sid
    return None


def meta(sid):
    """Quick summary of a slot for the UI (reads career.json header only)."""
    p = paths(sid)
    out = {"id": sid, "has_save": False, "db_exists": os.path.exists(p["db"]),
           "updated": None, "club": None, "season": None, "date": None, "size": 0}
    try:
        if os.path.exists(p["career"]):
            with open(p["career"]) as f:
                c = json.load(f)
            out["has_save"] = True
            out["date"] = c.get("date")
            out["season"] = c.get("season")
            car = c.get("career") or {}
            clubs = car.get("clubs") or []
            out["club"] = clubs[-1]["name"] if clubs else None
            mgr = car.get("manager")
            out["manager"] = mgr.get("name") if isinstance(mgr, dict) else None
            out["updated"] = c.get("saved_at")
        out["size"] = sum(os.path.getsize(os.path.join(p["dir"], f))
                          for f in (os.listdir(p["dir"]) if os.path.isdir(p["dir"]) else [])
                          if os.path.isfile(os.path.join(p["dir"], f)))
    except Exception:
        pass
    if not out["club"]:
        out["club"] = (load_reg()["slots"].get(sid) or {}).get("club")
    if not out["updated"]:
        out["updated"] = (load_reg()["slots"].get(sid) or {}).get("updated")
    return out


def summary():
    r = load_reg()
    act = r.get("active") or "slot1"
    slots = []
    free = None
    for i in range(1, MAX_SLOTS + 1):
        sid = "slot%d" % i
        m = dict(meta(sid), active=(sid == act))
        slots.append(m)
        if free is None and not m["has_save"]:
            free = sid
    return {"active": act, "slots": slots, "free": free,
            "max": MAX_SLOTS, "can_add": free is not None}


def set_active(sid):
    p = paths(sid)
    os.makedirs(p["dir"], exist_ok=True)
    r = load_reg()
    r["active"] = sid
    save_reg(r)
    return p


def record(sid, club=None):
    """Remember a human-friendly label for a slot after career events."""
    r = load_reg()
    cur = r["slots"].get(sid) or {}
    if club is not None:
        cur["club"] = club
    import datetime
    cur["updated"] = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M")
    r["slots"][sid] = cur
    save_reg(r)


def delete(sid, keep_if_active=True):
    act = active_id()
    if sid == act and keep_if_active:
        return False, "Switch to another slot first."
    r = load_reg()
    p = paths(sid)
    import shutil
    if os.path.isdir(p["dir"]):
        shutil.rmtree(p["dir"], ignore_errors=True)
    r["slots"].pop(sid, None)
    save_reg(r)
    return True, "Deleted."


def migrate_legacy():
    """One-time move of a pre-slots layout (data/world.db + career1.json) into slot1.

    Only runs when slots were never used (no slots dir) and a legacy world exists
    OUTSIDE of any slot directory.
    """
    if os.path.isdir(slots_dir()):
        return False
    legacy_candidates = [
        (os.environ.get("FM_DB"), os.environ.get("FM_SAVE")),
        (os.path.join(base_dir(), "world.db"), os.path.join(base_dir(), "saves", "career1.json")),
    ]
    for db, career in legacy_candidates:
        if not db or not career:
            continue
        if not (os.path.exists(db) and os.path.exists(career)):
            continue
        # never migrate a legacy path that IS slot1's resolved path already
        p1 = paths("slot1")
        if os.path.abspath(db) == os.path.abspath(p1["db"]):
            continue
        d = paths("slot1")["dir"]
        os.makedirs(d, exist_ok=True)
        import shutil
        shutil.copyfile(db, p1["db"])
        shutil.copyfile(career, p1["career"])
        return True
    return False
