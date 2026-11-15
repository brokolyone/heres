"""Sky, sun, volumetric clouds and atmospheric haze for the corridor-landscape scene.

`build() -> dict` sets the scene World (physically based multiple-scattering sky,
sun disc disabled), adds a matching Sun lamp ("Sun"), real volumetric cumulus
clouds (fog-volume grids generated from blob meshes with Mesh-to-Volume +
Volume-Displace, shaded by a noise-eroded Principled Volume) and aerial-perspective
haze.  Everything goes into the collection "Sky".  Nothing else in the scene is
touched (apart from scene.world and world mist settings).

Verified against bpy 5.3 (Sky Texture: sky_type 'MULTIPLE_SCATTERING').
"""
import math
import random

import bpy
import bmesh
from mathutils import Vector

import common

COLLECTION = "Sky"

# --------------------------------------------------------------------------
# Tunables
# --------------------------------------------------------------------------
# Sky Texture (MULTIPLE_SCATTERING).  Calibrated so that scene exposure 0 works:
# with SKY_STRENGTH the sunlit horizontal irradiance is ~ 5 (sun) + ~1 (sky).
SKY_STRENGTH = 0.085         # Background strength multiplying the sky texture
SKY_ALTITUDE = 50.0          # m
SKY_AIR = 1.0                # Rayleigh density (1 = clear day)
SKY_AEROSOL = 0.6            # < 1: cleaner air, more saturated blue, less white horizon
SKY_OZONE = 2.2              # > 1: deeper, slightly colder blue at the zenith
SKY_SATURATION = 1.30        # mild boost towards the vivid reference blue

# Sun lamp.  SUN_IRRADIANCE_PER_SKY_UNIT is the irradiance (perpendicular to the
# sun) of the sky texture's own sun disc at Background strength 1.0 for the
# settings above, measured by rendering a white diffuse card - so lamp and sky stay consistent.
SUN_IRRADIANCE_PER_SKY_UNIT = 151.0   # measured (red channel), see test_sky.py --calibrate notes
SUN_ANGLE_DEG = 0.6                   # real sun 0.53 deg; slightly larger = softer, cleaner
SUN_COLOR = (1.0, 0.94, 0.86)          # sky model's disc measures (1, .85, .675); whitened for clean white clouds
SUN_BASE_SKY_STRENGTH = 0.05          # lamp energy = SUN_IRRADIANCE_PER_SKY_UNIT * this (7.55 W/m2);
                                      # SKY_STRENGTH above is boosted 1.7x over physical for the vivid reference look

# Haze: 'VOLUME' (bounded homogeneous volume over the field; works through glass
# and in reflections), 'MIST' (only world mist settings, compositor must apply)
# or 'NONE'.
HAZE_MODE = "VOLUME"
HAZE_DENSITY = 1.5e-4        # 1/m  -> ~6 % extinction at the 380 m treeline
HAZE_COLOR = (0.62, 0.78, 1.0)
HAZE_TOP_Z = 45.0            # top of haze slab above GROUND_Z
MIST_START = 60.0
MIST_DEPTH = 1400.0          # mist factor at treeline ~ (380-60)/1400 = 0.23
MIST_HAZE_COLOR = (0.60, 0.74, 0.95)

# Clouds.  Positions are given as seen from the default camera:
# (azimuth in degrees from +Y towards -X, elevation deg, distance m,
#  width m, depth m, height m, seed, density multiplier)
CLOUD_DENSITY = 0.07         # 1/m peak extinction
CLOUD_SPECS = [
    # main flat cumulus fragment in the 2nd window bay
    (47.0, 9.3, 2100.0, 420.0, 260.0, 85.0, 11, 1.0),
    # its small detached wisp to the left
    (55.5, 9.8, 2200.0, 110.0, 90.0, 35.0, 5, 0.6),
    # small puff, far-left bay
    (61.5, 9.0, 1900.0, 130.0, 110.0, 55.0, 23, 0.9),
    # small puff, centre bay
    (31.5, 7.2, 2300.0, 120.0, 110.0, 55.0, 31, 0.9),
    # faint low wisps near the horizon, centre bay
    (36.5, 4.6, 2500.0, 240.0, 150.0, 40.0, 47, 0.45),
    (22.0, 5.2, 2500.0, 200.0, 140.0, 40.0, 59, 0.45),
    # out-of-frame clouds (behind / above) so floor & glass reflections see some
    (75.0, 16.0, 1800.0, 300.0, 220.0, 90.0, 71, 1.0),
    (12.0, 13.0, 2400.0, 320.0, 240.0, 90.0, 83, 0.9),
]

RECOMMENDED_CYCLES = {
    "volume_step_rate": 1.0,
    "volume_max_steps": 256,
    "volume_bounces": 3,
    "max_bounces": 8,
    "transparent_max_bounces": 12,
    "sample_clamp_indirect": 10.0,
}
RECOMMENDED_COLOR = {
    "view_transform": "AgX",          # fall back to 'Filmic' / 'Standard' if unavailable
    "look": "AgX - Medium High Contrast",
    "exposure": 0.0,
    "gamma": 1.0,
}


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def _sun_vec():
    return Vector(common.sun_direction_to_sun()).normalized()


def _sky_sun_angles():
    """(elevation, rotation) for the Sky Texture node.

    The node puts the sun at (sin(rot)*cos(el), cos(rot)*cos(el), sin(el)) with a
    sign convention verified by render test (see calibrate/test): rotation is
    measured from +Y towards -X ... handled through SUN_ROTATION_SIGN.
    """
    d = _sun_vec()
    el = math.asin(max(-1.0, min(1.0, d.z)))
    az = math.atan2(d.x, d.y)            # from +Y towards +X
    return el, SUN_ROTATION_SIGN * az


SUN_ROTATION_SIGN = 1.0   # verified by test (sun disc lands on common direction)


def _new_material(name):
    old = bpy.data.materials.get(name)
    if old is not None:
        bpy.data.materials.remove(old)
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.node_tree.nodes.clear()
    return mat


# --------------------------------------------------------------------------
# world
# --------------------------------------------------------------------------
def build_world(scene, sun_disc=False, strength=None):
    world = bpy.data.worlds.get("SkyWorld")
    if world is None:
        world = bpy.data.worlds.new("SkyWorld")
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()

    sky = nt.nodes.new("ShaderNodeTexSky")
    sky.name = "Sky Texture"
    sky.sky_type = "MULTIPLE_SCATTERING"
    el, rot = _sky_sun_angles()
    sky.sun_elevation = el
    sky.sun_rotation = rot
    sky.sun_disc = sun_disc
    sky.sun_size = math.radians(SUN_ANGLE_DEG)
    sky.sun_intensity = 1.0
    sky.altitude = SKY_ALTITUDE
    sky.air_density = SKY_AIR
    sky.aerosol_density = SKY_AEROSOL
    sky.ozone_density = SKY_OZONE

    hsv = nt.nodes.new("ShaderNodeHueSaturation")
    hsv.inputs["Saturation"].default_value = SKY_SATURATION
    nt.links.new(sky.outputs["Color"], hsv.inputs["Color"])

    bg = nt.nodes.new("ShaderNodeBackground")
    bg.name = "Sky Background"
    bg.inputs["Strength"].default_value = SKY_STRENGTH if strength is None else strength
    nt.links.new(hsv.outputs["Color"], bg.inputs["Color"])

    out = nt.nodes.new("ShaderNodeOutputWorld")
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])

    for i, n in enumerate((sky, hsv, bg, out)):
        n.location = (i * 220, 0)

    # mist settings (used only if the compositor applies the Mist pass)
    world.mist_settings.use_mist = True
    world.mist_settings.start = MIST_START
    world.mist_settings.depth = MIST_DEPTH
    world.mist_settings.falloff = "LINEAR"

    scene.world = world
    return world


# --------------------------------------------------------------------------
# sun lamp
# --------------------------------------------------------------------------
def build_sun(col):
    old = bpy.data.objects.get("Sun")
    if old is not None:
        bpy.data.objects.remove(old, do_unlink=True)
    light = bpy.data.lights.new("Sun", "SUN")
    light.energy = SUN_IRRADIANCE_PER_SKY_UNIT * SUN_BASE_SKY_STRENGTH
    light.color = SUN_COLOR
    light.angle = math.radians(SUN_ANGLE_DEG)
    try:
        light.cycles.max_bounces = 1024
    except Exception:
        pass
    obj = bpy.data.objects.new("Sun", light)
    d = _sun_vec()
    obj.location = d * 200.0 + Vector((0.0, 20.0, 0.0))   # position irrelevant, tidy only
    # a lamp shines along its local -Z, so local +Z must point TO the sun
    obj.rotation_euler = d.to_track_quat("Z", "Y").to_euler()
    col.objects.link(obj)
    return obj


# --------------------------------------------------------------------------
# clouds
# --------------------------------------------------------------------------
def _cloud_material():
    mat = _new_material("CloudVolume")
    nt = mat.node_tree
    N, L = nt.nodes, nt.links

    info = N.new("ShaderNodeVolumeInfo")
    geo = N.new("ShaderNodeNewGeometry")
    oinfo = N.new("ShaderNodeObjectInfo")

    # world-space position, offset per object so every cloud is different
    offs = N.new("ShaderNodeVectorMath")
    offs.operation = "MULTIPLY_ADD"
    L.new(oinfo.outputs["Random"], offs.inputs[0])
    offs.inputs[1].default_value = (913.0, 571.0, 377.0)
    L.new(geo.outputs["Position"], offs.inputs[2])

    # billow noise (cauliflower lumps, ~60 m) and fine erosion (~12 m)
    n1 = N.new("ShaderNodeTexNoise")
    n1.inputs["Scale"].default_value = 1.0 / 70.0
    n1.inputs["Detail"].default_value = 4.0
    n1.inputs["Roughness"].default_value = 0.55
    L.new(offs.outputs[0], n1.inputs["Vector"])
    n2 = N.new("ShaderNodeTexNoise")
    n2.inputs["Scale"].default_value = 1.0 / 14.0
    n2.inputs["Detail"].default_value = 2.0
    n2.inputs["Roughness"].default_value = 0.6
    L.new(offs.outputs[0], n2.inputs["Vector"])

    # shape = grid density (0..1, soft towards the hull) minus noise erosion
    er1 = N.new("ShaderNodeMath")
    er1.operation = "MULTIPLY_ADD"      # n1 * -0.9 + grid
    L.new(n1.outputs["Fac"], er1.inputs[0])
    er1.inputs[1].default_value = -0.95
    L.new(info.outputs["Density"], er1.inputs[2])
    er2 = N.new("ShaderNodeMath")
    er2.operation = "MULTIPLY_ADD"      # n2 * -0.3 + er1
    L.new(n2.outputs["Fac"], er2.inputs[0])
    er2.inputs[1].default_value = -0.30
    L.new(er1.outputs[0], er2.inputs[2])

    ramp = N.new("ShaderNodeMapRange")
    ramp.interpolation_type = "SMOOTHSTEP"
    ramp.inputs["From Min"].default_value = -0.38
    ramp.inputs["From Max"].default_value = -0.12
    ramp.inputs["To Min"].default_value = 0.0
    ramp.inputs["To Max"].default_value = 1.0
    L.new(er2.outputs[0], ramp.inputs["Value"])

    dens = N.new("ShaderNodeMath")
    dens.operation = "MULTIPLY"
    L.new(ramp.outputs["Result"], dens.inputs[0])
    dens.inputs[1].default_value = CLOUD_DENSITY
    # per-object density multiplier stored in object colour alpha
    dens2 = N.new("ShaderNodeMath")
    dens2.operation = "MULTIPLY"
    L.new(dens.outputs[0], dens2.inputs[0])
    L.new(oinfo.outputs["Alpha"], dens2.inputs[1])

    vol = N.new("ShaderNodeVolumePrincipled")
    vol.inputs["Color"].default_value = (1.0, 1.0, 1.0, 1.0)
    vol.inputs["Density Attribute"].default_value = ""
    vol.inputs["Anisotropy"].default_value = 0.35
    L.new(dens2.outputs[0], vol.inputs["Density"])

    out = N.new("ShaderNodeOutputMaterial")
    L.new(vol.outputs["Volume"], out.inputs["Volume"])
    return mat


def _blob_mesh(name, width, depth, height, seed):
    """Flat-based cluster of overlapping spheres, origin at base centre."""
    rng = random.Random(seed)
    bm = bmesh.new()
    n = max(4, int(width / 45.0) + 3)
    for i in range(n):
        t = (i + 0.5) / n
        # blobs along the long (local X) axis, bigger towards the middle
        cx = (t - 0.5) * width * 0.8 + rng.uniform(-0.05, 0.05) * width
        cy = rng.uniform(-0.25, 0.25) * depth
        bulge = 0.55 + 0.45 * math.sin(math.pi * t) * rng.uniform(0.7, 1.0)
        r = 0.5 * height * bulge
        rx = max(r * rng.uniform(1.3, 2.0), width / n * 0.8)
        ry = max(r * rng.uniform(1.1, 1.6), depth * 0.3)
        cz = r * rng.uniform(0.75, 1.0)
        res = bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.0)
        for v in res["verts"]:
            v.co = Vector((cx + v.co.x * rx, cy + v.co.y * ry, max(0.0, cz + v.co.z * r)))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return me


def _displace_texture():
    tex = bpy.data.textures.get("CloudDisplace")
    if tex is None:
        tex = bpy.data.textures.new("CloudDisplace", "CLOUDS")
    tex.noise_scale = 0.45
    tex.noise_depth = 2
    tex.cloud_type = "COLOR"
    return tex


def build_clouds(col, specs=None):
    specs = CLOUD_SPECS if specs is None else specs
    mat = _cloud_material()
    tex = _displace_texture()
    cam = Vector(common.CAMERA_LOCATION)
    clouds, sources = [], []
    for i, (az, el, dist, w, d, h, seed, dmul) in enumerate(specs):
        a, e = math.radians(az), math.radians(el)
        centre = cam + Vector((-math.sin(a) * math.cos(e) * dist,
                               math.cos(a) * math.cos(e) * dist,
                               math.sin(e) * dist))
        base = Vector((centre.x, centre.y, centre.z - 0.4 * h))
        name = "Cloud_%02d" % i

        for n_ in (name, name + "_src"):
            o = bpy.data.objects.get(n_)
            if o is not None:
                bpy.data.objects.remove(o, do_unlink=True)

        src = bpy.data.objects.new(name + "_src", _blob_mesh(name + "_src", w, d, h, seed))
        src.location = base
        # long axis perpendicular to the line of sight (+ a little variation)
        src.rotation_euler = (0.0, 0.0, a + math.radians(random.Random(seed).uniform(-20, 20)))
        src.hide_render = True
        src.hide_viewport = False
        src.display_type = "WIRE"
        col.objects.link(src)

        vdata = bpy.data.volumes.new(name)
        vobj = bpy.data.objects.new(name, vdata)
        col.objects.link(vobj)
        vdata.materials.append(mat)
        vobj.color = (1.0, 1.0, 1.0, dmul)

        m2v = vobj.modifiers.new("MeshToVolume", "MESH_TO_VOLUME")
        m2v.object = src
        m2v.resolution_mode = "VOXEL_SIZE"
        m2v.voxel_size = max(4.0, min(w, 400.0) / 56.0)
        m2v.interior_band_width = 0.42 * h      # soft density falloff to the hull
        m2v.density = 1.0

        dis = vobj.modifiers.new("Displace", "VOLUME_DISPLACE")
        dis.texture = tex
        dis.texture_map_mode = "GLOBAL"
        dis.strength = 0.22 * h
        dis.texture_sample_radius = 0.9 * h
        dis.texture_mid_level = (0.5, 0.5, 0.5)

        vdata.render.space = "WORLD"
        vdata.render.step_size = 0.0            # automatic (voxel size)
        vdata.render.clipping = 0.002
        clouds.append(vobj)
        sources.append(src)
    return clouds, sources


# --------------------------------------------------------------------------
# haze
# --------------------------------------------------------------------------
def build_haze(col):
    """Bounded homogeneous volume slab over the field (outdoors only)."""
    old = bpy.data.objects.get("HazeVolume")
    if old is not None:
        bpy.data.objects.remove(old, do_unlink=True)

    mat = _new_material("HazeVolume")
    nt = mat.node_tree
    sc = nt.nodes.new("ShaderNodeVolumeScatter")
    sc.inputs["Color"].default_value = (*HAZE_COLOR, 1.0)
    sc.inputs["Density"].default_value = HAZE_DENSITY
    sc.inputs["Anisotropy"].default_value = 0.2
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(sc.outputs["Volume"], out.inputs["Volume"])
    try:
        mat.cycles.volume_sampling = "DISTANCE"
    except Exception:
        pass

    x0, x1 = common.FIELD_X_MIN - 300.0, common.GLASS_X - 1.5
    y0, y1 = common.FIELD_Y_MIN - 300.0, common.FIELD_Y_MAX + 400.0
    z0, z1 = common.GROUND_Z - 3.0, common.GROUND_Z + HAZE_TOP_Z
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((x0 + (v.co.x + 0.5) * (x1 - x0),
                       y0 + (v.co.y + 0.5) * (y1 - y0),
                       z0 + (v.co.z + 0.5) * (z1 - z0)))
    me = bpy.data.meshes.new("HazeVolume")
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat)
    obj = bpy.data.objects.new("HazeVolume", me)
    obj.display_type = "BOUNDS"
    col.objects.link(obj)
    return obj


def setup_mist_compositor(scene, view_layer=None, strength=0.9):
    """OPTIONAL alternative to the haze volume: blend MIST_HAZE_COLOR over the
    image with the Mist pass.  NOTE: the mist pass stops at refractive glass, so
    this is only valid if the glazing uses a Transparent-BSDF (camera-ray
    transparent) shader.  Returns the node group, or None on failure."""
    view_layer = view_layer or scene.view_layers[0]
    view_layer.use_pass_mist = True
    try:
        ng = bpy.data.node_groups.new("HazeCompositor", "CompositorNodeTree")
        ng.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
        rl = ng.nodes.new("CompositorNodeRLayers")
        rl.scene = scene
        mul = ng.nodes.new("ShaderNodeMath")
        mul.operation = "MULTIPLY"
        mul.inputs[1].default_value = strength
        ng.links.new(rl.outputs["Mist"], mul.inputs[0])
        mix = ng.nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        mix.inputs["B"].default_value = (*MIST_HAZE_COLOR, 1.0)
        ng.links.new(mul.outputs[0], mix.inputs["Factor"])
        ng.links.new(rl.outputs["Image"], mix.inputs["A"])
        out = ng.nodes.new("NodeGroupOutput")
        ng.links.new(mix.outputs["Result"], out.inputs[0])
        scene.compositing_node_group = ng
        return ng
    except Exception as exc:     # compositor API differs - leave it to render agent
        print("sky.setup_mist_compositor failed:", exc)
        return None


# --------------------------------------------------------------------------
# public API
# --------------------------------------------------------------------------
def apply_recommended_settings(scene):
    """Convenience for the render agent: apply RECOMMENDED_CYCLES / colour."""
    for k, v in RECOMMENDED_CYCLES.items():
        if hasattr(scene.cycles, k):
            setattr(scene.cycles, k, v)
    vs = scene.view_settings
    for vt in (RECOMMENDED_COLOR["view_transform"], "Filmic", "Standard"):
        try:
            vs.view_transform = vt
            break
        except TypeError:
            continue
    try:
        vs.look = RECOMMENDED_COLOR["look"]
    except TypeError:
        pass
    vs.exposure = RECOMMENDED_COLOR["exposure"]
    vs.gamma = RECOMMENDED_COLOR["gamma"]


def build(clouds=True, haze=None):
    scene = bpy.context.scene
    col = common.get_collection(COLLECTION)
    haze = HAZE_MODE if haze is None else haze

    world = build_world(scene)
    sun = build_sun(col)
    cloud_objs, cloud_srcs = build_clouds(col) if clouds else ([], [])
    haze_obj = build_haze(col) if haze == "VOLUME" else None

    return {
        "collection": col,
        "world": world,
        "sun": sun,
        "sun_direction_to_sun": tuple(_sun_vec()),
        "clouds": cloud_objs,
        "cloud_sources": cloud_srcs,
        "haze": haze_obj,
        "haze_mode": haze,
        "mist": {"use_pass_mist": True, "start": MIST_START, "depth": MIST_DEPTH,
                 "falloff": "LINEAR", "haze_color": MIST_HAZE_COLOR},
        "recommended_cycles": dict(RECOMMENDED_CYCLES),
        "recommended_color": dict(RECOMMENDED_COLOR),
        "objects": [sun] + cloud_objs + cloud_srcs + ([haze_obj] if haze_obj else []),
    }


if __name__ == "__main__":
    print(build())
