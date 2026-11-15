"""Standalone test for grass.py: stand-in terrain, sky + sun, two cameras.

    python3 test_grass.py [wide] [close] [--samples N] [--mask] [--res WxH]
"""
import math
import os
import resource
import sys
import time

import bpy
import numpy as np
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common  # noqa: E402
import grass   # noqa: E402

ARGS = sys.argv[1:]
SAMPLES = int(ARGS[ARGS.index("--samples") + 1]) if "--samples" in ARGS else 40
RES = (800, 375)
if "--res" in ARGS:
    RES = tuple(int(v) for v in ARGS[ARGS.index("--res") + 1].split("x"))
VIEWS = [a for a in ARGS if a in ("wide", "close", "tall")] or ["wide", "close"]
WITH_MASK = "--mask" in ARGS


def terrain_height(x, y):
    return common.GROUND_Z + 0.18 * np.sin(x / 23.0) * np.cos(y / 31.0) + 0.06 * np.sin(x / 5.0 + y / 7.0)


def make_terrain():
    nx, ny = 180, 190
    xs = np.linspace(common.FIELD_X_MIN, common.FIELD_X_MAX, nx)
    ys = np.linspace(common.FIELD_Y_MIN, common.FIELD_Y_MAX, ny)
    X, Y = np.meshgrid(xs, ys, indexing="ij")
    Z = terrain_height(X, Y)
    verts = np.stack([X.ravel(), Y.ravel(), Z.ravel()], axis=1)
    faces = [(i * ny + j, (i + 1) * ny + j, (i + 1) * ny + j + 1, i * ny + j + 1)
             for i in range(nx - 1) for j in range(ny - 1)]
    me = bpy.data.meshes.new("Terrain")
    me.from_pydata(verts.tolist(), [], faces)
    if WITH_MASK:
        att = me.attributes.new("field_mask", 'FLOAT', 'POINT')
        att.data.foreach_set("value", (0.5 + 0.5 * np.sin(X.ravel() / 30.0) * np.sin(Y.ravel() / 40.0)))
    mat = bpy.data.materials.new("TerrainStandIn")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.10, 0.17, 0.03, 1)
    bsdf.inputs["Roughness"].default_value = 0.9
    me.materials.append(mat)
    ob = bpy.data.objects.new(common.TERRAIN_OBJECT_NAME, me)
    common.get_collection("Terrain").objects.link(ob)
    return ob


def make_world_and_sun():
    scene = bpy.context.scene
    w = bpy.data.worlds.new("TestSky")
    w.use_nodes = True
    nt = w.node_tree
    bg = nt.nodes["Background"]
    sky = nt.nodes.new("ShaderNodeTexSky")
    sky.sky_type = 'MULTIPLE_SCATTERING'
    sky.sun_disc = False
    sky.sun_elevation = math.radians(common.SUN_ELEVATION_DEG)
    nt.links.new(sky.outputs[0], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = 0.25
    scene.world = w
    to_sun = Vector(common.sun_direction_to_sun())
    ld = bpy.data.lights.new("Sun", 'SUN')
    ld.energy = 4.0
    ld.angle = math.radians(0.6)
    lo = bpy.data.objects.new("Sun", ld)
    lo.rotation_euler = (-to_sun).to_track_quat('-Z', 'Y').to_euler()
    scene.collection.objects.link(lo)


def add_camera(name, loc, rot=None, look_at=None, lens=24.0):
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    cd.sensor_width = 36.0
    cd.clip_start = 0.05
    cd.clip_end = 3000.0
    co = bpy.data.objects.new(name, cd)
    co.location = loc
    if look_at is not None:
        co.rotation_euler = (Vector(look_at) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    else:
        co.rotation_euler = rot
    bpy.context.scene.collection.objects.link(co)
    return co


def render(cam, path):
    scene = bpy.context.scene
    scene.camera = cam
    scene.render.filepath = path
    t = time.time()
    bpy.ops.render.render(write_still=True)
    return time.time() - t


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    terrain = make_terrain()
    t0 = time.time()
    info = grass.build(terrain_obj=terrain)
    print("[test] build %.1fs" % (time.time() - t0))
    print("[test] instance counts:", info["instance_counts"])
    print("[test] blades ~%.2f M" % (info["blade_count_estimate"] / 1e6))
    for name, blades, faces in info["prototypes"]:
        print("[test]   proto %-16s blades %3d faces %5d" % (name, blades, faces))
    make_world_and_sun()

    # check evaluated instance count
    dg = bpy.context.evaluated_depsgraph_get()
    n_inst = sum(1 for i in dg.object_instances if i.is_instance)
    print("[test] evaluated instances in depsgraph: %d" % n_inst)

    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = SAMPLES
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.use_denoising = True
    scene.cycles.max_bounces = 6
    scene.cycles.transmission_bounces = 6
    scene.render.threads_mode = 'FIXED'
    scene.render.threads = 2
    scene.render.resolution_x, scene.render.resolution_y = RES
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.view_settings.view_transform = 'AgX' if "--agx" in ARGS else 'Standard'

    out = os.path.join(HERE, "renders")
    os.makedirs(out, exist_ok=True)
    cams = {}
    cams["wide"] = add_camera(
        "CamWide", common.CAMERA_LOCATION,
        rot=(math.radians(90.0 + common.CAMERA_PITCH_DEG), 0.0, math.radians(common.CAMERA_YAW_LEFT_DEG)),
        lens=common.CAMERA_LENS_MM)
    cx, cy = -24.0, 16.0
    gz = float(terrain_height(cx, cy))
    cams["close"] = add_camera("CamClose", (cx, cy, gz + 1.05),
                               look_at=(cx - 0.75, cy + 1.25, gz + 0.45), lens=40.0)
    tx, ty = -9.5, 9.0
    gz = float(terrain_height(tx, ty))
    cams["tall"] = add_camera("CamTall", (tx, ty, gz + 1.5),
                              look_at=(tx - 0.3, ty + 1.9, gz + 0.95), lens=35.0)
    for v in VIEWS:
        dt = render(cams[v], os.path.join(out, "test_grass_%s.png" % v))
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0
        print("[test] render %-5s %dx%d %d spp: %.1fs, peak RSS so far %.0f MB" % (
            v, RES[0], RES[1], SAMPLES, dt, rss))


if __name__ == "__main__":
    main()
