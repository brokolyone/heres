"""Точка входа рендера: имя сцены (с необязательной локацией «имя@тема») → PNG.

Модули пакета (импорты без циклов):
    canvas      — холст, палитра-рампы, примитивы и хелперы света/дизеринга;
    backgrounds — небо, смог, горизонт по локациям, земля, дорога, рельсы, дым;
    vehicles / buildings / props — машины, сооружения, предметы;
    scenes      — композиции кадров и словарь SCENES;
    render      — нормализация имени сцены и кэшированный рендер.
"""

from functools import lru_cache

from ironvein.art.canvas import SCALE, Canvas, H, W
from ironvein.art.scenes import SCENES, THEMES, UNTHEMED

__all__ = ["SCALE", "SCENES", "THEMES", "UNTHEMED", "H", "W", "normalize_scene", "render_png"]


def normalize_scene(scene: str) -> str:
    """Каноническое имя: неизвестная сцена → start, тема только у сцен с горизонтом и только известная."""
    name, _, theme = scene.partition("@")
    if name not in SCENES:
        name = "start"
    if name in UNTHEMED or theme not in THEMES:
        return name
    return f"{name}@{theme}"


def render_png(scene: str) -> bytes:
    """scene — имя сцены, опционально с локацией: «truck@mazut» рисует горизонт Мазутного Яра."""
    return _render(normalize_scene(scene))


@lru_cache(maxsize=128)
def _render(scene: str) -> bytes:
    name, _, theme = scene.partition("@")
    c = Canvas(seed=sum(map(ord, name + theme)), theme=theme or None)
    SCENES[name](c)
    return c.png()
