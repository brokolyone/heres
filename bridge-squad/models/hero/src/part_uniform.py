"""Hero soldier — UNIFORM & GEAR part (owner: Uniform & Gear artist).

Builds: jacket torso + collar, sleeves, armoured shoulder pads with emblem, pants seat, pant legs,
cargo pockets, knee pads, boots (sole, welt, toe cap, tongue, laces, pull tab), belt + buckle +
belt pouches + canteen, plate carrier (front/back plates, cummerbund, shoulder straps, MOLLE rows,
triple mag pouch, admin pouch, radio + antenna), backpack (body, flap with emblem, front pocket, side
pockets, compression straps, buckles, carry handle, bedroll, shoulder straps + sternum strap).
LOD0 and LOD1 (.lo) versions. Run:  cd models/hero && python3 src/part_uniform.py [--no-preview]
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hero_common import *  # noqa
import bpy, bmesh
from mathutils import Vector, Matrix

V = Vector
OWNER = "uni"
UVU = 0.5           # 1 UV unit = 0.5 m
LOD = 0             # current LOD being built (set by build())
PI = math.pi


# =============================================================== generic helpers
def clamp(x, a, b):
    return a if x < a else b if x > b else x


def smooth01(t):
    t = clamp(t, 0.0, 1.0)
    return t * t * (3 - 2 * t)


def lerp(a, b, t):
    return a + (b - a) * t


def interp_keys(keys, z):
    """Catmull-Rom through keys [(z, a, b, c...)], returns tuple of values."""
    if z <= keys[0][0]:
        return keys[0][1:]
    if z >= keys[-1][0]:
        return keys[-1][1:]
    for i in range(len(keys) - 1):
        if keys[i][0] <= z <= keys[i + 1][0]:
            break
    k0 = keys[max(i - 1, 0)]; k1 = keys[i]; k2 = keys[i + 1]; k3 = keys[min(i + 2, len(keys) - 1)]
    t = (z - k1[0]) / (k2[0] - k1[0])
    out = []
    for j in range(1, len(k1)):
        p0, p1, p2, p3 = k0[j], k1[j], k2[j], k3[j]
        v = 0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3)
        out.append(v)
    return tuple(out)


def basis(origin, xdir, ydir):
    x = V(xdir).normalized()
    y = V(ydir) - x * x.dot(V(ydir)); y.normalize()
    z = x.cross(y)
    m = Matrix.Identity(4)
    for r in range(3):
        m[r][0] = x[r]; m[r][1] = y[r]; m[r][2] = z[r]; m[r][3] = origin[r]
    return m


def xform(bm, M):
    for v in bm.verts:
        v.co = M @ v.co


def auto_sharp(bm, deg=42.0):
    a = math.radians(deg)
    for f in bm.faces:
        f.smooth = True
    for e in bm.edges:
        if len(e.link_faces) == 2:
            try:
                if e.calc_face_angle() > a:
                    e.smooth = False
            except ValueError:
                pass


def finish(name, bm, mats, target="body", uv="auto", sharp=42.0):
    """bm -> object. mats: list of slot names (face.material_index indexes it)."""
    if LOD == 1:
        name += ".lo"
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    auto_sharp(bm, sharp)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    for m in mats:
        me.materials.append(mat(m))
    if uv == "auto" or not me.uv_layers:
        uv_world(ob, unit=UVU)
    else:
        me.uv_layers[0].name = "UVMap"
    tag(ob, target, LOD, OWNER)
    return ob


def merge_bm(dst, src, mat_index=0):
    """Append src bmesh into dst (both bmesh), setting material index; frees src."""
    me = bpy.data.meshes.new("_tmp")
    for f in src.faces:
        f.material_index = mat_index
    src.to_mesh(me); src.free()
    dst.from_mesh(me)
    bpy.data.meshes.remove(me)
    return dst


# --------------------------------------------------------------- primitives
def rbox(size, bevel=0.0, segs=2, cuts=(0, 0, 0), taper_top=0.0):
    """Bevelled box centred at origin, size (x,y,z). cuts: extra bisect cuts per axis.
    taper_top: shrink x at +z by this fraction (pouch look)."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    sx, sy, sz = size
    for v in bm.verts:
        v.co = V((v.co.x * sx, v.co.y * sy, v.co.z * sz))
    if bevel > 0 and segs > 0:
        bmesh.ops.bevel(bm, geom=bm.verts[:] + bm.edges[:], offset=bevel, offset_type="OFFSET",
                        segments=segs, profile=0.5, affect="EDGES", clamp_overlap=True)
    for ax in range(3):
        n = cuts[ax]
        for k in range(n):
            p = V((0, 0, 0)); no = V((0, 0, 0)); no[ax] = 1
            p[ax] = -size[ax] / 2 + size[ax] * (k + 1) / (n + 1)
            bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], dist=1e-6,
                                   plane_co=p, plane_no=no)
    if taper_top:
        for v in bm.verts:
            t = (v.co.z / sz) + 0.5
            v.co.x *= 1.0 - taper_top * t
    return bm


def cyl(r, h, n=12, caps=True, bevel=0.0, segs=1):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=caps, cap_tris=False, segments=n, radius1=r, radius2=r, depth=h)
    if bevel > 0:
        cap_edges = [e for e in bm.edges if abs(e.verts[0].co.z - e.verts[1].co.z) < 1e-7]
        bmesh.ops.bevel(bm, geom=cap_edges + bm.verts[:], offset=bevel, offset_type="OFFSET", segments=segs,
                        profile=0.5, affect="EDGES", clamp_overlap=True)
    return bm


def loft(rings, cap0=True, cap1=True, closed=True, uv=True):
    """Rings: list of lists of Vector (equal length). Quads between consecutive rings.
    Writes world-scale UVs: u = arc length, v = distance along columns."""
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap") if uv else None
    nr = len(rings); nv = len(rings[0])
    verts = [[bm.verts.new(p) for p in ring] for ring in rings]
    # UV coordinates (per ring arc length; per column distance)
    us = []
    for ring in rings:
        acc = [0.0]
        rng = ring + ([ring[0]] if closed else [])
        for i in range(1, len(rng)):
            acc.append(acc[-1] + (rng[i] - rng[i - 1]).length)
        us.append(acc)
    vs = [[0.0] * (nv + 1)]
    for r in range(1, nr):
        row = []
        for i in range(nv + 1):
            ii = i % nv
            row.append(vs[r - 1][i] + (rings[r][ii] - rings[r - 1][ii]).length)
        vs.append(row)
    ncol = nv if closed else nv - 1
    for r in range(nr - 1):
        for i in range(ncol):
            j = (i + 1) % nv
            f = bm.faces.new((verts[r][i], verts[r][j], verts[r + 1][j], verts[r + 1][i]))
            if uv:
                cs = [(us[r][i], vs[r][i]), (us[r][i + 1], vs[r][i + 1]), (us[r + 1][i + 1], vs[r + 1][i + 1]),
                      (us[r + 1][i], vs[r + 1][i])]
                for l, (a, b) in zip(f.loops, cs):
                    l[uvl].uv = (a / UVU, b / UVU)
    for ci, (do, r) in enumerate(((cap0, 0), (cap1, nr - 1))):
        if not do or not closed:
            continue
        c = sum(rings[r], V()) / nv
        cv = bm.verts.new(c)
        for i in range(nv):
            j = (i + 1) % nv
            tri = (verts[r][j], verts[r][i], cv) if ci == 0 else (verts[r][i], verts[r][j], cv)
            f = bm.faces.new(tri)
            if uv:
                for l in f.loops:
                    l[uvl].uv = (l.vert.co.x / UVU, l.vert.co.y / UVU)
    bm.normal_update()
    return bm


def grid_slab(outer, inner, uv=False):
    """outer/inner: 2D lists [row][col] of points. Builds closed slab (outer, inner reversed, walls)."""
    bm = bmesh.new()
    R = len(outer); C = len(outer[0])
    vo = [[bm.verts.new(p) for p in row] for row in outer]
    vi = [[bm.verts.new(p) for p in row] for row in inner]
    for r in range(R - 1):
        for c in range(C - 1):
            bm.faces.new((vo[r][c], vo[r][c + 1], vo[r + 1][c + 1], vo[r + 1][c]))
            bm.faces.new((vi[r][c], vi[r + 1][c], vi[r + 1][c + 1], vi[r][c + 1]))
    border = [(0, c) for c in range(C)] + [(r, C - 1) for r in range(1, R)] + \
             [(R - 1, c) for c in range(C - 2, -1, -1)] + [(r, 0) for r in range(R - 2, 0, -1)]
    for k in range(len(border)):
        a = border[k]; b = border[(k + 1) % len(border)]
        bm.faces.new((vo[a[0]][a[1]], vi[a[0]][a[1]], vi[b[0]][b[1]], vo[b[0]][b[1]]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def ribbon(path, normals, width, thick, uv=True, chamfer=0.35, cap=True, flat=False, solid=False):
    """Strap following path (list of V) lying on surface with normals. Cross-section is a
    chamfered rectangle (6 pts) — or a single flat quad strip if flat."""
    n = len(path)
    rings = []
    for i in range(n):
        t = (path[min(i + 1, n - 1)] - path[max(i - 1, 0)]).normalized()
        nn = normals[i] - t * normals[i].dot(t); nn.normalize()
        s = t.cross(nn).normalized()
        hw = width / 2; c = min(thick * chamfer * 2, hw * 0.5)
        if flat:
            sec = [(-hw, thick), (hw, thick)]
        else:
            sec = [(hw, -0.0015), (hw - min(thick * 0.5, hw * 0.3), thick), (-hw + min(thick * 0.5, hw * 0.3), thick), (-hw, -0.0015)]
        rings.append([path[i] + s * a + nn * b for a, b in sec])
    if flat:
        # quad strip: rows = path, cols = 2
        bm = loft(rings, cap0=False, cap1=False, closed=False, uv=uv)
        return bm
    if solid:   # closed section (for straps hanging in the air)
        return loft(rings, cap0=cap, cap1=cap, closed=True, uv=uv)
    bm = loft(rings, cap0=False, cap1=False, closed=False, uv=uv)
    if cap:
        bm.verts.ensure_lookup_table()
        m = len(rings[0])
        for idx, sign in ((list(range(m)), -1), (list(range(len(bm.verts) - m, len(bm.verts))), 1)):
            vs = [bm.verts[i] for i in idx]
            f = bm.faces.new(vs)
            tdir = (path[-1] - path[-2]) if sign > 0 else (path[0] - path[1])
            f.normal_update()
            if f.normal.dot(tdir) < 0:
                f.normal_flip()
    return bm


def resample(pts, n):
    """Resample polyline into n evenly spaced points."""
    L = [0.0]
    for i in range(1, len(pts)):
        L.append(L[-1] + (pts[i] - pts[i - 1]).length)
    out = []
    for k in range(n):
        s = L[-1] * k / (n - 1)
        for i in range(1, len(pts)):
            if L[i] >= s - 1e-12:
                break
        seg = max(L[i] - L[i - 1], 1e-12)
        t = (s - L[i - 1]) / seg
        out.append(pts[i - 1].lerp(pts[i], t))
    return out


def smooth_path(pts, it=2):
    for _ in range(it):
        q = [pts[0]]
        for i in range(1, len(pts) - 1):
            q.append((pts[i - 1] + pts[i] * 2 + pts[i + 1]) / 4)
        q.append(pts[-1])
        pts = q
    return pts


def pipe(pts, r, sides=5, caps=True):
    T, N, B = tube_frames(pts)
    rings = [[p + (N[i] * math.cos(a) + B[i] * math.sin(a)) * r for a in [2 * PI * k / sides for k in range(sides)]]
             for i, p in enumerate(pts)]
    return loft(rings, cap0=caps, cap1=caps)


def slab_edge_path(outer, inner, push=0.0):
    """Open boundary of a grid slab (left column down, last row across, right column up), midline."""
    R_ = len(outer); C_ = len(outer[0])
    idx = [(r, 0) for r in range(R_)] + [(R_ - 1, c) for c in range(1, C_)] + [(r, C_ - 1) for r in range(R_ - 2, -1, -1)]
    pts = []
    for r, c in idx:
        m = (outer[r][c] + inner[r][c]) / 2
        pts.append(m + (outer[r][c] - inner[r][c]).normalized() * push)
    return smooth_path(pts, 1)


def star_bm(r_out, r_in, depth, points=5):
    bm = bmesh.new()
    top = []; bot = []
    for k in range(points * 2):
        a = PI / 2 + k * PI / points
        r = r_out if k % 2 == 0 else r_in
        top.append(bm.verts.new((r * math.cos(a), depth, r * math.sin(a))))
        bot.append(bm.verts.new((r * math.cos(a), 0.0, r * math.sin(a))))
    ct = bm.verts.new((0, depth * 1.6, 0))
    m = len(top)
    for k in range(m):
        j = (k + 1) % m
        bm.faces.new((top[j], top[k], ct))
        bm.faces.new((bot[k], bot[j], top[j], top[k]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


# =============================================================== torso surface model
N_SE = 2.7
# (z, half-width x, front y, back y)  — jacket surface
TORSO = [
    (0.300, 0.132, 0.093, 0.091),
    (0.330, 0.134, 0.095, 0.093),
    (0.360, 0.139, 0.100, 0.097),
    (0.400, 0.150, 0.108, 0.102),
    (0.440, 0.160, 0.113, 0.107),
    (0.480, 0.165, 0.115, 0.110),
    (0.515, 0.166, 0.113, 0.109),
    (0.550, 0.162, 0.107, 0.105),
    (0.575, 0.152, 0.098, 0.097),
    (0.595, 0.132, 0.086, 0.087),
    (0.610, 0.105, 0.074, 0.076),
    (0.620, 0.078, 0.064, 0.066),
    (0.626, 0.060, 0.058, 0.060),
]
TZ0, TZ1 = TORSO[0][0], TORSO[-1][0]


def tprof(z):
    return interp_keys(TORSO, z)


def se_pt(t, hx, yf, yb, n=N_SE, off=0.0):
    c, s = math.cos(t), math.sin(t)
    x = hx * math.copysign(abs(c) ** (2 / n), c)
    y = (yf if s >= 0 else yb) * math.copysign(abs(s) ** (2 / n), s)
    if off:
        # numeric 2D normal
        e = 1e-3
        c2, s2 = math.cos(t + e), math.sin(t + e)
        x2 = hx * math.copysign(abs(c2) ** (2 / n), c2)
        y2 = (yf if s2 >= 0 else yb) * math.copysign(abs(s2) ** (2 / n), s2)
        tx, ty = x2 - x, y2 - y
        L = math.hypot(tx, ty) or 1
        x += ty / L * off; y += -tx / L * off
    return x, y


def se_field(p):
    z = clamp(p.z, TZ0, TZ1)
    hx, yf, yb = tprof(z)
    yy = yf if p.y >= 0 else yb
    f = (abs(p.x) / hx) ** N_SE + (abs(p.y) / yy) ** N_SE
    if p.z > TZ1:
        f += ((p.z - TZ1) / 0.012) ** 2
    if p.z < TZ0:
        f += ((TZ0 - p.z) / 0.012) ** 2
    return f


def s_normal(p):
    e = 1e-4
    g = V((se_field(p + V((e, 0, 0))) - se_field(p - V((e, 0, 0))),
           se_field(p + V((0, e, 0))) - se_field(p - V((0, e, 0))),
           se_field(p + V((0, 0, e))) - se_field(p - V((0, 0, e)))))
    return g.normalized()


def s_hit(c, d, tmax=0.4):
    d = V(d).normalized()
    a, b = 0.0, tmax
    for _ in range(40):
        m = (a + b) / 2
        if se_field(c + d * m) < 1.0:
            a = m
        else:
            b = m
    p = c + d * a
    return p, s_normal(p)


def surf_y(x, z, front=True):
    hx, yf, yb = tprof(z)
    u = min(abs(x) / hx, 0.999)
    r = (1 - u ** N_SE) ** (1 / N_SE)
    return yf * r if front else -yb * r


def conform_front(bm, front=True, base=0.0):
    """Verts built with local y = offset above the surface; moved onto the torso (projected along Y)."""
    for v in bm.verts:
        w = v.co.y + base
        sy = surf_y(v.co.x, v.co.z, front)
        v.co.y = sy + w if front else sy - w


# =============================================================== parts
def torso():
    nt = 24 if LOD == 0 else 8
    zs = ([0.300, 0.330, 0.360, 0.400, 0.440, 0.480, 0.515, 0.550, 0.575, 0.595, 0.610, 0.620, 0.626]
          if LOD == 0 else [0.30, 0.46, 0.55, 0.595, 0.626])
    if LOD == 0:
        zs = [0.300, 0.340, 0.400, 0.460, 0.515, 0.550, 0.575, 0.595, 0.610, 0.626]
    rings = []
    for z in zs:
        hx, yf, yb = tprof(z)
        ring = []
        for k in range(nt):
            t = -PI / 2 + 2 * PI * k / nt   # start at back centre (hidden under backpack)
            x, y = se_pt(t, hx, yf, yb)
            ring.append(V((x, y, z)))
        rings.append(ring)
    bm = loft(rings, cap0=True, cap1=True)
    finish("uni.jacket_torso", bm, ["M_jacket_blue"], uv="own")
    if LOD == 0:
        # front zipper placket strip (visible between vest plate and belt / in the collar V)
        pts = [V((0.0, 0, z)) for z in [0.335, 0.37, 0.56, 0.59, 0.612]]
        path = []; nrm = []
        for p in pts:
            q, n = s_hit(V((0, 0, p.z)), V((0, 1, 0.0)))
            path.append(q); nrm.append(n)
        bm = ribbon(path, nrm, 0.020, 0.004)
        finish("uni.jacket_placket", bm, ["M_jacket_blue"], uv="own")


def collar():
    if LOD == 1:
        return
    n = 24
    prof = [(0.068, 0.600), (0.067, 0.645), (0.062, 0.660), (0.056, 0.645)]
    if LOD == 1:
        prof = [(0.067, 0.600), (0.066, 0.655), (0.056, 0.655)]
    rings = []
    for r, z in prof:
        ring = []
        for k in range(n):
            a = -PI / 2 + 2 * PI * k / n
            front = max(0.0, math.sin(a)) ** 6        # V-notch at front
            zz = z - (0.030 * front if z > 0.62 else 0.0)
            ring.append(V((r * math.cos(a), r * math.sin(a) + 0.004, zz)))
        rings.append(ring)
    bm = loft(rings, cap0=False, cap1=False)
    finish("uni.collar", bm, ["M_jacket_blue"], uv="own", sharp=60)


def arm_path(side):
    if side == "R":
        S, E, W = A["shoulder_R"], A["elbow_R"], A["wrist_R"]
    else:
        S, E, W = A["shoulder_L"], A["elbow_L"], A["wrist_L"]
    out = V((1 if side == "R" else -1, 0, 0))
    S0 = S - out * 0.035 + V((0, 0, 0.004))
    dW = (W - E).normalized()
    Wend = W + dW * 0.010
    # rounded elbow: quadratic bezier between points before/after the elbow
    a = S0.lerp(E, 0.62); b = E.lerp(Wend, 0.30)
    pts = [S0.lerp(a, t / 4) for t in range(4)]
    for k in range(9):
        t = k / 8
        pts.append(a * (1 - t) ** 2 + E * 2 * (1 - t) * t + b * t * t)
    pts += [b.lerp(Wend, t / 5) for t in range(1, 6)]
    return pts, S, E, W


def tube_frames(path):
    n = len(path)
    T = [(path[min(i + 1, n - 1)] - path[max(i - 1, 0)]).normalized() for i in range(n)]
    up = V((0, 0, 1)) if abs(T[0].z) < 0.9 else V((0, 1, 0))
    N = [(up - T[0] * up.dot(T[0])).normalized()]
    for i in range(1, n):
        nn = N[-1] - T[i] * N[-1].dot(T[i]); nn.normalize()
        N.append(nn)
    B = [T[i].cross(N[i]) for i in range(n)]
    return T, N, B


def sleeve(side):
    raw, S, E, W = arm_path(side)
    nseg = 17 if LOD == 0 else 5
    nar = 12 if LOD == 0 else 6
    path = resample(smooth_path(raw, 1), nseg)
    T, N, B = tube_frames(path)
    L = [0.0]
    for i in range(1, len(path)):
        L.append(L[-1] + (path[i] - path[i - 1]).length)
    tot = L[-1]
    # elbow index & outer direction
    dU = (E - S).normalized(); dF = (W - E).normalized()
    outer = (dU - dF).normalized()
    ie = min(range(len(path)), key=lambda i: (path[i] - E).length)
    rings = []
    for i, p in enumerate(path):
        t = L[i] / tot
        r = lerp(0.060, 0.051, smooth01(t / 0.55))
        r = lerp(r, 0.044, smooth01((t - 0.55) / 0.35))
        if LOD == 0:
            # fabric bunching on forearm + cuff band at wrist
            if 0.58 < t < 0.88:
                r += 0.0028 * math.sin((t - 0.58) / 0.30 * PI * 3) ** 2
            dist_end = tot - L[i]
            if dist_end < 0.030:
                r = 0.0475
            if dist_end < 0.004:
                r = 0.043
        ring = []
        for k in range(nar):
            a = 2 * PI * k / nar + PI / 2
            d = N[i] * math.cos(a) + B[i] * math.sin(a)
            rr = r
            if LOD == 0:
                # elbow: gather folds on the inside of the bend, slight point on the outside
                w = math.exp(-((L[i] - L[ie]) / 0.03) ** 2)
                cosin = d.dot(outer)
                rr += w * (0.004 * max(0.0, cosin) - 0.004 * max(0.0, -cosin) * (0.5 + 0.5 * math.sin(L[i] * 260)))
            ring.append(p + d * rr)
        rings.append(ring)
    bm = loft(rings, cap0=True, cap1=True)
    finish(f"uni.sleeve_{side}", bm, ["M_jacket_blue"], uv="own")
    if LOD == 0:
        # pad strap ring around the upper arm, just below the shoulder pad (coaxial with the sleeve)
        i_s = min(range(len(path) // 2), key=lambda i: abs(path[i].z - 0.492))
        t = L[i_s] / tot
        r = lerp(0.060, 0.051, smooth01(t / 0.55)) + 0.0008
        ring = []; nn = []
        for k in range(13):
            a = 2 * PI * k / 12
            d = N[i_s] * math.cos(a) + B[i_s] * math.sin(a)
            ring.append(path[i_s] + d * r); nn.append(d)
        bm = ribbon(ring, nn, 0.014, 0.004, cap=False)
        finish(f"uni.pad_strap_{side}", bm, ["M_strap_tan"], uv="own")


def shoulder_pad(side):
    sgn = 1 if side == "R" else -1
    S = A["shoulder_R"] if side == "R" else A["shoulder_L"]
    C = V((S.x - sgn * 0.022, S.y - 0.002, S.z - 0.012))
    layers = [(0.084, -0.35, 1.35, 0.066, 0.074, 0.000)] if LOD == 1 else \
             [(0.086, -0.30, 1.52, 0.068, 0.076, 0.000)]
    for li, (R, b0, b1, yb, yf, dz) in enumerate(layers):
        nb = 6 if LOD == 0 else 2
        na = 7 if LOD == 0 else 2
        outer = []; inner = []
        for ib in range(nb + 1):
            beta = lerp(b0, b1, ib / nb)       # 0 = straight up, + = towards outside
            ro = []; ri = []
            for ia in range(na + 1):
                u = lerp(-1, 1, ia / na)
                yext = yf if u > 0 else yb
                # rounded corners: pull the corners in
                corner = (abs(u) ** 4) * (max(0.0, (ib / nb - 0.6) / 0.4) ** 2 + max(0.0, (0.15 - ib / nb) / 0.15) ** 2)
                y = u * yext * (1 - 0.30 * corner)
                droop = (u ** 2) * 0.018
                rr = R - droop
                p = C + V((sgn * math.sin(beta) * rr, y, math.cos(beta) * rr + dz))
                ro.append(p)
                ri.append(C + V((sgn * math.sin(beta) * (rr - 0.011), y * 0.97, math.cos(beta) * (rr - 0.011) + dz)))
            outer.append(ro); inner.append(ri)
        bm = grid_slab(outer, inner)
        finish(f"uni.shoulder_pad{li}_{side}", bm, ["M_helmet_blue"], sharp=70)
        if LOD == 0 and li == 0:
            bm = pipe(slab_edge_path(outer, inner, 0.0005), 0.0068, sides=5)
            finish(f"uni.pad_piping_{side}", bm, ["M_rubber_dark"], uv="own", sharp=70)
    if LOD == 0:
        # emblem star on the outer face
        beta = 0.82
        R = 0.086
        p = C + V((sgn * math.sin(beta) * R, 0.004, math.cos(beta) * R))
        nrm = V((sgn * math.sin(beta), 0, math.cos(beta)))
        bm = star_bm(0.026, 0.011, 0.003)
        xform(bm, basis(p - nrm * 0.0015, V((0, -sgn, 0)), nrm) @ Matrix.Rotation(0, 4, "X"))
        # basis maps local x->tangent(y), local y->normal, local z-> x cross y (up-ish)
        finish(f"uni.pad_emblem_{side}", bm, ["M_emblem"], sharp=30)


def pants_seat():
    keys = [(0.352, 0.133, 0.094, 0.095), (0.322, 0.136, 0.096, 0.098), (0.300, 0.148, 0.102, 0.108),
            (0.280, 0.146, 0.098, 0.108), (0.266, 0.126, 0.084, 0.094), (0.258, 0.090, 0.060, 0.068)]
    if LOD == 1:
        keys = [keys[0], keys[2], keys[4]]
    nt = 20 if LOD == 0 else 8
    rings = []
    for z, hx, yf, yb in keys:
        ring = []
        for k in range(nt):
            t = -PI / 2 + 2 * PI * k / nt
            x, y = se_pt(t, hx, yf, yb, n=2.5)
            ring.append(V((x, y, z)))
        rings.append(ring)
    bm = loft(rings)
    # pull the lowest cap centre to the crotch point
    finish("uni.pants_seat", bm, ["M_pants_navy"], uv="own")


def leg(side):
    sgn = 1 if side == "R" else -1
    hip = A["hip_R"] if side == "R" else A["hip_L"]
    knee = A["knee_R"] if side == "R" else A["knee_L"]
    tgt = "leg_" + side
    prof = [(0.318, 0.064), (0.295, 0.067), (0.255, 0.065), (0.210, 0.061),
            (0.170, 0.060), (0.150, 0.065), (0.136, 0.063), (0.126, 0.050), (0.116, 0.046)]
    if LOD == 1:
        prof = [(0.318, 0.064), (0.200, 0.062), (0.145, 0.064), (0.120, 0.052)]
    n = 14 if LOD == 0 else 6
    rings = []
    for z, r in prof:
        ring = []
        cy = lerp(0.0, knee.y, clamp((0.30 - z) / 0.135, 0, 1))
        for k in range(n):
            a = -PI / 2 + 2 * PI * k / n      # seam at the back
            rr = r
            if LOD == 0 and 0.13 < z < 0.16:
                rr += 0.0018 * math.cos(a * 4)   # soft bloused folds over boot
            ring.append(V((hip.x + rr * math.cos(a), cy + rr * math.sin(a) * 0.96, z)))
        rings.append(ring)
    bm = loft(rings)
    finish(f"uni.pant_leg_{side}", bm, ["M_pants_navy"], target=tgt, uv="own")
    axis = V((hip.x, knee.y, 0))

    def bend(bm, r, a0):
        # local: x = arc, y = radial offset, z = height
        for v in bm.verts:
            a = a0 + v.co.x / r
            R = r + v.co.y
            v.co = V((axis.x + R * math.cos(a), axis.y + R * math.sin(a) * 0.96, v.co.z))

    # knee pad (rubber) + 2 straps
    if LOD == 0:
        bm = rbox((0.088, 0.018, 0.070), bevel=0.007, segs=1, cuts=(3, 0, 1))
        for v in bm.verts:
            v.co.z += 0.172
            v.co.y += 0.009
            # domed: thicker in the middle
            v.co.y += 0.006 * (1 - (v.co.x / 0.044) ** 2) * (1 - ((v.co.z - 0.172) / 0.035) ** 2) * (v.co.y > 0.01)
        bend(bm, 0.059, PI / 2)
        finish(f"uni.knee_pad_{side}", bm, ["M_rubber_dark"], target=tgt)
        # raised cap plate on the knee pad
        bm = rbox((0.050, 0.008, 0.036), bevel=0.003, segs=1)
        for v in bm.verts:
            v.co.z += 0.176; v.co.y += 0.029
        bend(bm, 0.059, PI / 2)
        finish(f"uni.knee_cap_{side}", bm, ["M_rubber_dark"], target=tgt)
        for zz in (0.160, 0.198):
            ring = []; nn = []
            rz = interp_keys([(z_, r_) for z_, r_ in reversed(prof)], zz)[0] if False else None
            # linear interpolation of the pant profile (prof is top->bottom)
            for j in range(len(prof) - 1):
                if prof[j + 1][0] <= zz <= prof[j][0]:
                    tt = (zz - prof[j + 1][0]) / (prof[j][0] - prof[j + 1][0])
                    rz = lerp(prof[j + 1][1], prof[j][1], tt)
            cyz = lerp(0.0, knee.y, clamp((0.30 - zz) / 0.135, 0, 1))
            for k in range(n + 1):
                a = -PI / 2 + 2 * PI * k / n
                d = V((math.cos(a), math.sin(a) * 0.96, 0))
                ring.append(V((axis.x, cyz, zz)) + d * (rz + 0.0012)); nn.append(d.normalized())
            bm = ribbon(ring, nn, 0.011, 0.0035, cap=False)
            finish(f"uni.knee_strap_{side}_{int(zz*1000)}", bm, ["M_strap_tan"], target=tgt, uv="own")
        # cargo pocket on outer thigh + flap + snap
        a0 = 0.0 if side == "R" else PI
        sg = 1 if side == "R" else -1
        bm = rbox((0.070, 0.014, 0.068), bevel=0.005, segs=1, cuts=(2, 0, 0))
        for v in bm.verts:
            v.co.x *= sg; v.co.z += 0.238; v.co.y += 0.0075
            v.co.y += 0.004 * (1 - (v.co.x / 0.035) ** 2) * (v.co.y > 0.008)
        bend(bm, 0.0655, a0)
        finish(f"uni.cargo_pocket_{side}", bm, ["M_pants_navy"], target=tgt)
        bm = rbox((0.076, 0.010, 0.026), bevel=0.004, segs=1, cuts=(2, 0, 0))
        for v in bm.verts:
            v.co.x *= sg; v.co.z += 0.270; v.co.y += 0.020 - 0.004 * (v.co.z < 0.262)
        bend(bm, 0.0655, a0)
        finish(f"uni.cargo_flap_{side}", bm, ["M_pants_navy"], target=tgt)
    else:
        bm = rbox((0.080, 0.016, 0.066))
        for v in bm.verts:
            v.co.z += 0.172; v.co.y += 0.008
        bend(bm, 0.059, PI / 2)
        finish(f"uni.knee_pad_{side}", bm, ["M_rubber_dark"], target=tgt)
    boot(side)


def foot_ring(cx, z, yb, yf, hw, n, grow=0.0, nexp=2.4):
    ring = []
    for k in range(n):
        t = -PI / 2 + 2 * PI * k / n   # start at heel
        c, s = math.cos(t), math.sin(t)
        x = (hw + grow) * math.copysign(abs(c) ** (2 / nexp), c)
        yy = (yf + grow) if s >= 0 else (yb + grow)
        y = yy * math.copysign(abs(s) ** (2 / (nexp if s < 0 else 2.0)), s)
        # toe narrowing + slight inward toe (towards x=0)
        if y > 0:
            k2 = (y / (yf + grow)) ** 2
            x *= 1 - 0.18 * k2
        ring.append(V((cx + x, y, z)))
    return ring


BOOT = [  # z, heel y, toe y, half width
    (0.024, 0.062, 0.140, 0.055),
    (0.040, 0.064, 0.143, 0.057),
    (0.056, 0.064, 0.138, 0.0565),
    (0.069, 0.062, 0.122, 0.055),
    (0.080, 0.060, 0.096, 0.053),
    (0.092, 0.058, 0.075, 0.052),
    (0.106, 0.057, 0.064, 0.0515),
    (0.120, 0.057, 0.060, 0.053),
    (0.132, 0.058, 0.060, 0.0555),
    (0.136, 0.052, 0.054, 0.0500),
]


def boot_front(z):
    """front y of boot upper at height z (centre line), and surface normal in yz."""
    ks = [(b[0], b[2]) for b in BOOT]
    y = interp_keys(ks, z)[0]
    e = 0.002
    dy = (interp_keys(ks, z + e)[0] - interp_keys(ks, z - e)[0]) / (2 * e)
    nrm = V((0, 1.0, -dy)).normalized()
    return y, nrm


def boot(side):
    sgn = 1 if side == "R" else -1
    cx = A["ankle_R"].x if side == "R" else A["ankle_L"].x
    tgt = "leg_" + side
    n = 18 if LOD == 0 else 8
    keys = BOOT if LOD == 0 else [BOOT[0], BOOT[3], BOOT[5], BOOT[8]]
    rings = [foot_ring(cx, z, yb, yf, hw, n) for z, yb, yf, hw in keys]
    bm = loft(rings, cap0=(LOD == 1), cap1=True)
    finish(f"uni.boot_{side}", bm, ["M_leather_brown"], target=tgt, uv="own")
    # sole: z 0 .. 0.026, with welt lip
    sk = [(0.000, -0.003), (0.006, 0.002), (0.020, 0.004), (0.028, 0.0)] if LOD == 0 else \
         [(0.0, 0.002), (0.026, 0.002)]
    rings = [foot_ring(cx, z, 0.062, 0.140, 0.055, n, grow=g + 0.004) for z, g in sk]
    bm = loft(rings, cap0=True, cap1=True)
    finish(f"uni.sole_{side}", bm, ["M_rubber_dark"], target=tgt, uv="own", sharp=50)
    if LOD == 1:
        return
    # rubber toe bumper (wraps front of toe)
    rr = []
    for z in (0.020, 0.042, 0.060):
        ring = foot_ring(cx, z, 0.062, 0.140, 0.055, n, grow=0.0035 if z < 0.05 else 0.0015)
        rr.append(ring)
    # keep only front part of the ring (open strip)
    sel = [i for i in range(n) if rr[0][i].y > 0.075]
    strip = [[r[i] for i in sel] for r in rr]
    # thicken into slab
    inner = [[p + (V((cx, 0.02, p.z)) - p).normalized() * 0.004 for p in row] for row in strip]
    bm = grid_slab(strip, inner)
    finish(f"uni.toe_bumper_{side}", bm, ["M_rubber_dark"], target=tgt)
    # heel counter (rubber cap at back of heel)
    rr = []
    for z in (0.024, 0.050, 0.070):
        rr.append(foot_ring(cx, z, 0.062, 0.140, 0.055, n, grow=0.002))
    sel = [i for i in range(n) if rr[0][i].y < -0.030]
    sel = sorted(sel, key=lambda i: math.atan2(rr[0][i].y, rr[0][i].x - cx) % (2 * PI))
    strip = [[r[i] for i in sel] for r in rr]
    inner = [[p + (V((cx, 0.0, p.z)) - p).normalized() * 0.004 for p in row] for row in strip]
    bm = grid_slab(strip, inner)
    finish(f"uni.heel_counter_{side}", bm, ["M_leather_brown"], target=tgt)
    # tongue (raised strip up the instep)
    pts = []; nrm = []
    for z in [0.066, 0.080, 0.096, 0.112, 0.127, 0.140]:
        y, nn = boot_front(min(z, 0.131))
        if z > 0.131:
            y = 0.057 + (z - 0.131) * 0.4
        pts.append(V((cx, y - 0.001, z))); nrm.append(nn)
    bm = ribbon(pts, nrm, 0.040, 0.005)
    finish(f"uni.tongue_{side}", bm, ["M_leather_brown"], target=tgt, uv="own")
    # laces: crossing bars + eyelets
    lbm = bmesh.new(); ebm = bmesh.new()
    zs = [0.078, 0.090, 0.102, 0.114, 0.126]
    for i, z in enumerate(zs):
        y, nn = boot_front(z)
        p = V((cx, y + 0.0045, z))
        side_v = V((1, 0, 0))
        up = nn.cross(side_v)
        for s2 in (1, -1):
            b = rbox((0.036, 0.0035, 0.0045))
            xform(b, basis(p + nn * (0.001 if s2 > 0 else 0.0), side_v, nn) @ Matrix.Rotation(s2 * 0.32, 4, "Y"))
            merge_bm(lbm, b, 0)
        for ex in ():
            e = cyl(0.0042, 0.003, n=8)
            xform(e, basis(p + V((ex, -0.002, 0)), side_v, up) @ Matrix.Rotation(PI / 2, 4, "X"))
            merge_bm(ebm, e, 0)
    finish(f"uni.laces_{side}", lbm, ["M_strap_tan"], target=tgt)
    ebm.free()
    # pull tab loop at the back of the boot collar (seen from behind)
    pts = [V((cx, -0.055, 0.112)), V((cx, -0.062, 0.128)), V((cx, -0.064, 0.146)), V((cx, -0.060, 0.152)),
           V((cx, -0.055, 0.146)), V((cx, -0.054, 0.132))]
    nrm = [V((0, -1, 0.0))] * 6
    bm = ribbon(resample(smooth_path(pts, 1), 7), nrm[:1] * 7, 0.018, 0.003, solid=True)
    finish(f"uni.pull_tab_{side}", bm, ["M_strap_tan"], target=tgt, uv="own")
    return
    ring = []; nn = []
    for k in range(25):
        a = 2 * PI * k / 24
        y, _ = boot_front(0.118)
        d = V((math.cos(a), math.sin(a), 0))
        rx = 0.0525; ry = 0.0575 if math.sin(a) < 0 else y
        ring.append(V((cx + d.x * (rx + 0.001), (ry + 0.001) * d.y, 0.111))); nn.append(d)
    bm = ribbon(ring, nn, 0.010, 0.003, cap=False)
    finish(f"uni.ankle_strap_{side}", bm, ["M_leather_brown"], target=tgt, uv="own")
    bm = rbox((0.006, 0.016, 0.014), bevel=0.0015, segs=1)
    xform(bm, Matrix.Translation(V((cx + sgn * 0.056, 0.0, 0.111))))
    finish(f"uni.ankle_buckle_{side}", bm, ["M_metal_bright"], target=tgt)


# =============================================================== belt
BELT_Z = (0.305, 0.355)


def belt():
    n = 24 if LOD == 0 else 8
    zc = sum(BELT_Z) / 2
    hz = (BELT_Z[1] - BELT_Z[0]) / 2
    sec = [(-0.000, -hz), (0.009, -hz + 0.003), (0.009, hz - 0.003), (0.0, hz)] if LOD == 0 \
        else [(0.0, -hz), (0.008, -hz), (0.008, hz), (0.0, hz)]
    rings = []
    for off, dz in sec:
        ring = []
        for k in range(n):
            t = -PI / 2 + 2 * PI * k / n
            x, y = se_pt(t, 0.137, 0.098, 0.100, n=2.5, off=off)
            ring.append(V((x, y, zc + dz)))
        rings.append(ring)
    rings.append(rings[0])
    bm = loft(rings[:-1], cap0=False, cap1=False)
    # close inner wall
    bm2 = loft([rings[-2], rings[0]], cap0=False, cap1=False)
    merge_bm(bm, bm2, 0)
    finish("uni.belt", bm, ["M_strap_tan"], uv="own", sharp=50)
    # buckle
    yb = 0.098 + 0.009
    if LOD == 0:
        bm = rbox((0.062, 0.008, 0.048), bevel=0.003, segs=1)
        # recess the centre: inset the front face
        f = max(bm.faces, key=lambda f: f.calc_center_median().y)
        r = bmesh.ops.inset_region(bm, faces=[f], thickness=0.008, depth=-0.003)
        xform(bm, Matrix.Translation(V((0, yb + 0.003, zc))))
        finish("uni.belt_buckle", bm, ["M_metal_bright"], sharp=40)
        bm = rbox((0.040, 0.004, 0.026), bevel=0.0015, segs=1)
        xform(bm, Matrix.Translation(V((0, yb + 0.004, zc))))
        finish("uni.belt_buckle_tongue", bm, ["M_strap_tan"])
        # belt keepers
        for t in ():
            x, y = se_pt(t, 0.137, 0.098, 0.100, n=2.5, off=0.010)
            bm = rbox((0.012, 0.004, 0.056))
            tang = V((-math.sin(t), math.cos(t), 0))
            xform(bm, basis(V((x, y, zc)), tang, V((x, y, 0))))
            finish(f"uni.belt_keeper_{int(t*100)}", bm, ["M_strap_tan"])
    else:
        bm = rbox((0.055, 0.008, 0.044))
        xform(bm, Matrix.Translation(V((0, yb + 0.002, zc))))
        finish("uni.belt_buckle", bm, ["M_metal_bright"])


def pouch(name, center, normal, w, d, h, flap=True, flap_mat="M_vest_tan", body_mat="M_vest_tan",
          snap=True, up=V((0, 0, 1)), cuts=(1, 0, 0), molle_tabs=False):
    """Pouch box sitting on a surface: centre at back face, normal pointing out."""
    nrm = V(normal).normalized()
    xdir = nrm.cross(up).normalized()
    M = basis(center + nrm * (d / 2), xdir, nrm)   # local x=side, y=normal, z=up
    if LOD == 1:
        bm = rbox((w, d, h))
        xform(bm, M)
        return finish(name, bm, [body_mat])
    bm = rbox((w, d, h), bevel=min(0.006, d * 0.3), segs=1, cuts=cuts, taper_top=0.0)
    # slight bulge on front
    for v in bm.verts:
        if v.co.y > d * 0.3:
            v.co.y += 0.003 * (1 - (2 * v.co.x / w) ** 2) * (1 - (2 * v.co.z / h) ** 2)
    xform(bm, M)
    finish(name, bm, [body_mat])
    if flap:
        fh = h * 0.42
        bm = rbox((w + 0.004, 0.006, fh), bevel=0.0025, segs=1)
        for v in bm.verts:
            v.co.y += d / 2 + 0.0035 + 0.002 * (1 - (2 * v.co.x / w) ** 2)
            v.co.z += h / 2 - fh / 2 + 0.003
            # flap wraps over the top edge
            if v.co.z > h / 2 - 0.002:
                v.co.y -= (v.co.z - (h / 2 - 0.002)) * 1.5
        xform(bm, M)
        finish(name + "_flap", bm, [flap_mat])
        if snap:
            bm = rbox((0.012, 0.006, 0.016))
            xform(bm, M @ Matrix.Translation(V((0, d / 2 + 0.008, h / 2 - fh + 0.006))))
            finish(name + "_tab", bm, ["M_strap_tan"])


# =============================================================== plate carrier
def vest():
    # front plate: outline in x,z (swimmer cut), conformed to chest
    def plate(front=True):
        w, z0, z1 = 0.118, 0.372, 0.560
        if LOD == 0:
            bm = rbox((2 * w, 0.020, z1 - z0), bevel=0.006, segs=1, cuts=(5, 0, 3) if front else (3, 0, 1))
        else:
            bm = rbox((2 * w, 0.020, z1 - z0), cuts=(2, 0, 0))
        for v in bm.verts:
            v.co.z += (z0 + z1) / 2
            v.co.y += 0.012
            # swimmer cut: top corners cut inward
            top = smooth01((v.co.z - 0.50) / 0.06)
            v.co.x *= 1 - 0.30 * top
            if LOD == 0 and v.co.y > 0.018:
                v.co.y += 0.003 * (1 - (v.co.x / w) ** 2)
        conform_front(bm, front)
        return bm
    finish("uni.vest_front", plate(True), ["M_vest_tan"])
    finish("uni.vest_back", plate(False), ["M_vest_tan"])
    # cummerbund: band around the sides joining the plates
    n = 16 if LOD == 0 else 6
    zs = [0.378, 0.384, 0.460, 0.466] if LOD == 0 else [0.38, 0.465]
    rings = []
    for i, z in enumerate(zs):
        hx, yf, yb = tprof(z)
        off = 0.010 if (LOD == 1 or i in (1, 2)) else 0.004
        for side in (1, -1):
            pass
        ring = []
        for k in range(n + 1):
            # from front (t=0.62rad from +x towards +y) round the side to the back
            t = lerp(0.95, -0.95, k / n)
            x, y = se_pt(t, hx, yf, yb, off=off)
            ring.append(V((x, y, z)))
        rings.append(ring)
    for sgn in (1, -1):
        rr = [[V((p.x * sgn, p.y, p.z)) for p in r] for r in rings]
        if sgn < 0:
            rr = [list(reversed(r)) for r in rr]
        cols = [list(c) for c in zip(*rr)]   # rows along the band, cols = heights
        bm = loft([r for r in rr], cap0=False, cap1=False, closed=False)
        # close the inner side by a second inner loft (flat back)
        inner = [[p - V((p.x, p.y, 0)).normalized() * 0.008 for p in r] for r in (rr[0], rr[-1])]
        bm2 = loft([inner[1], inner[0]], cap0=False, cap1=False, closed=False)
        merge_bm(bm, bm2, 0)
        finish(f"uni.cummerbund_{'R' if sgn > 0 else 'L'}", bm, ["M_vest_tan"], uv="own", sharp=50)
    # MOLLE rows on the cummerbund + lower front
    if LOD == 0:
        mbm = bmesh.new()
        for z in (0.405, 0.435):
            for sgn in (1, -1):
                for k in range(3):
                    t = lerp(0.36, -0.36, (k + 0.5) / 3)
                    hx, yf, yb = tprof(z)
                    x, y = se_pt(t, hx, yf, yb, off=0.0115)
                    tang = V((-math.sin(t) * sgn, math.cos(t), 0))
                    b = rbox((0.040, 0.003, 0.013))
                    xform(b, basis(V((x * sgn, y, z)), tang, V((x * sgn, y, 0))))
                    merge_bm(mbm, b, 0)
        finish("uni.molle_sides", mbm, ["M_strap_tan"])
    # vest shoulder straps (over the shoulders, front plate top -> back plate top)
    for sgn in (1, -1):
        x = 0.088 * sgn
        path = []; nrm = []
        C = V((x, 0.0, 0.47))
        steps = 14 if LOD == 0 else 6
        for k in range(steps + 1):
            phi = lerp(-0.02, PI + 0.02, k / steps)
            p, nn = s_hit(C, V((0, math.cos(phi), math.sin(phi))))
            zf = p.z
            on_plate = 1.0 - smooth01((zf - 0.535) / 0.03)
            off = lerp(0.003, 0.021, on_plate)
            path.append(p + nn * off); nrm.append(nn)
        path = smooth_path(path, 2)
        if LOD == 1:
            continue
        bm = ribbon(path, nrm, 0.048, 0.012, flat=False)
        finish(f"uni.vest_strap_{'R' if sgn > 0 else 'L'}", bm, ["M_vest_tan"], uv="own", sharp=50)
    if LOD == 1:
        # mag pouch block + radio
        p = V((0.0, surf_y(0.0, 0.405) + 0.020, 0.405))
        pouch("uni.mag_pouches", p, V((0, 1, 0)), 0.19, 0.030, 0.075)
        rp = V((-0.172, -0.070, 0.43))
        bm = rbox((0.030, 0.048, 0.095))
        xform(bm, Matrix.Translation(rp + V((-0.016, 0, 0))))
        finish("uni.radio", bm, ["M_vest_tan"])
        return
    # triple mag pouch (front, lower plate)
    for i, x in enumerate((-0.066, 0.0, 0.066)):
        z = 0.408
        y = surf_y(x, z) + 0.021
        nrm = V((x * 0.9, 0.115, 0)).normalized()
        pouch(f"uni.mag_pouch_{i}", V((x, y, z)), nrm, 0.058, 0.030, 0.078)
    # admin pouch with emblem patch (upper chest)
    x, z = 0.0, 0.486
    y = surf_y(x, z) + 0.021
    pouch("uni.admin_pouch", V((x, y, z)), V((0, 1, 0)), 0.092, 0.016, 0.050, flap=False, snap=False)
    bm = rbox((0.060, 0.003, 0.026), bevel=0.0012, segs=1)
    xform(bm, Matrix.Translation(V((0, y + 0.018, z + 0.006))))
    finish("uni.name_tape", bm, ["M_jacket_blue"])
    bm = star_bm(0.0095, 0.004, 0.0015)
    xform(bm, Matrix.Translation(V((-0.020, y + 0.0195, z + 0.006))))
    finish("uni.chest_star", bm, ["M_emblem"], sharp=30)
    # radio pouch + radio on left side, antenna up behind left shoulder
    rp = V((-0.176, -0.068, 0.432))
    pouch("uni.radio_pouch", rp + V((0.0, 0, 0)), V((-1, -0.25, 0)), 0.050, 0.030, 0.080, flap=False, snap=False,
          cuts=(1, 0, 1))
    nrad = V((-1, -0.25, 0)).normalized()
    cR = rp + nrad * 0.015
    bm = rbox((0.030, 0.042, 0.050), bevel=0.004, segs=1)
    xform(bm, Matrix.Translation(cR + V((0, 0, 0.060))))
    finish("uni.radio_body", bm, ["M_rubber_dark"])
    for dx, dy, r, h in ((0.0, -0.010, 0.0065, 0.012), (0.0, 0.010, 0.0045, 0.008)):
        bm = cyl(r, h, n=8)
        xform(bm, Matrix.Translation(cR + V((dx, dy, 0.085 + h / 2))))
        finish(f"uni.radio_knob_{int(r*10000)}", bm, ["M_metal_bright" if r < 0.005 else "M_rubber_dark"])
    # antenna: flexible whip, slightly curved back
    base = cR + V((0.0, -0.010, 0.091))
    pts = [base + V((0.006 * t * t, -0.035 * t * t, 0.27 * t)) for t in [k / 6 for k in range(7)]]
    rings = []
    T, N, B = tube_frames(pts)
    for i, p in enumerate(pts):
        r = lerp(0.0085, 0.0055, i / 6)
        rings.append([p + (N[i] * math.cos(a) + B[i] * math.sin(a)) * r for a in [2 * PI * k / 5 for k in range(5)]])
    bm = loft(rings)
    finish("uni.radio_antenna", bm, ["M_rubber_dark"], uv="own")
    bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=6, v_segments=4, radius=0.0085)
    xform(bm, Matrix.Translation(pts[-1]))
    finish("uni.antenna_tip", bm, ["M_rubber_dark"])
    # PTT cable from radio to left shoulder strap + PTT handset on strap
    ptt = V((-0.092, surf_y(-0.092, 0.535) + 0.034, 0.535))
    cpts = [cR + V((0.0, 0.016, 0.075)), cR + V((0.02, 0.06, 0.13)), V((-0.15, 0.06, 0.585)),
            V((-0.12, 0.09, 0.575)), ptt + V((0, 0, 0.01))]
    cpts = resample(smooth_path(resample(cpts, 12), 3), 10)
    T, N, B = tube_frames(cpts)
    rings = [[p + (N[i] * math.cos(a) + B[i] * math.sin(a)) * 0.0045 for a in [2 * PI * k / 4 for k in range(4)]]
             for i, p in enumerate(cpts)]
    bm = loft(rings)
    finish("uni.ptt_cable", bm, ["M_rubber_dark"], uv="own")
    bm = rbox((0.030, 0.016, 0.040), bevel=0.005, segs=1)
    xform(bm, Matrix.Translation(ptt))
    finish("uni.ptt_handset", bm, ["M_rubber_dark"])
    bm = cyl(0.008, 0.006, n=8)
    xform(bm, Matrix.Translation(ptt + V((0, 0.010, 0.0))) @ Matrix.Rotation(PI / 2, 4, "X"))
    finish("uni.ptt_button", bm, ["M_rubber_dark"])


# =============================================================== backpack
def backpack():
    c = A["backpack"]; w, d, h = A["backpack_size"]
    yf = -0.120                          # front face (against the back)
    cy = yf - d / 2
    z0 = c.z - h / 2; z1 = c.z + h / 2
    if LOD == 1:
        bm = rbox((w, d, h))
        xform(bm, Matrix.Translation(V((0, cy, c.z))))
        finish("uni.pack_body", bm, ["M_backpack_blue"])
        bm = rbox((w + 0.012, d + 0.014, 0.020))
        for v in bm.verts:
            if v.co.y < 0:
                pass
        xform(bm, Matrix.Translation(V((0, cy - 0.005, z1 + 0.004))))
        finish("uni.pack_flap", bm, ["M_backpack_blue"])
        bm = rbox((w + 0.010, 0.014, 0.12))
        xform(bm, Matrix.Translation(V((0, yf - d - 0.006, z1 - 0.055))))
        finish("uni.pack_flap_back", bm, ["M_backpack_blue"])
        bm = cyl(0.042, 0.30, n=8)
        xform(bm, Matrix.Translation(V((0, cy - 0.002, z1 + 0.050))) @ Matrix.Rotation(PI / 2, 4, "Y"))
        finish("uni.bedroll", bm, ["M_cloth_olive"])
        for sgn in (1, -1):
            pts = [V((0.095 * sgn, yf + 0.002, z1 - 0.01)), V((0.11 * sgn, -0.06, 0.625)),
                   V((0.112 * sgn, 0.05, 0.615)), V((0.116 * sgn, 0.135, 0.53)), V((0.12 * sgn, 0.14, 0.43))]
            pts = resample(smooth_path(resample(pts, 9), 1), 6)
            nrm = []
            for p in pts:
                _, nn = s_hit(V((p.x * 0.9, 0, 0.47)), (p - V((p.x * 0.9, 0, 0.47))))
                nrm.append(nn)
            bm = ribbon(pts, nrm, 0.050, 0.012, solid=True)
            finish(f"uni.pack_strap_{'R' if sgn > 0 else 'L'}", bm, ["M_strap_tan"], uv="own")
        return
    # ---- main body: bevelled box, back face slightly bulged, tapered top
    bm = rbox((w, d, h), bevel=0.026, segs=2, cuts=(3, 0, 2))
    for v in bm.verts:
        ty = (v.co.y + d / 2) / d  # 0 back .. 1 front
        tz = (v.co.z + h / 2) / h
        # bulge outward on the back face and sides
        if v.co.y < 0:
            v.co.y -= 0.010 * (1 - (2 * v.co.x / w) ** 2) * (1 - (2 * v.co.z / h) ** 4)
        v.co.x *= 1 - 0.05 * tz
    xform(bm, Matrix.Translation(V((0, cy, c.z))))
    finish("uni.pack_body", bm, ["M_backpack_blue"])
    # piping seams along the side panels (vertical) — thin rounded strips
    for sgn in ():
        for yy in (yf - 0.004, yf - d + 0.004):
            pts = [V((sgn * (w / 2 - 0.002) * (1 - 0.05 * ((z - z0) / h)), yy, z)) for z in
                   [z0 + 0.03 + k * (h - 0.06) / 8 for k in range(9)]]
            nrm = [V((sgn, 0, 0))] * len(pts)
            bm = ribbon(pts, nrm, 0.006, 0.003)
            finish(f"uni.pack_piping_{sgn}_{int(-yy*1000)}", bm, ["M_backpack_blue"], uv="own")
    # ---- lid flap: covers the top and hangs down the back
    fw = w + 0.016
    ftop = z1 + 0.006
    # profile of the flap in (y, z) — from front edge, over the top, down the back
    prof = [(yf + 0.004, ftop - 0.008), (yf - 0.010, ftop + 0.004), (cy, ftop + 0.012),
            (yf - d + 0.012, ftop + 0.004), (yf - d - 0.006, ftop - 0.020), (yf - d - 0.012, ftop - 0.060),
            (yf - d - 0.014, ftop - 0.110), (yf - d - 0.014, ftop - 0.135)]
    nx = 6
    outer = []; inner = []
    for pi_, (y, z) in enumerate(prof):
        ro = []; ri = []
        for ix in range(nx + 1):
            u = lerp(-1, 1, ix / nx)
            x = u * fw / 2
            # rounded bottom corners of the hanging part
            zz = z
            if pi_ >= len(prof) - 2:
                zz += 0.030 * (abs(u) ** 6)
            # back part is domed
            yy = y - (0.006 * (1 - u * u) if pi_ >= 4 else 0)
            ro.append(V((x, yy, zz)))
            # inner: offset towards the bag
            if pi_ <= 3:
                ri.append(V((x * 0.985, y + (0.0 if pi_ == 0 else 0.0), zz - 0.010)))
            else:
                ri.append(V((x * 0.985, yy + 0.010, zz)))
        outer.append(ro); inner.append(ri)
    bm = grid_slab(outer, inner)
    finish("uni.pack_lid", bm, ["M_backpack_blue"], sharp=60)
    bm = pipe(slab_edge_path(outer, inner, 0.0005), 0.0068, sides=5)
    finish("uni.pack_lid_piping", bm, ["M_strap_tan"], uv="own", sharp=70)
    # emblem star on the flap's back face (seen from behind)
    yb_flap = yf - d - 0.020
    bm = star_bm(0.030, 0.013, 0.003)
    xform(bm, basis(V((0, yb_flap + 0.0005, ftop - 0.085)), V((-1, 0, 0)), V((0, -1, 0))))
    finish("uni.pack_emblem", bm, ["M_emblem"], sharp=30)
    # emblem backing patch (round, olive) behind the star
    bm = cyl(0.040, 0.003, n=12)
    xform(bm, Matrix.Translation(V((0, yb_flap + 0.0015, ftop - 0.085))) @ Matrix.Rotation(PI / 2, 4, "X"))
    finish("uni.pack_patch", bm, ["M_cloth_olive"])
    # two lid straps with buckles (from flap down to the front pocket)
    for sgn in (1, -1):
        x = 0.078 * sgn
        pts = [V((x, -0.2745, ftop - 0.02)), V((x, -0.2755, 0.478)), V((x, -0.3035, 0.452)),
               V((x, -0.3045, 0.425)), V((x, -0.2975, 0.37)), V((x, -0.290, 0.346))]
        nrm = [V((0, -1, 0)), V((0, -1, 0)), V((0, -1, 0.5)).normalized(), V((0, -1, 0)), V((0, -1, -0.15)).normalized(),
               V((0, -1, -0.4)).normalized()]
        bm = ribbon(pts, nrm, 0.024, 0.004, solid=True)
        finish(f"uni.lid_strap_{'R' if sgn > 0 else 'L'}", bm, ["M_strap_tan"], uv="own")
        bm = rbox((0.032, 0.006, 0.026))
        f = min(bm.faces, key=lambda f: f.calc_center_median().y)
        bmesh.ops.inset_region(bm, faces=[f], thickness=0.005, depth=-0.002)
        xform(bm, Matrix.Translation(V((x, -0.3105, 0.432))))
        finish(f"uni.lid_buckle_{'R' if sgn > 0 else 'L'}", bm, ["M_rubber_dark"])
    # front (rear-facing) pocket
    pw, pdp, ph = 0.20, 0.040, 0.115
    pc = V((0, yf - d - 0.004, z0 + 0.010 + ph / 2))
    bm = rbox((pw, pdp, ph), bevel=0.014, segs=2, cuts=(2, 0, 0))
    for v in bm.verts:
        if v.co.y < 0:
            v.co.y -= 0.005 * (1 - (2 * v.co.x / pw) ** 2)
    xform(bm, Matrix.Translation(pc + V((0, -pdp / 2 + 0.006, 0))))
    finish("uni.pack_pocket", bm, ["M_backpack_blue"])
    bm = rbox((pw + 0.006, 0.010, 0.040), bevel=0.004, segs=1, cuts=(2, 0, 0))
    for v in bm.verts:
        v.co.y -= 0.004 * (1 - (2 * v.co.x / pw) ** 2)
        if v.co.z > 0.012:
            v.co.y += (v.co.z - 0.012) * 0.8
    xform(bm, Matrix.Translation(pc + V((0, -pdp + 0.002, ph / 2 - 0.014))))
    finish("uni.pack_pocket_flap", bm, ["M_backpack_blue"])
    # MOLLE rows on pocket
    mbm = bmesh.new()
    for z in (pc.z - 0.030, pc.z - 0.008):
        for k in range(3):
            x = -0.06 + k * 0.06
            b = rbox((0.044, 0.003, 0.013))
            xform(b, Matrix.Translation(V((x, yf - d - 0.040 - 0.0045 * (1 - (x / 0.1) ** 2), z))))
            merge_bm(mbm, b, 0)
    finish("uni.pack_molle", mbm, ["M_strap_tan"])
    # side bottle pockets + compression straps
    for sgn in (1, -1):
        bm = rbox((0.034, 0.090, 0.120), bevel=0.012, segs=1, cuts=(0, 1, 0))
        for v in bm.verts:
            if v.co.x * 1 > 0:
                v.co.x += 0.004 * (1 - (2 * v.co.y / 0.09) ** 2)
            v.co.x *= sgn
        xform(bm, Matrix.Translation(V((sgn * (w / 2 + 0.008), cy - 0.004, z0 + 0.075))))
        finish(f"uni.pack_side_pocket_{'R' if sgn > 0 else 'L'}", bm, ["M_backpack_blue"])
        # compression straps (horizontal) around the side
        for zz in (z0 + 0.200,):
            xs = sgn * (w / 2 * (1 - 0.05 * (zz - z0) / h) + 0.002)
            pts = [V((xs - sgn * 0.010, yf - 0.006, zz)), V((xs, yf - 0.018, zz)), V((xs + sgn * 0.002, cy, zz)),
                   V((xs, yf - d + 0.016, zz)), V((xs - sgn * 0.014, yf - d - 0.004, zz))]
            pts = resample(smooth_path(resample(pts, 9), 1), 7)
            nrm = [(p - V((0, cy, zz))).normalized() for p in pts]
            bm = ribbon(pts, nrm, 0.018, 0.0035)
            finish(f"uni.compress_strap_{'R' if sgn > 0 else 'L'}_{int(zz*1000)}", bm, ["M_strap_tan"], uv="own")
            bm = rbox((0.005, 0.022, 0.024))
            xform(bm, Matrix.Translation(V((xs + sgn * 0.005, cy - 0.020, zz))))
            finish(f"uni.compress_buckle_{'R' if sgn > 0 else 'L'}_{int(zz*1000)}", bm, ["M_rubber_dark"])
    # carry handle on top (loop)
    pts = [V((-0.03, yf - 0.010, ftop + 0.004)), V((-0.026, yf - 0.012, ftop + 0.024)),
           V((0.0, yf - 0.012, ftop + 0.032)), V((0.026, yf - 0.012, ftop + 0.024)), V((0.03, yf - 0.010, ftop + 0.004))]
    pts = resample(smooth_path(resample(pts, 9), 1), 7)
    bm = ribbon(pts, [V((0, 0, 1)).lerp((p - V((0, p.y, ftop))).normalized(), 0.8).normalized() for p in pts],
                0.020, 0.005, solid=True)
    finish("uni.pack_handle", bm, ["M_strap_tan"], uv="own")
    # ---- bedroll on top of the lid, two straps
    br = 0.040; bl = 0.300
    bc = V((0, cy - 0.004, ftop + 0.012 + br * 0.92))
    nseg = 12
    rings = []
    xs = [-bl / 2, -bl / 2 + 0.008, -bl / 2 + 0.04, 0.0, bl / 2 - 0.04, bl / 2 - 0.008, bl / 2]
    for x in xs:
        endk = 1.0 - (0.12 if abs(x) > bl / 2 - 0.001 else 0.0)
        ring = []
        for k in range(nseg):
            a = 2 * PI * k / nseg - PI / 2
            r = br * endk * (1 + 0.035 * math.sin(a * 3 + x * 30)) * (1 - 0.06 * (abs(x) / (bl / 2)) ** 6)
            ring.append(bc + V((x, r * math.cos(a), r * math.sin(a) * 0.92)))
        rings.append(ring)
    bm = loft(rings, cap0=True, cap1=True)
    finish("uni.bedroll", bm, ["M_cloth_olive"], uv="own")
    # spiral end detail: a raised spiral groove on each end cap
    for sgn in (1, -1):
        pts = []
        for k in range(26):
            t = k / 25
            a = t * 2.5 * 2 * PI
            r = 0.006 + t * (br * 0.84 - 0.006)
            pts.append(bc + V((sgn * (bl / 2 - 0.0005), r * math.cos(a), r * math.sin(a) * 0.92)))
        nrm = [V((sgn, 0, 0))] * len(pts)
        bm = ribbon(pts, nrm, 0.0040, 0.0012, flat=True)
        finish(f"uni.bedroll_spiral_{'R' if sgn > 0 else 'L'}", bm, ["M_cloth_olive"], uv="own")
    for sgn in (1, -1):
        x = 0.095 * sgn
        ring = []; nn = []
        for k in range(nseg + 1):
            a = 2 * PI * k / nseg - PI / 2
            d2 = V((0, math.cos(a), math.sin(a) * 0.92))
            ring.append(bc + V((x, 0, 0)) + d2 * (br * 1.04 + 0.0008)); nn.append(d2)
        bm = ribbon(ring, nn, 0.018, 0.0035, cap=False)
        finish(f"uni.bedroll_strap_{'R' if sgn > 0 else 'L'}", bm, ["M_strap_tan"], uv="own")
        bm = rbox((0.022, 0.006, 0.018))
        xform(bm, Matrix.Translation(bc + V((x, -br - 0.003, 0.0))))
        finish(f"uni.bedroll_buckle_{'R' if sgn > 0 else 'L'}", bm, ["M_metal_bright"])
    # ---- shoulder straps: from pack top, over shoulder, down the chest, buckle, webbing back to pack bottom
    for sgn in (1, -1):
        x = 0.104 * sgn
        C = V((x * 0.95, 0.0, 0.47))
        path = []; nrm = []
        steps = 14
        for k in range(steps + 1):
            phi = lerp(-0.42, PI - 0.55, k / steps)
            p, nn = s_hit(C, V((0, math.cos(phi), math.sin(phi))))
            on_plate = 1.0 - smooth01((p.z - 0.535) / 0.03)
            on_strap = 1.0 - smooth01((abs(p.x) - 0.105) / 0.02)
            off = max(lerp(0.003, 0.022, on_plate) + 0.013 * on_strap, 0.024 if p.y > 0 and p.z < 0.56 else 0)
            path.append(p + nn * off); nrm.append(nn)
        path.reverse(); nrm.reverse()
        # start inside the pack top
        start = V((0.085 * sgn, yf - 0.020, z1 - 0.025))
        path = [start, start.lerp(path[0], 0.5)] + path
        nrm = [V((0, 1, 0.6)).normalized()] * 2 + nrm
        path = smooth_path(path, 2)
        bm = ribbon(path, nrm, 0.050, 0.013, solid=True)
        finish(f"uni.pack_strap_{'R' if sgn > 0 else 'L'}", bm, ["M_strap_tan"], uv="own", sharp=55)
        # padding stitch lines: 3 thin cross bars on the strap over the shoulder
        end = path[-1]; endn = nrm[-1]
        # ladder lock buckle at strap end
        bm = rbox((0.050, 0.006, 0.020))
        f = max(bm.faces, key=lambda f: f.calc_center_median().y)
        bmesh.ops.inset_region(bm, faces=[f], thickness=0.005, depth=-0.002)
        xform(bm, basis(end + endn * 0.004 + V((0, 0, -0.006)), V((1, 0, 0)), endn))
        finish(f"uni.pack_strap_buckle_{'R' if sgn > 0 else 'L'}", bm, ["M_rubber_dark"])
        # thin webbing from buckle round the side to the pack bottom corner
        wp = []; wn = []
        ks = 9
        for k in range(ks + 1):
            t = k / ks
            ang = lerp(math.atan2(end.y, abs(end.x)), -1.25, t)
            z = lerp(end.z - 0.018, 0.372, smooth01(t))
            p, nn = s_hit(V((0, 0, z)), V((math.cos(ang) * sgn, math.sin(ang), 0)))
            off = 0.026 if p.y > -0.06 else lerp(0.026, 0.006, smooth01((-0.06 - p.y) / 0.04))
            wp.append(p + nn * off); wn.append(nn)
        wp.append(V((0.120 * sgn, yf - 0.012, z0 + 0.03)))
        wn.append(V((sgn, 0, 0)))
        wp = smooth_path(wp, 1)
        bm = ribbon(wp, wn, 0.024, 0.004, solid=True)
        finish(f"uni.pack_webbing_{'R' if sgn > 0 else 'L'}", bm, ["M_strap_tan"], uv="own")
    # sternum strap + buckle
    z = 0.524
    pts = []; nn = []
    for k in range(5):
        x = lerp(-0.112, 0.112, k / 4)
        y = surf_y(x, z) + 0.021 + 0.028
        pts.append(V((x, y, z))); nn.append(V((x * 2, 0.115, 0)).normalized())
    bm = ribbon(pts, nn, 0.016, 0.004)
    finish("uni.sternum_strap", bm, ["M_strap_tan"], uv="own")
    bm = rbox((0.040, 0.010, 0.022), bevel=0.003, segs=1)
    f = max(bm.faces, key=lambda f: f.calc_center_median().y)
    bmesh.ops.inset_region(bm, faces=[f], thickness=0.004, depth=-0.002)
    xform(bm, Matrix.Translation(V((0.0, surf_y(0, z) + 0.021 + 0.034, z))))
    finish("uni.sternum_buckle", bm, ["M_rubber_dark"])


# =============================================================== belt kit
def belt_kit():
    zc = sum(BELT_Z) / 2
    if LOD == 1:
        return
    # right hip: double pistol mag pouch
    for i, t in enumerate((0.42,)):
        x, y = se_pt(t, 0.137, 0.098, 0.100, n=2.5, off=0.010)
        nrm = V((x, y, 0)).normalized()
        pouch(f"uni.belt_pouch_R{i}", V((x, y, zc - 0.012)), nrm, 0.036, 0.022, 0.066, cuts=(0, 0, 0))
    # left hip: IFAK/utility pouch (bigger), olive flap
    t = PI - 0.40
    x, y = se_pt(t, 0.137, 0.098, 0.100, n=2.5, off=0.010)
    pouch("uni.belt_pouch_L", V((x, y, zc - 0.018)), V((x, y, 0)).normalized(), 0.070, 0.034, 0.072,
          flap_mat="M_cloth_olive")
    # canteen on back right (below the pack)
    t = -PI / 2 + 0.62
    x, y = se_pt(t, 0.137, 0.098, 0.100, n=2.5, off=0.010)
    nrm = V((x, y, 0)).normalized()
    cc = V((x, y, zc - 0.028)) + nrm * 0.028
    rings = []
    for z, r in ((-0.040, 0.020), (-0.036, 0.026), (0.020, 0.027), (0.030, 0.024), (0.036, 0.016)):
        ring = []
        for k in range(12):
            a = 2 * PI * k / 12
            ring.append(cc + V((r * math.cos(a) * 1.15, r * math.sin(a) * 0.85, z)))
        rings.append(ring)
    bm = loft(rings)
    finish("uni.canteen_cover", bm, ["M_cloth_olive"], uv="own")
    bm = cyl(0.010, 0.014, n=8)
    xform(bm, Matrix.Translation(cc + V((0, 0, 0.042))))
    finish("uni.canteen_cap", bm, ["M_rubber_dark"])
    # dump pouch rolled on back left
    t = -PI / 2 - 0.62
    x, y = se_pt(t, 0.137, 0.098, 0.100, n=2.5, off=0.010)
    nrm = V((x, y, 0)).normalized()
    bm = cyl(0.020, 0.075, n=10, bevel=0.004)
    xform(bm, basis(V((x, y, zc - 0.010)) + nrm * 0.021, V((-nrm.y, nrm.x, 0)), V((0, 0, 1))) @ Matrix.Rotation(PI / 2, 4, "Y"))
    finish("uni.dump_pouch", bm, ["M_vest_tan"])


# =============================================================== build
def build(lod):
    global LOD
    LOD = lod
    torso(); collar()
    for s in ("R", "L"):
        sleeve(s); shoulder_pad(s); leg(s)
    pants_seat(); belt(); belt_kit(); vest(); backpack()


if __name__ == "__main__":
    reset()
    build(0)
    build(1)
    save_part("uniform")
    if "--no-preview" not in sys.argv:
        views = sys.argv[sys.argv.index("--views") + 1].split(",") if "--views" in sys.argv else ["back34", "front34", "side"]
        CUSTOM = {"armR": (V((1.1, 0.9, 0.7)), V((0.15, 0.08, 0.45))), "boots": (V((0.6, 1.0, 0.35)), V((0, 0.03, 0.1))),
                  "packback": (V((0.5, -1.3, 1.0)), V((0, -0.15, 0.48))), "radio": (V((-1.2, -0.4, 0.8)), V((-0.15, -0.05, 0.5))),
                  "chest": (V((0.25, 1.2, 0.6)), V((0, 0.1, 0.45)))}
        std = [v for v in views if v not in CUSTOM]
        if std:
            preview("part_uniform", views=std, lod=0)
        for v in views:
            if v in CUSTOM:
                preview("part_uniform_" + v, views=[CUSTOM[v]], lod=0)
        if "--lo" in sys.argv:
            preview("part_uniform_lo", views=["back34", "front34"], lod=1)
