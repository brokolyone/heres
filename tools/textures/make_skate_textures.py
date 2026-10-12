"""Paint the skateboard source textures (grip tape, deck graphic, plywood edge).

    python3 tools/textures/make_skate_textures.py art/skateboard

They feed the Blender materials in build_skateboard.py, which then get baked into
the single texture the mod uses.
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONT = "/usr/share/fonts/truetype/freefont/FreeSansBoldOblique.ttf"
rng = np.random.default_rng(7)


def grip(w=1024, h=256):
    base = rng.normal(22, 7, (h, w)).clip(0, 255)
    sparkle = rng.random((h, w)) > 0.985
    base[sparkle] += rng.uniform(25, 60, sparkle.sum())
    img = Image.fromarray(np.stack([base] * 3, -1).clip(0, 255).astype(np.uint8))
    d = ImageDraw.Draw(img)
    # two red pin-stripes behind the front truck
    for x in (150, 168):
        d.rectangle([x, 0, x + 6, h], fill=(170, 20, 25))
    return img


def graphic(w=1024, h=256):
    y = np.linspace(0, 1, h)[:, None]
    top = np.array([40, 10, 80])
    mid = np.array([235, 50, 120])
    bot = np.array([255, 170, 40])
    sky = np.where(y < 0.55, top + (mid - top) * (y / 0.55), mid + (bot - mid) * ((y - 0.55) / 0.45))
    img = Image.fromarray(np.broadcast_to(sky[:, None, :], (h, w, 3)).astype(np.uint8))
    d = ImageDraw.Draw(img)

    # striped retro sun
    cx, cy, r = w // 2, int(h * 0.62), int(h * 0.42)
    sun = Image.new("L", (w, h), 0)
    ImageDraw.Draw(sun).ellipse([cx - r, cy - r, cx + r, cy + r], fill=255)
    sd = ImageDraw.Draw(sun)
    for i, yy in enumerate(range(cy - r // 6, cy + r, 14)):
        sd.rectangle([0, yy, w, yy + 3 + i], fill=0)
    img.paste((255, 225, 90), mask=sun)

    # dragon wing silhouettes flanking the sun
    for sx in (-1, 1):
        pts = [(cx + sx * 40, cy - 10)]
        for k in range(5):
            pts.append((cx + sx * (110 + k * 45), cy - 95 + k * 22))
            pts.append((cx + sx * (125 + k * 45), cy - 40 + k * 12))
        pts.append((cx + sx * 40, cy + 20))
        d.polygon(pts, fill=(25, 5, 45))

    font = ImageFont.truetype(FONT, 118)
    text = "HERES"
    tw = d.textlength(text, font=font)
    d.text((cx - tw / 2, 28), text, font=font, fill=(255, 255, 255), stroke_width=7, stroke_fill=(20, 0, 35))
    small = ImageFont.truetype(FONT, 30)
    for label, x in (("SKATE CO.", 165), ("EST. 2026", w - 325)):
        d.text((x, h - 52), label, font=small, fill=(255, 245, 230), stroke_width=3, stroke_fill=(40, 0, 50))
    return img.filter(ImageFilter.SMOOTH)


def ply(w=256, h=64):
    colors = [(222, 190, 140), (40, 90, 170), (222, 190, 140), (200, 40, 50),
              (222, 190, 140), (40, 90, 170), (222, 190, 140)]
    rows = np.repeat(np.array(colors), h // len(colors) + 1, axis=0)[:h]
    img = np.broadcast_to(rows[:, None, :], (h, w, 3)).astype(np.float32)
    img = img * rng.uniform(0.9, 1.05, (1, w, 1))
    return Image.fromarray(img.clip(0, 255).astype(np.uint8))


if __name__ == "__main__":
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    grip().save(os.path.join(out, "grip.png"))
    graphic().save(os.path.join(out, "graphic.png"))
    ply().save(os.path.join(out, "ply.png"))
    print("textures written to", out)
