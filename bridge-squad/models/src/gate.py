"""gate.glb - one-lane gate frame (two of them close the road).
Width exactly 4.8 (x -2.4..2.4), height 3.0, bottom z=0. Middle is OPEN:
the game draws a 4.4 x 2.4 number panel from z=0.15 inside.
Material `accent` is recolored by the game (blue / red).
Run: python3 bridge-squad/models/src/gate.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import obstacle_lib as L

L.reset()
metal = L.mat("gate_metal", "#e8ecf3", 0.35, 0.15)
trim = L.mat("gate_trim", "#3b4560", 0.55, 0.1)
accent = L.mat("accent", "#2f7cf6", 0.3)
lamp = L.mat("gate_lamp", "#fff6d8", 0.3, emit="#fff1c2", emit_strength=3.0)

W = 2.4          # half width
PW = 0.26        # post thickness along X (<= 0.3)
PX = W - PW / 2  # post centre x
PD = 0.46        # post depth (Y)
BEAM_Z0, BEAM_Z1 = 2.58, 2.92

for s in (-1, 1):
    # foot: dark plinth, may extend inward below the panel (panel starts at 0.15)
    L.box((0.5, 0.9, 0.14), (s * (W - 0.25), 0, 0.07), trim, bev=0.04, name="foot")
    # post with sporty taper (wider at the base in depth)
    L.box((PW, PD + 0.18, BEAM_Z0 - 0.14 + 0.06), (s * PX, 0, 0.14 + (BEAM_Z0 - 0.14 + 0.06) / 2),
          metal, bev=0.05, taper=(1.0, PD / (PD + 0.18)), name="post")
    # lamp strips on front & back faces of each post (accent colour)
    for fy in (-1, 1):
        L.box((0.12, 0.05, 1.95), (s * PX, fy * (PD / 2 + 0.07), 1.25), accent, bev=0.02,
              rot=(fy * 2.0, 0, 0), name="strip")
    # angled corner caps where post meets beam (chamfered blocks, stay inside +-2.4)
    L.box((0.42, PD + 0.12, 0.4), (s * (W - 0.21), 0, 2.8), trim, bev=0.08, name="corner")

# top beam
L.box((2 * W - 0.5, PD + 0.04, BEAM_Z1 - BEAM_Z0), (0, 0, (BEAM_Z0 + BEAM_Z1) / 2), metal,
      bev=0.06, name="beam")
# accent stripe on front and back faces of the beam
for fy in (-1, 1):
    L.box((3.4, 0.05, 0.12), (0, fy * (PD / 2 + 0.035), (BEAM_Z0 + BEAM_Z1) / 2), accent,
          bev=0.02, name="beam_strip")
# raised centre crest (trapezoid) up to z=3.0
L.box((1.5, PD + 0.1, 0.26), (0, 0, 2.87), trim, bev=0.05, taper=(0.72, 0.8), name="crest")
for fy in (-1, 1):
    L.box((0.9, 0.04, 0.08), (0, fy * (PD / 2 + 0.07), 2.88), accent, bev=0.015, name="crest_strip")
# small white lamps on corner caps
for s in (-1, 1):
    for fy in (-1, 1):
        L.box((0.18, 0.04, 0.18), (s * (W - 0.21), fy * ((PD + 0.12) / 2 + 0.015), 2.8),
              lamp, bev=0.03, name="lamp")

ob = L.finalize("gate")
L.export(ob, "gate")
L.preview(ob, "gate", dist_mul=2.0)
