#!/usr/bin/env python3
"""Собирает тестовые .gmd, чтобы найти, какая часть уровня роняет игру.

  test_1_block.gmd   один блок, обычный заголовок: проверка самого импорта
  test_2_header.gmd  один блок, но заголовок и цвета как у captcha
  test_3_art.gmd     только картинка (без триггеров)
  test_4_logic.gmd   только логика, курсор и collision-блоки (без картинки)

Запуск: python3 make_tests.py <capture_dir> <scene.png> <scene_mask.png> <out_dir>
"""
import os
import sys

import build_level as bl


def save(path, name, L, palette_rgb, plain_header=False):
    if plain_header:
        data = "kS38,1_255_2_255_3_255_11_255_12_255_13_255_4_-1_6_1000_7_1_15_1_18_0_8_1|,kA22,1;"
        data += ";".join(bl.object_string(o) for o in L.objects) + ";"
    else:
        data = bl.level_string(L, palette_rgb)
    bl.write_gmd(path, name, name, data, len(L.objects))


def main(cap, scene, mask, out):
    os.makedirs(out, exist_ok=True)
    arts, correct = bl.make_arts(cap, scene, mask)
    pal = bl.build_palette(arts)
    palette_rgb = [tuple(pal.getpalette()[i * 3:i * 3 + 3]) for i in range(len(pal.getpalette()) // 3)][:250]

    one = bl.Level()
    one.add({1: 1, 2: 15.0, 3: 105.0})
    save(os.path.join(out, "test_1_block.gmd"), "test 1 block", one, palette_rgb, plain_header=True)
    save(os.path.join(out, "test_2_header.gmd"), "test 2 header", one, palette_rgb)

    art = bl.Level()
    for a in arts:
        bl.art_objects(art, a, pal)
    save(os.path.join(out, "test_3_art.gmd"), "test 3 art", art, palette_rgb)

    logic = bl.Level()
    for a in arts:
        if a.name in ("checkbox", "cursor"):
            bl.art_objects(logic, a, pal)
    bl.build_collision(logic)
    bl.build_helpers(logic)
    bl.build_logic(logic, correct)
    save(os.path.join(out, "test_4_logic.gmd"), "test 4 logic", logic, palette_rgb)
    for f in sorted(os.listdir(out)):
        print(f, os.path.getsize(os.path.join(out, f)))


if __name__ == "__main__":
    main(*sys.argv[1:5])
