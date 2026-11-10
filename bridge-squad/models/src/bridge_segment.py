"""Bridge segment: seamless 20 m piece of the suspension-bridge deck (y 0..20).

Road top at z=0, playfield x -5..5 kept clear. Run: python3 bridge-squad/models/src/bridge_segment.py
Add --debug to also render a side view into the scratch dir given by $PREVIEW_DEBUG_DIR.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy  # noqa: E402
import env_lib as L  # noqa: E402

LEN = 20.0

L.reset()

M_ASPH = L.material("Asphalt", "#62667A", rough=0.9)
M_LINE = L.material("RoadLine", "#F4F0E6", rough=0.7)
M_CURB = L.material("CurbConcrete", "#DDD4C6", rough=0.8)
M_DECK = L.material("DeckConcrete", "#A69C93", rough=0.85)
M_RED = L.material("BridgeRed", "#D8332E", rough=0.45)
M_TRUSS = L.material("TrussRed", "#B02B28", rough=0.55)
M_LAMP = L.material("LampPole", "#3E4A5C", rough=0.5)
M_GLOW = L.material("LampGlow", "#FFE7A6", rough=0.4, emit="#FFD98A", emit_strength=2.5)

b = L.Builder()


def extrude_y(profile, mat, y0=0.0, y1=LEN, smooth=False):
    """Extrude an open (x,z) polyline along y, no end caps (seamless)."""
    n = len(profile)
    verts = [(x, y0, z) for x, z in profile] + [(x, y1, z) for x, z in profile]
    faces = [(i, i + 1, n + i + 1, n + i) for i in range(n - 1)]
    b.add(verts, faces, mat, smooth)


def mirror_profile(profile):
    return [(-x, z) for x, z in reversed(profile)]


ENDS = ("-y", "+y")

# ---------------------------------------------------------------- road surface
b.box(-5.0, 5.0, 0, LEN, -0.35, 0.0, M_ASPH, skip=ENDS + ("-z", "-x", "+x"))

# road markings: thin quads slightly above asphalt
EPS = 0.006
for s in (-1, 1):
    x = s * 4.75
    b.quad((x - 0.08, 0, EPS), (x + 0.08, 0, EPS), (x + 0.08, LEN, EPS), (x - 0.08, LEN, EPS), M_LINE)
for k in range(4):  # 3 m dash, 2 m gap -> period 5 (divides 20)
    y0 = 1.0 + 5 * k
    b.quad((-0.1, y0, EPS), (0.1, y0, EPS), (0.1, y0 + 3, EPS), (-0.1, y0 + 3, EPS), M_LINE)

# ---------------------------------------------------------------- curb + walkway edge + red fascia
curb = [(5.0, -0.35), (5.0, 0.18), (5.07, 0.25), (5.6, 0.25), (5.6, 0.06), (6.1, 0.06)]
fascia = [(6.08, 0.06), (6.08, 0.16), (6.28, 0.16), (6.28, -0.95), (6.18, -1.1)]
for prof in (curb, fascia):
    extrude_y(prof, M_CURB if prof is curb else M_RED)
    extrude_y(mirror_profile(prof), M_CURB if prof is curb else M_RED)

# concrete deck slab under the road
b.box(-6.1, 6.1, 0, LEN, -0.9, -0.35, M_DECK, skip=ENDS + ("+z",))

# ---------------------------------------------------------------- stiffening truss (both sides)
TOP_Z, BOT_Z = -1.15, -3.45
for s in (-1, 1):
    xc = s * 5.95
    # chords
    b.box(xc - 0.17, xc + 0.17, 0, LEN, TOP_Z - 0.17, TOP_Z + 0.25, M_TRUSS, skip=ENDS)
    b.box(xc - 0.2, xc + 0.2, 0, LEN, BOT_Z - 0.2, BOT_Z + 0.2, M_TRUSS, skip=ENDS)
    # Warren diagonals: top nodes y=0,5,10,15(,20), bottom nodes y=2.5,7.5,...
    for k in range(4):
        yt = 5.0 * k
        yb = yt + 2.5
        b.prism((xc, max(yt, 0.22), TOP_Z), (xc, yb, BOT_Z), 0.15, M_TRUSS, sides=4, caps=False,
                smooth=False, roll=math.pi / 4)
        b.prism((xc, yb, BOT_Z), (xc, min(yt + 5.0, LEN - 0.22), TOP_Z), 0.15, M_TRUSS, sides=4, caps=False,
                smooth=False, roll=math.pi / 4)
        # vertical post at bottom node
        b.box(xc - 0.12, xc + 0.12, yb - 0.12, yb + 0.12, BOT_Z, TOP_Z, M_TRUSS, skip=("-z", "+z"))

# transverse floor beams (deck level + bottom chord level)
for k in range(4):
    y = 2.5 + 5.0 * k
    b.box(-5.8, 5.8, y - 0.2, y + 0.2, -1.35, -0.9, M_TRUSS, skip=("+z", "-x", "+x"))
    b.box(-5.8, 5.8, y - 0.15, y + 0.15, BOT_Z - 0.15, BOT_Z + 0.15, M_TRUSS, skip=("-x", "+x"))
    # lateral X bracing between bottom chords
for k in range(4):
    y0 = 2.5 + 5.0 * k
    y1 = y0 + 5.0 if k < 3 else None
    if y1 is not None:
        b.prism((-5.8, y0, BOT_Z), (5.8, y1, BOT_Z), 0.08, M_TRUSS, sides=4, caps=False, smooth=False)
        b.prism((5.8, y0, BOT_Z), (-5.8, y1, BOT_Z), 0.08, M_TRUSS, sides=4, caps=False, smooth=False)

# ---------------------------------------------------------------- railings
RX = 5.72
for s in (-1, 1):
    x = s * RX
    for k in range(10):
        y = 1.0 + 2.0 * k
        b.box(x - 0.06, x + 0.06, y - 0.06, y + 0.06, 0.06, 1.24, M_RED, skip=("-z",))
        # small baluster between posts
        if k < 9:
            b.box(x - 0.03, x + 0.03, y + 0.97, y + 1.03, 0.06, 0.7, M_RED, skip=("-z", "+z"))
    # seam baluster split in two halves so the piece stays exactly within y 0..20
    b.box(x - 0.03, x + 0.03, 0.0, 0.03, 0.06, 0.7, M_RED, skip=("-z", "+z", "-y"))
    b.box(x - 0.03, x + 0.03, LEN - 0.03, LEN, 0.06, 0.7, M_RED, skip=("-z", "+z", "+y"))
    b.prism((x, 0, 1.24), (x, LEN, 1.24), 0.075, M_RED, sides=6, caps=False, smooth=True)
    b.prism((x, 0, 0.7), (x, LEN, 0.7), 0.055, M_RED, sides=6, caps=False, smooth=True)

# ---------------------------------------------------------------- lamp posts (on curb, outside playfield)
for s in (-1, 1):
    x = s * 5.32
    y = 10.0
    b.prism((x, y, 0.25), (x, y, 4.3), 0.09, M_LAMP, sides=6, caps=False, smooth=True, r1=0.06)
    b.prism((x, y, 0.25), (x, y, 0.6), 0.16, M_LAMP, sides=6, caps=True, smooth=False)
    b.box(x - 0.17, x + 0.17, y - 0.17, y + 0.17, 4.3, 4.75, M_GLOW)
    b.cone((x, y, 4.75), 0.3, 0.26, M_LAMP, sides=4, cap=True, roll=math.pi / 4)

seg = b.build("bridge_segment")

L.export([seg], "bridge_segment")

# ---------------------------------------------------------------- preview: 3 segments in a row
for i in (1, 2):
    dup = seg.copy()
    dup.location.y = LEN * i
    bpy.context.scene.collection.objects.link(dup)
L.preview_setup(water=True, water_z=-9.0)
L.game_camera((0, 30, -1), 36, pitch_deg=45, lens=32)
L.render("bridge_segment")

dbg = os.environ.get("PREVIEW_DEBUG_DIR")
if dbg:
    L.camera((24, 2, 10), (0, 26, -2), lens=35)
    L.render(os.path.join(dbg, "bridge_segment_side.png"), samples=32)
