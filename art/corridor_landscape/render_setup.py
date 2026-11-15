"""Camera, Cycles render settings, colour management and compositor for the
corridor-landscape scene (Blender / bpy 5.3, Cycles CPU).

Public API
----------
setup_camera(**overrides)                 -> camera object ("Camera")
setup_render(quality, out_path, ...)      -> dict of the applied preset
setup_compositor(scene, **params)         -> compositor node group (or None)
apply_overrides(scene, mapping)           -> generic "attribute -> value" applier

Everything that depends on the (heavily changed) 5.x API is feature-probed and
degrades gracefully: a missing node / property prints a warning and is skipped.
"""
import math
import os

import bpy

import common as C

# ---------------------------------------------------------------------------
# Camera
# ---------------------------------------------------------------------------
# Fitted against reference.png (1009x473), see the notes in the final report.
#   * vanishing point of the corridor measured at 92.6 % width / 59.6 % height
#     (intersection of the ceiling/glass line and the floor/glass line; the
#     outdoor horizon / treeline base sits on the same row -> eye level).
#   * ceiling line slope 0.646, floor line slope 0.43  ->  eye height
#     h = CEILING_Z / (1 + 0.646/0.43) = 1.12 m, distance to the glass 2.07 m.
#   * the on-screen mullion spacing would want ~20 mm for the contract pitch
#     of 1.6 m, but the sky/terrain modules place clouds and field features
#     by azimuth for the contract's 24 mm / 32 deg camera -> compromise 22 mm,
#     yaw atan(0.851 * 18/22) = 34.8 deg.
#   * verticals are vertical in the reference -> pitch 0 and a vertical lens
#     shift instead of tilting the camera.
CAM = {
    "location": (C.GLASS_X + 2.14, -0.85, 1.12),
    "yaw_left_deg": 34.8,
    "pitch_deg": 0.0,
    "lens_mm": 22.0,
    "sensor_width": 36.0,
    "shift_x": 0.0,
    "shift_y": 0.045,          # (0.596 - 0.5) * 473 / 1009
    "clip_start": 0.05,
    "clip_end": 5000.0,
    "use_dof": True,           # practically pan-focus (reference is sharp)
    "fstop": 11.0,
    "focus_distance": 9.0,
}

# Y positions at which the corridor module puts mullions are assumed to be
# k * MULLION_PITCH (+ MULLION_PHASE).  The camera Y above places the nearest
# mullion at the far-left image edge like in the reference.
MULLION_PHASE = 0.0


def setup_camera(scene=None, **overrides):
    """Create (or reuse) the camera "Camera" and make it the scene camera."""
    scene = scene or bpy.context.scene
    p = dict(CAM)
    p.update(overrides)

    cam_data = bpy.data.cameras.get("Camera") or bpy.data.cameras.new("Camera")
    cam = bpy.data.objects.get("Camera")
    if cam is None or cam.type != 'CAMERA':
        cam = bpy.data.objects.new("Camera", cam_data)
    if not cam.users_collection:
        scene.collection.objects.link(cam)

    cam.location = p["location"]
    cam.rotation_mode = 'XYZ'
    # default camera looks down -Z; +90 deg about X looks along +Y; a positive
    # rotation about Z then turns it left, from +Y towards -X (the glass).
    cam.rotation_euler = (math.radians(90.0 + p["pitch_deg"]), 0.0,
                          math.radians(p["yaw_left_deg"]))

    cam_data.type = 'PERSP'
    cam_data.lens = p["lens_mm"]
    cam_data.sensor_fit = 'HORIZONTAL'
    cam_data.sensor_width = p["sensor_width"]
    cam_data.shift_x = p["shift_x"]
    cam_data.shift_y = p["shift_y"]
    cam_data.clip_start = p["clip_start"]
    cam_data.clip_end = p["clip_end"]
    cam_data.dof.use_dof = bool(p["use_dof"])
    cam_data.dof.aperture_fstop = p["fstop"]
    cam_data.dof.focus_distance = p["focus_distance"]

    scene.camera = cam
    return cam


# ---------------------------------------------------------------------------
# Render settings
# ---------------------------------------------------------------------------
QUALITY = {
    # scale: fraction of RES_X x RES_Y
    "draft": dict(
        scale=800.0 / C.RES_X, samples=32, adaptive_threshold=0.1, adaptive_min=8,
        max_bounces=8, diffuse=2, glossy=3, transmission=6, volume=0, transparent=12,
        clamp_indirect=6.0, prefilter='FAST', denoise_quality='BALANCED',
        volume_step_rate=4.0, volume_max_steps=128,
    ),
    "preview": dict(
        scale=0.5, samples=128, adaptive_threshold=0.04, adaptive_min=16,
        max_bounces=10, diffuse=3, glossy=4, transmission=8, volume=1, transparent=24,
        clamp_indirect=8.0, prefilter='ACCURATE', denoise_quality='HIGH',
        volume_step_rate=2.0, volume_max_steps=256,
    ),
    "final": dict(
        scale=1.0, samples=640, adaptive_threshold=0.012, adaptive_min=48,
        max_bounces=12, diffuse=4, glossy=6, transmission=12, volume=2, transparent=48,
        clamp_indirect=10.0, prefilter='ACCURATE', denoise_quality='HIGH',
        volume_step_rate=1.0, volume_max_steps=512,
    ),
}

# colour management: AgX keeps the very bright sky/windows from clipping to
# flat cyan/white, the "Punchy" look + a small exposure lift gives the
# saturated high-key feel of the reference (grade is finished in the compositor)
VIEW = dict(view_transform='AgX', look='AgX - Punchy', exposure=0.0, gamma=1.0)


def _set(obj, attr, value, quiet=False):
    """setattr guarded against missing attributes / invalid enum values."""
    if not hasattr(obj, attr):
        if not quiet:
            print(f"[render_setup] note: {type(obj).__name__}.{attr} not in this build - skipped")
        return False
    try:
        setattr(obj, attr, value)
        return True
    except Exception as exc:  # enum not available etc.
        if not quiet:
            print(f"[render_setup] WARNING: could not set {type(obj).__name__}.{attr}={value!r}: "
                  f"{str(exc).splitlines()[-1][:160]}")
        return False


def _set_first(obj, attr, values):
    for v in values:
        if _set(obj, attr, v, quiet=True):
            return v
    print(f"[render_setup] WARNING: none of {values} accepted for {type(obj).__name__}.{attr}")
    return None


def oidn_available(scene=None):
    scene = scene or bpy.context.scene
    try:
        prev = scene.cycles.denoiser
        scene.cycles.denoiser = 'OPENIMAGEDENOISE'
        ok = scene.cycles.denoiser == 'OPENIMAGEDENOISE'
        if not ok:
            scene.cycles.denoiser = prev
        return ok
    except Exception:
        return False


def setup_render(quality="final", out_path=None, scene=None, threads=0,
                 samples=None, scale=None, time_limit=None, denoise=True,
                 exposure=None, look=None, view_transform=None):
    """Configure Cycles CPU, film, passes, colour management and output.

    quality    : "draft" | "preview" | "final"
    out_path   : PNG path (16 bit RGB)
    threads    : 0 = all cores, otherwise fixed thread count
    samples / scale / time_limit : optional overrides of the preset
    """
    scene = scene or bpy.context.scene
    if quality not in QUALITY:
        raise ValueError(f"quality must be one of {list(QUALITY)}")
    q = dict(QUALITY[quality])
    if samples:
        q["samples"] = int(samples)
    if scale:
        q["scale"] = float(scale)

    r = scene.render
    r.engine = 'CYCLES'
    cy = scene.cycles
    _set(cy, "device", 'CPU')
    _set(cy, "feature_set", 'SUPPORTED')

    # ---- resolution --------------------------------------------------------
    r.resolution_x = max(4, int(round(C.RES_X * q["scale"])))
    r.resolution_y = max(4, int(round(C.RES_Y * q["scale"])))
    r.resolution_percentage = 100
    r.pixel_aspect_x = r.pixel_aspect_y = 1.0
    _set(r, "use_border", False)

    # ---- sampling ----------------------------------------------------------
    cy.samples = q["samples"]
    _set(cy, "use_adaptive_sampling", True)
    _set(cy, "adaptive_threshold", q["adaptive_threshold"])
    _set(cy, "adaptive_min_samples", min(q["adaptive_min"], q["samples"]))
    _set(cy, "time_limit", float(time_limit or 0.0))
    _set(cy, "use_light_tree", True)
    _set(cy, "sampling_pattern", 'TABULATED_SOBOL', quiet=True)
    # path guiding helps the sun-through-glass -> floor -> ceiling bounce light
    # on CPU, but costs memory/time: only for the final preset.
    _set(cy, "use_guiding", quality == "final", quiet=True)
    if quality == "final":
        _set(cy, "use_surface_guiding", True, quiet=True)
        _set(cy, "use_volume_guiding", False, quiet=True)
        _set(cy, "guiding_training_samples", 128, quiet=True)

    # ---- light paths -------------------------------------------------------
    cy.max_bounces = q["max_bounces"]
    cy.diffuse_bounces = q["diffuse"]
    cy.glossy_bounces = q["glossy"]
    cy.transmission_bounces = q["transmission"]   # double glazing = 4 interfaces
    cy.volume_bounces = q["volume"]
    cy.transparent_max_bounces = q["transparent"]  # alpha-mapped leaves / blades
    _set(cy, "min_light_bounces", 0)
    _set(cy, "min_transparent_bounces", 0)
    # sunlight has to get through the panes onto the floor: refractive caustics
    # on; reflective caustics off (fireflies from the polished floor), a little
    # glossy filtering to keep the remaining caustic paths tame.
    _set(cy, "caustics_refractive", True)
    _set(cy, "caustics_reflective", False)
    _set(cy, "blur_glossy", 0.6)
    # fireflies: never clamp direct light (sun patches must stay bright)
    _set(cy, "sample_clamp_direct", 0.0)
    _set(cy, "sample_clamp_indirect", q["clamp_indirect"])

    # ---- volumes (clouds) ----------------------------------------------------
    _set(cy, "volume_step_rate", q["volume_step_rate"], quiet=True)
    _set(cy, "volume_max_steps", q["volume_max_steps"], quiet=True)

    # ---- denoising ---------------------------------------------------------
    use_dn = bool(denoise) and oidn_available(scene)
    if denoise and not use_dn:
        print("[render_setup] WARNING: OpenImageDenoise not available - rendering without denoiser")
    _set(cy, "use_denoising", use_dn)
    if use_dn:
        _set(cy, "denoiser", 'OPENIMAGEDENOISE')
        _set(cy, "denoising_input_passes", 'RGB_ALBEDO_NORMAL')
        _set(cy, "denoising_prefilter", q["prefilter"])
        _set(cy, "denoising_quality", q["denoise_quality"], quiet=True)
        _set(cy, "denoising_use_gpu", False, quiet=True)

    # ---- performance -------------------------------------------------------
    _set(r, "use_persistent_data", False)
    _set(cy, "use_auto_tile", True)
    _set(cy, "tile_size", 1024)
    if threads and int(threads) > 0:
        r.threads_mode = 'FIXED'
        r.threads = int(threads)
    else:
        r.threads_mode = 'AUTO'
    _set(cy, "debug_use_spatial_splits", False, quiet=True)
    _set(cy, "debug_use_hair_bvh", True, quiet=True)
    _set(cy, "debug_use_compact_bvh", False, quiet=True)

    # ---- film --------------------------------------------------------------
    _set(r, "film_transparent", False)
    _set(cy, "pixel_filter_type", 'BLACKMAN_HARRIS')
    _set(cy, "filter_width", 1.5)
    _set(r, "use_motion_blur", False)
    _set(r, "dither_intensity", 0.5)

    # ---- passes ------------------------------------------------------------
    for vl in scene.view_layers:
        _set(vl, "use_pass_combined", True)
        _set(vl, "use_pass_mist", True)
        _set(vl, "use_pass_z", False)
        if hasattr(vl, "cycles"):
            _set(vl.cycles, "use_denoising", use_dn, quiet=True)
            _set(vl.cycles, "denoising_store_passes", False, quiet=True)

    # ---- colour management ---------------------------------------------------
    setup_color_management(scene, exposure=exposure, look=look, view_transform=view_transform)

    # ---- output ------------------------------------------------------------
    ims = r.image_settings
    _set(ims, "media_type", 'IMAGE', quiet=True)
    _set(ims, "file_format", 'PNG')
    _set(ims, "color_mode", 'RGB')
    _set(ims, "color_depth", '16')
    _set(ims, "compression", 30)
    _set(r, "use_file_extension", True)
    _set(r, "use_overwrite", True)
    if out_path:
        out_path = os.path.abspath(out_path)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        r.filepath = out_path
    r.use_compositing = True
    _set(r, "use_sequencer", False)
    _set(r, "compositor_device", 'CPU', quiet=True)
    _set(r, "compositor_precision", 'FULL' if quality == "final" else 'AUTO', quiet=True)

    q["resolution"] = (r.resolution_x, r.resolution_y)
    q["denoiser"] = 'OPENIMAGEDENOISE' if use_dn else None
    q["quality"] = quality
    return q


def setup_color_management(scene=None, exposure=None, look=None, view_transform=None):
    scene = scene or bpy.context.scene
    vs = scene.view_settings
    _set(scene.display_settings, "display_device", 'sRGB', quiet=True)
    vt = view_transform or VIEW["view_transform"]
    got = _set_first(vs, "view_transform", [vt, 'AgX', 'Filmic', 'Standard'])
    wanted_look = look or VIEW["look"]
    if got == 'AgX':
        _set_first(vs, "look", [wanted_look, 'AgX - Punchy', 'AgX - Medium High Contrast', 'None'])
    elif got == 'Filmic':
        _set_first(vs, "look", [wanted_look, 'Filmic - Medium High Contrast', 'Medium High Contrast', 'None'])
    else:
        _set_first(vs, "look", [wanted_look, 'None'])
    vs.exposure = VIEW["exposure"] if exposure is None else float(exposure)
    vs.gamma = VIEW["gamma"]
    _set(vs, "use_curve_mapping", False, quiet=True)
    _set(vs, "use_white_balance", False, quiet=True)
    try:
        scene.sequencer_colorspace_settings.name = 'sRGB'
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Generic override applier (used for the sky module's recommendations)
# ---------------------------------------------------------------------------
def apply_overrides(scene, mapping, protected=()):
    """Apply {attribute: value} to scene.cycles / scene.render / view settings /
    world mist settings - whichever owns an attribute of that name.
    Keys may be prefixed ("cycles.volume_step_rate", "render.film_transparent",
    "view_settings.exposure", "mist.start").  Returns list of applied keys."""
    applied = []
    if not isinstance(mapping, dict):
        return applied
    world = scene.world
    targets = {
        "cycles": scene.cycles,
        "render": scene.render,
        "view_settings": scene.view_settings,
        "view": scene.view_settings,
        "scene": scene,
    }
    if world is not None:
        targets["mist"] = world.mist_settings
        targets["mist_settings"] = world.mist_settings
        targets["world"] = world
    search_order = [scene.cycles, scene.render, scene.view_settings]
    for key, value in mapping.items():
        if not isinstance(key, str):
            continue
        if isinstance(value, dict) and key in targets:
            for k2, v2 in value.items():
                if k2 in protected or f"{key}.{k2}" in protected:
                    print(f"[render_setup] override {key}.{k2} is protected - ignored")
                    continue
                if isinstance(k2, str) and hasattr(targets[key], k2) and _set(targets[key], k2, v2):
                    applied.append(f"{key}.{k2}")
            continue
        if key in protected:
            print(f"[render_setup] override {key} is protected - ignored")
            continue
        if "." in key:
            head, attr = key.split(".", 1)
            tgt = targets.get(head)
            if tgt is not None and hasattr(tgt, attr) and _set(tgt, attr, value):
                applied.append(key)
            continue
        if isinstance(value, (dict, list, tuple, set)) and not isinstance(value, (list, tuple)):
            continue
        for tgt in search_order:
            if hasattr(tgt, key):
                if _set(tgt, key, value):
                    applied.append(key)
                break
    return applied


# ---------------------------------------------------------------------------
# Compositor
# ---------------------------------------------------------------------------
COMP_DEFAULTS = dict(
    # --- mist based atmospheric haze (scene-linear, before glare) -------------
    haze_strength=0.0,                 # 0 disables the haze branch entirely
    haze_color=(0.62, 0.76, 0.95),     # bluish horizon colour, scene linear
    mist_start=None,                   # world.mist_settings (metres); None = keep
    mist_depth=None,                   # what the sky module configured
    mist_falloff=None,
    # --- bloom ----------------------------------------------------------------
    glare=True,
    glare_threshold=1.6,               # only windows / sky / floor highlights
    glare_smoothness=0.5,
    glare_strength=0.12,
    glare_size=0.55,
    glare_saturation=0.9,
    # --- lens ------------------------------------------------------------------
    lens_distortion=0.004,
    lens_dispersion=0.006,
    vignette=0.16,                     # 0 disables; darkening in the far corners
    # --- grade toward the reference (bright, clean, saturated, cool whites) ----
    saturation=1.07,
    contrast=1.04,
    gain=1.0,
    gamma=1.0,
    temperature_shift=0.0,             # reserved
)


class _Tree:
    """Tiny helper around a compositor node group with graceful degradation."""

    def __init__(self, tree):
        self.tree = tree
        self.x = 0

    def new(self, idname, label=None):
        try:
            n = self.tree.nodes.new(idname)
        except Exception as exc:
            print(f"[compositor] WARNING: node {idname} unavailable ({str(exc)[:60]}) - step skipped")
            return None
        n.location = (self.x, 0)
        self.x += 220
        if label:
            n.label = label
        return n

    @staticmethod
    def set_in(node, name, value):
        """Set an input by name/identifier; tolerate missing sockets & bad enum values."""
        sock = node.inputs.get(name)
        if sock is None:
            for s in node.inputs:
                if s.identifier == name:
                    sock = s
                    break
        if sock is None:
            print(f"[compositor] note: {node.bl_idname} has no input '{name}' - skipped")
            return False
        try:
            sock.default_value = value
            return True
        except Exception as exc:
            print(f"[compositor] note: {node.bl_idname}.{name}={value!r} rejected "
                  f"({str(exc).splitlines()[-1][:80]})")
            return False

    def set_first(self, node, name, values):
        for v in values:
            sock = node.inputs.get(name)
            if sock is None:
                return None
            try:
                sock.default_value = v
                return v
            except Exception:
                continue
        print(f"[compositor] note: none of {values} accepted for {node.bl_idname}.{name}")
        return None

    def link(self, a, b):
        try:
            self.tree.links.new(a, b)
            return True
        except Exception as exc:
            print(f"[compositor] WARNING: link failed: {exc}")
            return False

    def mix(self, blend, fac, a, b, label=None):
        """Colour mix node (ShaderNodeMix in 5.x, legacy MixRGB otherwise).
        fac/a/b may be sockets or constants. Returns output socket or None."""
        n = None
        for idname in ("ShaderNodeMix", "CompositorNodeMixRGB", "ShaderNodeMixRGB"):
            try:
                n = self.tree.nodes.new(idname)
                break
            except Exception:
                continue
        if n is None:
            print("[compositor] WARNING: no mix node available - step skipped")
            return None
        n.location = (self.x, -200)
        self.x += 220
        if label:
            n.label = label
        if n.bl_idname == "ShaderNodeMix":
            n.data_type = 'RGBA'
            n.blend_type = blend
            n.clamp_factor = True
            sf, sa, sb = n.inputs["Factor_Float"] if "Factor_Float" in n.inputs else n.inputs[0], None, None
            for s in n.inputs:
                if s.identifier == "Factor_Float":
                    sf = s
                elif s.identifier == "A_Color":
                    sa = s
                elif s.identifier == "B_Color":
                    sb = s
            out = next(o for o in n.outputs if o.identifier == "Result_Color")
        else:
            n.blend_type = blend
            sf, sa, sb = n.inputs[0], n.inputs[1], n.inputs[2]
            out = n.outputs[0]
        for sock, val in ((sf, fac), (sa, a), (sb, b)):
            if isinstance(val, bpy.types.NodeSocket):
                self.link(val, sock)
            elif isinstance(val, (int, float)):
                sock.default_value = float(val)
            else:
                v = tuple(val)
                sock.default_value = v if len(v) == 4 else v + (1.0,)
        return out

    def math(self, op, a, b=None, clamp=False):
        n = None
        for idname in ("ShaderNodeMath", "CompositorNodeMath"):
            try:
                n = self.tree.nodes.new(idname)
                break
            except Exception:
                continue
        if n is None:
            return None
        n.location = (self.x, -400)
        self.x += 180
        n.operation = op
        n.use_clamp = clamp
        for sock, val in ((n.inputs[0], a), (n.inputs[1], b)):
            if val is None:
                continue
            if isinstance(val, bpy.types.NodeSocket):
                self.link(val, sock)
            else:
                sock.default_value = float(val)
        return n.outputs[0]


def _new_comp_tree(scene, name):
    """Return (tree, legacy) for both the 5.x node-group compositor and <=4.x."""
    if hasattr(scene, "compositing_node_group"):
        old = bpy.data.node_groups.get(name)
        if old is not None:
            bpy.data.node_groups.remove(old)
        tree = bpy.data.node_groups.new(name, "CompositorNodeTree")
        scene.compositing_node_group = tree
        return tree, False
    scene.use_nodes = True       # Blender <= 4.x
    tree = scene.node_tree
    tree.nodes.clear()
    return tree, True


def setup_compositor(scene=None, **params):
    """Photographic finishing. Chain (all in scene-linear, before the view
    transform):  Render Layers -> [mist haze mix] -> bloom glare -> lens
    distortion / dispersion -> vignette -> colour grade -> output.
    Every stage is optional and skipped with a warning if unavailable."""
    scene = scene or bpy.context.scene
    p = dict(COMP_DEFAULTS)
    unknown = [k for k in params if k not in p]
    if unknown:
        print(f"[compositor] note: ignoring unknown parameters {unknown}")
    p.update({k: v for k, v in params.items() if k in COMP_DEFAULTS and v is not None})

    # mist pass + world mist range
    for vl in scene.view_layers:
        _set(vl, "use_pass_mist", True)
    if scene.world is not None:
        ms = scene.world.mist_settings
        if p["mist_start"] is not None:
            ms.start = float(p["mist_start"])
        if p["mist_depth"] is not None:
            ms.depth = float(p["mist_depth"])
        if p["mist_falloff"] is not None:
            _set(ms, "falloff", p["mist_falloff"])

    try:
        tree, legacy = _new_comp_tree(scene, "CorridorCompositor")
    except Exception as exc:
        print(f"[compositor] WARNING: cannot create compositor tree ({exc}) - compositing disabled")
        scene.render.use_compositing = False
        return None
    T = _Tree(tree)

    rl = T.new("CompositorNodeRLayers")
    if rl is None:
        scene.render.use_compositing = False
        return None
    _set(rl, "scene", scene, quiet=True)
    img = rl.outputs["Image"]

    # ---- 1. atmospheric haze ------------------------------------------------
    if p["haze_strength"] > 0.0:
        mist = rl.outputs.get("Mist")
        if mist is None or not getattr(mist, "enabled", True):
            print("[compositor] WARNING: no Mist output on Render Layers - haze skipped")
        else:
            fac = T.math('MULTIPLY', mist, float(p["haze_strength"]), clamp=True)
            if fac is not None:
                out = T.mix('MIX', fac, img, tuple(p["haze_color"]), label="Atmospheric haze")
                if out is not None:
                    img = out

    # ---- 2. bloom ----------------------------------------------------------
    if p["glare"] and p["glare_strength"] > 0.0:
        g = T.new("CompositorNodeGlare", "Bloom")
        if g is not None:
            if g.inputs.get("Type") is not None:          # 5.x: everything is a socket
                T.set_first(g, "Type", ["Bloom", "Fog Glow"])
                T.set_first(g, "Quality", ["High", "Medium"])
                T.set_in(g, "Highlights Threshold", float(p["glare_threshold"]))
                T.set_in(g, "Highlights Smoothness", float(p["glare_smoothness"]))
                T.set_in(g, "Clamp Highlights", True)
                T.set_in(g, "Maximum Highlights", 30.0)
                T.set_in(g, "Strength", float(p["glare_strength"]))
                T.set_in(g, "Saturation", float(p["glare_saturation"]))
                T.set_in(g, "Size", float(p["glare_size"]))
            else:                                          # legacy properties
                _set_first(g, "glare_type", ['BLOOM', 'FOG_GLOW'])
                _set(g, "quality", 'HIGH', quiet=True)
                _set(g, "threshold", float(p["glare_threshold"]), quiet=True)
                _set(g, "mix", -1.0 + float(p["glare_strength"]), quiet=True)
                _set(g, "size", 7, quiet=True)
            if T.link(img, g.inputs["Image"]):
                img = g.outputs["Image"]

    # ---- 3. lens distortion / chromatic aberration -------------------------
    if abs(p["lens_distortion"]) > 0.0 or p["lens_dispersion"] > 0.0:
        ld = T.new("CompositorNodeLensdist", "Lens")
        if ld is not None:
            if ld.inputs.get("Type") is not None:
                T.set_first(ld, "Type", ["Radial"])
            T.set_first(ld, "Distortion", [float(p["lens_distortion"])]) \
                if ld.inputs.get("Distortion") is not None else None
            if ld.inputs.get("Dispersion") is not None:
                T.set_in(ld, "Dispersion", float(p["lens_dispersion"]))
            if ld.inputs.get("Fit") is not None:
                T.set_in(ld, "Fit", True)
            else:
                _set(ld, "use_fit", True, quiet=True)
            if T.link(img, ld.inputs["Image"]):
                img = ld.outputs["Image"]

    # ---- 4. vignette ---------------------------------------------------------
    if p["vignette"] > 0.0:
        em = T.new("CompositorNodeEllipseMask", "Vignette mask")
        bl = T.new("CompositorNodeBlur", "Vignette blur") if em is not None else None
        if em is not None and bl is not None:
            ok = True
            if em.inputs.get("Size") is not None:
                ok &= T.set_in(em, "Size", (1.08, 1.08))
                T.set_in(em, "Position", (0.5, 0.5))
            else:
                ok &= _set(em, "width", 1.08, quiet=True) and _set(em, "height", 1.08, quiet=True)
            blur_px = 0.16 * scene.render.resolution_x
            if bl.inputs.get("Size") is not None and bl.inputs["Size"].type == 'VECTOR':
                ok &= T.set_in(bl, "Size", (blur_px, blur_px))
                if bl.inputs.get("Type") is not None:
                    T.set_first(bl, "Type", ["Fast Gaussian", "Gaussian"])
                if bl.inputs.get("Extend Bounds") is not None:
                    T.set_in(bl, "Extend Bounds", False)
            else:
                _set(bl, "filter_type", 'FAST_GAUSS', quiet=True)
                _set(bl, "size_x", int(blur_px), quiet=True)
                _set(bl, "size_y", int(blur_px), quiet=True)
            mask_out = em.outputs[0]
            ok &= T.link(mask_out, bl.inputs["Image"])
            if ok:
                # factor = (1 - mask) * strength ; image *= (1 - factor)
                inv = T.math('SUBTRACT', 1.0, bl.outputs["Image"], clamp=True)
                fac = T.math('MULTIPLY', inv, float(p["vignette"]), clamp=True) if inv is not None else None
                if fac is not None:
                    out = T.mix('MULTIPLY', fac, img, (0.0, 0.0, 0.0, 1.0), label="Vignette")
                    if out is not None:
                        img = out

    # ---- 5. grade ------------------------------------------------------------
    if (abs(p["saturation"] - 1.0) > 1e-4 or abs(p["contrast"] - 1.0) > 1e-4
            or abs(p["gain"] - 1.0) > 1e-4 or abs(p["gamma"] - 1.0) > 1e-4):
        cc = T.new("CompositorNodeColorCorrection", "Grade")
        if cc is not None and cc.inputs.get("Master Saturation") is not None:
            T.set_in(cc, "Master Saturation", float(p["saturation"]))
            T.set_in(cc, "Master Contrast", float(p["contrast"]))
            T.set_in(cc, "Master Gain", float(p["gain"]))
            T.set_in(cc, "Master Gamma", float(p["gamma"]))
            if T.link(img, cc.inputs["Image"]):
                img = cc.outputs["Image"]
        elif cc is not None:      # legacy property based node
            _set(cc, "master_saturation", float(p["saturation"]), quiet=True)
            _set(cc, "master_contrast", float(p["contrast"]), quiet=True)
            _set(cc, "master_gain", float(p["gain"]), quiet=True)
            _set(cc, "master_gamma", float(p["gamma"]), quiet=True)
            if T.link(img, cc.inputs["Image"]):
                img = cc.outputs["Image"]
        else:
            hs = T.new("CompositorNodeHueSat", "Saturation")
            if hs is not None and hs.inputs.get("Saturation") is not None:
                T.set_in(hs, "Saturation", float(p["saturation"]))
                if T.link(img, hs.inputs["Image"]):
                    img = hs.outputs["Image"]

    # ---- output ------------------------------------------------------------
    ok = False
    if not legacy:
        try:
            tree.interface.new_socket(name="Image", in_out='OUTPUT', socket_type='NodeSocketColor')
            go = tree.nodes.new("NodeGroupOutput")
            go.location = (T.x, 0)
            go.is_active_output = True
            ok = T.link(img, go.inputs[0])
        except Exception as exc:
            print(f"[compositor] WARNING: group output failed: {exc}")
    else:
        comp = T.new("CompositorNodeComposite")
        if comp is not None:
            ok = T.link(img, comp.inputs[0])
    if not ok:
        print("[compositor] WARNING: could not wire compositor output - compositing disabled")
        scene.render.use_compositing = False
        return None
    scene.render.use_compositing = True
    return tree
