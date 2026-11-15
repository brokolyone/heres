"""Stand-alone test of sky.py:  python3 test_sky.py [--no-clouds] [--no-haze] [--out NAME] [--samples N]"""
import os, sys, time, math
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bpy
from mathutils import Vector
import common, sky

args = sys.argv[1:]
def opt(name, default):
    return type(default)(args[args.index(name) + 1]) if name in args else default

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

t0 = time.time()
res = sky.build(clouds="--no-clouds" not in args,
                haze="NONE" if "--no-haze" in args else None)
print("build() %.2fs ->" % (time.time() - t0), {k: (v if not isinstance(v, list) else [o.name for o in v]) for k, v in res.items()})

col = common.get_collection("TestStandIns")

def mat(name, color, rough=0.5, metallic=0.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metallic
    return m

def box(name, lo, hi, m):
    me = bpy.data.meshes.new(name)
    (x0, y0, z0), (x1, y1, z1) = lo, hi
    v = [(x0,y0,z0),(x1,y0,z0),(x1,y1,z0),(x0,y1,z0),(x0,y0,z1),(x1,y0,z1),(x1,y1,z1),(x0,y1,z1)]
    f = [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]
    me.from_pydata(v, [], f); me.materials.append(m)
    o = bpy.data.objects.new(name, me); col.objects.link(o); return o

G = common.GROUND_Z
box("Ground", (-4000, -4000, G - 1), (common.GLASS_X - 0.4, 4000, G), mat("grass", (0.13, 0.30, 0.03), 0.8))
T = common.TREELINE_DISTANCE
box("TreeX", (-T - 40, -600, G), (-T, 1500, G + 16), mat("trees", (0.012, 0.03, 0.012), 0.9))
box("TreeY", (-T - 40, T + 250, G), (common.GLASS_X - 5, T + 290, G + 16), bpy.data.materials["trees"])
box("Floor", (common.GLASS_X, common.CORRIDOR_Y_MIN, -0.1), (common.RIGHT_WALL_X, common.CORRIDOR_Y_MAX, 0.0),
    mat("floor", (0.55, 0.6, 0.6), 0.06))

cam = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera")); col.objects.link(cam)
cam.data.lens = common.CAMERA_LENS_MM; cam.data.clip_end = 20000
cam.location = common.CAMERA_LOCATION
cam.rotation_euler = (math.radians(90 + opt("--pitch", common.CAMERA_PITCH_DEG)), 0, math.radians(common.CAMERA_YAW_LEFT_DEG))
scene.camera = cam

scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = opt("--samples", 48)
scene.cycles.use_denoising = True
scene.render.threads_mode = "FIXED"; scene.render.threads = 2
scene.render.resolution_x, scene.render.resolution_y = 800, 375
scene.render.resolution_percentage = 100
sky.apply_recommended_settings(scene)
scene.view_settings.exposure = opt("--exposure", sky.RECOMMENDED_COLOR["exposure"])
print("view:", scene.view_settings.view_transform, scene.view_settings.look)
scene.render.image_settings.file_format = "PNG"
scene.render.filepath = os.path.join(HERE, "renders", opt("--out", "test_sky") + ".png")
t0 = time.time()
bpy.ops.render.render(write_still=True)
print("RENDER_TIME %.1fs -> %s" % (time.time() - t0, scene.render.filepath))
