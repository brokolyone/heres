"""Мелкие предметы и персонажи: рабочий, ящик, бочка, монеты, документ, постамент, часы, краска, герб,
инструменты и биржевые мелочи.

Предметы для премиальных сцен (watch, paint_can, crest) рисуются крупно по центру на постаменте —
как растение в терракотовом горшке на тёмном фоне в референсе. Свет везде падает сверху-слева:
блик на верхней/левой кромке, тень на нижней/правой, контур k.
"""

import math

from ironvein.art.canvas import Canvas, ramp

Cells = dict[tuple[int, int], str]

# --- Рабочий ---------------------------------------------------------------------------------------------

WORKER_W, WORKER_H = 11, 16  # габарит тела (без инструмента и контура): x — левый край, gy — строка под ботинками

_WPAL = {
    # каска (латунь) и фонарь
    "H": "brass3", "h": "brass2", "g": "brass1", "G": "brass0", "L": "lamp2", "l": "oil2",
    # лицо: тень под полями каски, щека, нос, глаз, усы
    "S": "skin2", "s": "skin1", "z": "skin0", "e": "k", "m": "wood0",
    # шейный платок
    "R": "red2", "r": "red1",
    # комбинезон (C свет, c тон, d тень), рукав (X блик, a свет, A тон), пуговица
    "C": "cloth2", "c": "cloth1", "d": "cloth0", "X": "steel2", "a": "cloth2", "A": "cloth1", "B": "brass2",
    # ремень, перчатки, сапоги
    "b": "wood0", "W": "wood2", "w": "wood1", "O": "wood1", "o": "wood0",
    # инструменты: дерево рукоятей и сталь
    "t": "wood2", "T": "wood1", "1": "steel1", "2": "steel2", "3": "steel3", "0": "steel0",
    # мешок (мешковина)
    "U": "paper0", "u": "wood2", "v": "wood1", "V": "wood0",
}

_HEAD = [
    "....hHHg...",
    "...hHhhgGL.",
    "..ggggggg..",
    "....mzzez..",
    "....zSSssS.",
    ".....zsmm..",
]
# Корпус (строки 6–10): с опущенной рукой, с рукой вперёд на уровне пояса, без ближней руки.
_TORSO = {
    "hang": [
        "....rRRrr..",
        "...CCXacd..",
        "...cdaAdd..",
        "...cdaAdB..",
        "...cdWwdd..",
    ],
    "fore": [
        "....rRRrr..",
        "...CCXacd..",
        "...cdaAdd..",
        "...cdaXaaW.",
        "...cCcdddw.",
    ],
    "none": [
        "....rRRrr..",
        "...CCcccd..",
        "...cCccBd..",
        "...cCcccd..",
        "...cCccdd..",
    ],
}
# Ноги (строки 11–15): стоит или шагает.
_LEGS = {
    "stand": [
        "...bbbbBb..",
        "...cCcccd..",
        "...cd.Ccd..",
        "...Oo.OOo..",
        "..ooo.oooo.",
    ],
    "stride": [
        "...bbbbBb..",
        "...cCcccd..",
        "..cCd.cCd..",
        ".OOo...OOo.",
        ".ooo...oooo",
    ],
}
# Наклон вперёд (толкает вагонетку): голова и корпус сдвинуты вперёд, задняя нога отставлена.
_LEAN = [
    "...........",
    "......hHHg..",
    ".....hHhhgGL",
    "....ggggggg.",
    "......mzzez.",
    "......zSSssS",
    ".......zsmm.",
    ".....rRRrr..",
    "....CCXaaaaW",
    "...cCcAAAAAw",
    "...cCccdd...",
    "..bbbbBb....",
    "..cCcccd....",
    ".cCd..Ccd...",
    "OOo....OOo..",
    "ooo....oooo.",
]

# Накладки поз: (начало, конец, символ, сзади) в координатах тела; сзади — не перекрывает тело.
_POSES: dict[str | None, tuple[list[str], list]] = {
    None: (_HEAD + _TORSO["hang"] + _LEGS["stand"], []),
    # кирка занесена вперёд-вверх: рукоять от пояса через кулак к обуху над головой
    "pick": (_HEAD + _TORSO["none"] + _LEGS["stand"], [
        ((8, 10), (12, 1), "t", False), ((9, 10), (13, 1), "T", False),
        ((5, 8), (7, 8), "a", False), ((5, 7), (7, 7), "X", False), ((8, 7), (8, 8), "W", False),
        ((9, 0), (10, -1), "2", False), ((11, -2), (13, -2), "3", False), ((11, -1), (13, -1), "2", False),
        ((14, -1), (14, -1), "3", False), ((14, 0), (15, 0), "2", False), ((16, 1), (17, 3), "1", False),
        ((15, 1), (15, 1), "1", False), ((16, 0), (16, 0), "2", False),
    ]),
    "sack": (_HEAD + _TORSO["none"] + _LEGS["stride"], [
        ((-1, 6), (3, 6), "u", True), ((-2, 7), (3, 7), "u", True), ((-2, 8), (3, 8), "u", True),
        ((-2, 9), (3, 9), "v", True), ((-2, 10), (3, 10), "v", True), ((-1, 11), (2, 11), "V", True),
        ((0, 5), (3, 5), "U", True), ((-1, 6), (1, 7), "U", True),
        ((4, 3), (4, 5), "V", True), ((3, 4), (3, 4), "u", True),
        ((5, 8), (5, 9), "A", False), ((5, 7), (5, 7), "X", False), ((6, 6), (6, 6), "a", False),
        ((5, 6), (5, 6), "W", False),
    ]),
    # ключ в кулаке перед собой, зевом вперёд
    "wrench": (_HEAD + _TORSO["fore"] + _LEGS["stand"], [
        ((10, 9), (13, 9), "2", False), ((11, 10), (13, 10), "1", False),
        ((14, 8), (15, 8), "3", False), ((14, 9), (14, 9), "2", False), ((14, 10), (15, 10), "1", False),
        ((14, 11), (14, 11), "0", False),
    ]),
    "cart": (_LEAN, []),
    # лупа перед собой на уровне груди: ручка из кулака вперёд-вверх
    "magnifier": (_HEAD + _TORSO["fore"] + _LEGS["stand"], [((10, 8), (11, 7), "T", False)]),
    # молоток занесён: рукоять из кулака вверх-вперёд, боёк поперёк
    "hammer": (_HEAD + _TORSO["fore"] + _LEGS["stand"], [
        ((10, 8), (12, 4), "t", False), ((11, 9), (12, 7), "T", False),
        ((11, 2), (14, 3), "2", False), ((10, 3), (13, 4), "1", False), ((11, 2), (12, 2), "3", False),
        ((14, 4), (15, 5), "1", False),
    ]),
}


def _bresenham(x0: int, y0: int, x1: int, y1: int):
    dx, dy = abs(x1 - x0), -abs(y1 - y0)
    sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
    err = dx + dy
    while True:
        yield x0, y0
        if x0 == x1 and y0 == y1:
            return
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


def _draw_cells(c: Canvas, x: int, y: int, cells: Cells, pal: dict[str, str], body_w: int, flip: bool,
                outline: str | None = "k") -> None:
    """Нарисовать клетки (i, j) → символ от (x, y) с контуром по 4 соседям; flip — зеркально
    относительно колонок тела 0..body_w-1 (x остаётся левым краем тела)."""
    def px(i: int) -> int:
        return x + (body_w - 1 - i if flip else i)

    if outline is not None:
        for (i, j) in cells:
            for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                if (i + di, j + dj) not in cells:
                    c.dot(px(i + di), y + j + dj, outline)
    for (i, j), ch in cells.items():
        c.dot(px(i), y + j, pal[ch])


def worker(c: Canvas, x: int, gy: int, tool: str | None = "pick", flip: bool = False, lamp: bool = True) -> None:
    """Рабочий 11×16 в латунной каске с фонарём (x — левый край тела, gy — строка под ботинками).

    Лицом вправо, flip — влево (инструмент остаётся впереди). tool: pick (кирка занесена вперёд-вверх,
    выступает на 7 px вперёд и 2 px вверх) | sack (мешок на плече за спиной, 2 px назад) | wrench (ключ
    перед собой) | cart (толкает вагонетку: кулаки на колонке 11, строки gy-8..gy-7) | magnifier
    (разглядывает лупой перед собой) | hammer (молоток в руке) | None (стоит). lamp — свет фонаря каски.
    """
    rows, extras = _POSES.get(tool, _POSES[None])
    cells: Cells = {}
    for j, row in enumerate(rows):
        for i, ch in enumerate(row):
            if ch != ".":
                cells[(i, j)] = ch
    for (x0, y0), (x1, y1), ch, behind in extras:
        for p in _bresenham(x0, y0, x1, y1):
            if not (behind and p in cells):
                cells[p] = ch
    top = gy - WORKER_H

    def px(i: int) -> int:
        return x + (WORKER_W - 1 - i if flip else i)

    if lamp:  # луч фонаря — до фигуры, чтобы свет лёг только на фон; только осветляет
        li, lj = next(p for p, ch in cells.items() if ch == "L")
        for k in range(1, 6):
            for dj in range(-(k // 2), k // 2 + 1):
                xx, yy = px(li + k), top + lj + dj
                level = (0.9, 0.6, 0.45, 0.3, 0.2)[k - 1] - 0.12 * abs(dj)
                if c.threshold(xx, yy, "bayer4") < level:
                    old = c.get(xx, yy)
                    col = "lamp1" if k == 1 and dj == 0 else "lamp0"
                    if old is None or sum(old) < sum(c.rgb(col)):
                        c.dot(xx, yy, col)
    _draw_cells(c, x, top, cells, _WPAL, WORKER_W, flip)
    if tool == "magnifier":  # лупа: латунный обод в контуре, стекло с бликом
        mx, my = px(13), top + 5
        c.disk(mx, my, 3, "k")
        c.ring(mx, my, 2, "brass2")
        c.disk(mx, my, 1, "glass1")
        f = -1 if flip else 1
        c.dot(mx - f, my - 1, "white")
        c.dot(mx + f, my + 1, "glass0")
        c.dot(mx - 2 * f, my - 1, "brass3")
        c.dot(mx + 2 * f, my + 1, "brass0")
        c.dot(mx + f, my + 2, "brass1")
    if lamp:
        c.dot(px(li), top + lj, "lamp2")


# --- Инструменты -----------------------------------------------------------------------------------------

def _rot(rows: list[str]) -> list[str]:
    """Повернуть символьный спрайт на 90° по часовой (верх → право): инструмент «лёжа»."""
    h, w = len(rows), max(len(r) for r in rows)
    rows = [r.ljust(w, ".") for r in rows]
    return ["".join(rows[h - 1 - j][i] for j in range(h)) for i in range(w)]


_WRENCH = [
    "h..m",
    "hm.m",
    "hmms",
    ".hs.",
    ".hs.",
    ".hs.",
    ".hs.",
    ".hs.",
    "hmms",
    "h.ms",
    "hmms",
]


def wrench(c: Canvas, x: int, y: int, ramp_name: str = "steel", lying: bool = False) -> None:
    """Гаечный ключ в контуре: открытый зев сверху, рукоять с бликом, накидное кольцо внизу.
    Стоймя 4×11 (x, y — верхний левый угол без контура); lying — лёжа 11×4, зев справа."""
    t = ramp(ramp_name)
    rows = _rot(_WRENCH) if lying else _WRENCH
    c.outline_sprite(x, y, rows, {"h": t[-1], "m": t[-2], "s": t[1]}, "k")


_HAMMER = [
    "HhhhgG",
    "hhhhgg",
    "..wW..",
    "..wW..",
    "..wW..",
    "..wW..",
    "..rR..",
    "..rR..",
    "..wW..",
]


def hammer(c: Canvas, x: int, y: int, lying: bool = False) -> None:
    """Молоток в контуре: стальной боёк с бликом, рукоять с красной обмоткой. Стоймя 6×9 (бойком
    вверх), lying — лёжа 9×6 (боёк справа)."""
    rows = _rot(_HAMMER) if lying else _HAMMER
    c.outline_sprite(x, y, rows, {"H": "steel3", "h": "steel2", "g": "steel1", "G": "steel0",
                                   "w": "wood2", "W": "wood1", "r": "red1", "R": "red0"}, "k")


def caliper(c: Canvas, x: int, y: int) -> None:
    """Штангенциркуль 16×7 лёжа (без контура): линейка со шкалой, губки вниз и вверх, подвижная
    рамка с латунным винтом."""
    c.outline_sprite(x, y, [
        ".3..3...........",
        "3333333333333332",
        "2k2k22k2k2k2k2k1",
        "2122121111111111",
        "21.21...........",
        "21.21...........",
        "1..1............",
    ], {"3": "steel3", "2": "steel2", "1": "steel1", "k": "steel0"}, "k")
    c.dot(x + 4, y, "brass3")  # винт фиксатора
    c.dot(x + 4, y - 1, "k")


def magnifier(c: Canvas, x: int, y: int) -> None:
    """Лупа 10×10: латунный обод в контуре, голубое стекло с бликом, деревянная ручка вниз-вправо."""
    cx, cy = x + 3, y + 3
    c.line(cx + 2, cy + 3, x + 9, y + 9, "k")
    c.line(cx + 3, cy + 2, x + 9, y + 8, "k")
    c.line(cx + 3, cy + 3, x + 8, y + 8, "wood2")
    c.dot(x + 9, y + 9, "wood0")
    c.dot(cx + 3, cy + 3, "brass1")
    c.disk(cx, cy, 3, "k")
    c.ring(cx, cy, 2, "brass2")
    c.dot(cx - 2, cy - 1, "brass3")
    c.dot(cx - 1, cy - 2, "brass3")
    c.dot(cx + 2, cy + 1, "brass0")
    c.dot(cx + 1, cy + 2, "brass0")
    c.disk(cx, cy, 1, "glass1")
    c.dot(cx - 1, cy - 1, "white")
    c.dot(cx + 1, cy + 1, "glass0")


# --- Ящики, бочки, мешки ---------------------------------------------------------------------------------

def _ground_shadow(c: Canvas, x: int, y: int, w: int) -> None:
    """Контактная тень строкой y под предметом шириной w, со сдвигом вправо (свет слева) и рваным краем."""
    for xx in range(x + 1, x + w + 1):
        if xx < x + w - 1 or c.threshold(xx, y, "checker") < 0.5:
            c.dot(xx, y, "oil0")


def crate(c: Canvas, x: int, y: int, s: int = 8, w: int | None = None, stencil: bool = True,
          shadow: bool = True) -> None:
    """Деревянный ящик s×s (или w×s; x, y — верхний левый угол): каркас из брусков (верх и лево на
    свету, право и низ в тени), щит из досок со стыками и волокнами, диагональная распорка,
    гвозди по углам, красное клеймо, контактная тень строкой ниже."""
    w = s if w is None else w
    h = s
    c.rect(x, y, w, h, "wood1", "k")
    # щит: доски по две строки, стыки тёмные, волокна — светлые и тёмные точки
    for yy in range(y + 2, y + h - 2):
        k = yy - y - 2
        if k % 2 == 1 and yy < y + h - 3:
            c.hline(x + 2, yy, w - 4, "wood0")
        else:
            for xx in range(x + 2, x + w - 2):
                v = (xx * 7 + yy * 13) % 11
                if v == 0:
                    c.dot(xx, yy, "wood2")
                elif v == 5:
                    c.dot(xx, yy, "wood0")
    # каркас
    c.hline(x + 1, y + 1, w - 2, "wood2")
    c.hline(x + 1, y + 1, w // 2, "paper0")
    c.vline(x + 1, y + 2, h - 3, "wood2")
    c.vline(x + w - 2, y + 2, h - 3, "wood0")
    c.hline(x + 2, y + h - 2, w - 3, "wood0")
    c.dot(x + 1, y + h - 2, "wood1")
    # распорка снизу-слева вверх-вправо: светлая кромка, тень под ней
    c.line(x + 2, y + h - 3, x + w - 3, y + 2, "wood2")
    if h >= 8:
        c.line(x + 3, y + h - 3, x + w - 3, y + 3, "wood0")
    # гвозди
    c.dot(x + 1, y + 1, "steel3")
    for gx, gy_ in ((x + w - 2, y + 1), (x + 1, y + h - 2), (x + w - 2, y + h - 2)):
        c.dot(gx, gy_, "steel1")
    if stencil and w >= 9:  # клеймо отправителя
        c.dot(x + w - 4, y + h - 4, "red1")
        c.dot(x + w - 3, y + h - 4, "red1")
        c.dot(x + w - 3, y + h - 5, "red0")
    if shadow:
        _ground_shadow(c, x, y + h, w)


_BARREL = [
    ".kkkkk.",
    "k01310k",
    "kabcdek",
    "kHIJKLk",
    "kabcdek",
    "kabcdek",
    "kHIJKLk",
    "kabcdek",
    ".kkkkk.",
]


def barrel(c: Canvas, x: int, y: int, ramp_name: str = "oil", hoops: str = "brass", shadow: bool = True) -> None:
    """Бочка 7×9 (x, y — верхний левый угол): стальная крышка с пробкой, цилиндр по колонкам (тёмная
    кромка, стальной блик, тон, тень), два обруча-зига, контактная тень строкой ниже.
    ramp_name — краска бочки (oil — чёрная под мазут, rust, steel, green, red), hoops — металл обручей."""
    t = ramp(ramp_name)
    spec = "steel1" if ramp_name == "oil" else t[-1]
    hp = ramp(hoops)
    pal = {"k": "k", "0": "steel0", "1": "steel1", "3": "steel3",
           "a": t[1], "b": spec, "c": t[-1] if ramp_name == "oil" else t[-2], "d": t[1], "e": t[0],
           "H": hp[1], "I": hp[3], "J": hp[2], "K": hp[1], "L": hp[0]}
    c.sprite(x, y, _BARREL, pal)
    if shadow:
        _ground_shadow(c, x, y + 9, 7)


def sack(c: Canvas, x: int, gy: int) -> None:
    """Мешок 8×9 из мешковины, перевязанный верёвкой (x — левый край, gy — строка под мешком)."""
    c.outline_sprite(x, gy - 9, [
        "...VV...",
        "..UuuV..",
        ".UUuuvv.",
        "UUuuuuvV",
        "Uuuuuuvv",
        "uuuuuvvV",
        "uuvuuvvV",
        ".vvvvvV.",
    ], _WPAL, "k")
    c.dot(x + 3, gy - 8, "brass1")  # верёвка
    _ground_shadow(c, x, gy, 8)


# --- Монеты и биржа --------------------------------------------------------------------------------------

_COIN_WOBBLE = (0, 1, 1, 0, -1, 0, 0, 1)


def coin_stack(c: Canvas, x: int, gy: int, n: int) -> None:
    """Столбик из n латунных монет 8×2 (x — левый край, gy — строка под столбиком): гурт с насечкой,
    блик слева, тень справа, монеты чуть гуляют; сверху аверс с чеканкой и искрой.
    Высота 2n + 3 строки."""
    _ground_shadow(c, x - 1, gy, 10)
    for i in range(n):
        cx = x + _COIN_WOBBLE[i % len(_COIN_WOBBLE)]
        cy = gy - 2 - i * 2
        c.dot(cx - 1, cy, "k")
        c.dot(cx + 8, cy, "k")
        c.dot(cx - 1, cy + 1, "k")
        c.dot(cx + 8, cy + 1, "k")
        for k, col in enumerate(("brass2", "brass3", "brass2", "brass2", "brass2", "brass2", "brass1", "brass1")):
            c.dot(cx + k, cy, col)
        for k in range(8):  # гурт с насечкой
            c.dot(cx + k, cy + 1, ("brass2" if k < 2 else "brass1") if k % 2 == 0 else "brass0")
    tx = x + _COIN_WOBBLE[(n - 1) % len(_COIN_WOBBLE)]
    ty = gy - 2 * n - 2  # аверс верхней монеты: эллипс в две строки над гуртом
    c.hline(tx, ty - 1, 8, "k")
    c.dot(tx - 1, ty, "k")
    c.dot(tx + 8, ty, "k")
    c.dot(tx - 1, ty + 1, "k")
    c.dot(tx + 8, ty + 1, "k")
    c.sprite(tx, ty, ["HHhhhhhg", "hhgGGghg"], {"H": "brass3", "h": "brass2", "g": "brass1", "G": "brass0"})
    c.dot(tx + 1, ty, "white")


def coin(c: Canvas, cx: int, cy: int, r: int = 4) -> None:
    """Крупная монета аверсом к зрителю: латунный диск в контуре, ободок, шестерня-чекан, блик."""
    c.shaded_disk(cx, cy, r, "brass", base=2)
    c.ring(cx, cy, r - 1, "brass1")
    c.disk(cx, cy, max(1, r - 3), "brass1")
    c.dot(cx, cy, "brass0")
    c.dot(cx - 1, cy - 1, "brass3")
    c.sparkle(cx - r + 1, cy - r + 1, "white", 1, "brass3")


def ticker_arrow(c: Canvas, x: int, y: int, up: bool = True) -> None:
    """Стрелка биржевой котировки 5×5 в контуре: зелёная вверх или красная вниз."""
    rows = ["..h..", ".hhm.", "hhmmm", ".hm..", ".hm.."]
    if not up:
        rows = rows[::-1]
    r = "green" if up else "red"
    c.outline_sprite(x, y, rows, {"h": f"{r}2", "m": f"{r}1"}, "k")


def ticker_tape(c: Canvas, x: int, y: int, w: int = 20) -> None:
    """Лента биржевого телеграфа шириной w (y — верх ленты): бумажная полоса волной, пробитые знаки,
    завиток рулончиком на конце."""
    for i in range(w):
        yy = y + (1 if (i // 4) % 2 else 0)
        c.dot(x + i, yy - 1, "k")
        c.dot(x + i, yy, "paper2" if (i // 4) % 2 == 0 else "paper1")
        c.dot(x + i, yy + 1, "paper1" if (i // 4) % 2 == 0 else "paper0")
        c.dot(x + i, yy + 2, "k")
        if i % 3 == 1:
            c.dot(x + i, yy + (i // 3) % 2, "oil1")
    c.disk(x + w + 1, y + 1, 2, "k")
    c.ring(x + w + 1, y + 1, 1, "paper1")
    c.dot(x + w, y, "paper2")
    c.dot(x + w + 1, y + 1, "paper0")


def price_tag(c: Canvas, x: int, y: int) -> None:
    """Ценник 8×5 на бечёвке: бумажная бирка со срезанными углами, люверс, цифры чернилами."""
    c.line(x - 1, y + 1, x - 3, y - 2, "paper0")
    c.outline_sprite(x, y, [
        ".PPPPPPp",
        "PoPkPkkp",
        "PPPkPkPp",
        ".ppppp0.",
    ], {"P": "paper2", "p": "paper0", "o": "k", "k": "oil1", "0": "paper0"}, "k")
    c.dot(x + 1, y + 1, "brass2")


def banknote(c: Canvas, x: int, y: int) -> None:
    """Банкнота 11×6: зелёная бумага с каймой, овал с портретом, номинал, печать."""
    c.rect(x, y, 11, 6, "green1", "k")
    c.rect(x + 1, y + 1, 9, 4, None, "green2")
    c.disk(x + 5, y + 3, 1, "paper1")
    c.dot(x + 5, y + 3, "green0")
    c.dot(x + 2, y + 2, "paper2")
    c.dot(x + 8, y + 3, "red1")


# --- Документ --------------------------------------------------------------------------------------------

def document(c: Canvas, x: int, y: int, stamp: bool = True) -> None:
    """Контракт 24×29 (x, y — верхний левый угол листа): тень листа, бумага с пятнами и загнутым
    углом, скрепка, эмблема и заголовок с красной двойной чертой, строки текста словами, чернильная
    подпись над чертой, сургучная печать с лентами."""
    c.rect(x + 1, y + 1, 24, 29, "sky0")  # тень листа
    c.box(x, y, 24, 29, "paper", outline="k", base=1)
    for k in range(9):  # пятна старой бумаги
        c.dot(x + 2 + (k * 7) % 20, y + 3 + (k * 11) % 24, "paper0")
    c.poly([(x + 18, y), (x + 24, y), (x + 24, y + 6)], "bg")  # загнутый угол
    c.poly([(x + 18, y), (x + 18, y + 6), (x + 24, y + 6)], "paper2")
    c.line(x + 18, y, x + 23, y + 5, "k")
    c.line(x + 19, y + 2, x + 21, y + 4, "paper1")
    c.vline(x + 18, y + 1, 6, "paper0")
    c.hline(x + 18, y + 6, 6, "k")
    c.dot(x + 23, y + 6, "paper0")
    # скрепка
    c.rect(x + 3, y - 2, 3, 6, None, "steel2")
    c.dot(x + 3, y - 2, "steel3")
    c.dot(x + 5, y + 3, "steel1")
    # эмблема-шестерня и заголовок
    c.sprite(x + 7, y + 2, [".b.", "bkb", ".b."], {"b": "brass1", "k": "paper0"})
    for i, ln in enumerate((3, 2, 3)):
        c.hline(x + 10 + i * 4 - (1 if i == 0 else 0), y + 3, ln, "oil1")
    c.hline(x + 4, y + 6, 14, "red1")
    c.hline(x + 4, y + 7, 14, "paper0")
    # строки текста словами (красная строка — с отступом)
    for j, row in enumerate(range(y + 9, y + 21, 2)):
        xx = x + (5 if j in (0, 3) else 3)
        end = x + 21 - (j * 5 % 4)
        k = j
        while xx < end:
            ln = 2 + (k * 3) % 4
            c.hline(xx, row, min(ln, end - xx), "cloth0")
            xx += ln + 1
            k += 1
    # подпись: росчерк синими чернилами над чертой
    c.hline(x + 3, y + 26, 11, "paper0")
    for a, b in (((3, 25), (5, 22)), ((5, 22), (6, 25)), ((6, 25), (8, 23)), ((8, 23), (9, 25)),
                 ((9, 25), (13, 23))):
        c.line(x + a[0], y + a[1], x + b[0], y + b[1], "cloth0")
    c.dot(x + 4, y + 24, "cloth1")
    if stamp:  # сургуч: ленты, капля с тиснением, блик
        sx, sy = x + 18, y + 23
        c.poly([(sx - 3, sy + 2), (sx - 1, sy + 2), (sx - 2, sy + 8), (sx - 3, sy + 7), (sx - 4, sy + 8)], "red0")
        c.poly([(sx + 1, sy + 2), (sx + 3, sy + 2), (sx + 4, sy + 8), (sx + 3, sy + 7), (sx + 2, sy + 8)], "red1")
        c.shaded_disk(sx, sy, 4, "red", outline="k", base=1)
        c.dot(sx + 4, sy - 2, "red1")  # наплыв сургуча
        c.dot(sx - 4, sy + 2, "red1")
        c.ring(sx, sy, 2, "red0")
        c.sprite(sx - 1, sy - 1, [".r.", "rRr", ".r."], {"r": "red0", "R": "red2"})
        c.dot(sx - 2, sy - 3, "red2")
        c.dot(sx - 3, sy - 2, "red2")


# --- Постамент и премиальные предметы ---------------------------------------------------------------------

def _col_tone(f: float, xx: int, yy: int, n: int) -> int:
    """Тон цилиндра по доле ширины f (0 — левый край): узкий блик, свет, тон, тень; швы — шахматкой."""
    edges = (0.1, 0.4, 0.78) if n >= 4 else (0.3, 0.75)
    idx = n - 1
    for e in edges:
        if f >= e:
            idx -= 1
    for e in edges:  # дизерный шов шириной ~6% по обе стороны границы
        if abs(f - e) < 0.05 and Canvas.threshold(xx, yy, "checker") < 0.5:
            idx = max(0, min(n - 1, idx + (1 if f >= e else -1)))
    return max(0, idx)


def pedestal(c: Canvas, cx: int, gy: int, w: int = 33, ramp_name: str = "rust", cushion: bool = False) -> None:
    """Терракотовый горшок-постамент как в референсе. gy — нижняя строка венчика, его верх — gy-3
    (на эту строку ставят предмет), w — ширина венчика. Венчик со скруглёнными краями и бликом,
    тень под ним, тело-трапеция с объёмом по колонкам, рельефный поясок, ножка, тень на полу.
    Высота ≈ w/4 + 8. cushion — бархатная подушка на венчике (верх подушки — gy-5)."""
    t = ramp(ramp_name)
    n = len(t)
    hw = w // 2
    body = max(6, w // 4)
    top = gy + 1
    # тень на полу — шире ножки, рваные края
    fy = top + body
    for xx in range(cx - hw + 2, cx + hw):
        if abs(xx - cx - 1) < hw - 4 or c.threshold(xx, fy + 3, "checker") < 0.5:
            c.dot(xx + 1, fy + 3, "oil0")
    # тело: трапеция, сужается книзу
    for j in range(body):
        inset = 2 + round(4 * j / max(1, body - 1))
        x0, x1 = cx - hw + inset, cx + hw - inset
        for xx in range(x0, x1 + 1):
            f = (xx - x0) / max(1, x1 - x0)
            c.dot(xx, top + j, t[_col_tone(f, xx, top + j, n)])
        c.dot(x0 - 1, top + j, "k")
        c.dot(x1 + 1, top + j, "k")
    c.hline(cx - hw + 2, top, 2 * hw - 3, t[0])  # тень под венчиком
    c.dither(cx - hw + 3, top + 1, 2 * hw - 5, 1, None, t[0], 0.5)
    # рельефный поясок: тёмный жёлоб и светлый валик
    by = top + body // 2 + 1
    for xx in range(cx - hw + 3, cx + hw - 2):
        if c.get(xx, by) is not None and c.get(xx, by) != c.rgb("k"):
            f = (xx - (cx - hw + 3)) / (2 * hw - 6)
            c.dot(xx, by, t[0])
            c.dot(xx, by + 1, t[min(n - 1, _col_tone(f, xx, by + 1, n) + 1)])
    # ножка
    c.rect(cx - hw + 6, fy, 2 * hw - 11, 3, t[1], "k")
    c.hline(cx - hw + 7, fy + 1, 2 * hw - 13, t[2])
    c.dot(cx - hw + 7, fy + 1, t[-1])
    # венчик: скруглённые углы, верхняя кромка на свету, нижняя губа в тени
    x0, x1 = cx - hw, cx + hw
    c.rect(x0, gy - 3, 2 * hw + 1, 4, t[2], "k")
    c.clear(x0, gy - 3)
    c.clear(x1, gy - 3)
    c.dot(x0 + 1, gy - 3, "k")
    c.dot(x1 - 1, gy - 3, "k")
    for xx in range(x0 + 1, x1):
        f = (xx - x0) / (x1 - x0)
        c.dot(xx, gy - 2, t[min(n - 1, _col_tone(f, xx, gy - 2, n) + 1)])
        c.dot(xx, gy - 1, t[_col_tone(f, xx, gy - 1, n)])
        c.dot(xx, gy, t[max(0, _col_tone(f, xx, gy, n) - 1)])
    c.hline(x0 + 3, gy - 2, 2, "white")
    c.dot(x0 + 6, gy - 2, t[-1])
    if cushion:  # бархатная подушка с кистями
        c.rect(cx - hw + 5, gy - 5, 2 * hw - 9, 3, "red1", "k")
        c.hline(cx - hw + 6, gy - 4, 2 * hw - 11, "red2")
        c.dot(cx - hw + 4, gy - 3, "brass2")
        c.dot(cx + hw - 4, gy - 3, "brass1")


def _bezier(p0, p1, p2, steps: int) -> list[tuple[int, int]]:
    """Точки квадратичной кривой Безье без повторов (провисающая цепочка, дужка)."""
    out: list[tuple[int, int]] = []
    for i in range(steps + 1):
        u = i / steps
        px = (1 - u) ** 2 * p0[0] + 2 * u * (1 - u) * p1[0] + u * u * p2[0]
        py = (1 - u) ** 2 * p0[1] + 2 * u * (1 - u) * p1[1] + u * u * p2[1]
        q = (round(px), round(py))
        if not out or out[-1] != q:
            out.append(q)
    return out


def watch(c: Canvas, cx: int, cy: int, r: int = 12) -> None:
    """Карманные часы инженера радиусом r с центром (cx, cy): латунный корпус с фаской, рифлёная
    заводная головка и ушко, цепочка провисает вправо до низа корпуса и лежит звеньями с брелоком,
    циферблат со светом сверху-слева, 12 меток, малая секундная шкала, стрелки 10:10, блик на стекле.
    Низ корпуса — cy + r, цепочка лежит на строке cy + r + 1."""
    # цепочка: от ушка дугой вправо и вниз, затем лежит звеньями на постаменте
    chain = _bezier((cx + 2, cy - r - 5), (cx + r + 9, cy - r + 2), (cx + r - 1, cy + r), 40)
    chain += [(cx + r + i, cy + r) for i in range(0, 5)]
    for px, py in chain:
        c.dot(px + 1, py + 1, "k")
    for i, (px, py) in enumerate(chain):
        c.dot(px, py, ("brass3", "brass1", "brass0")[i % 3])
    fx, fy = cx + r + 5, cy + r  # брелок-ключик: кольцо и бородка
    c.ring(fx + 1, fy - 1, 1, "k")
    c.dot(fx + 1, fy - 2, "brass3")
    c.dot(fx, fy - 1, "brass2")
    c.dot(fx + 2, fy - 1, "brass1")
    c.dot(fx + 1, fy, "brass1")
    c.hline(fx + 3, fy - 1, 3, "brass2")
    c.dot(fx + 5, fy, "brass1")
    c.hline(fx + 3, fy - 2, 3, "k")
    c.hline(fx + 3, fy, 2, "k")
    # ушко и головка
    c.ring(cx, cy - r - 5, 2, "k")
    c.ring(cx, cy - r - 5, 1, "brass2")
    c.dot(cx - 1, cy - r - 6, "brass3")
    c.rect(cx - 3, cy - r - 3, 7, 4, "brass1", "k")
    for i in range(5):  # насечка
        c.dot(cx - 2 + i, cy - r - 2, "brass3" if i % 2 == 0 else "brass0")
    c.dot(cx - 2 + 0, cy - r - 1, "brass2")
    c.shaded_disk(cx, cy, r, "brass", base=2)
    for dy in range(-r, r + 1):  # фаска: свет на верхне-левой дуге, тень на нижне-правой
        for dx in range(-r, r + 1):
            if c.in_disk(dx, dy, r - 1) and not c.in_disk(dx, dy, r - 2):
                d = dx + dy
                c.dot(cx + dx, cy + dy, "brass3" if d < -r // 2 else "brass0" if d > r // 2 else "brass2")
    d = r - 3
    c.disk(cx, cy, d, "paper1")
    for dy in range(-d, d + 1):  # свет на циферблате сверху-слева, тень снизу-справа
        for dx in range(-d, d + 1):
            if not c.in_disk(dx, dy, d):
                continue
            s = dx + dy
            if s < -d // 2 or (s < -d // 4 and c.threshold(cx + dx, cy + dy, "checker") < 0.5):
                c.dot(cx + dx, cy + dy, "paper2")
            elif s > d or (s > d * 3 // 4 and c.threshold(cx + dx, cy + dy, "checker") < 0.5):
                c.dot(cx + dx, cy + dy, "paper0")
    c.ring(cx, cy, d, "brass0")
    for k in range(12):  # метки: на 12, 3, 9 — двойные
        a = k * math.pi / 6
        mx, my = round(cx + math.sin(a) * (d - 1)), round(cy - math.cos(a) * (d - 1))
        if k == 6:
            continue
        c.dot(mx, my, "k" if k % 3 == 0 else "wood1")
        if k % 3 == 0:
            c.dot(round(cx + math.sin(a) * (d - 2)), round(cy - math.cos(a) * (d - 2)), "k")
    # малая секундная шкала на «6»
    sx, sy = cx, cy + d // 2 + 1
    c.ring(sx, sy, 2, "paper0")
    c.dot(sx, sy, "k")
    c.dot(sx - 1, sy - 1, "red1")
    # стрелки 10:10: минутная воронёная длиннее, часовая чёрная
    m_end = (round(cx + math.sin(math.pi / 3) * (d - 2)), round(cy - math.cos(math.pi / 3) * (d - 2)))
    h_end = (round(cx - math.sin(math.pi / 3) * (d - 4)), round(cy - math.cos(math.pi / 3) * (d - 4)))
    c.line(cx, cy, *m_end, "cloth0")
    c.line(cx, cy - 1, *h_end, "k")
    c.line(cx, cy, *h_end, "k")
    c.dot(cx, cy, "brass3")
    # блик на стекле
    c.line(cx - d + 2, cy - 2, cx - 2, cy - d + 2, "white")
    c.dot(cx - d + 3, cy - d + 4, "white")
    c.dot(cx + d - 3, cy + 2, "paper2")
    c.sparkle(cx - r + 2, cy - r + 2, "white", 1, "brass3")


_BRUSH = [
    "..kkk..",
    ".kOook.",
    "kOooook",
    "kooooik",
    ".kooik.",
    ".kBBbk.",
    ".kBbbk.",
    "..ktk..",
    "..ktk..",
    "..ktk..",
    "..ktk..",
    "..ktk..",
    "..ktk..",
    "..kTk..",
    "...k...",
]


def paint_can(c: Canvas, cx: int, cy: int, ramp_name: str = "oil", trim: str = "brass", brush: bool = True) -> None:
    """Банка премиальной краски с центром (cx, cy): цилиндр 21 px (блик, тон, тень и холодный контровой
    свет справа — чтобы чёрная банка читалась на тёмном фоне), латунная крышка-эллипс с канавкой и
    мазком краски, дужка-ручка, кремовая этикетка с образцом «чёрный с латунью», глянцевый потёк через
    этикетку, латунный поясок у дна, лужица; brush — кисть щетиной вверх справа.
    Габарит ≈ 31×28: дужка от cy-16, низ дна — cy+11 (ставить на верх постамента: cy = верх - 11)."""
    t = ramp(ramp_name)
    tr = ramp(trim)
    hw, e = 10, 3
    x0, x1 = cx - hw, cx + hw
    top, bot = cy - 6, cy + 7  # оси верхнего и нижнего эллипсов

    def arc(xx: int, a: int = hw, b: int = e) -> int:
        q = (xx - cx) / (a + 0.5)
        return round(b * math.sqrt(max(0.0, 1 - q * q)))

    # дужка-ручка: стальная проволока от ушек, за крышкой
    bail = _bezier((x0 + 1, top + 2), (cx, top - 21), (x1 - 1, top + 2), 48)
    for px, py in bail:
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            if (px + dx, py + dy) not in bail:
                c.dot(px + dx, py + dy, "k")
    for px, py in bail:
        c.dot(px, py, "steel3" if px < cx - 3 else "steel2" if px < cx + 4 else "steel1")
    # тело: тон по колонке, крайняя правая — контровой свет
    tone = {}
    for xx in range(x0, x1 + 1):
        tone[xx] = _col_tone((xx - x0) / (x1 - x0), xx, 0, 4)
        col = {3: "steel1", 2: t[2], 1: t[1], 0: t[0]}[tone[xx]]
        c.vline(xx, top, bot - top + arc(xx) + 1, "steel0" if xx == x1 else col)
        c.dot(xx, bot + arc(xx) + 1, "k")
    c.vline(x0 - 1, top, bot - top + 1, "k")
    c.vline(x1 + 1, top, bot - top + 1, "k")

    def ring_row(y0: int, cols: tuple[str, str, str, str]) -> None:
        for xx in range(x0, x1 + 1):
            c.dot(xx, y0 + arc(xx), cols[tone[xx]])

    ring_row(bot, (tr[0], tr[1], tr[2], tr[3]))  # латунный поясок у дна
    ring_row(bot - 1, (tr[0], tr[0], tr[1], tr[2]))
    # этикетка: кремовая бумага по колонкам, тёмные кромки
    paper = ("paper0", "paper1", "paper2", "paper2")
    for yy in range(top + 4, top + 11):
        ring_row(yy, paper)
    ring_row(top + 3, ("k",) * 4)
    ring_row(top + 11, ("k",) * 4)
    ring_row(top + 10, ("paper0", "paper0", "paper1", "paper1"))
    # образец краски: чёрный квадрат с латунной полосой, «надписи» по сторонам
    ly = top + 5 + arc(cx)
    c.rect(cx - 3, ly, 7, 5, t[1], "k")
    c.hline(cx - 2, ly + 2, 5, tr[2])
    c.dot(cx - 2, ly + 2, tr[3])
    c.dot(cx - 2, ly + 1, t[2])
    for k, xx in enumerate((x0 + 2, x0 + 3, x0 + 4, x1 - 4, x1 - 3, x1 - 2)):
        c.dot(xx, ly + 1 + arc(xx) - arc(cx), "wood0")
        if k % 3 != 2:
            c.dot(xx, ly + 3 + arc(xx) - arc(cx), "paper0")
    # крышка: латунный эллипс в контуре (свет слева), канавка, мазок краски
    for xx in range(x0 - 1, x1 + 2):
        a = arc(xx) if x0 <= xx <= x1 else 0
        c.dot(xx, top - a - 1, "k")
        f = (xx - x0) / (x1 - x0)
        for yy in range(top - a, top + a + 1):
            c.dot(xx, yy, tr[3] if f < 0.3 else tr[2] if f < 0.72 else tr[1])
        if x0 <= xx <= x1:
            c.dot(xx, top + a, tr[1] if f < 0.72 else tr[0])  # кромка крышки
    for xx in range(x0 + 2, x1 - 1):  # канавка
        a = arc(xx, hw - 2, e - 1)
        c.dot(xx, top - a, tr[0] if xx > cx - 4 else tr[1])
        c.dot(xx, top + a, tr[3] if xx < cx + 3 else tr[2])
    c.hline(x0 + 2, top - 1, 3, "white")
    # мазок и потёк: с края крышки вниз через этикетку, капля на конце
    px = cx + 4
    a = arc(px)
    c.hline(px - 2, top + a - 1, 5, t[1])
    c.hline(px - 1, top + a - 2, 3, t[1])
    c.dot(px - 1, top + a - 2, t[2])
    c.vline(px, top + a, 12, t[1])
    c.vline(px + 1, top + a, 6, t[1])
    c.dot(px + 1, top + a + 6, t[0])
    c.dot(px - 1, top + a + 2, t[1])
    c.dot(px, top + a + 1, t[2])
    for dx, dy in ((-1, 10), (-1, 11), (1, 10), (1, 11), (0, 12)):
        c.dot(px + dx, top + a + dy, "k")
    c.dot(px, top + a + 10, t[2])
    # лужица у дна справа
    py = bot + arc(cx + 6) + 2
    c.hline(cx + 3, py, 9, "k")
    c.hline(cx + 5, py - 1, 7, t[1])
    c.dot(cx + 7, py - 1, t[2])
    c.dot(cx + 8, py - 1, t[2])
    if brush:  # кисть щетиной вверх, прислонена справа
        c.sprite(x1 + 1, bot - 13, _BRUSH, {"k": "k", "O": t[2], "o": t[1], "i": t[0], "B": tr[3], "b": tr[1],
                                             "t": "wood2", "T": "wood1"})
    c.sparkle(x0 + 1, top - 3, "white", 1, tr[3])


_GEAR9 = [
    "...b.b...",
    "..bbbbb..",
    ".bBBbbbd.",
    "bbBb.bbdb",
    ".bb...dd.",
    "bbbb.bddb",
    ".bbbdddd.",
    "..bdddd..",
    "...d.d...",
]


def _thick_line(c: Canvas, x0: int, y0: int, x1: int, y1: int, lit: str, dark: str) -> None:
    """Диагональ в два пикселя с контуром: светлая верхняя нить и тёмная нижняя."""
    for dx, dy in ((-1, 0), (2, 0), (0, -1), (1, 2), (0, 2), (1, -1)):
        c.line(x0 + dx, y0 + dy, x1 + dx, y1 + dy, "k")
    c.line(x0, y0, x1, y1, lit)
    c.line(x0 + 1, y0 + (0 if (x1 - x0) * (y1 - y0) > 0 else 0) + 1, x1 + 1, y1 + 1, dark)


def crest(c: Canvas, cx: int, cy: int) -> None:
    """Герб синдиката с центром (cx, cy): щит 23×27 (cx-11..cx+11, cy-13..cy+13) с латунной каймой
    (блик слева, тень справа), синее поле со светом слева, красная глава с латунными заклёпками,
    шестерня-эмблема; за щитом скрещённые ключ и молот, сверху зубчатый венец, поперёк низа —
    пергаментная лента-девиз. Общий габарит ≈ 33×35 (cy-18..cy+16)."""
    top = cy - 13
    # скрещённые инструменты за щитом
    _thick_line(c, cx - 13, top - 2, cx + 12, top + 23, "steel2", "steel1")
    _thick_line(c, cx + 13, top - 2, cx - 12, top + 23, "wood2", "wood1")
    c.outline_sprite(cx - 17, top - 5, [".h..h", "hh..h", "hhhhh", ".hhm.", "..m.."],
                     {"h": "steel3", "m": "steel2"}, "k")  # зев ключа
    c.outline_sprite(cx + 11, top - 6, ["..hh.", ".hhhm", "hhhmm", ".hmm.", "..m.."],
                     {"h": "steel2", "m": "steel1"}, "k")  # боёк молота
    c.dot(cx + 12, top - 5, "steel3")
    c.dot(cx - 12, top + 24, "steel3")
    c.rect(cx + 11, top + 22, 3, 3, "red1", "k")
    # зубчатый венец
    c.disk(cx, top - 1, 5, "k")
    for k in range(7):
        a = math.pi * (k / 6)
        tx, ty = round(cx - math.cos(a) * 5), round(top - 1 - math.sin(a) * 5)
        c.rect(tx - 1, ty - 1, 3, 3, "k")
    for k in range(7):
        a = math.pi * (k / 6)
        tx, ty = round(cx - math.cos(a) * 5), round(top - 1 - math.sin(a) * 5)
        c.dot(tx, ty, "brass3" if k < 3 else "brass2" if k < 5 else "brass1")
    c.disk(cx, top - 1, 4, "brass2")
    c.disk(cx, top - 1, 2, "brass1")
    c.dot(cx - 2, top - 4, "brass3")
    c.dot(cx - 3, top - 3, "brass3")
    c.dot(cx, top - 1, "k")

    def half(j: int) -> int:
        """Полуширина щита на строке j (0..26): прямые борта до середины, затем дуги к острию."""
        if j <= 13:
            return 11
        return max(0, round(11 * math.cos((j - 13) / 13.5 * math.pi / 2)))

    for j in range(27):
        hw = half(j)
        for xx in range(cx - hw, cx + hw + 1):
            c.dot(xx, top + j, "k")
    for j in range(1, 26):
        hw = half(j) - 1
        for xx in range(cx - hw, cx + hw + 1):
            c.dot(xx, top + j, "brass2")
    for j in range(1, 26):  # кайма: блик слева и сверху, тень справа и снизу
        hw = half(j) - 1
        if hw < 0:
            continue
        c.dot(cx - hw, top + j, "brass3")
        c.dot(cx + hw, top + j, "brass1" if j < 14 else "brass0")
        if j >= 14 and hw > 1:
            c.dot(cx + hw - 1, top + j, "brass1")
    c.hline(cx - 10, top + 1, 20, "brass3")
    for j in range(3, 24):  # поле
        hw = half(j) - 3
        for xx in range(cx - hw, cx + hw + 1):
            f = (xx - (cx - hw)) / max(1, 2 * hw)
            col = ("cloth0", "cloth1", "cloth2", "cloth2")[_col_tone(f, xx, top + j, 4)]
            c.dot(xx, top + j, col)
    # глава: красная полоса с заклёпками
    c.rect(cx - 8, top + 3, 17, 5, "red1")
    c.hline(cx - 8, top + 3, 17, "red2")
    c.hline(cx - 8, top + 7, 17, "red0")
    c.vline(cx - 8, top + 3, 5, "red2")
    c.rivets(cx - 6, top + 5, 5, 3, "brass3", "brass0")
    c.hline(cx - 8, top + 8, 17, "k")
    # шестерня-эмблема
    c.outline_sprite(cx - 4, top + 10, _GEAR9, {"b": "brass2", "B": "brass3", "d": "brass1"}, "k")
    c.dot(cx, top + 14, "cloth0")
    # лента-девиз: хвосты с вырезом уходят за щит вниз-наружу, полоса поперёк щита
    ry = top + 20
    for sgn in (-1, 1):
        ex = cx + sgn * 17
        tail = [(cx + sgn * 11, ry + 1), (ex, ry + 2), (ex - sgn * 2, ry + 4), (ex, ry + 6), (cx + sgn * 11, ry + 6)]
        c.poly(tail, "paper0")
        c.line(cx + sgn * 11, ry + 1, ex, ry + 2, "k")
        c.line(ex, ry + 2, ex - sgn * 2, ry + 4, "k")
        c.line(ex - sgn * 2, ry + 4, ex, ry + 6, "k")
        c.line(ex, ry + 6, cx + sgn * 11, ry + 6, "k")
        c.dot(cx + sgn * 12, ry + 4, "k")  # складка
        c.dot(cx + sgn * 12, ry + 5, "wood0")
    c.rect(cx - 12, ry - 1, 25, 6, "paper1", "k")
    c.hline(cx - 11, ry, 23, "paper2")
    c.hline(cx - 11, ry + 3, 23, "paper0")
    for i in range(0, 18, 3):
        c.hline(cx - 8 + i, ry + 1 + (i // 3) % 2 * 0, 2, "wood0")
    c.sparkle(cx - 10, top + 1, "white", 1, "brass3")
