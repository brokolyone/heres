"""Сооружения: завод, буровая, станок-качалка, домна, НПЗ, мастерская, биржа и табло, шестерня, забой.

Все функции принимают x — левый край и gy — линию земли, на которой стоит сооружение
(если не сказано иное). Свет падает сверху-слева, окна и огни подсвечены ореолами.
"""

from ironvein.art.backgrounds import smoke
from ironvein.art.canvas import Canvas, ramp
from ironvein.art.props import barrel


def factory(c: Canvas, x: int, gy: int, w: int = 40, h: int = 21, chimneys: int = 2, col: str = "rust") -> None:
    """Цех: кирпичная (rust) или листовая (steel) стена, пилообразная крыша с фонарями, окна, ворота, трубы."""
    t = ramp(col)
    top = gy - h
    # Трубы позади крыши
    for n in range(chimneys):
        cx = x + 5 + n * (w // max(1, chimneys))
        ctop = top - 17 - (n % 2) * 3
        c.box(cx, ctop, 4, gy - ctop, "steel" if col == "rust" else "rust", base=1)
        c.hline(cx + 1, ctop + 3, 2, "red2")
        c.hline(cx + 1, ctop + 5, 2, "red1")
        c.rect(cx - 1, ctop - 1, 6, 2, "oil1", "k")
        smoke(c, cx + 2, ctop - 2, 7, tone=3)
    # Пилообразная крыша: скаты и световые фонари на вертикальных гранях
    for i in range(0, w - 3, 8):
        rx = x + i
        c.poly([(rx, top + 1), (rx + 7, top - 5), (rx + 8, top + 1)], t[0])
        c.line(rx + 1, top, rx + 6, top - 4, t[2])
        c.vline(rx + 7, top - 5, 6, "k")
        c.vline(rx + 6, top - 2, 2, "lamp1")
    # Стена
    if col == "rust":
        c.bricks(x, top, w, h, t[1], t[0], accent=t[2])
        c.hline(x, top, w, t[3])
    else:
        c.box(x, top, w, h, col, outline=None, base=1)
        for i in range(x + 6, x + w - 1, 7):
            c.vline(i, top + 1, h - 2, t[0])
        c.rivets(x + 2, top + 2, w // 3, 3, t[3], t[0])
    c.rect(x, top, w, h, None, "k")
    # Окна: арочные, часть горит
    for i in range(4, w - 5, 7):
        wx = x + i
        lit = c.rnd.random() < 0.65
        c.rect(wx - 1, top + 4, 5, 8, "k")
        c.rect(wx, top + 5, 3, 6, "lamp1" if lit else "oil1")
        if lit:
            c.dot(wx, top + 5, "lamp2")
            c.vline(wx + 1, top + 5, 6, "lamp0")
        c.hline(wx - 1, top + 12, 5, t[0])  # подоконник
    # Ворота с тёплым светом изнутри
    gx = x + w // 2 - 4
    c.glow(gx + 4, gy - 6, 6, ["haze1", "lamp0"])
    c.rect(gx, gy - 9, 9, 9, "k")
    c.rect(gx + 1, gy - 8, 7, 8, "fire0")
    c.rect(gx + 2, gy - 6, 5, 6, "fire1")
    c.box(gx + 5, gy - 8, 4, 8, "steel", base=1)  # приоткрытая створка
    c.hline(gx - 1, gy - 10, 11, "k")


def drill_rig(c: Canvas, x: int, gy: int) -> None:
    """Буровая: решётчатая вышка, кронблок, талевый блок на тросе, бурильная труба, дизельный домик."""
    h = 38
    for i in range(h):
        s = i // 4
        y = gy - 1 - i
        c.dot(x + s, y, "steel3")
        c.dot(x + 17 - s, y, "steel2")
        if i % 6 == 0:
            c.hline(x + s, y, 18 - 2 * s, "steel2")
            j = min(i + 6, h - 1)
            c.line(x + s, y, x + 17 - j // 4, gy - 1 - j, "steel1")
    c.box(x + 6, gy - h - 3, 6, 4, "rust", base=2)  # кронблок
    c.vline(x + 9, gy - h + 1, 20, "k")  # трос
    c.box(x + 7, gy - h + 21, 5, 4, "brass", base=1)  # талевый блок
    c.vline(x + 9, gy - h + 25, h - 31, "steel3")  # бурильная труба
    c.rect(x - 1, gy - 7, 20, 2, "wood1", "k")  # площадка
    c.hline(x, gy - 7, 18, "wood2")
    c.rect(x + 7, gy - 5, 5, 5, "steel1", "k")  # устье
    # Дизельный домик
    hx = x + 21
    c.box(hx, gy - 11, 13, 11, "rust", base=2)
    c.rect(hx - 1, gy - 12, 15, 2, "rust0", "k")
    c.rect(hx + 3, gy - 8, 4, 3, "k")
    c.rect(hx + 4, gy - 7, 2, 1, "lamp2")
    c.glow(hx + 5, gy - 7, 4, ["lamp0"])
    c.rivets(hx + 8, gy - 9, 3, 2, "rust3", "rust0", vertical=True)
    c.rect(hx + 10, gy - 19, 2, 8, "steel1")
    c.vline(hx + 10, gy - 19, 8, "steel2")
    smoke(c, hx + 11, gy - 20, 6, tone=2)
    # Штабель труб
    for k in range(3):
        c.hline(hx + 15, gy - 1 - k * 2, 9 - k * 2, "steel2")
        c.hline(hx + 15, gy - 2 - k * 2, 9 - k * 2, "steel3")
        c.dot(hx + 15, gy - 1 - k * 2, "k")


def pumpjack(c: Canvas, x: int, gy: int, tanks: bool = True) -> None:
    """Станок-качалка: рама, стойка-«А», балансир с головой, кривошип с противовесом, мотор; рядом бочки."""
    c.rect(x, gy - 3, 36, 3, "steel1", "k")
    c.hline(x + 1, gy - 2, 34, "steel2")
    # Стойка
    c.line(x + 14, gy - 3, x + 17, gy - 21, "steel2")
    c.line(x + 21, gy - 3, x + 18, gy - 21, "steel1")
    c.hline(x + 15, gy - 12, 6, "steel1")
    # Балансир
    for i in range(30):
        y = gy - 23 + i // 8
        c.dot(x + 3 + i, y, "k")
        c.dot(x + 3 + i, y + 1, "brass2")
        c.dot(x + 3 + i, y + 2, "brass0")
    c.box(x + 16, gy - 24, 4, 4, "steel", base=2)  # шарнир
    # Голова балансира и шток к устью
    c.box(x, gy - 27, 6, 9, "rust", base=2)
    c.hline(x + 1, gy - 27, 4, "rust3")
    c.vline(x + 2, gy - 18, 15, "steel3")
    c.box(x, gy - 6, 6, 3, "steel", base=1)  # устье
    # Кривошип с противовесом и шатун
    c.line(x + 32, gy - 20, x + 30, gy - 10, "steel2")
    c.shaded_disk(x + 30, gy - 8, 4, "rust", base=1)
    c.dot(x + 30, gy - 8, "steel3")
    # Мотор
    c.box(x + 22, gy - 9, 5, 6, "steel", base=1)
    c.dot(x + 23, gy - 7, "lamp2")
    if tanks:
        for i in range(3):
            barrel(c, x + 40 + i * 8, gy - 9)


def furnace(c: Canvas, x: int, gy: int) -> None:
    """Домна: кирпичная печь с пылающим зевом и ореолом, искры, труба, ковш с жидкой сталью, слитки."""
    # Труба
    c.box(x + 9, gy - 40, 8, 17, "steel", base=1)
    c.rect(x + 8, gy - 41, 10, 2, "oil1", "k")
    c.hline(x + 10, gy - 35, 6, "red1")
    smoke(c, x + 13, gy - 42, 8, tone=3)
    # Печь
    c.bricks(x, gy - 24, 26, 24, "rust1", "rust0", accent="rust2")
    c.rect(x, gy - 24, 26, 24, None, "k")
    c.hline(x + 1, gy - 23, 24, "rust3")
    c.rect(x - 1, gy - 25, 28, 2, "rust0", "k")
    # Зев с огнём
    c.glow(x + 13, gy - 7, 12, ["haze1", "fire0", "fire1"])
    c.rect(x + 7, gy - 13, 12, 11, "k")
    c.rect(x + 8, gy - 12, 10, 10, "fire1")
    c.rect(x + 9, gy - 10, 8, 7, "fire2")
    c.rect(x + 11, gy - 8, 4, 4, "fire3")
    c.hline(x + 7, gy - 13, 12, "steel1")
    for sx, sy in ((x + 20, gy - 15), (x + 23, gy - 19), (x + 4, gy - 17)):
        c.sparkle(sx, sy, "fire3", 1, "fire1")
    # Ковш с жидкой сталью
    lx = x + 30
    c.glow(lx + 5, gy - 8, 7, ["fire0"])
    c.poly([(lx, gy - 9), (lx + 11, gy - 9), (lx + 9, gy), (lx + 2, gy)], "steel1")
    c.line(lx, gy - 9, lx + 2, gy - 1, "steel2")
    c.hline(lx + 1, gy - 9, 10, "fire2")
    c.hline(lx + 3, gy - 9, 4, "fire3")
    c.rivets(lx + 3, gy - 6, 3, 3, "steel3", "steel0")
    # Слитки
    for i in range(3):
        c.box(lx + 14 + i * 7, gy - 4, 6, 4, "steel", base=2)


def refinery(c: Canvas, x: int, gy: int) -> None:
    """НПЗ: ректификационная колонна с площадками, факел с ореолом, два резервуара и латунные трубы."""
    # Колонна
    c.box(x, gy - 35, 8, 35, "steel", base=2)
    for j in range(gy - 31, gy - 3, 7):
        c.rect(x - 2, j, 12, 1, "steel0")
        c.hline(x - 2, j - 1, 12, "steel3")
        c.dot(x + 9, j - 2, "lamp2")
    c.vline(x + 9, gy - 33, 33, "steel1")  # лестница
    # Факел
    c.rect(x + 3, gy - 41, 2, 6, "steel1")
    c.glow(x + 4, gy - 44, 7, ["haze0", "haze1", "fire0"])
    c.poly([(x + 2, gy - 41), (x + 4, gy - 47), (x + 6, gy - 41)], "fire2")
    c.vline(x + 4, gy - 44, 3, "fire3")
    # Резервуары
    for i, (w, h) in enumerate(((16, 13), (13, 19))):
        tx = x + 11 + i * 19
        c.box(tx, gy - h, w, h, "steel", base=2)
        c.hline(tx + 1, gy - h - 1, w - 2, "steel1")
        c.hline(tx + 1, gy - h + 3, w - 2, "steel1")
        c.hline(tx + 1, gy - 4, w - 2, "red1")
        c.rivets(tx + 2, gy - h + 5, (w - 3) // 3, 3, "steel3", "steel1")
    # Трубы
    c.hline(x + 8, gy - 24, 32, "brass1")
    c.hline(x + 8, gy - 25, 32, "brass2")
    c.vline(x + 40, gy - 25, 25, "brass1")
    c.vline(x + 41, gy - 25, 25, "brass0")


def workshop(c: Canvas, x: int, gy: int) -> None:
    """Мастерская: дощатый сарай с ржавой крышей, вывеска-шестерня, светлый проём, окно, наковальня с искрами."""
    # Стена из досок
    c.rect(x, gy - 19, 35, 19, "wood1")
    for i in range(x + 2, x + 34, 3):
        c.vline(i, gy - 18, 18, "wood0")
    c.rect(x, gy - 19, 35, 19, None, "k")
    # Двускатная крыша из ржавого профлиста
    for i in range(10):
        c.hline(x - 2 + i * 2, gy - 20 - i, 39 - i * 4, "rust1" if i % 2 else "rust2")
    c.line(x - 2, gy - 20, x + 17, gy - 30, "rust3")
    # Проём с тёплым светом
    c.glow(x + 17, gy - 7, 7, ["haze1", "lamp0"])
    c.rect(x + 12, gy - 12, 11, 12, "k")
    c.rect(x + 13, gy - 11, 9, 11, "lamp0")
    c.rect(x + 14, gy - 9, 7, 9, "lamp1")
    c.hline(x + 13, gy - 11, 9, "fire1")
    # Окно и вывеска
    c.rect(x + 26, gy - 14, 6, 6, "k")
    c.rect(x + 27, gy - 13, 4, 4, "glass1")
    c.dot(x + 27, gy - 13, "glass2")
    gear(c, x + 6, gy - 13, 3, "brass")
    # Наковальня и горн
    ax = x + 40
    c.box(ax, gy - 6, 11, 3, "steel", base=1)
    c.rect(ax + 3, gy - 3, 5, 3, "steel1", "k")
    fx = ax + 14  # горн-жаровня
    c.glow(fx + 2, gy - 6, 6, ["haze0", "haze1"])
    c.box(fx, gy - 5, 5, 5, "steel", base=1)
    c.hline(fx + 1, gy - 5, 3, "fire2")
    c.dot(fx + 2, gy - 6, "fire3")
    c.dot(fx + 1, gy - 6, "fire1")
    c.dot(fx + 3, gy - 7, "fire2")
    c.sparkle(ax + 6, gy - 10, "fire3", 1, "fire1")
    c.dot(ax + 9, gy - 12, "fire2")
    c.dot(fx + 4, gy - 11, "fire1")


def market_hall(c: Canvas, x: int, gy: int, w: int = 54, h: int = 30) -> None:
    """Биржевой зал: стальной павильон с колоннами, арочной ржавой крышей и светящимися окнами."""
    top = gy - h
    c.box(x, top, w, h, "steel", base=1)
    for i in range(x + 4, x + w - 3, 8):  # колонны
        c.rect(i, top + 6, 3, h - 6, "steel2")
        c.vline(i, top + 6, h - 6, "steel3")
        c.vline(i + 2, top + 6, h - 6, "steel0")
    for i in range(x + 8, x + w - 7, 8):  # окна между колоннами
        c.rect(i, top + 9, 3, 7, "lamp1" if c.rnd.random() < 0.7 else "oil1")
        c.dot(i, top + 9, "lamp2")
    c.rect(x + w // 2 - 4, gy - 10, 9, 10, "k")  # вход
    c.rect(x + w // 2 - 3, gy - 9, 7, 9, "lamp0")
    # Арочная крыша и фронтон
    c.rect(x - 2, top - 2, w + 4, 4, "rust1", "k")
    c.hline(x - 1, top - 1, w + 2, "rust3")
    for i in range(6):
        c.hline(x + 4 + i * 3, top - 3 - i, w - 8 - i * 6, "rust1" if i % 2 else "rust2")
    c.rect(x + w // 2 - 7, top + 1, 15, 4, "k")
    c.hline(x + w // 2 - 6, top + 2, 13, "brass2")
    c.hline(x + w // 2 - 6, top + 3, 13, "brass1")


def board(c: Canvas, x: int, y: int, w: int = 45, h: int = 24) -> None:
    """Табло котировок: латунная рамка, строки «тикер — столбик цены — стрелка» зелёным и красным."""
    c.box(x, y, w, h, "brass", base=1)
    c.rect(x + 2, y + 2, w - 4, h - 4, "oil0")
    for j in range(y + 4, y + h - 3, 4):
        c.hline(x + 4, j, 6, "brass2")
        c.hline(x + 4, j + 1, 6, "brass0")
        up = c.rnd.random() < 0.6
        bars = c.rnd.randrange(6, w - 22)
        col = "green" if up else "red"
        c.hline(x + 13, j, bars, f"{col}2")
        c.hline(x + 13, j + 1, bars, f"{col}1")
        ax = x + w - 7
        if up:
            c.sprite(ax, j - 1, [".g.", "ggg"], {"g": "green2"})
        else:
            c.sprite(ax, j, ["rrr", ".r."], {"r": "red2"})
    c.vline(x + 8, y + h, 4, "steel1")
    c.vline(x + w - 9, y + h, 4, "steel1")


def gear(c: Canvas, cx: int, cy: int, r: int = 3, ramp_name: str = "brass") -> None:
    """Шестерня с центром (cx, cy): зубья по 8 направлениям, объёмный обод, отверстие."""
    t = ramp(ramp_name)
    for dx, dy in ((0, -1), (1, -1), (1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1)):
        tx, ty = cx + dx * (r + 1), cy + dy * (r + 1)
        if dx and dy:
            tx, ty = cx + dx * r, cy + dy * r
        c.rect(tx - (dx < 0), ty - (dy < 0), 2 if dx == 0 else 1, 2 if dy == 0 else 1, t[1])
    c.shaded_disk(cx, cy, r, ramp_name, outline="k")
    c.dot(cx, cy, "k")
    if r >= 3:
        c.dot(cx - 1, cy, t[0])
        c.dot(cx + 1, cy, t[0])
        c.dot(cx, cy - 1, t[0])
        c.dot(cx, cy + 1, t[0])
        c.dot(cx - 2, cy - 2, t[-1])


def rock(c: Canvas, x: int, gy: int, res: str) -> None:
    """Забой 38×20: скальный холм с прожилками руды/угля, крепь штольни с фонарём, куски породы у подножия."""
    main = {"ore": ("ore0", "ore1", "ore2"), "coal": ("coal0", "coal1", "coal2")}.get(res, ("steel0", "steel1", "steel2"))
    hill = [(x, gy), (x + 3, gy - 10), (x + 9, gy - 17), (x + 17, gy - 20), (x + 25, gy - 16), (x + 31, gy - 9),
            (x + 36, gy)]
    c.poly(hill, "steel1")
    # Освещённая кромка сверху-слева и тень справа
    for i in range(37):
        top = next((j for j in range(gy - 21, gy) if c.get(x + i, j) == c.rgb("steel1")), None)
        if top is None:
            continue
        c.dot(x + i, top, "steel3" if i < 18 else "steel2")
        if i < 22:
            c.dot(x + i, top + 1, "steel2")
        if i > 22:
            for j in range(top + 1, gy):
                if c.threshold(x + i, j, "bayer4") < (i - 22) / 14:
                    c.dot(x + i, j, "steel0")
    for _ in range(5):  # трещины
        px, py = x + c.rnd.randrange(4, 32), gy - c.rnd.randrange(3, 13)
        c.line(px, py, px + c.rnd.randrange(-2, 3), py + 2, "steel0")
    for _ in range(16):  # прожилки
        px, py = x + c.rnd.randrange(3, 33), gy - c.rnd.randrange(2, 14)
        if c.get(px, py) in (c.rgb("steel1"), c.rgb("steel0")):
            c.dot(px, py, main[1])
            c.dot(px + 1, py, main[2])
            c.dot(px, py + 1, main[0])
    # Штольня: деревянная крепь, тёмный проём, фонарь
    ax = x + 11
    c.rect(ax, gy - 11, 11, 11, "k")
    c.glow(ax + 5, gy - 3, 4, ["oil2"])
    c.rect(ax, gy - 12, 11, 2, "wood2", "wood0")
    c.rect(ax, gy - 10, 2, 10, "wood1")
    c.vline(ax, gy - 10, 10, "wood2")
    c.rect(ax + 9, gy - 10, 2, 10, "wood0")
    c.glow(ax + 5, gy - 8, 3, ["lamp0"])
    c.dot(ax + 5, gy - 9, "lamp2")
    c.dot(ax + 5, gy - 10, "k")
    c.sparkle(x + 28, gy - 12, "white" if res != "coal" else "steel3")
    for i in range(5):  # куски
        bx, by = x + 37 + i * 4, gy - 2 - (i % 2)
        c.rect(bx, by, 3, 2, main[1])
        c.dot(bx, by, main[2])
        c.dot(bx + 2, by + 1, main[0])
