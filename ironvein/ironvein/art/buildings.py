"""Сооружения: завод, буровая, станок-качалка, домна, НПЗ, мастерская, биржа и табло, шестерня, забой.

Все функции принимают x — левый край и gy — линию земли, на которой стоит сооружение
(если не сказано иное): нижний ряд сооружения — gy-1, строка gy и ниже — земля (на неё ложатся
контактная тень и пятна света из дверей и топок).

Свет падает сверху-слева: левые грани и верхние кромки светлее, правые и нижние уходят в тень;
цилиндры (трубы, колонны, резервуары) — с бликом в левой трети и дизерными стыками тонов.
Огни, окна, топки и факелы дают ореолы, которые только осветляют пиксели под собой.

Габариты при сцене 128×72 (x — левый край, gy — земля):
    factory      w×h стены (по умолчанию 40×21) + пилы крыши 6 px + трубы до h+20 и дым над ними
    drill_rig    x-8 … x+49, высота 45 (вышка x … x+17, моторная будка x+21 … x+34, куча руды x+37 … x+49)
    pumpjack     x-4 … x+43, высота 28; бочки (tanks) — пирамидкой на x+46 … x+68
    furnace      x-1 … x+61, высота 46 + дым (домна x … x+25, кран x+26 … x+47, слитки x+48 … x+61)
    refinery     x-12 … x+43, высота 46 (факел x-5, колонны x+1 … x+19, резервуар x+24 … x+40)
    workshop     x-2 … x+58, высота 32 (сарай x … x+34, наковальня x+38 … x+49, горн x+51 … x+58)
    market_hall  x-2 … x+w+1, высота h + фронтон и купол ≈ h+16
    board        w×h с верхним левым углом (x, y), стойки ниже на 4 px (или до gy)
    rock         x … x+46 (холм 38×20 и куча у подножия), рельсы из штольни до x+track
"""

import math

from ironvein.art.backgrounds import smoke
from ironvein.art.canvas import Canvas, lum, ramp
from ironvein.art.props import barrel

# --- Локальные тона (RGB): общей палитры canvas.py не меняют ---------------------------------------------

HEAT = ((150, 60, 46), (190, 88, 54), (226, 130, 70))  # кирпич и сталь в отсветах жара
MOLTEN = (255, 248, 212)  # белый жар: сердце зева и струи металла
FIRE_HALO = ((66, 38, 46), (98, 50, 50), (142, 68, 52))  # ореол огня: снаружи → внутрь
LAMP_HALO = ((50, 42, 52), (72, 56, 58), (104, 76, 60))  # ореол лампы и окна: снаружи → внутрь
SOOT = (34, 29, 36)  # копоть на оголовках труб
ROCK = ((38, 35, 50), (60, 56, 74), (88, 82, 102), (124, 116, 134))  # серо-лиловая порода забоя
ROCK_HI = (152, 142, 156)  # освещённая кромка скалы
CONCRETE = ((42, 42, 54), (62, 62, 74), (88, 88, 98))  # бетонные фундаменты и ступени
PATINA = ((34, 60, 64), (52, 92, 88), (88, 134, 118))  # медь купола в патине
SHEEN = (74, 60, 94)  # радужный отлив на мазутной луже


# --- Мелкие помощники ----------------------------------------------------------------------------------


def _lighten(c: Canvas, x: int, y: int, col) -> None:
    """Точка, только если она светлее того, что уже нарисовано (свет не затемняет)."""
    old = c.get(x, y)
    new = c.rgb(col)
    if old is None or lum(old) < lum(new):
        c.dot(x, y, new)


def _halo(c: Canvas, cx: int, cy: int, r: int, colors, ry: int | None = None) -> None:
    """Мягкий ореол: кольца colors (от внешнего к внутреннему) с переходами Байером 4×4; ry — сплющенный
    (пятно света на земле). Только осветляет — можно класть поверх чего угодно."""
    ry = r if ry is None else ry
    n = len(colors)
    rgbs = [c.rgb(k) for k in colors]
    for dy in range(-ry, ry + 1):
        for dx in range(-r, r + 1):
            d = math.hypot(dx / (r + 0.5), dy / (ry + 0.5))
            if d >= 1:
                continue
            t = (1 - d) * n
            i = int(t)
            k = i if c.threshold(cx + dx, cy + dy, "bayer4") < t - i else i - 1
            if k >= 0:
                _lighten(c, cx + dx, cy + dy, rgbs[min(k, n - 1)])


def _ground_shadow(c: Canvas, x: int, gy: int, w: int) -> None:
    """Контактная тень на земле под сооружением: строка gy плотная с дизерными концами, под ней — редкая."""
    for i in range(w):
        edge = min(i, w - 1 - i)
        if edge >= 2 or c.threshold(x + i, gy, "checker") < 0.5:
            c.dot(x + i, gy, "oil1")
        if edge >= 3 and c.threshold(x + i, gy + 1, "bayer4") < 0.45:
            c.dot(x + i, gy + 1, "ground0")


def _spill(c: Canvas, cx: int, gy: int, w: int, rows: int = 4, cols=("lamp0", "haze1")) -> None:
    """Пятно света на земле перед проёмом: трапеция, расширяется к зрителю и тает дизером."""
    for j in range(rows):
        hw = w // 2 + j
        level = 0.6 - j * (0.45 / max(1, rows - 1))
        col = cols[0] if j < rows // 2 else cols[1]
        for xx in range(cx - hw, cx + hw + 1):
            lv = level * (0.5 if abs(xx - cx) >= hw - 1 else 1.0)
            if c.threshold(xx, gy + j, "bayer4") < lv:
                _lighten(c, xx, gy + j, col)


_CYL = ((0.0, 2.2), (0.24, 3.2), (0.5, 2.1), (0.78, 1.0), (1.0, 0.0))  # профиль яркости цилиндра


def _cyl_levels(n: int, w: int, shift: float = 0.0) -> list[float]:
    """Тон каждого столбца цилиндра шириной w для рампы из n тонов (полутона — шахматный стык)."""
    out = []
    for i in range(w):
        f = (i + 0.5) / w
        v = 0.0
        for (f0, v0), (f1, v1) in zip(_CYL, _CYL[1:], strict=False):
            if f <= f1:
                v = v0 + (v1 - v0) * (f - f0) / (f1 - f0)
                break
        v = v * (n - 1) / 3 + shift
        fr = v - math.floor(v)
        v = math.floor(v) + 0.5 if (w >= 7 and 0.35 <= fr <= 0.65) else float(round(v))
        out.append(max(0.0, min(n - 1.0, v)))
    return out


def _cyl(c: Canvas, x: int, y: int, w: int, h: int, rname: str, outline="k", shift: float = 0.0,
         bricks: bool = False) -> None:
    """Вертикальный цилиндр (труба, колонна, бак): блик в левой трети, тень справа, контур по бокам.
    bricks — кирпичная кладка: швы на тон темнее, ряды со сдвигом."""
    t = ramp(rname)
    o = 1 if outline else 0
    lv = _cyl_levels(len(t), w - 2 * o, shift)
    for i, v in enumerate(lv):
        xx = x + o + i
        for yy in range(y, y + h):
            k = int(v)
            if v != k and c.threshold(xx, yy, "checker") < 0.5:
                k += 1
            if bricks:
                row = yy // 2
                if yy % 2 == 1 or (xx + (row % 2) * 2) % 4 == 3:
                    k -= 1
            c.dot(xx, yy, t[max(0, min(k, len(t) - 1))])
    if outline:
        c.vline(x, y, h, outline)
        c.vline(x + w - 1, y, h, outline)


def _hpipe(c: Canvas, x: int, y: int, w: int, rname: str = "brass", flanges: bool = True) -> None:
    """Горизонтальная труба 2 px: блик сверху, тень снизу, фланцы на концах."""
    t = ramp(rname)
    c.hline(x, y, w, t[-1] if len(t) > 3 else t[2])
    c.hline(x, y + 1, w, t[1])
    if flanges:
        for fx in (x, x + w - 1):
            c.vline(fx, y - 1, 4, t[0])
            c.dot(fx, y - 1, t[2])


def _vpipe(c: Canvas, x: int, y: int, h: int, rname: str = "brass") -> None:
    """Вертикальная труба 2 px: левая кромка освещена, правая в тени."""
    t = ramp(rname)
    c.vline(x, y, h, t[2])
    c.vline(x + 1, y, h, t[0])


def _valve(c: Canvas, cx: int, cy: int) -> None:
    """Красный штурвал задвижки 3×3 со ступицей."""
    c.sprite(cx - 1, cy - 1, ["ab.", "akb", ".bb"], {"a": "red2", "b": "red1", "k": "k"})


def _railing(c: Canvas, x: int, y: int, w: int, rail="steel2", post="steel1") -> None:
    """Перила над полом y: поручень на 2 строки выше, стойки через 3 px."""
    c.hline(x, y - 2, w, rail)
    for i in list(range(0, w, 3)) + [w - 1]:
        c.dot(x + i, y - 1, post)


def _ladder(c: Canvas, x: int, y: int, h: int, rail="steel1", rung="steel2") -> None:
    """Стремянка 3 px: две тетивы и ступени через строку."""
    c.vline(x, y, h, rail)
    c.vline(x + 2, y, h, rail)
    for j in range(y + 1, y + h, 2):
        c.dot(x + 1, j, rung)


def _lamp(c: Canvas, x: int, y: int, r: int = 4, col: str = "lamp2") -> None:
    """Огонёк с ореолом: точка col и мягкое тёплое свечение радиусом r."""
    _halo(c, x, y, r, LAMP_HALO if col.startswith("lamp") else FIRE_HALO)
    c.dot(x, y, col)


_FLAME = [
    "....0..",
    "...00..",
    "...10..",
    "..011..",
    "..0210.",
    ".01210.",
    ".02321.",
    "0123321",
    ".12332.",
    "..1221.",
]
_FLAME_PAL = {"0": "fire0", "1": "fire1", "2": "fire2", "3": "fire3"}


def _flame(c: Canvas, cx: int, by: int) -> None:
    """Язык пламени 7×10 (ветер сносит вправо): cx — центр основания, by — нижняя строка."""
    _halo(c, cx, by - 5, 12, FIRE_HALO)
    _halo(c, cx, by - 4, 5, ["fire0", "fire1"])
    c.sprite(cx - 3, by - len(_FLAME) + 1, _FLAME, _FLAME_PAL)
    c.dot(cx, by - 2, MOLTEN)
    c.dot(cx + 2, by - 11, "fire1")
    c.dot(cx + 3, by - 13, "fire0")


def _sparks(c: Canvas, cx: int, cy: int, n: int, rx: int, ry: int) -> None:
    """n искр над точкой (cx, cy) в полуовале rx×ry; часть — с остывающим хвостиком."""
    for _ in range(n):
        dx, dy = c.rnd.randint(-rx, rx), -c.rnd.randint(0, ry)
        col = c.rnd.choice(("fire3", "fire2", "fire2", "fire1"))
        c.dot(cx + dx, cy + dy, col)
        if c.rnd.random() < 0.35:
            c.dot(cx + dx - (1 if dx > 0 else -1), cy + dy + 1, "fire0")


_CHUNKS = (["ab", "bc"], ["abb", "bbc"], [".ab", "abc", "bc."], ["ab.", "bbc"], ["aab", "abc"], ["ab", "bb", "bc"])


def _heap(c: Canvas, x: int, gy: int, w: int, h: int, res: str) -> None:
    """Куча кусков руды/угля/породы шириной w и высотой h: тёмная подложка, поверх — куски разной формы
    (блик сверху-слева, тень снизу-справа; на правом склоне всё на тон темнее), контур, пара бликов."""
    tones = {"ore": ("ore0", "ore1", "ore2", "brass3"), "coal": ("coal0", "coal1", "coal2", "steel3")}.get(
        res, (ROCK[1], ROCK[2], ROCK[3], "white"))
    lo, mid, hi, glint = tones
    tops = []
    for i in range(w):
        f = (i + 0.5) / w * 2 - 1
        bump = ((i * 7) % 5 == 0) - ((i * 3) % 7 == 0)
        tops.append(gy - max(1, round(h * math.sqrt(max(0.0, 1 - f * f)) + bump * 0.6)))
    for i, ty in enumerate(tops):
        c.dot(x + i, ty - 1, "k")
        c.vline(x + i, ty, gy - ty, lo)
        if i == 0 or i == w - 1:
            c.vline(x + i, ty, gy - ty, "k")

    def inside(px: int, py: int) -> bool:
        return 0 < px - x < w - 1 and tops[px - x] <= py < gy

    for yy in range(gy - h, gy, 2):
        for xx in range(x + (yy % 3), x + w, 3):
            jx = xx + c.rnd.randrange(-1, 1)
            spr = c.rnd.choice(_CHUNKS)
            right = (jx - x) > w * 0.6
            pal = {"a": mid if right else hi, "b": lo if right else mid, "c": "k" if right else lo}
            for j, row in enumerate(spr):
                for i, ch in enumerate(row):
                    if ch != "." and inside(jx + i, yy + j):
                        c.dot(jx + i, yy + j, pal[ch])
    for i, ty in enumerate(tops):  # освещённая кромка
        if 0 < i < w * 0.55:
            c.dot(x + i, ty, hi)
    for _ in range(max(1, w // 6)):
        i = c.rnd.randrange(1, max(2, w // 2))
        c.dot(x + i, tops[i] + 1, glint)


# --- Завод ---------------------------------------------------------------------------------------------


def _chimney(c: Canvas, x0: int, ctop: int, base: int, brick: bool, beacon: bool = False) -> tuple[int, int]:
    """Заводская труба 6 px от ctop до base: кладка или клёпаный лист, стальные бандажи, копоть,
    оголовок-карниз и тлеющее устье. Возвращает точку, откуда идёт дым."""
    w = 6
    _cyl(c, x0, ctop, w, base - ctop, "rust" if brick else "steel", shift=-0.3 if brick else 0.0, bricks=brick)
    for j in range(4):  # копоть у оголовка
        for i in range(1, w - 1):
            if c.threshold(x0 + i, ctop + j, "bayer4") < 0.75 - j * 0.22:
                c.dot(x0 + i, ctop + j, SOOT)
    bands = [ctop + 5, ctop + 11] if brick else [ctop + 4, ctop + 9]
    for hy in bands:
        if hy >= base - 2:
            continue
        if brick:
            c.hline(x0 - 1, hy, w + 2, "k")
            c.hline(x0, hy + 1, w, "steel1")
            c.dot(x0 + 1, hy + 1, "steel3")
            c.dot(x0 + 2, hy + 1, "steel2")
            c.dot(x0 + 4, hy + 1, "steel0")
        else:
            c.hline(x0 + 1, hy, w - 2, "red2")
            c.hline(x0 + 1, hy + 1, w - 2, "red1")
            c.dot(x0 + 4, hy + 1, "red0")
            c.dot(x0 + 4, hy, "red1")
    if not brick:
        for j in range(ctop + 6, base, 4):  # заклёпки поперечных швов
            c.dot(x0 + 2, j, "steel3")
            c.dot(x0 + 4, j, "steel1")
    # Оголовок
    c.hline(x0 - 1, ctop - 2, w + 2, "k")
    c.hline(x0 - 1, ctop - 1, w + 2, "k")
    c.hline(x0, ctop - 1, w, "steel1")
    c.dot(x0, ctop - 1, "steel3")
    c.dot(x0 + 1, ctop - 1, "steel2")
    c.dot(x0 + w - 1, ctop - 1, "steel0")
    c.dot(x0 + 2, ctop - 2, "fire0")  # тлеющее устье
    c.dot(x0 + 3, ctop - 2, "fire1")
    if beacon:  # заградительный огонь
        _halo(c, x0 + w, ctop - 2, 2, ["red0"])
        c.dot(x0 + w, ctop - 2, "red2")
    return x0 + 3, ctop - 3


def _sawtooth(c: Canvas, x: int, top: int, w: int, rname: str) -> None:
    """Пилообразная крыша: скаты (гребень-блик, фальцы, тень у карниза) и остеклённые грани-фонари."""
    t = ramp(rname)
    n = max(1, round(w / 8))
    tw = w // n
    x0 = x + (w - n * tw) // 2
    th = 6
    for k in range(n):
        rx = x0 + k * tw
        sw = tw - 2
        for i in range(sw):
            hh = max(1, round((i + 1) * th / sw))
            yt = top - hh
            c.dot(rx + i, yt - 1, "k")
            c.dot(rx + i, yt, t[3])
            for yy in range(yt + 1, top):
                col = t[2] if (rx + i) % 2 == 0 else t[1]
                if yy >= top - 1:
                    col = t[0]
                c.dot(rx + i, yy, col)
        gx = rx + sw  # фонарь: стеклянная грань, обращённая вправо
        lit = c.rnd.random() < 0.8
        c.hline(gx, top - th - 1, 2, "k")
        for j, yy in enumerate(range(top - th, top)):
            if j % 3 == 2:
                col = "k"
            elif lit:
                col = "lamp2" if j % 3 == 0 else "lamp1"
            else:
                col = "glass0" if j % 3 == 0 else "oil1"
            c.dot(gx, yy, col)
            c.dot(gx + 1, yy, "k")
        if lit:
            _halo(c, gx, top - th // 2, 3, LAMP_HALO[:2])


def _factory_window(c: Canvas, wx: int, wy: int, ww: int, wh: int, lit: bool, arch: bool) -> None:
    """Высокое окно цеха с переплётом: горящее — тёплые стёкла с бликами (часть стёкол тусклее),
    тёмное — холодные стёкла с отражением неба."""
    if lit:
        _halo(c, wx + ww // 2, wy + wh // 2, max(ww, wh) // 2 + 3, LAMP_HALO[1:])
    c.rect(wx - 1, wy - 1, ww + 2, wh + 2, None, "k")
    for j in range(wh):
        for i in range(ww):
            mull = (ww >= 5 and i == ww // 2) or j % 4 == 3
            if mull:
                col = "k" if not lit else "lamp0"
            elif lit:
                dim = (i * 5 + j * 3 + wx) % 11 == 0
                col = "lamp0" if dim else ("lamp2" if j % 4 == 0 and i % 3 == 0 else "lamp1")
            else:
                col = "glass0" if (i + j) % 5 == 0 else "oil1"
            c.dot(wx + i, wy + j, col)
    if arch:
        c.dot(wx, wy, "k")
        c.dot(wx + ww - 1, wy, "k")


def factory(c: Canvas, x: int, gy: int, w: int = 40, h: int = 21, chimneys: int = 2, col: str = "rust") -> None:
    """Цех w×h: кирпичная (rust) или профлистовая (steel) стена с пилястрами, карнизом и цоколем,
    пилообразная крыша со светящимися фонарями, высокие окна с переплётом (часть горит), погрузочные
    ворота с приподнятой рольставней и светом изнутри, вывеска с фонарями, трубы с бандажами и густым дымом."""
    t = ramp(col)
    brick = col == "rust"
    top = gy - h
    _ground_shadow(c, x - 1, gy, w + 2)
    # Трубы позади крыши
    mouths = []
    for n in range(chimneys):
        cx = x + 3 + n * (w // max(1, chimneys))
        ctop = top - 19 - (n % 2) * 4
        mouths.append(_chimney(c, cx, ctop, top, brick, beacon=(n == chimneys - 1)))
    _sawtooth(c, x, top, w, "steel" if brick else "rust")
    # Стена
    if brick:
        c.bricks(x, top, w, h, t[1], t[0], accent=t[2])
        for j in range(top + 3, top + 6):  # копоть под карнизом
            c.dither(x, j, w, 1, None, SOOT, 0.35 - (j - top - 3) * 0.1, "bayer4")
    else:
        for i in range(w):  # гофра
            k = (x + i) % 3
            c.vline(x + i, top, h, t[1] if k == 0 else (t[3] if k == 1 and i < w // 3 else t[2]))
        for j in range(top + 7, gy - 3, 6):  # горизонтальные швы с заклёпками
            c.hline(x, j, w, t[0])
            c.rivets(x + 1, j - 1, w // 3, 3, t[3])
        for _ in range(max(2, w // 10)):  # рыжие потёки
            sx = x + 1 + c.rnd.randrange(w - 2)
            for j in range(top + 3, top + 3 + c.rnd.randrange(4, 9)):
                if (j + sx) % 3:
                    c.dot(sx, j, "rust1" if j % 2 else "rust0")
    # Карниз и цоколь
    c.hline(x, top, w, t[3])
    for i in range(w):
        c.dot(x + i, top + 1, t[2] if i % 2 == 0 else t[0])
    c.hline(x, top + 2, w, t[0])
    c.hline(x, gy - 3, w, "steel2")
    c.hline(x, gy - 2, w, "steel1")
    c.hline(x, gy - 1, w, "steel0")
    for i in range(0, w, 5):
        c.dot(x + i, gy - 2, "steel0")
    # Ворота посередине
    dw = 11 if w >= 36 else 9
    dh = min(12, h - 9)
    gx = x + (w - dw) // 2
    dy0 = gy - dh
    # Пилястры и окна по пролётам
    nb = max(2, round((w - 2) / 9))
    piers = [x + round(k * (w - 2) / nb) for k in range(nb + 1)]
    for k, px in enumerate(piers):
        if gx - 2 <= px <= gx + dw:
            continue
        c.vline(px, top + 3, gy - top - 6, t[2] if brick else t[3])
        c.vline(px + 1, top + 3, gy - top - 6, t[0])
        c.hline(px - 1 if k else px, top + 3, 3 if k else 2, t[3])
    wy, wh = top + 5, gy - top - 11
    for a, b in zip(piers, piers[1:], strict=False):
        inner = b - a - 2
        ww = 5 if inner >= 7 else 3
        wx = a + 2 + (inner - ww) // 2
        if wx + ww >= gx - 1 and wx <= gx + dw:
            continue
        _factory_window(c, wx, wy, ww, wh, c.rnd.random() < 0.75, brick)
        c.hline(wx - 1, wy + wh + 1, ww + 2, "steel2")  # подоконник
        c.dot(wx + ww, wy + wh + 1, "steel0")
        if brick:  # клинчатая перемычка
            for i in range(-1, ww + 1):
                c.dot(wx + i, wy - 2, t[3] if i % 2 else t[2])
    c.rect(x, top, w, h, None, "k")
    # Ворота: проём с освещённым нутром, рольставня приподнята на треть
    c.rect(gx, dy0, dw, dh, "lamp1")
    for yy in range(dy0, gy):
        for xx in (gx, gx + dw - 1):
            c.dot(xx, yy, "lamp0")
    c.dither(gx + 1, dy0, dw - 2, dh, None, "lamp2", 0.25, "bayer4")
    c.hline(gx, gy - 1, dw, "lamp0")
    c.rect(gx + 1, gy - 4, 3, 3, "wood0")  # ящики в глубине
    c.rect(gx + 2, gy - 6, 2, 2, "wood0")
    c.dot(gx + 1, gy - 4, "wood1")
    fx = gx + dw - 4  # силуэт рабочего
    c.rect(fx, gy - 5, 2, 4, "wood0")
    c.dot(fx, gy - 6, "wood0")
    c.dot(fx + 1, gy - 6, "wood0")
    c.dot(fx, gy - 1, "wood0")
    c.dot(fx + 1, gy - 1, "wood0")
    sh = max(2, dh // 3)
    for j in range(sh):
        c.hline(gx, dy0 + j, dw, "steel2" if j % 2 == 0 else "steel1")
    c.hline(gx, dy0 + sh, dw, "steel0")
    c.dot(gx + dw // 2, dy0 + sh, "steel3")  # ручка
    c.vline(gx - 1, dy0 - 1, dh + 1, "k")
    c.vline(gx + dw, dy0 - 1, dh + 1, "k")
    c.vline(gx - 2, dy0, dh, "steel2")  # направляющие
    c.vline(gx + dw + 1, dy0, dh, "steel0")
    # Вывеска над воротами и фонари по краям
    sy = dy0 - 4
    c.rect(gx - 2, sy, dw + 4, 3, "brass1", "k")
    c.hline(gx - 1, sy + 1, dw + 2, "brass2")
    for i in range(1, dw + 1, 2):
        c.dot(gx - 1 + i, sy + 1, "brass0")
    for lx in (gx - 3, gx + dw + 2):
        _lamp(c, lx, sy + 1, 4)
    _spill(c, gx + dw // 2, gy, dw, 4)
    for sx, sy2 in mouths:
        smoke(c, sx, sy2, 8, tone=2)


# --- Буровая -------------------------------------------------------------------------------------------


def drill_rig(c: Canvas, x: int, gy: int) -> None:
    """Буровая: подвышечное основание с красным превентором и лестницей, решётчатая вышка (освещённая
    левая нога, тёмная правая, пояса и X-раскосы), балкон верхового, кронблок с мачтой и огнём, талевый
    блок на канатах, крюк, вертлюг, ведущая труба и ротор, прожектор, дизельная будка с выхлопом, куча руды."""
    fl = gy - 8  # пол буровой
    th = 31
    top = fl - th
    _ground_shadow(c, x - 2, gy, 52)

    def legs(yy: int) -> tuple[int, int]:
        f = (fl - 1 - yy) / (th - 1)
        return round(x + 5 * f), round(x + 17 - 5 * f)

    # Подвышечное основание: стойки, раскосы, превентор
    for px in (x, x + 16):
        c.vline(px, fl + 2, gy - fl - 2, "steel2")
        c.vline(px + 1, fl + 2, gy - fl - 2, "steel0")
    c.line(x + 2, fl + 2, x + 5, gy - 1, "steel1")
    c.line(x + 15, fl + 2, x + 12, gy - 1, "steel1")
    c.box(x + 6, fl + 2, 6, gy - fl - 2, "red", base=1)
    c.hline(x + 5, fl + 4, 8, "steel2")
    c.hline(x + 5, fl + 5, 8, "steel0")
    c.dot(x + 5, fl + 4, "steel3")
    _valve(c, x + 13, fl + 3)
    # Лестница на пол буровой
    for k in range(7):
        c.hline(x - 2 - k, fl + 1 + k, 2, "steel2")
        c.dot(x - 1 - k, fl + 1 + k, "steel0")
    c.line(x - 1, fl - 2, x - 8, gy - 3, "steel1")
    # Вышка: X-раскосы в панелях, пояса, ноги
    girts = list(range(fl - 1, top, -6)) + [top]
    for y0, y1 in zip(girts, girts[1:], strict=False):
        a0, b0 = legs(y0)
        a1, b1 = legs(y1)
        c.line(a0 + 1, y0, b1 - 1, y1, "steel1")
        c.line(b0 - 1, y0, a1 + 1, y1, "steel0")
    for yy in girts:
        a, b = legs(yy)
        c.hline(a, yy, b - a + 1, "steel2")
    for yy in range(top, fl):
        a, b = legs(yy)
        c.dot(a, yy, "steel3")
        c.dot(b, yy, "steel1")
    for yy in girts[1:-1]:  # косынки на узлах
        a, b = legs(yy)
        c.dot(a + 1, yy - 1, "steel2")
        c.dot(b - 1, yy - 1, "steel1")
    # Балкон верхового
    mb = top + 12
    a, _ = legs(mb)
    c.hline(a - 4, mb, 5, "wood2")
    c.hline(a - 4, mb + 1, 5, "wood0")
    _railing(c, a - 4, mb, 4, "steel2", "steel1")
    # Кронблок, мачта с огнём
    c.box(x + 4, top - 3, 10, 4, "rust", base=2)
    c.dot(x + 6, top - 2, "k")
    c.dot(x + 9, top - 2, "k")
    c.dot(x + 12, top - 2, "k")
    c.line(x + 6, top - 4, x + 8, top - 7, "steel2")
    c.line(x + 11, top - 4, x + 9, top - 7, "steel1")
    c.sparkle(x + 9, top - 9, "red2", 1, "red0")
    # Талевая система: канаты, блок, крюк, вертлюг, ведущая труба, ротор
    ty = top + 9
    c.vline(x + 7, top + 1, ty - top - 1, "steel2")
    c.vline(x + 10, top + 1, ty - top - 1, "steel1")
    c.box(x + 6, ty, 6, 5, "brass", base=2)
    c.hline(x + 7, ty + 2, 4, "brass0")
    c.sprite(x + 8, ty + 5, ["kk", ".k", "kk"], {"k": "steel3"})
    c.box(x + 7, ty + 8, 4, 3, "rust", base=1)
    c.vline(x + 8, ty + 11, fl - ty - 13, "steel3")
    c.vline(x + 9, ty + 11, fl - ty - 13, "steel1")
    c.rect(x + 5, fl - 2, 8, 2, "steel1", "k")
    c.hline(x + 6, fl - 2, 6, "brass2")
    # Пол буровой
    c.rect(x - 2, fl, 21, 2, "wood1", "k")
    c.hline(x - 1, fl, 19, "wood2")
    for i in range(x, x + 18, 3):
        c.dot(i, fl + 1, "wood0")
    _railing(c, x + 14, fl, 5, "steel2", "steel1")
    # Прожектор на ноге вышки, свет на пол
    lx, ly = legs(fl - 14)[0], fl - 14
    _halo(c, lx - 2, ly, 4, LAMP_HALO)
    c.dot(lx - 1, ly - 1, "steel1")
    c.dot(lx - 1, ly, "lamp2")
    c.dot(lx - 2, ly, "white")
    # Дизельная будка: гофра, крыша, окно, решётка радиатора, выхлоп
    hx, hw, hh = x + 21, 14, 12
    _ground_shadow(c, hx - 1, gy, hw + 2)
    for i in range(hw):
        k = (hx + i) % 3
        c.vline(hx + i, gy - hh, hh, "steel1" if k == 0 else ("steel3" if k == 1 and i < 4 else "steel2"))
    c.hline(hx, gy - 3, hw, "steel0")
    c.rect(hx, gy - hh, hw, hh, None, "k")
    c.rect(hx - 1, gy - hh - 2, hw + 2, 3, "rust1", "k")
    c.hline(hx, gy - hh - 1, hw, "rust3")
    c.dot(hx + hw - 1, gy - hh - 1, "rust1")
    _halo(c, hx + 4, gy - 7, 5, LAMP_HALO[1:])
    c.rect(hx + 2, gy - 9, 5, 4, "k")
    c.rect(hx + 3, gy - 8, 3, 2, "lamp1")
    c.dot(hx + 3, gy - 8, "lamp2")
    for i in range(hx + 9, hx + 13):  # жалюзи радиатора
        c.vline(i, gy - 9, 5, "k" if i % 2 else "steel1")
    c.rivets(hx + 1, gy - hh + 1, 5, 3, "steel3")
    c.rect(hx + 10, gy - hh - 9, 3, 7, "steel1", "k")
    c.vline(hx + 11, gy - hh - 8, 6, "steel2")
    c.hline(hx + 9, gy - hh - 9, 5, "k")
    c.dot(hx + 11, gy - hh - 10, "fire1")
    smoke(c, hx + 11, gy - hh - 11, 6, tone=1)
    # Куча руды
    _heap(c, x + 37, gy, 13, 7, "ore")


# --- Станок-качалка ------------------------------------------------------------------------------------

_HORSEHEAD = [
    "..kkkkkk",
    ".kHHHHhk",
    "kSHhhhhk",
    "kShhhhmk",
    "kShhhhmk",
    "kShhhhmk",
    "kShhhmmk",
    "kShhhmmk",
    ".kShmmmk",
    "..kSmmmk",
    "...kSmmk",
    "....kkkk",
]


def pumpjack(c: Canvas, x: int, gy: int, tanks: bool = True) -> None:
    """Станок-качалка: бетонный фундамент, клёпаная рама, стойка-«А» с лестницей, латунный балансир-
    двутавр, «голова лошади» с канатной подвеской и полированным штоком, устье со штурвалом и лужей,
    редуктор с кривошипом и противовесом, шатуны, мотор с ремённым кожухом; рядом бочки пирамидкой."""
    _ground_shadow(c, x - 3, gy, 48)
    # Фундамент и рама
    c.rect(x - 2, gy - 2, 46, 2, CONCRETE[1], "k")
    c.hline(x - 1, gy - 2, 44, CONCRETE[2])
    c.rect(x + 8, gy - 4, 34, 2, "steel1", "k")
    c.hline(x + 9, gy - 4, 32, "steel2")
    c.rivets(x + 10, gy - 4, 10, 3, "steel3")
    # Стойка-«А»
    px, py = x + 18, gy - 24
    c.line(x + 13, gy - 5, px - 1, py + 2, "steel3")
    c.line(x + 14, gy - 5, px, py + 2, "steel2")
    c.line(x + 23, gy - 5, px + 2, py + 2, "steel1")
    c.line(x + 22, gy - 5, px + 1, py + 2, "steel0")
    c.hline(x + 15, gy - 13, 7, "steel2")
    c.line(x + 15, gy - 12, x + 21, gy - 6, "steel0")
    for j in range(gy - 11, gy - 5, 2):  # ступени лестницы на стойке
        c.dot(x + 12 + (gy - 5 - j) // 4, j, "steel2")
    # Редуктор на тумбе, мотор с кожухом ремня
    c.rect(x + 29, gy - 8, 7, 4, CONCRETE[1], "k")
    c.box(x + 28, gy - 15, 9, 8, "steel", base=1)
    c.hline(x + 29, gy - 11, 7, "steel0")
    c.dot(x + 30, gy - 13, "brass2")
    c.box(x + 37, gy - 11, 6, 7, "green", base=1)
    for i in range(x + 38, x + 42, 2):
        c.vline(i, gy - 9, 4, "green0")
    c.dot(x + 41, gy - 10, "red2")
    c.poly([(x + 33, gy - 16), (x + 36, gy - 16), (x + 41, gy - 11), (x + 38, gy - 11)], "steel1")
    c.line(x + 33, gy - 16, x + 37, gy - 12, "steel2")
    # Кривошип с противовесом
    sx, sy = x + 32, gy - 12
    c.shaded_disk(sx, sy, 5, "rust", base=1)
    c.poly([(sx - 5, sy + 1), (sx + 6, sy + 1), (sx + 4, sy + 5), (sx - 4, sy + 5)], "rust0")
    c.hline(sx - 4, sy + 1, 9, "rust1")
    c.dot(sx - 3, sy - 3, "rust3")
    c.dot(sx - 2, sy - 4, "rust3")
    c.line(sx, sy, sx - 2, sy - 5, "k")
    c.dot(sx, sy, "brass3")
    c.dot(sx + 2, sy + 3, "steel2")
    c.dot(sx - 2, sy + 3, "steel2")
    pin = (sx - 2, sy - 5)
    # Балансир: двутавр с наклоном, заклёпки
    def beam_y(bx: int) -> int:
        return py + round((bx - px) / 11)

    bx0, bx1 = x + 6, x + 36
    for bx in range(bx0, bx1 + 1):
        by = beam_y(bx)
        c.dot(bx, by - 2, "k")
        c.dot(bx, by - 1, "brass3" if bx < px else "brass2")
        c.dot(bx, by, "brass1")
        c.dot(bx, by + 1, "brass0")
        c.dot(bx, by + 2, "k")
        if (bx - bx0) % 3 == 1:
            c.dot(bx, by, "brass2")
    c.vline(bx1 + 1, beam_y(bx1) - 2, 5, "k")
    # Шатун от хвоста балансира к пальцу кривошипа
    tx, ty = bx1 - 1, beam_y(bx1 - 1) + 2
    c.line(tx, ty, pin[0], pin[1], "steel2")
    c.line(tx + 1, ty, pin[0] + 1, pin[1], "steel0")
    c.box(tx - 2, ty - 1, 4, 2, "steel", outline=None, base=1)
    c.dot(pin[0], pin[1], "brass3")
    # Опора балансира
    c.box(px - 2, py - 1, 6, 4, "steel", base=2)
    c.dot(px, py, "brass3")
    # «Голова лошади», канатная подвеска, шток, устье
    hy = beam_y(bx0) - 5
    c.sprite(x, hy, _HORSEHEAD, {"k": "k", "H": "rust3", "h": "rust2", "m": "rust1", "S": "steel2"})
    cy0 = hy + 10
    c.vline(x + 1, cy0, gy - 12 - cy0, "steel1")
    c.vline(x + 2, cy0 + 1, gy - 13 - cy0, "k")
    c.rect(x, gy - 12, 4, 2, "steel2", "k")
    c.vline(x + 1, gy - 10, 3, "white")
    c.vline(x + 2, gy - 10, 3, "steel2")
    c.box(x - 1, gy - 7, 6, 3, "steel", base=2)
    c.rect(x, gy - 8, 4, 1, "steel1")
    c.hline(x - 3, gy - 6, 2, "brass2")
    _valve(c, x - 4, gy - 8)
    c.vline(x + 1, gy - 4, 2, "steel1")
    c.vline(x + 2, gy - 4, 2, "steel0")
    c.hline(x - 1, gy, 6, "oil0")  # мазутная лужа у устья
    c.hline(x + 1, gy + 1, 5, "oil0")
    c.dot(x + 2, gy, SHEEN)
    c.dot(x + 3, gy + 1, "oil2")
    if tanks:
        bx = x + 46
        _ground_shadow(c, bx - 1, gy, 18)
        barrel(c, bx, gy - 9)
        barrel(c, bx + 8, gy - 9)
        barrel(c, bx + 4, gy - 18)
        c.hline(bx + 15, gy, 4, "oil0")
        c.dot(bx + 16, gy, SHEEN)


# --- Домна ---------------------------------------------------------------------------------------------


def _heat_tint(c: Canvas, cx: int, cy: int, rx: int, ry: int) -> None:
    """Отсвет жара на кладке: в эллипсе rx×ry тона ржавчины заменяются тонами накала (текстура кладки
    сохраняется), край эллипса — дизером."""
    remap = {c.rgb("rust0"): HEAT[0], c.rgb("rust1"): HEAT[1], c.rgb("rust2"): HEAT[2], c.rgb("steel1"): "rust1",
             c.rgb("steel3"): "fire2"}
    for dy in range(-ry, ry + 1):
        for dx in range(-rx, rx + 1):
            d = math.hypot(dx / (rx + 0.5), dy / (ry + 0.5))
            if d >= 1 or (d > 0.7 and c.threshold(cx + dx, cy + dy, "bayer4") < (d - 0.7) / 0.3):
                continue
            new = remap.get(c.get(cx + dx, cy + dy))
            if new is not None:
                c.dot(cx + dx, cy + dy, new)


def _ingot(c: Canvas, x: int, y: int, hot: bool) -> None:
    """Слиток 7×4 (x, y — верхний левый угол): скошенные торцы, светлая верхняя грань; раскалённый —
    в тонах огня с ореолом."""
    t = ("fire0", "fire1", "fire2", "fire3") if hot else ("steel0", "steel1", "steel2", "steel3")
    if hot:
        _halo(c, x + 3, y + 2, 5, FIRE_HALO[1:])
    c.sprite(x, y, [".kkkkk.", "kabbbck", "kbbbcck", ".kkkkk."],
             {"k": "k" if not hot else "fire0", "a": t[3], "b": t[2], "c": t[1]})
    if hot:
        c.dot(x + 2, y + 1, MOLTEN)


def _ladle(c: Canvas, lx: int, ly: int) -> None:
    """Разливочный ковш 12×11 (lx, ly — левый край и строка зеркала металла): клёпаный конус с поясом,
    цапфы, дужка к крюку, зеркало жидкой стали, носок справа."""
    _halo(c, lx + 6, ly, 7, FIRE_HALO[1:])
    for dx, dy in ((0, 3), (11, 3)):  # дужка от цапф к крюку
        c.line(lx + dx, ly + dy, lx + 5 + (dx > 0), ly - 6, "steel1" if dx else "steel2")
    c.hline(lx + 1, ly - 1, 10, "k")
    c.dot(lx, ly, "k")
    c.dot(lx + 11, ly, "k")
    c.hline(lx + 1, ly, 10, "fire2")
    c.hline(lx + 3, ly, 6, "fire3")
    c.hline(lx + 5, ly, 2, MOLTEN)
    c.hline(lx, ly + 1, 12, "steel3")
    c.hline(lx + 6, ly + 1, 6, "steel2")
    c.dot(lx, ly + 1, "k")
    c.dot(lx + 11, ly + 1, "k")
    for j in range(2, 10):
        a = lx + (j - 2) // 3
        b = lx + 11 - (j - 2) // 3
        c.dot(a, ly + j, "k")
        c.dot(b, ly + j, "k")
        lv = _cyl_levels(4, b - a - 1)
        for i, v in enumerate(lv):
            k = int(v) + (1 if v != int(v) and c.threshold(a + 1 + i, ly + j, "checker") < 0.5 else 0)
            if j == 5:
                k -= 2
            c.dot(a + 1 + i, ly + j, ramp("steel")[max(0, min(3, k))])
    c.hline(lx + 3, ly + 10, 6, "k")
    c.rivets(lx + 2, ly + 6, 3, 3, "steel3")
    c.dot(lx - 1, ly + 3, "steel2")  # цапфы
    c.dot(lx + 12, ly + 3, "steel1")
    c.dot(lx + 12, ly, "steel2")  # носок
    c.dot(lx + 12, ly - 1, "k")
    c.dot(lx + 13, ly, "fire3")


def furnace(c: Canvas, x: int, gy: int) -> None:
    """Домна: кирпичный горн с бандажами и фурмами, клёпаная шахта-конус, площадка колошника с перилами,
    труба с дымом, огнедышащий зев с ореолом и отсветами на кладке, жёлоб с металлом, консольный кран
    с ковшом, который льёт сталь в изложницу, искры, раскалённый и остывшие слитки."""
    _ground_shadow(c, x - 1, gy, 64)
    bt = gy - 20  # верх горна
    # Труба над колошником
    st = gy - 46
    _cyl(c, x + 9, st, 8, bt - 13 - st, "steel", shift=-0.2)
    for hy in (st + 4, st + 9):
        c.hline(x + 9, hy, 8, "k")
        c.hline(x + 10, hy + 1, 6, "red1")
        c.dot(x + 10, hy + 1, "red2")
        c.dot(x + 15, hy + 1, "red0")
    for j in range(3):
        c.dither(x + 10, st + j, 6, 1, None, SOOT, 0.7 - j * 0.25, "bayer4")
    c.rect(x + 8, st - 2, 10, 2, "steel1", "k")
    c.dot(x + 9, st - 1, "steel3")
    c.dot(x + 12, st - 2, "fire0")
    c.dot(x + 13, st - 2, "fire1")
    # Шахта: усечённый конус из клёпаного листа
    s_top = bt - 13
    for yy in range(s_top, bt):
        f = (yy - s_top) / (bt - s_top)
        a, b = round(x + 6 - 3 * f), round(x + 19 + 3 * f)
        lv = _cyl_levels(4, b - a - 1)
        c.dot(a, yy, "k")
        c.dot(b, yy, "k")
        for i, v in enumerate(lv):
            k = int(v) + (1 if v != int(v) and c.threshold(a + 1 + i, yy, "checker") < 0.5 else 0)
            if (yy - s_top) % 4 == 3:
                k -= 1
            c.dot(a + 1 + i, yy, ramp("steel")[max(0, min(3, k))])
        if (yy - s_top) % 4 == 3:
            for i in range(a + 2, b - 1, 3):
                c.dot(i, yy - 1, "steel3" if i < x + 12 else "steel2")
    # Колошниковая площадка с перилами и газоотводом
    c.rect(x + 3, s_top - 2, 20, 2, "steel2", "k")
    c.hline(x + 4, s_top - 2, 18, "steel3")
    _railing(c, x + 3, s_top - 2, 20, "steel2", "steel1")
    c.hline(x + 20, s_top - 6, 7, "brass3")
    c.hline(x + 20, s_top - 5, 6, "brass1")
    _vpipe(c, x + 25, s_top - 5, bt - s_top + 3, "brass")
    c.dot(x + 26, s_top - 6, "brass2")
    # Ореол топки — до горна: кладка его перекроет, на небе и земле он останется
    mx, my = x + 13, gy - 6
    _halo(c, mx, my, 16, FIRE_HALO)
    # Горн: кладка, бандажи, кольцевой воздуховод с фурмами
    c.bricks(x, bt, 26, gy - bt, "rust1", "rust0", accent="rust2")
    for yy in (bt + 7, bt + 14):
        c.hline(x, yy, 26, "steel1")
        c.hline(x, yy - 1, 26, "k")
        c.rivets(x + 2, yy, 8, 3, "steel3")
    c.rect(x - 1, bt - 2, 28, 3, "steel1", "k")
    c.hline(x, bt - 2, 26, "steel3")
    c.hline(x + 18, bt - 1, 8, "steel0")
    for i in (x + 3, x + 12, x + 21):  # фурмы с огоньком
        c.rect(i, bt + 1, 3, 2, "steel1", "k")
        c.dot(i + 1, bt + 2, "fire2")
    c.rect(x, bt, 26, gy - bt, None, "k")
    _heat_tint(c, mx, my, 10, 8)
    # Зев: арка, огонь, белый жар
    c.rect(x + 7, gy - 12, 12, 12, "k")
    c.dot(x + 7, gy - 12, HEAT[0])
    c.dot(x + 18, gy - 12, HEAT[0])
    c.rect(x + 8, gy - 11, 10, 11, "fire0")
    c.rect(x + 9, gy - 10, 8, 10, "fire1")
    c.rect(x + 10, gy - 8, 6, 8, "fire2")
    c.rect(x + 11, gy - 6, 4, 6, "fire3")
    c.rect(x + 12, gy - 4, 2, 3, MOLTEN)
    c.dot(x + 8, gy - 11, "k")
    c.dot(x + 17, gy - 11, "k")
    c.hline(x + 6, gy - 13, 14, "steel2")
    c.dot(x + 6, gy - 13, "steel3")
    c.hline(x + 7, gy - 14, 12, "k")
    # Жёлоб с текущим металлом
    c.hline(x + 14, gy - 1, 14, "fire2")
    c.hline(x + 26, gy, 3, "k")
    for i in range(x + 15, x + 28, 3):
        c.dot(i, gy - 1, "fire3")
    # Пятно света на земле, искры
    _halo(c, mx + 4, gy + 1, 15, ["haze1", HEAT[0]], ry=4)
    _sparks(c, mx, gy - 14, 4, 6, 5)
    c.sparkle(x + 22, gy - 15, "fire3", 1, "fire1")
    # Консольный кран-балка с подкосом
    by = s_top + 2
    bx1 = x + 44
    c.rect(x + 22, by, bx1 - x - 21, 2, "steel2", "k")
    c.hline(x + 23, by, bx1 - x - 24, "steel3")
    for i in range(x + 24, bx1, 3):
        c.dot(i, by + 1, "steel0")
    c.line(x + 26, bt - 3, x + 38, by + 2, "steel1")
    c.line(x + 26, bt - 2, x + 38, by + 3, "steel0")
    # Тележка, цепи, крюк, ковш, струя в изложницу
    lx, ly = x + 30, gy - 15
    c.box(lx + 3, by + 2, 6, 3, "rust", base=1)
    for chx in (lx + 5, lx + 6):
        for j in range(by + 5, ly - 6):
            c.dot(chx, j, "steel2" if (j + chx) % 2 else "steel0")
    _ladle(c, lx, ly)
    c.vline(lx + 13, ly + 1, gy - ly - 5, "fire2")
    c.vline(lx + 14, ly + 2, gy - ly - 6, "fire1")
    for j in range(ly + 2, gy - 4, 3):
        c.dot(lx + 13, j, MOLTEN)
    c.rect(lx + 10, gy - 4, 8, 4, "steel1", "k")
    c.hline(lx + 11, gy - 4, 6, "fire2")
    c.dot(lx + 13, gy - 4, MOLTEN)
    c.hline(lx + 11, gy - 3, 6, "fire0")
    c.hline(lx + 11, gy - 2, 6, "steel2")
    _sparks(c, lx + 13, gy - 5, 6, 4, 4)
    # Слитки: раскалённый у изложницы, штабель остывших
    _ingot(c, x + 48, gy - 4, True)
    _ingot(c, x + 55, gy - 4, False)
    _ingot(c, x + 57, gy - 7, False)


# --- НПЗ -----------------------------------------------------------------------------------------------


def _column(c: Canvas, x: int, gy: int, w: int, h: int, decks: list[int], ladder_right: bool = True) -> None:
    """Ректификационная колонна: цилиндр с куполом, пояса с заклёпками, площадки с перилами и огнями,
    лестница-стремянка вдоль борта."""
    top = gy - h
    _cyl(c, x, top + 2, w, h - 2, "steel")
    c.hline(x + 2, top, w - 4, "k")
    c.hline(x + 1, top + 1, w - 2, "k")
    c.hline(x + 2, top + 1, w - 4, "steel2")
    c.dot(x + 2, top + 1, "steel3")
    for j in range(top + 5, gy - 2, 6):
        c.hline(x + 1, j, w - 2, "steel0")
        c.dot(x + 2, j - 1, "steel3")
    if ladder_right:
        _ladder(c, x + w, top + 4, h - 4, "steel1", "steel2")
    for d in decks:
        y = gy - d
        c.hline(x - 2, y, w + 5, "steel3")
        c.hline(x - 2, y + 1, w + 5, "steel0")
        _railing(c, x - 2, y, w + 5, "steel2", "steel1")
        _lamp(c, x - 2 if d % 2 == 0 else x + w + 2, y - 3, 3)


def refinery(c: Canvas, x: int, gy: int) -> None:
    """НПЗ: факельная труба с растяжками и пламенем, две ректификационные колонны с площадками, огнями и
    лестницами, шлемовая труба между ними, резервуар с куполом, винтовой лестницей и полосой, трубная
    эстакада с фланцами и задвижками, струйка пара."""
    _ground_shadow(c, x - 6, gy, 49)
    # Факельная труба с растяжками
    fx, ft = x - 5, gy - 38
    c.line(fx, ft + 6, x - 12, gy - 1, "steel0")
    c.line(fx + 1, ft + 6, x + 1, gy - 1, "steel0")
    c.vline(fx, ft, gy - ft, "steel2")
    c.vline(fx + 1, ft, gy - ft, "steel0")
    for j in range(ft + 3, gy, 5):
        c.dot(fx, j, "steel3")
        c.dot(fx + 1, j, "k")
    c.rect(fx - 1, ft - 1, 4, 2, "steel1", "k")
    _flame(c, fx + 1, ft - 2)
    # Колонны
    _column(c, x + 1, gy, 8, 38, [12, 24, 34])
    _column(c, x + 13, gy, 7, 27, [11, 21])
    # Шлемовая труба: с верха высокой колонны в верх низкой
    c.hline(x + 5, gy - 41, 13, "brass3")
    c.hline(x + 5, gy - 40, 13, "brass1")
    c.vline(x + 4, gy - 40, 2, "brass2")
    _vpipe(c, x + 16, gy - 40, 13, "brass")
    c.vline(x + 16, gy - 39, 1, "brass3")
    # Резервуар
    tx, tw, th = x + 24, 17, 16
    top = gy - th
    _ground_shadow(c, tx - 1, gy, tw + 2)
    _cyl(c, tx, top, tw, th, "steel")
    c.hline(tx + 3, top - 2, tw - 6, "k")
    c.hline(tx + 1, top - 1, tw - 2, "k")
    c.hline(tx + 3, top - 1, tw - 6, "steel2")
    c.hline(tx + 4, top - 1, 3, "steel3")
    c.hline(tx + 1, top, tw - 2, "steel0")
    c.hline(tx + 1, top + 5, tw - 2, "red1")
    c.hline(tx + 1, top + 6, tw - 2, "red0")
    c.hline(tx + 3, top + 5, 3, "red2")
    c.rect(tx + 8, top + 4, 5, 4, "brass1", "k")  # латунная табличка-эмблема
    c.dot(tx + 10, top + 5, "brass3")
    for j in (top + 10, gy - 2):
        c.hline(tx + 1, j, tw - 2, "steel0")
        c.rivets(tx + 2, j - 1, (tw - 3) // 3, 3, "steel3")
    for i in range(th - 2):  # винтовая лестница по борту
        c.dot(tx + tw - 2 - i // 2 * 1 - i // 3, gy - 2 - i, "steel3")
    c.line(tx + tw - 1, gy - 3, tx + 6, top + 1, "steel1")
    c.vline(tx + 12, top - 5, 3, "steel2")
    c.dot(tx + 12, top - 6, "red2")
    _halo(c, tx + 12, top - 6, 3, ["red0"])
    c.rect(tx + 2, gy - 4, 3, 3, "k")  # лаз
    c.dot(tx + 3, gy - 3, "steel1")
    # Трубная эстакада
    _hpipe(c, x + 9, gy - 8, 15, "brass")
    _hpipe(c, x - 3, gy - 4, 27, "steel")
    _vpipe(c, x + 21, gy - 8, 4, "brass")
    _valve(c, x + 11, gy - 11)
    c.vline(x + 11, gy - 10, 2, "steel1")
    _valve(c, x + 22, gy - 13)
    for px in (x + 10, x + 18):
        c.vline(px, gy - 6, 2, "steel1")
    # Пар из клапана
    smoke(c, x + 16, gy - 29, 4, tone=3)


# --- Мастерская ----------------------------------------------------------------------------------------

_INTERIOR = [
    "oooooooooooo",
    "o.......k..o",
    "o.ddddd.k..o",
    "o.d.dddkkk.o",
    "o.d..d..w..o",
    "o.d..d.....o",
    "o.d........o",
    "o..........o",
    "oSs......d.o",
    "oBBBBBBBBBBo",
    "oddddddddddo",
    "o.d......d.o",
    "ooddoooooddo",
]

_ANVIL = [
    "kkkkkkkkkkk.",
    "kHHHHHHHHhhk",
    ".kkhhhhhhhmk",
    "...kkhhhmkk.",
    "....khhmk...",
    "...khhhmmk..",
    "...kkkkkkk..",
]


def workshop(c: Canvas, x: int, gy: int) -> None:
    """Мастерская: дощатый сарай под вальмовой крышей из ржавого профлиста, шестерня-вывеска на коньке,
    печная труба, распахнутые откатные ворота — внутри свет лампы, верстак с тисками и инструменты на
    стене; окно с переплётом; снаружи наковальня на колоде с искрами и горн с жаром."""
    ww, wh = 35, 17
    top = gy - wh
    _ground_shadow(c, x - 1, gy, ww + 2)
    # Печная труба и шестерня на коньке (позади крыши)
    c.rect(x + 26, top - 15, 3, 9, "steel1", "k")
    c.vline(x + 27, top - 14, 8, "steel2")
    c.rect(x + 25, top - 16, 5, 2, "steel2", "k")
    c.vline(x + 17, top - 11, 3, "steel1")
    gear(c, x + 17, top - 14, 4, "brass")
    # Крыша: вальмовая, профлист
    rt, ry0 = top - 9, top - 1
    for yy in range(rt, ry0 + 1):
        f = (yy - rt) / (ry0 - rt)
        a, b = round(x + 6 - 8 * f), round(x + ww - 7 + 8 * f)
        for xx in range(a, b + 1):
            k = (xx - x) % 3
            col = "rust2" if k == 0 else ("rust1" if k == 1 else "rust2")
            if k == 2 and (xx * 7 + yy) % 5 == 0:
                col = "rust3"
            c.dot(xx, yy, col)
        c.dot(a - 1, yy, "k")
        c.dot(b + 1, yy, "k")
        for i in range(0, 3):  # торцевые скаты вальмы: левый освещён, правый в тени
            c.dot(a + i, yy, "rust3" if i < 2 else "rust2")
            c.dot(b - i, yy, "rust0" if i < 2 else "rust1")
    for _ in range(4):  # пятна ржавчины
        px, py = x + 2 + c.rnd.randrange(ww - 4), rt + 1 + c.rnd.randrange(ry0 - rt - 1)
        c.dot(px, py, "rust0")
        c.dot(px, py + 1, "rust0")
    c.hline(x + 6, rt - 1, ww - 12, "k")
    c.hline(x + 6, rt, ww - 12, "steel2")  # конёк
    c.hline(x + 6, rt, 4, "steel3")
    c.hline(x - 3, ry0 + 1, ww + 6, "k")  # свес
    c.hline(x - 2, ry0, ww + 4, "rust0")
    # Стена из досок
    for i in range(ww):
        k = (x + i) % 4
        c.vline(x + i, top + 1, wh - 1, "wood0" if k == 0 else ("wood2" if k == 1 else "wood1"))
    c.dither(x, top + 1, ww, 2, None, "wood0", 0.5)  # тень под свесом
    c.hline(x, gy - 7, ww, "wood0")
    for i in range(x + 1, x + ww, 4):
        c.dot(i, gy - 8, "steel2")  # шляпки гвоздей
    c.rect(x, top, ww, wh, None, "k")
    # Проём ворот и освещённое нутро: лампа на шнуре, инструменты на стене, полка, верстак с тисками
    dx0, dw, dh = x + 12, 12, 13
    dy0 = gy - dh
    _halo(c, dx0 + 8, dy0 + 5, 9, LAMP_HALO)
    c.rect(dx0, dy0, dw, dh, "lamp1")
    _halo(c, dx0 + 8, dy0 + 6, 4, ["lamp2"])
    c.sprite(dx0, dy0, _INTERIOR, {"o": "lamp0", "d": "wood0", "k": "k", "w": "white", "s": "steel1",
                                   "S": "steel2", "b": "wood1", "B": "wood2", "f": "fire1"})
    c.vline(dx0 - 1, dy0 - 1, dh + 1, "k")
    c.vline(dx0 + dw, dy0 - 1, dh + 1, "k")
    c.hline(dx0 - 1, dy0 - 1, dw + 2, "k")
    # Откатная створка, сдвинутая влево, и направляющая
    sx0 = x + 2
    c.rect(sx0, dy0, 9, dh, "wood1", "k")
    for i in range(sx0 + 2, sx0 + 8, 2):
        c.vline(i, dy0 + 1, dh - 2, "wood0")
    c.vline(sx0 + 1, dy0 + 1, dh - 2, "wood2")
    c.line(sx0 + 1, gy - 2, sx0 + 7, dy0 + 2, "wood2")
    c.hline(sx0 + 1, dy0 + 2, 7, "wood2")
    c.hline(sx0 + 1, gy - 2, 7, "wood2")
    c.hline(x + 1, dy0 - 2, dx0 + dw - x, "steel1")
    c.dot(sx0 + 2, dy0 - 1, "steel3")
    c.dot(sx0 + 6, dy0 - 1, "steel3")
    # Окно с переплётом и ставней
    wx, wy = x + 27, gy - 13
    _halo(c, wx + 2, wy + 2, 6, LAMP_HALO[1:])
    c.rect(wx - 1, wy - 1, 7, 7, "k")
    c.rect(wx, wy, 5, 5, "lamp1")
    c.vline(wx + 2, wy, 5, "wood0")
    c.hline(wx, wy + 2, 5, "wood0")
    c.dot(wx, wy, "lamp2")
    c.dot(wx + 3, wy, "lamp2")
    c.hline(wx - 1, wy + 6, 7, "wood2")
    c.vline(wx + 6, wy - 1, 7, "wood0")
    _spill(c, dx0 + dw // 2, gy, dw - 2, 4)
    # Наковальня на колоде, молот, искры
    ax = x + 38
    c.rect(ax + 3, gy - 4, 6, 4, "wood1", "k")
    c.hline(ax + 4, gy - 4, 4, "wood2")
    c.vline(ax + 7, gy - 3, 2, "wood0")
    c.sprite(ax, gy - 11, _ANVIL, {"k": "k", "H": "steel3", "h": "steel2", "m": "steel1"})
    c.dot(ax + 4, gy - 10, "white")
    c.line(ax + 9, gy - 13, ax + 12, gy - 16, "wood2")  # молот в замахе
    c.rect(ax + 7, gy - 15, 3, 3, "steel2", "k")
    c.rect(ax + 4, gy - 11, 3, 1, "fire2")  # раскалённая заготовка
    c.dot(ax + 5, gy - 11, "fire3")
    _halo(c, ax + 5, gy - 12, 5, FIRE_HALO[1:])
    c.sparkle(ax + 3, gy - 14, "fire3", 1, "fire1")
    _sparks(c, ax + 5, gy - 13, 7, 5, 5)
    # Горн-жаровня на ножках с вытяжкой
    fx = ax + 13
    _halo(c, fx + 3, gy - 6, 9, FIRE_HALO)
    c.line(fx + 1, gy - 1, fx + 2, gy - 4, "steel1")
    c.line(fx + 6, gy - 1, fx + 5, gy - 4, "steel0")
    c.poly([(fx, gy - 7), (fx + 8, gy - 7), (fx + 6, gy - 4), (fx + 2, gy - 4)], "steel1")
    c.hline(fx, gy - 7, 8, "k")
    c.hline(fx + 1, gy - 8, 6, "fire1")
    c.hline(fx + 2, gy - 9, 4, "fire2")
    c.dot(fx + 3, gy - 9, "fire3")
    c.dot(fx + 4, gy - 10, "fire3")
    c.dot(fx + 2, gy - 10, "fire1")
    c.dot(fx + 5, gy - 11, "fire0")
    c.hline(fx + 1, gy - 6, 6, "steel2")
    c.line(fx + 2, gy - 18, fx + 6, gy - 18, "steel2")  # колпак вытяжки
    c.line(fx + 1, gy - 17, fx + 7, gy - 17, "steel1")
    c.hline(fx + 1, gy - 17, 1, "steel3")
    c.rect(fx + 3, gy - 24, 3, 6, "steel1", "k")
    smoke(c, fx + 4, gy - 25, 5, tone=1)


# --- Биржа и табло -------------------------------------------------------------------------------------


def market_hall(c: Canvas, x: int, gy: int, w: int = 54, h: int = 30) -> None:
    """Биржевой зал: ступени, колоннада с капителями, арочные окна с тёплым светом, вход под полосатым
    навесом с фонарями, антаблемент с латунной вывеской, фронтон с часами, медный купол в патине
    со световым фонарём и флагом."""
    top = gy - h
    cx = x + w // 2
    _ground_shadow(c, x - 3, gy, w + 6)
    # Купол позади фронтона
    dr = max(6, w // 8)
    dtop = top - dr - 3
    for dy in range(-dr, 1):
        for dx in range(-dr, dr + 1):
            if c.in_disk(dx, dy, dr):
                f = (dx + dr) / (2 * dr)
                k = 2 if f < 0.35 else (1 if f < 0.75 else 0)
                if dx % 3 == 0 and dy < -1:
                    k = max(0, k - 1)
                c.dot(cx + dx, top - 3 + dy, PATINA[k])
    for dy in range(-dr - 1, 1):
        for dx in range(-dr - 1, dr + 2):
            if not c.in_disk(dx, dy, dr) and any(c.in_disk(dx + a, dy + b, dr) for a, b in ((1, 0), (-1, 0), (0, 1))):
                c.dot(cx + dx, top - 3 + dy, "k")
    c.rect(cx - 2, dtop - 4, 5, 4, "steel1", "k")  # световой фонарь
    c.dot(cx - 1, dtop - 3, "lamp2")
    c.dot(cx + 1, dtop - 3, "lamp1")
    c.vline(cx, dtop - 9, 5, "steel2")
    c.rect(cx + 1, dtop - 9, 4, 2, "red1")
    c.dot(cx + 1, dtop - 9, "red2")
    # Стены и колоннада
    c.rect(x, top + 6, w, h - 9, "steel0")
    c.dither(x + 1, top + 6, w - 2, 2, None, "oil1", 0.5)
    ncol = max(3, (w - 4) // 8 + 1)
    cols = [x + 2 + round(i * (w - 7) / (ncol - 1)) for i in range(ncol)]
    for a, b in zip(cols, cols[1:], strict=False):  # арочные окна между колоннами
        mid = (a + b + 3) // 2
        if abs(mid - cx) <= 3:
            continue
        lit = c.rnd.random() < 0.8
        wx, wy, wwid, wht = mid - 2, top + 10, 4, h - 18
        if lit:
            _halo(c, mid, wy + wht // 2, 5, LAMP_HALO[1:])
        c.rect(wx - 1, wy - 1, wwid + 2, wht + 2, None, "k")
        c.rect(wx, wy, wwid, wht, "lamp1" if lit else "oil1")
        c.dot(wx, wy, "k")
        c.dot(wx + wwid - 1, wy, "k")
        c.hline(wx, wy + wht // 2, wwid, "k" if not lit else "lamp0")
        c.vline(wx + 1, wy + 1, wht - 1, "lamp0" if lit else "oil0")
        if lit:
            c.dot(wx + 2, wy + 1, "lamp2")
    for px in cols:  # колонны: база, ствол-цилиндр с каннелюрами, капитель
        _cyl(c, px, top + 9, 4, h - 13, "steel", outline=None, shift=0.3)
        for j in range(top + 10, gy - 4, 2):
            c.dot(px + 2, j, "steel1")
        c.rect(px - 1, top + 7, 6, 2, "steel3")
        c.hline(px - 1, top + 8, 6, "steel1")
        c.rect(px - 1, gy - 5, 6, 2, "steel2")
        c.hline(px - 1, gy - 4, 6, "steel0")
    # Вход: двери с тёплым светом, навес в полоску, фонари
    dw, dh = 8, 10
    dx0 = cx - dw // 2
    _halo(c, cx, gy - 7, 8, LAMP_HALO)
    c.rect(dx0 - 1, gy - dh - 4, dw + 2, dh + 1, "k")
    c.rect(dx0, gy - dh - 3, dw, dh, "lamp1")
    c.dither(dx0, gy - dh - 3, dw, 3, None, "lamp2", 0.5)
    c.vline(dx0, gy - dh - 3, dh, "wood1")
    c.vline(dx0 + dw - 1, gy - dh - 3, dh, "wood0")
    c.vline(cx, gy - dh + 1, 3, "wood0")  # силуэт посетителя
    c.dot(cx, gy - dh, "wood0")
    for i in range(dw + 6):  # навес
        xx = dx0 - 3 + i
        stripe = "red2" if (i // 2) % 2 == 0 else "paper1"
        c.dot(xx, gy - dh - 6, "k")
        c.dot(xx, gy - dh - 5, stripe)
        c.dot(xx, gy - dh - 4, stripe if stripe != "red2" else "red1")
        if i % 2 == 0:
            c.dot(xx, gy - dh - 3, "red1" if (i // 2) % 2 == 0 else "paper0")
    c.dot(dx0 - 4, gy - dh - 5, "k")
    c.dot(dx0 + dw + 3, gy - dh - 5, "k")
    for lx in (dx0 - 3, dx0 + dw + 2):
        c.vline(lx, gy - 8, 3, "oil2")
        _lamp(c, lx, gy - 9, 4)
    # Антаблемент с латунной вывеской
    c.rect(x - 1, top + 1, w + 2, 6, "steel2", "k")
    c.hline(x, top + 1, w, "steel3")
    for i in range(x, x + w, 2):
        c.dot(i, top + 5, "steel1")
    c.rect(cx - 9, top + 2, 19, 3, "brass1", "k")
    c.hline(cx - 8, top + 3, 17, "brass2")
    for i in range(cx - 7, cx + 8, 2):
        c.dot(i, top + 3, "brass0")
    c.dot(cx - 8, top + 3, "brass3")
    # Фронтон с часами
    ph = max(5, w // 9)
    pts = [(x - 1, top + 1), (cx, top + 1 - ph), (x + w, top + 1)]
    c.poly(pts, "k")
    c.poly([(x + 2, top + 1), (cx, top + 3 - ph), (x + w - 3, top + 1)], "steel1")
    c.line(x - 1, top, cx, top - ph, "steel3")
    c.line(cx + 1, top - ph + 1, x + w, top, "steel1")
    c.shaded_disk(cx, top - ph // 2 + 1, 2, "paper", outline="brass1", base=2)
    c.dot(cx, top - ph // 2, "k")
    c.dot(cx + 1, top - ph // 2 + 1, "k")
    c.dot(cx, top - ph - 1, "brass3")
    # Ступени
    for k in range(3):
        sy = gy - 3 + k
        c.hline(x - 1 - k, sy, w + 2 + 2 * k, CONCRETE[2] if k == 0 else CONCRETE[1])
        c.dot(x - 1 - k, sy, "k")
        c.dot(x + w + k, sy, "k")
        c.dot(x - k, sy, CONCRETE[2])
    c.hline(x - 3, gy - 1, w + 6, CONCRETE[0])
    _spill(c, cx, gy, dw, 3)


def _glyph(c: Canvas, x: int, y: int, code: int, col: str) -> None:
    """Псевдобуква 3×3 для тикеров табло (форма зависит от code)."""
    shapes = ("###.#.#.#", "###..#.##", "#.##.####", "###.##.#.", "##.#.###.", "#..###..#", "###.#..#.")
    s = shapes[code % len(shapes)]
    for i, ch in enumerate(s):
        if ch == "#":
            c.dot(x + i % 3, y + i // 3, col)


def board(c: Canvas, x: int, y: int, w: int = 45, h: int = 24, gy: int | None = None) -> None:
    """Табло котировок w×h (x, y — верхний левый угол): латунная рама с заклёпками и гирляндой ламп,
    тёмный экран со шкалой, строки «тикер — столбик цены — стрелка» зелёным и красным, стойки
    с раскосом (до земли gy, если задана) и два софита на кронштейнах."""
    _halo(c, x + w // 2, y - 1, w // 2 + 2, LAMP_HALO[:1], ry=3)
    c.box(x, y, w, h, "brass", base=1)
    c.rect(x + 1, y + 1, w - 2, 2, "brass1")
    for i in range(x + 2, x + w - 2, 3):  # гирлянда ламп по верхней раме
        c.dot(i, y + 1, "lamp2" if (i // 3) % 2 else "lamp1")
    c.hline(x + 1, y + 2, w - 2, "brass0")
    for px, py in ((x + 1, y + 3), (x + w - 2, y + 3), (x + 1, y + h - 2), (x + w - 2, y + h - 2)):
        c.dot(px, py, "brass3")
    c.rect(x + 2, y + 3, w - 4, h - 5, "oil0")
    for i in range(x + 3, x + w - 3, 6):  # сетка шкалы
        for j in range(y + 4, y + h - 2, 2):
            c.dot(i, j, "oil1")
    for j in range(y + 4, y + h - 5, 4):
        up = c.rnd.random() < 0.6
        code = c.rnd.randrange(100)
        for k in range(3):
            _glyph(c, x + 4 + k * 4, j, code + k * 3, "brass2")
        col = "green" if up else "red"
        bx = x + 17
        bars = c.rnd.randrange(6, max(7, w - 30))
        c.hline(bx, j, bars, f"{col}2")
        c.hline(bx, j + 1, bars, f"{col}1")
        c.dot(bx + bars - 1, j + 1, f"{col}0")
        c.dot(bx + bars + 1, j + 1, "brass1")
        c.dot(bx + bars + 3, j + 1, "brass1")
        ax = x + w - 7
        if up:
            c.sprite(ax, j - 1, [".g.", "ggg", ".G."], {"g": "green2", "G": "green1"})
        else:
            c.sprite(ax, j, ["R.R", "rrr", ".r."], {"r": "red2", "R": "red1"})
    c.hline(x + 2, y + h - 3, w - 4, "brass0")
    # Стойки и раскос
    leg = (gy - y - h) if gy is not None else 4
    for lx in (x + 6, x + w - 8):
        c.vline(lx, y + h, leg, "steel2")
        c.vline(lx + 1, y + h, leg, "steel0")
    if leg >= 6:
        c.line(x + 7, y + h + 1, x + w - 9, y + h + leg - 2, "steel1")
    # Софиты на кронштейнах
    for lx in (x + 8, x + w - 10):
        c.vline(lx, y - 3, 3, "steel1")
        c.hline(lx - 1, y - 4, 3, "steel2")
        c.dot(lx, y - 5, "lamp2")


def gear(c: Canvas, cx: int, cy: int, r: int = 3, ramp_name: str = "brass") -> None:
    """Шестерня с центром (cx, cy) и радиусом обода r: прямые зубья по кругу (у крупных их больше),
    объёмная заливка со светом сверху-слева и контуром; у r ≥ 4 — канавка у обода и ступица,
    у r ≥ 5 — облегчающие отверстия. Полный размер ≈ 2r+5 (2r+7 при r ≥ 5)."""
    t = ramp(ramp_name)
    n = 8 if r <= 3 else 2 * r + 2
    rt = r + (2 if r >= 5 else 1)
    hw = 0.62 if r <= 3 else 0.8
    shape: set[tuple[int, int]] = set()
    for dy in range(-rt - 1, rt + 2):
        for dx in range(-rt - 1, rt + 2):
            if c.in_disk(dx, dy, r):
                shape.add((dx, dy))
                continue
            for k in range(n):
                a = 2 * math.pi * k / n - math.pi / 2
                ux, uy = math.cos(a), math.sin(a)
                along, across = dx * ux + dy * uy, -dx * uy + dy * ux
                if r - 0.5 < along <= rt + 0.45 and abs(across) <= hw:
                    shape.add((dx, dy))
                    break
    for dx, dy in shape:
        for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            if (dx + a, dy + b) not in shape:
                c.dot(cx + dx + a, cy + dy + b, "k")
    for dx, dy in shape:
        if (dx + 1, dy) not in shape or (dx, dy + 1) not in shape:
            col = t[0]
        elif (dx - 1, dy) not in shape or (dx, dy - 1) not in shape:
            col = t[-1]
        else:
            col = t[2] if dx + dy < 0 else t[1]
        c.dot(cx + dx, cy + dy, col)
    if r >= 4:  # канавка у обода и ступица
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                if c.in_disk(dx, dy, r - 1) and not c.in_disk(dx, dy, r - 2):
                    c.dot(cx + dx, cy + dy, t[0] if dx + dy >= 0 else t[1])
        hr = max(1, r // 3)
        for dy in range(-hr, hr + 1):
            for dx in range(-hr, hr + 1):
                if c.in_disk(dx, dy, hr):
                    c.dot(cx + dx, cy + dy, t[-1] if dx + dy < 0 else t[2])
    if r >= 5:  # облегчающие отверстия
        d = (r + hr) // 2 + 1
        for hx, hy in ((d, 0), (-d, 0), (0, d), (0, -d)):
            c.dot(cx + hx, cy + hy, "k")
            c.dot(cx + hx - (hy != 0), cy + hy - (hx != 0), t[0])
    if r == 3:
        c.dot(cx - 1, cy - 1, t[-1])
    c.dot(cx, cy, "k")


# --- Забой ---------------------------------------------------------------------------------------------


def rock(c: Canvas, x: int, gy: int, res: str, track: int = 66) -> None:
    """Забой: гранёный скальный холм 38×20 (грани освещены слева, справа в тени, трещины между гранями),
    жилы руды с самородками или пласты угля с блеском, штольня с деревянной крепью и фонарём, рельсы
    узкоколейки из штольни вправо на track px (0 — без рельсов), куча добытого у подножия с лопатой."""
    hill = [(x, gy), (x + 1, gy - 4), (x + 3, gy - 7), (x + 4, gy - 10), (x + 7, gy - 12), (x + 9, gy - 15),
            (x + 12, gy - 16), (x + 14, gy - 19), (x + 18, gy - 20), (x + 21, gy - 18), (x + 24, gy - 18),
            (x + 27, gy - 14), (x + 30, gy - 12), (x + 32, gy - 9), (x + 35, gy - 6), (x + 37, gy - 2), (x + 38, gy)]
    lay = c.layer(40, 22)
    lay.poly([(px - x + 1, py - gy + 21) for px, py in hill], ROCK[1])
    # Грани: ближайшая «затравка» → грань; тон грани зависит от её положения (свет слева)
    seeds = [(5, 15), (11, 9), (17, 4), (24, 6), (30, 12), (35, 18), (14, 17), (23, 15), (9, 19), (28, 20)]
    tone_of = []
    for sx, _sy in seeds:
        v = 3.3 - sx / 10 + (c.rnd.random() - 0.5) * 0.8
        tone_of.append(max(0, min(3, round(v))))
    owner = {}
    for yy in range(22):
        for xx in range(40):
            if lay.get(xx, yy) is None:
                continue
            k = min(range(len(seeds)), key=lambda i: (xx - seeds[i][0]) ** 2 + (yy - seeds[i][1]) ** 2 * 1.4)
            owner[(xx, yy)] = k
    for (xx, yy), k in owner.items():
        tn = tone_of[k]
        right, below = owner.get((xx + 1, yy)), owner.get((xx, yy + 1))
        left, above = owner.get((xx - 1, yy)), owner.get((xx, yy - 1))
        if (right is not None and right != k) or (below is not None and below != k):
            col = ROCK[0]
        elif (left is not None and left != k) or (above is not None and above != k):
            col = ROCK[min(3, tn + 1)]
        else:
            col = ROCK[tn]
            if tn > 0 and lay.threshold(xx, yy, "bayer4") < 0.12:
                col = ROCK[tn - 1]
        lay.dot(xx, yy, col)
    # Освещённая кромка сверху-слева, тень справа
    for xx in range(40):
        col_top = next((yy for yy in range(22) if lay.get(xx, yy) is not None), None)
        if col_top is None:
            continue
        lay.dot(xx, col_top, ROCK_HI if xx < 18 else ROCK[2])
        if xx < 14:
            lay.dot(xx, col_top + 1, ROCK[3])
        if xx > 25:
            for yy in range(col_top + 1, 22):
                if lay.get(xx, yy) is not None and lay.threshold(xx, yy, "bayer4") < (xx - 25) / 16:
                    lay.dot(xx, yy, ROCK[0])
    # Жилы / пласты
    if res == "coal":
        for base, th in ((15, 2), (19, 3)):
            for xx in range(40):
                yy0 = base + round(xx * 0.12 + math.sin(xx * 0.5) * 0.6) - 6
                for j in range(th):
                    yy = yy0 + j
                    if lay.get(xx, yy) is not None:
                        lay.dot(xx, yy, "coal1" if j == 0 else "coal0")
                if lay.get(xx, yy0) is not None and (xx * 5) % 7 == 0:
                    lay.dot(xx, yy0, "coal2")
    else:
        main = ("ore0", "ore1", "ore2") if res == "ore" else ("steel0", "steel1", "steel2")
        for sx, sy, ex, ey in ((3, 18, 16, 8), (12, 20, 30, 10), (22, 21, 35, 16)):
            steps = max(abs(ex - sx), abs(ey - sy))
            for s in range(steps + 1):
                xx = round(sx + (ex - sx) * s / steps)
                yy = round(sy + (ey - sy) * s / steps + math.sin(s * 0.9) * 0.8)
                if lay.get(xx, yy) is not None:
                    lay.dot(xx, yy, main[1])
                    if s % 4 == 1 and lay.get(xx + 1, yy) is not None:
                        lay.dot(xx + 1, yy, main[2])
                        lay.dot(xx, yy + 1, main[0])
                    if s % 6 == 3:
                        lay.dot(xx, yy - 1, "brass3" if res == "ore" else main[2])
    lay_outline = "k"
    c.paste(lay, x - 1, gy - 21, outline=lay_outline)
    c.sparkle(x + 9, gy - 13, "white" if res != "coal" else "steel3", 1, "brass2" if res == "ore" else "steel1")
    # Штольня: тёмный проём с уходящей вглубь крепью, рельсы, фонарь
    ax = x + 12
    c.rect(ax, gy - 12, 11, 12, "k")
    c.rect(ax + 3, gy - 9, 5, 8, "wood0")
    c.rect(ax + 4, gy - 8, 3, 7, "k")
    c.hline(ax + 3, gy - 9, 5, "wood1")
    _halo(c, ax + 5, gy - 2, 5, ["oil2", "haze0"])
    c.rect(ax, gy - 13, 11, 2, "wood2", "k")
    c.hline(ax - 1, gy - 13, 13, "k")
    c.hline(ax, gy - 12, 11, "wood1")
    c.hline(ax + 1, gy - 13, 5, "wood2")
    c.rect(ax, gy - 11, 2, 11, "wood1")
    c.vline(ax, gy - 11, 11, "wood2")
    c.rect(ax + 9, gy - 11, 2, 11, "wood0")
    c.vline(ax + 9, gy - 11, 11, "wood1")
    for j in (gy - 8, gy - 4):
        c.dot(ax + 1, j, "wood0")
        c.dot(ax + 10, j, "k")
    _halo(c, ax + 5, gy - 8, 5, LAMP_HALO)
    c.vline(ax + 5, gy - 11, 1, "k")
    c.dot(ax + 5, gy - 10, "lamp1")
    c.dot(ax + 5, gy - 9, "lamp2")
    if track:
        for xx in range(ax + 2, x + track, 4):
            c.hline(xx, gy + 1, 2, "wood0")
            c.dot(xx, gy + 1, "wood1")
        c.hline(ax + 2, gy, x + track - ax - 2, "steel2")
        c.hline(ax + 2, gy + 1, x + track - ax - 2, "steel0")
        c.hline(ax + 3, gy - 1, 6, "steel1")
    # Куча добытого и лопата
    _heap(c, x + 31, gy, 16, 6, res)
    c.line(x + 42, gy - 5, x + 45, gy - 12, "wood2")
    c.rect(x + 44, gy - 15, 3, 2, "wood1")
    c.poly([(x + 40, gy - 6), (x + 43, gy - 6), (x + 42, gy - 3)], "steel2")
    c.dot(x + 40, gy - 6, "steel3")
