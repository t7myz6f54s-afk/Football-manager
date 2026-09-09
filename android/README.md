# Touchline — Android build

The Android app is a **thin shell around the existing web game**. No game logic was
rewritten: the same `fm/` package runs inside the APK.

```
┌─────────────────────────────── APK ───────────────────────────────┐
│  MainActivity (WebView)                                           │
│    1. extracts assets/game  →  filesDir/www   (HTML/CSS/JS)       │
│    2. Chaquopy CPython 3.13 →  bootstrap.start(filesDir, www)     │
│    3. waits for GET /api/boot, then loads http://127.0.0.1:8000   │
│                                                                   │
│  bootstrap.py  →  fm.app.main()  (daemon thread, loopback only)   │
│  world.db + saves  →  filesDir/data  (app-private, persists)      │
└───────────────────────────────────────────────────────────────────┘
```

* **ABI:** `arm64-v8a` only (all modern phones). `minSdk 24`, `targetSdk 34`.
* **Offline:** no network access is needed. `INTERNET` permission exists only so the
  WebView can talk to the loopback server.
* **Persistence:** the world database and career save live in the app's private
  storage, so progress survives restarts and is removed on uninstall.
* **Size:** ~12 MB (CPython runtime + stdlib + game code + assets).

## Reproducing the build

The toolchain is deliberately *not* vendored into the repo. Install once, anywhere:

| Component | Version | Path used by `make_apk.sh` |
|---|---|---|
| JDK | Temurin 17 | `/usr/local/jdk17` |
| Gradle | 8.9 | `/usr/local/gradle-8.9` |
| Android SDK | platform 34 + build-tools 34.0.0 | `/usr/local/android-sdk` |
| Host Python | 3.13.x (must match app Python major.minor) | `/usr/local/bin/python3` |
| AGP / Chaquopy | 8.5.2 / 17.0.0 (both from Maven Central + Google) | — |

Then:

```sh
cd android && ./make_apk.sh
# -> ../release/Touchline-1.0-arm64.apk
```

`make_apk.sh` stages the game each run (copies `../fm/*.py` into
`app/src/main/python/fm/` and `../fm/static/` into `app/src/main/assets/game/`), so the
repo never holds a second copy of the game. Those staged directories are gitignored.

The APK is signed with the standard Android debug key. For Play Store distribution,
generate your own keystore and add a `signingConfigs.release` block — nothing else changes.

## Configuration hooks

`fm/app.py` reads its paths from the environment (defaults unchanged, so the desktop
server behaves exactly as before):

| Variable | Default | Android value |
|---|---|---|
| `FM_DB` | `data/world.db` | `filesDir/data/world.db` |
| `FM_SAVE_DIR` / `FM_SAVE` | `data/saves/…` | `filesDir/data/saves/…` (consumed by `fm/engine.py` too) |
| `FM_STATIC` | `fm/static` | `filesDir/www` |
| `FM_HOST` / `PORT` | `0.0.0.0` / `8000` | `127.0.0.1` / `8000` |
