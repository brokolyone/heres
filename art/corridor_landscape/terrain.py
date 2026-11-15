"""Terrain + distant vegetation for the corridor-landscape scene (bpy 5.3).

build() ADDS (never resets):
  collection "Terrain"        : "Terrain" (fine graded field mesh), "FarGround", "DistantHills"
  collection "Trees"          : "TreeLine" (GN instancer, forest belt), "MidVegetation" (GN instancer)
  collection "TreePrototypes" : real 3D tree / conifer / bush meshes (hidden from render, instanced)

Point attributes on the Terrain mesh (FLOAT, POINT):
  field_mask    0..1  large soft patches (vegetation variation)
  grass_density 0..1  0 on apron strip / track / ditch / forest floor, lower on bunds
  forest_mask   0..1  1 under the forest belt
"""
import math
import numpy as np
import bpy

import common

# ----------------------------------------------------------------------------
# tunables
# ----------------------------------------------------------------------------
SEED = 7
HAZE_DISTANCE = 1500.0      # aerial-perspective e-folding distance (m); <=0 disables fake haze
HAZE_COLOR = (0.50, 0.63, 0.82, 1.0)
NEAR_SOIL_RANGE = (6.0, 55.0)   # camera distance over which ground goes from soil look -> canopy look

# paddy layout (shared by mesh heights and ground shader)
PLOT_ANGLE = math.radians(14.0)
PLOT_LU, PLOT_LV = 110.0, 45.0     # plot size along u (~X) and v (~Y)
PLOT_U0, PLOT_V0 = -78.0, 95.0     # an edge passes through u=U0 / v=V0
TRACK_HALF_W = 1.3                 # dirt track along the line u = PLOT_U0
DITCH_HALF_W = 0.8                 # irrigation ditch along the line v = PLOT_V0
BUND_H = 0.22

BELT_THETA = (math.radians(-35.0), math.radians(215.0))   # angle from +Y towards -X
BELT_DEPTH = 70.0

_C, _S = math.cos(PLOT_ANGLE), math.sin(PLOT_ANGLE)


# ----------------------------------------------------------------------------
# numpy helpers
# ----------------------------------------------------------------------------
def _smooth(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _snoise(x, y, wavelength, seed, n=7):
    """Cheap smooth pseudo-noise (sum of random plane waves), approx. range [-1, 1]."""
    rng = np.random.default_rng(seed)
    out = np.zeros_like(x, dtype=np.float64)
    for _ in range(n):
        a = rng.uniform(0, 2 * math.pi)
        k = 2 * math.pi / (wavelength * rng.uniform(0.6, 1.6))
        out += np.sin((x * math.cos(a) + y * math.sin(a)) * k + rng.uniform(0, 2 * math.pi))
    return out / (n * 0.5)


def _hash2(i, j):
    v = np.sin(i * 127.1 + j * 311.7) * 43758.5453
    return v - np.floor(v)


def forest_front_radius(theta):
    return (common.TREELINE_DISTANCE + 30.0 * np.sin(2.3 * theta + 1.0)
            + 18.0 * np.sin(5.1 * theta + 2.2) + 8.0 * np.sin(11.0 * theta))


def _plot_coords(x, y):
    u = x * _C + y * _S - PLOT_U0
    v = -x * _S + y * _C - PLOT_V0
    return u, v


def field_functions(x, y):
    """Returns (height offset from GROUND_Z, field_mask, grass_density, forest_mask)."""
    u, v = _plot_coords(x, y)
    iu, iv = np.floor(u / PLOT_LU), np.floor(v / PLOT_LV)
    du = (0.5 - np.abs(u / PLOT_LU - iu - 0.5)) * PLOT_LU
    dv = (0.5 - np.abs(v / PLOT_LV - iv - 0.5)) * PLOT_LV
    dedge = np.minimum(du, dv)
    cell = _hash2(iu, iv)

    h = 0.10 * _snoise(x, y, 220.0, SEED + 1) + 0.035 * _snoise(x, y, 35.0, SEED + 2)
    h += (cell - 0.5) * 0.10                       # paddies sit at slightly different levels
    bund = 1.0 - _smooth(0.30, 1.25, dedge)
    h += BUND_H * bund
    h += 0.02 * _snoise(x, y, 3.0, SEED + 3)       # micro relief

    dtrack = np.abs(u)                              # track on the line u = 0
    track = 1.0 - _smooth(TRACK_HALF_W, TRACK_HALF_W + 0.9, dtrack)
    h = h * (1 - track) + track * (0.12 + 0.03 * _snoise(x, y, 6.0, SEED + 4))
    dditch = np.abs(v)                              # ditch on the line v = 0
    ditch = (1.0 - _smooth(DITCH_HALF_W * 0.4, DITCH_HALF_W + 0.6, dditch)) * (1 - track)
    h -= 0.65 * ditch

    # flat strip next to the building, fade to exact GROUND_Z at the field borders
    dbuild = common.FIELD_X_MAX - x
    h *= _smooth(2.5, 9.0, dbuild)
    dborder = np.minimum.reduce([x - common.FIELD_X_MIN, y - common.FIELD_Y_MIN,
                                 common.FIELD_Y_MAX - y])
    h *= _smooth(0.0, 25.0, dborder)

    fm = 0.5 + 0.42 * _snoise(x, y, 140.0, SEED + 5) + 0.18 * _snoise(x, y, 45.0, SEED + 6)
    fm += (cell - 0.5) * 0.35
    fm = np.clip(fm, 0.0, 1.0)

    r = np.hypot(x, y)
    theta = np.arctan2(-x, y)
    rf = forest_front_radius(theta)
    forest = _smooth(rf - 7.0, rf + 3.0, r)

    dens = np.ones_like(h)
    dens *= 1.0 - 0.45 * bund
    dens *= 1.0 - track
    dens *= 1.0 - _smooth(0.0, 0.5, ditch)
    dens *= _smooth(0.6, 2.2, dbuild)
    dens *= 1.0 - forest
    return h, fm, np.clip(dens, 0, 1), forest


def terrain_height(x, y):
    """World Z of the field at (x, y) (scalars or arrays)."""
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    return common.GROUND_Z + field_functions(x, y)[0]


# ----------------------------------------------------------------------------
# node helper
# ----------------------------------------------------------------------------
class NB:
    def __init__(self, nt):
        self.nt = nt

    def node(self, kind, **props):
        n = self.nt.nodes.new(kind)
        for k, v in props.items():
            setattr(n, k, v)
        return n

    def link(self, a, b):
        self.nt.links.new(a, b)

    def set(self, sock, val):
        if isinstance(val, bpy.types.NodeSocket):
            self.nt.links.new(val, sock)
        elif val is not None:
            sock.default_value = val

    def math(self, op, a, b=None, c=None, clamp=False):
        n = self.node('ShaderNodeMath', operation=op, use_clamp=clamp)
        self.set(n.inputs[0], a)
        self.set(n.inputs[1], b)
        self.set(n.inputs[2], c)
        return n.outputs[0]

    def smooth(self, val, e0, e1, to0=0.0, to1=1.0):
        n = self.node('ShaderNodeMapRange', interpolation_type='SMOOTHSTEP')
        self.set(n.inputs['Value'], val)
        n.inputs['From Min'].default_value = e0
        n.inputs['From Max'].default_value = e1
        n.inputs['To Min'].default_value = to0
        n.inputs['To Max'].default_value = to1
        return n.outputs['Result']

    def mixcol(self, fac, a, b, blend='MIX'):
        n = self.node('ShaderNodeMix', data_type='RGBA', blend_type=blend)
        n.clamp_factor = True
        self.set(n.inputs[0], fac)
        self.set(n.inputs[6], a)
        self.set(n.inputs[7], b)
        return n.outputs[2]

    def noise(self, vec, scale, detail=2.0, rough=0.5, out='Factor'):
        n = self.node('ShaderNodeTexNoise')
        self.set(n.inputs['Vector'], vec)
        n.inputs['Scale'].default_value = scale
        n.inputs['Detail'].default_value = detail
        n.inputs['Roughness'].default_value = rough
        return n.outputs[out]

    def haze(self, shader):
        """Cheap aerial perspective: blend towards a lit bluish diffuse with camera distance."""
        if HAZE_DISTANCE <= 0:
            return shader
        cam = self.node('ShaderNodeCameraData')
        e = self.math('POWER', math.e, self.math('MULTIPLY', cam.outputs['View Distance'],
                                                 -1.0 / HAZE_DISTANCE))
        fac = self.math('SUBTRACT', 1.0, e, clamp=True)
        d = self.node('ShaderNodeBsdfDiffuse')
        d.inputs['Color'].default_value = HAZE_COLOR
        # haze should not shade like the surface: use the direction to the viewer as normal
        geo = self.node('ShaderNodeNewGeometry')
        up = self.node('ShaderNodeVectorMath', operation='ADD')
        self.link(geo.outputs['Incoming'], up.inputs[0])
        up.inputs[1].default_value = (0.0, 0.0, 1.5)
        self.link(up.outputs[0], d.inputs['Normal'])
        m = self.node('ShaderNodeMixShader')
        self.link(fac, m.inputs[0])
        self.link(shader, m.inputs[1])
        self.link(d.outputs[0], m.inputs[2])
        return m.outputs[0]


def _new_material(name):
    old = bpy.data.materials.get(name)
    if old is not None:
        bpy.data.materials.remove(old)
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    return mat, NB(nt), out


# ----------------------------------------------------------------------------
# materials
# ----------------------------------------------------------------------------
def make_ground_material():
    mat, nb, out = _new_material("TerrainGround")
    geo = nb.node('ShaderNodeNewGeometry')
    sep = nb.node('ShaderNodeSeparateXYZ')
    nb.link(geo.outputs['Position'], sep.inputs[0])
    x, y = sep.outputs[0], sep.outputs[1]
    u = nb.math('SUBTRACT', nb.math('ADD', nb.math('MULTIPLY', x, _C), nb.math('MULTIPLY', y, _S)), PLOT_U0)
    v = nb.math('SUBTRACT', nb.math('ADD', nb.math('MULTIPLY', x, -_S), nb.math('MULTIPLY', y, _C)), PLOT_V0)
    un, vn = nb.math('DIVIDE', u, PLOT_LU), nb.math('DIVIDE', v, PLOT_LV)
    iu, iv = nb.math('FLOOR', un), nb.math('FLOOR', vn)
    du = nb.math('MULTIPLY', nb.math('SUBTRACT', 0.5, nb.math('ABSOLUTE', nb.math('SUBTRACT', nb.math('FRACT', un), 0.5))), PLOT_LU)
    dv = nb.math('MULTIPLY', nb.math('SUBTRACT', 0.5, nb.math('ABSOLUTE', nb.math('SUBTRACT', nb.math('FRACT', vn), 0.5))), PLOT_LV)
    dedge = nb.math('MINIMUM', du, dv)
    bund = nb.smooth(dedge, 0.35, 1.5, 1.0, 0.0)
    cellv = nb.node('ShaderNodeCombineXYZ')
    nb.link(iu, cellv.inputs[0]); nb.link(iv, cellv.inputs[1])
    wn = nb.node('ShaderNodeTexWhiteNoise', noise_dimensions='2D')
    nb.link(cellv.outputs[0], wn.inputs['Vector'])
    cell = wn.outputs['Value']
    sepc = nb.node('ShaderNodeSeparateColor')
    nb.link(wn.outputs['Color'], sepc.inputs[0])
    cell2 = sepc.outputs[1]

    # row-aligned coordinates (rows run along u)
    uv = nb.node('ShaderNodeCombineXYZ')
    nb.link(u, uv.inputs[0]); nb.link(v, uv.inputs[1])

    attr = nb.node('ShaderNodeAttribute', attribute_name="field_mask")
    fattr = nb.node('ShaderNodeAttribute', attribute_name="forest_mask")
    n_big = nb.noise(geo.outputs['Position'], 0.011, 3.0, 0.55)
    n_med = nb.noise(geo.outputs['Position'], 0.09, 3.0, 0.6)
    patch = nb.math('ADD', nb.math('MULTIPLY', attr.outputs['Factor'], 0.55),
                    nb.math('MULTIPLY', n_big, 0.55))
    patch = nb.math('ADD', patch, nb.math('MULTIPLY', nb.math('SUBTRACT', cell, 0.5), 0.45))
    patch = nb.math('ADD', patch, nb.math('MULTIPLY', nb.math('SUBTRACT', n_med, 0.5), 0.25), clamp=True)

    # canopy colours (linear): bright yellow-green rice -> deeper green
    ramp = nb.node('ShaderNodeValToRGB')
    nb.link(patch, ramp.inputs[0])
    els = ramp.color_ramp.elements
    els[0].position, els[0].color = 0.15, (0.105, 0.300, 0.022, 1)
    els[1].position, els[1].color = 0.85, (0.300, 0.470, 0.040, 1)
    e = els.new(0.5); e.color = (0.185, 0.400, 0.030, 1)
    canopy = ramp.outputs[0]

    # fine anisotropic canopy texture (stretched along rows) + clumps
    mp = nb.node('ShaderNodeMapping')
    mp.inputs['Scale'].default_value = (0.35, 2.6, 1.0)
    nb.link(uv.outputs[0], mp.inputs['Vector'])
    n_rows = nb.noise(mp.outputs[0], 3.0, 4.0, 0.65)
    n_clump = nb.noise(geo.outputs['Position'], 0.9, 3.0, 0.6)
    tex = nb.math('ADD', nb.math('MULTIPLY', n_rows, 0.6), nb.math('MULTIPLY', n_clump, 0.4))
    shade = nb.smooth(tex, 0.25, 0.75, 0.62, 1.22)
    canopy = nb.mixcol(1.0, canopy, shade, 'MULTIPLY')
    # some plots are riper (yellower)
    ripe = nb.smooth(cell2, 0.72, 0.95, 0.0, 0.35)
    canopy = nb.mixcol(ripe, canopy, (0.36, 0.42, 0.045, 1))

    # soil / thatch look near the camera where real blades stand on it
    n_soil = nb.noise(geo.outputs['Position'], 7.0, 5.0, 0.7)
    soil = nb.mixcol(n_soil, (0.020, 0.014, 0.008, 1), (0.055, 0.040, 0.022, 1))
    soilgreen = nb.mixcol(nb.smooth(n_clump, 0.35, 0.7), soil, (0.045, 0.110, 0.015, 1))
    cam = nb.node('ShaderNodeCameraData')
    nearf = nb.smooth(cam.outputs['View Distance'], NEAR_SOIL_RANGE[0], NEAR_SOIL_RANGE[1], 0.85, 0.0)
    col = nb.mixcol(nearf, canopy, soilgreen)

    # bunds: drier, grassy ridges
    col = nb.mixcol(nb.math('MULTIPLY', bund, 0.55), col, (0.21, 0.30, 0.055, 1))

    # dirt track along u = 0 (two ruts, grassy centre)
    au = nb.math('ABSOLUTE', u)
    track = nb.smooth(au, TRACK_HALF_W, TRACK_HALF_W + 0.9, 1.0, 0.0)
    rut = nb.smooth(nb.math('ABSOLUTE', nb.math('SUBTRACT', au, 0.75)), 0.2, 0.55, 1.0, 0.25)
    dirt = nb.mixcol(n_soil, (0.16, 0.115, 0.07, 1), (0.27, 0.21, 0.13, 1))
    col = nb.mixcol(nb.math('MULTIPLY', track, rut), col, dirt)

    # ditch along v = 0 (dark water)
    av = nb.math('ABSOLUTE', v)
    ditch = nb.math('MULTIPLY', nb.smooth(av, DITCH_HALF_W * 0.5, DITCH_HALF_W + 0.3, 1.0, 0.0),
                    nb.math('SUBTRACT', 1.0, track))
    col = nb.mixcol(ditch, col, (0.012, 0.020, 0.016, 1))

    # forest floor
    col = nb.mixcol(fattr.outputs['Factor'], col, (0.012, 0.022, 0.008, 1))

    # apron strip right at the building: gravel
    apron = nb.smooth(x, common.FIELD_X_MAX - 1.6, common.FIELD_X_MAX - 0.5)
    n_grav = nb.noise(geo.outputs['Position'], 60.0, 2.0, 0.6)
    col = nb.mixcol(apron, col, nb.mixcol(n_grav, (0.16, 0.15, 0.135, 1), (0.36, 0.34, 0.31, 1)))

    bsdf = nb.node('ShaderNodeBsdfPrincipled')
    nb.link(col, bsdf.inputs['Base Color'])
    rough = nb.math('SUBTRACT', 0.62, nb.math('MULTIPLY', ditch, 0.55))
    nb.link(rough, bsdf.inputs['Roughness'])
    bsdf.inputs['Specular IOR Level'].default_value = 0.35
    bsdf.inputs['Sheen Weight'].default_value = 0.25
    bsdf.inputs['Sheen Roughness'].default_value = 0.5
    bsdf.inputs['Sheen Tint'].default_value = (0.6, 0.9, 0.3, 1)

    bump = nb.node('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.55
    bump.inputs['Distance'].default_value = 0.12
    hgt = nb.math('MULTIPLY', nb.math('ADD', tex, nb.math('MULTIPLY', n_soil, 0.25)),
                  nb.math('SUBTRACT', 1.0, ditch))
    nb.link(hgt, bump.inputs['Height'])
    nb.link(bump.outputs[0], bsdf.inputs['Normal'])
    nb.link(nb.haze(bsdf.outputs[0]), out.inputs['Surface'])
    return mat


def make_leaf_material(name, base, light, trans=0.32):
    mat, nb, out = _new_material(name)
    geo = nb.node('ShaderNodeNewGeometry')
    oi = nb.node('ShaderNodeObjectInfo')
    wn = nb.node('ShaderNodeTexWhiteNoise', noise_dimensions='1D')
    nb.link(oi.outputs['Random'], wn.inputs['W'])
    sepc = nb.node('ShaderNodeSeparateColor')
    nb.link(wn.outputs['Color'], sepc.inputs[0])
    r1, r2, r3 = sepc.outputs[0], sepc.outputs[1], sepc.outputs[2]
    leaf_r = geo.outputs['Random Per Island']
    # per-tree colour: mix base<->light, then hue/sat/value jitter
    c = nb.mixcol(nb.math('ADD', nb.math('MULTIPLY', r1, 0.55), nb.math('MULTIPLY', leaf_r, 0.3)), base, light)
    hsv = nb.node('ShaderNodeHueSaturation')
    nb.set(hsv.inputs['Hue'], nb.math('ADD', 0.47, nb.math('MULTIPLY', r2, 0.06)))
    nb.set(hsv.inputs['Saturation'], nb.math('ADD', 0.8, nb.math('MULTIPLY', r3, 0.35)))
    nb.set(hsv.inputs['Value'], nb.math('ADD', 0.7, nb.math('MULTIPLY', leaf_r, 0.6)))
    nb.link(c, hsv.inputs['Color'])
    col = hsv.outputs[0]
    bsdf = nb.node('ShaderNodeBsdfPrincipled')
    nb.link(col, bsdf.inputs['Base Color'])
    bsdf.inputs['Roughness'].default_value = 0.42
    bsdf.inputs['Specular IOR Level'].default_value = 0.4
    tr = nb.node('ShaderNodeBsdfTranslucent')
    tcol = nb.mixcol(1.0, col, (1.6, 1.9, 0.7, 1), 'MULTIPLY')
    nb.link(tcol, tr.inputs['Color'])
    mix = nb.node('ShaderNodeMixShader')
    mix.inputs[0].default_value = trans
    nb.link(bsdf.outputs[0], mix.inputs[1])
    nb.link(tr.outputs[0], mix.inputs[2])
    nb.link(nb.haze(mix.outputs[0]), out.inputs['Surface'])
    return mat


def make_bark_material(name="TreeBark", c0=(0.035, 0.026, 0.018, 1), c1=(0.16, 0.13, 0.10, 1)):
    mat, nb, out = _new_material(name)
    tc = nb.node('ShaderNodeTexCoord')
    mp = nb.node('ShaderNodeMapping')
    mp.inputs['Scale'].default_value = (1.0, 1.0, 0.12)
    nb.link(tc.outputs['Object'], mp.inputs['Vector'])
    n1 = nb.noise(mp.outputs[0], 9.0, 5.0, 0.7)
    n2 = nb.noise(tc.outputs['Object'], 1.3, 2.0, 0.5)
    col = nb.mixcol(nb.smooth(n1, 0.3, 0.7), c0, c1)
    col = nb.mixcol(nb.smooth(n2, 0.45, 0.75, 0.0, 0.45), col, (0.10, 0.13, 0.07, 1))  # lichen/moss
    bsdf = nb.node('ShaderNodeBsdfPrincipled')
    nb.link(col, bsdf.inputs['Base Color'])
    bsdf.inputs['Roughness'].default_value = 0.85
    bump = nb.node('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.8
    bump.inputs['Distance'].default_value = 0.03
    nb.link(n1, bump.inputs['Height'])
    nb.link(bump.outputs[0], bsdf.inputs['Normal'])
    nb.link(nb.haze(bsdf.outputs[0]), out.inputs['Surface'])
    return mat


def make_hills_material():
    mat, nb, out = _new_material("DistantForest")
    geo = nb.node('ShaderNodeNewGeometry')
    n1 = nb.noise(geo.outputs['Position'], 0.08, 4.0, 0.7)
    n2 = nb.noise(geo.outputs['Position'], 0.012, 2.0, 0.5)
    col = nb.mixcol(n1, (0.010, 0.028, 0.008, 1), (0.035, 0.085, 0.020, 1))
    col = nb.mixcol(nb.smooth(n2, 0.4, 0.7, 0.0, 0.5), col, (0.02, 0.05, 0.02, 1))
    bsdf = nb.node('ShaderNodeBsdfPrincipled')
    nb.link(col, bsdf.inputs['Base Color'])
    bsdf.inputs['Roughness'].default_value = 0.8
    bump = nb.node('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 1.0
    bump.inputs['Distance'].default_value = 6.0
    nb.link(n1, bump.inputs['Height'])
    nb.link(bump.outputs[0], bsdf.inputs['Normal'])
    nb.link(nb.haze(bsdf.outputs[0]), out.inputs['Surface'])
    return mat


# ----------------------------------------------------------------------------
# ground meshes
# ----------------------------------------------------------------------------
def _graded_axis(lo, hi, a0, a1, stops):
    """1D coordinates in [lo, hi]; spacing is a piecewise-linear function of the distance to
    the anchor interval [a0, a1]; stops = [(dist, spacing), ...]."""
    ds = np.array([s[0] for s in stops], dtype=float)
    hs = np.array([s[1] for s in stops], dtype=float)
    h0 = hs[0]
    n = max(1, int(round((a1 - a0) / h0)))
    core = list(np.linspace(a0, a1, n + 1))
    up, p = [], a1
    while p < hi - 1e-6:
        p = min(hi, p + float(np.interp(p - a1, ds, hs)))
        up.append(p)
    if len(up) > 1 and up[-1] - up[-2] < 0.3 * (up[-2] - (up[-3] if len(up) > 2 else a1)):
        up.pop(-2)
    dn, p = [], a0
    while p > lo + 1e-6:
        p = max(lo, p - float(np.interp(a0 - p, ds, hs)))
        dn.append(p)
    if len(dn) > 1 and dn[-2] - dn[-1] < 0.3 * ((dn[-3] if len(dn) > 2 else a0) - dn[-2]):
        dn.pop(-2)
    return np.array(dn[::-1] + core + up)


def _grid_mesh(name, xs, ys, zfunc=None):
    nx, ny = len(xs), len(ys)
    X, Y = np.meshgrid(xs, ys, indexing='ij')
    x, y = X.ravel(), Y.ravel()
    extra = None
    if zfunc is None:
        z = np.full_like(x, common.GROUND_Z)
    else:
        z, extra = zfunc(x, y)
    co = np.stack([x, y, z], axis=1).astype(np.float32)
    i, j = np.meshgrid(np.arange(nx - 1), np.arange(ny - 1), indexing='ij')
    a = (i * ny + j).ravel()
    faces = np.stack([a, a + ny, a + ny + 1, a + 1], axis=1).astype(np.int32)
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(co))
    me.vertices.foreach_set("co", co.ravel())
    me.loops.add(faces.size)
    me.loops.foreach_set("vertex_index", faces.ravel())
    me.polygons.add(len(faces))
    me.polygons.foreach_set("loop_start", np.arange(0, faces.size, 4, dtype=np.int32))
    me.polygons.foreach_set("use_smooth", np.ones(len(faces), dtype=bool))
    me.update(calc_edges=True)
    me.validate()
    return me, extra


def build_ground(col):
    x_anchor = common.FIELD_X_MAX
    xs = _graded_axis(common.FIELD_X_MIN, common.FIELD_X_MAX, x_anchor, x_anchor,
                      [(0, 0.5), (40, 0.5), (150, 2.0), (700, 12.0)])
    xs = np.unique(np.round(xs, 4))
    ys = _graded_axis(common.FIELD_Y_MIN, common.FIELD_Y_MAX, common.CORRIDOR_Y_MIN - 2.0,
                      common.CORRIDOR_Y_MAX + 10.0, [(0, 0.6), (30, 0.6), (150, 2.0), (520, 12.0)])
    ys = np.unique(np.round(ys, 4))

    def zf(x, y):
        h, fm, dens, forest = field_functions(x.astype(np.float64), y.astype(np.float64))
        return common.GROUND_Z + h, (fm, dens, forest)

    me, (fm, dens, forest) = _grid_mesh(common.TERRAIN_OBJECT_NAME, xs, ys, zf)
    for nm, arr in (("field_mask", fm), ("grass_density", dens), ("forest_mask", forest)):
        at = me.attributes.new(nm, 'FLOAT', 'POINT')
        at.data.foreach_set("value", arr.astype(np.float32))
    gmat = make_ground_material()
    me.materials.append(gmat)
    terrain = bpy.data.objects.new(common.TERRAIN_OBJECT_NAME, me)
    col.objects.link(terrain)

    # far ground: flat ring out to the horizon (and under the building), slightly overlapping
    R = 9000.0
    x0, x1 = common.FIELD_X_MIN + 2.0, common.FIELD_X_MAX
    y0, y1 = common.FIELD_Y_MIN + 2.0, common.FIELD_Y_MAX - 2.0
    verts, faces = [], []

    def rect(ax, bx, ay, by, n=6):
        base = len(verts)
        gx, gy = np.linspace(ax, bx, n), np.linspace(ay, by, n)
        for px in gx:
            for py in gy:
                verts.append((px, py, common.GROUND_Z - 0.03))
        for i in range(n - 1):
            for j in range(n - 1):
                a = base + i * n + j
                faces.append((a, a + n, a + n + 1, a + 1))
    rect(-R, x0, -R, R)          # beyond the far field edge
    rect(x1, R, -R, R)           # building side
    rect(x0, x1, -R, y0)         # behind
    rect(x0, x1, y1, R)          # ahead
    fme = bpy.data.meshes.new("FarGround")
    fme.from_pydata(verts, [], faces)
    fme.update()
    fx = np.array([v[0] for v in verts]); fy = np.array([v[1] for v in verts])
    at = fme.attributes.new("field_mask", 'FLOAT', 'POINT')
    at.data.foreach_set("value", np.full(len(verts), 0.5, dtype=np.float32))
    rr = np.hypot(fx, fy)
    at = fme.attributes.new("forest_mask", 'FLOAT', 'POINT')
    at.data.foreach_set("value", (rr > 900).astype(np.float32))
    fme.materials.append(gmat)
    far = bpy.data.objects.new("FarGround", fme)
    col.objects.link(far)

    # distant wooded low hills: backstop behind the tree belt
    nth = 360
    th = np.linspace(-math.pi, math.pi, nth, endpoint=False)
    radii = [820.0, 1000.0, 1350.0, 2000.0, 3200.0]
    hbase = [0.0, 16.0, 24.0, 30.0, 34.0]
    hv, hf = [], []
    for k, (r, hb) in enumerate(zip(radii, hbase)):
        nz = 1.0 + 0.35 * np.sin(3 * th + k) + 0.25 * np.sin(7 * th + 2.0 * k) + 0.15 * np.sin(17 * th + k * k)
        rr_ = r * (1 + 0.04 * np.sin(5 * th + k))
        for t, r2, n_ in zip(th, rr_, nz):
            hv.append((-r2 * math.sin(t), r2 * math.cos(t), common.GROUND_Z - 0.5 + hb * max(n_, 0.3)))
    for k in range(len(radii) - 1):
        for i in range(nth):
            a, b = k * nth + i, k * nth + (i + 1) % nth
            hf.append((a, b, b + nth, a + nth))
    hme = bpy.data.meshes.new("DistantHills")
    hme.from_pydata(hv, [], hf)
    hme.update()
    hme.polygons.foreach_set("use_smooth", np.ones(len(hf), dtype=bool))
    hme.materials.append(make_hills_material())
    hills = bpy.data.objects.new("DistantHills", hme)
    col.objects.link(hills)
    return terrain, far, hills


# ----------------------------------------------------------------------------
# procedural trees (real geometry: tapered tube trunk/branches + leaf quads)
# ----------------------------------------------------------------------------
def _unit(v):
    return v / (np.linalg.norm(v, axis=-1, keepdims=True) + 1e-9)


class TreeBuilder:
    def __init__(self, seed):
        self.rng = np.random.default_rng(seed)
        self.verts, self.faces = [], []
        self.nv = 0
        self.leaf_c, self.leaf_out = [], []   # leaf centres and "outward" hints

    def _perp(self, d):
        ref = np.array([0.0, 0.0, 1.0]) if abs(d[2]) < 0.9 else np.array([1.0, 0.0, 0.0])
        a = _unit(np.cross(d, ref))
        return a, np.cross(d, a)

    def path(self, start, d, length, nseg, wander, up):
        pts = [np.asarray(start, float)]
        d = _unit(np.asarray(d, float))
        for _ in range(nseg):
            d = _unit(d + self.rng.normal(0, wander, 3) + np.array([0, 0, up]))
            pts.append(pts[-1] + d * length / nseg)
        return np.array(pts)

    def tube(self, pts, r0, r1, sides, flare=0.0):
        n = len(pts)
        tang = np.gradient(pts, axis=0)
        tang = _unit(tang)
        t = np.linspace(0, 1, n)
        rad = r0 + (r1 - r0) * t ** 0.85
        if flare > 0:
            rad = rad * (1 + flare * np.exp(-t * n * 1.2))
        ang = np.linspace(0, 2 * math.pi, sides, endpoint=False) + self.rng.uniform(0, 6.28)
        rings = []
        for i in range(n):
            a, b = self._perp(tang[i])
            rings.append(pts[i] + rad[i] * (np.outer(np.cos(ang), a) + np.outer(np.sin(ang), b)))
        self.verts.append(np.concatenate(rings))
        base = self.nv
        i, j = np.meshgrid(np.arange(n - 1), np.arange(sides), indexing='ij')
        a = base + (i * sides + j).ravel()
        b = base + (i * sides + (j + 1) % sides).ravel()
        self.faces.append(np.stack([a, b, b + sides, a + sides], axis=1))
        self.nv += n * sides
        return rad

    def add_leaves(self, pts, count, spread, t_min=0.15, centre=None):
        n = len(pts)
        t = self.rng.uniform(t_min, 1.0, count) ** 0.7 * (n - 1)
        i0 = np.minimum(t.astype(int), n - 2)
        f = (t - i0)[:, None]
        p = pts[i0] * (1 - f) + pts[i0 + 1] * f
        off = self.rng.normal(0, 1, (count, 3))
        off = _unit(off) * (self.rng.uniform(0, 1, (count, 1)) ** 0.5) * spread
        self.leaf_c.append(p + off)
        c = pts[0] if centre is None else centre
        self.leaf_out.append(_unit(p + off - c))

    def finish(self, leaf_len, leaf_w, droop=0.3, flat=0.0):
        nb_faces = sum(len(f) for f in self.faces)
        if self.leaf_c:
            c = np.concatenate(self.leaf_c)
            o = np.concatenate(self.leaf_out)
            m = len(c)
            rnd = _unit(self.rng.normal(0, 1, (m, 3)))
            nrm = _unit(rnd * (1.0 - flat) + o * 0.7 + np.array([0, 0, 0.8 + flat * 2.0]))
            a = _unit(np.cross(nrm, _unit(self.rng.normal(0, 1, (m, 3)))))
            b = np.cross(nrm, a)
            L = leaf_len * self.rng.uniform(0.7, 1.3, (m, 1))
            W = leaf_w * self.rng.uniform(0.7, 1.3, (m, 1))
            fold = nrm * W * 0.25
            dz = np.array([0, 0, -1.0]) * L * droop
            p0 = c - a * L * 0.5
            p1 = c + b * W * 0.5 + fold
            p2 = c + a * L * 0.5 + dz
            p3 = c - b * W * 0.5 + fold
            lv = np.stack([p0, p1, p2, p3], axis=1).reshape(-1, 3)
            base = self.nv
            self.verts.append(lv)
            self.faces.append(base + np.arange(m * 4).reshape(m, 4))
            self.nv += m * 4
        verts = np.concatenate(self.verts).astype(np.float32)
        faces = np.concatenate(self.faces).astype(np.int32)
        mat_idx = np.zeros(len(faces), dtype=np.int32)
        mat_idx[nb_faces:] = 1
        return verts, faces, mat_idx


def _grow(tb, start, d, length, radius, level, P, trunk_axis):
    rng = tb.rng
    maxl = P['levels']
    nseg = max(3, int(P['segs'][min(level, len(P['segs']) - 1)]))
    up = P['up'][min(level, len(P['up']) - 1)]
    pts = tb.path(start, d, length, nseg, P['wander'] * (1 + 0.5 * level), up)
    tip = max(radius * 0.25, 0.006)
    sides = P['sides'][min(level, len(P['sides']) - 1)]
    rad = tb.tube(pts, radius, tip, sides, flare=0.5 if level == 0 else 0.0)
    if level >= maxl:
        tb.add_leaves(pts, P['leaves_twig'], P['leaf_spread'], centre=trunk_axis)
        return
    if level == maxl - 1:
        tb.add_leaves(pts, P['leaves_twig'] // 2, P['leaf_spread'] * 1.2, t_min=0.5, centre=trunk_axis)
    k = P['children'][min(level, len(P['children']) - 1)]
    t0 = P['crown_start'] if level == 0 else 0.25
    az = rng.uniform(0, 6.28)
    tang = _unit(np.gradient(pts, axis=0))
    for c in range(k):
        t = t0 + (1 - t0) * (c + rng.uniform(0.2, 0.9)) / k
        fi = t * (len(pts) - 1)
        i0 = min(int(fi), len(pts) - 2)
        p = pts[i0] + (pts[i0 + 1] - pts[i0]) * (fi - i0)
        dd = tang[i0]
        a, b = tb._perp(dd)
        az += 2.399963 + rng.uniform(-0.4, 0.4)
        ang = math.radians(rng.uniform(*P['angle'])) * (1.0 - 0.45 * t if level == 0 else 1.0)
        nd = dd * math.cos(ang) + (a * math.cos(az) + b * math.sin(az)) * math.sin(ang)
        s = (t - t0) / max(1e-6, 1 - t0)
        if level == 0:
            shape = P['crown_shape'](s)
            ln = P['crown_radius'] * shape * rng.uniform(0.8, 1.2)
        else:
            ln = length * P['ratio'] * (1.0 - 0.45 * s) * rng.uniform(0.8, 1.2)
        r_here = rad[i0]
        cr = min(r_here * 0.75, max(r_here * P['rratio'], 0.012) * (1.15 - 0.4 * s))
        _grow(tb, p, nd, ln, cr, level + 1, P, trunk_axis)


def _round_crown(s):
    return 0.45 + 0.55 * math.sin(math.pi * min(1.0, 0.12 + 0.8 * s))


def _tall_crown(s):
    return 0.35 + 0.65 * math.sin(math.pi * min(1.0, 0.25 + 0.7 * s)) ** 0.8


def gen_broadleaf(seed, height=18.0, lod=0, crown=_round_crown, spread=1.0):
    tb = TreeBuilder(seed)
    rng = tb.rng
    P = dict(levels=3, segs=[10, 7, 5, 4], up=[0.10, 0.10, 0.06, 0.02], wander=0.07,
             sides=[10, 6, 4, 3] if lod == 0 else [7, 5, 3, 3],
             children=[int(rng.integers(9, 12)), 5, 4] if lod == 0 else [int(rng.integers(8, 10)), 4, 4],
             crown_start=rng.uniform(0.22, 0.38), crown_shape=crown,
             crown_radius=height * rng.uniform(0.30, 0.38) * spread,
             angle=(45, 80), ratio=0.62, rratio=0.45,
             leaves_twig=95 if lod == 0 else 36,
             leaf_spread=0.062 * height * (1.0 if lod == 0 else 1.1))
    axis = np.array([0, 0, height * 0.62])
    lean = np.array([rng.normal(0, 0.05), rng.normal(0, 0.05), 1.0])
    _grow(tb, (0, 0, -0.3), lean, height * 0.93, height * rng.uniform(0.018, 0.024), 0, P, axis)
    if lod == 0:
        return tb.finish(0.24, 0.13, droop=0.25)
    return tb.finish(0.42, 0.24, droop=0.25)


def gen_conifer(seed, height=22.0, lod=0):
    tb = TreeBuilder(seed)
    rng = tb.rng
    trunk = tb.path((0, 0, -0.3), (rng.normal(0, 0.02), rng.normal(0, 0.02), 1), height, 14, 0.012, 0.3)
    tb.tube(trunk, height * 0.017, 0.02, 8 if lod == 0 else 6, flare=0.4)
    axis_top = trunk[-1]
    n_whorl = int(height / (0.75 if lod == 0 else 1.0))
    z0 = rng.uniform(0.18, 0.3)
    az = rng.uniform(0, 6.28)
    for w in range(n_whorl):
        t = z0 + (1 - z0) * (w + 0.5) / n_whorl
        fi = t * (len(trunk) - 1)
        i0 = min(int(fi), len(trunk) - 2)
        p = trunk[i0] + (trunk[i0 + 1] - trunk[i0]) * (fi - i0)
        s = (t - z0) / (1 - z0)
        blen = height * 0.24 * (1.0 - s) ** 0.85 + 0.35
        nb_ = int(rng.integers(4, 7)) if lod == 0 else int(rng.integers(3, 6))
        for k in range(nb_):
            az += 6.283 / nb_ + rng.uniform(-0.3, 0.3)
            elev = math.radians(rng.uniform(-22, 2) + 25 * s)
            d = np.array([math.cos(az) * math.cos(elev), math.sin(az) * math.cos(elev), math.sin(elev)])
            L = blen * rng.uniform(0.75, 1.15)
            pts = tb.path(p, d, L, 5, 0.04, 0.035)
            tb.tube(pts, max(0.012, 0.022 * L), 0.006, 4 if lod == 0 else 3)
            cnt = int((150 if lod == 0 else 55) * (0.3 + L / (height * 0.24)))
            tb.add_leaves(pts, cnt, 0.10 * L + 0.15, t_min=0.08,
                          centre=np.array([p[0], p[1], p[2] - 2.0]))
        az += 0.6
    top = trunk[-3:]
    tb.add_leaves(top, 120 if lod == 0 else 50, 0.3, t_min=0.0, centre=axis_top - np.array([0, 0, 2.0]))
    if lod == 0:
        return tb.finish(0.34, 0.085, droop=0.35, flat=0.5)
    return tb.finish(0.58, 0.17, droop=0.35, flat=0.5)


def gen_bush(seed, height=2.2):
    tb = TreeBuilder(seed)
    rng = tb.rng
    P = dict(levels=2, segs=[5, 4, 3], up=[0.12, 0.08, 0.03], wander=0.10, sides=[5, 4, 3],
             children=[4, 3], crown_start=0.3, crown_shape=lambda s: 0.8, crown_radius=height * 0.45,
             angle=(30, 65), ratio=0.6, rratio=0.5, leaves_twig=60, leaf_spread=0.2 * height)
    nst = int(rng.integers(6, 10))
    axis = np.array([0, 0, height * 0.45])
    for k in range(nst):
        az = 6.283 * k / nst + rng.uniform(-0.4, 0.4)
        tilt = rng.uniform(0.25, 0.95)
        d = np.array([math.cos(az) * tilt, math.sin(az) * tilt, 1.0])
        st = np.array([math.cos(az), math.sin(az), 0]) * rng.uniform(0.05, 0.3) - np.array([0, 0, 0.15])
        _grow(tb, st, d, height * rng.uniform(0.6, 1.0), 0.03 * height * 0.5, 0, P, axis)
    return tb.finish(0.15, 0.085, droop=0.2)


def _tree_object(name, data, mats, col):
    verts, faces, mat_idx = data
    old = bpy.data.objects.get(name)
    if old is not None:
        bpy.data.objects.remove(old)
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(verts))
    me.vertices.foreach_set("co", verts.ravel())
    me.loops.add(faces.size)
    me.loops.foreach_set("vertex_index", faces.ravel())
    me.polygons.add(len(faces))
    me.polygons.foreach_set("loop_start", np.arange(0, faces.size, 4, dtype=np.int32))
    me.polygons.foreach_set("material_index", mat_idx)
    me.polygons.foreach_set("use_smooth", mat_idx == 0)
    me.update(calc_edges=True)
    for m in mats:
        me.materials.append(m)
    ob = bpy.data.objects.new(name, me)
    col.objects.link(ob)
    return ob


def build_prototypes(col):
    """Returns (objects sorted by name, index lists per category)."""
    bark = make_bark_material("TreeBark")
    bark_c = make_bark_material("TreeBarkConifer", (0.045, 0.028, 0.02, 1), (0.14, 0.09, 0.065, 1))
    leaf_a = make_leaf_material("TreeLeafBroad", (0.016, 0.050, 0.010, 1), (0.050, 0.120, 0.018, 1))
    leaf_b = make_leaf_material("TreeLeafBroadLight", (0.030, 0.080, 0.012, 1), (0.085, 0.170, 0.025, 1))
    leaf_c = make_leaf_material("TreeLeafConifer", (0.008, 0.028, 0.012, 1), (0.020, 0.055, 0.020, 1), trans=0.12)
    leaf_s = make_leaf_material("TreeLeafShrub", (0.030, 0.085, 0.012, 1), (0.085, 0.180, 0.025, 1))
    objs, cats = [], dict(far_broad=[], far_conifer=[], hi_broad=[], bush=[], hi_conifer=[])
    specs = []
    crowns = [_round_crown, _tall_crown]
    for i in range(6):   # far (treeline) broadleaf, lower detail
        specs.append(("far_broad", lambda i=i: gen_broadleaf(SEED * 100 + i, height=16.0 + 1.2 * (i % 4), lod=1,
                                                             crown=crowns[i % 2], spread=1.0 + 0.12 * (i % 3)),
                      (bark, leaf_a if i % 3 else leaf_b)))
    for i in range(2):
        specs.append(("far_conifer", lambda i=i: gen_conifer(SEED * 200 + i, height=21.0 + 2 * i, lod=1),
                      (bark_c, leaf_c)))
    for i in range(3):   # high detail (mid-field)
        specs.append(("hi_broad", lambda i=i: gen_broadleaf(SEED * 300 + i, height=13.0 + 2 * i, lod=0,
                                                            crown=crowns[i % 2], spread=1.1),
                      (bark, leaf_b if i % 2 else leaf_a)))
    for i in range(3):
        specs.append(("bush", lambda i=i: gen_bush(SEED * 400 + i, height=2.0 + 0.4 * i), (bark, leaf_s)))
    specs.append(("hi_conifer", lambda: gen_conifer(SEED * 500, height=17.0, lod=0), (bark_c, leaf_c)))
    for idx, (cat, fn, mats) in enumerate(specs):
        ob = _tree_object("TreeProto_%02d_%s" % (idx, cat), fn(), mats, col)
        objs.append(ob)
        cats[cat].append(idx)
    return objs, cats


# ----------------------------------------------------------------------------
# instancing
# ----------------------------------------------------------------------------
def _instancer_group(proto_col):
    name = "TreeInstancer"
    old = bpy.data.node_groups.get(name)
    if old is not None:
        bpy.data.node_groups.remove(old)
    ng = bpy.data.node_groups.new(name, 'GeometryNodeTree')
    ng.interface.new_socket("Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket("Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')
    N, L = ng.nodes, ng.links
    gi, go = N.new('NodeGroupInput'), N.new('NodeGroupOutput')
    ci = N.new('GeometryNodeCollectionInfo')
    ci.transform_space = 'ORIGINAL'
    ci.inputs['Collection'].default_value = proto_col
    ci.inputs['Separate Children'].default_value = True
    ci.inputs['Reset Children'].default_value = True
    iop = N.new('GeometryNodeInstanceOnPoints')
    iop.inputs['Pick Instance'].default_value = True

    def attr(nm, dt):
        a = N.new('GeometryNodeInputNamedAttribute')
        a.data_type = dt
        a.inputs['Name'].default_value = nm
        return a.outputs['Attribute']
    e2r = N.new('FunctionNodeEulerToRotation')
    L.new(attr("tree_euler", 'FLOAT_VECTOR'), e2r.inputs['Euler'])
    L.new(gi.outputs[0], iop.inputs['Points'])
    L.new(ci.outputs[0], iop.inputs['Instance'])
    L.new(attr("tree_index", 'INT'), iop.inputs['Instance Index'])
    L.new(e2r.outputs[0], iop.inputs['Rotation'])
    L.new(attr("tree_scale", 'FLOAT_VECTOR'), iop.inputs['Scale'])
    L.new(iop.outputs[0], go.inputs[0])
    return ng


def _points_object(name, pos, index, euler, scale, ng, col):
    old = bpy.data.objects.get(name)
    if old is not None:
        bpy.data.objects.remove(old)
    me = bpy.data.meshes.new(name)
    n = len(pos)
    me.vertices.add(n)
    me.vertices.foreach_set("co", np.asarray(pos, dtype=np.float32).ravel())
    a = me.attributes.new("tree_index", 'INT', 'POINT')
    a.data.foreach_set("value", np.asarray(index, dtype=np.int32))
    a = me.attributes.new("tree_euler", 'FLOAT_VECTOR', 'POINT')
    a.data.foreach_set("vector", np.asarray(euler, dtype=np.float32).ravel())
    a = me.attributes.new("tree_scale", 'FLOAT_VECTOR', 'POINT')
    a.data.foreach_set("vector", np.asarray(scale, dtype=np.float32).ravel())
    me.update()
    ob = bpy.data.objects.new(name, me)
    col.objects.link(ob)
    mod = ob.modifiers.new("TreeInstancer", 'NODES')
    mod.node_group = ng
    return ob


def _treeline_points(cats):
    rng = np.random.default_rng(SEED + 50)
    pos, idx, eul, scl = [], [], [], []
    th0, th1 = BELT_THETA
    step_s, step_d = 4.6, 5.0
    nrows = int(BELT_DEPTH / step_d)
    arc = (th1 - th0) * common.TREELINE_DISTANCE
    ns = int(arc / step_s)
    fb, fc = cats['far_broad'], cats['far_conifer']
    for row in range(-1, nrows):
        for i in range(ns):
            th = th0 + (th1 - th0) * (i + rng.uniform(0, 1)) / ns
            d = (row + rng.uniform(0, 1)) * step_d
            if row == -1:
                if rng.uniform() > 0.25:      # sparse stragglers in front of the belt
                    continue
                d = rng.uniform(-9, 0)
            elif rng.uniform() < 0.10 + 0.25 * row / nrows:
                continue
            r = float(forest_front_radius(th)) + d
            x, y = -r * math.sin(th), r * math.cos(th)
            # skyline: low-frequency height modulation + random
            lf = 1.0 + 0.16 * math.sin(th * 9.0 + 1.3) + 0.10 * math.sin(th * 23.0 + 0.4) \
                + 0.07 * math.sin(th * 61.0)
            conif = (math.sin(th * 14.0 + 2.0) + 0.6 * math.sin(th * 37.0)) > 1.0
            if conif and rng.uniform() < 0.6 or rng.uniform() < 0.04:
                k = fc[int(rng.integers(len(fc)))]
                s = rng.uniform(0.7, 1.08) * lf
                sxy = s * rng.uniform(0.85, 1.1)
            else:
                k = fb[int(rng.integers(len(fb)))]
                s = rng.uniform(0.74, 1.25) * lf
                if row == -1:
                    s *= 0.6
                sxy = s * rng.uniform(0.9, 1.25)
            s = float(np.clip(s, 0.62, 1.42))
            z = float(terrain_height(x, y)) if (common.FIELD_X_MIN < x < common.FIELD_X_MAX and
                                                common.FIELD_Y_MIN < y < common.FIELD_Y_MAX) else common.GROUND_Z
            pos.append((x, y, z))
            idx.append(k)
            eul.append((rng.normal(0, 0.03), rng.normal(0, 0.03), rng.uniform(0, 6.283)))
            scl.append((sxy, sxy, s))
    # understory shrubs closing the base of the forest edge
    bs = cats['bush']
    nb_ = int(arc / 2.6)
    for i in range(nb_):
        th = th0 + (th1 - th0) * (i + rng.uniform(0, 1)) / nb_
        r = float(forest_front_radius(th)) + rng.uniform(-6.0, 4.0)
        x, y = -r * math.sin(th), r * math.cos(th)
        s = rng.uniform(1.3, 2.6)
        pos.append((x, y, common.GROUND_Z - 0.1))
        idx.append(bs[int(rng.integers(len(bs)))])
        eul.append((0, 0, rng.uniform(0, 6.283)))
        scl.append((s * rng.uniform(1.0, 1.5), s * rng.uniform(1.0, 1.5), s))
    return pos, idx, eul, scl


def _midfield_points(cats):
    rng = np.random.default_rng(SEED + 90)
    pos, idx, eul, scl = [], [], [], []
    hb, bs, hc = cats['hi_broad'], cats['bush'], cats['hi_conifer']
    # (x, y, n_bushes, radius, small_tree scale or 0)
    clumps = [(-136, 127, 7, 7.0, 0.42), (-73, 85, 4, 4.0, 0.0), (-150, 150, 5, 6.0, 0.0),
              (-215, 60, 6, 6.0, 0.55), (-110, 235, 6, 6.0, 0.48), (-60, 300, 5, 5.0, 0.0),
              (-240, 250, 8, 9.0, 0.62), (-180, 10, 4, 4.0, 0.0), (-95, 180, 3, 3.0, 0.0),
              (-260, 150, 5, 6.0, 0.5), (-40, 215, 3, 3.5, 0.0), (-170, 330, 6, 7.0, 0.55),
              (-120, -60, 5, 5.0, 0.45), (-250, -120, 6, 7.0, 0.6), (-300, 60, 4, 5, 0.7)]
    for (cx, cy, nb_, rad, ts) in clumps:
        for k in range(nb_):
            a, rr = rng.uniform(0, 6.283), rad * math.sqrt(rng.uniform(0, 1))
            x, y = cx + rr * math.cos(a) * 1.6, cy + rr * math.sin(a)
            s = rng.uniform(0.7, 1.5)
            pos.append((x, y, float(terrain_height(x, y)) - 0.05))
            idx.append(bs[int(rng.integers(len(bs)))])
            eul.append((0, 0, rng.uniform(0, 6.283)))
            scl.append((s * rng.uniform(1.0, 1.4), s * rng.uniform(1.0, 1.4), s))
        if ts > 0:
            x, y = cx + rng.uniform(-2, 2), cy + rng.uniform(-2, 2)
            s = ts * rng.uniform(0.85, 1.15)
            k = hb[int(rng.integers(len(hb)))] if rng.uniform() > 0.15 else hc[0]
            pos.append((x, y, float(terrain_height(x, y)) - 0.05))
            idx.append(k)
            eul.append((rng.normal(0, 0.03), rng.normal(0, 0.03), rng.uniform(0, 6.283)))
            scl.append((s * 1.1, s * 1.1, s))
    return pos, idx, eul, scl


# ----------------------------------------------------------------------------
def build():
    tcol = common.get_collection("Terrain")
    vcol = common.get_collection("Trees")
    pcol = common.get_collection("TreePrototypes")

    terrain, far, hills = build_ground(tcol)

    protos, cats = build_prototypes(pcol)
    pcol.hide_render = True
    pcol.hide_viewport = True

    ng = _instancer_group(pcol)
    tl = _treeline_points(cats)
    treeline = _points_object("TreeLine", *tl, ng, vcol)
    mv = _midfield_points(cats)
    mid = _points_object("MidVegetation", *mv, ng, vcol)

    return {
        "terrain": terrain,
        "far_ground": far,
        "distant_hills": hills,
        "treeline": treeline,
        "mid_vegetation": mid,
        "prototypes": protos,
        "prototype_categories": cats,
        "collections": {"terrain": tcol, "trees": vcol, "prototypes": pcol},
        "ground_material": terrain.data.materials[0],
        "attributes": ["field_mask", "grass_density", "forest_mask"],
        "terrain_vertex_count": len(terrain.data.vertices),
        "treeline_instances": len(tl[0]),
        "mid_instances": len(mv[0]),
        "prototype_polys": {o.name: len(o.data.polygons) for o in protos},
        "height_function": terrain_height,
    }
