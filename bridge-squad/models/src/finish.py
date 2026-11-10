"""finish.glb - finish arch over the whole road.
Width 11 (posts centred at x=+-5.5, outside the 10 m road), height ~5,
checkered banner (geometry + 2 materials, no textures) and flags.
Run: python3 bridge-squad/models/src/finish.py
"""
import math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import obstacle_lib as L
import bmesh

L.reset()
white = L.mat("finish_white", "#f7f4ec", 0.4)
navy = L.mat("finish_checker_dark", "#222838", 0.5)
red = L.mat("finish_red", "#e8403a", 0.35)
gold = L.mat("finish_gold", "#ffc531", 0.35, 0.3)
base = L.mat("finish_base", "#3b4560", 0.6)
pole = L.mat("finish_pole", "#c9ced9", 0.3, 0.6)
lamp = L.mat("finish_lamp", "#fff6d8", 0.3, emit="#fff1c2", emit_strength=3.0)

PX = 5.5           # post centre
PW = 0.6           # post width
POST_H = 4.7

for s in (-1, 1):
    x = s * PX
    L.box((1.0, 1.0, 0.36), (x, 0, 0.18), base, bev=0.06, name="plinth")
    L.box((PW, PW, POST_H - 0.36), (x, 0, 0.36 + (POST_H - 0.36) / 2), white, bev=0.07,
          taper=(0.8, 0.8), name="post")
    # red bands around the post (sporty stripes)
    for k, zc in enumerate((0.8, 1.6, 2.4, 3.2)):
        t = 1.0 - 0.2 * (zc - 0.36) / (POST_H - 0.36)   # follow taper
        L.box((PW * t + 0.04, PW * t + 0.04, 0.3), (x, 0, zc), red, bev=0.03, name="band")
    # lamps facing the road on the inner face
    for zc in (1.2, 2.0, 2.8):
        t = 1.0 - 0.2 * (zc - 0.36) / (POST_H - 0.36)
        L.box((0.04, 0.2, 0.2), (x - s * (PW * t / 2 + 0.01), 0, zc), lamp, bev=0.02, name="lamp")
    # gold cap
    L.box((0.62, 0.62, 0.16), (x, 0, POST_H + 0.08), gold, bev=0.05, name="cap")
    # flag pole + waving flag
    L.cyl(0.035, 1.0, (x, 0, POST_H + 0.16 + 0.5), pole, segs=8, name="pole")
    L.cyl(0.07, 0.07, (x, 0, POST_H + 1.19), gold, segs=8, name="pole_tip")
    # wavy flag pointing inward (over the road), checker 3x2
    n, fl, fh = 6, 1.25, 0.78
    bm = bmesh.new()
    rows = []
    for j in range(3):
        row = []
        for i in range(n + 1):
            u = i / n
            xx = u * fl
            yy = 0.12 * math.sin(u * math.pi * 1.6)
            zz = j / 2 * fh - 0.06 * u
            row.append(bm.verts.new((-s * (xx + 0.03) + x, yy, POST_H + 0.42 + zz)))
        rows.append(row)
    for j in range(2):
        for i in range(n):
            f = bm.faces.new((rows[j][i], rows[j][i + 1], rows[j + 1][i + 1], rows[j + 1][i]))
            f.material_index = (i // 2 + j) % 2
    res = bmesh.ops.solidify(bm, geom=list(bm.faces), thickness=0.025)
    L.from_bm(bm, [white, navy], "flag")

# ---- top beam and checkered banner
BZ0, BZ1 = 3.55, 4.55          # banner bottom / top
BX = PX - PW / 2 + 0.02        # banner half width (between posts)
cols, rows_n = 16, 2
cw = 2 * BX / cols
ch = (BZ1 - BZ0) / rows_n
BD = 0.16                      # banner depth
for i in range(cols):
    for j in range(rows_n):
        m = white if (i + j) % 2 == 0 else navy
        L.box((cw, BD, ch), (-BX + cw * (i + 0.5), 0, BZ0 + ch * (j + 0.5)), m, name="cell")
# red frame rails above / below the banner
L.box((2 * PX + 0.2, 0.3, 0.2), (0, 0, BZ1 + 0.1), red, bev=0.05, name="rail_top")
L.box((2 * BX, 0.24, 0.14), (0, 0, BZ0 - 0.07), red, bev=0.04, name="rail_bot")

# ---- bunting under the banner: small triangular pennants
pc = 14
for k in range(pc):
    xk = -BX + 0.35 + k * (2 * BX - 0.7) / (pc - 1)
    m = gold if k % 2 == 0 else red
    bm = bmesh.new()
    sag = 0.10 * math.cos((xk / BX) * math.pi / 2)
    ztop = BZ0 - 0.14 - sag
    a = bm.verts.new((xk - 0.17, 0, ztop))
    b = bm.verts.new((xk + 0.17, 0, ztop))
    c = bm.verts.new((xk, 0, ztop - 0.38))
    bm.faces.new((a, b, c))
    bmesh.ops.solidify(bm, geom=list(bm.faces), thickness=0.03)
    L.from_bm(bm, m, "pennant", smooth=False)

ob = L.finalize("finish", smooth_angle=40)
L.export(ob, "finish")
L.preview(ob, "finish", dist_mul=1.55, yaw=15)
