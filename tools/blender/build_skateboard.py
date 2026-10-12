"""Model a street skateboard (popsicle deck with kicks and concave, trucks, wheels).

    blender -b --factory-startup --python tools/blender/build_skateboard.py -- art/skateboard

Reads grip.png / graphic.png / ply.png from that folder (make_skate_textures.py)
and writes skateboard.blend there. Units are metres; +X is the nose.
"""
import math
import os
import sys

import bmesh
import bpy

ART = os.path.abspath(sys.argv[sys.argv.index("--") + 1])

LENGTH, WIDTH, THICK = 0.80, 0.205, 0.012
KICK_START, KICK_RISE = 0.225, 0.062
CONCAVE = 0.006
TRUCK_X = 0.185
WHEEL_R, WHEEL_W = 0.0265, 0.034
AXLE_Z = -0.052


def image_material(name, image, roughness=0.8):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(os.path.join(ART, image))
    bsdf = nt.nodes["Principled BSDF"]
    bsdf.inputs["Roughness"].default_value = roughness
    nt.links.new(tex.outputs[0], bsdf.inputs["Base Color"])
    return mat


def color_material(name, rgb, roughness=0.5, metallic=0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*rgb, 1)
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    return mat


def deck_height(x, y):
    ax = abs(x)
    kick = KICK_RISE * ((ax - KICK_START) / (LENGTH / 2 - KICK_START)) ** 1.7 if ax > KICK_START else 0.0
    return kick + CONCAVE * (2 * y / WIDTH) ** 2


def half_width(x):
    """Popsicle outline: straight sides, rounded (super-elliptic) nose and tail."""
    r = WIDTH / 2
    ex = abs(x) - (LENGTH / 2 - r)
    if ex <= 0:
        return r
    return r * max(0.0, 1 - (ex / r) ** 2.4) ** (1 / 2.4)


def build_deck(mats):
    nx, ny = 96, 14
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    grid = {}
    for side, dz in (("top", 0.0), ("bot", -THICK)):
        for i in range(nx + 1):
            x = -LENGTH / 2 + LENGTH * i / nx
            # keep a sliver of width at the very tip so faces don't degenerate
            hw = max(half_width(x), 0.012)
            for j in range(ny + 1):
                y = -hw + 2 * hw * j / ny
                grid[side, i, j] = bm.verts.new((x, y, deck_height(x, y) + dz))

    def face(vs, mat, uvs):
        f = bm.faces.new(vs)
        f.material_index = mat
        for loop, t in zip(f.loops, uvs):
            loop[uv].uv = t

    def plan_uv(v):
        return ((v.co.x + LENGTH / 2) / LENGTH, (v.co.y + WIDTH / 2) / WIDTH)

    for i in range(nx):
        for j in range(ny):
            t = [grid["top", i, j], grid["top", i + 1, j], grid["top", i + 1, j + 1], grid["top", i, j + 1]]
            face(t, 0, [plan_uv(v) for v in t])
            b = [grid["bot", i, j + 1], grid["bot", i + 1, j + 1], grid["bot", i + 1, j], grid["bot", i, j]]
            face(b, 1, [plan_uv(v) for v in b])

    # plywood rim: walk the outline (j=0 edge forward, nose, j=ny edge back, tail)
    ring = [(i, 0) for i in range(nx + 1)] + [(nx, j) for j in range(1, ny + 1)] \
        + [(i, ny) for i in range(nx - 1, -1, -1)] + [(0, j) for j in range(ny - 1, 0, -1)]
    for k in range(len(ring)):
        a, b = ring[k], ring[(k + 1) % len(ring)]
        u0, u1 = k / len(ring) * 8, (k + 1) / len(ring) * 8
        face([grid["top", a[0], a[1]], grid["bot", a[0], a[1]], grid["bot", b[0], b[1]], grid["top", b[0], b[1]]],
             2, [(u0, 1), (u0, 0), (u1, 0), (u1, 1)])

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new("deck")
    bm.to_mesh(me)
    for m in mats:
        me.materials.append(m)
    obj = bpy.data.objects.new("deck", me)
    bpy.context.scene.collection.objects.link(obj)


def add(prim, name, mat, loc, rot=(0, 0, 0), scale=(1, 1, 1), bevel=0.0, **kw):
    getattr(bpy.ops.mesh, prim)(location=loc, rotation=rot, **kw)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = scale
    obj.data.materials.append(mat)
    if bevel:
        mod = obj.modifiers.new("bevel", "BEVEL")
        mod.width = bevel
        mod.segments = 2
    return obj


def build_truck(x, metal, dark, bushing, wheel_mat, bearing):
    under = deck_height(x, 0) - THICK
    s = 1 if x > 0 else -1
    # baseplate with four bolt heads
    add("primitive_cube_add", "baseplate", metal, (x, 0, under - 0.004), scale=(0.032, 0.03, 0.004), bevel=0.002)
    for bx in (-0.02, 0.02):
        for by in (-0.018, 0.018):
            add("primitive_cylinder_add", "bolt", dark, (x + bx, by, under + 0.0015), radius=0.0035, depth=0.003, vertices=10)
    # kingpin, bushings and pivot
    add("primitive_cylinder_add", "kingpin", dark, (x - s * 0.012, 0, under - 0.02), rot=(0, s * 0.6, 0),
        radius=0.0045, depth=0.04, vertices=12)
    add("primitive_cylinder_add", "bushing", bushing, (x - s * 0.012, 0, under - 0.024), rot=(0, s * 0.6, 0),
        radius=0.011, depth=0.016, vertices=16)
    # hanger: tapered body + axle
    hanger = add("primitive_cube_add", "hanger", metal, (x, 0, AXLE_Z + 0.008), scale=(0.014, 0.07, 0.014), bevel=0.004)
    for v in hanger.data.vertices:
        if v.co.z > 0:
            v.co.y *= 0.55
    add("primitive_cylinder_add", "axle", dark, (x, 0, AXLE_Z), rot=(math.pi / 2, 0, 0),
        radius=0.0035, depth=WIDTH + 0.01, vertices=10)
    for side in (-1, 1):
        wy = side * (WIDTH / 2 - WHEEL_W / 2 + 0.006)
        add("primitive_cylinder_add", "wheel", wheel_mat, (x, wy, AXLE_Z), rot=(math.pi / 2, 0, 0),
            radius=WHEEL_R, depth=WHEEL_W, vertices=28, bevel=0.007)
        add("primitive_cylinder_add", "bearing", bearing, (x, wy + side * (WHEEL_W / 2 - 0.0025), AXLE_Z),
            rot=(math.pi / 2, 0, 0), radius=0.011, depth=0.006, vertices=16)
        add("primitive_cylinder_add", "nut", dark, (x, wy + side * (WHEEL_W / 2 + 0.002), AXLE_Z),
            rot=(math.pi / 2, 0, 0), radius=0.005, depth=0.005, vertices=6)


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    grip = image_material("grip", "grip.png", 0.95)
    graphic = image_material("graphic", "graphic.png", 0.4)
    ply = image_material("ply", "ply.png", 0.7)
    metal = color_material("truck_metal", (0.62, 0.63, 0.66), 0.35)
    dark = color_material("hardware", (0.08, 0.08, 0.09), 0.4)
    bushing = color_material("bushing", (0.95, 0.75, 0.1), 0.6)
    wheel = color_material("urethane", (0.1, 0.75, 0.75), 0.55)
    bearing = color_material("bearing", (0.18, 0.18, 0.2), 0.3)

    build_deck([grip, graphic, ply])
    for x in (TRUCK_X, -TRUCK_X):
        build_truck(x, metal, dark, bushing, wheel, bearing)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ART, "skateboard.blend"))


main()
