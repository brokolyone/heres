"""Tower (pylon) of the suspension bridge, art-deco style, with stay cables.

Origin (0,0,0) = road level at the tower centre. Columns at x=+-6.6 (outside the road),
cross beams at z>=11, cables fan forward/backward along Y to the deck edges (x=+-5.85, y up to +-20).
Run: python3 bridge-squad/models/src/tower.py
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy  # noqa: E402
import env_lib as L  # noqa: E402

L.reset()

M_RED = L.material("BridgeRed", "#D8332E", rough=0.45)
M_RED_DARK = L.material("BridgeRedShade", "#B02B28", rough=0.5)
M_CABLE = L.material("CableRed", "#C93A31", rough=0.4)
M_STONE = L.material("PierStone", "#D7CBB8", rough=0.85)
M_WARN = L.material("WarningLight", "#FF5A4A", rough=0.3, emit="#FF4433", emit_strength=4.0)

CX = 6.6
b = L.Builder()

# (z0, z1, size_x, size_y) column stages; each one steps in (art-deco setbacks)
STAGES = [(-4.0, 9.0, 1.6, 2.0), (9.0, 14.6, 1.36, 1.72), (14.6, 19.2, 1.14, 1.44), (19.2, 20.4, 0.9, 1.16)]

for s in (-1, 1):
    x = s * CX
    # stone pier in the water
    b.box(x - 1.5, x + 1.5, -1.9, 1.9, -9.0, -4.0, M_STONE, skip=("-z",))
    b.box(x - 1.1, x + 1.1, -1.5, 1.5, -4.0, -3.7, M_STONE, skip=("-z",))
    for i, (z0, z1, sx, sy) in enumerate(STAGES):
        b.box(x - sx / 2, x + sx / 2, -sy / 2, sy / 2, z0, z1, M_RED, skip=("-z",))
        if i < 3:
            # cornice ledge at top of each stage
            b.box(x - sx / 2 - 0.08, x + sx / 2 + 0.08, -sy / 2 - 0.08, sy / 2 + 0.08,
                  z1 - 0.28, z1, M_RED_DARK)
            # vertical art-deco fins on front/back (+-y) faces
            for fx in (-sx * 0.26, sx * 0.26):
                for fy in (-1, 1):
                    y0 = fy * sy / 2
                    b.box(x + fx - 0.09, x + fx + 0.09, min(y0, y0 + fy * 0.1), max(y0, y0 + fy * 0.1),
                          z0 + 0.4, z1 - 0.28, M_RED_DARK, skip=("-z", "+z", "-y" if fy > 0 else "+y"))
            # one fin on the outer side face
            ox = x + s * sx / 2
            b.box(min(ox, ox + s * 0.1), max(ox, ox + s * 0.1), -0.1, 0.1, z0 + 0.4, z1 - 0.28,
                  M_RED_DARK, skip=("-z", "+z", "-x" if s > 0 else "+x"))
    # stepped pyramid cap + warning light
    b.cone((x, 0, 20.4), 0.75, 0.52, M_RED_DARK, sides=4, roll=math.pi / 4)
    b.prism((x, 0, 21.1), (x, 0, 21.45), 0.13, M_WARN, sides=6, caps=True, smooth=False)

# ---------------------------------------------------------------- cross beams (z >= 11)
BEAMS = [(12.1, 13.3, 1.1), (16.4, 17.4, 0.95), (19.4, 20.3, 0.85)]  # lowest part of any beam >= 11.2
for z0, z1, d in BEAMS:
    inner = CX - 0.5
    b.box(-inner, inner, -d / 2, d / 2, z0, z1, M_RED)
    # stepped under-band (art-deco layering)
    b.box(-inner + 0.6, inner - 0.6, -d / 2 + 0.12, d / 2 - 0.12, z0 - 0.3, z0, M_RED_DARK, skip=("+z",))
    b.box(-inner + 1.5, inner - 1.5, -d / 2 + 0.22, d / 2 - 0.22, z0 - 0.55, z0 - 0.3, M_RED_DARK, skip=("+z",))
    # corner knee blocks
    for s in (-1, 1):
        xi = s * (inner - 0.3)
        b.box(xi - 0.3, xi + 0.3, -d / 2 + 0.05, d / 2 - 0.05, z0 - 0.9, z0, M_RED_DARK, skip=("+z",))
    # vertical panel ribs on beam front/back
    for k in (-2, -1, 0, 1, 2):
        rx = k * 2.0
        for fy in (-1, 1):
            y0 = fy * d / 2
            b.box(rx - 0.1, rx + 0.1, min(y0, y0 + fy * 0.07), max(y0, y0 + fy * 0.07), z0 + 0.15, z1 - 0.15,
                  M_RED_DARK, skip=("-y" if fy > 0 else "+y",))

# top crown above the upper beam
b.box(-2.4, 2.4, -0.38, 0.38, 20.3, 20.75, M_RED_DARK, skip=("-z",))
b.box(-1.2, 1.2, -0.3, 0.3, 20.75, 21.15, M_RED, skip=("-z",))

# ---------------------------------------------------------------- stay cables
DECK_X = 5.85
for s in (-1, 1):
    for fy in (-1, 1):
        for i, yd in enumerate((4.0, 8.0, 12.0, 16.0, 20.0)):
            top = (s * CX, fy * 0.35, 18.9 - 0.85 * (4 - i))  # outermost cable anchors highest
            bot = (s * DECK_X, fy * yd, 0.15)
            b.prism(top, bot, 0.055 if i < 4 else 0.07, M_CABLE, sides=6, caps=False, smooth=True)
            b.box(s * DECK_X - 0.14, s * DECK_X + 0.14, fy * yd - 0.18, fy * yd + 0.18, 0.06, 0.3,
                  M_RED_DARK, skip=("-z",))
        # saddle block where cables meet the column
        b.box(s * CX - 0.3, s * CX + 0.3, fy * 0.55 - 0.18, fy * 0.55 + 0.18, 15.0, 19.1, M_RED_DARK)

tower = b.build("tower")
L.export([tower], "tower")

# ---------------------------------------------------------------- preview with bridge segments for context
seg_path = os.path.join(L.MODELS_DIR, "bridge_segment.glb")
if os.path.exists(seg_path):
    for i in range(-2, 3):
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=seg_path)
        for ob in set(bpy.data.objects) - before:
            if ob.parent is None:
                ob.location.y += 20.0 * i
L.preview_setup(water=True, water_z=-9.0)
L.game_camera((0, 6, 6), 44, pitch_deg=45, lens=32)
L.render("tower")

dbg = os.environ.get("PREVIEW_DEBUG_DIR")
if dbg:
    L.camera((34, -26, 14), (0, 0, 6), lens=35)
    L.render(os.path.join(dbg, "tower_side.png"), samples=32)
