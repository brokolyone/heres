"""Export everything the native Android game needs into an assets folder.

usage: python3 export_assets.py <gameBuildDir> <repoRoot> <outAssetsDir>

<gameBuildDir> is a game build (GAME=1 extract.js, interior_merge.js, rasterize.js, sound.py), see build_native.sh.
Writes: img/*.webp (backdrops and sprites, 1.2x), hero/*.png (puppet limbs, 3x), sfx/*.wav,
music_out.ogg, music_in.ogg, crackle.ogg, font.ttf (if it can be fetched) and scene.json, which
describes both scenes as ordered draw lists plus every animation as keyframe tracks (a port of the
CSS keyframes used by the web version).
"""
import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image

build, root, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
here = Path(__file__).parent
RENDER = 2      # build bitmaps are rendered at 2x
SCALE = 0.6     # -> 1.2 px per canvas px in the app
for d in ('img', 'hero', 'sfx'):
    (out / d).mkdir(parents=True, exist_ok=True)
env = dict(os.environ, NODE_PATH=os.environ.get('NODE_PATH', '/opt/node-tools/node_modules'))


def save_webp(img, name, quality=88):
    img = img.resize((max(1, round(img.width * SCALE)), max(1, round(img.height * SCALE))), Image.LANCZOS)
    img.save(out / 'img' / name, 'WEBP', quality=quality, method=6)
    return name


def trimmed(png):
    img = Image.open(png).convert('RGBA')
    box = img.getchannel('A').point(lambda a: 255 if a > 2 else 0).getbbox()
    if not box:
        return None, None
    x0, y0, x1, y1 = box
    x0, y0, x1, y1 = max(0, x0 - 2), max(0, y0 - 2), min(img.width, x1 + 2), min(img.height, y1 + 2)
    return img.crop((x0, y0, x1, y1)), [x0 / RENDER, y0 / RENDER, (x1 - x0) / RENDER, (y1 - y0) / RENDER]


def num(v):
    """'1.5deg' -> 1.5, '6s' -> 6000, '-2s' -> -2000, '4px' -> 4."""
    v = str(v)
    if v.endswith('ms'):
        return float(v[:-2])
    if v.endswith('s'):
        return float(v[:-1]) * 1000
    return float(re.sub(r'(deg|px)$', '', v))


# ---------------- animations: the CSS keyframes as per-property tracks ----------------
# frames: (percent, {prop: value}); value is a number or an expression over the part's vars
# ('a', '-a', 'dy', 'sx+5', '-sx+2', 'sw*14'). Transform props: tx ty rot sx sy skx sky sa (scale along axis);
# other props: op (opacity) br (brightness).
E_IO, E_O, E_I, LIN = 'ease-in-out', 'ease-out', 'ease-in', 'linear'
ANIMS = {
    'sway': (6000, E_IO, [(0, {'rot': 'a'}), (50, {'rot': '-a'}), (100, {'rot': 'a'})], {'a': 1.5}),
    'frond': (6000, E_IO, [(0, {'rot': 'a'}), (50, {'rot': '-a'}), (100, {'rot': 'a'})], {'a': 1.5}),
    'skew': (6000, E_IO, [(0, {'skx': 'a'}), (50, {'skx': '-a'}), (100, {'skx': 'a'})], {'a': 1}),
    'bob': (6000, E_IO, [(0, {'ty': 0}), (50, {'ty': 'dy'}), (100, {'ty': 0})], {'dy': 4}),
    'spin': (6000, LIN, [(0, {'rot': 0}), (100, {'rot': 360})], {}),
    'spinR': (6000, LIN, [(0, {'rot': 0}), (100, {'rot': -360})], {}),
    'bubbles': (3000, E_O, [(0, {'tx': 0, 'ty': 6, 'sx': .5, 'sy': .5, 'op': 0}), (15, {'op': 1}), (80, {'op': .85}),
                            (100, {'tx': 10, 'ty': -26, 'sx': 1.25, 'sy': 1.25, 'op': 0})], {}),
    'drip': (4000, E_I, [(0, {'sx': .3, 'sy': .3, 'op': 0}), (10, {'op': 1}), (60, {'ty': 0, 'op': 1}), (72, {'sy': 1.35, 'ty': 2}),
                         (90, {'ty': 60, 'op': 0}), (100, {'ty': 60, 'op': 0})], {}),
    'breathe': (4000, E_IO, [(0, {'sx': 1}), (45, {'sx': 1.012, 'sy': 1.03}), (100, {'sx': 1})], {}),
    'flyBeetle': (12000, E_IO, [(0, {'tx': 0}), (25, {'tx': 48, 'ty': -14, 'rot': -4}), (50, {'tx': 80, 'ty': 6, 'rot': 3}),
                                (75, {'tx': 30, 'ty': 16, 'rot': -2}), (100, {'tx': 0})], {}),
    'prop': (240, LIN, [(0, {'sx': 1}), (50, {'sx': -1}), (100, {'sx': 1})], {}),
    'exhaust': (1000, LIN, [(0, {'tx': -6, 'op': .2}), (30, {'op': 1}), (100, {'tx': 10, 'ty': 3, 'op': 0})], {}),
    'flyMoth': (12000, E_IO, [(0, {'tx': 0}), (20, {'tx': -26, 'ty': -18, 'rot': -8}), (40, {'tx': -8, 'ty': -34, 'rot': 6}),
                              (60, {'tx': 28, 'ty': -14, 'rot': 10}), (80, {'tx': 20, 'ty': 12, 'rot': -4}), (100, {'tx': 0})], {}),
    'flap': (400, E_IO, [(0, {'sx': 1}), (50, {'sx': .5}), (100, {'sx': 1})], {}),
    'jelly': (6000, E_IO, [(0, {'ty': 0}), (25, {'ty': -8, 'sx': 1.05, 'sy': .93}), (50, {'ty': -16}), (75, {'ty': -6, 'sx': .96, 'sy': 1.04}), (100, {'ty': 0})], {}),
    'antennae': (2000, E_IO, [(0, {'rot': 0}), (20, {'rot': 7}), (40, {'rot': -3}), (55, {'rot': 2}), (100, {'rot': 0})], {}),
    'smoke': (6000, E_IO, [(0, {'skx': 0, 'op': .9}), (33, {'skx': -5, 'sy': 1.04, 'op': 1}), (66, {'skx': 4, 'sy': .98, 'op': .8}), (100, {'skx': 0, 'op': .9})], {}),
    'flicker': (3000, LIN, [(0, {'op': 1}), (8, {'op': .82}), (14, {'op': 1}), (30, {'op': .9}), (42, {'op': 1}), (57, {'op': .75}),
                            (63, {'op': .97}), (78, {'op': .86}), (88, {'op': 1}), (100, {'op': 1})], {}),
    'needle': (1500, E_IO, [(0, {'rot': 0}), (30, {'rot': -14}), (55, {'rot': 6}), (75, {'rot': -4}), (100, {'rot': 0})], {}),
    'flag': (1000, E_IO, [(0, {'sky': 0}), (33, {'sky': 5, 'sx': .94}), (66, {'sky': -3, 'sx': 1.02}), (100, {'sky': 0})], {}),
    'swing': (4000, E_IO, [(0, {'rot': 4}), (50, {'rot': -4}), (100, {'rot': 4})], {}),
    'twinkle': (3000, E_IO, [(0, {'op': 1}), (50, {'op': .2}), (100, {'op': 1})], {}),
    'ladder': (6000, E_IO, [(0, {'rot': 2.5}), (50, {'rot': -2.5}), (100, {'rot': 2.5})], {}),
    'glowpulse': (4000, E_IO, [(0, {'op': 1}), (50, {'op': .45}), (100, {'op': 1})], {}),
    'rays': (12000, E_IO, [(0, {'op': .55, 'rot': 0}), (50, {'op': 1, 'rot': 1.5}), (100, {'op': .55, 'rot': 0})], {}),
    'spider': (6000, E_IO, [(0, {'ty': 0}), (40, {'ty': 4}), (60, {'ty': 3}), (100, {'ty': 0})], {}),
    'snail': (3000, E_IO, [(0, {'sa': 1}), (50, {'sa': 1.06}), (100, {'sa': 1})], {}),
    'leaf': (6000, E_IO, [(0, {'tx': 0}), (25, {'tx': 5, 'ty': 4, 'rot': 'a'}), (50, {'tx': 9}), (75, {'tx': 4, 'ty': -4, 'rot': '-a'}), (100, {'tx': 0})], {'a': 12}),
    'fly1': (6000, E_IO, [(0, {'tx': 0, 'op': 1}), (25, {'tx': 8, 'ty': -10, 'op': .3}), (50, {'tx': 16, 'op': 1}), (75, {'tx': 7, 'ty': 9, 'op': .55}), (100, {'tx': 0, 'op': 1})], {}),
    'fly2': (6000, E_IO, [(0, {'tx': 0, 'op': .4}), (30, {'tx': -12, 'ty': -6, 'op': 1}), (60, {'tx': -4, 'ty': -16, 'op': .25}), (80, {'tx': 4, 'ty': -6, 'op': 1}), (100, {'tx': 0, 'op': .4})], {}),
    'fly3': (6000, E_IO, [(0, {'tx': 0, 'op': 1}), (20, {'op': .2}), (40, {'tx': 10, 'ty': 10, 'op': 1}), (70, {'tx': -8, 'ty': 6, 'op': .6}), (100, {'tx': 0, 'op': 1})], {}),
    'pendulum': (2000, E_IO, [(0, {'rot': 9}), (50, {'rot': -9}), (100, {'rot': 9})], {}),
    'fire': (1300, LIN, [(0, {'op': 1, 'br': 1}), (18, {'op': .86, 'br': 1.12}), (37, {'op': .97, 'br': .92}), (58, {'op': .82, 'br': 1.18}),
                         (79, {'op': .94, 'br': .96}), (100, {'op': 1, 'br': 1})], {}),
    'candle': (1500, E_IO, [(0, {'sx': 1}), (30, {'sx': .95, 'sy': 1.08, 'skx': 4}), (60, {'sx': 1.03, 'sy': .96, 'skx': -3}), (100, {'sx': 1})], {}),
    'none': (6000, LIN, [], {}),
}
T_PROPS = ['tx', 'ty', 'rot', 'sx', 'sy', 'skx', 'sky', 'sa']
DEFAULT = {'tx': 0, 'ty': 0, 'rot': 0, 'sx': 1, 'sy': 1, 'skx': 0, 'sky': 0, 'sa': 1, 'op': 1, 'br': 1}


def tracks(frames):
    """CSS semantics: a keyframe that sets any transform function resets the other transform functions to identity;
    opacity and brightness are tracked independently; missing ends take the base value."""
    tr = {}
    for pct, props in frames:
        full = dict(props)
        if any(k in T_PROPS for k in props):
            for k in T_PROPS:
                full.setdefault(k, DEFAULT[k])
        for k, v in full.items():
            tr.setdefault(k, []).append([pct / 100, v])
    for k, pts in tr.items():
        if pts[0][0] > 0:
            pts.insert(0, [0, DEFAULT[k]])
        if pts[-1][0] < 1:
            pts.append([1, DEFAULT[k]])
    return tr


anims_json = {name: {'dur': dur, 'ease': ease, 'tracks': tracks(frames), 'vars': dv} for name, (dur, ease, frames, dv) in ANIMS.items()}


def part_vars(p):
    v = {}
    for k, val in (p.get('vars') or {}).items():
        v[k] = num(val)
    return v


# ---------------- island scene ----------------
LAYERS = ['bg', 'island', 'cave', 'structures', 'flora', 'characters', 'details']
parts = json.load(open(build / 'parts.json'))
for p in parts:
    img, box = trimmed(build / 'parts' / f"{p['id']}.png")
    p['img'], p['box'] = img, box
parts = [p for p in parts if p['img'] is not None]
for p in parts:
    p['children'] = sorted([c for c in parts if c['parent'] == p['id']], key=lambda c: c['pos'])


def part_json(p):
    x, y, w, h = p['box']
    o = p['origin'] or [x + w / 2, y + h / 2]
    v = part_vars(p)
    anim = p['anim'] if p['anim'] in ANIMS else 'none'
    return {'t': 'part', 'id': p['id'], 'f': save_webp(p['img'], f"p_{p['id']}.webp"), 'box': [round(c, 2) for c in p['box']], 'o': o,
            'anim': anim, 'dur': v.pop('dur', ANIMS[anim][0]), 'delay': v.pop('delay', 0), 'vars': v,
            'below': [part_json(c) for c in p['children'] if c['below']], 'above': [part_json(c) for c in p['children'] if not c['below']]}


tops = sorted([p for p in parts if not p['parent']], key=lambda p: (LAYERS.index(p['layer']), p['pos']))
out_items = [{'t': 'img', 'f': save_webp(Image.open(build / 'static_bg.png').convert('RGB'), 'bg_out.webp', 86)},
             {'t': 'extra', 'kind': 'moonglow'}, {'t': 'extra', 'kind': 'stars'}, {'t': 'extra', 'kind': 'shoot'}]
out_items += [part_json(p) for p in tops if p['layer'] == 'bg']
out_items.append({'t': 'img', 'f': save_webp(Image.open(build / 'static_mid.png'), 'mid_out.webp', 90)})
out_items += [part_json(p) for p in tops if p['layer'] != 'bg' and not p.get('front')]
out_items.append({'t': 'hero'})
out_items += [part_json(p) for p in tops if p['layer'] != 'bg' and p.get('front')]
out_items += [{'t': 'extra', 'kind': 'glow', 'x': 534, 'y': 418, 'w': 76, 'h': 68, 'delay': -1700, 'id': 'glow-window'},
              {'t': 'extra', 'kind': 'puffs'}, {'t': 'extra', 'kind': 'spores'}, {'t': 'extra', 'kind': 'fall'},
              {'t': 'extra', 'kind': 'grain'}]

# ---------------- house interior ----------------
iparts = json.load(open(build / 'iparts.json'))
in_back, in_front = [], []
for p in iparts:
    img, box = trimmed(build / 'iparts' / f"{p['id']}.png")
    if img is None:
        continue
    p['img'], p['box'], p['children'] = img, box, []
    j = part_json(p)
    (in_front if p['front'] else in_back).append(j)
    if p['id'] == 'fire-back':
        in_back.append({'t': 'extra', 'kind': 'firebox'})
in_items = [{'t': 'img', 'f': save_webp(Image.open(build / 'static_interior.png').convert('RGB'), 'bg_in.webp', 86)},
            {'t': 'extra', 'kind': 'dust'}] + in_back + [
            {'t': 'extra', 'kind': 'steam'}, {'t': 'extra', 'kind': 'glow', 'x': 1150, 'y': 610, 'w': 310, 'h': 300, 'delay': -300, 'id': 'stoveglow'},
            {'t': 'hero'}, {'t': 'extra', 'kind': 'shade'}] + in_front + [{'t': 'extra', 'kind': 'grain'}]

# ---------------- the gnome as limbs ----------------
src = (root / 'art/samorost/layers/characters.svg').read_text()
i0 = src.index('<g id="characters-gnome">')
depth, j = 0, i0
for m in re.finditer(r'<g[\s>]|</g>', src[i0:]):
    depth += -1 if m.group(0) == '</g>' else 1
    if depth == 0:
        j = i0 + m.end()
        break
lines = src[i0:j].split('\n')[1:-1]
defs = ''.join(re.findall(r'<(?:radialGradient|linearGradient|filter) id="characters-(?:suit|cap|face|beam|shadow|grainlite|soft)"[\s\S]*?</(?:radialGradient|linearGradient|filter)>', src))
LIMBS = {
    'shadow': ['<ellipse cx="781" cy="549"'], 'beam': ['<path d="M806,499'],
    'legL': ['<path d="M775,532', '<path d="M767,549', '<path d="M770,544'],
    'legR': ['<path d="M786,532', '<path d="M786,549', '<path d="M789,544'],
    'armL': ['<path d="M770,517', '<circle cx="764" cy="532"'],
    'armR': ['<path d="M791,517', '<g transform="translate(800 508)', '<circle cx="800" cy="508"'],
    'head': ['<g transform="rotate(4 781 505)">', '<path d="M790,474', '<path d="M795,501'],
}
EYES = ('<ellipse cx="776.5"', '<ellipse cx="777.4"', '<ellipse cx="787.7"', '<circle cx="777.9"')
limbs = {k: [] for k in ['shadow', 'beam', 'legL', 'legR', 'body', 'armL', 'armR', 'head', 'eyes']}
k = 0
while k < len(lines):
    ln = lines[k]
    if ln in ('</g>', '<g filter="url(#characters-grainlite)">') or not ln.strip():
        k += 1
        continue
    if ln.startswith('<g') and ln.count('<g') > ln.count('</g>'):
        d, chunk = 0, []
        while True:
            chunk.append(lines[k])
            d += lines[k].count('<g') - lines[k].count('</g>')
            k += 1
            if d == 0:
                break
        el = '\n'.join(chunk)
    else:
        el, k = ln, k + 1
    limb = next((n for n, pre in LIMBS.items() if any(el.startswith(p) for p in pre)), 'body')
    if el.startswith('<g transform="rotate(4 781 505)">'):
        inner = el.split('\n')
        limbs['eyes'].append('<g transform="rotate(4 781 505)">' + ''.join(x for x in inner if x.startswith(EYES)) + '</g>')
        el = '\n'.join(x for x in inner if not x.startswith(EYES))
    limbs[limb].append(el)
HERO_SCALE = 3
jobs = []
for name, els in limbs.items():
    body = ''.join(els)
    if name not in ('shadow', 'beam'):
        body = f'<g filter="url(#characters-grainlite)">{body}</g>'
    jobs.append({'id': name, 'svg': f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 1000" width="1600" height="1000"><defs>{defs}</defs><g id="limb">{body}</g></svg>'})
(build / 'limbs.json').write_text(json.dumps(jobs))
subprocess.run(['node', str(here / 'render_limbs.js'), str(build / 'limbs.json'), str(out / 'hero'), str(HERO_SCALE)], check=True, env=env)
hero_boxes = json.loads((out / 'hero' / 'limbs_box.json').read_text())
(out / 'hero' / 'limbs_box.json').unlink()

# ---------------- sound ----------------
subprocess.run(['node', str(here / 'render_sfx.js'), str(root / 'tools/samorost/game/game.js'), str(out / 'sfx')], check=True, env=env)
ff = ['ffmpeg', '-y', '-loglevel', 'error']
subprocess.run(ff + ['-i', str(build / 'soundtrack.wav'), '-c:a', 'libvorbis', '-q:a', '4', str(out / 'music_out.ogg')], check=True)
subprocess.run(ff + ['-i', str(build / 'soundtrack.wav'), '-af', 'lowpass=f=900,lowpass=f=900', '-c:a', 'libvorbis', '-q:a', '3', str(out / 'music_in.ogg')], check=True)
rng = np.random.default_rng(3)  # stove crackle bed, 4 s loop
n = 44100 * 4
d = rng.standard_normal(n) * 0.02
for _ in range(90):
    p0, L, a = rng.integers(0, n - 800), int(rng.uniform(80, 580)), rng.uniform(0, .8)
    d[p0:p0 + L] += rng.standard_normal(L) * a * np.exp(-np.arange(L) / (L / 4))
X = np.fft.rfft(d)
f = np.fft.rfftfreq(n, 1 / 44100)
d = np.fft.irfft(X / np.sqrt(1 + (0.7 * (f / 2400 - 2400 / np.maximum(f, 1))) ** 2), n)
d = (d / np.abs(d).max() * 0.5 * 32767).astype('<i2')
import wave
with wave.open(str(build / 'crackle.wav'), 'wb') as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(44100); w.writeframes(d.tobytes())
subprocess.run(ff + ['-i', str(build / 'crackle.wav'), '-c:a', 'libvorbis', '-q:a', '3', str(out / 'crackle.ogg')], check=True)

# ---------------- font ----------------
try:
    css = urllib.request.urlopen(urllib.request.Request('https://fonts.googleapis.com/css2?family=Neucha', headers={'User-Agent': 'curl/8'}), timeout=20).read().decode()
    url = re.search(r'url\((https://[^)]+\.ttf)\)', css).group(1)
    (out / 'font.ttf').write_bytes(urllib.request.urlopen(url, timeout=20).read())
except Exception as e:  # the app falls back to a system serif
    print('font not fetched:', e)

scene = {'anims': anims_json, 'out': out_items, 'in': in_items,
         'hero': {'scale': HERO_SCALE, 'boxes': hero_boxes},
         'sfx': sorted(f.stem for f in (out / 'sfx').glob('*.wav'))}
(out / 'scene.json').write_text(json.dumps(scene, separators=(',', ':')))
print(f"assets: {len(list((out / 'img').iterdir()))} images, {len(hero_boxes)} limbs, {len(scene['sfx'])} sfx")
