"""Фон сцен: небо, смог, луна/солнце, два слоя горизонта по локациям, земля, дорога, рельсы, фонари, дым.

Слои рисуются от дальнего к ближнему:
    небо (4–6 дизер-полос от фиолетовой ночи к тёплому зареву) → звёзды → светило с ореолом →
    высокие полосы смога → кучевой смог → дальний горизонт (светлый силуэт, дымы стелются по ветру) →
    низкая пелена смога у земли → ближний горизонт (тёмный, контровой свет по кромкам, огни, факелы,
    дым) → земля (галька, грязь, лужи с отражением зарева).

Ближний план рисуется на прозрачный слой: так кромки силуэта получают контровой свет зарева, а ореолы
огней и дым кладутся потом поверх уже на холст (ореол только осветляет пиксели).
Локальные тона (RGB-кортежи) объявлены ниже — общей палитры canvas.py они не меняют.
"""

import math

from ironvein.art.canvas import Canvas, W, lum, ramp

GY = 56  # линия горизонта / земли по умолчанию

FAR, NEAR, SHADE = "sil2", "sil1", "sil0"  # дальний план, ближний план, теневая сторона ближнего

# Локальные тона фона (между тонами общих рамп).
FAR_D = (30, 27, 41)  # детали дальнего силуэта: швы, теневые грани
RIM = (44, 35, 50)  # контровой свет зарева на верхних кромках ближнего плана
RIM_HOT = (78, 48, 50)  # контровой свет у нефтяных факелов
MOON = ((96, 90, 100), (142, 132, 122), (186, 174, 150), (224, 214, 188))  # моря → блик
SHEEN = ((52, 62, 84), (84, 66, 70))  # радужная плёнка на мазутном пятне
COBBLE = (58, 54, 64)  # блик на булыжнике
STEAM = (122, 114, 134)  # светлый пар: тон над smog3 для дыма tone=3

# Полосы неба сверху вниз по локациям и строки (доли высоты до горизонта), с которых они начинаются.
_DUSK = {
    None: ["sky0", "sky1", "sky2", "sky3", "haze0", "haze1"],
    "rust": ["sky0", "sky1", "sky2", "haze0", "haze1", "haze2"],
    "mazut": ["sky0", "sky1", (42, 30, 44), (66, 40, 50), (96, 52, 52), (132, 70, 54)],
    "kotlo": ["sky0", "sky1", "sky2", "sky3", "smog1", "haze0"],
}
_STOPS = (0.0, 0.17, 0.37, 0.57, 0.75, 0.89)


# --- Мелкие помощники ----------------------------------------------------------------------------------


def _lighten(c: Canvas, x: int, y: int, col) -> None:
    """Точка, только если она светлее того, что уже нарисовано (свет не затемняет)."""
    old = c.get(x, y)
    if old is not None and lum(old) < lum(c.rgb(col)):
        c.dot(x, y, col)


def _veil(c: Canvas, x: int, y: int, w: int, h: int, col, level: float, pattern: str = "bayer4") -> None:
    """Полупрозрачная дымка: доля level пикселей светлеет до col (тёмное осветляется, светлое не трогается)."""
    for yy in range(y, y + h):
        for xx in range(x, x + w):
            if c.threshold(xx, yy, pattern) < level:
                _lighten(c, xx, yy, col)


def _bands(c: Canvas, x: int, y: int, w: int, h: int, colors: list, stops: tuple, blend: int = 4) -> None:
    """Сплошные полосы colors с началами stops (доли h) и дизерными стыками высотой blend строк (Байер 4×4)."""
    starts = [round(s * h) for s in stops[:len(colors)]]
    for j in range(h):
        k = max(i for i, s in enumerate(starts) if j >= s)
        ca = colors[k]
        level = 0.0
        if k + 1 < len(colors):
            seam = starts[k + 1] - blend
            if j >= seam:
                level = (j - seam + 1) / (blend + 1)
        if level <= 0:
            c.hline(x, y + j, w, ca)
            continue
        cb = colors[k + 1]
        for xx in range(x, x + w):
            c.dot(xx, y + j, cb if c.threshold(xx, y + j, "bayer4") < level else ca)


# --- Небо ----------------------------------------------------------------------------------------------


def sky(c: Canvas, gy: int = GY, smoggy: bool = True, moon: bool = True) -> None:
    """Сумеречное небо: дизер-полосы от ночной синевы к зареву у горизонта (тон по локации), редкие звёзды,
    светило с ореолом, высокие перистые полосы и кучевой смог двумя ярусами."""
    _bands(c, 0, 0, W, gy, _DUSK.get(c.theme, _DUSK[None]), _STOPS)
    _stars(c, gy, 5 if c.theme in ("rust", "mazut") else 11)
    disk = celestial(c) if moon else None
    if not smoggy:
        streak(c, c.rnd.randrange(0, W // 2), int(gy * 0.62), c.rnd.randrange(30, 50), "haze0")
        return
    for i in range(3):  # высокий ярус: тонкие полосы
        streak(c, i * 44 + c.rnd.randrange(-12, 16), c.rnd.randrange(3, int(gy * 0.24)),
               c.rnd.randrange(18, 36), "sky3" if i % 2 else "smog0")
    slots = list(range(4))
    c.rnd.shuffle(slots)
    for k, i in enumerate(slots):  # средний ярус: гряды смога, ниже — подсвеченные заревом снизу
        w = c.rnd.randrange(16, 30)
        x = i * (W // 4) + c.rnd.randrange(-8, 10)
        y = int(gy * (0.24 + 0.09 * k)) + c.rnd.randrange(0, 4)
        if disk and abs(x + w // 2 - disk[0]) < w // 2 + disk[2] + 2 and abs(y - disk[1]) < disk[2] + 5:
            continue  # не закрывать светило: перед ним уже есть своя тучка
        cloud(c, x, y, w, tone=1 if k < 3 else 0, under="haze0" if y > gy * 0.42 else None)


def _stars(c: Canvas, gy: int, n: int) -> None:
    """Редкие тусклые звёзды в верхней полосе; одна-две мерцают крестиком."""
    top = max(4, int(gy * 0.3))
    for i in range(n):
        x, y = c.rnd.randrange(2, W - 2), c.rnd.randrange(1, top)
        if i < 2 and c.rnd.random() < 0.7:
            c.sparkle(x, y, "smog2", 1, "sky2")
        else:
            c.dot(x, y, "sky3" if c.rnd.random() < 0.6 else "smog1")


def celestial(c: Canvas, x: int | None = None, y: int | None = None, r: int = 5) -> tuple[int, int, int]:
    """Светило за смогом: бледная луна с морями (столица и по умолчанию), низкое рыжее солнце над шахтами,
    багровое — над нефтепромыслом. Солнце перечёркнуто полосами смога, по нижнему краю ползёт тучка.
    Возвращает (x, y, r) — чтобы облака не закрыли диск."""
    theme = c.theme
    lo_x = W // 2 + 14 if theme == "kotlo" else W // 2  # над столицей — правее часовой башни
    x = c.rnd.randrange(lo_x, W - 11) if x is None else x
    y = c.rnd.randrange(10, 16) if y is None else y
    if theme in ("rust", "mazut"):
        r += 1
        if theme == "rust":
            tones, halo = ("ore0", "ore1", "ore2", (214, 152, 104)), ["haze0", "haze1"]
        else:
            tones, halo = ("red0", "fire0", "red2", "fire1"), ["haze0", "haze1", (124, 62, 56)]
        c.glow(x, y, r + 13, halo, soft=0.6)
        _disk_shaded(c, x, y, r, tones)
        for k, dy in enumerate((r // 2, r // 2 + 2, r - 1)):  # полосы смога поперёк диска
            ww = 2 * r + 5 - 2 * k
            c.hline(x - ww // 2, y + dy, ww, halo[1] if k < 2 else halo[0])
    else:
        c.glow(x, y, r + 12, ["sky2", "sky3", "smog1"], soft=0.6)
        c.glow(x, y, r + 4, ["smog1", "smog2"], soft=0.5)
        _disk_shaded(c, x, y, r, MOON)
        for mx, my, mr in ((-2, -1, 1), (1, 1, 1), (2, -2, 0), (-1, 3, 0)):  # лунные моря
            if mr:
                c.dot(x + mx + 1, y + my, MOON[1])
                c.dot(x + mx, y + my + 1, MOON[1])
            c.dot(x + mx, y + my, MOON[1])
        streak(c, x - r - 4, y + 1, 2 * r + 9, "smog2")  # тонкая прядь смога через диск
    cloud(c, x - r - 4 - c.rnd.randrange(4), y + r, 2 * r + 9, tone=1)
    return x, y, r


def _disk_shaded(c: Canvas, cx: int, cy: int, r: int, tones) -> None:
    """Диск в 4 тона: блик серпом сверху-слева (с дизер-переходом), тень снизу-справа."""
    t0, t1, t2, t3 = (c.rgb(t) for t in tones)
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if not c.in_disk(dx, dy, r):
                continue
            x, y = cx + dx, cy + dy
            if not c.in_disk(dx + 1, dy + 1, r):
                col = t1
            elif not c.in_disk(dx - 1, dy - 1, r):
                col = t3
            elif not c.in_disk(dx - 2, dy - 2, r):
                col = t3 if c.threshold(x, y, "checker") < 0.5 else t2
            elif not c.in_disk(dx + 2, dy + 2, r):
                col = t1 if c.threshold(x, y, "checker") < 0.5 else t2
            else:
                col = t2
            c.dot(x, y, col)
    del t0


def streak(c: Canvas, x: int, y: int, w: int, col="smog1") -> None:
    """Тонкая полоса смога: сплошная середина, дизерные «рваные» концы, короткая прядь строкой ниже."""
    c.hline(x + 3, y, w - 6, col)
    for i in (0, 1, 2):
        for xx in (x + i, x + w - 1 - i):
            if c.threshold(xx, y, "bayer4") < 0.25 + 0.25 * i:
                c.dot(xx, y, col)
    sub = w // 3
    sx = x + w // 3 + (w // 6 if (x + y) % 2 else -w // 6)
    c.hline(sx + 1, y + 1, sub - 2, col)
    c.dot(sx, y + 1, col) if c.threshold(sx, y + 1, "checker") < 0.5 else None


def cloud(c: Canvas, x: int, y: int, w: int, tone: int = 1, ramp_name: str = "smog", under=None) -> None:
    """Гряда смога шириной w: бугры над плоским брюхом. (x, y) — левый верх тела, бугры выше на 1–3 px.
    Свет сверху-слева: светлая макушка и левые склоны, тёмное брюхо с дизерным рваным низом.
    under — цвет подсветки брюха снизу (зарево у горизонта), иначе тень рампы."""
    tones = ramp(ramp_name)
    n = len(tones)
    hi, mid, lo = tones[min(tone + 1, n - 1)], tones[tone], tones[max(tone - 1, 0)]
    h = max(2, min(4, w // 8))  # высота тела под буграми
    base = y + h  # первая строка под облаком
    heights = []
    bumps = [(x + 2 + c.rnd.randrange(max(1, w - 4)), c.rnd.randrange(2, 4 + w // 12)) for _ in range(max(1, w // 9))]
    for i in range(w):
        px = x + i
        hh = h - (1 if i in (0, w - 1) else 0) - (1 if i in (1, w - 2) and h > 2 else 0)
        for bx, br in bumps:
            d = abs(px - bx)
            if d <= br:
                hh = max(hh, h - 1 + int(math.sqrt(br * br - d * d) * 0.8))
        heights.append(max(1, hh))
    for i, hh in enumerate(heights):
        px = x + i
        left = heights[i - 1] if i else 0
        for k in range(hh):
            py = base - 1 - k
            if k == hh - 1 or (k >= left and k > 0):
                col = hi  # макушка и левые склоны бугров
            elif k == 0:
                col = under or lo
            elif k == 1 and c.threshold(px, py, "checker") < 0.5:
                col = lo
            else:
                col = mid
            c.dot(px, py, col)
        if 1 < i < w - 2 and c.threshold(px, base, "bayer4") < 0.3:  # рваный низ
            c.dot(px, base, under or lo)


# --- Горизонт: общее -----------------------------------------------------------------------------------


def skyline(c: Canvas, gy: int = GY) -> None:
    """Оба слоя горизонта по локации сцены (Canvas.theme): дальний, пелена смога, ближний."""
    skyline_far(c, gy)
    skyline_near(c, gy)


def skyline_far(c: Canvas, gy: int = GY) -> None:
    """Дальний план: светлый силуэт (FAR) почти без деталей, дымы стелются по ветру, у земли его съедает
    тёплая пелена смога (воздушная перспектива)."""
    {"rust": _far_rust, "mazut": _far_mazut, "kotlo": _far_kotlo}.get(c.theme or "", _far_default)(c, gy)
    haze = "haze1" if c.theme in ("rust", "mazut") else "haze0"
    for k in range(6):  # пелена густеет к земле
        _veil(c, 0, gy - 6 + k, W, 1, haze, 0.12 + 0.09 * k)
    for _ in range(2):  # низкие пряди смога поперёк дальнего плана
        streak(c, c.rnd.randrange(-10, W - 20), gy - c.rnd.randrange(9, 16), c.rnd.randrange(24, 44), "haze0")


def skyline_near(c: Canvas, gy: int = GY) -> None:
    """Ближний план: тёмный силуэт (NEAR) с теневыми гранями и контровым светом по кромкам, огни окон,
    трубы, факелы и дым — по локации."""
    layer = c.layer(c.w, c.h)
    fx: list = []  # свет и дым: кладутся на холст после силуэта
    {"rust": _near_rust, "mazut": _near_mazut, "kotlo": _near_kotlo}.get(c.theme or "", _near_default)(layer, gy, fx)
    _rim(layer, RIM_HOT if c.theme == "mazut" else RIM)
    c.paste(layer, 0, 0)
    for f in fx:
        f(c)


def _rim(layer: Canvas, col) -> None:
    """Контровой свет: верхний пиксель силуэта NEAR под открытым небом светлеет до col."""
    src, rc = layer.rgb(NEAR), (*layer.rgb(col), 255)
    px = layer.px
    for y in range(1, layer.h):
        for x in range(layer.w):
            v = px[x, y]
            if v[3] and v[:3] == src and not px[x, y - 1][3]:
                px[x, y] = rc


def _plume(c: Canvas, x: int, y: int, length: int, col="smog1", drift: int = 1) -> None:
    """Дальний дым из трубы: поднимается на пару пикселей и стелется по ветру, расширяясь и тая дизером."""
    for i in range(length):
        t = i / length
        cx = x + i * drift
        cy = y - min(i, 3) - int(t * 4)
        thick = 1 + int(t * 3)
        level = 1.0 - 0.8 * t
        for k in range(thick):
            yy = cy - k + (1 if (i // 3) % 2 and k == thick - 1 else 0)
            if c.threshold(cx, yy, "bayer4") < level:
                c.dot(cx, yy, col)


def _lattice(c: Canvas, x: int, gy: int, h: int, col, width: int, slope: int, rung: int) -> None:
    """Решётчатая башня: две сходящиеся ноги, перекладины через rung строк и зигзаг раскосов
    (копёр шахты, буровая вышка, опоры водонапорной башни)."""
    def legs(i: int) -> tuple[int, int]:
        step = i // slope
        return x + step, x + width - 1 - step

    for i in range(h):
        a, b = legs(i)
        c.dot(a, gy - 1 - i, col)
        c.dot(b, gy - 1 - i, col)
    for k, i in enumerate(range(0, h, rung)):
        a, b = legs(i)
        c.hline(a, gy - 1 - i, b - a + 1, col)
        j = min(i + rung, h - 1)
        a2, b2 = legs(j)
        if b - a > 2:
            if k % 2:
                c.line(a, gy - 1 - i, b2, gy - 1 - j, col)
            else:
                c.line(b, gy - 1 - i, a2, gy - 1 - j, col)


def _wheel(c: Canvas, cx: int, cy: int, r: int, col, hub=None) -> None:
    """Шкив со спицами (копёр): обод, спицы крестом (и по диагоналям у крупных), ступица."""
    c.ring(cx, cy, r, col)
    for k in range(1, r):
        for dx, dy in ((k, 0), (-k, 0), (0, k), (0, -k)):
            c.dot(cx + dx, cy + dy, col)
    if r >= 4:
        for k in range(1, r - 1):
            for dx, dy in ((k, k), (-k, k), (k, -k), (-k, -k)):
                c.dot(cx + dx, cy + dy, col)
    c.dot(cx, cy, hub or col)


def _dim_windows(c: Canvas, x: int, top: int, bw: int, bh: int, lit: float) -> None:
    """Редкие тусклые огни дальнего плана."""
    for j in range(top + 2, top + bh - 2, 3):
        for i in range(x + 1, x + bw - 1, 2):
            if c.rnd.random() < lit:
                c.dot(i, j, "haze1" if c.rnd.random() < 0.7 else "haze2")


# --- Дальний план по локациям --------------------------------------------------------------------------


def _far_default(c: Canvas, gy: int) -> None:
    """Промышленный город: корпуса с плоскими и пилообразными крышами, газгольдер, градирня, дымы по ветру."""
    x = -c.rnd.randrange(0, 4)
    special = c.rnd.randrange(20, W - 30)
    while x < W:
        if special <= x < special + 14:
            if c.rnd.random() < 0.5:  # газгольдер: цилиндр в решётке колонн
                c.rect(x + 1, gy - 10, 12, 10, FAR)
                c.hline(x + 2, gy - 11, 10, FAR)
                for i in range(0, 14, 4):
                    c.vline(x + i, gy - 13, 13, FAR)
                c.hline(x, gy - 13, 14, FAR)
                for j in (gy - 7, gy - 4):
                    c.hline(x + 1, j, 12, FAR_D)
            else:  # градирня: вогнутый силуэт
                for j in range(14):
                    half = 5 - (j * (13 - j)) // 22
                    c.hline(x + 7 - half, gy - 1 - j, 2 * half, FAR)
                _plume(c, x + 7, gy - 16, 14, "smog1")
            x += 16
            special = 10 ** 6
            continue
        bw, bh = c.rnd.randrange(6, 14), c.rnd.randrange(10, 22)
        c.rect(x, gy - bh, bw, bh, FAR)
        if c.rnd.random() < 0.3:
            for i in range(0, bw - 2, 3):
                c.poly([(x + i, gy - bh), (x + i + 3, gy - bh - 2), (x + i + 3, gy - bh)], FAR)
        if c.rnd.random() < 0.35:
            cx = x + c.rnd.randrange(1, max(2, bw - 2))
            ch = c.rnd.randrange(6, 12)
            c.rect(cx, gy - bh - ch, 2, ch, FAR)
            c.hline(cx - 1, gy - bh - ch, 4, FAR)
            _plume(c, cx + 1, gy - bh - ch - 1, c.rnd.randrange(10, 20), "smog1")
        _dim_windows(c, x, gy - bh, bw, bh, 0.05)
        x += bw + c.rnd.randrange(0, 3)


def _far_rust(c: Canvas, gy: int) -> None:
    """Шахтёрский край: крупные конусы отвалов с теневым склоном, далёкие копры со шкивами, кирпичные трубы."""
    x = -c.rnd.randrange(0, 6)
    while x < W:
        r = c.rnd.random()
        if r < 0.25:
            h = c.rnd.randrange(13, 19)
            _lattice(c, x, gy, h, FAR, width=7, slope=5, rung=4)
            c.ring(x + 3, gy - h - 2, 1, FAR)
            c.line(x + 5, gy - h - 1, x + 10, gy - 4, FAR)
            x += 10
        elif r < 0.4:
            ch = c.rnd.randrange(16, 24)
            c.rect(x + 1, gy - ch, 2, ch, FAR)
            c.hline(x, gy - ch, 4, FAR)
            c.dot(x + 1, gy - ch + 3, FAR_D)
            c.dot(x + 2, gy - ch + 3, FAR_D)
            _plume(c, x + 2, gy - ch - 1, c.rnd.randrange(14, 24), "smog1")
            x += 5
        else:
            hw = c.rnd.randrange(9, 18)
            hh = hw * 2 // 3 + c.rnd.randrange(0, 4)
            c.poly([(x, gy), (x + hw - 1, gy - hh), (x + hw + 1, gy - hh), (x + 2 * hw, gy)], FAR)
            c.poly([(x + hw + 1, gy - hh), (x + 2 * hw, gy), (x + hw + 3, gy)], FAR_D)
            x += hw + c.rnd.randrange(3, 10)


def _far_mazut(c: Canvas, gy: int) -> None:
    """Нефтепромысел: плоская степь, частокол тонких вышек с огоньками, низкие резервуары, факельная труба."""
    x = -c.rnd.randrange(0, 4)
    stack = c.rnd.randrange(10, W - 20)
    while x < W:
        if stack <= x:
            c.rect(x, gy - 22, 2, 22, FAR)  # факельная труба с крупным пламенем
            c.glow(x + 1, gy - 25, 7, ["haze1", (124, 62, 56)], soft=0.6)
            c.sprite(x - 1, gy - 28, [".1.", "121", "232", ".1."], {"1": "fire0", "2": "fire1", "3": "fire2"})
            _plume(c, x + 1, gy - 29, 18, "smog0")
            x += 5
            stack = 10 ** 6
            continue
        if c.rnd.random() < 0.5:
            h = c.rnd.randrange(9, 16)
            _lattice(c, x, gy, h, FAR, width=5, slope=6, rung=3)
            c.dot(x + 2, gy - h - 1, "fire1")
            c.dot(x + 2, gy - h - 2, "fire0" if c.rnd.random() < 0.5 else "haze2")
            x += 6 + c.rnd.randrange(0, 4)
        else:
            w, h = c.rnd.randrange(6, 12), c.rnd.randrange(3, 6)
            c.rect(x, gy - h, w, h, FAR)
            c.hline(x + 1, gy - h - 1, w - 2, FAR)
            c.vline(x + w - 1, gy - h, h, FAR_D)
            x += w + c.rnd.randrange(2, 8)


def _far_kotlo(c: Canvas, gy: int) -> None:
    """Столица: плотная стена высоток, шпили, купола, ступенчатая высотка со шпилем; в небе — дирижабль."""
    _airship(c, c.rnd.randrange(28, 40), c.rnd.randrange(9, 13))
    x = -c.rnd.randrange(0, 4)
    big = c.rnd.randrange(2, 22)  # левее часовой башни; луна — справа
    while x < W:
        if big <= x:
            _stepped_tower(c, x, gy)
            x += 15
            big = 10 ** 6
            continue
        bw, bh = c.rnd.randrange(6, 12), c.rnd.randrange(14, 28)
        c.rect(x, gy - bh, bw, bh, FAR)
        r = c.rnd.random()
        if r < 0.22:
            c.vline(x + bw // 2, gy - bh - 6, 6, FAR)
            c.hline(x + bw // 2 - 1, gy - bh - 2, 3, FAR)
        elif r < 0.38:
            c.disk(x + bw // 2, gy - bh, bw // 2 - 1, FAR)
            c.vline(x + bw // 2, gy - bh - bw // 2 - 2, 2, FAR)
        elif r < 0.55:
            c.poly([(x, gy - bh), (x + bw // 2, gy - bh - 4), (x + bw, gy - bh)], FAR)
        c.vline(x + bw - 1, gy - bh + 1, bh - 1, FAR_D)
        _dim_windows(c, x, gy - bh, bw, bh, 0.09)
        x += bw + c.rnd.randrange(0, 2)


def _stepped_tower(c: Canvas, x: int, gy: int) -> None:
    """Ступенчатая высотка столицы (13 px шириной, ~33 высотой): три яруса, шпиль со звездой-огнём."""
    top = gy
    for w, h in ((13, 17), (9, 7), (5, 4)):
        top -= h
        lx = x + (13 - w) // 2
        c.rect(lx, top, w, h, FAR)
        c.vline(lx + w - 1, top + 1, h - 1, FAR_D)
        c.hline(lx - 1, top, w + 2, FAR)  # карниз яруса
    c.vline(x + 6, top - 5, 5, FAR)
    c.dot(x + 6, top - 6, "red1")
    _dim_windows(c, x, gy - 17, 13, 17, 0.14)


def _airship(c: Canvas, x: int, y: int) -> None:
    """Дирижабль (≈30×10): сигара, освещённая луной сверху, тёмное брюхо, рёбра обшивки, оперение,
    гондола с тёплыми окнами и красный ходовой огонь на киле."""
    a, b = 11, 3
    c.poly([(x + a - 3, y - 1), (x + a + 3, y - b - 3), (x + a + 4, y - b - 3), (x + a + 4, y)], "smog0")  # киль
    c.poly([(x + a - 3, y + 1), (x + a + 3, y + b + 2), (x + a + 4, y + b + 2), (x + a + 4, y + 1)], "sil2")
    for dy in range(-b, b + 1):
        for dx in range(-a, a + 1):
            if (dx / (a + 0.5)) ** 2 + (dy / (b + 0.6)) ** 2 > 1:
                continue
            col = ("smog2", "smog1", "smog1", "smog0", "smog0", "sil2", "sil1")[dy + b]
            if dx % 4 == 1 and -b < dy < b:  # рёбра обшивки
                col = {"smog1": "smog0", "smog0": "sil2", "sil2": "sil1"}.get(col, col)
            c.dot(x + dx, y + dy, col)
    c.dot(x - a, y, "smog1")
    c.rect(x - 4, y + b + 1, 7, 2, "sil1")  # гондола
    c.dot(x - 3, y + b + 1, "lamp1")
    c.dot(x - 1, y + b + 1, "lamp2")
    c.dot(x + 1, y + b + 1, "lamp1")
    c.dot(x + a + 4, y - b - 3, "red2")


# --- Ближний план по локациям (рисуется на прозрачный слой L, свет и дым — в fx) ----------------------


def _block(L: Canvas, x: int, gy: int, bw: int, bh: int, lit: float = 0.22) -> None:
    """Корпус ближнего плана: силуэт, теневая правая грань, карниз, горящие окна 1×1 (тёплые и тусклые)."""
    L.rect(x, gy - bh, bw, bh, NEAR)
    L.vline(x + bw - 1, gy - bh + 1, bh - 1, SHADE)
    for j in range(gy - bh + 2, gy - 2, 3):
        for i in range(x + 1, x + bw - 2, 2):
            if L.rnd.random() < lit:
                L.dot(i, j, "lamp1" if L.rnd.random() < 0.65 else "lamp0")


def _chimney(L: Canvas, x: int, top: int, gy: int, fx: list, bands: bool = True, smoke_n: int = 5) -> None:
    """Кирпичная труба 3 px: оголовок, красные полосы, теневая грань, сигнальный огонь и дым."""
    L.rect(x, top, 3, gy - top, NEAR)
    L.vline(x + 2, top + 1, gy - top - 1, SHADE)
    L.hline(x - 1, top, 5, NEAR)
    for j in range(top + 4, gy, 3):  # кирпичные швы
        L.dot(x + (j // 3) % 2, j, SHADE)
    if bands:
        for j in (top + 2, top + 5):
            L.hline(x, j, 3, "red0")
            L.dot(x, j, "red1")
    fx.append(lambda c: c.dot(x + 1, top + 1, "red2"))
    fx.append(lambda c: smoke(c, x + 1, top - 1, smoke_n, tone=1))


def _street_lamp(L: Canvas, x: int, gy: int, fx: list, h: int = 8) -> None:
    """Маленький фонарь ближнего плана у подножия домов: столб, кронштейн, огонь с ореолом."""
    L.vline(x, gy - h, h, NEAR)
    L.dot(x + 1, gy - h, NEAR)
    fx.append(lambda c: c.glow(x + 2, gy - h + 1, 4, ["haze0", "haze1"], soft=0.6))
    fx.append(lambda c: c.dot(x + 2, gy - h + 1, "lamp2"))
    fx.append(lambda c: c.dot(x + 2, gy - h, "oil2"))


def _near_default(L: Canvas, gy: int, fx: list) -> None:
    """Промзона: цеха с пилообразными крышами и светящимся остеклением, кирпичные корпуса, трубы с дымом,
    водонапорная башня, фонари."""
    x = -L.rnd.randrange(0, 4)
    tower = L.rnd.randrange(30, W - 20)
    while x < W:
        if tower <= x:  # водонапорная башня: бак на решётчатых ногах
            _lattice(L, x, gy, 9, NEAR, width=9, slope=9, rung=3)
            L.rect(x, gy - 15, 9, 6, NEAR)
            L.vline(x + 8, gy - 14, 5, SHADE)
            L.poly([(x - 1, gy - 15), (x + 4, gy - 18), (x + 9, gy - 15)], NEAR)
            L.hline(x + 1, gy - 12, 7, SHADE)
            L.dot(x + 2, gy - 13, "lamp0")
            x += 11
            tower = 10 ** 6
            continue
        bw, bh = L.rnd.randrange(7, 14), L.rnd.randrange(6, 14)
        if L.rnd.random() < 0.4:  # пилообразная крыша: на крутых гранях — тёплое остекление
            for i in range(0, bw - 3, 4):
                L.poly([(x + i, gy - bh), (x + i + 3, gy - bh - 3), (x + i + 4, gy - bh)], NEAR)
                L.vline(x + i + 3, gy - bh - 2, 2, "lamp0" if L.rnd.random() < 0.6 else SHADE)
            _block(L, x, gy, bw, bh, 0.12)
        else:
            _block(L, x, gy, bw, bh)
        if L.rnd.random() < 0.3:
            _chimney(L, x + L.rnd.randrange(1, max(2, bw - 3)), gy - bh - L.rnd.randrange(7, 12), gy - bh, fx,
                     bands=L.rnd.random() < 0.5)
        gap = L.rnd.randrange(0, 5)
        if gap >= 4 and L.rnd.random() < 0.6:
            _street_lamp(L, x + bw + 1, gy, fx)
        x += bw + gap


def _headframe(L: Canvas, x: int, gy: int, h: int, fx: list) -> None:
    """Копёр шахты: решётчатая башня с площадкой, шкив со спицами, подкос и трос к подъёмной машине."""
    _lattice(L, x, gy, h, NEAR, width=11, slope=4, rung=4)
    top = gy - h
    L.hline(x + 1, top, 9, NEAR)
    _wheel(L, x + 5, top - 4, 3, NEAR, hub="brass0")
    L.vline(x + 5, top - 1, 1, NEAR)
    L.line(x + 9, top + 1, x + 15, gy - 9, NEAR)  # подкос
    L.line(x + 8, top - 4, x + 16, gy - 10, SHADE)  # трос
    L.rect(x + 13, gy - 9, 10, 9, NEAR)  # подъёмная машина с двускатной крышей
    L.poly([(x + 12, gy - 9), (x + 18, gy - 13), (x + 24, gy - 9)], NEAR)
    L.vline(x + 22, gy - 8, 8, SHADE)
    L.windows(x + 15, gy - 7, 3, 1, ww=1, wh=2, gx=1, lit=0.7, on=("lamp1", "lamp2"), off=SHADE)


def _spoil_heap(L: Canvas, x: int, gy: int, hw: int, fx: list) -> None:
    """Отвал породы: конус с теневым склоном, осыпь камней, наклонный путь скипа с вагонеткой."""
    hh = hw * 3 // 4 + 2
    L.poly([(x, gy), (x + hw - 1, gy - hh), (x + hw, gy - hh), (x + 2 * hw, gy)], NEAR)
    L.poly([(x + hw, gy - hh), (x + 2 * hw, gy), (x + hw + 2, gy)], SHADE)
    for _ in range(hw):
        i = L.rnd.randrange(1, 2 * hw - 1)
        top = gy - hh + abs(i - hw) * hh // hw
        if top < gy - 1:
            L.dot(x + i, L.rnd.randrange(top + 1, gy), SHADE if i < hw else NEAR)
    L.line(x + 2, gy - 1, x + hw - 1, gy - hh + 1, SHADE)  # путь скипа по склону
    t = L.rnd.randrange(3, max(4, hw - 2))
    L.rect(x + 1 + t, gy - 2 - t * (hh - 2) // max(1, hw - 3) - 1, 2, 2, NEAR)


def _furnace_shed(L: Canvas, x: int, gy: int, fx: list) -> None:
    """Плавильный цех: корпус с фонарём на крыше, раскалённые окна и ворота, отблеск огня."""
    L.rect(x, gy - 10, 14, 10, NEAR)
    L.rect(x + 4, gy - 12, 6, 2, NEAR)
    L.vline(x + 13, gy - 9, 9, SHADE)
    for i in (2, 5, 8, 11):
        L.vline(x + i, gy - 8, 2, "fire1")
        L.dot(x + i, gy - 8, "fire2")
    L.rect(x + 5, gy - 4, 3, 4, "fire1")
    L.vline(x + 6, gy - 3, 3, "fire2")
    L.hline(x + 5, gy - 11, 4, "fire0")
    fx.append(lambda c: c.glow(x + 6, gy - 3, 7, ["haze0", "haze1", "fire0"], soft=0.6))
    fx.append(lambda c: c.glow(x + 6, gy - 12, 4, ["haze0", "haze1"], soft=0.6))
    _chimney(L, x + 10, gy - 22, gy - 10, fx, bands=True, smoke_n=6)


def _near_rust(L: Canvas, gy: int, fx: list) -> None:
    """Шахтёрский город: копры со шкивами, отвалы, плавильный цех, трубы в красных полосах."""
    order = ["head", "heap", "shed", "block", "head", "heap", "block", "stack"]
    L.rnd.shuffle(order)
    x = -L.rnd.randrange(0, 6)
    i = 0
    while x < W:
        kind = order[i % len(order)]
        i += 1
        if kind == "head":
            _headframe(L, x, gy, L.rnd.randrange(14, 20), fx)
            x += 25
        elif kind == "heap":
            hw = L.rnd.randrange(7, 12)
            _spoil_heap(L, x, gy, hw, fx)
            x += 2 * hw - 2
        elif kind == "shed":
            _furnace_shed(L, x, gy, fx)
            x += 16
        elif kind == "stack":
            _chimney(L, x, gy - L.rnd.randrange(18, 24), gy, fx)
            x += 5
        else:
            bw, bh = L.rnd.randrange(6, 10), L.rnd.randrange(5, 10)
            _block(L, x, gy, bw, bh, 0.2)
            L.poly([(x - 1, gy - bh), (x + bw // 2, gy - bh - 3), (x + bw, gy - bh)], NEAR)
            x += bw + L.rnd.randrange(1, 3)


def _flare(c: Canvas, fx_: int, fy: int, big: bool = True) -> None:
    """Горящий факел: ореол жара, пламя из 4 тонов огня с языком, сносимым ветром."""
    c.glow(fx_, fy - 2, 8 if big else 5, ["haze1", (118, 60, 54), (156, 74, 52)], soft=0.4)
    lick = c.rnd.choice((-1, 0, 1))
    c.sprite(fx_ - 2, fy - 5, [
        "..0..",
        ".010.",
        ".121.",
        "01310",
        ".020.",
    ] if big else [".0.", "010", "121", ".2."], {"0": "fire0", "1": "fire1", "2": "fire2", "3": "fire3"})
    c.dot(fx_ + lick, fy - 6, "fire1")
    c.dot(fx_ + lick + (1 if lick >= 0 else -1), fy - 7, "fire0")


def _derrick(L: Canvas, x: int, gy: int, h: int, fx: list) -> None:
    """Нефтяная вышка (≈16 px с будкой и факелом): решётка, кронблок с огнём, будка бурильщика,
    рядом факельная труба 2 px с горящим факелом и маревом жара."""
    _lattice(L, x, gy, h, NEAR, width=11, slope=5, rung=4)
    top = gy - h
    L.rect(x + 4, top - 2, 3, 2, NEAR)  # кронблок
    L.rect(x - 4, gy - 5, 5, 5, NEAR)  # будка бурильщика
    L.hline(x - 5, gy - 5, 7, NEAR)
    L.dot(x - 3, gy - 3, "lamp1")
    sh = h * 2 // 3
    L.rect(x + 12, gy - sh, 2, sh, NEAR)  # факельная труба
    L.vline(x + 13, gy - sh + 1, sh - 1, SHADE)
    L.hline(x + 11, gy - sh, 4, NEAR)
    fx.append(lambda c: _flare(c, x + 12, gy - sh - 1))
    fx.append(lambda c: c.dot(x + 5, top - 3, "red2"))


def _tank(L: Canvas, x: int, gy: int, w: int, h: int, fx: list) -> None:
    """Резервуар: цилиндр с вертикальным бликом зарева и теневым боком, пологий купол, пояса,
    винтовая лестница с перилами, ржавые потёки из-под верхнего пояса."""
    L.rect(x, gy - h, w, h, NEAR)
    L.hline(x + 1, gy - h - 1, w - 2, NEAR)
    L.hline(x + 3, gy - h - 2, w - 6, NEAR)
    hx = x + w // 4  # вертикальный блик на боку цилиндра
    L.vline(hx, gy - h, h, RIM_HOT)
    L.vline(hx - 1, gy - h + 1, h - 1, RIM)
    L.vline(hx + 1, gy - h + 1, h - 1, RIM)
    L.vline(x + w - 1, gy - h, h, SHADE)
    L.vline(x + w - 2, gy - h + 1, h - 1, SHADE)
    for j in (gy - h + 2, gy - 3):  # пояса
        L.hline(x, j, w, SHADE)
        L.dot(hx, j, RIM)
    for _ in range(L.rnd.randrange(2, 4)):  # ржавые потёки
        sx = x + 2 + L.rnd.randrange(max(1, w - 4))
        for j in range(gy - h + 3, gy - h + 3 + L.rnd.randrange(2, max(3, h - 3))):
            if (j + sx) % 3:
                L.dot(sx, j, "rust0")
    n = min(w - 4, h - 1)
    for i in range(n):  # винтовая лестница: ступени и перила
        L.dot(x + w - 3 - i, gy - 1 - i, "steel0")
        L.dot(x + w - 3 - i, gy - 3 - i, SHADE)
    L.vline(x + w // 2, gy - h - 4, 2, NEAR)
    fx.append(lambda c: c.dot(x + w // 2, gy - h - 4, "red1"))


def _pipeline(L: Canvas, x: int, gy: int, w: int) -> None:
    """Трубопровод на опорах: труба с бликом сверху, опоры через 5 px, задвижка со штурвалом."""
    L.hline(x, gy - 3, w, RIM_HOT)
    L.hline(x, gy - 2, w, NEAR)
    for i in range(1, w, 5):
        L.vline(x + i, gy - 1, 1, NEAR)
        L.hline(x + i - 1, gy - 1, 3, SHADE)
    if w > 7:
        vx = x + w // 2
        L.vline(vx, gy - 6, 3, NEAR)
        L.hline(vx - 1, gy - 6, 3, NEAR)


def _near_mazut(L: Canvas, gy: int, fx: list) -> None:
    """Нефтепромысел: вышки с факелами и маревом, резервуары с лестницами и потёками, трубопроводы."""
    x = -L.rnd.randrange(0, 4)
    last = ""
    while x < W:
        r = L.rnd.random()
        if r < 0.38 and last != "derrick":
            _derrick(L, x + 5, gy, L.rnd.randrange(18, 26), fx)
            x += 21
            last = "derrick"
        elif r < 0.75 and last != "tank":
            w, h = L.rnd.randrange(13, 20), L.rnd.randrange(8, 13)
            _tank(L, x, gy, w, h, fx)
            x += w + 1
            last = "tank"
        else:
            w = L.rnd.randrange(6, 12)
            _pipeline(L, x, gy, w)
            x += w
            last = "pipe"


def _clock_tower(L: Canvas, x: int, gy: int, fx: list) -> None:
    """Часовая башня столицы (13 px): цоколь, ствол с пилястрами и окнами, часовой ярус со светящимся
    циферблатом, звонница с арками, шпиль с огнём."""
    w = 13
    L.rect(x, gy - 5, w, 5, NEAR)  # цоколь
    L.rect(x + 1, gy - 28, w - 2, 23, NEAR)  # ствол
    L.vline(x + w - 2, gy - 27, 22, SHADE)
    L.vline(x + 1, gy - 27, 22, RIM)  # освещённая пилястра
    for j in range(gy - 24, gy - 7, 4):
        L.vline(x + 4, j, 2, "lamp0")
        L.vline(x + 8, j, 2, "lamp1" if (j // 4) % 2 else "lamp0")
    L.rect(x, gy - 39, w, 11, NEAR)  # часовой ярус
    L.hline(x - 1, gy - 28, w + 2, NEAR)  # карнизы
    L.hline(x - 1, gy - 39, w + 2, NEAR)
    L.vline(x + w - 1, gy - 38, 10, SHADE)
    L.rect(x + 2, gy - 45, w - 4, 6, NEAR)  # звонница
    for i in (3, 6, 9):
        L.vline(x + i, gy - 43, 3, "lamp0")
    L.vline(x + w - 3, gy - 44, 5, SHADE)
    L.poly([(x + 1, gy - 45), (x + 6, gy - 53), (x + 7, gy - 53), (x + 12, gy - 45)], NEAR)  # шпиль
    L.vline(x + 6, gy - 56, 3, NEAR)
    dx, dy = x + 6, gy - 34

    def dial(c: Canvas) -> None:
        c.glow(dx, dy, 10, ["haze0", "haze1", "lamp0"], soft=0.6)
        c.disk(dx, dy, 4, "lamp0")
        c.disk(dx, dy, 3, "lamp1")
        for ox, oy in ((-1, -2), (-2, -1), (-2, 0), (-1, -1)):
            c.dot(dx + ox, dy + oy, "lamp2")
        for ox, oy in ((0, -3), (3, 0), (0, 3), (-3, 0)):
            c.dot(dx + ox, dy + oy, "lamp0")
        c.vline(dx, dy - 2, 3, "k")
        c.line(dx, dy, dx + 2, dy + 1, "k")
        c.dot(dx, dy, "brass1")
        c.dot(dx, gy - 57, "red2")

    fx.append(dial)


def _near_kotlo(L: Canvas, gy: int, fx: list) -> None:
    """Столица: плотная застройка с сетками окон, мансардами, куполами, трубами на крышах, фонари вдоль
    улицы и часовая башня в центре."""
    tower_at = W // 2 - 6
    x = -L.rnd.randrange(0, 4)
    while x < W:
        if x + 13 > tower_at and x < tower_at + 13:
            _clock_tower(L, tower_at, gy, fx)
            x = tower_at + 14
            continue
        bw, bh = L.rnd.randrange(7, 13), L.rnd.randrange(12, 24)
        bw = min(bw, max(4, tower_at - x - 1)) if x < tower_at else bw
        L.rect(x, gy - bh, bw, bh, NEAR)
        L.vline(x + bw - 1, gy - bh + 1, bh - 1, SHADE)
        r = L.rnd.random()
        if r < 0.35:  # карниз и мансарда со слуховыми окнами
            L.hline(x - 1, gy - bh, bw + 2, NEAR)
            L.poly([(x + 1, gy - bh), (x + 2, gy - bh - 3), (x + bw - 3, gy - bh - 3), (x + bw - 2, gy - bh)], NEAR)
            if bw > 7:
                L.dot(x + bw // 2, gy - bh - 2, "lamp1")
        elif r < 0.55:  # двускатная крыша с печной трубой
            L.poly([(x - 1, gy - bh), (x + bw // 2, gy - bh - bw // 2), (x + bw, gy - bh)], NEAR)
            L.rect(x + bw - 3, gy - bh - bw // 2, 1, bw // 2, NEAR)
        elif r < 0.68 and bw >= 8:  # купол со шпилем
            L.disk(x + bw // 2, gy - bh, bw // 2 - 2, NEAR)
            L.vline(x + bw // 2, gy - bh - bw // 2 - 2, 3, NEAR)
        L.windows(x + 1, gy - bh + 2, (bw - 2) // 2, (bh - 5) // 3, ww=1, wh=2, gx=1, gy=1, lit=0.33,
                  on=("lamp1", "lamp2"), off=SHADE)
        if L.rnd.random() < 0.3 and bw > 4:
            _street_lamp(L, x + bw - 1, gy, fx, h=7)
        x += bw + L.rnd.randrange(0, 2)


# --- Земля, дорога, рельсы -----------------------------------------------------------------------------


def ground(c: Canvas, gy: int = GY) -> None:
    """Земля: освещённая зарево кромка, темнеющие к зрителю полосы, галька с тенью, комья грязи, лужи с
    отражением неба; по локации — крошка руды и угля или мазутные пятна."""
    h = c.h - gy
    _bands(c, 0, gy + 1, W, h - 1, ["ground1", "ground0"], (0.0, 0.5), blend=4)
    c.hline(0, gy, W, "ground2")
    c.dither(0, gy + 1, W, 1, None, "ground2", 0.5, "checker")
    c.dither(0, gy + 2, W, 1, None, "ground2", 0.2, "bayer4")
    for _ in range(10):  # колеи и борозды вдоль горизонта
        x, y = c.rnd.randrange(-4, W), c.rnd.randrange(gy + 2, gy + 6)
        c.hline(x, y, c.rnd.randrange(3, 9), "ground0")
    for _ in range(int(h * 2.2)):  # галька: светлый верх, тень снизу
        x, y = c.rnd.randrange(W), c.rnd.randrange(gy + 2, c.h)
        c.dot(x, y, "ground2")
        c.dot(x, y + 1, "ground0")
        if c.rnd.random() < 0.3:
            c.dot(x + 1, y, "ground2")
            c.dot(x + 1, y + 1, "ground0")
    extra = {"rust": ["ore0", "ore1", "coal1"], "mazut": ["oil0", "oil1"], "kotlo": ["steel0", "ground2"]}
    c.speckle(0, gy + 2, W, h - 2, extra.get(c.theme, ["steel0", "wood0"]), int(h * 1.2))
    if c.theme == "mazut":
        for _ in range(3):
            _oil_stain(c, c.rnd.randrange(4, W - 8), c.rnd.randrange(gy + 3, c.h - 2), c.rnd.randrange(4, 9))
    for _ in range(2 if c.theme != "mazut" else 1):
        puddle(c, c.rnd.randrange(4, W - 14), c.rnd.randrange(gy + 4, c.h - 3), c.rnd.randrange(7, 14))


def puddle(c: Canvas, x: int, y: int, w: int = 10, glint="haze2") -> None:
    """Лужа шириной w (3 строки): тёмная вода отражает зарево полосами, мокрая кромка, блик."""
    rows = ((2, "haze0", "haze1"), (0, "sky2", "haze0"), (1, "sky1", "sky2"))
    for j, (inset, body, refl) in enumerate(rows):
        c.hline(x + inset, y + j, w - 2 * inset, body)
        for i in range(inset + 1, w - inset - 1):
            if c.threshold(x + i, y + j, "bayer4") < (0.45 if j == 0 else 0.2):
                c.dot(x + i, y + j, refl)
    c.hline(x + 3, y - 1, w - 6, "ground2")  # мокрая кромка
    c.hline(x + 2, y + 3, w - 4, "ground0")
    gx = x + w // 3 + c.rnd.randrange(max(1, w // 3))
    c.hline(gx, y + 1, 2, glint)


def _oil_stain(c: Canvas, x: int, y: int, w: int) -> None:
    """Мазутное пятно: чёрная клякса в 2 строки с радужной плёнкой."""
    c.hline(x + 1, y, w - 2, "oil1")
    c.hline(x, y + 1, w, "oil0")
    c.hline(x + 2, y + 2, max(1, w - 4), "oil1")
    c.dot(x + w // 2, y + 1, SHEEN[0])
    c.dot(x + w // 2 + 1, y + 1, SHEEN[1])


def road(c: Canvas, y: int = 58, h: int = 8) -> None:
    """Булыжная дорога высотой h от строки y: дальний бордюр с водостоком, мостовая из камней 3×2 в
    перевязку (блик сверху-слева, тень снизу-справа, тёмные и стёртые камни вперемешку), затёртая
    разметка посередине, мазутные пятна, ближний бордюр со стыками."""
    c.hline(0, y, W, "road2")  # дальний бордюр
    for x in range(c.rnd.randrange(6), W, 7):
        c.dot(x, y, "road1")
    c.hline(0, y + 1, W, "road0")  # водосток
    mid = y + h // 2
    for j in range(y + 2, y + h - 1):
        row = j - (y + 2)
        pair, top = row // 2, row % 2 == 0
        off = 2 * (pair % 2)
        for x in range(W):
            k = (x + off) % 4
            v = ((x + off) // 4 * 7 + pair * 5) % 6  # разные камни: 0 — тёмный, 1 — стёртый
            if k == 3:
                col = "road0"  # шов
            elif top:
                col = ("road1" if v == 0 else COBBLE) if k == 0 else ("road1" if v == 0 else "road2")
            else:
                col = "road0" if (k == 2 or v == 0) else "road1"
            if v == 1 and col in ("road0",) and k != 3:
                col = "road1"
            c.dot(x, j, col)
    for x in range(c.rnd.randrange(4), W, 12):  # затёртая разметка: краска осталась пятнами
        for i in range(6):
            if (x + i) * 5 % 7 != 0:
                c.dot(x + i, mid, "line")
    for _ in range(3):
        sx = c.rnd.randrange(2, W - 8)
        _oil_stain(c, sx, y + 2 + c.rnd.randrange(max(1, h - 5)), c.rnd.randrange(3, 7))
    c.hline(0, y + h - 1, W, "road2")  # ближний бордюр
    for x in range(c.rnd.randrange(8), W, 8):
        c.dot(x, y + h - 1, "road0")


def rails(c: Canvas, y: int = 62) -> None:
    """Пути: y — головка дальнего рельса (на неё встают колёса). Насыпь из щебня, шпалы с торцами,
    подкладки, два рельса с бликами (головка, шейка, тень), осыпь щебня по краю."""
    c.rect(0, y - 1, W, 7, "ground1")
    c.dither(0, y - 1, W, 1, None, "smog0", 0.5, "checker")
    for j in range(y, y + 6):  # щебень: светлые и тёмные камешки
        for x in range(W):
            t = c.threshold(x, j, "bayer4")
            if t < 0.3:
                c.dot(x, j, "smog0" if (x * 7 + j * 3) % 5 else "steel0")
            elif t > 0.85:
                c.dot(x, j, "ground0")
    for x in range(c.rnd.randrange(2), W, 4):  # шпалы
        c.hline(x, y + 1, 3, "wood1")
        c.hline(x, y + 2, 3, "wood1")
        c.dot(x, y + 1, "wood2")
        c.dot(x + 2, y + 2, "wood0")
        c.hline(x, y + 3, 3, "wood0")
        c.dot(x + 1, y + 1, "steel1")  # подкладка под дальний рельс
    c.hline(0, y, W, "steel2")  # дальний рельс
    c.hline(0, y + 1, W, "steel0")
    c.hline(0, y + 3, W, "steel3")  # ближний рельс
    c.hline(0, y + 4, W, "steel1")
    c.hline(0, y + 5, W, "oil1")
    for x in range(c.rnd.randrange(5), W, 9):  # блики на головках
        c.dot(x, y + 3, "white")
        c.dot(x + 1, y + 3, "white")
        c.dot(x + 4, y, "steel3")
    c.speckle(0, y + 6, W, 1, ["ground2", "smog0", "steel0"], 30)


# --- Фонари и дым --------------------------------------------------------------------------------------


def lamp_post(c: Canvas, x: int, gy: int, h: int = 16, flip: bool = False, lit: bool = True) -> None:
    """Уличный фонарь: x — столб, gy — земля у основания, h — высота (рекомендуется 14–20).
    Чугунная тумба, столб с кольцами, кованый кронштейн с плафоном в 3 px от столба (влево при flip);
    горящий — ореол дизером в 3 кольца, пятно света на земле и отблеск на столбе."""
    d = -1 if flip else 1
    top = gy - h
    lx, ly = x + 3 * d, top + 2
    if lit:
        c.glow(lx, ly, 9, ["haze0", "haze1", "lamp0"], soft=0.4)
        for j in range(3):  # пятно света на земле
            ww = 11 - 2 * j
            _veil(c, lx - ww // 2, gy - 1 + j, ww, 1, "haze1" if j == 0 else "ground2", 0.6 - 0.15 * j, "checker")
    c.rect(x - 1, gy - 3, 3, 3, "oil1")  # тумба
    c.dot(x - 1, gy - 3, "oil2")
    c.dot(x + 1, gy - 2, "oil0")
    c.vline(x, top, h - 3, "oil2")  # столб
    if lit:
        c.vline(x, top + 1, h // 3, "steel1")  # отблеск плафона на верху столба
    for j in (top + h // 3 + 1, gy - 6):
        c.dot(x, j, "steel2")
    c.dot(x, top - 1, "steel1")  # навершие
    for i in range(1, 4):  # кронштейн
        c.dot(x + i * d, top, "oil2")
    c.dot(x + d, top + 1, "oil2")  # завиток
    c.hline(lx - 1, ly - 1, 3, "oil2")  # козырёк плафона
    c.dot(lx, ly - 1, "steel1")
    c.dot(lx - 1, ly, "lamp1" if lit else "oil1")
    c.dot(lx, ly, "lamp2" if lit else "oil1")
    c.dot(lx + 1, ly, "lamp1" if lit else "oil1")
    c.dot(lx, ly + 1, "lamp1" if lit else "oil0")


def smoke(c: Canvas, x: int, y: int, n: int = 5, tone: int = 2, ramp_name: str = "smog", drift: int = 1) -> None:
    """Дым из точки (x, y) вверх: клубы растут, перекрываются и сносятся ветром по дуге (drift — сила и
    сторона сноса). Каждый клуб — шар (у крупных — с боковым бугром) в 3 тона: светлый серп сверху-слева,
    тень снизу-справа, между ними дизерный полутон. Верхний клуб ложится на нижний тёмным брюхом —
    складки между клубами. Клуб у устья темнее (сажа), верхний темнее и рвётся по краю — дым тает.
    tone 3 у «smog» — светлый пар (берёт локальный тон светлее smog3)."""
    tones = ramp(ramp_name) + ([STEAM] if ramp_name == "smog" else [])

    def t(i: int):
        return tones[max(0, min(i, len(tones) - 1))]

    sign = 1 if drift >= 0 else -1
    puffs = []
    cy, prev = y, 0
    for i in range(n):
        r = min(1 + i // 2, 4)
        cy -= (prev + r - 1) if i else r
        cx = x + round(drift * (0.5 * i + 0.12 * i * i)) + sign * (1 if i % 2 else -1) * (i > 1)
        puffs.append((cx, cy, r, i))
        prev = r
    for cx, cy, r, i in puffs:  # снизу вверх: брюхо верхнего клуба ложится складкой на нижний
        discs = [(0, 0, r)]
        if r >= 3:  # боковой бугор: клуб не идеально круглый
            discs.append(((r // 2 + 1) * (1 if (i + x) % 2 else -1), 1, r - 2))
        cells: dict[tuple[int, int], float] = {}
        for ox, oy, rr in discs:
            for dy in range(-rr, rr + 1):
                for dx in range(-rr, rr + 1):
                    if c.in_disk(dx, dy, rr) and (dx + ox, dy + oy) not in cells:
                        cells[(dx + ox, dy + oy)] = (-dx - dy) / (rr * 1.41 + 0.5)  # освещённость сверху-слева
        top = n > 3 and i == n - 1
        b = max(1, min(tone, len(tones) - 2)) - (1 if (top or i == 0) else 0)
        hi, mid, lo = t(b + 1), t(b), t(b - 1)
        for (dx, dy), v in cells.items():
            px, py = cx + dx, cy + dy
            edge = any((dx + a, dy + e) not in cells for a, e in ((1, 0), (-1, 0), (0, 1), (0, -1)))
            if edge and (top or (i == n - 2 and n > 3 and dy < 0)) and c.threshold(px, py, "checker") < 0.5:
                continue  # тающий край
            ch = c.threshold(px, py, "checker") < 0.5
            if r == 1:
                col = hi if v > 0 else (lo if v < -0.3 else mid)
            elif v > 0.4 or (v > 0.2 and ch):
                col = hi
            elif v < -0.5 or (v < -0.3 and ch) or (dx, dy + 1) not in cells:
                col = lo
            else:
                col = mid
            c.dot(px, py, col)


def backdrop(c: Canvas, gy: int = GY, smoggy: bool = True, horizon: bool = True) -> None:
    """Типовой фон уличной сцены: небо, оба слоя горизонта (если horizon), земля."""
    sky(c, gy, smoggy)
    if horizon:
        skyline(c, gy)
    ground(c, gy)
