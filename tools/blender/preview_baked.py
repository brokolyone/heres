"""Render a baked .mesh.blend with only its baked texture, to check the bake.

    blender -b <name>.mesh.blend --python tools/blender/preview_baked.py -- <texture.png> <out.png>
"""
import math
import sys

import bpy
import mathutils

tex_path, out = sys.argv[sys.argv.index("--") + 1:][:2]
obj = [o for o in bpy.data.objects if o.type == "MESH"][0]
mat = bpy.data.materials.new("preview")
mat.use_nodes = True
nt = mat.node_tree
bsdf = nt.nodes["Principled BSDF"]
bsdf.inputs["Roughness"].default_value = 0.8
tex = nt.nodes.new("ShaderNodeTexImage")
tex.image = bpy.data.images.load(tex_path)
tex.interpolation = "Closest"
uvn = nt.nodes.new("ShaderNodeUVMap")
uvn.uv_map = "bake"
nt.links.new(uvn.outputs[0], tex.inputs[0])
nt.links.new(tex.outputs[0], bsdf.inputs["Base Color"])
obj.data.materials.clear()
obj.data.materials.append(mat)
for p in obj.data.polygons:
    p.use_smooth = False

center = sum((obj.matrix_world @ mathutils.Vector(c) for c in obj.bound_box), mathutils.Vector()) / 8
size = max(obj.dimensions)
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
bpy.context.scene.collection.objects.link(cam)
cam.data.lens = 50
bpy.context.scene.camera = cam
sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
sun.data.energy = 3
sun.rotation_euler = (math.radians(40), 0, math.radians(30))
bpy.context.scene.collection.objects.link(sun)
sc = bpy.context.scene
sc.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items] else "CYCLES"
sc.render.engine = "CYCLES"
sc.cycles.samples = 16
sc.render.resolution_x, sc.render.resolution_y = 1000, 500
views = sys.argv[sys.argv.index("--") + 3:] or ["0,-1,0.15", "0.6,-0.8,0.5", "-0.5,0.7,0.4"]
for i, v in enumerate(views):
    d = mathutils.Vector([float(x) for x in v.split(",")]).normalized()
    cam.location = center + d * size * 1.9
    cam.rotation_euler = (center - cam.location).to_track_quat("-Z", "Y").to_euler()
    sc.render.filepath = out.replace(".png", f"_{i}.png")
    bpy.ops.render.render(write_still=True)
