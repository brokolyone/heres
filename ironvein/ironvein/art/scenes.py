"""Композиции сцен: каждая функция _scene_* собирает кадр W×H из фона, сооружений, машин и предметов.

Земля по умолчанию на GY=56; объекты переднего плана стоят чуть ниже (gy 58–64), чтобы горизонт
читался позади них. SCENES — словарь «имя сцены → функция(c: Canvas)».
"""

from ironvein.art.backgrounds import GY, backdrop, ground, rails, road, sky
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
    coin_stack,
    crate,
    crest,
    document,
    paint_can,
    pedestal,
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
    gear(c, 92, 42, 4, "steel")
    gear(c, 102, 49, 3, "brass")


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
    wrench(c, 80, 52)
    gear(c, 94, 50, 4, "brass")
    gear(c, 104, 56, 3, "steel")


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
    worker(c, 62, 64, "sack")
    for x in range(14, 58, 8):  # следы на асфальте
        c.dot(x, 64 - (x // 8) % 2, "road2")
        c.dot(x + 1, 64 - (x // 8) % 2, "road2")


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
    for i in range(4):
        crate(c, 28 + i * 9, 50)
    crate(c, 37, 42)
    crate(c, 46, 42)
    barrel(c, 74, 49)
    barrel(c, 82, 49)
    coin_stack(c, 96, 58, 3)


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
}

THEMES = ("rust", "mazut", "kotlo")
# Сцены без горизонта (интерьер, предмет на постаменте) не зависят от локации.
UNTHEMED = {"assembly", "repair", "item_watch", "item_paint", "item_crest", "done"}
