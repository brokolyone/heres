"""Hero soldier — helmet & rifle (owner: Helmet & Weapon artist).

Run: cd models/hero && python3 src/part_helmet_weapon.py
Builds helmet (shell, rubber edge trim, cover seams, ARC side rails, NVG shroud + mount, goggles with
strap, chin strap + cup + buckles, counterweight pouch, side star roundels, IR patch) and the rifle
(stock, buffer tube, receiver, ejection port, charging handle, pistol grip, trigger + guard, curved
magazine, M-LOK handguard with team-blue stripes, picatinny rail, holo optic with glowing lens,
barrel, muzzle brake, folded front sight, swivels + slack sling) in LOD0 and LOD1.
Saves parts/helmet_weapon.blend and previews/part_helmet_weapon_*.png.
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hero_common import *  # noqa
import bpy, bmesh
from mathutils import Vector, Matrix

OWNER = "helmet_weapon"
V = Vector
reset()
OBJS = []
GLOW = "M_lens_glow" if "M_lens_glow" in PALETTE else "M_goggle_lens"
rad = math.radians


# =============================================================== generic mesh building
class MB:
    """bmesh accumulator with per-face material names."""

    def __init__(s, name, lod=0, smooth=35.0):
        s.name, s.lod, s.smooth = name, lod, smooth
        s.bm = bmesh.new()
        s.mats = []

    def mi(s, m):
        if m not in s.mats:
            s.mats.append(m)
        return s.mats.index(m)

    def face(s, verts, m):
        try:
            f = s.bm.faces.new(verts)
        except ValueError:
            return None
        f.material_index = s.mi(m)
        return f

    def grid(s, rings, mats, closed=True, loop=False, cap0=None, cap1=None):
        """rings: list of point lists (equal length). mats: one name or list per ring gap."""
        vs = [[s.bm.verts.new(p) for p in r] for r in rings]
        n = len(rings[0])
        rng = range(len(vs) - 1) if not loop else range(len(vs))
        for i in rng:
            a, b = vs[i], vs[(i + 1) % len(vs)]
            m = mats if isinstance(mats, str) else mats[i]
            for j in range(n if closed else n - 1):
                j2 = (j + 1) % n
                s.face((a[j], a[j2], b[j2], b[j]), m)
        if cap0:
            s.face(list(reversed(vs[0])), cap0)
        if cap1:
            s.face(vs[-1], cap1)
        return vs

    def fan(s, ring_verts, center, m, reverse=False):
        c = s.bm.verts.new(center)
        n = len(ring_verts)
        for j in range(n):
            q = (ring_verts[j], ring_verts[(j + 1) % n], c)
            s.face(q[::-1] if reverse else q, m)

    def cube(s, mtx, m):
        r = bmesh.ops.create_cube(s.bm, size=1.0, matrix=mtx)
        for f in {f for v in r["verts"] for f in v.link_faces}:
            f.material_index = s.mi(m)

    def cyl(s, mtx, r1, r2, depth, seg, m):
        r = bmesh.ops.create_cone(s.bm, cap_ends=True, cap_tris=False, segments=seg, radius1=r1,
                                  radius2=r2, depth=depth, matrix=mtx)
        for f in {f for v in r["verts"] for f in v.link_faces}:
            f.material_index = s.mi(m)

    def build(s, bevel=None, segs=2, recalc=True):
        if recalc:
            bmesh.ops.recalc_face_normals(s.bm, faces=s.bm.faces[:])
        bmesh.ops.remove_doubles(s.bm, verts=s.bm.verts[:], dist=1e-6)
        me = bpy.data.meshes.new(s.name)
        s.bm.to_mesh(me)
        s.bm.free()
        ob = bpy.data.objects.new(s.name, me)
        bpy.context.scene.collection.objects.link(ob)
        for m in s.mats:
            me.materials.append(mat(m))
        if bevel:
            md = ob.modifiers.new("bevel", "BEVEL")
            md.width = bevel
            md.segments = segs
            md.limit_method = "ANGLE"
            md.angle_limit = rad(40)
            md.harden_normals = False
            md.use_clamp_overlap = True
        ob["_smooth"] = s.smooth
        tag(ob, "body", s.lod, OWNER)
        OBJS.append(ob)
        return ob


def box_mtx(center, size, rot=None):
    m = Matrix.Translation(V(center))
    if rot is not None:
        m = m @ rot
    return m @ Matrix.Diagonal((size[0], size[1], size[2], 1.0))


def frame_mtx(origin, X, Y, Z):
    m = Matrix.Identity(4)
    for i in range(3):
        m[i][0], m[i][1], m[i][2] = X[i], Y[i], Z[i]
        m[i][3] = origin[i]
    return m


def frames(path, up):
    out = []
    n = len(path)
    for i, p in enumerate(path):
        t = (path[min(i + 1, n - 1)] - path[max(i - 1, 0)]).normalized()
        u = up(p, i) if callable(up) else V(up)
        b = t.cross(u).normalized()
        nn = b.cross(t).normalized()
        out.append((p, t, b, nn))
    return out


def sweep(mb, path, prof, up, mats, caps=True, loop=False):
    """prof: list of (u,v) — u along side vector b, v along normal n."""
    rings = [[p + b * u + nn * v for (u, v) in prof] for (p, t, b, nn) in frames(path, up)]
    cm = mats if isinstance(mats, str) else mats[0]
    return mb.grid(rings, mats, closed=True, loop=loop,
                   cap0=cm if caps and not loop else None, cap1=cm if caps and not loop else None)


def rrect(w, h, r, seg=3):
    """rounded rectangle centred at 0, CCW, (u, v)."""
    pts = []
    for cx, cy, a0 in ((w / 2 - r, h / 2 - r, 0), (-w / 2 + r, h / 2 - r, 90), (-w / 2 + r, -h / 2 + r, 180),
                       (w / 2 - r, -h / 2 + r, 270)):
        for k in range(seg + 1):
            a = rad(a0 + 90 * k / seg)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def circle(r, n, z0=0.0):
    return [(r * math.cos(2 * math.pi * k / n), r * math.sin(2 * math.pi * k / n)) for k in range(n)]


def superellipse(hw, hh, p, n):
    pts = []
    for k in range(n):
        a = 2 * math.pi * k / n
        c, s_ = math.cos(a), math.sin(a)
        pts.append((hw * math.copysign(abs(c) ** (2 / p), c), hh * math.copysign(abs(s_) ** (2 / p), s_)))
    return pts


def lathe(mb, prof, origin, axis, seg, mats, cap_start=None, cap_end=None):
    """prof: list of (r, h) along axis ('Y' only here). Rings around Y axis through origin."""
    rings = []
    for (r, h) in prof:
        ring = []
        for k in range(seg):
            a = 2 * math.pi * k / seg + math.pi / seg
            ring.append(V(origin) + V((r * math.cos(a), h, r * math.sin(a))))
        rings.append(ring)
    vs = mb.grid(rings, mats, closed=True)
    if cap_start:
        mb.fan(vs[0], V(origin) + V((0, prof[0][1], 0)), cap_start, reverse=True)
    if cap_end:
        mb.fan(vs[-1], V(origin) + V((0, prof[-1][1], 0)), cap_end)
    return vs


# =============================================================== helmet geometry
HC = A["helmet"]
HR = A["helmet_r"]
LIP_DT = 0.0172  # tangential reach of the rubber trim below the last blue row


def zbrim(phi):
    s = math.sin(phi)  # +1 front (+Y), -1 back
    return 0.76 + 0.0525 * s + 0.0275 * s * s


def abrim(phi):
    """alpha of the last blue row so the trim's lower edge lands on the plan's brim height."""
    a_bot = math.acos(max(-1, min(1, (zbrim(phi) - HC.z) / (HR + 0.006))))
    return a_bot - LIP_DT / (HR + 0.006)


def sdir(a, phi):
    return V((math.sin(a) * math.cos(phi), math.sin(a) * math.sin(phi), math.cos(a)))


def smooth01(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


def shell_r(a, phi):
    ab = abrim(phi)
    return HR + 0.006 * smooth01(0.72 * ab, ab, a)


def on_shell(a, phi, off=0.0):
    return HC + (shell_r(a, phi) + off) * sdir(a, phi)


def shell_frame(a, phi):
    n = sdir(a, phi)
    up = -V((math.cos(a) * math.cos(phi), math.cos(a) * math.sin(phi), -math.sin(a)))
    X = n.cross(up)
    return X, n, up


def ang(p):
    d = (V(p) - HC).normalized()
    return math.acos(max(-1, min(1, d.z))), math.atan2(d.y, d.x)


def shell(mb, M, N, lip=True, inner=True):
    rings = []
    phis = [math.pi / 2 + 2 * math.pi * j / M for j in range(M)]
    for k in range(1, N + 1):
        t = k / N
        t = 1 - (1 - t) ** 1.15  # slightly denser near the brim
        rings.append([on_shell(t * abrim(p), p) for p in phis])
    mats = ["M_helmet_blue"] * (N - 1)
    if lip:
        prof = [(0.0030, 0.0013), (0.0050, 0.0089), (0.0026, 0.0163), (-0.0034, 0.0181),
                (-0.0105, 0.0135), (-0.0125, 0.0034)]
        if inner:
            prof += [(-0.0135, -0.06)]
        for dr, dt in prof:
            row = []
            for p in phis:
                ab = abrim(p)
                rb = shell_r(ab, p)
                row.append(HC + (rb + dr) * sdir(ab + dt / rb, p))
            rings.append(row)
        mats += ["M_rubber_dark"] * len(prof)
    vs = mb.grid(rings, mats, closed=True)
    mb.fan(vs[0], HC + V((0, 0, HR)), "M_helmet_blue", reverse=True)
    if lip and inner:  # close the inside (single-sided export): inner dome fan
        mb.fan(vs[-1], HC + V((0, 0, HR - 0.03)), "M_rubber_dark")
    return vs


def puck(mb, a0, phi0, outline, rings, center=None, rot=0.0):
    """Conforming pad on the shell. outline: [(x,y)] metres (x→character-right tangent, y→up).
    rings: [(scale, offset, mat_of_band_leading_to_this_ring)], first ring's mat unused.
    center: (offset, mat) for a fan closing the last ring."""
    rr = shell_r(a0, phi0)
    cr, sr = math.cos(rot), math.sin(rot)
    vsl = []
    for sc, off, _m in rings:
        row = []
        for (x, y) in outline:
            x, y = x * cr - y * sr, x * sr + y * cr
            a = a0 - y * sc / rr
            ph = phi0 - x * sc / (rr * max(0.2, math.sin(a0)))
            row.append(on_shell(a, ph, off))
        vsl.append(row)
    vs = mb.grid(vsl, [r[2] for r in rings[1:]], closed=True)
    if center:
        mb.fan(vs[-1], on_shell(a0, phi0, center[0]), center[1])
    return vs


def star_outline(ro, ri, n=5):
    pts = []
    for k in range(2 * n):
        r = ro if k % 2 == 0 else ri
        a = math.pi / 2 + math.pi * k / n
        pts.append((r * math.cos(a), r * math.sin(a)))
    return pts


def load_head_bvh():
    """BVH of the body artist's head + ears (read-only use of parts/body.blend); None if unavailable."""
    from mathutils.bvhtree import BVHTree
    path = os.path.join(PARTS_DIR, "body.blend")
    if not os.path.exists(path):
        return None
    names = {"body.head", "body.ear_L", "body.ear_R"}
    with bpy.data.libraries.load(path, link=False) as (src, dst):
        dst.meshes = []
        dst.objects = [n for n in src.objects if n in names]
    bm = bmesh.new()
    for o in dst.objects:
        if o is None:
            continue
        me = o.data.copy()
        me.transform(o.matrix_world)
        bm.from_mesh(me)
        bpy.data.meshes.remove(me)
        m = o.data
        bpy.data.objects.remove(o, do_unlink=True)
        if m.users == 0:
            bpy.data.meshes.remove(m)
    if not bm.verts:
        bm.free()
        return None
    bm.normal_update()
    t = BVHTree.FromBMesh(bm)
    bm.free()
    return t


def build_helmet():
    # ---- shell + trim + inner band
    mb = MB("hw.helmet_shell", 0, smooth=48)
    shell(mb, 36, 9)
    mb.build()

    # ---- cover seams (two front-to-back raised seams + a cross seam over the top)
    mb = MB("hw.helmet_seams", 0, smooth=60)
    prof = [(-0.0030, -0.0008), (0.0, 0.0018), (0.0030, -0.0008)]
    for xo in (-0.058, 0.058):
        path = []
        for i in range(17):
            phi = math.pi / 2 if xo > 0 else math.pi / 2
            # walk from front (alpha≈0.80*ab_front) over the top to back
            g = -1.0 + 2.0 * i / 16  # -1 front .. +1 back
            ph = math.pi / 2 if g < 0 else -math.pi / 2
            a_front = 0.80 * abrim(math.pi / 2)
            a_back = 0.80 * abrim(-math.pi / 2)
            # direction param in the plane x = xo
            ang_ = (-a_front + (a_back + a_front) * (i / 16))  # signed polar angle in yz-plane
            rho = math.sqrt(max(1e-6, HR ** 2 - xo ** 2))
            y = HC.y + rho * math.sin(-ang_)
            z = HC.z + rho * math.cos(ang_)
            d = V((xo, y, z)) - HC
            a, p = ang(HC + d)
            path.append(on_shell(a, p, 0.0005))
        sweep(mb, path, prof, lambda p, i: (p - HC).normalized(), "M_helmet_blue", caps=True)
    # cross seam (left-right) slightly behind the top
    path = []
    for i in range(17):
        u = -1 + 2 * i / 16
        phi = 0.0 if u >= 0 else math.pi
        a = abs(u) * 0.62 * abrim(0.0)
        path.append(on_shell(max(a, 0.02), phi if a > 0.02 else 0.0, 0.0005) + V((0, -0.035, 0)) * (1 - abs(u)) * 0)
    # rotate the cross seam slightly back so it doesn't sit on the exact top pole
    rot = Matrix.Rotation(rad(14), 4, "X")
    path = [HC + (rot @ (p - HC)) for p in path]
    path = [on_shell(*ang(p), 0.0005) for p in path]
    sweep(mb, path, prof, lambda p, i: (p - HC).normalized(), "M_helmet_blue", caps=True)
    mb.build()

    # ---- ARC side rails with slots and bolts
    mb = MB("hw.helmet_rails", 0, smooth=40)
    det = MB("hw.helmet_rail_detail", 0, smooth=40)
    rail_prof = [(u, v) for (u, v) in rrect(0.026, 0.010, 0.003, 1)]
    for side in (1, -1):
        base = 0.0 if side > 0 else math.pi
        path = []
        span = [rad(-30), rad(36)]
        for i in range(13):
            d = span[0] + (span[1] - span[0]) * i / 12
            ph = base + d * side
            a = abrim(ph) - 0.085
            path.append(on_shell(a, ph, 0.004))
        sweep(mb, path, rail_prof, lambda p, i: (p - HC).normalized(), "M_polymer_gun", caps=True)
        # slots & bolts
        for k, d in enumerate([rad(-20), rad(-6), rad(8), rad(22)]):
            ph = base + d * side
            a = abrim(ph) - 0.085
            X, n, up = shell_frame(a, ph)
            c = on_shell(a, ph, 0.0095)
            det.cube(frame_mtx(c, X, n, up) @ Matrix.Diagonal((0.014, 0.0016, 0.006, 1)), "M_rubber_dark")
        for d in (rad(-27), rad(32)):
            ph = base + d * side
            a = abrim(ph) - 0.085
            X, n, up = shell_frame(a, ph)
            c = on_shell(a, ph, 0.0095)
            det.cyl(frame_mtx(c, X, up, -n) @ Matrix.Rotation(0, 4, "X"), 0.0042, 0.0036, 0.003, 6, "M_metal_bright")
    mb.build()
    det.build(recalc=True)

    # ---- NVG shroud plate + mount bracket + bolts
    mb = MB("hw.helmet_shroud", 0, smooth=40)
    a0, p0 = rad(39), math.pi / 2
    puck(mb, a0, p0, superellipse(0.032, 0.022, 3.2, 20),
         [(1.0, -0.002, None), (1.0, 0.0035, "M_polymer_gun"), (0.94, 0.0055, "M_polymer_gun"),
          (0.88, 0.0058, "M_polymer_gun")], center=(0.0062, "M_polymer_gun"))
    X, n, up = shell_frame(a0, p0)
    c = on_shell(a0, p0, 0.0125) - up * 0.002
    mb.cube(frame_mtx(c, X, n, up) @ Matrix.Diagonal((0.030, 0.014, 0.020, 1)), "M_polymer_gun")
    mb.cube(frame_mtx(c + n * 0.0072 + up * 0.0015, X, n, up) @ Matrix.Diagonal((0.020, 0.002, 0.009, 1)),
            "M_rubber_dark")
    shroud = mb.build(bevel=0.0022, segs=1)
    mb = MB("hw.helmet_shroud_bolts", 0, smooth=40)
    for dx, dy in ((-0.024, 0.012), (0.024, 0.012), (-0.024, -0.012), (0.024, -0.012)):
        rr = shell_r(a0, p0)
        a = a0 - dy / rr
        ph = p0 - dx / (rr * math.sin(a0))
        X, n, up = shell_frame(a, ph)
        mb.cyl(frame_mtx(on_shell(a, ph, 0.0062), X, up, -n), 0.0032, 0.0026, 0.0022, 6, "M_metal_bright")
    mb.build()

    # ---- goggles: two lens pods + bridge + strap + side clips
    mb = MB("hw.goggles", 0, smooth=50)
    ga = math.acos((A["goggles"].z - HC.z) / HR)
    for side in (1, -1):
        ph = math.pi / 2 - side * rad(16.5)
        outline = []
        for (x, y) in superellipse(0.036, 0.0225, 3.4, 20):
            # outer-bottom corner droops (classic goggle shape)
            y -= 0.006 * max(0.0, x * side) / 0.036 * (1 if y < 0 else 0.3)
            outline.append((x * side * side, y))
        puck(mb, ga, ph, outline,
             [(1.0, -0.002, None), (1.06, 0.007, "M_rubber_dark"), (1.03, 0.015, "M_rubber_dark"),
              (0.88, 0.0190, "M_rubber_dark"), (0.82, 0.0150, "M_rubber_dark"),
              (0.55, 0.0180, "M_goggle_lens")],
             center=(0.0197, "M_goggle_lens"))
    # nose bridge
    puck(mb, ga + 0.01, math.pi / 2, superellipse(0.012, 0.010, 3, 10),
         [(1.0, -0.002, None), (1.0, 0.012, "M_rubber_dark"), (0.8, 0.015, "M_rubber_dark")],
         center=(0.0155, "M_rubber_dark"))
    mb.build()

    mb = MB("hw.goggle_strap", 0, smooth=50)
    path = []
    p_start, p_end = math.pi / 2 + rad(34), math.pi / 2 + 2 * math.pi - rad(34)
    a_back = math.acos((0.862 - HC.z) / HR)
    for i in range(37):
        ph = p_start + (p_end - p_start) * i / 36
        w = (1 - math.sin(ph)) / 2  # 0 front, 1 back
        a = ga + (a_back - ga) * w
        path.append(on_shell(a, ph, 0.0004))
    sweep(mb, path, [(-0.0105, 0), (0.0105, 0), (0.0105, 0.0042), (-0.0105, 0.0042)], lambda p, i: (p - HC).normalized(), "M_strap_tan")
    mb.build()
    mb = MB("hw.goggle_clips", 0, smooth=40)
    # strap clips where the strap enters the frame
    for side in (1, -1):
        ph = math.pi / 2 - side * rad(37)
        X, n, up = shell_frame(ga, ph)
        c = on_shell(ga, ph, 0.006)
        mb.cube(frame_mtx(c, X, n, up) @ Matrix.Diagonal((0.016, 0.008, 0.026, 1)), "M_rubber_dark")
    mb.build(bevel=0.0018, segs=1)

    # ---- side star roundels (face the game camera: back-right / back-left)
    mb = MB("hw.helmet_emblems", 0, smooth=50)
    for side in (1, -1):
        ph = rad(-52) if side > 0 else rad(180 + 52)
        a = math.acos((0.808 - HC.z) / HR)
        puck(mb, a, ph, circle(0.027, 16),
             [(1.0, -0.0015, None), (1.0, 0.0019, "M_pants_navy"), (0.87, 0.0019, "M_emblem"),
              (0.81, 0.0019, "M_pants_navy")], center=(0.0019, "M_pants_navy"))
        puck(mb, a, ph, star_outline(0.0175, 0.0072),
             [(1.0, 0.0008, None), (1.0, 0.0032, "M_emblem")], center=(0.0032, "M_emblem"))
    # IR / velcro patch on the top-back (reads from the game camera)
    puck(mb, rad(30), -math.pi / 2, rrect(0.044, 0.030, 0.006, 1),
         [(1.0, -0.0015, None), (1.0, 0.0018, "M_cloth_olive"), (0.92, 0.0024, "M_cloth_olive")],
         center=(0.0024, "M_cloth_olive"))
    puck(mb, rad(30), -math.pi / 2, rrect(0.026, 0.014, 0.003, 1),
         [(1.0, 0.0012, None), (1.0, 0.0032, "M_emblem")], center=(0.0032, "M_emblem"))
    mb.build()

    # ---- counterweight pouch on the back
    mb = MB("hw.helmet_pouch", 0, smooth=45)
    pa, pp = math.acos((0.781 - HC.z) / HR), -math.pi / 2
    puck(mb, pa, pp, rrect(0.094, 0.050, 0.012, 2),
         [(1.0, -0.004, None), (1.0, 0.012, "M_vest_tan"), (0.97, 0.020, "M_vest_tan"),
          (0.90, 0.0235, "M_vest_tan"), (0.80, 0.0245, "M_vest_tan")], center=(0.025, "M_vest_tan"))
    # flap
    fl = [(x, y * 0.55 + 0.011) for (x, y) in rrect(0.098, 0.050, 0.012, 2)]
    puck(mb, pa, pp, fl,
         [(1.0, 0.018, None), (1.0, 0.0275, "M_vest_tan"), (0.96, 0.0285, "M_vest_tan")],
         center=(0.0288, "M_vest_tan"))
    # flap velcro tab + loop at the bottom
    puck(mb, pa, pp, [(x, y - 0.002) for (x, y) in rrect(0.022, 0.012, 0.003, 1)],
         [(1.0, 0.026, None), (1.0, 0.0305, "M_strap_tan")], center=(0.0305, "M_strap_tan"))
    mb.build()

    # ---- chin strap (Y harness from the helmet to a chin cup) + buckles
    HD, HRAD = A["head"], A["head_r"]

    def hp(theta, e, s=1.075):
        return HD + V((s * HRAD.x * math.cos(e) * math.cos(theta), s * HRAD.y * math.cos(e) * math.sin(theta),
                       s * HRAD.z * math.sin(e)))

    def hn_ell(p):
        d = p - HD
        return V((d.x / HRAD.x ** 2, d.y / HRAD.y ** 2, d.z / HRAD.z ** 2)).normalized()

    # Snap the strap onto the body artist's real head surface when parts/body.blend exists.
    bvh = load_head_bvh()

    def snap(p, off=0.0009):
        if bvh is None:
            return p
        loc, nrm, _i, _d = bvh.find_nearest(p)
        if loc is None:
            return p
        return loc + nrm * off

    def hn(p):
        if bvh is not None:
            loc, nrm, _i, _d = bvh.find_nearest(p)
            if loc is not None:
                return nrm
        return hn_ell(p)

    mb = MB("hw.chin_strap", 0, smooth=50)
    det = MB("hw.chin_strap_hw", 0, smooth=40)
    right = [(rad(26), rad(-2)), (rad(28), rad(-14)), (rad(31), rad(-28)), (rad(36), rad(-42)),
             (rad(45), rad(-56)), (rad(58), rad(-67)), (rad(74), rad(-74)), (rad(90), rad(-76))]
    pts_r = [hp(t, e) for t, e in right]
    pts_l = [V((-p.x, p.y, p.z)) for p in pts_r]
    top_r = on_shell(abrim(rad(26)) + 0.05, rad(26), -0.016)
    top_l = V((-top_r.x, top_r.y, top_r.z))
    path = [top_l] + pts_l[:-1] + list(reversed(pts_r))
    path.insert(0, top_l)
    # upsample with Catmull-Rom for smoothness
    def cr(pts, sub=3):
        out = []
        P = [pts[0]] + pts + [pts[-1]]
        for i in range(1, len(P) - 2):
            p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
            for k in range(sub):
                t = k / sub
                out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t +
                                  (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
        out.append(pts[-1])
        return out
    path = cr(path[1:], 2)
    path = [path[0]] + [snap(p) for p in path[1:-1]] + [path[-1]] if bvh else path
    path[1] = path[0].lerp(path[2], 0.5) if bvh else path[1]
    path[-2] = path[-1].lerp(path[-3], 0.5) if bvh else path[-2]
    sweep(mb, path, [(-0.0065, 0), (0.0065, 0), (0.0065, 0.0028), (-0.0065, 0.0028)], lambda p, i: hn(p), "M_strap_tan")
    # rear branch of the Y (from behind the ear up into the helmet)
    for sx in (1, -1):
        # rear branch runs BEHIND the ear and under the lobe to the buckle junction
        back = on_shell(abrim(rad(-26)) + 0.05, rad(-26), -0.016)
        ctrl = [back, hp(rad(-24), rad(-10)), hp(rad(-12), rad(-27)), hp(rad(8), rad(-35)), hp(rad(30), rad(-30))]
        bpath = cr([V((q.x * sx, q.y, q.z)) for q in ctrl], 2)
        if bvh:
            bpath = [bpath[0]] + [snap(p) for p in bpath[1:]]
        sweep(mb, bpath, [(-0.005, 0), (0.005, 0), (0.005, 0.0026), (-0.005, 0.0026)], lambda p, i: hn(p), "M_strap_tan")
        # buckle on the junction + slider
        for (t, e, sz) in ((rad(31), rad(-29), (0.018, 0.005, 0.014)), (rad(29), rad(-45), (0.016, 0.004, 0.008))):
            p = hp(t, e, 1.10)
            p = V((p.x * sx, p.y, p.z))
            n = hn(p)
            p = snap(p, 0.0035) if bvh else p
            tang = (hp(t, e - 0.05) - hp(t, e + 0.05)).normalized()
            tang = V((tang.x * sx, tang.y, tang.z))
            X = tang.cross(n).normalized()
            Z = n.cross(X).normalized()
            det.cube(frame_mtx(p, X, n, Z) @ Matrix.Diagonal((sz[0], sz[1], sz[2], 1)), "M_metal_bright")
    # chin cup
    cup_path = [hp(rad(t), rad(-75.5), 1.10) for t in range(62, 119, 14)]
    if bvh:
        cup_path = [snap(p, 0.0012) for p in cup_path]
    sweep(mb, cup_path, rrect(0.026, 0.006, 0.0025, 1), lambda p, i: hn(p), "M_leather_brown")
    mb.build()
    det.build()


def build_helmet_lo():
    mb = MB("hw.helmet.lo", 1, smooth=50)
    rings = []
    M = 16
    phis = [math.pi / 2 + 2 * math.pi * j / M for j in range(M)]
    for t in (0.30, 0.56, 0.80, 1.0):
        rings.append([on_shell(t * abrim(p), p) for p in phis])
    for dr, dt in ((0.0050, 0.0085), (-0.004, LIP_DT), (-0.0125, 0.004)):
        rings.append([HC + (shell_r(abrim(p), p) + dr) * sdir(abrim(p) + dt / HR, p) for p in phis])
    vs = mb.grid(rings, ["M_helmet_blue"] * 3 + ["M_rubber_dark"] * 3)
    mb.fan(vs[0], HC + V((0, 0, HR)), "M_helmet_blue", reverse=True)
    mb.fan(vs[-1], HC + V((0, 0, HR - 0.03)), "M_rubber_dark")
    ga = math.acos((A["goggles"].z - HC.z) / HR)
    puck(mb, ga, math.pi / 2, superellipse(0.075, 0.022, 4, 10),
         [(1.0, -0.002, None), (1.0, 0.016, "M_rubber_dark")], center=(0.018, "M_goggle_lens"))
    mb.build()


# =============================================================== rifle
RX, RZ = A["rifle_x"], A["rifle_z"]


def build_rifle():
    rot0 = None
    # ---- metal: receiver, magwell, buffer tube, charging handle (bevelled boxes)
    mb = MB("hw.rifle_receiver", 0, smooth=35)
    mb.cube(box_mtx((RX, 0.236, 0.4705), (0.034, 0.132, 0.031)), "M_metal_gun")        # upper
    mb.cube(box_mtx((RX, 0.226, 0.438), (0.031, 0.112, 0.036)), "M_metal_gun")          # lower
    mb.cube(box_mtx((RX, 0.274, 0.425), (0.033, 0.054, 0.034)), "M_metal_gun")          # magwell
    mb.cube(box_mtx((RX, 0.168, 0.4825), (0.030, 0.012, 0.008)), "M_metal_gun")         # charging handle
    mb.cube(box_mtx((RX + 0.0105, 0.200, 0.4625), (0.008, 0.016, 0.012)), "M_metal_gun")  # forward assist
    mb.cube(box_mtx((RX, 0.300, 0.4705), (0.038, 0.012, 0.035)), "M_metal_gun")         # barrel nut ring
    mb.build(bevel=0.0035, segs=1)

    det = MB("hw.rifle_details", 0, smooth=35)
    det.cube(box_mtx((RX + 0.0172, 0.236, 0.469), (0.0016, 0.044, 0.014)), "M_rubber_dark")  # ejection port
    det.cube(box_mtx((RX + 0.0176, 0.236, 0.4775), (0.002, 0.040, 0.0025)), "M_metal_bright")  # port cover hinge
    det.cube(box_mtx((RX + 0.0162, 0.215, 0.444), (0.002, 0.010, 0.007)), "M_metal_bright")  # selector
    det.cube(box_mtx((RX - 0.0162, 0.215, 0.444), (0.002, 0.010, 0.007)), "M_metal_bright")
    det.cube(box_mtx((RX + 0.0166, 0.262, 0.432), (0.002, 0.008, 0.006)), "M_metal_bright")  # mag release
    for y in (0.188, 0.284):  # takedown pins
        for sx in (1, -1):
            det.cyl(box_mtx((RX + sx * 0.0158, y, 0.446), (1, 1, 1),
                            Matrix.Rotation(rad(90), 4, "Y")), 0.0032, 0.0032, 0.003, 6, "M_metal_bright")
    det.build()

    # ---- picatinny rail (receiver + handguard top)
    mb = MB("hw.rifle_rail", 0, smooth=30)
    mb.cube(box_mtx((RX, 0.345, 0.4885), (0.017, 0.340, 0.0042)), "M_metal_gun")
    y = 0.180
    while y < 0.512:
        mb.cube(box_mtx((RX, y, 0.4925), (0.020, 0.0062, 0.0042)), "M_metal_gun")
        y += 0.0150
    mb.build()

    # ---- handguard (polymer) with M-LOK slots + team-blue stripes
    mb = MB("hw.rifle_handguard", 0, smooth=35)
    # round-ish (superellipse) tube, radius 0.026 around the rifle axis (AD ruling 19:18)
    hprof = superellipse(0.026, 0.026, 2.7, 20)
    hrings = []
    for (yy, sc) in ((0.290, 0.86), (0.2935, 1.0), (0.5145, 1.0), (0.5185, 0.90), (0.5195, 0.80)):
        hrings.append([V((RX + x * sc, yy, RZ + z * sc)) for (x, z) in hprof])
    vs = mb.grid(hrings, "M_polymer_gun", closed=True)
    mb.fan(vs[0], V((RX, 0.290, RZ)), "M_polymer_gun", reverse=True)
    mb.fan(vs[-1], V((RX, 0.5195, RZ)), "M_polymer_gun")
    hg = mb.build()
    det = MB("hw.rifle_handguard_detail", 0, smooth=35)
    for sx in (1, -1):
        det.cube(box_mtx((RX + sx * 0.0255, 0.408, RZ + 0.0085), (0.0024, 0.186, 0.0055)), "M_gun_accent")
        for yy in (0.338, 0.381, 0.424, 0.467):
            det.cube(box_mtx((RX + sx * 0.0254, yy, RZ - 0.0060), (0.0024, 0.026, 0.0068)), "M_rubber_dark")
    for yy in (0.350, 0.405, 0.460):
        det.cube(box_mtx((RX, yy, RZ - 0.0258), (0.010, 0.030, 0.0024)), "M_rubber_dark")
    det.cube(box_mtx((RX, 0.404, RZ + 0.0285), (0.0150, 0.226, 0.0070)), "M_polymer_gun")  # rail riser
    det.build()

    # ---- barrel, gas block stub, muzzle brake (lathe)
    mb = MB("hw.rifle_barrel", 0, smooth=40)
    lathe(mb, [(0.0115, 0.476), (0.0115, 0.620), (0.0126, 0.622), (0.0126, 0.638)], (RX, 0, RZ + 0.006), "Y", 12,
          "M_metal_gun", cap_start="M_metal_gun")
    prof = [(0.0130, 0.636), (0.0160, 0.640), (0.0160, 0.6555), (0.0146, 0.6585), (0.0160, 0.6615),
            (0.0160, 0.6740), (0.0162, 0.6755), (0.0162, 0.6785), (0.0150, 0.6800),
            (0.0066, 0.6800), (0.0058, 0.672)]
    mats = ["M_metal_gun"] * 5 + ["M_metal_bright"] * 4 + ["M_rubber_dark"]
    lathe(mb, prof, (RX, 0, RZ + 0.006), "Y", 14, mats, cap_start="M_metal_gun", cap_end="M_rubber_dark")
    mb.cube(box_mtx((RX, 0.5275, RZ + 0.009), (0.026, 0.014, 0.030)), "M_metal_gun")  # gas block
    mb.cube(box_mtx((RX, 0.5275, RZ + 0.0255), (0.016, 0.009, 0.004)), "M_metal_bright")  # gas block top screw plate
    for sx in (1, -1):  # brake side ports
        for yy in (0.648, 0.668):
            mb.cube(box_mtx((RX + sx * 0.0150, yy, RZ + 0.006), (0.004, 0.011, 0.010)), "M_rubber_dark")
    mb.build()

    # ---- front sight (folded) + rear sight (folded) on the rail
    mb = MB("hw.rifle_sights", 0, smooth=35)
    mb.cube(box_mtx((RX, 0.503, 0.4995), (0.018, 0.016, 0.009)), "M_polymer_gun")
    mb.cube(box_mtx((RX, 0.503, 0.5055), (0.010, 0.010, 0.004)), "M_polymer_gun")
    mb.cube(box_mtx((RX, 0.181, 0.4990), (0.018, 0.012, 0.008)), "M_polymer_gun")
    mb.build()

    # ---- stock + buffer tube + butt pad + cheek riser
    mb = MB("hw.rifle_buffer", 0, smooth=40)
    lathe(mb, [(0.0115, 0.112), (0.0115, 0.172), (0.0135, 0.174), (0.0135, 0.180)], (RX, 0, 0.4655), "Y", 12,
          "M_metal_gun", cap_start="M_metal_gun", cap_end="M_metal_gun")
    mb.build()
    mb = MB("hw.rifle_stock", 0, smooth=35)
    mb.cube(box_mtx((RX, 0.133, 0.457), (0.034, 0.058, 0.060)), "M_polymer_gun")
    mb.cube(box_mtx((RX, 0.140, 0.4815), (0.030, 0.048, 0.016)), "M_polymer_gun")   # cheek riser
    mb.cube(box_mtx((RX, 0.150, 0.425), (0.028, 0.034, 0.012)), "M_polymer_gun")    # lower lug
    mb.build(bevel=0.0065, segs=2)
    mb = MB("hw.rifle_buttpad", 0, smooth=35)
    mb.cube(box_mtx((RX, 0.1025, 0.4555), (0.037, 0.008, 0.068)), "M_rubber_dark")
    mb.build(bevel=0.003, segs=1)
    det = MB("hw.rifle_stock_detail", 0, smooth=35)
    for sx in (1, -1):
        det.cube(box_mtx((RX + sx * 0.0172, 0.131, 0.452), (0.0016, 0.032, 0.018)), "M_gun_accent")
    det.cube(box_mtx((RX, 0.122, 0.4335), (0.036, 0.008, 0.006)), "M_rubber_dark")  # QD slot band
    det.build()

    # ---- pistol grip (raked) + trigger + guard
    mb = MB("hw.rifle_grip", 0, smooth=35)
    # AD ruling: section 0.030 x 0.040, raked 17 deg, through hand_R, top z~0.430, bottom z~0.355
    rg = Matrix.Rotation(rad(-17), 4, "X")
    gc = V((RX, A["hand_R"].y, A["hand_R"].z))
    mb.cube(box_mtx(gc, (0.030, 0.040, 0.080), rg), "M_polymer_gun")
    mb.cube(box_mtx(gc + (rg.to_3x3() @ V((0, -0.001, -0.037))), (0.032, 0.044, 0.008), rg), "M_polymer_gun")
    mb.build(bevel=0.0065, segs=2)
    mb = MB("hw.rifle_trigger", 0, smooth=40)
    gpath = [V((RX, 0.222, 0.424)), V((RX, 0.224, 0.411)), V((RX, 0.232, 0.406)), V((RX, 0.248, 0.406)),
             V((RX, 0.254, 0.411)), V((RX, 0.256, 0.422))]
    sweep(mb, gpath, [(-0.004, -0.002), (0.004, -0.002), (0.004, 0.002), (-0.004, 0.002)], (1, 0, 0), "M_metal_gun")
    tpath = [V((RX, 0.240, 0.421)), V((RX, 0.239, 0.415)), V((RX, 0.236, 0.411))]
    sweep(mb, tpath, rrect(0.0035, 0.004, 0.0012, 1), (1, 0, 0), "M_metal_bright")
    mb.build()

    # ---- curved magazine (sweep) + team-blue base plate + ribs
    mb = MB("hw.rifle_mag", 0, smooth=35)
    mpath = []
    for i in range(9):
        t = i / 8
        mpath.append(V((RX, 0.272 + 0.010 * t + 0.016 * t * t, 0.432 - 0.088 * t)))
    sweep(mb, mpath, rrect(0.046, 0.025, 0.006, 2), (1, 0, 0), "M_polymer_gun")
    for t in (0.35, 0.6):
        p = V((RX, 0.272 + 0.010 * t + 0.016 * t * t, 0.432 - 0.088 * t))
        mb.cube(box_mtx(p + V((0, 0.0, 0)), (0.0262, 0.040, 0.004), Matrix.Rotation(rad(14 * t + 5), 4, "X")),
                "M_polymer_gun")
    mb.build()
    mb = MB("hw.rifle_mag_base", 0, smooth=35)
    pb = mpath[-1]
    mb.cube(box_mtx(pb + V((0, 0.003, -0.002)), (0.030, 0.054, 0.010), Matrix.Rotation(rad(19), 4, "X")),
            "M_gun_accent")
    mb.build(bevel=0.0028, segs=1)

    # ---- holo optic: mount, lathe body, hood, glowing front lens, rear lens, turrets
    oc = V((RX, 0, 0.5305))
    mb = MB("hw.rifle_optic_mount", 0, smooth=35)
    mb.cube(box_mtx((RX, 0.228, 0.5015), (0.024, 0.056, 0.010)), "M_metal_gun")
    mb.cube(box_mtx((RX, 0.228, 0.5085), (0.016, 0.040, 0.008)), "M_metal_gun")
    mb.cube(box_mtx((RX + 0.0135, 0.236, 0.5005), (0.006, 0.014, 0.008)), "M_metal_bright")  # QD lever
    mb.build(bevel=0.0018, segs=1)
    mb = MB("hw.rifle_optic", 0, smooth=40)
    prof = [(0.0150, 0.200), (0.0175, 0.196), (0.0200, 0.197), (0.0210, 0.202), (0.0210, 0.248), (0.0222, 0.252),
            (0.0236, 0.262), (0.0236, 0.270), (0.0222, 0.2725), (0.0190, 0.2725), (0.0180, 0.267)]
    mats = ["M_polymer_gun"] * 3 + ["M_metal_gun"] + ["M_polymer_gun"] * 6
    lathe(mb, prof, oc, "Y", 16, mats)
    # rear lens (dark, slightly recessed)
    r0 = lathe(mb, [(0.0150, 0.200), (0.0150, 0.201)], oc, "Y", 16, "M_polymer_gun")
    mb.fan(r0[-1], oc + V((0, 0.2005, 0)), "M_rubber_dark", reverse=True)
    # front glowing lens
    r1 = lathe(mb, [(0.0180, 0.267), (0.0180, 0.2655)], oc, "Y", 16, "M_polymer_gun")
    mb.fan(r1[-1], oc + V((0, 0.2645, 0)), GLOW)
    # turrets
    mb.cyl(box_mtx(oc + V((0, 0.226, 0.0225)), (1, 1, 1)), 0.0068, 0.0062, 0.010, 8, "M_metal_gun")
    mb.cyl(box_mtx(oc + V((0.0225, 0.226, 0)), (1, 1, 1), Matrix.Rotation(rad(90), 4, "Y")), 0.0062, 0.0056, 0.009,
           8, "M_metal_gun")
    mb.cube(box_mtx(oc + V((0, 0.226, 0.0285)), (0.007, 0.0016, 0.0012)), "M_metal_bright")
    mb.build()
    # tiny blue accent ring around the optic front
    mb = MB("hw.rifle_optic_ring", 0, smooth=40)
    lathe(mb, [(0.0213, 0.2485), (0.0228, 0.2490), (0.0228, 0.2540), (0.0213, 0.2545)], oc, "Y", 16, "M_gun_accent")
    mb.build()

    # ---- sling swivels + slack sling + tri-glide
    front = V((RX - 0.0245, 0.448, 0.4505))
    rear = V((RX - 0.0195, 0.120, 0.433))
    mb = MB("hw.rifle_swivels", 0, smooth=40)
    for c in (front, rear):
        ring = [c + V((0, 0.0075 * math.cos(2 * math.pi * k / 8), 0.0075 * math.sin(2 * math.pi * k / 8) - 0.005))
                for k in range(8)]
        sweep(mb, ring, circle(0.0016, 4), (1, 0, 0), "M_metal_bright", caps=False, loop=True)
    mb.build()
    mb = MB("hw.rifle_sling", 0, smooth=40)
    pts = []
    a, b = front + V((-0.002, 0, -0.012)), rear + V((-0.002, 0, -0.012))
    for i in range(21):
        t = i / 20
        p = a.lerp(b, t)
        sag = 4 * t * (1 - t)
        p = p + V((-0.022 * sag, -0.01 * sag, -0.088 * sag ** 0.9))
        pts.append(p)
    sweep(mb, pts, [(-0.0095, -0.0016), (0.0095, -0.0016), (0.0095, 0.0016), (-0.0095, 0.0016)], (1, 0, 0), "M_strap_tan")
    mb.build()
    mb = MB("hw.rifle_sling_hw", 0, smooth=35)
    for t in (0.12, 0.86):
        i = int(t * 20)
        p0, p1 = pts[i], pts[i + 1]
        tt = (p1 - p0).normalized()
        X = V((1, 0, 0))
        Z = tt.cross(X).normalized()
        mb.cube(frame_mtx(p0, X, tt, Z) @ Matrix.Diagonal((0.006, 0.006, 0.024, 1)), "M_metal_bright")
    mb.build()


def build_rifle_lo():
    mb = MB("hw.rifle.lo", 1, smooth=40)
    mb.cube(box_mtx((RX, 0.13, 0.456), (0.034, 0.06, 0.062)), "M_polymer_gun")
    mb.cube(box_mtx((RX, 0.232, 0.455), (0.033, 0.14, 0.066)), "M_metal_gun")
    mb.cyl(box_mtx((RX, 0.405, RZ), (1, 1, 1), Matrix.Rotation(rad(90), 4, "X")), 0.026, 0.026, 0.23, 8,
           "M_polymer_gun")
    mb.cube(box_mtx((RX, 0.200, 0.395), (0.030, 0.040, 0.078), Matrix.Rotation(rad(-17), 4, "X")), "M_polymer_gun")
    mb.cube(box_mtx((RX, 0.284, 0.387), (0.025, 0.046, 0.092), Matrix.Rotation(rad(12), 4, "X")), "M_gun_accent")
    mb.cube(box_mtx((RX, 0.233, 0.530), (0.040, 0.074, 0.040)), "M_polymer_gun")
    mb.cube(box_mtx((RX, 0.345, 0.494), (0.020, 0.340, 0.020)), "M_metal_gun")  # rail + optic mount
    mb.cyl(box_mtx((RX, 0.580, RZ + 0.006), (1, 1, 1), Matrix.Rotation(rad(90), 4, "X")), 0.0115, 0.0115, 0.12, 6,
           "M_metal_gun")
    mb.cyl(box_mtx((RX, 0.660, RZ + 0.006), (1, 1, 1), Matrix.Rotation(rad(90), 4, "X")), 0.016, 0.016, 0.040, 6,
           "M_metal_gun")
    mb.build()


# =============================================================== finalize
def smooth_by_angle(ob, deg):
    me = ob.data
    bm = bmesh.new()
    bm.from_mesh(me)
    lim = rad(deg)
    for f in bm.faces:
        f.smooth = True
    for e in bm.edges:
        if len(e.link_faces) != 2:
            e.smooth = False
        else:
            e.smooth = e.calc_face_angle(0.0) < lim
    bm.to_mesh(me)
    bm.free()


build_helmet()
build_helmet_lo()
build_rifle()
build_rifle_lo()

for ob in OBJS:
    apply_all(ob)
    smooth_by_angle(ob, ob.get("_smooth", 35))
    del ob["_smooth"]
    uv_world(ob)

if "--nosave" not in sys.argv:
    save_part(OWNER)
else:
    report()

helmet_tris = sum(tris(o) for o in OBJS if o.get("hero_lod") == 0 and (".helmet" in o.name or "goggle" in o.name or "chin" in o.name))
rifle_tris = sum(tris(o) for o in OBJS if o.get("hero_lod") == 0 and ".rifle" in o.name)
print(f"HELMET LOD0 tris {helmet_tris}   RIFLE LOD0 tris {rifle_tris}")

if "--nopreview" not in sys.argv:
    views = sys.argv[sys.argv.index("--views") + 1].split(",") if "--views" in sys.argv else ["front34", "back34", "side"]
    CUSTOM = {
        "helm_back": (V((0.9, -1.3, 1.65)), V((0, -0.01, 0.84))),
        "helm_front": (V((0.55, 1.25, 1.05)), V((0, 0.03, 0.83))),
        "helm_top": (V((0.0, -0.25, 2.2)), V((0, 0.0, 0.85))),
        "rifle_r": (V((1.55, 0.80, 0.62)), V((0.085, 0.39, 0.45))),
        "rifle_l": (V((-1.45, 0.95, 0.58)), V((0.085, 0.39, 0.45))),
        "lo": (V((1.3, 2.0, 0.95)), V((0, 0.05, 0.6))),
    }
    vlist = [CUSTOM.get(v, v) for v in views]
    out = preview("part_helmet_weapon", views=[v for v in views if v in VIEWS] or (), lod=0, lens=100)
    sc = bpy.context.scene
    for v in views:
        if v in CUSTOM:
            res = preview(f"part_helmet_weapon_{v}", views=[CUSTOM[v]], lod=(1 if v == "lo" else 0), lens=100)
