"""Shared helpers for environment models (bridge_segment, tower, skyline).

Builds low-poly meshes directly from vertex/face lists so triangle counts stay
under tight control, exports GLB per CONTRACT.md and renders a Cycles preview.
"""
import math
import os

import bpy
import bmesh
from mathutils import Vector

SRC_DIR = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.dirname(SRC_DIR)
PREVIEW_DIR = os.path.join(MODELS_DIR, "previews")


# ---------------------------------------------------------------- scene / materials
def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def hex_rgb(h):
    h = h.lstrip("#")
    srgb = [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]

    def lin(c):
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    return tuple(lin(c) for c in srgb)


def material(name, color, rough=0.6, metal=0.0, emit=None, emit_strength=0.0):
    mat = bpy.data.materials.new(name)
    try:
        mat.use_nodes = True
    except Exception:
        pass
    nt = mat.node_tree
    bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if bsdf is None:
        for n in list(nt.nodes):
            nt.nodes.remove(n)
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
        nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    rgb = hex_rgb(color)
    bsdf.inputs["Base Color"].default_value = (*rgb, 1.0)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    if emit:
        bsdf.inputs["Emission Color"].default_value = (*hex_rgb(emit), 1.0)
        bsdf.inputs["Emission Strength"].default_value = emit_strength
    mat.diffuse_color = (*rgb, 1.0)
    mat.roughness = rough
    return mat


# ---------------------------------------------------------------- mesh builder
class Builder:
    """Accumulates polygons with per-face material + smooth flag."""

    def __init__(self):
        self.verts = []
        self.faces = []
        self.mats = []
        self.smooth = []
        self.mat_list = []

    def _mi(self, mat):
        if mat not in self.mat_list:
            self.mat_list.append(mat)
        return self.mat_list.index(mat)

    def add(self, verts, faces, mat, smooth=False):
        base = len(self.verts)
        self.verts.extend(Vector(v) for v in verts)
        mi = self._mi(mat)
        for f in faces:
            self.faces.append([base + i for i in f])
            self.mats.append(mi)
            self.smooth.append(smooth)

    def quad(self, a, b, c, d, mat):
        self.add([a, b, c, d], [(0, 1, 2, 3)], mat)

    def box(self, x0, x1, y0, y1, z0, z1, mat, skip=()):
        """Axis aligned box. skip: subset of {'-x','+x','-y','+y','-z','+z'}."""
        v = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
             (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
        f = {"-z": (0, 3, 2, 1), "+z": (4, 5, 6, 7), "-y": (0, 1, 5, 4),
             "+y": (2, 3, 7, 6), "-x": (3, 0, 4, 7), "+x": (1, 2, 6, 5)}
        self.add(v, [f[k] for k in f if k not in skip], mat)

    def cbox(self, cx, cy, cz, sx, sy, sz, mat, skip=()):
        self.box(cx - sx / 2, cx + sx / 2, cy - sy / 2, cy + sy / 2, cz - sz / 2, cz + sz / 2, mat, skip)

    def prism(self, p0, p1, r, mat, sides=6, caps=True, smooth=True, r1=None, roll=0.0):
        """Cylinder/tapered prism from p0 to p1 (radius r at p0, r1 at p1)."""
        p0, p1 = Vector(p0), Vector(p1)
        r1 = r if r1 is None else r1
        axis = (p1 - p0).normalized()
        helper = Vector((0, 0, 1)) if abs(axis.z) < 0.9 else Vector((1, 0, 0))
        u = axis.cross(helper).normalized()
        w = axis.cross(u).normalized()
        verts = []
        for p, rr in ((p0, r), (p1, r1)):
            for i in range(sides):
                a = roll + 2 * math.pi * i / sides
                verts.append(p + (u * math.cos(a) + w * math.sin(a)) * rr)
        faces = [(i, (i + 1) % sides, sides + (i + 1) % sides, sides + i) for i in range(sides)]
        self.add(verts, faces, mat, smooth)
        if caps:
            base = len(self.verts) - 2 * sides
            mi = self._mi(mat)
            self.faces.append([base + i for i in reversed(range(sides))])
            self.mats.append(mi)
            self.smooth.append(False)
            self.faces.append([base + sides + i for i in range(sides)])
            self.mats.append(mi)
            self.smooth.append(False)

    def cone(self, base_c, height, r, mat, sides=6, cap=False, roll=0.0, smooth=False):
        c = Vector(base_c)
        verts = [c + Vector((math.cos(roll + 2 * math.pi * i / sides) * r,
                             math.sin(roll + 2 * math.pi * i / sides) * r, 0)) for i in range(sides)]
        verts.append(c + Vector((0, 0, height)))
        faces = [(i, (i + 1) % sides, sides) for i in range(sides)]
        if cap:
            faces.append(tuple(reversed(range(sides))))
        self.add(verts, faces, mat, smooth)

    def from_bmesh(self, bm, mat_fn, smooth=False):
        """mat_fn(face) -> material."""
        idx = {v: i for i, v in enumerate(bm.verts)}
        base = len(self.verts)
        self.verts.extend(v.co.copy() for v in bm.verts)
        for f in bm.faces:
            self.faces.append([base + idx[v] for v in f.verts])
            self.mats.append(self._mi(mat_fn(f)))
            self.smooth.append(smooth)

    def build(self, name, merge_dist=None):
        me = bpy.data.meshes.new(name)
        me.from_pydata([tuple(v) for v in self.verts], [], self.faces)
        for m in self.mat_list:
            me.materials.append(m)
        for p, mi, sm in zip(me.polygons, self.mats, self.smooth):
            p.material_index = mi
            p.use_smooth = sm
        me.validate()
        me.update()
        if merge_dist:
            bm = bmesh.new()
            bm.from_mesh(me)
            bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=merge_dist)
            bm.to_mesh(me)
            bm.free()
        ob = bpy.data.objects.new(name, me)
        bpy.context.scene.collection.objects.link(ob)
        return ob


# ---------------------------------------------------------------- export / stats
def tri_count(ob):
    return sum(len(p.vertices) - 2 for p in ob.data.polygons)


def bbox(objs):
    mn = Vector((1e9, 1e9, 1e9))
    mx = Vector((-1e9, -1e9, -1e9))
    for ob in objs:
        for c in ob.bound_box:
            w = ob.matrix_world @ Vector(c)
            mn = Vector(map(min, mn, w))
            mx = Vector(map(max, mx, w))
    return mn, mx


def export(objs, name):
    path = os.path.join(MODELS_DIR, name + ".glb")
    bpy.ops.object.select_all(action="DESELECT")
    for ob in objs:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", export_yup=True,
                              export_apply=True, use_selection=True)
    tris = sum(tri_count(o) for o in objs)
    mn, mx = bbox(objs)
    size = mx - mn
    print(f"[{name}] {path}")
    print(f"[{name}] triangles: {tris}")
    print(f"[{name}] bbox Blender min ({mn.x:.2f}, {mn.y:.2f}, {mn.z:.2f}) "
          f"max ({mx.x:.2f}, {mx.y:.2f}, {mx.z:.2f}) size ({size.x:.2f} x {size.y:.2f} x {size.z:.2f})")
    return path, tris, (mn, mx)


# ---------------------------------------------------------------- preview
def preview_setup(water=True, water_z=-9.0, sun_rot=(50, 0, 35)):
    scn = bpy.context.scene
    world = bpy.data.worlds.new("PreviewWorld")
    scn.world = world
    try:
        world.use_nodes = True
    except Exception:
        pass
    bg = next((n for n in world.node_tree.nodes if n.type == "BACKGROUND"), None)
    if bg is None:
        bg = world.node_tree.nodes.new("ShaderNodeBackground")
        out = world.node_tree.nodes.new("ShaderNodeOutputWorld")
        world.node_tree.links.new(bg.outputs[0], out.inputs[0])
    bg.inputs[0].default_value = (*hex_rgb("#BFE3F2"), 1)
    bg.inputs[1].default_value = 0.9

    sun_d = bpy.data.lights.new("PreviewSun", "SUN")
    sun_d.energy = 3.2
    sun_d.angle = math.radians(8)
    sun_d.color = hex_rgb("#FFF1DC")
    sun = bpy.data.objects.new("PreviewSun", sun_d)
    sun.rotation_euler = [math.radians(a) for a in sun_rot]
    scn.collection.objects.link(sun)

    if water:
        wm = material("PreviewWater", "#2FB4C6", rough=0.25)
        b = Builder()
        b.box(-400, 400, -400, 400, water_z, water_z, wm, skip=("-z", "-x", "+x", "-y", "+y"))
        b.build("PreviewWater")


def camera(loc, target, lens=35):
    cd = bpy.data.cameras.new("PreviewCam")
    cd.lens = lens
    cd.clip_end = 2000
    cam = bpy.data.objects.new("PreviewCam", cd)
    bpy.context.scene.collection.objects.link(cam)
    cam.location = Vector(loc)
    d = Vector(target) - Vector(loc)
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = cam
    return cam


def render(name, samples=48, res=768):
    scn = bpy.context.scene
    scn.render.engine = "CYCLES"
    scn.cycles.device = "CPU"
    scn.cycles.samples = samples
    scn.cycles.use_denoising = False
    try:
        scn.cycles.use_adaptive_sampling = True
    except Exception:
        pass
    scn.cycles.max_bounces = 4
    scn.render.resolution_x = res
    scn.render.resolution_y = res
    scn.render.resolution_percentage = 100
    scn.render.film_transparent = False
    try:
        scn.view_settings.view_transform = "Standard"
        scn.view_settings.look = "None"
    except Exception:
        pass
    scn.render.image_settings.file_format = "PNG"
    os.makedirs(PREVIEW_DIR, exist_ok=True)
    path = name if os.path.isabs(name) else os.path.join(PREVIEW_DIR, name + ".png")
    scn.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print(f"preview -> {path}")
    return path


def game_camera(target, dist, pitch_deg=45, x=0.0, lens=35):
    t = Vector(target)
    p = math.radians(pitch_deg)
    loc = (t.x + x, t.y - dist * math.cos(p), t.z + dist * math.sin(p))
    return camera(loc, t, lens)
