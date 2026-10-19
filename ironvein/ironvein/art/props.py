"""Мелкие предметы и персонажи: рабочий, ящик, бочка, монеты, документ, постамент, часы, краска, герб, инструменты.

Предметы для премиальных сцен (watch, paint_can, crest) рисуются крупно по центру на постаменте —
как растение в горшке на тёмном фоне в референсе.
"""

import math

from ironvein.art.canvas import Canvas, ramp

_WORKER = [
    "...bbb...",
    "..bBBbb..",
    ".bbbbbbL.",
    "...sSs...",
    "...sss...",
    "..cCCcc..",
    ".cCCcccc.",
    ".cc.ccc.c",
    ".s..cdc.s",
    "...dddd..",
    "...dd.d..",
    "...dd.d..",
    "..kkk.kk.",
]
_WORKER_PAL = {"b": "brass1", "B": "brass3", "L": "lamp2", "s": "skin1", "S": "skin2",
               "c": "cloth1", "C": "cloth2", "d": "cloth0", "k": "k"}


def worker(c: Canvas, x: int, gy: int, tool: str | None = "pick", flip: bool = False) -> None:
    """Рабочий в каске с фонарём 9×13 (x — левый край, gy — низ ботинок). flip — смотрит влево.

    tool: pick (кирка) | sack (мешок за спиной) | wrench (гаечный ключ) | None.
    """
    y = gy - len(_WORKER)
    if tool == "sack":  # мешок за спиной — позади фигуры
        sx = x + (6 if flip else -3)
        c.box(sx, y + 5, 5, 6, "wood", base=1)
        c.dot(sx + 2, y + 5, "wood0")
    c.outline_sprite(x, y, _WORKER, _WORKER_PAL, "k", flip)
    if tool == "pick":
        hx = x + (-2 if flip else 9)
        c.line(hx, y + 9, hx + (-3 if flip else 3), y + 1, "wood2")
        head_x = hx + (-3 if flip else 3)
        c.hline(head_x - 2, y + 1, 5, "steel2")
        c.dot(head_x - 2, y + 2, "steel1")
        c.dot(head_x + 2, y + 2, "steel1")
        c.dot(head_x, y + 1, "steel3")
    elif tool == "wrench":
        wrench(c, x + (-3 if flip else 9), y + 4)


def wrench(c: Canvas, x: int, y: int, ramp_name: str = "steel") -> None:
    """Гаечный ключ 3×9 стоймя: зев сверху, рукоять вниз."""
    t = ramp(ramp_name)
    c.sprite(x, y, ["h.h", "hmh", ".m.", ".m.", ".m.", ".m.", ".s.", ".s.", ".s."],
             {"h": t[-1], "m": t[2], "s": t[1]})


def hammer(c: Canvas, x: int, y: int) -> None:
    """Молоток 5×8: стальной боёк, деревянная рукоять."""
    c.sprite(x, y, ["hhhhh", "hHHhh", "..w..", "..w..", "..w..", "..w..", "..W..", "..W.."],
             {"h": "steel2", "H": "steel3", "w": "wood2", "W": "wood1"})


def crate(c: Canvas, x: int, y: int, s: int = 8) -> None:
    """Деревянный ящик s×s (x, y — верхний левый угол): рамка, диагональная распорка, блик."""
    c.box(x, y, s, s, "wood", outline="wood0", base=1)
    c.line(x + 1, y + s - 2, x + s - 2, y + 1, "wood0")
    c.hline(x + 1, y + 1, s - 2, "wood2")
    c.dot(x + 1, y + s - 2, "brass1")
    c.dot(x + s - 2, y + 1, "brass1")


def barrel(c: Canvas, x: int, y: int) -> None:
    """Бочка с мазутом 7×9 (x, y — верхний левый угол): латунные обручи, блик, крышка."""
    c.box(x, y, 7, 9, "oil", base=1)
    c.vline(x + 2, y + 1, 7, "oil2")
    for j in (y + 2, y + 6):
        c.hline(x + 1, j, 5, "brass1")
        c.dot(x + 2, j, "brass3")
    c.hline(x + 1, y, 5, "steel1")
    c.dot(x + 4, y, "steel2")


def coin_stack(c: Canvas, x: int, gy: int, n: int) -> None:
    """Столбик из n латунных монет 8×2 (x — левый край, gy — низ столбика), монеты слегка гуляют."""
    for i in range(n):
        cx = x + (i * 5 % 3) - 1
        cy = gy - 2 - i * 2
        c.hline(cx + 1, cy, 6, "brass2")
        c.hline(cx, cy + 1, 8, "brass1")
        c.dot(cx, cy + 1, "brass0")
        c.dot(cx + 7, cy + 1, "brass0")
        c.dot(cx + 2, cy, "brass3")
    c.sparkle(x + 2, gy - 2 * n - 2, "brass3")


def document(c: Canvas, x: int, y: int, stamp: bool = True) -> None:
    """Контракт 24×29: бумага с загнутым углом, строки текста, подпись и красная печать."""
    c.box(x, y, 24, 29, "paper", outline="paper0", base=1)
    c.poly([(x + 18, y), (x + 24, y), (x + 24, y + 6)], "bg")  # загнутый угол
    c.poly([(x + 18, y), (x + 18, y + 6), (x + 24, y + 6)], "paper2")
    c.line(x + 18, y, x + 23, y + 5, "paper0")
    c.hline(x + 4, y + 4, 11, "k")  # заголовок
    for j in range(8, 21, 3):
        c.hline(x + 3, y + j, 17 - (j * 7 % 5), "paper0")
    c.line(x + 3, y + 25, x + 5, y + 23, "k")  # подпись
    c.line(x + 5, y + 23, x + 8, y + 25, "k")
    c.line(x + 8, y + 25, x + 10, y + 24, "k")
    if stamp:
        c.shaded_disk(x + 17, y + 22, 4, "red", outline="red0", base=1)
        c.ring(x + 17, y + 22, 2, "red2")
        c.dot(x + 17, y + 22, "paper2")


def pedestal(c: Canvas, cx: int, gy: int, w: int = 33) -> None:
    """Постамент-горшок как в референсе (gy — верх столешницы, w — ширина плиты): плита с бликом,
    сужающееся тело с латунным поясом, база с контуром. Высота ≈ w/4 + 5."""
    hw = w // 2
    body = max(6, w // 4)
    c.box(cx - hw, gy - 3, 2 * hw + 1, 4, "wood", base=1)
    c.hline(cx - hw + 1, gy - 2, 2 * hw - 1, "wood2")
    bl, br = cx - hw + 2, cx + hw - 2
    c.poly([(bl, gy + 1), (br + 1, gy + 1), (br - 2, gy + 1 + body), (bl + 3, gy + 1 + body)], "wood1")
    c.line(bl, gy + 1, bl + 2, gy + body, "wood2")
    c.line(br, gy + 1, br - 2, gy + body, "wood0")
    c.dither(bl + 1, gy + 1, br - bl - 1, 1, None, "wood0", 0.5)  # тень от плиты
    c.hline(bl + 1, gy + 3, br - bl - 1, "wood0")
    c.hline(bl + 1, gy + 4, br - bl - 1, "brass1")
    c.dot(bl + 2, gy + 4, "brass3")
    c.rect(bl + 1, gy + 1 + body, br - bl - 1, 3, "wood0", "k")
    c.hline(bl + 2, gy + 1 + body, br - bl - 3, "wood1")


def watch(c: Canvas, cx: int, cy: int, r: int = 12) -> None:
    """Карманные часы радиусом r с центром (cx, cy): латунный корпус, циферблат с 12 метками,
    стрелки, заводная головка с ушком, цепочка, блик на стекле."""
    for i in range(r):  # цепочка
        c.dot(cx + r - 1 + i, cy - r // 2 + i // 2 + (i % 2), "brass2" if i % 2 else "brass1")
    c.ring(cx, cy - r - 4, 1, "brass2")  # ушко
    c.rect(cx - 1, cy - r - 3, 3, 3, "brass1", "k")  # головка
    c.dot(cx, cy - r - 2, "brass3")
    c.shaded_disk(cx, cy, r, "brass", base=2)
    c.ring(cx, cy, r - 2, "brass0")
    d = r - 3
    c.disk(cx, cy, d, "paper2")
    c.ring(cx, cy, d, "paper1")
    for k in range(12):  # часовые метки
        a = k * math.pi / 6
        mx, my = round(cx + math.sin(a) * (d - 1)), round(cy - math.cos(a) * (d - 1))
        c.dot(mx, my, "k" if k % 3 == 0 else "paper0")
    c.vline(cx, cy - d + 2, d - 2, "k")  # минутная стрелка
    c.line(cx, cy, cx + d // 2, cy + d // 3, "k")  # часовая
    c.dot(cx, cy, "red1")
    c.dot(cx - d // 2, cy - d // 2 - 1, "white")  # блик на стекле
    c.dot(cx - d // 2 + 1, cy - d // 2 - 1, "paper2")
    c.sparkle(cx - r + 2, cy - r + 2, "white", 1, "brass3")


def paint_can(c: Canvas, cx: int, cy: int, ramp_name: str = "oil", trim: str = "brass") -> None:
    """Банка премиальной краски 23×22 с центром (cx, cy): крышка, этикетка с латунной полосой и ромбом,
    потёк краски, кисть рядом."""
    c.box(cx - 11, cy - 8, 23, 19, "steel", base=2)
    c.vline(cx - 9, cy - 7, 17, "steel3")
    c.box(cx - 11, cy - 4, 23, 10, ramp_name, base=1)
    c.hline(cx - 10, cy - 1, 21, f"{trim}2")
    c.hline(cx - 10, cy, 21, f"{trim}1")
    c.dot(cx - 9, cy - 1, f"{trim}3")
    c.sprite(cx - 2, cy - 3, ["..b..", ".bBb.", "bBkBb", ".bBb.", "..b.."],
             {"b": f"{trim}1", "B": f"{trim}2", "k": "k"})
    c.rect(cx - 12, cy - 11, 25, 4, "steel1", "k")  # крышка
    c.hline(cx - 11, cy - 10, 23, "steel3")
    c.vline(cx + 5, cy - 8, 6, ramp_name + "1")  # потёк
    c.dot(cx + 5, cy - 2, ramp_name + "2")
    c.dot(cx + 6, cy - 8, ramp_name + "1")
    # кисть, прислонённая к банке
    c.line(cx + 13, cy + 10, cx + 17, cy - 6, "wood2")
    c.line(cx + 14, cy + 10, cx + 18, cy - 6, "wood1")
    c.rect(cx + 16, cy - 10, 4, 4, "steel2", "k")
    c.rect(cx + 16, cy - 14, 4, 4, ramp_name + "1")
    c.hline(cx + 16, cy - 14, 4, ramp_name + "2")
    c.sparkle(cx - 8, cy - 13, "brass3", 1, "brass1")


_GEAR7 = [".b.b.b.", "bbbbbbb", ".bBBbb.", "bbBkbbb", ".bbbbd.", "bbbbbdb", ".b.b.b."]


def crest(c: Canvas, cx: int, cy: int) -> None:
    """Герб компании 23×27 с центром (cx, cy): щит с латунной каймой (блик слева, тень справа),
    поле в две тени, латунный пояс с заклёпками и шестерня-эмблема."""
    top = cy - 13

    def shield(i: int) -> list[tuple[int, int]]:
        return [(cx - 10 + i, top + i), (cx + 12 - i, top + i), (cx + 12 - i, top + 13),
                (cx + 1, top + 26 - i * 2), (cx - 10 + i, top + 13)]

    c.poly(shield(0), "k")
    c.poly(shield(1), "brass2")
    c.poly(shield(3), "rust1")
    left = c.rgb("rust1")
    for y in range(top + 3, top + 25):  # левая половина поля светлее — свет слева
        for x in range(cx - 8, cx + 1):
            if c.get(x, y) == left:
                c.dot(x, y, "rust2")
    c.vline(cx - 9, top + 1, 13, "brass3")
    c.line(cx - 9, top + 14, cx, top + 24, "brass3")
    c.vline(cx + 10, top + 2, 12, "brass1")
    c.line(cx + 10, top + 14, cx + 2, top + 23, "brass1")
    c.rect(cx - 7, top + 3, 17, 4, "brass1")  # пояс
    c.hline(cx - 7, top + 3, 17, "brass3")
    c.rivets(cx - 5, top + 5, 5, 3, "brass3", "brass0")
    c.outline_sprite(cx - 3, top + 10, _GEAR7, {"b": "brass2", "B": "brass3", "d": "brass1", "k": "k"})
    c.sparkle(cx - 9, top - 1, "white", 1, "brass3")
