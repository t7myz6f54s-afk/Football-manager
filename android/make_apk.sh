#!/bin/sh
# Build the Touchline Android APK.
#
#   ./make_apk.sh            -> release/Touchline-1.5.0-arm64.apk
#
# Toolchain lives outside the workspace (/usr/local) so the repo stays lean.
# The game itself is NOT duplicated in git: fm/ is copied in here at build time.
set -e

export JAVA_HOME=/usr/local/jdk17
export ANDROID_HOME=/usr/local/android-sdk
export ANDROID_SDK_ROOT=/usr/local/android-sdk
export GRADLE_USER_HOME=/usr/local/gradle-home
export PATH="$JAVA_HOME/bin:/usr/local/gradle-8.9/bin:$PATH"

cd "$(dirname "$0")"
echo "sdk.dir=/usr/local/android-sdk" > local.properties

echo "[1/4] staging game files"
rm -rf app/src/main/python/fm app/src/main/assets/game
mkdir -p app/src/main/python app/src/main/assets
cp -r ../fm app/src/main/python/fm
rm -rf app/src/main/python/fm/static            # static ships as Android assets
find app/src/main/python -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true
cp -r ../fm/static app/src/main/assets/game
# pristine world database -> instant first launch & instant new careers on device
rm -f /tmp/world.seed.db /tmp/world.seed.db-wal /tmp/world.seed.db-shm
(cd .. && FM_DB=/tmp/world.seed.db PYTHONPATH=. python3 -c "from fm.world import build_world; build_world()")
cp /tmp/world.seed.db app/src/main/assets/game/world.seed.db
echo "      seed db: $(du -h app/src/main/assets/game/world.seed.db | cut -f1)"
echo "      python: $(find app/src/main/python -name '*.py' | wc -l) files"
echo "      assets: $(du -sh app/src/main/assets/game | cut -f1)"

echo "[2/4] gradle assembleDebug (downloads deps on first run)"
gradle --no-daemon --console=plain assembleDebug

echo "[3/4] collecting APK"
APK=app/build/outputs/apk/debug/app-debug.apk
test -f "$APK" || { echo "APK not found"; exit 1; }
mkdir -p ../release
cp "$APK" ../release/Touchline-1.5.0-arm64.apk
ls -lh ../release/Touchline-1.5.0-arm64.apk

echo "[4/4] verifying"
BT=/usr/local/android-sdk/build-tools/34.0.0
"$BT/aapt2" dump badging ../release/Touchline-1.5.0-arm64.apk | head -6 || true
unzip -l ../release/Touchline-1.5.0-arm64.apk | grep -cE "assets/game/|assets/chaquopy|lib/arm64-v8a" || true
echo "done"
