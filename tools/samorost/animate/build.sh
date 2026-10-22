#!/bin/sh
# Build the animated Samorost page and a looping MP4.
# usage: tools/samorost/animate/build.sh <buildDir>
set -e
here=$(cd "$(dirname "$0")" && pwd)
root=$(cd "$here/../../.." && pwd)
build=${1:?build dir}
out="$root/art/samorost/animated"
export NODE_PATH=${NODE_PATH:-/opt/node-tools/node_modules}
rm -rf "$build" && mkdir -p "$build" "$out"
node "$here/extract.js" "$root/art/samorost/layers" "$build"
node "$here/rasterize.js" "$build"
python3 "$here/assemble.py" "$build" "$out/samorost_animated.html"
node "$here/video.js" "$out/samorost_animated.html" "$build/frames" 12 30
ffmpeg -y -loglevel error -framerate 30 -i "$build/frames/f%04d.png" -c:v libx264 -preset slow -crf 18 -pix_fmt yuv420p -movflags +faststart "$out/samorost_animated.mp4"
ls -la "$out"
