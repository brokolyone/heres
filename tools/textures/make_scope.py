"""Draw the sniper scope overlay (mil-dot reticle) used while aiming.

    python3 tools/textures/make_scope.py src/main/resources/assets/heres/textures/misc/sniper_scope.png

Minecraft stretches it over a square in the middle of the screen, the same way it
draws the vanilla spyglass_scope.png, and fills the rest of the screen black.
"""
import sys

import numpy as np
from PIL import Image, ImageDraw

N = 1024
SS = 2  # supersample for smooth edges


def main(out):
    n = N * SS
    c = n / 2
    yy, xx = np.mgrid[0:n, 0:n]
    r = np.hypot(xx - c + 0.5, yy - c + 0.5) / c

    alpha = np.clip((r - 0.86) / 0.12, 0, 1) ** 1.5  # soft vignette into the black tube
    alpha[r > 0.98] = 1.0
    rgba = np.zeros((n, n, 4), np.uint8)
    rgba[..., 3] = (alpha * 255).astype(np.uint8)
    img = Image.fromarray(rgba, "RGBA")
    d = ImageDraw.Draw(img)

    black = (0, 0, 0, 255)
    thin = 2 * SS
    thick = 12 * SS
    gap = 0.18 * c
    # thick outer posts, thin centre crosshair
    d.rectangle([c - thick / 2, c + gap * 2.2, c + thick / 2, n], fill=black)
    d.rectangle([0, c - thick / 2, c - gap * 2.2, c + thick / 2], fill=black)
    d.rectangle([c + gap * 2.2, c - thick / 2, n, c + thick / 2], fill=black)
    d.rectangle([c - thin / 2, 0, c + thin / 2, c + gap * 2.2], fill=black)
    d.rectangle([c - gap * 2.2, c - thin / 2, c + gap * 2.2, c + thin / 2], fill=black)
    # mil dots
    for k in range(1, 6):
        off = k * gap * 2.2 / 5.5
        for dx, dy in ((off, 0), (-off, 0), (0, off), (0, -off)):
            rr = 4 * SS
            d.ellipse([c + dx - rr, c + dy - rr, c + dx + rr, c + dy + rr], fill=black)
    # illuminated red centre dot
    rr = 4 * SS
    d.ellipse([c - rr, c - rr, c + rr, c + rr], fill=(230, 20, 20, 255))

    img.resize((N, N), Image.LANCZOS).save(out)
    print("scope written to", out)


if __name__ == "__main__":
    main(sys.argv[1])
