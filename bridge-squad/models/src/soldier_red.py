"""soldier_red -- enemy grunt for "Bridge Squad".

Run:  python3 bridge-squad/models/src/soldier_red.py
Builds the model from scratch, exports GLB and renders two previews
(front-top and side). Objects: body, leg_L, leg_R (see CONTRACT.md).
"""
import math
import os
import sys

import bpy  # noqa: E402  (must come before bmesh/mathutils)
import bmesh
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT_GLB = os.path.join(ROOT, "soldier_red.glb")
OUT_PREV = os.path.join(ROOT, "previews", "soldier_red.png")
OUT_PREV_SIDE = os.path.join(ROOT, "previews", "soldier_red_side.png")
TRI_BUDGET = 900
DEBUG = "--debug" in sys.argv

bpy.ops.wm.read_factory_settings(use_empty=True)

# ---------------------------------------------------------------- materials
PALETTE = {
    "red_helmet":   ((0.78, 0.06, 0.05), 0.35),
    "red_crest":    ((0.20, 0.025, 0.03), 0.5),
    "jacket_brick": ((0.20, 0.035, 0.03), 0.75),
    "jacket_dark":  ((0.09, 0.018, 0.02), 0.75),
    "pants_graphite": ((0.075, 0.075, 0.095), 0.75),
    "boots_black":  ((0.035, 0.026, 0.024), 0.55),
    "belt_leather": ((0.06, 0.035, 0.022), 0.6),
    "buckle_brass": ((0.85, 0.55, 0.12), 0.25),
    "skin":         ((0.80, 0.44, 0.30), 0.6),
    "mask_black":   ((0.035, 0.028, 0.032), 0.6),
    "mask_red":     ((0.65, 0.05, 0.05), 0.5),
    "eye_white":    ((0.92, 0.86, 0.72), 0.3),
    "brow_dark":    ((0.03, 0.015, 0.012), 0.6),
    "gun_dark":     ((0.05, 0.05, 0.065), 0.45),
    "gun_metal":    ((0.22, 0.20, 0.20), 0.3),
}
MATS = {}
for name, (col, rough) in PALETTE.items():
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*col, 1.0)
    bsdf.inputs["Roughness"].default_value = rough
    m.diffuse_color = (*col, 1.0)
    MATS[name] = m


# ---------------------------------------------------------------- builder
class Builder:
    """Accumulates primitive parts in one bmesh with per-face materials."""

    def __init__(self):
        self.bm = bmesh.new()
        self.mat_names = []

    def _mat(self, name):
        if name not in self.mat_names:
            self.mat_names.append(name)
        return self.mat_names.index(name)

    def _finish(self, before, mat, matrix, smooth):
        new = [f for f in self.bm.faces if f not in before]
        verts = {v for f in new for v in f.verts}
        for v in verts:
            v.co = matrix @ v.co
        idx = self._mat(mat)
        if DEBUG:
            print(f"  part {mat:15s} {sum(len(f.verts) - 2 for f in new):4d} tris")
        for f in new:
            f.material_index = idx
            f.smooth = smooth
        return new

    def box(self, mat, size, loc, rot=(0, 0, 0), bevel=0.0, taper=None, smooth=False):
        """size=(sx,sy,sz); taper=(top_scale_x, top_scale_y) narrows the +Z face."""
        before = set(self.bm.faces)
        res = bmesh.ops.create_cube(self.bm, size=1.0)
        vs = res["verts"]
        for v in vs:
            if taper and v.co.z > 0:
                v.co.x *= taper[0]
                v.co.y *= taper[1]
            v.co = Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2]))
        if bevel > 0:
            edges = list({e for v in vs for e in v.link_edges})
            bmesh.ops.bevel(self.bm, geom=edges + vs, offset=bevel, segments=1,
                            affect='EDGES', profile=0.5, clamp_overlap=True)
        m = Matrix.Translation(loc) @ _euler(rot)
        return self._finish(before, mat, m, smooth)

    def sphere(self, mat, radius, loc, scale=(1, 1, 1), seg=8, rings=6,
               rot=(0, 0, 0), cut_below=None, smooth=True):
        before = set(self.bm.faces)
        res = bmesh.ops.create_uvsphere(self.bm, u_segments=seg, v_segments=rings,
                                        radius=radius)
        vs = res["verts"]
        if cut_below is not None:
            kill = [v for v in vs if v.co.z < cut_below - 1e-6]
            bmesh.ops.delete(self.bm, geom=kill, context='VERTS')
            vs = [v for v in vs if v.is_valid]
            border = [e for e in {e for v in vs for e in v.link_edges} if e.is_boundary]
            if border:
                bmesh.ops.holes_fill(self.bm, edges=border, sides=0)
        m = Matrix.Translation(loc) @ _euler(rot) @ Matrix.Diagonal((*scale, 1))
        return self._finish(before, mat, m, smooth)

    def cyl(self, mat, r1, r2, depth, loc, seg=8, rot=(0, 0, 0), scale=(1, 1, 1),
            smooth=True, caps=True):
        before = set(self.bm.faces)
        bmesh.ops.create_cone(self.bm, cap_ends=caps, cap_tris=False, segments=seg,
                              radius1=r1, radius2=r2, depth=depth)
        m = Matrix.Translation(loc) @ _euler(rot) @ Matrix.Diagonal((*scale, 1))
        return self._finish(before, mat, m, smooth)

    def limb(self, mat, p0, p1, r0, r1, seg=6, smooth=True):
        """Cylinder from p0 to p1 (radius r0 at p0, r1 at p1)."""
        p0, p1 = Vector(p0), Vector(p1)
        d = p1 - p0
        before = set(self.bm.faces)
        bmesh.ops.create_cone(self.bm, cap_ends=True, cap_tris=False, segments=seg,
                              radius1=r0, radius2=r1, depth=d.length)
        rot = Vector((0, 0, 1)).rotation_difference(d.normalized()).to_matrix().to_4x4()
        m = Matrix.Translation((p0 + p1) / 2) @ rot
        return self._finish(before, mat, m, smooth)

    def to_object(self, name, origin=(0, 0, 0)):
        bmesh.ops.translate(self.bm, verts=self.bm.verts, vec=-Vector(origin))
        bmesh.ops.remove_doubles(self.bm, verts=self.bm.verts, dist=1e-5)
        me = bpy.data.meshes.new(name)
        self.bm.to_mesh(me)
        self.bm.free()
        for n in self.mat_names:
            me.materials.append(MATS[n])
        try:
            me.set_sharp_from_angle(angle=math.radians(42))
        except Exception:
            pass
        ob = bpy.data.objects.new(name, me)
        ob.location = origin
        bpy.context.scene.collection.objects.link(ob)
        return ob


def _euler(rot):
    from mathutils import Euler
    return Euler([math.radians(a) for a in rot], 'XYZ').to_matrix().to_4x4()


# ---------------------------------------------------------------- body
B = Builder()

# Torso (brick jacket), slightly tapered towards the shoulders for a chunky look
B.box("jacket_brick", (0.36, 0.24, 0.27), (0, 0, 0.505), bevel=0.045, taper=(1.0, 0.92))
# dark zip/placket stripe on the chest
B.box("jacket_dark", (0.035, 0.02, 0.2), (0, 0.118, 0.51))
# collar
B.cyl("jacket_dark", 0.15, 0.13, 0.05, (0, 0, 0.65), seg=8, caps=False)
# belt + brass buckle
B.cyl("belt_leather", 0.205, 0.205, 0.06, (0, 0, 0.39), seg=8, scale=(1.0, 0.7, 1), smooth=False)
B.box("buckle_brass", (0.085, 0.03, 0.06), (0, 0.145, 0.39))

# Shoulder pads -- red angular plates, widen the silhouette vs. blue heroes
for sx in (-1, 1):
    B.box("red_helmet", (0.13, 0.17, 0.06), (sx * 0.2, 0, 0.635), rot=(0, sx * 22, 0),
          taper=(0.8, 0.85))

# Head (chibi: ~40% of height)
HEAD_Z = 0.84
B.sphere("skin", 0.2, (0, 0, HEAD_Z), scale=(1.06, 0.98, 1.0), seg=10, rings=6)

# Respirator bandana: black cone wrapped around the lower face
B.cyl("mask_black", 0.15, 0.205, 0.115, (0, 0.006, 0.712), seg=10, scale=(1.06, 1.0, 1))
# red diagonal stripe on the bandana front
B.box("mask_red", (0.26, 0.012, 0.018), (0, 0.197, 0.755), rot=(-12, 0, 0))
# respirator filter (red can) on the snout
B.cyl("mask_red", 0.042, 0.036, 0.05, (0, 0.215, 0.7), seg=8, rot=(-90, 0, 0))

# Angry eyes (slanted pale slits) and thick brows angled down to the nose
for sx in (-1, 1):
    B.box("eye_white", (0.06, 0.03, 0.03), (sx * 0.074, 0.188, 0.802),
          rot=(0, sx * -16, sx * -18), taper=(0.75, 1.0))
    B.box("brow_dark", (0.095, 0.04, 0.034), (sx * 0.072, 0.19, 0.838),
          rot=(0, sx * -24, sx * -14))

# Helmet: red dome, cut above the brows
B.sphere("red_helmet", 0.222, (0, -0.008, 0.875), scale=(1.06, 1.04, 0.95),
         seg=10, rings=8, cut_below=-0.005)
# visor / brim -- short peaked front, thicker than the heroes'
B.box("red_helmet", (0.3, 0.08, 0.03), (0, 0.2, 0.885), rot=(16, 0, 0), bevel=0.012,
      taper=(0.95, 1.0))
# crest / mohawk ridge on top (dark red) -- signature silhouette
B.box("red_crest", (0.075, 0.36, 0.1), (0, -0.03, 1.07), bevel=0.02, taper=(0.6, 0.8))

# Arms: from the shoulders forward to the weapon
SH_Z = 0.6
for sx in (-1, 1):
    sh = (sx * 0.2, 0.0, SH_Z)
    if sx > 0:  # right hand on the grip
        hand = (0.07, 0.22, 0.43)
    else:       # left hand on the handguard
        hand = (-0.045, 0.33, 0.47)
    elbow = (sx * 0.22, 0.12, 0.47)
    B.limb("jacket_brick", sh, elbow, 0.062, 0.055, seg=6)
    B.limb("jacket_brick", elbow, hand, 0.055, 0.048, seg=6)
    B.sphere("skin", 0.052, hand, seg=6, rings=3)

# Weapon: stubby SMG, barrel pointing +Y
GX, GZ = 0.0, 0.47
B.box("gun_dark", (0.06, 0.3, 0.085), (GX, 0.27, GZ), bevel=0.012)           # receiver
B.box("gun_dark", (0.05, 0.14, 0.06), (GX, 0.07, GZ - 0.01))      # stock
B.box("gun_metal", (0.04, 0.05, 0.11), (GX, 0.22, GZ - 0.085), rot=(-12, 0, 0))  # magazine
B.box("gun_dark", (0.035, 0.04, 0.07), (0.035, 0.17, GZ - 0.06), rot=(15, 0, 0))   # grip
B.cyl("gun_metal", 0.02, 0.02, 0.14, (GX, 0.47, GZ + 0.01), seg=6, rot=(-90, 0, 0))  # barrel
B.box("mask_red", (0.062, 0.05, 0.03), (GX, 0.38, GZ + 0.05))                 # red sight stripe

body = B.to_object("body")

# ---------------------------------------------------------------- legs
HIP_Z = 0.34
HIP_X = 0.095
legs = []
for name, sx in (("leg_L", -1), ("leg_R", 1)):
    L = Builder()
    hx = sx * HIP_X
    L.cyl("pants_graphite", 0.07, 0.085, 0.25, (hx, 0, HIP_Z - 0.115), seg=8, caps=False)
    # boot: chunky beveled block, toe forward
    L.box("boots_black", (0.13, 0.2, 0.12), (hx, 0.03, 0.06), bevel=0.03,
          taper=(0.95, 0.75))
    legs.append(L.to_object(name, origin=(hx, 0, HIP_Z)))


# ---------------------------------------------------------------- report
bpy.context.view_layer.update()
def tri_count(ob):
    return sum(len(p.vertices) - 2 for p in ob.data.polygons)


objs = [body] + legs
total = sum(tri_count(o) for o in objs)
mins = Vector((1e9, 1e9, 1e9))
maxs = Vector((-1e9, -1e9, -1e9))
for o in objs:
    for v in o.data.vertices:
        w = o.matrix_world @ v.co
        for i in range(3):
            mins[i] = min(mins[i], w[i])
            maxs[i] = max(maxs[i], w[i])
for o in objs:
    print(f"{o.name}: {tri_count(o)} tris, origin {tuple(round(c, 3) for c in o.location)}")
print(f"TOTAL TRIS: {total} (budget {TRI_BUDGET})")
print(f"BBOX min {tuple(round(c, 3) for c in mins)} max {tuple(round(c, 3) for c in maxs)} "
      f"size {tuple(round(c, 3) for c in (maxs - mins))}")
if total > TRI_BUDGET:
    print("!! over budget")
    sys.exit(1)

# ---------------------------------------------------------------- export
bpy.ops.object.select_all(action='DESELECT')
for o in objs:
    o.select_set(True)
bpy.context.view_layer.objects.active = body
bpy.ops.export_scene.gltf(filepath=OUT_GLB, export_format='GLB', export_yup=True,
                          export_apply=True, use_selection=True)
print("exported", OUT_GLB)

# ---------------------------------------------------------------- preview
if "--no-render" in sys.argv:
    sys.exit(0)

scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 32
scene.cycles.use_denoising = False
scene.render.resolution_x = scene.render.resolution_y = 768
scene.render.film_transparent = False
scene.view_settings.view_transform = 'Standard'

world = bpy.data.worlds.new("world")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.55, 0.62, 0.72, 1)
world.node_tree.nodes["Background"].inputs[1].default_value = 0.9
scene.world = world

# ground
bpy.ops.mesh.primitive_plane_add(size=6, location=(0, 0, 0))
ground = bpy.context.active_object
gm = bpy.data.materials.new("preview_ground")
gm.use_nodes = True
gm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.42, 0.40, 0.36, 1)
ground.data.materials.append(gm)

sun_d = bpy.data.lights.new("sun", 'SUN')
sun_d.energy = 3.5
sun_d.angle = math.radians(8)
sun = bpy.data.objects.new("sun", sun_d)
sun.rotation_euler = (math.radians(40), math.radians(-20), math.radians(-30))
scene.collection.objects.link(sun)

cam_d = bpy.data.cameras.new("cam")
cam_d.type = 'ORTHO'
cam_d.ortho_scale = 1.55
cam = bpy.data.objects.new("cam", cam_d)
scene.collection.objects.link(cam)
scene.camera = cam


def aim(pos, target=(0, 0, 0.55)):
    cam.location = pos
    d = Vector(target) - Vector(pos)
    cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()


# front-top: the player sees enemies running towards them
aim((0.9, 2.2, 2.0))
scene.render.filepath = OUT_PREV
bpy.ops.render.render(write_still=True)
# side
aim((2.6, 0.25, 0.75))
scene.render.filepath = OUT_PREV_SIDE
bpy.ops.render.render(write_still=True)
print("previews:", OUT_PREV, OUT_PREV_SIDE)
