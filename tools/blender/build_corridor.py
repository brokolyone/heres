"""Rebuild the sunlit glass corridor from art/corridor/reference.png.

    blender -b --factory-startup --python tools/blender/build_corridor.py -- art/corridor \
        [--render out.png] [--scale 1.0] [--samples 256] [--no-save] [--tune overrides.json]

Writes corridor.blend into the given folder (and renders it when --render is given).
The rice is generated here; the weedy ferns by the glass are a CC0 Poly Haven scan in
<folder>/assets/fern_02.
Units are metres. +Y runs down the corridor, the glass wall is on -X, floor at z = 0.

The camera was solved from the reference: corridor vanishing point at (925, 283) px of
the 1009x473 frame, focal length ~1200 px, level camera with the horizon pushed down by
lens shift. Floor/ceiling/wall lines then fix the room: glass wall 2.81 m to the left,
right wall 1.75 m to the right, ceiling 3.2 m, eye height 1.23 m.
"""
import math
import os
import sys

import bmesh
import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
OUT = os.path.abspath(argv[0])
RENDER = argv[argv.index("--render") + 1] if "--render" in argv else None
SCALE = float(argv[argv.index("--scale") + 1]) if "--scale" in argv else 1.0
SAMPLES = int(argv[argv.index("--samples") + 1]) if "--samples" in argv else 256
SAVE = "--no-save" not in argv

# look-dev knobs (colours are sRGB 0-255); --tune file.json overrides any of them
# Values below were fitted region by region against the reference renders (see
# tools/blender/fit_corridor.py), then the grade was pushed a touch darker.
T = {
    "sun_strength": 6.0,
    "sun_out_elev": 40.0,
    "sun_out_az": -25.0,        # relative to the camera's forward direction
    "sky_light": (110, 185, 255),
    "sky_light_strength": 3.4,
    # what the camera sees of the sunlit landscape, as linear multipliers
    "field_mul": (0.263, 0.159, 0.13),
    "plant_mul": (0.586, 0.366, 0.01),
    "tree_mul": (0.01, 0.369, 1.36),
    "sky_mul": (0.769, 0.637, 0.655),
    "exposure": 0.5,
    "grade_gamma": 1.12,        # compositor: slightly darker, deeper mid-tones
    "floor_window": (100, 135, 145),
    "floor_sun": (190, 215, 95),
    "floor_shade": (46, 143, 16),
    "reflect_window": 0.411,
    "reflect_tint": (0.78, 1.0, 0.74),   # floor and glass mirror a little greener
    "reflect_window_tint": (0.92, 0.94, 1.0),   # by the glass the floor mirrors the sky
    "reflect_sun": 0.1,
    "reflect_shade": 0.05,
    "ceiling_fill": (0.96, 0.435, 0.775),    # W/m^2 per channel
    "wall_fill": 1.5031,
    "sun_stripes": (1.8, 0.55, 0.25),   # period (m), lit fraction, light left in the dark bands
    "sun_patch": 0.3362,                        # strength of the sun band painted on the floor
    "sun_patch_color": (0.9, 0.82, 0.12),
    "frame": (134, 127, 115),
    "channel": (116, 134, 139),
    "wall": (222, 232, 235),
    "ceiling": (225, 232, 232),
    "glass_tint": (0.86, 0.97, 0.97),
    "glass_graze": (2, 2, 2),
    "glass_reflect": 0.6,
    "fern_tint": ((50, 90, 15), (150, 195, 40), (215, 235, 110)),
    "far_mul": (0.559, 0.268, 0.48),
    "mid_mul": (0.866, 0.379, 0.01),
    "plant_value": 1.6,
    "rice": ((60, 105, 20), (135, 185, 35), (205, 228, 90)),
}
if "--tune" in argv:
    import json
    T.update(json.load(open(argv[argv.index("--tune") + 1])))

REF_W, REF_H = 1009, 473
VP = (925.0, 283.0)
FOCAL_PX = 1200.0

LEFT = -2.81          # inner face of the sill / window head
RIGHT = 1.75          # right wall
HEIGHT = 3.2          # floor to ceiling
EYE = 1.23
NEAR, FAR = -60.0, 140.0
GLASS_X = LEFT - 0.06
SILL_TOP = 0.23
# column covers: deep side facing the camera, a light nose and a recessed dark channel
MULLION_DEPTH = 0.21
MULLION_NOSE = 0.10
MULLION_WIDTH = 0.26
# near edges of the first four solved from the reference pixels, then a 3.6 m module
MULLIONS = [3.40, 6.59, 10.32, 13.93]
while MULLIONS[-1] < FAR:
    MULLIONS.append(MULLIONS[-1] + 3.6)
MULLIONS = [-0.2 - 3.6 * k for k in range(16, 0, -1)] + [-0.2] + MULLIONS
PILASTER_STEP = 6.8

YAW = math.atan((VP[0] - REF_W / 2) / FOCAL_PX)
# the sun patch on the floor is a lengthwise band, as in the reference
SUN_BAND = (-1.375, 0.0)
# the corridor is a raised walkway: the paddies lie 3.5 m below its floor, which is what
# makes the field read as a flat carpet of paddies the way it does in the reference
GROUND_Z = -3.5
FOREST_R = 2000.0
# fair-weather clouds as (x, y, width, height) in reference pixels
CLOUDS = [(288, 168, 72, 22), (345, 178, 62, 15), (372, 192, 46, 14), (160, 178, 36, 24),
          (242, 192, 24, 6), (520, 195, 34, 14), (560, 214, 64, 8), (18, 176, 44, 18)]
# bushes in the paddies: (x, y of the base, height) in reference pixels
BUSHES = [(332, 309, 14), (360, 307, 8), (412, 316, 10), (300, 304, 6), (205, 306, 7),
          (630, 300, 7), (700, 298, 6), (545, 303, 6)]


def pixel_ray(px, py):
    """World direction through a pixel of the 1009x473 reference frame."""
    right = Vector((math.cos(YAW), math.sin(YAW), 0.0))
    fwd = Vector((-math.sin(YAW), math.cos(YAW), 0.0))
    d = right * (px - REF_W / 2) + Vector((0, 0, 1)) * (VP[1] - py) + fwd * FOCAL_PX
    return d.normalized()


def canopy(a, R=FOREST_R):
    """Forest height above ground at azimuth a (radians from +X), fitted to the reference's
    tree line: it stands taller toward the left edge of the frame."""
    rel = max(-1.5, min(1.5, (a - math.radians(90) - YAW) / math.radians(23)))
    return (13.8 + 6.9 * rel) * R / 1000.0 + (EYE - GROUND_Z)


def ground_point(px, py):
    d = pixel_ray(px, py)
    t = (GROUND_Z - EYE) / d.z
    return Vector((0, 0, EYE)) + d * t


# ---------------------------------------------------------------- helpers

def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def link(obj):
    bpy.context.scene.collection.objects.link(obj)
    return obj


def mesh_obj(name, bm, mat=None):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(name, me)
    if mat:
        obj.data.materials.append(mat)
    return link(obj)


def add_box(bm, x0, x1, y0, y1, z0, z1):
    vs = [bm.verts.new((x, y, z)) for z in (z0, z1) for y in (y0, y1) for x in (x0, x1)]
    idx = [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)]
    for f in idx:
        bm.faces.new([vs[i] for i in f])


def box(name, x0, x1, y0, y1, z0, z1, mat):
    bm = bmesh.new()
    add_box(bm, x0, x1, y0, y1, z0, z1)
    return mesh_obj(name, bm, mat)


def quad(name, corners, mat):
    bm = bmesh.new()
    bm.faces.new([bm.verts.new(c) for c in corners])
    return mesh_obj(name, bm, mat)


def disc(bm, cx, cy, z, r, segs=24):
    ring = [bm.verts.new((cx + r * math.cos(a), cy + r * math.sin(a), z))
            for a in (2 * math.pi * i / segs for i in range(segs))]
    bm.faces.new(ring)


class Nodes:
    """Tiny wrapper so shader graphs read top-down."""

    def __init__(self, mat):
        mat.use_nodes = True
        self.nt = mat.node_tree
        self.nt.nodes.clear()
        self.out = self.new("ShaderNodeOutputMaterial")

    def new(self, kind, **inputs):
        n = self.nt.nodes.new(kind)
        for k, v in inputs.items():
            if k.startswith("_"):
                setattr(n, k[1:], v)
            else:
                self.set(n.inputs[k], v)
        return n

    def set(self, socket, v):
        if isinstance(v, bpy.types.NodeSocket):
            self.nt.links.new(v, socket)
        else:
            socket.default_value = v

    def math(self, op, a, b=0.0, clamp=False):
        n = self.new("ShaderNodeMath", _operation=op, _use_clamp=clamp)
        self.set(n.inputs[0], a)
        self.set(n.inputs[1], b)
        return n.outputs[0]

    def mix(self, fac, a, b):
        n = self.new("ShaderNodeMix", _data_type="RGBA")
        self.set(n.inputs[0], fac)
        self.set(n.inputs[6], a)
        self.set(n.inputs[7], b)
        return n.outputs[2]

    def ramp(self, fac, stops):
        n = self.new("ShaderNodeValToRGB")
        self.set(n.inputs[0], fac)
        els = n.color_ramp.elements
        while len(els) < len(stops):
            els.new(0.5)
        for e, (p, c) in zip(els, stops):
            e.position = p
            e.color = (*c, 1.0) if len(c) == 3 else c
        return n.outputs[0]

    def xyz(self, coord="Object"):
        sep = self.new("ShaderNodeSeparateXYZ")
        self.set(sep.inputs[0], self.coords(coord))
        return sep.outputs

    def coords(self, kind="Object"):
        if not hasattr(self, "_tc"):
            self._tc = self.new("ShaderNodeTexCoord")
        return self._tc.outputs[kind]

    def scaled(self, vec, scale):
        m = self.new("ShaderNodeMapping", Scale=scale)
        self.set(m.inputs["Vector"], vec)
        return m.outputs[0]

    def noise(self, vec, scale, detail=2.0, rough=0.5):
        n = self.new("ShaderNodeTexNoise", Scale=scale, Detail=detail, Roughness=rough)
        self.set(n.inputs["Vector"], self.coords() if vec is None else vec)
        return n.outputs["Fac"]

    def line_mask(self, coord, period, half_width, offset=0.0):
        """1 within half_width of every multiple of period (plus offset)."""
        t = self.math("DIVIDE", self.math("SUBTRACT", coord, offset), period)
        d = self.math("ABSOLUTE", self.math("SUBTRACT", self.math("FRACT", self.math("ADD", t, 0.5)), 0.5))
        return self.math("LESS_THAN", self.math("MULTIPLY", d, period), half_width)

    def principled(self, color, rough=0.5, spec=0.5, **extra):
        p = self.new("ShaderNodeBsdfPrincipled", Roughness=rough)
        self.set(p.inputs["Base Color"], color)
        p.inputs["Specular IOR Level"].default_value = spec
        for k, v in extra.items():
            self.set(p.inputs[k], v)
        return p

    def output(self, shader):
        self.set(self.out.inputs["Surface"], shader.outputs[0] if isinstance(shader, bpy.types.Node) else shader)


def camera_tint(n, color, mul):
    """Albedo as the camera sees it (times mul) vs. as it bounces light (unchanged):
    the reference is an HDR-style blend where the bright outdoors is held down."""
    lp = n.new("ShaderNodeLightPath")
    scaled = n.new("ShaderNodeMix", _data_type="RGBA", _blend_type="MULTIPLY")
    scaled.inputs[0].default_value = 1.0
    n.set(scaled.inputs[6], color)
    scaled.inputs[7].default_value = (*mul, 1.0)
    return n.mix(lp.outputs["Is Camera Ray"], color, scaled.outputs[2])


def rgb(*c):
    return (*c, 1.0)


def srgb(r, g, b):
    def lin(v):
        v /= 255.0
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    return (lin(r), lin(g), lin(b), 1.0)


# ---------------------------------------------------------------- materials

def mat_simple(name, color, rough=0.5, spec=0.5, metallic=0.0):
    m = bpy.data.materials.new(name)
    n = Nodes(m)
    n.output(n.principled(color, rough, spec, Metallic=metallic))
    return m


def mat_floor():
    """One glossy resin floor in three soft lengthwise zones, as in the reference: a
    blue-reflecting strip by the glass, a band of sun in the middle and deeper green
    toward the inner wall. The sun band is painted in as light (an emission pattern)
    so it can be as soft and wavy as in the reference instead of hard mullion shadows."""
    m = bpy.data.materials.new("floor")
    n = Nodes(m)
    x, y, _ = n.xyz("Object")
    # zone edges wander a little along the corridor
    wob = n.math("MULTIPLY", n.math("SUBTRACT", n.noise(n.scaled(n.coords(), (0.2, 0.05, 1.0)), 2.0, 2.0), 0.5), 0.35)
    u = n.math("ADD", x, wob)

    def ramp_up(lo, hi):
        r = n.new("ShaderNodeMapRange", **{"From Min": lo, "From Max": hi, "_interpolation_type": "SMOOTHSTEP"})
        n.set(r.inputs["Value"], u)
        return r.outputs[0]

    past_window = ramp_up(SUN_BAND[0] - 0.2, SUN_BAND[0] + 0.25)
    shade = ramp_up(SUN_BAND[1] - 0.15, SUN_BAND[1] + 0.45)
    sun = n.math("SUBTRACT", past_window, shade, clamp=True)

    def zones(a, b, c):
        return n.mix(shade, n.mix(past_window, a, b), c)

    col = zones(srgb(*T["floor_window"]), srgb(*T["floor_sun"]), srgb(*T["floor_shade"]))
    streak = n.noise(n.scaled(n.coords(), (1.0, 0.06, 1.0)), 5.0, 4.0, 0.6)
    tone = n.new("ShaderNodeMix", _data_type="RGBA", _blend_type="MULTIPLY")
    tone.inputs[0].default_value = 1.0
    n.set(tone.inputs[6], col)
    n.set(tone.inputs[7], n.ramp(streak, [(0.3, (0.7, 0.7, 0.7)), (0.7, (1.15, 1.15, 1.15))]))
    col = tone.outputs[2]

    # sun light: cross stripes square to the line of sight (shadows of the glazing),
    # warped and broken up by long grassy streaks like the reference's light on the floor
    q = n.math("ADD", n.math("MULTIPLY", x, -math.sin(YAW)), n.math("MULTIPLY", y, math.cos(YAW)))
    warp = n.math("MULTIPLY", n.math("SUBTRACT", n.noise(n.scaled(n.coords(), (0.5, 1.4, 1.0)), 1.3, 4.0, 0.6), 0.5), 1.4)
    period, duty, low = T["sun_stripes"]
    wave = n.math("MULTIPLY", n.math("ADD", n.math("SINE", n.math("MULTIPLY", n.math("ADD", q, warp),
                                                                  2 * math.pi / period)), 1.0), 0.5)
    lit = n.new("ShaderNodeMapRange", **{"From Min": 1.0 - duty - 0.2, "From Max": 1.0 - duty + 0.2,
                                          "To Min": low, "_interpolation_type": "SMOOTHSTEP"})
    n.set(lit.inputs["Value"], wave)
    along = n.new("ShaderNodeMapping", Rotation=(0, 0, YAW), Scale=(0.15, 1.0, 1.0))
    n.set(along.inputs[0], n.coords())
    grass = n.noise(along.outputs[0], 7.0, 6.0, 0.65)
    texture = n.new("ShaderNodeMapRange", **{"From Min": 0.3, "From Max": 0.7, "To Min": 0.55, "To Max": 1.2})
    n.set(texture.inputs["Value"], grass)
    light = n.math("MULTIPLY", n.math("MULTIPLY", lit.outputs[0], texture.outputs[0]), sun)
    em = n.new("ShaderNodeEmission", Color=(*T["sun_patch_color"], 1.0))
    n.set(em.inputs["Strength"], n.math("MULTIPLY", light, T["sun_patch"]))

    reflect = n.new("ShaderNodeMix")
    n.set(reflect.inputs[0], shade)
    n.set(reflect.inputs[2], n.math("ADD", n.math("MULTIPLY", n.math("SUBTRACT", 1.0, past_window), T["reflect_window"] - T["reflect_sun"]), T["reflect_sun"]))
    reflect.inputs[3].default_value = T["reflect_shade"]
    rough = n.math("ADD", n.math("MULTIPLY", shade, 0.12), n.math("ADD", 0.04, n.math("MULTIPLY", n.noise(None, 3.0, 2.0), 0.05)))
    diffuse = n.principled(col, 0.6, 0.0)
    gloss = n.new("ShaderNodeBsdfGlossy")
    n.set(gloss.inputs["Color"], n.mix(past_window, rgb(*T["reflect_window_tint"]), rgb(*T["reflect_tint"])))
    n.set(gloss.inputs["Roughness"], rough)
    mix = n.new("ShaderNodeMixShader")
    n.set(mix.inputs[0], reflect.outputs[0])
    n.set(mix.inputs[1], diffuse.outputs[0])
    n.set(mix.inputs[2], gloss.outputs[0])
    add = n.new("ShaderNodeAddShader")
    n.set(add.inputs[0], mix.outputs[0])
    n.set(add.inputs[1], em.outputs[0])
    n.output(add)
    return m


def mat_metal(name, color, rough=0.3, metallic=0.5, bevel=0.01):
    """Painted / anodised aluminium: rounded edges that catch the light."""
    m = bpy.data.materials.new(name)
    n = Nodes(m)
    bev = n.new("ShaderNodeBevel", Radius=bevel)
    bev.samples = 8
    n.output(n.principled(srgb(*color), rough, 0.5, Metallic=metallic, Normal=bev.outputs[0]))
    return m


def mat_ceiling():
    m = bpy.data.materials.new("ceiling")
    n = Nodes(m)
    x, y, _ = n.xyz("Object")
    lines = n.math("MAXIMUM", n.line_mask(x, 1.2, 0.005, LEFT + 0.3),
                   n.line_mask(y, 1.2, 0.005))
    beams = n.line_mask(y, 7.2, 0.02, 0.6)
    base = srgb(*T["ceiling"])
    col = n.mix(n.math("MULTIPLY", lines, 0.55), base, srgb(120, 125, 120))
    col = n.mix(n.math("MULTIPLY", beams, 0.7), col, srgb(110, 115, 110))
    speck = n.noise(None, 400.0, 0.0)
    col = n.mix(n.math("MULTIPLY", speck, 0.15), col, srgb(200, 205, 198))
    bump = n.new("ShaderNodeBump", Strength=0.4, Distance=0.004)
    n.set(bump.inputs["Height"], n.math("SUBTRACT", 1.0, n.math("MAXIMUM", lines, beams)))
    p = n.principled(col, 0.85, 0.2, Normal=bump.outputs[0])
    n.output(p)
    return m


def mat_glass(name="glass", tint=T["glass_tint"], graze=None):
    m = bpy.data.materials.new(name)
    n = Nodes(m)
    fres = n.new("ShaderNodeFresnel", IOR=1.5)
    lw = n.new("ShaderNodeLayerWeight", Blend=0.5)
    # longer path through the pane at grazing angles -> stronger green-cyan tint
    tint_col = n.mix(n.math("POWER", lw.outputs["Facing"], 3.0), rgb(*tint), rgb(*(graze or T["glass_graze"])))
    tr = n.new("ShaderNodeBsdfTransparent")
    n.set(tr.inputs["Color"], tint_col)
    gl = n.new("ShaderNodeBsdfGlossy", Roughness=0.02, Color=rgb(*T["reflect_tint"]))
    mix = n.new("ShaderNodeMixShader")
    n.set(mix.inputs[0], n.math("MULTIPLY", fres.outputs[0], T["glass_reflect"]))
    n.set(mix.inputs[1], tr.outputs[0])
    n.set(mix.inputs[2], gl.outputs[0])
    n.output(mix)
    m.blend_method = "BLEND"
    return m


def aerial(n, col):
    """Distance haze: the reference field turns into a pale cyan-green mist past ~600 m."""
    d = n.new("ShaderNodeCameraData").outputs["View Distance"]
    near = n.math("SUBTRACT", 1.0, n.math("EXPONENT", n.math("DIVIDE", d, -450.0)))
    far = n.new("ShaderNodeMapRange", **{"From Min": 480.0, "From Max": 1100.0, "_interpolation_type": "SMOOTHSTEP"})
    n.set(far.inputs["Value"], d)
    haze = n.math("ADD", n.math("MULTIPLY", near, 0.12), n.math("MULTIPLY", far.outputs[0], 0.75))
    return n.mix(haze, col, srgb(150, 198, 172))


def mat_field():
    m = bpy.data.materials.new("field")
    n = Nodes(m)
    # paddies: brick rows along the camera's right vector, so the dikes read as horizontal
    # lines like in the reference (bricks are kept very long: their end joints would
    # otherwise show up as dark wedges running away from the camera)
    rot = n.new("ShaderNodeMapping", Rotation=(0, 0, -YAW))
    n.set(rot.inputs[0], n.coords())
    bricks = n.new("ShaderNodeTexBrick", Scale=1.0, **{
        "Mortar Size": 0.9, "Mortar Smooth": 0.6, "Bias": 0.0, "Brick Width": 4000.0, "Row Height": 32.0,
        "Color1": srgb(182, 214, 60), "Color2": srgb(115, 175, 35), "Mortar": srgb(60, 110, 25)})
    bricks.offset = 0.37
    n.set(bricks.inputs["Vector"], rot.outputs[0])
    col = bricks.outputs["Color"]
    big = n.noise(n.scaled(rot.outputs[0], (1.0, 3.0, 1.0)), 0.006, 3.0, 0.6)
    col = n.mix(n.math("MULTIPLY", n.math("ABSOLUTE", n.math("SUBTRACT", big, 0.5)), 1.2), col,
                srgb(100, 165, 30))
    fine = n.noise(n.scaled(rot.outputs[0], (1.0, 1.0, 3.0)), 3.0, 4.0, 0.7)
    col = n.mix(n.math("MULTIPLY", n.math("SUBTRACT", fine, 0.45), 0.9), col, srgb(80, 135, 25))
    # aerial perspective
    col = aerial(n, col)
    bump = n.new("ShaderNodeBump", Strength=0.3)
    n.set(bump.inputs["Height"], fine)
    p = n.principled(camera_tint(n, col, T["field_mul"]), 1.0, 0.0, Normal=bump.outputs[0])
    n.output(p)
    return m


def mat_cloud():
    m = bpy.data.materials.new("cloud")
    n = Nodes(m)
    u, v, _ = n.xyz("UV")
    du = n.math("MULTIPLY", n.math("SUBTRACT", u, 0.5), 2.0)
    dv = n.math("MULTIPLY", n.math("SUBTRACT", v, 0.5), 2.0)
    r = n.math("SQRT", n.math("ADD", n.math("MULTIPLY", du, du), n.math("MULTIPLY", dv, dv)))
    info = n.new("ShaderNodeObjectInfo")
    nz = n.new("ShaderNodeTexNoise", _noise_dimensions="4D", Scale=2.5, Detail=8.0, Roughness=0.62)
    n.set(nz.inputs["Vector"], n.coords("UV"))
    n.set(nz.inputs["W"], n.math("MULTIPLY", info.outputs["Random"], 100.0))
    dens = n.math("SUBTRACT", n.math("SUBTRACT", nz.outputs["Fac"], 0.2), n.math("MULTIPLY", r, 0.38))
    base = n.math("MULTIPLY", n.math("SUBTRACT", v, 0.12), 4.0, clamp=True)   # flat cumulus base
    alpha = n.math("MULTIPLY", n.math("MULTIPLY", dens, 5.0, clamp=True), base)
    shade = n.mix(n.math("POWER", v, 0.6), srgb(215, 232, 245), srgb(255, 255, 255))
    em = n.new("ShaderNodeEmission", Strength=1.12)
    n.set(em.inputs["Color"], shade)
    tr = n.new("ShaderNodeBsdfTransparent")
    mix = n.new("ShaderNodeMixShader")
    n.set(mix.inputs[0], alpha)
    n.set(mix.inputs[1], tr.outputs[0])
    n.set(mix.inputs[2], em.outputs[0])
    n.output(mix)
    m.blend_method = "BLEND"
    return m


def adapt_plant(mat, alpha_path, tint, gain):
    """Hook up the leaf cut-out (the glTF diffuse is a JPEG without alpha), push the scan
    toward the paddy's yellow-green and apply the camera-only tint."""
    n = Nodes.__new__(Nodes)
    n.nt = mat.node_tree
    out = next(x for x in n.nt.nodes if x.type == "OUTPUT_MATERIAL")
    bsdf = next(x for x in n.nt.nodes if x.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Specular IOR Level"].default_value = 0.15
    cut = n.new("ShaderNodeTexImage")
    cut.image = bpy.data.images.load(alpha_path, check_existing=True)
    cut.image.colorspace_settings.name = "Non-Color"
    n.set(bsdf.inputs["Alpha"], n.math("GREATER_THAN", cut.outputs["Color"], 0.5))
    base = bsdf.inputs["Base Color"]
    if base.is_linked:
        # keep the scan's light and shade, recolour it along a paddy-green ramp
        lum = n.new("ShaderNodeRGBToBW")
        n.set(lum.inputs[0], base.links[0].from_socket)
        dark, mid, light = tint
        col = n.ramp(n.math("MULTIPLY", lum.outputs[0], T["plant_value"]), [
            (0.0, srgb(*dark)), (0.35, srgb(*mid)), (0.8, srgb(*light))])
        n.set(base, camera_tint(n, aerial(n, col), gain))


def mat_crowns():
    """Far canopy: one continuous leafy texture across all crowns (world-space noise),
    only a slight tint per tree, and occlusion deepening the gaps between crowns."""
    m = bpy.data.materials.new("crowns")
    n = Nodes(m)
    info = n.new("ShaderNodeObjectInfo")
    world = n.new("ShaderNodeNewGeometry").outputs["Position"]
    canopy_tex = n.noise(world, 0.08, 5.0, 0.6)
    col = n.ramp(n.math("ADD", n.math("MULTIPLY", info.outputs["Random"], 0.15),
                        n.math("MULTIPLY", canopy_tex, 0.85)), [
        (0.3, srgb(14, 54, 54)), (0.5, srgb(24, 72, 72)), (0.7, srgb(38, 90, 84))])
    clumps = n.noise(world, 0.6, 4.0, 0.6)
    gaps = n.new("ShaderNodeMapRange", **{"From Min": 0.35, "From Max": 0.6, "To Min": 0.75, "To Max": 1.0})
    n.set(gaps.inputs["Value"], clumps)
    ao = n.new("ShaderNodeAmbientOcclusion", Distance=3.0)
    ao.samples = 8
    shade = n.math("MULTIPLY", gaps.outputs[0], n.math("ADD", 0.7, n.math("MULTIPLY", ao.outputs["AO"], 0.3)))
    comb = n.new("ShaderNodeCombineColor")
    for i in range(3):
        n.set(comb.inputs[i], shade)
    dark = n.new("ShaderNodeMix", _data_type="RGBA", _blend_type="MULTIPLY")
    dark.inputs[0].default_value = 1.0
    n.set(dark.inputs[6], col)
    n.set(dark.inputs[7], comb.outputs[0])
    bump = n.new("ShaderNodeBump", Strength=0.3)
    n.set(bump.inputs["Height"], clumps)
    # darker, greener toward the forest floor; tops catch the blue of the open sky
    _, _, wz = n.new("ShaderNodeSeparateXYZ").outputs
    sep = wz.node
    n.set(sep.inputs[0], world)
    height = n.new("ShaderNodeMapRange", **{"From Min": GROUND_Z, "From Max": GROUND_Z + 45.0,
                                             "_interpolation_type": "SMOOTHSTEP"})
    n.set(height.inputs["Value"], wz)
    grade = n.new("ShaderNodeMix", _data_type="RGBA", _blend_type="MULTIPLY")
    grade.inputs[0].default_value = 1.0
    n.set(grade.inputs[6], dark.outputs[2])
    n.set(grade.inputs[7], n.mix(height.outputs[0], rgb(0.6, 0.92, 1.0), rgb(0.95, 1.0, 0.85)))
    col = camera_tint(n, grade.outputs[2], T["tree_mul"])
    p = n.principled(col, 1.0, 0.1, Normal=bump.outputs[0])
    # at two kilometres the haze flattens the lighting: much of what reaches the eye is
    # airlight in the forest's own tone rather than sun/sky shading
    flat = n.new("ShaderNodeEmission", Strength=0.6)
    n.set(flat.inputs["Color"], col)
    mix = n.new("ShaderNodeMixShader")
    mix.inputs[0].default_value = 0.65
    n.set(mix.inputs[1], p.outputs[0])
    n.set(mix.inputs[2], flat.outputs[0])
    n.output(mix)
    return m


# ---------------------------------------------------------------- geometry

def build_corridor(M):
    quad("floor", [(GLASS_X - 0.05, NEAR, 0), (RIGHT, NEAR, 0), (RIGHT, FAR, 0), (GLASS_X - 0.05, FAR, 0)],
         M["floor"])
    quad("ceiling", [(LEFT + 0.22, NEAR, HEIGHT), (LEFT + 0.22, FAR, HEIGHT), (RIGHT, FAR, HEIGHT),
                     (RIGHT, NEAR, HEIGHT)], M["ceiling"])
    # window head: white head frame, a plain soffit strip, then a thin dark curtain slot
    box("head", GLASS_X, LEFT, NEAR, FAR, HEIGHT - 0.11, HEIGHT + 0.12, M["dark"])
    quad("soffit", [(LEFT, NEAR, HEIGHT), (LEFT, FAR, HEIGHT), (LEFT + 0.12, FAR, HEIGHT),
                    (LEFT + 0.12, NEAR, HEIGHT)], M["ceiling"])
    box("pocket", LEFT + 0.12, LEFT + 0.22, NEAR, FAR, HEIGHT, HEIGHT + 0.12, M["dark"])

    # sill: low white frame under the glass with a dark kick recess at the floor
    box("sill", GLASS_X - 0.05, LEFT, NEAR, FAR, 0.05, SILL_TOP, M["sill"])
    box("sill_cap", GLASS_X - 0.02, LEFT + 0.025, NEAR, FAR, SILL_TOP - 0.025, SILL_TOP, M["sill"])
    box("kick", GLASS_X - 0.05, LEFT - 0.03, NEAR, FAR, 0.0, 0.05, M["dark"])

    quad("glass", [(GLASS_X, NEAR, SILL_TOP), (GLASS_X, FAR, SILL_TOP),
                   (GLASS_X, FAR, HEIGHT - 0.11), (GLASS_X, NEAR, HEIGHT - 0.11)], M["glass"])

    bm, bm_ch = bmesh.new(), bmesh.new()
    for y in MULLIONS:
        add_box(bm, GLASS_X - 0.03, GLASS_X + MULLION_DEPTH, y, y + MULLION_NOSE, 0.0, HEIGHT - 0.06)
        add_box(bm_ch, GLASS_X - 0.03, GLASS_X + MULLION_DEPTH - 0.035, y + MULLION_NOSE,
                y + MULLION_WIDTH, 0.0, HEIGHT - 0.06)
    mesh_obj("mullions", bm, M["frame"])
    mesh_obj("mullion_channels", bm_ch, M["channel"])
    # white covers on the upper part of each column, as in the reference
    bm = bmesh.new()
    for y in MULLIONS:
        add_box(bm, GLASS_X - 0.03, GLASS_X + MULLION_DEPTH + 0.008, y - 0.008, y + MULLION_NOSE + 0.008,
                2.25, HEIGHT - 0.06)
    mesh_obj("mullion_caps", bm, M["frame"])
    # inner glass skin in front of the columns (a double facade): at grazing angles it
    # washes the far columns into the milky glass wall the reference shows
    skin_x = GLASS_X + MULLION_DEPTH + 0.03
    quad("glass_inner", [(skin_x, NEAR, SILL_TOP), (skin_x, FAR, SILL_TOP), (skin_x, FAR, HEIGHT - 0.11),
                         (skin_x, NEAR, HEIGHT - 0.11)], M["glass_inner"])

    # right wall with pilasters, skirting and small wall-mounted signs
    quad("right_wall", [(RIGHT, NEAR, 0), (RIGHT, NEAR, HEIGHT), (RIGHT, FAR, HEIGHT),
                        (RIGHT, FAR, 0)], M["wall"])
    bm = bmesh.new()
    y = 1.0
    while y < FAR:
        add_box(bm, RIGHT - 0.16, RIGHT, y, y + 0.55, 0.0, HEIGHT)
        y += PILASTER_STEP
    mesh_obj("pilasters", bm, M["wall"])
    box("skirting", RIGHT - 0.012, RIGHT, NEAR, FAR, 0.0, 0.1, M["skirting"])
    bm = bmesh.new()
    y = 1.0
    while y < FAR:
        add_box(bm, RIGHT - 0.16 - 0.06, RIGHT - 0.16, y + 0.15, y + 0.4, 2.55, 2.75)
        y += PILASTER_STEP
    mesh_obj("signs", bm, M["dark"])

    # far end: the corridor runs into a blank wall
    quad("end_wall", [(GLASS_X - 0.05, FAR, 0), (RIGHT, FAR, 0), (RIGHT, FAR, HEIGHT + 0.12),
                      (GLASS_X - 0.05, FAR, HEIGHT + 0.12)], M["wall"])
    box("end_skirting", LEFT, RIGHT, FAR - 0.012, FAR, 0.0, 0.1, M["skirting"])
    # cap the box behind the camera so the room is closed
    quad("back", [(LEFT - 1, NEAR, -0.5), (LEFT - 1, NEAR, HEIGHT + 0.5),
                  (RIGHT, NEAR, HEIGHT + 0.5), (RIGHT, NEAR, -0.5)], M["wall"])

    # ceiling fixtures: downlights, speakers and linear diffusers on the mullion module
    bm_light, bm_spk, bm_lin = bmesh.new(), bmesh.new(), bmesh.new()
    z = HEIGHT - 0.003
    for i, y in enumerate(MULLIONS):
        disc(bm_light, -0.9, y + 1.0, z, 0.05)
        disc(bm_light, 0.75, y + 1.0, z, 0.05)
        if i % 2 == 0:
            disc(bm_spk, -0.1, y + 2.2, z, 0.16)
        else:
            add_box(bm_lin, -1.6, -1.6 + 0.12, y + 1.6, y + 2.8, z - 0.002, z)
    mesh_obj("downlights", bm_light, M["downlight"])
    mesh_obj("speakers", bm_spk, M["speaker"])
    mesh_obj("diffusers", bm_lin, M["diffuser"])


def crown_variants(mat):
    """Canopy pieces for the far forest: a lumpy crown on the upper part of a unit-height,
    unit-width volume, plus a couple of narrow conifers."""
    import random
    from mathutils import noise
    rng = random.Random(11)
    coll = bpy.data.collections.new("crowns")
    for i in range(7):
        bm = bmesh.new()
        if i < 5:
            lumps = [(Vector((0, 0, 0.74)), Vector((0.5, 0.5, 0.25)))]
            for _ in range(rng.randint(4, 6)):
                a = rng.uniform(0, 2 * math.pi)
                r = rng.uniform(0.12, 0.28)
                lumps.append((Vector((r * math.cos(a), r * math.sin(a), rng.uniform(0.72, 0.86))),
                              Vector((0.26, 0.26, 0.14)) * rng.uniform(0.8, 1.2)))
            for c, rad in lumps:
                geo = bmesh.ops.create_icosphere(bm, subdivisions=3, radius=1.0)
                for v in geo["verts"]:
                    d = v.co.normalized()
                    v.co = Vector((d.x * rad.x, d.y * rad.y, d.z * rad.z))
                    v.co += d * 0.05 * noise.fractal(d * 4.0 + c * 7.0, 0.6, 2.0, 3)
                    v.co += c
                    v.co.z = max(v.co.z, 0.5)
        else:
            bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=0.3, radius2=0.0, depth=1.0)
            for v in bm.verts:
                v.co.z += 0.5
        o = mesh_obj(f"crown{i}", bm, mat)
        for c in o.users_collection:
            c.objects.unlink(o)
        coll.objects.link(o)
        for poly in o.data.polygons:
            poly.use_smooth = True
    return coll


def build_forest(M):
    """A dense canopy of small crowns along the forest edge; its top stays a gently
    undulating line, taller toward the left of frame, like the reference."""
    import random
    rng = random.Random(5)
    verts, scales, kinds, spins = [], [], [], []
    for row in range(8):
        a = math.radians(66) + rng.uniform(0, 0.004)
        while a < math.radians(180):
            R = FOREST_R + row * 12.0 + rng.uniform(-4, 4)
            swell = 1 + 0.04 * math.sin(a * 37.0) + 0.025 * math.sin(a * 113.0 + 1.3)
            h = canopy(a, R) * swell * rng.uniform(0.94, 1.04)
            w = h * rng.uniform(0.55, 0.8)
            kind = rng.randrange(7) if rng.random() < 0.03 else rng.randrange(5)
            if kind >= 5:
                w *= 0.7
            verts.append((R * math.cos(a), R * math.sin(a), GROUND_Z))
            scales.append((w, w, h))
            kinds.append(kind)
            spins.append(rng.uniform(0, 2 * math.pi))
            a += w * rng.uniform(0.4, 0.55) / R
    me = bpy.data.meshes.new("forest")
    me.from_pydata(verts, [], [])
    me.attributes.new("tscale", "FLOAT_VECTOR", "POINT").data.foreach_set(
        "vector", [c for sc in scales for c in sc])
    me.attributes.new("variant", "INT", "POINT").data.foreach_set("value", kinds)
    me.attributes.new("spin", "FLOAT", "POINT").data.foreach_set("value", spins)
    forest = link(bpy.data.objects.new("forest", me))

    crowns = crown_variants(M["crowns"])
    ng = bpy.data.node_groups.new("forest", "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    nd, lk = ng.nodes, ng.links.new
    gi, go = nd.new("NodeGroupInput"), nd.new("NodeGroupOutput")
    ci = nd.new("GeometryNodeCollectionInfo")
    ci.inputs["Collection"].default_value = crowns
    ci.inputs["Separate Children"].default_value = True
    ci.inputs["Reset Children"].default_value = True
    inst = nd.new("GeometryNodeInstanceOnPoints")
    inst.inputs["Pick Instance"].default_value = True

    def attr(name, kind):
        a = nd.new("GeometryNodeInputNamedAttribute")
        a.data_type = kind
        a.inputs["Name"].default_value = name
        return a.outputs["Attribute"]

    rot = nd.new("ShaderNodeCombineXYZ")
    lk(attr("spin", "FLOAT"), rot.inputs["Z"])
    lk(gi.outputs[0], inst.inputs["Points"])
    lk(ci.outputs[0], inst.inputs["Instance"])
    lk(attr("variant", "INT"), inst.inputs["Instance Index"])
    lk(attr("tscale", "FLOAT_VECTOR"), inst.inputs["Scale"])
    lk(rot.outputs[0], inst.inputs["Rotation"])
    lk(inst.outputs[0], go.inputs[0])
    forest.modifiers.new("forest", "NODES").node_group = ng
    return forest


def mat_rice(name, mul):
    """Rice leaves: darker at the base, sunlit yellow-green toward the tips, a little
    translucent, faded with distance like the rest of the field."""
    m = bpy.data.materials.new(name)
    n = Nodes(m)
    _, _, z = n.xyz("Object")
    info = n.new("ShaderNodeObjectInfo")
    tip = n.math("ADD", z, n.math("MULTIPLY", n.math("SUBTRACT", info.outputs["Random"], 0.5), 0.5))
    col = n.ramp(tip, [(0.0, srgb(*T["rice"][0])), (0.45, srgb(*T["rice"][1])), (0.95, srgb(*T["rice"][2]))])
    # each paddy grows a slightly different shade; rows run along the camera's right vector
    rot = n.new("ShaderNodeMapping", Rotation=(0, 0, -YAW))
    n.set(rot.inputs[0], n.new("ShaderNodeNewGeometry").outputs["Position"])
    paddy = n.new("ShaderNodeTexBrick", Scale=1.0, **{
        "Mortar Size": 0.0, "Bias": 0.0, "Brick Width": 4000.0, "Row Height": 32.0,
        "Color1": (1.0, 1.0, 1.0, 1.0), "Color2": (0.78, 0.92, 0.7, 1.0)})
    n.set(paddy.inputs["Vector"], rot.outputs[0])
    shade = n.new("ShaderNodeMix", _data_type="RGBA", _blend_type="MULTIPLY")
    shade.inputs[0].default_value = 1.0
    n.set(shade.inputs[6], col)
    n.set(shade.inputs[7], paddy.outputs["Color"])
    col = camera_tint(n, aerial(n, shade.outputs[2]), T[mul])
    leaf = n.principled(col, 0.7, 0.1)
    glow = n.new("ShaderNodeBsdfTranslucent")
    n.set(glow.inputs["Color"], col)
    mix = n.new("ShaderNodeMixShader")
    mix.inputs[0].default_value = 0.3
    n.set(mix.inputs[1], leaf.outputs[0])
    n.set(mix.inputs[2], glow.outputs[0])
    n.output(mix)
    return m


def rice_clumps(name, mat, variants=4):
    """Paddy rice hills: 14-20 thin arching leaves each, unit height, base at the origin."""
    import random
    rng = random.Random(len(name))
    coll = bpy.data.collections.new(name)
    for k in range(variants):
        bm = bmesh.new()
        for _ in range(rng.randint(14, 20)):
            ang = rng.uniform(0, 2 * math.pi)
            out = Vector((math.cos(ang), math.sin(ang), 0))
            side = Vector((-out.y, out.x, 0))
            lean = rng.uniform(0.08, 0.45)
            h = rng.uniform(0.7, 1.0)
            w = rng.uniform(0.012, 0.02)
            base = out * rng.uniform(0.0, 0.04)
            prev = None
            for i in range(6):
                t = i / 5
                c = base + out * lean * h * t ** 1.7 + Vector((0, 0, h * t * (1 - 0.25 * lean * t)))
                half = side * w * (1 - 0.9 * t)
                pair = (bm.verts.new(c - half), bm.verts.new(c + half))
                if prev:
                    bm.faces.new((prev[0], pair[0], pair[1], prev[1]))
                prev = pair
        o = mesh_obj(f"{name}{k}", bm, mat)
        for c in o.users_collection:
            c.objects.unlink(o)
        coll.objects.link(o)
    return coll


def import_asset(name, tint, mul="plant_mul"):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=os.path.join(OUT, "assets", name, f"{name}_1k.gltf"))
    objs = [o for o in bpy.data.objects if o not in before and o.type == "MESH"]
    coll = bpy.data.collections.new(name)
    for o in objs:
        for c in o.users_collection:
            c.objects.unlink(o)
        coll.objects.link(o)
        o.location = (0, 0, 0)
    alpha = os.path.join(OUT, "assets", name, "textures", f"{name}_alpha_1k.jpg")
    for mat in {sl.material for o in objs for sl in o.material_slots}:
        adapt_plant(mat, alpha, tint, T[mul])
    return coll


def scatter(name, coll, x0, x1, y0, y1, density, scale, seed, fade=(14.0, 24.0), start=None, flat=1.0):
    """Geometry-nodes scatter of a collection's pieces over a ground rectangle, thinning
    out between fade[0] and fade[1] metres from the camera (and in over start[0..1]).
    flat < 1 squashes the pieces vertically (wide, low patches for the distance)."""
    bm = bmesh.new()
    nx, ny = 32, 32
    vs = [[bm.verts.new((x0 + (x1 - x0) * i / nx, y0 + (y1 - y0) * j / ny, GROUND_Z))
           for j in range(ny + 1)] for i in range(nx + 1)]
    for i in range(nx):
        for j in range(ny):
            bm.faces.new((vs[i][j], vs[i + 1][j], vs[i + 1][j + 1], vs[i][j + 1]))
    patch = mesh_obj(name, bm)
    ng = bpy.data.node_groups.new(name, "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    nd = ng.nodes
    gi, go = nd.new("NodeGroupInput"), nd.new("NodeGroupOutput")
    dist = nd.new("GeometryNodeDistributePointsOnFaces")
    dist.inputs["Seed"].default_value = seed
    pos = nd.new("GeometryNodeInputPosition")
    far = nd.new("ShaderNodeVectorMath")
    far.operation = "DISTANCE"
    far.inputs[1].default_value = (0.0, 0.0, EYE)
    fall = nd.new("ShaderNodeMapRange")
    fall.inputs["From Min"].default_value = fade[0]
    fall.inputs["From Max"].default_value = fade[1]
    fall.inputs["To Min"].default_value = density
    fall.inputs["To Max"].default_value = 0.0
    ng.links.new(pos.outputs[0], far.inputs[0])
    ng.links.new(far.outputs["Value"], fall.inputs["Value"])
    dens = fall.outputs["Result"]
    if start:
        rise = nd.new("ShaderNodeMapRange")
        rise.inputs["From Min"].default_value = start[0]
        rise.inputs["From Max"].default_value = start[1]
        ng.links.new(far.outputs["Value"], rise.inputs["Value"])
        mul = nd.new("ShaderNodeMath")
        mul.operation = "MULTIPLY"
        ng.links.new(dens, mul.inputs[0])
        ng.links.new(rise.outputs["Result"], mul.inputs[1])
        dens = mul.outputs[0]
    ng.links.new(dens, dist.inputs["Density"])
    ci = nd.new("GeometryNodeCollectionInfo")
    ci.inputs["Collection"].default_value = coll
    ci.inputs["Separate Children"].default_value = True
    ci.inputs["Reset Children"].default_value = True
    inst = nd.new("GeometryNodeInstanceOnPoints")
    inst.inputs["Pick Instance"].default_value = True
    pick = nd.new("FunctionNodeRandomValue")
    pick.data_type = "INT"
    pick.inputs["Max"].default_value = len(coll.objects) - 1
    pick.inputs["Seed"].default_value = seed + 1
    spin = nd.new("FunctionNodeRandomValue")
    spin.data_type = "FLOAT_VECTOR"
    spin.inputs["Max"].default_value = (0.0, 0.0, 2 * math.pi)
    spin.inputs["Seed"].default_value = seed + 2
    size = nd.new("FunctionNodeRandomValue")
    size.data_type = "FLOAT"
    size.inputs["Min"].default_value = scale[0]
    size.inputs["Max"].default_value = scale[1]
    size.inputs["Seed"].default_value = seed + 3
    lk = ng.links.new
    lk(gi.outputs[0], dist.inputs["Mesh"])
    lk(dist.outputs["Points"], inst.inputs["Points"])
    lk(ci.outputs[0], inst.inputs["Instance"])
    lk(pick.outputs[2], inst.inputs["Instance Index"])
    lk(spin.outputs[0], inst.inputs["Rotation"])
    sxyz = nd.new("ShaderNodeCombineXYZ")
    squash = nd.new("ShaderNodeMath")
    squash.operation = "MULTIPLY"
    squash.inputs[1].default_value = flat
    lk(size.outputs[1], sxyz.inputs["X"])
    lk(size.outputs[1], sxyz.inputs["Y"])
    lk(size.outputs[1], squash.inputs[0])
    lk(squash.outputs[0], sxyz.inputs["Z"])
    lk(sxyz.outputs[0], inst.inputs["Scale"])
    lk(inst.outputs[0], go.inputs[0])
    mod = patch.modifiers.new(name, "NODES")
    mod.node_group = ng
    return patch


def build_outside(M):
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=3000)
    ground = mesh_obj("ground", bm, M["field"])
    ground.location = (0, 0, GROUND_Z)

    # the body of the forest: a continuous wall of foliage up to where the crowns begin
    R, segs = FOREST_R + 15.0, 384
    a0, a1 = math.radians(66), math.radians(180)
    bm = bmesh.new()
    prev = None
    for i in range(segs + 1):
        a = a0 + (a1 - a0) * i / segs
        c = Vector((math.cos(a), math.sin(a), 0))
        pair = (bm.verts.new(c * R + Vector((0, 0, GROUND_Z - 1))),
                bm.verts.new(c * (R + 25.0) + Vector((0, 0, GROUND_Z + canopy(a, R) * 0.82))))
        if prev:
            bm.faces.new((prev[0], pair[0], pair[1], prev[1]))
        prev = pair
    trees = mesh_obj("forest_wall", bm, M["crowns"])
    forest = build_forest(M)

    # rice paddy right outside the glass and on into the distance, a few weedy ferns
    # against the building, bushes further out
    fern = import_asset("fern_02", T["fern_tint"])
    rice_near = rice_clumps("rice_near", M["rice_near"])
    rice_mid = rice_clumps("rice_mid", M["rice_mid"])
    rice_far = rice_clumps("rice_far", M["rice_far"])
    scatter("grass_near", rice_near, -95.0, -3.3, -30.0, 95.0, 10.0, (0.6, 0.85), 3, (70.0, 95.0), (18.0, 26.0))
    scatter("grass_mid", rice_mid, -260.0, -3.3, -80.0, 260.0, 2.5, (1.3, 1.9), 13, (200.0, 260.0), (75.0, 95.0))
    scatter("grass_far", rice_far, -620.0, -3.3, -200.0, 620.0, 0.4, (3.0, 4.5), 17, (450.0, 620.0),
            (200.0, 260.0), flat=0.4)
    # leafy weeds at the foot of the glass, where the reference shows big bright leaves
    c = ground_point(330, 468)
    scatter("ferns", fern, c.x - 6, c.x + 6, c.y - 6, c.y + 6, 0.35, (2.0, 3.2), 11, (60.0, 80.0))
    bushes = []
    for i, (px, py, hpx) in enumerate(BUSHES):
        p = ground_point(px, py)
        h = hpx / FOCAL_PX * (p - Vector((0, 0, EYE))).length
        for j in range(3):
            o = bpy.data.objects.new(f"bush{i}_{j}", None)
            o.instance_type = "COLLECTION"
            o.instance_collection = fern
            off = Vector(((j - 1) * h * 0.5, (j % 2) * h * 0.4, 0))
            o.location = p + off
            o.rotation_euler = (0, 0, 1.7 * i + 2.1 * j)
            o.scale = (h * 2.4,) * 3
            link(o)
            bushes.append(o)

    # clouds: camera-facing cards far out in the exact directions seen in the reference
    for i, (px, py, w, h) in enumerate(CLOUDS):
        d = pixel_ray(px, py)
        D = 4000.0
        bm = bmesh.new()
        uvl = bm.loops.layers.uv.new()
        sx, sy = 1.5 * w / FOCAL_PX * D, 1.6 * h / FOCAL_PX * D
        f = bm.faces.new([bm.verts.new((x * sx / 2, y * sy / 2, 0)) for x, y in
                          ((-1, -1), (1, -1), (1, 1), (-1, 1))])
        for loop, uvv in zip(f.loops, ((0, 0), (1, 0), (1, 1), (0, 1))):
            loop[uvl].uv = uvv
        c = mesh_obj(f"cloud{i}", bm, M["cloud"])
        c.location = Vector((0, 0, EYE)) + d * D
        c.rotation_euler = (-d).to_track_quat("Z", "Y").to_euler()
        c.visible_shadow = False
        c.visible_diffuse = False
        c.visible_glossy = False
    return [ground] + [bpy.data.objects[n] for n in (
        "grass_near", "ferns", "grass_mid", "grass_far")] + bushes


def build_world():
    w = bpy.data.worlds.new("sky")
    bpy.context.scene.world = w
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    n = Nodes.__new__(Nodes)
    n.nt = nt
    out = n.new("ShaderNodeOutputWorld")
    tc = n.new("ShaderNodeTexCoord")
    sep = n.new("ShaderNodeSeparateXYZ")
    n.set(sep.inputs[0], tc.outputs["Generated"])
    dz = n.math("MAXIMUM", sep.outputs[2], 0.0)
    elev = n.math("ARCSINE", n.math("MINIMUM", dz, 1.0))
    t = n.math("POWER", n.math("DIVIDE", elev, math.radians(14)), 0.8)
    sky = n.ramp(t, [(0.0, srgb(252, 255, 255)), (0.18, srgb(240, 252, 255)),
                     (0.55, srgb(212, 238, 252)), (1.0, srgb(170, 214, 242))])
    bg = n.new("ShaderNodeBackground", Strength=1.0)
    sky_cam = n.new("ShaderNodeMix", _data_type="RGBA", _blend_type="MULTIPLY")
    sky_cam.inputs[0].default_value = 1.0
    n.set(sky_cam.inputs[6], sky)
    sky_cam.inputs[7].default_value = (*T["sky_mul"], 1.0)
    n.set(bg.inputs["Color"], sky_cam.outputs[2])
    # lighting sky is deeper blue than what the camera sees through the haze
    lit = n.new("ShaderNodeBackground", Strength=T["sky_light_strength"], Color=srgb(*T["sky_light"]))
    lp = n.new("ShaderNodeLightPath")
    mix = n.new("ShaderNodeMixShader")
    n.set(mix.inputs[0], lp.outputs["Is Camera Ray"])
    n.set(mix.inputs[1], lit.outputs[0])
    n.set(mix.inputs[2], bg.outputs[0])
    n.set(out.inputs["Surface"], mix.outputs[0])


def add_sun(name, strength, elev, az, receivers, color=(1.0, 0.96, 0.88), blockers=None):
    sun = bpy.data.lights.new(name, "SUN")
    sun.energy = strength
    sun.color = color
    sun.angle = math.radians(0.6)
    obj = bpy.data.objects.new(name, sun)
    # az/elev give the direction the light travels (az measured from +X toward +Y)
    d = Vector((math.cos(az) * math.cos(elev), math.sin(az) * math.cos(elev), -math.sin(elev)))
    obj.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    link(obj)
    coll = bpy.data.collections.new(name + "_receivers")
    for r in receivers:
        coll.objects.link(r)
    obj.light_linking.receiver_collection = coll
    if blockers is not None:
        coll = bpy.data.collections.new(name + "_blockers")
        for b in blockers:
            coll.objects.link(b)
        obj.light_linking.blocker_collection = coll


def build_lights(outside):
    # Two suns, the way the reference was evidently lit: the paddies are front lit from
    # behind the camera, while the corridor gets a lengthwise band of sun across the floor.
    add_sun("sun_landscape", T["sun_strength"], math.radians(T["sun_out_elev"]),
            math.radians(90 + math.degrees(YAW) + T["sun_out_az"]), outside,
            blockers=outside)    # the corridor itself casts no shadow onto the field

    # bounce card: the reference ceiling is a cooler, brighter green than the sunlit floor
    # and the paddies alone would bounce up to it
    fill = bpy.data.lights.new("ceiling_fill", "AREA")
    rgb_fill = T["ceiling_fill"]
    peak = max(rgb_fill)
    fill.color = tuple(c / peak for c in rgb_fill)
    fill.shape = "RECTANGLE"
    fill.size, fill.size_y = RIGHT - LEFT, FAR - NEAR
    fill.energy = peak * (RIGHT - LEFT) * (FAR - NEAR)
    obj = bpy.data.objects.new("ceiling_fill", fill)
    obj.location = ((LEFT + RIGHT) / 2, (NEAR + FAR) / 2, 0.05)
    obj.rotation_euler = (math.pi, 0, 0)        # emit upward
    obj.visible_camera = False
    obj.visible_glossy = False
    link(obj)
    coll = bpy.data.collections.new("ceiling_fill_receivers")
    for name in ("ceiling", "soffit", "head"):
        coll.objects.link(bpy.data.objects[name])
    obj.light_linking.receiver_collection = coll

    # the same for the inner wall, which the reference keeps a cool pale cyan
    fill = bpy.data.lights.new("wall_fill", "AREA")
    peak = T["wall_fill"]
    fill.color = (0.7, 1.0, 1.0)
    fill.shape = "RECTANGLE"
    fill.size, fill.size_y = FAR - NEAR, HEIGHT
    fill.energy = peak * (FAR - NEAR) * HEIGHT
    obj = bpy.data.objects.new("wall_fill", fill)
    obj.location = (LEFT + 0.3, (NEAR + FAR) / 2, HEIGHT / 2)
    obj.rotation_euler = Vector((1, 0, 0)).to_track_quat("-Z", "Y").to_euler()   # emit toward +X
    obj.visible_camera = False
    obj.visible_glossy = False
    link(obj)
    coll = bpy.data.collections.new("wall_fill_receivers")
    for name in ("right_wall", "pilasters", "skirting", "signs"):
        coll.objects.link(bpy.data.objects[name])
    obj.light_linking.receiver_collection = coll


def build_camera():
    cam = bpy.data.cameras.new("cam")
    cam.sensor_fit = "HORIZONTAL"
    cam.sensor_width = 36.0
    cam.lens = FOCAL_PX / REF_W * 36.0
    cam.shift_y = (VP[1] - REF_H / 2) / REF_W
    cam.clip_start = 0.05
    cam.clip_end = 10000
    obj = bpy.data.objects.new("camera", cam)
    obj.location = (0, 0, EYE)
    obj.rotation_euler = (math.radians(90), 0, YAW)
    link(obj)
    bpy.context.scene.camera = obj


def setup_render():
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = SAMPLES
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.adaptive_threshold = 0.02
    sc.cycles.use_denoising = True
    sc.cycles.denoiser = "OPENIMAGEDENOISE"
    sc.cycles.max_bounces = 8
    sc.cycles.diffuse_bounces = 4
    sc.cycles.glossy_bounces = 4
    sc.cycles.transmission_bounces = 4
    sc.cycles.transparent_max_bounces = 16
    sc.cycles.caustics_reflective = False
    sc.cycles.caustics_refractive = False
    sc.cycles.sample_clamp_indirect = 8.0
    sc.render.resolution_x = round(REF_W * SCALE)
    sc.render.resolution_y = round(REF_H * SCALE)
    sc.render.resolution_percentage = 100
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.look = "None"
    sc.view_settings.exposure = T["exposure"]
    sc.render.image_settings.file_format = "PNG"
    sc.use_nodes = True
    nt = sc.node_tree
    nt.nodes.clear()
    rl = nt.nodes.new("CompositorNodeRLayers")
    gamma = nt.nodes.new("CompositorNodeGamma")
    gamma.inputs["Gamma"].default_value = T["grade_gamma"]
    out = nt.nodes.new("CompositorNodeComposite")
    nt.links.new(rl.outputs["Image"], gamma.inputs["Image"])
    nt.links.new(gamma.outputs["Image"], out.inputs["Image"])


def main():
    reset()
    M = {
        "floor": mat_floor(),
        "ceiling": mat_ceiling(),
        "frame": mat_metal("frame", T["frame"], 0.22, 0.75),
        "channel": mat_metal("channel", T["channel"], 0.15, 0.85, 0.004),
        "sill": mat_metal("sill", (225, 235, 238), 0.35, 0.2),
        "wall": mat_simple("wall", srgb(*T["wall"]), 0.8, 0.3),
        "dark": mat_simple("dark", srgb(30, 40, 42), 0.6),
        "skirting": mat_simple("skirting", srgb(70, 90, 95), 0.4),
        "glass": mat_glass(),
        "glass_inner": mat_glass("glass_inner", (1.0, 1.0, 1.0), graze=(0.72, 0.95, 0.97)),
        "downlight": mat_simple("downlight", srgb(175, 180, 176), 0.3, 0.5, 0.6),
        "speaker": mat_simple("speaker", srgb(200, 205, 200), 0.6),
        "diffuser": mat_simple("diffuser", srgb(165, 170, 166), 0.5),
        "field": mat_field(),
        "crowns": mat_crowns(),
        "rice_near": mat_rice("rice_near", "plant_mul"),
        "rice_mid": mat_rice("rice_mid", "mid_mul"),
        "rice_far": mat_rice("rice_far", "far_mul"),
        "cloud": mat_cloud(),
    }
    build_corridor(M)
    outside = build_outside(M)
    build_world()
    build_lights(outside)
    build_camera()
    setup_render()
    if SAVE:
        os.makedirs(OUT, exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "corridor.blend"))
        bpy.ops.file.make_paths_relative()
        bpy.ops.wm.save_mainfile()
    if RENDER:
        bpy.context.scene.render.filepath = os.path.abspath(RENDER)
        bpy.ops.render.render(write_still=True)


main()
