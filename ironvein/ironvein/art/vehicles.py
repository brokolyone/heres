"""Транспорт: колёса, грузовики всех окрасок и кузовов, паровоз, вагоны, поезд, вагонетка.

Машины рисуются на прозрачном слое лицом вправо и кладутся на холст через Canvas.paste — так flip
(едет влево) зеркалит всю машину целиком. Контактные тени, конус и ореол фары, дым и пар рисуются уже
на холсте, поверх фона.

Окраска задаётся ролями тонов, а не цветами: 0 — глубокая тень, 1 — тень, 2 — основной, 3 — блик,
4 — искра блика. Кабина грузовика — ручная пиксельная карта (_CAB) из символов-ролей, поэтому одна
и та же форма перекрашивается в ржавчину, сталь, латунь или чёрный лак. Крупные объёмы произвольной
формы (крылья, бронекузов) — «пятна» _blob: край — контур k, блик по верхней/левой кромке, тень по
нижней/правой, середина — основной тон. Свет всегда падает сверху-слева.
"""

import math

from ironvein.art.backgrounds import rails, smoke
from ironvein.art.canvas import RAMPS, Canvas, lum

TRUCK_W, TRUCK_H = 48, 34  # габарит грузовика вместе с грузом и трубой (дым и свет фары — на холсте)
LOCO_W, LOCO_H = 37, 28  # паровоз; низ колёс — уровень рельса
WAGON_W, WAGON_H = 28, 20  # вагон; низ колёс — уровень рельса

# Окраска грузовика: (рампа кабины, рампа кузова, рампа отделки)
PAINTS = {
    "rust": ("rust", "wood", "steel"),
    "steel": ("steel", "wood", "steel"),
    "brass": ("brass", "wood", "steel"),
    "black_brass": ("oil", "oil", "brass"),  # премиальная: чёрный лак и латунь
}

_N4 = ((1, 0), (-1, 0), (0, 1), (0, -1))
Cells = set[tuple[int, int]]
Tones = tuple[str, str, str, str, str]

# Роли тонов (глубокая тень, тень, основной, блик, искра) для каждой рампы. У чёрного лака блик
# холодный стальной — иначе чёрная машина сливается с ночным фоном.
_TONES: dict[str, Tones] = {
    "rust": ("rust0", "rust1", "rust2", "rust3", "brass3"),
    "steel": ("steel0", "steel1", "steel2", "steel3", "white"),
    "brass": ("brass0", "brass1", "brass2", "brass3", "white"),
    "oil": ("oil0", "oil1", "oil2", "steel1", "steel2"),
    "armor": ("oil1", "steel0", "steel1", "steel2", "steel3"),  # воронёная броня — сталь на тон темнее
    "wood": ("oil0", "wood0", "wood1", "wood2", "paper0"),
    "red": ("red0", "red0", "red1", "red2", "fire2"),
    "green": ("green0", "green0", "green1", "green2", "paper2"),
}


# --- Общие хелперы -------------------------------------------------------------------------------------


def _tones(name: str, shift: int = 0) -> Tones:
    """Пять ролей тона рампы; shift = -1 — та же краска на тон темнее (крылья, теневые детали)."""
    t = _TONES.get(name)
    if t is None:  # произвольная рампа: растягиваем её тона на пять ролей
        keys = [f"{name}{i}" for i in range(len(RAMPS[name]))]
        n = len(keys)
        t = (keys[0], keys[0], keys[min(1, n - 1)], keys[min(2, n - 1)], keys[-1]) if n == 3 else \
            (keys[0], keys[0], keys[1], keys[2], keys[3])
    if shift < 0:
        t = ("k", t[0], t[1], t[2], t[3])
    return t


def _span(*rows: tuple[int, int, int]) -> Cells:
    """Множество пикселей из строк (y, x0, x1), концы включительно."""
    return {(x, y) for y, x0, x1 in rows for x in range(x0, x1 + 1)}


def _blob(c: Canvas, cells: Cells, t: Tones, outline: str | None = "k", round_low: bool = False) -> None:
    """Объёмная деталь произвольной формы: край — outline, затем блик по верхней/левой кромке и тень по
    нижней/правой, середина — основной тон. round_low — нижняя треть дизером уходит в тень (скруглённая
    панель). outline=None — край тоже тонируется (деталь без контура)."""
    _, lo, base, hi, _ = t
    edge = {(x, y) for x, y in cells if any((x + a, y + b) not in cells for a, b in _N4)}
    inner = cells - edge if outline is not None else cells
    if not inner:
        return
    ys = [y for _, y in inner]
    y0, y1 = min(ys), max(ys)
    for x, y in cells:
        if outline is not None and (x, y) in edge:
            col = outline
        elif (x, y + 1) not in inner or (x + 1, y) not in inner:
            col = lo
        elif (x, y - 1) not in inner or (x - 1, y) not in inner:
            col = hi
        elif round_low and y > y0 + (y1 - y0) * 2 // 3 and c.threshold(x, y, "checker") < 0.5:
            col = lo
        else:
            col = base
        c.dot(x, y, col)


def _lighten(c: Canvas, x: int, y: int, col: str) -> None:
    """Положить цвет, только если он светлее того, что уже лежит (свет не затемняет)."""
    old = c.get(x, y)
    if old is not None and lum(old) < lum(c.rgb(col)):
        c.dot(x, y, col)


def _beam(c: Canvas, x: int, y: int, direction: int, length: int = 14) -> None:
    """Конус света фары от (x, y) в сторону direction (±1): тёплое ядро у стекла, расширяющийся к
    концу конус шахматкой и редеющим Байером. Только осветляет то, что уже нарисовано."""
    for i in range(length):
        far = i / length
        half = 1 + i * 2 // 5
        for dy in range(-half, half + 2):
            px, py = x + direction * i, y + dy
            core = abs(dy - 0.5) <= 1 + i // 6
            if core and far < 0.35:
                col, level = ("lamp2" if i < 2 else "lamp1"), (1.0 if i < 3 else 0.6)
            elif core and far < 0.7:
                col, level = "lamp0", 0.5
            else:
                col, level = ("lamp0" if far < 0.45 else "haze1"), 0.45 - far * 0.3
            if c.threshold(px, py, "bayer4") < level:
                _lighten(c, px, py, col)


def _light_pool(c: Canvas, x: int, y: int, direction: int, length: int = 12) -> None:
    """Пятно света фар на дороге впереди машины: вытянутый эллипс редкого дизера (только осветляет)."""
    for i in range(length):
        k = 1 - abs(i - length / 2) / (length / 2 + 1)
        for dy in (-1, 0, 1):
            level = 0.35 * k - 0.12 * abs(dy)
            px = x + direction * i
            if c.threshold(px, y + dy, "bayer4") < level:
                _lighten(c, px, y + dy, "haze1" if abs(dy) else "haze2")


def _contact_shadow(c: Canvas, x: int, y: int, w: int) -> None:
    """Контактная тень машины: сплошная строка под колёсами с рваными краями и дизер под днищем."""
    c.shadow(x, y + 1, w, "oil0")
    c.dither(x + 3, y + 2, w - 6, 1, None, "oil0", 0.5)
    c.dither(x + 2, y, w - 4, 1, None, "oil0", 0.5)


# --- Колесо --------------------------------------------------------------------------------------------


def wheel(c: Canvas, cx: int, cy: int, r: int = 3, hub: str = "steel", rim: str | None = None) -> None:
    """Колесо с центром (cx, cy) радиуса r (диаметр 2r+1) в контуре k.

    Покрышка: внешнее кольцо — шашки протектора, у r ≥ 4 ещё кольцо боковины с бликом сверху-слева.
    Диск — кольцо из рампы rim (по умолчанию сталь; можно ключ цвета), колпак 3×3 — выпуклый, из рампы
    hub (латунь у премиальной окраски). Свет сверху-слева: блик на верхне-левой дуге, тень на нижне-правой.
    """
    ht = _tones(hub) if (hub in RAMPS or hub in _TONES) else (hub,) * 5
    if rim is None:
        rt = _tones("steel")
    elif rim in RAMPS or rim in _TONES:
        rt = _tones(rim)
    else:
        rt = (rim,) * 5
    tyre = 2 if r >= 4 else 1
    for dy in range(-r - 1, r + 2):
        for dx in range(-r - 1, r + 2):
            x, y = cx + dx, cy + dy
            if not c.in_disk(dx, dy, r):
                if any(c.in_disk(dx + a, dy + b, r) for a, b in _N4):
                    c.dot(x, y, "k")
                continue
            d = math.hypot(dx, dy)
            lit = -(dx + dy) / (d * 1.41) if d else 0.0  # 1 — верх-лево, -1 — низ-право
            if not c.in_disk(dx, dy, r - tyre):  # покрышка
                outer = not c.in_disk(dx, dy, r - 1)
                ang = math.atan2(dy, dx)
                notch = outer and int((ang + math.pi) / (2 * math.pi) * (4 * r + 4)) % 2 == 0
                if lit > 0.45:
                    col = ("smog1" if notch else "smog2") if outer else "smog1"
                elif lit < -0.35:
                    col = ("oil1" if notch else "oil2") if outer else "oil1"
                else:
                    col = ("smog0" if notch else "smog1") if outer else "oil2"
            elif r >= 3 and not c.in_disk(dx, dy, 1):  # диск
                col = rt[3] if lit > 0.4 else (rt[1] if lit < -0.3 else rt[2])
                if lit > 0.85 and r >= 4:
                    col = rt[4]
            elif dx == 0 and dy == 0:  # колпак: центр
                col = ht[2] if r >= 3 else ht[1]
            elif r >= 3:  # колпак: выпуклый, блик сверху-слева, тень снизу-справа
                col = ht[3] if (dx + dy) <= -1 else (ht[0] if (dx + dy) >= 1 else ht[1])
            else:  # маленькое колесо: диск без колпака
                col = rt[3] if (dx + dy) < 0 else (rt[1] if (dx + dy) > 0 else rt[2])
            c.dot(x, y, col)


# --- Грузовик ------------------------------------------------------------------------------------------

_WY, _WR = 29, 4  # центр и радиус колёс грузовика на слое (низ колёс — последняя строка слоя)
_FWX = 39  # переднее колесо
_REAR = {"cargo": (7, 17), "armored": (7, 17), "light": (12,)}
_LAMP = (45, 16)  # стекло фары на слое (от него — конус света)

# Кабина и капот, x = 24…47, y = 4…22. Роли: k контур; 0–4 тона краски; a b c — стекло (тень → блик),
# w — блик на стекле; m — молдинг по поясу; Y T — хром/латунь отделки (решётка радиатора).
_CAB_X, _CAB_Y = 24, 4
_CAB = [
    "....kkkkkk..............",  # 4  крыша
    "..kk333333kk............",  # 5
    ".k332222222ck...........",  # 6  лобовое стекло в профиль (c/b/a у переднего края)
    ".k321111111bk...........",  # 7  рамка бокового окна
    ".k321bbcwb12bk..........",  # 8  боковое окно с двумя бликами
    ".k321bcwba12bk..........",  # 9
    ".k321cwbaa12bk..........",  # 10
    ".k321bbaaa12ak..........",  # 11
    ".k321111111223kkkkkkk...",  # 12 подоконник, капот начинается
    ".k3212222222223333333k..",  # 13 верх капота — блик
    ".k3mmmmmmmmmmmmmmmmmm3k.",  # 14 молдинг по поясу
    ".k32122222222122222222Yk",  # 15 шов двери, шов капота, решётка
    ".k3212YT22222103032222kk",  # 16 ручка двери, жалюзи капота
    ".k32122222222103032222Yk",  # 17
    ".k32122222222103032222kk",  # 18
    ".k32122222222122222221Yk",  # 19
    ".k32121212121121212121kk",  # 20 низ панелей скруглён дизером
    ".k31111111111011111110Yk",  # 21
    ".kkkkkkkkkkkkkkkkkkkkkkk",  # 22
]


def _truck_palette(paint: str, armored: bool) -> dict[str, str]:
    """Палитра ролей для карты кабины: тона краски, стекла, отделки."""
    cab, _, trim = PAINTS.get(paint, PAINTS["rust"])
    pt = _tones("armor" if armored else cab)
    tt = _tones(trim)
    brass = paint == "black_brass"
    return {
        "k": "k", "0": pt[0], "1": pt[1], "2": pt[2], "3": pt[3], "4": pt[4],
        "a": "glass0", "b": "glass1", "c": "glass2", "w": "white",
        "m": tt[2] if brass else (pt[3] if not armored else pt[1]),
        "t": tt[1], "T": tt[2], "Y": tt[3] if not armored else pt[1],
    }


def truck(c: Canvas, x: int, y: int, body: str = "cargo", paint: str = "rust", cargo: str | None = "crates",
          flip: bool = False, lights: bool = True, exhaust: bool = True) -> None:
    """Грузовик 1940-х в габарите TRUCK_W×TRUCK_H; x — левый край, y — низ колёс. Кабина справа, flip — влево.

    body: cargo (дощатый кузов, тандем задних колёс) | armored (бронекузов с башенкой) | light (короткий
    низкий кузов, одна задняя ось). paint: rust | steel | brass | black_brass.
    cargo: crates | barrels | ore | coal | None (у бронекузова груз не виден).
    lights — конус, ореол фары и пятно света на дороге; exhaust — сажа из выхлопной трубы.
    """
    lay = c.layer(TRUCK_W, TRUCK_H)
    _truck_body(lay, body, paint, cargo)
    top = y - (TRUCK_H - 1)
    d = -1 if flip else 1

    def X(px: int) -> int:
        return x + (TRUCK_W - 1 - px if flip else px)

    _contact_shadow(c, x + 1, y, TRUCK_W - 2)
    lx, ly = X(_LAMP[0]), top + _LAMP[1]
    if lights:
        _light_pool(c, X(TRUCK_W) + d * 2, y, d, 12)
        _beam(c, lx + 2 * d, ly, d, 15)
        c.glow(lx + d, ly, 4, ["haze1", "lamp0", "lamp1"])
    c.paste(lay, x, top, flip)
    if lights:
        c.dot(lx, ly, "white")
        c.dot(lx, ly + 1, "lamp2")
    if exhaust:  # сажа из трубы тянется назад
        smoke(c, X(23) - d, top - 1, 6, tone=1, drift=-d)
        c.dot(X(23), top + 1, "oil1")


def _truck_body(c: Canvas, body: str, paint: str, cargo: str | None) -> None:
    """Грузовик на слое TRUCK_W×TRUCK_H лицом вправо; низ колёс — последняя строка слоя."""
    armored, light = body == "armored", body == "light"
    cab, bed, trim = PAINTS.get(paint, PAINTS["rust"])
    brass = paint == "black_brass"
    pal = _truck_palette(paint, armored)
    pt = _tones("armor" if armored else cab)
    ft = _tones("armor" if armored else "oil")  # крылья — чёрные, как у грузовиков 1940-х
    tt = _tones(trim)

    # Рама и задний брызговик
    c.rect(0, 22, 46, 2, "oil1")
    c.hline(0, 22, 46, "k")
    c.hline(1, 23, 44, "oil2")
    for xx in range(3, 44, 5):
        c.dot(xx, 23, "steel1")  # болты рамы

    # Кузов и груз (за кабиной)
    if armored:
        _bed_armored(c)
    elif light:
        if cargo:
            _truck_cargo(c, cargo, 4, 16)
        _bed_slats(c, 3, 16, bed, tt, brass, posts=(3, 12, 20))
    else:
        if cargo:
            _truck_cargo(c, cargo, 0, 11)
        _bed_slats(c, 0, 11, bed, tt, brass, posts=(0, 10, 20))
    c.rect(0, 24, 2, 5, "oil1", "k")  # брызговик за задним колесом
    c.dot(0, 20, "red2")  # задний фонарь
    c.dot(0, 21, "red0")

    # Выхлопная труба за кабиной: закопчённый срез, побежалость от жара, хомуты
    c.rect(21, 1, 5, 2, "k")
    c.dot(22, 1, "steel1" if not brass else "brass2")
    c.vline(22, 3, 19, "k")
    for yy in range(3, 22):
        hot = yy < 7
        c.dot(23, yy, ("rust2" if yy < 5 else "brass1") if hot else (tt[3] if brass else "steel2"))
        c.dot(24, yy, ("rust0" if yy < 5 else "rust1") if hot else (tt[1] if brass else "steel1"))
    for yy in (9, 17):
        c.hline(22, yy, 3, "k")
        c.dot(23, yy, tt[4] if brass else "steel3")
        c.dot(24, yy, tt[2])

    # Колёса; ниша переднего колеса под крылом — тёмная
    fender, well = _fender_cells()
    for xx, yy in well:
        c.dot(xx, yy, "oil0")
    rear = _REAR[body if body in _REAR else "cargo"]
    for wx in (*rear, _FWX):
        wheel(c, wx, _WY, _WR, hub=trim, rim=cab if not armored else "armor")
    if not armored:  # задние крылья: короткие чёрные дуги над колёсами
        for wx in rear:
            for xx in range(wx - 5, wx + 6):
                yy = 24 if abs(xx - wx) <= 3 else 25
                c.dot(xx, yy, "k")
                if abs(xx - wx) <= 3:
                    c.dot(xx, yy - 1, tt[3] if brass else "steel0")
            c.dot(wx - 4, 24, "k")
            c.dot(wx + 4, 24, "k")
    if light:  # ящик с инструментом под кузовом
        c.rect(18, 23, 7, 4, "steel1", "k")
        c.hline(19, 24, 5, "steel2")
        c.dot(21, 25, tt[4])

    # Топливный бак под дверью
    _blob(c, _span((24, 27, 33), (25, 27, 33), (26, 27, 33), (27, 27, 33)), _tones("steel", -1) if not brass else ft)
    c.dot(28, 25, tt[3])
    c.dot(32, 25, "k")

    # Кабина и капот (ручная карта)
    c.sprite(_CAB_X, _CAB_Y, _CAB, pal)
    if armored:
        _cab_armor(c, pt)
    if brass:
        c.hline(27, 21, 18, tt[1])  # латунная полоса по низу
        c.dot(30, 16, tt[4])

    # Крыло над передним колесом и подножка: гребень с бликом, у премиальной — латунная кромка
    _blob(c, fender, ft, round_low=True)
    for xx, yy in fender:
        if (xx, yy - 1) not in fender and (xx, yy + 2) in fender and 34 <= xx <= 45:
            c.dot(xx, yy + 1, tt[3] if brass else ft[3])
            if 37 <= xx <= 39 and not brass:
                c.dot(xx, yy + 1, ft[4])
    c.hline(27, 23, 6, tt[2] if brass else ft[3])  # рифлёная подножка
    for xx in range(28, 33, 2):
        c.dot(xx, 23, ft[1])

    # Фара на крыле, бампер, зеркало, фигурка на капоте
    _headlamp(c, armored, tt)
    c.rect(41, 24, 7, 4, None, "k")  # бампер
    c.hline(42, 25, 5, tt[3] if not armored else pt[2])
    c.hline(42, 26, 5, tt[1] if not armored else pt[1])
    c.dot(42, 25, tt[4] if not armored else pt[3])
    c.dot(46, 26, "k")
    c.rect(45, 22, 2, 2, "oil1")  # фартук под решёткой
    if not armored:
        c.rect(38, 3, 3, 5, None, "k")  # зеркало на кронштейне
        c.dot(39, 4, "glass2")
        c.dot(39, 5, "glass1")
        c.dot(39, 6, "glass0")
        c.dot(38, 8, "k")
        c.dot(43, 11, "k")  # пробка радиатора с фигуркой
        c.dot(44, 11, tt[3])
        c.dot(44, 10, tt[4])
        c.dot(45, 10, "k")
        c.dot(43, 10, "k")
        c.dot(44, 9, "k")
        c.dot(29, 3, "lamp1")  # габаритные огни на крыше
        c.dot(32, 3, "lamp1")
    # Эмблема компании на двери, заклёпки и дорожная грязь по низу кабины
    if not armored:
        c.sprite(32, 17, [".t.", "tYt", ".t."], {"t": tt[1] if not brass else tt[2], "Y": tt[4]})
    c.rivets(29, 20, 3, 3, pt[3], pt[0])
    for xx in range(27, 38):
        if c.threshold(xx, 21, "bayer4") < 0.3:
            c.dot(xx, 21, pt[0])


def _fender_cells() -> tuple[Cells, Cells]:
    """Крыло: дуга над передним колесом с гребнем, спереди опускается к бамперу, сзади переходит в
    подножку. Возвращает (крыло, тёмная ниша колеса между крылом и покрышкой)."""
    top = {31: 22, 32: 21, 33: 21, 34: 20, 35: 20, 36: 19, 37: 19, 38: 19, 39: 19, 40: 19, 41: 19, 42: 19,
           43: 20, 44: 20, 45: 21, 46: 21, 47: 22}
    fender, well = set(), set()
    for xx in range(26, 48):
        y0 = top.get(xx, 22)
        y1 = 24 if xx < 34 else (24 if xx >= 45 else 26)
        for yy in range(y0, y1 + 1):
            dd = math.hypot(xx - _FWX, yy - _WY)
            if dd < 6.2 and xx >= 33:
                if dd >= 4.8:
                    well.add((xx, yy))
                continue
            fender.add((xx, yy))
    return fender, well


def _headlamp(c: Canvas, armored: bool, tt: Tones) -> None:
    """Круглая фара на крыле: хромированный (латунный) корпус с бликом, стекло вперёд, кронштейн.
    У бронеавтомобиля — под козырьком-бронешторкой."""
    lx, ly = _LAMP
    c.sprite(lx - 3, ly - 2, [
        ".kkk.",
        "kYTLk",
        "kTtWk",
        "ktTLk",
        ".kkk.",
        "..k..",
    ], {"k": "k", "Y": tt[4], "T": tt[3], "t": tt[2], "L": "lamp2", "W": "white"})
    if armored:
        c.hline(lx - 3, ly - 2, 5, "k")  # бронекозырёк
        c.hline(lx - 3, ly - 3, 5, "steel1")
        c.dot(lx - 3, ly - 3, "steel2")
        c.dot(lx + 1, ly - 3, "k")


def _cab_armor(c: Canvas, pt: Tones) -> None:
    """Бронирование кабины: стёкла закрыты листами со смотровыми щелями, заклёпки, жалюзи радиатора."""
    deep, lo, base, hi, spec = pt
    c.rect(29, 8, 5, 4, base)  # бронещиток бокового окна
    c.hline(29, 8, 5, hi)
    c.hline(29, 9, 5, "k")  # смотровая щель
    c.dot(30, 9, "glass1")
    c.dot(29, 11, lo)
    c.rivets(29, 10, 3, 2, hi)
    for yy in range(6, 12):  # лобовой щиток вместо стекла
        for xx in (35, 36):
            if c.get(xx, yy) in (c.rgb("glass0"), c.rgb("glass1"), c.rgb("glass2")):
                c.dot(xx, yy, lo)
    c.dot(36, 9, "k")
    c.rivets(26, 8, 4, 3, spec, deep, vertical=True)
    c.rivets(39, 13, 2, 4, spec)
    for yy in range(15, 22):  # бронежалюзи вместо хромированной решётки
        c.dot(46, yy, "k" if yy % 2 else lo)
    c.vline(45, 15, 7, deep)


def _bed_slats(c: Canvas, x0: int, top: int, bed: str, tt: Tones, brass: bool,
               posts: tuple[int, ...] = (0, 10, 20)) -> None:
    """Дощатый борт кузова от x0 до x=21, верх top, низ — строка 21: верхний брус, доски по 3 строки
    (блик, основной, тень) с тёмными щелями, стальные стойки с болтами, нижний брус."""
    bt = _tones(bed)
    deep, lo, base, hi, spec = bt
    x1, bottom = 21, 21
    w = x1 - x0 + 1
    c.rect(x0, top, w, bottom - top + 1, base, "k")
    c.hline(x0 + 1, top + 1, w - 2, tt[3] if brass else hi)  # верхний брус
    c.hline(x0 + 1, top + 2, w - 2, tt[1] if brass else lo)
    for yy in range(top + 3, bottom):
        k = (yy - top - 3) % 3
        c.hline(x0 + 1, yy, w - 2, (hi if k == 0 else (base if k == 1 else deep)))
    c.hline(x0 + 1, bottom - 1, w - 2, deep)
    # Зерно и сучки на досках — несколько тёмных/светлых штрихов
    for i, yy in enumerate(range(top + 4, bottom - 1, 3)):
        for xx in range(x0 + 3 + (i * 5) % 7, x1 - 2, 7):
            c.dot(xx, yy, lo)
            c.dot(xx + 1, yy - 1, spec if not brass else hi)
    for px in posts:  # стальные стойки с болтами
        sx = max(x0, min(px, x1 - 1))
        c.vline(sx, top + 1, bottom - top - 1, tt[2] if brass else "steel2")
        c.vline(sx + 1, top + 1, bottom - top - 1, tt[0] if brass else "steel0")
        for yy in (top + 3, bottom - 3):
            c.dot(sx, yy, tt[4] if brass else "steel3")
    c.rect(x0, top, w, bottom - top + 1, None, "k")
    if brass:
        c.hline(x0 + 2, bottom - 4, w - 4, "brass2")  # латунная полоса по борту
        c.hline(x0 + 2, bottom - 3, w - 4, "brass0")


def _bed_armored(c: Canvas) -> None:
    """Бронекузов: два больших листа со скошенным верхом на заклёпках, башенка со смотровой щелью и
    коротким стволом, смотровые щели и бойница, броне-юбка над задними колёсами, антенна."""
    at = _tones("armor")
    deep, _, _, hi, spec = at
    body = _span((8, 3, 19), (9, 2, 20), *[(yy, 1, 21) for yy in range(10, 23)])
    _blob(c, body, at, round_low=True)
    c.hline(3, 9, 17, spec)  # блик на скосе крыши
    c.vline(11, 10, 12, deep)  # стык листов
    c.vline(12, 10, 12, hi)
    c.rivets(3, 11, 3, 3, spec, deep)
    c.rivets(14, 11, 3, 3, spec, deep)
    c.rivets(10, 13, 3, 3, spec, vertical=True)
    c.hline(3, 14, 5, "k")  # смотровые щели
    c.dot(4, 14, "glass1")
    c.hline(15, 14, 4, "k")
    c.dot(16, 14, "glass1")
    c.rect(15, 17, 4, 3, "k")  # бойница с заслонкой
    c.hline(15, 16, 4, hi)
    c.dot(16, 18, "oil2")
    c.hline(2, 20, 19, deep)  # нижний пояс
    # Башенка с щелью и стволом назад
    turret = _span((3, 8, 13), (4, 7, 14), (5, 6, 15), (6, 6, 15), (7, 6, 15), (8, 6, 15))
    _blob(c, turret, at)
    c.hline(8, 4, 5, hi)
    c.hline(9, 6, 5, "k")
    c.dot(10, 6, "glass2")
    c.rect(1, 5, 6, 2, "steel1", "k")  # ствол
    c.dot(2, 5, "steel2")
    c.dot(11, 2, "k")  # перископ
    c.dot(11, 1, "glass2")
    c.vline(20, 0, 8, "steel1")  # антенна
    c.dot(20, 0, "steel3")
    # Броне-юбка над задними колёсами
    skirt = _span(*[(yy, 0, 22) for yy in range(22, 28)])
    _blob(c, skirt, at)
    c.rivets(2, 24, 7, 3, spec, deep)


def _truck_cargo(c: Canvas, cargo: str, x0: int, btop: int) -> None:
    """Груз в кузове: рисуется до бортов на своём слое (обведён контуром), низ утоплен за борт."""
    w = 21 - x0
    h = btop + 4
    lay = c.layer(w, h)
    bottom = h - 1
    if cargo == "crates":
        if w >= 18:
            _crate(lay, 0, bottom - 8, 9, 9)
            _crate(lay, 9, bottom - 6, 8, 7)
            _crate(lay, 2, bottom - 13, 6, 6, stencil=False)
            _tarp(lay, 16, bottom - 4, w - 16)
        else:
            _crate(lay, 1, bottom - 6, 7, 7)
            _crate(lay, 8, bottom - 5, 7, 6, stencil=False)
    elif cargo == "barrels":
        for i in range(0, w - 5, 7 if w >= 18 else 6):
            _drum(lay, i, bottom - 9, ("oil", "rust", "oil")[(i // 7) % 3])
    else:
        _heap(lay, 0, bottom, w, 9 if w >= 18 else 6, cargo)
    c.paste(lay, x0 + 1, btop + 4 - h)


def _crate(c: Canvas, x: int, y: int, w: int, h: int, stencil: bool = True) -> None:
    """Ящик w×h: контур, светлая верхняя/левая кромка, доски с тенью справа, раскос, клеймо."""
    c.rect(x, y, w, h, "wood1", "k")
    c.hline(x + 1, y + 1, w - 2, "paper0")
    c.vline(x + 1, y + 1, h - 2, "wood2")
    c.vline(x + w - 2, y + 2, h - 3, "wood0")
    c.hline(x + 2, y + h - 2, w - 3, "wood0")
    for yy in range(y + 3, y + h - 2, 2):  # стыки досок
        c.hline(x + 2, yy, w - 4, "wood0" if (yy - y) % 4 == 3 else "wood1")
    c.line(x + 2, y + h - 3, x + w - 3, y + 2, "wood2")  # раскос
    c.line(x + 3, y + h - 3, x + w - 3, y + 3, "wood0")
    c.dot(x + 1, y + 1, "paper1")
    if stencil and w >= 8:
        c.dot(x + w - 3, y + h - 4, "red1")  # клеймо отправителя
        c.dot(x + w - 4, y + h - 4, "red1")


def _tarp(c: Canvas, x: int, y: int, w: int) -> None:
    """Свёрток брезента, перетянутый верёвкой."""
    c.rect(x, y, w, 5, "green0", "k")
    c.hline(x + 1, y + 1, w - 2, "green1")
    c.vline(x + w // 2, y + 1, 3, "wood2")


def _drum(c: Canvas, x: int, y: int, paint: str = "oil") -> None:
    """Бочка 6×10 стоймя: объём в три тона (блик слева, тень справа), крышка с пробкой, два обруча."""
    t = _tones(paint)
    c.rect(x, y, 6, 10, t[2], "k")
    c.vline(x + 1, y + 1, 8, t[3])
    c.vline(x + 4, y + 1, 8, t[1])
    c.hline(x + 1, y + 1, 4, "steel2")  # крышка
    c.dot(x + 3, y + 1, "steel3")
    c.dot(x + 2, y + 1, "steel1")
    for j in (y + 3, y + 7):  # обручи
        c.hline(x + 1, j, 4, "brass1")
        c.dot(x + 1, j, "brass3")
        c.dot(x + 4, j, "brass0")


def _heap(c: Canvas, x0: int, bottom: int, w: int, peak: int, res: str) -> None:
    """Горка руды/угля: профиль с шумом, блик на левом склоне, тень на правом, комья с бликом и тенью,
    искры металла."""
    lo, mid, hi = ("coal0", "coal1", "coal2") if res == "coal" else ("ore0", "ore1", "ore2")
    glint = "steel3" if res == "coal" else "brass3"
    hs = []
    for i in range(w):
        f = math.sin(math.pi * (i + 0.5) / w)
        hs.append(max(3, round(peak * f ** 0.6) + (c.rnd.choice((-1, 0, 0, 1)) if f > 0.35 else 0)))
    cx = w / 2
    for i, h in enumerate(hs):
        topy = bottom - h + 1
        for yy in range(topy, bottom + 1):
            depth = yy - topy
            if depth == 0:
                col = "k"
            elif depth == 1:
                col = hi if i < cx + 1 else mid
            elif i > cx + 2 and c.threshold(x0 + i, yy, "checker") < 0.5:
                col = lo
            else:
                col = mid if depth < 4 or c.threshold(x0 + i, yy, "bayer4") > 0.35 else lo
            c.dot(x0 + i, yy, col)
    for _ in range(w // 2):  # комья
        i = c.rnd.randrange(1, w - 2)
        yy = bottom - c.rnd.randrange(1, max(2, hs[i] - 2))
        c.dot(x0 + i, yy, hi)
        c.dot(x0 + i + 1, yy, mid)
        c.dot(x0 + i + 1, yy + 1, lo)
    for _ in range(3):
        i = c.rnd.randrange(2, w - 2)
        c.dot(x0 + i, bottom - hs[i] + 2, glint)


# --- Поезд ---------------------------------------------------------------------------------------------


# Паровоз выше колёс, x = 0…36, y = 0…20 (колёса — ниже, процедурно): будка с горящим окном в две
# створки и номерной табличкой, котёл с латунными бандажами, песочница и сухопарник, свисток, дымовая
# коробка с заклёпками и петлями, труба с раструбом, прожектор, площадка с красным фартуком, буферный
# брус. Роли — _LOCO_PAL.
_LOCO = [
    "..........................kkkkkkkk...",  # 0  раструб трубы
    "..........................kSSsssok...",  # 1
    "kkkkkkkkkkkk...............kSssok....",  # 2  крыша будки
    "kSSSSSSSSSsk...............kYyyukkkk.",  # 3
    "kkkkkkkkkkkk......kkk......kSssokkYLk",  # 4  прожектор
    "kRrrrrrrrrkY.....kYYyk.....kSssokkyWk",  # 5
    "kRkkkkkkrrky.kk.kYYyyuk....kSssokkuLk",  # 6
    "kRkLLklkrrkukGgkkYyyyuk...kkkkkkkkkk.",  # 7
    "kRkLLklkrrkkkkkkkkkkkkkkkkkPPPPPOk...",  # 8  верх котла
    "kRklLklkrrkGGGYGGGGYGGGGYGkPOOOOok...",  # 9
    "kRkllkkkrrkGwwYGGGGYGGGGYGkPsOOOSk...",  # 10
    "kRkkkkkkrqkgggyggggyggggygkPOOOOok...",  # 11
    "kYyyyyyyyukgggyggggyggggygkPsOOOok...",  # 12 латунный пояс будки
    "kRrrrrrrrqkgggyggggyggggygkPOOOOok...",  # 13
    "kRkkkkkkrqkgggugggguggggugkPsOOOSk...",  # 14
    "kRkYuYukrqkhhhuhhhhuhhhhuhkPOOOOok...",  # 15 номерная табличка
    "kRkkkkkkrqkhhhuhhhhuhhhhuhkPsOOOokkkk",  # 16
    "kRqqqqqqqqkjjjkjjjjkjjjjkjkooooookRrk",  # 17
    "kSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSkrqk",  # 18 площадка
    "krRrrRrrRrrRrrRrrRrrRrrRrrRrrRrrRkqqk",  # 19 красный фартук с заклёпками
    "kkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkk",  # 20
]
_LOCO_PAL = {
    "k": "k", "S": "steel2", "s": "steel1", "o": "oil0", "O": "oil1", "P": "oil2",
    "Y": "brass3", "y": "brass2", "u": "brass1", "L": "lamp2", "l": "lamp1", "W": "white",
    "R": "red2", "r": "red1", "q": "red0",
    # котёл — тёмная «паровозная» зелень: блик, основной, тень, глубокая тень, искра
    "G": "green1", "g": "green0", "h": (27, 54, 46), "j": (19, 36, 36), "w": "green2",
}


def _driver(c: Canvas, cx: int, cy: int, r: int = 4, pin: tuple[int, int] = (2, 1)) -> None:
    """Ведущее колесо паровоза (дисковое): стальной бандаж с бликом сверху-слева, красный диск в три
    тона, тёмный противовес-полумесяц напротив пальца кривошипа, стальная ступица с бликом."""
    for dy in range(-r - 1, r + 2):
        for dx in range(-r - 1, r + 2):
            x, y = cx + dx, cy + dy
            if not c.in_disk(dx, dy, r):
                if any(c.in_disk(dx + a, dy + b, r) for a, b in _N4):
                    c.dot(x, y, "k")
                continue
            d = math.hypot(dx, dy)
            lit = -(dx + dy) / (d * 1.41) if d else 0.0
            if not c.in_disk(dx, dy, r - 1):  # бандаж
                col = "steel3" if lit > 0.55 else ("steel0" if lit < -0.3 else "steel1")
            elif d > 1.5 and (dx * pin[0] + dy * pin[1]) / (d * math.hypot(*pin)) < -0.55:
                col = "red0"  # противовес
            elif not c.in_disk(dx, dy, r - 2):  # кромка диска
                col = "red2" if lit > 0.3 else ("k" if lit < -0.5 else "red1")
            else:
                col = "red1"
            c.dot(x, y, col)
    c.dot(cx, cy, "steel2")
    c.dot(cx - 1, cy, "steel1")
    c.dot(cx, cy - 1, "steel3")


def locomotive(c: Canvas, x: int, y: int, steam: bool = True) -> None:
    """Тяжёлый паровоз в габарите LOCO_W×LOCO_H лицом вправо; x — левый край, y — уровень рельса
    (низ колёс). Котёл с латунными бандажами, дымовая коробка, труба, сухопарник, будка с горящим
    окном, прожектор, три ведущих колеса со спарником и шатуном, цилиндр, скотоотбойник.
    steam — дым из трубы и пар из цилиндра (на холсте)."""
    lay = c.layer(LOCO_W, LOCO_H)
    _loco_body(lay)
    top = y - (LOCO_H - 1)
    c.shadow(x + 1, y + 1, LOCO_W - 2, "oil0")
    c.glow(x + 36, top + 6, 4, ["haze0", "haze1", "lamp0"])  # ореол прожектора
    c.glow(x + 9, top + 20, 3, ["haze0", "fire0"])  # отсвет топки под будкой
    c.paste(lay, x, top)
    c.dot(x + 36, top + 7, "lamp2")
    if steam:
        smoke(c, x + 29, top - 1, 7, tone=2, drift=-1)  # дым из трубы тянется назад над составом
        smoke(c, x + 35, y - 1, 2, tone=3, drift=1)  # пар из продувки цилиндра
        c.dot(x + 11, top + 4, "smog3")  # облачко у свистка
        c.dot(x + 12, top + 3, "smog2")


def _loco_body(c: Canvas) -> None:
    """Паровоз на слое LOCO_W×LOCO_H: карта корпуса, колёса, движущий механизм, отбойник."""
    L = LOCO_H - 1  # строка рельса
    wy = L - 4  # центр ведущих колёс
    c.sprite(0, 0, _LOCO, _LOCO_PAL)
    # Три ведущих колеса и отсвет топки под будкой
    for wx in (5, 15, 25):
        _driver(c, wx, wy, 4)
    c.dot(10, L - 8, "fire2")
    c.dot(10, L - 7, "fire1")
    # Цилиндр с крышкой и заклёпками
    c.rect(28, L - 9, 6, 5, "steel1", "k")
    c.hline(29, L - 8, 4, "steel3")
    c.hline(29, L - 6, 4, "steel0")
    c.dot(29, L - 7, "steel2")
    c.dot(31, L - 7, "steel2")
    c.vline(33, L - 8, 3, "steel0")
    # Спарник через пальцы кривошипов и шатун от крейцкопфа к среднему колесу
    c.hline(6, wy + 2, 22, "k")
    c.hline(6, wy + 1, 22, "steel3")
    c.dot(6, wy + 1, "steel1")
    for wx in (5, 15, 25):
        c.dot(wx + 2, wy + 1, "white")
    c.line(17, wy + 1, 27, L - 7, "steel2")
    c.line(18, wy + 1, 27, L - 6, "k")
    c.rect(26, L - 8, 2, 2, "steel3")  # крейцкопф
    # Скотоотбойник: наклонные прутья под буферным брусом, по низу — полоса
    for xx in (33, 35):
        c.line(xx, L - 8, xx + 1, L - 1, "k")
    for xx in (34, 36):
        c.line(xx, L - 8, xx, L - 1, "red1" if xx == 36 else "red2")
    c.hline(33, L - 4, 4, "red0")
    c.hline(33, L, 4, "k")


def wagon(c: Canvas, x: int, y: int, kind: str = "box", color: str = "rust") -> None:
    """Вагон WAGON_W×WAGON_H: box (крытый: обшивка с рёбрами, откатная дверь, лесенка) | hopper (хоппер
    с горкой угля/руды и разгрузочной воронкой) | tank (цистерна с колпаком, лесенкой и бандажами).
    x — левый край, y — уровень рельса (низ колёс). color — рампа окраски кузова."""
    lay = c.layer(WAGON_W, WAGON_H)
    L = WAGON_H - 1
    t = _tones(color if (color in RAMPS or color in _TONES) else "rust")
    if kind == "hopper":
        _wagon_hopper(lay, t)
    elif kind == "tank":
        _wagon_tank(lay, t)
    else:
        _wagon_box(lay, t)
    _wagon_chassis(lay, L)
    c.shadow(x + 1, y + 1, WAGON_W - 2, "oil0")
    c.paste(lay, x, y - L)


def _small_wheel(c: Canvas, cx: int, cy: int) -> None:
    """Вагонное колесо диаметром 5: стальной обод с бликом сверху-слева, тёмный центр, ступица."""
    for dy in range(-3, 4):
        for dx in range(-3, 4):
            if not c.in_disk(dx, dy, 2):
                if any(c.in_disk(dx + a, dy + b, 2) for a, b in _N4):
                    c.dot(cx + dx, cy + dy, "k")
                continue
            if c.in_disk(dx, dy, 1):
                col = "oil1" if (dx + dy) < 0 else "oil0"
            else:
                s = dx + dy
                col = "steel3" if s <= -2 else ("steel0" if s >= 2 else ("steel2" if s < 0 else "steel1"))
            c.dot(cx + dx, cy + dy, col)
    c.dot(cx, cy, "steel2")


def _wagon_chassis(c: Canvas, L: int) -> None:
    """Хребтовая балка с бликом, буфера по торцам, две тележки: рама-боковина с буксами и рессорой,
    по два колеса."""
    c.rect(0, L - 7, WAGON_W, 3, "oil1", "k")  # балка
    c.hline(1, L - 6, WAGON_W - 2, "oil2")
    for xx in range(3, WAGON_W - 2, 4):
        c.dot(xx, L - 6, "steel1")
    for bx in (0, WAGON_W - 1):  # буфера
        c.vline(bx, L - 7, 3, "k")
        c.dot(bx, L - 6, "steel2")
    for bx in (2, 16):  # тележка: рама над колёсами с рессорой, буксы на осях
        c.rect(bx, L - 5, 10, 2, "oil2", "k")
        c.dot(bx + 4, L - 4, "brass1")
        c.dot(bx + 5, L - 4, "brass2")
    for wx in (4, 9, 18, 23):
        _small_wheel(c, wx, L - 2)
        c.dot(wx, L - 2, "steel3")  # букса


def _wagon_box(c: Canvas, t: Tones) -> None:
    """Крытый вагон: крыша с выносом, стенки с рёбрами, откатная дверь с раскосами на рельсе,
    лесенка у торца, трафаретная надпись."""
    deep, lo, base, hi, spec = t
    c.rect(1, 0, 26, 1, "k")  # крыша
    c.rect(0, 1, 28, 2, "steel1", "k")
    c.hline(1, 1, 26, "steel2")
    c.hline(3, 1, 10, "steel3")
    c.rect(1, 3, 26, 10, base, "k")  # стенки
    c.hline(2, 4, 24, hi)
    c.hline(2, 11, 24, deep)
    c.dither(2, 9, 24, 2, None, lo, 0.5)
    for yy in (6, 9):  # швы досок обшивки
        c.hline(2, yy, 24, lo)
    for rx in (4, 7, 20, 23):  # стальные рёбра жёсткости
        c.vline(rx, 4, 7, hi)
        c.vline(rx + 1, 4, 7, deep)
        c.dot(rx, 6, spec)
    c.rect(10, 3, 8, 10, lo, "k")  # откатная дверь
    c.vline(11, 4, 8, base)
    c.hline(11, 4, 6, base)
    c.line(11, 11, 16, 5, deep)
    c.line(11, 5, 16, 11, deep)
    c.dot(15, 8, spec)  # задвижка
    c.dot(16, 8, "k")
    c.hline(8, 3, 12, "k")  # рельс двери
    c.dot(9, 3, "steel2")
    c.dot(18, 3, "steel2")
    c.hline(2, 6, 2, "paper1")  # трафарет
    c.hline(2, 8, 1, "paper0")
    c.vline(25, 4, 8, "k")  # лесенка у торца
    for yy in range(5, 12, 2):
        c.dot(25, yy, "steel2")


def _wagon_hopper(c: Canvas, t: Tones) -> None:
    """Хоппер: горка угля или руды над бортом, кузов со скошенными к воронке торцами, рёбра жёсткости
    и верхняя обвязка, разгрузочная воронка между тележками."""
    deep, lo, _, hi, spec = t
    _heap(c, 1, 5, 26, 6, "ore" if c.rnd.random() < 0.5 else "coal")
    body = _span(*[(yy, 1, 26) for yy in range(4, 11)], (11, 3, 24), (12, 5, 22), (13, 7, 20), (14, 9, 18),
                 (15, 11, 16))
    _blob(c, body, t)
    c.hline(2, 5, 24, hi)  # верхняя обвязка
    c.hline(2, 6, 24, deep)
    for rx in (5, 10, 16, 21):  # рёбра жёсткости
        c.vline(rx, 7, 4, hi)
        c.vline(rx + 1, 7, 4, deep)
        c.dot(rx, 7, spec)
    c.hline(2, 10, 24, lo)
    c.line(3, 11, 7, 14, hi)  # скос торцов к воронке
    c.line(24, 11, 20, 14, deep)
    c.hline(3, 8, 1, "paper1")  # трафарет
    c.dot(23, 8, "paper0")


def _wagon_tank(c: Canvas, t: Tones) -> None:
    """Цистерна: цилиндр со скруглёнными днищами (блик полосой, тень снизу), колпак с люком,
    бандажи, лесенка, поручень, табличка «огнеопасно»."""
    _, lo, _, hi, spec = t
    tank = _span((3, 3, 24), (4, 2, 25), *[(yy, 1, 26) for yy in range(5, 12)], (12, 2, 25), (13, 4, 23))
    _blob(c, tank, t, round_low=True)
    c.hline(3, 5, 22, hi)
    c.hline(4, 6, 8, spec)  # блик на цилиндре
    c.hline(3, 10, 22, lo)
    for bx in (6, 21):  # бандажи
        c.vline(bx, 4, 9, "k")
        c.dot(bx, 5, "steel2")
        c.dot(bx, 12, "steel1")
    dome = _span((0, 12, 15), (1, 11, 16), (2, 11, 16), (3, 11, 16))
    _blob(c, dome, t)
    c.dot(12, 1, spec)
    c.hline(12, 0, 4, "k")
    c.dot(13, 0, "steel2")  # люк
    c.vline(17, 3, 10, "k")  # лесенка
    for yy in range(4, 13, 2):
        c.dot(18, yy, "steel2")
    c.vline(19, 3, 10, "k")
    c.rect(8, 7, 5, 3, "red1", "k")  # табличка
    c.dot(9, 8, "fire3")
    c.dot(10, 8, "red2")


def train(c: Canvas, x: int, y: int, wagons: tuple[str, ...] = ("box", "hopper", "tank")) -> None:
    """Рельсы на уровне y, вагоны слева направо от x и паровоз в голове состава (справа).
    Вагоны соединены сцепками; окраска — крытый ржавый, хоппер стальной, цистерна чёрная."""
    rails(c, y)
    paint = {"box": "rust", "hopper": "steel", "tank": "oil"}
    cx = x
    for k in wagons:
        wagon(c, cx, y, k, paint.get(k, "rust"))
        _coupler(c, cx + WAGON_W, y - 6)
        cx += WAGON_W + 1
    locomotive(c, cx, y)


def _coupler(c: Canvas, x: int, y: int) -> None:
    """Сцепка в зазоре между вагонами: стальное звено с бликом."""
    c.dot(x, y, "steel2")
    c.dot(x, y + 1, "k")
    c.dot(x - 1, y, "steel1")
    c.dot(x + 1, y, "steel1")


def minecart(c: Canvas, x: int, gy: int, res: str = "ore", track: bool = True) -> None:
    """Шахтная вагонетка 16×16 (с горкой): клёпаный кузов-трапеция с бортиком и поясом, горка руды или угля,
    два колеса под днищем. x — левый край, gy — низ колёс; track — отрезок узкоколейки под ней."""
    if track:
        for xx in range(x - 3, x + 20, 4):  # шпалы
            c.hline(xx, gy + 1, 2, "wood0")
            c.dot(xx, gy + 1, "wood1")
        c.hline(x - 4, gy, 24, "steel2")
        c.hline(x - 4, gy + 1, 24, "steel0")
        c.dither(x - 4, gy + 1, 24, 1, None, "wood0", 0.25)
    c.shadow(x + 1, gy + 1, 14, "oil0")
    lay = c.layer(16, 14)
    _heap(lay, 1, 7, 14, 7, res)
    tub = _span(*[(yy, (yy - 6) // 3, 15 - (yy - 6) // 3) for yy in range(6, 14)])
    _blob(lay, tub, _tones("rust"), round_low=True)
    lay.hline(0, 6, 16, "k")
    lay.hline(1, 7, 14, "steel2")  # стальной бортик
    lay.dot(1, 7, "steel3")
    lay.hline(1, 8, 14, "rust1")
    lay.hline(2, 10, 12, "rust3")  # пояс с заклёпками
    lay.hline(2, 11, 12, "rust0")
    lay.rivets(3, 10, 4, 3, "steel3")
    c.paste(lay, x, gy - 16)
    _small_wheel(c, x + 4, gy - 2)
    _small_wheel(c, x + 11, gy - 2)
