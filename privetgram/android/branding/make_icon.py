#!/usr/bin/env python3
"""Privetgram launcher icon: the paper plane, black & white, with a glitch on top.

Usage: make_icon.py <android res dir>   (writes mipmap-*/ic_launcher*.png, icon_foreground*.png)
       make_icon.py --preview out.png
Needs Pillow. Deterministic (fixed seed), so rebuilds give the same icon.
"""
import random, re, sys, os
from PIL import Image, ImageDraw, ImageChops, ImageFilter

# Plane outline from TMessagesProj/src/main/res/drawable/icon_plane.xml (viewport 90x90).
PLANE = ("M30.3652 44.5699C38.1874 41.1615 43.4013 38.9115 46.0124 37.8254C53.4624 34.7226 55.0096 34.1838 56.0179 34.1671"
 "C56.2402 34.1643 56.7374 34.2171 57.0596 34.4782C57.329 34.7004 57.404 34.9976 57.4402 35.206C57.4763 35.4143 57.5207 35.8921 57.4846 36.2643"
 "C57.0818 40.5088 55.3346 50.8143 54.4457 55.5699C54.0707 57.581 53.329 58.256 52.6124 58.3227C51.054 58.4643 49.8707 57.2921 48.3624 56.3004"
 "C46.0013 54.7532 44.6679 53.7865 42.3763 52.2754C39.7263 50.5282 41.4429 49.5699 42.954 48.0004C43.3485 47.5893 50.2124 41.3393 50.3457 40.7726"
 "C50.3624 40.7004 50.3763 40.4365 50.2207 40.2977C50.0624 40.1588 49.8318 40.206 49.6652 40.2449C49.429 40.2977 45.6568 42.7921 38.3485 47.731"
 "C37.279 48.4671 36.3068 48.8254 35.4402 48.806C34.4818 48.7865 32.6374 48.2643 31.2679 47.8171C29.5874 47.2726 28.5013 46.9893 28.6179 46.0615"
 "C28.679 45.5782 29.2624 45.081 30.3652 44.5699Z")

def plane_polygon():
    toks = re.findall(r'[MCZ]|-?\d*\.?\d+', PLANE)
    pts, cur, i, cmd = [], (0, 0), 0, None
    while i < len(toks):
        t = toks[i]
        if t in 'MCZ':
            cmd = t; i += 1
            if t == 'Z': continue
        if cmd == 'M':
            cur = (float(toks[i]), float(toks[i+1])); pts.append(cur); i += 2
        elif cmd == 'C':
            p1 = (float(toks[i]), float(toks[i+1])); p2 = (float(toks[i+2]), float(toks[i+3])); p3 = (float(toks[i+4]), float(toks[i+5]))
            for k in range(1, 17):
                s = k / 16; u = 1 - s
                pts.append(tuple(u**3*a + 3*u*u*s*b + 3*u*s*s*c + s**3*d for a, b, c, d in zip(cur, p1, p2, p3)))
            cur = p3; i += 6
    return pts

def plane_mask(size, scale):
    """White plane on transparent, centred, plane width = scale * size."""
    pts = plane_polygon()
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    w, h = max(xs) - min(xs), max(ys) - min(ys)
    k = scale * size / w
    cx, cy = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
    ss = 4
    m = Image.new('L', (size * ss, size * ss), 0)
    ImageDraw.Draw(m).polygon([((x - cx) * k * ss + size * ss / 2 - size * ss * 0.02,
                                (y - cy) * k * ss + size * ss / 2) for x, y in pts], fill=255)
    return m.resize((size, size), Image.LANCZOS)

def glitch_layer(size, scale, seed=7):
    """RGBA: glitched B/W plane on transparent background."""
    rnd = random.Random(seed)
    mask = plane_mask(size, scale)
    off = round(size * 0.035)
    ghost = ImageChops.offset(mask, -off, 0).point(lambda v: v * 0.55)   # grey echo to the left
    ghost2 = ImageChops.offset(mask, off // 2, 0).point(lambda v: v * 0.25)
    white = Image.new('L', (size, size), 255)
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    img.paste((150, 150, 150, 255), (0, 0), ghost)
    img.paste((90, 90, 90, 255), (0, 0), ghost2)
    img.paste((255, 255, 255, 255), (0, 0), mask)
    # displaced horizontal bands
    for _ in range(7):
        y0 = rnd.randint(int(size * 0.28), int(size * 0.70))
        hgt = max(1, round(size * rnd.uniform(0.008, 0.05)))
        dx = round(size * rnd.choice([-1, 1]) * rnd.uniform(0.02, 0.09))
        band = img.crop((0, y0, size, y0 + hgt))
        img.paste((0, 0, 0, 0), (0, y0, size, y0 + hgt))
        img.paste(band, (dx, y0), band)
    # noise blocks
    d = ImageDraw.Draw(img)
    for _ in range(9):
        x0 = rnd.randint(int(size * 0.18), int(size * 0.78)); y0 = rnd.randint(int(size * 0.25), int(size * 0.75))
        bw = round(size * rnd.uniform(0.02, 0.10)); bh = max(1, round(size * rnd.uniform(0.004, 0.015)))
        g = rnd.choice([255, 200, 120])
        d.rectangle((x0, y0, x0 + bw, y0 + bh), fill=(g, g, g, 255))
    # scanlines
    step = max(2, size // 64)
    a = img.split()[3]
    lines = Image.new('L', (size, size), 255)
    ld = ImageDraw.Draw(lines)
    for y in range(0, size, step):
        ld.line((0, y, size, y), fill=150)
    img.putalpha(ImageChops.multiply(a, lines))
    return img

def legacy_icon(size):
    """Round black icon with the glitched plane (pre-Android 8 launchers)."""
    big = size * 4
    bg = Image.new('RGBA', (big, big), (0, 0, 0, 0))
    ImageDraw.Draw(bg).ellipse((big * 0.04, big * 0.04, big * 0.96, big * 0.96), fill=(12, 12, 12, 255))
    bg = bg.resize((size, size), Image.LANCZOS)
    g = glitch_layer(size, 0.62)
    circle = Image.new('L', (size, size), 0)
    ImageDraw.Draw(circle).ellipse((size * 0.04, size * 0.04, size * 0.96, size * 0.96), fill=255)
    g.putalpha(ImageChops.multiply(g.split()[3], circle))
    bg.alpha_composite(g)
    return bg

DENS = {'mdpi': 1, 'hdpi': 1.5, 'xhdpi': 2, 'xxhdpi': 3, 'xxxhdpi': 4}

def main():
    if sys.argv[1] == '--preview':
        im = Image.new('RGBA', (512, 512), (255, 255, 255, 255)); im.alpha_composite(legacy_icon(512))
        im.save(sys.argv[2]); return
    res = sys.argv[1]
    for name, k in DENS.items():
        d = os.path.join(res, 'mipmap-' + name)
        os.makedirs(d, exist_ok=True)
        leg = legacy_icon(round(48 * k))
        leg.save(os.path.join(d, 'ic_launcher.png')); leg.save(os.path.join(d, 'ic_launcher_round.png'))
        fg = glitch_layer(round(108 * k), 0.40)   # adaptive icon: plane inside the 66dp safe zone
        for f in ('icon_foreground.png', 'icon_foreground_round.png', 'icon_foreground_sa.png'):
            fg.save(os.path.join(d, f))

if __name__ == '__main__':
    main()
