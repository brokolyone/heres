"""Render final previews from the exported GLBs (owner: Art Director).  python3 src/final_previews.py"""
import sys, os, math, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hero_common import *


def load(path):
    reset()
    bpy.ops.import_scene.gltf(filepath=path)
    objs = [o for o in bpy.data.objects if o.type == "MESH"]
    for o in objs:
        o["hero_lod"] = 0
    return objs


def main(only_crowd=False):
    hi = os.path.join(HERO_DIR, "hero_hi.glb"); lo = os.path.join(HERO_DIR, "hero_lo.glb")
    if not only_crowd:
        load(hi)
        preview("final_hi", views=("back34", "front34", "front", "face"), res=1024, samples=64)
    if not only_crowd:
        load(lo)
        preview("final_lo", views=("back34", "front34"), res=768, samples=48)
    # crowd shot: ~60 lo soldiers with swinging legs, seen from the game camera
    objs = load(lo)
    base = {o.name: o for o in objs}
    home = {o.name: o.location.copy() for o in objs}
    random.seed(3)
    for i in range(60):
        x = (i % 10 - 4.5) * 0.5 + random.uniform(-0.06, 0.06)
        y = (i // 10) * 0.5 + random.uniform(-0.08, 0.08)
        ph = random.uniform(0, 6.28)
        for nm, o in base.items():
            c = o if i == 0 else o.copy()
            if i:
                bpy.context.scene.collection.objects.link(c)
            c.location = home[nm] + V((x, y, 0))
            if nm.startswith("leg"):
                c.rotation_mode = "XYZ"
                c.rotation_euler.x = math.sin(ph) * 0.5 * (1 if nm == "leg_L" else -1)
    preview("final_crowd", views=((V((0, -4.5, 5.0)), V((0, 1.5, 0.3))),), res=1024, samples=32, lens=45)


if __name__ == "__main__":
    main("--crowd" in sys.argv)
