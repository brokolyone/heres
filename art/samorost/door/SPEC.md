# The house door — spec for the door agent

The stump house in the Samorost-style painting (`art/samorost/samorost.png`; the house is in
`art/samorost/layers/structures.svg`, x 440–640) has a round-topped plank door. In the game
(`art/samorost/game/ostrov-pen.html`) the gnome opens it and walks in. Repaint the door so it
looks great closed AND opening, in the painting's style (painterly Samorost look: textured wood
grain via feTurbulence, rust, wear, collage feel — not flat vector).

## Fixed geometry (canvas viewBox 0 0 1600 1000)
- Door frame (stays in the painting, do not draw): arch outer radius 40 around (538,524),
  x 498–578, bottom ≈ y 565–567, with rivets around it.
- Door leaf opening: arch radius 34 around (538,524): x 504–572, top y 490, bottom left y 565.2,
  bottom right y 563.2 (the ground slopes slightly). Hinges on the LEFT edge (x=504).
- Warm light from the house interior; outside is the night island (cool moonlight from the upper right).

## Files to write (each a full 1600×1000 SVG, transparent outside the door area)
- `art/samorost/door/leaf_0.svg` — the door CLOSED: planks, iron straps with rivets, ring handle,
  keyhole, a little glowing peephole, wear and moss at the bottom. This replaces the door in the painting.
- `art/samorost/door/leaf_1.svg` — the same door swung ~40° inward on its left hinges, in perspective
  (narrower, the free edge further away and a little smaller, its thickness visible, darker as it turns away).
- `art/samorost/door/leaf_2.svg` — swung ~80° inward: a narrow dark sliver along the left hinge side.
- `art/samorost/door/doorway.svg` — what is seen through the OPEN doorway (drawn inside the leaf arch):
  a glimpse into the warm, lived-in room inside the stump (look at `art/samorost/interior/previews/`
  and `art/samorost/interior/layers/` to match it: wooden walls, warm lamp light, a bit of rug and
  furniture), with depth, shadows (darker toward the arch edges and top, shadow of the open leaf on
  the left), light spilling onto the threshold. It must read clearly at small size.
The game shows doorway.svg under the leaf frames and steps leaf_0 → leaf_1 → leaf_2 to open.

## Rules
- Prefix every id with the file name (`leaf0-`, `leaf1-`, `leaf2-`, `doorway-`). Pure SVG, no scripts/images/fonts.
- Check your work: `node /home/user/heres/tools/samorost/render.js <out.png> /home/user/heres/art/samorost/samorost.svg <your files…>`
  and look at a zoomed crop (e.g. render with Playwright at deviceScaleFactor 6 clipped to x 480–600,
  y 470–590; Chromium is at /opt/pw-browsers, the playwright module at /opt/node-tools/node_modules/playwright).
  Iterate at least 3 times. Previews into `art/samorost/door/`.
- Only write inside `art/samorost/door/`. Do not commit.
