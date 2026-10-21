# Samorost-style painting — shared spec for all 5 layer agents

Style target: Amanita Design's *Samorost* (1/2/3). Tiny surreal floating worlds made of
moss, old bark, fungi, rusty little machines and photo-collage-like organic textures.
Muted, earthy, dusky palette: deep teal/blue-green night sky, olive and moss greens,
ochre, sienna, burnt umber, bone-white, rusty orange, a few warm glowing accents
(lantern yellow #f3d27a, ember orange #e08a3c). Soft, painterly, lots of fine organic detail
(bark grain, lichen spots, moss fuzz, tiny holes, cracks). Whimsical, quiet, a bit melancholic.
NO flat cartoon vector look: use gradients, many semi-transparent overlapping shapes, feTurbulence
noise textures (feTurbulence + feDisplacementMap / feColorMatrix / feComposite) to get an organic,
textured, hand-made feel.

## Canvas
SVG, viewBox="0 0 1600 1000". Layers are stacked in this order (bottom → top):
1. bg          — sky, stars, giant planet, distant floating islands, haze
2. island      — the main floating world: a huge old mossy tree stump / asteroid
3. structures  — little houses & contraptions standing on the island
4. flora       — mushrooms, ferns, grass, vines growing on the island and structures
5. characters  — the gnome hero and creatures

## Fixed geography (everyone must respect it)
- Main island top surface (the ground line), exactly this path:
  `M380,610 C470,560 600,545 720,548 C850,550 980,555 1080,570 C1150,580 1200,595 1230,615`
  Approx ground y by x: 400→597, 500→566, 600→552, 700→548, 800→549, 900→551, 1000→558, 1100→573, 1200→600.
- Island body: from that top edge down to an irregular rounded underside, lowest ~y=880 around x=780;
  hanging roots dangle down to ~y=980. Island spans x≈360–1250.
- A secondary small floating rock with a tiny tree: centered (230, 330), ~150 wide (belongs to bg agent,
  drawn in full detail, mid-ground). A rope from it to the main island is drawn by structures agent
  from (290, 345) to (470, 575).
- Giant pale planet/moon (bg): center (1260, 230), r=170, cratered, with soft glow.
- Structures:
  - Hollow-log house on the left: occupies x 440–640, sits on ground (~y 560), up to y≈380, round door,
    small crooked window, tin-pipe chimney with a smoke curl.
  - Rusty contraption on the right: x 980–1160, a spindly wooden/metal tower with a propeller or
    gramophone horn, gears, pipes, a dangling lantern, top around y≈330.
  - Small ladder or rope hanging from the island underside around x=900.
- Characters:
  - The gnome hero (Samorost style: small, white/cream jumpsuit, white cap, big round head, tiny body,
    simple dark dot eyes), standing at x=780, feet on ground y≈548, total height ~80 px.
  - A large sleepy moss-covered creature/beast lying in front-right, x 1150–1260 top area or hanging
    off the edge near (1190, 600).
  - A small long-legged bug/insect near the house door (~ x 560, y 555).
  - 2–3 small flying creatures (moth, odd beetle with propeller) in the sky around (900,250) and (650,200).
- Flora: big mushroom cluster at x 660–720 (behind gnome, left of him), smaller mushrooms around
  x 850–950, moss tufts & grass along the whole ground line, ferns, hanging vines/roots from the island
  edge, lichens on the house and stump, a few glowing tiny mushrooms. Keep x 755–805, y 465–550 clear
  (that's where the gnome stands).

## Technical rules
- Write ONE file: `art/samorost/layers/<layer>.svg` — a complete SVG
  `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 1000" width="1600" height="1000">`.
  Everything outside your layer must be TRANSPARENT (except bg which fills the canvas).
- Prefix EVERY id (gradients, filters, patterns, clipPaths) with your layer name, e.g. `island-bark`,
  so layers can be merged into one SVG without collisions. Put all content inside
  `<g id="layer-<layer>"> ... </g>` with `<defs>` at the top of the svg.
- Pure SVG, no external images/fonts, no scripts, no CSS `<style>` with global selectors (inline
  attributes only). Keep the file under ~400 KB.
- Self-check: render to PNG with Playwright's preinstalled Chromium
  (node + `playwright` or python `playwright`; executablePath `/opt/pw-browsers/chromium` if needed —
  never run `playwright install`) and LOOK at the PNG with the Read tool, then iterate until it looks
  rich and convincingly Samorost-like. Put preview PNGs in `art/samorost/previews/<layer>.png`.
  A combined preview of all finished layers may be built by stacking available layer files to check fit.
- Do not touch other agents' files. Do not commit or push.
