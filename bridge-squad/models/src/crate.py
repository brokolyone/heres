"""crate.glb - explosive barrels + ammo crates on a pallet.
Footprint ~2 x 2, height ~1.8, centred at 0,0, bottom z=0.
Run: python3 bridge-squad/models/src/crate.py
"""
import math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import obstacle_lib as L

L.reset()
wood = L.mat("pallet_wood", "#b9834d", 0.8)
wood_dark = L.mat("pallet_wood_dark", "#8a5a32", 0.85)
yellow = L.mat("barrel_yellow", "#f5c02c", 0.4, 0.2)
black = L.mat("hazard_dark", "#272b36", 0.5, 0.2)
steel = L.mat("barrel_rim", "#5d6577", 0.35, 0.6)
red = L.mat("explosive_red", "#e2392f", 0.4)
olive = L.mat("ammo_olive", "#5f7b3a", 0.6)
olive_d = L.mat("ammo_olive_dark", "#45592b", 0.65)
stencil = L.mat("ammo_stencil", "#f2e7c4", 0.6)

# ---- pallet (top at z=0.16)
PT = 0.16
for x in (-0.82, 0.0, 0.82):
    L.box((0.22, 2.0, 0.1), (x, 0, 0.05), wood_dark, name="runner")
for k in range(5):
    y = -0.84 + k * 0.42
    L.box((2.0, 0.34, 0.06), (0, y, 0.13), wood, name="slat")

# ---- barrels
BR, BH = 0.42, 1.12


def barrel(x, y, rotz=0.0, top_red=True):
    z0 = PT
    L.cyl(BR, BH, (x, y, z0 + BH / 2), yellow, segs=16, bev=0.03, name="barrel")
    # steel rims (top, bottom)
    for zz in (0.07, BH - 0.07):
        bm = L.band_bm(BR + 0.02, -0.03, 0.03, segs=16, mat_pattern=(0,))
        L.xform(bm, (x, y, z0 + zz))
        L.from_bm(bm, steel, "rim", smooth=True)
    # diagonal hazard band between the ribs
    bm = L.band_bm(BR + 0.012, BH * 0.39, BH * 0.61, segs=16, twist=math.radians(22))
    L.xform(bm, (x, y, z0), (0, 0, rotz))
    L.from_bm(bm, [black, yellow], "hazard", smooth=False)
    # lid details: red bung + dark cap disc
    L.cyl(BR - 0.07, 0.02, (x, y, z0 + BH + 0.005), black, segs=16, name="lid")
    if top_red:
        L.cyl(0.07, 0.06, (x + 0.18, y + 0.1, z0 + BH + 0.03), red, segs=8, name="bung")


barrel(-0.5, 0.48, 0)
barrel(0.47, 0.5, 11)
barrel(-0.5, -0.47, 5)

# ---- ammo crate front-right (on pallet)
CX, CY = 0.48, -0.48
L.box((0.86, 0.8, 0.56), (CX, CY, PT + 0.28), olive, bev=0.04, name="ammo")
L.box((0.9, 0.84, 0.1), (CX, CY, PT + 0.56 - 0.04), olive_d, bev=0.03, name="ammo_lid")
for sx in (-1, 1):
    L.box((0.08, 0.86, 0.5), (CX + sx * 0.3, CY, PT + 0.26), olive_d, bev=0.02, name="ammo_band")
L.box((0.36, 0.03, 0.12), (CX, CY - 0.415, PT + 0.28), stencil, name="ammo_label")
L.box((0.12, 0.05, 0.05), (CX, CY - 0.43, PT + 0.42), black, bev=0.01, name="ammo_handle")

# ---- crate on top of the two back barrels: explosives box (red)
TZ = PT + BH + 0.02
L.box((1.3, 0.6, 0.46), (0.0, 0.5, TZ + 0.23), red, bev=0.05, rot=(0, 0, 4), name="tnt")
L.box((1.34, 0.64, 0.08), (0.0, 0.5, TZ + 0.06), black, bev=0.02, rot=(0, 0, 4), name="tnt_base")
# yellow/black stripe across the front of the explosives box
for k in range(6):
    m = yellow if k % 2 == 0 else black
    L.box((0.16, 0.03, 0.16), (-0.4 + k * 0.16, 0.5 - 0.3 - 0.012 + (-0.4 + k * 0.16) * math.tan(math.radians(4)),
                               TZ + 0.27), m, rot=(0, 45, 4), name="tnt_stripe")

ob = L.finalize("crate", smooth_angle=40)
L.export(ob, "crate")
L.preview(ob, "crate", dist_mul=2.7)
