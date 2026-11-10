#!/usr/bin/env bash
# Builds out/otryad-na-mostu.apk without Gradle: aapt2 + javac + d8 + zipalign + apksigner.
set -euo pipefail
cd "$(dirname "$0")"
SDK=${ANDROID_HOME:-/opt/android}
BT=$SDK/build-tools/35.0.0
JAR=$SDK/platforms/android-34/android.jar
OUT=out; rm -rf $OUT/tmp; mkdir -p $OUT/tmp/res $OUT/tmp/classes $OUT/tmp/dex
# web build -> assets
cp ../web/dist/index.html assets/index.html
$BT/aapt2 compile --dir res -o $OUT/tmp/res
$BT/aapt2 link -o $OUT/tmp/base.apk -I $JAR --manifest AndroidManifest.xml -A assets $OUT/tmp/res/*.flat --java $OUT/tmp/gen --auto-add-overlay
javac -source 8 -target 8 -Xlint:-options -bootclasspath $JAR -classpath $JAR -d $OUT/tmp/classes $(find src $OUT/tmp/gen -name '*.java')
$BT/d8 --release --min-api 24 --lib $JAR --output $OUT/tmp/dex $(find $OUT/tmp/classes -name '*.class')
cp $OUT/tmp/base.apk $OUT/tmp/unsigned.apk
(cd $OUT/tmp/dex && zip -q ../unsigned.apk classes.dex)
$BT/zipalign -f -p 4 $OUT/tmp/unsigned.apk $OUT/tmp/aligned.apk
KS=${KEYSTORE:-release.keystore}
if [ ! -f "$KS" ]; then
  keytool -genkeypair -keystore "$KS" -alias bridgesquad -keyalg RSA -keysize 2048 -validity 10000 \
    -storepass bridgesquad -keypass bridgesquad -dname "CN=Bridge Squad" >/dev/null 2>&1
fi
$BT/apksigner sign --ks "$KS" --ks-pass pass:bridgesquad --ks-key-alias bridgesquad --out $OUT/otryad-na-mostu.apk $OUT/tmp/aligned.apk
$BT/apksigner verify $OUT/otryad-na-mostu.apk
rm -rf $OUT/tmp
ls -la $OUT/otryad-na-mostu.apk
