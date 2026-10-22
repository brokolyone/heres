#!/usr/bin/env python3
"""Generate door leaf_0/1/2 + doorway SVGs for the Samorost stump house."""
import math, os, random

OUT = '/home/user/heres/art/samorost/door'
HX, CX, CY, R = 504.0, 538.0, 524.0, 34.0
W = 68.0
# viewer / vanishing centre for the swing perspective
VX, VY, D = 540.0, 455.0, 190.0
THICK = 4.2


def bottom(u):
    return 565.2 - 2.0 * u / W


def top(u):
    du = u - R
    return CY - math.sqrt(max(0.0, R * R - du * du))


def P(u, y, th, depth=0.0):
    """project local leaf point (u from hinge, screen y) for swing angle th (deg).
    depth: offset along the leaf normal into the house (thickness)."""
    t = math.radians(th)
    X = HX + u * math.cos(t) - depth * math.sin(t)
    Z = u * math.sin(t) + depth * math.cos(t)
    if th == 0 and depth == 0:
        return (X, y)
    s = D / (D + Z)
    return (VX + (X - VX) * s, VY + (y - VY) * s)


def f(v):
    return f'{v:.2f}'.rstrip('0').rstrip('.')


def path(pts, close=True):
    d = 'M' + ' L'.join(f'{f(x)},{f(y)}' for x, y in pts)
    return d + (' Z' if close else '')


def leaf_outline(th, depth=0.0, u0=0.0, u1=W, n=40):
    pts = [P(u0, bottom(u0), th, depth)]
    for i in range(n + 1):
        u = u0 + (u1 - u0) * i / n
        pts.append(P(u, top(u), th, depth))
    pts.append(P(u1, bottom(u1), th, depth))
    return pts


def strip(u0, u1, y0f, y1f, th, n=10):
    """quad strip between u0..u1 with y given by functions of u"""
    a = [P(u0 + (u1 - u0) * i / n, y0f(u0 + (u1 - u0) * i / n), th) for i in range(n + 1)]
    b = [P(u0 + (u1 - u0) * i / n, y1f(u0 + (u1 - u0) * i / n), th) for i in range(n, -1, -1)]
    return a + b


def scale_at(u, th):
    t = math.radians(th)
    Z = u * math.sin(t)
    return D / (D + Z) if th else 1.0


SEAMS = [7.0, 20.5, 34.0, 47.5, 61.0]
PLANK_TONES = ['#8a6f52', '#a08665', '#866a4b', '#9b7f5c', '#7f6447', '#957a58']


def strap_y(base):
    return lambda u: base + 1.2 * math.sin(u / 68 * math.pi) * 0.6 + (u / 68) * 0.6


def leaf_svg(name, th):
    p = name  # id prefix
    random.seed(7)
    dark = {0: 0.0, 40: 0.55, 80: 0.78}[th]
    o = []
    o.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 1000" width="1600" height="1000">')
    o.append('<defs>')
    o.append(f'''<filter id="{p}-grain" x="-5%" y="-5%" width="110%" height="110%" color-interpolation-filters="sRGB">
  <feTurbulence type="fractalNoise" baseFrequency="{f(1.4/max(0.3, math.cos(math.radians(th))))} 0.045" numOctaves="3" seed="11" result="n"/>
  <feColorMatrix in="n" type="matrix" values="0 0 0 0 0.16  0 0 0 0 0.10  0 0 0 0 0.05  2.2 0 0 0 -0.95" result="g"/>
  <feComposite in="g" in2="SourceGraphic" operator="in" result="gi"/>
  <feTurbulence type="fractalNoise" baseFrequency="0.5 0.03" numOctaves="2" seed="4" result="n2"/>
  <feColorMatrix in="n2" type="matrix" values="0 0 0 0 0.93  0 0 0 0 0.86  0 0 0 0 0.72  -2.4 0 0 0 1.05" result="h"/>
  <feComposite in="h" in2="SourceGraphic" operator="in" result="hi"/>
  <feMerge><feMergeNode in="SourceGraphic"/><feMergeNode in="hi"/><feMergeNode in="gi"/></feMerge>
</filter>
<filter id="{p}-rust" x="-10%" y="-60%" width="120%" height="220%" color-interpolation-filters="sRGB">
  <feTurbulence type="fractalNoise" baseFrequency="0.7" numOctaves="3" seed="3" result="n"/>
  <feDisplacementMap in="SourceGraphic" in2="n" scale="1.4" xChannelSelector="R" yChannelSelector="G" result="d"/>
  <feColorMatrix in="n" type="matrix" values="0 0 0 0 0.62  0 0 0 0 0.30  0 0 0 0 0.12  0 2.6 0 0 -1.25" result="r"/>
  <feComposite in="r" in2="d" operator="in" result="ri"/>
  <feMerge><feMergeNode in="d"/><feMergeNode in="ri"/></feMerge>
</filter>
<filter id="{p}-rough" x="-10%" y="-10%" width="120%" height="120%">
  <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" seed="9" result="n"/>
  <feDisplacementMap in="SourceGraphic" in2="n" scale="1.1" xChannelSelector="R" yChannelSelector="G"/>
</filter>
<filter id="{p}-moss" x="-20%" y="-50%" width="140%" height="200%" color-interpolation-filters="sRGB">
  <feTurbulence type="fractalNoise" baseFrequency="1.3" numOctaves="2" seed="21" result="n"/>
  <feDisplacementMap in="SourceGraphic" in2="n" scale="2.6" xChannelSelector="R" yChannelSelector="G" result="d"/>
  <feColorMatrix in="n" type="matrix" values="0 0 0 0 0.75  0 0 0 0 0.85  0 0 0 0 0.35  2.4 0 0 0 -1.25" result="sp"/>
  <feComposite in="sp" in2="d" operator="in" result="spi"/>
  <feMerge><feMergeNode in="d"/><feMergeNode in="spi"/></feMerge>
</filter>
<filter id="{p}-glow" x="-200%" y="-200%" width="500%" height="500%"><feGaussianBlur stdDeviation="1.6"/></filter>
<filter id="{p}-soft" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="0.6"/></filter>''')
    # lighting gradients (screen space)
    o.append(f'''<linearGradient id="{p}-moon" gradientUnits="userSpaceOnUse" x1="572" y1="490" x2="506" y2="560">
  <stop offset="0" stop-color="#cfe0ff" stop-opacity="0.22"/><stop offset="0.45" stop-color="#cfe0ff" stop-opacity="0.04"/>
  <stop offset="1" stop-color="#0d0905" stop-opacity="0.38"/></linearGradient>
<linearGradient id="{p}-foot" gradientUnits="userSpaceOnUse" x1="0" y1="540" x2="0" y2="566">
  <stop offset="0" stop-color="#1a1008" stop-opacity="0"/><stop offset="1" stop-color="#1a1008" stop-opacity="0.55"/></linearGradient>
<radialGradient id="{p}-peep" cx="0.5" cy="0.5" r="0.5"><stop offset="0" stop-color="#fff6c8"/><stop offset="0.5" stop-color="#ffd36a"/><stop offset="1" stop-color="#d9822e"/></radialGradient>
<radialGradient id="{p}-peephalo" cx="0.5" cy="0.5" r="0.5"><stop offset="0" stop-color="#ffd27a" stop-opacity="0.55"/><stop offset="1" stop-color="#ffd27a" stop-opacity="0"/></radialGradient>
<linearGradient id="{p}-ring" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#f0d596"/><stop offset="0.45" stop-color="#a77d3c"/><stop offset="1" stop-color="#4d3518"/></linearGradient>''')
    if th:
        # turn-away shading: darker toward the free edge, warm rim at the far edge
        x_near = P(0, 520, th)[0]
        x_far = P(W, 520, th)[0]
        o.append(f'''<linearGradient id="{p}-turn" gradientUnits="userSpaceOnUse" x1="{f(x_near)}" y1="0" x2="{f(x_far)}" y2="0">
  <stop offset="0" stop-color="#140904" stop-opacity="{f(dark*0.85)}"/><stop offset="1" stop-color="#0a0503" stop-opacity="{f(min(0.94, dark*1.3))}"/></linearGradient>
<linearGradient id="{p}-edge" gradientUnits="userSpaceOnUse" x1="0" y1="490" x2="0" y2="566">
  <stop offset="0" stop-color="#ffd58a"/><stop offset="0.6" stop-color="#d7954a"/><stop offset="1" stop-color="#6b3f1c"/></linearGradient>''')
    outline = leaf_outline(th)
    o.append(f'<clipPath id="{p}-clip"><path d="{path(outline)}"/></clipPath>')
    o.append(f'<clipPath id="{p}-open"><path d="M504,566 L504,524 A34,34 0 0 1 572,524 L572,564 Z"/></clipPath>')
    o.append('</defs>')

    o.append(f'<g id="{p}-door" clip-path="url(#{p}-open)">')
    if th:
        # leaf thickness: inner face offset into the house, shows as a band along the top/free edge
        inner = leaf_outline(th, depth=THICK)
        o.append(f'<path id="{p}-thick" d="{path(inner)}" fill="#3a2513"/>')
        # warm rim of the thickness lit from the room
        rim = [P(u, top(u), th, THICK) for u in [W * i / 30 for i in range(31)]]
        o.append(f'<path d="{path(rim, False)}" fill="none" stroke="url(#{p}-edge)" stroke-width="{f(1.3*scale_at(W,th))}" opacity="0.85"/>')
        # the free edge face (fudged visible a little, lit warm from inside)
        fe = [P(W, top(W), th), P(W, bottom(W), th), P(W, bottom(W), th, THICK), P(W, top(W), th, THICK)]
        ex = [(x + 2.4 * scale_at(W, th) * (1 - th / 110), y) for x, y in fe[2:]]
        o.append(f'<path d="{path(fe[:2] + ex)}" fill="url(#{p}-edge)" opacity="0.9"/>')

    if th:
        sh = [P(u, bottom(u) + 0.6, th) for u in [W * i / 12 for i in range(13)]]
        sh2 = [(x + 2.5 * (1 - th / 90), y + 2.2) for x, y in reversed(sh)]
        o.append(f'<path d="{path(sh + sh2)}" fill="#0a0503" opacity="0.6" filter="url(#{p}-soft)"/>')
    o.append(f'<g clip-path="url(#{p}-clip)">')
    o.append(f'<g filter="url(#{p}-grain)">')
    # planks
    edges = [0.0] + SEAMS + [W]
    for i in range(len(edges) - 1):
        u0, u1 = edges[i], edges[i + 1]
        pts = strip(u0, u1, lambda u: top(u) - 3, bottom, th, 8)
        o.append(f'<path d="{path(pts)}" fill="{PLANK_TONES[i]}"/>')
    o.append('</g>')
    # plank tonal variation (light streaks, knots)
    for i in range(len(edges) - 1):
        u0, u1 = edges[i], edges[i + 1]
        um = u0 + (u1 - u0) * random.uniform(0.3, 0.6)
        a = [P(um, top(um) + 2, th), P(um + 2.2, top(um) + 2, th), P(um + 1.6, bottom(um), th), P(um - 0.6, bottom(um), th)]
        o.append(f'<path d="{path(a)}" fill="#e8d6b6" opacity="0.10"/>')
    for (u, y, r) in [(15, 528, 1.6), (44, 503, 1.3), (27, 553, 1.4), (63, 526, 1.1)]:
        x0, y0 = P(u, y, th)
        s = scale_at(u, th) * (math.cos(math.radians(th)) if th else 1)
        o.append(f'<ellipse cx="{f(x0)}" cy="{f(y0)}" rx="{f(r*s+0.05)}" ry="{f(r*1.8*scale_at(u,th))}" fill="none" stroke="#3b2715" stroke-width="0.6" opacity="0.7"/>')
        o.append(f'<ellipse cx="{f(x0)}" cy="{f(y0)}" rx="{f(r*0.4*s+0.05)}" ry="{f(r*0.8*scale_at(u,th))}" fill="#3b2715" opacity="0.75"/>')
    # seams
    for u in SEAMS:
        a, b = P(u, top(u), th), P(u, bottom(u), th)
        a2, b2 = P(u + 0.9, top(u), th), P(u + 0.9, bottom(u), th)
        o.append(f'<path d="M{f(a[0])},{f(a[1])} L{f(b[0])},{f(b[1])}" stroke="#1a0f07" stroke-width="{f(1.7*scale_at(u,th))}" filter="url(#{p}-rough)"/>')
        a3, b3 = P(u - 1.6, top(u), th), P(u - 1.6, bottom(u), th)
        o.append(f'<path d="M{f(a3[0])},{f(a3[1])} L{f(b3[0])},{f(b3[1])}" stroke="#2a1a0c" stroke-width="{f(1.6*scale_at(u,th))}" opacity="0.25"/>')
        o.append(f'<path d="M{f(a2[0])},{f(a2[1])} L{f(b2[0])},{f(b2[1])}" stroke="#d9c4a0" stroke-width="0.45" opacity="0.35"/>')
    # wear: scuffs near handle and a few scratches
    sx, sy = P(55, 538, th)
    o.append(f'<ellipse cx="{f(sx)}" cy="{f(sy)}" rx="{f(7*scale_at(55,th)*max(.2,math.cos(math.radians(th))))}" ry="{f(9*scale_at(55,th))}" fill="#3a2614" opacity="0.28" filter="url(#{p}-soft)"/>')
    for (u, y, du, dy) in [(10, 522, 4, 3), (30, 530, 5, -2), (40, 556, 6, 1), (59, 500, -3, 4)]:
        a, b = P(u, y, th), P(u + du, y + dy, th)
        o.append(f'<path d="M{f(a[0])},{f(a[1])} L{f(b[0])},{f(b[1])}" stroke="#f1e2c4" stroke-width="0.35" opacity="0.4"/>')
    # nail holes
    for (u, y) in [(3, 500), (13, 526), (40, 527), (66, 529), (27, 559), (54, 559)]:
        x0, y0 = P(u, y, th)
        o.append(f'<circle cx="{f(x0)}" cy="{f(y0)}" r="{f(0.45*scale_at(u,th))}" fill="#1b110a" opacity="0.8"/>')

    # iron straps with rivets
    for base in (510.0, 540.0):
        yf = strap_y(base)
        pts = strip(-1, W + 1, lambda u: yf(u) - 2.6, lambda u: yf(u) + 2.6, th, 16)
        o.append(f'<path d="{path(pts)}" fill="#55392a" filter="url(#{p}-rust)"/>')
        hl = [P(u, yf(u) - 2.0, th) for u in [W * i / 16 for i in range(17)]]
        o.append(f'<path d="{path(hl, False)}" fill="none" stroke="#c49a74" stroke-width="{f(0.5*scale_at(30,th))}" opacity="0.45"/>')
        sh = [P(u, yf(u) + 3.3, th) for u in [W * i / 16 for i in range(17)]]
        o.append(f'<path d="{path(sh, False)}" fill="none" stroke="#1d1209" stroke-width="{f(1.2*scale_at(30,th))}" opacity="0.5"/>')
        # rust drips
        for u in (12, 31, 50, 63):
            a, b = P(u, yf(u) + 2.6, th), P(u + 0.3, yf(u) + 2.6 + random.uniform(3, 8), th)
            o.append(f'<path d="M{f(a[0])},{f(a[1])} L{f(b[0])},{f(b[1])}" stroke="#8c4519" stroke-width="{f(0.8*scale_at(u,th))}" stroke-linecap="round" opacity="0.45"/>')
        for k in range(6):
            u = 5.5 + k * 11.4
            x0, y0 = P(u, yf(u), th)
            s = scale_at(u, th)
            cs = math.cos(math.radians(th)) if th else 1.0
            o.append(f'<ellipse cx="{f(x0)}" cy="{f(y0)}" rx="{f(1.75*s*max(cs,.35))}" ry="{f(1.75*s)}" fill="#24180f"/>')
            o.append(f'<ellipse cx="{f(x0-0.5*s*cs)}" cy="{f(y0-0.55*s)}" rx="{f(0.65*s*max(cs,.35))}" ry="{f(0.6*s)}" fill="#d8c3a2" opacity="0.85"/>')
        # hinge knuckle on the left
        x0, y0 = P(0, base, th)
        o.append(f'<rect x="{f(x0-1.2)}" y="{f(y0-4.2)}" width="2.6" height="8.4" rx="1" fill="#2d1f16"/>')
        o.append(f'<rect x="{f(x0-0.8)}" y="{f(y0-3.8)}" width="0.7" height="7.6" fill="#a58a6c" opacity="0.6"/>')

    # peephole (glows from the warm room)
    px, py = P(34, 501, th)
    s = scale_at(34, th)
    cs = max(0.25, math.cos(math.radians(th))) if th else 1.0
    if th == 0:
        o.append(f'<circle cx="{f(px)}" cy="{f(py)}" r="7" fill="url(#{p}-peephalo)"/>')
    o.append(f'<ellipse cx="{f(px)}" cy="{f(py)}" rx="{f(4.1*s*cs)}" ry="{f(4.1*s)}" fill="#24180e"/>')
    o.append(f'<ellipse cx="{f(px)}" cy="{f(py)}" rx="{f(3.4*s*cs)}" ry="{f(3.4*s)}" fill="none" stroke="#b08b4e" stroke-width="{f(0.9*s)}"/>')
    if th == 0:
        o.append(f'<circle cx="{f(px)}" cy="{f(py)}" r="2.5" fill="url(#{p}-peep)"/>')
        o.append(f'<circle cx="{f(px)}" cy="{f(py)}" r="2.6" fill="#ffd36a" opacity="0.5" filter="url(#{p}-glow)"/>')
        o.append(f'<circle cx="{f(px-0.8)}" cy="{f(py-0.8)}" r="0.6" fill="#fffbe6"/>')
    else:
        o.append(f'<ellipse cx="{f(px)}" cy="{f(py)}" rx="{f(2.5*s*cs)}" ry="{f(2.5*s)}" fill="#1a0f07"/>')

    # ring handle + staple + keyhole
    hx, hy = P(55, 527.5, th)
    s = scale_at(55, th)
    cs = max(0.2, math.cos(math.radians(th))) if th else 1.0
    o.append(f'<ellipse cx="{f(hx)}" cy="{f(hy)}" rx="{f(2.4*s*cs)}" ry="{f(2.0*s)}" fill="#2a1c12"/>')
    o.append(f'<ellipse cx="{f(hx-0.5*cs)}" cy="{f(hy-0.5)}" rx="{f(0.9*s*cs)}" ry="{f(0.7*s)}" fill="#b89a6a" opacity="0.7"/>')
    rx_, ry_ = P(55, 534.5, th)
    o.append(f'<ellipse cx="{f(rx_+0.5)}" cy="{f(ry_+0.9)}" rx="{f(6*s*cs)}" ry="{f(6*s)}" fill="none" stroke="#1a1008" stroke-width="{f(2.2*s)}" opacity="0.5"/>')
    o.append(f'<ellipse cx="{f(rx_)}" cy="{f(ry_)}" rx="{f(6*s*cs)}" ry="{f(6*s)}" fill="none" stroke="url(#{p}-ring)" stroke-width="{f(2.1*s)}"/>')
    o.append(f'<ellipse cx="{f(rx_)}" cy="{f(ry_)}" rx="{f(6*s*cs)}" ry="{f(6*s)}" fill="none" stroke="#fff0c4" stroke-width="{f(0.6*s)}" stroke-dasharray="{f(4*s)} {f(30*s)}" stroke-dashoffset="{f(-2*s)}" opacity="0.85"/>')
    kx, ky = P(55, 549.5, th)
    o.append(f'<ellipse cx="{f(kx)}" cy="{f(ky+0.3)}" rx="{f(2.6*s*cs)}" ry="{f(3.6*s)}" fill="#6e5236" stroke="#2a1c12" stroke-width="0.5"/>')
    if th == 0:
        o.append(f'<path d="M{f(kx)},{f(ky-1.6)} a1.05,1.05 0 1 1 0.01,0 M{f(kx-0.55)},{f(ky-0.8)} L{f(kx-0.9)},{f(ky+1.9)} L{f(kx+0.9)},{f(ky+1.9)} L{f(kx+0.55)},{f(ky-0.8)} Z" fill="#ffcf73"/>')
        o.append(f'<circle cx="{f(kx)}" cy="{f(ky)}" r="1.6" fill="#ffcf73" opacity="0.45" filter="url(#{p}-glow)"/>')
    else:
        o.append(f'<ellipse cx="{f(kx)}" cy="{f(ky)}" rx="{f(0.7*s*cs)}" ry="{f(1.6*s)}" fill="#1a1008"/>')

    # bottom wear, damp darkening and moss
    o.append(f'<rect x="490" y="486" width="90" height="82" fill="url(#{p}-foot)"/>')
    mpts = []
    random.seed(5)
    for i in range(23):
        u = W * i / 22
        hgt = 1.2 + 3.5 * math.exp(-((u - 4) / 6) ** 2) + 2.5 * math.exp(-((u - 60) / 5) ** 2) + 1.8 * math.exp(-((u - 26) / 4) ** 2)
        mpts.append(P(u, bottom(u) - hgt - random.uniform(0, 1.6), th))
    mpts += [P(W + 1, bottom(W) + 2, th), P(-1, bottom(0) + 2, th)]
    o.append(f'<path d="{path(mpts)}" fill="#3e5a22" filter="url(#{p}-moss)" opacity="{f(1-dark*0.4)}"/>')
    for (u, y, rx, ry) in [(2.5, 556, 2.6, 5), (1.5, 547, 1.6, 3), (64, 558, 2.4, 3.6)]:
        x0, y0 = P(u, y, th)
        o.append(f'<ellipse cx="{f(x0)}" cy="{f(y0)}" rx="{f(rx*scale_at(u,th)*(math.cos(math.radians(th)) if th else 1)+0.3)}" ry="{f(ry*scale_at(u,th))}" fill="#41602a" filter="url(#{p}-moss)" opacity="{f(1-dark*0.4)}"/>')
    random.seed(8)
    for i in range(14):
        u = random.choice([random.uniform(1, 9), random.uniform(55, 66), random.uniform(20, 32)])
        x0, y0 = P(u, bottom(u) - random.uniform(1, 4.5), th)
        o.append(f'<circle cx="{f(x0)}" cy="{f(y0)}" r="{f(random.uniform(0.5,1.1)*scale_at(u,th))}" fill="#9cc25a" opacity="0.7"/>')
    # lighting: moon from upper right on the closed door; turning shade on the open ones
    if th == 0:
        o.append(f'<rect x="490" y="486" width="90" height="82" fill="url(#{p}-moon)"/>')
        # recess shadow cast by the frame (upper left inside the arch)
        o.append(f'<path d="M505,566 L505,524 A33,33 0 0 1 571,524" fill="none" stroke="#0b0603" stroke-width="5" opacity="0.55" filter="url(#{p}-soft)"/>')
    else:
        o.append(f'<rect x="490" y="486" width="90" height="82" fill="url(#{p}-turn)"/>')
        # warm interior light grazing the back of the free edge
        a = [P(W - 3.5, top(W - 3.5) + 1, th), P(W, top(W), th), P(W, bottom(W), th), P(W - 3.5, bottom(W - 3.5), th)]
        o.append(f'<path d="{path(a)}" fill="#ffb862" opacity="{f(0.28 if th < 60 else 0.18)}" filter="url(#{p}-soft)"/>')
        # top of leaf in shadow of the lintel
        o.append(f'<path d="{path(leaf_outline(th), True)}" fill="none" stroke="#060302" stroke-width="2.4" opacity="0.6" filter="url(#{p}-soft)"/>')
    o.append('</g>')  # clip leaf
    if th:
        # crisp silhouette edge
        o.append(f'<path d="{path(outline)}" fill="none" stroke="#120a05" stroke-width="0.6" opacity="0.8"/>')
    o.append('</g></svg>')
    return '\n'.join(o)


def doorway_svg():
    p = 'doorway'
    random.seed(3)
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 1000" width="1600" height="1000">', '<defs>']
    o.append(f'''<clipPath id="{p}-arch"><path d="M504,566 L504,524 A34,34 0 0 1 572,524 L572,564 Z"/></clipPath>
<filter id="{p}-wood" x="0" y="0" width="1" height="1" color-interpolation-filters="sRGB">
  <feTurbulence type="fractalNoise" baseFrequency="1.6 0.05" numOctaves="3" seed="2" result="n"/>
  <feColorMatrix in="n" type="matrix" values="0 0 0 0 0.12  0 0 0 0 0.06  0 0 0 0 0.02  2.4 0 0 0 -1.0" result="g"/>
  <feComposite in="g" in2="SourceGraphic" operator="in" result="gi"/>
  <feMerge><feMergeNode in="SourceGraphic"/><feMergeNode in="gi"/></feMerge>
</filter>
<filter id="{p}-floor" x="0" y="0" width="1" height="1" color-interpolation-filters="sRGB">
  <feTurbulence type="fractalNoise" baseFrequency="0.06 1.5" numOctaves="3" seed="6" result="n"/>
  <feColorMatrix in="n" type="matrix" values="0 0 0 0 0.10  0 0 0 0 0.05  0 0 0 0 0.02  2.2 0 0 0 -0.95" result="g"/>
  <feComposite in="g" in2="SourceGraphic" operator="in" result="gi"/>
  <feMerge><feMergeNode in="SourceGraphic"/><feMergeNode in="gi"/></feMerge>
</filter>
<filter id="{p}-rug" x="-5%" y="-30%" width="110%" height="160%" color-interpolation-filters="sRGB">
  <feTurbulence type="fractalNoise" baseFrequency="1.8 0.9" numOctaves="2" seed="12" result="n"/>
  <feDisplacementMap in="SourceGraphic" in2="n" scale="0.8" xChannelSelector="R" yChannelSelector="G" result="d"/>
  <feColorMatrix in="n" type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  1.6 0 0 0 -0.7" result="g"/>
  <feComposite in="g" in2="d" operator="in" result="gi"/>
  <feMerge><feMergeNode in="d"/><feMergeNode in="gi"/></feMerge>
</filter>
<filter id="{p}-blur" x="-100%" y="-100%" width="300%" height="300%"><feGaussianBlur stdDeviation="2.2"/></filter>
<filter id="{p}-blur1" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="0.7"/></filter>
<filter id="{p}-blur4" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="4"/></filter>
<radialGradient id="{p}-lamp" gradientUnits="userSpaceOnUse" cx="556" cy="512" r="38">
  <stop offset="0" stop-color="#ffe7a6" stop-opacity="0.95"/><stop offset="0.25" stop-color="#ffbe5c" stop-opacity="0.55"/>
  <stop offset="0.6" stop-color="#d9772e" stop-opacity="0.18"/><stop offset="1" stop-color="#d9772e" stop-opacity="0"/></radialGradient>
<radialGradient id="{p}-candle" gradientUnits="userSpaceOnUse" cx="563" cy="538" r="12">
  <stop offset="0" stop-color="#ffe9a8" stop-opacity="0.9"/><stop offset="0.4" stop-color="#ffb554" stop-opacity="0.35"/><stop offset="1" stop-color="#ffb554" stop-opacity="0"/></radialGradient>
<linearGradient id="{p}-wallg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#3a200e"/><stop offset="0.5" stop-color="#8a5a2e"/><stop offset="1" stop-color="#5e3819"/></linearGradient>
<linearGradient id="{p}-floorg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#4a2b14"/><stop offset="1" stop-color="#7a4d26"/></linearGradient>
<radialGradient id="{p}-edge" gradientUnits="userSpaceOnUse" cx="546" cy="534" r="44">
  <stop offset="0.35" stop-color="#050201" stop-opacity="0"/><stop offset="0.8" stop-color="#050201" stop-opacity="0.55"/><stop offset="1" stop-color="#050201" stop-opacity="0.9"/></radialGradient>
<linearGradient id="{p}-top" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#050201" stop-opacity="0.8"/><stop offset="0.28" stop-color="#050201" stop-opacity="0.12"/><stop offset="0.5" stop-color="#050201" stop-opacity="0"/></linearGradient>
<linearGradient id="{p}-leafsh" gradientUnits="userSpaceOnUse" x1="504" y1="0" x2="540" y2="0"><stop offset="0" stop-color="#050201" stop-opacity="0.9"/><stop offset="0.45" stop-color="#050201" stop-opacity="0.45"/><stop offset="1" stop-color="#050201" stop-opacity="0"/></linearGradient>
<linearGradient id="{p}-spill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffc56e" stop-opacity="0.55"/><stop offset="1" stop-color="#ffc56e" stop-opacity="0"/></linearGradient>''')
    o.append('</defs>')
    o.append(f'<g id="{p}-room" clip-path="url(#{p}-arch)">')
    # back wall: vertical planks of the stump's inner wall
    o.append(f'<g filter="url(#{p}-wood)"><rect x="500" y="486" width="76" height="62" fill="url(#{p}-wallg)"/>')
    x = 500.0
    tones = ['#8a5730', '#704423', '#94603a', '#673d1d', '#86552f']
    i = 0
    while x < 576:
        w = random.uniform(5.5, 8.5)
        o.append(f'<rect x="{f(x)}" y="486" width="{f(w)}" height="62" fill="{tones[i%5]}" opacity="0.55"/>')
        o.append(f'<path d="M{f(x)},486 L{f(x+random.uniform(-.3,.3))},548" stroke="#1d0f06" stroke-width="0.7" opacity="0.8"/>')
        x += w; i += 1
    o.append('</g>')
    # floor with boards converging to the vanishing point
    o.append(f'<g filter="url(#{p}-floor)"><path d="M496,547.5 L580,547.5 L580,570 L496,570 Z" fill="url(#{p}-floorg)"/>')
    for k in range(-6, 8):
        xb = 540 + k * 9.5
        o.append(f'<path d="M{f(540+k*3.2)},547.5 L{f(xb)},570" stroke="#2a1608" stroke-width="0.6" opacity="0.7"/>')
    o.append('</g>')
    o.append(f'<path d="M496,547.6 L580,547.6" stroke="#1a0c04" stroke-width="1.4" opacity="0.8"/>')
    # baseboard moss + little glowing mushrooms (like the interior)
    for k in range(9):
        xm = 506 + k * 8 + random.uniform(-2, 2)
        if k % 3 == 1: continue
        o.append(f'<path d="M{f(xm-2.5)},547.8 q0.6,-1.8 1.6,-1.2 q0.8,-1.4 1.8,-0.4 q1,-0.9 1.6,1.6 Z" fill="#3f5a22" opacity="0.85"/>')
    for (xm, c) in [(512, '#9cff9a'), (531, '#b6ff8a'), (570, '#9cff9a')]:
        o.append(f'<circle cx="{xm}" cy="546.3" r="0.9" fill="{c}"/><circle cx="{xm}" cy="546.3" r="2.4" fill="{c}" opacity="0.35" filter="url(#{p}-blur1)"/>')
    # shelf with jars and books on the back wall (left)
    o.append(f'<rect x="507" y="516" width="27" height="1.8" fill="#3a2210"/><rect x="507" y="517.8" width="27" height="1" fill="#120802" opacity="0.6"/>')
    bx = 509
    for (w, h, c) in [(2, 6, '#7a2d22'), (1.6, 7, '#2f4f5e'), (2.2, 5.5, '#8a6a2a'), (1.4, 6.5, '#4c5a2a')]:
        o.append(f'<rect x="{bx}" y="{516-h}" width="{w}" height="{h}" fill="{c}"/><rect x="{bx}" y="{516-h}" width="0.4" height="{h}" fill="#ffd8a0" opacity="0.4"/>')
        bx += w + 0.3
    for (cx, h, c) in [(521, 5, '#5c7a4a'), (524.5, 6.5, '#7a4a3a'), (528, 4, '#a0884a'), (531, 5.5, '#3e6070')]:
        o.append(f'<rect x="{cx-1.2}" y="{516-h}" width="2.4" height="{h}" rx="0.8" fill="{c}" opacity="0.9"/><rect x="{cx-0.5}" y="{516-h-1}" width="1" height="1.2" fill="#3a2210"/><rect x="{cx+0.4}" y="{516-h+0.8}" width="0.4" height="{h-1.5}" fill="#ffe2a8" opacity="0.6"/>')
    # hanging herbs from the ceiling
    for (hx, ln) in [(514, 9), (520, 7), (562, 6)]:
        o.append(f'<path d="M{hx},486 L{hx},{486+ln}" stroke="#2a1a0c" stroke-width="0.4"/>')
        o.append(f'<path d="M{hx-2},{486+ln} q2,6 4,0 q-2,-2 -4,0 Z" fill="#5a6b2c"/><path d="M{hx-1},{487+ln} l-1,4 M{hx+1},{487+ln} l1,4" stroke="#7e8f3a" stroke-width="0.5"/>')
    # small picture frame and clock on the wall
    o.append(f'<rect x="537" y="523" width="8" height="6.5" fill="#d9c18c" stroke="#4a2c12" stroke-width="1"/><path d="M538,528.5 q3,-4 6,0" fill="#6a8c5a" opacity="0.7"/>')
    # hanging lantern (main warm light)
    # rug in the foreground: concentric striped ellipse
    rings = ['#6b2a2a', '#c08a3a', '#2f5a5a', '#8a3a2a', '#d7b46a', '#4a3a6a', '#9a4a2a', '#e0c07a']
    o.append(f'<g filter="url(#{p}-rug)">')
    for k, c in enumerate(rings):
        rx = 34 - k * 3.6
        ry = 8.5 - k * 0.9
        o.append(f'<ellipse cx="540" cy="561" rx="{f(rx)}" ry="{f(ry)}" fill="{c}"/>')
    o.append('</g>')
    o.append(f'<ellipse cx="540" cy="561" rx="34" ry="8.5" fill="none" stroke="#2a140a" stroke-width="0.6" opacity="0.6"/>')
    # patchwork bed corner on the left
    o.append(f'<path d="M500,536 L519,536 L520,553 L500,553 Z" fill="#3a2210"/>')
    pc = ['#a8432f', '#d0a04a', '#3f6a6a', '#8a5a9a', '#c86a3a', '#5a7a3a']
    for r_ in range(3):
        for c_ in range(3):
            o.append(f'<rect x="{500+c_*6.4}" y="{535+r_*4.2}" width="6.4" height="4.2" fill="{pc[(r_*3+c_)%6]}" opacity="0.85"/>')
    o.append(f'<path d="M500,535 L519.5,535 L520,548 L500,548" fill="none" stroke="#1a0d05" stroke-width="0.5" stroke-dasharray="1 1" opacity="0.6"/>')
    o.append(f'<ellipse cx="508" cy="533" rx="8" ry="3" fill="#e8dcc0"/><ellipse cx="507" cy="532.4" rx="6" ry="1.6" fill="#fffaf0" opacity="0.6"/>')
    # round table with candle on the right
    o.append(f'<path d="M561.5,542 L560,556 L566,556 L564.5,542 Z" fill="#2f1a0b"/>')
    o.append(f'<ellipse cx="563" cy="556" rx="5" ry="1.2" fill="#1d0f05"/>')
    o.append(f'<ellipse cx="563" cy="542" rx="11" ry="2.6" fill="#5a3518"/><ellipse cx="563" cy="541.4" rx="10.4" ry="2.1" fill="#8a5a2c"/>')
    o.append(f'<rect x="562.2" y="534.5" width="1.6" height="6.5" fill="#f3e6c4"/><path d="M563,531.4 q1.2,1.6 0,3.1 q-1.2,-1.5 0,-3.1 Z" fill="#fff0a8"/>')
    o.append(f'<rect x="556" y="539" width="3" height="2.4" rx="0.5" fill="#d9d2c0"/><rect x="567" y="539.4" width="4" height="2" fill="#6a3a1a"/>')
    # table shadow on the floor
    o.append(f'<ellipse cx="557" cy="557" rx="9" ry="1.6" fill="#120802" opacity="0.5" filter="url(#{p}-blur1)"/>')
    # depth & shading: top dark, edges dark, shadow of the open leaf on the left
    o.append(f'<rect x="496" y="486" width="84" height="82" fill="url(#{p}-top)"/>')
    o.append(f'<path d="M504,566 L504,488 L536,488 L524,548 L540,570 Z" fill="url(#{p}-leafsh)" filter="url(#{p}-blur1)"/>')
    o.append(f'<rect x="496" y="486" width="84" height="82" fill="url(#{p}-edge)"/>')
    # warm pool of lamplight on the floor and rug
    o.append(f'<ellipse cx="546" cy="556" rx="22" ry="6" fill="#ffc06a" opacity="0.22" filter="url(#{p}-blur)"/>')
    # depth of the stump wall: soft shadow just inside the right side of the opening
    o.append(f'<path d="M570,564 L570,524 A32,32 0 0 0 548,494" fill="none" stroke="#0a0402" stroke-width="4" opacity="0.6" filter="url(#{p}-blur1)"/>')
    o.append(f'<rect x="496" y="486" width="84" height="80" fill="url(#{p}-lamp)"/>')
    o.append(f'<path d="M558,486 L558,503" stroke="#1a0e05" stroke-width="0.6"/>')
    o.append(f'<path d="M553.5,505 L562.5,505 L561.5,503 L554.5,503 Z" fill="#2a1a0c"/>')
    o.append(f'<path d="M554,505 L562,505 L561.3,513 L554.7,513 Z" fill="#ffd67c"/><path d="M556.5,506 L559.5,506 L559.3,512 L556.7,512 Z" fill="#fff4cf"/>')
    o.append(f'<path d="M558,505 L558,513 M554.4,509 L561.6,509" stroke="#3a2412" stroke-width="0.6"/>')
    o.append(f'<path d="M553.5,513 L562.5,513 L562,514.6 L554,514.6 Z" fill="#2a1a0c"/>')
    o.append(f'<circle cx="558" cy="509" r="6" fill="#ffcf73" opacity="0.6" filter="url(#{p}-blur)"/>')
    o.append(f'<rect x="530" y="526" width="60" height="40" fill="url(#{p}-candle)"/>')
    o.append(f'<path d="M563,531.4 q1.2,1.6 0,3.1 q-1.2,-1.5 0,-3.1 Z" fill="#fff6c8"/><circle cx="563" cy="532.8" r="2.6" fill="#ffd67c" opacity="0.55" filter="url(#{p}-blur1)"/>')
    o.append(f'<path d="M568,560 L568,524 A30,30 0 0 0 563,509" fill="none" stroke="#ffb862" stroke-width="0.6" opacity="0.5"/>')
    # warm threshold plank
    o.append(f'<path d="M504,566.2 L572,564.2 L572,561.4 L504,562.8 Z" fill="#7a4a22"/>')
    o.append(f'<path d="M520,562.4 L572,561.4" stroke="#ffcf7a" stroke-width="0.7" opacity="0.6"/>')
    o.append('</g>')
    # rim of the opening and light spilling out onto the ground
    o.append(f'<path d="M504,566 L504,524 A34,34 0 0 1 572,524 L572,564" fill="none" stroke="#0a0503" stroke-width="1.6" opacity="0.8"/>')
    o.append(f'<path d="M508,565.8 L570,564 L590,580 L516,584 Z" fill="url(#{p}-spill)" filter="url(#{p}-blur)" opacity="0.7"/>')
    o.append('</svg>')
    return '\n'.join(o)


if __name__ == '__main__':
    for name, th in [('leaf_0', 0), ('leaf_1', 40), ('leaf_2', 80)]:
        open(os.path.join(OUT, name + '.svg'), 'w').write(leaf_svg(name.replace('_', ''), th))
    open(os.path.join(OUT, 'doorway.svg'), 'w').write(doorway_svg())
    print('written')
