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


def test_location_themes_render_and_differ():
    from ironvein.art.render import THEMES
    for name in ("truck", "mine_ore", "market", "arrive"):
        pngs = {t: render_png(f"{name}@{t}") for t in THEMES}
        assert len(set(pngs.values())) == len(THEMES), name
    assert render_png("truck@unknown")  # неизвестная тема не ломает рендер


def test_unthemed_scenes_share_one_render():
    from ironvein.art.render import normalize_scene
    assert normalize_scene("assembly@mazut") == "assembly"
    assert render_png("done@rust") == render_png("done@kotlo") == render_png("done")
    assert normalize_scene("truck@mazut") == "truck@mazut" and normalize_scene("zzz@rust") == "start@rust"


def test_every_scene_is_fast_and_small():
    """Каждая сцена (и с каждой локацией) рисуется без кэша быстрее 200 мс и весит меньше 250 КБ."""
    import time

    from ironvein.art.render import THEMES, UNTHEMED, _render
    names = [n for n in SCENES] + [f"{n}@{t}" for n in SCENES if n not in UNTHEMED for t in THEMES]
    for name in names:
        t0 = time.perf_counter()
        png = _render.__wrapped__(name)
        dt = time.perf_counter() - t0
        assert dt < 0.2, (name, dt)
        assert len(png) < 250_000, (name, len(png))


def test_render_is_deterministic():
    from ironvein.art.render import _render
    for name in ("start", "truck@mazut", "item_crest", "market@kotlo"):
        assert _render.__wrapped__(name) == _render.__wrapped__(name), name


def test_every_scene_name_used_by_the_bot_exists():
    """Имя сцены, которого нет в SCENES, молча превращается в заставку — ловим это тестом по исходникам."""
    import re
    from pathlib import Path

    from ironvein.art.render import SCENES as ALL
    src = Path(__file__).resolve().parents[1] / "ironvein"
    used = set()
    for f in list((src / "handlers").glob("*.py")) + [src / "bot.py"]:
        text = f.read_text()
        used |= set(re.findall(r'scene\s*=\s*f?"([a-z_]+)', text))
        used |= set(re.findall(r'"(item_watch|item_paint|item_crest|inspect|masterwork|truck_\w+)"', text))
    used = {n for n in used if not n.endswith("_")} - {"scene"}  # f"mine_{res}" — префикс, не имя
    missing = sorted(n for n in used if n not in ALL)
    assert not missing, missing
