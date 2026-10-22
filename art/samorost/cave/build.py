#!/usr/bin/env python3
"""Builds art/samorost/layers/cave.svg and art/samorost/cave/light.svg.
The little hollow under the house: a rolled bark callus lip around a deep,
warmly lit nook with a hanging lantern, shelf of jars, stores, glowing
mushrooms, roots, moss, lichen, bracket fungi, a snail and a rope ladder."""
import math, random, os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', 'layers', 'cave.svg')
LIGHT = os.path.join(HERE, 'light.svg')
R = random.Random(7)

def f(v):
    return ('%.1f' % v).rstrip('0').rstrip('.')

# ---------------------------------------------------------------- shapes
# opening of the hollow (inner edge of the lip)
OPEN = ("M488.5,769 C485.5,754 487.5,737 496,726 C502,718 511,714.5 521,714.5 "
        "C533,714.5 543.5,719.5 549.5,730 C555,740 555.5,755 553.5,769.5 "
        "C541,773.5 501,773.5 488.5,769 Z")
# outer edge of the rolled callus lip
RIM = ("M476.5,777 C471,757 473.5,733 487,716.5 C497,704.5 511,699.5 524,700 "
       "C541,700.5 556,709 563.5,727 C569.5,743 569,763 563.5,780 "
       "C549,788.5 492,789.5 476.5,777 Z")
# a second, deeper chamber going back to the right
TUNNEL = ("M527.5,757 C526.5,746 530.5,736.5 538,735.5 C545,735 548.5,743 547.5,757 "
          "C541,758.5 533,758.5 527.5,757 Z")
# the lit earthen floor
FLOOR = ("M486,768.5 C494,761.5 509,759.5 522,759.5 C536,759.5 548,761 556,766 "
         "L556,776 L486,776 Z")

def taper(pts, w0, w1):
    """Closed tapered ribbon along a polyline (smooth via Catmull-Rom sampling)."""
    # sample catmull-rom
    P = [pts[0]] + pts + [pts[-1]]
    samp = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        for k in range(8):
            t = k / 8
            t2, t3 = t * t, t * t * t
            x = 0.5 * ((2 * p1[0]) + (-p0[0] + p2[0]) * t + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2 + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3)
            y = 0.5 * ((2 * p1[1]) + (-p0[1] + p2[1]) * t + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2 + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3)
            samp.append((x, y))
    samp.append(pts[-1])
    n = len(samp)
    L, Rr = [], []
    for i, (x, y) in enumerate(samp):
        a = samp[max(i - 1, 0)]; b = samp[min(i + 1, n - 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        d = math.hypot(dx, dy) or 1
        nx, ny = -dy / d, dx / d
        w = (w0 + (w1 - w0) * i / (n - 1)) / 2
        L.append((x + nx * w, y + ny * w)); Rr.append((x - nx * w, y - ny * w))
    poly = L + Rr[::-1]
    return 'M' + ' L'.join(f(x) + ',' + f(y) for x, y in poly) + ' Z'

def smooth(pts):
    """Open smooth path through points (quadratic midpoints)."""
    d = 'M%s,%s' % (f(pts[0][0]), f(pts[0][1]))
    for i in range(1, len(pts) - 1):
        mx = (pts[i][0] + pts[i + 1][0]) / 2; my = (pts[i][1] + pts[i + 1][1]) / 2
        d += ' Q%s,%s %s,%s' % (f(pts[i][0]), f(pts[i][1]), f(mx), f(my))
    d += ' L%s,%s' % (f(pts[-1][0]), f(pts[-1][1]))
    return d

def ellipse_pt(cx, cy, rx, ry, a):
    return cx + rx * math.cos(a), cy + ry * math.sin(a)

out = []
A = out.append

# ---------------------------------------------------------------- defs
A('''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 1000" width="1600" height="1000">
<defs>
  <clipPath id="cave-openClip"><path d="%s"/></clipPath>
  <clipPath id="cave-rimClip"><path d="%s"/></clipPath>
  <clipPath id="cave-tunnelClip"><path d="%s"/></clipPath>
  <clipPath id="cave-area"><rect x="458" y="688" width="124" height="114"/></clipPath>
  <filter id="cave-fuzz" x="-10%%" y="-10%%" width="120%%" height="120%%">
    <feTurbulence type="fractalNoise" baseFrequency="0.3" numOctaves="2" seed="13" result="n"/>
    <feDisplacementMap in="SourceGraphic" in2="n" scale="3.2" xChannelSelector="R" yChannelSelector="G"/>
  </filter>
  <filter id="cave-fuzzBig" x="-10%%" y="-10%%" width="120%%" height="120%%">
    <feTurbulence type="fractalNoise" baseFrequency="0.16" numOctaves="3" seed="4" result="n"/>
    <feDisplacementMap in="SourceGraphic" in2="n" scale="5" xChannelSelector="R" yChannelSelector="G" result="d"/>
    <feGaussianBlur in="d" stdDeviation="0.35"/>
  </filter>
  <filter id="cave-rimTex" x="0" y="0" width="1" height="1">
    <feTurbulence type="fractalNoise" baseFrequency="0.09 0.05" numOctaves="4" seed="31" result="n"/>
    <feDiffuseLighting in="n" surfaceScale="3.2" diffuseConstant="1.25" lighting-color="#fff2d8" result="lit">
      <feDistantLight azimuth="-120" elevation="40"/>
    </feDiffuseLighting>
    <feBlend in="SourceGraphic" in2="lit" mode="multiply" result="m"/>
    <feComposite in="m" in2="SourceAlpha" operator="in"/>
  </filter>
  <filter id="cave-grit" x="0" y="0" width="1" height="1">
    <feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves="2" seed="8" result="n"/>
    <feColorMatrix in="n" type="matrix" values="0 0 0 0 0.06  0 0 0 0 0.04  0 0 0 0 0.02  0 0 0 2.6 -1.15" result="g"/>
    <feComposite in="g" in2="SourceGraphic" operator="in"/>
  </filter>
  <filter id="cave-speck" x="0" y="0" width="1" height="1">
    <feTurbulence type="fractalNoise" baseFrequency="0.7" numOctaves="2" seed="19" result="n"/>
    <feColorMatrix in="n" type="matrix" values="0 0 0 0 1  0 0 0 0 0.82  0 0 0 0 0.5  0 0 0 3 -1.75" result="g"/>
    <feComposite in="g" in2="SourceGraphic" operator="in"/>
  </filter>
  <filter id="cave-moss" x="-15%%" y="-15%%" width="130%%" height="130%%">
    <feTurbulence type="fractalNoise" baseFrequency="0.45" numOctaves="3" seed="11" result="n"/>
    <feDisplacementMap in="SourceGraphic" in2="n" scale="4.5" xChannelSelector="R" yChannelSelector="G" result="d"/>
    <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" seed="5" result="n2"/>
    <feColorMatrix in="n2" type="matrix" values="0 0 0 0 0.66  0 0 0 0 0.74  0 0 0 0 0.34  0 0 0 2.4 -1.3" result="spk"/>
    <feComposite in="spk" in2="d" operator="in" result="spk2"/>
    <feMerge><feMergeNode in="d"/><feMergeNode in="spk2"/></feMerge>
  </filter>
  <filter id="cave-b02" x="-30%%" y="-30%%" width="160%%" height="160%%"><feGaussianBlur stdDeviation="0.25"/></filter>
  <filter id="cave-b06" x="-30%%" y="-30%%" width="160%%" height="160%%"><feGaussianBlur stdDeviation="0.6"/></filter>
  <filter id="cave-b1" x="-40%%" y="-40%%" width="180%%" height="180%%"><feGaussianBlur stdDeviation="1.2"/></filter>
  <filter id="cave-b2" x="-50%%" y="-50%%" width="200%%" height="200%%"><feGaussianBlur stdDeviation="2.4"/></filter>
  <filter id="cave-b4" x="-60%%" y="-60%%" width="220%%" height="220%%"><feGaussianBlur stdDeviation="4.5"/></filter>
  <radialGradient id="cave-backGlow" cx="0.47" cy="0.62" r="0.55">
    <stop offset="0" stop-color="#ffe7a6"/>
    <stop offset="0.22" stop-color="#f6b65c"/>
    <stop offset="0.5" stop-color="#b8602a"/>
    <stop offset="0.8" stop-color="#4a200e"/>
    <stop offset="1" stop-color="#1a0b05"/>
  </radialGradient>
  <linearGradient id="cave-ceil" x1="0" y1="714" x2="0" y2="752" gradientUnits="userSpaceOnUse">
    <stop offset="0" stop-color="#0b0503" stop-opacity="1"/>
    <stop offset="0.45" stop-color="#140904" stop-opacity="0.75"/>
    <stop offset="1" stop-color="#140904" stop-opacity="0"/>
  </linearGradient>
  <linearGradient id="cave-floorG" x1="0" y1="759" x2="0" y2="774" gradientUnits="userSpaceOnUse">
    <stop offset="0" stop-color="#d89048"/>
    <stop offset="0.35" stop-color="#9a5a28"/>
    <stop offset="1" stop-color="#3a1c0c"/>
  </linearGradient>
  <linearGradient id="cave-floorSide" x1="486" y1="0" x2="556" y2="0" gradientUnits="userSpaceOnUse">
    <stop offset="0" stop-color="#120804" stop-opacity="0.85"/>
    <stop offset="0.22" stop-color="#120804" stop-opacity="0"/>
    <stop offset="0.78" stop-color="#120804" stop-opacity="0"/>
    <stop offset="1" stop-color="#120804" stop-opacity="0.85"/>
  </linearGradient>
  <linearGradient id="cave-rimG" x1="480" y1="700" x2="560" y2="785" gradientUnits="userSpaceOnUse">
    <stop offset="0" stop-color="#7a6644"/>
    <stop offset="0.45" stop-color="#5c4a30"/>
    <stop offset="1" stop-color="#2e2418"/>
  </linearGradient>
  <radialGradient id="cave-lampGlow" cx="0.5" cy="0.5" r="0.5">
    <stop offset="0" stop-color="#fff6c8" stop-opacity="1"/>
    <stop offset="0.25" stop-color="#ffd27a" stop-opacity="0.75"/>
    <stop offset="0.6" stop-color="#f08a34" stop-opacity="0.25"/>
    <stop offset="1" stop-color="#e07020" stop-opacity="0"/>
  </radialGradient>
  <radialGradient id="cave-mushGlow" cx="0.5" cy="0.5" r="0.5">
    <stop offset="0" stop-color="#d8fff0" stop-opacity="0.9"/>
    <stop offset="0.4" stop-color="#8fe0c8" stop-opacity="0.35"/>
    <stop offset="1" stop-color="#5ac0a8" stop-opacity="0"/>
  </radialGradient>
  <radialGradient id="cave-spill" cx="0.5" cy="0.2" r="0.6">
    <stop offset="0" stop-color="#ffb860" stop-opacity="0.55"/>
    <stop offset="0.5" stop-color="#e07a30" stop-opacity="0.2"/>
    <stop offset="1" stop-color="#e07a30" stop-opacity="0"/>
  </radialGradient>
  <radialGradient id="cave-shell" cx="0.4" cy="0.35" r="0.7">
    <stop offset="0" stop-color="#f0c070"/>
    <stop offset="0.6" stop-color="#b8642a"/>
    <stop offset="1" stop-color="#5a2a10"/>
  </radialGradient>
</defs>
''' % (OPEN, RIM, TUNNEL))

A('<g id="cave-layer" clip-path="url(#cave-area)">')

# ---------------------------------------------------------------- 1. shadow ring outside the lip (raised callus casts shade on bark)
A('<path d="%s" fill="none" stroke="#120d08" stroke-width="7" opacity="0.55" filter="url(#cave-b2)"/>' % RIM)

# ---------------------------------------------------------------- 2. the rolled bark lip
A('<g id="cave-rim">')
A('<path d="%s" fill="url(#cave-rimG)" filter="url(#cave-fuzzBig)"/>' % RIM)
A('<g clip-path="url(#cave-rimClip)">')
A('<path d="%s" fill="url(#cave-rimG)" filter="url(#cave-rimTex)"/>' % RIM)
# concentric growth rings of the callus around the wound
for i, (k, col, op, w) in enumerate([(1.06, '#a8905e', 0.55, 1.1), (1.13, '#21180f', 0.55, 1.0),
                                     (1.2, '#9a8254', 0.45, 0.9), (1.28, '#1d150d', 0.5, 1.1),
                                     (1.36, '#8a7450', 0.35, 0.8), (1.44, '#1d150d', 0.35, 1.2)]):
    cx, cy = 520.5, 746
    pts = []
    for j in range(15):
        a = math.pi * (0.97 + 1.06 * j / 14)  # from lower-left over the top to lower-right
        rx, ry = 33.5 * k, 31.5 * k
        x, y = ellipse_pt(cx, cy, rx, ry, a)
        x += R.uniform(-0.7, 0.7); y += R.uniform(-0.7, 0.7)
        pts.append((x, y))
    A('<path d="%s" fill="none" stroke="%s" stroke-width="%s" opacity="%s" stroke-linecap="round" filter="url(#cave-fuzz)"/>'
      % (smooth(pts), col, w, op))
# lower lip rings (flatter, under the floor)
for k, col, op in [(0, '#c8884a', 0.55), (3.5, '#22180e', 0.6), (6.5, '#a07040', 0.35), (9.5, '#1d150d', 0.45)]:
    y0 = 772.5 + k
    A('<path d="M%s,%s C%s,%s %s,%s %s,%s" fill="none" stroke="%s" stroke-width="1.1" opacity="%s" filter="url(#cave-fuzz)"/>'
      % (f(484 - k * 0.9), f(y0 - 3), f(500), f(y0 + 2.5), f(540), f(y0 + 2.5), f(557 + k * 0.9), f(y0 - 3), col, op))
# vertical bark fibres running into the lip
for i in range(26):
    x = R.uniform(474, 566); y = R.uniform(700, 786)
    dx = (x - 520.5); dy = (y - 746)
    if (dx / 34) ** 2 + (dy / 31) ** 2 < 1.15: continue
    l = R.uniform(4, 9)
    A('<path d="M%s,%s q%s,%s %s,%s" stroke="%s" stroke-width="%s" opacity="%s" fill="none"/>'
      % (f(x), f(y), f(R.uniform(-1, 1)), f(l / 2), f(R.uniform(-1.5, 1.5)), f(l),
         R.choice(['#1a120a', '#1a120a', '#b09a6a']), f(R.uniform(0.5, 0.9)), f(R.uniform(0.25, 0.5))))
# top-left light, bottom-right shade on the roll
A('<ellipse cx="497" cy="714" rx="22" ry="12" fill="#d8c08a" opacity="0.16" filter="url(#cave-b2)"/>')
A('<ellipse cx="556" cy="772" rx="16" ry="14" fill="#0d0905" opacity="0.45" filter="url(#cave-b2)"/>')
# warm light from the hollow licking the lower inner lip
A('<path d="M486,773 C500,779 540,779 556,772" fill="none" stroke="#f0a050" stroke-width="5" opacity="0.35" filter="url(#cave-b2)"/>')
A('<rect x="470" y="690" width="104" height="104" fill="#000" filter="url(#cave-grit)" opacity="0.9"/>')
A('</g>')
A('</g>')

# ---------------------------------------------------------------- 3. interior of the hollow
A('<g id="cave-inside" clip-path="url(#cave-openClip)">')
A('<rect x="480" y="708" width="80" height="70" fill="#100703"/>')
# back wall glow
A('<ellipse cx="516" cy="752" rx="34" ry="30" fill="url(#cave-backGlow)" filter="url(#cave-b1)"/>')
# back-wall wood grain catching light: curved ribs following the hollow
for i in range(14):
    x0 = R.uniform(492, 548); y0 = R.uniform(724, 752)
    side = -1 if x0 < 520 else 1
    A('<path d="M%s,%s q%s,%s %s,%s" stroke="%s" stroke-width="%s" opacity="%s" fill="none" stroke-linecap="round"/>'
      % (f(x0), f(y0), f(side * R.uniform(1, 3)), f(R.uniform(4, 7)), f(side * R.uniform(0, 2)), f(R.uniform(9, 15)),
         R.choice(['#ffd890', '#5a2a10', '#3a1808', '#f0b060']), f(R.uniform(0.4, 0.8)), f(R.uniform(0.2, 0.45))))
A('<rect x="480" y="708" width="80" height="70" fill="#000" filter="url(#cave-speck)" opacity="0.18"/>')
A('<rect x="480" y="708" width="80" height="70" fill="#000" filter="url(#cave-grit)" opacity="0.7"/>')

# the deeper chamber at the back right: darker hole with a faint far glow and a pair of shy eyes
A('<path d="%s" fill="#1c0c05" opacity="0.92" filter="url(#cave-fuzz)"/>' % TUNNEL)
A('<g clip-path="url(#cave-tunnelClip)">')
A('<ellipse cx="539" cy="754" rx="7" ry="5" fill="#b8642a" opacity="0.55" filter="url(#cave-b1)"/>')
A('<ellipse cx="540" cy="752" rx="2.6" ry="2.1" fill="#ffc870" opacity="0.65" filter="url(#cave-b06)"/>')
A('</g>')
A('<path d="M528,757 C527,746 531,736.5 538,735.5 C545,735 548.5,743 547.5,757" fill="none" stroke="#e89a50" stroke-width="0.8" opacity="0.5" filter="url(#cave-fuzz)"/>')
# shy eyes in the dark of the tunnel
for ex in (536.6, 540.4):
    A('<ellipse cx="%s" cy="744.2" rx="0.95" ry="1.15" fill="#fff4c4"/>' % f(ex))
    A('<circle cx="%s" cy="744.5" r="0.45" fill="#1a0c04"/>' % f(ex + 0.2))

# ceiling darkness and inner shade along the walls
A('<rect x="480" y="708" width="80" height="50" fill="url(#cave-ceil)"/>')
A('<path d="%s" fill="none" stroke="#080402" stroke-width="7" opacity="0.85" filter="url(#cave-b2)"/>' % OPEN)

# little roots poking through the ceiling, silhouetted, with warm rim light
for (x0, len_, cur) in [(503, 13, 1.5), (507, 8, -1), (526, 10, 2), (531, 15, -1.5), (544, 9, 1)]:
    pts = [(x0, 714), (x0 + cur * 0.6, 714 + len_ * 0.45), (x0 + cur, 714 + len_)]
    A('<path d="%s" fill="#160a04"/>' % taper(pts, 1.6, 0.2))
    A('<path d="%s" fill="none" stroke="#f0a050" stroke-width="0.35" opacity="0.7"/>'
      % smooth([(x0 + 0.5, 718), (x0 + cur * 0.6 + 0.4, 714 + len_ * 0.45), (x0 + cur + 0.2, 714 + len_ - 0.5)]))

# shelf on the left wall with jars of preserves
A('<path d="M493,748.8 L507.5,747.6" stroke="#2a1408" stroke-width="1.3" stroke-linecap="round"/>')
A('<path d="M493,748.1 L507.5,746.9" stroke="#f0b060" stroke-width="0.4" opacity="0.8"/>')
A('<path d="M495,748.6 l-0.6,3 M506,747.7 l0.4,3" stroke="#2a1408" stroke-width="0.6"/>')
for (x, h, col, lid) in [(495.2, 3.6, '#c8562a', '#5a3018'), (498.4, 2.8, '#8a9a3a', '#4a3018'),
                         (501.2, 4.2, '#e0a848', '#5a3018'), (504.4, 3.0, '#7a3a58', '#4a3018')]:
    A('<rect x="%s" y="%s" width="2.3" height="%s" rx="0.8" fill="%s"/>' % (f(x), f(747.6 - h), f(h), col))
    A('<rect x="%s" y="%s" width="2.3" height="0.8" fill="%s"/>' % (f(x), f(747.6 - h), lid))
    A('<rect x="%s" y="%s" width="0.45" height="%s" fill="#fff4d0" opacity="0.8"/>' % (f(x + 1.5), f(747.6 - h + 1.1), f(h - 1.6)))
# bundle of dried herbs hanging on the left wall
A('<path d="M497,733 l0,4" stroke="#3a2010" stroke-width="0.4"/>')
for dx in (-1.1, -0.4, 0.3, 1.0):
    A('<path d="M497,737 q%s,3 %s,6" stroke="#6a7a30" stroke-width="0.7" fill="none" stroke-linecap="round"/>' % (f(dx * 0.6), f(dx * 1.6)))
A('<circle cx="497" cy="737" r="0.7" fill="#9a4a20"/>')

# the floor
A('<path d="%s" fill="url(#cave-floorG)" filter="url(#cave-fuzz)"/>' % FLOOR)
A('<path d="%s" fill="url(#cave-floorSide)"/>' % FLOOR)
A('<path d="M489,766.5 C500,760.6 540,760 553,764.5" fill="none" stroke="#ffd690" stroke-width="0.6" opacity="0.55" filter="url(#cave-fuzz)"/>')
# woven rug
A('<ellipse cx="517" cy="765.2" rx="10.5" ry="2.4" fill="#8a2e1a"/>')
A('<ellipse cx="517" cy="765.2" rx="8" ry="1.6" fill="none" stroke="#e8a448" stroke-width="0.45" stroke-dasharray="1 0.8"/>')
A('<ellipse cx="517" cy="765.2" rx="4.5" ry="0.8" fill="#c86a2a"/>')
A('<ellipse cx="517" cy="764.6" rx="10" ry="1.4" fill="#ffd690" opacity="0.18"/>')
# a tiny mushroom-stool table with a steaming cup
A('<path d="M520.6,764.6 L521,760.6 L522.2,760.6 L522.6,764.6 Z" fill="#e8d0a0"/>')
A('<ellipse cx="521.6" cy="760.4" rx="4" ry="1.2" fill="#a83a1c"/>')
A('<ellipse cx="521.2" cy="759.9" rx="3.2" ry="0.6" fill="#e0703a"/>')
A('<circle cx="520" cy="760.2" r="0.35" fill="#fff0d0"/><circle cx="523.2" cy="760.4" r="0.3" fill="#fff0d0"/>')
A('<rect x="522" y="757.6" width="1.6" height="1.9" rx="0.4" fill="#f4ecd8"/>')
A('<path d="M523.6,758 q0.8,0.3 0,1" stroke="#f4ecd8" stroke-width="0.35" fill="none"/>')
A('<path d="M522.6,757 q-0.8,-1.5 0.2,-2.8 q0.8,-1.2 -0.1,-2.6" stroke="#fff4dc" stroke-width="0.4" fill="none" opacity="0.45" filter="url(#cave-b02)"/>')
# a little round bed/nest of moss and a blanket at the left back
A('<ellipse cx="502" cy="763.5" rx="6.5" ry="2.6" fill="#3a3a18"/>')
A('<ellipse cx="502" cy="762.6" rx="5.6" ry="1.9" fill="#6a7a30"/>')
A('<path d="M497.5,763 C499,760.6 505,760.4 507.5,762.2 L506.5,764 C503,764.6 500,764.4 497.5,763 Z" fill="#b84a2a"/>')
A('<path d="M499,762.4 L506,762.2" stroke="#f0c070" stroke-width="0.35" stroke-dasharray="0.7 0.6"/>')
A('<ellipse cx="498.5" cy="761.6" rx="1.5" ry="1" fill="#e8dcc0"/>')
# stores on the right: a barrel and a fat sack, plus a few nuts
A('<path d="M541.8,767.8 L541.4,761.2 Q544.2,760.2 547,761.2 L546.6,767.8 Q544.2,768.6 541.8,767.8 Z" fill="#7a3e18"/>')
A('<path d="M541.5,763.2 Q544.2,762.4 546.9,763.2 M541.7,766 Q544.2,765.3 546.7,766" stroke="#2a1408" stroke-width="0.5" fill="none"/>')
A('<path d="M542.5,761.5 L542.7,767.4" stroke="#f0b060" stroke-width="0.45" opacity="0.7"/>')
A('<ellipse cx="544.2" cy="761.2" rx="2.8" ry="0.7" fill="#4a240c"/>')
A('<path d="M533.5,768 C532.5,764.5 534,761.5 536.6,761.6 C539.2,761.7 540.6,764.6 539.8,768 Z" fill="#c8a468"/>')
A('<path d="M535.3,761.9 L536.6,760.4 L537.9,761.9" stroke="#6a4a24" stroke-width="0.5" fill="none"/>')
A('<path d="M534.4,763.4 C534.1,765 534.3,766.4 534.8,767.6" stroke="#fff0c8" stroke-width="0.45" fill="none" opacity="0.7"/>')
for (x, y) in [(530.6, 767.6), (531.9, 768.2), (548.5, 768.4)]:
    A('<ellipse cx="%s" cy="%s" rx="0.85" ry="0.7" fill="#8a4a1c"/><circle cx="%s" cy="%s" r="0.25" fill="#ffd690"/>' % (f(x), f(y), f(x - 0.3), f(y - 0.3)))
# floor bottom shade
A('<rect x="480" y="769" width="80" height="8" fill="#1a0b04" opacity="0.5" filter="url(#cave-b06)"/>')

# the hanging lantern (main light source)
A('<path d="M513.2,714 C513.4,719 512.8,723 513,728.4" stroke="#1a0c04" stroke-width="0.5" fill="none"/>')
A('<circle cx="513" cy="732" r="9" fill="url(#cave-lampGlow)" opacity="0.85"/>')
A('<path d="M511.2,729.4 L514.8,729.4 L513,727.8 Z" fill="#2a160a"/>')
A('<rect x="511.4" y="729.4" width="3.2" height="4.6" rx="0.9" fill="#fff2b8"/>')
A('<rect x="512.3" y="730.2" width="1.4" height="3" rx="0.6" fill="#ffffff"/>')
A('<path d="M511.4,730.8 L514.6,730.8 M513,729.4 L513,734" stroke="#4a2810" stroke-width="0.35" opacity="0.7"/>')
A('<rect x="511.2" y="733.8" width="3.6" height="0.8" rx="0.3" fill="#2a160a"/>')
A('</g>')

# ---------------------------------------------------------------- 4. lip edge: darkness inside + lit lower threshold
A('<path d="M488.5,769 C485.5,754 487.5,737 496,726 C502,718 511,714.5 521,714.5 C533,714.5 543.5,719.5 549.5,730 C555,740 555.5,755 553.5,769.5" '
  'fill="none" stroke="#1a0f08" stroke-width="2" filter="url(#cave-fuzz)"/>')
A('<path d="M490,725 C497,716 509,712.6 521,712.8 C534,713 545,718.5 551,729" fill="none" stroke="#b49a6a" stroke-width="0.9" opacity="0.55" filter="url(#cave-fuzz)"/>')
A('<path d="M488.5,769.2 C501,773.8 541,773.8 553.5,769.8" fill="none" stroke="#ffc070" stroke-width="1.5" opacity="0.85" filter="url(#cave-fuzz)"/>')
A('<path d="M489,770.6 C502,775 540,775 553,771" fill="none" stroke="#3a1c0c" stroke-width="0.8" opacity="0.6"/>')
# glowing mushrooms at the lower-left inner corner of the entrance
A('<circle cx="493" cy="767" r="6" fill="url(#cave-mushGlow)"/>')
for (x, y, s) in [(490.6, 768.4, 1.0), (492.8, 767.2, 1.35), (495.3, 768.8, 0.85), (489.3, 766.6, 0.7)]:
    A('<path d="M%s,%s L%s,%s" stroke="#e8fff4" stroke-width="%s" stroke-linecap="round"/>' % (f(x), f(y + 2.4 * s), f(x + 0.15), f(y), f(0.55 * s)))
    A('<path d="M%s,%s q%s,%s %s,0 Z" fill="#bff5e2"/>' % (f(x - 1.5 * s), f(y + 0.3), f(1.5 * s), f(-2.4 * s), f(3 * s)))
    A('<circle cx="%s" cy="%s" r="%s" fill="#ffffff" opacity="0.9"/>' % (f(x - 0.4 * s), f(y - 0.7 * s), f(0.35 * s)))

# ---------------------------------------------------------------- 5. roots woven over the lip and hanging over the entrance
roots = [
    # thick root arching over the top from the left, sinking into the bark on the right
    ([(474, 742), (480, 722), (494, 708.5), (512, 704), (530, 705), (546, 711), (558, 722)], 4.2, 1.6),
    ([(488, 703), (499, 709), (504, 717), (503.5, 727), (501.5, 737)], 2.2, 0.35),
    ([(519, 700), (520, 708), (518.5, 716), (519.5, 724)], 1.5, 0.3),
    ([(536, 702), (538, 710), (540.5, 719), (539.6, 731), (541, 741)], 1.9, 0.3),
    ([(552, 709), (553.5, 718), (556.5, 726), (556, 736), (558.5, 744)], 1.6, 0.3),
    ([(565, 726), (562, 740), (564, 756), (562.5, 772)], 2.6, 1.2),
]
for pts, w0, w1 in roots:
    d = taper(pts, w0, w1)
    A('<path d="%s" fill="#000" opacity="0.35" transform="translate(0.8,1.2)" filter="url(#cave-b06)"/>' % d)
    A('<path d="%s" fill="#4a3220" filter="url(#cave-fuzz)"/>' % d)
    hl = [(x - 0.35 * w0 * 0.5, y - 0.3) for x, y in pts[:-1]]
    A('<path d="%s" fill="none" stroke="#c8a070" stroke-width="%s" opacity="0.6" stroke-linecap="round"/>' % (smooth(hl), f(max(0.35, w0 * 0.22))))
# warm rim light on hanging root tips in front of the glow
for pts in [[(503.5, 727), (501.5, 737)], [(518.5, 716), (519.5, 724)], [(539.6, 731), (541, 741)], [(556, 736), (558.5, 744)]]:
    A('<path d="%s" fill="none" stroke="#ffb860" stroke-width="0.45" opacity="0.8"/>' % smooth([(pts[0][0] + 0.6, pts[0][1]), (pts[1][0] + 0.4, pts[1][1] - 0.6)]))
# tiny dew drops on the root tips
for (x, y) in [(501.4, 738.4), (519.5, 725.2), (541.1, 742.3)]:
    A('<ellipse cx="%s" cy="%s" rx="0.7" ry="0.9" fill="#ffe0a0" opacity="0.9"/><circle cx="%s" cy="%s" r="0.25" fill="#fff"/>' % (f(x), f(y), f(x - 0.2), f(y - 0.3)))
# fine rootlets
for i in range(9):
    x = R.uniform(486, 556); y = R.uniform(703, 712)
    A('<path d="M%s,%s q%s,%s %s,%s" stroke="#2a1a0e" stroke-width="0.4" fill="none" opacity="0.8"/>'
      % (f(x), f(y), f(R.uniform(-2, 2)), f(R.uniform(2, 4)), f(R.uniform(-2, 2)), f(R.uniform(4, 8))))

# ---------------------------------------------------------------- 6. moss cushions, lichen, bracket fungi, snail
A('<g filter="url(#cave-moss)">')
A('<path d="M476,733 C474,720 482,707 494,702 C503,698.5 512,699 518,702.5 C510,704 500,707.5 492,714 C485,720 481,728 480,738 Z" fill="#3a4a1e"/>')
A('<path d="M480,726 C482,716 490,708 500,704.5 C496,709 491,714 487,721 Z" fill="#6f8034"/>')
A('<path d="M556,776 C561,770 567,769 569,774 C567,780 560,782 555,781 Z" fill="#3a4a1e"/>')
A('<path d="M484,780 C488,776 496,777 499,781 C494,783.5 487,783.5 484,780 Z" fill="#45561f"/>')
A('</g>')
for i in range(26):
    x = R.uniform(477, 517); y = R.uniform(700, 732)
    if y > 745 - (x - 470) * 1.3 + 20: continue
    A('<circle cx="%s" cy="%s" r="%s" fill="%s" opacity="0.85"/>' % (f(x), f(y), f(R.uniform(0.3, 0.7)), R.choice(['#9aae4a', '#b8c860', '#556a26'])))
# moss sporophytes (tiny stalks with heads)
for (x, y, h) in [(486, 709, 3.5), (488.5, 707.4, 4.2), (491, 706, 3.2), (494, 704.6, 3.8)]:
    A('<path d="M%s,%s q0.6,%s 0.3,%s" stroke="#c89a50" stroke-width="0.35" fill="none"/><ellipse cx="%s" cy="%s" rx="0.45" ry="0.7" fill="#d87a3a"/>'
      % (f(x), f(y), f(-h / 2), f(-h), f(x + 0.3), f(y - h)))
# lichen rosettes on the right of the lip
for i in range(16):
    a = R.uniform(-1.2, 0.5); rr = R.uniform(38, 46)
    x = 520.5 + rr * math.cos(a) * 1.0; y = 746 + rr * math.sin(a) * 0.95
    s = R.uniform(0.6, 1.5)
    A('<circle cx="%s" cy="%s" r="%s" fill="%s" opacity="0.8" filter="url(#cave-fuzz)"/>' % (f(x), f(y), f(s), R.choice(['#a8b4a0', '#c0c8b0', '#8a9a88', '#d8c890'])))
# bracket fungi on the lower right of the lip
for (x, y, s) in [(560.5, 762, 1.0), (564.5, 767.5, 1.25), (559, 770.5, 0.8)]:
    A('<path d="M%s,%s C%s,%s %s,%s %s,%s C%s,%s %s,%s %s,%s Z" fill="#c8682a" filter="url(#cave-fuzz)"/>'
      % (f(x - 4 * s), f(y), f(x - 3.5 * s), f(y - 2.8 * s), f(x + 3.5 * s), f(y - 2.8 * s), f(x + 4 * s), f(y),
         f(x + 2 * s), f(y + 0.9 * s), f(x - 2 * s), f(y + 0.9 * s), f(x - 4 * s), f(y)))
    A('<path d="M%s,%s C%s,%s %s,%s %s,%s" fill="none" stroke="#f4b868" stroke-width="%s"/>'
      % (f(x - 3.6 * s), f(y - 0.6 * s), f(x - 2.8 * s), f(y - 2.6 * s), f(x + 2.8 * s), f(y - 2.6 * s), f(x + 3.6 * s), f(y - 0.6 * s), f(0.5 * s)))
    A('<path d="M%s,%s C%s,%s %s,%s %s,%s" fill="none" stroke="#5a2410" stroke-width="%s" opacity="0.8"/>'
      % (f(x - 3.8 * s), f(y + 0.2), f(x - 2, ), f(y + 1.0 * s), f(x + 2), f(y + 1.0 * s), f(x + 3.8 * s), f(y + 0.2), f(0.45 * s)))
# a snail climbing the left side of the lip
A('<path d="M478.5,756 C478,752 478.6,749 479.6,747.2 C480.4,746.4 481.2,747 481,748.4 C480.8,751 480.6,754 480.4,756.6 Z" fill="#c8b490"/>')
A('<path d="M479.9,747.2 l-0.7,-1.6 M480.6,747.1 l0.3,-1.7" stroke="#c8b490" stroke-width="0.35"/>')
A('<circle cx="482.2" cy="752.8" r="3" fill="url(#cave-shell)"/>')
A('<path d="M482.2,752.8 m0.9,0 a0.9,0.9 0 1 1 -0.9,-0.9 a1.8,1.8 0 1 1 -1.6,2.4 a2.6,2.6 0 0 1 3.2,-3.6" stroke="#4a200c" stroke-width="0.35" fill="none"/>')
A('<circle cx="481.3" cy="751.6" r="0.5" fill="#fff0c8" opacity="0.8"/>')

# ---------------------------------------------------------------- 7. rope ladder dangling from the threshold
ropeL = [(512.5, 773.5), (512.2, 781), (512.8, 789), (512.3, 797)]
ropeR = [(518.5, 773.7), (518.8, 781), (518.4, 789), (519, 797)]
A('<path d="%s" stroke="#c8a468" stroke-width="0.55" fill="none"/>' % smooth(ropeL))
A('<path d="%s" stroke="#c8a468" stroke-width="0.55" fill="none"/>' % smooth(ropeR))
for i, y in enumerate(range(777, 798, 4)):
    A('<path d="M%s,%s L%s,%s" stroke="#6a3c18" stroke-width="1" stroke-linecap="round"/>' % (f(511.8), f(y + 0.2 * (i % 2)), f(519.2), f(y - 0.1)))
    A('<path d="M%s,%s L%s,%s" stroke="#f0b060" stroke-width="0.35" opacity="%s"/>' % (f(512), f(y - 0.35 + 0.2 * (i % 2)), f(519), f(y - 0.45), f(max(0.15, 0.85 - i * 0.15))))
A('<circle cx="512.5" cy="773.6" r="0.8" fill="#3a2010"/><circle cx="518.5" cy="773.8" r="0.8" fill="#3a2010"/>')

# ---------------------------------------------------------------- 8. warm light spilling out of the hollow (static part)
A('<ellipse cx="519" cy="782" rx="30" ry="9" fill="url(#cave-spill)" filter="url(#cave-b2)"/>')
A('<ellipse cx="520" cy="745" rx="40" ry="36" fill="#f09a48" opacity="0.07" filter="url(#cave-b4)"/>')

A('</g>')
A('</svg>')

open(OUT, 'w').write('\n'.join(out) + '\n')

# ---------------------------------------------------------------- light.svg: flickering glow only
light = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 1000" width="1600" height="1000">
<defs>
  <clipPath id="cavelight-open"><path d="%s"/></clipPath>
  <filter id="cavelight-blur" x="-60%%" y="-60%%" width="220%%" height="220%%"><feGaussianBlur stdDeviation="3"/></filter>
  <filter id="cavelight-blurBig" x="-60%%" y="-60%%" width="220%%" height="220%%"><feGaussianBlur stdDeviation="9"/></filter>
  <radialGradient id="cavelight-g" cx="0.5" cy="0.5" r="0.5">
    <stop offset="0" stop-color="#ffe2a0" stop-opacity="0.6"/>
    <stop offset="0.5" stop-color="#f09a48" stop-opacity="0.22"/>
    <stop offset="1" stop-color="#e07a30" stop-opacity="0"/>
  </radialGradient>
</defs>
<g id="cavelight-layer" style="mix-blend-mode:screen">
  <g clip-path="url(#cavelight-open)"><ellipse cx="514" cy="738" rx="20" ry="18" fill="url(#cavelight-g)" filter="url(#cavelight-blur)"/></g>
  <ellipse cx="519" cy="752" rx="46" ry="40" fill="url(#cavelight-g)" opacity="0.35" filter="url(#cavelight-blurBig)"/>
  <ellipse cx="519" cy="778" rx="26" ry="6" fill="#ffb860" opacity="0.18" filter="url(#cavelight-blur)"/>
</g>
</svg>
''' % OPEN
open(LIGHT, 'w').write(light)
print('ok')
