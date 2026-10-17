#!/usr/bin/env python3
"""Generates ArtGraf's logo, window icon and splash artwork.

Run from this directory:  python3 make_art.py
Outputs: logo.png (512x512), artgraf.ico (16..256), splash.png (960x560)
Requires Pillow. Flat shapes only; the title uses DejaVu Sans (free license).
"""
from PIL import Image, ImageDraw, ImageFont

BLUE = (38, 128, 235)
BLUE_DARK = (22, 92, 186)
BLUE_DEEP = (14, 52, 110)
BLUE_LIGHT = (110, 176, 248)
INK = (17, 21, 28)

S = 2048  # working resolution, downsampled for antialiasing


def squircle(size, n=5.0, pad=0.0):
    """Superellipse mask, the usual app-icon shape."""
    m = Image.new("L", (size, size), 0)
    px = m.load()
    r = size / 2 * (1 - pad)
    c = size / 2
    for y in range(size):
        dy = abs((y + 0.5 - c) / r)
        if dy >= 1:
            continue
        xr = (1 - dy ** n) ** (1 / n) * r
        for x in range(max(0, int(c - xr)), min(size, int(c + xr) + 1)):
            px[x, y] = 255
    return m


def make_logo():
    img = Image.new("RGBA", (S, S), BLUE + (255,))
    d = ImageDraw.Draw(img)
    # lower half one step darker: a flat two-tone, no gradients
    d.rectangle([0, S * 0.62, S, S], fill=BLUE_DARK + (255,))

    # Bold geometric "A"
    a = Image.new("L", (S, S), 0)
    da = ImageDraw.Draw(a)
    top, base = S * 0.19, S * 0.81
    half_top, half_base = S * 0.07, S * 0.30
    stroke = S * 0.145
    outer = [(S / 2 - half_top, top), (S / 2 + half_top, top), (S / 2 + half_base, base), (S / 2 + half_base - stroke, base),
             (S / 2, top + S * 0.17), (S / 2 - half_base + stroke, base), (S / 2 - half_base, base)]
    da.polygon(outer, fill=255)
    da.rectangle([S * 0.36, S * 0.56, S * 0.64, S * 0.65], fill=255)
    img.paste((255, 255, 255, 255), (0, 0), a)

    mask = squircle(S, n=5.0, pad=0.03)
    img.putalpha(mask)
    return img


def make_splash(logo):
    W, H = 960, 560
    img = Image.new("RGB", (W, H), INK)
    d = ImageDraw.Draw(img)

    # Right side: flat overlapping blocks, like layers in a document
    blocks = [((560, -40, 1010, 300), BLUE_DEEP), ((640, 120, 1000, 600), BLUE_DARK), ((520, 260, 820, 600), BLUE),
              ((760, 40, 900, 200), BLUE_LIGHT), ((600, 330, 700, 430), (235, 240, 248))]
    for box, col in blocks:
        d.rounded_rectangle(box, radius=18, fill=col)

    # Left side text
    lg = logo.resize((96, 96), Image.LANCZOS)
    img.paste(lg, (56, 64), lg)

    def font(names, size):
        for n in names:
            try:
                return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/" + n, size)
            except OSError:
                pass
        return ImageFont.load_default()

    title = font(["DejaVuSans-Bold.ttf"], 60)
    sub = font(["DejaVuSans.ttf"], 21)
    small = font(["DejaVuSans.ttf"], 14)
    d.text((54, 196), "ArtGraf", font=title, fill=(240, 243, 248))
    d.text((58, 274), "Графический редактор", font=sub, fill=(150, 162, 180))
    d.text((58, 512), "Версия 2.0", font=small, fill=(110, 122, 140))
    return img


if __name__ == "__main__":
    logo = make_logo()
    logo.resize((512, 512), Image.LANCZOS).save("logo.png", optimize=True)
    logo.resize((256, 256), Image.LANCZOS).save(
        "artgraf.ico", sizes=[(16, 16), (20, 20), (24, 24), (32, 32), (40, 40), (48, 48), (64, 64), (128, 128), (256, 256)])
    make_splash(logo).save("splash.png", optimize=True)
    print("ok")
