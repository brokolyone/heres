"""Test render of terrain.py: python3 test_terrain.py [main|trees|mid|all] [samples]"""
import math
import os
import sys
import time

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common
import terrain

what = sys.argv[1] if len(sys.argv) > 1 else "all"
samples = int(sys.argv[2]) if len(sys.argv) > 2 else 32

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

t0 = time.time()
info = terrain.build()
print("build() %.1fs  terrain verts=%d  treeline instances=%d  mid=%d" % (
    time.time() - t0, info["terrain_vertex_count"], info["treeline_instances"], info["mid_instances"]))
print("prototype polys:", info["prototype_polys"])

# ---- sky + sun ----------------------------------------------------------------
world = bpy.data.worlds.new("TestSky")
scene.world = world
world.use_nodes = True
nt = world.node_tree
bg = nt.nodes["Background"]
sky = nt.nodes.new("ShaderNodeTexSky")
sky.sky_type = 'MULTIPLE_SCATTERING'
sky.sun_disc = False
sky.sun_elevation = math.radians(common.SUN_ELEVATION_DEG)
sky.sun_rotation = math.radians(common.SUN_AZIMUTH_DEG)
nt.links.new(sky.outputs[0], bg.inputs[0])
bg.inputs[1].default_value = 0.25

sd = Vector(common.sun_direction_to_sun())
sun = bpy.data.objects.new("TestSun", bpy.data.lights.new("TestSun", 'SUN'))
sun.data.energy = 5.0
sun.data.angle = math.radians(0.6)
sun.rotation_euler = sd.to_track_quat('Z', 'Y').to_euler()
scene.collection.objects.link(sun)

# ---- camera -------------------------------------------------------------------
cam = bpy.data.objects.new("TestCam", bpy.data.cameras.new("TestCam"))
scene.collection.objects.link(cam)
scene.camera = cam
cam.data.clip_start = 0.1
cam.data.clip_end = 20000


def aim(loc, yaw_left_deg, pitch_deg, lens):
    cam.location = loc
    cam.rotation_euler = (math.radians(90 + pitch_deg), 0, math.radians(yaw_left_deg))
    cam.data.lens = lens


r = scene.render
r.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = samples
scene.cycles.use_denoising = True
scene.cycles.max_bounces = 6
scene.cycles.transparent_max_bounces = 8
r.threads_mode = 'FIXED'
r.threads = 2
r.resolution_x, r.resolution_y = 800, 375
r.resolution_percentage = 100
scene.view_settings.view_transform = 'AgX'
try:
    scene.view_settings.look = 'AgX - Medium High Contrast'
except Exception:
    pass
r.image_settings.file_format = 'PNG'

shots = {
    "main": ("test_terrain.png", common.CAMERA_LOCATION, common.CAMERA_YAW_LEFT_DEG,
             common.CAMERA_PITCH_DEG, common.CAMERA_LENS_MM),
    "trees": ("test_terrain_trees.png", (-3.0, 0.0, 1.55), 62.0, 1.3, 420.0),
    "mid": ("test_terrain_mid.png", (-3.0, 0.0, 1.55), 47.0, -0.6, 200.0),
    "left": ("test_terrain_left.png", (-3.0, 0.0, 1.55), 75.0, -4.0, 24.0),
}
for key, (fn, loc, yaw, pitch, lens) in shots.items():
    if what not in ("all", key):
        continue
    aim(loc, yaw, pitch, lens)
    r.filepath = os.path.join(HERE, "renders", fn)
    t0 = time.time()
    bpy.ops.render.render(write_still=True)
    print("rendered %s in %.1fs" % (fn, time.time() - t0))
try:
    import resource
    print("peak RSS MB: %.0f" % (resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024))
except Exception:
    pass
