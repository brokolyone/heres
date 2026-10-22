# Interior of the stump house — shared spec for the 5 interior agents

This is the inside of the hollow tree-stump house from the Samorost-style painting
(`art/samorost/samorost.png`, layers in `art/samorost/layers/`). Look at the painting first
(especially the house at x 440–640 in `structures.svg`) and match its style EXACTLY:
Amanita Design's *Samorost*: painterly, organic, collage-like textures, lots of fine detail,
feTurbulence-based wood grain / noise / displacement, muted earthy palette with warm lamp/fire
light and cool moonlight. NOT flat clean vector clip-art. Every surface needs texture and wear.

## What the house looks like from outside (the inside must agree)
- A hollow old stump with a broken, splintered, OPEN top: from inside you look up through a
  jagged rim at the night sky.
- A round-topped plank door with iron straps on the front; three nailed plank patches on the
  upper left; a small crooked window upper right with a riveted tin patch next to it; a rusty
  stove pipe leaving the house high on the RIGHT side (the chimney with a rain cap outside).
- The night sky, moon, stars and the small floating rock with a tree are the ones in
  `art/samorost/layers/bg.svg` — the interior must show THAT sky, not a new one.

## Canvas and layering
SVG, viewBox="0 0 1600 1000". Files are stacked bottom → top:
1. `shell.svg`        — sky + room shell (agent 1)
2. `walls_detail.svg` — growth on the walls (agent 5, part A)
3. `left.svg`         — left side furniture (agent 2)
4. `center.svg`       — centre (agent 3)
5. `right.svg`        — right side (agent 4)
6. `atmos.svg`        — lighting & atmosphere over everything (agent 5, part B)
The playable gnome (about 190 px tall, feet at y=905) walks IN FRONT of everything from x=175 to
x=1430, then the foreground parts are drawn over him.

## Fixed room geometry
- Back wall meets the floor along y = 770 + 115*((x-800)/800)^2 (≈770 in the middle, ≈885 at the
  edges). Floor below that; the gnome's feet line is y=905.
- Splintered top rim of the wall around y≈205–250 (higher in the middle, lower at the sides), with
  spikes up to ~90 px. Above it: sky. A crooked crossbeam branch spans the opening from (300,232)
  over (800,~215) to (1300,240); the lamp hangs from it at x=800.
- Moonlight shaft falls from the upper right through the opening onto the floor centre.

## Objects that MUST be inside these boxes (the game's tap targets) — x, y, w, h
- Door (exit), left wall: 90,580,200,330 — round-topped plank door, iron straps, ring handle.
- Coat hook with the gnome's spare white cap + striped scarf: 296,570,110,190.
- Bed (the gnome sleeps on it, lying with his neck at (560,752), head toward the pillow on the
  left, body to x≈650): 410,630,360,240; mattress top ≈ y 778 between x 430 and 760.
- Shelf above the bed at y≈470 (x 430–720) with jars and books; one GLOWING mushroom jar: 445,408,48,66.
- Wall clock with a pendulum: 810,336,80,225 (pendulum pivot (850,462), bob near (850,546)).
- Hanging lamp: 764,405,72,95 (hangs from the beam at (800,222)).
- Round log-slice table centred at x≈920, top ≈ y 776, with: a small music box 846,730,72,50
  (crank on its right side, pivot (904,754)); a candle 926,705,34,75 (flame tip ≈ (942,712)).
- Window, right wall: 1034,286,150,160 (night sky with stars visible through it).
- Tin patch next to the window: ≈1190–1250, 315–390.
- Pot-belly iron stove: 1215,640,180,215, glowing fire door ≈1262–1348 × 705–790. Its pipe goes UP
  from the stove top (≈1305,585) to y≈320, elbows and leaves through the upper RIGHT wall (x 1540+).
- Kettle on the stove top: 1255,540,120,62, spout tip ≈ (1366,566) (steam comes out there).
- A small sleeping moss creature by the stove: 1122,846,108,60.
- Firewood stack at x 1400–1560 on the floor; a ladder leaning up toward the rim at the far right.
- Foreground mushroom clusters in the bottom corners: left 0,880,130,120 and right 1460,860,140,140.

## Animated parts (separate files in `art/samorost/interior/parts/<id>.svg`, full 1600×1000 canvas,
## transparent elsewhere). Do NOT also draw these into your layer file.
| id | owner | content | pivot / origin (do not move) |
|---|---|---|---|
| jar | agent 2 | the glowing jar + its glow halo | (469,446) |
| pendulum | agent 3 | pendulum rod + bob | (850,462) |
| lamp | agent 3 | chain from (800,222) + the lantern + its warm glow | swings about (800,222) |
| crank | agent 3 | music box crank handle | (904,754) |
| candle | agent 3 | candle flame + small glow (not the candle body) | (942,731) |
| stovefire | agent 4 | the fire seen through the stove door (flames + embers + glow) | (1305,788) |
| kettle | agent 4 | the kettle | (1300,598) |
| pet | agent 4 | the sleeping moss creature | (1170,898) |
| front-left | agent 5 | foreground mushrooms bottom-left | (60,1000) |
| front-right | agent 5 | foreground mushrooms bottom-right | (1540,1000) |

## Technical rules
- Each layer/part is a complete SVG: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 1000" width="1600" height="1000">`.
  Everything outside your content is transparent (only shell.svg fills the canvas).
- Prefix EVERY id with your file name, e.g. `left-wood`, `pendulum-brass`, so files merge
  without collisions. Pure SVG: no scripts, no external images or fonts, no global CSS.
- Keep each file under ~500 KB.
- Self-check: render with
  `node /home/user/heres/tools/samorost/render.js <out.png> <svg files in stack order…>`
  (stack whatever other layers already exist to check fit), look at the PNG with the Read tool,
  and iterate at least 3 times until it is rich and convincingly Samorost-like. Previews go in
  `art/samorost/interior/previews/`.
- Do not edit other agents' files, the island layers or anything outside `art/samorost/interior/`.
  Do not commit.
