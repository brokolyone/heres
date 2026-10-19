"""Фон уличных сцен: небо, смог, луна/солнце, два слоя горизонта по локациям, земля, дорога, рельсы,
фонари, дым.

Слои рисуются от дальнего к ближнему:
    небо (6 полос с дизерными стыками: от ночной синевы к зареву смога у горизонта, тон по локации) →
    звёзды → светило с плавным ореолом → верхний ярус смога (длинные пряди) → нижний ярус (гряды
    кучевого смога, снизу подсвечены заревом) → дальний горизонт (светлый силуэт с тоном локации, дымы
    стелются по ветру) → пелена смога у земли → ближний горизонт (тёмный силуэт, контровой свет по
    кромкам, огни, факелы, дым) → земля (галька, колеи, грязь, лужи с отражением неба; по локации —
    руда и уголь, мазут, мостовая плитка).

Ближний план рисуется на прозрачный слой: так его кромки получают контровой свет зарева. Свет от него
кладётся в два прохода: большие ореолы (факелы, циферблат) — ДО слоя, чтобы силуэты чётко вставали на
фоне зарева, а сами огни, отблески и дым — ПОСЛЕ, поверх (ореол только осветляет пиксели).
Ветер во всех сценах дует вправо: дальние дымы и пряди смога тянутся вправо, smoke() по умолчанию тоже.
Локальные тона (RGB-кортежи) объявлены ниже — общей палитры canvas.py они не меняют.
"""

import math

from ironvein.art.canvas import Canvas, W, lum, ramp

GY = 56  # линия горизонта / земли по умолчанию

FAR, NEAR, SHADE = "sil2", "sil1", "sil0"  # дальний план, ближний план, теневая сторона ближнего

# --- Локальные тона -------------------------------------------------------------------------------------

MOON = ((96, 90, 100), (142, 132, 122), (186, 174, 150), (224, 214, 188))  # моря → блик
SUN_RUST = ((150, 78, 58), (192, 112, 72), (224, 152, 94), (246, 198, 134))
SUN_MAZUT = ((132, 40, 40), (186, 62, 46), (226, 102, 58), (250, 156, 96))
SHEEN = ((52, 62, 92), (88, 62, 84), (62, 86, 78))  # радужная плёнка на мазуте: синий, лиловый, зелёный
COBBLE = (58, 54, 64)  # блик на булыжнике
STEAM = (122, 114, 134)  # светлый пар: тон над smog3 для дыма tone=3
STEAM_HI = (152, 144, 160)  # гребень самого светлого клуба пара
GRASS = ((40, 42, 36), (62, 62, 46), (88, 84, 58))  # сухая трава пустыря
PEBBLE = (72, 61, 59)  # блик крупной гальки и бровки луж
BALLAST = ((27, 25, 33), (38, 36, 46), (56, 53, 64))  # щебень насыпи: щели, камень, блик

# Небо по локациям: полосы сверху вниз (с какой доли высоты до горизонта начинается каждая — _STOPS).
_SKY = {
    None: [(22, 21, 31), "sky1", "sky2", "sky3", (60, 50, 66), (86, 63, 72)],
    "rust": [(23, 20, 30), "sky1", (40, 32, 46), (60, 43, 54), (90, 58, 60), (128, 84, 68)],
    "mazut": [(25, 19, 29), (36, 23, 35), (54, 30, 44), (82, 40, 48), (116, 56, 50), (152, 78, 56)],
    "kotlo": [(19, 20, 31), (25, 26, 40), (33, 34, 52), (44, 43, 64), (58, 54, 75), (82, 68, 78)],
}
_STOPS = (0.0, 0.11, 0.29, 0.47, 0.65, 0.82)

# Смог (тени → блики) по локациям: холодный серо-лиловый, тёплый рыжий, багровый, сине-серый.
_SMOG = {
    None: ((44, 41, 56), (58, 54, 72), (74, 68, 88), (96, 88, 108)),
    "rust": ((52, 40, 52), (70, 52, 60), (94, 68, 68), (124, 90, 78)),
    "mazut": ((56, 32, 42), (76, 42, 50), (102, 56, 56), (136, 76, 62)),
    "kotlo": ((40, 41, 58), (54, 55, 76), (70, 70, 94), (92, 92, 116)),
}

# Дальний план: силуэт, теневые грани/швы, дым — ближе к цвету зарева (воздушная перспектива).
_FAR = {
    None: ((39, 34, 51), (32, 28, 43), (64, 58, 76)),
    "rust": ((47, 34, 45), (38, 28, 39), (84, 62, 66)),
    "mazut": ((66, 36, 46), (52, 29, 39), (98, 58, 58)),
    "kotlo": ((34, 33, 51), (28, 28, 43), (64, 62, 86)),
}

# Контровой свет зарева на верхних кромках ближнего плана; жаркий — у нефтяных факелов.
_RIM = {None: (48, 38, 54), "rust": (74, 48, 52), "mazut": (96, 52, 50), "kotlo": (50, 46, 70)}
RIM_HOT = (112, 60, 52)

# Освещённая заревом кромка земли у горизонта.
_EDGE = {None: (62, 50, 54), "rust": (82, 56, 50), "mazut": (92, 52, 46), "kotlo": (60, 54, 66)}

# Ореол огня (снаружи → внутрь), жар у факелов.
_FIRE_HALO = [(84, 44, 46), (122, 58, 50), (170, 82, 54)]
_LAMP_HALO = ["haze0", "haze1", "lamp0"]


def _pick(table: dict, c: Canvas):
    return table.get(c.theme, table[None])


# --- Мелкие помощники ----------------------------------------------------------------------------------


def _lighten(c: Canvas, x: int, y: int, col) -> None:
    """Точка, только если она светлее того, что уже нарисовано (свет не затемняет)."""
    old = c.get(x, y)
    new = c.rgb(col)
    if old is not None and lum(old) < lum(new):
        c.dot(x, y, new)


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


def halo(c: Canvas, cx: int, cy: int, r: int, colors: list, ry: int | None = None) -> None:
    """Плавный ореол света: кольца colors (от внешнего к внутреннему) с переходами Байером 4×4 — мягче
    шахматки Canvas.glow. ry — вертикальный радиус (сплющенный ореол, пятно света на земле).
    Только осветляет: можно класть поверх чего угодно."""
    ry = r if ry is None else ry
    n = len(colors)
    rgbs = [c.rgb(k) for k in colors]
    for dy in range(-ry, ry + 1):
        for dx in range(-r, r + 1):
            d = math.hypot(dx / (r + 0.5), dy / (ry + 0.5))
            if d >= 1:
                continue
            t = (1 - d) * n  # 0 на краю … n в центре
            i = int(t)
            k = i if c.threshold(cx + dx, cy + dy, "bayer4") < t - i else i - 1
            if k >= 0:
                _lighten(c, cx + dx, cy + dy, rgbs[min(k, n - 1)])


def _sky_at(c: Canvas, gy: int, y: int, shift: int = 0):
    """Цвет полосы неба на строке y (shift > 0 — на столько полос светлее: пряди смога в тон небу)."""
    bands = _pick(_SKY, c)
    k = max(i for i, s in enumerate(_STOPS) if y >= round(s * gy))
    return bands[max(0, min(k + shift, len(bands) - 1))]


# --- Небо ----------------------------------------------------------------------------------------------


def sky(c: Canvas, gy: int = GY, smoggy: bool = True, moon: bool = True) -> None:
    """Сумеречное небо: 6 полос дизером от ночной синевы к зареву у горизонта (тон по локации), редкие
    звёзды, светило с ореолом и смог двумя ярусами — высокие пряди и низкие гряды, подсвеченные снизу.
    smoggy=False — ясная ночь: больше звёзд, пара тонких прядей и низкая пелена тумана у горизонта."""
    _bands(c, 0, 0, W, gy, _pick(_SKY, c), _STOPS)
    _stars(c, gy, {"rust": 6, "mazut": 4}.get(c.theme, 12 if smoggy else 18))
    disk = celestial(c) if moon else None
    if not smoggy:
        for k in range(2):
            y = int(gy * (0.56 + 0.13 * k))
            streak(c, c.rnd.randrange(-8, W - 40), y, c.rnd.randrange(30, 52), _sky_at(c, gy, y, 1))
        mist = _pick(_SKY, c)[-1]
        for k in range(4):  # пелена тумана над самой землёй
            _veil(c, 0, gy - 4 + k, W, 1, tuple(min(255, v + 10) for v in c.rgb(mist)), 0.12 + 0.1 * k)
        return
    for i in range(3):  # верхний ярус: длинные тонкие пряди
        y = c.rnd.randrange(3, max(4, int(gy * 0.27)))
        x = i * 44 + c.rnd.randrange(-14, 12)
        if disk and abs(y - disk[1]) <= disk[2] + 1 and x - 4 < disk[0] < x + 46:
            y = disk[1] + disk[2] + 4
        streak(c, x, y, c.rnd.randrange(24, 44), _sky_at(c, gy, y, 1))
    tones = _pick(_SMOG, c)
    glow = _pick(_SKY, c)[-1]
    slots = list(range(4))
    c.rnd.shuffle(slots)
    for k, i in enumerate(slots):  # нижний ярус: гряды кучевого смога, нижние подсвечены заревом
        w = c.rnd.randrange(18, 32)
        x = i * (W // 4) + c.rnd.randrange(-8, 8)
        y = int(gy * (0.27 + 0.085 * k)) + c.rnd.randrange(0, 3)
        if disk and x - disk[2] - 3 < disk[0] < x + w + disk[2] + 3 and abs(y - disk[1]) < disk[2] + 6:
            continue  # не закрывать светило: перед ним уже есть своя тучка
        cloud(c, x, y, w, tone=1 if k < 2 else 2, ramp_name=tones, under=glow if y > gy * 0.42 else None)


def _stars(c: Canvas, gy: int, n: int) -> None:
    """Редкие тусклые звёзды в верхних полосах; две-три мерцают крестиком."""
    top = max(4, int(gy * 0.3))
    for i in range(n):
        x, y = c.rnd.randrange(2, W - 2), c.rnd.randrange(1, top)
        if i < 3 and c.rnd.random() < 0.7:
            c.sparkle(x, y, (128, 122, 140), 1, "sky3")
        else:
            c.dot(x, y, "sky3" if c.rnd.random() < 0.55 else (84, 80, 100))


def celestial(c: Canvas, x: int | None = None, y: int | None = None, r: int = 5) -> tuple[int, int, int]:
    """Светило за смогом: бледная луна с морями (столица и по умолчанию), низкое рыжее солнце над шахтами,
    багровое — над нефтепромыслом (солнце перечёркнуто прядями смога). Плавный ореол, по нижнему краю
    ползёт тучка. Возвращает (x, y, r) — чтобы облака не закрыли диск."""
    theme = c.theme
    lo_x = W // 2 + 16 if theme == "kotlo" else W // 2  # над столицей — правее часовой башни
    x = c.rnd.randrange(lo_x, W - 12) if x is None else x
    y = c.rnd.randrange(10, 16) if y is None else y
    smog = _pick(_SMOG, c)
    if theme in ("rust", "mazut"):
        r += 1
        if theme == "rust":
            tones, ring = SUN_RUST, [(36, 30, 43), (60, 44, 54), (108, 72, 66)]
        else:
            tones, ring = SUN_MAZUT, [(44, 26, 38), (72, 37, 46), (124, 58, 54)]
        halo(c, x, y, r + 12, ring[:2])
        halo(c, x, y, r + 4, ring[1:])
        _disk_shaded(c, x, y, r, tones)
        for k, dy in enumerate((1, 3, 5)):  # пряди смога поперёк нижней половины диска, книзу толще
            ww = 2 * r + 7 - 2 * k
            c.hline(x - ww // 2, y + dy, ww, smog[2] if k < 2 else smog[1])
            if k == 2:
                c.hline(x - ww // 2 + 2, y + dy + 1, ww - 4, smog[1])
        c.hline(x - r - 6, y - 2, 6, smog[2])  # хвост пряди за диском
    else:
        halo(c, x, y, r + 10, [(33, 32, 45), (44, 42, 58), (58, 55, 72)])
        halo(c, x, y, r + 4, [(76, 72, 88), (98, 94, 106)])
        _disk_shaded(c, x, y, r, MOON)
        for mx, my, big in ((-2, -1, True), (1, 1, True), (2, -3, False), (-1, 3, False), (3, 2, False)):
            c.dot(x + mx, y + my, MOON[1])  # лунные моря
            if big:
                c.dot(x + mx + 1, y + my, MOON[1])
                c.dot(x + mx, y + my + 1, MOON[1])
                c.dot(x + mx + 1, y + my - 1, MOON[3])  # светлая кромка кратера
        streak(c, x - r - 5, y + 1, 2 * r + 11, smog[2])  # тонкая прядь смога через диск
    cloud(c, x - r - 4 - c.rnd.randrange(4), y + r - 1, 2 * r + 10, tone=1, ramp_name=smog)
    return x, y, r


def _disk_shaded(c: Canvas, cx: int, cy: int, r: int, tones) -> None:
    """Диск в 4 тона: блик серпом сверху-слева (с дизер-переходом), тень снизу-справа."""
    t0, t1, t2, t3 = (c.rgb(t) for t in tones)
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if not c.in_disk(dx, dy, r):
                continue
            x, y = cx + dx, cy + dy
            ch = c.threshold(x, y, "checker") < 0.5
            if not c.in_disk(dx + 1, dy + 1, r):
                col = t0 if (dx > 0 and dy > 0) else t1
            elif not c.in_disk(dx - 1, dy - 1, r):
                col = t3
            elif not c.in_disk(dx - 2, dy - 2, r):
                col = t3 if ch else t2
            elif not c.in_disk(dx + 2, dy + 2, r):
                col = t1 if ch else t2
            else:
                col = t2
            c.dot(x, y, col)


def streak(c: Canvas, x: int, y: int, w: int, col="smog1") -> None:
    """Тонкая прядь смога: сплошная середина, дизерные «рваные» концы, короткая прядь строкой ниже
    (смещена по ветру)."""
    c.hline(x + 3, y, w - 6, col)
    for i in (0, 1, 2):
        for xx in (x + i, x + w - 1 - i):
            if c.threshold(xx, y, "bayer4") < 0.25 + 0.25 * i:
                c.dot(xx, y, col)
    sub = w // 3
    sx = x + w // 3 + (w // 6 if (x + y) % 2 else -w // 6)
    c.hline(sx + 1, y + 1, sub - 2, col)
    if c.threshold(sx, y + 1, "checker") < 0.5:
        c.dot(sx, y + 1, col)
    if w > 30:  # тонкий хвост по ветру
        for xx in range(x + w, x + w + 5):
            if c.threshold(xx, y - 1, "bayer4") < 0.4 - 0.07 * (xx - x - w):
                c.dot(xx, y - 1, col)


def _tones(ramp_name) -> list:
    """Тона рампы по имени или готовый список цветов (тени → блики)."""
    return ramp(ramp_name) if isinstance(ramp_name, str) else list(ramp_name)


def cloud(c: Canvas, x: int, y: int, w: int, tone: int = 1, ramp_name="smog", under=None) -> None:
    """Гряда смога шириной w: круглые бугры над плоским брюхом. (x, y) — левый верх тела, бугры выше.
    Свет сверху-слева: светлые макушки и левые склоны бугров (у крупных — с дизерным полутоном), тёмные
    правые склоны, брюхо в тени с рваным дизерным низом. ramp_name — имя рампы или список тонов.
    under — цвет подсветки брюха снизу (зарево у горизонта), иначе тень рампы."""
    tones = _tones(ramp_name)
    n = len(tones)
    hi, mid, lo = tones[min(tone + 1, n - 1)], tones[tone], tones[max(tone - 1, 0)]
    top_hi = tones[min(tone + 2, n - 1)]
    h = max(2, min(4, w // 8))  # высота тела под буграми
    base = y + h  # первая строка под облаком
    nb = max(1, w // 8)
    bumps = []
    for k in range(nb):
        bx = x + 2 + int((k + 0.5) * (w - 4) / nb) + c.rnd.randrange(-1, 2)
        bumps.append((bx, c.rnd.randrange(2, 4 + w // 12)))
    cells = set()
    for i in range(w):
        px = x + i
        hh = h - (1 if i in (0, w - 1) else 0) - (1 if i in (1, w - 2) and h > 2 else 0)
        for bx, br in bumps:
            d = abs(px - bx)
            if d <= br:
                hh = max(hh, h - 1 + int(math.sqrt(br * br - d * d) * 0.85 + 0.3))
        for k in range(max(1, hh)):
            cells.add((px, base - 1 - k))
    for px, py in cells:
        up, left, right = (px, py - 1) in cells, (px - 1, py) in cells, (px + 1, py) in cells
        below, below2 = (px, py + 1) in cells, (px, py + 2) in cells
        ch = c.threshold(px, py, "checker") < 0.5
        if not up:
            col = top_hi if (not left or (px - 1, py - 1) not in cells) and w > 16 and ch else hi
        elif not left or (not (px - 1, py - 1) in cells and ch):
            col = hi
        elif not below:
            col = under or lo
        elif not right:
            col = lo
        elif not below2 and ch:
            col = lo
        elif (px, py - 2) not in cells and ch:
            col = hi
        else:
            col = mid
        c.dot(px, py, col)
    for i in range(2, w - 2):  # рваный низ
        if c.threshold(x + i, base, "bayer4") < 0.28:
            c.dot(x + i, base, under or lo)


# --- Горизонт: общее -----------------------------------------------------------------------------------


def skyline(c: Canvas, gy: int = GY) -> None:
    """Оба слоя горизонта по локации сцены (Canvas.theme): дальний, пелена смога, ближний."""
    skyline_far(c, gy)
    skyline_near(c, gy)


def skyline_far(c: Canvas, gy: int = GY) -> None:
    """Дальний план: светлый силуэт тона локации почти без деталей, дымы стелются по ветру, у земли его
    съедает тёплая пелена смога (воздушная перспектива)."""
    {"rust": _far_rust, "mazut": _far_mazut, "kotlo": _far_kotlo}.get(c.theme or "", _far_default)(c, gy)
    glow = _pick(_SKY, c)[-1]
    for k in range(6):  # пелена густеет к земле
        _veil(c, 0, gy - 6 + k, W, 1, glow, 0.08 + 0.075 * k)
    smog = _pick(_SMOG, c)
    for _ in range(2):  # низкие пряди смога поперёк дальнего плана
        streak(c, c.rnd.randrange(-10, W - 20), gy - c.rnd.randrange(8, 15), c.rnd.randrange(24, 44), smog[1])


class _FX:
    """Свет и дым ближнего плана: back — до слоя (большие ореолы за силуэтом), front — после (огни, дым)."""

    def __init__(self) -> None:
        self.back: list = []
        self.front: list = []


def skyline_near(c: Canvas, gy: int = GY) -> None:
    """Ближний план: тёмный силуэт (NEAR) с теневыми гранями и контровым светом по кромкам, огни окон,
    трубы, факелы и дым — по локации."""
    layer = c.layer(c.w, c.h)
    fx = _FX()
    {"rust": _near_rust, "mazut": _near_mazut, "kotlo": _near_kotlo}.get(c.theme or "", _near_default)(layer, gy, fx)
    _rim(layer, _pick(_RIM, c))
    for f in fx.back:
        f(c)
    c.paste(layer, 0, 0)
    for f in fx.front:
        f(c)


def _rim(layer: Canvas, col) -> None:
    """Контровой свет: верхний пиксель силуэта (NEAR/SHADE) под открытым небом светлеет до col."""
    src = {layer.rgb(NEAR), layer.rgb(SHADE)}
    rc = (*layer.rgb(col), 255)
    px = layer.px
    for y in range(1, layer.h):
        for x in range(layer.w):
            v = px[x, y]
            if v[3] and v[:3] in src and not px[x, y - 1][3]:
                px[x, y] = rc


def _plume(c: Canvas, x: int, y: int, length: int, col, drift: int = 1) -> None:
    """Дальний дым из трубы: столбик поднимается на 3 px, гнётся и тянется лентой по ветру, медленно
    поднимаясь, утолщаясь (1 → 3 px, с комками) и тая дизером к хвосту. Верхняя кромка ленты светлее
    (освещена небом), нижняя — тон col."""
    lit = tuple(min(255, v + 14) for v in col)
    cx, cy = x, y
    for i in range(length):
        if i < 3:
            cy = y - i
        else:
            cx += drift
            cy = y - 3 - (i - 3) // 4
        thick = 1 if i < 4 else min(3, 2 + (i - 4) // 7)
        if i > 6 and (i // 3) % 3 == 1:
            thick += 1  # комок
        t = i / max(1, length - 1)
        level = 1.0 if t < 0.3 else 1.0 - (t - 0.3) / 0.7 * 0.9
        for k in range(thick):
            yy = cy - k
            if c.threshold(cx, yy, "bayer4") < level:
                c.dot(cx, yy, lit if (k == thick - 1 and thick > 1) else col)


def _truss(c: Canvas, x: int, gy: int, h: int, col, base: int, top: int, panel: int, cross: bool = True) -> None:
    """Решётчатая башня-ферма: две прямые ноги сходятся от base px у земли к top px наверху, пояса через
    panel строк, в каждой панели X-раскосы (или один раскос, если cross=False или панель узкая).
    Буровые вышки, копры, опоры водонапорных башен."""
    inset = (base - top) // 2
    ax0, bx0 = x, x + base - 1
    ax1, bx1 = x + inset, x + base - 1 - inset

    def legs(i: int) -> tuple[int, int]:  # i — строка от земли
        f = i / max(1, h - 1)
        return round(ax0 + (ax1 - ax0) * f), round(bx0 + (bx1 - bx0) * f)

    c.line(ax0, gy - 1, ax1, gy - h, col)
    c.line(bx0, gy - 1, bx1, gy - h, col)
    rows = list(range(0, h - 1, panel)) + [h - 1]
    for k, (i, j) in enumerate(zip(rows, rows[1:], strict=False)):
        a, b = legs(i)
        a2, b2 = legs(j)
        c.hline(a, gy - 1 - i, b - a + 1, col)
        if b - a < 3:
            continue
        if cross and b - a >= 5:
            c.line(a, gy - 1 - i, b2, gy - 1 - j, col)
            c.line(b, gy - 1 - i, a2, gy - 1 - j, col)
        elif k % 2:
            c.line(a, gy - 1 - i, b2, gy - 1 - j, col)
        else:
            c.line(b, gy - 1 - i, a2, gy - 1 - j, col)
    a, b = legs(h - 1)
    c.hline(a, gy - h, b - a + 1, col)


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
    """Редкие тусклые огни дальнего плана (сквозь смог — приглушённо-тёплые)."""
    for j in range(top + 2, top + bh - 3, 3):
        for i in range(x + 1, x + bw - 1, 2):
            if c.rnd.random() < lit:
                c.dot(i, j, (104, 72, 62) if c.rnd.random() < 0.7 else (140, 96, 70))


# --- Дальний план по локациям --------------------------------------------------------------------------


def _far_chimney(c: Canvas, x: int, gy: int, ch: int, base_h: int = 0, plume: int = 16) -> None:
    """Дальняя труба 2 px с оголовком и дымом по ветру; стоит на крыше высоты base_h."""
    F, D, S = _pick(_FAR, c)
    top = gy - base_h - ch
    c.rect(x, top, 2, ch, F)
    c.hline(x - 1, top, 4, F)
    c.dot(x + 1, top + 3, D)
    if plume:
        _plume(c, x + 1, top - 1, plume, S)


def _far_default(c: Canvas, gy: int) -> None:
    """Промышленный город: корпуса с плоскими, ступенчатыми и пилообразными крышами, газгольдер или
    градирня, трубы с дымом по ветру, редкие тусклые окна."""
    F, D, S = _pick(_FAR, c)
    x = -c.rnd.randrange(0, 4)
    special = c.rnd.randrange(20, W - 30)
    while x < W:
        if special <= x:
            if c.rnd.random() < 0.5:  # газгольдер: цилиндр в решётке направляющих колонн
                c.rect(x + 1, gy - 10, 12, 10, F)
                c.hline(x + 2, gy - 11, 10, F)
                for i in range(0, 14, 4):
                    c.vline(x + i, gy - 14, 14, F)
                c.hline(x, gy - 14, 14, F)
                c.hline(x, gy - 8, 14, D)
                c.hline(x + 1, gy - 4, 12, D)
                c.vline(x + 11, gy - 10, 10, D)
            else:  # градирня: вогнутый силуэт и белый пар
                for j in range(15):
                    half = 6 - (j * (14 - j)) // 24
                    c.hline(x + 7 - half, gy - 1 - j, 2 * half, F)
                    c.dot(x + 6 + half, gy - 1 - j, D)
                _plume(c, x + 7, gy - 17, 16, S)
            x += 16
            special = 10 ** 6
            continue
        bw, bh = c.rnd.randrange(6, 14), c.rnd.randrange(8, 20)
        c.rect(x, gy - bh, bw, bh, F)
        c.vline(x + bw - 1, gy - bh + 1, bh - 1, D)
        r = c.rnd.random()
        if r < 0.28:  # пилообразная крыша
            for i in range(0, bw - 2, 3):
                c.poly([(x + i, gy - bh), (x + i + 3, gy - bh - 2), (x + i + 3, gy - bh)], F)
        elif r < 0.45 and bw > 7:  # ступенчатый верх
            c.rect(x + 2, gy - bh - 4, bw - 4, 4, F)
            c.vline(x + bw - 3, gy - bh - 3, 3, D)
        elif r < 0.55:  # бак на крыше
            c.rect(x + 1, gy - bh - 3, 3, 2, F)
            c.dot(x + 1, gy - bh - 1, F)
            c.dot(x + 3, gy - bh - 1, F)
        if c.rnd.random() < 0.38:
            _far_chimney(c, x + c.rnd.randrange(1, max(2, bw - 2)), gy, c.rnd.randrange(6, 12), bh,
                         c.rnd.randrange(12, 22))
        _dim_windows(c, x, gy - bh, bw, bh, 0.06)
        x += bw + c.rnd.randrange(0, 3)


def _far_rust(c: Canvas, gy: int) -> None:
    """Шахтёрский край: крупные конусы отвалов с теневым склоном, далёкие копры со шкивами, кирпичные
    трубы с дымом и наклонная галерея конвейера."""
    F, D, S = _pick(_FAR, c)
    x = -c.rnd.randrange(0, 6)
    gallery = False
    while x < W:
        r = c.rnd.random()
        if r < 0.25:
            h = c.rnd.randrange(12, 18)  # копёр: прямая башня, наклонная нога, шкив на вершине
            _truss(c, x, gy, h, F, base=5, top=4, panel=4, cross=False)
            c.line(x + 4, gy - h, x + 10, gy - 1, F)
            c.line(x + 5, gy - h, x + 11, gy - 1, D)
            _wheel(c, x + 4, gy - h - 2, 2, F)
            x += 13
        elif r < 0.42:
            _far_chimney(c, x + 1, gy, c.rnd.randrange(16, 24), 0, c.rnd.randrange(14, 24))
            x += 5
        else:
            hw = c.rnd.randrange(9, 18)
            hh = hw * 2 // 3 + c.rnd.randrange(0, 4)
            c.poly([(x, gy), (x + hw - 1, gy - hh), (x + hw + 1, gy - hh), (x + 2 * hw, gy)], F)
            c.poly([(x + hw + 1, gy - hh), (x + 2 * hw, gy), (x + hw + 3, gy)], D)
            if not gallery and hw > 11:  # галерея конвейера на вершину отвала
                gallery = True
                c.line(x + hw, gy - hh, x + hw + 13, gy - 3, F)
                c.line(x + hw, gy - hh + 1, x + hw + 13, gy - 2, F)
                for k in range(3, 13, 4):
                    c.vline(x + hw + k, gy - hh + 1 + k * (hh - 3) // 13, hh - 3 - k * (hh - 3) // 13, F)
            x += hw + c.rnd.randrange(3, 10)


def _far_mazut(c: Canvas, gy: int) -> None:
    """Нефтепромысел: плоская степь, частокол тонких вышек с огоньками, низкие резервуары, трубопровод на
    опорах и факельная труба с крупным пламенем."""
    F, D, S = _pick(_FAR, c)
    c.hline(0, gy - 3, W, F)  # трубопровод вдоль горизонта
    for i in range(c.rnd.randrange(4), W, 7):
        c.vline(i, gy - 2, 2, F)
    x = -c.rnd.randrange(0, 4)
    stack = c.rnd.randrange(10, W - 20)
    while x < W:
        if stack <= x:
            c.rect(x, gy - 22, 2, 22, F)  # факельная труба с крупным пламенем
            c.hline(x - 1, gy - 22, 4, F)
            halo(c, x + 1, gy - 25, 8, _FIRE_HALO[:2])
            c.sprite(x - 1, gy - 29, [".1.", "121", "232", ".1."], {"1": "fire0", "2": "fire1", "3": "fire2"})
            _plume(c, x + 1, gy - 30, 18, D)
            x += 5
            stack = 10 ** 6
            continue
        if c.rnd.random() < 0.5:
            h = c.rnd.randrange(9, 16)
            _truss(c, x, gy, h, F, base=5, top=1, panel=3, cross=False)
            c.dot(x + 2, gy - h - 1, F)
            if c.rnd.random() < 0.6:
                c.dot(x + 2, gy - h - 2, "fire1" if c.rnd.random() < 0.5 else (170, 90, 60))
            x += 6 + c.rnd.randrange(0, 4)
        else:
            w, h = c.rnd.randrange(6, 12), c.rnd.randrange(3, 6)
            c.rect(x, gy - h, w, h, F)
            c.hline(x + 1, gy - h - 1, w - 2, F)
            c.vline(x + w - 1, gy - h, h, D)
            x += w + c.rnd.randrange(2, 8)


def _far_kotlo(c: Canvas, gy: int) -> None:
    """Столица: плотная стена высоток, шпили, купола, радиомачта, ступенчатая высотка со шпилем;
    в небе — дирижабль."""
    F, D, S = _pick(_FAR, c)
    _airship(c, c.rnd.randrange(26, 38), c.rnd.randrange(9, 13))
    x = -c.rnd.randrange(0, 4)
    big = c.rnd.randrange(2, 22)  # левее часовой башни; луна — справа
    mast = c.rnd.randrange(78, W - 10)
    while x < W:
        if big <= x:
            _stepped_tower(c, x, gy)
            x += 15
            big = 10 ** 6
            continue
        bw, bh = c.rnd.randrange(6, 12), c.rnd.randrange(14, 28)
        c.rect(x, gy - bh, bw, bh, F)
        r = c.rnd.random()
        if mast <= x:  # радиомачта с красным огнём
            c.vline(x + bw // 2, gy - bh - 9, 9, F)
            c.hline(x + bw // 2 - 1, gy - bh - 6, 3, F)
            c.dot(x + bw // 2, gy - bh - 10, "red1")
            mast = 10 ** 6
        elif r < 0.22:
            c.vline(x + bw // 2, gy - bh - 6, 6, F)
            c.hline(x + bw // 2 - 1, gy - bh - 2, 3, F)
        elif r < 0.38:
            c.disk(x + bw // 2, gy - bh, bw // 2 - 1, F)
            c.vline(x + bw // 2, gy - bh - bw // 2 - 2, 2, F)
        elif r < 0.55:
            c.poly([(x, gy - bh), (x + bw // 2, gy - bh - 4), (x + bw, gy - bh)], F)
        c.vline(x + bw - 1, gy - bh + 1, bh - 1, D)
        _dim_windows(c, x, gy - bh, bw, bh, 0.1)
        x += bw + c.rnd.randrange(0, 2)


def _stepped_tower(c: Canvas, x: int, gy: int) -> None:
    """Ступенчатая высотка столицы (13 px шириной, ~33 высотой): три яруса, шпиль со звездой-огнём."""
    F, D, S = _pick(_FAR, c)
    top = gy
    for w, h in ((13, 17), (9, 7), (5, 4)):
        top -= h
        lx = x + (13 - w) // 2
        c.rect(lx, top, w, h, F)
        c.vline(lx + w - 1, top + 1, h - 1, D)
        c.hline(lx - 1, top, w + 2, F)  # карниз яруса
    c.vline(x + 6, top - 5, 5, F)
    c.dot(x + 6, top - 6, "red1")
    _dim_windows(c, x, gy - 17, 13, 17, 0.16)


def _airship(c: Canvas, x: int, y: int) -> None:
    """Дирижабль (≈30×10): сигара, освещённая луной сверху, тёмное брюхо, рёбра обшивки, оперение,
    гондола с тёплыми окнами и красный ходовой огонь на киле."""
    a, b = 11, 3
    body = ((84, 80, 100), (66, 63, 82), (56, 53, 72), (46, 43, 60), (40, 37, 53), (32, 30, 44), (26, 24, 36))
    c.poly([(x + a - 3, y - 1), (x + a + 3, y - b - 3), (x + a + 4, y - b - 3), (x + a + 4, y)], body[3])  # киль
    c.poly([(x + a - 3, y + 1), (x + a + 3, y + b + 2), (x + a + 4, y + b + 2), (x + a + 4, y + 1)], body[5])
    for dy in range(-b, b + 1):
        for dx in range(-a, a + 1):
            if (dx / (a + 0.5)) ** 2 + (dy / (b + 0.6)) ** 2 > 1:
                continue
            k = dy + b
            if dx % 4 == 1 and -b < dy < b:  # рёбра обшивки
                k = min(k + 1, 6)
            c.dot(x + dx, y + dy, body[k])
    c.dot(x - a, y, body[2])
    c.rect(x - 4, y + b + 1, 7, 2, body[6])  # гондола
    c.dot(x - 3, y + b + 1, "lamp1")
    c.dot(x - 1, y + b + 1, "lamp2")
    c.dot(x + 1, y + b + 1, "lamp1")
    c.dot(x + a + 4, y - b - 3, "red2")


# --- Ближний план по локациям (рисуется на прозрачный слой L, свет и дым — в fx) ----------------------


def _window(L: Canvas, x: int, y: int, h: int = 2) -> None:
    """Окно 1×h ближнего плана: горит тёплым (верх светлее) или тлеет тускло."""
    r = L.rnd.random()
    if r < 0.55:
        L.vline(x, y, h, "lamp1")
        L.dot(x, y, "lamp2")
    elif r < 0.8:
        L.vline(x, y, h, "lamp0")
    else:
        L.vline(x, y, h, (150, 96, 54))
        L.dot(x, y + h - 1, "lamp0")


def _block(L: Canvas, x: int, gy: int, bw: int, bh: int, lit: float = 0.22, roof: bool = True) -> None:
    """Корпус ближнего плана: силуэт, теневая правая грань, карниз с тенью под ним, окна 1×2 (тёплые и
    тусклые), иногда — освещённые ворота; на крыше — вентиляционные будки и дефлекторы."""
    top = gy - bh
    L.rect(x, top, bw, bh, NEAR)
    L.vline(x + bw - 1, top + 1, bh - 1, SHADE)
    if bw > 5:
        L.hline(x - 1, top, bw + 2, NEAR)
        L.hline(x, top + 1, bw, SHADE)
    for j in range(top + 3, gy - 3, 4):
        for i in range(x + 1, x + bw - 2, 2):
            if L.rnd.random() < lit:
                _window(L, i, j)
    if bw >= 9 and bh >= 7 and L.rnd.random() < 0.3:  # ворота с тёплым светом изнутри
        dx = x + 2 + L.rnd.randrange(bw - 6)
        L.rect(dx, gy - 3, 3, 3, "lamp0")
        L.hline(dx, gy - 3, 3, (150, 96, 54))
        L.dot(dx + 1, gy - 1, "lamp1")
    if roof:
        for _ in range(bw // 6):
            vx = x + 1 + L.rnd.randrange(max(1, bw - 3))
            if L.rnd.random() < 0.5:
                L.rect(vx, top - 2, 2, 2, NEAR)  # вентиляционная будка
            else:
                L.vline(vx, top - 3, 3, NEAR)  # дефлектор
                L.dot(vx + 1, top - 3, NEAR)


def _chimney(L: Canvas, x: int, top: int, gy: int, fx: _FX, bands: bool = True, smoke_n: int = 5) -> None:
    """Кирпичная труба 3 px: оголовок, красные полосы с бликом, кирпичные швы, теневая грань, сигнальный
    огонь с ореолом и дым по ветру."""
    L.rect(x, top, 3, gy - top, NEAR)
    L.vline(x + 2, top + 1, gy - top - 1, SHADE)
    L.hline(x - 1, top, 5, NEAR)
    L.hline(x - 1, top + 1, 5, SHADE)
    for j in range(top + 5, gy, 3):  # кирпичные швы
        L.dot(x + (j // 3) % 2, j, SHADE)
    if bands:
        for j in (top + 3, top + 6):
            L.hline(x, j, 3, "red0")
            L.dot(x, j, "red1")
    fx.front.append(lambda c: halo(c, x + 1, top - 1, 3, [(70, 34, 40)]))
    fx.front.append(lambda c: c.dot(x + 1, top - 1, "red2"))
    fx.front.append(lambda c: smoke(c, x + 1, top - 2, smoke_n, tone=1))


def _street_lamp(L: Canvas, x: int, gy: int, fx: _FX, h: int = 8) -> None:
    """Маленький фонарь ближнего плана у подножия домов: столб, кронштейн, огонь с ореолом."""
    L.vline(x, gy - h, h, NEAR)
    L.dot(x + 1, gy - h, NEAR)
    fx.front.append(lambda c: halo(c, x + 2, gy - h + 1, 3, [(74, 52, 54)]))
    fx.front.append(lambda c: halo(c, x + 2, gy, 3, [(56, 44, 50)], ry=1))  # пятно света у столба
    fx.front.append(lambda c: c.dot(x + 2, gy - h + 1, "lamp2"))
    fx.front.append(lambda c: c.dot(x + 2, gy - h, (40, 36, 50)))


def _hall(L: Canvas, x: int, gy: int, bw: int, bh: int) -> None:
    """Цех с пилообразной крышей: на крутых гранях зубцов — тёплое остекление фонарей."""
    top = gy - bh
    for i in range(0, bw - 3, 4):
        L.poly([(x + i, top), (x + i + 3, top - 3), (x + i + 4, top)], NEAR)
        glass = L.rnd.random() < 0.65
        L.vline(x + i + 3, top - 2, 2, "lamp0" if glass else SHADE)
        if glass:
            L.dot(x + i + 3, top - 2, "lamp1")
    _block(L, x, gy, bw, bh, 0.12, roof=False)


def _water_tower(L: Canvas, x: int, gy: int) -> None:
    """Водонапорная башня 9 px: бак с поясами и конической крышей на решётчатых ногах."""
    _truss(L, x, gy, 9, NEAR, base=9, top=7, panel=4)
    L.rect(x, gy - 15, 9, 6, NEAR)
    L.vline(x + 8, gy - 14, 5, SHADE)
    L.vline(x + 7, gy - 14, 5, SHADE)
    L.poly([(x - 1, gy - 15), (x + 4, gy - 19), (x + 9, gy - 15)], NEAR)
    L.hline(x + 1, gy - 12, 7, SHADE)
    L.vline(x + 4, gy - 20, 1, NEAR)


def _crane(L: Canvas, x: int, gy: int) -> None:
    """Портальный кран 18 px: две ноги-рамы, решётчатая балка с кабиной, трос с крюком."""
    h = 15
    for lx in (x + 1, x + 10):
        L.vline(lx, gy - h, h, NEAR)
        L.line(lx - 1, gy - 1, lx, gy - 5, NEAR)
    L.hline(x, gy - h - 1, 18, NEAR)  # балка
    L.hline(x, gy - h - 3, 18, NEAR)
    for i in range(0, 18, 2):
        L.dot(x + i, gy - h - 2, NEAR)
    L.rect(x + 4, gy - h + 0, 3, 3, NEAR)  # кабина
    L.dot(x + 5, gy - h + 1, "lamp0")
    L.vline(x + 15, gy - h, 6, SHADE)  # трос
    L.hline(x + 14, gy - h + 6, 3, NEAR)  # крюковая обойма
    L.dot(x + 15, gy - h + 7, NEAR)


def _gasholder(L: Canvas, x: int, gy: int, fx: _FX) -> None:
    """Газгольдер ближнего плана 15 px: цилиндр с поясами и бликом зарева в решётке направляющих колонн,
    сигнальный огонь на верхнем кольце."""
    h = 11
    L.rect(x + 1, gy - h, 13, h, NEAR)
    L.hline(x + 2, gy - h - 1, 11, NEAR)
    L.vline(x + 12, gy - h + 1, h - 1, SHADE)
    L.vline(x + 11, gy - h + 1, h - 1, SHADE)
    L.vline(x + 4, gy - h + 1, h - 1, _pick(_RIM, L))  # блик зарева на боку цилиндра
    for j in (gy - h + 3, gy - h + 7):  # пояса-ступени телескопа
        L.hline(x + 1, j, 13, SHADE)
    for i in (0, 5, 9, 14):  # направляющие колонны и верхнее кольцо
        L.vline(x + i, gy - h - 4, h + 4, NEAR)
    L.hline(x, gy - h - 4, 15, NEAR)
    for i in (0, 5, 9):
        L.line(x + i, gy - h - 4, x + i + (5 if i < 9 else 5), gy - h + 1, NEAR)
    fx.front.append(lambda c: c.dot(x + 7, gy - h - 5, "red2"))


def _near_default(L: Canvas, gy: int, fx: _FX) -> None:
    """Промзона: цеха с пилообразными крышами и светящимся остеклением, кирпичные корпуса, трубы с дымом,
    газгольдер, водонапорная башня или портальный кран, фонари. Застройка ниже дальнего плана и с
    просветами, чтобы за ней читался дальний город."""
    x = -L.rnd.randrange(0, 4)
    specials = {L.rnd.randrange(8, 44): "gas", L.rnd.randrange(64, W - 20): "tower"}
    crane = L.rnd.random() < 0.5
    while x < W:
        due = [k for k in specials if k <= x]
        if due:
            kind = specials.pop(due[0])
            if kind == "gas":
                _gasholder(L, x + 1, gy, fx)
                x += 18
            elif crane:
                _crane(L, x, gy)
                x += 19
            else:
                _water_tower(L, x, gy)
                x += 11
            continue
        bw, bh = L.rnd.randrange(7, 14), L.rnd.randrange(5, 12)
        if L.rnd.random() < 0.45:
            _hall(L, x, gy, bw, bh)
        else:
            _block(L, x, gy, bw, bh)
        if L.rnd.random() < 0.32:
            _chimney(L, x + L.rnd.randrange(1, max(2, bw - 3)), gy - bh - L.rnd.randrange(8, 14), gy - bh, fx,
                     bands=L.rnd.random() < 0.7)
        gap = L.rnd.randrange(0, 6)
        if gap >= 4 and L.rnd.random() < 0.6:
            _street_lamp(L, x + bw + 1, gy, fx)
        x += bw + gap


def _headframe(L: Canvas, x: int, gy: int, h: int, fx: _FX) -> None:
    """Копёр шахты (≈25 px с машинным зданием): башня-ферма с X-раскосами, площадка с перилами, шкив со
    спицами на стойках, наклонный подкос к машинному зданию, трос; у здания двускатная крыша и горящие
    окна; красный огонь над шкивом."""
    _truss(L, x + 1, gy, h, NEAR, base=9, top=5, panel=4)
    top = gy - h
    L.hline(x + 1, top, 9, NEAR)  # площадка с перилами
    L.dot(x + 1, top - 1, NEAR)
    L.dot(x + 9, top - 1, NEAR)
    L.line(x + 3, top - 1, x + 5, top - 3, NEAR)  # стойки шкива
    L.line(x + 7, top - 1, x + 5, top - 3, NEAR)
    _wheel(L, x + 5, top - 5, 3, NEAR, hub="brass0")
    L.line(x + 9, top, x + 16, gy - 9, NEAR)  # подкос к машинному зданию
    L.line(x + 9, top + 1, x + 16, gy - 8, NEAR)
    L.line(x + 8, top - 6, x + 17, gy - 12, SHADE)  # трос со шкива
    L.rect(x + 14, gy - 9, 10, 9, NEAR)  # подъёмная машина
    L.poly([(x + 13, gy - 9), (x + 19, gy - 13), (x + 25, gy - 9)], NEAR)
    L.vline(x + 23, gy - 8, 8, SHADE)
    L.windows(x + 16, gy - 7, 3, 1, ww=1, wh=2, gx=1, lit=0.75, on=("lamp1", "lamp2"), off=SHADE)
    fx.front.append(lambda c: halo(c, x + 5, top - 9, 2, [(70, 34, 40)]))
    fx.front.append(lambda c: c.dot(x + 5, top - 9, "red2"))


def _spoil_heap(L: Canvas, x: int, gy: int, hw: int, fx: _FX) -> None:
    """Терриконик: конус с теневым склоном, осыпь камней, наклонный путь скипа с вагонеткой, тлеющие
    угли у вершины с тонкой струйкой дыма."""
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
    if hw >= 9:  # тлеющие угли и дымок
        for dx, dy in ((1, 2), (3, 4), (-1, 3)):
            L.dot(x + hw + dx, gy - hh + dy, "red0")
        L.dot(x + hw + 1, gy - hh + 2, "fire0")
        fx.front.append(lambda c: _plume(c, x + hw + 1, gy - hh - 1, 10, _pick(_FAR, c)[2]))


def _furnace_shed(L: Canvas, x: int, gy: int, fx: _FX) -> None:
    """Плавильный цех: корпус с фонарём на крыше, раскалённые окна и ворота, отблеск огня на земле."""
    L.rect(x, gy - 10, 14, 10, NEAR)
    L.hline(x - 1, gy - 10, 16, NEAR)
    L.rect(x + 4, gy - 12, 6, 2, NEAR)
    L.vline(x + 13, gy - 9, 9, SHADE)
    for i in (2, 5, 8, 11):
        L.vline(x + i, gy - 8, 2, "fire1")
        L.dot(x + i, gy - 8, "fire2")
    L.rect(x + 5, gy - 4, 3, 4, "fire1")
    L.vline(x + 6, gy - 3, 3, "fire2")
    L.dot(x + 6, gy - 1, "fire3")
    L.hline(x + 5, gy - 11, 4, "fire0")
    fx.front.append(lambda c: halo(c, x + 6, gy - 3, 8, [(70, 40, 44), (104, 54, 46), "fire0"]))
    fx.front.append(lambda c: halo(c, x + 7, gy - 12, 4, [(70, 40, 44), (104, 54, 46)]))
    _chimney(L, x + 10, gy - 22, gy - 10, fx, bands=True, smoke_n=6)


def _barracks(L: Canvas, x: int, gy: int, bw: int) -> None:
    """Барак шахтёров: низкий дом с двускатной крышей, печной трубой и парой окон."""
    bh = L.rnd.randrange(5, 8)
    _block(L, x, gy, bw, bh, 0.45, roof=False)
    L.poly([(x - 1, gy - bh), (x + bw // 2, gy - bh - 4), (x + bw, gy - bh)], NEAR)
    L.rect(x + bw - 3, gy - bh - 4, 1, 3, NEAR)


def _near_rust(L: Canvas, gy: int, fx: _FX) -> None:
    """Шахтёрский город: копры со шкивами, терриконы, плавильный цех, трубы в красных полосах, бараки."""
    order = ["head", "heap", "shed", "block", "head", "heap", "block", "stack"]
    L.rnd.shuffle(order)
    x = -L.rnd.randrange(0, 6)
    i = 0
    while x < W:
        kind = order[i % len(order)]
        i += 1
        if kind == "head":
            _headframe(L, x, gy, L.rnd.randrange(14, 19), fx)
            x += 27
        elif kind == "heap":
            hw = L.rnd.randrange(7, 12)
            _spoil_heap(L, x, gy, hw, fx)
            x += 2 * hw - 2
        elif kind == "shed":
            _furnace_shed(L, x, gy, fx)
            x += 16
        elif kind == "stack":
            _chimney(L, x + 1, gy - L.rnd.randrange(18, 24), gy, fx)
            x += 6
        else:
            bw = L.rnd.randrange(7, 11)
            _barracks(L, x, gy, bw)
            x += bw + L.rnd.randrange(1, 3)


def _flare(c: Canvas, fx_: int, fy: int, big: bool = True) -> None:
    """Пламя факела: 4 тона огня, язык сносит ветром вправо, искра над пламенем."""
    lick = c.rnd.choice((0, 1, 1))
    c.sprite(fx_ - 2, fy - 5, [
        "..0..",
        ".010.",
        ".121.",
        "01310",
        ".020.",
    ] if big else [".0.", "010", "121", ".2."], {"0": "fire0", "1": "fire1", "2": "fire2", "3": "fire3"})
    c.dot(fx_ + lick, fy - 6, "fire1")
    c.dot(fx_ + lick + 1, fy - 7, "fire0")
    c.dot(fx_ + lick + 2, fy - 9, "fire1")  # искра


def _derrick(L: Canvas, x: int, gy: int, h: int, fx: _FX) -> None:
    """Нефтяная вышка (≈19 px с будкой и факелом): решётка, кронблок с огнём, будка бурильщика;
    рядом факельная труба 2 px с горящим факелом — жар за силуэтами и марево."""
    _truss(L, x, gy, h, NEAR, base=11, top=3, panel=5)
    top = gy - h
    L.rect(x + 4, top - 2, 3, 2, NEAR)  # кронблок
    L.vline(x + 5, top - 4, 2, NEAR)
    L.rect(x - 4, gy - 5, 5, 5, NEAR)  # будка бурильщика
    L.hline(x - 5, gy - 5, 7, NEAR)
    L.dot(x - 3, gy - 3, "lamp1")
    L.dot(x - 3, gy - 2, "lamp0")
    sh = h * 2 // 3
    L.rect(x + 12, gy - sh, 2, sh, NEAR)  # факельная труба
    L.vline(x + 13, gy - sh + 1, sh - 1, SHADE)
    L.hline(x + 11, gy - sh, 4, NEAR)
    fx.back.append(lambda c: halo(c, x + 12, gy - sh - 3, 13, _FIRE_HALO))
    fx.front.append(lambda c: halo(c, x + 12, gy - sh - 3, 5, [(150, 70, 50)]))
    fx.front.append(lambda c: _flare(c, x + 12, gy - sh - 1))
    fx.front.append(lambda c: c.dot(x + 5, top - 5, "red2"))


def _tank(L: Canvas, x: int, gy: int, w: int, h: int, fx: _FX) -> None:
    """Резервуар: цилиндр с контровым светом зарева по левому боку (к середине тает дизером — бок
    круглый) и теневым правым боком, пологий купол, пояса, винтовая лестница с перилами, ржавые потёки
    из-под верхнего пояса, красный огонь на вентиляционной трубе."""
    rim, band = (84, 46, 46), (58, 34, 41)
    L.rect(x, gy - h, w, h, NEAR)
    L.hline(x + 1, gy - h - 1, w - 2, NEAR)
    L.hline(x + 3, gy - h - 2, w - 6, NEAR)
    hx = x + 1  # контровой свет зарева по левому боку (край силуэта остаётся тёмным), к середине тает
    for j in range(gy - h, gy):
        L.dot(hx, j, rim)
        L.dot(hx + 1, j, band if L.threshold(hx + 1, j, "checker") < 0.5 else rim)
        if L.threshold(hx + 2, j, "bayer4") < 0.3:
            L.dot(hx + 2, j, band)
        if L.threshold(x + w - 3, j, "checker") < 0.5:
            L.dot(x + w - 3, j, SHADE)
    L.hline(x + 2, gy - h - 1, 3, rim)  # блик на кромке купола
    L.vline(x + w - 1, gy - h, h, SHADE)
    L.vline(x + w - 2, gy - h + 1, h - 1, SHADE)
    for j in (gy - h + 2, gy - 3):  # пояса: на освещённом боку — тёмный обод
        L.hline(x, j, w, SHADE)
        L.hline(hx, j, 3, band)
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
    fx.front.append(lambda c: c.dot(x + w // 2, gy - h - 4, "red1"))


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


def _nodding_donkey(L: Canvas, x: int, gy: int) -> None:
    """Силуэт станка-качалки 12 px: рама, балансир с головой, противовес."""
    L.line(x + 3, gy - 1, x + 6, gy - 7, NEAR)
    L.line(x + 9, gy - 1, x + 6, gy - 7, NEAR)
    L.hline(x + 1, gy - 8, 11, NEAR)  # балансир
    L.rect(x, gy - 9, 2, 4, NEAR)  # голова
    L.vline(x, gy - 5, 4, SHADE)  # шток
    L.rect(x + 9, gy - 5, 3, 3, NEAR)  # противовес
    L.hline(x, gy - 1, 12, NEAR)


def _near_mazut(L: Canvas, gy: int, fx: _FX) -> None:
    """Нефтепромысел: вышки с факелами и маревом, резервуары с лестницами и потёками, трубопроводы,
    качалки."""
    x = -L.rnd.randrange(0, 4)
    last = ""
    while x < W:
        r = L.rnd.random()
        if r < 0.36 and last != "derrick":
            _derrick(L, x + 5, gy, L.rnd.randrange(18, 26), fx)
            x += 21
            last = "derrick"
        elif r < 0.7 and last != "tank":
            w, h = L.rnd.randrange(13, 20), L.rnd.randrange(8, 13)
            _tank(L, x, gy, w, h, fx)
            x += w + 1
            last = "tank"
        elif r < 0.84 and last != "donkey":
            _nodding_donkey(L, x + 1, gy)
            x += 14
            last = "donkey"
        else:
            w = L.rnd.randrange(6, 12)
            _pipeline(L, x, gy, w)
            x += w
            last = "pipe"


def _clock_tower(L: Canvas, x: int, gy: int, fx: _FX) -> None:
    """Часовая башня столицы (13 px, ~52 высотой): цоколь, ствол с пилястрами и окнами, часовой ярус со
    светящимся циферблатом (ореол за башней — ярус чётко встаёт на фоне света), звонница с арками,
    шпиль с огнём."""
    w = 13
    L.rect(x, gy - 5, w, 5, NEAR)  # цоколь
    L.hline(x - 1, gy - 5, w + 2, NEAR)
    L.rect(x + 1, gy - 24, w - 2, 19, NEAR)  # ствол
    L.vline(x + w - 2, gy - 23, 18, SHADE)
    L.vline(x + 3, gy - 23, 18, SHADE)  # пилястры
    L.vline(x + 9, gy - 23, 18, SHADE)
    for j in range(gy - 21, gy - 7, 4):
        L.vline(x + 6, j, 2, "lamp1" if (j // 4) % 2 else "lamp0")
        L.dot(x + 6, j, "lamp2" if (j // 4) % 2 else "lamp1")
    L.rect(x + 5, gy - 4, 3, 4, "lamp0")  # вход
    L.vline(x + 6, gy - 3, 3, "lamp1")
    L.rect(x, gy - 35, w, 11, NEAR)  # часовой ярус
    L.hline(x - 1, gy - 24, w + 2, NEAR)  # карнизы
    L.hline(x - 1, gy - 35, w + 2, NEAR)
    L.dot(x - 1, gy - 36, NEAR)
    L.dot(x + w, gy - 36, NEAR)
    L.vline(x + w - 1, gy - 34, 10, SHADE)
    L.rect(x + 2, gy - 41, w - 4, 6, NEAR)  # звонница
    for i in (4, 6, 8):
        L.vline(x + i, gy - 39, 3, "lamp0")
        L.dot(x + i, gy - 39, "lamp1")
    L.vline(x + w - 3, gy - 40, 5, SHADE)
    L.poly([(x + 1, gy - 41), (x + 6, gy - 49), (x + 7, gy - 49), (x + 12, gy - 41)], NEAR)  # шпиль
    L.vline(x + 7, gy - 47, 6, SHADE)
    L.vline(x + 6, gy - 52, 3, NEAR)
    dx, dy = x + 6, gy - 30

    def back(c: Canvas) -> None:
        halo(c, dx, dy, 14, [(52, 48, 66), (74, 62, 70), (104, 80, 70)])

    def dial(c: Canvas) -> None:
        halo(c, dx, dy, 6, [(92, 72, 62)])
        c.disk(dx, dy, 4, "brass1")  # обод
        for ox, oy in ((2, 4), (3, 3), (4, 2), (4, 1), (1, 4)):
            c.dot(dx + ox, dy + oy, "brass0")
        c.disk(dx, dy, 3, "lamp2")  # светящееся стекло
        for ox, oy in ((1, 3), (2, 2), (3, 1), (0, 3), (3, 0), (2, 3), (3, 2)):
            if c.in_disk(ox, oy, 3):
                c.dot(dx + ox, dy + oy, "lamp1")
        for ox, oy in ((0, -3), (3, 0), (0, 3), (-3, 0)):  # метки 12, 3, 6, 9
            c.dot(dx + ox, dy + oy, "lamp0")
        c.vline(dx, dy - 2, 2, "k")  # минутная — на 12
        c.hline(dx + 1, dy, 2, "k")  # часовая — на 3
        c.dot(dx, dy, "brass2")
        c.dot(dx, gy - 53, "red2")

    fx.back.append(back)
    fx.front.append(dial)


def _city_block(L: Canvas, x: int, gy: int, bw: int, bh: int, fx: _FX) -> None:
    """Доходный дом столицы: сетка окон, теневая грань, одна из крыш — мансарда со слуховым окном,
    двускатная с печными трубами, купол со шпилем, плоская с баком или антенной; иногда — вертикальная
    вывеска и фонарь у подъезда."""
    top = gy - bh
    L.rect(x, top, bw, bh, NEAR)
    L.vline(x + bw - 1, top + 1, bh - 1, SHADE)
    r = L.rnd.random()
    if r < 0.3:  # карниз и мансарда со слуховым окном
        L.hline(x - 1, top, bw + 2, NEAR)
        L.poly([(x + 1, top), (x + 2, top - 3), (x + bw - 3, top - 3), (x + bw - 2, top)], NEAR)
        if bw > 7:
            L.dot(x + bw // 2, top - 2, "lamp1")
    elif r < 0.5:  # двускатная крыша с печными трубами
        L.poly([(x - 1, top), (x + bw // 2, top - bw // 2), (x + bw, top)], NEAR)
        L.rect(x + bw - 3, top - bw // 2, 1, bw // 2, NEAR)
        L.rect(x + 1, top - 2, 1, 2, NEAR)
    elif r < 0.62 and bw >= 8:  # купол со шпилем
        L.hline(x - 1, top, bw + 2, NEAR)
        L.disk(x + bw // 2, top, bw // 2 - 2, NEAR)
        L.vline(x + bw // 2, top - bw // 2 - 2, 3, NEAR)
    elif r < 0.8:  # бак на крыше
        L.rect(x + 1, top - 4, 4, 3, NEAR)
        L.dot(x + 1, top - 1, NEAR)
        L.dot(x + 4, top - 1, NEAR)
        L.vline(x + 4, top - 4, 3, SHADE)
    else:  # антенна
        L.vline(x + bw - 3, top - 6, 6, NEAR)
        L.hline(x + bw - 4, top - 4, 3, NEAR)
    L.windows(x + 1, top + 2, (bw - 2) // 2, (bh - 5) // 3, ww=1, wh=2, gx=1, gy=1, lit=0.34,
              on=("lamp1", "lamp2"), off=SHADE)
    if bh > 15 and L.rnd.random() < 0.22:  # вертикальная вывеска на кронштейне: буквы-огни
        sx, sy = x + bw, top + 3
        L.vline(sx, sy - 1, 9, "k")
        L.dot(sx - 1, sy - 1, "k")
        for k in range(0, 7, 2):
            L.dot(sx, sy + k, "red2" if k % 4 == 0 else "lamp2")
            L.dot(sx, sy + k + 1, (90, 36, 40) if k % 4 == 0 else "lamp0")
    if L.rnd.random() < 0.3 and bw > 4:
        _street_lamp(L, x + bw - 1, gy, fx, h=7)


def _near_kotlo(L: Canvas, gy: int, fx: _FX) -> None:
    """Столица: плотная застройка доходных домов с сетками окон и разными крышами, фонари вдоль улицы и
    часовая башня в центре."""
    tower_at = W // 2 - 6
    x = -L.rnd.randrange(0, 4)
    while x < W:
        if x + 13 > tower_at and x < tower_at + 13:
            _clock_tower(L, tower_at, gy, fx)
            x = tower_at + 14
            continue
        bw, bh = L.rnd.randrange(7, 13), L.rnd.randrange(12, 24)
        bw = min(bw, max(4, tower_at - x - 1)) if x < tower_at else bw
        _city_block(L, x, gy, bw, bh, fx)
        x += bw + L.rnd.randrange(0, 2)


# --- Земля, дорога, рельсы -----------------------------------------------------------------------------


def ground(c: Canvas, gy: int = GY) -> None:
    """Земля: освещённая заревом кромка, темнеющие к зрителю полосы, пара колей с подсвеченными бровками,
    галька с бликом и тенью (крупнее ближе к зрителю), сухая трава, лужи с отражением неба; по локации —
    куски руды и угля, мазутные пятна, мостовая плитка столицы с обрывками афиш, по умолчанию — лом."""
    h = c.h - gy
    edge = _pick(_EDGE, c)
    _bands(c, 0, gy, W, h, ["ground2", "ground1", "ground0"], (0.0, 0.2, 0.78), blend=3)
    c.hline(0, gy, W, edge)
    c.dither(0, gy + 1, W, 1, None, edge, 0.3, "bayer4")
    if c.theme == "kotlo":
        _flagstones(c, gy + 2, h - 2)
    else:
        _ruts(c, gy + 5 + c.rnd.randrange(0, 3))
    for _ in range(int(h * 1.8) if h > 3 else 0):  # галька: светлый верх, тень снизу; ближе к зрителю — крупнее
        x, y = c.rnd.randrange(W), c.rnd.randrange(gy + 2, c.h)
        c.dot(x, y, "ground2")
        c.dot(x, y + 1, "ground0")
        if y > gy + h // 2 and c.rnd.random() < 0.5:
            c.dot(x + 1, y, PEBBLE)
            c.dot(x + 1, y + 1, "ground1")
            c.dot(x + 2, y + 1, "ground0")
    _debris(c, gy, h)
    if c.theme in (None, "rust"):  # сухая трава у кромки пустыря
        for _ in range(8):
            _tuft(c, c.rnd.randrange(2, W - 2), c.rnd.randrange(gy + 2, gy + 6))
    if c.theme == "mazut" and h >= 6:
        for _ in range(3):
            _oil_stain(c, c.rnd.randrange(4, W - 8), c.rnd.randrange(gy + 3, c.h - 2), c.rnd.randrange(4, 9))
    for _ in range((2 if c.theme != "mazut" else 1) if h >= 9 else 0):
        puddle(c, c.rnd.randrange(4, W - 14), c.rnd.randrange(gy + 5, c.h - 3), c.rnd.randrange(8, 15))


def _ruts(c: Canvas, y0: int) -> None:
    """Пара колей через всю сцену: тёмная борозда, бровка над ней подсвечена заревом, местами разрывы."""
    phase = c.rnd.random() * 6.28
    gaps = {c.rnd.randrange(W) for _ in range(4)}
    for x in range(W):
        if any(g <= x < g + 6 for g in gaps):
            continue
        y = y0 + round(math.sin(x / 19 + phase) * 0.8)
        for yy in (y, y + 3):
            c.dot(x, yy, "ground0")
            if c.threshold(x, yy - 1, "checker") < 0.5:
                c.dot(x, yy - 1, "ground2")


def _debris(c: Canvas, gy: int, h: int) -> None:
    """Мелочь на земле по локации: куски руды и угля, мусор столицы, лом и щепа пустыря."""
    for _ in range(int(h * 0.9) if h >= 5 else 0):
        x, y = c.rnd.randrange(1, W - 3), c.rnd.randrange(gy + 3, c.h - 1)
        k = c.rnd.random()
        if c.theme == "rust":
            if k < 0.55:  # кусок руды: блик, тело, тень
                c.dot(x, y, "ore2")
                c.dot(x + 1, y, "ore1")
                c.dot(x + 1, y + 1, "ore0")
            else:  # уголь
                c.dot(x, y, "coal2")
                c.dot(x + 1, y, "coal0")
        elif c.theme == "mazut":
            c.dot(x, y, "oil0" if k < 0.6 else "oil2")
        elif c.theme == "kotlo":
            if k < 0.25:  # обрывок афиши
                c.dot(x, y, "paper0")
                c.dot(x + 1, y, (120, 104, 86))
            else:
                c.dot(x, y, "steel0")
        else:
            if k < 0.3:  # гайка
                c.dot(x, y, "steel1")
                c.dot(x, y + 1, "steel0")
            elif k < 0.5:  # щепа
                c.hline(x, y, 3, "wood0")
                c.dot(x, y, "wood1")
            else:
                c.dot(x, y, "rust0")


def _tuft(c: Canvas, x: int, y: int) -> None:
    """Пучок сухой травы 3×3: светлые травинки веером, тёмный корень."""
    c.dot(x, y, GRASS[0])
    c.dot(x - 1, y - 1, GRASS[1])
    c.dot(x + 1, y - 1, GRASS[2])
    c.dot(x, y - 2, GRASS[2] if (x + y) % 2 else GRASS[1])


def _flagstones(c: Canvas, y: int, h: int) -> None:
    """Мостовая плитка столицы: ряды плит в перевязку, к зрителю ряды выше (перспектива); у каждой плиты
    светлая верхняя кромка, тёмный шов, часть плит стёрта светлее."""
    j, row, rh = y, 0, 1
    while j < y + h:
        off = (row * 5) % 9
        c.hline(0, j, W, "ground0")  # шов между рядами
        for x in range(-off, W, 9):
            worn = (x // 9 + row * 3) % 4 == 0
            c.hline(x + 1, j + 1, 8, PEBBLE if worn else (52, 45, 50))  # верхняя кромка плиты
            for k in range(1, rh + 1):
                c.dot(x, j + k, "ground0")  # вертикальный шов
        j += rh + 1
        row += 1
        rh = min(rh + 1, 4)


def puddle(c: Canvas, x: int, y: int, w: int = 10, glint="haze2") -> None:
    """Лужа шириной w (3 строки): вода отражает небо «вверх ногами» — у дальнего края зарево горизонта,
    ближе ночная синева, рябь дизером; мокрая тёмная кромка, светлая бровка и блик-отражение огня."""
    bands = _pick(_SKY, c)
    rows = ((2, bands[-1], _pick(_EDGE, c)), (0, bands[-2], bands[-1]), (1, bands[-4], bands[-3]))
    for j, (inset, body, refl) in enumerate(rows):
        c.hline(x + inset, y + j, w - 2 * inset, body)
        for i in range(inset + 1, w - inset - 1):
            if c.threshold(x + i, y + j, "bayer4") < (0.45 if j < 2 else 0.25):
                c.dot(x + i, y + j, refl)
    c.hline(x + 3, y - 1, w - 6, PEBBLE)  # бровка, подсвеченная сверху
    c.hline(x + 2, y + 3, w - 4, "ground0")  # мокрая тень у ближнего края
    c.dot(x + 1, y, "ground0")
    c.dot(x + w - 2, y, "ground0")
    gx = x + w // 3 + c.rnd.randrange(max(1, w // 3))
    c.hline(gx, y + 1, 2, glint)  # блик-отражение
    c.dot(gx, y, "white" if glint == "haze2" else glint)
    c.dot(gx + 3, y + 1, bands[-1])


def _oil_stain(c: Canvas, x: int, y: int, w: int) -> None:
    """Мазутное пятно: чёрная клякса в 3 строки с радужной плёнкой и бликом."""
    c.hline(x + 1, y, w - 2, "oil1")
    c.hline(x, y + 1, w, "oil0")
    c.hline(x + 2, y + 2, max(1, w - 4), "oil1")
    m = x + w // 2
    c.dot(m - 1, y + 1, SHEEN[0])
    c.dot(m, y + 1, SHEEN[1])
    if w > 5:
        c.dot(m + 1, y + 1, SHEEN[2])
        c.dot(m - 2, y, "oil2")


def road(c: Canvas, y: int = 58, h: int = 8) -> None:
    """Булыжная дорога высотой h от строки y: дальний бордюр со стыками, водосток, мостовая из камней 3×2
    в перевязку (блик сверху-слева, тень снизу-справа, тёмные и стёртые камни вперемешку), затёртая
    разметка посередине, мазутные пятна с плёнкой, ближний бордюр. По локации: рыжая рудная пыль в
    шахтёрском городе, больше мазута на нефтепромысле, яркая разметка в столице."""
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
            if v == 1 and col == "road0" and k != 3:
                col = "road1"
            c.dot(x, j, col)
    bright = c.theme == "kotlo"
    for x in range(c.rnd.randrange(4), W, 12):  # затёртая разметка: краска осталась пятнами
        for i in range(6):
            if (x + i) * 5 % 7 != 0 or bright:
                c.dot(x + i, mid, "line")
        if bright:
            c.dot(x, mid, (140, 126, 96))
    dust = {"rust": ["ore0", "ore1"], "mazut": ["oil0"], "kotlo": []}.get(c.theme, ["ground2"])
    if dust:
        c.speckle(0, y + 2, W, h - 3, dust, 26)
    for _ in range(5 if c.theme == "mazut" else 3):
        sx = c.rnd.randrange(2, W - 8)
        _oil_stain(c, sx, y + 2 + c.rnd.randrange(max(1, h - 5)), c.rnd.randrange(3, 8))
    edge = _pick(_EDGE, c)
    for _ in range(3):  # мокрый булыжник отражает зарево: короткие дизерные блики по верху камней
        rx, ry = c.rnd.randrange(0, W - 10), y + 2 + 2 * c.rnd.randrange(max(1, (h - 3) // 2))
        for i in range(c.rnd.randrange(5, 11)):
            if c.threshold(rx + i, ry, "checker") < 0.5 and ry != mid:
                c.dot(rx + i, ry, edge)
    c.hline(0, y + h - 1, W, "road2")  # ближний бордюр
    for x in range(c.rnd.randrange(8), W, 8):
        c.dot(x, y + h - 1, "road0")


def rails(c: Canvas, y: int = 62) -> None:
    """Пути: y — головка дальнего рельса (на неё встают колёса). Насыпь из щебня в 3 тона с подсвеченным
    гребнем, шпалы с бликом и тенью, подкладки и костыли, два рельса (головка, шейка, подошва с тенью),
    неровные блики-отражения на головках, осыпь щебня по краю насыпи."""
    edge = _pick(_EDGE, c)
    c.rect(0, y - 1, W, 7, BALLAST[1])
    for x in range(W):  # гребень насыпи, подсвеченный заревом
        if c.threshold(x, y - 1, "bayer4") < 0.5:
            c.dot(x, y - 1, edge if c.threshold(x, y - 1, "bayer4") < 0.15 else BALLAST[2])
    for j in range(y, y + 6):  # щебень: светлые камешки сверху, тёмные щели
        for x in range(W):
            t = c.threshold(x + j // 4, j, "bayer4")
            if t < 0.28:
                c.dot(x, j, BALLAST[2])
            elif t > 0.8:
                c.dot(x, j, BALLAST[0])
    for x in range(c.rnd.randrange(2), W, 4):  # шпалы: блик сверху-слева, тень снизу-справа
        c.hline(x, y + 1, 3, "wood1")
        c.hline(x, y + 2, 3, "wood1")
        c.dot(x, y + 1, "wood2")
        c.dot(x + 1, y + 1, "wood2")
        c.dot(x + 2, y + 2, "wood0")
        c.hline(x, y + 3, 3, "wood0")
        c.dot(x + 1, y + 1, "steel1")  # подкладка под дальний рельс
        c.dot(x + 1, y + 5, "steel0")  # костыль у подошвы ближнего
    c.hline(0, y, W, "steel2")  # дальний рельс
    c.hline(0, y + 1, W, "steel0")
    c.hline(0, y + 3, W, "steel2")  # ближний рельс: головка, шейка, подошва
    c.hline(0, y + 4, W, "steel1")
    c.hline(0, y + 5, W, "oil1")
    x = c.rnd.randrange(3)
    while x < W:  # неровные полосы блеска на головках
        ln = c.rnd.randrange(3, 9)
        c.hline(x, y + 3, ln, "steel3")
        c.dot(x + ln // 2, y + 3, "white")
        if c.rnd.random() < 0.5:
            c.hline(x + 2, y, max(1, ln - 4), "steel3")
        x += ln + c.rnd.randrange(4, 12)
    for x in range(W):  # осыпь щебня по краю насыпи
        if c.threshold(x, y + 6, "bayer4") < 0.45:
            c.dot(x, y + 6, BALLAST[1] if c.threshold(x, y + 6, "checker") < 0.5 else BALLAST[0])
    c.speckle(0, y + 6, W, 1, [BALLAST[2], "steel0"], 16)


# --- Фонари и дым --------------------------------------------------------------------------------------


def lamp_post(c: Canvas, x: int, gy: int, h: int = 16, flip: bool = False, lit: bool = True) -> None:
    """Уличный фонарь: x — столб, gy — земля у основания, h — высота (рекомендуется 14–20; занимает
    по ширине x-1 … x+5, при flip — x-5 … x+1). Чугунная тумба с цоколем, столб с кольцами и бликом,
    изогнутый «пастуший посох» с колпаком-колоколом и лампой в 3 px от столба (влево при flip).
    Горящий: плавный ореол в 3 кольца, дизерный конус света до земли и пятно света на земле."""
    d = -1 if flip else 1
    top = gy - h
    lx, ly = x + 3 * d, top + 3  # лампа под колпаком
    if lit:
        halo(c, lx, ly, 10, _LAMP_HALO)
        for j in range(ly + 2, gy):  # конус света: шире и прозрачнее к земле
            f = (j - ly - 2) / max(1, gy - ly - 2)
            hw = 1 + round(f * 4)
            _veil(c, lx - hw, j, 2 * hw + 1, 1, "haze1" if f < 0.5 else "haze0", 0.45 - 0.3 * f)
        halo(c, lx, gy, 7, ["haze0", "haze1"], ry=2)  # пятно света на земле
    c.rect(x - 1, gy - 3, 3, 3, "oil1")  # тумба
    c.hline(x - 2, gy - 1, 5, "oil1")  # цоколь
    c.dot(x - 2, gy - 1, "oil2")
    c.dot(x - 1, gy - 3, "oil2")
    c.vline(x + 1, gy - 3, 2, "oil0")
    c.dot(x + 2, gy - 1, "oil0")
    c.vline(x, top, h - 3, "oil2")  # столб
    if lit:  # отблеск лампы на стороне столба, обращённой к ней
        c.vline(x, top + 1, h // 3, "steel1")
        c.dot(x, top + 1, "steel2")
    for j in (top + h // 3 + 1, gy - 6):  # кольца
        c.dot(x, j, "steel2")
        c.dot(x - d, j, "oil1")
    c.dot(x, top - 1, "steel1")  # навершие
    c.dot(x, top - 2, "oil2")
    c.dot(x + d, top - 1, "oil2")  # изгиб посоха
    c.dot(x + 2 * d, top - 1, "oil2")
    c.dot(x + 3 * d, top, "oil2")
    c.dot(x + d, top + 1, "oil1")  # завиток под изгибом
    c.hline(min(lx - 1, lx + 1), top + 1, 3, "oil2")  # колпак-колокол
    c.dot(lx - d, top + 1, "steel1")
    c.hline(lx - 2, top + 2, 5, "oil1")
    c.dot(lx - 2 * d, top + 2, "oil2")
    c.dot(lx - 1, ly, "lamp1" if lit else "oil1")  # лампа
    c.dot(lx, ly, "lamp2" if lit else "oil2")
    c.dot(lx + 1, ly, "lamp1" if lit else "oil1")
    c.dot(lx, ly + 1, "lamp1" if lit else "oil0")
    if lit:
        c.dot(lx, ly, "white")


def smoke(c: Canvas, x: int, y: int, n: int = 5, tone: int = 2, ramp_name: str = "smog", drift: int = 1) -> None:
    """Дым из точки (x, y) вверх: клубы растут и сносятся ветром по дуге (drift — сила и сторона сноса),
    между соседними клубами — перемычка, так что дым идёт сплошным бугристым столбом.
    Каждый клуб освещён как шар светом сверху-слева, 3 тона: круглый блик смещён вверх-влево (у крупных
    клубов пара/дыма — со светлым ядром), полутон, тень по нижне-правому краю и по силуэту столба.
    Младший (нижний) клуб лежит поверх старшего. Клуб у устья темнее (сажа), верхний меньше и тает
    дизером от края к центру, над ним — оторвавшиеся клочки.
    tone 3 у «smog» — светлый пар (локальные тона светлее smog3). Высота столба при n=7 ≈ 26 px."""
    tones = _tones(ramp_name) + ([STEAM, STEAM_HI] if ramp_name == "smog" else [])

    def t(i: int):
        return tones[max(0, min(i, len(tones) - 1))]

    sign = 1 if drift >= 0 else -1
    puffs = []
    cy, prev = y, 0
    for i in range(n):
        r = min(1 + i // 2, 4)
        cy -= (prev + r - 1) if i else r
        cx = x + round(drift * (0.5 * i + 0.12 * i * i)) + sign * (1 if i % 2 else -1) * (i > 1)
        puffs.append((cx, cy, r))
        prev = r
    top_k = n - 1 if n > 3 else -1
    owner: dict[tuple[int, int], tuple[int, float, float]] = {}  # пиксель → (клуб, до блика, до центра)
    for k in range(n - 1, -1, -1):  # от старшего к младшему: младший перекрывает
        cx, cy, r = puffs[k]
        discs = [(cx, cy, r - (1 if k == top_k and r > 2 else 0))]
        if r >= 3 and k != top_k:  # боковой бугор: клуб не идеально круглый
            discs.append((cx + (r // 2 + 1) * (1 if (k + x) % 2 else -1), cy + 1, r - 2))
        if k > 0 and min(r, puffs[k - 1][2]) >= 2:  # перемычка к младшему клубу
            pcx, pcy, pr = puffs[k - 1]
            discs.append(((cx + pcx) // 2, (cy + pcy + 1) // 2, min(pr, r) - 1))
        for ox, oy, rr in discs:
            hx, hy = ox - rr * 0.4, oy - rr * 0.45  # блик шара — вверху слева
            for dy in range(-rr, rr + 1):
                for dx in range(-rr, rr + 1):
                    if c.in_disk(dx, dy, rr):
                        px, py = ox + dx, oy + dy
                        owner[(px, py)] = (k, math.hypot(px - hx, py - hy) / (rr + 0.5),
                                           math.hypot(dx, dy) / (rr + 0.5))
    base_b = max(1, min(tone, len(tones) - 2))
    for (px, py), (k, dh, d) in owner.items():
        if k == top_k and c.threshold(px, py, "bayer4") > 1.3 - 1.15 * d:
            continue  # верхний клуб тает: плотная серёдка, редеющий край
        r = puffs[k][2]
        b = base_b - (1 if k == 0 else 0)
        hi, mid, lo = t(b + 1), t(b), t(b - 1)
        ch = c.threshold(px, py, "checker") < 0.5
        edge = (px + 1, py) not in owner or (px, py + 1) not in owner  # нижне-правый силуэт столба
        if r == 1:
            col = hi if dh < 0.7 else (lo if edge else mid)
        elif dh < 0.3 and r >= 3 and tone >= 2:
            col = t(b + 2)  # светлое ядро блика
        elif dh < 0.62:
            col = hi
        elif dh > 1.18 or edge or (dh > 1.0 and ch):
            col = lo
        else:
            col = mid
        c.dot(px, py, col)
    if n > 4:  # оторвавшиеся клочки над столбом
        cx, cy, r = puffs[-1]
        for dx, dy in ((drift * 2 + 1, -r - 1), (drift * 2 + 2, -r - 1), (drift * 3 - 1, -r - 3)):
            c.dot(cx + dx, cy + dy, t(base_b - 1))


def backdrop(c: Canvas, gy: int = GY, smoggy: bool = True, horizon: bool = True) -> None:
    """Типовой фон уличной сцены: небо, оба слоя горизонта (если horizon), земля."""
    sky(c, gy, smoggy)
    if horizon:
        skyline(c, gy)
    ground(c, gy)
