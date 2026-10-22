#!/usr/bin/env python3
"""Готовит снимки из capture.js к хранению в репозитории.

Забеливает в них фото Google в клетках (в уровне оно не используется,
там своя сцена) и копирует только те файлы, которые читает build_level.py.
Запуск: python3 clean_capture.py <capture_dir> <out_dir>
"""
import os
import shutil
import sys

from PIL import Image, ImageDraw

from build_level import BFRAME, CLIP

NEEDED = [
    "page_challenge.png", "challenge_skip.png", "challenge_verify.png", "challenge_selected.png",
    "widget_base.png", "widget_checked.png", "sprite_tilecheck.png",
    "err_rc-imageselect-incorrect-response.png", "err_rc-imageselect-error-select-more.png",
]
GRID = (6, 126, 394, 513)       # сетка клеток внутри окна, CSS-пиксели


def main(src, dst):
    os.makedirs(dst, exist_ok=True)
    for name in NEEDED:
        path = os.path.join(src, name)
        if name == "page_challenge.png":
            img = Image.open(path).convert("RGB")
            x0 = (BFRAME[0] + GRID[0] - CLIP[0]) * 2
            y0 = (BFRAME[1] + GRID[1] - CLIP[1]) * 2
            x1 = (BFRAME[0] + GRID[2] - CLIP[0]) * 2
            y1 = (BFRAME[1] + GRID[3] - CLIP[1]) * 2
            ImageDraw.Draw(img).rectangle([x0, y0, x1, y1], fill=(255, 255, 255))
            img.save(os.path.join(dst, name))
        elif name.startswith(("challenge_", "err_")):
            img = Image.open(path).convert("RGB")
            ImageDraw.Draw(img).rectangle([GRID[0] * 2, GRID[1] * 2, GRID[2] * 2, GRID[3] * 2],
                                          fill=(255, 255, 255))
            img.save(os.path.join(dst, name))
        else:
            shutil.copy(path, os.path.join(dst, name))


if __name__ == "__main__":
    main(*sys.argv[1:3])
