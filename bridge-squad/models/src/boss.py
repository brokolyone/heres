"""Boss model for "Отряд на мосту": a huge armored brute with a minigun.

Run: python3 bridge-squad/models/src/boss.py
Outputs: models/boss.glb, models/previews/boss.png, models/previews/boss_side.png
Contract: objects body, leg_L, leg_R (origin at hip joint), feet on z=0, faces +Y.
"""
import math
import os

import bpy
import bmesh
from mathutils import Matrix, Vector, Euler

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS = os.path.dirname(HERE)
GLB = os.path.join(MODELS, "boss.glb")
PREV = os.path.join(MODELS, "previews")

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

# ---------------------------------------------------------------- materials
def mat(name, color, rough=0.5, metal=0.0, emit=None, strength=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    p = m.node_tree.nodes.get("Principled BSDF")
    p.inputs["Base Color"].default_value = (*color, 1.0)
    p.inputs["Roughness"].default_value = rough
    p.inputs["Metallic"].default_value = metal
    if emit:
        p.inputs["Emission Color"].default_value = (*emit, 1.0)
        p.inputs["Emission Strength"].default_value = strength
    m.diffuse_color = (*color, 1.0)
    return m

M = {
    "red": mat("boss_armor_red", (0.62, 0.035, 0.03), 0.38, 0.15),
    "red_dark": mat("boss_armor_red_dark", (0.28, 0.02, 0.025), 0.45, 0.1),
    "graphite": mat("boss_graphite", (0.055, 0.06, 0.075), 0.5, 0.3),
    "steel": mat("boss_gunmetal", (0.2, 0.22, 0.27), 0.32, 0.75),
    "suit": mat("boss_undersuit", (0.09, 0.07, 0.085), 0.75),
    "brass": mat("boss_brass", (0.85, 0.55, 0.16), 0.3, 0.85),
    "hazard": mat("boss_hazard_yellow", (0.95, 0.62, 0.04), 0.45),
    "visor": mat("boss_visor_glow", (1.0, 0.04, 0.02), 0.2, 0.0, (1.0, 0.02, 0.01), 3.0),
    "core": mat("boss_core_glow", (1.0, 0.16, 0.03), 0.2, 0.0, (1.0, 0.08, 0.01), 2.5),
}

# ---------------------------------------------------------------- helpers
PARTS = {"body": [], "leg_L": [], "leg_R": []}


def finish(obj, m, group, bevel=0.0, seg=1, smooth=False):
    obj.data.materials.append(m)
    if bevel > 0:
        b = obj.modifiers.new("bevel", "BEVEL")
        b.width = bevel
        b.segments = seg
        b.limit_method = "ANGLE"
        b.angle_limit = math.radians(40)
        b.harden_normals = False
    obj["smooth"] = smooth
    PARTS[group].append(obj)
    return obj


def bake(obj, scale=(1, 1, 1), rot=None, loc=(0, 0, 0), taper=None):
    """Bake scale/taper/rotation/location into mesh data (object stays identity)."""
    me = obj.data
    me.transform(Matrix.Diagonal((*scale, 1.0)))
    if taper:  # (top_sx, top_sy, bottom_sx, bottom_sy) relative factors, by z
        tx, ty, bx, by = taper
        zs = [v.co.z for v in me.vertices]
        z0, z1 = min(zs), max(zs)
        for v in me.vertices:
            t = (v.co.z - z0) / max(z1 - z0, 1e-6)
            v.co.x *= bx + (tx - bx) * t
            v.co.y *= by + (ty - by) * t
    if rot is not None:
        r = rot if not isinstance(rot, (tuple, list)) else Euler([math.radians(a) for a in rot]).to_matrix()
        me.transform(r.to_4x4() if hasattr(r, "to_4x4") else r)
    me.transform(Matrix.Translation(loc))
    obj.location = (0, 0, 0)
    obj.rotation_euler = (0, 0, 0)
    obj.scale = (1, 1, 1)


def box(group, loc, size, m, bevel=0.03, seg=1, rot=None, taper=None):
    bpy.ops.mesh.primitive_cube_add(size=1)
    o = bpy.context.active_object
    bake(o, size, rot, loc, taper)
    return finish(o, m, group, bevel, seg)


def cyl(group, loc, r, depth, m, verts=10, axis="Z", rot=None, bevel=0.0, seg=1, smooth=True, caps=True):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r, depth=depth,
                                        end_fill_type="NGON" if caps else "NOTHING")
    o = bpy.context.active_object
    base = {"Z": None, "X": Euler((0, math.radians(90), 0)).to_matrix(),
            "Y": Euler((math.radians(90), 0, 0)).to_matrix()}[axis]
    if base is not None:
        o.data.transform(base.to_4x4())
    if rot is not None:
        o.data.transform(Euler([math.radians(a) for a in rot]).to_matrix().to_4x4())
    o.data.transform(Matrix.Translation(loc))
    return finish(o, m, group, bevel, seg, smooth)


def ball(group, loc, r, m, scale=(1, 1, 1), seg=10, rings=6, rot=None):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=seg, ring_count=rings, radius=r)
    o = bpy.context.active_object
    bake(o, scale, rot, loc)
    return finish(o, m, group, smooth=True)


def rivet(group, loc, normal, m=None, r=0.04):
    bpy.ops.mesh.primitive_cone_add(vertices=6, radius1=r, radius2=0.0, depth=r * 0.9,
                                    end_fill_type="NOTHING")
    o = bpy.context.active_object
    q = Vector(normal).normalized().to_track_quat("Z", "Y")
    o.data.transform(q.to_matrix().to_4x4())
    o.data.transform(Matrix.Translation(Vector(loc) + Vector(normal).normalized() * r * 0.2))
    return finish(o, m or M["steel"], group, smooth=True)


def beam(group, p1, p2, w, d, m, bevel=0.04, seg=1, up=(0, 0, 1), taper=None):
    """Box from p1 to p2 (its local Z along the segment)."""
    p1, p2 = Vector(p1), Vector(p2)
    v = p2 - p1
    bpy.ops.mesh.primitive_cube_add(size=1)
    o = bpy.context.active_object
    o.data.transform(Matrix.Translation((0, 0, 0.5)))
    o.data.transform(Matrix.Diagonal((w, d, v.length, 1)))
    if taper:
        for vv in o.data.vertices:
            t = vv.co.z / v.length
            f = taper[0] + (taper[1] - taper[0]) * t
            vv.co.x *= f
            vv.co.y *= f
    q = v.to_track_quat("Z", "Y")
    o.data.transform(q.to_matrix().to_4x4())
    o.data.transform(Matrix.Translation(p1))
    return finish(o, m, group, bevel, seg)


# ================================================================ LEGS
HIP_Z = 1.22
HIP_X = 0.46
for side, g in ((-1, "leg_L"), (1, "leg_R")):
    x = side * HIP_X
    cyl(g, (x, 0, HIP_Z), 0.21, 0.36, M["graphite"], verts=10, axis="X")
    # thigh
    box(g, (x, 0.0, 0.96), (0.44, 0.48, 0.5), M["suit"], 0.06, taper=(1.0, 1.0, 0.85, 0.85))
    box(g, (x + side * 0.02, 0.2, 1.0), (0.42, 0.14, 0.42), M["red"], 0.05, 1,
        rot=(-8, 0, 0), taper=(1.0, 1.0, 0.8, 1.0))
    box(g, (x + side * 0.2, 0.0, 1.0), (0.1, 0.4, 0.38), M["red_dark"], 0.0)
    # knee
    box(g, (x, 0.29, 0.69), (0.36, 0.2, 0.3), M["red"], 0.07, 1, rot=(10, 0, 0))
    rivet(g, (x, 0.4, 0.71), (0, 1, 0.15), r=0.045)
    # shin / boot
    box(g, (x, 0.02, 0.44), (0.54, 0.6, 0.5), M["graphite"], 0.06, taper=(0.92, 0.92, 1.05, 1.05))
    box(g, (x, 0.29, 0.44), (0.42, 0.1, 0.36), M["red_dark"], 0.0, rot=(-6, 0, 0))
    # foot
    box(g, (x, 0.1, 0.12), (0.66, 0.96, 0.24), M["graphite"], 0.05)
    box(g, (x, 0.54, 0.11), (0.6, 0.22, 0.2), M["red"], 0.06, 1)
    box(g, (x, -0.38, 0.06), (0.6, 0.16, 0.12), M["steel"], 0.0)

# ================================================================ TORSO
B = "body"
box(B, (0, 0, 1.3), (1.04, 0.7, 0.36), M["suit"], 0.06)
box(B, (0, 0.0, 1.45), (1.18, 0.8, 0.16), M["graphite"], 0.04)                 # belt
box(B, (0, 0.41, 1.45), (0.3, 0.06, 0.2), M["brass"], 0.0)                    # buckle
for sx in (-1, 1):                                                             # tassets
    box(B, (sx * 0.42, 0.3, 1.22), (0.36, 0.1, 0.34), M["red_dark"], 0.04, rot=(-12, 0, sx * -10))
box(B, (0, 0.0, 1.72), (1.1, 0.78, 0.44), M["suit"], 0.06, taper=(1.15, 1.1, 1.0, 1.0))  # abdomen
for i, z in enumerate((1.62, 1.8)):                                            # ab plates
    box(B, (0, 0.38, z), (0.62 + i * 0.1, 0.1, 0.15), M["graphite"], 0.0)
# chest: big tapered barrel
box(B, (0, 0.02, 2.38), (1.75, 1.12, 0.96), M["red"], 0.12, 2, taper=(1.0, 1.0, 0.74, 0.86))
box(B, (0, 0.55, 2.42), (0.95, 0.12, 0.62), M["red_dark"], 0.06, 1, taper=(1.0, 1.0, 0.7, 1.0))
# glowing reactor core
cyl(B, (0, 0.62, 2.42), 0.2, 0.06, M["graphite"], verts=8, axis="Y", smooth=False)
cyl(B, (0, 0.66, 2.42), 0.13, 0.04, M["core"], verts=8, axis="Y", smooth=False)
for sx in (-1, 1):
    for z in (2.62, 2.2):
        rivet(B, (sx * 0.38, 0.62, z), (0, 1, 0))
    rivet(B, (sx * 0.7, 0.55, 2.62), (sx * 0.3, 1, 0.2))
# gorget / collar
box(B, (0, -0.02, 2.9), (1.0, 0.82, 0.24), M["graphite"], 0.06, 1, taper=(0.85, 0.85, 1.0, 1.0))
# back generator
box(B, (0, -0.68, 2.45), (1.1, 0.5, 0.8), M["graphite"], 0.07, 1)
box(B, (0, -0.94, 2.45), (0.8, 0.06, 0.5), M["red_dark"], 0.0)
for sx in (-1, 1):
    cyl(B, (sx * 0.36, -0.72, 3.0), 0.09, 0.4, M["steel"], verts=8)
    cyl(B, (sx * 0.36, -0.72, 3.21), 0.11, 0.06, M["graphite"], verts=8)

# ================================================================ HEAD
box(B, (0, 0.08, 3.17), (0.56, 0.6, 0.54), M["graphite"], 0.1, 1, taper=(0.9, 0.95, 1.0, 1.0))
box(B, (0, 0.04, 3.46), (0.12, 0.6, 0.2), M["red"], 0.04, 1)                   # crest
for sx in (-1, 1):
    cyl(B, (sx * 0.29, 0.04, 3.18), 0.11, 0.08, M["red"], verts=8, axis="X")
    # angry V visor slits (inner end lower)
    box(B, (sx * 0.125, 0.385, 3.22), (0.24, 0.06, 0.085), M["visor"], 0.0,
        rot=(0, sx * -20, 0))
box(B, (0, 0.36, 3.3), (0.5, 0.06, 0.07), M["red"], 0.0)                     # brow
box(B, (0, 0.34, 3.0), (0.4, 0.12, 0.16), M["steel"], 0.03, rot=(15, 0, 0))   # jaw guard
for sx in (-0.1, 0, 0.1):
    box(B, (sx, 0.4, 3.0), (0.04, 0.03, 0.1), M["graphite"], 0.0, rot=(15, 0, 0))

# ================================================================ SHOULDERS & ARMS
for sx in (-1, 1):
    ball(B, (sx * 0.84, 0.0, 2.6), 0.26, M["suit"], seg=8, rings=5)
    box(B, (sx * 0.84, -0.02, 2.86), (0.62, 0.92, 0.42), M["red"], 0.14, 2,
        rot=(0, sx * 16, 0), taper=(0.8, 0.85, 1.0, 1.0))
    box(B, (sx * 0.86, -0.02, 2.66), (0.66, 0.96, 0.1), M["graphite"], 0.03,
        rot=(0, sx * 16, 0))
    for y in (-0.3, 0.0, 0.3):
        rivet(B, (sx * 0.98, y, 2.92), (sx * 0.55, 0, 1))
    # hazard stripe on pad front
    box(B, (sx * 0.82, 0.44, 2.86), (0.3, 0.04, 0.12), M["hazard"], 0.0, rot=(0, sx * 16, 0))

# upper arms (shoulder -> elbow)
SH = {-1: Vector((-0.86, 0.0, 2.55)), 1: Vector((0.86, 0.0, 2.55))}
EL = {-1: Vector((-0.88, 0.18, 1.95)), 1: Vector((0.9, 0.12, 1.95))}
WR = {-1: Vector((-0.2, 1.08, 1.92)), 1: Vector((0.48, 0.58, 1.62))}
for sx in (-1, 1):
    beam(B, SH[sx], EL[sx], 0.34, 0.34, M["suit"], 0.06)
    beam(B, SH[sx] + Vector((sx * 0.05, 0, -0.1)), EL[sx] + Vector((sx * 0.05, 0, 0.12)),
         0.3, 0.3, M["red_dark"], 0.06)
    ball(B, EL[sx], 0.2, M["steel"], seg=8, rings=4)
    # gauntlet (big, tapered towards wrist)
    beam(B, EL[sx], WR[sx], 0.46, 0.42, M["red"], 0.08, 1, taper=(1.0, 0.82))
    box(B, WR[sx] + (WR[sx] - EL[sx]).normalized() * 0.1, (0.3, 0.3, 0.28), M["graphite"], 0.07)

# ================================================================ MINIGUN
GX, GZ = 0.18, 1.74
box(B, (GX, 0.72, GZ), (0.54, 0.7, 0.54), M["steel"], 0.06, 1)               # housing
box(B, (GX, 0.98, GZ), (0.56, 0.12, 0.56), M["hazard"], 0.04)                 # hazard band
box(B, (GX, 0.72, GZ + 0.31), (0.2, 0.5, 0.1), M["graphite"], 0.0)           # top rail
cyl(B, (GX, 0.33, GZ), 0.19, 0.14, M["graphite"], verts=10, axis="Y")          # motor
cyl(B, (GX, 0.25, GZ), 0.1, 0.06, M["red"], verts=8, axis="Y")
for y, r in ((1.12, 0.25), (1.72, 0.22), (2.3, 0.24)):                        # clamps
    cyl(B, (GX, y, GZ), r, 0.09 if y < 2 else 0.12, M["graphite"], verts=10, axis="Y")
cyl(B, (GX, 1.7, GZ), 0.07, 1.2, M["graphite"], verts=6, axis="Y")             # spindle
for i in range(6):
    a = math.radians(30 + i * 60)
    cyl(B, (GX + 0.15 * math.cos(a), 1.74, GZ + 0.15 * math.sin(a)), 0.06, 1.24,
        M["steel"], verts=6, axis="Y")
# front handle for left hand
beam(B, (GX - 0.05, 1.08, GZ + 0.15), (-0.2, 1.1, 1.92), 0.1, 0.1, M["graphite"], 0.02)
# rear grip for right hand
beam(B, (GX + 0.2, 0.62, GZ - 0.05), (0.48, 0.62, 1.58), 0.1, 0.1, M["graphite"], 0.02)
# ammo feed chute under gun
box(B, (GX, 0.72, GZ - 0.3), (0.22, 0.26, 0.18), M["graphite"], 0.0)

# ammo drum on the right hip + belt
cyl(B, (0.8, -0.18, 1.5), 0.3, 0.36, M["graphite"], verts=12, axis="X", bevel=0.04)
cyl(B, (0.8, -0.18, 1.5), 0.2, 0.38, M["red"], verts=12, axis="X")
P0, P1, P2 = Vector((GX, 0.72, GZ - 0.4)), Vector((0.55, 0.85, 0.98)), Vector((0.8, 0.12, 1.42))
N = 15
pts = [(1 - t) ** 2 * P0 + 2 * (1 - t) * t * P1 + t * t * P2 for t in (i / (N - 1) for i in range(N))]
for i in range(N - 1):
    a, b = pts[i], pts[i + 1]
    mid = (a + b) / 2
    tang = (b - a).normalized()
    side = tang.cross(Vector((0, 0, 1)))
    if side.length < 1e-3:
        side = Vector((1, 0, 0))
    side.normalize()
    # cartridge lies across the belt
    beam(B, mid - side * 0.09, mid + side * 0.09, 0.055, 0.055,
         M["brass"] if i % 2 == 0 else M["red_dark"], 0.0)

# ================================================================ BUILD OBJECTS
depsgraph = bpy.context.evaluated_depsgraph_get()


def merge(name, objs, origin=(0, 0, 0)):
    bm = bmesh.new()
    me = bpy.data.meshes.new(name)
    mats = []
    smooth_flags = []
    dg = bpy.context.evaluated_depsgraph_get()
    for o in objs:
        ev = o.evaluated_get(dg)
        tmp = bpy.data.meshes.new_from_object(ev)
        m = o.data.materials[0]
        if m not in mats:
            mats.append(m)
        idx = mats.index(m)
        for p in tmp.polygons:
            p.material_index = idx
            p.use_smooth = bool(o["smooth"])
        bm.from_mesh(tmp)
        bpy.data.meshes.remove(tmp)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bm.to_mesh(me)
    bm.free()
    for m in mats:
        me.materials.append(m)
    for o in objs:
        bpy.data.objects.remove(o, do_unlink=True)
    me.transform(Matrix.Translation(-Vector(origin)))
    ob = bpy.data.objects.new(name, me)
    ob.location = origin
    scene.collection.objects.link(ob)
    return ob


body = merge("body", PARTS["body"])
leg_L = merge("leg_L", PARTS["leg_L"], (-HIP_X, 0, HIP_Z))
leg_R = merge("leg_R", PARTS["leg_R"], (HIP_X, 0, HIP_Z))
CHARS = [body, leg_L, leg_R]

# ================================================================ EXPORT
bpy.ops.object.select_all(action="DESELECT")
for o in CHARS:
    o.select_set(True)
bpy.context.view_layer.objects.active = body
bpy.ops.export_scene.gltf(filepath=GLB, export_format="GLB", export_yup=True,
                          export_apply=True, use_selection=True)

tris = 0
mn = Vector((1e9,) * 3)
mx = Vector((-1e9,) * 3)
for o in CHARS:
    me = o.data
    me.calc_loop_triangles()
    t = len(me.loop_triangles)
    tris += t
    for v in me.vertices:
        w = o.matrix_world @ v.co
        mn = Vector(map(min, mn, w))
        mx = Vector(map(max, mx, w))
    print(f"{o.name}: {t} tris, origin {tuple(round(c, 3) for c in o.location)}")
print(f"TOTAL TRIS: {tris}")
print(f"BBOX min {tuple(round(c, 3) for c in mn)} max {tuple(round(c, 3) for c in mx)} "
      f"size {tuple(round(c, 3) for c in (mx - mn))}")

# ================================================================ PREVIEW
if os.environ.get("NO_PREVIEW"):
    raise SystemExit
os.makedirs(PREV, exist_ok=True)
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = int(os.environ.get("SAMPLES", "32"))
scene.cycles.use_denoising = False
scene.render.resolution_x = scene.render.resolution_y = 768
scene.view_settings.view_transform = "Standard"
scene.view_settings.look = "None"

world = bpy.data.worlds.new("world")
scene.world = world
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.42, 0.55, 0.7, 1)
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.7

bpy.ops.mesh.primitive_plane_add(size=30)
ground = bpy.context.active_object
ground.data.materials.append(mat("preview_ground", (0.5, 0.42, 0.33), 0.9))

sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
sun.data.energy = 3.5
sun.data.angle = math.radians(8)
sun.rotation_euler = Euler((math.radians(40), math.radians(10), math.radians(150)))
scene.collection.objects.link(sun)

cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
scene.collection.objects.link(cam)
scene.camera = cam


def shoot(path, pos, target, lens=50):
    cam.location = pos
    d = Vector(target) - Vector(pos)
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = lens
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


shoot(os.path.join(PREV, "boss.png"), (5.2, 7.6, 5.9), (0, 0.4, 1.7), 50)
shoot(os.path.join(PREV, "boss_side.png"), (9.0, 0.6, 2.2), (0, 0.6, 1.8), 50)
print("previews written")
