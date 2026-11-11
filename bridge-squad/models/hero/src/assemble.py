"""Assemble the hero from parts/*.blend (owner: Art Director).

    python3 src/assemble.py [lod] [views...]      -> previews/asm_lod<lod>_<view>.png
As a module: assemble(lod, library=True) -> {"body": obj, "leg_L": obj, "leg_R": obj}
"""
import sys, os, re, glob, importlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hero_common import *

PART_FILES = ["body", "uniform", "helmet_weapon"]


def load_parts(lod=None):
    objs = []
    for nm in PART_FILES:
        p = os.path.join(PARTS_DIR, nm + ".blend")
        if not os.path.exists(p):
            print("missing part file", p)
            continue
        with bpy.data.libraries.load(p, link=False) as (src, dst):
            dst.objects = list(src.objects)
        for o in dst.objects:
            if o is None or o.type != "MESH":
                continue
            if lod is not None and int(o.get("hero_lod", 0)) != lod:
                bpy.data.objects.remove(o, do_unlink=True)
                continue
            bpy.context.scene.collection.objects.link(o)
            objs.append(o)
    # merge duplicated placeholder materials (M_skin.001 -> M_skin)
    for o in objs:
        for s in o.material_slots:
            if s.material:
                base = re.sub(r"\.\d+$", "", s.material.name)
                if base != s.material.name:
                    if base in bpy.data.materials:
                        s.material = bpy.data.materials[base]
                    else:
                        s.material.name = base
    return objs


def apply_library(objs):
    try:
        import materials
        importlib.reload(materials)
        materials.apply_library(objs)
        print("material library applied")
        return True
    except Exception as e:
        import traceback; traceback.print_exc()
        print("material library not available -> placeholders", e)
        return False


def join(objs, name):
    if not objs:
        return None
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    if len(objs) > 1:
        bpy.ops.object.join()
    o = bpy.context.view_layer.objects.active
    o.name = name; o.data.name = name
    return o


def assemble(lod=0, library=True):
    objs = load_parts(lod)
    if library:
        apply_library(objs)
    out = {}
    groups = {t: [o for o in objs if o.get("hero_target", "body") == t] for t in ("body", "leg_L", "leg_R")}
    for tgt in ("body", "leg_L", "leg_R"):
        o = join(groups[tgt], tgt)
        if o is None:
            continue
        if tgt != "body":
            hip = A["hip_L"] if tgt == "leg_L" else A["hip_R"]
            o.data.transform(Matrix.Translation(-hip))
            o.location = hip
        o["hero_lod"] = lod
        out[tgt] = o
    return out


if __name__ == "__main__":
    args = [a for a in sys.argv[sys.argv.index("--") + 1:]] if "--" in sys.argv else sys.argv[1:]
    lod = int(args[0]) if args else 0
    views = tuple(args[1:]) or ("back34", "front34", "side", "face")
    reset()
    parts = assemble(lod)
    for k, o in parts.items():
        print(k, tris(o), "tris", [round(v, 3) for v in o.dimensions])
    print("TOTAL", sum(tris(o) for o in parts.values()))
    preview(f"asm_lod{lod}", views=views, res=640, samples=24)
