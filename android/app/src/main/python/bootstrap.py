"""Chaquopy entry point — start the Touchline server inside the app.

The game code is unmodified: we only point its environment variables at the
app's private storage (writable) and bind the server to the loopback interface.
"""
import os
import threading
import traceback

_started = False
_lock = threading.Lock()


def start(files_dir, www_dir, port=8000):
    """Set up paths and launch the server thread. Safe to call more than once."""
    global _started
    with _lock:
        if _started:
            return False
        _started = True

    data = os.path.join(files_dir, "data")
    saves = os.path.join(data, "saves")
    os.makedirs(saves, exist_ok=True)

    # must be set before fm.world / fm.app are imported (they read env at import)
    db = os.path.join(data, "world.db")
    os.environ["FM_DB"] = db
    seed = os.path.join(www_dir, "world.seed.db")
    os.environ["FM_SEED_DB"] = seed
    # first launch: drop in the pristine world that ships in the assets
    if os.path.exists(seed) and not os.path.exists(db):
        import shutil
        shutil.copyfile(seed, db)
    os.environ["FM_SAVE_DIR"] = saves
    os.environ["FM_SAVE"] = os.path.join(saves, "career1.json")
    os.environ["FM_STATIC"] = www_dir
    os.environ["FM_HOST"] = "127.0.0.1"
    os.environ["PORT"] = str(port)
    os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")

    threading.Thread(target=_run, name="touchline-server", daemon=True).start()
    return True


def _run():
    try:
        from fm import app as fmapp
        fmapp.main()
    except Exception:
        traceback.print_exc()


def status():
    return {"started": _started,
            "db": os.environ.get("FM_DB"),
            "static": os.environ.get("FM_STATIC"),
            "host": os.environ.get("FM_HOST"),
            "port": os.environ.get("PORT")}
