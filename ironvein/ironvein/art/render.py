import io
import random
from functools import lru_cache

from PIL import Image

W, H = 96, 54
SCALE = 6

P = {
    "bg": (28, 27, 38), "bg2": (34, 32, 46), "bg3": (40, 37, 53),
    "smog": (52, 49, 66), "smog2": (64, 60, 79), "smog3": (78, 73, 94),
    "ground": (36, 31, 36), "ground2": (48, 40, 42), "road": (30, 28, 34), "line": (96, 88, 74),
    "k": (15, 14, 22), "k2": (22, 20, 30),
    "steel": (86, 94, 112), "steel2": (124, 134, 156), "steel3": (60, 66, 82),
    "rust": (139, 58, 43), "rust2": (181, 86, 58), "rust3": (98, 42, 36),
    "brass": (212, 162, 76), "brass2": (143, 106, 42), "brass3": (240, 204, 120),
    "glass": (120, 190, 214), "glass2": (70, 120, 150),
    "fire": (240, 140, 50), "fire2": (255, 210, 100), "fire3": (190, 70, 40),
    "oil": (20, 18, 26), "oil2": (44, 40, 58),
    "green": (98, 168, 112), "green2": (60, 118, 80),
    "ore": (150, 90, 70), "ore2": (110, 64, 56), "coal": (40, 38, 46), "coal2": (70, 68, 80),
    "skin": (214, 160, 120), "cloth": (70, 84, 110), "cloth2": (50, 60, 82),
    "paper": (214, 200, 168), "paper2": (170, 154, 122), "red": (170, 50, 46), "red2": (210, 80, 60),
    "wood": (110, 74, 50), "wood2": (80, 54, 40), "white": (226, 222, 210),
}


class Canvas:
    def __init__(self, seed: int = 1):
        self.img = Image.new("RGB", (W, H), P["bg"])
        self.px = self.img.load()
        self.rnd = random.Random(seed)

    def dot(self, x, y, c):
        if 0 <= x < W and 0 <= y < H:
            self.px[x, y] = P[c] if isinstance(c, str) else c

    def rect(self, x, y, w, h, fill, outline=None):
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                edge = outline and (xx in (x, x + w - 1) or yy in (y, y + h - 1))
                self.dot(xx, yy, outline if edge else fill)

    def hline(self, x, y, w, c):
        for xx in range(x, x + w):
            self.dot(xx, y, c)

    def vline(self, x, y, h, c):
        for yy in range(y, y + h):
            self.dot(x, yy, c)

    def sprite(self, x, y, rows: list[str], pal: dict[str, str], flip: bool = False):
        for j, row in enumerate(rows):
            if flip:
                row = row[::-1]
            for i, ch in enumerate(row):
                if ch != "." and ch in pal:
                    self.dot(x + i, y + j, pal[ch])

    def png(self) -> bytes:
        out = io.BytesIO()
        self.img.resize((W * SCALE, H * SCALE), Image.NEAREST).save(out, "PNG", optimize=True)
        return out.getvalue()


# --- Фон ---------------------------------------------------------------------------------------------


def sky(c: Canvas, ground_y: int = 42, smoggy: bool = True):
    for y in range(ground_y):
        band = "bg" if y < 14 else "bg2" if y < 28 else "bg3"
        c.hline(0, y, W, band)
    # Дизеринг на границах полос
    for y in (13, 27):
        for x in range(0, W, 2):
            c.dot(x + (y % 2), y, "bg2" if y == 13 else "bg3")
    if smoggy:
        for _ in range(5):
            cloud(c, c.rnd.randrange(-6, W), c.rnd.randrange(3, 18), c.rnd.randrange(8, 18))


def cloud(c: Canvas, x, y, w, col="smog"):
    c.hline(x + 2, y, w - 4, col)
    c.hline(x, y + 1, w, col)
    c.hline(x + 1, y + 2, w - 2, col)


def skyline(c: Canvas, ground_y: int = 42, col="k2"):
    x = 0
    while x < W:
        bw = c.rnd.randrange(5, 11)
        bh = c.rnd.randrange(6, 15)
        c.rect(x, ground_y - bh, bw, bh, col)
        if c.rnd.random() < 0.45:
            cx = x + c.rnd.randrange(1, bw - 1)
            ch = c.rnd.randrange(5, 10)
            c.rect(cx, ground_y - bh - ch, 2, ch, col)
            smoke(c, cx, ground_y - bh - ch - 1, 4, "smog")
        for _ in range(c.rnd.randrange(0, 3)):
            c.dot(x + c.rnd.randrange(1, bw - 1), ground_y - c.rnd.randrange(2, bh), "brass2")
        x += bw + c.rnd.randrange(0, 3)


def smoke(c: Canvas, x, y, n, col="smog2"):
    for i in range(n):
        r = 1 + i // 2
        cx = x + i + (i % 2)
        cy = y - i * 2
        c.rect(cx - r // 2, cy - r // 2, r + 1, r, col)


def ground(c: Canvas, y: int = 42, col="ground", col2="ground2"):
    c.rect(0, y, W, H - y, col)
    c.hline(0, y, W, col2)
    for _ in range(40):
        c.dot(c.rnd.randrange(W), c.rnd.randrange(y + 2, H), col2)


def road(c: Canvas, y: int = 44):
    c.rect(0, y, W, 6, "road")
    c.hline(0, y, W, "ground2")
    for x in range(2, W, 8):
        c.hline(x, y + 3, 4, "line")


def rails(c: Canvas, y: int = 46):
    c.hline(0, y, W, "steel2")
    c.hline(0, y + 2, W, "steel3")
    for x in range(1, W, 4):
        c.rect(x, y + 1, 2, 2, "wood2")


# --- Машины ------------------------------------------------------------------------------------------

WHEEL = [".kk.", "kbbk", "kbbk", ".kk."]
WHEEL_PAL = {"k": "k", "b": "steel3"}


def wheel(c, x, y):
    c.sprite(x, y, [".kkkk.", "kbbbbk", "kbggbk", "kbbbbk", ".kkkk."], {"k": "k", "b": "oil2", "g": "steel2"})


def truck(c: Canvas, x: int, y: int, body: str = "cargo", paint: str = "rust", cargo: str | None = "crates",
          flip: bool = False):
    """y — линия дороги (низ колёс). Кабина справа (едет вправо); flip — влево."""
    main, light, dark = (paint, paint + "2", paint + "3") if paint in ("rust", "steel", "brass") else ("oil2", "brass", "oil")
    if paint == "black_brass":
        main, light, dark = "oil2", "brass", "oil"
    # координаты рисуем как будто вправо, затем зеркалим через функцию
    parts = []
    bw = 22 if body != "light" else 18
    bh = 9 if body != "light" else 6
    top = y - 5 - bh
    parts.append(("rect", 0, top, bw, bh, "steel3" if body != "armored" else "steel", "k"))
    if body == "cargo":
        for i in range(3, bw - 1, 4):
            parts.append(("vline", i, top + 1, bh - 2, "steel"))
    if body == "armored":
        for i in range(2, bw - 2, 5):
            parts.append(("dot", i, top + 2, "steel2"))
            parts.append(("dot", i, top + bh - 3, "steel2"))
        parts.append(("rect", 4, top + 3, 6, 2, "k", None))
    # кабина
    parts.append(("rect", bw, top + 2, 9, bh - 2 + 0, main, "k"))
    parts.append(("rect", bw + 2, top + 3, 5, 3, "glass", "k"))
    parts.append(("dot", bw + 3, top + 4, "white"))
    parts.append(("rect", bw + 8, top + 5, 3, bh - 5, main, "k"))
    parts.append(("dot", bw + 9, top + 6, "brass3"))
    # рама
    parts.append(("rect", -1, y - 5, bw + 12, 2, dark, "k"))
    parts.append(("hline", 0, y - 6, bw, light))
    # выхлоп
    parts.append(("vline", bw + 1, top - 3, 5, "steel3"))
    if cargo == "crates" and body != "armored":
        for i in range(2, bw - 5, 6):
            parts.append(("rect", i, top - 4, 5, 4, "wood", "wood2"))
    elif cargo == "barrels" and body != "armored":
        for i in range(2, bw - 4, 5):
            parts.append(("rect", i, top - 4, 4, 4, "oil2", "k"))
            parts.append(("hline", i, top - 3, 4, "brass2"))
    elif cargo == "ore" and body != "armored":
        for i in range(1, bw - 1):
            hgt = 1 + (i * 7 % 3)
            parts.append(("vline", i, top - hgt, hgt, "ore" if i % 3 else "ore2"))

    total = bw + 12

    def X(px, w=1):
        return x + (total - px - w) if flip else x + px

    for p in parts:
        kind = p[0]
        if kind == "rect":
            _, px, py, w, h, fill, outl = p
            c.rect(X(px, w), py, w, h, fill, outl)
        elif kind == "vline":
            c.vline(X(p[1]), p[2], p[3], p[4])
        elif kind == "hline":
            c.hline(X(p[1], p[3]), p[2], p[3], p[4])
        elif kind == "dot":
            c.dot(X(p[1]), p[2], p[3])
    smoke(c, X(bw + 1) + (-1 if flip else 0), top - 5, 4)
    for wx in (2, 9, bw + 3):
        wheel(c, X(wx, 6), y - 4)


def locomotive(c: Canvas, x: int, y: int):
    """Тепловоз/бронепаровоз, смотрит вправо. y — уровень рельса."""
    c.rect(x, y - 14, 18, 10, "oil2", "k")
    c.rect(x + 18, y - 11, 6, 7, "oil2", "k")
    c.rect(x + 2, y - 18, 6, 5, "rust", "k")
    c.rect(x + 3, y - 17, 3, 2, "glass", None)
    c.rect(x + 13, y - 19, 3, 6, "steel3", "k")
    smoke(c, x + 14, y - 21, 6, "smog3")
    for i in range(9, 17, 3):
        c.vline(x + i, y - 13, 8, "brass2")
    c.rect(x + 22, y - 9, 2, 2, "fire2")
    c.hline(x, y - 4, 24, "k")
    for wx in (1, 7, 13, 18):
        wheel(c, x + wx, y - 4)


def wagon(c: Canvas, x: int, y: int, kind: str = "box", color: str = "rust"):
    if kind == "tank":
        c.rect(x + 1, y - 11, 18, 7, "oil2", "k")
        c.hline(x + 2, y - 10, 16, "steel3")
        c.rect(x + 8, y - 13, 4, 2, "oil2", "k")
        c.hline(x + 1, y - 7, 18, "brass2")
    elif kind == "hopper":
        c.rect(x, y - 10, 20, 6, color, "k")
        for i in range(1, 19):
            h = 1 + (i * 5 % 3)
            c.vline(x + i, y - 10 - h, h, "coal2" if i % 2 else "ore")
    else:
        c.rect(x, y - 13, 20, 9, color, "k")
        c.rect(x + 8, y - 12, 4, 7, color + "3" if color in ("rust", "steel", "brass") else "k", "k")
        c.hline(x + 1, y - 12, 18, color + "2" if color in ("rust", "steel", "brass") else color)
    c.hline(x - 1, y - 4, 22, "k")
    wheel(c, x + 1, y - 4)
    wheel(c, x + 13, y - 4)


def train(c: Canvas, x: int, y: int, wagons=("box", "hopper", "tank")):
    rails(c, y)
    cx = x
    for i, k in enumerate(wagons):
        wagon(c, cx, y, k, ("rust", "steel", "rust")[i % 3])
        cx += 22
    locomotive(c, cx, y)


# --- Сооружения --------------------------------------------------------------------------------------


def factory(c: Canvas, x: int, gy: int, w: int = 30, h: int = 16, chimneys: int = 2, col="rust"):
    c.rect(x, gy - h, w, h, col, "k")
    for i in range(0, w - 4, 6):  # пилообразная крыша
        for j in range(4):
            c.hline(x + i + j, gy - h - 4 + j, 6 - j * 1 - (j > 2), col + "3" if col in ("rust", "steel") else col)
    for i in range(3, w - 3, 5):
        c.rect(x + i, gy - h + 4, 3, 4, "fire2" if (i // 5) % 2 else "brass2", "k")
    for n in range(chimneys):
        cx = x + 4 + n * (w // max(1, chimneys))
        c.rect(cx, gy - h - 12, 3, 12, "steel3", "k")
        c.hline(cx, gy - h - 9, 3, "red")
        smoke(c, cx + 1, gy - h - 14, 6, "smog3")
    c.rect(x + w // 2 - 2, gy - 6, 5, 6, "k2", "k")


def drill_rig(c: Canvas, x: int, gy: int):
    for i in range(14):
        c.dot(x + i // 2, gy - 1 - i * 2, "steel2")
        c.dot(x + 13 - i // 2, gy - 1 - i * 2, "steel2")
        if i % 3 == 0:
            c.hline(x + i // 2, gy - 1 - i * 2, 14 - i, "steel3")
    c.rect(x + 5, gy - 30, 4, 3, "rust", "k")
    c.vline(x + 7, gy - 27, 27, "k")
    c.rect(x + 14, gy - 8, 9, 8, "rust", "k")
    c.rect(x + 16, gy - 6, 3, 2, "fire2")
    c.rect(x + 20, gy - 13, 2, 5, "steel3")
    smoke(c, x + 21, gy - 15, 5)


def pumpjack(c: Canvas, x: int, gy: int):
    c.rect(x, gy - 2, 26, 2, "steel3", "k")
    c.vline(x + 12, gy - 14, 12, "steel2")
    c.vline(x + 13, gy - 14, 12, "steel3")
    for i in range(22):
        c.dot(x + 2 + i, gy - 16 + i // 6, "k")
        c.dot(x + 2 + i, gy - 15 + i // 6, "brass2")
    c.rect(x, gy - 18, 4, 6, "rust", "k")
    c.vline(x + 1, gy - 12, 10, "k")
    c.rect(x + 20, gy - 9, 6, 7, "rust3", "k")
    for i in range(3):
        c.rect(x + 30 + i * 6, gy - 6, 5, 6, "oil2", "k")
        c.hline(x + 30 + i * 6, gy - 4, 5, "brass2")


def furnace(c: Canvas, x: int, gy: int):
    c.rect(x, gy - 18, 20, 18, "rust3", "k")
    for j in range(gy - 17, gy - 1, 3):
        for i in range(x + 1 + (j % 2) * 2, x + 19, 4):
            c.hline(i, j, 3, "rust")
    c.rect(x + 6, gy - 9, 8, 7, "fire", "k")
    c.rect(x + 8, gy - 7, 4, 4, "fire2")
    c.rect(x + 7, gy - 30, 6, 12, "steel3", "k")
    smoke(c, x + 9, gy - 32, 7, "smog3")
    # ковш со сталью
    c.rect(x + 22, gy - 6, 8, 6, "steel", "k")
    c.hline(x + 23, gy - 6, 6, "fire2")
    for i in range(3):
        c.rect(x + 32 + i * 5, gy - 3, 4, 3, "steel2", "k")


def refinery(c: Canvas, x: int, gy: int):
    c.rect(x, gy - 26, 6, 26, "steel", "k")
    for j in range(gy - 24, gy - 2, 5):
        c.hline(x + 1, j, 4, "steel3")
    c.rect(x + 2, gy - 30, 2, 4, "steel3")
    c.dot(x + 2, gy - 31, "fire2")
    c.dot(x + 3, gy - 32, "fire")
    for i, (w, h) in enumerate(((12, 10), (10, 14))):
        tx = x + 8 + i * 14
        c.rect(tx, gy - h, w, h, "steel2", "k")
        c.hline(tx + 1, gy - h + 2, w - 2, "steel")
        c.hline(tx + 1, gy - 3, w - 2, "red")
    c.hline(x + 6, gy - 18, 24, "brass2")
    c.vline(x + 30, gy - 18, 18, "brass2")


def workshop(c: Canvas, x: int, gy: int):
    c.rect(x, gy - 14, 26, 14, "wood2", "k")
    for i in range(14):
        c.hline(x - 1 + i // 2, gy - 14 - i // 2, 28 - i, "rust3" if i % 2 else "rust")
    c.rect(x + 9, gy - 9, 8, 9, "k2", "k")
    gear(c, x + 2, gy - 11)
    c.rect(x + 20, gy - 10, 4, 4, "glass2", "k")
    # наковальня
    c.rect(x + 30, gy - 4, 8, 2, "steel3", "k")
    c.rect(x + 32, gy - 2, 4, 2, "steel3", "k")
    c.dot(x + 39, gy - 6, "fire2")
    c.dot(x + 40, gy - 7, "fire")


def gear(c: Canvas, x: int, y: int, col="brass"):
    c.sprite(x, y, [".b.b.", "bbbbb", ".bkb.", "bbbbb", ".b.b."], {"b": col, "k": "k"})


def rock(c: Canvas, x: int, gy: int, res: str):
    main, dark = {"ore": ("ore", "ore2"), "coal": ("coal2", "coal")}.get(res, ("steel3", "k2"))
    c.rect(x, gy - 10, 20, 10, "ground2")
    for i in range(20):
        h = 6 + (i * 13 % 5)
        c.vline(x + i, gy - h, h, "steel3" if i % 4 else "k2")
    for _ in range(14):
        c.dot(x + c.rnd.randrange(1, 19), gy - c.rnd.randrange(1, 8), main)
    for i in range(4):
        c.rect(x + 22 + i * 3, gy - 2 - (i % 2), 2, 2, main, None)
        c.dot(x + 22 + i * 3, gy - 2 - (i % 2), dark)


def worker(c: Canvas, x: int, gy: int, tool: str | None = "pick", flip: bool = False):
    rows = [
        "..hh..",
        ".hhhh.",
        "..ss..",
        ".cccc.",
        "cccccc",
        ".cccc.",
        ".dd.d.",
        ".d..d.",
        "kk..kk",
    ]
    c.sprite(x, gy - 9, rows, {"h": "brass2", "s": "skin", "c": "cloth", "d": "cloth2", "k": "k"}, flip)
    if tool == "pick":
        tx = x + (-3 if flip else 6)
        c.vline(tx + 1, gy - 10, 5, "wood")
        c.hline(tx - 1, gy - 10, 5, "steel2")
    elif tool == "sack":
        c.rect(x + (5 if flip else -3), gy - 8, 4, 5, "wood", "wood2")


# --- Предметы и интерфейс ----------------------------------------------------------------------------


def crate(c, x, y):
    c.rect(x, y, 6, 6, "wood", "wood2")
    c.dot(x + 1, y + 1, "wood2")
    c.dot(x + 4, y + 4, "wood2")


def barrel(c, x, y):
    c.rect(x, y, 5, 7, "oil2", "k")
    c.hline(x, y + 2, 5, "brass2")
    c.hline(x, y + 5, 5, "brass2")


def coin_stack(c, x, gy, n):
    for i in range(n):
        c.rect(x, gy - 2 - i * 2, 6, 2, "brass", "brass2")
        c.dot(x + 1, gy - 2 - i * 2, "brass3")


def document(c, x, y, stamp=True):
    c.rect(x, y, 18, 22, "paper", "paper2")
    for j in range(3, 17, 3):
        c.hline(x + 3, y + j, 12 - (j % 4), "paper2")
    if stamp:
        c.rect(x + 10, y + 14, 6, 6, "red", "red2")
        c.dot(x + 12, y + 16, "paper")
        c.dot(x + 13, y + 17, "paper")
    c.rect(x + 2, y + 18, 6, 1, "k")


def board(c, x, y, w=30, h=16):
    c.rect(x, y, w, h, "k2", "brass2")
    rnd = random.Random(7)
    for j in range(y + 3, y + h - 2, 3):
        c.hline(x + 2, j, 6, "brass")
        bars = rnd.randrange(3, w - 12)
        c.hline(x + 10, j, bars, "green" if rnd.random() < 0.6 else "red2")


def pedestal(c, cx, gy):
    """Горшок/постамент как в референсе: предмет по центру на тёмном фоне."""
    c.rect(cx - 9, gy - 3, 18, 2, "wood", None)
    c.hline(cx - 9, gy - 1, 18, "wood2")
    c.rect(cx - 7, gy, 14, 4, "wood2", None)
    c.rect(cx - 5, gy + 4, 10, 2, "wood2", None)


def watch(c, cx, cy):
    c.rect(cx - 1, cy - 9, 3, 2, "brass2")
    c.rect(cx - 6, cy - 7, 13, 13, "brass", "brass2")
    c.rect(cx - 4, cy - 5, 9, 9, "paper", "brass2")
    c.vline(cx, cy - 4, 4, "k")
    c.hline(cx, cy, 3, "k")
    for dx, dy in ((0, -4), (4, 0), (0, 4), (-4, 0)):
        c.dot(cx + dx, cy + dy, "brass2")
    c.dot(cx - 4, cy - 6, "brass3")
    for i in range(6):  # цепочка
        c.dot(cx + 7 + i, cy - 6 + i * 2 // 2, "brass2" if i % 2 else "brass")


def paint_can(c, cx, cy):
    c.rect(cx - 6, cy - 6, 12, 12, "steel2", "k")
    c.rect(cx - 6, cy - 2, 12, 5, "oil", "k")
    c.hline(cx - 5, cy, 10, "brass")
    c.rect(cx - 7, cy - 8, 14, 2, "steel", "k")
    for i in range(4):
        c.dot(cx - 4 + i * 3, cy - 9 - (i % 2), "brass")


def crest(c, cx, cy):
    rows = [
        "kkkkkkkkkkk",
        "kbbbbbbbbbk",
        "kbrrrrrrrbk",
        "kbrrgggrrbk",
        "kbrgkgkgrbk",
        "kbrrgggrrbk",
        "kbrrrrrrrbk",
        ".kbrrrrrbk.",
        "..kbrrrbk..",
        "...kbbbk...",
        "....kkk....",
    ]
    c.sprite(cx - 5, cy - 6, rows, {"k": "k", "b": "brass", "r": "rust", "g": "brass3"})


# --- Сцены -------------------------------------------------------------------------------------------


def _scene_start(c):
    sky(c)
    skyline(c, 42)
    ground(c, 42)
    factory(c, 6, 42)
    train(c, 40, 50, ("box", "hopper"))


def _scene_mine(c, res):
    sky(c)
    skyline(c, 42, "k2")
    ground(c, 42)
    if res == "oil":
        pumpjack(c, 10, 44)
        worker(c, 64, 44, None)
        barrel(c, 74, 37)
    else:
        rock(c, 16, 44, res)
        worker(c, 46, 44, "pick", flip=True)
        c.rect(58, 40, 12, 4, "wood", "wood2")
        for i in range(5):
            c.dot(59 + i * 2, 39, "ore" if res == "ore" else "coal2")
        wheel(c, 58, 42)
        wheel(c, 64, 42)


def _scene_drill(c):
    sky(c)
    skyline(c, 42)
    ground(c, 42)
    drill_rig(c, 20, 44)
    for i in range(3):
        c.rect(58 + i * 7, 38, 6, 6, "ore", "ore2")


def _scene_pump(c):
    sky(c)
    skyline(c, 42)
    ground(c, 42)
    pumpjack(c, 14, 44)


def _scene_smelter(c):
    sky(c)
    skyline(c, 42)
    ground(c, 42)
    furnace(c, 18, 44)


def _scene_refinery(c):
    sky(c)
    skyline(c, 42)
    ground(c, 42)
    refinery(c, 20, 44)
    for i in range(3):
        barrel(c, 60 + i * 6, 37)


def _scene_workshop(c):
    sky(c)
    skyline(c, 42)
    ground(c, 42)
    workshop(c, 16, 44)
    gear(c, 64, 30, "steel2")
    gear(c, 70, 34)


def _scene_assembly(c):
    sky(c)
    ground(c, 42)
    workshop(c, 4, 44)
    truck(c, 48, 47, "cargo", "rust", None)


def _scene_repair(c):
    sky(c, smoggy=False)
    ground(c, 42)
    truck(c, 10, 47, "cargo", "steel", None)
    worker(c, 50, 46, None, flip=True)
    c.rect(56, 36, 2, 7, "steel2")  # ключ
    c.rect(55, 35, 4, 2, "steel2")
    gear(c, 66, 34)
    gear(c, 72, 38, "steel2")


def _scene_truck(c, body="cargo", cargo="crates", paint="rust", flip=False):
    sky(c)
    skyline(c, 41)
    ground(c, 41)
    road(c, 43)
    truck(c, 30, 48, body, paint, cargo, flip)


def _scene_arrive(c):
    sky(c)
    skyline(c, 41)
    ground(c, 41)
    road(c, 43)
    factory(c, 56, 43, 34, 14, 2, "steel")
    truck(c, 12, 48, "cargo", "rust", "crates")
    crate(c, 50, 37)


def _scene_foot(c):
    sky(c)
    skyline(c, 42)
    ground(c, 42)
    road(c, 44)
    worker(c, 42, 47, "sack")
    for x in range(10, 40, 7):
        c.dot(x, 48, "line")


def _scene_train(c):
    sky(c)
    skyline(c, 40)
    ground(c, 40)
    train(c, 2, 48)


def _scene_market(c):
    sky(c)
    skyline(c, 40)
    ground(c, 40)
    c.rect(8, 18, 40, 24, "steel3", "k")
    for i in range(10, 46, 6):
        c.rect(i, 22, 2, 20, "steel")
    c.rect(6, 15, 44, 4, "rust", "k")
    board(c, 54, 14, 34, 18)
    coin_stack(c, 56, 42, 4)
    coin_stack(c, 64, 42, 6)
    crate(c, 74, 36)
    barrel(c, 82, 35)


def _scene_contract(c):
    sky(c)
    skyline(c, 40)
    ground(c, 40)
    rails(c, 48)
    wagon(c, 2, 48, "box", "rust")
    wagon(c, 24, 48, "hopper", "steel")
    document(c, 60, 12)
    coin_stack(c, 82, 40, 3)


def _scene_company(c):
    sky(c)
    skyline(c, 42)
    ground(c, 42)
    factory(c, 4, 42, 40, 18, 3, "rust")
    c.vline(52, 14, 28, "steel2")
    c.rect(53, 14, 10, 6, "red", "k")
    gear(c, 55, 15, "brass")
    truck(c, 62, 47, "cargo", "steel", "crates")


def _scene_item(c, kind):
    c.rect(0, 0, W, H, "bg")
    cx = W // 2
    pedestal(c, cx, 40)
    if kind == "watch":
        watch(c, cx, 28)
    elif kind == "paint":
        paint_can(c, cx, 30)
    else:
        crest(c, cx, 29)


def _scene_done(c):
    sky(c, smoggy=False)
    ground(c, 42)
    for i in range(4):
        crate(c, 24 + i * 7, 36)
    crate(c, 31, 30)
    crate(c, 38, 30)
    barrel(c, 60, 35)
    barrel(c, 66, 35)
    coin_stack(c, 74, 42, 3)


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


@lru_cache(maxsize=64)
def render_png(scene: str) -> bytes:
    fn = SCENES.get(scene) or SCENES["start"]
    c = Canvas(seed=sum(map(ord, scene)))
    fn(c)
    return c.png()
