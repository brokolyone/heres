"""Paints the textures for the hand-made parts of the creek scene: taro leaf and frog skin."""
import math, sys
import numpy as np
from PIL import Image, ImageFilter

out = sys.argv[1] if len(sys.argv) > 1 else "art/creek/textures"
rng = np.random.default_rng(7)


def noise(n, scale, octaves=4):
    acc = np.zeros((n, n))
    amp = 1.0
    for o in range(octaves):
        s = max(2, int(scale * 2 ** o))
        small = rng.random((s, s))
        acc += amp * np.asarray(Image.fromarray((small * 255).astype(np.uint8)).resize((n, n), Image.BICUBIC)) / 255.0
        amp *= 0.5
    return acc / acc.max()


def save(arr, name):
    Image.fromarray(np.clip(arr * 255, 0, 255).astype(np.uint8)).save(f"{out}/{name}")


# Leaf: U across the blade (0..1, midrib at 0.5), V from the base (0) to the tip (1).
N = 1024
v, u = np.mgrid[0:N, 0:N] / (N - 1)
v = 1 - v
x = (u - 0.5) * 2
mid = np.exp(-(x / 0.018) ** 2)
veins = np.zeros_like(u)
for k in range(14):
    start = 0.04 + k * 0.068
    # lateral veins leave the midrib and bend toward the tip
    target = start + 0.22 * np.abs(x) ** 0.8
    d = np.abs(v - target)
    veins = np.maximum(veins, np.exp(-(d / 0.006) ** 2) * (np.abs(x) > 0.02) * (1 - np.abs(x) ** 3))
fine = noise(N, 40, 3)
fine_veins = (np.abs(np.sin(fine * 60)) < 0.08) * 0.15
mottle = noise(N, 6, 4)
edge = np.clip(np.abs(x) * 1.1, 0, 1) ** 4
base = np.stack([0.07, 0.20, 0.035])[None, None] * (0.75 + 0.5 * mottle[..., None])
light = np.array([0.30, 0.42, 0.10])
rib = np.array([0.42, 0.52, 0.16])
col = base + (light - base) * (0.35 * edge[..., None] + 0.15 * v[..., None] ** 2)
col = col + (rib - col) * np.clip(mid * 0.8 + veins * 0.22 + fine_veins * 0.4, 0, 1)[..., None]
save(col, "taro_leaf_color.png")
bump = np.clip(0.5 + 0.5 * mid + 0.35 * veins + 0.1 * fine_veins - 0.05 * mottle, 0, 1)
save(np.repeat(bump[..., None], 3, 2), "taro_leaf_bump.png")
trans = np.clip(0.35 + 0.5 * (1 - mid) * (1 - 0.6 * veins) * (0.7 + 0.3 * mottle), 0, 1)
save(np.repeat(trans[..., None], 3, 2), "taro_leaf_translucency.png")

# Stem: long, yellow-green, slightly striped. U around, V along.
v, u = np.mgrid[0:256, 0:64] / np.array([255, 63])[:, None, None]
stripes = 0.5 + 0.5 * np.sin(u * math.tau * 6 + noise(256, 4)[:, :64] * 3)
stem = np.array([0.42, 0.55, 0.12]) * (0.85 + 0.15 * stripes[..., None])
stem = stem + (np.array([0.20, 0.35, 0.06]) - stem) * (1 - v[..., None]) * 0.5
save(stem, "taro_stem_color.png")

# Frog skin: olive green back with dark spots, paler belly, warty bump. Spherical UV: V=0 belly .. 1 back.
N = 1024
v, u = np.mgrid[0:N, 0:N] / (N - 1)
v = 1 - v
cells = rng.random((40, 2))
pts = rng.random((260, 2))
d = np.full((N, N), 9.0)
for p in pts:
    du = np.minimum(np.abs(u - p[0]), 1 - np.abs(u - p[0]))
    d = np.minimum(d, np.hypot(du * 2, v - p[1]))
spots = 0.6 * np.clip(1 - d / 0.03, 0, 1) ** 0.6 * (v > 0.45)
warts = np.zeros((N, N))
for p in rng.random((900, 2)):
    du = np.minimum(np.abs(u - p[0]), 1 - np.abs(u - p[0]))
    warts = np.maximum(warts, np.clip(1 - np.hypot(du * 2, v - p[1]) / 0.012, 0, 1))
m = noise(N, 8, 4)
back = np.array([0.30, 0.40, 0.12]) * (0.8 + 0.4 * m[..., None])
belly = np.array([0.62, 0.60, 0.40])
side = np.clip((v - 0.30) / 0.25, 0, 1)[..., None]
skin = belly + (back - belly) * side
skin = skin * (1 - 0.75 * spots[..., None])
skin = skin + (np.array([0.45, 0.50, 0.18]) - skin) * (warts[..., None] * 0.35 * side)
save(skin, "frog_green_color.png")
brown = skin * np.array([1.2, 0.9, 0.75])
brown = brown + (np.array([0.35, 0.18, 0.10]) - brown) * 0.45 * side
save(brown, "frog_brown_color.png")
save(np.repeat((0.5 + 0.5 * warts - 0.2 * spots)[..., None], 3, 2), "frog_bump.png")

# Small flower petal (pink-magenta, darker centre), square UV.
N = 256
y, x = np.mgrid[-1:1:N * 1j, -1:1:N * 1j]
r = np.hypot(x, y)
petal = np.array([0.95, 0.45, 0.45]) * (1 - 0.35 * np.clip(1 - r, 0, 1)[..., None])
petal = petal + (np.array([0.98, 0.85, 0.85]) - petal) * np.clip(r - 0.6, 0, 1)[..., None]
save(petal, "flower_petal_color.png")
print("textures written to", out)
