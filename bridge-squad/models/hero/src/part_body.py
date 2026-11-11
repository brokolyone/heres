"""Hero soldier — BODY & FACE part (owner: Body & face artist).

Builds: head (skull with sculpted nose/cheeks/chin/brow ridge/eye sockets), hair shell (nape + sideburns),
eyes (eyeball with iris / limbal ring / pupil, highlights, upper lid with lash line, lower lid),
brows, mouth, ears, neck, both gloved hands wrapped round the rifle grips (+ leather cuffs, knuckle
pads), and LOD1 versions of all of it.
    cd models/hero && python3 src/part_body.py
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hero_common import *
import bmesh
from mathutils import Vector as V, Matrix
from mathutils.bvhtree import BVHTree

OWNER = "body"
pi = math.pi
rad = math.radians

# ------------------------------------------------------------------ rifle interface (PLAN §3 + NOTES)
GRIP_C = V((0.085, 0.200, 0.395))          # pistol grip centre line passes here
GRIP_DIR = V((0.0, -0.30, -1.0)).normalized()   # grip axis, pointing down (raked back)
GRIP_R = 0.018                             # effective grip radius (fingers wrap at this)
HG_C = V((A["rifle_x"], A["hand_L"].y, A["rifle_z"]))   # handguard axis point under the left hand
HG_R = 0.026                               # effective handguard radius

# ------------------------------------------------------------------ generic mesh helpers

def new_obj(name, verts, faces, mats, fmat=None, smooth=True, recalc="closed", ref=None):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], faces)
    me.update()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    for m in mats:
        me.materials.append(mat(m))
    if fmat:
        for p, i in zip(me.polygons, fmat):
            p.material_index = i
    bm = bmesh.new(); bm.from_mesh(me)
    if recalc == "closed":
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    elif recalc == "ref":       # open shell: normals point away from ref point
        for f in bm.faces:
            if f.normal.dot(f.calc_center_median() - ref) < 0:
                f.normal_flip()
    bm.to_mesh(me); bm.free()
    for p in me.polygons:
        p.use_smooth = smooth
    return ob


def sweep(pts, ups, ra, rb, segs=8, caps=(True, True), cap_rings=2, cap_len=None):
    """Tube along pts. ups: per-point up vectors (rb is measured along up, ra along side=t x up).
    ra/rb: per-point radii (lists) or scalars. Returns verts, faces (closed if both caps)."""
    n = len(pts)
    P = [V(p) for p in pts]
    if not isinstance(ups, (list, tuple)) or isinstance(ups[0], (int, float)):
        ups = [V(ups)] * n
    ra = ra if isinstance(ra, (list, tuple)) else [ra] * n
    rb = rb if isinstance(rb, (list, tuple)) else [rb] * n
    T = []
    for i in range(n):
        t = (P[min(i + 1, n - 1)] - P[max(i - 1, 0)]).normalized()
        T.append(t)
    verts, faces, rings = [], [], []

    def ring(c, t, up, a, b):
        side = t.cross(V(up)).normalized()
        u2 = side.cross(t).normalized()
        idx = []
        for k in range(segs):
            ang = 2 * pi * k / segs
            verts.append(c + side * (a * math.cos(ang)) + u2 * (b * math.sin(ang)))
            idx.append(len(verts) - 1)
        return idx

    def cap(i, sgn):
        out = []
        cl = cap_len if cap_len is not None else (ra[i] + rb[i]) * 0.5
        for j in range(1, cap_rings + 1):
            ph = (pi / 2) * j / (cap_rings + 1)
            out.append(ring(P[i] + T[i] * (sgn * cl * math.sin(ph)), T[i], ups[i], ra[i] * math.cos(ph), rb[i] * math.cos(ph)))
        verts.append(P[i] + T[i] * (sgn * cl)); pole = len(verts) - 1
        return out, pole

    seq = []
    pole0 = pole1 = None
    if caps[0]:
        cr, pole0 = cap(0, -1)
        seq += cr[::-1]
    for i in range(n):
        seq.append(ring(P[i], T[i], ups[i], ra[i], rb[i]))
    if caps[1]:
        cr, pole1 = cap(n - 1, +1)
        seq += cr
    for r0, r1 in zip(seq[:-1], seq[1:]):
        for k in range(segs):
            k2 = (k + 1) % segs
            faces.append((r0[k], r0[k2], r1[k2], r1[k]))
    if pole0 is not None:
        r = seq[0]
        for k in range(segs):
            faces.append((pole0, r[(k + 1) % segs], r[k]))
    if pole1 is not None:
        r = seq[-1]
        for k in range(segs):
            faces.append((pole1, r[k], r[(k + 1) % segs]))
    return verts, faces


def polar_sphere(pole, rings_deg, segs, xform, last_pole=True):
    """Sphere-ish surface with rings at given polar angles (deg) from `pole` (unit dir).
    xform(unit_dir) -> world point. rings_deg[0] must be 0 (pole vertex). If last value is 180 and
    last_pole, closes with a pole. Returns verts, faces, ring_index_per_face (band index)."""
    pole = V(pole).normalized()
    e1 = pole.orthogonal().normalized()
    e2 = pole.cross(e1).normalized()
    verts, faces, band = [], [], []
    verts.append(xform(pole))
    rings = []
    inner = [a for a in rings_deg[1:]]
    closed = last_pole and abs(rings_deg[-1] - 180) < 1e-6
    if closed:
        inner = inner[:-1]
    for a in inner:
        t = rad(a)
        idx = []
        for k in range(segs):
            ph = 2 * pi * k / segs
            d = pole * math.cos(t) + (e1 * math.cos(ph) + e2 * math.sin(ph)) * math.sin(t)
            verts.append(xform(d)); idx.append(len(verts) - 1)
        rings.append(idx)
    r = rings[0]
    for k in range(segs):
        faces.append((0, r[k], r[(k + 1) % segs])); band.append(0)
    for bi, (r0, r1) in enumerate(zip(rings[:-1], rings[1:])):
        for k in range(segs):
            k2 = (k + 1) % segs
            faces.append((r0[k], r1[k], r1[k2], r0[k2])); band.append(bi + 1)
    if closed:
        verts.append(xform(-pole)); p1 = len(verts) - 1
        r = rings[-1]
        for k in range(segs):
            faces.append((p1, r[(k + 1) % segs], r[k])); band.append(len(rings))
    return verts, faces, band, (e1, e2)


def rounded_box(name, center, axes, dims, matname, bevel=0.006, segs=2):
    """Box with bevelled edges; axes = (ax, ay, az) unit vectors, dims full sizes along them."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(ob)
    me.materials.append(mat(matname))
    M = Matrix((axes[0] * dims[0], axes[1] * dims[1], axes[2] * dims[2])).transposed().to_4x4()
    M.translation = center
    me.transform(M)
    md = ob.modifiers.new("bev", "BEVEL"); md.width = bevel; md.segments = segs; md.limit_method = "NONE"
    md.harden_normals = False
    for p in me.polygons:
        p.use_smooth = True
    apply_all(ob)
    for p in ob.data.polygons:
        p.use_smooth = True
    return ob


def finish(ob, lod, target="body"):
    tag(ob, target, lod, OWNER)
    uv_world(ob)
    return ob


def gauss(p, c, s):
    return math.exp(-((p - c).length_squared) / (2 * s * s))


# ------------------------------------------------------------------ HEAD
HC = A["head"]
HR = A["head_r"]
NOSE_TIP = V((0.0, 0.160, 0.729))

# frontal face features: (x, z) centre, sigma, amplitude along the radial normal (only front-facing)
FACE_BUMPS = [
    ((0.0, 0.729), 0.0105, 0.0200),     # button nose ball
    ((0.0, 0.737), 0.0060, 0.0030),     # nose tip roundness (upturn)
    ((0.0, 0.752), 0.0075, 0.0045),     # nose bridge
    ((0.0150, 0.722), 0.0062, 0.0050),  # nostril wings
    ((-0.0150, 0.722), 0.0062, 0.0050),
    ((0.0, 0.713), 0.0045, -0.0022),    # under-nose notch
    ((0.078, 0.700), 0.026, 0.0080),    # chubby cheeks
    ((-0.078, 0.700), 0.026, 0.0080),
    ((0.050, 0.766), 0.018, -0.0095),   # eye sockets
    ((-0.050, 0.766), 0.018, -0.0095),
    ((0.052, 0.806), 0.015, 0.0045),    # brow ridge
    ((-0.052, 0.806), 0.015, 0.0045),
    ((0.0, 0.672), 0.0080, 0.0030),     # lower lip
    ((0.0, 0.661), 0.0060, -0.0022),    # crease under lip
    ((0.0, 0.645), 0.0150, 0.0060),     # chin ball
    ((0.034, 0.690), 0.0055, -0.0020),  # mouth corner dimples
    ((-0.034, 0.690), 0.0055, -0.0020),
]
BUMPS = [  # 3D: (centre, sigma, amplitude)
    (V((0.098, 0.050, 0.668)), 0.022, 0.0060),   # jaw corners
    (V((-0.098, 0.050, 0.668)), 0.022, 0.0060),
]


def head_shape(d, bumps=True):
    """unit direction (head-normalised space) -> world position on sculpted head."""
    x, y, z = d.x, d.y, d.z
    s = max(0.0, -z)
    x *= 1.0 - 0.17 * s ** 1.4                     # jaw taper
    if y < 0:
        y *= 1.0 - 0.28 * s ** 1.4                 # back of jaw blends into neck
    if y > 0:
        y *= 1.0 - 0.07 * (max(0.0, y) ** 4)       # slightly flatter face plane
    if z < -0.70 and y > -0.5:                     # flatter jaw underside -> chin/jaw plane
        z = -0.70 - (-z - 0.70) * 0.75
    if z < 0 and y > 0:                            # lower face/chin comes forward (less egg-like)
        y += 0.20 * (s ** 1.2) * (y ** 2)
    if z > 0:
        z *= 1.0 + 0.04 * (z ** 2)                 # rounder cranium
    if y < 0 and z > 0:
        y *= 1.0 + 0.06 * z                        # occipital bulge
    q = V((HC.x + x * HR.x, HC.y + y * HR.y, HC.z + z * HR.z))
    if bumps:
        n = (q - HC).normalized()
        off = 0.0
        for c, sg, amp in BUMPS:
            off += amp * gauss(q, c, sg)
        fw = max(0.0, min(1.0, (n.y - 0.25) / 0.35))
        if fw > 0:
            for (cx, cz), sg, amp in FACE_BUMPS:
                off += fw * amp * math.exp(-((q.x - cx) ** 2 + (q.z - cz) ** 2) / (2 * sg * sg))
        q = q + n * off
    return q


def build_head(lod):
    pole = V(((NOSE_TIP - HC).x / HR.x, (NOSE_TIP - HC).y / HR.y, (NOSE_TIP - HC).z / HR.z)).normalized()
    if lod == 0:
        rings = [0, 2.5, 5, 7.5, 10, 13, 16, 19.5, 23, 27, 31, 36, 41, 47, 54, 62, 71, 81, 92, 105, 120, 140, 160, 180]
        segs = 28
    else:
        rings = [0, 14, 30, 50, 72, 98, 125, 152, 180]
        segs = 12
    verts, faces, band, _ = polar_sphere(pole, rings, segs, lambda d: head_shape(d, bumps=True))
    ob = new_obj("body.head" + (".lo" if lod else ""), verts, faces, ["M_skin"])
    return ob


def bvh_of(ob):
    bm = bmesh.new(); bm.from_mesh(ob.data)
    bm.transform(ob.matrix_world)
    t = BVHTree.FromBMesh(bm)
    return t, bm


def surf_front(tree, x, z, y0=0.5):
    hit = tree.ray_cast(V((x, y0, z)), V((0, -1, 0)))
    return hit[0], hit[1]


# ---------------------------- hair shell
HAIRLINE = [(0.0, 0.852), (0.90, 0.852), (1.06, 0.770), (1.13, 0.738), (1.30, 0.733), (1.40, 0.756),
            (1.80, 0.762), (2.05, 0.722), (2.5, 0.703), (pi, 0.698)]


def zline(p):
    psi = abs(math.atan2(p.x, p.y - HC.y))
    for (a0, z0), (a1, z1) in zip(HAIRLINE[:-1], HAIRLINE[1:]):
        if psi <= a1:
            t = (psi - a0) / (a1 - a0)
            t = t * t * (3 - 2 * t)
            return z0 + (z1 - z0) * t
    return HAIRLINE[-1][1]


def cut_field(me, fn, snap=0.12):
    """Split mesh `me` along the zero contour of scalar field fn(co). Returns nothing."""
    bm = bmesh.new(); bm.from_mesh(me)
    vals = {v: fn(v.co) for v in bm.verts}
    zero = set()
    for e in list(bm.edges):
        a, b = e.verts
        ha, hb = vals[a], vals[b]
        if a in zero or b in zero or (ha < 0) == (hb < 0):
            continue
        t = ha / (ha - hb)
        if t < snap:
            a.co = a.co.lerp(b.co, t); vals[a] = 0.0; zero.add(a); continue
        if t > 1 - snap:
            b.co = a.co.lerp(b.co, t); vals[b] = 0.0; zero.add(b); continue
        ne, nv = bmesh.utils.edge_split(e, a, t)
        vals[nv] = 0.0; zero.add(nv)
    for f in list(bm.faces):
        vs = [v for v in f.verts if v in zero]
        if len(vs) == 2:
            nb = [x for x in f.verts]
            i, j = nb.index(vs[0]), nb.index(vs[1])
            if abs(i - j) not in (1, len(nb) - 1):
                bmesh.ops.connect_verts(bm, verts=vs)
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4])
    bm.to_mesh(me); bm.free()


def hair_h(co):
    return co.z - zline(co)


def build_hair(head):
    cut_field(head.data, hair_h)
    for p in head.data.polygons:
        p.use_smooth = True
    me = head.data
    bm = bmesh.new(); bm.from_mesh(me)
    bm.normal_update()
    sel = [f for f in bm.faces if min(hair_h(v.co) for v in f.verts) > -1e-6]
    vmap, verts, nrms, faces, bnd = {}, [], [], [], set()
    for f in sel:
        idx = []
        for v in f.verts:
            if v.index not in vmap:
                vmap[v.index] = len(verts); verts.append(v.co.copy()); nrms.append(v.normal.copy())
                if abs(hair_h(v.co)) < 1e-6:
                    bnd.add(vmap[v.index])
            idx.append(vmap[v.index])
        faces.append(tuple(idx))
    bm.free()
    out = [p + n * (-0.0002 if i in bnd else 0.0022) for i, (p, n) in enumerate(zip(verts, nrms))]
    ob = new_obj("body.hair", out, faces, ["M_hair"], recalc="ref", ref=HC)
    return ob


# ---------------------------- eyes
EYE_R = V((0.0290, 0.0200, 0.0345))     # eyeball radii (side, depth, height): tall cartoon eyes


def eye_frame(side):
    f = V((0.10 * side, 1.0, 0.0)).normalized()     # eyes sit on a curved face: slight outward yaw
    up = V((0, 0, 1))
    sx = up.cross(f).normalized() * -1               # local +x = character's right
    return f, up, sx


def build_eye(tree, side, lod_tag=""):
    ax = A["eye_R"] if side > 0 else A["eye_L"]
    S, _ = surf_front(tree, ax.x, ax.z)
    f, up, sx = eye_frame(side)
    C = V((ax.x, S.y + 0.0040 - EYE_R.y, ax.z))      # eye front pokes 4 mm out of the socket
    # pupils look straight ahead (+Y) and very slightly down/inward toward the gun = focused
    look = V((-0.04 * side, 1.0, -0.03)).normalized()

    def ell(d, k=1.0):
        # d in world-aligned unit dir; scale by eye radii in eye frame
        lx, ly, lz = d.dot(sx), d.dot(f), d.dot(up)
        return C + (sx * (lx * EYE_R.x) + f * (ly * EYE_R.y) + up * (lz * EYE_R.z)) * k

    rings = [0, 8, 16, 26, 35, 39, 52, 72, 100]
    verts, faces, band, _ = polar_sphere(look, rings, 16, ell, last_pole=False)
    # materials: 0 white 1 iris 2 pupil
    fm = []
    for b in band:
        a_out = rings[b + 1] if b + 1 < len(rings) else 180
        if a_out <= 16:
            fm.append(2)
        elif a_out <= 35:
            fm.append(1)
        elif a_out <= 39:
            fm.append(2)       # dark limbal ring around the iris
        else:
            fm.append(0)
    # iris inner bands: ring 15-19 slightly darker? (keep iris) -> handled by material
    nm = "body.eye_" + ("R" if side > 0 else "L")
    eye = new_obj(nm, verts, faces, ["M_eye_white", "M_eye_iris", "M_eye_pupil"], fm, recalc="ref", ref=C)

    # highlights (same screen side on both eyes: character's right/up)
    objs = [eye]
    for (pol, az, r, dz) in ((21, 40, 0.0062, 0.0), (24, 220, 0.0030, 0.0)):
        t = rad(pol); ph = rad(az)
        e1 = look.orthogonal().normalized()
        # build a stable frame: e1 = sideways(+x), e2 = up
        e1 = sx - look * sx.dot(look); e1.normalize()
        e2 = look.cross(e1).normalized() * -1 if look.cross(e1).z < 0 else look.cross(e1).normalized()
        d = look * math.cos(t) + (e1 * math.cos(ph) + e2 * math.sin(ph)) * math.sin(t)
        P = ell(d, 1.0)
        nrm = (P - C).normalized()
        hv, hf = sweep([P + nrm * 0.0006, P + nrm * 0.0011], nrm.orthogonal(), r, r * 1.15, segs=8,
                       caps=(False, True), cap_rings=1, cap_len=0.0007)
        # close the back with a fan (0.6 mm off the iris: no z-fight in the bake)
        hv.append(P + nrm * 0.0006); c0 = len(hv) - 1
        for k in range(8):
            hf.append((c0, (k + 1) % 8, k))
        objs.append(new_obj(nm + "_hl%d" % (len(objs)), hv, hf, ["M_eye_white"]))

    # upper lid: spherical cap around tilted axis, on an enlarged ellipsoid, rolled edge = lash line
    def lid(axis, beta, k_out, lash, nmx):
        axis = axis.normalized()
        rr = [0, 30, beta - 7, beta]
        vv, ff, bb, _ = polar_sphere(axis, rr, 16, lambda d: ell(d, k_out), last_pole=False)
        # roll the edge inward toward the eyeball: append one more ring at beta+3 deg on k=1.0
        e1 = axis.orthogonal().normalized(); e2 = axis.cross(e1).normalized()
        e1 = axis.orthogonal().normalized()
        # rebuild with polar_sphere's own frame for consistency
        pole = axis
        pe1 = pole.orthogonal().normalized(); pe2 = pole.cross(pe1).normalized()
        last = list(range(len(vv) - 16, len(vv)))
        newr = []
        t = rad(beta + 2.5)
        for kk in range(16):
            ph = 2 * pi * kk / 16
            d = pole * math.cos(t) + (pe1 * math.cos(ph) + pe2 * math.sin(ph)) * math.sin(t)
            vv.append(ell(d, 1.004)); newr.append(len(vv) - 1)
        for kk in range(16):
            k2 = (kk + 1) % 16
            ff.append((last[kk], newr[kk], newr[k2], last[k2])); bb.append(len(rr))
        fm2 = [1 if (lash and b >= len(rr) - 2) else 0 for b in bb]
        return new_obj(nmx, vv, ff, ["M_skin", "M_hair"], fm2, recalc="ref", ref=C)

    # inner corner lower = determined look. axis tilts toward the nose (-side)
    up_axis = V((-0.20 * side, 0.30, 1.0))
    objs.append(lid(up_axis, 50.0, 1.075, True, nm + "_lidU"))
    lo_axis = V((0.10 * side, 0.34, -1.0))
    objs.append(lid(lo_axis, 36.0, 1.06, False, nm + "_lidD"))
    return objs, C


# ---------------------------- brows / mouth (sweeps projected onto face)

def projected_path(tree, xz, lift):
    pts, nrms = [], []
    for x, z in xz:
        loc, nrm = surf_front(tree, x, z)
        pts.append(loc + nrm * lift); nrms.append(nrm)
    return pts, nrms


def build_brow(tree, side):
    xs = [0.016, 0.030, 0.048, 0.066, 0.080, 0.090]
    zs = [0.799, 0.806, 0.812, 0.814, 0.811, 0.805]
    xz = [(x * side, z) for x, z in zip(xs, zs)]
    pts, nrms = projected_path(tree, xz, 0.0030)
    h = [0.0078, 0.0080, 0.0074, 0.0062, 0.0048, 0.0032]   # half height (thick inner end, taper)
    th = [0.0042, 0.0045, 0.0042, 0.0038, 0.0032, 0.0024]
    v, f = sweep(pts, nrms, h, th, segs=8, cap_rings=1)
    return new_obj("body.brow_" + ("R" if side > 0 else "L"), v, f, ["M_hair"])


def build_mouth(tree):
    xs = [-0.031, -0.024, -0.014, -0.005, 0.005, 0.014, 0.024, 0.032]
    def zf(x):
        return 0.6835 + 5.5 * x * x + 0.05 * x + (0.0016 if x > 0.026 else 0.0)
    xz = [(x, zf(x)) for x in xs]
    pts, nrms = projected_path(tree, xz, 0.0002)
    h = [0.0012, 0.0019, 0.0025, 0.0028, 0.0028, 0.0025, 0.0019, 0.0013]
    th = [0.0016] * 8
    v, f = sweep(pts, nrms, h, th, segs=6, cap_rings=1)
    return new_obj("body.mouth", v, f, ["M_mouth"])


# ---------------------------- ears

def build_ear(side, lod):
    c = V((0.141 * side, 0.004, 0.764))
    n = V((side * 1.0, 0.30, 0.0)).normalized()      # cup faces outward & a bit forward
    upv = V((0, -0.22, 1.0)).normalized()            # top leans back
    w = upv.cross(n).normalized()
    if side < 0:
        w = -w
    R3 = (0.0125, 0.0255, 0.040)                     # thickness, width, height
    segs, rings = (14, [0, 15, 32, 50, 70, 95, 120, 145, 165, 180]) if lod == 0 else (6, [0, 60, 120, 180])

    def ear_pt(d):
        lx, ly, lz = d.x, d.y, d.z          # local: x=normal, y=width, z=height
        # cup: push the outer face inward inside an inner ellipse, leaving a rolled helix rim
        if lod == 0 and lx > 0:
            r2 = (ly / 0.80) ** 2 + (lz / 0.84) ** 2
            if r2 < 1.0:
                lx -= 1.25 * lx * (1 - r2) ** 1.3
            # small antihelix/tragus bump at the front-low part
            lx += 0.35 * math.exp(-((ly - 0.45) ** 2 + (lz + 0.15) ** 2) / 0.03) * max(lx, 0) * 0
        # earlobe: slightly fuller at the bottom, narrower top-front
        ly *= 1.0 + 0.10 * max(0.0, -lz)
        p = n * (lx * R3[0]) + w * (ly * R3[1]) + upv * (lz * R3[2])
        return c + p
    verts, faces, band, _ = polar_sphere(V((1, 0, 0)), rings, segs, ear_pt)
    return new_obj("body.ear_" + ("R" if side > 0 else "L") + (".lo" if lod else ""), verts, faces, ["M_skin"])


# ---------------------------- neck

def build_neck(lod):
    pts = [V((0, -0.014, 0.548)), V((0, -0.010, 0.590)), V((0, -0.004, 0.635)), V((0, 0.0, 0.675))]
    ra = [0.056, 0.0505, 0.048, 0.046]
    if lod == 0:
        v, f = sweep(pts, V((0, 1, 0)), ra, [r * 0.93 for r in ra], segs=12, cap_rings=1)
    else:
        v, f = sweep([pts[0], pts[2], pts[3]], V((0, 1, 0)), [ra[0], ra[2], ra[3]], [ra[0] * .93, ra[2] * .93, ra[3] * .93],
                     segs=8, caps=(True, False), cap_rings=0)
    return new_obj("body.neck" + (".lo" if lod else ""), v, f, ["M_skin"])


# ------------------------------------------------------------------ HANDS

def hand_frame(c, w, u_hint, v_hint):
    w = w.normalized()
    u = (u_hint - w * u_hint.dot(w)).normalized()
    v = w.cross(u).normalized()
    if v.dot(v_hint) < 0:
        v = -v
    return c, u, v, w


def build_hand(side, lod):
    """side +1 = right hand on the pistol grip, -1 = left hand under the handguard."""
    tagn = "R" if side > 0 else "L"
    sfx = ".lo" if lod else ""
    objs = []
    if side > 0:
        c, u, v, w = hand_frame(GRIP_C, GRIP_DIR, V((1, 0, 0)), V((0, 1, 0)))
        rg = GRIP_R
        palm_off = rg + 0.0135
        wrist = A["wrist_R"]
        P = c + u * palm_off
        idx_w = -0.033                       # index finger nearest the receiver (w points down)
        stack = +1
    else:
        c = HG_C
        u0 = (A["hand_L"] - c)
        c, u, v, w = hand_frame(c, V((0, 1, 0)), u0, V((0.77, 0, -0.64)))
        rg = HG_R
        palm_off = max(u0.length, rg + 0.012)
        wrist = A["wrist_L"]
        P = c + u * palm_off
        idx_w = +0.030                       # index toward the muzzle (+Y)
        stack = -1
    rf = 0.0108
    sp = 2 * rf + 0.0006
    pl = 0.050                                # palm length heel->knuckles
    pt = 0.024                                # palm thickness
    width = 4 * sp + 0.002
    w_mid = idx_w + stack * 1.5 * sp          # centre of the four fingers along w
    Pw = P + w * w_mid

    def polar(ang_deg, R, wo):
        a = rad(ang_deg)
        return c + w * wo + (u * math.cos(a) + v * math.sin(a)) * R

    if lod == 1:
        # ---- mitten: one fat curled tube + thumb + cuff
        R = rg + 0.012
        path = [Pw - v * (pl * 0.45), polar(50, R + 0.006, w_mid), polar(105, R, w_mid),
                polar(150, R - 0.001, w_mid)]
        vv, ff = sweep(path, w, 0.0125, width * 0.5, segs=6, cap_rings=1)
        objs.append(new_obj("body.hand_%s.lo" % tagn, vv, ff, ["M_glove"]))
        tb = Pw - v * 0.012 + w * (idx_w - stack * 0.004)
        if side > 0:
            tp = [tb, polar(-50, rg + 0.011, idx_w - 0.010), polar(-120, rg + 0.011, idx_w - 0.008)]
        else:
            tp = [tb, polar(-62, rg + 0.012, idx_w + 0.006), polar(-72, rg + 0.012, idx_w + 0.036)]
        vv, ff = sweep(tp, w if side > 0 else u, 0.0095, 0.0095, segs=4, cap_rings=1)
        objs.append(new_obj("body.thumb_%s.lo" % tagn, vv, ff, ["M_glove"]))
        H = Pw - v * (pl * 0.45)
        d = (wrist - H).normalized()
        elbow = A["elbow_R"] if side > 0 else A["elbow_L"]
        dW = (wrist - elbow).normalized()
        vv, ff = sweep([H, wrist + dW * 0.030, wrist + dW * 0.014, wrist - dW * 0.004], w,
                       [0.018, 0.029, 0.050, 0.051], [0.026, 0.029, 0.050, 0.051],
                       segs=6, caps=(False, True), cap_rings=0)
        objs.append(new_obj("body.cuff_%s.lo" % tagn, vv, ff, ["M_leather_brown"]))
        return objs

    # ---- palm / back of hand
    palm = rounded_box("body.palm_" + tagn, Pw + u * 0.001, (u, v, w), (pt, pl, width), "M_glove", bevel=0.0085, segs=2)
    objs.append(palm)
    # knuckle armour pad on the back of the hand
    pad = rounded_box("body.kpad_" + tagn, Pw + u * (pt * 0.5 + 0.0012) + v * (pl * 0.30), (u, v, w),
                      (0.007, 0.016, width * 0.86), "M_rubber_dark", bevel=0.0028, segs=1)
    objs.append(pad)
    # back-of-hand padded plate (slight bulge)
    plate = rounded_box("body.hplate_" + tagn, Pw + u * (pt * 0.5 + 0.0006) - v * (pl * 0.08), (u, v, w),
                        (0.0045, pl * 0.42, width * 0.70), "M_glove", bevel=0.0018, segs=1)
    objs.append(plate)

    # ---- fingers
    names = ["index", "middle", "ring", "pinky"]
    lengths = [1.00, 1.07, 1.00, 0.84]
    radii = [1.0, 1.02, 0.98, 0.88]
    for i, nmf in enumerate(names):
        wo = idx_w + stack * i * sp
        r = rf * radii[i]
        K = P + w * wo + v * (pl * 0.5 - 0.004) + u * 0.001         # knuckle (MCP)
        R = rg + r + 0.0006
        if side > 0 and i == 0:
            # trigger discipline: index straight along the receiver side, pointing forward
            fwd = V((0, 1, 0))
            pts = [K - v * 0.004, K + fwd * 0.014 + u * -0.001, K + fwd * 0.030 - u * 0.004 + V((0, 0, 0.004)),
                   K + fwd * 0.046 - u * 0.007 + V((0, 0, 0.006))]
            rr = [r * 1.02, r * 1.04, r * 0.97, r * 0.92]
            vv, ff = sweep(pts, w, rr, rr, segs=7, caps=(True, True), cap_rings=1)
        else:
            span = 98 * lengths[i]
            a0 = 62
            arc = [polar(a0 + span * t, R + 0.0008 * math.sin(pi * t), wo) for t in (0.0, 0.33, 0.66, 1.0)]
            pts = [K - v * 0.004, K + (arc[0] - K) * 0.5 + u * 0.004] + arc
            rr = [r * 1.03, r * 1.06, r * 1.0, r * 1.0, r * 0.97, r * 0.92]
            vv, ff = sweep(pts, w, rr, rr, segs=7, caps=(True, True), cap_rings=1)
        objs.append(new_obj("body.%s_%s" % (nmf, tagn), vv, ff, ["M_glove"]))

    # ---- thumb
    rt = rf * 1.12
    tb = P + w * (idx_w - stack * 0.004) - v * 0.010 + u * 0.002
    if side > 0:
        Rt = rg + rt + 0.002
        wo = idx_w - 0.012
        pts = [tb, polar(-35, Rt + 0.006, wo + 0.002), polar(-75, Rt + 0.002, wo), polar(-115, Rt, wo + 0.003),
               polar(-150, Rt, wo + 0.008), polar(-178, Rt, wo + 0.014)]
    else:
        Rt = rg + rt + 0.001
        pts = [tb, polar(-48, Rt + 0.004, idx_w + 0.000), polar(-66, Rt, idx_w + 0.016), polar(-74, Rt, idx_w + 0.034),
               polar(-77, Rt, idx_w + 0.050)]
    rr = [rt * 1.25, rt * 1.12, rt * 1.0, rt * 1.0, rt * 0.95, rt * 0.9][:len(pts)]
    upt = w if side > 0 else u
    vv, ff = sweep(pts, upt, rr, rr, segs=8, cap_rings=1)
    objs.append(new_obj("body.thumb_" + tagn, vv, ff, ["M_glove"]))
    # thenar pad (thumb muscle) bridging palm & thumb
    vv, ff = sweep([tb - v * 0.012 + w * stack * 0.006, tb + (pts[1] - tb) * 0.5], u, 0.012, 0.010, segs=8, cap_rings=1)
    objs.append(new_obj("body.thenar_" + tagn, vv, ff, ["M_glove"]))

    # ---- wrist: glove body -> leather cuff with strap
    H = Pw - v * (pl * 0.5 - 0.006)
    d = (wrist - H).normalized()
    mid = H + (wrist - H) * 0.45
    # cuff is coaxial with the sleeve (uniform: axis elbow->wrist, band r 0.0475, ends 10 mm past wrist)
    elbow = A["elbow_R"] if side > 0 else A["elbow_L"]
    dW = (wrist - elbow).normalized()
    cuff_end = wrist + dW * 0.031
    vv, ff = sweep([H + v * 0.012, H, H.lerp(cuff_end, 0.5), cuff_end - dW * 0.004], w,
                   [pt * 0.5, pt * 0.52, 0.0215, 0.0250], [width * 0.5 - 0.004, width * 0.48, 0.0270, 0.0275],
                   segs=12, caps=(True, True), cap_rings=1)
    objs.append(new_obj("body.wristg_" + tagn, vv, ff, ["M_glove"], recalc="closed"))
    # flared leather gauntlet: wide end goes OVER the sleeve end, narrow end hugs the glove wrist
    cp = [wrist - dW * 0.004, wrist + dW * 0.006, wrist + dW * 0.014, wrist + dW * 0.021, wrist + dW * 0.027, cuff_end]
    cr = [0.0505, 0.0510, 0.0495, 0.0440, 0.0360, 0.0290]
    vv, ff = sweep(cp, w, cr, cr, segs=16, caps=(True, True), cap_rings=1, cap_len=0.002)
    objs.append(new_obj("body.cuff_" + tagn, vv, ff, ["M_leather_brown"]))
    # dark rubber rim rolled round the wide open edge
    vv, ff = sweep([wrist - dW * 0.006, wrist + dW * 0.0005], w, 0.0530, 0.0530,
                   segs=16, caps=(True, True), cap_rings=1, cap_len=0.002)
    objs.append(new_obj("body.cuffrim_" + tagn, vv, ff, ["M_rubber_dark"]))
    # velcro strap across the back of the cuff
    o = (u - dW * u.dot(dW)).normalized()
    sc = wrist + dW * 0.013 + o * 0.0505
    strap = rounded_box("body.strap_" + tagn, sc, (o, dW, o.cross(dW).normalized()), (0.006, 0.012, 0.060), "M_glove",
                        bevel=0.0020, segs=1)
    objs.append(strap)
    return objs


# ------------------------------------------------------------------ build all

def build():
    reset()
    lod0, lod1 = [], []
    head = build_head(0)
    tree, hbm = bvh_of(head)
    lod0.append(head)
    lod0.append(build_hair(head))
    for side in (1, -1):
        eo, _ = build_eye(tree, side)
        lod0 += eo
        lod0.append(build_brow(tree, side))
        lod0.append(build_ear(side, 0))
    lod0.append(build_mouth(tree))
    lod0.append(build_neck(0))
    for side in (1, -1):
        lod0 += build_hand(side, 0)
    hbm.free()
    # LOD1
    lod1.append(build_head(1))
    lod1.append(build_neck(1))
    for side in (1, -1):
        lod1.append(build_ear(side, 1))
        lod1 += build_hand(side, 1)
    for o in lod0:
        finish(o, 0)
    for o in lod1:
        finish(o, 1)
    return lod0, lod1


if __name__ == "__main__":
    lod0, lod1 = build()
    print("LOD0 tris:", sum(tris(o) for o in lod0), " LOD1 tris:", sum(tris(o) for o in lod1))
    save_part(OWNER)
    if "--nopreview" not in sys.argv:
        preview("part_body", views=("face", "front34", "back34", "side"), lod=0, res=640, samples=24)
        hands = (V((0.55, 0.65, 0.62)), V((0.07, 0.25, 0.42)))
        preview("part_body_hands", views=(hands,), lod=0, res=640, samples=24)
        preview("part_body_lod1", views=("front34", "back34"), lod=1, res=512, samples=16)
