"""Assemble the animated Samorost page from rendered backdrops and sprite parts.

usage: python3 assemble.py <buildDir> <out.html> [soundtrack.ogg soundtrack.m4a]

Static backdrops and every animated part are pre-rendered bitmaps (the live SVG filters are far
too heavy to repaint every frame); the page only moves bitmaps with CSS transforms, so it runs
smoothly. Every animation period divides 12 s, so the whole scene loops seamlessly every 12 s.
"""
import base64
import io
import json
import random
import sys
from pathlib import Path

from PIL import Image

build, out = Path(sys.argv[1]), Path(sys.argv[2])
audio = [Path(a) for a in sys.argv[3:5]]
SCALE = 2  # bitmaps are rendered at 2x
LAYERS = ['bg', 'island', 'structures', 'flora', 'characters', 'details']
rnd = random.Random(7)


def data_uri(img, quality, alpha=True):
    buf = io.BytesIO()
    img.save(buf, 'WEBP', quality=quality, method=6, exact=False) if alpha else img.convert('RGB').save(buf, 'WEBP', quality=quality, method=6)
    return 'data:image/webp;base64,' + base64.b64encode(buf.getvalue()).decode()


def sprite(png):
    img = Image.open(png).convert('RGBA')
    box = img.getchannel('A').point(lambda a: 255 if a > 2 else 0).getbbox()
    if not box:
        return None
    x0, y0, x1, y1 = box
    x0, y0 = max(0, x0 - 2), max(0, y0 - 2)
    x1, y1 = min(img.width, x1 + 2), min(img.height, y1 + 2)
    return img.crop((x0, y0, x1, y1)), (x0 / SCALE, y0 / SCALE, (x1 - x0) / SCALE, (y1 - y0) / SCALE)


parts = json.load(open(build / 'parts.json'))
for p in parts:
    s = sprite(build / 'parts' / f"{p['id']}.png")
    p['img'], p['box'] = s if s else (None, None)
parts = [p for p in parts if p['img'] is not None]
byid = {p['id']: p for p in parts}
for p in parts:
    p['children'] = sorted([c for c in parts if c['parent'] == p['id']], key=lambda c: c['pos'])


def render(p):
    x, y, w, h = p['box']
    ox, oy = p['origin'] or (x + w / 2, y + h / 2)
    style = [f"transform-origin:{ox:.1f}px {oy:.1f}px"]
    style += [f"--{k}:{v}" for k, v in p['vars'].items()]
    img = (f'<img src="{data_uri(p["img"], 88)}" style="left:{x:.1f}px;top:{y:.1f}px;width:{w:.1f}px;height:{h:.1f}px" alt="">')
    below = ''.join(render(c) for c in p['children'] if c['below'])
    above = ''.join(render(c) for c in p['children'] if not c['below'])
    return f'<div class="p a-{p["anim"]}" data-id="{p["id"]}" style="{";".join(style)}">{below}{img}{above}</div>\n'


tops = [p for p in parts if not p['parent']]
tops.sort(key=lambda p: (LAYERS.index(p['layer']), p['pos']))
bg_parts = ''.join(render(p) for p in tops if p['layer'] == 'bg')
mid_parts = (''.join(render(p) for p in tops if p['layer'] != 'bg' and not p.get('front')) + '<!--CHARACTER-->\n'
             + ''.join(render(p) for p in tops if p['layer'] != 'bg' and p.get('front')))

bg_img = data_uri(Image.open(build / 'static_bg.png'), 86, alpha=False)
mid_img = data_uri(Image.open(build / 'static_mid.png'), 90)

# ---------- extra CSS-only life: stars, moon glow, shooting star, chimney smoke, spores, a falling leaf ----------
def stars():
    out = []
    for _ in range(46):
        while True:
            x, y = rnd.uniform(20, 1580), rnd.uniform(15, 620)
            if (x - 1260) ** 2 + (y - 230) ** 2 > 200 ** 2 and not (330 < x < 1270 and y > 330):
                break
        s = rnd.choice([1.4, 1.8, 2.2, 2.8])
        out.append(f'<i class="star" style="left:{x:.0f}px;top:{y:.0f}px;width:{s}px;height:{s}px;--dur:{rnd.choice([2, 3, 4, 6])}s;--delay:-{rnd.uniform(0, 6):.2f}s"></i>')
    return ''.join(out)


def puffs():
    # puffs escape from under the chimney's rain cap, left and right of its legs
    return ''.join(f'<i class="puff" style="left:{(624 if i % 2 else 648)}px;top:324px;--delay:-{i * 1.0:.1f}s;--sx:{rnd.uniform(-10, 10):.0f}px"></i>' for i in range(6))


def spores():
    out = []
    for _ in range(34):
        x, y = rnd.uniform(60, 1540), rnd.uniform(80, 940)
        out.append(f'<i class="spore s{rnd.randint(1, 3)}" style="left:{x:.0f}px;top:{y:.0f}px;--dur:{rnd.choice([6, 12])}s;--delay:-{rnd.uniform(0, 12):.2f}s;--dx:{rnd.uniform(-24, 24):.0f}px;--dy:{rnd.uniform(-30, -8):.0f}px"></i>')
    return ''.join(out)


LEAF = ('<svg class="fall" viewBox="-10 -10 20 20" width="18" height="18"><path d="M0,-8 Q6,-2 0,8 Q-6,-2 0,-8 Z" fill="#b8742e"/>'
        '<path d="M0,-7 L0,10" stroke="#3a2614" stroke-width="0.6"/></svg>')

OVERLAY = '''<svg class="overlay" viewBox="0 0 1600 1000" width="1600" height="1000">
<defs>
  <filter id="final-grain" x="0" y="0" width="100%" height="100%">
    <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" seed="7" result="n"/>
    <feColorMatrix in="n" type="matrix" values="0 0 0 0 0.45  0 0 0 0 0.4  0 0 0 0 0.3  0 0 0 0.09 0"/>
  </filter>
  <radialGradient id="final-vignette" cx="0.52" cy="0.5" r="0.75">
    <stop offset="0.55" stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#05110f" stop-opacity="0.55"/>
  </radialGradient>
  <radialGradient id="final-warm" cx="0.5" cy="0.55" r="0.4">
    <stop offset="0" stop-color="#f3d27a" stop-opacity="0.08"/><stop offset="1" stop-color="#f3d27a" stop-opacity="0"/>
  </radialGradient>
</defs>
<rect width="1600" height="1000" fill="url(#final-warm)"/>
<rect width="1600" height="1000" fill="url(#final-vignette)"/>
<rect width="1600" height="1000" filter="url(#final-grain)"/>
</svg>'''

CSS = '''
html,body{margin:0;height:100%;background:#061210;overflow:hidden}
#wrap{position:fixed;inset:0;display:flex;align-items:center;justify-content:center}
#stage{position:relative;width:1600px;height:1000px;flex:none;overflow:hidden;transform-origin:center center}
#stage img,#stage .base{position:absolute;display:block}
.base{left:0;top:0;width:1600px;height:1000px}
.overlay{position:absolute;left:0;top:0;pointer-events:none;will-change:transform}
.p{position:absolute;inset:0;pointer-events:none;animation-duration:var(--dur,6s);animation-delay:var(--delay,0s);
   animation-iteration-count:infinite;animation-timing-function:ease-in-out}
.p>.p{inset:0}

.a-sway{animation-name:sway;--a:1.5deg}
@keyframes sway{0%,100%{transform:rotate(var(--a))}50%{transform:rotate(calc(var(--a) * -1))}}
.a-skew{animation-name:skew;--a:1deg}
@keyframes skew{0%,100%{transform:skewX(var(--a))}50%{transform:skewX(calc(var(--a) * -1))}}
.a-frond{animation-name:sway}
.a-bob{animation-name:bob;--dy:4px}
@keyframes bob{0%,100%{transform:translateY(0)}50%{transform:translateY(var(--dy))}}
.a-spin{animation-name:spin;animation-timing-function:linear}
.a-spinR{animation-name:spin;animation-timing-function:linear;animation-direction:reverse}
@keyframes spin{to{transform:rotate(360deg)}}
.a-headtilt{animation-name:headtilt;--dur:6s}
@keyframes headtilt{0%,100%{transform:rotate(0)}25%{transform:rotate(-5deg)}45%{transform:rotate(-4deg)}70%{transform:rotate(3deg)}85%{transform:rotate(1deg)}}
.a-blink{animation-name:blink;--dur:4s;animation-timing-function:linear}
@keyframes blink{0%,90%,94%,100%{transform:scaleY(1)}92%{transform:scaleY(.08)}}
.a-beam{animation-name:beam;--dur:3s}
@keyframes beam{0%,100%{transform:rotate(0);opacity:1}20%{opacity:.8}30%{transform:rotate(-2deg);opacity:1}55%{opacity:.88}70%{transform:rotate(1.5deg)}85%{opacity:.75}}
.a-lamp{animation-name:lamp;--dur:2s}
@keyframes lamp{0%,100%{transform:scale(1);opacity:1}50%{transform:scale(1.25);opacity:.8}}
.a-bubbles{animation-name:bubbles;--dur:3s;animation-timing-function:ease-out}
@keyframes bubbles{0%{transform:translate(0,6px) scale(.5);opacity:0}15%{opacity:1}80%{opacity:.85}100%{transform:translate(10px,-26px) scale(1.25);opacity:0}}
.a-drip{animation-name:drip;--dur:4s;animation-timing-function:ease-in}
@keyframes drip{0%{transform:scale(.3);opacity:0}10%{opacity:1}60%{transform:scale(1) translateY(0);opacity:1}72%{transform:scaleY(1.35) translateY(2px)}90%{transform:translateY(60px);opacity:0}100%{transform:translateY(60px);opacity:0}}
.a-breathe{animation-name:breathe;--dur:4s}
@keyframes breathe{0%,100%{transform:scale(1,1)}45%{transform:scale(1.012,1.03)}}
.a-flyBeetle{animation-name:flyBeetle;--dur:12s}
@keyframes flyBeetle{0%,100%{transform:translate(0,0) rotate(0)}25%{transform:translate(48px,-14px) rotate(-4deg)}50%{transform:translate(80px,6px) rotate(3deg)}75%{transform:translate(30px,16px) rotate(-2deg)}}
.a-prop{animation-name:prop;--dur:.24s;animation-timing-function:linear}
@keyframes prop{0%,100%{transform:scaleX(1)}50%{transform:scaleX(-1)}}
.a-exhaust{animation-name:exhaust;--dur:1s;animation-timing-function:linear}
@keyframes exhaust{0%{transform:translate(-6px,0);opacity:.2}30%{opacity:1}100%{transform:translate(10px,3px);opacity:0}}
.a-flyMoth{animation-name:flyMoth;--dur:12s}
@keyframes flyMoth{0%,100%{transform:translate(0,0) rotate(0)}20%{transform:translate(-26px,-18px) rotate(-8deg)}40%{transform:translate(-8px,-34px) rotate(6deg)}60%{transform:translate(28px,-14px) rotate(10deg)}80%{transform:translate(20px,12px) rotate(-4deg)}}
.a-flap{animation-name:flap;--dur:.4s}
@keyframes flap{0%,100%{transform:scaleX(1)}50%{transform:scaleX(.5)}}
.a-jelly{animation-name:jelly;--dur:6s}
@keyframes jelly{0%,100%{transform:translateY(0) scale(1,1)}25%{transform:translateY(-8px) scale(1.05,.93)}50%{transform:translateY(-16px) scale(1,1)}75%{transform:translateY(-6px) scale(.96,1.04)}}
.a-antennae{animation-name:antennae;--dur:2s}
@keyframes antennae{0%,100%{transform:rotate(0)}20%{transform:rotate(7deg)}40%{transform:rotate(-3deg)}55%{transform:rotate(2deg)}}
.a-smoke{animation-name:smoke;--dur:6s}
@keyframes smoke{0%,100%{transform:skewX(0) scaleY(1);opacity:.9}33%{transform:skewX(-5deg) scaleY(1.04);opacity:1}66%{transform:skewX(4deg) scaleY(.98);opacity:.8}}
.a-flicker{animation-name:flicker;--dur:3s;animation-timing-function:linear}
@keyframes flicker{0%,100%{opacity:1}8%{opacity:.82}14%{opacity:1}30%{opacity:.9}42%{opacity:1}57%{opacity:.75}63%{opacity:.97}78%{opacity:.86}88%{opacity:1}}
.a-needle{animation-name:needle;--dur:1.5s}
@keyframes needle{0%,100%{transform:rotate(0)}30%{transform:rotate(-14deg)}55%{transform:rotate(6deg)}75%{transform:rotate(-4deg)}}
.a-flag{animation-name:flag;--dur:1s}
@keyframes flag{0%,100%{transform:skewY(0) scaleX(1)}33%{transform:skewY(5deg) scaleX(.94)}66%{transform:skewY(-3deg) scaleX(1.02)}}
.a-swing{animation-name:swing;--dur:4s}
@keyframes swing{0%,100%{transform:rotate(4deg)}50%{transform:rotate(-4deg)}}
.a-twinkle{animation-name:twinkle;--dur:3s}
@keyframes twinkle{0%,100%{opacity:1}50%{opacity:.2}}
.a-ladder{animation-name:ladder;--dur:6s}
@keyframes ladder{0%,100%{transform:rotate(2.5deg)}50%{transform:rotate(-2.5deg)}}
.a-glowpulse{animation-name:glowpulse;--dur:4s}
@keyframes glowpulse{0%,100%{opacity:1}50%{opacity:.45}}
.a-rays{animation-name:rays;--dur:12s}
@keyframes rays{0%,100%{opacity:.55;transform:rotate(0)}50%{opacity:1;transform:rotate(1.5deg)}}
.a-spider{animation-name:spider;--dur:6s}
@keyframes spider{0%,100%{transform:translateY(0)}40%{transform:translateY(4px)}60%{transform:translateY(3px)}}
.a-snail{animation-name:snail;--dur:3s}
@keyframes snail{0%,100%{transform:rotate(-18deg) scaleX(1) rotate(18deg)}50%{transform:rotate(-18deg) scaleX(1.06) rotate(18deg)}}
.a-leaf{animation-name:leaf;--dur:6s;--a:12deg}
@keyframes leaf{0%,100%{transform:translate(0,0) rotate(0)}25%{transform:translate(5px,4px) rotate(var(--a))}50%{transform:translate(9px,0) rotate(0)}75%{transform:translate(4px,-4px) rotate(calc(var(--a) * -1))}}
.a-fly1{animation-name:fly1}
.a-fly2{animation-name:fly2}
.a-fly3{animation-name:fly3}
@keyframes fly1{0%,100%{transform:translate(0,0);opacity:1}25%{transform:translate(8px,-10px);opacity:.3}50%{transform:translate(16px,0);opacity:1}75%{transform:translate(7px,9px);opacity:.55}}
@keyframes fly2{0%,100%{transform:translate(0,0);opacity:.4}30%{transform:translate(-12px,-6px);opacity:1}60%{transform:translate(-4px,-16px);opacity:.25}80%{transform:translate(4px,-6px);opacity:1}}
@keyframes fly3{0%,100%{transform:translate(0,0);opacity:1}20%{opacity:.2}40%{transform:translate(10px,10px);opacity:1}70%{transform:translate(-8px,6px);opacity:.6}}

/* extras */
.glow{position:absolute;border-radius:50%;mix-blend-mode:screen;pointer-events:none;
      background:radial-gradient(closest-side,rgba(240,170,80,.42),rgba(240,170,80,0));animation:flicker 3s linear var(--delay) infinite}
.star{position:absolute;border-radius:50%;background:#f4f2dc;box-shadow:0 0 4px 1px rgba(244,242,220,.7);
      animation:twinkle var(--dur) ease-in-out var(--delay) infinite}
.moonglow{position:absolute;left:1030px;top:0;width:460px;height:460px;border-radius:50%;
      background:radial-gradient(circle,rgba(246,242,222,.22) 0%,rgba(246,242,222,.10) 45%,rgba(246,242,222,0) 70%);
      animation:moonglow 12s ease-in-out infinite}
@keyframes moonglow{0%,100%{opacity:.5;transform:scale(1)}50%{opacity:1;transform:scale(1.05)}}
.shoot{position:absolute;left:180px;top:60px;width:140px;height:1.6px;border-radius:2px;
      background:linear-gradient(90deg,rgba(255,250,225,0),rgba(255,250,225,.95));transform-origin:100% 50%;
      animation:shoot 12s linear infinite;opacity:0}
@keyframes shoot{0%,70%{transform:translate(0,0) rotate(18deg) scaleX(.2);opacity:0}71%{opacity:1}76%{transform:translate(380px,125px) rotate(18deg) scaleX(1);opacity:0}100%{opacity:0}}
.puff{position:absolute;left:640px;top:322px;width:22px;height:22px;border-radius:50%;
      background:radial-gradient(circle,rgba(215,212,195,.55),rgba(215,212,195,0) 70%);
      animation:puff 6s ease-out var(--delay) infinite}
@keyframes puff{0%{transform:translate(0,0) scale(.4);opacity:0}12%{opacity:1}100%{transform:translate(calc(70px + var(--sx)),-170px) scale(3.2);opacity:0}}
.spore{position:absolute;border-radius:50%;animation:spore var(--dur) ease-in-out var(--delay) infinite}
.spore.s1{width:3px;height:3px;background:#f6e6a0;box-shadow:0 0 6px 2px rgba(246,230,160,.55)}
.spore.s2{width:2px;height:2px;background:#d9f2cf;box-shadow:0 0 5px 2px rgba(200,240,200,.45)}
.spore.s3{width:5px;height:5px;background:radial-gradient(circle,rgba(255,250,230,.8),rgba(255,250,230,0) 70%)}
@keyframes spore{0%,100%{transform:translate(0,0);opacity:.25}25%{opacity:1}50%{transform:translate(var(--dx),var(--dy));opacity:.6}75%{opacity:1}}
.fall{position:absolute;left:0;top:0;animation:fall 12s linear infinite}
@keyframes fall{0%{transform:translate(1380px,-20px) rotate(0)}25%{transform:translate(1300px,240px) rotate(160deg)}
  50%{transform:translate(1390px,520px) rotate(320deg)}75%{transform:translate(1310px,790px) rotate(480deg)}100%{transform:translate(1370px,1030px) rotate(640deg)}}
#snd{position:fixed;right:18px;bottom:18px;width:46px;height:46px;border-radius:50%;border:1px solid rgba(240,230,200,.35);
     background:rgba(10,24,22,.55);color:#efe6c8;cursor:pointer;display:flex;align-items:center;justify-content:center;
     backdrop-filter:blur(4px);-webkit-backdrop-filter:blur(4px);z-index:5;transition:background .2s}
#snd:hover{background:rgba(30,50,44,.75)}
#snd .on{display:none}#snd.playing .on{display:inline}#snd.playing .off{display:none}
#hint{position:fixed;right:74px;bottom:30px;font:14px/1.2 Georgia,serif;color:#efe6c8;opacity:.85;transition:opacity 1s;
      text-shadow:0 1px 4px #000;pointer-events:none;z-index:5}
#credits{position:fixed;left:14px;bottom:12px;max-width:min(520px,80vw);font:12px/1.45 Georgia,serif;color:rgba(239,230,200,.75);z-index:5}
#credits summary{cursor:pointer;opacity:.6;list-style:none}
#credits[open]{background:rgba(6,18,16,.8);padding:10px 12px;border-radius:8px}
@media (prefers-reduced-motion: reduce){.p,.star,.moonglow,.shoot,.puff,.spore,.fall,.glow{animation:none!important}}
'''

def audio_ui():
    if not audio:
        return ''
    srcs = ','.join(f"['{t}','data:{t};base64,{base64.b64encode(p.read_bytes()).decode()}']"
                    for t, p in zip(('audio/ogg', 'audio/mp4'), audio))
    return f'''<button id="snd" type="button" aria-label="Включить звук" title="Звук">
<svg viewBox="0 0 24 24" width="22" height="22"><path d="M4 9h4l5-4v14l-5-4H4z" fill="currentColor"/>
<path class="on" d="M16 8.5c1.2 1 1.8 2.2 1.8 3.5s-.6 2.5-1.8 3.5M18.5 6c2 1.6 3 3.6 3 6s-1 4.4-3 6" stroke="currentColor" stroke-width="1.6" fill="none" stroke-linecap="round"/>
<path class="off" d="M16.5 9.5l5 5m0-5l-5 5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg></button>
<div id="hint">нажми, чтобы включить звук</div>
<details id="credits"><summary>звуки</summary>
Музыка, гул, тиканье, пузырьки, капли, храп, сова и звездопад синтезированы.<br>
Записи с Wikimedia Commons: «Spring Peeper Frogs… North Pittston PA» — JohnDziak, CC0;
«Howling wind» — Tvabutzku1234, CC0; «Door handle creaking» и «Rusty metal door clasp» — stephan, public domain.</details>
<script>
(function(){{
var SRC=[{srcs}],ctx,buf,node,gain,on=false,btn=document.getElementById('snd'),hint=document.getElementById('hint');
function clock(){{var a=document.getAnimations()[0];return a&&a.startTime!=null?(document.timeline.currentTime-a.startTime)/1000:performance.now()/1000}}
function decode(ab){{return new Promise(function(ok,no){{ctx.decodeAudioData(ab,ok,no)}})}}
async function load(){{
  ctx=new(window.AudioContext||window.webkitAudioContext)();
  for(var i=0;i<SRC.length&&!buf;i++){{try{{buf=await decode(await (await fetch(SRC[i][1])).arrayBuffer())}}catch(e){{}}}}
}}
async function toggle(){{
  hint.style.opacity=0;
  if(!ctx)await load();
  if(!buf)return;
  if(!on){{
    await ctx.resume();
    node=ctx.createBufferSource();node.buffer=buf;node.loop=true;
    gain=ctx.createGain();gain.gain.setValueAtTime(0,ctx.currentTime);gain.gain.linearRampToValueAtTime(1,ctx.currentTime+1.2);
    node.connect(gain);gain.connect(ctx.destination);
    node.start(0,clock()%buf.duration);on=true;
  }}else{{
    gain.gain.cancelScheduledValues(ctx.currentTime);gain.gain.setValueAtTime(gain.gain.value,ctx.currentTime);
    gain.gain.linearRampToValueAtTime(0,ctx.currentTime+.4);node.stop(ctx.currentTime+.45);on=false;
  }}
  btn.classList.toggle('playing',on);btn.setAttribute('aria-label',on?'Выключить звук':'Включить звук');
}}
btn.addEventListener('click',toggle);
setTimeout(function(){{hint.style.opacity=0}},6000);
}})();
</script>'''


FIT = '''<script>
function fit(){var s=Math.min(innerWidth/1600,innerHeight/1000);document.getElementById('stage').style.transform='scale('+s+')'}
addEventListener('resize',fit);fit();
</script>'''

html = f'''<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Samorost — живая картина</title>
<style>{CSS}</style></head>
<body><div id="wrap"><div id="stage">
<img class="base" src="{bg_img}" alt="">
<div class="moonglow"></div>
{stars()}
<i class="shoot"></i>
{bg_parts}
<img class="base" src="{mid_img}" alt="Летающий остров-пень с гномиком в стиле Samorost">
{mid_parts}
<i class="glow" style="left:452px;top:690px;width:136px;height:120px;--delay:-.4s"></i>
<i class="glow" style="left:534px;top:418px;width:76px;height:68px;--delay:-1.7s"></i>
{puffs()}
{spores()}
{LEAF}
{OVERLAY}
</div></div>
{FIT}
{audio_ui()}
</body></html>
'''
out.write_text(html)
print(f'{out} {out.stat().st_size / 1e6:.1f} MB, {len(parts)} sprites')
