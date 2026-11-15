#!/usr/bin/env python3
"""Assemble and render the corridor-landscape scene.

    python3 build_scene.py --quality draft|preview|final --out renders/final.png
                           [--save-blend corridor_landscape.blend]
                           [--no-grass] [--no-clouds-ok] [--no-render]
                           [--threads N] [--samples N] [--scale F] [--time-limit S]
                           [--exposure EV] [--look NAME] [--haze F] [--no-compositor]
                           [--placeholder terrain,grass,corridor,sky]

Build order: terrain -> grass -> corridor -> sky -> camera / render / compositor.
Every sibling module is optional: if it is missing or raises, a clearly named
PLACEHOLDER_* stand-in is built instead and a loud warning is printed.
"""
import argparse
import importlib
import inspect
import math
import os
import resource
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import bpy  # noqa: E402

import common as C  # noqa: E402
import render_setup  # noqa: E402

WARNINGS = []


def warn(msg):
    WARNINGS.append(msg)
    bar = "!" * 78
    print(f"\n{bar}\n!!! WARNING: {msg}\n{bar}\n", flush=True)


def peak_mem_gb():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024.0 * 1024.0)


# ---------------------------------------------------------------------------
# placeholders
# ---------------------------------------------------------------------------
def _mat(name, color, roughness=0.5, metallic=0.0):
    m = bpy.data.materials.new(name)
    try:
        m.use_nodes = True
    except Exception:
        pass
    m.diffuse_color = (*color, 1.0)
    b = m.node_tree.nodes.get("Principled BSDF") if m.node_tree else None
    if b is not None:
        b.inputs["Base Color"].default_value = (*color, 1.0)
        b.inputs["Roughness"].default_value = roughness
        b.inputs["Metallic"].default_value = metallic
    return m


def _box(name, lo, hi, mat, col):
    """Axis aligned box from min/max corners."""
    x0, y0, z0 = lo
    x1, y1, z1 = hi
    verts = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
             (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    faces = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    ob = bpy.data.objects.new(name, me)
    if mat is not None:
        me.materials.append(mat)
    col.objects.link(ob)
    return ob


def placeholder_corridor():
    """Blockout at the contract coordinates (also used for camera fitting)."""
    col = C.get_collection("PLACEHOLDER_Corridor")
    white = _mat("PLACEHOLDER_White", (0.8, 0.82, 0.82), 0.5)
    frame = _mat("PLACEHOLDER_Mullion", (0.75, 0.8, 0.8), 0.35, 0.6)
    floor = _mat("PLACEHOLDER_Floor", (0.55, 0.6, 0.62), 0.06)
    y0, y1 = C.CORRIDOR_Y_MIN, C.CORRIDOR_Y_MAX
    gx, rx, cz = C.GLASS_X, C.RIGHT_WALL_X, C.CEILING_Z
    objs = [
        _box("PLACEHOLDER_Floor", (gx - 0.15, y0, -0.3), (rx, y1, 0.0), floor, col),
        _box("PLACEHOLDER_Ceiling", (gx - 0.15, y0, cz), (rx, y1, cz + 0.3), white, col),
        _box("PLACEHOLDER_RightWall", (rx, y0, 0.0), (rx + 0.2, y1, cz), white, col),
        _box("PLACEHOLDER_EndWall", (gx, y1, 0.0), (rx, y1 + 0.2, cz), white, col),
        _box("PLACEHOLDER_BackWall", (gx, y0 - 0.2, 0.0), (rx, y0, cz), white, col),
        _box("PLACEHOLDER_Sill", (gx - 0.06, y0, 0.0), (gx + 0.06, y1, 0.30), white, col),
        _box("PLACEHOLDER_Head", (gx - 0.06, y0, cz - 0.12), (gx + 0.06, y1, cz), white, col),
    ]
    # mullions: one joined mesh
    verts, faces = [], []
    n0 = int(math.ceil(y0 / C.MULLION_PITCH))
    n1 = int(math.floor(y1 / C.MULLION_PITCH))
    hw, hd = 0.045, 0.07
    for k in range(n0, n1 + 1):
        y = k * C.MULLION_PITCH + render_setup.MULLION_PHASE
        b = len(verts)
        for z in (0.30, cz - 0.12):
            verts += [(gx - hd, y - hw, z), (gx + hd, y - hw, z), (gx + hd, y + hw, z), (gx - hd, y + hw, z)]
        faces += [(b, b + 1, b + 5, b + 4), (b + 1, b + 2, b + 6, b + 5),
                  (b + 2, b + 3, b + 7, b + 6), (b + 3, b, b + 4, b + 7)]
    me = bpy.data.meshes.new("PLACEHOLDER_Mullions")
    me.from_pydata(verts, [], faces)
    me.update()
    me.materials.append(frame)
    mob = bpy.data.objects.new("PLACEHOLDER_Mullions", me)
    col.objects.link(mob)
    objs.append(mob)

    # glass: fresnel mix of transparent + glossy (lets light and mist through)
    g = bpy.data.materials.new("PLACEHOLDER_Glass")
    try:
        g.use_nodes = True
    except Exception:
        pass
    nt = g.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    mix = nt.nodes.new("ShaderNodeMixShader")
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    tr.inputs["Color"].default_value = (0.93, 0.97, 0.96, 1.0)
    gl = nt.nodes.new("ShaderNodeBsdfGlossy")
    gl.inputs["Roughness"].default_value = 0.0
    fr = nt.nodes.new("ShaderNodeFresnel")
    fr.inputs["IOR"].default_value = 1.5
    nt.links.new(fr.outputs[0], mix.inputs[0])
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(gl.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    gm = bpy.data.meshes.new("PLACEHOLDER_GlassPane")
    gm.from_pydata([(gx, y0, 0.3), (gx, y1, 0.3), (gx, y1, cz - 0.12), (gx, y0, cz - 0.12)], [], [(0, 1, 2, 3)])
    gm.update()
    gm.materials.append(g)
    gob = bpy.data.objects.new("PLACEHOLDER_GlassPane", gm)
    col.objects.link(gob)
    objs.append(gob)
    return {"collection": col, "objects": objs, "placeholder": True}


def placeholder_terrain():
    col = C.get_collection("PLACEHOLDER_Terrain")
    green = _mat("PLACEHOLDER_FieldGreen", (0.16, 0.42, 0.03), 0.8)
    dark = _mat("PLACEHOLDER_TreeGreen", (0.012, 0.035, 0.02), 0.9)
    z = C.GROUND_Z
    me = bpy.data.meshes.new("PLACEHOLDER_Ground")
    me.from_pydata([(-3000, -1500, z), (C.GLASS_X + 6.0, -1500, z), (C.GLASS_X + 6.0, 3000, z), (-3000, 3000, z)],
                   [], [(0, 1, 2, 3)])
    me.update()
    me.materials.append(green)
    ground = bpy.data.objects.new("PLACEHOLDER_Ground", me)
    col.objects.link(ground)
    d = C.TREELINE_DISTANCE
    t1 = _box("PLACEHOLDER_Treeline_W", (-d - 40, -400, z), (-d, 900, z + 16), dark, col)
    t2 = _box("PLACEHOLDER_Treeline_N", (-d - 40, 520, z), (40, 560, z + 16), dark, col)
    return {"collection": col, "terrain": ground, "objects": [ground, t1, t2], "placeholder": True}


def placeholder_sky():
    scene = bpy.context.scene
    col = C.get_collection("PLACEHOLDER_Sky")
    world = bpy.data.worlds.new("PLACEHOLDER_World")
    try:
        world.use_nodes = True
    except Exception:
        pass
    nt = world.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    bg = nt.nodes.new("ShaderNodeBackground")
    sky = nt.nodes.new("ShaderNodeTexSky")
    for t in ("MULTIPLE_SCATTERING", "SINGLE_SCATTERING", "NISHITA", "HOSEK_WILKIE", "PREETHAM"):
        try:
            sky.sky_type = t
            break
        except Exception:
            continue
    for attr, val in (("sun_disc", False), ("sun_elevation", math.radians(C.SUN_ELEVATION_DEG)),
                      ("sun_rotation", math.radians(C.SUN_AZIMUTH_DEG))):
        if hasattr(sky, attr):
            try:
                setattr(sky, attr, val)
            except Exception:
                pass
    bg.inputs["Strength"].default_value = 0.05
    nt.links.new(sky.outputs[0], bg.inputs["Color"])
    nt.links.new(bg.outputs[0], out.inputs["Surface"])
    scene.world = world

    ld = bpy.data.lights.new("PLACEHOLDER_Sun", 'SUN')
    ld.energy = 5.0
    ld.angle = math.radians(0.6)
    ld.color = (1.0, 0.92, 0.82)
    sun = bpy.data.objects.new("PLACEHOLDER_Sun", ld)
    col.objects.link(sun)
    from mathutils import Vector
    to_sun = Vector(C.sun_direction_to_sun())
    sun.rotation_euler = to_sun.to_track_quat('Z', 'Y').to_euler()   # lamp shines along -Z
    return {"collection": col, "world": world, "sun": sun, "objects": [sun], "placeholder": True}


# ---------------------------------------------------------------------------
# guarded module build
# ---------------------------------------------------------------------------
def _snapshot():
    return {
        "objects": set(bpy.data.objects), "collections": set(bpy.data.collections),
    }


def _rollback(snap):
    """Remove whatever a failed build() left behind so the placeholder is clean."""
    for ob in [o for o in bpy.data.objects if o not in snap["objects"]]:
        try:
            bpy.data.objects.remove(ob, do_unlink=True)
        except Exception:
            pass
    for c in [c for c in bpy.data.collections if c not in snap["collections"]]:
        try:
            bpy.data.collections.remove(c)
        except Exception:
            pass


def _call_filtered(fn, **kwargs):
    """Call fn with only the keyword arguments its signature accepts."""
    try:
        params = inspect.signature(fn).parameters
        if not any(p.kind == p.VAR_KEYWORD for p in params.values()):
            kwargs = {k: v for k, v in kwargs.items() if k in params}
    except (TypeError, ValueError):
        pass
    return fn(**kwargs)


def guarded_build(name, placeholder, force_placeholder=False, **kwargs):
    """Import module `name` and call its build(); on any failure use placeholder.
    Returns (result_dict, used_placeholder, seconds)."""
    t0 = time.time()
    if force_placeholder:
        warn(f"'{name}' placeholder forced on the command line")
    else:
        snap = _snapshot()
        try:
            mod = importlib.import_module(name)
            res = _call_filtered(mod.build, **kwargs)
            if not isinstance(res, dict):
                res = {"result": res}
            dt = time.time() - t0
            print(f"[build_scene] {name}.build() ok in {dt:.1f}s  (peak mem {peak_mem_gb():.2f} GB)", flush=True)
            return res, False, dt
        except ModuleNotFoundError as exc:
            if exc.name == name:
                warn(f"module '{name}.py' not found -> using PLACEHOLDER for {name}")
            else:
                traceback.print_exc()
                warn(f"module '{name}' failed to import ({exc}) -> using PLACEHOLDER for {name}")
            _rollback(snap)
        except Exception as exc:
            traceback.print_exc()
            warn(f"{name}.build() raised {type(exc).__name__}: {exc} -> using PLACEHOLDER for {name}")
            _rollback(snap)
    res = placeholder() if placeholder is not None else {"placeholder": True}
    res["placeholder"] = True
    return res, True, time.time() - t0


def find_terrain(terrain_res):
    ob = bpy.data.objects.get(C.TERRAIN_OBJECT_NAME)
    if ob is not None:
        return ob
    for key in ("terrain", "terrain_obj", "object", "ground"):
        v = terrain_res.get(key) if isinstance(terrain_res, dict) else None
        if isinstance(v, bpy.types.Object):
            return v
    return None


# ---------------------------------------------------------------------------
# sky recommendations
# ---------------------------------------------------------------------------
# things this script owns - a sibling module may not override them
PROTECTED = ("samples", "use_adaptive_sampling", "adaptive_threshold", "resolution_x", "resolution_y",
             "resolution_percentage", "filepath", "threads", "threads_mode", "engine", "device",
             "use_denoising", "denoiser", "time_limit")
REC_KEYS = ("render_settings", "recommended", "recommended_settings", "recommended_render_settings",
            "recommended_cycles", "cycles", "cycles_settings", "settings")
COLOR_KEYS = ("recommended_color", "color_management", "view_settings", "recommended_view")


def apply_sky_recommendations(scene, sky_res, quality, args):
    """Apply whatever the sky module recommends. Returns compositor kwargs."""
    comp = {}
    if not isinstance(sky_res, dict):
        return comp
    for key in REC_KEYS:
        rec = sky_res.get(key)
        if not isinstance(rec, dict):
            continue
        rec = dict(rec)
        if quality == "draft":
            # keep the draft cheap: never raise bounces / volume quality above the preset
            for k in ("volume_bounces", "max_bounces", "transparent_max_bounces", "volume_max_steps",
                      "diffuse_bounces", "glossy_bounces", "transmission_bounces"):
                if k in rec and hasattr(scene.cycles, k):
                    rec[k] = min(rec[k], getattr(scene.cycles, k))
            if "volume_step_rate" in rec and hasattr(scene.cycles, "volume_step_rate"):
                rec["volume_step_rate"] = max(rec["volume_step_rate"], scene.cycles.volume_step_rate)
        else:
            # light path depth: glass + glossy floor need at least our preset
            for k in ("max_bounces", "transparent_max_bounces", "volume_bounces"):
                if k in rec and hasattr(scene.cycles, k):
                    rec[k] = max(rec[k], getattr(scene.cycles, k))
        applied = render_setup.apply_overrides(scene, rec, protected=PROTECTED)
        print(f"[build_scene] sky['{key}'] applied: {applied}")
    for key in COLOR_KEYS:
        rec = sky_res.get(key)
        if not isinstance(rec, dict):
            continue
        # exposure belongs to the sky's light calibration -> honour it (unless the
        # CLI overrides); view transform / look are this module's grading decision.
        if "exposure" in rec and args.exposure is None:
            try:
                scene.view_settings.exposure = float(rec["exposure"]) + render_setup.VIEW["exposure"]
                print(f"[build_scene] sky['{key}'] exposure {rec['exposure']} "
                      f"(+ grade offset {render_setup.VIEW['exposure']}) applied")
            except Exception as exc:
                print(f"[build_scene] could not apply sky exposure: {exc}")
        print(f"[build_scene] sky['{key}'] = {rec} (view transform/look kept: "
              f"{scene.view_settings.view_transform} / {scene.view_settings.look})")
    # haze: only composite mist haze when the sky module asks for it (it normally
    # ships a real haze volume, which also works through glass and in reflections)
    mist = sky_res.get("mist") if isinstance(sky_res.get("mist"), dict) else {}
    haze_mode = str(sky_res.get("haze_mode", "")).upper()
    if haze_mode == "MIST":
        comp["haze_strength"] = float(mist.get("strength", mist.get("haze_strength", 0.9)))
    for src, dst in (("haze_color", "haze_color"), ("color", "haze_color"), ("start", "mist_start"),
                     ("depth", "mist_depth"), ("falloff", "mist_falloff")):
        if src in mist and mist[src] is not None:
            comp[dst] = mist[src]
    return comp


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--quality", choices=["draft", "preview", "final"], default="draft")
    ap.add_argument("--out", default=os.path.join(HERE, "renders", "final.png"))
    ap.add_argument("--save-blend", default=None, help="path of .blend to save before rendering")
    ap.add_argument("--no-grass", action="store_true", help="skip the grass module entirely")
    ap.add_argument("--no-clouds-ok", action="store_true",
                    help="if the sky module fails with clouds, retry it without clouds before "
                         "falling back to the placeholder sky")
    ap.add_argument("--no-clouds", action="store_true", help="build the sky without clouds")
    ap.add_argument("--no-render", action="store_true", help="assemble (and save) only")
    ap.add_argument("--no-compositor", action="store_true")
    ap.add_argument("--no-denoise", action="store_true")
    ap.add_argument("--threads", type=int, default=0, help="0 = all cores")
    ap.add_argument("--samples", type=int, default=None)
    ap.add_argument("--scale", type=float, default=None, help="resolution scale of 2018x946")
    ap.add_argument("--time-limit", type=float, default=None, help="Cycles time limit in seconds")
    ap.add_argument("--exposure", type=float, default=None)
    ap.add_argument("--look", default=None)
    ap.add_argument("--view-transform", default=None)
    ap.add_argument("--haze", type=float, default=None, help="mist haze strength in the compositor")
    ap.add_argument("--placeholder", default="",
                    help="comma list of modules to replace by placeholders (terrain,grass,corridor,sky)")
    if argv is None:
        argv = sys.argv[1:]
        if "--" in argv:                      # also usable via `blender -b -P build_scene.py -- ...`
            argv = argv[argv.index("--") + 1:]
    return ap.parse_args(argv)


def assemble(args):
    """Build the whole scene. Returns (scene, info dict)."""
    t_start = time.time()
    forced = {s.strip() for s in args.placeholder.split(",") if s.strip()}
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.unit_settings.system = 'METRIC'
    info = {"placeholders": [], "timing": {}}

    def run(name, placeholder, **kw):
        res, ph, dt = guarded_build(name, placeholder, force_placeholder=name in forced, **kw)
        info["timing"][name] = dt
        if ph:
            info["placeholders"].append(name)
        return res

    cam_loc = tuple(render_setup.CAM["location"])

    # 1. terrain
    terrain_res = run("terrain", placeholder_terrain)
    terrain_obj = find_terrain(terrain_res)

    # 2. grass
    if args.no_grass:
        print("[build_scene] --no-grass: grass skipped")
        grass_res = {}
    else:
        if terrain_obj is None:
            warn(f"no '{C.TERRAIN_OBJECT_NAME}' object (terrain placeholder in use) -> "
                 f"grass.build(terrain_obj=None): the grass module falls back to a flat field")
        grass_res = run("grass", None, terrain_obj=terrain_obj, camera_location=cam_loc)

    # 3. corridor
    corridor_res = run("corridor", placeholder_corridor)

    # 4. sky
    if args.no_clouds_ok and "sky" not in forced:
        sky_res, ph, dt = guarded_build("sky", None, clouds=not args.no_clouds)
        if ph and not args.no_clouds:
            warn("sky failed with clouds -> retrying without clouds (--no-clouds-ok)")
            sky_res, ph, dt2 = guarded_build("sky", None, clouds=False)
            dt += dt2
        if ph:
            sky_res = placeholder_sky()
            sky_res["placeholder"] = True
            info["placeholders"].append("sky")
        info["timing"]["sky"] = dt
    else:
        sky_res = run("sky", placeholder_sky, clouds=not args.no_clouds)
    if scene.world is None:
        warn("sky module did not set scene.world -> placeholder world")
        placeholder_sky()

    # 5. camera / render / compositor
    cam = render_setup.setup_camera(scene)
    preset = render_setup.setup_render(
        args.quality, out_path=args.out, scene=scene, threads=args.threads, samples=args.samples,
        scale=args.scale, time_limit=args.time_limit, denoise=not args.no_denoise,
        exposure=args.exposure, look=args.look, view_transform=args.view_transform)
    comp_kw = apply_sky_recommendations(scene, sky_res, args.quality, args)
    if args.haze is not None:
        comp_kw["haze_strength"] = args.haze
    if args.no_compositor:
        scene.render.use_compositing = False
        comp = None
    else:
        try:
            comp = render_setup.setup_compositor(scene, **comp_kw)
        except Exception as exc:
            traceback.print_exc()
            warn(f"compositor setup failed ({exc}) -> rendering without compositing")
            scene.render.use_compositing = False
            comp = None

    info.update(scene=scene, camera=cam, preset=preset, compositor=comp,
                results=dict(terrain=terrain_res, grass=grass_res, corridor=corridor_res, sky=sky_res))
    info["timing"]["assemble_total"] = time.time() - t_start
    return scene, info


def main(argv=None):
    args = parse_args(argv)
    t0 = time.time()
    scene, info = assemble(args)
    t_build = time.time() - t0
    mem_build = peak_mem_gb()

    r = scene.render
    cam = info["camera"]
    print("\n[build_scene] ---------------- scene summary ----------------")
    print(f"  objects: {len(bpy.data.objects)}   meshes: {len(bpy.data.meshes)}   "
          f"collections: {[c.name for c in bpy.data.collections]}")
    print(f"  camera: loc={tuple(round(v, 3) for v in cam.location)} "
          f"rot_deg={tuple(round(math.degrees(v), 2) for v in cam.rotation_euler)} "
          f"lens={cam.data.lens}mm shift=({cam.data.shift_x}, {cam.data.shift_y})")
    print(f"  render: {args.quality} {r.resolution_x}x{r.resolution_y} samples={scene.cycles.samples} "
          f"thr={scene.cycles.adaptive_threshold} bounces={scene.cycles.max_bounces} "
          f"denoiser={info['preset']['denoiser']} threads="
          f"{r.threads if r.threads_mode == 'FIXED' else 'auto'}")
    print(f"  view: {scene.view_settings.view_transform} / {scene.view_settings.look} "
          f"exposure={scene.view_settings.exposure}   compositing={r.use_compositing}")
    print(f"  placeholders in use: {info['placeholders'] or 'none'}")
    print(f"  build time {t_build:.1f}s, peak memory after build {mem_build:.2f} GB", flush=True)

    if args.save_blend:
        path = os.path.abspath(args.save_blend)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        try:
            bpy.ops.wm.save_as_mainfile(filepath=path, compress=True)
            print(f"[build_scene] saved {path} ({os.path.getsize(path) / 1e6:.1f} MB)")
        except Exception as exc:
            warn(f"could not save blend file: {exc}")

    t_render = 0.0
    if not args.no_render:
        t1 = time.time()
        print(f"[build_scene] rendering -> {r.filepath}", flush=True)
        bpy.ops.render.render(write_still=True)
        t_render = time.time() - t1
        ok = os.path.exists(r.filepath)
        print(f"[build_scene] render {'written' if ok else 'FAILED - no file'}: {r.filepath}")

    print("\n[build_scene] ================= done =================")
    for k, v in info["timing"].items():
        print(f"  {k:16s} {v:8.1f} s")
    print(f"  {'render':16s} {t_render:8.1f} s")
    print(f"  {'total':16s} {time.time() - t0:8.1f} s")
    print(f"  peak memory (RSS): {peak_mem_gb():.2f} GB")
    if WARNINGS:
        print(f"\n  {len(WARNINGS)} WARNING(S):")
        for w in WARNINGS:
            print(f"   - {w}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
