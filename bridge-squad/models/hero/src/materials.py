"""Hero soldier material library (owner: Materials & Textures artist).

API (see PLAN.md §6):
    SPEC                      dict name -> {"color", "rough", "metal", "tex", "scale", "normal_strength", ...}
    build(name)               -> bpy.types.Material  (full PBR material, real CC0 textures via UV "UVMap")
    apply_library(objects)    replaces every material slot whose material name is in SPEC with build(name)

Design rules
* Textures are ambientCG CC0 sets in models/hero/textures/<AssetId>/ (fetched by src/fetch_textures.py).
* The palette colour stays the perceived average colour: the photo albedo is reduced to luminance,
  divided by its own mean (precomputed in textures/STATS.json) and multiplied onto the palette colour,
  with a per-material "detail" contrast. So a brown leather photo can't make boots orange.
* Roughness map is re-centred on SPEC["rough"]; normal map (OpenGL) via Normal Map node on "UVMap".
* Only bake-safe nodes (image textures, math, mix, normal map, noise). No Geometry/AO/Pointiness,
  no light-path tricks. If a texture folder is missing, the material falls back to a flat colour,
  so modelers are never blocked.
"""
import json
import os

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
TEX_DIR = os.path.normpath(os.path.join(HERE, "..", "textures"))
UV_NAME = "UVMap"

# ---------------------------------------------------------------------------------------------
# SPEC. "tex": ambientCG asset id or None. "scale": texture repeats per UV unit (1 UV = 0.5 m),
# "detail": 0..1 how much of the photo's light/dark variation survives on the albedo,
# "rough_var": how much the roughness map swings around "rough", "normal_strength": normal map.
# Optional: "noise": procedural (bake-safe) mottling amount for untextured materials,
# "emission": strength of self-illumination (lens), "coat": clearcoat weight.
# ---------------------------------------------------------------------------------------------
SPEC = {
    "M_helmet_blue":   dict(color="#2F6BFF", rough=0.40, metal=0.10, tex="PaintedMetal002", scale=2.4, normal_strength=0.45, detail=0.22, rough_var=0.60, coat=0.20, grime=0.10),
    "M_jacket_blue":   dict(color="#3C7FE0", rough=0.86, metal=0.0, tex="Fabric061", scale=5.5, normal_strength=0.6, detail=0.95, rough_var=0.15, grime=0.12),
    "M_pants_navy":    dict(color="#283A63", rough=0.88, metal=0.0, tex="Fabric069", scale=5.5, normal_strength=0.55, detail=0.85, rough_var=0.15, grime=0.12),
    "M_vest_tan":      dict(color="#C7A36B", rough=0.80, metal=0.0, tex="Fabric062", scale=6.0, normal_strength=0.6, detail=0.90, rough_var=0.15, grime=0.14),
    "M_strap_tan":     dict(color="#A98654", rough=0.78, metal=0.0, tex="Fabric079", scale=9.0, normal_strength=0.6, detail=0.80, rough_var=0.15, grime=0.08),
    "M_backpack_blue": dict(color="#2C5BC4", rough=0.85, metal=0.0, tex="Fabric066", scale=4.5, normal_strength=0.6, detail=0.95, rough_var=0.15, grime=0.14),
    "M_leather_brown": dict(color="#5A3E2B", rough=0.52, metal=0.0, tex="Leather014", scale=3.6, normal_strength=0.6, detail=0.90, rough_var=0.60, grime=0.10),
    "M_rubber_dark":   dict(color="#2B2D33", rough=0.80, metal=0.0, tex="Rubber004", scale=4.0, normal_strength=0.5, detail=0.70, rough_var=0.30, grime=0.06),
    "M_glove":         dict(color="#3B4252", rough=0.58, metal=0.0, tex="Leather030", scale=5.0, normal_strength=0.55, detail=0.85, rough_var=0.50, grime=0.06),
    "M_skin":          dict(color="#F0BE96", rough=0.55, metal=0.0, tex=None, noise=0.03,
                            # warm stylized blush: (world centre, radius m, strength) — anchors from PLAN §3
                            blush_color="#E8907E", warm=0.07,
                            blush=[((-0.078, 0.118, 0.712), 0.050, 0.55), ((0.078, 0.118, 0.712), 0.050, 0.55),
                                   ((0.0, 0.160, 0.740), 0.030, 0.35),
                                   ((-0.142, 0.0, 0.770), 0.040, 0.45), ((0.142, 0.0, 0.770), 0.040, 0.45),
                                   ((0.0, 0.130, 0.655), 0.035, 0.15)]),
    "M_hair":          dict(color="#4A3022", rough=0.70, metal=0.0, tex=None, noise=0.10),
    "M_eye_white":     dict(color="#F4F1EA", rough=0.25, metal=0.0, tex=None),
    "M_eye_iris":      dict(color="#3B6EA8", rough=0.15, metal=0.0, tex=None),
    "M_eye_pupil":     dict(color="#1E2430", rough=0.10, metal=0.0, tex=None),
    "M_mouth":         dict(color="#B5655A", rough=0.50, metal=0.0, tex=None),
    "M_goggle_lens":   dict(color="#FFB23E", rough=0.08, metal=0.0, tex=None, emission=0.15, coat=0.5),
    "M_metal_gun":     dict(color="#3A414D", rough=0.38, metal=0.85, tex="Metal046A", scale=4.0, normal_strength=0.5, detail=0.85, rough_var=0.60, grime=0.06),
    "M_polymer_gun":   dict(color="#2E333B", rough=0.62, metal=0.0, tex="Plastic018A", scale=5.0, normal_strength=0.45, detail=0.70, rough_var=0.40, grime=0.06),
    "M_gun_accent":    dict(color="#2F6BFF", rough=0.40, metal=0.10, tex="PaintedMetal002", scale=5.0, normal_strength=0.4, detail=0.30, rough_var=0.50, coat=0.20),
    "M_metal_bright":  dict(color="#B9BEC6", rough=0.30, metal=1.0, tex="Metal032", scale=5.0, normal_strength=0.4, detail=0.60, rough_var=0.50),
    "M_emblem":        dict(color="#FFD54A", rough=0.40, metal=0.0, tex=None),
    "M_lens_glow":     dict(color="#7FE8FF", rough=0.05, metal=0.0, tex=None, emission=3.0, coat=0.3),
    "M_cloth_olive":   dict(color="#6F7A4E", rough=0.88, metal=0.0, tex="Fabric066", scale=4.5, normal_strength=0.6, detail=0.95, rough_var=0.15, grime=0.14),
}

_DEFAULTS = dict(color="#808080", rough=0.6, metal=0.0, tex=None, scale=2.0, normal_strength=0.6,
                 detail=0.5, rough_var=0.2, noise=0.0, emission=0.0, coat=0.0, grime=0.0,
                 blush=(), blush_color="#E8907E", warm=0.0)

_STATS = None


def hex_to_linear(h):
    h = h.lstrip("#")
    out = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255.0
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return (out[0], out[1], out[2], 1.0)


def _spec(name):
    s = dict(_DEFAULTS)
    s.update(SPEC[name])
    return s


# ---------------------------------------------------------------------------------------------
# texture lookup
# ---------------------------------------------------------------------------------------------
def _find_map(asset, kind):
    """kind: Color | Roughness | NormalGL | Metalness | AmbientOcclusion. Returns path or None."""
    d = os.path.join(TEX_DIR, asset)
    if not os.path.isdir(d):
        return None
    for f in sorted(os.listdir(d)):
        low = f.lower()
        if low.endswith((".jpg", ".jpeg", ".png")) and ("_" + kind.lower() + ".") in low:
            return os.path.join(d, f)
    return None


def _load_image(path, non_color):
    name = os.path.basename(path)
    img = bpy.data.images.get(name)
    if img is None or os.path.normpath(bpy.path.abspath(img.filepath)) != os.path.normpath(path):
        img = bpy.data.images.load(path, check_existing=True)
    img.colorspace_settings.name = "Non-Color" if non_color else "sRGB"
    return img


def _stats():
    global _STATS
    if _STATS is None:
        p = os.path.join(TEX_DIR, "STATS.json")
        try:
            with open(p) as f:
                _STATS = json.load(f)
        except (OSError, ValueError):
            _STATS = {}
    return _STATS


def _image_means(asset, color_path, rough_path):
    """Mean linear luminance of the albedo and mean roughness (cached in STATS.json by fetch script;
    computed here as a fallback)."""
    st = _stats().get(asset)
    if st:
        return st["lum_mean"], st.get("rough_mean", 0.5)
    import numpy as np
    lum = 0.5
    rough = 0.5
    if color_path:
        img = _load_image(color_path, False)
        px = np.empty(len(img.pixels), dtype=np.float32)
        img.pixels.foreach_get(px)
        px = px.reshape(-1, 4)[:, :3]
        lin = np.where(px <= 0.04045, px / 12.92, ((px + 0.055) / 1.055) ** 2.4)
        lum = float((lin @ np.array([0.2126, 0.7152, 0.0722])).mean())
    if rough_path:
        img = _load_image(rough_path, True)
        px = np.empty(len(img.pixels), dtype=np.float32)
        img.pixels.foreach_get(px)
        rough = float(px.reshape(-1, 4)[:, 0].mean())
    _stats()[asset] = {"lum_mean": lum, "rough_mean": rough}
    return lum, rough


# ---------------------------------------------------------------------------------------------
# node helpers
# ---------------------------------------------------------------------------------------------
def _n(nt, typ, x, y, label=None):
    n = nt.nodes.new(typ)
    n.location = (x, y)
    if label:
        n.label = label
    return n


def _math(nt, op, a, b, x, y, clamp=False):
    m = _n(nt, "ShaderNodeMath", x, y)
    m.operation = op
    m.use_clamp = clamp
    for i, v in enumerate((a, b)):
        if isinstance(v, (int, float)):
            m.inputs[i].default_value = v
        else:
            nt.links.new(v, m.inputs[i])
    return m.outputs[0]


def _set_input(bsdf, names, value):
    for nm in names:
        if nm in bsdf.inputs:
            bsdf.inputs[nm].default_value = value
            return bsdf.inputs[nm]
    return None


def _inp(bsdf, *names):
    for nm in names:
        if nm in bsdf.inputs:
            return bsdf.inputs[nm]
    return None


def build(name):
    """Build (or rebuild in place) the full material `name`. Unknown names get a neutral material."""
    s = _spec(name) if name in SPEC else dict(_DEFAULTS)
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    if mat.node_tree is None:
        mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    col = hex_to_linear(s["color"])
    mat.diffuse_color = col  # viewport / workbench colour
    mat.roughness = s["rough"]
    mat.metallic = s["metal"]

    out = _n(nt, "ShaderNodeOutputMaterial", 900, 0)
    bsdf = _n(nt, "ShaderNodeBsdfPrincipled", 550, 0)
    nt.links.new(bsdf.outputs[0], out.inputs["Surface"])
    bsdf.inputs["Base Color"].default_value = col
    bsdf.inputs["Roughness"].default_value = s["rough"]
    bsdf.inputs["Metallic"].default_value = s["metal"]
    if s["coat"]:
        _set_input(bsdf, ("Coat Weight", "Clearcoat"), s["coat"])
        _set_input(bsdf, ("Coat Roughness", "Clearcoat Roughness"), 0.15)
    if s["emission"]:
        e = _inp(bsdf, "Emission Color", "Emission")
        if e is not None:
            e.default_value = col
        _set_input(bsdf, ("Emission Strength",), s["emission"])

    asset = s["tex"]
    cpath = _find_map(asset, "Color") if asset else None
    rpath = _find_map(asset, "Roughness") if asset else None
    npath = _find_map(asset, "NormalGL") if asset else None

    if cpath or rpath or npath:
        uv = _n(nt, "ShaderNodeUVMap", -1400, 0)
        uv.uv_map = UV_NAME
        mp = _n(nt, "ShaderNodeMapping", -1200, 0)
        sc = s["scale"]
        mp.inputs["Scale"].default_value = (sc, sc, sc)
        nt.links.new(uv.outputs["UV"], mp.inputs["Vector"])
        vec = mp.outputs["Vector"]
        lum_mean, rough_mean = _image_means(asset, cpath, rpath)

        if cpath:
            tc = _n(nt, "ShaderNodeTexImage", -950, 300, "albedo")
            tc.image = _load_image(cpath, False)
            nt.links.new(vec, tc.inputs["Vector"])
            bw = _n(nt, "ShaderNodeRGBToBW", -650, 300)
            nt.links.new(tc.outputs["Color"], bw.inputs[0])
            # rel = lum / mean ; k = 1 + (rel - 1) * detail ; clamp to [0.25, 1.9]
            rel = _math(nt, "MULTIPLY", bw.outputs[0], 1.0 / max(lum_mean, 1e-4), -480, 300)
            d = _math(nt, "SUBTRACT", rel, 1.0, -320, 300)
            d = _math(nt, "MULTIPLY", d, s["detail"], -160, 300)
            k = _math(nt, "ADD", d, 1.0, 0, 300)
            k = _math(nt, "MAXIMUM", k, 0.25, 120, 300)
            k = _math(nt, "MINIMUM", k, 1.9, 240, 300)
            if s["grime"] > 0:
                # large, soft UV-space mottling (dust/wear) -> breaks the uniform CG look; mean stays 1
                gz = _n(nt, "ShaderNodeTexNoise", -650, 600, "grime")
                gz.inputs["Scale"].default_value = 1.6
                gz.inputs["Detail"].default_value = 4.0
                gz.inputs["Roughness"].default_value = 0.55
                nt.links.new(uv.outputs["UV"], gz.inputs["Vector"])
                g = _math(nt, "SUBTRACT", gz.outputs["Fac"], 0.5, -450, 600)
                g = _math(nt, "MULTIPLY", g, 1.6 * s["grime"], -300, 600)
                g = _math(nt, "ADD", g, 1.0, -150, 600)
                k = _math(nt, "MULTIPLY", k, g, 360, 450)
            mix = _n(nt, "ShaderNodeMix", 360, 300, "tint")
            mix.data_type = "RGBA"
            mix.blend_type = "MULTIPLY"
            mix.inputs["Factor"].default_value = 1.0
            mix.inputs[6].default_value = col  # A
            # k is a float; feed into B colour socket (auto-converted to grey)
            nt.links.new(k, mix.inputs[7])
            nt.links.new(mix.outputs[2], bsdf.inputs["Base Color"])

        if rpath:
            tr = _n(nt, "ShaderNodeTexImage", -950, -50, "roughness")
            tr.image = _load_image(rpath, True)
            nt.links.new(vec, tr.inputs["Vector"])
            r = _math(nt, "SUBTRACT", tr.outputs["Color"], rough_mean, -650, -50)
            r = _math(nt, "MULTIPLY", r, s["rough_var"], -480, -50)
            r = _math(nt, "ADD", r, s["rough"], -320, -50, clamp=True)
            nt.links.new(r, bsdf.inputs["Roughness"])

        if npath and s["normal_strength"] > 0:
            tn = _n(nt, "ShaderNodeTexImage", -950, -400, "normal")
            tn.image = _load_image(npath, True)
            nt.links.new(vec, tn.inputs["Vector"])
            nm = _n(nt, "ShaderNodeNormalMap", -320, -400)
            nm.space = "TANGENT"
            nm.uv_map = UV_NAME
            nm.inputs["Strength"].default_value = s["normal_strength"]
            nt.links.new(tn.outputs["Color"], nm.inputs["Color"])
            nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])

    elif s["noise"] > 0:
        # subtle, bake-safe procedural mottling (object space so it doesn't depend on UVs)
        tco = _n(nt, "ShaderNodeTexCoord", -900, 200)
        nz = _n(nt, "ShaderNodeTexNoise", -700, 200)
        nz.inputs["Scale"].default_value = 7.0
        nz.inputs["Detail"].default_value = 1.0
        nt.links.new(tco.outputs["Object"], nz.inputs["Vector"])
        k = _math(nt, "SUBTRACT", nz.outputs["Fac"], 0.5, -450, 200)
        k = _math(nt, "MULTIPLY", k, 2.0 * s["noise"], -300, 200)
        k = _math(nt, "ADD", k, 1.0, -150, 200)
        mix = _n(nt, "ShaderNodeMix", 100, 200, "tint")
        mix.data_type = "RGBA"
        mix.blend_type = "MULTIPLY"
        mix.inputs["Factor"].default_value = 1.0
        mix.inputs[6].default_value = col
        nt.links.new(k, mix.inputs[7])
        nt.links.new(mix.outputs[2], bsdf.inputs["Base Color"])

    if s["blush"]:
        # world-position spherical falloffs (bake-safe: the hi mesh is baked in place)
        geo = _n(nt, "ShaderNodeNewGeometry", -900, -700)
        acc = None
        for i, (c, r, w) in enumerate(s["blush"]):
            d = _n(nt, "ShaderNodeVectorMath", -700, -700 - 120 * i)
            d.operation = "DISTANCE"
            d.inputs[1].default_value = c
            nt.links.new(geo.outputs["Position"], d.inputs[0])
            f = _math(nt, "DIVIDE", d.outputs["Value"], r, -550, -700 - 120 * i)
            f = _math(nt, "SUBTRACT", 1.0, f, -420, -700 - 120 * i, clamp=True)
            f = _math(nt, "MULTIPLY", f, f, -300, -700 - 120 * i)
            f = _math(nt, "MULTIPLY", f, w, -180, -700 - 120 * i)
            acc = f if acc is None else _math(nt, "ADD", acc, f, -60, -700 - 120 * i)
        if s["warm"]:
            acc = _math(nt, "ADD", acc, s["warm"], 0, -650)
        acc = _math(nt, "MINIMUM", acc, 1.0, 60, -700)
        bl = _n(nt, "ShaderNodeMix", 250, -500, "blush")
        bl.data_type = "RGBA"
        bl.blend_type = "MIX"
        nt.links.new(acc, bl.inputs["Factor"])
        cur = bsdf.inputs["Base Color"].links[0].from_socket if bsdf.inputs["Base Color"].is_linked else None
        if cur is not None:
            nt.links.new(cur, bl.inputs[6])
        else:
            bl.inputs[6].default_value = col
        bl.inputs[7].default_value = hex_to_linear(s["blush_color"])
        nt.links.new(bl.outputs[2], bsdf.inputs["Base Color"])

    mat["hero_spec"] = json.dumps(SPEC.get(name, {}))
    return mat


def apply_library(objects):
    """Replace every placeholder slot (material named like a SPEC entry) with the full material."""
    built = {}
    for ob in objects:
        if getattr(ob, "type", None) != "MESH":
            continue
        for slot in ob.material_slots:
            m = slot.material
            if m is None:
                continue
            base = m.name.split(".")[0] if m.name not in SPEC else m.name
            if base not in SPEC:
                continue
            if base not in built:
                built[base] = build(base)
            if slot.material is not built[base]:
                slot.material = built[base]
    return built


def build_all():
    return {n: build(n) for n in SPEC}


if __name__ == "__main__":
    mats = build_all()
    print("built", len(mats), "materials:", ", ".join(sorted(mats)))
