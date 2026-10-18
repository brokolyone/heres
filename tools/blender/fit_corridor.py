"""Fit the corridor's look-dev knobs to art/corridor/reference.png, region by region.

    python3 tools/blender/fit_corridor.py tune.json [iterations] [samples]

tune.json holds overrides for build_corridor.py's T table (start from {}). Each iteration
renders a half-size frame, compares the mean colour of fixed regions with the reference
and moves the knob that region depends on by the linear-light ratio (damped). Albedos are
capped at 0.92; camera-only multipliers and fill lights are free. The file is rewritten
after every pass; paste the result into T when happy. Needs numpy and Pillow.
"""
import json
import os
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
REF = np.asarray(Image.open(f"{REPO}/art/corridor/reference.png").convert("RGB")).astype(float)

# (x0, y0, x1, y1) in reference pixels
REGIONS = {
    "sky_top": (150, 10, 400, 60), "sky_mid": (150, 120, 400, 150), "sky_horizon": (150, 225, 400, 250),
    "trees": (150, 268, 400, 282), "field_far": (150, 285, 400, 290), "field_far2": (150, 291, 400, 300),
    "field_mid": (150, 305, 400, 345), "field_near": (150, 400, 400, 440),
    "mullion_a_side": (58, 150, 90, 400), "mullion_a_front": (104, 150, 140, 400),
    "mullion_b": (421, 150, 443, 380), "ceiling_near": (640, 10, 900, 60), "ceiling_far": (840, 150, 905, 235),
    "glass_far": (760, 200, 880, 280), "floor_mid": (760, 380, 900, 470), "floor_right": (935, 420, 1000, 470),
    "floor_blue": (520, 445, 640, 473), "right_wall": (955, 250, 1005, 380), "cap": (446, 10, 466, 100),
}
ALBEDO = {
    "frame": ["mullion_a_side", "mullion_b"], "channel": ["mullion_a_front"],
    "floor_shade": ["floor_right"],
}
MULT = {
    "field_mul": ["field_far"], "far_mul": ["field_far2"], "mid_mul": ["field_mid"], "plant_mul": ["field_near"],
    "sky_mul": ["sky_top", "sky_mid", "sky_horizon"], "tree_mul": ["trees"], "glass_graze": ["glass_far"],
    "ceiling_fill": ["ceiling_near", "ceiling_far"], "wall_fill": ["right_wall"], "sun_patch": ["floor_mid"],
    "reflect_window": ["floor_blue"],
}
CAPS = {"reflect_window": 0.9, "glass_graze": 2.0, "ceiling_fill": 40.0, "wall_fill": 40.0, "sun_patch": 40.0}
SCALAR = {"wall_fill", "reflect_window", "sun_patch"}   # strength only, the colour stays as built
DAMP = 0.85


def lin(c):
    c = np.asarray(c, float) / 255
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def srgb(v):
    v = np.clip(np.asarray(v, float), 0, 1)
    return np.where(v <= 0.0031308, v * 12.92, 1.055 * v ** (1 / 2.4) - 0.055) * 255


def mean(img, names):
    return np.mean([img[y0:y1, x0:x1].reshape(-1, 3).mean(0) for x0, y0, x1, y1 in (REGIONS[n] for n in names)], 0)


def render(tune, samples, workdir):
    path = os.path.join(workdir, "tune.json")
    out = os.path.join(workdir, "fit.png")
    json.dump(dict(tune, grade_gamma=1.0), open(path, "w"))
    subprocess.run(["blender", "-b", "--factory-startup", "--python", f"{REPO}/tools/blender/build_corridor.py",
                    "--", f"{REPO}/art/corridor", "--render", out, "--scale", "0.5", "--samples", str(samples),
                    "--no-save", "--tune", path], check=True, capture_output=True)
    img = Image.open(out).convert("RGB").resize((REF.shape[1], REF.shape[0]), Image.LANCZOS)
    return np.asarray(img).astype(float)


def current(tune, key):
    if key in tune:
        return tune[key]
    # fall back to the script's own defaults
    src = open(f"{REPO}/tools/blender/build_corridor.py").read()
    table = src[src.index("T = {"):src.index("\n}\n", src.index("T = {")) + 2]
    scope = {}
    exec(table, scope)
    v = scope["T"][key]
    return v if isinstance(v, (int, float)) else list(v)


def main():
    path = sys.argv[1]
    iters = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    samples = int(sys.argv[3]) if len(sys.argv) > 3 else 32
    tune = json.load(open(path)) if os.path.exists(path) else {}
    with tempfile.TemporaryDirectory() as work:
        for it in range(iters):
            img = render(tune, samples, work)
            errs = {}
            for key, names in list(ALBEDO.items()) + list(MULT.items()):
                ref, got = mean(REF, names), mean(img, names)
                errs[key] = float(np.abs(ref - got).mean())
                ratio = np.clip((lin(ref) + 1e-3) / (lin(got) + 1e-3), 0.3, 3.0) ** DAMP
                if key in ALBEDO:
                    new = np.clip(lin(current(tune, key)) * ratio, 0.005, 0.92)
                    tune[key] = [int(round(v)) for v in srgb(new)]
                elif key in SCALAR:
                    tune[key] = round(float(np.clip(current(tune, key) * ratio.mean(), 0.01, CAPS.get(key, 4.0))), 4)
                else:
                    new = np.clip(np.asarray(current(tune, key), float) * ratio, 0.01, CAPS.get(key, 4.0))
                    tune[key] = [round(float(v), 4) for v in new]
            print(f"pass {it}: mean error {np.mean(list(errs.values())):.2f}",
                  {k: round(v, 1) for k, v in errs.items()}, flush=True)
            json.dump(tune, open(path, "w"), indent=1)


main()
