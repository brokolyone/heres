"""soldier_blue — chibi player soldier for «Отряд на мосту».

Run: python3 bridge-squad/models/src/soldier_blue.py
Builds the model from scratch, exports GLB, renders previews (3/4 back-top + front).
Objects: body, leg_L, leg_R (leg origins at hip joints). Forward = +Y, up = +Z.
"""
import math
import os
import sys

import bpy  # noqa: E402  (bpy must be imported before bmesh)
import bmesh
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS = os.path.dirname(HERE)
OUT_GLB = os.path.join(MODELS, "soldier_blue.glb")
PREV_DIR = os.path.join(MODELS, "previews")
PREV_BACK = os.path.join(PREV_DIR, "soldier_blue.png")
PREV_FRONT = os.path.join(PREV_DIR, "soldier_blue_front.png")
TRI_BUDGET = 900

bpy.ops.wm.read_factory_settings(use_empty=True)


# ---------------------------------------------------------------- materials
def srgb_to_lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(srgb_to_lin(int(h[i:i + 2], 16) / 255.0) for i in (0, 2, 4))


def make_mat(name, hexcol, rough, metal=0.0, coat=0.0):
    m = bpy.data.materials.new(name)
    try:
        m.use_nodes = True
    except Exception:
        pass
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    if bsdf is None:
        bsdf = m.node_tree.nodes.new("ShaderNodeBsdfPrincipled")
        out = m.node_tree.nodes.get("Material Output") or m.node_tree.nodes.new("ShaderNodeOutputMaterial")
        m.node_tree.links.new(bsdf.outputs[0], out.inputs[0])
    rgb = hex_rgb(hexcol)
    bsdf.inputs["Base Color"].default_value = (*rgb, 1.0)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    if coat and "Coat Weight" in bsdf.inputs:
        bsdf.inputs["Coat Weight"].default_value = coat
    m.diffuse_color = (*rgb, 1.0)
    m.roughness = rough
    return m


MATS = {
    "helmet": make_mat("Helmet_Blue", "#2F7BFF", 0.2),
    "helmet_rim": make_mat("Helmet_Rim_Blue", "#1F5FD6", 0.3),
    "skin": make_mat("Skin", "#F5C49C", 0.6),
    "eye": make_mat("Eye_Dark", "#2A2238", 0.3),
    "eye_hi": make_mat("Eye_Shine", "#FFF6E8", 0.3),
    "blush": make_mat("Cheek_Blush", "#F29A8A", 0.7),
    "strap": make_mat("Strap_Brown", "#4A3426", 0.7),
    "vest": make_mat("Vest_Sand", "#D9B97C", 0.8),
    "pouch": make_mat("Pouch_Tan", "#B08A55", 0.8),
    "pants": make_mat("Pants_Navy", "#25356A", 0.75),
    "belt": make_mat("Belt_Brown", "#4E3524", 0.6),
    "buckle": make_mat("Buckle_Brass", "#E3B04B", 0.35, metal=0.6),
    "boots": make_mat("Boots_Brown", "#6E4528", 0.65),
    "pack": make_mat("Backpack_Khaki", "#9E7E4C", 0.8),
    "gun": make_mat("Gun_Graphite", "#2C3038", 0.4, metal=0.3),
    "gun_dark": make_mat("Gun_Graphite_Dark", "#1E2128", 0.5),
    "gun_accent": make_mat("Gun_Accent_Blue", "#4DB2FF", 0.3),
}


# ---------------------------------------------------------------- builder
class Builder:
    """Accumulates parts into one bmesh with material slots."""

    def __init__(self):
        self.bm = bmesh.new()
        self.mats = []

    def _slot(self, key):
        m = MATS[key]
        if m not in self.mats:
            self.mats.append(m)
        return self.mats.index(m)

    def _tag(self, before, key, smooth):
        idx = self._slot(key)
        new = [f for f in self.bm.faces if f not in before]
        for f in new:
            f.material_index = idx
            f.smooth = smooth
        return new

    def box(self, key, center, size, bevel=0.0, rot=None, smooth=False):
        before = set(self.bm.faces)
        S = Matrix.Diagonal((*size, 1.0))
        res = bmesh.ops.create_cube(self.bm, size=1.0, matrix=S)
        verts = res["verts"]
        if bevel > 0:
            edges = list({e for v in verts for e in v.link_edges})
            bmesh.ops.bevel(self.bm, geom=verts + edges, offset=bevel, segments=1,
                            affect="EDGES", profile=0.5, clamp_overlap=True)
            verts = list({v for f in self.bm.faces if f not in before for v in f.verts})
        M = Matrix.Translation(center) @ (rot.to_4x4() if rot else Matrix())
        bmesh.ops.transform(self.bm, matrix=M, verts=verts)
        return self._tag(before, key, smooth)

    def sphere(self, key, center, radius, scale=(1, 1, 1), u=8, v=4, smooth=True,
               cut_below=None, rot=None):
        before = set(self.bm.faces)
        res = bmesh.ops.create_uvsphere(self.bm, u_segments=u, v_segments=v, radius=radius)
        verts = res["verts"]
        if cut_below is not None:
            kill = [vt for vt in verts if vt.co.z < cut_below * radius - 1e-5]
            bmesh.ops.delete(self.bm, geom=kill, context="VERTS")
            verts = [vt for vt in verts if vt.is_valid]
        M = Matrix.Translation(center) @ (rot.to_4x4() if rot else Matrix()) @ Matrix.Diagonal((*scale, 1.0))
        bmesh.ops.transform(self.bm, matrix=M, verts=verts)
        return self._tag(before, key, smooth)

    def tube(self, key, p1, p2, r1, r2, sides=6, caps=False, smooth=True, scale_xy=(1, 1), spin=0.0):
        """Cylinder/cone from p1 (radius r1) to p2 (radius r2)."""
        before = set(self.bm.faces)
        p1, p2 = Vector(p1), Vector(p2)
        d = p2 - p1
        res = bmesh.ops.create_cone(self.bm, cap_ends=caps, cap_tris=False, segments=sides,
                                    radius1=r1, radius2=r2, depth=d.length)
        verts = res["verts"]
        q = Vector((0, 0, 1)).rotation_difference(d.normalized())
        M = (Matrix.Translation((p1 + p2) / 2) @ q.to_matrix().to_4x4()
             @ Matrix.Rotation(spin, 4, "Z") @ Matrix.Diagonal((*scale_xy, 1, 1)))
        bmesh.ops.transform(self.bm, matrix=M, verts=verts)
        return self._tag(before, key, smooth)

    def disc(self, key, center, radius, normal, scale=(1, 1), sides=6):
        before = set(self.bm.faces)
        res = bmesh.ops.create_circle(self.bm, cap_ends=True, segments=sides, radius=radius)
        q = Vector((0, 0, 1)).rotation_difference(Vector(normal).normalized())
        M = Matrix.Translation(center) @ q.to_matrix().to_4x4() @ Matrix.Diagonal((scale[0], scale[1], 1, 1))
        bmesh.ops.transform(self.bm, matrix=M, verts=res["verts"])
        return self._tag(before, key, False)

    def to_object(self, name, location=(0, 0, 0)):
        bmesh.ops.triangulate(self.bm, faces=self.bm.faces[:])
        if location != (0, 0, 0):
            bmesh.ops.translate(self.bm, vec=-Vector(location), verts=self.bm.verts[:])
        me = bpy.data.meshes.new(name)
        self.bm.to_mesh(me)
        self.bm.free()
        for m in self.mats:
            me.materials.append(m)
        ob = bpy.data.objects.new(name, me)
        ob.location = location
        bpy.context.scene.collection.objects.link(ob)
        return ob


# ---------------------------------------------------------------- dimensions
HEAD_C = Vector((0, 0.01, 0.835))
HEAD_R = 0.215
HIP_Z = 0.285
HIP_X = 0.095

# ---------------------------------------------------------------- body
b = Builder()

# Head (skin), slightly wide chibi shape
b.sphere("skin", HEAD_C, HEAD_R, scale=(1.05, 0.97, 0.95), u=10, v=6)

# Helmet: glossy dome + darker rim lip, slightly longer front-back
HEL_C = HEAD_C + Vector((0, -0.01, 0.045))
HEL_R = 0.245
b.sphere("helmet", HEL_C, HEL_R, scale=(1.06, 1.1, 0.88), u=10, v=8, cut_below=0.0)
# rim: short flared band at the dome's equator
b.tube("helmet_rim", HEL_C + Vector((0, 0, -0.04)), HEL_C,
       HEL_R * 1.1, HEL_R, sides=10, scale_xy=(1.06, 1.1))

# Face: eyes (dark ovals) + shine + blush
eye_z = HEAD_C.z - 0.045
for sx in (-1, 1):
    ex = sx * 0.075
    # point on the scaled head surface
    ny = math.sqrt(max(0.0, 1 - (ex / (HEAD_R * 1.05)) ** 2 - ((eye_z - HEAD_C.z) / (HEAD_R * 0.95)) ** 2))
    ey = HEAD_C.y + HEAD_R * 0.97 * ny + 0.004
    nrm = Vector((ex / 1.05 ** 2, (ey - HEAD_C.y) / 0.97 ** 2, (eye_z - HEAD_C.z) / 0.95 ** 2)).normalized()
    b.disc("eye", (ex, ey, eye_z), 0.028, nrm, scale=(0.8, 1.25), sides=8)
    b.disc("eye_hi", (ex + sx * 0.008 - 0.004 * sx, ey + 0.004, eye_z + 0.014), 0.009, nrm, sides=5)
    # blush below-outside the eye
    bx, bz = sx * 0.125, eye_z - 0.05
    ny = math.sqrt(max(0.0, 1 - (bx / (HEAD_R * 1.05)) ** 2 - ((bz - HEAD_C.z) / (HEAD_R * 0.95)) ** 2))
    by = HEAD_C.y + HEAD_R * 0.97 * ny + 0.003
    nrm2 = Vector((bx / 1.05 ** 2, (by - HEAD_C.y) / 0.97 ** 2, (bz - HEAD_C.z) / 0.95 ** 2)).normalized()
    b.disc("blush", (bx, by, bz), 0.024, nrm2, scale=(1.3, 0.7), sides=6)

# Chin strap: thin open loop from helmet rim around the chin
strap_c = HEAD_C + Vector((0, 0.0, -0.06))
_sf = b.tube("strap", strap_c + Vector((0, 0, -0.012)), strap_c + Vector((0, 0, 0.012)),
             HEAD_R * 1.0, HEAD_R * 1.0, sides=8, smooth=False, scale_xy=(1.07, 0.92))
# tilt the loop about X so it passes under the chin in front and up to the rim behind
_sv = list({v for f in _sf for v in f.verts})
bmesh.ops.rotate(b.bm, verts=_sv, cent=strap_c, matrix=Matrix.Rotation(math.radians(-55), 3, "X"))

# Torso = sand vest/jacket, chunky chamfered block
TORSO_C = Vector((0, 0, 0.495))
b.box("vest", TORSO_C, (0.38, 0.27, 0.33), bevel=0.07)
# Pouches on the vest front
for px in (-0.1, 0.1):
    b.box("pouch", (px, 0.14, 0.43), (0.1, 0.05, 0.1))
# Belt + buckle
b.box("belt", (0, 0, 0.345), (0.40, 0.29, 0.06), bevel=0.03)
b.box("buckle", (0, 0.148, 0.345), (0.07, 0.02, 0.05))
# Pelvis (pants) under the belt
b.box("pants", (0, 0, 0.285), (0.33, 0.23, 0.1))

# Backpack
b.box("pack", (0, -0.2, 0.5), (0.3, 0.13, 0.27), bevel=0.04)
b.box("pouch", (0, -0.27, 0.46), (0.18, 0.04, 0.12))          # front pocket
b.box("helmet", (0, -0.195, 0.64), (0.31, 0.15, 0.035))      # blue lid = team marker from behind

# Arms (sleeves sand), hands skin
SH_R = Vector((0.195, 0.0, 0.58))
SH_L = Vector((-0.195, 0.0, 0.58))
EL_R = Vector((0.23, 0.10, 0.45))
EL_L = Vector((-0.22, 0.17, 0.47))
HAND_R = Vector((0.07, 0.23, 0.43))
HAND_L = Vector((-0.02, 0.40, 0.475))
for sh, el, hd in ((SH_R, EL_R, HAND_R), (SH_L, EL_L, HAND_L)):
    b.sphere("vest", sh, 0.075, u=6, v=3)
    b.tube("vest", sh, el, 0.07, 0.062, sides=6)
    b.sphere("vest", el, 0.062, u=6, v=3)
    b.tube("vest", el, hd, 0.062, 0.05, sides=6)
    b.sphere("skin", hd, 0.052, u=6, v=3)

# Rifle along +Y, graphite with blue accent
GX, GZ = 0.035, 0.47
b.box("gun", (GX, 0.27, GZ), (0.07, 0.24, 0.1))        # receiver
b.box("gun_accent", (GX, 0.27, GZ + 0.005), (0.076, 0.13, 0.024))     # accent stripe
b.box("gun_dark", (GX, 0.43, GZ - 0.005), (0.078, 0.12, 0.078))         # handguard
b.tube("gun", (GX, 0.47, GZ + 0.01), (GX, 0.66, GZ + 0.01), 0.021, 0.021, sides=6, smooth=True)  # barrel
b.tube("gun_accent", (GX, 0.63, GZ + 0.01), (GX, 0.68, GZ + 0.01), 0.03, 0.03, sides=6, caps=True)  # muzzle
b.box("gun_dark", (GX, 0.115, GZ - 0.015), (0.05, 0.11, 0.075))       # stock
b.box("gun_dark", (GX, 0.31, GZ - 0.085),
      (0.04, 0.05, 0.1), rot=Matrix.Rotation(math.radians(-15), 3, "X"))  # magazine
b.box("gun_dark", (GX, 0.22, GZ - 0.07),
      (0.04, 0.04, 0.07), rot=Matrix.Rotation(math.radians(15), 3, "X"))  # grip
b.box("gun", (GX, 0.25, GZ + 0.06), (0.03, 0.07, 0.035))               # sight

body = b.to_object("body")

# ---------------------------------------------------------------- legs
legs = []
for name, sx in (("leg_L", -1), ("leg_R", 1)):
    lb = Builder()
    hip = Vector((sx * HIP_X, 0.0, HIP_Z))
    lb.tube("pants", hip + Vector((0, 0, 0.02)), Vector((hip.x, 0.0, 0.085)), 0.085, 0.072, sides=6, spin=math.pi / 6)
    lb.box("boots", (hip.x + sx * 0.005, 0.025, 0.055), (0.135, 0.2, 0.11), bevel=0.035)
    legs.append(lb.to_object(name, location=tuple(hip)))

# ---------------------------------------------------------------- report
def tri_count(ob):
    return sum(len(p.vertices) - 2 for p in ob.data.polygons)


bpy.context.view_layer.update()
export_objs = [body] + legs
total = 0
for ob in export_objs:
    t = tri_count(ob)
    total += t
    print(f"{ob.name}: {t} tris, origin {tuple(round(c, 4) for c in ob.location)}")
mins = Vector((1e9,) * 3)
maxs = Vector((-1e9,) * 3)
for ob in export_objs:
    for v in ob.data.vertices:
        w = ob.matrix_world @ v.co
        mins = Vector(map(min, mins, w))
        maxs = Vector(map(max, maxs, w))
print(f"TOTAL tris: {total} (budget {TRI_BUDGET})")
print(f"BBOX min {tuple(round(c, 3) for c in mins)} max {tuple(round(c, 3) for c in maxs)} "
      f"size {tuple(round(c, 3) for c in (maxs - mins))}")
if total > TRI_BUDGET:
    print("WARNING: over triangle budget!", file=sys.stderr)

# ---------------------------------------------------------------- export
bpy.ops.object.select_all(action="DESELECT")
for ob in export_objs:
    ob.select_set(True)
bpy.context.view_layer.objects.active = body
bpy.ops.export_scene.gltf(filepath=OUT_GLB, export_format="GLB", export_yup=True,
                          export_apply=True, use_selection=True)
print("exported", OUT_GLB)

# ---------------------------------------------------------------- preview
if "--no-render" in sys.argv:
    sys.exit(0)

scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = 32
scene.cycles.use_denoising = False
scene.render.resolution_x = 768
scene.render.resolution_y = 768
scene.render.film_transparent = False
try:
    scene.view_settings.view_transform = "Standard"
except Exception:
    pass

world = bpy.data.worlds.new("PreviewWorld")
scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes.get("Background")
bg.inputs[0].default_value = (*hex_rgb("#BFD3E6"), 1.0)
bg.inputs[1].default_value = 0.9

ground_mat = make_mat("Preview_Ground", "#8E9AA8", 0.9)
bpy.ops.mesh.primitive_plane_add(size=6, location=(0, 0, 0))
bpy.context.object.data.materials.append(ground_mat)

sun_data = bpy.data.lights.new("Sun", "SUN")
sun_data.energy = 3.2
sun_data.angle = math.radians(8)
sun = bpy.data.objects.new("Sun", sun_data)
sun.rotation_euler = (math.radians(40), math.radians(-25), math.radians(-30))
scene.collection.objects.link(sun)

cam_data = bpy.data.cameras.new("Cam")
cam_data.lens = 60
cam = bpy.data.objects.new("Cam", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam


def shoot(pos, path, target=(0, 0.08, 0.52)):
    cam.location = pos
    d = Vector(target) - Vector(pos)
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print("rendered", path)


os.makedirs(PREV_DIR, exist_ok=True)
shoot((1.45, -2.2, 2.35), PREV_BACK)
shoot((1.25, 2.45, 1.25), PREV_FRONT)
