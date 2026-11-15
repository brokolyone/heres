"""Standalone test render of corridor.build() with a temporary sky / sun / ground / camera.

usage: python3 test_corridor.py [out.png] [res_x] [samples]
"""
import math
import os
import sys
import time

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common as C  # noqa: E402
import corridor  # noqa: E402

out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "renders", "test_corridor.png")
res_x = int(sys.argv[2]) if len(sys.argv) > 2 else 800
samples = int(sys.argv[3]) if len(sys.argv) > 3 else 40
res_x = min(res_x, 800)
samples = min(samples, 48)

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
t0 = time.time()
info = corridor.build()
print("build() ok in %.2fs, keys: %s" % (time.time() - t0, sorted(info.keys())))
print("objects:", len(info["objects"]), "ceiling counts:", info["ceiling_counts"])

tmp = C.get_collection("TestRig")

# --- world: physical sky (no sun disc; a sun lamp gives the direct light)
world = bpy.data.worlds.new("TestSky")
scene.world = world
if world.node_tree is None:
    world.use_nodes = True
nt = world.node_tree
nt.nodes.clear()
sky = nt.nodes.new("ShaderNodeTexSky")
sky.sky_type = "MULTIPLE_SCATTERING"
sky.sun_disc = False
sky.sun_elevation = math.radians(C.SUN_ELEVATION_DEG)
sky.sun_rotation = math.radians(C.SUN_AZIMUTH_DEG)
bg = nt.nodes.new("ShaderNodeBackground")
bg.inputs["Strength"].default_value = 0.22
wo = nt.nodes.new("ShaderNodeOutputWorld")
nt.links.new(sky.outputs[0], bg.inputs[0])
nt.links.new(bg.outputs[0], wo.inputs[0])

# --- sun
sd = bpy.data.lights.new("TestSun", "SUN")
sd.energy = 5.0
sd.angle = math.radians(0.6)
sun = bpy.data.objects.new("TestSun", sd)
tmp.objects.link(sun)
to_sun = Vector(C.sun_direction_to_sun())
sun.rotation_euler = to_sun.to_track_quat("Z", "Y").to_euler()   # lamp shines along its -Z

# --- green ground
me = bpy.data.meshes.new("TestGround")
s = 2000.0
me.from_pydata([(-s, -s, C.GROUND_Z), (C.FIELD_X_MAX, -s, C.GROUND_Z), (C.FIELD_X_MAX, s, C.GROUND_Z),
                (-s, s, C.GROUND_Z)], [], [(0, 1, 2, 3)])
gm = bpy.data.materials.new("TestGrass")
if gm.node_tree is None:
    gm.use_nodes = True
pb = next(n for n in gm.node_tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled")
pb.inputs["Base Color"].default_value = (0.16, 0.42, 0.04, 1)
pb.inputs["Roughness"].default_value = 0.8
me.materials.append(gm)
tmp.objects.link(bpy.data.objects.new("TestGround", me))
# dark treeline stand-in
tm = bpy.data.meshes.new("TestTrees")
d = -C.TREELINE_DISTANCE
tm.from_pydata([(d, -s, C.GROUND_Z), (d, s, C.GROUND_Z), (d, s, C.GROUND_Z + 14), (d, -s, C.GROUND_Z + 14)],
               [], [(0, 1, 2, 3)])
tmat = bpy.data.materials.new("TestTrees")
if tmat.node_tree is None:
    tmat.use_nodes = True
next(n for n in tmat.node_tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled").inputs[
    "Base Color"].default_value = (0.02, 0.05, 0.02, 1)
tm.materials.append(tmat)
tmp.objects.link(bpy.data.objects.new("TestTrees", tm))

# --- camera
cd = bpy.data.cameras.new("TestCam")
cd.lens = C.CAMERA_LENS_MM
cd.sensor_width = 36.0
cd.clip_start, cd.clip_end = 0.05, 5000.0
cam = bpy.data.objects.new("TestCam", cd)
tmp.objects.link(cam)
cam.location = C.CAMERA_LOCATION
cam.rotation_euler = (math.radians(90.0 + C.CAMERA_PITCH_DEG), 0.0, math.radians(C.CAMERA_YAW_LEFT_DEG))
scene.camera = cam

# --- render settings (small: CPU is shared)
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = samples
scene.cycles.use_adaptive_sampling = True
scene.cycles.adaptive_threshold = 0.03
scene.cycles.use_denoising = True
scene.cycles.max_bounces = 8
scene.cycles.diffuse_bounces = 4
scene.cycles.glossy_bounces = 4
scene.cycles.transparent_max_bounces = 12
scene.cycles.transmission_bounces = 4
scene.cycles.caustics_reflective = False
scene.cycles.caustics_refractive = False
scene.cycles.sample_clamp_indirect = 8.0
scene.render.threads_mode = "FIXED"
scene.render.threads = 2
scene.render.resolution_x = res_x
scene.render.resolution_y = int(round(res_x * C.RES_Y / C.RES_X))
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.render.filepath = out
scene.view_settings.exposure = -0.9
try:
    scene.view_settings.look = "AgX - Medium High Contrast"
except Exception as e:
    print("look not set:", e)

t0 = time.time()
bpy.ops.render.render(write_still=True)
print("rendered %s in %.1fs" % (out, time.time() - t0))
