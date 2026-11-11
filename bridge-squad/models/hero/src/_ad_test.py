import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hero_common import *
reset()
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.15, location=A["head"])
o = bpy.context.active_object; o.name = "ad.test"
o.data.materials.append(mat("M_skin")); uv_world(o); tag(o, "body", 0, "ad")
print(tris(o))
preview("_ad_test", views=("front34","back34"), res=384)
