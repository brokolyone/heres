"""tires.glb - barricade of stacked tyres wrapped in red/white tape + sandbags.
Footprint ~2.2 x 2.2, height ~2.0, centred at 0,0, bottom z=0.
Run: python3 bridge-squad/models/src/tires.py
"""
import math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import obstacle_lib as L
import bmesh

L.reset()
rubber = L.mat("tire_rubber", "#2c3140", 0.8)
inner = L.mat("tire_inner", "#1d212c", 0.9)
tape_r = L.mat("tape_red", "#e5383b", 0.45)
tape_w = L.mat("tape_white", "#f6f2e9", 0.45)
sand = L.mat("sandbag", "#c9a86b", 0.9)
rope = L.mat("sandbag_tie", "#8c6a3c", 0.9)

R, r, rz = 0.66, 0.32, 0.25          # tyre ring radius, tube radius, tube half-height
offsets = [(0.0, 0.0, 0), (0.06, -0.04, 11), (-0.05, 0.03, 4), (0.03, 0.05, 15)]
for i, (ox, oy, ph) in enumerate(offsets):
    z = rz + i * 2 * rz
    bm = L.torus_bm(R, r, nu=16, nv=8, rz=rz, phase=math.radians(ph))
    L.xform(bm, (ox, oy, z))
    L.from_bm(bm, rubber, "tyre")
    # hazard tape around the tread, diagonal stripes, alternating direction
    tw = math.radians(14) * (1 if i % 2 == 0 else -1)
    bm = L.band_bm(R + r + 0.04, -0.1, 0.1, segs=16, twist=tw)
    L.xform(bm, (ox, oy, z), (0, 0, ph))
    L.from_bm(bm, [tape_r, tape_w], "tape", smooth=False)

# dark core filling the hole of the stack
L.cyl(R - r + 0.06, 4 * 2 * rz - 0.12, (0, 0, (4 * 2 * rz - 0.12) / 2), inner, segs=12, name="core")

def sandbag(loc, rotz, scale=(0.95, 0.66, 0.32), tilt=0.0):
    """Pillow-shaped bag: beveled box with pinched ends and a puffy middle."""
    bm = L.box_bm(scale, bev=0.11, segs=2)
    hx = scale[0] / 2
    for v in bm.verts:
        k = 1.0 - 0.22 * (abs(v.co.x) / hx) ** 2       # pinch towards the ends
        v.co.y *= k
        v.co.z = (v.co.z + scale[2] / 2) * k - scale[2] / 2 * k  # keep bottom flat-ish
    L.xform(bm, (loc[0], loc[1], loc[2]), (tilt, 0, rotz))
    L.from_bm(bm, sand, "sandbag")
    for sx in (-1, 1):   # ties at both ends
        a = math.radians(rotz)
        d = hx - 0.02
        L.cyl(0.06, 0.06, (loc[0] + sx * d * math.cos(a), loc[1] + sx * d * math.sin(a), loc[2]),
              rope, segs=6, rot=(0, 90, rotz), name="tie")


# sandbags at the base on the player-facing side (-Y) and sides
sandbag((-0.48, -0.84, 0.15), 6)
sandbag((0.5, -0.83, 0.15), -8)
sandbag((0.02, -0.86, 0.44), 2, tilt=-6)
sandbag((0.86, 0.3, 0.15), 78)
sandbag((-0.87, 0.24, 0.15), -82)

ob = L.finalize("tires", smooth_angle=50)
L.export(ob, "tires")
L.preview(ob, "tires", dist_mul=2.6)
