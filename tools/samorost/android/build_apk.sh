#!/bin/sh
# Package the «Остров-пень» game page into an Android APK (landscape, full screen WebView).
# usage: ANDROID_SDK=<sdk dir> tools/samorost/android/build_apk.sh
# Needs: Android SDK platform android-34 and build-tools 34.0.0, a JDK, Python with Pillow.
# Signs with tools/samorost/android/release.keystore (created on first run).
set -e
here=$(cd "$(dirname "$0")" && pwd)
root=$(cd "$here/../../.." && pwd)
sdk=${ANDROID_SDK:?set ANDROID_SDK to the Android SDK directory}
bt="$sdk/build-tools/34.0.0"
jar="$sdk/platforms/android-34/android.jar"
work=$(mktemp -d)
out="$root/art/samorost/game/ostrov-pen.apk"
mkdir -p "$work/assets" "$work/res/mipmap-xxxhdpi" "$work/res/mipmap-xxhdpi" "$work/res/mipmap-xhdpi" "$work/res/mipmap-hdpi" "$work/res/mipmap-mdpi" "$work/gen" "$work/classes" "$work/dex"

# the game page as a full HTML document
{ printf '<!doctype html>\n<html lang="ru"><head><meta charset="utf-8">\n<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no,viewport-fit=cover">\n'
  cat "$root/art/samorost/game/ostrov-pen.html"; printf '\n</html>\n'; } > "$work/assets/index.html"

# launcher icon cut from the painting: the gnome in front of the stump house
python3 - "$root/art/samorost/samorost.png" "$work/res" <<'PY'
import sys
from PIL import Image, ImageDraw
src, res = sys.argv[1], sys.argv[2]
im = Image.open(src).convert('RGB').crop((450, 340, 850, 740))
for d, s in (('xxxhdpi', 192), ('xxhdpi', 144), ('xhdpi', 96), ('hdpi', 72), ('mdpi', 48)):
    ic = im.resize((s, s), Image.LANCZOS).convert('RGBA')
    m = Image.new('L', (s, s), 0); ImageDraw.Draw(m).rounded_rectangle((0, 0, s - 1, s - 1), radius=s // 5, fill=255)
    ic.putalpha(m); ic.save(f'{res}/mipmap-{d}/ic_launcher.png')
PY

"$bt/aapt2" compile --dir "$work/res" -o "$work/res.zip"
"$bt/aapt2" link -o "$work/base.apk" -I "$jar" --manifest "$here/AndroidManifest.xml" -A "$work/assets" \
  --min-sdk-version 21 --target-sdk-version 34 --java "$work/gen" -0 html "$work/res.zip"
javac -source 11 -target 11 -nowarn -classpath "$jar" -d "$work/classes" $(find "$here/src" "$work/gen" -name '*.java') 2>&1 | grep -v 'bootstrap classpath\|^warning\|^1 warning' || true
"$bt/d8" --lib "$jar" --min-api 21 --output "$work/dex" $(find "$work/classes" -name '*.class')
(cd "$work/dex" && zip -q "$work/base.apk" classes.dex)
"$bt/zipalign" -f -p 4 "$work/base.apk" "$work/aligned.apk"
ks="$here/release.keystore"
[ -f "$ks" ] || keytool -genkeypair -keystore "$ks" -storepass ostrovpen -keypass ostrovpen -alias ostrovpen \
  -keyalg RSA -keysize 2048 -validity 10000 -dname "CN=Ostrov-pen" >/dev/null 2>&1
"$bt/apksigner" sign --ks "$ks" --ks-pass pass:ostrovpen --key-pass pass:ostrovpen --out "$out" "$work/aligned.apk"
"$bt/apksigner" verify "$out"
rm -rf "$work"
ls -la "$out"
