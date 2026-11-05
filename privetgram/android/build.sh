#!/usr/bin/env bash
# Build the Privetgram APK (official Telegram Android UI, via the teamgram-android fork).
#
#   ./build.sh /path/to/server_pkcs1.pub
#
# Needs: git, python3 + Pillow, openssl, JDK 17-21, Android SDK with
#   platforms;android-35  build-tools;35.0.0  ndk;21.4.7075529  cmake;3.10.2.4988404
# (ANDROID_HOME must point to it).
#
# Signing: set KEYSTORE, KEYSTORE_PASSWORD, KEY_ALIAS, KEY_PASSWORD to sign with your key
# (keep it — Android only installs updates signed with the same key).
# Without them the public dummy key from the upstream repo is used.
set -euo pipefail

PUBKEY=$(realpath "${1:?usage: build.sh server_pkcs1.pub}")
HERE=$(cd "$(dirname "$0")" && pwd)
COMMIT=340c24c4b5c54f1cce8736e47e0a1c72f64b1407   # teamgram-android, Telegram 12.5.1
WORK=${WORK:-$HERE/work}
OUT=${OUT:-$HERE/out}
: "${ANDROID_HOME:?set ANDROID_HOME to your Android SDK}"

rm -rf "$WORK/teamgram-android"
mkdir -p "$WORK/teamgram-android" "$OUT"
cd "$WORK/teamgram-android"
git init -q
git remote add origin https://github.com/teamgram/teamgram-android.git
git fetch -q --depth 1 origin "$COMMIT"
git checkout -q FETCH_HEAD

python3 "$HERE/apply.py" . "$PUBKEY" --name "${APP_NAME:-Privetgram}" --package "${APP_PACKAGE:-org.privetgram.messenger}"

if [ -n "${KEYSTORE:-}" ]; then
  cp "$KEYSTORE" TMessagesProj/config/release.keystore
  sed -i "s/^RELEASE_KEY_PASSWORD=.*/RELEASE_KEY_PASSWORD=${KEY_PASSWORD}/; s/^RELEASE_KEY_ALIAS=.*/RELEASE_KEY_ALIAS=${KEY_ALIAS}/; s/^RELEASE_STORE_PASSWORD=.*/RELEASE_STORE_PASSWORD=${KEYSTORE_PASSWORD}/" gradle.properties
fi

echo "sdk.dir=$ANDROID_HOME" > local.properties
./gradlew --no-daemon :TMessagesProj_App:assembleAfatRelease

APK=$(find TMessagesProj_App/build/outputs/apk/afat/release -name '*.apk' | head -1)
cp "$APK" "$OUT/Privetgram.apk"
echo "APK: $OUT/Privetgram.apk"
