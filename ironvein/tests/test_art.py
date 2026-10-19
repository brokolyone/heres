import io

from PIL import Image

from ironvein.art import SCENES, render_png
from ironvein.art.render import SCALE, H, W


def test_every_scene_renders_pixel_art_png():
    for name in SCENES:
        png = render_png(name)
        img = Image.open(io.BytesIO(png))
        assert img.size == (W * SCALE, H * SCALE)
        assert len(png) < 200_000
        # Крупные пиксели: каждый блок SCALE×SCALE одноцветный.
        px = img.convert("RGB").load()
        for x, y in ((10, 10), (300, 200), (500, 50)):
            bx, by = x - x % SCALE, y - y % SCALE
            assert len({px[bx + i, by + j] for i in range(SCALE) for j in range(SCALE)}) == 1, name


def test_unknown_scene_falls_back():
    assert render_png("nope") == render_png("start")
