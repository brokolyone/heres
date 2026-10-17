"""Builds the sunset creek scene (mossy rock, frogs, taro leaves, grass, stream) and saves it.

blender -b --python tools/creek/build_scene.py -- art/creek
Expects Poly Haven assets in <dir>/assets (tools/creek/fetch_assets.py) and painted
textures in <dir>/textures (tools/creek/make_textures.py).
"""
import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Euler, Matrix, Vector, noise

ROOT = os.path.abspath(sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else "art/creek")
A = os.path.join(ROOT, "assets")
T = os.path.join(ROOT, "textures")
rnd = random.Random(11)

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene


CAM_LOC = Vector((0.0, -1.0, 0.18))
CAM_TILT = math.radians(86.3)
CAM_LENS, CAM_SENSOR = 50.0, 36.0
RES = (1080, 490)


def unproject(px, py, d):
    """World point seen at reference pixel (px, py) at distance d along the view axis."""
    fwd = Vector((0, math.sin(CAM_TILT), -math.cos(CAM_TILT)))
    up = Vector((0, math.cos(CAM_TILT), math.sin(CAM_TILT)))
    k = CAM_SENSOR / 2 / CAM_LENS
    sx = (px / RES[0] - 0.5) * 2 * k
    sy = (0.5 - py / RES[1]) * 2 * k * RES[1] / RES[0]
    return CAM_LOC + d * (fwd + Vector((sx, 0, 0)) + sy * up)


def px_size(d):
    """Metres covered by one reference pixel at distance d."""
    return d * CAM_SENSOR / CAM_LENS / RES[0]


def smooth(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


def lerp_pts(pts, y):
    """Piecewise linear x(y) through (y, x) points."""
    if y <= pts[0][0]:
        return pts[0][1]
    for (y0, x0), (y1, x1) in zip(pts, pts[1:]):
        if y <= y1:
            return x0 + (x1 - x0) * (y - y0) / (y1 - y0)
    return pts[-1][1]


def collection(name, exclude=False):
    c = bpy.data.collections.new(name)
    scene.collection.children.link(c)
    if exclude:
        bpy.context.view_layer.layer_collection.children[name].exclude = True
    return c


def link(obj, coll):
    for c in obj.users_collection:
        c.objects.unlink(obj)
    coll.objects.link(obj)


# ---------------------------------------------------------------- materials
def node(nt, kind, loc=(0, 0), **props):
    n = nt.nodes.new(kind)
    n.location = loc
    for k, v in props.items():
        setattr(n, k, v)
    return n


def image(path, colorspace="sRGB"):
    img = bpy.data.images.load(path, check_existing=True)
    img.colorspace_settings.name = colorspace
    return img


def pbr_layer(nt, folder, name, vector, x=-900, y=0, box=False):
    """Diffuse/rough/normal image nodes of a Poly Haven texture set. Returns (color, rough, normal) sockets."""
    base = os.path.join(A, "tex", name, name)
    out = []
    for i, (suffix, cs) in enumerate((("_Diffuse.jpg", "sRGB"), ("_Rough.jpg", "Non-Color"), ("_nor_gl.jpg", "Non-Color"))):
        t = node(nt, "ShaderNodeTexImage", (x, y - i * 280))
        t.image = image(base + suffix, cs)
        if box:
            t.projection = "BOX"
            t.projection_blend = 0.3
        nt.links.new(vector, t.inputs["Vector"])
        out.append(t)
    nm = node(nt, "ShaderNodeNormalMap", (x + 300, y - 560))
    nt.links.new(out[2].outputs["Color"], nm.inputs["Color"])
    return out[0].outputs["Color"], out[1].outputs["Color"], nm.outputs["Normal"]


def new_material(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = node(nt, "ShaderNodeOutputMaterial", (600, 0))
    return m, nt, out


def foliage_tweak(mat, translucency=0.35, tint=(1.0, 0.95, 0.55), fresh=False):
    """Adds backlit translucency to an imported foliage material (alpha-masked Principled)."""
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    col = bsdf.inputs["Base Color"].links[0].from_socket if bsdf.inputs["Base Color"].is_linked else None
    tr = node(nt, "ShaderNodeBsdfTranslucent", (bsdf.location.x, bsdf.location.y - 500))
    mul = node(nt, "ShaderNodeMix", (bsdf.location.x - 200, bsdf.location.y - 500), data_type="RGBA", blend_type="MULTIPLY")
    mul.inputs["Factor"].default_value = 1.0
    mul.inputs[7].default_value = (tint[0] * 1.7, tint[1] * 1.7, tint[2] * 1.5, 1)
    if col and fresh:
        hs = node(nt, "ShaderNodeHueSaturation", (bsdf.location.x - 400, bsdf.location.y))
        hs.inputs["Hue"].default_value = 0.51
        hs.inputs["Saturation"].default_value = 1.35
        hs.inputs["Value"].default_value = 0.95
        nt.links.new(col, hs.inputs["Color"])
        col = hs.outputs["Color"]
        nt.links.new(col, bsdf.inputs["Base Color"])
    if col:
        nt.links.new(col, mul.inputs[6])
    else:
        mul.inputs[6].default_value = bsdf.inputs["Base Color"].default_value
    nt.links.new(mul.outputs[2], tr.inputs["Color"])
    if bsdf.inputs["Normal"].is_linked:
        nt.links.new(bsdf.inputs["Normal"].links[0].from_socket, tr.inputs["Normal"])
    mix = node(nt, "ShaderNodeMixShader", (bsdf.location.x + 300, bsdf.location.y - 250))
    mix.inputs["Fac"].default_value = translucency
    surf = out.inputs["Surface"].links[0].from_socket
    nt.links.new(surf, mix.inputs[1])
    nt.links.new(tr.outputs[0], mix.inputs[2])
    # the 2k glTF carries the diffuse as JPEG, so the cut-out comes from the separate alpha map
    alpha_path = os.path.join(A, "models", mat.name, "textures", f"{mat.name}_alpha_2k.jpg")
    if os.path.exists(alpha_path):
        diff = next(n for n in nt.nodes if n.type == "TEX_IMAGE" and "diff" in n.image.name)
        at = node(nt, "ShaderNodeTexImage", (diff.location.x, diff.location.y - 300))
        at.image = image(alpha_path, "Non-Color")
        if diff.inputs["Vector"].is_linked:
            nt.links.new(diff.inputs["Vector"].links[0].from_socket, at.inputs["Vector"])
        if bsdf.inputs["Alpha"].is_linked:
            for l in list(bsdf.inputs["Alpha"].links):
                nt.links.remove(l)
        nt.links.new(at.outputs["Color"], bsdf.inputs["Alpha"])
    # keep the alpha cut-out working for the translucent half too
    if bsdf.inputs["Alpha"].is_linked:
        alpha = bsdf.inputs["Alpha"].links[0].from_socket
        transp = node(nt, "ShaderNodeBsdfTransparent", (bsdf.location.x + 300, bsdf.location.y - 450))
        mix2 = node(nt, "ShaderNodeMixShader", (bsdf.location.x + 500, bsdf.location.y - 250))
        nt.links.new(alpha, mix2.inputs["Fac"])
        nt.links.new(transp.outputs[0], mix2.inputs[1])
        nt.links.new(mix.outputs[0], mix2.inputs[2])
        bsdf.inputs["Alpha"].default_value = 1.0
        for l in list(bsdf.inputs["Alpha"].links):
            nt.links.remove(l)
        nt.links.new(mix2.outputs[0], out.inputs["Surface"])
    else:
        nt.links.new(mix.outputs[0], out.inputs["Surface"])
    bsdf.inputs["Specular IOR Level"].default_value = 0.6
    return mat


# ---------------------------------------------------------------- asset import
def import_gltf(name):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=os.path.join(A, "models", name, f"{name}_2k.gltf"))
    objs = [o for o in bpy.data.objects if o not in before]
    meshes = []
    for o in objs:
        if o.type == "MESH":
            o.parent = None
            meshes.append(o)
    for o in objs:
        if o.type != "MESH":
            bpy.data.objects.remove(o)
    for o in meshes:
        o.location = (0, 0, 0)
        o.rotation_euler = (0, 0, 0)
    return meshes


lib = collection("library", exclude=False)
grass_tall = collection("lib_grass_tall")
grass_short = collection("lib_grass_short")
flowers_lib = collection("lib_flowers")
moss_lib = collection("lib_moss")
for name in ("grass_medium_01", "grass_medium_02", "grass_bermuda_01", "periwinkle_plant", "shrub_sorrel_01", "moss_01"):
    for o in import_gltf(name):
        n = o.name
        if name == "grass_medium_01" and ("tall" in n or "mid" in n or "large" in n):
            link(o, grass_tall)
        elif name == "grass_medium_02":
            bpy.data.objects.remove(o)  # mostly dry blades; the reference grass is fresh
            continue
        elif "dead" in n or "flattened" in n or name == "shrub_sorrel_01":
            bpy.data.objects.remove(o)
            continue
        elif name == "moss_01":
            o.data.transform(Matrix.Diagonal((1.0, 1.0, 0.45, 1.0)))  # low cushions, not upright tufts
            link(o, moss_lib)
        elif name == "grass_bermuda_01" or "tiny" in n or "small" in n:
            link(o, grass_short)
        else:
            link(o, flowers_lib)
for c in (lib, grass_tall, grass_short, flowers_lib, moss_lib):
    bpy.context.view_layer.layer_collection.children[c.name].exclude = True
for m in bpy.data.materials:
    if any(k in m.name for k in ("grass", "periwinkle", "sorrel", "moss_01")):
        foliage_tweak(m, 0.5 if "grass" in m.name else 0.35, fresh="grass" in m.name or "moss" in m.name)

world_coll = scene.collection


# ---------------------------------------------------------------- terrain
# stream centreline (x, y) and half-width; it runs away from the camera and bends to the right at the back
CHANNEL = [(0.55, -1.4, 0.85), (0.56, 0.0, 0.57), (0.78, 1.0, 0.51), (1.02, 2.2, 0.49), (1.25, 3.5, 0.5),
           (1.5, 4.8, 0.5), (2.5, 5.8, 0.5), (5.0, 6.3, 0.5)]


def channel(x, y):
    """Signed distance to the stream edge (<0 in the water) and side (+1 left/back bank, -1 right bank)."""
    best = (9e9, 1, 0.5)
    for (x0, y0, w0), (x1, y1, w1) in zip(CHANNEL, CHANNEL[1:]):
        dx, dy = x1 - x0, y1 - y0
        t = max(0.0, min(1.0, ((x - x0) * dx + (y - y0) * dy) / (dx * dx + dy * dy)))
        px, py = x0 + dx * t, y0 + dy * t
        d = math.hypot(x - px, y - py)
        if d < best[0]:
            side = 1 if dx * (y - y0) - dy * (x - x0) > 0 else -1
            best = (d, side, w0 + (w1 - w0) * t)
    d, side, w = best
    w += 0.04 * noise.noise(Vector((x * 2, y * 2, 7.0)))
    # the pool in front of the rock: water reaches the left edge of the frame up to the rock's front face
    pool = (math.hypot((x - 0.05) / 0.42, (y + 0.62) / 0.55) - 1.0) * 0.35
    pool = min(pool, (math.hypot((x + 0.10) / 0.36, (y + 0.08) / 0.17) - 1.0) * 0.12)
    e = d - w
    if pool < e:
        e, side = pool, 1
    return e, side


def left_bank_x(y):
    """x of the left water edge at depth y (for placing things on the bank)."""
    lo, hi = -2.0, 2.0
    for _ in range(30):
        mid = (lo + hi) / 2
        if channel(mid, y)[0] < 0:
            hi = mid
        else:
            lo = mid
    return lo


ROCK_XY = (-0.13, 0.06)


def bank_mound(x, y):
    """The bank swells up behind the rock so the rock reads as its mossy nose, not a loose boulder."""
    d = math.hypot((x - ROCK_XY[0]) / 0.26, (y - ROCK_XY[1] - 0.12) / 0.24)
    return 0.12 * (1 - smooth(0.25, 1.0, d)) + 0.008 * noise.noise(Vector((x * 20, y * 20, 3.0)))


def ground_height(x, y):
    return max(_ground_height(x, y), bank_mound(x, y) if y > ROCK_XY[1] - 0.02 else -1)


def _ground_height(x, y):
    e, side = channel(x, y)
    n = noise.noise(Vector((x * 3, y * 3, 0.5)))
    # far background: a low ridge across the frame rising to the hill on the right
    far = 0.25 * smooth(4.5, 7.5, y) + 0.55 * smooth(4.5, 8.5, y) * smooth(0.8, 2.6, x) + 0.03 * n
    if side > 0:
        land = 0.035 + 0.01 * n + 0.04 * smooth(2.0, 5.0, y)
        land += 0.09 * smooth(0.2, 2.0, y) * (1 - smooth(-0.5, 0.1, x))  # the left bank rises away from the water
    else:
        land = 0.03 + 0.01 * n + 0.1 * smooth(0.8, 2.5, e)
    land = max(land, far)
    if e >= 0:
        return land * smooth(-0.005, 0.06, e) + (-0.01) * (1 - smooth(-0.005, 0.06, e))
    return -0.012 - 0.04 * smooth(0.0, 0.25, -e) + 0.006 * noise.noise(Vector((x * 9, y * 9, 2.0)))


def build_terrain():
    bm = bmesh.new()
    xs = [-1.2 + i * 0.012 for i in range(0, int(4.4 / 0.012))]
    ys = []
    y = -1.2
    while y < 9.0:
        ys.append(y)
        y += 0.012 if y < 1.0 else (0.03 if y < 3 else 0.08)
    grid = []
    for y in ys:
        row = []
        span = 1 + y * 0.35  # widen the far rows so the hills fill the frame
        for x in xs:
            xx = x * span if y > 1 else x
            row.append(bm.verts.new((xx, y, ground_height(xx, y))))
        grid.append(row)
    for j in range(len(ys) - 1):
        for i in range(len(xs) - 1):
            bm.faces.new((grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]))
    me = bpy.data.meshes.new("terrain")
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    obj = bpy.data.objects.new("terrain", me)
    world_coll.objects.link(obj)
    return obj


terrain = build_terrain()

# terrain material: forest ground on the banks, river pebbles under the water, mossy at the water edge
mat, nt, out = new_material("terrain")
tc = node(nt, "ShaderNodeTexCoord", (-1500, 0))
mp = node(nt, "ShaderNodeMapping", (-1300, 0))
mp.inputs["Scale"].default_value = (2.5, 2.5, 2.5)
nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
g_col, g_rough, g_nor = pbr_layer(nt, A, "forest_ground_04", mp.outputs["Vector"], -1000, 600)
mp2 = node(nt, "ShaderNodeMapping", (-1300, -600))
mp2.inputs["Scale"].default_value = (3.5, 3.5, 3.5)
nt.links.new(tc.outputs["Object"], mp2.inputs["Vector"])
r_col, r_rough, r_nor = pbr_layer(nt, A, "river_small_rocks", mp2.outputs["Vector"], -1000, -400)
gras_col, _, gras_nor = pbr_layer(nt, A, "leafy_grass", mp.outputs["Vector"], -1000, -1400)
sep = node(nt, "ShaderNodeSeparateXYZ", (-800, 1100))
nt.links.new(tc.outputs["Object"], sep.inputs[0])
wet = node(nt, "ShaderNodeMapRange", (-600, 1100))
wet.inputs["From Min"].default_value = -0.002
wet.inputs["From Max"].default_value = 0.012
nt.links.new(sep.outputs["Z"], wet.inputs["Value"])
grassy = node(nt, "ShaderNodeMapRange", (-600, 900))
grassy.inputs["From Min"].default_value = 0.015
grassy.inputs["From Max"].default_value = 0.03
nt.links.new(sep.outputs["Z"], grassy.inputs["Value"])
mixc = node(nt, "ShaderNodeMix", (-300, 400), data_type="RGBA")
nt.links.new(wet.outputs[0], mixc.inputs["Factor"])
nt.links.new(r_col, mixc.inputs[6])
nt.links.new(g_col, mixc.inputs[7])
mixg = node(nt, "ShaderNodeMix", (-150, 400), data_type="RGBA")
nt.links.new(grassy.outputs[0], mixg.inputs["Factor"])
nt.links.new(mixc.outputs[2], mixg.inputs[6])
nt.links.new(gras_col, mixg.inputs[7])
mixr = node(nt, "ShaderNodeMix", (-300, 100), data_type="FLOAT")
nt.links.new(wet.outputs[0], mixr.inputs["Factor"])
nt.links.new(r_rough, mixr.inputs[2])
nt.links.new(g_rough, mixr.inputs[3])
mixn = node(nt, "ShaderNodeMix", (-300, -200), data_type="VECTOR")
nt.links.new(wet.outputs[0], mixn.inputs["Factor"])
nt.links.new(r_nor, mixn.inputs[4])
nt.links.new(g_nor, mixn.inputs[5])
bsdf = node(nt, "ShaderNodeBsdfPrincipled", (100, 200))
nt.links.new(mixg.outputs[2], bsdf.inputs["Base Color"])
nt.links.new(mixr.outputs[0], bsdf.inputs["Roughness"])
nt.links.new(mixn.outputs[1], bsdf.inputs["Normal"])
nt.links.new(bsdf.outputs[0], out.inputs["Surface"])
terrain.data.materials.append(mat)


# ---------------------------------------------------------------- scattering with geometry nodes
def weight_group(obj, name, fn):
    vg = obj.vertex_groups.new(name=name)
    mw = obj.matrix_world
    for v in obj.data.vertices:
        w = fn(mw @ v.co)
        if w > 0:
            vg.add([v.index], min(1.0, w), "REPLACE")


def scatter(obj, coll, group, density, smin, smax, tilt, seed, zmin=0.0):
    ng = bpy.data.node_groups.new(f"scatter_{group}_{coll.name}", "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    n = ng.nodes
    gi = n.new("NodeGroupInput")
    go = n.new("NodeGroupOutput")
    attr = n.new("GeometryNodeInputNamedAttribute")
    attr.data_type = "FLOAT"
    attr.inputs["Name"].default_value = group
    mul = n.new("ShaderNodeMath")
    mul.operation = "MULTIPLY"
    mul.inputs[1].default_value = density
    dist = n.new("GeometryNodeDistributePointsOnFaces")
    dist.distribute_method = "RANDOM"
    dist.inputs["Seed"].default_value = seed
    ci = n.new("GeometryNodeCollectionInfo")
    ci.inputs["Collection"].default_value = coll
    ci.inputs["Separate Children"].default_value = True
    ci.inputs["Reset Children"].default_value = True
    iop = n.new("GeometryNodeInstanceOnPoints")
    iop.inputs["Pick Instance"].default_value = True
    ridx = n.new("FunctionNodeRandomValue")
    ridx.data_type = "INT"
    ridx.inputs[4].default_value = 0
    ridx.inputs[5].default_value = len(coll.objects) - 1
    ridx.inputs["Seed"].default_value = seed + 1
    rrot = n.new("FunctionNodeRandomValue")
    rrot.data_type = "FLOAT_VECTOR"
    rrot.inputs[0].default_value = (-tilt, -tilt, 0)
    rrot.inputs[1].default_value = (tilt, tilt, math.tau)
    rrot.inputs["Seed"].default_value = seed + 2
    rsc = n.new("FunctionNodeRandomValue")
    rsc.data_type = "FLOAT"
    rsc.inputs[2].default_value = smin
    rsc.inputs[3].default_value = smax
    rsc.inputs["Seed"].default_value = seed + 3
    join = n.new("GeometryNodeJoinGeometry")
    l = ng.links
    l.new(gi.outputs[0], dist.inputs["Mesh"])
    l.new(attr.outputs["Attribute"], mul.inputs[0])
    l.new(mul.outputs[0], dist.inputs["Density"])
    l.new(dist.outputs["Points"], iop.inputs["Points"])
    l.new(ci.outputs[0], iop.inputs["Instance"])
    l.new(ridx.outputs[2], iop.inputs["Instance Index"])
    l.new(rrot.outputs[0], iop.inputs["Rotation"])
    l.new(rsc.outputs[1], iop.inputs["Scale"])
    l.new(gi.outputs[0], join.inputs[0])
    l.new(iop.outputs[0], join.inputs[0])
    l.new(join.outputs[0], go.inputs[0])
    mod = obj.modifiers.new(group + coll.name, "NODES")
    mod.node_group = ng
    return mod


def bank_weight(p):
    if p.z < 0.012:
        return 0.0
    return 1.0


def near_weight(p):
    # thick near the rock and on the visible bank, fading with distance
    if p.z < 0.012:
        return 0.0
    d = (p - Vector((0, -1.0, 0))).length
    w = max(0.15, 1.0 - 0.25 * d)
    if -0.05 < p.x < 0.4 and 0.0 < p.y < 0.6:
        w *= 0.35  # keep the taro leaves on the bank right of the rock in the open
    if p.y > 0.35:
        w *= 1 - smooth(0.35, 0.6, p.y)  # the back bank gets the taller layer below
    return w * (1 - 0.85 * rock_bank_weight(p))


def rock_bank_weight(p):
    """Moss carries on from the rock over the bank behind it."""
    if p.z < 0.01:
        return 0.0
    d = math.hypot((p.x - ROCK_XY[0]) / 0.24, (p.y - ROCK_XY[1] - 0.08) / 0.2)
    return 1 - smooth(0.5, 1.0, d)


def back_weight(p):
    if p.z < 0.012 or p.y > 2.6:
        return 0.0
    # tall grass on the far left; thin and short toward the gap above the stream
    return smooth(0.3, 0.6, p.y) * (1 - 0.8 * smooth(-0.6, 0.0, p.x))


weight_group(terrain, "grass", near_weight)
weight_group(terrain, "short", bank_weight)
weight_group(terrain, "bankmoss", rock_bank_weight)
weight_group(terrain, "back", back_weight)
weight_group(terrain, "flower", lambda p: 1.0 if p.z > 0.02 and 0.0 < p.y < 2.5 and p.x < 0.8 else 0.0)
weight_group(terrain, "far", lambda p: (1.0 if p.z > 0.025 and p.y > 2.2 and -2.5 < p.x < 4.0 else 0.0) * (1 - 0.85 * smooth(-0.8, 0.0, p.x) * (1 - smooth(1.4, 2.4, p.x))))
scatter(terrain, grass_tall, "grass", 3200, 0.22, 0.4, 0.25, 3)
scatter(terrain, grass_short, "short", 2000, 0.6, 1.2, 0.2, 9)
scatter(terrain, grass_tall, "back", 4200, 0.32, 0.6, 0.2, 41)
scatter(terrain, flowers_lib, "flower", 14, 0.22, 0.4, 0.15, 21)
scatter(terrain, grass_tall, "far", 1600, 0.3, 0.55, 0.2, 33)


# ---------------------------------------------------------------- main mossy rock
def rock_from_set(name, objname, loc, rot, scale):
    src = [o for o in import_gltf(name) if o.name.startswith(objname)][0]
    src.location = loc
    src.rotation_euler = rot
    src.scale = (scale,) * 3
    link(src, world_coll)
    return src


def moss_material(base_mat, name, moss_amount=0.35):
    """Base rock material with a lumpy yellow-green moss layer on upward faces."""
    m = base_mat.copy()
    m.name = name
    nt = m.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    tc = node(nt, "ShaderNodeTexCoord", (-1800, 800))
    mp = node(nt, "ShaderNodeMapping", (-1600, 800))
    mp.inputs["Scale"].default_value = (2.2, 2.2, 2.2)
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    mc, mr, mn = pbr_layer(nt, A, "mossy_rock", mp.outputs["Vector"], -1300, 1400, box=True)
    # mask: faces pointing up + noise breakup
    geo = node(nt, "ShaderNodeNewGeometry", (-1300, 2000))
    sepn = node(nt, "ShaderNodeSeparateXYZ", (-1100, 2000))
    nt.links.new(geo.outputs["Normal"], sepn.inputs[0])
    nz = node(nt, "ShaderNodeTexNoise", (-1300, 2300))
    nz.inputs["Scale"].default_value = 6.0
    nz.inputs["Detail"].default_value = 8.0
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    add = node(nt, "ShaderNodeMath", (-900, 2100), operation="ADD")
    nt.links.new(sepn.outputs["Z"], add.inputs[0])
    nt.links.new(nz.outputs["Fac"], add.inputs[1])
    ramp = node(nt, "ShaderNodeMapRange", (-700, 2100))
    ramp.inputs["From Min"].default_value = 1.0 - moss_amount
    ramp.inputs["From Max"].default_value = 1.15 - moss_amount
    nt.links.new(add.outputs[0], ramp.inputs["Value"])
    # moss colour: texture pushed toward a sunlit yellow-green
    lum = node(nt, "ShaderNodeRGBToBW", (-1000, 1500))
    nt.links.new(mc, lum.inputs[0])
    cush = node(nt, "ShaderNodeTexNoise", (-1100, 1700))
    cush.inputs["Scale"].default_value = 25.0
    cush.inputs["Detail"].default_value = 4.0
    nt.links.new(tc.outputs["Object"], cush.inputs["Vector"])
    lm = node(nt, "ShaderNodeMath", (-850, 1600), operation="MULTIPLY_ADD")
    nt.links.new(lum.outputs[0], lm.inputs[0])
    lm.inputs[1].default_value = 1.4
    nt.links.new(cush.outputs["Fac"], lm.inputs[2])
    tint = node(nt, "ShaderNodeValToRGB", (-700, 1500))
    els = tint.color_ramp.elements
    els[0].position, els[0].color = 0.45, (0.035, 0.06, 0.012, 1)
    els[1].position, els[1].color = 1.05, (0.75, 0.75, 0.12, 1)
    mid = els.new(0.75)
    mid.color = (0.25, 0.33, 0.05, 1)
    nt.links.new(lm.outputs[0], tint.inputs["Fac"])
    base_col = bsdf.inputs["Base Color"].links[0].from_socket
    mixc = node(nt, "ShaderNodeMix", (-400, 900), data_type="RGBA")
    nt.links.new(ramp.outputs[0], mixc.inputs["Factor"])
    nt.links.new(base_col, mixc.inputs[6])
    nt.links.new(tint.outputs["Color"], mixc.inputs[7])
    nt.links.new(mixc.outputs[2], bsdf.inputs["Base Color"])
    if bsdf.inputs["Normal"].is_linked:
        base_n = bsdf.inputs["Normal"].links[0].from_socket
        mixn = node(nt, "ShaderNodeMix", (-400, 600), data_type="VECTOR")
        nt.links.new(ramp.outputs[0], mixn.inputs["Factor"])
        nt.links.new(base_n, mixn.inputs[4])
        cb = node(nt, "ShaderNodeBump", (-600, 700))
        cb.inputs["Strength"].default_value = 0.8
        cb.inputs["Distance"].default_value = 0.004
        nt.links.new(lm.outputs[0], cb.inputs["Height"])
        nt.links.new(mn, cb.inputs["Normal"])
        nt.links.new(cb.outputs[0], mixn.inputs[5])
        nt.links.new(mixn.outputs[1], bsdf.inputs["Normal"])
    rough = node(nt, "ShaderNodeMath", (-400, 400), operation="MAXIMUM")
    rough.inputs[1].default_value = 0.0
    nt.links.new(ramp.outputs[0], rough.inputs[0])
    rough.inputs[1].default_value = 0.85
    bsdf.inputs["Roughness"].default_value = 0.9
    for l in list(bsdf.inputs["Roughness"].links):
        nt.links.remove(l)
    nt.links.new(rough.outputs[0], bsdf.inputs["Roughness"])
    bsdf.inputs["Subsurface Weight"].default_value = 0.08
    bsdf.inputs["Subsurface Radius"].default_value = (0.02, 0.03, 0.005)
    return m


rock = rock_from_set("rock_moss_set_02", "rock_moss_set_02_rock10", (-0.13, 0.06, -0.03), (0, math.radians(15), math.radians(8)), 0.165)
rock.scale = (0.15, 0.17, 0.2)
rock.data.materials[0] = moss_material(rock.data.materials[0], "main_rock_moss", 0.95)
sub = rock.modifiers.new("sub", "SUBSURF")
sub.levels = sub.render_levels = 2
tex = bpy.data.textures.new("moss_lumps", "CLOUDS")
tex.noise_scale = 0.5
tex.noise_depth = 1
disp = rock.modifiers.new("lumps", "DISPLACE")
disp.texture = tex
disp.texture_coords = "OBJECT"
disp.strength = 0.35
disp.mid_level = 0.5
for p in rock.data.polygons:
    p.use_smooth = True
# moss cushions: real moss tufts on every upward face of the rock
rvg = rock.vertex_groups.new(name="moss")
nmat = rock.matrix_world.to_3x3().inverted().transposed()
for v in rock.data.vertices:
    nz = (nmat @ v.normal).normalized().z
    wz = (rock.matrix_world @ v.co).z
    w = smooth(-0.1, 0.5, nz) * smooth(-0.005, 0.01, wz)
    if w > 0:
        rvg.add([v.index], w, "REPLACE")
inv_s = 1 / 0.17
scatter(rock, moss_lib, "moss", 3500, 0.3 * inv_s, 0.55 * inv_s, 0.6, 51)
scatter(terrain, moss_lib, "bankmoss", 90000, 0.3, 0.55, 0.6, 61)

# background rocks in the stream on the right
bg_rocks = [
    ("rock_moss_set_02_rock11", (1.75, 4.6, -0.05), 0.0, 0.24, 0.7),
    ("rock_moss_set_02_rock09", (1.35, 4.35, -0.04), 1.2, 0.22, 0.05),
    ("rock_moss_set_02_rock12", (2.0, 4.9, -0.03), 2.0, 0.22, 0.4),
]
for objname, loc, rz, sc, mossy in bg_rocks:
    r = rock_from_set("rock_moss_set_02", objname, loc, (0, 0, rz), sc)
    r.data.materials[0] = moss_material(r.data.materials[0], objname + "_moss", mossy)
# pebbles/stones half in the water at the left rock base
for i, (objname, loc, sc) in enumerate([("rock_moss_set_02_rock08", (0.07, 0.05, -0.02), 0.05),
                                         ("rock_moss_set_02_rock09", (-0.33, -0.12, -0.02), 0.06)]):
    r = rock_from_set("rock_moss_set_02", objname, loc, (0, 0, i * 2.0), sc)
    r.data.materials[0] = moss_material(r.data.materials[0], f"pebble{i}_moss", 0.5)
for o in list(bpy.data.objects):
    if o.name.startswith("rock_moss_set_02") and o.users_collection and o.users_collection[0] == scene.collection \
            and o.location.length == 0:
        bpy.data.objects.remove(o)


# ---------------------------------------------------------------- water
def build_water():
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=560, y_subdivisions=1120, size=1)
    w = bpy.context.object
    w.name = "water"
    w.scale = (2.8, 5.6, 1)
    w.location = (0.8, 1.6, 0.0)
    bpy.ops.object.transform_apply(scale=True)
    link(w, world_coll)
    for i, (kind, size, strength, stretch) in enumerate((("waves", 0.03, 0.005, 2.5), ("chop", 0.008, 0.0045, 1.8))):
        tx = bpy.data.textures.new("water_" + kind, "CLOUDS")
        tx.noise_scale = size
        tx.noise_depth = 2
        empty = bpy.data.objects.new("water_tex_" + kind, None)
        empty.scale = (1, stretch, 1)
        empty.rotation_euler = (0, 0, math.radians(25))
        world_coll.objects.link(empty)
        d = w.modifiers.new(kind, "DISPLACE")
        d.texture = tx
        d.texture_coords = "OBJECT"
        d.texture_coords_object = empty
        d.strength = strength
    for p in w.data.polygons:
        p.use_smooth = True
    m, nt, out = new_material("water")
    b = node(nt, "ShaderNodeBsdfPrincipled", (0, 0))
    b.inputs["Base Color"].default_value = (0.85, 0.92, 0.95, 1)
    b.inputs["Roughness"].default_value = 0.025
    b.inputs["IOR"].default_value = 1.333
    b.inputs["Specular IOR Level"].default_value = 0.42
    b.inputs["Transmission Weight"].default_value = 1.0
    nz = node(nt, "ShaderNodeTexNoise", (-600, -300))
    nz.inputs["Scale"].default_value = 140
    nz.inputs["Detail"].default_value = 4
    tc = node(nt, "ShaderNodeTexCoord", (-1000, -300))
    mpw = node(nt, "ShaderNodeMapping", (-800, -300))
    mpw.inputs["Scale"].default_value = (1.0, 0.5, 1.0)
    nt.links.new(tc.outputs["Object"], mpw.inputs["Vector"])
    nt.links.new(mpw.outputs[0], nz.inputs["Vector"])
    bump = node(nt, "ShaderNodeBump", (-300, -300))
    bump.inputs["Strength"].default_value = 0.6
    bump.inputs["Distance"].default_value = 0.002
    nt.links.new(nz.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs[0], b.inputs["Normal"])
    vol = node(nt, "ShaderNodeVolumeAbsorption", (0, -400))
    vol.inputs["Color"].default_value = (0.7, 0.78, 0.7, 1)
    vol.inputs["Density"].default_value = 3.0
    nt.links.new(b.outputs[0], out.inputs["Surface"])
    nt.links.new(vol.outputs[0], out.inputs["Volume"])
    w.data.materials.append(m)
    return w


water = build_water()


# ---------------------------------------------------------------- taro leaves
def tex_material(name, color, bump=None, translucency=None, rough=0.35, spec=0.5):
    m, nt, out = new_material(name)
    uv = node(nt, "ShaderNodeTexCoord", (-900, 0))
    c = node(nt, "ShaderNodeTexImage", (-600, 200))
    c.image = image(os.path.join(T, color))
    nt.links.new(uv.outputs["UV"], c.inputs["Vector"])
    b = node(nt, "ShaderNodeBsdfPrincipled", (0, 200))
    nt.links.new(c.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = rough
    b.inputs["Specular IOR Level"].default_value = spec
    if bump:
        bi = node(nt, "ShaderNodeTexImage", (-600, -200))
        bi.image = image(os.path.join(T, bump), "Non-Color")
        nt.links.new(uv.outputs["UV"], bi.inputs["Vector"])
        bn = node(nt, "ShaderNodeBump", (-250, -200))
        bn.inputs["Strength"].default_value = 0.4
        bn.inputs["Distance"].default_value = 0.0008
        nt.links.new(bi.outputs["Color"], bn.inputs["Height"])
        nt.links.new(bn.outputs[0], b.inputs["Normal"])
    shader = b.outputs[0]
    if translucency:
        ti = node(nt, "ShaderNodeTexImage", (-600, -600))
        ti.image = image(os.path.join(T, translucency), "Non-Color")
        nt.links.new(uv.outputs["UV"], ti.inputs["Vector"])
        tr = node(nt, "ShaderNodeBsdfTranslucent", (0, -500))
        bright = node(nt, "ShaderNodeMix", (-250, -500), data_type="RGBA", blend_type="MULTIPLY")
        bright.inputs["Factor"].default_value = 1.0
        bright.inputs[7].default_value = (1.6, 1.5, 0.45, 1)
        nt.links.new(c.outputs["Color"], bright.inputs[6])
        nt.links.new(bright.outputs[2], tr.inputs["Color"])
        mix = node(nt, "ShaderNodeMixShader", (300, 0))
        mfac = node(nt, "ShaderNodeMath", (0, -800), operation="MULTIPLY")
        mfac.inputs[1].default_value = 0.22
        nt.links.new(ti.outputs["Color"], mfac.inputs[0])
        nt.links.new(mfac.outputs[0], mix.inputs["Fac"])
        nt.links.new(b.outputs[0], mix.inputs[1])
        nt.links.new(tr.outputs[0], mix.inputs[2])
        shader = mix.outputs[0]
    nt.links.new(shader, out.inputs["Surface"])
    return m


leaf_mat = tex_material("taro_leaf", "taro_leaf_color.png", "taro_leaf_bump.png", "taro_leaf_translucency.png", 0.42, 0.4)
stem_mat = tex_material("taro_stem", "taro_stem_color.png", rough=0.45)
leaf_coll = collection("taro")


def leaf_mesh(length, width, fold, droop, notch=0.18):
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new()
    nu, nv = 14, 24
    verts = []
    for j in range(nv + 1):
        t = j / nv
        w = width * math.sin(math.pi * (0.12 + 0.88 * t)) ** 0.85 * (1 - 0.25 * t)
        row = []
        for i in range(nu + 1):
            u = i / nu * 2 - 1
            x = u * w
            s = length * t + notch * length * (1 - abs(u)) * (1 - t) ** 6 - notch * length * 0.6
            z = fold * abs(x) ** 1.3 * 6 - droop * (s / length) ** 2 * length
            row.append((bm.verts.new((x, s, z)), (i / nu, t)))
        verts.append(row)
    for j in range(nv):
        for i in range(nu):
            q = [verts[j][i], verts[j][i + 1], verts[j + 1][i + 1], verts[j + 1][i]]
            f = bm.faces.new([v for v, _ in q])
            for loop, (_, uv) in zip(f.loops, q):
                loop[uvl].uv = uv
    me = bpy.data.meshes.new("taro_leaf")
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    me.materials.append(leaf_mat)
    return me


def stem_mesh(points, radius):
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new()
    seg = 8
    rings = []
    for k, p in enumerate(points):
        nxt = points[min(k + 1, len(points) - 1)]
        prv = points[max(k - 1, 0)]
        d = (nxt - prv).normalized()
        a = d.orthogonal().normalized()
        b = d.cross(a)
        r = radius * (1 - 0.35 * k / len(points))
        rings.append([bm.verts.new(p + (a * math.cos(i / seg * math.tau) + b * math.sin(i / seg * math.tau)) * r)
                      for i in range(seg)])
    for k in range(len(rings) - 1):
        for i in range(seg):
            f = bm.faces.new((rings[k][i], rings[k][(i + 1) % seg], rings[k + 1][(i + 1) % seg], rings[k + 1][i]))
            for loop, uv in zip(f.loops, ((i / seg, k / len(rings)), ((i + 1) / seg, k / len(rings)),
                                          ((i + 1) / seg, (k + 1) / len(rings)), (i / seg, (k + 1) / len(rings)))):
                loop[uvl].uv = uv
    me = bpy.data.meshes.new("taro_stem")
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    me.materials.append(stem_mat)
    return me


def taro(px, py, d, size_px, tip, tilt, droop=0.10, fold=0.05, lean=0.25):
    """Leaf blade seen at reference pixel (px, py), distance d, length size_px pixels.

    tip: direction the tip points in the image, degrees (0 = right, 90 = up).
    tilt: how far the blade turns away from facing the camera (0 = face-on, 90 = edge-on).
    """
    size = size_px * px_size(d)
    attach = unproject(px, py, d)
    # stem: from the ground below and slightly behind, curving up to the blade base
    gx = attach.x + rnd.uniform(-1, 1) * lean * size - math.cos(math.radians(tip)) * size * 0.6
    gy = attach.y + rnd.uniform(0.0, 0.5) * size
    gz = min(ground_height(gx, gy), 0.0) if ground_height(gx, gy) < 0.005 else ground_height(gx, gy)
    base = Vector((gx, gy, gz - 0.01))
    blade_base = attach - Vector((math.cos(math.radians(tip)), 0, math.sin(math.radians(tip)))) * size * 0.45
    pts = []
    for k in range(13):
        t = k / 12
        p = base.lerp(blade_base, t)
        p.x = base.x + (blade_base.x - base.x) * t ** 2.2       # rises vertically, bends at the top
        p.y = base.y + (blade_base.y - base.y) * t ** 2.2
        pts.append(p)
    stem = bpy.data.objects.new("taro_stem", stem_mesh(pts, max(0.0018, size * 0.045)))
    leaf_coll.objects.link(stem)
    leaf = bpy.data.objects.new("taro_leaf", leaf_mesh(size, size * 0.42, fold, droop))
    leaf_coll.objects.link(leaf)
    leaf.location = blade_base
    # blade lies along local +Y; stand it up facing the camera (-Y), rotate to the tip angle, then tilt away
    m = Matrix.Rotation(math.radians(tilt), 4, "Z") @ Matrix.Rotation(-math.radians(tip - 90), 4, "Y") \
        @ Matrix.Rotation(math.radians(90 - 8), 4, "X")
    leaf.rotation_euler = m.to_euler()
    return stem, leaf


# (px, py, distance, length px, tip angle, tilt) measured on the reference frame
TARO = [
    # left foreground cluster, close and out of focus
    (90, 150, 0.55, 120, 115, 35),
    (170, 185, 0.55, 90, -10, 55),
    (30, 232, 0.5, 80, 150, 40),
    (132, 243, 0.55, 50, 20, 50),
    (185, 410, 0.42, 140, 20, 60),
    (265, 430, 0.42, 120, -15, 65),
    (60, 440, 0.4, 90, 160, 50),
    # centre, on the bank right of the rock
    (445, 197, 1.2, 140, 150, 30),
    (630, 230, 1.15, 150, 5, 58),
    (575, 290, 1.05, 110, -40, 20),
    (790, 270, 1.4, 70, 200, 60),
    # right, far side
    (755, 185, 1.6, 85, 140, 35),
    (820, 203, 1.6, 75, 5, 70),
    (760, 262, 1.5, 60, 210, 50),
    (700, 238, 1.5, 45, 60, 45),
    # right edge, foreground
    (1040, 300, 0.75, 140, 205, 30),
    (1028, 385, 0.7, 90, 235, 70),
]
for args in TARO:
    taro(*args)


# ---------------------------------------------------------------- pink flowers on thin stalks and yellow stalks
petal_mat = tex_material("flower_petal", "flower_petal_color.png", None, "taro_leaf_translucency.png", rough=0.5)
_pb = next(n for n in petal_mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
_pc = next(n for n in petal_mat.node_tree.nodes if n.type == "TEX_IMAGE")
petal_mat.node_tree.links.new(_pc.outputs["Color"], _pb.inputs["Emission Color"])
_pb.inputs["Emission Strength"].default_value = 1.2
stalk_mat, snt, sout = new_material("stalk")
sb = node(snt, "ShaderNodeBsdfPrincipled")
sb.inputs["Base Color"].default_value = (0.55, 0.6, 0.12, 1)
sb.inputs["Roughness"].default_value = 0.5
st = node(snt, "ShaderNodeBsdfTranslucent")
st.inputs["Color"].default_value = (0.9, 0.85, 0.15, 1)
sm = node(snt, "ShaderNodeMixShader")
sm.inputs["Fac"].default_value = 0.55
snt.links.new(sb.outputs[0], sm.inputs[1])
snt.links.new(st.outputs[0], sm.inputs[2])
snt.links.new(sm.outputs[0], sout.inputs["Surface"])
flower_coll = collection("flowers")


def flower(base, height, bend, yaw, head=0.012, open_=0.7):
    base = Vector(base)
    d = Vector((math.sin(yaw), math.cos(yaw), 0))
    pts = [base + Vector((0, 0, height * k / 10)) + d * bend * (k / 10) ** 2 for k in range(11)]
    me = stem_mesh(pts, 0.0008)
    me.materials[0] = stalk_mat
    s = bpy.data.objects.new("stalk", me)
    flower_coll.objects.link(s)
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new()
    for k in range(5):
        a = k / 5 * math.tau
        c, sn = math.cos(a), math.sin(a)
        pts2 = [Vector((0, 0, 0)), Vector((c * 0.5 - sn * 0.35, sn * 0.5 + c * 0.35, open_ * 0.4)) * head,
                Vector((c, sn, open_)) * head, Vector((c * 0.5 + sn * 0.35, sn * 0.5 - c * 0.35, open_ * 0.4)) * head]
        f = bm.faces.new([bm.verts.new(p) for p in pts2])
        for loop, uv in zip(f.loops, ((0.5, 0.5), (0.2, 0.8), (0.5, 1.0), (0.8, 0.8))):
            loop[uvl].uv = uv
    me = bpy.data.meshes.new("flower_head")
    bm.to_mesh(me)
    bm.free()
    me.materials.append(petal_mat)
    h = bpy.data.objects.new("flower_head", me)
    h.location = pts[-1]
    h.rotation_euler = (rnd.uniform(0.5, 1.4), 0, rnd.uniform(0, math.tau))
    flower_coll.objects.link(h)


def ground_below(p):
    return max(ground_height(p.x, p.y), -0.012)


# pink flower heads floating above the grass, by reference pixel; (px, py, distance)
FLOWERS = [(135, 48, 2.6), (178, 47, 2.8), (222, 78, 2.0), (168, 95, 1.6), (305, 45, 2.4), (318, 52, 2.4),
           (452, 92, 2.2), (500, 113, 1.7), (512, 118, 1.7), (520, 104, 2.0), (553, 88, 2.8), (528, 205, 1.3),
           (494, 182, 1.3), (85, 98, 2.4), (270, 70, 3.0), (370, 60, 3.2), (420, 75, 2.8), (600, 95, 3.5),
           (1048, 108, 0.9), (1058, 150, 0.9), (1030, 180, 0.9), (955, 98, 4.0), (900, 110, 4.2)]
for px, py, d in FLOWERS:
    head = unproject(px, py, d)
    base = Vector((head.x + rnd.uniform(-0.02, 0.02), head.y, 0))
    base.z = ground_below(base)
    flower(base, head.z - base.z, rnd.uniform(-0.02, 0.02), rnd.uniform(0, math.tau),
           px_size(d) * rnd.uniform(12, 17))

# backlit yellow grass blades and stalks: (px range, py top range, distance range, count)
REEDS = [((0, 85), (200, 330), (0.45, 0.6), 8), ((480, 570), (125, 205), (1.2, 1.4), 16),
         ((1030, 1080), (100, 250), (0.8, 0.95), 10), ((600, 740), (150, 230), (1.3, 1.7), 10),
         ((90, 230), (90, 160), (1.4, 1.9), 12)]
for (x0, x1), (y0, y1), (d0, d1), count in REEDS:
    for i in range(count):
        top = unproject(rnd.uniform(x0, x1), rnd.uniform(y0, y1), rnd.uniform(d0, d1))
        bend = Vector((rnd.uniform(-1, 1), rnd.uniform(-0.3, 0.3), 0)) * rnd.uniform(0.01, 0.05)
        base = Vector((top.x - bend.x, top.y - bend.y, 0))
        base.z = ground_below(base) - 0.005
        pts = [base.lerp(top, k / 10) + bend * ((k / 10) ** 2 - k / 10) for k in range(11)]
        me = stem_mesh(pts, rnd.uniform(0.0007, 0.0014))
        me.materials[0] = stalk_mat
        flower_coll.objects.link(bpy.data.objects.new("reed", me))


# ---------------------------------------------------------------- frogs
frog_coll = collection("frogs")


def frog(name, loc, yaw, size, skin):
    s = size
    parts = []

    def ball(co, r, scale=(1, 1, 1), rot=(0, 0, 0)):
        bpy.ops.mesh.primitive_uv_sphere_add(radius=r * s, segments=24, ring_count=12, location=Vector(co) * s,
                                             rotation=rot, scale=scale)
        parts.append(bpy.context.object)

    ball((0, 0, 0.22), 0.42, (0.75, 1.0, 0.55), (math.radians(-18), 0, 0))   # body
    ball((0, 0.38, 0.30), 0.30, (0.9, 0.85, 0.55))                          # head
    for sx in (-1, 1):
        ball((sx * 0.16, 0.45, 0.43), 0.11)                                 # eye bumps
        ball((sx * 0.30, -0.15, 0.14), 0.22, (0.55, 1.0, 0.45))            # thigh
        ball((sx * 0.30, 0.10, 0.06), 0.13, (0.45, 1.0, 0.35))             # foot
        ball((sx * 0.26, 0.42, 0.10), 0.10, (0.4, 0.4, 1.0))               # front leg
    bpy.ops.object.select_all(action="DESELECT")
    for o in parts:
        o.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    obj = bpy.context.object
    obj.name = name
    rm = obj.modifiers.new("fuse", "REMESH")
    rm.mode = "VOXEL"
    rm.voxel_size = s * 0.025
    sm = obj.modifiers.new("smooth", "SMOOTH")
    sm.iterations = 6
    bpy.ops.object.modifier_apply(modifier="fuse")
    bpy.ops.object.modifier_apply(modifier="smooth")
    link(obj, frog_coll)
    me = obj.data
    while me.uv_layers:
        me.uv_layers.remove(me.uv_layers[0])
    # spherical UVs: U around, V from belly to back
    uvl = me.uv_layers.new()
    for poly in me.polygons:
        for li in poly.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            c = co - Vector((0, 0.1 * s, 0.22 * s))
            uvl.data[li].uv = ((math.atan2(c.x, c.y) / math.tau) % 1.0, 0.5 + 0.5 * max(-1, min(1, c.z / (0.3 * s))))
    for p in me.polygons:
        p.use_smooth = True
    m = tex_material(name + "_skin", skin, "frog_bump.png", rough=0.4, spec=0.35)
    b = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    b.inputs["Subsurface Weight"].default_value = 0.15
    b.inputs["Subsurface Radius"].default_value = (0.004, 0.003, 0.001)
    me.materials.append(m)
    # eyes
    eye_m, ent, eout = new_material(name + "_eye")
    eb = node(ent, "ShaderNodeBsdfPrincipled")
    eb.inputs["Base Color"].default_value = (0.05, 0.03, 0.01, 1)
    eb.inputs["Roughness"].default_value = 0.05
    ent.links.new(eb.outputs[0], eout.inputs["Surface"])
    for sx in (-1, 1):
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.075 * s, location=(sx * 0.19 * s, 0.50 * s, 0.45 * s), segments=16,
                                             ring_count=8)
        e = bpy.context.object
        e.data.materials.append(eye_m)
        link(e, frog_coll)
        e.parent = obj
    obj.location = loc
    obj.rotation_euler = (0, 0, math.radians(yaw))
    return obj


def on_rock(x, y):
    bpy.context.view_layer.update()
    deps = bpy.context.evaluated_depsgraph_get()
    ev = rock.evaluated_get(deps)
    inv = ev.matrix_world.inverted()
    o = inv @ Vector((x, y, 1.0))
    d = (inv.to_3x3() @ Vector((0, 0, -1))).normalized()
    hit, loc, *_ = ev.ray_cast(o, d)
    return (x, y, (ev.matrix_world @ loc).z - 0.002) if hit else (x, y, 0.08)


p1 = unproject(285, 290, 1.02)
p2 = unproject(553, 350, 0.98)
frog("frog_top", on_rock(p1.x, p1.y), -70, 0.048, "frog_green_color.png")
frog("frog_edge", on_rock(p2.x, p2.y), 150, 0.03, "frog_brown_color.png")


# ---------------------------------------------------------------- lights, world, camera
world = bpy.data.worlds.new("sunset")
scene.world = world
world.use_nodes = True
wn = world.node_tree
wn.nodes.clear()
env = node(wn, "ShaderNodeTexEnvironment", (-400, 0))
env.image = bpy.data.images.load(os.path.join(A, "hdri", "rosendal_park_sunset_puresky_4k.exr"))
wtc = node(wn, "ShaderNodeTexCoord", (-900, 0))
wmp = node(wn, "ShaderNodeMapping", (-700, 0))
SUN_AZ = math.radians(-15)   # sun direction measured from +Y toward +X (behind the scene, slightly left)
SUN_EL = math.radians(16)
wn.links.new(wtc.outputs["Generated"], wmp.inputs["Vector"])
wn.links.new(wmp.outputs[0], env.inputs["Vector"])
bg = node(wn, "ShaderNodeBackground", (-100, 0))
bg.inputs["Strength"].default_value = 0.65
wo = node(wn, "ShaderNodeOutputWorld", (200, 0))
wn.links.new(env.outputs["Color"], bg.inputs["Color"])
# the sky the camera sees directly is the warm cream of the reference; lighting keeps the HDRI colours
cam_bg = node(wn, "ShaderNodeBackground", (-100, -200))
tint = node(wn, "ShaderNodeMix", (-250, -200), data_type="RGBA", blend_type="MULTIPLY")
tint.inputs["Factor"].default_value = 1.0
tint.inputs[7].default_value = (1.0, 0.94, 0.8, 1)
wn.links.new(env.outputs["Color"], tint.inputs[6])
wn.links.new(tint.outputs[2], cam_bg.inputs["Color"])
cam_bg.inputs["Strength"].default_value = 2.6
lp = node(wn, "ShaderNodeLightPath", (-300, 300))
wmix = node(wn, "ShaderNodeMixShader", (50, 0))
wn.links.new(lp.outputs["Is Camera Ray"], wmix.inputs["Fac"])
# reflections in the stream read cooler and dimmer than the sky around the sun
gl_bg = node(wn, "ShaderNodeBackground", (-100, 200))
gl_tint = node(wn, "ShaderNodeMix", (-250, 200), data_type="RGBA", blend_type="MULTIPLY")
gl_tint.inputs["Factor"].default_value = 1.0
gl_tint.inputs[7].default_value = (0.42, 0.5, 0.6, 1)
wn.links.new(env.outputs["Color"], gl_tint.inputs[6])
wn.links.new(gl_tint.outputs[2], gl_bg.inputs["Color"])
gmix = node(wn, "ShaderNodeMixShader", (-50, 100))
wn.links.new(lp.outputs["Is Glossy Ray"], gmix.inputs["Fac"])
wn.links.new(bg.outputs[0], gmix.inputs[1])
wn.links.new(gl_bg.outputs[0], gmix.inputs[2])
wn.links.new(gmix.outputs[0], wmix.inputs[1])
wn.links.new(cam_bg.outputs[0], wmix.inputs[2])
wn.links.new(wmix.outputs[0], wo.inputs["Surface"])


def hdri_sun_rotation():
    """Rotate the HDRI so its brightest spot lines up with the sun lamp."""
    import numpy as np
    img = env.image
    w, h = img.size
    px = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(px)
    lum = px.reshape(h, w, 4)[..., :3].sum(2)
    u = (int(lum.argmax()) % w) / w
    hdri_az = (0.5 - u) * math.tau                           # Cycles equirect: u=0.5 looks along +X
    target = math.atan2(math.cos(SUN_AZ), math.sin(SUN_AZ))  # sun lamp azimuth from +X
    return hdri_az - target


wmp.inputs["Rotation"].default_value = (0, 0, hdri_sun_rotation())

sun_data = bpy.data.lights.new("sun", "SUN")
sun_data.energy = 18.0
sun_data.angle = math.radians(1.2)
sun_data.color = (1.0, 0.8, 0.5)
sun = bpy.data.objects.new("sun", sun_data)
world_coll.objects.link(sun)
d = Vector((math.sin(SUN_AZ) * math.cos(SUN_EL), math.cos(SUN_AZ) * math.cos(SUN_EL), math.sin(SUN_EL)))
sun.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()

cam_data = bpy.data.cameras.new("cam")
cam_data.lens = 50
cam_data.sensor_width = 36
cam_data.dof.use_dof = True
cam_data.dof.aperture_fstop = 5.6
cam_data.clip_start = 0.01
cam = bpy.data.objects.new("cam", cam_data)
world_coll.objects.link(cam)
cam.location = CAM_LOC
cam.rotation_euler = (CAM_TILT, 0, 0)
focus = bpy.data.objects.new("focus", None)
focus.location = (-0.12, 0.0, 0.07)
world_coll.objects.link(focus)
cam_data.dof.focus_object = focus
scene.camera = cam

# ---------------------------------------------------------------- render
r = scene.render
r.engine = "CYCLES"
r.resolution_x, r.resolution_y = 1080, 490
r.resolution_percentage = 100
scene.cycles.device = "CPU"
scene.cycles.samples = 160
scene.cycles.use_denoising = True
scene.cycles.max_bounces = 8
scene.cycles.transmission_bounces = 8
scene.cycles.volume_bounces = 1
scene.cycles.caustics_reflective = False
scene.cycles.caustics_refractive = False
scene.cycles.blur_glossy = 1.0
scene.view_settings.view_transform = "AgX"
scene.view_settings.look = "AgX - Medium Low Contrast"
scene.view_settings.exposure = 0.7
scene.view_layers[0].use_pass_mist = True
world.mist_settings.start = 1.6
world.mist_settings.depth = 6.0
world.mist_settings.falloff = "LINEAR"

# compositor: depth haze toward the warm sky colour + soft glow
scene.use_nodes = True
ct = scene.node_tree
ct.nodes.clear()
rl = node(ct, "CompositorNodeRLayers", (-600, 0))
mixh = node(ct, "CompositorNodeMixRGB", (-300, 0), blend_type="SCREEN")
mixh.inputs[2].default_value = (1.0, 0.96, 0.78, 1)
hmul = node(ct, "CompositorNodeMath", (-450, -200), operation="MULTIPLY")
hmul.inputs[1].default_value = 0.06
ct.links.new(rl.outputs["Mist"], hmul.inputs[0])
ct.links.new(hmul.outputs[0], mixh.inputs[0])
ct.links.new(rl.outputs["Image"], mixh.inputs[1])
glare = node(ct, "CompositorNodeGlare", (-100, 0))
glare.glare_type = "FOG_GLOW"
try:
    glare.inputs["Strength"].default_value = 0.22
    glare.inputs["Threshold"].default_value = 1.2
    glare.inputs["Size"].default_value = 0.6
except KeyError:
    glare.mix = -0.6
    glare.threshold = 0.9
    glare.size = 8
ct.links.new(mixh.outputs[0], glare.inputs["Image"])
comp = node(ct, "CompositorNodeComposite", (200, 0))
ct.links.new(glare.outputs["Image"], comp.inputs["Image"])

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ROOT, "creek.blend"))
bpy.ops.file.make_paths_relative()
bpy.ops.wm.save_mainfile()
print("saved", os.path.join(ROOT, "creek.blend"))
