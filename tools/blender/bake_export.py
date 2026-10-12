"""Bake a Blender scene into a single-texture mesh the mod can render.

Usage (rifle from a .blend):
    blender -b art/precision_rifle.blend --python tools/blender/bake_export.py -- \
        <out.mesh> <out.png> <texture_size> <target_triangles>

Pipeline: join all meshes -> limited dissolve + decimate to the triangle budget ->
fresh smart-UV layout -> Cycles bake of diffuse colour under a soft studio sky
(so bump/AO detail survives) -> tone lift (Minecraft has no specular, so near-black
gun finishes would read as a flat silhouette) -> export triangles.

Mesh format (little endian): b"HMSH", int32 triangle count, then per triangle
3 vertices of (x, y, z, u, v, nx, ny, nz) float32. Normals are smoothed across
edges sharper than SMOOTH_ANGLE so round parts shade round and hard edges stay hard. Coordinates are Minecraft model space:
+Y up, the long axis (Blender +X) points to -Z, centred on (0.5, 0.5, 0.5).
"""
import math
import struct
import sys

import bmesh
import bpy
import numpy as np


def clean_scene(skip_names=("floor",)):
    for o in list(bpy.data.objects):
        if o.type != "MESH" or o.name.split(".")[0] in skip_names or o.hide_render:
            bpy.data.objects.remove(o, do_unlink=True)


def join_meshes():
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    bpy.ops.object.select_all(action="DESELECT")
    for o in meshes:
        o.hide_set(False)
        o.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    bpy.ops.object.make_single_user(object=True, obdata=True)
    bpy.ops.object.convert(target="MESH")
    bpy.ops.object.join()
    obj = bpy.context.view_layer.objects.active
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    return obj


def tri_count(obj):
    return sum(len(p.vertices) - 2 for p in obj.data.polygons)


def reduce(obj, target):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(2), verts=bm.verts, edges=bm.edges,
                             delimit={"MATERIAL"})
    bm.to_mesh(obj.data)
    bm.free()
    tris = tri_count(obj)
    if tris > target:
        mod = obj.modifiers.new("dec", "DECIMATE")
        mod.ratio = target / tris
        mod.use_collapse_triangulate = True
        bpy.ops.object.modifier_apply(modifier=mod.name)
    mod = obj.modifiers.new("tri", "TRIANGULATE")
    bpy.ops.object.modifier_apply(modifier=mod.name)
    print("TRIS", tri_count(obj))


def unwrap(obj):
    uv = obj.data.uv_layers.new(name="bake")
    obj.data.uv_layers.active = uv
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.004,
                             area_weight=0.0, scale_to_bounds=True)
    bpy.ops.object.mode_set(mode="OBJECT")


def studio_world():
    world = bpy.data.worlds.new("bake_sky")
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()
    coord = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    rng = nt.nodes.new("ShaderNodeMapRange")
    rng.inputs["From Min"].default_value = -1.0
    rng.inputs["From Max"].default_value = 1.0
    rng.inputs["To Min"].default_value = 0.45
    rng.inputs["To Max"].default_value = 1.25
    bg = nt.nodes.new("ShaderNodeBackground")
    out = nt.nodes.new("ShaderNodeOutputWorld")
    nt.links.new(coord.outputs["Generated"], sep.inputs[0])
    nt.links.new(sep.outputs["Z"], rng.inputs["Value"])
    nt.links.new(rng.outputs["Result"], bg.inputs["Strength"])
    nt.links.new(bg.outputs[0], out.inputs[0])
    bpy.context.scene.world = world


def bake(obj, size, out_png, lift=(1.0, 0.0)):
    img = bpy.data.images.new("bake", size, size, alpha=False)
    for slot in obj.material_slots:
        mat = slot.material
        if mat is None:
            continue
        mat.use_nodes = True
        nt = mat.node_tree
        for n in nt.nodes:
            if n.type == "BSDF_PRINCIPLED":
                n.inputs["Metallic"].default_value = 0.0
                for name in ("Transmission Weight", "Coat Weight"):
                    if name in n.inputs:
                        n.inputs[name].default_value = 0.0
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = img
        nt.nodes.active = tex
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 48
    sc.render.bake.margin = 6
    sc.render.bake.use_pass_direct = True
    sc.render.bake.use_pass_indirect = True
    sc.render.bake.use_pass_color = True
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.bake(type="DIFFUSE", pass_filter={"DIRECT", "INDIRECT", "COLOR"}, margin=6)

    px = np.array(img.pixels[:], dtype=np.float32).reshape(size, size, 4)
    gain, offset = lift
    px[..., :3] = np.clip(px[..., :3] * gain + offset, 0.0, 1.0)
    img.pixels[:] = px.ravel()
    img.filepath_raw = out_png
    img.file_format = "PNG"
    img.save()


SMOOTH_ANGLE = math.radians(35)


def smooth_normals(co, tris):
    """Per-corner normals: area-weighted average of the face normals around the
    vertex, only over faces within SMOOTH_ANGLE of the corner's own face."""
    a, b, c = co[tris[:, 0]], co[tris[:, 1]], co[tris[:, 2]]
    fn_area = np.cross(b - a, c - a)
    fn = fn_area / np.maximum(np.linalg.norm(fn_area, axis=1, keepdims=True), 1e-12)
    vert_faces = {}
    for fi, t in enumerate(tris):
        for vi in t:
            vert_faces.setdefault(vi, []).append(fi)
    cos_lim = math.cos(SMOOTH_ANGLE)
    out = np.zeros((len(tris), 3, 3))
    for fi, t in enumerate(tris):
        for k, vi in enumerate(t):
            nb = np.array(vert_faces[vi])
            ok = nb[fn[nb] @ fn[fi] >= cos_lim]
            n = fn_area[ok].sum(axis=0)
            ln = np.linalg.norm(n)
            out[fi, k] = n / ln if ln > 1e-12 else fn[fi]
    return out


def export(obj, out_mesh, axis_map, scale=1.0):
    mesh = obj.data
    mesh.calc_loop_triangles()
    uv = mesh.uv_layers["bake"].data
    co = np.array([axis_map(v.co) for v in mesh.vertices], dtype=np.float64) * scale
    co += 0.5 - (co.min(axis=0) + co.max(axis=0)) / 2
    tri_v = np.array([t.vertices[:] for t in mesh.loop_triangles])
    tri_l = np.array([t.loops[:] for t in mesh.loop_triangles])
    normals = smooth_normals(co, tri_v)
    with open(out_mesh, "wb") as f:
        f.write(b"HMSH")
        f.write(struct.pack("<i", len(tri_v)))
        for fi in range(len(tri_v)):
            for k in range(3):
                u, v = uv[tri_l[fi, k]].uv
                x, y, z = co[tri_v[fi, k]]
                nx, ny, nz = normals[fi, k]
                f.write(struct.pack("<8f", x, y, z, u, 1.0 - v, nx, ny, nz))
    print("EXPORTED", len(tri_v), "tris, size", co.max(axis=0) - co.min(axis=0))


# Blender (+X long axis, +Z up) -> Minecraft (long axis to -Z, +Y up), mirror-free.
def blender_to_mc(c):
    return (-c[1], c[2], -c[0])


def run(out_mesh, out_png, size, target, lift=(1.0, 0.0), scale=1.0):
    clean_scene()
    obj = join_meshes()
    reduce(obj, target)
    unwrap(obj)
    studio_world()
    bake(obj, size, out_png, lift)
    bpy.ops.wm.save_as_mainfile(filepath=out_mesh + ".blend")
    export(obj, out_mesh, blender_to_mc, scale)


if __name__ == "__main__" and "--" in sys.argv:
    a = sys.argv[sys.argv.index("--") + 1:]
    run(a[0], a[1], int(a[2]), int(a[3]),
        lift=(float(a[4]), float(a[5])) if len(a) > 5 else (1.0, 0.0))
