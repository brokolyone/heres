"""Bake atlases + export hero_hi.glb / hero_lo.glb (owner: Art Director).

    python3 src/export_hero.py [hi|lo|both] [--fast]

hi: LOD0 parts, library materials baked into one 2048 atlas set (base colour w/ baked AO, normal, rough/metal).
lo: LOD1 parts, 1024 atlas baked from the hi model (selected->active), + COLOR_0 vertex colours.
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hero_common import *
import assemble as asm
import numpy as np

OUT_DIR = os.environ.get("HERO_OUT_DIR") or HERO_DIR
BAKE_DIR = os.path.join(OUT_DIR, "textures_baked")
os.makedirs(BAKE_DIR, exist_ok=True)
FAST = "--fast" in sys.argv
AA = 4 if FAST else 16  # samples for colour/normal/rough bakes = anti-aliasing of texture detail

# texel-density boost per dominant material of a part object (face gets more pixels)
BOOST = {"M_skin": 2.6, "M_eye_white": 3.0, "M_eye_iris": 3.0, "M_eye_pupil": 3.0, "M_mouth": 3.0, "M_hair": 2.6,
         "M_helmet_blue": 1.5, "M_emblem": 2.0, "M_goggle_lens": 2.0, "M_glove": 1.6,
         "M_metal_gun": 1.4, "M_polymer_gun": 1.4, "M_gun_accent": 1.4, "M_metal_bright": 1.4,
         "M_rubber_dark": 0.7}


def dominant_material(o):
    cnt = {}
    for p in o.data.polygons:
        if p.material_index < len(o.material_slots) and o.material_slots[p.material_index].material:
            n = o.material_slots[p.material_index].material.name
            cnt[n] = cnt.get(n, 0) + p.area
    return max(cnt, key=cnt.get) if cnt else None


def add_atlas_uv(o, boost=True):
    me = o.data
    if not me.uv_layers:
        uv_world(o)
    src = me.uv_layers.get("UVMap") or me.uv_layers[0]
    at = me.uv_layers.get("Atlas") or me.uv_layers.new(name="Atlas")
    data = np.zeros(len(me.loops) * 2, dtype=np.float32)
    src.data.foreach_get("uv", data)
    k = 1.0
    if boost:
        n = o.name.lower()
        k = BOOST.get(dominant_material(o), 1.0)
        if any(s in n for s in ("head", "face", "eye", "ear", "nose", "brow")):
            k = max(k, 2.6)
    at.data.foreach_set("uv", data * k)


def pack_atlas(objs, margin=0.004):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
        o.data.uv_layers.active = o.data.uv_layers["Atlas"]
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.select_all(action="SELECT")
    kw = dict(rotate=True, margin=margin)
    try:
        bpy.ops.uv.pack_islands(shape_method="CONCAVE", **kw)
    except TypeError:
        bpy.ops.uv.pack_islands(**kw)
    bpy.ops.object.mode_set(mode="OBJECT")


def joined_copy(objs, name):
    bpy.ops.object.select_all(action="DESELECT")
    cps = []
    for o in objs:
        c = o.copy(); c.data = o.data.copy(); bpy.context.scene.collection.objects.link(c)
        c.matrix_world = o.matrix_world.copy()
        cps.append(c)
    for c in cps:
        c.select_set(True)
    bpy.context.view_layer.objects.active = cps[0]
    bpy.ops.object.join()
    j = bpy.context.view_layer.objects.active
    j.name = name
    return j


def new_image(name, size, non_color=False, color=(0.5, 0.5, 0.5, 1.0)):
    if name in bpy.data.images:
        bpy.data.images.remove(bpy.data.images[name])
    im = bpy.data.images.new(name, size, size, alpha=False, float_buffer=False)
    im.generated_color = color
    if non_color:
        im.colorspace_settings.name = "Non-Color"
    return im


def set_bake_target(objs, image):
    for o in objs:
        for s in o.material_slots:
            m = s.material
            if not m:
                continue
            m.use_nodes = True
            nt = m.node_tree
            n = nt.nodes.get("_bake") or nt.nodes.new("ShaderNodeTexImage")
            n.name = "_bake"; n.image = image
            for x in nt.nodes:
                x.select = False
            n.select = True
            nt.nodes.active = n
        uvs = o.data.uv_layers
        uvs.active = uvs["Atlas"]
        if "UVMap" in uvs:
            uvs["UVMap"].active_render = True


def setup_cycles(samples):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.render.bake.margin = 6
    if sc.world is None:
        sc.world = bpy.data.worlds.new("bake_world")
    sc.world.light_settings.distance = 0.09  # AO distance at character scale (default 10 m = everything dark)
    try:
        sc.render.bake.margin_type = "EXTEND"
    except Exception:
        pass


def bake(objs, type_, image, active=None, pass_filter=None, normal_space="TANGENT", samples=4, **sel):
    setup_cycles(samples)
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    if active is not None:
        active.select_set(True)
        bpy.context.view_layer.objects.active = active
        set_bake_target([active], image)
    else:
        bpy.context.view_layer.objects.active = objs[0]
        set_bake_target(objs, image)
    kw = dict(type=type_, margin=6, use_clear=True)
    if pass_filter:
        kw["pass_filter"] = pass_filter
    if type_ == "NORMAL":
        kw["normal_space"] = normal_space
    if active is not None:
        kw.update(use_selected_to_active=True, cage_extrusion=sel.get("cage", 0.03),
                  max_ray_distance=sel.get("ray", 0.12))
    t = time.time()
    bpy.ops.object.bake(**kw)
    print(f"  baked {type_} -> {image.name} in {time.time() - t:.1f}s")


def wire_metal_to_emission(objs):
    for o in objs:
        for s in o.material_slots:
            if not s.material or not s.material.node_tree:
                continue
            m = s.material = s.material.copy()  # don't break the shared library material
            nt = m.node_tree
            out = next((n for n in nt.nodes if n.type == "OUTPUT_MATERIAL" and n.is_active_output), None) or \
                next((n for n in nt.nodes if n.type == "OUTPUT_MATERIAL"), None)
            if out is None:
                continue
            emi = nt.nodes.new("ShaderNodeEmission"); emi.inputs["Strength"].default_value = 1.0
            p = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
            if p is not None and p.inputs["Metallic"].is_linked:
                nt.links.new(p.inputs["Metallic"].links[0].from_socket, emi.inputs["Color"])
            else:
                v = p.inputs["Metallic"].default_value if p is not None else 0.0
                emi.inputs["Color"].default_value = (v, v, v, 1)
            nt.links.new(emi.outputs[0], out.inputs["Surface"])


def img_np(im):
    a = np.empty(im.size[0] * im.size[1] * 4, dtype=np.float32)
    im.pixels.foreach_get(a)
    return a.reshape(im.size[1], im.size[0], 4)


def np_img(name, arr, non_color=False):
    h, w = arr.shape[:2]
    im = new_image(name, w, non_color)
    im.pixels.foreach_set(arr.astype(np.float32).ravel())
    return im


def save_jpg(im, path, quality=92):
    sc = bpy.context.scene
    s = sc.render.image_settings
    s.file_format = "JPEG"; s.quality = quality; s.color_mode = "RGB"
    im.save_render(path, scene=sc)
    im2 = bpy.data.images.load(path)
    if im.colorspace_settings.name == "Non-Color":
        im2.colorspace_settings.name = "Non-Color"
    return im2


def save_png(im, path):
    sc = bpy.context.scene
    s = sc.render.image_settings
    s.file_format = "PNG"; s.color_mode = "RGB"; s.compression = 90
    im.save_render(path, scene=sc)
    im2 = bpy.data.images.load(path)
    if im.colorspace_settings.name == "Non-Color":
        im2.colorspace_settings.name = "Non-Color"
    return im2


def final_material(name, base, normal, orm, emissive=None, normal_strength=1.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    m.use_backface_culling = True  # glTF doubleSided=false (all parts must be closed / have thickness)
    nt = m.node_tree
    p = nt.nodes["Principled BSDF"]
    uv = nt.nodes.new("ShaderNodeUVMap"); uv.uv_map = "UVMap"
    tb = nt.nodes.new("ShaderNodeTexImage"); tb.image = base
    nt.links.new(uv.outputs[0], tb.inputs[0]); nt.links.new(tb.outputs[0], p.inputs["Base Color"])
    if normal is not None:
        tn = nt.nodes.new("ShaderNodeTexImage"); tn.image = normal
        nm = nt.nodes.new("ShaderNodeNormalMap"); nm.inputs["Strength"].default_value = normal_strength
        nt.links.new(uv.outputs[0], tn.inputs[0]); nt.links.new(tn.outputs[0], nm.inputs["Color"])
        nt.links.new(nm.outputs[0], p.inputs["Normal"])
    if orm is not None:
        to = nt.nodes.new("ShaderNodeTexImage"); to.image = orm
        sp = nt.nodes.new("ShaderNodeSeparateColor")
        nt.links.new(uv.outputs[0], to.inputs[0]); nt.links.new(to.outputs[0], sp.inputs[0])
        nt.links.new(sp.outputs[1], p.inputs["Roughness"]); nt.links.new(sp.outputs[2], p.inputs["Metallic"])
    else:
        p.inputs["Roughness"].default_value = 0.6
    if emissive is not None:
        te = nt.nodes.new("ShaderNodeTexImage"); te.image = emissive
        nt.links.new(uv.outputs[0], te.inputs[0]); nt.links.new(te.outputs[0], p.inputs["Emission Color"])
        p.inputs["Emission Strength"].default_value = 1.0
    return m


def finalize_objects(objs, material):
    for o in objs:
        me = o.data
        if "UVMap" in me.uv_layers and "Atlas" in me.uv_layers:
            me.uv_layers.remove(me.uv_layers["UVMap"])
        me.uv_layers["Atlas"].name = "UVMap"
        me.materials.clear()
        me.materials.append(material)
        me.name = o.name
        for k in list(o.keys()):
            del o[k]


def export(objs, path):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    vc = "ACTIVE" if any(o.data.color_attributes for o in objs) else "NONE"
    bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", export_yup=True, export_apply=True,
                              use_selection=True, export_image_format="AUTO", export_vertex_color=vc,
                              export_all_vertex_colors=False, export_materials="EXPORT")
    print("exported", path, os.path.getsize(path) // 1024, "KB")


def build_hi(size=2048):
    print("== HI ==")
    parts = asm.assemble(0, library=True)
    objs = [parts[k] for k in ("body", "leg_L", "leg_R") if k in parts]
    # atlas UVs are made on the joined final objects using each original part's boost: re-derive per object
    for o in objs:
        add_atlas_uv_by_material(o)
    pack_atlas(objs)
    tmp = joined_copy(objs, "_bake_hi")
    for o in objs:  # originals coincide with the bake copy -> would self-occlude the AO
        bpy.context.scene.collection.objects.unlink(o)
    samples_ao = 8 if FAST else 64
    im_col = new_image("hi_col", size); bake([tmp], "DIFFUSE", im_col, pass_filter={"COLOR"}, samples=AA)
    im_nrm = new_image("hi_nrm", size, True, (0.5, 0.5, 1, 1)); bake([tmp], "NORMAL", im_nrm, samples=AA)
    im_rgh = new_image("hi_rgh", size, True); bake([tmp], "ROUGHNESS", im_rgh, samples=AA)
    im_ao = new_image("hi_ao", size, True, (1, 1, 1, 1)); bake([tmp], "AO", im_ao, samples=samples_ao)
    im_emi = new_image("hi_emi", size, False, (0, 0, 0, 1)); bake([tmp], "EMIT", im_emi, samples=AA)
    wire_metal_to_emission([tmp])
    im_met = new_image("hi_met", size, True, (0, 0, 0, 1)); bake([tmp], "EMIT", im_met, samples=AA)
    bpy.data.objects.remove(tmp, do_unlink=True)
    for o in objs:
        bpy.context.scene.collection.objects.link(o)
    col = img_np(im_col); ao = blur(img_np(im_ao)[..., :1])
    aof = 1.0 - 0.55 * (1.0 - np.clip(ao, 0, 1))  # soft AO multiply
    col[..., :3] *= aof
    orm = np.ones_like(col)
    orm[..., 0] = ao[..., 0]; orm[..., 1] = img_np(im_rgh)[..., 0]; orm[..., 2] = img_np(im_met)[..., 0]
    base = save_jpg(np_img("hero_hi_basecolor", col), os.path.join(BAKE_DIR, "hero_hi_basecolor.jpg"))
    nrm = save_png(im_nrm, os.path.join(BAKE_DIR, "hero_hi_normal.png"))
    ormi = save_jpg(np_img("hero_hi_orm", orm, True), os.path.join(BAKE_DIR, "hero_hi_orm.jpg"))
    emi = img_np(im_emi)
    emi_img = None
    if emi[..., :3].max() > 0.02:
        emi_img = save_jpg(np_img("hero_hi_emissive", emi), os.path.join(BAKE_DIR, "hero_hi_emissive.jpg"))
    return parts, objs, (base, nrm, ormi, emi_img)


def blur(a, it=2):
    for _ in range(it):
        b = a.copy()
        b[1:-1, 1:-1] = (a[1:-1, 1:-1] * 4 + a[:-2, 1:-1] + a[2:, 1:-1] + a[1:-1, :-2] + a[1:-1, 2:]) / 8
        a = b
    return a


def add_atlas_uv_by_material(o):
    """Atlas UV with per-face boost by face material (faces of an island share one material in practice)."""
    me = o.data
    src = me.uv_layers.get("UVMap") or me.uv_layers[0]
    at = me.uv_layers.get("Atlas") or me.uv_layers.new(name="Atlas")
    n = len(me.loops)
    data = np.zeros(n * 2, dtype=np.float32); src.data.foreach_get("uv", data)
    data = data.reshape(-1, 2)
    names = [s.material.name if s.material else "" for s in o.material_slots]
    for p in me.polygons:
        k = BOOST.get(names[p.material_index] if p.material_index < len(names) else "", 1.0)
        if k != 1.0:
            data[p.loop_start:p.loop_start + p.loop_total] *= k
    at.data.foreach_set("uv", data.ravel())


def build_lo(hi_objs, size=1024):
    print("== LO ==")
    for o in hi_objs:
        o.name = "hi_" + o.name.replace("_src_", ""); o.data.name = o.name
    parts = asm.assemble(1, library=True)
    objs = [parts[k] for k in ("body", "leg_L", "leg_R") if k in parts]
    for o in objs:
        add_atlas_uv_by_material(o)
    pack_atlas(objs, margin=0.006)
    tmp = joined_copy(objs, "_bake_lo")
    for o in objs:
        bpy.context.scene.collection.objects.unlink(o)
    # 1) hi -> lo (selected to active): carries face, emblems, straps, seams from the hero model
    im_col = new_image("lo_col", size)
    bake(hi_objs, "DIFFUSE", im_col, active=tmp, pass_filter={"COLOR"}, samples=AA)
    im_nrm = new_image("lo_nrm", size, True, (0.5, 0.5, 1, 1))
    bake(hi_objs, "NORMAL", im_nrm, active=tmp, samples=AA)
    im_rgh = new_image("lo_rgh", size, True)
    bake(hi_objs, "ROUGHNESS", im_rgh, active=tmp, samples=AA)
    # 2) lo's own library materials as fallback where the hi->lo rays missed; + self AO (hi unlinked)
    for o in hi_objs:
        bpy.context.scene.collection.objects.unlink(o)
    im_cs = new_image("lo_col_self", size)
    bake([tmp], "DIFFUSE", im_cs, pass_filter={"COLOR"}, samples=AA)
    im_rs = new_image("lo_rgh_self", size, True)
    bake([tmp], "ROUGHNESS", im_rs, samples=AA)
    im_ao = new_image("lo_ao", size, True, (1, 1, 1, 1))
    bake([tmp], "AO", im_ao, samples=8 if FAST else 48)
    for o in hi_objs:
        bpy.context.scene.collection.objects.link(o)
    bpy.data.objects.remove(tmp, do_unlink=True)
    for o in objs:
        bpy.context.scene.collection.objects.link(o)
    col = img_np(im_col); cs = img_np(im_cs); nrm_a = img_np(im_nrm); rg = img_np(im_rgh); rs = img_np(im_rs)
    miss = col[..., :3].max(-1) < 0.006
    print(f"  hi->lo misses: {miss.mean() * 100:.1f}% of pixels -> filled from lo materials")
    col[miss] = cs[miss]; rg[miss] = rs[miss]; nrm_a[miss] = (0.5, 0.5, 1.0, 1.0)
    # hi->lo normals are wild where hi and lo shapes differ (separate straps/pouches): keep only gentle
    # deviations, fade strong ones to flat, and soften overall
    t = nrm_a[..., :3] * 2 - 1
    w = np.clip((t[..., 2:3] - 0.6) / 0.3, 0, 1) * 0.75
    t = t * w + np.array([0, 0, 1.0]) * (1 - w)
    t /= np.linalg.norm(t, axis=-1, keepdims=True) + 1e-6
    nrm_a[..., :3] = t * 0.5 + 0.5
    im_col = np_img("lo_col_merged", col)
    im_rgh = np_img("lo_rgh_merged", rg, True)
    im_nrm = np_img("lo_nrm_merged", nrm_a, True)
    col = img_np(im_col); ao = blur(img_np(im_ao)[..., :1])
    col[..., :3] *= 1.0 - 0.5 * (1.0 - np.clip(ao, 0, 1))
    orm = np.ones_like(col); orm[..., 0] = ao[..., 0]; orm[..., 1] = img_np(im_rgh)[..., 0]; orm[..., 2] = 0.0
    base = save_jpg(np_img("hero_lo_basecolor", col), os.path.join(BAKE_DIR, "hero_lo_basecolor.jpg"))
    nrm = save_png(im_nrm, os.path.join(BAKE_DIR, "hero_lo_normal.png"))
    ormi = save_jpg(np_img("hero_lo_orm", orm, True), os.path.join(BAKE_DIR, "hero_lo_orm.jpg"))
    # vertex colours (game crowd shader multiplies COLOR_0)
    cpix = col
    H, W = cpix.shape[:2]
    for o in objs:
        me = o.data
        uv = np.zeros(len(me.loops) * 2, dtype=np.float32); me.uv_layers["Atlas"].data.foreach_get("uv", uv)
        uv = uv.reshape(-1, 2)
        out = np.ones((len(me.loops), 4), dtype=np.float32)
        for p in me.polygons:
            sl = slice(p.loop_start, p.loop_start + p.loop_total)
            c = uv[sl].mean(axis=0)
            pts = uv[sl] * 0.6 + c * 0.4
            xs = np.clip((pts[:, 0] * W).astype(int), 0, W - 1); ys = np.clip((pts[:, 1] * H).astype(int), 0, H - 1)
            out[sl, :3] = cpix[ys, xs, :3]
        ca = me.color_attributes.new("Color", "BYTE_COLOR", "CORNER")
        ca.data.foreach_set("color", out.ravel())  # linear values; byte colour stores sRGB-encoded internally
        me.color_attributes.active_color = ca
    return parts, objs, (base, nrm, ormi)


def remove_objs(objs):
    for o in objs:
        me = o.data
        bpy.data.objects.remove(o, do_unlink=True)
        if me is not None and me.users == 0:
            bpy.data.meshes.remove(me)


def check_glb(path, views, prefix, res=640):
    reset()
    bpy.ops.import_scene.gltf(filepath=path)
    objs = [o for o in bpy.data.objects if o.type == "MESH"]
    info = []
    for o in objs:
        info.append((o.name, tris(o), tuple(round(v, 3) for v in o.location), tuple(round(v, 3) for v in o.dimensions)))
    print("GLB", path, info, "TOTAL", sum(i[1] for i in info))
    for o in objs:
        o["hero_lod"] = 0
    mn = min((o.matrix_world @ V(c)).z for o in objs for c in o.bound_box)
    mx = max((o.matrix_world @ V(c)).z for o in objs for c in o.bound_box)
    print("height range", round(mn, 4), round(mx, 4))
    if views:
        preview(prefix, views=views, res=res, samples=32)
    return info


if __name__ == "__main__":
    which = next((a for a in sys.argv[1:] if a in ("hi", "lo", "both")), "both")
    reset()
    hi_parts, hi_objs, hi_imgs = build_hi(1024 if FAST else 2048)
    if which in ("hi", "both"):
        # export hi with a copy so the original library-material hi stays for the lo bake
        cps = []
        for o in hi_objs:
            c = o.copy(); c.data = o.data.copy(); bpy.context.scene.collection.objects.link(c); cps.append(c)
        m = final_material("M_hero_hi", *hi_imgs)
        finalize_objects(cps, m)
        for o, src in zip(cps, hi_objs):
            nm = src.name; src.name = "_src_" + nm; src.data.name = "_src_" + nm; o.name = nm; o.data.name = nm
        export(cps, os.path.join(OUT_DIR, "hero_hi.glb"))
        remove_objs(cps)
    if which in ("lo", "both"):
        lo_parts, lo_objs, lo_imgs = build_lo(hi_objs, 512 if FAST else 1024)
        remove_objs(hi_objs)
        m = final_material("M_hero_lo", *lo_imgs)
        finalize_objects(lo_objs, m)
        export(lo_objs, os.path.join(OUT_DIR, "hero_lo.glb"))
    if "--check" in sys.argv:
        if which in ("hi", "both"):
            check_glb(os.path.join(OUT_DIR, "hero_hi.glb"), ("back34", "front34", "face"), "glb_hi")
        if which in ("lo", "both"):
            check_glb(os.path.join(OUT_DIR, "hero_lo.glb"), ("back34", "front34"), "glb_lo")
