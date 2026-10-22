# The little cave under the house — spec for the cave agent

On the underside of the floating island in the Samorost-style painting (`art/samorost/samorost.png`,
layers in `art/samorost/layers/`) there is a small cave in the bark below the house, centred about
(520,745): the opening is roughly x 486–554, y 715–770 (see the dark arch in `island.svg`, the paths
around `M486,767 C482,737 500,715 522,715`). The current cave looks bad. Repaint it so it becomes a
memorable little Samorost-style nook, matching the painting exactly in style: painterly, organic,
textured (feTurbulence noise, displacement), collage feel, warm inner light against the dark bark.

## What to make
- `art/samorost/layers/cave.svg` — a full 1600×1000 SVG, transparent outside about x 460–580,
  y 690–800. It is drawn on top of the island layer (and under the house, plants and characters).
  It must fully cover the old cave (paint over it), blend into the bark around (rough rocky or
  root-woven rim, moss, lichen, roots hanging over the entrance), and show a deep, cosy interior
  with a source of warm light and a few charming details someone would live with (it is tiny: think
  a little hollow home of a small creature, glowing mushrooms, a tiny lantern, stores, roots) — your
  design, but it must read at its real size (about 70 px wide in a 1600 px painting).
- Optionally `art/samorost/cave/light.svg` — the flickering warm light (glow only) as a separate
  file so it can animate; same canvas, transparent elsewhere.

## Rules
- Prefix every id with `cave-` (or `cavelight-`). Pure SVG, no scripts/images/fonts.
- Check your work: `node /home/user/heres/tools/samorost/render.js <out.png> /home/user/heres/art/samorost/samorost.svg <your files…>`
  and look at zoomed crops (render with Playwright at deviceScaleFactor 6 clipped to x 450–590,
  y 680–810; the playwright module is at /opt/node-tools/node_modules/playwright). Iterate at least
  3 times. Previews into `art/samorost/cave/`.
- Only write `art/samorost/layers/cave.svg` and files in `art/samorost/cave/`. Do not commit.
