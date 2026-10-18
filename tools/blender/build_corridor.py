"""Rebuild the sunlit glass corridor from art/corridor/reference.png.

    blender -b --factory-startup --python tools/blender/build_corridor.py -- art/corridor \
        [--render out.png] [--scale 1.0] [--samples 256] [--no-save] [--tune overrides.json]

Writes corridor.blend into the given folder (and renders it when --render is given).
Plants come from the CC0 Poly Haven scans in <folder>/assets (grass_medium_01/02, fern_02).
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
    "sun_floor_strength": 12.0,
    "sun_elev": 35.0,
    "sun_az": 0.0,
    "sky_light": (110, 185, 255),
    "sky_light_strength": 3.4,
    # what the camera sees of the sunlit landscape, as linear multipliers
    "field_mul": (0.235, 0.168, 0.145),
    "plant_mul": (1.28, 0.859, 0.01),
    "tree_mul": (1.14, 0.839, 1.01),
    "sky_mul": (0.79, 0.724, 0.72),
    "exposure": 0.5,
    "grade_gamma": 1.12,        # compositor: slightly darker, deeper mid-tones
    "floor_window": (130, 150, 150),
    "floor_sun": (185, 235, 104),
    "floor_shade": (173, 246, 44),
    "reflect_window": 0.35,
    "reflect_tint": (0.78, 1.0, 0.74),   # floor and glass mirror a little greener
    "reflect_sun": 0.1,
    "reflect_shade": 0.05,
    "ceiling_fill": (0.978, 0.565, 0.848),    # W/m^2 per channel
    "wall_fill": (0.213, 0.01, 1.84),
    "sun_stripes": (1.8, 0.5, 0.3),   # period (m), lit fraction, albedo of the dark bands
    "frame": (163, 170, 144),
    "channel": (114, 200, 207),
    "wall": (205, 222, 225),
    "ceiling": (225, 232, 232),
    "glass_tint": (0.86, 0.97, 0.97),
    "glass_graze": (1.15, 1.15, 1.15),
    "glass_reflect": 0.22,
    "grass_tint": ((45, 80, 10), (130, 180, 30), (200, 225, 80)),
    "fern_tint": ((50, 90, 15), (150, 195, 40), (215, 235, 110)),
    "far_grass_tint": ((85, 135, 20), (150, 195, 40), (205, 228, 85)),
    "far_mul": (0.83, 0.416, 0.948),
    "mid_mul": (2, 0.824, 0.01),
    "plant_value": 1.6,
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
SUN_ELEV = math.radians(T["sun_elev"])
SUN_AZ = math.radians(T["sun_az"])   # 0: light crosses the corridor square to the glass
# the sun patch on the floor is a lengthwise band, as in the reference
SUN_BAND = (-1.375, 0.0)
GROUND_Z = -0.35
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


def mat_floor(name, color, reflect, rough=0.06, stripes=None):
    """Resin floor: diffuse colour plus a mirror layer of fixed strength (the reference
    shows little of the Fresnel brightening a real glossy floor gets at grazing angles)."""
    m = bpy.data.materials.new(name)
    n = Nodes(m)
    # glossy resin with lengthwise trowel streaks
    streak = n.noise(n.scaled(n.coords(), (1.0, 0.06, 1.0)), 5.0, 4.0, 0.6)
    col = n.mix(n.math("MULTIPLY", n.math("SUBTRACT", streak, 0.35), 1.2, clamp=True),
                srgb(*(int(c * 0.6) for c in color)), srgb(*(min(255, c + 45) for c in color)))
    if stripes:
        # the reference's sun band is broken into wavy cross stripes, more of them than
        # the mullions alone would cast; they run square to the line of sight. By the glass
        # they only show as thin dark lines (duty close to 1).
        period, duty, dark = stripes
        x, y, _ = n.xyz("Object")
        q = n.math("ADD", n.math("MULTIPLY", x, -math.sin(YAW)), n.math("MULTIPLY", y, math.cos(YAW)))
        wob = n.math("MULTIPLY", n.math("SUBTRACT", n.noise(n.scaled(n.coords(), (0.5, 1.4, 1.0)), 1.5, 4.0, 0.6), 0.5), 1.3)
        phase = n.math("MULTIPLY", n.math("ADD", q, wob), 2 * math.pi / period)
        wave = n.math("MULTIPLY", n.math("ADD", n.math("SINE", phase), 1.0), 0.5)
        lit = n.new("ShaderNodeMapRange", **{"From Min": 1.0 - duty - 0.12, "From Max": 1.0 - duty + 0.12})
        n.set(lit.inputs["Value"], wave)
        shade = n.new("ShaderNodeMix", _data_type="RGBA", _blend_type="MULTIPLY")
        shade.inputs[0].default_value = 1.0
        n.set(shade.inputs[6], col)
        shade.inputs[7].default_value = (dark, dark, dark, 1.0)
        col = n.mix(lit.outputs[0], shade.outputs[2], col)
    r = n.math("ADD", rough, n.math("MULTIPLY", n.noise(None, 3.0, 2.0), 0.06))
    diffuse = n.principled(col, 0.6, 0.0)
    gloss = n.new("ShaderNodeBsdfGlossy", Color=rgb(*T["reflect_tint"]))
    n.set(gloss.inputs["Roughness"], r)
    mix = n.new("ShaderNodeMixShader")
    mix.inputs[0].default_value = reflect
    n.set(mix.inputs[1], diffuse.outputs[0])
    n.set(mix.inputs[2], gloss.outputs[0])
    n.output(mix)
    return m


def mat_ceiling():
    m = bpy.data.materials.new("ceiling")
    n = Nodes(m)
    x, y, _ = n.xyz("Object")
    lines = n.math("MAXIMUM", n.line_mask(x, 1.2, 0.008, LEFT + 0.3),
                   n.line_mask(y, 1.2, 0.008))
    base = srgb(*T["ceiling"])
    col = n.mix(lines, base, srgb(150, 155, 150))
    speck = n.noise(None, 400.0, 0.0)
    col = n.mix(n.math("MULTIPLY", speck, 0.15), col, srgb(200, 205, 198))
    bump = n.new("ShaderNodeBump", Strength=0.4, Distance=0.004)
    n.set(bump.inputs["Height"], n.math("SUBTRACT", 1.0, lines))
    p = n.principled(col, 0.85, 0.2, Normal=bump.outputs[0])
    n.output(p)
    return m


def mat_glass(name="glass", tint=T["glass_tint"]):
    m = bpy.data.materials.new(name)
    n = Nodes(m)
    fres = n.new("ShaderNodeFresnel", IOR=1.5)
    lw = n.new("ShaderNodeLayerWeight", Blend=0.5)
    # longer path through the pane at grazing angles -> stronger green-cyan tint
    tint_col = n.mix(n.math("POWER", lw.outputs["Facing"], 3.0), rgb(*tint), rgb(*T["glass_graze"]))
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
    """Distance haze: the reference field turns into a pale cyan-green mist past ~250 m."""
    d = n.new("ShaderNodeCameraData").outputs["View Distance"]
    near = n.math("SUBTRACT", 1.0, n.math("EXPONENT", n.math("DIVIDE", d, -150.0)))
    far = n.new("ShaderNodeMapRange", **{"From Min": 170.0, "From Max": 380.0, "_interpolation_type": "SMOOTHSTEP"})
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


def mat_trees():
    m = bpy.data.materials.new("trees")
    n = Nodes(m)
    u, v, _ = n.xyz("UV")
    # crown silhouette: noisy top edge along the strip
    vec = n.new("ShaderNodeCombineXYZ")
    n.set(vec.inputs[0], n.math("MULTIPLY", u, 120.0))
    edge = n.noise(vec.outputs[0], 1.0, 5.0, 0.6)
    top = n.math("ADD", 0.86, n.math("MULTIPLY", n.math("SUBTRACT", edge, 0.5), 0.22))
    alpha = n.math("LESS_THAN", v, top)
    leaf = n.noise(n.scaled(n.coords(), (1.0, 1.0, 1.0)), 0.3, 3.0)
    col = n.mix(n.math("MULTIPLY", leaf, 0.6), srgb(18, 50, 38), srgb(30, 70, 50))
    em = n.principled(camera_tint(n, col, T["tree_mul"]), 1.0, 0.2)
    tr = n.new("ShaderNodeBsdfTransparent")
    mix = n.new("ShaderNodeMixShader")
    n.set(mix.inputs[0], alpha)
    n.set(mix.inputs[1], tr.outputs[0])
    n.set(mix.inputs[2], em.outputs[0])
    n.output(mix)
    m.blend_method = "CLIP"
    return m


def mat_crowns():
    m = bpy.data.materials.new("crowns")
    n = Nodes(m)
    info = n.new("ShaderNodeObjectInfo")
    leaf = n.noise(n.coords(), 6.0, 4.0, 0.65)
    col = n.ramp(n.math("ADD", n.math("MULTIPLY", info.outputs["Random"], 0.6),
                        n.math("MULTIPLY", leaf, 0.4)), [
        (0.25, srgb(12, 50, 52)), (0.5, srgb(24, 72, 72)), (0.75, srgb(42, 95, 88))])
    # leaf clumps with dark gaps between them, and occlusion where crowns crowd together
    clumps = n.noise(n.coords(), 14.0, 4.0, 0.6)
    gaps = n.new("ShaderNodeMapRange", **{"From Min": 0.35, "From Max": 0.6, "To Min": 0.35, "To Max": 1.0})
    n.set(gaps.inputs["Value"], clumps)
    ao = n.new("ShaderNodeAmbientOcclusion", Distance=3.0)
    ao.samples = 8
    shade = n.math("MULTIPLY", gaps.outputs[0], n.math("ADD", 0.35, n.math("MULTIPLY", ao.outputs["AO"], 0.65)))
    dark = n.new("ShaderNodeMix", _data_type="RGBA", _blend_type="MULTIPLY")
    dark.inputs[0].default_value = 1.0
    n.set(dark.inputs[6], col)
    n.set(dark.inputs[7], n.new("ShaderNodeCombineColor").outputs[0])
    comb = dark.inputs[7].links[0].from_node
    for i in range(3):
        n.set(comb.inputs[i], shade)
    col = dark.outputs[2]
    bump = n.new("ShaderNodeBump", Strength=0.4)
    n.set(bump.inputs["Height"], clumps)
    p = n.principled(camera_tint(n, col, T["tree_mul"]), 1.0, 0.1, Normal=bump.outputs[0])
    n.output(p)
    return m


# ---------------------------------------------------------------- geometry

def build_corridor(M):
    edges = [GLASS_X - 0.05, SUN_BAND[0], SUN_BAND[1], RIGHT]
    for name, x0, x1 in zip(("floor_window", "floor_sun", "floor_shade"), edges, edges[1:]):
        quad(name, [(x0, NEAR, 0), (x1, NEAR, 0), (x1, FAR, 0), (x0, FAR, 0)], M[name])
    quad("ceiling", [(LEFT + 0.22, NEAR, HEIGHT), (LEFT + 0.22, FAR, HEIGHT), (RIGHT, FAR, HEIGHT),
                     (RIGHT, NEAR, HEIGHT)], M["ceiling"])
    # window head: white head frame, a plain soffit strip, then a thin dark curtain slot
    box("head", GLASS_X, LEFT, NEAR, FAR, HEIGHT - 0.11, HEIGHT + 0.12, M["frame"])
    quad("soffit", [(LEFT, NEAR, HEIGHT), (LEFT, FAR, HEIGHT), (LEFT + 0.12, FAR, HEIGHT),
                    (LEFT + 0.12, NEAR, HEIGHT)], M["ceiling"])
    box("pocket", LEFT + 0.12, LEFT + 0.22, NEAR, FAR, HEIGHT, HEIGHT + 0.12, M["dark"])

    # sill: low white frame under the glass with a dark kick recess at the floor
    box("sill", GLASS_X - 0.05, LEFT, NEAR, FAR, 0.05, SILL_TOP, M["frame"])
    box("sill_cap", GLASS_X - 0.02, LEFT + 0.025, NEAR, FAR, SILL_TOP - 0.025, SILL_TOP, M["frame"])
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
    """Broadleaf crowns built from a few overlapping leafy lumps, plus a couple of cedar
    cones; unit height, base at the origin."""
    import random
    from mathutils import noise
    rng = random.Random(11)
    coll = bpy.data.collections.new("crowns")
    for i in range(7):
        bm = bmesh.new()
        if i < 5:
            lumps = [(Vector((0, 0, 0.5)), 0.42)]
            for _ in range(rng.randint(3, 5)):
                a = rng.uniform(0, 2 * math.pi)
                r = rng.uniform(0.12, 0.22)
                lumps.append((Vector((r * math.cos(a), r * math.sin(a), rng.uniform(0.35, 0.75))),
                              rng.uniform(0.2, 0.3)))
            for c, r in lumps:
                geo = bmesh.ops.create_icosphere(bm, subdivisions=3, radius=r)
                for v in geo["verts"]:
                    v.co += v.co.normalized() * r * 0.18 * noise.fractal(v.co * 9.0 + c * 5.0, 0.6, 2.0, 3)
                    v.co += c
                    v.co.z = max(v.co.z, 0.02)
        else:
            bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=0.24, radius2=0.0, depth=1.0)
            for v in bm.verts:
                v.co.z += 0.5
                v.co.x *= 1 + 0.2 * noise.noise(v.co * 5.0)
        o = mesh_obj(f"crown{i}", bm, mat)
        for c in o.users_collection:
            c.objects.unlink(o)
        coll.objects.link(o)
        for poly in o.data.polygons:
            poly.use_smooth = True
    return coll


def build_forest(M):
    """Rows of individual crowns along the forest edge, taller toward the left of frame."""
    import random
    rng = random.Random(5)
    axis = math.radians(90) + YAW
    verts, scales, kinds, spins = [], [], [], []
    for row in range(7):
        a = math.radians(66) + rng.uniform(0, 0.004)
        while a < math.radians(180):
            rel = max(-1.5, min(1.5, (a - axis) / math.radians(23)))
            R = 1000.0 + row * 6.0 + rng.uniform(-3, 3)
            h = (14.4 + 6.4 * rel) * rng.uniform(0.8, 1.08) * (1 + 0.035 * row)
            w = h * rng.uniform(0.5, 0.75)
            kind = rng.randrange(7) if rng.random() < 0.3 else rng.randrange(5)
            if kind >= 5:
                w *= 0.6
            verts.append((R * math.cos(a), R * math.sin(a), GROUND_Z))
            scales.append((w, w, h))
            kinds.append(kind)
            spins.append(rng.uniform(0, 2 * math.pi))
            a += w * rng.uniform(0.45, 0.7) / R
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

    # dark understorey behind the crowns so no sky shows between them
    R, segs = 1040.0, 256
    a0, a1 = math.radians(66), math.radians(180)
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new()
    ring = []
    for i in range(segs + 1):
        a = a0 + (a1 - a0) * i / segs
        rel = max(-1.5, min(1.5, (a - math.radians(90) - YAW) / math.radians(23)))
        h = (13.5 + 6.0 * rel) * 0.85 + 2.0
        ring.append((bm.verts.new((R * math.cos(a), R * math.sin(a), GROUND_Z - 1)),
                     bm.verts.new((R * math.cos(a), R * math.sin(a), GROUND_Z - 1 + h)), i / segs))
    for (b0, t0, u0), (b1, t1, u1) in zip(ring, ring[1:]):
        f = bm.faces.new((b0, b1, t1, t0))
        for loop, (uu, vv) in zip(f.loops, ((u0, 0), (u1, 0), (u1, 1), (u0, 1))):
            loop[uv].uv = (uu, vv)
    trees = mesh_obj("tree_belt", bm, M["trees"])
    # and a low dark hedge of undergrowth along the front edge
    bm = bmesh.new()
    prev = None
    for i in range(segs + 1):
        a = a0 + (a1 - a0) * i / segs
        rel = max(-1.5, min(1.5, (a - math.radians(90) - YAW) / math.radians(23)))
        h = (13.5 + 6.0 * rel) * 0.35
        c = (996.0 * math.cos(a), 996.0 * math.sin(a))
        pair = (bm.verts.new((*c, GROUND_Z - 0.5)), bm.verts.new((*c, GROUND_Z + h)))
        if prev:
            bm.faces.new((prev[0], pair[0], pair[1], prev[1]))
        prev = pair
    hedge = mesh_obj("hedge", bm, M["trees"])
    forest = build_forest(M)

    # paddy grass and a few ferns right outside the glass, bushes further out
    grass = import_asset("grass_medium_01", T["grass_tint"])
    grass2 = import_asset("grass_medium_02", T["grass_tint"])
    fern = import_asset("fern_02", T["fern_tint"])
    scatter("grass_near", grass, -24.0, -3.3, -4.0, 24.0, 34.0, (1.1, 1.8), 3, (9.0, 22.0))
    scatter("grass_tufts", grass2, -24.0, -3.3, -4.0, 24.0, 5.0, (1.3, 2.0), 7, (9.0, 22.0))
    scatter("ferns", fern, -12.0, -3.3, 0.0, 16.0, 0.9, (0.9, 1.5), 11, (10.0, 16.0))
    # further out the paddy is still made of plants, just coarser: tufts, then clumps
    mid_grass = import_asset("grass_medium_01", T["far_grass_tint"], "mid_mul")
    far_grass = import_asset("grass_medium_02", T["far_grass_tint"], "far_mul")
    scatter("grass_mid", mid_grass, -95.0, -3.3, -30.0, 95.0, 4.0, (2.4, 3.6), 13, (60.0, 95.0), (16.0, 24.0),
            flat=0.6)
    scatter("grass_far", far_grass, -300.0, -3.3, -80.0, 300.0, 0.5, (4.5, 7.5), 17, (150.0, 260.0),
            (70.0, 95.0), flat=0.3)
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
        "grass_near", "grass_tufts", "ferns", "grass_mid", "grass_far")] + bushes


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
    add_sun("sun_floor", T["sun_floor_strength"], SUN_ELEV, SUN_AZ, [bpy.data.objects["floor_sun"]])

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
    rgb_fill = T["wall_fill"]
    peak = max(rgb_fill)
    fill.color = tuple(c / peak for c in rgb_fill)
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
        "floor_window": mat_floor("floor_window", T["floor_window"], T["reflect_window"], 0.12,
                                  stripes=(T["sun_stripes"][0], 0.9, 0.35)),
        "floor_sun": mat_floor("floor_sun", T["floor_sun"], T["reflect_sun"], 0.05, stripes=T["sun_stripes"]),
        "floor_shade": mat_floor("floor_shade", T["floor_shade"], T["reflect_shade"], 0.15),
        "ceiling": mat_ceiling(),
        "frame": mat_simple("frame", srgb(*T["frame"]), 0.35, 0.5),
        "channel": mat_simple("channel", srgb(*T["channel"]), 0.4, 0.5),
        "wall": mat_simple("wall", srgb(*T["wall"]), 0.8, 0.3),
        "dark": mat_simple("dark", srgb(30, 40, 42), 0.6),
        "skirting": mat_simple("skirting", srgb(70, 90, 95), 0.4),
        "glass": mat_glass(),
        "downlight": mat_simple("downlight", srgb(150, 155, 152), 0.3, 0.5, 0.6),
        "speaker": mat_simple("speaker", srgb(190, 195, 192), 0.6),
        "diffuser": mat_simple("diffuser", srgb(120, 125, 122), 0.5),
        "field": mat_field(),
        "trees": mat_trees(),
        "crowns": mat_crowns(),
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
