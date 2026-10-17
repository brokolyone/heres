"""blender -b art/creek/creek.blend --python tools/creek/render.py -- out.png [percent] [samples]"""
import sys
import bpy

args = sys.argv[sys.argv.index("--") + 1:]
scene = bpy.context.scene
scene.render.resolution_percentage = int(args[1]) if len(args) > 1 else 100
if len(args) > 2:
    scene.cycles.samples = int(args[2])
scene.render.filepath = args[0]
bpy.ops.render.render(write_still=True)
