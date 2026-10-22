#!/bin/sh
# Build the animated Samorost page and a looping MP4.
# usage: tools/samorost/animate/build.sh <buildDir>
# Field recordings come from art/samorost/sound_sources (override with SOUND_SRC); see CREDITS.md there.
set -e
here=$(cd "$(dirname "$0")" && pwd)
root=$(cd "$here/../../.." && pwd)
build=${1:?build dir}
out="$root/art/samorost/animated"
export NODE_PATH=${NODE_PATH:-/opt/node-tools/node_modules}
rm -rf "$build" && mkdir -p "$build" "$out"
node "$here/extract.js" "$root/art/samorost/layers" "$build"
node "$here/rasterize.js" "$build"
python3 "$here/sound.py" "${SOUND_SRC:-$root/art/samorost/sound_sources}" "$build/soundtrack.wav"
ffmpeg -y -loglevel error -i "$build/soundtrack.wav" -c:a libopus -b:a 112k "$build/soundtrack.ogg"
ffmpeg -y -loglevel error -i "$build/soundtrack.wav" -c:a aac -b:a 128k "$build/soundtrack.m4a"
python3 "$here/assemble.py" "$build" "$out/samorost_animated.html" "$build/soundtrack.ogg" "$build/soundtrack.m4a"
node "$here/video.js" "$out/samorost_animated.html" "$build/frames" 12 30
ffmpeg -y -loglevel error -framerate 30 -i "$build/frames/f%04d.png" -c:v libx264 -preset slow -crf 18 -pix_fmt yuv420p "$build/loop12.mp4"
# four animation cycles under the 48 s soundtrack
ffmpeg -y -loglevel error -stream_loop 3 -i "$build/loop12.mp4" -i "$build/soundtrack.wav" -map 0:v -map 1:a -c:v copy -c:a aac -b:a 192k -shortest -movflags +faststart "$out/samorost_animated.mp4"
ls -la "$out"
