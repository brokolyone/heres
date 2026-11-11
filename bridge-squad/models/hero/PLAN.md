# HERO SOLDIER — ART & TECH PLAN (v1, art director)

One character, five artists, one model. Read this fully before modelling. Amendments go to NOTES.md
(signed `— Art Director`) and override this file.

## 1. Look
* **Style**: premium stylized mobile hero (think Brawl Stars / Squad Busters / Clash proportions, a bit
  more grounded): chibi, ~2.7 heads tall, chunky hands & boots, big helmet, soft bevelled forms,
  clean big shapes first, then secondary detail (seams, pouches, buckles, straps, rivets) and real
  PBR fabric/metal/leather textures for micro detail. No horror-realism, no thin fiddly parts that
  alias on a phone.
* **Silhouette** (must read at 40 px tall from behind-above): big rounded BLUE helmet, broad BLUE
  shoulders, BLUE backpack flap, rifle pointing forward sticking out past the head on the right,
  sturdy boots. Pose: neutral "ready" — feet together under hips, rifle held at chest height with
  both hands, barrel forward (+Y).
* **Colour scheme** (team colour = BLUE, dominant from top/back; enemies are red, so no red/orange
  large areas on us; small warm accents OK):

| Material slot        | Base colour (sRGB hex) | Notes |
|----------------------|------------------------|-------|
| `M_helmet_blue`      | #2F6BFF | painted metal, satin; THE team-colour read |
| `M_jacket_blue`      | #3C7FE0 | fabric (canvas/twill) — jacket, sleeves |
| `M_pants_navy`       | #283A63 | fabric — trousers |
| `M_vest_tan`         | #C7A36B | nylon/cordura — plate vest, pouches |
| `M_strap_tan`        | #A98654 | webbing — straps, belt, sling |
| `M_backpack_blue`    | #2C5BC4 | canvas — backpack body & flap |
| `M_leather_brown`    | #5A3E2B | boots upper, holster, glove cuffs |
| `M_rubber_dark`      | #2B2D33 | soles, rubber, knee pads |
| `M_glove`            | #3B4252 | gloves (leather, dark slate) |
| `M_skin`             | #F0BE96 | face, neck, ears |
| `M_hair`             | #4A3022 | eyebrows / sideburns |
| `M_eye_white`        | #F4F1EA | |
| `M_eye_iris`         | #3B6EA8 | iris (+pupil may use `M_eye_pupil` #1E2430) |
| `M_eye_pupil`        | #1E2430 | |
| `M_mouth`            | #B5655A | lips / mouth line |
| `M_goggle_lens`      | #FFB23E | glossy amber lens on helmet goggles (accent) |
| `M_metal_gun`        | #3A414D | gunmetal (receiver, barrel) |
| `M_polymer_gun`      | #2E333B | polymer (grip, stock, handguard) |
| `M_gun_accent`       | #2F6BFF | small team-blue stripe/parts on rifle |
| `M_metal_bright`     | #B9BEC6 | buckles, rivets, muzzle tip, D-rings |
| `M_emblem`           | #FFD54A | yellow star emblem (helmet side, shoulder) |
| `M_cloth_olive`      | #6F7A4E | small accents only (bedroll, pouch flaps) — optional |

No pure black / white / grey. Only these slot names may appear on meshes (ask in NOTES to add one).

## 2. Units, axes, pose
* Blender units = metres. **+Z up, character faces +Y**, character's RIGHT side = **+X**, left = -X.
* Feet on z=0. Total height (helmet top) ≈ **0.97–1.00**.
* Symmetric about X=0 except arms/hands/rifle (posed).

## 3. Anchors (hard constraints — fit your parts to these). All in metres (x, y, z).
Also available as `A[...]` in `src/hero_common.py`.

| Anchor | Value | Meaning |
|--------|-------|---------|
| `hip_L` / `hip_R` | (∓0.085, 0, 0.30) | leg pivots = leg object origins (L at -X) |
| `knee_L/R` | (∓0.085, 0.005, 0.165) | |
| `ankle_L/R` | (∓0.085, 0, 0.075) | boot: sole z 0–0.025, boot top z≈0.13, toe y=+0.145, heel y=-0.065, width 0.115 |
| `crotch_z` | 0.255 | lowest point of body-object pants seat |
| `belt` | z 0.305–0.355, waist half-width x 0.145, y ±0.105 | |
| `chest` | z 0.48: half-width x 0.165, front y +0.115, back y -0.110 (jacket surface) | vest adds ≤0.025 |
| `shoulder_L/R` | (∓0.185, 0.015, 0.545) | arm joints; shoulder top z ≈ 0.60 |
| `elbow_R` | (0.215, 0.050, 0.405) | |
| `wrist_R` | (0.115, 0.150, 0.405) | |
| `hand_R` | (0.085, 0.200, 0.395) | palm centre, gripping pistol grip |
| `elbow_L` | (-0.170, 0.135, 0.430) | |
| `wrist_L` | (0.010, 0.270, 0.430) | |
| `hand_L` | (0.060, 0.330, 0.425) | palm centre, under/left of handguard |
| `neck` | centre (0, 0.0, 0.615), radius 0.05, z 0.58–0.66 | |
| `head` | centre (0, 0.012, 0.775), radii x 0.140 y 0.145 z 0.155 | chin z≈0.625, crown 0.93 |
| `eye_L/R` | (∓0.050, 0.138, 0.765) | eye centres (surface of face) |
| `ear_L/R` | (∓0.140, 0.0, 0.770) | |
| `helmet` | dome centre (0, -0.005, 0.795), outer r 0.172 | brim lower edge: front z 0.840, sides 0.760, back 0.735; top ≈ 0.967 |
| `goggles` | on helmet front, centre (0, 0.150, 0.880) | strap around helmet |
| `rifle_axis` | line x=0.085, z=0.455, butt y=+0.100, muzzle y=+0.680 | pistol grip under y≈0.20, magazine at y≈0.27, handguard y 0.29–0.48 |
| `backpack` | centre (0, -0.185, 0.460), size 0.28 w × 0.13 d × 0.26 h | front face y=-0.120 sits on jacket back; top flap z≈0.59 |

Arms are a bent two-segment pose: upper arm shoulder→elbow, forearm elbow→wrist, hands at hand_*.

## 4. Ownership & files (all paths relative to `models/hero/`)
| Who | Script (only owner edits) | Output part file | Builds |
|-----|---------------------------|------------------|--------|
| 1 Art Director | `src/hero_common.py`, `src/assemble.py`, `src/export_hero.py` | `hero_hi.glb`, `hero_lo.glb`, previews | integration, atlas bake, export |
| 2 Body & face | `src/part_body.py` | `parts/body.blend` | head (skull, face, nose, ears, eyes, brows, mouth), neck, hands/gloves (both, posed at hand anchors, fingers wrapped round grips), a simple hidden torso core (optional) |
| 3 Uniform & gear | `src/part_uniform.py` | `parts/uniform.blend` | jacket torso + collar, sleeves (shoulder→wrist along the arm anchors, cuffs meet gloves), shoulder pads (blue + emblem), pants seat (body), pant legs + knee pads + boots (legs), belt + buckle + pouches, plate vest / chest rig, backpack + straps, rifle sling optional |
| 4 Helmet & weapon | `src/part_helmet_weapon.py` | `parts/helmet_weapon.blend` | helmet (shell, rim, cover detail, goggles, chin strap, emblem), rifle (receiver, barrel, muzzle, handguard, stock, pistol grip, magazine, sight/optic, rail, blue accent) |
| 5 Materials & textures | `src/fetch_textures.py`, `src/materials.py` | `textures/<AssetId>/...`, `textures/CREDITS.json` | downloads CC0 PBR sets (ambientCG), builds the material library |

Each part script is standalone: `cd models/hero && python3 src/part_X.py` → starts from an empty
scene, builds, **applies all modifiers**, saves `parts/X.blend` (via `hero_common.save_part`) and
renders its own check preview `previews/part_X.png` (`hero_common.preview`). Re-run it whenever you change
something; the assembler always picks up the latest `.blend`. Write to a temp name and rename
(save_part does this) so the assembler never reads half-written files.

## 5. Object naming & tagging
* Object name: `<owner>.<part>` e.g. `body.head`, `uni.boot_L`, `hw.rifle_barrel`. LOD1 objects get suffix `.lo`.
* Every object MUST have custom props (use `hero_common.tag(obj, target, lod, owner)`):
  * `hero_target` = `"body"` | `"leg_L"` | `"leg_R"` — which final object it is joined into.
  * `hero_lod` = `0` (hi) or `1` (lo / crowd). Provide both LODs (see budgets). If you don't provide
    a LOD1 for something, the assembler will decimate your LOD0 (ugly) — please don't rely on it.
* Object transforms: apply them (location/rotation/scale identity, verts in world space). The
  assembler sets the leg origins to the hip anchors itself.
* No parenting, no armatures, no cameras/lights in part files (preview helper cleans them).

## 6. Materials / texture API (modelers ↔ materials artist)
* Modelers assign materials **only** via `hero_common.mat("M_xxx")` (names from §1). That creates a
  flat placeholder (palette colour) so your previews look right. You never build node trees.
* Materials artist provides `src/materials.py` with:
  * `build(name) -> bpy.types.Material` — full Principled material named `name` using real CC0
    textures (base colour tinted to the palette colour, normal, roughness, metallic where relevant),
    texture coordinates = UV map **`UVMap`** through a Mapping node with a per-material scale.
  * `apply_library(objects)` — replaces every placeholder slot on these objects with `build(name)`.
  * `SPEC: dict name -> {"color": hex, "rough": float, "metal": float, "tex": asset id or None, "scale": float, "normal_strength": float}`
  The palette colour MUST stay the perceived average colour after texturing (tint/desaturate the
  texture's albedo, don't let a brown leather photo make the boots orange).
* Textures: ambientCG CC0, 1K or 2K JPG, unpacked into `textures/<AssetId>/` with `CREDITS.json`
  listing asset id, URL, licence (CC0). Suggested picks: fabric/canvas for jacket/pants/backpack,
  nylon/cordura-ish fabric for vest/straps, leather for boots/gloves, painted metal (fine scratches)
  for helmet, worn/scratched metal for gun, plastic/rubber for polymer & soles, skin: no photo
  texture, maybe very subtle noise/procedural.

## 7. UV rules
* Every mesh has a UV map named exactly `UVMap` at **world scale: 1 UV unit = 0.5 m** of surface
  (`hero_common.uv_world(obj)` does smart-project + rescale; you may unwrap by hand if you
  keep the same density). Islands may overlap/exceed 0–1: textures are tiling.
* Seams: hide seams under/inside/behind where possible; fabric grain roughly vertical on clothing.
* The assembler creates a second UV map `Atlas` (packed, non-overlapping) for baking, and bakes
  base colour / normal / roughness+metal into one atlas set. Don't make a map named `Atlas`.

## 8. Triangle budgets (after modifiers; triangulated count)
| Part owner | LOD0 (hero_hi) | LOD1 (hero_lo) |
|------------|----------------|----------------|
| Body & face (head, face, neck, hands) | 7 000 | 550 |
| Uniform & gear (clothes, boots, vest, belt, pouches, backpack) | 11 000 | 1 000 |
| Helmet & weapon (helmet 3 500 + rifle 4 500) | 8 000 | 700 |
| Reserve (AD) | 4 000 | 250 |
| **Total** | **≤ 30 000** | **≤ 2 500** |
LOD1 tips: no fingers (mitten hands), helmet ~150 tris, rifle ~200, boots ~80 each, closed simple
forms, no interior faces. Detail in LOD1 will come from the baked normal map + colour atlas.

## 9. Integration & export (Art Director)
* `src/assemble.py`: loads all `parts/*.blend`, applies `materials.apply_library`, joins by
  `hero_target` per LOD into `body`, `leg_L`, `leg_R`; leg origins at hip anchors.
* `src/export_hero.py`: bakes atlas (Cycles): hi = 2048 px base colour + normal + ORM-ish
  (roughness/metal); lo = 1024 px colour + normal baked from hi. One material per GLB
  (`M_hero_hi` / `M_hero_lo`). Vertex colours `COLOR_0` also written on lo (game's crowd shader
  multiplies vertex colours). Export GLB, `export_yup=True`, apply modifiers, only the 3 meshes.
* Previews by AD in `previews/` (`asm_*.png`, `final_*.png`). Feedback in NOTES.md.

## 10. Process
1. Start now; post in NOTES.md what you're doing (one line is enough), sign with your role.
2. Ship a rough blockout of your parts within the first ~15 min so integration starts; iterate.
3. Read NOTES.md between iterations — AD feedback appears there. Post `DONE <part>` when finished
   (with your tri counts LOD0/LOD1).
4. Don't edit other people's scripts. Need something from someone → ask in NOTES.md.
