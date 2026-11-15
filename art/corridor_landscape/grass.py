"""Grass / rice field for the corridor-landscape scene (Blender / bpy 5.3).

Every blade is real geometry.  Blade prototypes (folded cross-section with a
mid-rib crease, tapered tip, bend, twist, occasional kinked/broken blades) are
assembled into clump ("tiller") prototypes, some with culms and seed panicles.
Scatter points are generated with numpy (paddy rows, distance LOD, view-cone
culling, noise patches, wind lean) and a Geometry Nodes modifier drops them
onto the terrain (raycast), samples the optional "field_mask" attribute and
instances the prototypes (instances are NOT realized).

    import grass; info = grass.build(terrain_obj=None, camera_location=None)
"""
import math
import time

import bpy
import numpy as np

import common

# ----------------------------------------------------------------------------
# Tunables
# ----------------------------------------------------------------------------
SEED = 7
DENSITY_SCALE = 1.0        # global multiplier on the number of clumps (all LODs)
BLADE_COUNT_SCALE = 1.0    # multiplier on blades per clump prototype

# LOD rings, distances measured from camera_location in the XY plane
NEAR_RADIUS = 75.0         # LOD0: full per-blade clumps up to here
NEAR_BLEND = 18.0          # width of the LOD0 -> LOD1 cross-fade
MID_RADIUS = 210.0         # LOD1: lighter clumps up to here
MID_BLEND = 50.0           # width of the LOD1 -> LOD2 cross-fade
FAR_LIMIT = common.TREELINE_DISTANCE + 70.0   # nothing beyond (hidden by forest)

# paddy rows (LOD0): spacing between rows / between hills along a row (m)
ROW_SPACING = 0.24
HILL_SPACING = 0.135
ROW_ANGLE_DEG = 9.0        # row direction, rotated from +Y towards -X
ROW_JITTER = 0.035         # positional jitter (m) across / along rows
MID_SPACING = 0.36         # LOD1 jittered grid pitch (m)
FAR_SPACING = 0.80         # LOD2 jittered grid pitch (m)

# view cone culling (camera yaw from common), generous margin for reflections
VIEW_MARGIN_DEG = 14.0
NEAR_KEEP_RADIUS = 28.0    # keep everything this close to the camera
BUILDING_CLEARANCE = 0.5   # only scatter where X < GLASS_X - clearance

# tall, seed-bearing foreground plants along the building
TALL_BAND_WIDTH = 11.0     # mean width of the band measured from the glass (m)
TALL_BAND_NOISE = 4.5      # +- variation of that width (m)
TALL_STRAY_FRACTION = 0.012  # stray tall plants inside the field (near LOD)

# look
FIELD_HEIGHT = 0.72        # typical rice canopy height (m)
TALL_HEIGHT = 1.25         # typical height of the tall foreground plants (m)
WIND_DIR_DEG = 250.0       # compass-style direction the wind blows TOWARDS
WIND_LEAN_DEG = 7.0        # mean lean of the clumps with the wind
RANDOM_LEAN_DEG = 5.0
TRANSLUCENCY = 0.42        # mix factor of the translucent lobe (backlit glow)
HUE_SHIFT = 0.0            # global hue offset (+ = greener/bluer, - = yellower)
COLOR_GAIN = 1.0           # global brightness multiplier of the blade albedo

GRASS_COLLECTION = "Grass"
PROTO_COLLECTION = "GrassPrototypes"
FIELD_OBJECT_NAME = "GrassField"
NODE_GROUP_NAME = "GrassScatter"


def tunables():
    return {k: v for k, v in globals().items()
            if k.isupper() and isinstance(v, (int, float, str))}


# ----------------------------------------------------------------------------
# numpy helpers
# ----------------------------------------------------------------------------
def _smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _value_noise(x, y, scale, seed):
    """Bilinear value noise in 0..1 (cheap, vectorised)."""
    rng = np.random.default_rng(seed)
    n = 256
    tab = rng.random((n, n))
    fx, fy = x / scale, y / scale
    ix, iy = np.floor(fx).astype(np.int64), np.floor(fy).astype(np.int64)
    tx, ty = fx - ix, fy - iy
    tx = tx * tx * (3 - 2 * tx)
    ty = ty * ty * (3 - 2 * ty)
    a = tab[ix % n, iy % n]
    b = tab[(ix + 1) % n, iy % n]
    c = tab[ix % n, (iy + 1) % n]
    d = tab[(ix + 1) % n, (iy + 1) % n]
    return (a * (1 - tx) + b * tx) * (1 - ty) + (c * (1 - tx) + d * tx) * ty


def _fbm(x, y, scale, seed, octaves=3):
    tot, amp, norm = 0.0, 1.0, 0.0
    for o in range(octaves):
        tot = tot + amp * _value_noise(x, y, scale / (2 ** o), seed + 17 * o)
        norm += amp
        amp *= 0.5
    return tot / norm


def _quat_mul(a, b):
    aw, ax, ay, az = a[:, 0], a[:, 1], a[:, 2], a[:, 3]
    bw, bx, by, bz = b[:, 0], b[:, 1], b[:, 2], b[:, 3]
    return np.stack([
        aw * bw - ax * bx - ay * by - az * bz,
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw], axis=1)


def _quat_axis_angle(axis_xy_angle, tilt):
    """Quaternion for a tilt about a horizontal axis at azimuth `axis_xy_angle`."""
    h = tilt * 0.5
    s = np.sin(h)
    return np.stack([np.cos(h), np.cos(axis_xy_angle) * s,
                     np.sin(axis_xy_angle) * s, np.zeros_like(h)], axis=1)


# ----------------------------------------------------------------------------
# Blade / clump geometry
# ----------------------------------------------------------------------------
class _MeshBuilder:
    def __init__(self):
        self.verts, self.faces, self.uvs = [], [], []
        self.data, self.mats, self.sharp = [], [], []
        self.nv = 0
        self.blades = 0

    def add(self, verts, faces, uvs, data, mat):
        """verts (n,3); faces list of index tuples; uvs (n,2); data (4,)"""
        off = self.nv
        self.verts.append(np.asarray(verts, dtype=np.float32))
        self.uvs.append(np.asarray(uvs, dtype=np.float32))
        self.data.append(np.tile(np.asarray(data, dtype=np.float32), (len(verts), 1)))
        for f in faces:
            self.faces.append(tuple(i + off for i in f))
            self.mats.append(mat)
        self.nv += len(verts)

    def to_mesh(self, name, materials):
        me = bpy.data.meshes.new(name)
        verts = np.concatenate(self.verts)
        uvs = np.concatenate(self.uvs)
        data = np.concatenate(self.data)
        me.from_pydata(verts.tolist(), [], self.faces)
        for m in materials:
            me.materials.append(m)
        me.polygons.foreach_set("material_index", self.mats)
        me.polygons.foreach_set("use_smooth", [True] * len(self.faces))
        uv = me.uv_layers.new(name="UVMap")
        loop_v = np.zeros(len(me.loops), dtype=np.int32)
        me.loops.foreach_get("vertex_index", loop_v)
        uv.data.foreach_set("uv", uvs[loop_v].ravel())
        att = me.attributes.new("blade_data", 'FLOAT_COLOR', 'POINT')
        att.data.foreach_set("color", data.ravel())
        # mid-rib crease: edges joining two vertices with u == 0.5 are sharp
        ev = np.zeros(len(me.edges) * 2, dtype=np.int32)
        me.edges.foreach_get("vertices", ev)
        ev = ev.reshape(-1, 2)
        u = uvs[:, 0]
        sharp = (np.abs(u[ev[:, 0]] - 0.5) < 1e-4) & (np.abs(u[ev[:, 1]] - 0.5) < 1e-4)
        sa = me.attributes.new("sharp_edge", 'BOOLEAN', 'EDGE')
        sa.data.foreach_set("value", sharp)
        me.update()
        return me


def _blade(rng, length, width, lean0, bend, twist, fold, segs,
           azimuth, base, kink=None, tip_curl=0.0, across=3):
    """One grass blade.  Returns verts, faces, uvs.

    Centre line starts at `base`, leaves at `lean0` rad from vertical towards
    `azimuth` and droops by `bend` rad along its length.  `kink`=(t, angle)
    adds a sharp break.  Cross-section is a V folded about the mid-rib.
    """
    t = np.linspace(0.0, 1.0, segs + 1)
    theta = lean0 + bend * t ** 1.7 + tip_curl * np.clip((t - 0.7) / 0.3, 0, 1) ** 2
    if kink is not None:
        theta = theta + kink[1] * _smoothstep(kink[0] - 0.03, kink[0] + 0.03, t)
    theta = np.clip(theta, -0.3, 2.9)
    ds = length / segs
    # integrate centre line in the (r, z) plane
    tm = 0.5 * (theta[:-1] + theta[1:])
    r = np.concatenate([[0.0], np.cumsum(np.sin(tm) * ds)])
    z = np.concatenate([[0.0], np.cumsum(np.cos(tm) * ds)])
    T = np.stack([np.sin(theta), np.zeros_like(theta), np.cos(theta)], axis=1)
    S = np.tile(np.array([0.0, 1.0, 0.0]), (segs + 1, 1))
    N = np.stack([np.cos(theta), np.zeros_like(theta), -np.sin(theta)], axis=1)
    phi = twist * t
    c, s = np.cos(phi)[:, None], np.sin(phi)[:, None]
    S2 = S * c + N * s
    N2 = N * c - S * s
    # width profile: sheath-narrow base, widest ~30 %, long taper to a point
    prof = np.where(t < 0.3, 0.5 + 0.5 * (t / 0.3) ** 0.8,
                    np.clip((1.0 - t) / 0.7, 0, 1) ** 0.85)
    prof = np.maximum(prof, 0.03)
    w = width * prof
    fa = fold * (1.0 - 0.75 * t)           # fold flattens towards the tip
    C = np.stack([r, np.zeros_like(r), z], axis=1)
    hw = (w * 0.5)[:, None]
    cf, sf = np.cos(fa)[:, None], np.sin(fa)[:, None]
    if across == 3:
        rows = [C - S2 * hw * cf - N2 * hw * sf, C, C + S2 * hw * cf - N2 * hw * sf]
        us = [0.0, 0.5, 1.0]
    else:
        rows = [C - S2 * hw, C + S2 * hw]
        us = [0.0, 1.0]
    k = len(rows)
    verts = np.stack(rows, axis=1).reshape(-1, 3)      # (segs+1)*k
    ca, sa = math.cos(azimuth), math.sin(azimuth)
    x = verts[:, 0] * ca - verts[:, 1] * sa + base[0]
    y = verts[:, 0] * sa + verts[:, 1] * ca + base[1]
    verts = np.stack([x, y, verts[:, 2] + base[2]], axis=1)
    uvs = np.stack([np.tile(us, segs + 1), np.repeat(t, k)], axis=1)
    faces = []
    for i in range(segs):
        for j in range(k - 1):
            a = i * k + j
            faces.append((a, a + 1, a + k + 1, a + k))
    return verts, faces, uvs


def _tube(points, radii, sides=4):
    """Thin tapered tube along a polyline (culms / panicle rachis)."""
    points = np.asarray(points, dtype=np.float64)
    n = len(points)
    tang = np.gradient(points, axis=0)
    tang /= np.linalg.norm(tang, axis=1)[:, None] + 1e-9
    ref = np.array([0.0, 1.0, 0.0])
    a = np.cross(tang, ref)
    a /= np.linalg.norm(a, axis=1)[:, None] + 1e-9
    b = np.cross(tang, a)
    verts, uvs, faces = [], [], []
    for i in range(n):
        for j in range(sides):
            ang = 2 * math.pi * j / sides
            verts.append(points[i] + radii[i] * (math.cos(ang) * a[i] + math.sin(ang) * b[i]))
            uvs.append((j / sides, i / (n - 1) * 0.6 + 0.2))
    for i in range(n - 1):
        for j in range(sides):
            p, q = i * sides + j, i * sides + (j + 1) % sides
            faces.append((p, q, q + sides, p + sides))
    return np.array(verts), faces, np.array(uvs)


def _grain(center, direction, length, radius):
    """Elongated octahedron: one rice grain / spikelet."""
    d = np.asarray(direction, dtype=np.float64)
    d /= np.linalg.norm(d) + 1e-9
    ref = np.array([0.0, 0.0, 1.0]) if abs(d[2]) < 0.9 else np.array([1.0, 0.0, 0.0])
    a = np.cross(d, ref)
    a /= np.linalg.norm(a)
    b = np.cross(d, a)
    c = np.asarray(center)
    mid = c + d * length * 0.45
    verts = np.array([c, mid + a * radius, mid + b * radius * 0.7,
                      mid - a * radius, mid - b * radius * 0.7, c + d * length])
    faces = [(0, 1, 2), (0, 2, 3), (0, 3, 4), (0, 4, 1),
             (5, 2, 1), (5, 3, 2), (5, 4, 3), (5, 1, 4)]
    uvs = np.array([(0.5, 0.0), (0, 0.5), (0.33, 0.5), (0.66, 0.5), (1, 0.5), (0.5, 1.0)])
    return verts, faces, uvs


def _add_culm_with_panicle(mb, rng, base, azimuth, height, lean, grains):
    """Stem ending in a nodding panicle of grains."""
    n = 9
    t = np.linspace(0, 1, n)
    theta = lean * (0.3 + 0.7 * t ** 2)
    ds = height / (n - 1)
    r = np.concatenate([[0], np.cumsum(np.sin(theta[1:]) * ds)])
    z = np.concatenate([[0], np.cumsum(np.cos(theta[1:]) * ds)])
    ca, sa = math.cos(azimuth), math.sin(azimuth)
    pts = np.stack([base[0] + r * ca, base[1] + r * sa, base[2] + z], axis=1)
    rad = np.linspace(0.0028, 0.0012, n)
    v, f, uv = _tube(pts, rad)
    mb.add(v, f, uv, (rng.random(), 0.0, rng.random(), 1.0), 0)
    # panicle rachis: arcs over and nods
    plen = rng.uniform(0.16, 0.26)
    m = 8
    tt = np.linspace(0, 1, m)
    th = theta[-1] + rng.uniform(1.2, 2.3) * tt ** 1.3
    dsp = plen / (m - 1)
    rr = np.concatenate([[0], np.cumsum(np.sin(th[1:]) * dsp)])
    zz = np.concatenate([[0], np.cumsum(np.cos(th[1:]) * dsp)])
    ppts = np.stack([pts[-1, 0] + rr * ca, pts[-1, 1] + rr * sa, pts[-1, 2] + zz], axis=1)
    v, f, uv = _tube(ppts, np.linspace(0.0011, 0.0005, m), sides=3)
    mb.add(v, f, uv, (rng.random(), 0.6, rng.random(), 1.0), 0)
    seed_rand = rng.random()
    for g in range(grains):
        u = rng.uniform(0.08, 1.0)
        idx = u * (m - 1)
        i0 = min(int(idx), m - 2)
        p = ppts[i0] + (ppts[i0 + 1] - ppts[i0]) * (idx - i0)
        tang = ppts[i0 + 1] - ppts[i0]
        tang /= np.linalg.norm(tang)
        side = rng.normal(size=3)
        side -= tang * side.dot(tang)
        side /= np.linalg.norm(side) + 1e-9
        d = tang * 0.75 + side * 0.55 + np.array([0, 0, -0.35])
        off = side * rng.uniform(0.002, 0.012)
        v, f, uv = _grain(p + off, d, rng.uniform(0.007, 0.010), rng.uniform(0.0015, 0.0021))
        mb.add(v, f, uv, (seed_rand, rng.random(), rng.random(), 1.0), 1)


def _make_clump(name, rng, mats, n_blades, height, width, segs, radius,
                across=3, spread=1.0, culms=0, culm_height=1.2, grains=45,
                broken_frac=0.08, dry_frac=0.22):
    mb = _MeshBuilder()
    n_blades = max(3, int(round(n_blades * BLADE_COUNT_SCALE)))
    for i in range(n_blades):
        az = rng.uniform(0, 2 * math.pi)
        rr = radius * math.sqrt(rng.random())
        bang = rng.uniform(0, 2 * math.pi)
        base = (rr * math.cos(bang), rr * math.sin(bang), -0.01)
        # inner blades stand up, outer ones arch outwards
        outer = rng.random() ** 0.8
        length = height * rng.uniform(0.55, 1.12) * (1.0 - 0.15 * outer)
        lean0 = (0.06 + 0.32 * outer) * spread * rng.uniform(0.6, 1.3)
        bend = (0.25 + 1.25 * outer ** 1.5) * spread * rng.uniform(0.5, 1.25)
        kink = None
        if rng.random() < broken_frac:
            kink = (rng.uniform(0.35, 0.75), rng.uniform(0.9, 2.0))
        dry = 0.0
        if rng.random() < dry_frac:
            dry = rng.uniform(0.06, 0.35)
            if rng.random() < 0.12:
                dry = rng.uniform(0.6, 1.0)      # a fully dead, straw leaf
        v, f, uv = _blade(
            rng, length, width * rng.uniform(0.7, 1.2), lean0, bend,
            twist=rng.normal(0, 1.1), fold=rng.uniform(0.35, 0.75), segs=segs,
            azimuth=az, base=base, kink=kink,
            tip_curl=rng.uniform(0.0, 0.7), across=across)
        mb.add(v, f, uv, (rng.random(), dry, rng.random(), 1.0), 0)
        mb.blades += 1
    for i in range(culms):
        az = rng.uniform(0, 2 * math.pi)
        rr = radius * 0.7 * math.sqrt(rng.random())
        bang = rng.uniform(0, 2 * math.pi)
        _add_culm_with_panicle(
            mb, rng, (rr * math.cos(bang), rr * math.sin(bang), -0.01), az,
            culm_height * rng.uniform(0.8, 1.08), rng.uniform(0.1, 0.45), grains)
    me = mb.to_mesh(name, mats)
    ob = bpy.data.objects.new(name, me)
    return ob, mb.blades, len(mb.faces)


# ----------------------------------------------------------------------------
# Materials
# ----------------------------------------------------------------------------
def _mat_new(name):
    old = bpy.data.materials.get(name)
    if old is not None:
        bpy.data.materials.remove(old)
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    return m, nt


def _math(nt, op, a=None, b=None, c=None, clamp=False):
    n = nt.nodes.new("ShaderNodeMath")
    n.operation = op
    n.use_clamp = clamp
    for i, v in enumerate((a, b, c)):
        if v is None:
            continue
        if isinstance(v, (int, float)):
            n.inputs[i].default_value = v
        else:
            nt.links.new(v, n.inputs[i])
    return n.outputs[0]


def _mix_rgb(nt, blend, fac, a, b):
    n = nt.nodes.new("ShaderNodeMix")
    n.data_type = 'RGBA'
    n.blend_type = blend
    n.clamp_factor = True
    for sock, v in ((n.inputs["Factor"], fac), (n.inputs["A"], a), (n.inputs["B"], b)):
        if isinstance(v, (int, float)):
            sock.default_value = v
        elif isinstance(v, tuple):
            sock.default_value = v
        else:
            nt.links.new(v, sock)
    return n.outputs["Result"]


def _instance_inputs(nt):
    """(blade_rand, blade_dry, blade_rand2, inst_rand, inst_patch, inst_dry, mask)"""
    L = nt.links
    bd = nt.nodes.new("ShaderNodeAttribute")
    bd.attribute_type = 'GEOMETRY'
    bd.attribute_name = "blade_data"
    bs = nt.nodes.new("ShaderNodeSeparateColor")
    L.new(bd.outputs["Color"], bs.inputs[0])
    idt = nt.nodes.new("ShaderNodeAttribute")
    idt.attribute_type = 'INSTANCER'
    idt.attribute_name = "inst_data"
    isep = nt.nodes.new("ShaderNodeSeparateColor")
    L.new(idt.outputs["Color"], isep.inputs[0])
    im = nt.nodes.new("ShaderNodeAttribute")
    im.attribute_type = 'INSTANCER'
    im.attribute_name = "inst_mask"
    return (bs.outputs[0], bs.outputs[1], bs.outputs[2],
            isep.outputs[0], isep.outputs[1], isep.outputs[2], im.outputs["Factor"])


def make_blade_material(name="GrassBlade"):
    m, nt = _mat_new(name)
    L = nt.links
    N = nt.nodes
    out = N.new("ShaderNodeOutputMaterial")
    uvn = N.new("ShaderNodeUVMap")
    uvn.uv_map = "UVMap"
    sep = N.new("ShaderNodeSeparateXYZ")
    L.new(uvn.outputs["UV"], sep.inputs[0])
    u, v = sep.outputs["X"], sep.outputs["Y"]
    b_rand, b_dry, b_rand2, i_rand, i_patch, i_dry, i_mask = _instance_inputs(nt)

    # base-to-tip gradient
    ramp = N.new("ShaderNodeValToRGB")
    cr = ramp.color_ramp
    g = COLOR_GAIN
    stops = [(0.00, (0.200, 0.190, 0.045)),   # pale straw sheath at the base
             (0.10, (0.150, 0.250, 0.030)),
             (0.30, (0.115, 0.330, 0.022)),   # deepest green
             (0.65, (0.185, 0.455, 0.030)),   # fresh spring green
             (1.00, (0.300, 0.560, 0.050))]   # light yellow-green tip
    cr.elements[0].position = stops[0][0]
    cr.elements[0].color = tuple(c * g for c in stops[0][1]) + (1,)
    cr.elements[1].position = stops[-1][0]
    cr.elements[1].color = tuple(c * g for c in stops[-1][1]) + (1,)
    for p, c in stops[1:-1]:
        e = cr.elements.new(p)
        e.color = tuple(x * g for x in c) + (1,)
    L.new(v, ramp.inputs["Fac"])
    col = ramp.outputs["Color"]

    # per-blade / per-instance / per-patch hue & value variation
    hue = _math(nt, 'ADD', 0.5 + HUE_SHIFT, _math(nt, 'MULTIPLY', _math(nt, 'SUBTRACT', b_rand, 0.5), 0.050))
    hue = _math(nt, 'ADD', hue, _math(nt, 'MULTIPLY', _math(nt, 'SUBTRACT', i_rand, 0.5), 0.035))
    hue = _math(nt, 'ADD', hue, _math(nt, 'MULTIPLY', _math(nt, 'SUBTRACT', i_patch, 0.5), 0.055))
    hue = _math(nt, 'ADD', hue, _math(nt, 'MULTIPLY', _math(nt, 'SUBTRACT', i_mask, 0.5), 0.030))
    val = _math(nt, 'ADD', 0.80, _math(nt, 'MULTIPLY', b_rand2, 0.42))
    val = _math(nt, 'MULTIPLY', val, _math(nt, 'ADD', 0.88, _math(nt, 'MULTIPLY', i_rand, 0.24)))
    val = _math(nt, 'MULTIPLY', val, _math(nt, 'ADD', 0.90, _math(nt, 'MULTIPLY', i_mask, 0.20)))
    sat = _math(nt, 'ADD', 0.92, _math(nt, 'MULTIPLY', b_rand, 0.16))
    hsv = N.new("ShaderNodeHueSaturation")
    L.new(hue, hsv.inputs["Hue"])
    L.new(sat, hsv.inputs["Saturation"])
    L.new(val, hsv.inputs["Value"])
    L.new(col, hsv.inputs["Color"])
    col = hsv.outputs["Color"]

    # longitudinal veins: parallel ridges across u, plus a pale mid-rib
    vein = _math(nt, 'SINE', _math(nt, 'MULTIPLY', u, 2 * math.pi * 11.0))
    vein01 = _math(nt, 'ADD', _math(nt, 'MULTIPLY', vein, 0.5), 0.5)
    fine = _math(nt, 'SINE', _math(nt, 'MULTIPLY', u, 2 * math.pi * 37.0))
    midrib = _math(nt, 'SUBTRACT', 1.0, _math(nt, 'MULTIPLY', _math(nt, 'ABSOLUTE', _math(nt, 'SUBTRACT', u, 0.5)), 14.0), clamp=True)
    col = _mix_rgb(nt, 'MULTIPLY', _math(nt, 'MULTIPLY', vein01, 0.22), col, (0.62, 0.74, 0.55, 1))
    col = _mix_rgb(nt, 'MIX', _math(nt, 'MULTIPLY', midrib, 0.45), col, (0.36 * g, 0.58 * g, 0.12 * g, 1))

    # fine mottling / speckle (object space of the prototype, stretched along Z)
    tc = N.new("ShaderNodeTexCoord")
    mp = N.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (260.0, 260.0, 45.0)
    L.new(tc.outputs["Object"], mp.inputs["Vector"])
    noise = N.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 1.0
    noise.inputs["Detail"].default_value = 3.0
    L.new(mp.outputs["Vector"], noise.inputs["Vector"])
    nfac = noise.outputs["Fac"] if "Fac" in noise.outputs else noise.outputs[0]
    col = _mix_rgb(nt, 'MULTIPLY', 0.35, col,
                   _mix_rgb(nt, 'MIX', nfac, (0.72, 0.80, 0.62, 1), (1.12, 1.10, 1.0, 1)))

    # dry / yellowed tips: blade_dry = fraction of the blade (from the tip) that is dry
    dry_len = _math(nt, 'ADD', b_dry, _math(nt, 'MULTIPLY', i_dry, 0.10))
    edge = _math(nt, 'ADD', _math(nt, 'SUBTRACT', v, 1.0), dry_len)
    edge = _math(nt, 'ADD', edge, _math(nt, 'MULTIPLY', _math(nt, 'SUBTRACT', nfac, 0.5), 0.10))
    dry_f = _math(nt, 'MULTIPLY', _math(nt, 'DIVIDE', edge, 0.10, clamp=True),
                  _math(nt, 'GREATER_THAN', dry_len, 0.02))
    dry_col = _mix_rgb(nt, 'MIX', nfac, (0.50 * g, 0.40 * g, 0.10 * g, 1), (0.34 * g, 0.22 * g, 0.06 * g, 1))
    yel_f = _math(nt, 'MULTIPLY', _math(nt, 'DIVIDE', _math(nt, 'ADD', edge, 0.14), 0.14, clamp=True),
                  _math(nt, 'GREATER_THAN', dry_len, 0.02))
    col = _mix_rgb(nt, 'MIX', _math(nt, 'MULTIPLY', yel_f, 0.8), col, (0.50 * g, 0.55 * g, 0.06 * g, 1))
    col = _mix_rgb(nt, 'MIX', dry_f, col, dry_col)

    # bump: vein ridges + fine ribs + noise
    h = _math(nt, 'ADD', _math(nt, 'MULTIPLY', vein01, 0.6), _math(nt, 'MULTIPLY', fine, 0.12))
    h = _math(nt, 'ADD', h, _math(nt, 'MULTIPLY', nfac, 0.35))
    h = _math(nt, 'ADD', h, _math(nt, 'MULTIPLY', midrib, 0.8))
    bump = N.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.55
    bump.inputs["Distance"].default_value = 0.0006
    L.new(h, bump.inputs["Height"])

    rough = _math(nt, 'ADD', 0.30, _math(nt, 'MULTIPLY', nfac, 0.22))
    rough = _math(nt, 'ADD', rough, _math(nt, 'MULTIPLY', dry_f, 0.25))
    rough = _math(nt, 'ADD', rough, _math(nt, 'MULTIPLY', b_rand2, 0.10))

    pb = N.new("ShaderNodeBsdfPrincipled")
    L.new(col, pb.inputs["Base Color"])
    L.new(rough, pb.inputs["Roughness"])
    L.new(bump.outputs["Normal"], pb.inputs["Normal"])
    pb.inputs["Specular IOR Level"].default_value = 0.45
    pb.inputs["Sheen Weight"].default_value = 0.08
    pb.inputs["Sheen Roughness"].default_value = 0.4

    # translucency: transmitted light is yellower and more saturated
    tcol = _mix_rgb(nt, 'MULTIPLY', 1.0, col, (1.25, 1.12, 0.55, 1))
    tr = N.new("ShaderNodeBsdfTranslucent")
    L.new(tcol, tr.inputs["Color"])
    L.new(bump.outputs["Normal"], tr.inputs["Normal"])
    mix = N.new("ShaderNodeMixShader")
    tfac = _math(nt, 'MULTIPLY', TRANSLUCENCY, _math(nt, 'SUBTRACT', 1.0, _math(nt, 'MULTIPLY', dry_f, 0.5)))
    L.new(tfac, mix.inputs[0])
    L.new(pb.outputs[0], mix.inputs[1])
    L.new(tr.outputs[0], mix.inputs[2])
    L.new(mix.outputs[0], out.inputs["Surface"])
    return m


def make_seed_material(name="GrassSeed"):
    m, nt = _mat_new(name)
    L = nt.links
    N = nt.nodes
    out = N.new("ShaderNodeOutputMaterial")
    b_rand, b_dry, b_rand2, i_rand, i_patch, i_dry, i_mask = _instance_inputs(nt)
    g = COLOR_GAIN
    ripe = _math(nt, 'ADD', _math(nt, 'MULTIPLY', b_rand, 0.6), _math(nt, 'MULTIPLY', i_rand, 0.4))
    col = _mix_rgb(nt, 'MIX', ripe, (0.34 * g, 0.50 * g, 0.07 * g, 1), (0.62 * g, 0.50 * g, 0.12 * g, 1))
    col = _mix_rgb(nt, 'MULTIPLY', 1.0, col,
                   _mix_rgb(nt, 'MIX', b_rand2, (0.8, 0.8, 0.8, 1), (1.15, 1.15, 1.15, 1)))
    uvn = N.new("ShaderNodeUVMap")
    sep = N.new("ShaderNodeSeparateXYZ")
    L.new(uvn.outputs["UV"], sep.inputs[0])
    ridge = _math(nt, 'SINE', _math(nt, 'MULTIPLY', sep.outputs["X"], 2 * math.pi * 5.0))
    bump = N.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.6
    bump.inputs["Distance"].default_value = 0.0004
    L.new(ridge, bump.inputs["Height"])
    pb = N.new("ShaderNodeBsdfPrincipled")
    L.new(col, pb.inputs["Base Color"])
    pb.inputs["Roughness"].default_value = 0.5
    L.new(bump.outputs["Normal"], pb.inputs["Normal"])
    tr = N.new("ShaderNodeBsdfTranslucent")
    L.new(col, tr.inputs["Color"])
    mix = N.new("ShaderNodeMixShader")
    mix.inputs[0].default_value = 0.2
    L.new(pb.outputs[0], mix.inputs[1])
    L.new(tr.outputs[0], mix.inputs[2])
    L.new(mix.outputs[0], out.inputs["Surface"])
    return m


# ----------------------------------------------------------------------------
# Prototypes
# ----------------------------------------------------------------------------
def _build_prototypes(rng, mats, proto_col):
    """Create clump prototypes.  Returns dict lod -> list of (index, blades)."""
    specs = []   # (sort name, kwargs)
    H = FIELD_HEIGHT
    for i in range(7):       # LOD0 rice hills
        specs.append(("a_rice%d" % i, dict(
            n_blades=rng.integers(40, 56), height=H * rng.uniform(0.9, 1.12),
            width=rng.uniform(0.0085, 0.0125), segs=10, radius=rng.uniform(0.045, 0.075),
            spread=rng.uniform(0.8, 1.2))))
    for i in range(5):       # LOD0 tall seed-bearing plants
        specs.append(("b_tall%d" % i, dict(
            n_blades=rng.integers(30, 42), height=TALL_HEIGHT * rng.uniform(0.72, 0.9),
            width=rng.uniform(0.012, 0.018), segs=11, radius=rng.uniform(0.05, 0.09),
            spread=rng.uniform(0.9, 1.3), culms=int(rng.integers(5, 10)),
            culm_height=TALL_HEIGHT * rng.uniform(0.9, 1.1), grains=int(rng.integers(38, 60)),
            dry_frac=0.4, broken_frac=0.14)))
    for i in range(4):       # LOD1 lighter clumps (fewer, wider blades)
        specs.append(("c_mid%d" % i, dict(
            n_blades=rng.integers(15, 20), height=H * rng.uniform(0.9, 1.1),
            width=rng.uniform(0.022, 0.03), segs=5, radius=0.09,
            spread=rng.uniform(0.9, 1.2), broken_frac=0.05)))
    for i in range(3):       # LOD2 low-poly tufts
        specs.append(("d_far%d" % i, dict(
            n_blades=rng.integers(9, 12), height=H * rng.uniform(0.9, 1.1),
            width=rng.uniform(0.05, 0.07), segs=3, radius=0.16, across=2,
            spread=rng.uniform(1.0, 1.3), broken_frac=0.0, dry_frac=0.15)))
    specs.sort(key=lambda s: s[0])   # Collection Info orders children by name
    lods = {"rice": [], "tall": [], "mid": [], "far": []}
    stats = []
    for idx, (nm, kw) in enumerate(specs):
        name = "GP_%02d_%s" % (idx, nm)
        old = bpy.data.objects.get(name)
        if old is not None:
            bpy.data.objects.remove(old)
        ob, blades, faces = _make_clump(name, rng, mats, **kw)
        proto_col.objects.link(ob)
        key = {"a": "rice", "b": "tall", "c": "mid", "d": "far"}[nm[0]]
        lods[key].append((idx, blades))
        stats.append((name, blades, faces))
    return lods, stats


# ----------------------------------------------------------------------------
# Scatter points
# ----------------------------------------------------------------------------
def _jittered_grid(rng, x0, x1, y0, y1, sx, sy, jitter, angle=0.0, center=(0.0, 0.0)):
    """Jittered lattice covering the bbox, optionally rotated about `center`."""
    if angle != 0.0:
        cx, cy = 0.5 * (x0 + x1), 0.5 * (y0 + y1)
        rad = 0.5 * math.hypot(x1 - x0, y1 - y0)
        gx = np.arange(-rad, rad, sx)
        gy = np.arange(-rad, rad, sy)
    else:
        cx = cy = 0.0
        gx = np.arange(x0, x1, sx)
        gy = np.arange(y0, y1, sy)
    X, Y = np.meshgrid(gx, gy, indexing="ij")
    X = X.ravel() + rng.uniform(-jitter, jitter, X.size) * 1.0
    Y = Y.ravel() + rng.uniform(-jitter, jitter, Y.size) * 1.0
    if angle != 0.0:
        c, s = math.cos(angle), math.sin(angle)
        X, Y = cx + X * c - Y * s, cy + X * s + Y * c
        keep = (X >= x0) & (X < x1) & (Y >= y0) & (Y < y1)
        X, Y = X[keep], Y[keep]
    return X, Y


def _generate_points(rng, cam, lods):
    cx, cy = float(cam[0]), float(cam[1])
    yaw = math.radians(common.CAMERA_YAW_LEFT_DEG)
    fwd = (-math.sin(yaw), math.cos(yaw))
    hfov = 2.0 * math.atan(18.0 / common.CAMERA_LENS_MM)
    half_cone = 0.5 * hfov + math.radians(VIEW_MARGIN_DEG)
    x_max = min(common.GLASS_X - BUILDING_CLEARANCE, common.FIELD_X_MAX)
    dens = math.sqrt(max(DENSITY_SCALE, 1e-3))

    def region_mask(X, Y):
        dx, dy = X - cx, Y - cy
        d = np.hypot(dx, dy)
        ang = np.arccos(np.clip((dx * fwd[0] + dy * fwd[1]) / np.maximum(d, 1e-6), -1, 1))
        ok = (ang < half_cone) | (d < NEAR_KEEP_RADIUS)
        ok &= (X < x_max) & (X > common.FIELD_X_MIN) & (Y > common.FIELD_Y_MIN) & (Y < common.FIELD_Y_MAX)
        ok &= d < FAR_LIMIT
        return ok, d

    def bbox(radius):
        return (max(cx - radius, common.FIELD_X_MIN), min(cx + radius, x_max),
                max(cy - radius, common.FIELD_Y_MIN), min(cy + radius, common.FIELD_Y_MAX))

    out = []
    counts = {}

    # ---------------- LOD0: paddy rows of full clumps --------------------
    X, Y = _jittered_grid(rng, *bbox(NEAR_RADIUS), ROW_SPACING / dens, HILL_SPACING / dens,
                          ROW_JITTER, angle=math.radians(ROW_ANGLE_DEG))
    ok, d = region_mask(X, Y)
    p0 = 1.0 - _smoothstep(NEAR_RADIUS - NEAR_BLEND, NEAR_RADIUS, d)
    ok &= rng.random(X.size) < p0
    # a few missing hills / thin patches
    thin = _fbm(X, Y, 6.0, SEED + 3)
    ok &= rng.random(X.size) < (0.80 + 0.6 * thin).clip(0, 1)
    X, Y, d = X[ok], Y[ok], d[ok]
    # tall band along the building with a ragged edge + strays
    wall_d = common.GLASS_X - X
    edge = TALL_BAND_WIDTH + TALL_BAND_NOISE * (2.0 * _fbm(X, Y, 9.0, SEED + 5) - 1.0)
    p_tall = 1.0 - _smoothstep(edge - 1.8, edge + 1.8, wall_d)
    tall = rng.random(X.size) < np.maximum(p_tall * 0.92, TALL_STRAY_FRACTION)
    # tall plants are bigger: thin them a little so they do not turn into a wall
    drop = tall & (rng.random(X.size) < 0.45)
    X, Y, d, tall = X[~drop], Y[~drop], d[~drop], tall[~drop]
    n = X.size
    rice_ids = np.array([i for i, _ in lods["rice"]])
    tall_ids = np.array([i for i, _ in lods["tall"]])
    proto = np.where(tall, tall_ids[rng.integers(0, len(tall_ids), n)],
                     rice_ids[rng.integers(0, len(rice_ids), n)])
    sxy = np.where(tall, rng.uniform(0.85, 1.25, n), rng.uniform(0.85, 1.2, n))
    sz = np.where(tall, rng.uniform(0.75, 1.15, n), rng.uniform(0.82, 1.15, n))
    out.append((X, Y, d, proto, sxy, sz, np.where(tall, 1, 0)))
    counts["lod0_rice"] = int((~tall).sum())
    counts["lod0_tall"] = int(tall.sum())

    # ---------------- LOD1: lighter clumps --------------------------------
    X, Y = _jittered_grid(rng, *bbox(MID_RADIUS), MID_SPACING / dens, MID_SPACING / dens,
                          MID_SPACING * 0.45)
    ok, d = region_mask(X, Y)
    p1 = _smoothstep(NEAR_RADIUS - NEAR_BLEND, NEAR_RADIUS, d) * \
        (1.0 - _smoothstep(MID_RADIUS - MID_BLEND, MID_RADIUS, d))
    ok &= rng.random(X.size) < p1
    X, Y, d = X[ok], Y[ok], d[ok]
    n = X.size
    ids = np.array([i for i, _ in lods["mid"]])
    grow = 1.0 + 0.55 * _smoothstep(NEAR_RADIUS, MID_RADIUS, d)
    out.append((X, Y, d, ids[rng.integers(0, len(ids), n)],
                rng.uniform(1.25, 1.7, n) * grow, rng.uniform(0.85, 1.15, n), np.full(n, 2)))
    counts["lod1_mid"] = int(n)

    # ---------------- LOD2: sparse low-poly tufts --------------------------
    X, Y = _jittered_grid(rng, *bbox(FAR_LIMIT), FAR_SPACING / dens, FAR_SPACING / dens,
                          FAR_SPACING * 0.48)
    ok, d = region_mask(X, Y)
    ok &= rng.random(X.size) < _smoothstep(MID_RADIUS - MID_BLEND, MID_RADIUS, d)
    X, Y, d = X[ok], Y[ok], d[ok]
    n = X.size
    ids = np.array([i for i, _ in lods["far"]])
    grow = 1.0 + 0.5 * _smoothstep(MID_RADIUS, FAR_LIMIT, d)
    out.append((X, Y, d, ids[rng.integers(0, len(ids), n)],
                rng.uniform(1.9, 2.6, n) * grow, rng.uniform(0.9, 1.2, n), np.full(n, 3)))
    counts["lod2_far"] = int(n)

    X = np.concatenate([o[0] for o in out])
    Y = np.concatenate([o[1] for o in out])
    proto = np.concatenate([o[3] for o in out]).astype(np.int32)
    sxy = np.concatenate([o[4] for o in out])
    sz = np.concatenate([o[5] for o in out])
    kind = np.concatenate([o[6] for o in out])
    n = X.size

    # patch variation: growth (height) and hue patches, shared by all LODs
    growth = _fbm(X, Y, 38.0, SEED + 11)
    growth2 = _fbm(X, Y, 7.0, SEED + 12)
    patch = _fbm(X, Y, 55.0, SEED + 13, octaves=4)
    sz = sz * (0.86 + 0.22 * growth + 0.12 * growth2)
    sxy = sxy * (0.94 + 0.12 * growth)
    scale = np.stack([sxy, sxy, sz], axis=1).astype(np.float32)

    # rotation: random yaw, small random lean, consistent wind lean with gusts
    yawq = rng.uniform(0, 2 * math.pi, n)
    q_yaw = np.stack([np.cos(yawq / 2), np.zeros(n), np.zeros(n), np.sin(yawq / 2)], axis=1)
    q_rand = _quat_axis_angle(rng.uniform(0, 2 * math.pi, n),
                              np.radians(RANDOM_LEAN_DEG) * rng.random(n))
    wind_az = math.radians(90.0 - WIND_DIR_DEG)          # compass -> math angle
    gust = _fbm(X + 0.6 * Y, Y, 14.0, SEED + 21)
    wtilt = np.radians(WIND_LEAN_DEG) * (0.35 + 1.3 * gust)
    wdir = wind_az + (rng.random(n) - 0.5) * 0.5
    q_wind = _quat_axis_angle(wdir + math.pi / 2, wtilt)   # axis = z x wind
    rot = _quat_mul(q_wind, _quat_mul(q_rand, q_yaw)).astype(np.float32)

    dry = np.clip(_fbm(X, Y, 21.0, SEED + 31) * 1.3 - 0.45, 0, 1) * rng.random(n)
    dry = np.where(kind == 1, np.clip(dry + 0.35, 0, 1), dry)
    inst = np.stack([rng.random(n), patch, dry, np.ones(n)], axis=1).astype(np.float32)
    pos = np.stack([X, Y, np.full(n, common.GROUND_Z)], axis=1).astype(np.float32)
    return pos, proto, scale, rot, inst, counts


# ----------------------------------------------------------------------------
# Geometry nodes
# ----------------------------------------------------------------------------
def _build_node_group(terrain_obj, proto_col):
    old = bpy.data.node_groups.get(NODE_GROUP_NAME)
    if old is not None:
        bpy.data.node_groups.remove(old)
    ng = bpy.data.node_groups.new(NODE_GROUP_NAME, "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket("Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')
    N, L = ng.nodes, ng.links
    gin = N.new("NodeGroupInput")
    gout = N.new("NodeGroupOutput")
    geo = gin.outputs[0]

    def named(name, dtype):
        n = N.new("GeometryNodeInputNamedAttribute")
        n.data_type = dtype
        n.inputs["Name"].default_value = name
        return n

    mask_val = None
    if terrain_obj is not None:
        oi = N.new("GeometryNodeObjectInfo")
        oi.transform_space = 'RELATIVE'
        oi.inputs["Object"].default_value = terrain_obj
        pos = N.new("GeometryNodeInputPosition")
        sep = N.new("ShaderNodeSeparateXYZ")
        L.new(pos.outputs[0], sep.inputs[0])
        src = N.new("ShaderNodeCombineXYZ")
        L.new(sep.outputs["X"], src.inputs["X"])
        L.new(sep.outputs["Y"], src.inputs["Y"])
        src.inputs["Z"].default_value = common.GROUND_Z + 1000.0
        fm = named("field_mask", 'FLOAT')
        ray = N.new("GeometryNodeRaycast")
        ray.data_type = 'FLOAT'
        L.new(oi.outputs["Geometry"], ray.inputs["Target Geometry"])
        L.new(fm.outputs["Attribute"], ray.inputs["Attribute"])
        L.new(src.outputs[0], ray.inputs["Source Position"])
        ray.inputs["Ray Direction"].default_value = (0.0, 0.0, -1.0)
        ray.inputs["Ray Length"].default_value = 3000.0
        # optional attribute: fall back to 0.5 when the terrain has no field_mask.
        # "Exists" must be evaluated on the terrain, so sample it through a 2nd ray.
        ray2 = N.new("GeometryNodeRaycast")
        ray2.data_type = 'FLOAT'
        ex = N.new("GeometryNodeSwitch")
        ex.input_type = 'FLOAT'
        L.new(fm.outputs["Exists"], ex.inputs["Switch"])
        ex.inputs["False"].default_value = 0.0
        ex.inputs["True"].default_value = 1.0
        L.new(oi.outputs["Geometry"], ray2.inputs["Target Geometry"])
        L.new(ex.outputs[0], ray2.inputs["Attribute"])
        L.new(src.outputs[0], ray2.inputs["Source Position"])
        ray2.inputs["Ray Direction"].default_value = (0.0, 0.0, -1.0)
        ray2.inputs["Ray Length"].default_value = 3000.0
        has = N.new("ShaderNodeMath")
        has.operation = 'GREATER_THAN'
        L.new(ray2.outputs["Attribute"], has.inputs[0])
        has.inputs[1].default_value = 0.5
        sw = N.new("GeometryNodeSwitch")
        sw.input_type = 'FLOAT'
        L.new(has.outputs[0], sw.inputs["Switch"])
        sw.inputs["False"].default_value = 0.5
        L.new(ray.outputs["Attribute"], sw.inputs["True"])
        mask_val = sw.outputs[0]

        setp = N.new("GeometryNodeSetPosition")
        L.new(geo, setp.inputs["Geometry"])
        L.new(ray.outputs["Is Hit"], setp.inputs["Selection"])
        L.new(ray.outputs["Hit Position"], setp.inputs["Position"])
        store = N.new("GeometryNodeStoreNamedAttribute")
        store.data_type = 'FLOAT'
        store.domain = 'POINT'
        store.inputs["Name"].default_value = "inst_mask"
        L.new(setp.outputs[0], store.inputs["Geometry"])
        L.new(mask_val, store.inputs["Value"])
        # remove points that are not above the terrain (captured before moving)
        hit_store = N.new("GeometryNodeStoreNamedAttribute")
        hit_store.data_type = 'BOOLEAN'
        hit_store.domain = 'POINT'
        hit_store.inputs["Name"].default_value = "_hit"
        L.new(geo, hit_store.inputs["Geometry"])
        L.new(ray.outputs["Is Hit"], hit_store.inputs["Value"])
        L.new(hit_store.outputs[0], setp.inputs["Geometry"])
        hit = named("_hit", 'BOOLEAN')
        inv = N.new("FunctionNodeBooleanMath")
        inv.operation = 'NOT'
        L.new(hit.outputs["Attribute"], inv.inputs[0])
        dele = N.new("GeometryNodeDeleteGeometry")
        dele.domain = 'POINT'
        L.new(store.outputs[0], dele.inputs["Geometry"])
        L.new(inv.outputs[0], dele.inputs["Selection"])
        geo = dele.outputs[0]
    else:
        store = N.new("GeometryNodeStoreNamedAttribute")
        store.data_type = 'FLOAT'
        store.domain = 'POINT'
        store.inputs["Name"].default_value = "inst_mask"
        store.inputs["Value"].default_value = 0.5
        L.new(geo, store.inputs["Geometry"])
        geo = store.outputs[0]

    ci = N.new("GeometryNodeCollectionInfo")
    ci.transform_space = 'ORIGINAL'
    ci.inputs["Collection"].default_value = proto_col
    ci.inputs["Separate Children"].default_value = True
    ci.inputs["Reset Children"].default_value = True

    # field_mask (0..1) also modulates plant height a little
    scl = named("scale", 'FLOAT_VECTOR')
    mk = named("inst_mask", 'FLOAT')
    hmul = N.new("ShaderNodeMath")
    hmul.operation = 'MULTIPLY_ADD'
    L.new(mk.outputs["Attribute"], hmul.inputs[0])
    hmul.inputs[1].default_value = 0.24
    hmul.inputs[2].default_value = 0.88
    vs = N.new("ShaderNodeVectorMath")
    vs.operation = 'SCALE'
    L.new(scl.outputs["Attribute"], vs.inputs[0])
    L.new(hmul.outputs[0], vs.inputs["Scale"])

    iop = N.new("GeometryNodeInstanceOnPoints")
    L.new(geo, iop.inputs["Points"])
    L.new(ci.outputs[0], iop.inputs["Instance"])
    iop.inputs["Pick Instance"].default_value = True
    L.new(named("proto", 'INT').outputs["Attribute"], iop.inputs["Instance Index"])
    L.new(named("rot", 'QUATERNION').outputs["Attribute"], iop.inputs["Rotation"])
    L.new(vs.outputs[0], iop.inputs["Scale"])
    L.new(iop.outputs[0], gout.inputs[0])
    return ng


# ----------------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------------
def build(terrain_obj=None, camera_location=None):
    """Add the grass field to the current scene.

    terrain_obj      mesh to scatter on (default bpy.data.objects["Terrain"];
                     if missing the grass is placed flat at common.GROUND_Z)
    camera_location  LOD / culling centre (default common.CAMERA_LOCATION)
    Returns a dict with objects, collections, materials, instance counts, tunables.
    """
    t0 = time.time()
    rng = np.random.default_rng(SEED)
    if terrain_obj is None:
        terrain_obj = bpy.data.objects.get(common.TERRAIN_OBJECT_NAME)
    cam = tuple(camera_location) if camera_location is not None else common.CAMERA_LOCATION

    col = common.get_collection(GRASS_COLLECTION)
    proto_col = common.get_collection(PROTO_COLLECTION)
    proto_col.hide_render = True       # originals never render, only instances
    proto_col.hide_viewport = True

    # remove a previous build of ours (only our own data)
    for ob in list(proto_col.objects):
        me = ob.data
        bpy.data.objects.remove(ob)
        if me is not None and me.users == 0:
            bpy.data.meshes.remove(me)
    old = bpy.data.objects.get(FIELD_OBJECT_NAME)
    if old is not None:
        me = old.data
        bpy.data.objects.remove(old)
        if me is not None and me.users == 0:
            bpy.data.meshes.remove(me)

    mats = [make_blade_material(), make_seed_material()]
    lods, proto_stats = _build_prototypes(rng, mats, proto_col)

    pos, proto, scale, rot, inst, counts = _generate_points(rng, cam, lods)
    n = len(pos)
    me = bpy.data.meshes.new(FIELD_OBJECT_NAME)
    me.vertices.add(n)
    me.vertices.foreach_set("co", pos.ravel())
    me.attributes.new("proto", 'INT', 'POINT').data.foreach_set("value", proto)
    me.attributes.new("scale", 'FLOAT_VECTOR', 'POINT').data.foreach_set("vector", scale.ravel())
    me.attributes.new("rot", 'QUATERNION', 'POINT').data.foreach_set("value", rot.ravel())
    me.attributes.new("inst_data", 'FLOAT_COLOR', 'POINT').data.foreach_set("color", inst.ravel())
    me.update()
    field = bpy.data.objects.new(FIELD_OBJECT_NAME, me)
    col.objects.link(field)
    # materials on the instancer too, so slots survive if someone realizes it
    for m in mats:
        me.materials.append(m)

    ng = _build_node_group(terrain_obj, proto_col)
    mod = field.modifiers.new("GrassScatter", 'NODES')
    mod.node_group = ng

    blades_per = {}
    for key in lods:
        for idx, b in lods[key]:
            blades_per[idx] = b
    blade_total = int(sum(blades_per[int(i)] * c for i, c in
                          zip(*np.unique(proto, return_counts=True))))
    counts["total"] = int(n)
    info = {
        "objects": [field],
        "collection": col,
        "prototype_collection": proto_col,
        "prototypes": proto_stats,          # (name, blades, faces)
        "materials": mats,
        "node_group": ng,
        "terrain": terrain_obj,
        "instance_counts": counts,
        "blade_count_estimate": blade_total,
        "tunables": tunables(),
        "build_seconds": time.time() - t0,
    }
    print("[grass] instances %s  blades~%.1fM  prototypes %d  build %.1fs" % (
        counts, blade_total / 1e6, len(proto_stats), info["build_seconds"]))
    return info


if __name__ == "__main__":
    build()
