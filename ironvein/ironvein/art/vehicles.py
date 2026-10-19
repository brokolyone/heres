"""Транспорт: колёса, грузовики всех окрасок и кузовов, паровоз, вагоны, поезд, вагонетка.

Машины рисуются на прозрачном слое лицом вправо и кладутся на холст через Canvas.paste — так
flip (едет влево) зеркалит всю машину целиком. Ореолы фар и дым рисуются уже на холсте.
"""

from ironvein.art.backgrounds import rails, smoke
from ironvein.art.canvas import Canvas, ramp

TRUCK_W, TRUCK_H = 48, 34  # габарит грузовика (без дыма и груза выше кабины — он внутри TRUCK_H)
LOCO_W, LOCO_H = 37, 28
WAGON_W, WAGON_H = 28, 20

# Окраска: (рампа кабины, рампа кузова, рампа отделки)
PAINTS = {
    "rust": ("rust", "steel", "steel"),
    "steel": ("steel", "steel", "brass"),
    "brass": ("brass", "steel", "rust"),
    "black_brass": ("oil", "oil", "brass"),  # премиальная: чёрный лак и латунь
}


def wheel(c: Canvas, cx: int, cy: int, r: int = 3, hub: str = "steel", rim: str | None = None) -> None:
    """Колесо с центром (cx, cy): шина из мазутной рампы с бликом, ступица hub, болт-блик."""
    c.shaded_disk(cx, cy, r, "oil", outline="k")
    hr = max(1, r - 2)
    if r >= 3:
        c.shaded_disk(cx, cy, hr, hub, outline=rim or "oil0")
    c.dot(cx, cy, f"{hub}3" if hub in ("steel", "brass", "rust") else hub)
    if r >= 3:
        c.dot(cx - 1, cy - 1, f"{hub}2" if hub in ("steel", "brass", "rust") else hub)


# --- Грузовик ------------------------------------------------------------------------------------------


def truck(c: Canvas, x: int, y: int, body: str = "cargo", paint: str = "rust", cargo: str | None = "crates",
          flip: bool = False) -> None:
    """Грузовик в габарите TRUCK_W×TRUCK_H; x — левый край, y — низ колёс. Кабина справа, flip — влево.

    body: cargo (решётчатый кузов) | armored (бронекузов с заклёпками) | light (короткий кузов).
    paint: rust | steel | brass | black_brass. cargo: crates | barrels | ore | None.
    """
    lay = c.layer(TRUCK_W, TRUCK_H)
    _truck_body(lay, body, paint, cargo)
    top = y - (TRUCK_H - 1)

    def X(px: int) -> int:
        return x + (TRUCK_W - 1 - px if flip else px)

    c.glow(X(46), top + 18, 7, ["haze0", "lamp0", "lamp1"])  # фара светит в смог
    c.paste(lay, x, top, flip)
    c.dot(X(46), top + 18, "lamp2")
    smoke(c, X(28), top + 4, 5, tone=2, drift=-1 if flip else 1)


def _truck_body(c: Canvas, body: str, paint: str, cargo: str | None) -> None:
    """Грузовик на слое TRUCK_W×TRUCK_H, лицом вправо, низ колёс — последняя строка."""
    cab, box_ramp, trim = PAINTS.get(paint, PAINTS["rust"])
    cab_t, box_t, trim_t = ramp(cab), ramp(box_ramp), ramp(trim)
    L = TRUCK_H - 1
    light = body == "light"
    bw, bh = (22, 9) if light else (28, 12)
    btop = L - 8 - bh  # верх кузова

    # Рама и подножка
    c.rect(0, L - 8, 47, 3, "oil1")
    c.hline(0, L - 8, 47, "oil2")
    c.hline(0, L - 6, 47, "k")

    # Кузов
    if body == "armored":
        c.box(0, btop - 1, bw, bh + 1, "steel", base=2)
        for i in range(7, bw - 1, 7):  # швы броневых листов
            c.vline(i, btop, bh - 1, "steel1")
            c.vline(i + 1, btop, bh - 1, "steel3")
        c.rivets(2, btop + 1, (bw - 3) // 3, 3, "steel3", "steel0")
        c.rivets(2, btop + bh - 3, (bw - 3) // 3, 3, "steel3", "steel0")
        c.rect(4, btop + 4, 9, 2, "k")  # бойница
        c.hline(4, btop + 6, 9, "steel3")
        c.rect(16, btop + 3, 3, 3, "steel1", "k")  # лючок
    else:
        c.box(0, btop, bw, bh, box_ramp, base=1)
        for i in range(3, bw - 2, 4):  # доски/рёбра решётки
            c.vline(i, btop + 1, bh - 2, box_t[0])
            c.vline(i + 1, btop + 1, bh - 2, box_t[min(2, len(box_t) - 1)])
        c.hline(0, btop, bw, trim_t[1])  # верхний борт в цвет отделки
        c.hline(1, btop, bw - 2, trim_t[-1] if trim == "brass" else trim_t[2])
        c.hline(1, btop + bh - 2, bw - 2, trim_t[1] if trim != "steel" else box_t[0])
        c.rivets(2, btop + bh - 2, bw // 4, 4, trim_t[-1])

    # Груз над кузовом
    if body != "armored" and cargo:
        _truck_cargo(c, cargo, bw, btop)

    # Выхлопная труба за кабиной
    c.rect(bw, L - 29, 2, 22, "steel1")
    c.vline(bw, L - 29, 22, "steel2")
    c.rect(bw - 1, L - 30, 4, 2, "steel0", "k")

    # Кабина
    cx0 = bw + 2
    cw = 10
    ctop = L - 23
    c.box(cx0, ctop, cw, L - 7 - ctop, cab, base=len(cab_t) // 2)
    c.clear(cx0 + cw - 1, ctop)  # скруглённый угол крыши
    c.hline(cx0 + 1, ctop + 1, cw - 3, cab_t[-1])  # блик на крыше
    if body == "armored":
        c.rect(cx0 + 3, ctop + 3, 6, 2, "k")  # смотровая щель
        c.hline(cx0 + 4, ctop + 3, 3, "glass1")
        c.rivets(cx0 + 2, ctop + 7, 3, 3, "steel3", "steel0")
    else:
        c.rect(cx0 + 2, ctop + 2, 7, 6, "k")
        c.rect(cx0 + 3, ctop + 3, 5, 4, "glass1")
        c.hline(cx0 + 3, ctop + 6, 5, "glass0")
        c.dot(cx0 + 3, ctop + 3, "glass2")
        c.dot(cx0 + 4, ctop + 3, "glass2")
        c.dot(cx0 + 3, ctop + 4, "glass2")
        c.vline(cx0 + 1, ctop + 9, 6, cab_t[0])  # шов двери
        c.dot(cx0 + 7, ctop + 10, trim_t[-1])  # ручка
    # Капот и решётка радиатора
    hx = cx0 + cw
    htop = L - 17
    c.box(hx - 1, htop, 8, L - 7 - htop, cab, base=len(cab_t) // 2)
    c.hline(hx, htop + 1, 6, cab_t[-1])
    for i in range(hx + 1, hx + 5, 2):  # жалюзи
        c.vline(i, htop + 3, 3, cab_t[0])
    c.vline(hx + 7, htop, L - 7 - htop, "k")
    for j in range(htop + 1, L - 8, 2):
        c.dot(hx + 7, j, trim_t[-1] if trim == "brass" else "steel2")
    # Крылья над колёсами
    c.hline(hx - 4, L - 7, 11, cab_t[0])
    c.hline(hx - 3, L - 8, 9, cab_t[1])
    # Бампер и фара
    c.rect(hx + 5, L - 6, 3, 2, "steel2", "k")
    c.rect(hx + 5, htop - 1, 3, 3, "k")
    c.dot(hx + 6, htop, "lamp2")
    # Латунная отделка премиальной окраски
    if paint == "black_brass":
        c.hline(1, btop + 4, bw - 2, "brass2")
        c.hline(cx0 + 1, ctop + 9, cw - 2, "brass2")
        c.hline(hx, htop + 6, 7, "brass2")
        c.dot(hx, htop + 6, "brass3")

    # Колёса
    rear = (6, 15) if not light else (5, 13)
    for wx in (*rear, hx + 1):
        wheel(c, wx, L - 3, 3, hub="brass" if paint == "black_brass" else "steel")


def _truck_cargo(c: Canvas, cargo: str, bw: int, btop: int) -> None:
    if cargo == "crates":
        for i in range(1, bw - 7, 9):
            crate_small(c, i, btop - 8, 8)
    elif cargo == "barrels":
        for i in range(1, bw - 5, 7):
            c.box(i, btop - 8, 6, 8, "oil", base=1)
            c.hline(i + 1, btop - 6, 4, "brass1")
            c.hline(i + 1, btop - 3, 4, "brass1")
            c.dot(i + 1, btop - 6, "brass2")
    elif cargo == "ore":
        for i in range(1, bw - 1):
            hgt = 2 + min(i, bw - 1 - i, 5) // 2 + (i * 7 % 3) // 2
            for j in range(hgt):
                col = "ore2" if j == hgt - 1 else ("ore1" if (i + j) % 3 else "ore0")
                c.dot(i, btop - 1 - j, col)
        c.speckle(2, btop - 4, bw - 4, 3, ["brass2", "ore2"], 4)


def crate_small(c: Canvas, x: int, y: int, s: int = 8) -> None:
    """Деревянный ящик s×s: доски, диагональная распорка, блик сверху."""
    c.box(x, y, s, s, "wood", outline="wood0", base=1)
    c.line(x + 1, y + s - 2, x + s - 2, y + 1, "wood0")
    c.hline(x + 1, y + 1, s - 2, "wood2")


# --- Поезд ---------------------------------------------------------------------------------------------


def locomotive(c: Canvas, x: int, y: int) -> None:
    """Паровоз в габарите LOCO_W×LOCO_H лицом вправо; x — левый край, y — уровень рельса (низ колёс)."""
    lay = c.layer(LOCO_W, LOCO_H)
    L = LOCO_H - 1
    # Будка машиниста
    lay.box(0, L - 23, 10, 16, "rust", base=2)
    lay.rect(-1, L - 24, 12, 2, "oil1", "k")
    lay.rect(2, L - 20, 5, 4, "k")
    lay.rect(3, L - 19, 3, 2, "lamp1")
    lay.dot(3, L - 19, "lamp2")
    lay.rivets(2, L - 12, 3, 3, "rust3", "rust0")
    # Котёл
    lay.rect(9, L - 18, 22, 10, "oil1")
    lay.rect(9, L - 18, 22, 10, None, "k")
    lay.hline(10, L - 17, 20, "oil2")
    lay.hline(10, L - 16, 20, "steel0")
    lay.hline(10, L - 10, 20, "oil0")
    for i in range(13, 30, 6):  # латунные бандажи
        lay.vline(i, L - 17, 8, "brass1")
        lay.dot(i, L - 17, "brass3")
    # Дымовая коробка, труба, сухопарник
    lay.rect(30, L - 19, 5, 12, "oil0", "k")
    lay.dot(32, L - 14, "steel2")
    lay.box(26, L - 25, 4, 7, "oil", base=1)
    lay.rect(25, L - 26, 6, 2, "oil1", "k")
    lay.hline(26, L - 23, 4, "brass2")
    lay.box(18, L - 21, 5, 4, "brass", base=2)
    # Фара
    lay.rect(33, L - 22, 3, 3, "k")
    lay.dot(34, L - 21, "lamp2")
    # Ходовая: подножка с красной полосой, скотосбрасыватель
    lay.rect(0, L - 8, 35, 2, "oil1")
    lay.hline(0, L - 8, 35, "red1")
    lay.poly([(31, L - 6), (36, L - 6), (36, L)], "steel1")
    lay.line(32, L - 6, 36, L - 1, "steel2")
    # Колёса и дышло
    for wx in (6, 14, 22):
        lay.shaded_disk(wx, L - 3, 3, "red", outline="k")
        lay.dot(wx, L - 3, "steel3")
    wheel(lay, 29, L - 2, 2)
    lay.hline(5, L - 3, 19, "steel3")
    lay.hline(5, L - 2, 19, "steel1")
    lay.rect(-1, L - 6, 2, 1, "k")  # сцепка

    top = y - L
    c.glow(x + 34, top + L - 21, 8, ["haze0", "lamp0", "lamp1"])
    c.paste(lay, x, top)
    c.dot(x + 34, top + L - 21, "lamp2")
    c.sparkle(x + 35, top + L - 21, "lamp2", 1, "lamp1")
    smoke(c, x + 28, top + L - 27, 7, tone=3)


def wagon(c: Canvas, x: int, y: int, kind: str = "box", color: str = "rust") -> None:
    """Вагон WAGON_W×WAGON_H: box (крытый) | hopper (полувагон с углём/рудой) | tank (цистерна).
    x — левый край, y — уровень рельса."""
    lay = c.layer(WAGON_W, WAGON_H)
    L = WAGON_H - 1
    t = ramp(color) if color in ("rust", "steel", "brass", "oil", "wood", "green", "red") else ramp("rust")
    if kind == "tank":
        lay.rect(1, L - 14, 26, 9, "oil1", "k")
        lay.hline(2, L - 13, 24, "oil2")
        lay.hline(2, L - 12, 24, "steel0")
        lay.hline(2, L - 7, 24, "oil0")
        for i in (5, 22):
            lay.vline(i, L - 13, 7, "brass1")
            lay.dot(i, L - 13, "brass3")
        lay.box(11, L - 17, 6, 4, "oil", base=1)
        lay.hline(12, L - 17, 4, "brass2")
        lay.vline(25, L - 18, 4, "steel2")  # поручень
    elif kind == "hopper":
        lay.box(0, L - 13, WAGON_W, 8, color if color in ("rust", "steel") else "rust", base=1)
        for i in range(4, WAGON_W - 2, 5):
            lay.vline(i, L - 12, 6, t[0])
            lay.vline(i + 1, L - 12, 6, t[2])
        for i in range(1, WAGON_W - 1):  # насыпь угля и руды
            h = 1 + (i * 5 % 3) + (1 if 6 < i < WAGON_W - 7 else 0)
            for j in range(h):
                lay.dot(i, L - 14 - j, ("coal2" if i % 2 else "ore1") if j == h - 1 else ("coal1" if i % 3 else "ore0"))
    else:
        lay.box(0, L - 17, WAGON_W, 12, color if color in ("rust", "steel", "brass") else "rust", base=2)
        lay.rect(-1, L - 18, WAGON_W + 2, 2, "steel1", "k")  # крыша
        for i in range(3, WAGON_W - 1, 3):
            if not 10 <= i <= 17:
                lay.vline(i, L - 15, 9, t[1])
        lay.rect(10, L - 15, 8, 10, t[1], "k")  # дверь с распоркой
        lay.line(11, L - 14, 16, L - 7, t[0])
        lay.line(16, L - 14, 11, L - 7, t[0])
        lay.rivets(2, L - 15, 3, 3, t[3] if len(t) > 3 else t[-1])
        lay.rivets(20, L - 15, 3, 3, t[3] if len(t) > 3 else t[-1])
    # Рама, сцепки, тележки
    lay.rect(0, L - 5, WAGON_W, 2, "oil1")
    lay.hline(0, L - 5, WAGON_W, "k")
    lay.dot(0, L - 4, "k")
    lay.dot(WAGON_W - 1, L - 4, "k")
    for wx in (4, 9, 18, 23):
        wheel(lay, wx, L - 2, 2)
    c.paste(lay, x, y - L)


def train(c: Canvas, x: int, y: int, wagons: tuple[str, ...] = ("box", "hopper", "tank")) -> None:
    """Рельсы на уровне y, вагоны слева направо от x и паровоз в голове состава (справа)."""
    rails(c, y)
    cx = x
    for i, k in enumerate(wagons):
        wagon(c, cx, y, k, ("rust", "steel", "rust")[i % 3])
        c.hline(cx + WAGON_W, y - 4, 1, "k")  # сцепка между вагонами
        cx += WAGON_W + 1
    locomotive(c, cx, y)


def minecart(c: Canvas, x: int, gy: int, res: str = "ore") -> None:
    """Шахтная вагонетка 16×10 с горкой руды или угля; gy — низ колёс."""
    c.poly([(x, gy - 9), (x + 16, gy - 9), (x + 14, gy - 3), (x + 2, gy - 3)], "rust1")
    c.hline(x, gy - 9, 16, "rust3")
    c.hline(x + 1, gy - 8, 14, "rust2")
    c.line(x, gy - 9, x + 2, gy - 3, "k")
    c.line(x + 15, gy - 9, x + 13, gy - 3, "k")
    c.hline(x + 2, gy - 3, 12, "k")
    c.rivets(x + 3, gy - 6, 4, 3, "rust3", "rust0")
    main = ("ore2", "ore1", "ore0") if res == "ore" else ("coal2", "coal1", "coal0")
    for i in range(1, 15):
        h = 1 + min(i, 15 - i, 4) // 2
        for j in range(h):
            c.dot(x + i, gy - 10 - j, main[0] if j == h - 1 else main[1 + (i + j) % 2])
    if res == "ore":
        c.dot(x + 6, gy - 11, "brass3")
    wheel(c, x + 4, gy - 2, 2)
    wheel(c, x + 12, gy - 2, 2)
