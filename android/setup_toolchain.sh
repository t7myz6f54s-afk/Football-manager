#!/bin/sh
# One-shot toolchain installer for the Touchline Android build.
# Installs JDK 17, Gradle 8.9 and Android SDK (platform 34 + build-tools 34.0.0)
# into /usr/local, matching the paths make_apk.sh expects.
#
#   sudo not required if /usr/local is writable. Run once per fresh machine:
#     sh android/setup_toolchain.sh
set -e

PREFIX=/usr/local
mkdir -p "$PREFIX"

# make sure the fresh JDK17 is the one on PATH for sdkmanager/gradle
if [ -d "$PREFIX/jdk17" ]; then
  export JAVA_HOME="$PREFIX/jdk17"
  export PATH="$JAVA_HOME/bin:$PATH"
fi

echo "[1/3] Temurin JDK 17"
if [ ! -x "$PREFIX/jdk17/bin/java" ]; then
  curl -sL -o /tmp/jdk17.tar.gz \
    "https://api.adoptium.net/v3/binary/latest/17/ga/linux/x64/jdk/hotspot/normal/eclipse"
  tar -xzf /tmp/jdk17.tar.gz -C "$PREFIX"
  ln -sfn "$PREFIX"/jdk-17* "$PREFIX/jdk17"
  rm -f /tmp/jdk17.tar.gz
fi
"$PREFIX/jdk17/bin/java" -version

echo "[2/3] Gradle 8.9"
if [ ! -x "$PREFIX/gradle-8.9/bin/gradle" ]; then
  curl -sL -o /tmp/gradle.zip "https://services.gradle.org/distributions/gradle-8.9-bin.zip"
  unzip -q -o /tmp/gradle.zip -d "$PREFIX"
  rm -f /tmp/gradle.zip
fi
"$PREFIX/gradle-8.9/bin/gradle" --version | head -3

echo "[3/3] Android SDK (cmdline-tools, platform 34, build-tools 34.0.0)"
mkdir -p "$PREFIX/android-sdk/cmdline-tools"
if [ ! -x "$PREFIX/android-sdk/cmdline-tools/latest/bin/sdkmanager" ]; then
  curl -sL -o /tmp/clt.zip \
    "https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip"
  unzip -q -o /tmp/clt.zip -d /tmp/clt
  mv /tmp/clt/cmdline-tools "$PREFIX/android-sdk/cmdline-tools/latest"
  rm -rf /tmp/clt /tmp/clt.zip
fi
yes | "$PREFIX/android-sdk/cmdline-tools/latest/bin/sdkmanager" --sdk_root="$PREFIX/android-sdk" --licenses > /dev/null 2>&1 || true
"$PREFIX/android-sdk/cmdline-tools/latest/bin/sdkmanager" --sdk_root="$PREFIX/android-sdk" \
  "platforms;android-34" "build-tools;34.0.0" "platform-tools" > /dev/null

echo "toolchain ready:"
echo "  java:   $PREFIX/jdk17"
echo "  gradle: $PREFIX/gradle-8.9"
echo "  sdk:    $PREFIX/android-sdk"
echo "next: cd android && ./make_apk.sh"
