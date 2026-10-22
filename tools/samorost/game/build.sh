#!/bin/sh
# Build the «Остров-пень» game page.
# usage: tools/samorost/game/build.sh <buildDir>
set -e
here=$(cd "$(dirname "$0")" && pwd)
anim="$here/../animate"
root=$(cd "$here/../../.." && pwd)
build=${1:?build dir}
out="$root/art/samorost/game"
export NODE_PATH=${NODE_PATH:-/opt/node-tools/node_modules}
rm -rf "$build" && mkdir -p "$build" "$out"
GAME=1 node "$anim/extract.js" "$root/art/samorost/layers" "$build"
node "$here/interior_merge.js" "$root/art/samorost/interior" "$build"
node "$anim/rasterize.js" "$build"
python3 "$anim/assemble.py" "$build" "$build/scene.html"
python3 "$anim/sound.py" "${SOUND_SRC:-$root/art/samorost/sound_sources}" "$build/soundtrack.wav"
ffmpeg -y -loglevel error -i "$build/soundtrack.wav" -c:a libopus -b:a 96k "$build/soundtrack.ogg"
ffmpeg -y -loglevel error -i "$build/soundtrack.wav" -c:a aac -b:a 112k "$build/soundtrack.m4a"
python3 "$here/game.py" "$build" "$root/art/samorost/layers/characters.svg" "$out/ostrov-pen.html" "$build/soundtrack.ogg" "$build/soundtrack.m4a"
