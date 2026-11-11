import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hero_common import *
reset()
def sph(c, r, m):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1, location=c, segments=24, ring_count=12)
    o = bpy.context.active_object; o.scale = r; o.data.materials.append(mat(m)); bpy.ops.object.shade_smooth(); return o
def cyl(a, b, r, m):
    d = b - a
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=d.length, location=(a+b)/2, vertices=16)
    o = bpy.context.active_object; o.rotation_euler = d.to_track_quat('Z','Y').to_euler(); o.data.materials.append(mat(m)); return o
def box(c, s, m):
    bpy.ops.mesh.primitive_cube_add(size=1, location=c); o = bpy.context.active_object; o.scale = s
    o.data.materials.append(mat(m)); md = o.modifiers.new("b", "BEVEL"); md.width = 0.02; md.segments = 3; return o
sph(A["head"], A["head_r"], "M_skin")
h = sph(A["helmet"], (0.172,)*3, "M_helmet_blue")
bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.object.mode_set(mode='OBJECT')
import bmesh
bm = bmesh.new(); bm.from_mesh(h.data)
for v in [v for v in bm.verts if v.co.z < -0.1 + (0.3 if v.co.y>0.5 else 0)]: bm.verts.remove(v)
bm.to_mesh(h.data)
box((0,0,0.45), (0.33,0.23,0.30), "M_jacket_blue")
box((0,0.005,0.33), (0.29,0.21,0.05), "M_strap_tan")
box((0,0.0,0.28), (0.27,0.19,0.08), "M_pants_navy")
box((0,0.12,0.47), (0.30,0.04,0.2), "M_vest_tan")
box(A["backpack"], A["backpack_size"], "M_backpack_blue")
for s in "LR":
    hip = A["hip_"+s]
    cyl(hip, A["knee_"+s], 0.06, "M_pants_navy"); cyl(A["knee_"+s], A["ankle_"+s], 0.055, "M_pants_navy")
    box((hip.x, 0.04, 0.06), (0.115, 0.21, 0.12), "M_leather_brown")
    sph(A["shoulder_"+s], (0.075,)*3, "M_jacket_blue")
    cyl(A["shoulder_"+s], A["elbow_"+s], 0.05, "M_jacket_blue"); cyl(A["elbow_"+s], A["wrist_"+s], 0.045, "M_jacket_blue")
    sph(A["hand_"+s], (0.045,)*3, "M_glove")
rx, rz = A["rifle_x"], A["rifle_z"]
box((rx, (0.1+0.68)/2, rz), (0.05, 0.58, 0.07), "M_metal_gun")
box((rx, 0.27, rz-0.07), (0.035, 0.05, 0.12), "M_polymer_gun")
for o in list(bpy.data.objects):
    c = o.location
    tgt = "body"
    if c.z < 0.25 and abs(c.x) > 0.05: tgt = "leg_L" if c.x < 0 else "leg_R"
    tag(o, tgt, 0, "ad")
for o in list(bpy.data.objects):
    apply_all(o); uv_world(o)
    c = o.copy(); c.data = o.data.copy(); bpy.context.scene.collection.objects.link(c)
    md = c.modifiers.new("d","DECIMATE"); md.ratio = 0.25; apply_all(c); c["hero_lod"] = 1; c.name = o.name+".lo"
import os
if os.environ.get("HERO_PARTS_DIR"):
    save_part("body")
else:
    preview("_ad_proxy", views=("back34","front34","side"), res=400)
