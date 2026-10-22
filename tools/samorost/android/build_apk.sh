#!/bin/sh
# Build the native «Остров-пень» Android app (landscape, full screen, drawn on a Canvas: no WebView).
# usage: ANDROID_SDK=<sdk dir> tools/samorost/android/build_apk.sh <gameBuildDir> [assetsDir]
# <gameBuildDir> is a game build made by tools/samorost/game/build.sh (parts, iparts, soundtrack.wav);
# the assets are exported from it into [assetsDir] (default: a temp dir) by export/export_assets.py.
# Needs: Android SDK platform android-34 and build-tools 34.0.0, a JDK, Node with Playwright, Python with Pillow/numpy, ffmpeg.
# Signs with tools/samorost/android/release.keystore (created on first run). KEEP=1 keeps the work dir.
set -e
here=$(cd "$(dirname "$0")" && pwd)
root=$(cd "$here/../../.." && pwd)
sdk=${ANDROID_SDK:?set ANDROID_SDK to the Android SDK directory}
build=${1:?game build dir}
bt="$sdk/build-tools/34.0.0"
jar="$sdk/platforms/android-34/android.jar"
work=$(mktemp -d)
assets=${2:-$work/assets}
out="$root/art/samorost/game/ostrov-pen.apk"
mkdir -p "$assets" "$work/res/mipmap-xxxhdpi" "$work/res/mipmap-xxhdpi" "$work/res/mipmap-xhdpi" "$work/res/mipmap-hdpi" "$work/res/mipmap-mdpi" "$work/gen" "$work/classes" "$work/dex"

[ -f "$assets/scene.json" ] || python3 "$here/export/export_assets.py" "$build" "$root" "$assets"

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
# sounds stay uncompressed so SoundPool and MediaPlayer can read them straight from the APK
"$bt/aapt2" link -o "$work/base.apk" -I "$jar" --manifest "$here/AndroidManifest.xml" -A "$assets" \
  --min-sdk-version 21 --target-sdk-version 34 --java "$work/gen" -0 ogg -0 wav -0 webp -0 png "$work/res.zip"
javac -source 11 -target 11 -nowarn -classpath "$jar" -d "$work/classes" $(find "$here/src" "$work/gen" -name '*.java') 2>&1 | grep -v 'bootstrap classpath\|^warning\|^1 warning\|^Note:' || true
"$bt/d8" --lib "$jar" --min-api 21 --output "$work/dex" $(find "$work/classes" -name '*.class')
cp "$work/base.apk" "$work/unsigned.apk"
(cd "$work/dex" && zip -q "$work/unsigned.apk" classes.dex)
"$bt/zipalign" -f -p 4 "$work/unsigned.apk" "$work/aligned.apk"
ks="$here/release.keystore"
[ -f "$ks" ] || keytool -genkeypair -keystore "$ks" -storepass ostrovpen -keypass ostrovpen -alias ostrovpen \
  -keyalg RSA -keysize 2048 -validity 10000 -dname "CN=Ostrov-pen" >/dev/null 2>&1
"$bt/apksigner" sign --ks "$ks" --ks-pass pass:ostrovpen --key-pass pass:ostrovpen --out "$out" "$work/aligned.apk"
"$bt/apksigner" verify "$out"
if [ -n "$KEEP" ]; then echo "work dir: $work"; else rm -rf "$work"; fi
ls -la "$out"
