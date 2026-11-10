"""Shared helpers for obstacle models (gate, tires, crate, finish).

Geometry is built directly with bmesh (bevels baked in), each part is its own
object; at the end all parts are joined into one mesh, smoothed by angle and
exported as GLB. Then a Cycles preview is rendered from behind-above (~40deg),
the way the player sees the obstacle.
"""
import bpy, bmesh, math, os
from mathutils import Matrix, Vector

MODELS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


# ---------------------------------------------------------------- materials
def _lin(c):
    c = c / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hexcol(h):
    h = h.lstrip('#')
    return tuple(_lin(int(h[i:i + 2], 16)) for i in (0, 2, 4)) + (1.0,)


def mat(name, color, rough=0.5, metal=0.0, emit=None, emit_strength=0.0):
    m = bpy.data.materials.new(name)
    try:
        m.use_nodes = True
    except Exception:
        pass
    nt = m.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    if bsdf is None:
        nt.nodes.clear()
        bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        nt.links.new(bsdf.outputs[0], out.inputs[0])
    col = hexcol(color)
    bsdf.inputs["Base Color"].default_value = col
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    if emit:
        bsdf.inputs["Emission Color"].default_value = hexcol(emit)
        bsdf.inputs["Emission Strength"].default_value = emit_strength
    m.diffuse_color = col
    return m


# ---------------------------------------------------------------- objects
PARTS = []


def from_bm(bm, mats, name="part", smooth=True):
    if not isinstance(mats, (list, tuple)):
        mats = [mats]
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    for f in bm.faces:
        f.smooth = smooth
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for m in mats:
        me.materials.append(m)
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    PARTS.append(ob)
    return ob


def xform(bm, loc=(0, 0, 0), rot=(0, 0, 0), scale=None):
    if scale:
        bmesh.ops.scale(bm, vec=scale, verts=bm.verts)
    R = (Matrix.Rotation(math.radians(rot[2]), 4, 'Z') @
         Matrix.Rotation(math.radians(rot[1]), 4, 'Y') @
         Matrix.Rotation(math.radians(rot[0]), 4, 'X'))
    bmesh.ops.transform(bm, matrix=R, verts=bm.verts)
    bmesh.ops.translate(bm, vec=Vector(loc), verts=bm.verts)


def bevel(bm, amount, segs=1, edges=None):
    if amount <= 0:
        return
    edges = list(bm.edges) if edges is None else edges
    bmesh.ops.bevel(bm, geom=edges, offset=amount, offset_type='OFFSET',
                    segments=segs, profile=0.5, affect='EDGES', clamp_overlap=True)


def box_bm(size, bev=0.0, segs=1):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=size, verts=bm.verts)
    bevel(bm, bev, segs)
    return bm


def box(size, loc, m, bev=0.0, segs=1, rot=(0, 0, 0), name="box", taper=None):
    """taper=(sx, sy): scale of the top face relative to the bottom."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=size, verts=bm.verts)
    if taper:
        for v in bm.verts:
            if v.co.z > 0:
                v.co.x *= taper[0]
                v.co.y *= taper[1]
    bevel(bm, bev, segs)
    xform(bm, loc, rot)
    return from_bm(bm, m, name, smooth=False)


def cyl_bm(r, h, segs=16, r2=None, caps=True):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=caps, cap_tris=False, segments=segs,
                          radius1=r, radius2=r if r2 is None else r2, depth=h)
    return bm


def cyl(r, h, loc, m, segs=16, r2=None, rot=(0, 0, 0), bev=0.0, name="cyl", smooth=True):
    bm = cyl_bm(r, h, segs, r2)
    if bev:
        # bevel only the cap rims
        rim = [e for e in bm.edges if abs(e.verts[0].co.z - e.verts[1].co.z) < 1e-6
               and abs(abs(e.verts[0].co.z) - h / 2) < 1e-6 and
               (e.verts[0].co.xy.length > 1e-4)]
        bevel(bm, bev, 1, rim)
    xform(bm, loc, rot)
    return from_bm(bm, m, name, smooth)


def torus_bm(R, r, nu=16, nv=8, rz=None, phase=0.0):
    rz = r if rz is None else rz
    bm = bmesh.new()
    grid = []
    for i in range(nu):
        a = 2 * math.pi * i / nu + phase
        row = []
        for j in range(nv):
            b = 2 * math.pi * j / nv
            rr = R + r * math.cos(b)
            row.append(bm.verts.new((rr * math.cos(a), rr * math.sin(a), rz * math.sin(b))))
        grid.append(row)
    for i in range(nu):
        for j in range(nv):
            a, b = grid[i][j], grid[(i + 1) % nu][j]
            c, d = grid[(i + 1) % nu][(j + 1) % nv], grid[i][(j + 1) % nv]
            bm.faces.new((a, b, c, d))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def band_bm(r, z0, z1, segs=16, twist=0.0, r_top=None, mat_pattern=(0, 1)):
    """Open ring (outward facing) with per-face alternating material index.
    twist (radians) shifts the top loop -> diagonal hazard stripes."""
    rt = r if r_top is None else r_top
    bm = bmesh.new()
    bot, top = [], []
    for i in range(segs):
        a = 2 * math.pi * i / segs
        bot.append(bm.verts.new((r * math.cos(a), r * math.sin(a), z0)))
        a2 = a + twist
        top.append(bm.verts.new((rt * math.cos(a2), rt * math.sin(a2), z1)))
    for i in range(segs):
        j = (i + 1) % segs
        f = bm.faces.new((bot[i], bot[j], top[j], top[i]))
        f.material_index = mat_pattern[i % len(mat_pattern)]
    return bm


# ---------------------------------------------------------------- finish
def finalize(name, smooth_angle=40.0):
    bpy.ops.object.select_all(action='DESELECT')
    for o in PARTS:
        o.select_set(True)
    bpy.context.view_layer.objects.active = PARTS[0]
    if len(PARTS) > 1:
        bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    ob.name = name
    ob.data.name = name
    try:
        bpy.ops.object.shade_smooth_by_angle(angle=math.radians(smooth_angle))
    except Exception as e:  # older API fallback
        print("smooth_by_angle failed:", e)
    # merge duplicate material slots (same material appended many times)
    me = ob.data
    uniq, remap = [], {}
    for i, m in enumerate(me.materials):
        if m not in uniq:
            uniq.append(m)
        remap[i] = uniq.index(m)
    idx = [remap[p.material_index] for p in me.polygons]
    me.materials.clear()
    for m in uniq:
        me.materials.append(m)
    for p, k in zip(me.polygons, idx):
        p.material_index = k
    return ob


def stats(ob):
    me = ob.data
    tris = sum(len(p.vertices) - 2 for p in me.polygons)
    xs = [v.co.x for v in me.vertices]
    ys = [v.co.y for v in me.vertices]
    zs = [v.co.z for v in me.vertices]
    bb = ((min(xs), max(xs)), (min(ys), max(ys)), (min(zs), max(zs)))
    return tris, bb


def export(ob, name):
    path = os.path.join(MODELS_DIR, name + ".glb")
    bpy.ops.object.select_all(action='DESELECT')
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', export_yup=True,
                              export_apply=True, use_selection=True)
    tris, bb = stats(ob)
    print("=== %s.glb: %d tris; bbox X[%.3f, %.3f] Y[%.3f, %.3f] Z[%.3f, %.3f]" %
          (name, tris, bb[0][0], bb[0][1], bb[1][0], bb[1][1], bb[2][0], bb[2][1]))
    print("    materials:", [m.name for m in ob.data.materials])
    return path


def preview(ob, name, pitch=40.0, yaw=22.0, dist_mul=2.3, road=True, samples=32):
    scene = bpy.context.scene
    tris, bb = stats(ob)
    cx = (bb[0][0] + bb[0][1]) / 2
    cy = (bb[1][0] + bb[1][1]) / 2
    cz = (bb[2][0] + bb[2][1]) / 2
    size = max(bb[0][1] - bb[0][0], bb[1][1] - bb[1][0], bb[2][1] - bb[2][0])
    # ground: bridge deck
    road_m = mat("_road", "#7d8494", 0.85)
    edge_m = mat("_edge", "#e9e4d6", 0.6)
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0, -0.001))
    g = bpy.context.active_object
    g.scale = (10, 60, 1)
    g.data.materials.append(road_m)
    if road:
        for sx in (-1, 1):
            bpy.ops.mesh.primitive_cube_add(size=1, location=(sx * 5.1, 0, 0.1))
            c = bpy.context.active_object
            c.scale = (0.2, 60, 0.2)
            c.data.materials.append(edge_m)
    # water around
    water = mat("_water", "#3d8fc4", 0.3)
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0, -1.5))
    w = bpy.context.active_object
    w.scale = (200, 200, 1)
    w.data.materials.append(water)
    # camera
    d = size * dist_mul
    p, y = math.radians(pitch), math.radians(yaw)
    target = Vector((cx, cy, cz * 0.8))
    cam_pos = target + Vector((-math.sin(y) * d * math.cos(p),
                               -math.cos(y) * d * math.cos(p),
                               d * math.sin(p)))
    cam_data = bpy.data.cameras.new("cam")
    cam_data.lens = 50
    cam = bpy.data.objects.new("cam", cam_data)
    scene.collection.objects.link(cam)
    cam.location = cam_pos
    direction = target - cam_pos
    cam.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
    scene.camera = cam
    # lights
    sun_d = bpy.data.lights.new("sun", 'SUN')
    sun_d.energy = 3.5
    sun_d.angle = math.radians(8)
    sun = bpy.data.objects.new("sun", sun_d)
    scene.collection.objects.link(sun)
    sun.rotation_euler = (math.radians(50), math.radians(-15), math.radians(-35))
    world = bpy.data.worlds.new("w")
    scene.world = world
    try:
        world.use_nodes = True
    except Exception:
        pass
    bg = world.node_tree.nodes.get("Background")
    if bg is None:
        bg = world.node_tree.nodes.new("ShaderNodeBackground")
        out = world.node_tree.nodes.new("ShaderNodeOutputWorld")
        world.node_tree.links.new(bg.outputs[0], out.inputs[0])
    bg.inputs[0].default_value = hexcol("#bfe0f5")
    bg.inputs[1].default_value = 1.0
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = samples
    scene.cycles.use_denoising = False
    scene.render.resolution_x = 768
    scene.render.resolution_y = 768
    scene.render.resolution_percentage = 100
    try:
        scene.view_settings.view_transform = 'Standard'
    except Exception:
        pass
    out = os.path.join(MODELS_DIR, "previews", name + ".png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    scene.render.filepath = out
    bpy.ops.render.render(write_still=True)
    print("preview:", out)
