"""Транспорт: колёса, грузовики всех окрасок и кузовов, паровоз, вагоны, поезд, вагонетка.

Машины рисуются на прозрачном слое лицом вправо и кладутся на холст через Canvas.paste — так
flip (едет влево) зеркалит всю машину целиком. Контактные тени, конусы и ореолы фар, дым и пар
рисуются уже на холсте, поверх фона.

Объём деталей — «пятна» (_blob): край — контур k, внутреннее кольцо — блик сверху-слева и тень
снизу-справа, середина — основной тон. Внутренние швы (дверь, капот, листы брони) — тёмным тоном
своей рампы, а не чёрным: так силуэт читается чётко, а детали внутри не рябят.
"""

import math

from ironvein.art.backgrounds import rails, smoke
from ironvein.art.canvas import RAMPS, Canvas, lum, tone
from ironvein.art.props import barrel, crate

TRUCK_W, TRUCK_H = 48, 34  # габарит грузовика вместе с грузом и трубой (дым — выше, на холсте)
LOCO_W, LOCO_H = 37, 30
WAGON_W, WAGON_H = 28, 20

# Окраска: (рампа кабины, рампа кузова, рампа отделки)
PAINTS = {
    "rust": ("rust", "steel", "steel"),
    "steel": ("steel", "steel", "brass"),
    "brass": ("brass", "steel", "rust"),
    "black_brass": ("oil", "oil", "brass"),  # премиальная: чёрный лак и латунь
}

_N4 = ((1, 0), (-1, 0), (0, 1), (0, -1))
Cells = set[tuple[int, int]]


# --- Общие хелперы -------------------------------------------------------------------------------------


def _t(name: str, shift: int = 0) -> tuple[str, str, str, str]:
    """Четыре тона детали из рампы любой длины: (глубокая тень, тень, основной, блик).

    shift < 0 — деталь темнее (броня, крылья); у коротких рамп (oil, wood) темнее некуда — shift ≥ 0.
    """
    n = len(RAMPS[name])
    b = n // 2 + (shift if n >= 4 else max(shift, 0))
    return tone(name, b - 2), tone(name, b - 1), tone(name, b), tone(name, b + 1)


def _span(*rows: tuple[int, int, int]) -> Cells:
    """Множество пикселей из строк (y, x0, x1), концы включительно."""
    return {(x, y) for y, x0, x1 in rows for x in range(x0, x1 + 1)}


def _blob(c: Canvas, cells: Cells, t: tuple[str, str, str, str], outline: str | None = "k") -> None:
    """Объёмная деталь произвольной формы: край — outline, затем блик по верху/левой кромке и тень по
    низу/правой, середина — основной тон. outline=None — край тоже тонируется (деталь без контура)."""
    _, lo, base, hi = t
    edge = {(x, y) for x, y in cells if any((x + a, y + b) not in cells for a, b in _N4)}
    inner = cells - edge if outline is not None else cells
    for x, y in cells:
        if outline is not None and (x, y) in edge:
            c.dot(x, y, outline)
        elif (x, y + 1) not in inner or (x + 1, y) not in inner:
            c.dot(x, y, lo)
        elif (x, y - 1) not in inner or (x - 1, y) not in inner:
            c.dot(x, y, hi)
        else:
            c.dot(x, y, base)


def _outline(c: Canvas, col: str = "k") -> None:
    """Обвести силуэт прозрачного слоя изнутри: крайние непрозрачные пиксели → col."""
    edge = [(x, y) for y in range(c.h) for x in range(c.w)
            if c.get(x, y) is not None and any(c.get(x + a, y + b) is None for a, b in _N4)]
    for x, y in edge:
        c.dot(x, y, col)


def _lighten(c: Canvas, x: int, y: int, col: str) -> None:
    """Положить цвет, только если он светлее того, что уже лежит (свет не затемняет фон)."""
    old = c.get(x, y)
    if old is None or lum(old) < lum(c.rgb(col)):
        c.dot(x, y, col)


def _beam(c: Canvas, x: int, y: int, direction: int, length: int = 14) -> None:
    """Конус света фары от (x, y) в сторону direction (±1): яркое ядро у фары, по краям и к концу —
    шахматка и редкий дизер. Только осветляет то, что уже нарисовано."""
    for i in range(length):
        half = 1 + i * 2 // 5
        core = i * 1 // 4
        for dy in range(-half, half + 1):
            px, py = x + direction * i, y + dy
            far = i / length
            if abs(dy) <= core and far < 0.45:
                col, level = ("lamp1" if i < 2 else "lamp0"), 1.0 if i < 3 else 0.5
            else:
                col, level = ("lamp0" if far < 0.3 else "haze1"), (0.5 if far < 0.5 else 0.25)
            if c.threshold(px, py, "bayer4") < level:
                _lighten(c, px, py, col)


def _ground_shadow(c: Canvas, x: int, y: int, w: int) -> None:
    """Контактная тень машины: сплошная строка под колёсами с рваными краями и дизер над ней."""
    c.shadow(x, y + 1, w, "oil0")
    c.dither(x + 3, y, w - 6, 1, None, "oil0", 0.5)


# --- Колесо --------------------------------------------------------------------------------------------


def wheel(c: Canvas, cx: int, cy: int, r: int = 3, hub: str = "steel", rim: str | None = None) -> None:
    """Колесо с центром (cx, cy): покрышка с шашками протектора и бликом сверху-слева, светлое кольцо
    диска (r ≥ 3), тёмная ступица с ярким колпаком из рампы hub. rim — цвет кольца диска вместо рампы."""
    ht = _t(hub) if hub in RAMPS else (hub,) * 4
    tyre_in = r - 1.0 if r >= 4 else r - 0.5
    rim_in = tyre_in - 1.0 if r >= 3 else tyre_in
    for dy in range(-r - 1, r + 2):
        for dx in range(-r - 1, r + 2):
            x, y = cx + dx, cy + dy
            if not c.in_disk(dx, dy, r):
                if any(c.in_disk(dx + a, dy + b, r) for a, b in _N4):
                    c.dot(x, y, "k")
                continue
            d = math.hypot(dx, dy)
            lit = -(dx + dy) / d if d else 0.0  # > 0 — сторона к свету (верх-лево)
            if d >= tyre_in:
                ang = math.atan2(dy, dx)
                tread = d > r - 0.5 and int((ang + math.pi) / (2 * math.pi) * 4 * r) % 2 == 0
                shade = 2 if lit > 0.5 else (0 if lit < -0.4 else 1)
                col = (("oil0", "oil1"), ("oil1", "oil2"), ("oil2", "smog1"))[shade][0 if tread else 1]
            elif d >= rim_in:
                col = rim or (ht[3] if lit > 0.3 else (ht[1] if lit < -0.4 else ht[2]))
            else:
                col = ht[1] if lit > 0.3 else ht[0]
            c.dot(x, y, col)
    c.dot(cx, cy, ht[3])  # колпак ступицы


# --- Грузовик ------------------------------------------------------------------------------------------

_WY, _WR = 29, 4  # центр и радиус колёс грузовика на слое (низ колёс — последняя строка слоя)
_FWX = 39  # переднее колесо
_BED_X1 = 22  # правый край кузова (дальше — выхлопная труба и кабина)


def truck(c: Canvas, x: int, y: int, body: str = "cargo", paint: str = "rust", cargo: str | None = "crates",
          flip: bool = False, lights: bool = True) -> None:
    """Грузовик в габарите TRUCK_W×TRUCK_H; x — левый край, y — низ колёс. Кабина справа, flip — влево.

    body: cargo (дощатый кузов) | armored (бронекузов с башенкой) | light (короткий низкий кузов).
    paint: rust | steel | brass | black_brass. cargo: crates | barrels | ore | coal | None.
    lights — конус и ореол фары (выключить для дневной сцены).
    """
    lay = c.layer(TRUCK_W, TRUCK_H)
    _truck_body(lay, body, paint, cargo)
    top = y - (TRUCK_H - 1)
    d = -1 if flip else 1

    def X(px: int) -> int:
        return x + (TRUCK_W - 1 - px if flip else px)

    _ground_shadow(c, x + 1, y, TRUCK_W - 2)
    if lights:
        _beam(c, X(47) + d, top + 18, d, 14)
        c.glow(X(46), top + 18, 4, ["haze1", "lamp0", "lamp1"])
    c.paste(lay, x, top, flip)
    if lights:
        c.dot(X(46), top + 18, "white")
        c.dot(X(46), top + 17, "lamp2")
    # Сажа из трубы тянется назад
    smoke(c, X(24) - d, top + 1, 6, tone=1, drift=-d)
    c.dot(X(24) - d, top, "oil2")


def _truck_body(c: Canvas, body: str, paint: str, cargo: str | None) -> None:
    """Грузовик на слое TRUCK_W×TRUCK_H лицом вправо; низ колёс — последняя строка слоя."""
    cab, bed, trim = PAINTS.get(paint, PAINTS["rust"])
    armored, light = body == "armored", body == "light"
    brass = paint == "black_brass"
    ct = _t(cab, -1 if armored else 0)  # кабина и капот
    ft = _t(cab, -1)  # крылья и подножка — на тон темнее
    tt = _t(trim)  # отделка: решётка, бампер, ручки
    hub = "brass" if trim == "brass" and brass else "steel"

    # Ниша переднего колеса (тёмная), бак, колёса
    fender, well = set(), set()
    for yy in range(19, 25):
        for xx in range(30, 47):
            dd = math.hypot(xx - _FWX, yy - _WY)
            if 6.2 <= dd <= 9.3:
                fender.add((xx, yy))
            elif dd < 6.2:
                well.add((xx, yy))
    for xx, yy in well:
        c.dot(xx, yy, "oil0")
    _blob(c, _span((25, 26, 31), (26, 26, 31), (27, 26, 31), (28, 26, 31)), _t("steel", -1))  # топливный бак
    c.dot(27, 26, "steel3")
    rear = (13,) if light else (7, 17)
    for wx in (*rear, _FWX):
        wheel(c, wx, _WY, _WR, hub=hub)

    # Рама
    c.hline(0, 23, 45, "oil2")
    c.hline(0, 24, 45, "oil1")
    for xx in range(2, 44, 4):
        c.dot(xx, 23, "steel1")  # болты рамы

    # Кузов и груз
    if armored:
        _bed_armored(c, ct)
    else:
        btop = 16 if light else 12
        bx0 = 4 if light else 0
        if cargo:
            _truck_cargo(c, cargo, bx0, btop)
        _bed_slats(c, bx0, btop, _t(bed, -1), tt, brass)

    # Выхлопная труба за кабиной
    c.vline(23, 4, 19, "k")
    c.vline(24, 4, 19, tone(trim, 3) if brass else "steel2")
    c.vline(25, 4, 19, tone(trim, 1) if brass else "steel1")
    c.vline(26, 4, 4, "k")
    c.rect(22, 2, 6, 3, "oil1", "k")
    c.dot(23, 3, "steel2")
    for yy in (5, 6):
        c.hline(24, yy, 2, "oil1")  # закопчённый срез
    for yy in (11, 18):
        c.hline(23, yy, 3, "steel3" if not brass else "brass3")  # хомуты

    # Кабина и капот одним объёмом
    cab_cells = _span((6, 29, 34), (7, 27, 35), (8, 26, 36), (9, 26, 36), (10, 26, 37), (11, 26, 37),
                      *[(yy, 26, 38) for yy in range(12, 23)])
    hood = _span((14, 39, 44), (15, 39, 46), *[(yy, 39, 47) for yy in range(16, 23)])
    _blob(c, cab_cells | hood, ct)
    _cab_details(c, ct, tt, armored, brass)

    # Крыло и подножка
    _blob(c, fender | _span((22, 27, 34), (23, 27, 34), (24, 27, 34)), ft)
    if brass:
        for xx, yy in fender:
            if (xx, yy - 1) not in fender and (xx, yy - 2) not in fender and (xx, yy + 1) in fender:
                c.dot(xx, yy + 1, "brass2")
        c.hline(28, 23, 6, "brass2")

    # Фара на крыле, бампер, зеркало
    c.dot(44, 21, "k")
    c.rect(42, 16, 5, 5, tt[2], "k")
    c.clear(42, 16), c.clear(46, 16), c.clear(42, 20), c.clear(46, 20)
    c.dot(43, 17, tt[3])
    c.vline(45, 17, 3, "lamp2" if not armored else "lamp1")
    c.dot(44, 19, tt[1])
    if armored:
        c.hline(42, 16, 5, "k")  # козырёк-бронешторка
    _blob(c, _span((24, 43, 47), (25, 43, 47), (26, 43, 47)), tt)
    c.dot(37, 9, "k")
    c.dot(38, 8, "k")
    c.rect(38, 4, 3, 4, None, "k")
    c.dot(39, 5, "glass2")
    c.dot(39, 6, "steel1")

    # Брызговик и задний фонарь
    c.vline(0, 25, 5, "k")
    c.vline(1, 25, 4, "oil1")
    c.dot(1, 29, "k")
    c.dot(0, 21, "red2")
    c.dot(0, 22, "red1")


def _cab_details(c: Canvas, ct: tuple, tt: tuple, armored: bool, brass: bool) -> None:
    """Окна, двери, жалюзи капота, решётка радиатора; у бронеавтомобиля — щитки со смотровыми щелями."""
    deep, lo, base, hi = ct
    # Рамка бокового окна и швы двери
    c.rect(29, 8, 6, 6, None, deep)
    c.vline(28, 8, 14, lo)
    c.hline(28, 21, 10, lo)
    c.vline(38, 15, 7, deep)
    c.vline(39, 16, 6, hi)
    if armored:
        c.rect(30, 9, 4, 4, base)
        c.hline(30, 9, 4, hi)
        c.hline(30, 11, 4, "k")  # смотровая щель
        c.dot(31, 11, "glass1")
        for xx, yy in ((35, 8), (35, 9), (36, 10), (36, 11), (37, 12), (37, 13)):
            c.dot(xx, yy, base)
        c.rivets(27, 9, 4, 3, hi, deep, vertical=True)
        c.rivets(30, 18, 3, 3, hi, deep)
    else:
        glass = {(30, 9): "glass0", (31, 9): "glass1", (32, 9): "glass2", (33, 9): "glass2",
                 (30, 10): "glass1", (31, 10): "glass2", (32, 10): "glass2", (33, 10): "glass1",
                 (30, 11): "glass2", (31, 11): "glass2", (32, 11): "glass1", (33, 11): "glass0",
                 (30, 12): "glass2", (31, 12): "glass1", (32, 12): "glass0", (33, 12): "glass0"}
        for (xx, yy), col in glass.items():
            c.dot(xx, yy, col)
        for xx, yy in ((35, 8), (35, 9), (36, 10), (36, 11), (37, 12), (37, 13)):  # лобовое стекло в профиль
            c.dot(xx, yy, "glass2" if yy < 10 else "glass1")
        c.dot(30, 16, tt[3])  # ручка двери
        c.dot(31, 16, tt[1])
    c.rivets(33, 19, 2, 3, hi)
    # Жалюзи капота
    for lx in (41, 43):
        c.vline(lx, 16, 3, deep)
        c.dot(lx + 1, 18, hi)
    c.hline(40, 15, 6, hi)
    # Решётка радиатора
    c.vline(45, 16, 7, tt[1])
    for yy in range(16, 23):
        c.dot(46, yy, ("k" if yy % 2 else tt[1]) if armored else ("k" if yy % 2 else tt[3]))
    c.dot(44, 13, tt[3])  # пробка радиатора
    c.dot(45, 13, tt[1])
    if brass:
        c.hline(27, 15, 11, "brass2")  # латунный молдинг по поясу
        c.hline(40, 15, 6, "brass3")
        c.dot(27, 15, "brass1")


def _bed_slats(c: Canvas, x0: int, top: int, bt: tuple, tt: tuple, brass: bool) -> None:
    """Дощатый борт кузова от x0 до _BED_X1, верх top, низ — строка 22: брус, доски, стойки с болтами."""
    deep, lo, base, hi = bt
    x1, bottom = _BED_X1, 22
    w = x1 - x0 + 1
    c.rect(x0, top, w, bottom - top + 1, base, "k")
    c.hline(x0 + 1, top + 1, w - 2, tt[3] if brass else hi)
    c.hline(x0 + 1, top + 2, w - 2, tt[1] if brass else lo)
    for yy in range(top + 3, bottom - 1):
        k = (yy - top - 3) % 3
        c.hline(x0 + 1, yy, w - 2, hi if k == 0 else (base if k == 1 else deep))
    c.hline(x0 + 1, bottom - 1, w - 2, "oil1")
    for sx in (x0 + 1, (x0 + x1) // 2, x1 - 2):
        c.vline(sx, top + 1, bottom - top - 1, hi)
        c.vline(sx + 1, top + 1, bottom - top - 1, deep)
        for yy in (top + 4, bottom - 3):
            c.dot(sx, yy, tt[3])
            c.dot(sx + 1, yy, tt[1])
    if brass:
        c.hline(x0 + 1, bottom - 4, w - 2, "brass1")


def _bed_armored(c: Canvas, ct: tuple) -> None:
    """Бронекузов: скошенные листы на заклёпках, башенка со щелью, бойницы, броне-юбка над колёсами."""
    at = _t("steel", -1)
    deep, lo, base, hi = at
    body = _span((8, 3, 20), (9, 2, 21), (10, 1, 22), *[(yy, 0, 22) for yy in range(11, 23)])
    _blob(c, body, at)
    turret = _span((3, 9, 14), (4, 8, 15), (5, 8, 15), (6, 8, 15), (7, 8, 15))
    _blob(c, turret, at)
    c.hline(9, 5, 5, "k")
    c.dot(10, 5, "glass1")
    c.dot(11, 3, hi)
    for sx in (8, 15):  # швы листов
        c.vline(sx, 11, 11, deep)
        c.vline(sx + 1, 11, 11, hi)
    c.hline(1, 16, 21, deep)
    c.rivets(3, 11, 7, 3, hi, deep)
    c.rivets(2, 20, 7, 3, hi, deep)
    c.hline(3, 13, 4, "k")  # смотровые щели
    c.hline(17, 13, 4, "k")
    c.dot(4, 14, hi)
    c.dot(18, 14, hi)
    c.rect(11, 17, 3, 3, "k")  # бойница
    c.dot(12, 18, "oil2")
    # антенна
    c.vline(1, 0, 8, "steel1")
    c.dot(1, 0, "steel3")
    # Броне-юбка над задними колёсами
    skirt = _span(*[(yy, 1, 22) for yy in range(23, 28)])
    _blob(c, skirt, at)
    c.rivets(3, 25, 7, 3, hi, deep)


def _truck_cargo(c: Canvas, cargo: str, x0: int, btop: int) -> None:
    """Груз в кузове: рисуется до бортов, низ груза утоплен за брус на 3 строки."""
    w = _BED_X1 - x0
    lay = c.layer(w, 16)
    bottom = 15
    if cargo == "crates":
        crate(lay, 0, bottom - 7, 8)
        crate(lay, 8, bottom - 7, 8)
        crate(lay, 16, bottom - 5, 6) if w >= 22 else None
        crate(lay, 4, bottom - 13, 6)
    elif cargo == "barrels":
        for i in range(0, w - 6, 7):
            barrel(lay, i, bottom - 8)
    else:
        _heap(lay, 0, bottom, w, 8, cargo)
    _outline(lay)
    c.paste(lay, x0 + 1, btop + 3 - 16)


def _heap(c: Canvas, x0: int, bottom: int, w: int, peak: int, res: str) -> None:
    """Горка руды/угля: профиль-синус с шумом, блик на левом склоне, тень на правом, комья и искры."""
    lo, mid, hi = ("coal0", "coal1", "coal2") if res == "coal" else ("ore0", "ore1", "ore2")
    glint = "steel3" if res == "coal" else "brass3"
    hs = []
    for i in range(w):
        f = math.sin(math.pi * (i + 0.5) / w)
        hs.append(max(2, round(peak * f ** 0.55) + (c.rnd.choice((-1, 0, 0, 1)) if f > 0.35 else 0)))
    cx = w / 2
    for i, h in enumerate(hs):
        topy = bottom - h + 1
        for yy in range(topy, bottom + 1):
            depth = yy - topy
            if depth <= 1:
                col = hi if i < cx + 1 else mid
            elif i > cx + 2 and c.threshold(x0 + i, yy, "checker") < 0.5:
                col = lo
            else:
                col = mid if depth < 4 or c.threshold(x0 + i, yy, "bayer4") > 0.3 else lo
            c.dot(x0 + i, yy, col)
    for _ in range(w // 3):  # комья
        i = c.rnd.randrange(1, w - 2)
        yy = bottom - c.rnd.randrange(1, max(2, hs[i] - 1))
        c.dot(x0 + i, yy, hi)
        c.dot(x0 + i + 1, yy + 1, lo)
    for _ in range(3):
        i = c.rnd.randrange(2, w - 2)
        c.dot(x0 + i, bottom - hs[i] + 2, glint)


# --- Поезд ---------------------------------------------------------------------------------------------


def locomotive(c: Canvas, x: int, y: int) -> None:
    """Паровоз в габарите LOCO_W×LOCO_H лицом вправо; x — левый край, y — уровень рельса (низ колёс)."""
    lay = c.layer(LOCO_W, LOCO_H)
    L = LOCO_H - 1
    lay.box(0, L - 23, 10, 16, "rust", base=2)
    lay.rect(-1, L - 24, 12, 2, "oil1", "k")
    lay.rect(2, L - 20, 5, 4, "k")
    lay.rect(3, L - 19, 3, 2, "lamp1")
    lay.rect(9, L - 18, 22, 10, "oil1", "k")
    lay.rect(30, L - 19, 5, 12, "oil0", "k")
    lay.box(26, L - 25, 4, 7, "oil", base=1)
    lay.rect(0, L - 8, 35, 2, "oil1")
    for wx in (6, 14, 22):
        lay.shaded_disk(wx, L - 3, 3, "red", outline="k")
    top = y - L
    c.paste(lay, x, top)


def wagon(c: Canvas, x: int, y: int, kind: str = "box", color: str = "rust") -> None:
    """Вагон WAGON_W×WAGON_H: box (крытый) | hopper (полувагон с углём/рудой) | tank (цистерна).
    x — левый край, y — уровень рельса."""
    lay = c.layer(WAGON_W, WAGON_H)
    L = WAGON_H - 1
    lay.box(0, L - 17, WAGON_W, 12, "rust", base=2)
    for wx in (4, 9, 18, 23):
        wheel(lay, wx, L - 2, 2)
    c.paste(lay, x, y - L)


def train(c: Canvas, x: int, y: int, wagons: tuple[str, ...] = ("box", "hopper", "tank")) -> None:
    """Рельсы на уровне y, вагоны слева направо от x и паровоз в голове состава (справа)."""
    rails(c, y)
    cx = x
    for i, k in enumerate(wagons):
        wagon(c, cx, y, k, ("rust", "steel", "rust")[i % 3])
        c.hline(cx + WAGON_W, y - 4, 1, "k")
        cx += WAGON_W + 1
    locomotive(c, cx, y)


def minecart(c: Canvas, x: int, gy: int, res: str = "ore") -> None:
    """Шахтная вагонетка 16×10 с горкой руды или угля; gy — низ колёс."""
    c.poly([(x, gy - 9), (x + 16, gy - 9), (x + 14, gy - 3), (x + 2, gy - 3)], "rust1")
    wheel(c, x + 4, gy - 2, 2)
    wheel(c, x + 12, gy - 2, 2)
