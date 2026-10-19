"""Композиции сцен: каждая функция _scene_* собирает кадр W×H из фона, сооружений, машин и предметов.

Земля по умолчанию на GY=56; объекты переднего плана стоят чуть ниже (gy 58–64), чтобы горизонт
читался позади них. SCENES — словарь «имя сцены → функция(c: Canvas)».
"""

from ironvein.art.backgrounds import GY, backdrop, ground, lamp_post, rails, road, sky
from ironvein.art.buildings import (
    board,
    drill_rig,
    factory,
    furnace,
    gear,
    market_hall,
    pumpjack,
    refinery,
    rock,
    workshop,
)
from ironvein.art.canvas import Canvas, W
from ironvein.art.props import (
    barrel,
    caliper,
    coin_stack,
    crate,
    crest,
    document,
    hammer,
    magnifier,
    paint_can,
    pedestal,
    sack,
    watch,
    worker,
    wrench,
)
from ironvein.art.vehicles import TRUCK_W, minecart, train, truck, wagon


def _scene_start(c: Canvas) -> None:
    backdrop(c)
    factory(c, 6, GY, 40, 21)
    train(c, 30, 66, ("box", "hopper"))


def _scene_mine(c: Canvas, res: str) -> None:
    backdrop(c)
    if res == "oil":
        pumpjack(c, 12, 58)
        worker(c, 86, 58, None)
        barrel(c, 98, 49)
    else:
        rock(c, 14, 58, res)
        worker(c, 66, 58, "pick", flip=True)
        minecart(c, 84, 58, res)


def _scene_drill(c: Canvas) -> None:
    backdrop(c)
    drill_rig(c, 22, 58)
    for i in range(3):
        crate(c, 92 + i * 9, 50)


def _scene_pump(c: Canvas) -> None:
    backdrop(c)
    pumpjack(c, 22, 58)


def _scene_smelter(c: Canvas) -> None:
    backdrop(c)
    furnace(c, 22, 58)


def _scene_refinery(c: Canvas) -> None:
    backdrop(c)
    refinery(c, 24, 58)
    for i in range(3):
        barrel(c, 82 + i * 9, 49)


def _scene_workshop(c: Canvas) -> None:
    backdrop(c)
    workshop(c, 18, 58)
    crate(c, 90, 50, 9)  # ящик с готовыми шестернями у двери
    gear(c, 94, 46, 4, "steel")
    gear(c, 101, 47, 3, "brass")
    barrel(c, 104, 49)


def _scene_assembly(c: Canvas) -> None:
    sky(c)
    ground(c)
    workshop(c, 6, 58)
    truck(c, 72, 64, "cargo", "rust", None)


def _scene_repair(c: Canvas) -> None:
    sky(c, smoggy=False)
    ground(c)
    truck(c, 10, 64, "cargo", "steel", None)
    worker(c, 64, 63, "wrench", flip=True)
    crate(c, 92, 55, 8)  # ящик с запчастями, инструмент лежит на земле
    gear(c, 96, 51, 3, "brass")
    gear(c, 106, 61, 3, "steel")
    wrench(c, 78, 61, lying=True)


def _scene_truck(c: Canvas, body: str = "cargo", cargo: str | None = "crates", paint: str = "rust",
                 flip: bool = False) -> None:
    backdrop(c, 55)
    road(c, 57, 8)
    truck(c, (W - TRUCK_W) // 2, 63, body, paint, cargo, flip)


def _scene_arrive(c: Canvas) -> None:
    backdrop(c, 55)
    factory(c, 76, 57, 46, 19, 2, "steel")
    road(c, 57, 8)
    truck(c, 12, 63, "cargo", "rust", "crates")
    crate(c, 64, 49)


def _scene_foot(c: Canvas) -> None:
    backdrop(c)
    road(c, 58, 8)
    lamp_post(c, 96, 58, 20)
    _signpost(c, 18, 58)
    for x in range(30, 56, 6):  # следы на асфальте
        c.dot(x, 63 - (x // 6) % 2, "road2")
    worker(c, 58, 65, "sack")
    sack(c, 104, 64)
    crate(c, 110, 56)


def _signpost(c: Canvas, x: int, gy: int) -> None:
    """Дорожный указатель: столб и две таблички-стрелки."""
    c.box(x, gy - 22, 2, 22, "wood", base=1)
    for y, dx, w in ((gy - 21, 2, 14), (gy - 15, -12, 13)):
        c.box(x + dx, y, w, 4, "wood", base=2)
        c.hline(x + dx + 2, y + 2, w - 5, "wood0")
        tip = x + dx + w if dx > 0 else x + dx - 1
        c.dot(tip, y + 1, "wood2")
        c.dot(tip, y + 2, "wood1")


def _scene_train(c: Canvas) -> None:
    backdrop(c, 54)
    train(c, 2, 64)


def _scene_market(c: Canvas) -> None:
    backdrop(c, 54)
    market_hall(c, 6, 56, 56, 30)
    board(c, 70, 14, 50, 24)
    coin_stack(c, 72, 56, 4)
    coin_stack(c, 83, 56, 6)
    crate(c, 96, 48)
    barrel(c, 108, 47)


def _scene_contract(c: Canvas) -> None:
    backdrop(c, 54)
    rails(c, 64)
    wagon(c, 2, 64, "box", "rust")
    wagon(c, 31, 64, "hopper", "steel")
    c.glow(88, 28, 20, ["sky3", "smog1"])
    document(c, 76, 13)
    coin_stack(c, 106, 56, 3)


def _scene_company(c: Canvas) -> None:
    backdrop(c)
    factory(c, 4, GY, 54, 24, 3, "rust")
    c.vline(64, 14, 42, "steel2")  # флагшток с гербовым флагом
    c.vline(65, 14, 42, "steel0")
    c.dot(64, 13, "brass3")
    c.box(66, 14, 14, 9, "red", base=1)
    gear(c, 72, 18, 2, "brass")
    truck(c, 78, 64, "cargo", "steel", "crates")


def _scene_item(c: Canvas, kind: str) -> None:
    c.fill("bg")
    cx = W // 2
    c.glow(cx, 36, 30, ["sky2"])  # мягкий «прожектор» за предметом
    c.dither(cx - 18, 67, 37, 1, None, "sky0", 0.5)  # тень под постаментом
    pedestal(c, cx, 56, 35)
    if kind == "watch":
        watch(c, cx, 39, 12)
    elif kind == "paint":
        paint_can(c, cx, 42)
    else:
        crest(c, cx, 39)


def _scene_done(c: Canvas) -> None:
    sky(c, smoggy=False)
    ground(c)
    lamp_post(c, 14, 60, 22)
    c.box(24, 58, 50, 2, "wood", base=1)  # поддон
    for i in range(5):
        crate(c, 25 + i * 9, 50)
    for i in range(4):
        crate(c, 29 + i * 9, 42)
    crate(c, 38, 34)
    crate(c, 47, 34)
    for i in range(3):
        barrel(c, 86 + i * 8, 50)
    barrel(c, 90, 41)
    coin_stack(c, 112, 60, 4)
    coin_stack(c, 119, 60, 6)
    worker(c, 73, 60, None, flip=True)
    for x, y in ((50, 26), (96, 30), (112, 40)):
        c.sparkle(x, y, "brass3", 1, "white")

def _bench(c: Canvas) -> None:
    """Верстак под лампой: тёмная мастерская, конус света, столешница с инструментом."""
    c.fill("bg")
    c.vline(64, 0, 9, "steel1")  # шнур лампы
    c.box(59, 9, 11, 4, "steel", base=1)
    c.hline(61, 13, 7, "lamp2")
    c.glow(64, 30, 34, ["sky2", "haze0", "haze1"], soft=0.6)
    for x, y in ((8, 10), (12, 22), (114, 14), (118, 26)):  # инструмент на стене
        c.rect(x, y, 6, 1, "steel1")
    c.box(14, 50, 100, 6, "wood", base=1)  # столешница
    c.box(18, 56, 5, 14, "wood", base=0)
    c.box(105, 56, 5, 14, "wood", base=0)
    c.dither(10, 70, 108, 2, None, "sky0", 0.5)
    caliper(c, 24, 46)
    magnifier(c, 92, 40)
    hammer(c, 104, 41)
    worker(c, 2, 70, "wrench")


def _part(c: Canvas, cx: int, cy: int) -> None:
    """Свежевыточенная деталь — шестерня на валу."""
    c.box(cx - 15, cy + 6, 4, 3, "steel", base=0)  # опоры вала на верстаке
    c.box(cx + 11, cy + 6, 4, 3, "steel", base=0)
    c.box(cx - 13, cy + 3, 26, 3, "steel", base=1)  # вал
    gear(c, cx, cy, 8, "steel")
    gear(c, cx + 11, cy + 2, 4, "brass")


def _scene_inspect(c: Canvas) -> None:
    _bench(c)
    _part(c, 62, 41)


def _scene_masterwork(c: Canvas) -> None:
    _bench(c)
    c.glow(62, 41, 24, ["brass0", "brass1", "brass2"], soft=0.55)
    _part(c, 62, 41)
    for x, y, a in ((40, 22, 2), (86, 20, 2), (48, 34, 1), (80, 32, 1), (62, 16, 2), (34, 40, 1), (92, 44, 1)):
        c.sparkle(x, y, "brass3", a, "white")
    c.disk(100, 18, 6, "k")  # латунная розетка «мастер»
    c.disk(100, 18, 5, "brass2")
    c.disk(100, 18, 3, "brass3")
    c.dot(100, 18, "red1")
    c.rect(97, 23, 2, 6, "red1")
    c.rect(101, 23, 2, 6, "red0")


SCENES = {
    "start": _scene_start,
    "mine_ore": lambda c: _scene_mine(c, "ore"),
    "mine_coal": lambda c: _scene_mine(c, "coal"),
    "mine_oil": lambda c: _scene_mine(c, "oil"),
    "drill": _scene_drill,
    "pump": _scene_pump,
    "smelter": _scene_smelter,
    "refinery": _scene_refinery,
    "workshop": _scene_workshop,
    "assembly": _scene_assembly,
    "repair": _scene_repair,
    "truck": _scene_truck,
    "truck_ore": lambda c: _scene_truck(c, cargo="ore"),
    "truck_oil": lambda c: _scene_truck(c, cargo="barrels"),
    "truck_armored": lambda c: _scene_truck(c, body="armored", paint="steel"),
    "truck_brass": lambda c: _scene_truck(c, paint="black_brass"),
    "arrive": _scene_arrive,
    "foot": _scene_foot,
    "train": _scene_train,
    "market": _scene_market,
    "contract": _scene_contract,
    "company": _scene_company,
    "item_watch": lambda c: _scene_item(c, "watch"),
    "item_paint": lambda c: _scene_item(c, "paint"),
    "item_crest": lambda c: _scene_item(c, "crest"),
    "done": _scene_done,
    "inspect": _scene_inspect,
    "masterwork": _scene_masterwork,
}

THEMES = ("rust", "mazut", "kotlo")
# Сцены без горизонта (интерьер, предмет на постаменте) не зависят от локации.
UNTHEMED = {"assembly", "repair", "item_watch", "item_paint", "item_crest", "done", "inspect", "masterwork"}
