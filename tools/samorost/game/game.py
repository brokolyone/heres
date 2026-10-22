"""Build «Остров-пень»: a small point-and-click game on the Samorost island.

usage: python3 game.py <buildDir> <characters.svg> <out.html> [soundtrack.ogg soundtrack.m4a]

<buildDir> must already hold (see build.sh):
  scene.html            the animated island assembled without the gnome (GAME=1 extract + assemble.py),
                        with a <!--CHARACTER--> slot between the scenery and the foreground parts
  static_interior.png   the house interior backdrop and iparts/*.png + iparts.json (interior_merge.js + rasterize.js)
The gnome becomes a jointed SVG puppet built from its own drawing in characters.svg.
Output is an HTML fragment (title, style, body content) suitable for publishing as an artifact;
it also opens directly in a browser.
"""
import base64
import io
import json
import os
import re
import sys
from pathlib import Path

from PIL import Image

build, chars_svg, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
audio = [Path(a) for a in sys.argv[4:6]]
SCALE = 2


IMG_SCALE = float(os.environ.get('IMG_SCALE', '1'))  # < 1 for the phone build: smaller bitmaps, less GPU memory


def webp(img, quality, alpha=True):
    if IMG_SCALE != 1:
        img = img.resize((max(1, round(img.width * IMG_SCALE)), max(1, round(img.height * IMG_SCALE))), Image.LANCZOS)
    buf = io.BytesIO()
    (img if alpha else img.convert('RGB')).save(buf, 'WEBP', quality=quality, method=6)
    return 'data:image/webp;base64,' + base64.b64encode(buf.getvalue()).decode()


def trimmed(png):
    img = Image.open(png).convert('RGBA')
    box = img.getchannel('A').point(lambda a: 255 if a > 2 else 0).getbbox()
    if not box:
        return None, None
    x0, y0, x1, y1 = box
    x0, y0, x1, y1 = max(0, x0 - 2), max(0, y0 - 2), min(img.width, x1 + 2), min(img.height, y1 + 2)
    return img.crop((x0, y0, x1, y1)), (x0 / SCALE, y0 / SCALE, (x1 - x0) / SCALE, (y1 - y0) / SCALE)


# ---------------- the island scene (already assembled) ----------------
scene = (build / 'scene.html').read_text()
scene_css = scene[scene.index('<style>') + 7:scene.index('</style>')]
stage_inner = scene[scene.index('<div id="stage">') + len('<div id="stage">'):scene.rindex('</div></div>')]
stage_inner = stage_inner.replace('<!--CHARACTER-->', '<div id="slot-out" class="slot"></div>\n<div id="fx-out" class="fx"></div>', 1)

# ---------------- the house interior ----------------
FIREFX = '''<div class="firebox"><i class="flame" style="left:0px;width:24px;height:40px;--d:0.9s;--dl:-0.1s"></i><i class="flame" style="left:14px;width:26px;height:56px;--d:0.7s;--dl:-0.4s"></i><i class="flame" style="left:32px;width:24px;height:48px;--d:1.1s;--dl:-0.2s"></i><i class="flame" style="left:48px;width:26px;height:58px;--d:0.8s;--dl:-0.6s"></i><i class="flame" style="left:62px;width:22px;height:38px;--d:1s;--dl:-0.3s"></i><i class="ember" style="left:20px;--dl:-0.2s"></i><i class="ember" style="left:36px;--dl:-1.1s"></i><i class="ember" style="left:54px;--dl:-0.7s"></i><i class="ember" style="left:70px;--dl:-1.6s"></i><i class="ember" style="left:44px;--dl:-2.2s"></i></div>'''
iparts = json.load(open(build / 'iparts.json'))
interior_back, interior_front = [], []
for p in iparts:
    img, box = trimmed(build / 'iparts' / f"{p['id']}.png")
    if img is None:
        continue
    x, y, w, h = box
    ox, oy = p['origin'] or (x + w / 2, y + h / 2)
    style = ';'.join([f'left:{x:.1f}px;top:{y:.1f}px;width:{w:.1f}px;height:{h:.1f}px', f'transform-origin:{ox - x:.1f}px {oy - y:.1f}px']
                     + [f'--{k}:{v}' for k, v in p['vars'].items()])
    html = (f'<div class="p a-{p["anim"]}" data-id="{p["id"]}" data-x="{x:.1f}" data-y="{y:.1f}" data-w="{w:.1f}" data-h="{h:.1f}" '
            f'style="{style}"><img src="{webp(img, 88)}" alt=""></div>\n')
    (interior_front if p['front'] else interior_back).append(html)
    if p['id'] == 'fire-back':  # live flame tongues and rising embers sit behind the logs and the grille
        interior_back.append(FIREFX)
interior_img = webp(Image.open(build / 'static_interior.png'), 86, alpha=False)


def dust():
    import random
    rnd = random.Random(3)
    out_ = []
    for _ in range(40):  # motes drifting in the moonlight shaft from the open top
        t = rnd.random()
        y = rnd.uniform(80, 880)
        x = 1050 - (1050 - 520) * (y / 905) + rnd.uniform(-60, 160) + t * 40
        out_.append(f'<i class="spore s{rnd.randint(1, 3)}" style="left:{x:.0f}px;top:{y:.0f}px;--dur:{rnd.choice([6, 12])}s;'
                    f'--delay:-{rnd.uniform(0, 12):.2f}s;--dx:{rnd.uniform(-30, 30):.0f}px;--dy:{rnd.uniform(10, 40):.0f}px"></i>')
    return ''.join(out_)


INTERIOR = f'''<div id="inside" class="scene" hidden>
<img class="base" src="{interior_img}" alt="Внутри дома-пня: печка, кровать, стол и открытый верх с луной">
{dust()}
{''.join(interior_back)}
<i class="steam" style="--delay:-0.00s;--sx:0px;--sw:1"></i><i class="steam" style="--delay:-0.43s;--sx:4px;--sw:-1"></i><i class="steam" style="--delay:-0.86s;--sx:-2px;--sw:1"></i><i class="steam" style="--delay:-1.29s;--sx:6px;--sw:-1"></i><i class="steam" style="--delay:-1.72s;--sx:1px;--sw:1"></i><i class="steam" style="--delay:-2.15s;--sx:-3px;--sw:-1"></i>
<i class="glow stoveglow" style="left:1150px;top:610px;width:310px;height:300px;--delay:-.3s"></i>
<div id="slot-in" class="slot"></div>
<div id="fx-in" class="fx"></div>
{''.join(interior_front)}
<div id="room-shade"></div>
<div class="overlay grainlayer"></div>
</div>'''

# ---------------- the gnome as a jointed puppet ----------------
src = chars_svg.read_text()
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
limbs = {k: [] for k in ['shadow', 'beam', 'legL', 'legR', 'body', 'armL', 'armR', 'head']}
k = 0
while k < len(lines):
    ln = lines[k]
    if ln in ('</g>', '<g filter="url(#characters-grainlite)">') or not ln.strip():
        k += 1
        continue
    if ln.startswith('<g') and ln.count('<g') > ln.count('</g>'):  # multi-line group (the head)
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
        eyes = [x for x in inner if x.startswith(EYES)]
        rest = [x for x in inner if not x.startswith(EYES)]
        at = next(n for n, x in enumerate(rest) if x.startswith('<path d="M774.2,492.3'))
        rest.insert(at, '<g id="h-eyes">' + ''.join(eyes) + '</g>')
        el = '\n'.join(rest)
    limbs[limb].append(el)
HERO = f'''<svg id="hero" class="layer" viewBox="0 0 1600 1000" width="1600" height="1000"><defs>{defs}</defs>
<g id="h-root">
<g id="h-shadow">{''.join(limbs['shadow'])}</g>
<g filter="url(#characters-grainlite)">
<g id="h-legL">{''.join(limbs['legL'])}</g><g id="h-legR">{''.join(limbs['legR'])}</g>
<g id="h-upper">
<g id="h-armL">{''.join(limbs['armL'])}</g>
<g id="h-body">{''.join(limbs['body'])}</g>
<g id="h-armR"><g id="h-beam">{''.join(limbs['beam'])}</g>{''.join(limbs['armR'])}</g>
<g id="h-head">{''.join(limbs['head'])}</g>
</g></g></g></svg>'''

# ---------------- page ----------------
CSS = scene_css.replace('html,body{margin:0;height:100%;background:#061210;overflow:hidden}', '') + r'''
[hidden]{display:none!important}
:root{--ink:#efe6c8;--ink-dim:rgba(239,230,200,.7);--night:#061210;--panel:rgba(8,20,18,.72);--amber:#f3d27a;color-scheme:dark}
html,body{margin:0;height:100%;background:var(--night);overflow:hidden;touch-action:manipulation;-webkit-user-select:none;user-select:none}
#stage{cursor:default}
#stage.hot{cursor:pointer}
.scene{position:absolute;inset:0}
.layer{position:absolute;left:0;top:0;pointer-events:none}
.slot,.fx{position:absolute;inset:0;pointer-events:none}
.fx>*{position:absolute;left:0;top:0;pointer-events:none;will-change:transform,opacity}
#curtain{position:absolute;inset:0;background:#000;opacity:0;pointer-events:none;transition:opacity .35s}
/* the room is darker and its sides fall into deep shadow; only the stove, lamp and candle keep their light */
#room-shade{position:absolute;inset:0;pointer-events:none;
  background:linear-gradient(90deg,rgba(6,3,2,.88) 0%,rgba(6,3,2,.55) 9%,rgba(6,3,2,.12) 24%,rgba(6,3,2,.12) 76%,rgba(6,3,2,.55) 91%,rgba(6,3,2,.88) 100%),
    linear-gradient(180deg,rgba(6,3,2,.35) 0%,rgba(6,3,2,0) 30%,rgba(6,3,2,0) 75%,rgba(6,3,2,.45) 100%),rgba(10,6,3,.22);
  -webkit-mask-image:radial-gradient(circle at 1305px 745px,rgba(0,0,0,.25) 0,rgba(0,0,0,.25) 90px,#000 300px),radial-gradient(circle at 800px 460px,rgba(0,0,0,.35) 0,#000 260px),radial-gradient(circle at 942px 722px,rgba(0,0,0,.45) 0,#000 150px);
  -webkit-mask-composite:source-in;
  mask-image:radial-gradient(circle at 1305px 745px,rgba(0,0,0,.25) 0,rgba(0,0,0,.25) 90px,#000 300px),radial-gradient(circle at 800px 460px,rgba(0,0,0,.35) 0,#000 260px),radial-gradient(circle at 942px 722px,rgba(0,0,0,.45) 0,#000 150px);
  mask-composite:intersect}
.a-pendulum{animation-name:pend;--dur:2s}
@keyframes pend{0%,100%{transform:rotate(9deg)}50%{transform:rotate(-9deg)}}
.a-fire{animation-name:fireglow;--dur:1.3s;animation-timing-function:linear}
@keyframes fireglow{0%,100%{opacity:1;filter:brightness(1)}18%{opacity:.86;filter:brightness(1.12)}37%{opacity:.97;filter:brightness(.92)}58%{opacity:.82;filter:brightness(1.18)}79%{opacity:.94;filter:brightness(.96)}}
.firebox{position:absolute;left:1264px;top:708px;width:82px;height:80px;overflow:hidden;mix-blend-mode:screen;opacity:.7;pointer-events:none}
.flame{position:absolute;bottom:-8px;border-radius:50% 50% 42% 42%/62% 62% 38% 38%;transform-origin:50% 100%;
  background:radial-gradient(ellipse at 50% 85%,rgba(255,244,180,.95),rgba(255,170,70,.75) 42%,rgba(220,80,20,0) 74%);animation:flame var(--d) ease-in-out var(--dl) infinite}
@keyframes flame{0%,100%{transform:scale(1,1) skewX(0)}25%{transform:scale(.82,1.3) skewX(7deg)}50%{transform:scale(1.12,.84) skewX(-5deg)}75%{transform:scale(.9,1.16) skewX(3deg)}}
.ember{position:absolute;top:66px;width:3px;height:3px;border-radius:50%;background:#ffcf6a;box-shadow:0 0 5px 2px rgba(255,150,50,.8);
  animation:ember 2.4s ease-out var(--dl) infinite;opacity:0}
@keyframes ember{0%{transform:translate(0,0);opacity:0}10%{opacity:1}100%{transform:translate(14px,-60px);opacity:0}}
.a-candle{animation-name:candle;--dur:1.5s}
@keyframes candle{0%,100%{transform:scale(1,1) skewX(0)}30%{transform:scale(.95,1.08) skewX(4deg)}60%{transform:scale(1.03,.96) skewX(-3deg)}}
.stoveglow{background:radial-gradient(closest-side,rgba(255,150,60,.5),rgba(255,150,60,0))}
.steam{position:absolute;left:1360px;top:555px;width:9px;height:15px;border-radius:50%;pointer-events:none;
  background:radial-gradient(ellipse,rgba(242,242,234,.6),rgba(242,242,234,0) 70%);filter:blur(1.2px);transform-origin:50% 80%;
  animation:steam 2.6s linear var(--delay) infinite;opacity:0}
@keyframes steam{0%{transform:translate(0,0) scale(.4,.5);opacity:0}8%{opacity:.8}
  28%{transform:translate(calc(var(--sx) + 5px),-20px) scale(.8,1.2) rotate(calc(var(--sw) * 14deg))}
  52%{transform:translate(calc(var(--sx) * -1 + 2px),-44px) scale(1.3,1.6) rotate(calc(var(--sw) * -10deg));opacity:.45}
  76%{transform:translate(calc(var(--sx) + 9px),-70px) scale(1.9,2) rotate(calc(var(--sw) * 8deg));opacity:.2}
  100%{transform:translate(calc(var(--sx) * -1 + 5px),-96px) scale(2.5,2.3);opacity:0}}
/* interface */
#ui{position:fixed;inset:0;pointer-events:none;font-family:"Neucha","Comic Sans MS",Georgia,serif;color:var(--ink);z-index:6}
#ui button{pointer-events:auto;font:inherit;color:inherit}
#found{position:absolute;left:max(16px,env(safe-area-inset-left,0px));top:calc(12px + env(safe-area-inset-top,0px));
  padding:6px 12px;border-radius:999px;background:var(--panel);font-size:17px;letter-spacing:.02em;opacity:0;transition:opacity .6s}
#found b{color:var(--amber);font-weight:400}
#toast{position:absolute;left:50%;bottom:calc(22px + env(safe-area-inset-bottom,0px));transform:translateX(-50%);max-width:min(560px,86vw);
  text-align:center;padding:8px 16px;border-radius:14px;background:var(--panel);font-size:18px;line-height:1.3;opacity:0;transition:opacity .6s}
#snd{position:absolute;right:calc(16px + env(safe-area-inset-right,0px));top:calc(10px + env(safe-area-inset-top,0px));bottom:auto}
#start{position:fixed;inset:0;z-index:8;display:flex;align-items:center;justify-content:center;flex-direction:column;gap:18px;
  background:radial-gradient(ellipse at 50% 40%,rgba(10,30,28,.35),rgba(3,10,9,.92));color:var(--ink);font-family:"Neucha","Comic Sans MS",Georgia,serif;
  padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px));text-align:center;transition:opacity .8s}
#start h1{margin:0;font-weight:400;font-size:clamp(40px,9vw,84px);letter-spacing:.02em;text-wrap:balance;color:#f4ecd2;text-shadow:0 2px 18px rgba(243,210,122,.25)}
#start p{margin:0;font-size:clamp(16px,2.6vw,21px);max-width:34em;color:var(--ink-dim);line-height:1.4}
#play{pointer-events:auto;font:inherit;font-size:24px;padding:10px 34px;border-radius:999px;border:1px solid rgba(243,210,122,.55);
  background:rgba(243,210,122,.12);color:#f4ecd2;cursor:pointer}
#play:hover,#play:focus-visible{background:rgba(243,210,122,.25);outline:none}
#turn{position:fixed;left:0;right:0;top:calc(10px + env(safe-area-inset-top,0px));text-align:center;z-index:7;pointer-events:none;
  font-family:"Neucha",Georgia,serif;color:var(--ink-dim);font-size:15px;display:none}
@media (orientation:portrait){#turn{display:block}}
.note{font:22px Georgia,serif;color:#f3d27a;text-shadow:0 0 6px rgba(243,210,122,.7)}
.zz{font:bold 20px Georgia,serif;color:#e6eedf;text-shadow:0 0 6px rgba(200,230,220,.6)}
.dot{width:6px;height:6px;border-radius:50%;background:#f6e6a0;box-shadow:0 0 8px 3px rgba(246,230,160,.6)}
.spark{width:4px;height:4px;border-radius:50%;background:#ffd27a;box-shadow:0 0 6px 2px rgba(255,170,60,.8)}
.puffx{width:24px;height:24px;border-radius:50%;background:radial-gradient(circle,rgba(220,218,205,.7),rgba(220,218,205,0) 70%)}
.streak{width:120px;height:2px;border-radius:2px;background:linear-gradient(90deg,rgba(255,250,225,0),rgba(255,250,225,.95))}
'''

AUDIO_SRC = ','.join(f"['{t}','data:{t};base64,{base64.b64encode(p.read_bytes()).decode()}']"
                     for t, p in zip(('audio/ogg', 'audio/mp4'), audio))

JS = (Path(__file__).parent / 'game.js').read_text().replace('%%AUDIO%%', AUDIO_SRC)

page = f'''<title>Остров-пень</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Neucha&display=swap">
<style>{CSS}</style>
<div id="wrap"><div id="stage">
<div id="outside" class="scene">
{stage_inner}
</div>
{INTERIOR}
<div id="curtain"></div>
</div></div>
<template id="hero-tpl">{HERO}</template>
<div id="ui">
<div id="found">найдено <b id="nfound">0</b> из <span id="ntotal">0</span></div>
<div id="toast"></div>
<button id="snd" type="button" aria-label="Выключить звук" title="Звук" class="playing">
<svg viewBox="0 0 24 24" width="22" height="22"><path d="M4 9h4l5-4v14l-5-4H4z" fill="currentColor"/>
<path class="on" d="M16 8.5c1.2 1 1.8 2.2 1.8 3.5s-.6 2.5-1.8 3.5M18.5 6c2 1.6 3 3.6 3 6s-1 4.4-3 6" stroke="currentColor" stroke-width="1.6" fill="none" stroke-linecap="round"/>
<path class="off" d="M16.5 9.5l5 5m0-5l-5 5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg></button>
</div>
<div id="turn">поверни телефон горизонтально — так остров виден целиком</div>
<div id="start">
<h1>Остров-пень</h1>
<p>Маленький гномик живёт на летающем пне. Тапни по земле, чтобы он пошёл туда, а по чему-нибудь интересному, чтобы он с этим поиграл. Загляни и в дом.</p>
<button id="play" type="button">Играть</button>
</div>
<script>
{JS}
</script>
'''
out.write_text(page)
print(f'{out} {out.stat().st_size / 1e6:.1f} MB; puppet limbs: ' + ', '.join(f'{n}={len(v)}' for n, v in limbs.items()))
