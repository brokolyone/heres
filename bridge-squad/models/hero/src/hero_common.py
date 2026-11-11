"""Shared constants & helpers for the hero soldier (owner: Art Director).

Usage in a part script:
    import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from hero_common import *
    reset()
    ... build meshes ..., obj.data.materials.append(mat("M_skin")); uv_world(obj); tag(obj, "body", 0, "body")
    save_part("body"); preview("part_body")
"""
import bpy, bmesh, math, os, json
from mathutils import Vector, Matrix

HERO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARTS_DIR = os.environ.get("HERO_PARTS_DIR") or os.path.join(HERO_DIR, "parts")
PREVIEW_DIR = os.path.join(HERO_DIR, "previews")
TEX_DIR = os.path.join(HERO_DIR, "textures")
for _d in (PARTS_DIR, PREVIEW_DIR, TEX_DIR):
    os.makedirs(_d, exist_ok=True)

V = Vector
# ---------------------------------------------------------------- anchors (PLAN.md §3)
A = {
    "hip_L": V((-0.085, 0.0, 0.30)), "hip_R": V((0.085, 0.0, 0.30)),
    "knee_L": V((-0.085, 0.005, 0.165)), "knee_R": V((0.085, 0.005, 0.165)),
    "ankle_L": V((-0.085, 0.0, 0.075)), "ankle_R": V((0.085, 0.0, 0.075)),
    "crotch_z": 0.255,
    "belt_z": (0.305, 0.355), "waist_half": (0.145, 0.105),
    "chest_z": 0.48, "chest_half_x": 0.165, "chest_front_y": 0.115, "chest_back_y": -0.110,
    "shoulder_L": V((-0.185, 0.015, 0.545)), "shoulder_R": V((0.185, 0.015, 0.545)),
    "elbow_R": V((0.215, 0.050, 0.405)), "wrist_R": V((0.115, 0.150, 0.405)), "hand_R": V((0.085, 0.200, 0.395)),
    "elbow_L": V((-0.170, 0.135, 0.430)), "wrist_L": V((0.010, 0.270, 0.430)), "hand_L": V((0.060, 0.330, 0.425)),
    "neck": V((0.0, 0.0, 0.615)), "neck_r": 0.05,
    "head": V((0.0, 0.012, 0.775)), "head_r": V((0.140, 0.145, 0.155)),
    "eye_L": V((-0.050, 0.138, 0.765)), "eye_R": V((0.050, 0.138, 0.765)),
    "ear_L": V((-0.140, 0.0, 0.770)), "ear_R": V((0.140, 0.0, 0.770)),
    "helmet": V((0.0, -0.005, 0.795)), "helmet_r": 0.172,
    "brim_z": {"front": 0.840, "side": 0.760, "back": 0.735},
    "goggles": V((0.0, 0.150, 0.880)),
    "rifle_x": 0.085, "rifle_z": 0.455, "rifle_butt_y": 0.100, "rifle_muzzle_y": 0.680,
    "backpack": V((0.0, -0.185, 0.460)), "backpack_size": V((0.28, 0.13, 0.26)),
}

PALETTE = {
    "M_helmet_blue": "#2F6BFF", "M_jacket_blue": "#3C7FE0", "M_pants_navy": "#283A63",
    "M_vest_tan": "#C7A36B", "M_strap_tan": "#A98654", "M_backpack_blue": "#2C5BC4",
    "M_leather_brown": "#5A3E2B", "M_rubber_dark": "#2B2D33", "M_glove": "#3B4252",
    "M_skin": "#F0BE96", "M_hair": "#4A3022", "M_eye_white": "#F4F1EA", "M_eye_iris": "#3B6EA8",
    "M_eye_pupil": "#1E2430", "M_mouth": "#B5655A", "M_goggle_lens": "#FFB23E",
    "M_metal_gun": "#3A414D", "M_polymer_gun": "#2E333B", "M_gun_accent": "#2F6BFF",
    "M_metal_bright": "#B9BEC6", "M_emblem": "#FFD54A", "M_cloth_olive": "#6F7A4E",
    "M_lens_glow": "#7FE8FF",
}
ROUGH = {"M_helmet_blue": 0.42, "M_goggle_lens": 0.08, "M_metal_gun": 0.38, "M_metal_bright": 0.3,
         "M_eye_white": 0.25, "M_eye_iris": 0.15, "M_eye_pupil": 0.1, "M_polymer_gun": 0.55}
METAL = {"M_metal_gun": 0.85, "M_metal_bright": 1.0}


def srgb_to_lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hex_lin(h):
    h = h.lstrip("#")
    return tuple(srgb_to_lin(int(h[i:i + 2], 16) / 255.0) for i in (0, 2, 4))


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def mat(name):
    """Placeholder material (flat palette colour). The materials artist's library replaces it by name."""
    if name not in PALETTE:
        raise KeyError(f"unknown material slot {name}; allowed: {sorted(PALETTE)}")
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    rgb = hex_lin(PALETTE[name])
    m.diffuse_color = (*rgb, 1.0)
    m.roughness = ROUGH.get(name, 0.7)
    m.metallic = METAL.get(name, 0.0)
    m.use_nodes = True
    b = m.node_tree.nodes.get("Principled BSDF")
    if b:
        b.inputs["Base Color"].default_value = (*rgb, 1.0)
        b.inputs["Roughness"].default_value = ROUGH.get(name, 0.7)
        b.inputs["Metallic"].default_value = METAL.get(name, 0.0)
    return m


def tag(obj, target="body", lod=0, owner="?"):
    assert target in ("body", "leg_L", "leg_R")
    obj["hero_target"] = target
    obj["hero_lod"] = int(lod)
    obj["hero_owner"] = owner
    return obj


def apply_all(obj):
    """Apply modifiers + transforms so verts are in world space."""
    bpy.context.view_layer.objects.active = obj
    for o in bpy.context.selected_objects:
        o.select_set(False)
    obj.select_set(True)
    for m in list(obj.modifiers):
        try:
            bpy.ops.object.modifier_apply(modifier=m.name)
        except Exception as e:
            print("modifier apply failed", obj.name, m.name, e)
            obj.modifiers.remove(m)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    obj.select_set(False)


def uv_world(obj, unit=0.5, angle=66.0, margin=0.002):
    """Smart-project and rescale UVs so 1 UV unit == `unit` metres of surface. Map name 'UVMap'."""
    me = obj.data
    if not me.uv_layers:
        me.uv_layers.new(name="UVMap")
    me.uv_layers[0].name = "UVMap"
    me.uv_layers.active = me.uv_layers[0]
    bpy.context.view_layer.objects.active = obj
    for o in bpy.context.selected_objects:
        o.select_set(False)
    obj.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(angle), island_margin=margin, scale_to_bounds=False)
    bpy.ops.object.mode_set(mode="OBJECT")
    bm = bmesh.new(); bm.from_mesh(me)
    uvl = bm.loops.layers.uv.active
    a3 = 0.0; a2 = 0.0
    mw = obj.matrix_world
    for f in bm.faces:
        a3 += f.calc_area() * (mw.median_scale ** 2)
        uvs = [l[uvl].uv for l in f.loops]
        s = 0.0
        for i in range(len(uvs)):
            x1, y1 = uvs[i]; x2, y2 = uvs[(i + 1) % len(uvs)]
            s += x1 * y2 - x2 * y1
        a2 += abs(s) / 2
    if a2 > 1e-12:
        k = math.sqrt(a3 / a2) / unit
        for f in bm.faces:
            for l in f.loops:
                l[uvl].uv = l[uvl].uv * k
    bm.to_mesh(me); bm.free()
    obj.select_set(False)


def tris(obj):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(dg)
    me = ev.to_mesh()
    n = sum(len(p.vertices) - 2 for p in me.polygons)
    ev.to_mesh_clear()
    return n


def report(owner=None):
    tot = {}
    for o in bpy.data.objects:
        if o.type != "MESH" or (owner and o.get("hero_owner") != owner):
            continue
        k = (o.get("hero_lod", 0), o.get("hero_target", "?"))
        tot[k] = tot.get(k, 0) + tris(o)
    for k in sorted(tot):
        print(f"  LOD{k[0]} {k[1]:6s}: {tot[k]} tris")
    for lod in (0, 1):
        print(f"  LOD{lod} total: {sum(v for k, v in tot.items() if k[0] == lod)}")
    return tot


def save_part(owner):
    """Apply modifiers/transforms on all mesh objects, remove non-mesh objects, save parts/<owner>.blend atomically."""
    for o in list(bpy.data.objects):
        if o.type != "MESH":
            bpy.data.objects.remove(o, do_unlink=True)
    for o in list(bpy.data.objects):
        o.parent = None
    for o in list(bpy.data.objects):
        apply_all(o)
        if "hero_target" not in o:
            print("WARNING untagged object", o.name, "-> body/lod0")
            tag(o, "body", 0, owner)
        if not o.data.uv_layers:
            uv_world(o)
    report()
    path = os.path.join(PARTS_DIR, owner + ".blend")
    tmp = os.path.join(PARTS_DIR, owner + ".tmp.blend")
    bpy.ops.wm.save_as_mainfile(filepath=tmp, compress=True, copy=True)
    os.replace(tmp, path)
    print("saved", path)
    return path


# ---------------------------------------------------------------- preview rendering
VIEWS = {  # name: (camera location, look-at)
    "back34": (V((1.6, -2.3, 2.2)), V((0, 0.05, 0.48))),   # like the game camera (behind, above)
    "front34": (V((1.3, 2.0, 0.95)), V((0, 0.05, 0.5))),
    "front": (V((0.0, 2.6, 0.6)), V((0, 0.05, 0.5))),
    "side": (V((2.6, 0.1, 0.6)), V((0, 0.1, 0.5))),
    "face": (V((0.35, 1.0, 0.85)), V((0, 0.06, 0.79))),
    "top": (V((0.0, -0.4, 3.0)), V((0, 0.0, 0.4))),
}


def _look(cam, target):
    d = target - cam.location
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


def preview(name, views=("front34", "back34", "side"), lod=None, res=512, engine="CYCLES", lens=85,
            samples=16, objects=None):
    """Render each view to previews/<name>_<view>.png. Non-destructive: cleans up its cameras/lights.
    lod=None renders everything, otherwise only objects with hero_lod==lod (others hidden)."""
    sc = bpy.context.scene
    hidden = []
    for o in bpy.data.objects:
        if o.type == "MESH":
            show = (lod is None or o.get("hero_lod", 0) == lod) and (objects is None or o in objects)
            if not show:
                o.hide_render = True; hidden.append(o)
    sc.render.resolution_x = sc.render.resolution_y = res
    sc.render.film_transparent = False
    world = sc.world or bpy.data.worlds.new("W")
    sc.world = world
    created = []
    if engine == "WORKBENCH":
        sc.render.engine = "BLENDER_WORKBENCH"
        sh = sc.display.shading
        sh.light = "STUDIO"; sh.color_type = "MATERIAL"
        sh.show_cavity = True; sh.cavity_type = "BOTH"
        sh.show_shadows = True
        sh.background_type = "VIEWPORT"; sh.background_color = (0.62, 0.70, 0.78)
        try:
            sc.display.shading.show_object_outline = False
        except Exception:
            pass
    else:
        sc.render.engine = "CYCLES"
        sc.cycles.device = "CPU"; sc.cycles.samples = samples
        sc.cycles.use_denoising = True
        try:
            sc.cycles.denoiser = "OPENIMAGEDENOISE"
        except Exception:
            pass
        world.use_nodes = True
        bg = world.node_tree.nodes.get("Background")
        bg.inputs[0].default_value = (0.55, 0.65, 0.78, 1); bg.inputs[1].default_value = 0.9
        for nm, rot, en, sz in (("key", (50, 0, -35), 3.2, 3), ("rim", (60, 0, 160), 2.0, 5), ("fill", (70, 0, 60), 0.8, 10)):
            ld = bpy.data.lights.new(nm, "SUN"); ld.energy = en; ld.angle = math.radians(sz)
            lo = bpy.data.objects.new(nm, ld); sc.collection.objects.link(lo)
            lo.rotation_euler = [math.radians(r) for r in rot]
            created.append(lo)
        # ground
        bpy.ops.mesh.primitive_plane_add(size=60, location=(0, 0, 0))
        g = bpy.context.active_object
        gm = bpy.data.materials.new("_ground"); gm.use_nodes = True
        gm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.42, 0.45, 0.5, 1)
        g.data.materials.append(gm); created.append(g)
    cd = bpy.data.cameras.new("cam"); cd.lens = lens
    cam = bpy.data.objects.new("cam", cd); sc.collection.objects.link(cam); created.append(cam)
    sc.camera = cam
    out = []
    for v in views:
        loc, tgt = VIEWS[v] if isinstance(v, str) else v
        cam.location = loc; _look(cam, tgt)
        vname = v if isinstance(v, str) else "custom"
        path = os.path.join(PREVIEW_DIR, f"{name}_{vname}.png")
        sc.render.filepath = path
        bpy.ops.render.render(write_still=True)
        out.append(path)
    for o in created:
        bpy.data.objects.remove(o, do_unlink=True)
    for o in hidden:
        o.hide_render = False
    print("previews:", out)
    return out
