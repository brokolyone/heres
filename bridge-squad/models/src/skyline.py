"""Skyline decoration: rocky islands with pines, a lighthouse and a pastel city silhouette.

Spans ~120 m along X (x -58..60), ~25 m along Y, bottom on the water line z=-9.
Meant to sit 40-80 m to the side of the bridge (mirror it for the other side).
Run: python3 bridge-squad/models/src/skyline.py
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy  # noqa: E402
import bmesh  # noqa: E402
from mathutils import Vector  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402

import env_lib as L  # noqa: E402

WATER = -9.0
rnd = random.Random(11)

L.reset()

M_ROCK = L.material("RockWarm", "#CDB9A8", rough=0.9)
M_ROCK2 = L.material("RockShade", "#B39E92", rough=0.9)
M_GRASS = L.material("GrassPastel", "#9FCB86", rough=0.9)
M_SAND = L.material("SandPastel", "#F0DDB2", rough=0.9)
M_PINE = L.material("PineGreen", "#4E9C7B", rough=0.8)
M_PINE2 = L.material("PineGreenLight", "#68B58A", rough=0.8)
M_TRUNK = L.material("TrunkBrown", "#8C6650", rough=0.9)
M_WHITE = L.material("LighthouseWhite", "#F7F2E8", rough=0.6)
M_RED = L.material("LighthouseRed", "#D8332E", rough=0.5)
M_METAL = L.material("LighthouseMetal", "#3F4C5E", rough=0.5)
M_LAMP = L.material("LighthouseLamp", "#FFE9A8", rough=0.3, emit="#FFD77A", emit_strength=3.0)
M_QUAY = L.material("QuayStone", "#E2D6C3", rough=0.85)
M_HILL = L.material("HillGreen", "#B3D9A6", rough=0.9)
M_GLASS = L.material("WindowBand", "#8FB3D3", rough=0.3)
M_ROOF = L.material("RoofTerracotta", "#E08A6E", rough=0.8)
BLD = [L.material(n, c, rough=0.8) for n, c in (
    ("BuildingPeach", "#F5BCA2"), ("BuildingLavender", "#BDB5E0"), ("BuildingSky", "#A9D0EA"),
    ("BuildingMint", "#AADDC6"), ("BuildingButter", "#F4E1A2"), ("BuildingRose", "#EDAAB7"),
    ("BuildingCream", "#F3E8D3"))]

b = L.Builder()


# ---------------------------------------------------------------- islands
def rock_lump(cx, cy, rx, ry, h, subdiv=2, jitter=0.14):
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=1.0)
    for v in bm.verts:
        n = v.co.normalized()
        j = 1.0 + rnd.uniform(-jitter, jitter)
        v.co = Vector((n.x * rx * j + cx, n.y * ry * j + cy, n.z * h * j * (1.0 if n.z > 0 else 0.4) + WATER - 0.4))
    bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=(0, 0, WATER),
                           plane_no=(0, 0, 1), clear_inner=True)
    return bm


def island(lumps, subdiv=2):
    """lumps: list of (cx, cy, rx, ry, h). Returns BVH of the island for placing props."""
    bms = []
    for lp in lumps:
        bm = rock_lump(*lp, subdiv=subdiv)
        top = max(v.co.z for v in bm.verts)

        def mat_fn(f, top=top):
            c = f.calc_center_median()
            if c.z < WATER + 0.55:
                return M_SAND
            if f.normal.z > 0.62 and c.z > WATER + (top - WATER) * 0.35:
                return M_GRASS
            return M_ROCK if (hash((round(c.x, 1), round(c.y, 1))) % 3) else M_ROCK2

        bm.normal_update()
        b.from_bmesh(bm, mat_fn)
        bms.append(bm)
    return bms


def ground_z(bms, x, y):
    best = None
    for bm in bms:
        tree = BVHTree.FromBMesh(bm)
        hit = tree.ray_cast(Vector((x, y, 50)), Vector((0, 0, -1)))
        if hit[0] is not None and (best is None or hit[0].z > best):
            best = hit[0].z
    return best


def pine(x, y, z, scale):
    trunk_h = 0.9 * scale
    b.prism((x, y, z - 0.3), (x, y, z + trunk_h), 0.22 * scale, M_TRUNK, sides=5, caps=False, smooth=False)
    mat = M_PINE if rnd.random() < 0.6 else M_PINE2
    zz = z + trunk_h * 0.7
    roll = rnd.uniform(0, math.pi)
    for r, hh in ((1.45, 2.2), (1.1, 1.9), (0.75, 1.6)):
        b.cone((x, y, zz), hh * scale, r * scale, mat, sides=6, cap=True, roll=roll)
        zz += hh * scale * 0.52


def scatter_pines(bms, cx, cy, rx, ry, n, smin=0.9, smax=1.4, inner=0.62):
    placed = []
    tries = 0
    while len(placed) < n and tries < 400:
        tries += 1
        a = rnd.uniform(0, 2 * math.pi)
        rr = math.sqrt(rnd.random()) * inner
        x, y = cx + math.cos(a) * rx * rr, cy + math.sin(a) * ry * rr
        if any((x - px) ** 2 + (y - py) ** 2 < 3.2 for px, py in placed):
            continue
        z = ground_z(bms, x, y)
        if z is None or z < WATER + 1.2:
            continue
        pine(x, y, z, rnd.uniform(smin, smax))
        placed.append((x, y))


# big pine island (left)
bmsA = island([(-47, 2, 10.5, 7.5, 7.5), (-38, -2, 6.5, 5.5, 4.5), (-54, -3, 5, 4.5, 3.5)], subdiv=3)
scatter_pines(bmsA, -46, 1, 10, 7, 11)
scatter_pines(bmsA, -38, -2, 5, 4, 3)

# small rocky islet with a few pines
bmsB = island([(-28, -5, 4.8, 4.0, 4.2)])
scatter_pines(bmsB, -28, -5, 4, 3.5, 3, inner=0.5)

# lighthouse island
bmsC = island([(-14, 1, 6.5, 5.5, 5.0), (-9, -1.5, 3.8, 3.2, 2.6)], subdiv=3)
scatter_pines(bmsC, -16.5, 2.5, 3.0, 2.5, 2, inner=0.6)

# tiny rocks
island([(-34, -11, 2.2, 1.8, 1.8)])
island([(-3, -7, 2.0, 1.6, 1.4)])
island([(-60, 6, 2.6, 2.2, 2.2)])

# lighthouse
lx, ly = -12.5, 0.2
lz = ground_z(bmsC, lx, ly) - 0.4
bands = [M_WHITE, M_RED, M_WHITE, M_RED]
H = 9.0
r0, r1 = 1.35, 0.9
for i, m in enumerate(bands):
    t0, t1 = i / 4, (i + 1) / 4
    b.prism((lx, ly, lz + H * t0), (lx, ly, lz + H * t1), r0 + (r1 - r0) * t0, m, sides=10,
            caps=False, smooth=True, r1=r0 + (r1 - r0) * t1)
b.prism((lx, ly, lz - 0.6), (lx, ly, lz + 0.5), 1.75, M_WHITE, sides=10, caps=True, smooth=False)
b.prism((lx, ly, lz + H), (lx, ly, lz + H + 0.3), 1.3, M_METAL, sides=10, caps=True, smooth=False)
b.prism((lx, ly, lz + H + 0.3), (lx, ly, lz + H + 1.4), 0.68, M_LAMP, sides=8, caps=False, smooth=False)
b.prism((lx, ly, lz + H + 1.4), (lx, ly, lz + H + 1.55), 0.85, M_METAL, sides=8, caps=True, smooth=False)
b.cone((lx, ly, lz + H + 1.55), 0.9, 0.85, M_RED, sides=8)
b.prism((lx, ly, lz + H + 2.4), (lx, ly, lz + H + 2.9), 0.06, M_METAL, sides=4, caps=False, smooth=False)
# keeper's cottage
hx, hy = -15.8, -0.6
hz = ground_z(bmsC, hx, hy) - 0.3
b.box(hx - 1.4, hx + 1.4, hy - 1.0, hy + 1.0, hz, hz + 1.8, M_WHITE, skip=("-z",))
b.add([(hx - 1.6, hy - 1.15, hz + 1.8), (hx + 1.6, hy - 1.15, hz + 1.8), (hx + 1.6, hy, hz + 3.0),
       (hx - 1.6, hy, hz + 3.0), (hx - 1.6, hy + 1.15, hz + 1.8), (hx + 1.6, hy + 1.15, hz + 1.8)],
      [(0, 1, 2, 3), (3, 2, 5, 4), (0, 3, 4), (1, 5, 2)], M_RED)

# ---------------------------------------------------------------- city
QX0, QX1 = 3.0, 60.0
# quay / low land with sloped sea wall
b.add([(QX0, -11, WATER), (QX1, -11, WATER), (QX1, 11, WATER), (QX0, 11, WATER),
       (QX0 + 1.0, -10, WATER + 1.4), (QX1 - 0.5, -10, WATER + 1.4), (QX1 - 0.5, 10, WATER + 1.4),
       (QX0 + 1.0, 10, WATER + 1.4)],
      [(4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (3, 0, 4, 7), (2, 3, 7, 6)], M_QUAY)
QZ = WATER + 1.4

# green hills behind the city
hills = [(26, 14, 18, 7, 9), (48, 13, 14, 6, 12)]
for cx, cy, rx, ry, h in hills:
    bm = rock_lump(cx, cy, rx, ry, h, subdiv=2, jitter=0.06)
    b.from_bmesh(bm, lambda f: M_HILL if f.calc_center_median().z > WATER + 0.6 else M_SAND)


def building(x, y, w, d, h, mat, bands=0, top=None):
    b.box(x - w / 2, x + w / 2, y - d / 2, y + d / 2, QZ, QZ + h, mat, skip=("-z",))
    for k in range(bands):
        zb = QZ + h * (0.3 + 0.55 * k / max(1, bands))
        b.box(x - w / 2 - 0.05, x + w / 2 + 0.05, y - d / 2 - 0.05, y + d / 2 + 0.05, zb, zb + 0.5, M_GLASS,
              skip=("-z", "+z"))
    zt = QZ + h
    if top == "step":
        b.box(x - w * 0.33, x + w * 0.33, y - d * 0.33, y + d * 0.33, zt, zt + h * 0.12, mat, skip=("-z",))
        b.box(x - w * 0.18, x + w * 0.18, y - d * 0.18, y + d * 0.18, zt + h * 0.12, zt + h * 0.2, mat,
              skip=("-z",))
        b.cone((x, y, zt + h * 0.2), h * 0.22, w * 0.12, M_WHITE, sides=4, roll=math.pi / 4)
    elif top == "roof":
        b.add([(x - w / 2, y - d / 2, zt), (x + w / 2, y - d / 2, zt), (x + w / 2, y, zt + w * 0.35),
               (x - w / 2, y, zt + w * 0.35), (x - w / 2, y + d / 2, zt), (x + w / 2, y + d / 2, zt)],
              [(0, 1, 2, 3), (3, 2, 5, 4), (0, 3, 4), (1, 5, 2)], M_ROOF)
    elif top == "dome":
        b.cone((x, y, zt), min(w, d) * 0.45, min(w, d) * 0.45, M_ROOF, sides=8)
    elif top == "tank":
        b.prism((x + w * 0.2, y, zt), (x + w * 0.2, y, zt + 1.2), 0.5, M_ROOF, sides=6, caps=True, smooth=False)


# skyline: low houses in front, taller towers in the middle/back; peak near x~32
x = QX0 + 2.6
row_rand = random.Random(5)
while x < QX1 - 2.5:
    peak = math.exp(-((x - 33.0) / 13.0) ** 2)
    for row, y in enumerate((-6.5, -1.0, 4.5)):
        w = row_rand.uniform(2.6, 4.2)
        d = row_rand.uniform(3.0, 4.6)
        base = (2.5, 5.0, 7.0)[row]
        h = base + peak * (6 + 10 * row) * row_rand.uniform(0.6, 1.1) + row_rand.uniform(0, 2.5)
        if row == 0:
            top = "roof" if row_rand.random() < 0.55 else None
        else:
            top = row_rand.choice([None, None, "tank", "step" if h > 12 else "roof", "dome" if h < 9 else None])
        building(x + row_rand.uniform(-0.4, 0.4), y, w, d, h, row_rand.choice(BLD),
                 bands=(2 if h > 12 else 1 if h > 7 else 0), top=top)
    x += row_rand.uniform(4.0, 5.2)

# landmark art-deco skyscraper
building(33.5, 1.5, 5.0, 5.0, 26.0, BLD[6], bands=3, top="step")
building(42.0, 3.0, 3.6, 3.6, 20.0, BLD[1], bands=2, top="step")

sky = b.build("skyline")
L.export([sky], "skyline")

# ---------------------------------------------------------------- preview (game-like: behind/above)
L.preview_setup(water=True, water_z=WATER)
L.game_camera((0, 12, -2), 118, pitch_deg=40, lens=30)
L.render("skyline")
dbg = os.environ.get("PREVIEW_DEBUG_DIR")
if dbg:
    L.camera((0, -70, 4), (0, 0, -2), lens=30)
    L.render(os.path.join(dbg, "skyline_front.png"), samples=32)
