# Hero soldier — «Отряд на мосту»

One stylized chibi soldier (team colour blue). Five artists built separate parts of this one model in Blender 5.1
(Python only, no GUI). The model is baked into two game-ready GLBs.

| File | Tris | Material / textures | Use |
|------|------|---------------------|-----|
| `hero_hi.glb` | 25 372 (body 22 236, legs 1 568 each) | 1 material `M_hero_hi`: base colour 2048² JPG (AO baked in), normal 2048² PNG, ORM 2048² JPG (R=AO, G=roughness, B=metal), emissive 2048² JPG (goggle and sight glow) | menu, victory screen, close-ups |
| `hero_lo.glb` | 1 946 (body 1 634, legs 156 each) | 1 material `M_hero_lo`: base colour, normal and ORM at 1024² each, plus **COLOR_0** vertex colours | crowd (300 instances) |

Both files satisfy `models/CONTRACT.md`:
- They contain exactly 3 mesh nodes, named `body`, `leg_L` and `leg_R`.
- Each leg node's origin is at its hip joint (±0.085, 0.30 Blender Z). The game swings the legs around local X.
- The character faces -Z in glTF (+Y in Blender). Feet are at height 0 and the helmet top is at 0.967.
- They were exported with `export_yup`. There is no armature or animation.
- Materials are single-sided. Every part is closed or has thickness.

Note for the game code: `web/src/assets.js → bakeCharacter()` ignores textures and multiplies the material colour
(white here) by `COLOR_0`. For that reason `hero_lo.glb` has vertex colours sampled from its baked albedo, so it
looks right in the current crowd shader without any code change. When you render it with its textures
(`MeshStandardMaterial` + map), set `vertexColors = false`, because otherwise the colour is applied twice.
`hero_hi.glb` has no vertex colours. Load it as a normal textured glTF.

## Layout
```
PLAN.md                 art & tech plan (anchors, palette, budgets, API)
NOTES.md                team coordination log
src/hero_common.py      shared anchors/palette/helpers (mat, tag, uv_world, save_part, preview)   – Art Director
src/part_body.py        head, face, hair, eyes, neck, gloved hands         -> parts/body.blend          – Body & face
src/part_uniform.py     jacket, sleeves, pads, vest, belt, pouches, pants, boots, backpack -> parts/uniform.blend – Uniform & gear
src/part_helmet_weapon.py helmet, goggles, chin strap, rifle, sling         -> parts/helmet_weapon.blend – Helmet & weapon
src/fetch_textures.py   downloads CC0 PBR sets from ambientCG -> textures/<AssetId>/, CREDITS.json   – Materials
src/materials.py        material library: build(name), apply_library(objs) (palette-tinted PBR)     – Materials
src/assemble.py         loads parts, applies library, joins into body/leg_L/leg_R                   – Art Director
src/export_hero.py      atlas UV packing, Cycles bakes, hi + lo GLB export                          – Art Director
src/final_previews.py   renders previews/final_*.png from the exported GLBs
textures_baked/         the baked atlases (also embedded in the GLBs)
previews/               part checks, assembly checks, final_* renders
```

## Rebuild
```
cd models/hero
python3 src/fetch_textures.py          # only if textures/ is missing (needs internet)
python3 src/part_body.py
python3 src/part_uniform.py            # the helmet script snaps the chin strap to parts/body.blend, so build body first
python3 src/part_helmet_weapon.py
python3 src/assemble.py 0              # optional: previews/asm_lod0_*.png
python3 src/export_hero.py both        # ≈2.5 min on 4 CPU cores -> hero_hi.glb, hero_lo.glb, textures_baked/
python3 src/final_previews.py          # ≈6 min -> previews/final_*.png
```
How the bake works:
- **hi:** each part has a world-scale UV map. The script copies it to an `Atlas` UV map and gives the face, eyes,
  helmet and gun more texels. It packs that map and then bakes diffuse colour, normal, roughness, AO, emission and
  metal (the metal goes through emission) with Cycles. Afterwards `Atlas` becomes the only UV map.
- **lo:** colour, normal and roughness are baked from the hi model onto the LOD1 meshes (selected → active). Where
  those rays missed, the LOD1 meshes' own library materials fill in. Strong hi→lo normal deviations are faded to
  flat. The lo mesh also gets its own AO bake.

## Texture credits
All photo textures come from **ambientCG** (https://ambientcg.com) and are licensed **CC0 1.0 Universal** (public
domain; attribution is not required but is given here). They were downloaded as 1K JPG sets. Details are in
`textures/CREDITS.json`.

| Asset | Used for |
|-------|----------|
| Fabric061 | jacket / sleeves |
| Fabric069 | trousers |
| Fabric062 | plate vest, pouches |
| Fabric079 | webbing straps, belt, sling |
| Fabric066 | backpack, olive cloth (bedroll) |
| Leather014 | boots, holster |
| Leather030 | gloves |
| Rubber004 | soles, knee pads, rubber trims |
| PaintedMetal002 | helmet paint, rifle accent |
| Metal046A | gun metal |
| Plastic018A | rifle polymer |
| Metal032 | buckles, rivets, bright metal |

Skin, hair, eyes, emblems and lenses are procedural or flat colour. All geometry was modelled from scratch by script.
