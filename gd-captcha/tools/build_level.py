#!/usr/bin/env python3
"""Собирает платформер-уровень GD 2.2 «captcha» в файл .gmd.

Вход: папка со снимками настоящего виджета (tools/capture.js) и своя сцена
(tools/scene.py). Картинки переводятся в цветные блоки (ID 211), одинаковые
пиксели склеиваются в прямоугольники. Логика собрана на триггерах 2.2:
Event (кнопки двух игроков), Instant Collision (клик), Collision (наведение
и края экрана), Pickup/Instant Count (счётчики), Toggle (состояния).

Запуск:
  python3 build_level.py <capture_dir> <scene.png> <scene_mask.png> <out.gmd> [preview_dir] [--swap]
"""
import base64
import gzip
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

# ---------------------------------------------------------------- геометрия
S = 0.5                     # единиц GD на CSS-пиксель
# Страница стоит так, чтобы точка появления игроков (x 15, y 105) попала
# в кадр слева снизу, за краем капчи: игроки остаются в кадре и не погибают.
X0, Y0 = 100.0, 445.0       # где в мире GD лежит точка (0, 0) страницы


def gx(css_x):
    return X0 + css_x * S


def gy(css_y):
    return Y0 - css_y * S


# Всё снято с демо-страницы Google в 2x. Координаты ниже — CSS-пиксели страницы.
CLIP = (13.0, 63.5)               # левый верх снимка page_challenge.png
WIDGET = (33.0, 336.0)            # iframe виджета
BFRAME = (85.0, 84.0)             # содержимое окна с заданием
CHECKBOX = (13.0, 22.5, 28.0)     # рамка чекбокса внутри виджета
SPINNER = (9.0, 18.5, 36.0)
CHECKMARK = (8.0, 22.5)
TILE0 = (7.0, 127.0)              # первая картинка-клетка внутри окна
TILE_STEP, TILE_SIZE = 97.0, 95.0
TILE_HIT = (6.0, 126.0, 97.0)     # зона клика по клетке (с белой рамкой)
BUTTON = (292.0, 530.0, 100.0, 42.0)
FOOTER_Y = 520.0
ERROR_H = 30.0
CURSOR_START = (215.0, 470.0)
BOUNDS = (14.0, 70.0, 500.0, 676.0)   # куда может ехать курсор (x0, y0, x1, y1)
CAM = (287.0, 376.0)              # центр камеры

CURSOR_SPEED = 300                # CSS-пикселей в секунду
HOVER_TIME = 0.15                 # плавность наведения на чекбокс

COLOR_NORMAL = (68, 71, 70)       # рамка чекбокса: #444746
COLOR_HOVER = (178, 178, 178)     # с курсором: #B2B2B2

# ---------------------------------------------------------------- ID в GD
BLOCK = 211                 # Colored Inner Square: пиксель
TINY = 1764                 # Tiny Circle: невидимые центры групп
COLLISION_BLOCK = 1816
T_MOVE, T_ALPHA, T_TOGGLE, T_SPAWN, T_STOP = 901, 1007, 1049, 1268, 1616
T_COLOR, T_ROTATE, T_SCALE, T_PICKUP = 899, 1346, 2067, 1817
T_INSTANT_COUNT, T_COLLISION, T_INSTANT_COLLISION = 1811, 1815, 3609
T_EVENT, T_OPTIONS, T_STATIC_CAMERA, T_END = 3604, 2899, 1914, 3600

Z_B4, Z_B3, Z_B2, Z_B1, Z_T1, Z_T2, Z_T3 = -3, -1, 1, 3, 5, 7, 9

# События Event-триггера (enum GJGameEvent).
EV_JUMP_PUSH, EV_LEFT_PUSH, EV_LEFT_RELEASE, EV_RIGHT_PUSH, EV_RIGHT_RELEASE = 69, 71, 72, 73, 74
P1, P2, ANY = 1, 2, 0

# Цветовые каналы.
CH_CHECKBOX = 10
CH_HIDDEN = 11              # прозрачный, для служебных объектов
CH_WHITE = 1011
CH_PALETTE = 100

# Группы с картинками.
G_CHECKBOX, G_SPINNER, G_GREEN, G_OVERLAY, G_POPUP, G_FOOTER = 10, 11, 12, 13, 14, 15
G_SKIP, G_VERIFY, G_SUBDIM, G_ERR_TRY, G_ERR_MORE, G_FILLER = 16, 17, 18, 19, 20, 21
G_CURSOR, G_SPIN_CENTER, G_CAM = 22, 23, 24
G_TILE, G_TICK, G_TILE_CENTER = 30, 50, 70     # + номер клетки

# Collision-блоки.
B_CURSOR, B_CHECKBOX, B_BUTTON = 1, 2, 3
B_WALL = {"L": 4, "R": 5, "U": 6, "D": 7}
B_TILE = 10                                    # + номер клетки

# Счётчики.
I_SELECTED, I_WRONG, I_BOOTED = 1, 2, 3


# ---------------------------------------------------------------- объекты
class Level:
    def __init__(self):
        self.objects = []
        self.next_group = 200
        self.trigger_x = 3000.0

    def add(self, props):
        self.objects.append(props)
        return props

    def group(self):
        self.next_group += 1
        return self.next_group

    def trigger(self, obj_id, groups, props, spawn=True):
        """Служебный триггер. Ставится правее по x в порядке создания:
        spawn-триггеры с «Spawn Ordered» запускают группу слева направо."""
        self.trigger_x += 2
        o = {1: obj_id, 2: self.trigger_x, 3: 300.0}
        if groups:
            o[57] = ".".join(str(g) for g in groups)
        if spawn:
            o[62] = 1
            o[87] = 1
        o.update(props)
        return self.add(o)


def fmt(v):
    if isinstance(v, float):
        s = f"{v:.4f}".rstrip("0").rstrip(".")
        return s if s not in ("", "-0") else "0"
    return str(v)


def object_string(o):
    return ",".join(f"{k},{fmt(v)}" for k, v in o.items())


# ---------------------------------------------------------------- картинки → блоки
def rgba(path):
    return Image.open(path).convert("RGBA")


def crop_px(img, x0, y0, x1, y1):
    return img.crop((int(round(x0)), int(round(y0)), int(round(x1)), int(round(y1))))


def keep_diff(img, ref_color, thresh):
    """Оставляет непрозрачными только пиксели, отличные от фона."""
    a = np.array(img).astype(int)
    diff = np.abs(a[..., :3] - np.array(ref_color)).sum(axis=2)
    a[..., 3] = np.where(diff > thresh, 255, 0)
    return Image.fromarray(a.astype(np.uint8), "RGBA")


class Art:
    """Слой картинки: RGBA-изображение, где оно лежит на странице и сколько
    картиночных пикселей приходится на один CSS-пиксель."""

    def __init__(self, name, img, css_x, css_y, px_per_css, groups, z, z_order=0,
                 channel=None):
        self.name, self.img = name, img
        self.css_x, self.css_y, self.k = css_x, css_y, px_per_css
        self.groups, self.z, self.z_order, self.channel = groups, z, z_order, channel


def build_palette(arts, colors=250):
    pix = []
    for a in arts:
        if a.channel is not None:
            continue
        arr = np.array(a.img)
        pix.append(arr[arr[..., 3] >= 128][:, :3])
    allpix = np.concatenate(pix)
    side = int(np.ceil(np.sqrt(len(allpix))))
    canvas = np.zeros((side * side, 3), np.uint8)
    canvas[: len(allpix)] = allpix
    canvas[len(allpix):] = allpix[0]
    img = Image.fromarray(canvas.reshape(side, side, 3), "RGB")
    return img.quantize(colors=colors, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)


def rects(idx):
    """Склеивает одинаковые пиксели в прямоугольники (жадно: строка, потом вниз)."""
    h, w = idx.shape
    used = np.zeros_like(idx, bool)
    out = []
    for y in range(h):
        x = 0
        while x < w:
            c = idx[y, x]
            if c < 0 or used[y, x]:
                x += 1
                continue
            x1 = x
            while x1 < w and idx[y, x1] == c and not used[y, x1]:
                x1 += 1
            y1 = y + 1
            while y1 < h and (idx[y1, x:x1] == c).all() and not used[y1, x:x1].any():
                y1 += 1
            used[y:y1, x:x1] = True
            out.append((x, y, x1 - x, y1 - y, int(c)))
            x = x1
    return out


def art_objects(level, art, palette_img):
    arr = np.array(art.img)
    alpha = arr[..., 3] >= 128
    if art.channel is None:
        q = np.array(art.img.convert("RGB").quantize(palette=palette_img, dither=Image.Dither.NONE))
        idx = np.where(alpha, q.astype(int), -1)
    else:
        idx = np.where(alpha, 0, -1)
    unit = S / art.k                       # размер картиночного пикселя в GD
    pad = 0.12                             # лёгкий нахлёст, чтобы не было щелей
    count = 0
    for x, y, w, h, c in rects(idx):
        cx = art.css_x + (x + w / 2) / art.k
        cy = art.css_y + (y + h / 2) / art.k
        o = {1: BLOCK, 2: gx(cx), 3: gy(cy),
             128: (w * unit + pad) / 30.0, 129: (h * unit + pad) / 30.0,
             21: art.channel if art.channel is not None else CH_PALETTE + c,
             24: art.z, 25: art.z_order, 64: 1, 121: 1}
        if art.groups:
            o[57] = ".".join(str(g) for g in art.groups)
        level.add(o)
        count += 1
    return count


# ---------------------------------------------------------------- сборка картинок
def make_arts(cap, scene_path, mask_path):
    page = rgba(os.path.join(cap, "page_challenge.png"))
    skip = rgba(os.path.join(cap, "challenge_skip.png"))
    verify = rgba(os.path.join(cap, "challenge_verify.png"))
    selected = rgba(os.path.join(cap, "challenge_selected.png"))
    widget = rgba(os.path.join(cap, "widget_base.png"))
    checked = rgba(os.path.join(cap, "widget_checked.png"))
    scene = rgba(scene_path)
    mask = np.array(Image.open(mask_path).convert("L")) > 0

    def page_px(cx, cy):
        return (cx - CLIP[0]) * 2, (cy - CLIP[1]) * 2

    arts = []

    # Белая страница.
    bg = Image.new("RGBA", (4, 4), (255, 255, 255, 255))
    arts.append(Art("page", bg, -300, -200, 4 / 1200, [], Z_B4, channel=CH_WHITE))

    # Плашка без рамки чекбокса (подпись уже «captcha»).
    arts.append(Art("widget", widget, WIDGET[0], WIDGET[1], 2, [], Z_B3))

    # Рамка чекбокса 28x28, толщина 2, скругление 2: свой канал для наведения.
    cb = Image.new("RGBA", (56, 56), (0, 0, 0, 0))
    d = ImageDraw.Draw(cb)
    d.rounded_rectangle([0, 0, 55, 55], radius=4, fill=(0, 0, 0, 255))
    d.rounded_rectangle([4, 4, 51, 51], radius=1, fill=(0, 0, 0, 0))
    arts.append(Art("checkbox", cb, WIDGET[0] + CHECKBOX[0], WIDGET[1] + CHECKBOX[1], 2,
                    [G_CHECKBOX], Z_B2, 0, channel=CH_CHECKBOX))

    # Спиннер: кольцо 36px с толщиной 6, окрашены верхняя и правая четверти.
    n = 72
    yy, xx = np.mgrid[0:n, 0:n] + 0.5
    r = np.hypot(xx - n / 2, yy - n / 2)
    ang = np.degrees(np.arctan2(n / 2 - yy, xx - n / 2))
    ring = (r <= n / 2) & (r >= n / 2 - 12) & (ang >= -45) & (ang <= 135)
    sp = np.zeros((n, n, 4), np.uint8)
    sp[ring] = (77, 144, 254, 255)
    arts.append(Art("spinner", Image.fromarray(sp, "RGBA"), WIDGET[0] + SPINNER[0],
                    WIDGET[1] + SPINNER[1], 2, [G_SPINNER], Z_B2, 2))

    # Зелёная галочка из настоящего виджета.
    gx0, gy0 = CHECKMARK[0] * 2, CHECKMARK[1] * 2
    green = keep_diff(crop_px(checked, gx0, gy0, gx0 + 76, gy0 + 60), (249, 249, 249), 24)
    arts.append(Art("green", green, WIDGET[0] + CHECKMARK[0], WIDGET[1] + CHECKMARK[1], 2,
                    [G_GREEN], Z_B2, 3))

    # Белая дымка 5% поверх страницы, пока открыто окно.
    arts.append(Art("overlay", bg, -300, -200, 4 / 1200, [G_OVERLAY], Z_B1, channel=CH_WHITE))

    # Окно: рамка, тень и всё содержимое со снимка страницы.
    px0, py0 = page_px(84, 82.5)
    px1, py1 = page_px(491.5, 670.5)
    popup = crop_px(page, px0, py0, px1, py1)
    pd = ImageDraw.Draw(popup)

    def bf(bx, by):          # координаты окна → пиксели вырезки popup
        x, y = page_px(BFRAME[0] + bx, BFRAME[1] + by)
        return x - px0, y - py0

    # Убираем фото Google и кнопку: на их месте будут свои слои.
    for i in range(16):
        r_, c_ = divmod(i, 4)
        x, y = bf(TILE_HIT[0] + c_ * TILE_STEP, TILE_HIT[1] + r_ * TILE_STEP)
        pd.rectangle([x, y, x + TILE_HIT[2] * 2 - 1, y + TILE_HIT[2] * 2 - 1], fill=(255, 255, 255, 255))
    x, y = bf(BUTTON[0], BUTTON[1])
    pd.rectangle([x, y, x + BUTTON[2] * 2 - 1, y + BUTTON[3] * 2 - 1], fill=(255, 255, 255, 255))
    fy = int(round(bf(0, FOOTER_Y)[1]))
    top = popup.crop((0, 0, popup.width, fy))
    bottom = popup.crop((0, fy, popup.width, popup.height))
    css_px0, css_py0 = 84.0, 82.5
    arts.append(Art("popup_top", top, css_px0, css_py0, 2, [G_POPUP], Z_T1, 0))
    arts.append(Art("popup_footer", bottom, css_px0, css_py0 + fy / 2, 2, [G_POPUP, G_FOOTER], Z_T1, 0))

    # Полоса, которая заполняет место под ошибку (как строка над футером).
    strip_y = int(round(bf(0, 517)[1]))
    strip = popup.crop((0, strip_y, popup.width, strip_y + 1)).resize((popup.width, int(ERROR_H * 2)))
    arts.append(Art("filler", strip, css_px0, css_py0 + fy / 2, 2, [G_POPUP, G_FILLER], Z_T1, 1))

    # Стрелка окна, которая указывает на чекбокс.
    ax0, ay0 = page_px(62, 360)
    ax1, ay1 = page_px(85, 387)
    arrow = crop_px(page, ax0, ay0, ax1, ay1)
    wpx = widget.crop((int((62 - WIDGET[0]) * 2), int((360 - WIDGET[1]) * 2),
                       int((85 - WIDGET[0]) * 2), int((387 - WIDGET[1]) * 2)))
    a = np.array(arrow).astype(int)
    b = np.array(wpx).astype(int)
    keep = np.abs(a[..., :3] - b[..., :3]).sum(axis=2) > 12
    a[..., 3] = np.where(keep, 255, 0)
    arts.append(Art("arrow", Image.fromarray(a.astype(np.uint8), "RGBA"), 62, 360, 2, [G_POPUP], Z_T1, 1))

    def iframe_crop(img, bx, by, w, h):
        return img.crop((int(bx * 2), int(by * 2), int((bx + w) * 2), int((by + h) * 2)))

    # Кнопки SKIP и VERIFY.
    for name, img, g in (("skip", skip, G_SKIP), ("verify", verify, G_VERIFY)):
        arts.append(Art(name, iframe_crop(img, *BUTTON), BFRAME[0] + BUTTON[0], BFRAME[1] + BUTTON[1], 2,
                        [G_POPUP, G_FOOTER, g], Z_T1, 2))

    # Подзаголовок «If there are none, click skip» бледнеет, когда что-то выбрано.
    # Перекрываем строку целиком вместе с синим фоном, чтобы не двоились буквы.
    sub = iframe_crop(selected, 31, 82, 166, 16)
    arts.append(Art("subtitle_dim", sub, BFRAME[0] + 31, BFRAME[1] + 82, 2, [G_POPUP, G_SUBDIM], Z_T1, 2))

    # Сообщения об ошибках.
    for name, file, by, g in (
            ("err_try", "err_rc-imageselect-incorrect-response.png", 513, G_ERR_TRY),
            ("err_more", "err_rc-imageselect-error-select-more.png", 543, G_ERR_MORE)):
        img = iframe_crop(rgba(os.path.join(cap, file)), 7, by, 386, ERROR_H)
        img = keep_diff(img, (255, 255, 255), 30)
        arts.append(Art(name, img, BFRAME[0] + 7, BFRAME[1] + 513, 2, [G_POPUP, g], Z_T1, 3))

    # Клетки со своей сценой и синие галочки выбора.
    # Галочка выбора: синий круг и белая птичка, ровно два цвета.
    tick = np.array(rgba(os.path.join(cap, "sprite_tilecheck.png")).resize((48, 48), Image.LANCZOS))
    light = tick[..., :3].min(axis=2) > 160
    tick[..., :3] = np.where(light[..., None], (255, 255, 255), (26, 115, 232))
    tick[..., 3] = np.where(tick[..., 3] >= 128, 255, 0)
    tick = Image.fromarray(tick.astype(np.uint8), "RGBA")
    n_scene = scene.width // 4
    correct = []
    for i in range(16):
        r_, c_ = divmod(i, 4)
        tile = scene.crop((c_ * n_scene, r_ * n_scene, (c_ + 1) * n_scene, (r_ + 1) * n_scene))
        tx = BFRAME[0] + TILE0[0] + c_ * TILE_STEP
        ty = BFRAME[1] + TILE0[1] + r_ * TILE_STEP
        arts.append(Art(f"tile{i}", tile, tx, ty, n_scene / TILE_SIZE,
                        [G_POPUP, G_TILE + i], Z_T1, 4))
        arts.append(Art(f"tick{i}", tick, tx + 3.5, ty + 2.5, 2,
                        [G_POPUP, G_TICK + i], Z_T1, 6))
        m = mask[r_ * n_scene:(r_ + 1) * n_scene, c_ * n_scene:(c_ + 1) * n_scene]
        correct.append(bool(m.sum() >= 4))

    # Курсор: обычная стрелка, остриё в левом верхнем пикселе.
    rows = [
        "B...........",
        "BB..........",
        "BWB.........",
        "BWWB........",
        "BWWWB.......",
        "BWWWWB......",
        "BWWWWWB.....",
        "BWWWWWWB....",
        "BWWWWWWWB...",
        "BWWWWWWWWB..",
        "BWWWWWWWWWB.",
        "BWWWWWWBBBBB",
        "BWWWBWWB....",
        "BWWB.BWWB...",
        "BWB..BWWB...",
        "BB....BWWB..",
        "B.....BWWB..",
        ".......BWWB.",
        ".......BWWB.",
        "........BB..",
    ]
    cur = np.zeros((len(rows), 12, 4), np.uint8)
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch == "B":
                cur[y, x] = (0, 0, 0, 255)
            elif ch == "W":
                cur[y, x] = (255, 255, 255, 255)
    arts.append(Art("cursor", Image.fromarray(cur, "RGBA"), CURSOR_START[0], CURSOR_START[1], 1,
                    [G_CURSOR], Z_T3, 0))
    return arts, correct


# ---------------------------------------------------------------- логика
def build_logic(L, correct, swap_players=False):
    t = L.trigger

    def spawn(groups, target, delay=0.0):
        return t(T_SPAWN, groups, {51: target, 63: delay, 441: 1})

    def alpha(groups, target, value, time=0.0):
        return t(T_ALPHA, groups, {51: target, 35: value, 10: time})

    def toggle(groups, target, on):
        return t(T_TOGGLE, groups, {51: target, 56: 1 if on else 0})

    def pickup(groups, item, count, override=False):
        p = {80: item, 77: count}
        if override:
            p[139] = 1
        return t(T_PICKUP, groups, p)

    def if_count(groups, item, value, cmp, target):
        # cmp: 0 равно, 1 больше, 2 меньше. Activate Group обязательно включён.
        return t(T_INSTANT_COUNT, groups, {80: item, 77: value, 88: cmp, 51: target, 56: 1})

    def if_touch(groups, block, true_id=0, false_id=0):
        p = {80: B_CURSOR, 95: block}
        if true_id:
            p[51] = true_id
        if false_id:
            p[71] = false_id
        return t(T_INSTANT_COLLISION, groups, p)

    def on_collision(groups, block, target, on_exit=False):
        p = {80: B_CURSOR, 95: block, 51: target, 56: 1}
        if on_exit:
            p[93] = 1
        return t(T_COLLISION, groups, p)

    def event(groups, ev, player, target):
        return t(T_EVENT, groups, {51: target, 430: str(ev), 525: player})

    def color(groups, channel, rgb, time):
        return t(T_COLOR, groups, {23: channel, 7: rgb[0], 8: rgb[1], 9: rgb[2], 10: time, 35: 1})

    def move(groups, target, dx, dy, time=0.0):
        return t(T_MOVE, groups, {51: target, 28: int(round(dx)), 29: int(round(dy)), 10: time, 393: 1})

    def stop(groups, target):
        return t(T_STOP, groups, {51: target})

    BOOT, START = L.group(), L.group()
    GATE_WIDGET, GATE_CHALLENGE = L.group(), L.group()

    # Движение курсора: нажатие запускает долгий Move, отпускание его гасит.
    speed = CURSOR_SPEED * S
    run_time = 30.0
    dirs = {"L": (-1, 0), "R": (1, 0), "U": (0, 1), "D": (0, -1)}
    push, release = {}, {}
    for key, (dx, dy) in dirs.items():
        run, push[key], release[key] = L.group(), L.group(), L.group()
        move([run], G_CURSOR, dx * speed * run_time, dy * speed * run_time, run_time)
        if_touch([push[key]], B_WALL[key], false_id=run)   # у стенки не едем
        stop([release[key]], run)
        on_collision([START], B_WALL[key], release[key])   # доехали до края

    # Кнопки. P2 — стрелки: ←/→ по горизонтали. P1 — A/D: вниз/вверх.
    # С --swap игроки меняются местами (если в игре стрелки окажутся у P1).
    CLICK = L.group()
    horiz, vert = (P1, P2) if swap_players else (P2, P1)
    for ev_push, ev_release, player, key in (
            (EV_LEFT_PUSH, EV_LEFT_RELEASE, horiz, "L"),
            (EV_RIGHT_PUSH, EV_RIGHT_RELEASE, horiz, "R"),
            (EV_LEFT_PUSH, EV_LEFT_RELEASE, vert, "D"),
            (EV_RIGHT_PUSH, EV_RIGHT_RELEASE, vert, "U")):
        event([START], ev_push, player, push[key])
        event([START], ev_release, player, release[key])
    event([START], EV_JUMP_PUSH, ANY, CLICK)               # любой прыжок — клик

    # Наведение на чекбокс: рамка плавно светлеет и возвращается.
    hover_on, hover_off = L.group(), L.group()
    color([hover_on], CH_CHECKBOX, COLOR_HOVER, HOVER_TIME)
    color([hover_off], CH_CHECKBOX, COLOR_NORMAL, HOVER_TIME)
    on_collision([START], B_CHECKBOX, hover_on)
    on_collision([START], B_CHECKBOX, hover_off, on_exit=True)

    # Спиннер крутится вокруг своего центра: оборот за 2,5 с.
    SPIN_RUN = L.group()
    t(T_ROTATE, [SPIN_RUN], {51: G_SPINNER, 71: G_SPIN_CENTER, 68: 0, 69: 40, 10: 100.0})

    # Ошибки под сеткой: футер уезжает вниз на высоту строки.
    err_show, err_hide = L.group(), L.group()
    swap_err_on, swap_err_off = L.group(), L.group()
    ERR_HIDE, ERR_TRY, ERR_MORE = L.group(), L.group(), L.group()
    move([err_show], G_FOOTER, 0, -ERROR_H * S)
    spawn([err_show], swap_err_on, 0.05)
    toggle([swap_err_on], err_show, False)
    toggle([swap_err_on], err_hide, True)
    for g in (G_ERR_TRY, G_ERR_MORE, G_FILLER):
        alpha([err_hide], g, 0)
    move([err_hide], G_FOOTER, 0, ERROR_H * S)
    spawn([err_hide], swap_err_off, 0.05)
    toggle([swap_err_off], err_hide, False)
    toggle([swap_err_off], err_show, True)
    spawn([ERR_HIDE], err_hide)
    for grp, show, other in ((ERR_TRY, G_ERR_TRY, G_ERR_MORE), (ERR_MORE, G_ERR_MORE, G_ERR_TRY)):
        alpha([grp], other, 0)
        alpha([grp], show, 1)
        alpha([grp], G_FILLER, 1)
        spawn([grp], err_show)

    # SKIP ↔ VERIFY и бледный подзаголовок.
    UPDATE, state_empty, state_some = L.group(), L.group(), L.group()
    if_count([UPDATE], I_SELECTED, 0, 0, state_empty)
    if_count([UPDATE], I_SELECTED, 0, 1, state_some)
    for grp, sk, ve in ((state_empty, 1, 0), (state_some, 0, 1)):
        alpha([grp], G_SKIP, sk)
        alpha([grp], G_VERIFY, ve)
        alpha([grp], G_SUBDIM, ve)

    # Клетки: два обработчика (выбрать/снять), включён всегда один.
    sel_on, sel_off = [], []
    for i in range(16):
        on_g, off_g, swap_on, swap_off, click = (L.group() for _ in range(5))
        wrong = -1 if correct[i] else 1
        t(T_SCALE, [on_g], {51: G_TILE + i, 71: G_TILE_CENTER + i, 150: 0.8, 151: 0.8, 10: 0.1})
        alpha([on_g], G_TICK + i, 1, 0.1)
        pickup([on_g], I_SELECTED, 1)
        pickup([on_g], I_WRONG, wrong)
        spawn([on_g], ERR_HIDE)
        spawn([on_g], UPDATE, 0.05)
        spawn([on_g], swap_on, 0.05)
        toggle([swap_on], on_g, False)
        toggle([swap_on], off_g, True)

        t(T_SCALE, [off_g], {51: G_TILE + i, 71: G_TILE_CENTER + i, 150: 0.8, 151: 0.8,
                             153: 1, 154: 1, 10: 0.1})
        alpha([off_g], G_TICK + i, 0, 0.1)
        pickup([off_g], I_SELECTED, -1)
        pickup([off_g], I_WRONG, -wrong)
        spawn([off_g], ERR_HIDE)
        spawn([off_g], UPDATE, 0.05)
        spawn([off_g], swap_off, 0.05)
        toggle([swap_off], off_g, False)
        toggle([swap_off], on_g, True)

        spawn([click], on_g)
        spawn([click], off_g)
        if_touch([CLICK, GATE_CHALLENGE], B_TILE + i, true_id=click)
        sel_on.append(on_g)
        sel_off.append(off_g)

    # Клик по чекбоксу: спиннер, через секунду окно с заданием.
    CB_CLICK, OPEN = L.group(), L.group()
    if_touch([CLICK, GATE_WIDGET], B_CHECKBOX, true_id=CB_CLICK)
    toggle([CB_CLICK], GATE_WIDGET, False)
    alpha([CB_CLICK], G_CHECKBOX, 0, 0.15)
    alpha([CB_CLICK], G_SPINNER, 1, 0.15)
    spawn([CB_CLICK], SPIN_RUN)
    spawn([CB_CLICK], OPEN, 1.0)
    stop([OPEN], SPIN_RUN)
    alpha([OPEN], G_SPINNER, 0, 0.1)
    alpha([OPEN], G_CHECKBOX, 1, 0.1)
    alpha([OPEN], G_OVERLAY, 0.05)
    alpha([OPEN], G_POPUP, 1, 0.1)
    toggle([OPEN], GATE_CHALLENGE, True)

    # Кнопка SKIP/VERIFY.
    BTN, BAD, FAIL, WIN, WIN2, FINISH = (L.group() for _ in range(6))
    if_touch([CLICK, GATE_CHALLENGE], B_BUTTON, true_id=BTN)
    if_count([BTN], I_WRONG, 0, 0, WIN)
    if_count([BTN], I_WRONG, 0, 1, BAD)
    if_count([BAD], I_SELECTED, 0, 0, ERR_MORE)       # ничего не выбрано
    if_count([BAD], I_SELECTED, 0, 1, FAIL)           # выбрано, но неправильно
    for off_g in sel_off:                             # снимаем всё выбранное
        spawn([FAIL], off_g)
    spawn([FAIL], ERR_TRY, 0.2)

    # Победа: окно закрывается, спиннер, зелёная галочка, конец уровня.
    toggle([WIN], GATE_CHALLENGE, False)
    alpha([WIN], G_POPUP, 0, 0.1)
    alpha([WIN], G_OVERLAY, 0, 0.1)
    alpha([WIN], G_CHECKBOX, 0, 0.15)
    alpha([WIN], G_SPINNER, 1, 0.15)
    spawn([WIN], SPIN_RUN)
    spawn([WIN], WIN2, 0.8)
    stop([WIN2], SPIN_RUN)
    alpha([WIN2], G_SPINNER, 0, 0.1)
    alpha([WIN2], G_GREEN, 1, 0.2)
    spawn([WIN2], FINISH, 1.5)
    t(T_END, [FINISH], {})

    # Старт: камера, скрыть игроков, начальные состояния.
    t(T_OPTIONS, [START], {162: 1, 163: 1, 532: 1, 161: 1})
    t(T_STATIC_CAMERA, [START], {71: G_CAM, 10: 0})
    for g in (G_SPINNER, G_GREEN, G_OVERLAY, G_POPUP, G_VERIFY, G_SUBDIM,
              G_ERR_TRY, G_ERR_MORE, G_FILLER):
        alpha([START], g, 0)
    for i in range(16):
        alpha([START], G_TICK + i, 0)
        toggle([START], sel_off[i], False)
    toggle([START], GATE_CHALLENGE, False)
    toggle([START], err_hide, False)
    pickup([START], I_SELECTED, 0, override=True)
    pickup([START], I_WRONG, sum(correct), override=True)
    color([START], CH_CHECKBOX, COLOR_NORMAL, 0)

    # Запуск: Spawn Group уровня (kA36) спавнит BOOT на старте. Запасной Spawn
    # на x = 0 сработает, если игрок шагнёт. Счётчик не даёт запустить START дважды.
    if_count([BOOT], I_BOOTED, 0, 0, START)
    pickup([START], I_BOOTED, 1, override=True)
    L.add({1: T_SPAWN, 2: 0.0, 3: 135.0, 51: BOOT, 63: 0.1})
    return BOOT


def build_collision(L):
    def block(bid, css_x, css_y, w, h, groups=(), dynamic=False):
        o = {1: COLLISION_BLOCK, 2: gx(css_x + w / 2), 3: gy(css_y + h / 2), 80: bid,
             128: w * S / 30.0, 129: h * S / 30.0}
        if dynamic:
            o[94] = 1
        if groups:
            o[57] = ".".join(str(g) for g in groups)
        L.add(o)

    # Остриё курсора: квадрат 2x2 CSS-пикселя.
    block(B_CURSOR, CURSOR_START[0], CURSOR_START[1], 2, 2, [G_CURSOR], dynamic=True)
    block(B_CHECKBOX, WIDGET[0] + CHECKBOX[0], WIDGET[1] + CHECKBOX[1], CHECKBOX[2], CHECKBOX[2])
    for i in range(16):
        r_, c_ = divmod(i, 4)
        block(B_TILE + i, BFRAME[0] + TILE_HIT[0] + c_ * TILE_STEP,
              BFRAME[1] + TILE_HIT[1] + r_ * TILE_STEP, TILE_HIT[2], TILE_HIT[2])
    block(B_BUTTON, BFRAME[0] + BUTTON[0], BFRAME[1] + BUTTON[1], BUTTON[2], BUTTON[3], [G_FOOTER])
    x0, y0, x1, y1 = BOUNDS
    big = 400
    block(B_WALL["L"], x0 - big, y0 - big, big, (y1 - y0) + 2 * big)
    block(B_WALL["R"], x1, y0 - big, big, (y1 - y0) + 2 * big)
    block(B_WALL["U"], x0 - big, y0 - big, (x1 - x0) + 2 * big, big)
    block(B_WALL["D"], x0 - big, y1, (x1 - x0) + 2 * big, big)


def build_helpers(L):
    """Невидимые центры: камера, спиннер, клетки. И коробка для игроков."""
    def tiny(css_x, css_y, group):
        L.add({1: TINY, 2: gx(css_x), 3: gy(css_y), 21: CH_HIDDEN, 57: str(group), 32: 0.2})

    tiny(CAM[0], CAM[1], G_CAM)
    tiny(WIDGET[0] + SPINNER[0] + SPINNER[2] / 2, WIDGET[1] + SPINNER[1] + SPINNER[2] / 2, G_SPIN_CENTER)
    for i in range(16):
        r_, c_ = divmod(i, 4)
        tiny(BFRAME[0] + TILE0[0] + c_ * TILE_STEP + TILE_SIZE / 2,
             BFRAME[1] + TILE0[1] + r_ * TILE_STEP + TILE_SIZE / 2, G_TILE_CENTER + i)
    # Загон для игроков: свой пол (на случай, если Hide Ground уберёт землю),
    # стенка справа и потолок. Сверху белая плашка, если игроки вдруг не скроются.
    # Блоки белые и твёрдые: на белой странице их не видно.
    def wall(x, y):
        L.add({1: BLOCK, 2: x, 3: y, 21: CH_WHITE, 24: Z_B3, 64: 1})
    for x in (15.0, 45.0, 75.0):
        wall(x, 75.0)
        wall(x, 195.0)
    for y in (75.0, 105.0, 135.0, 165.0, 195.0):
        wall(105.0, y)
    L.add({1: BLOCK, 2: 45.0, 3: 135.0, 128: 3.2, 129: 3.2, 21: CH_WHITE, 24: Z_T3, 25: 50,
           64: 1, 121: 1})


def check_links(L):
    """Каждая группа, на которую ссылается триггер, должна быть у какого-то объекта."""
    have = set()
    for o in L.objects:
        have.update(int(g) for g in str(o.get(57, "")).split(".") if g)
    refs = {T_SPAWN: (51,), T_ALPHA: (51,), T_TOGGLE: (51,), T_STOP: (51,), T_MOVE: (51,),
            T_ROTATE: (51, 71), T_SCALE: (51, 71), T_INSTANT_COUNT: (51,), T_COLLISION: (51,),
            T_INSTANT_COLLISION: (51, 71), T_EVENT: (51,), T_STATIC_CAMERA: (71,)}
    missing = set()
    for o in L.objects:
        for k in refs.get(o[1], ()):
            if o.get(k) and int(o[k]) not in have:
                missing.add((o[1], k, o[k]))
    blocks = {o[80] for o in L.objects if o[1] == COLLISION_BLOCK}
    for o in L.objects:
        if o[1] in (T_COLLISION, T_INSTANT_COLLISION):
            for k in (80, 95):
                if o[k] not in blocks:
                    missing.add((o[1], k, o[k]))
    if missing:
        raise SystemExit(f"битые ссылки: {sorted(missing)}")


# ---------------------------------------------------------------- файл уровня
def color_string(palette_rgb):
    def entry(ch, rgb, opacity=1.0):
        return f"1_{rgb[0]}_2_{rgb[1]}_3_{rgb[2]}_11_255_12_255_13_255_4_-1_6_{ch}_7_{fmt(opacity)}_15_1_18_0_8_1"
    parts = [entry(1000, (255, 255, 255)), entry(1001, (255, 255, 255)), entry(1002, (255, 255, 255)),
             entry(1009, (255, 255, 255)), entry(CH_CHECKBOX, COLOR_NORMAL), entry(CH_HIDDEN, (255, 255, 255), 0)]
    for i, rgb in enumerate(palette_rgb):
        parts.append(entry(CH_PALETTE + i, rgb))
    return "|".join(parts) + "|"


def level_string(L, palette_rgb, spawn_group=0):
    header = {
        "kS38": color_string(palette_rgb), "kA13": 0, "kA15": 0, "kA16": 0, "kA14": "", "kA6": 0,
        "kA7": 0, "kA25": 0, "kA17": 0, "kA18": 0, "kS39": 0, "kA2": 0, "kA3": 0, "kA8": 1,
        "kA4": 0, "kA9": 0, "kA10": 1, "kA22": 1, "kA23": 0, "kA24": 0, "kA27": 1, "kA40": 1,
        "kA41": 1, "kA42": 1, "kA28": 0, "kA29": 0, "kA31": 0, "kA32": 1, "kA36": spawn_group, "kA43": 1,
        "kA44": 0, "kA45": 1, "kA33": 1, "kA34": 1, "kA35": 0, "kA37": 1, "kA38": 1, "kA39": 1,
        "kA19": 0, "kA26": 0, "kA20": 0, "kA21": 0, "kA11": 0,
    }
    head = ",".join(f"{k},{v}" for k, v in header.items())
    return head + ";" + ";".join(object_string(o) for o in L.objects) + ";"


def write_gmd(path, name, desc, data, n_objects):
    enc = base64.urlsafe_b64encode(gzip.compress(data.encode())).decode()
    d = base64.urlsafe_b64encode(desc.encode()).decode()
    xml = ('<?xml version="1.0"?><plist version="1.0" gjver="2.0"><dict>'
           '<k>kCEK</k><i>4</i>'
           f'<k>k2</k><s>{name}</s>'
           f'<k>k3</k><s>{d}</s>'
           f'<k>k4</k><s>{enc}</s>'
           '<k>k13</k><t/><k>k16</k><i>1</i><k>k21</k><i>2</i><k>k23</k><i>5</i>'
           '<k>k43</k><t/><k>k47</k><t/>'
           f'<k>k48</k><i>{n_objects}</i>'
           '<k>k50</k><i>45</i>'
           f'<k>kI1</k><r>{gx(CAM[0]):.0f}</r><k>kI2</k><r>{gy(CAM[1]) - 160:.0f}</r><k>kI3</k><r>0.5</r>'
           '</dict></plist>')
    with open(path, "w") as f:
        f.write(xml)


# ---------------------------------------------------------------- превью
def render_preview(L, palette_rgb, hidden_groups, alphas, path, scale=3, offsets=None, scales=None):
    """Рисует видимую часть уровня так, как её покажет статичная камера."""
    cx, cy = gx(CAM[0]), gy(CAM[1])
    w, h = 569, 320
    img = Image.new("RGB", (w * scale, h * scale), (255, 255, 255))
    d = ImageDraw.Draw(img, "RGBA")
    objs = [o for o in L.objects if o[1] == BLOCK]
    objs.sort(key=lambda o: (o.get(24, 0), o.get(25, 0)))
    colors = {CH_WHITE: (255, 255, 255), CH_CHECKBOX: COLOR_NORMAL}
    colors.update({CH_PALETTE + i: c for i, c in enumerate(palette_rgb)})
    for o in objs:
        groups = [int(g) for g in str(o.get(57, "")).split(".") if g]
        a = 1.0
        for g in groups:
            if g in hidden_groups:
                a = 0
            a *= alphas.get(g, 1.0)
        if a <= 0:
            continue
        ow, oh = o.get(128, 1.0) * 30, o.get(129, 1.0) * 30
        ox, oy = o[2], o[3]
        for g in groups:
            if scales and g in scales:
                sx, sy, k = scales[g]
                ox, oy, ow, oh = sx + (ox - sx) * k, sy + (oy - sy) * k, ow * k, oh * k
            if offsets and g in offsets:
                ox, oy = ox + offsets[g][0], oy + offsets[g][1]
        x0 = (ox - ow / 2 - cx + w / 2) * scale
        y0 = (cy - oy - oh / 2 + h / 2) * scale
        col = colors.get(o[21], (255, 0, 255))
        d.rectangle([x0, y0, x0 + ow * scale, y0 + oh * scale], fill=col + (int(255 * a),))
    img.save(path)


def main():
    args = [a for a in sys.argv[1:] if a != "--swap"]
    swap = "--swap" in sys.argv
    cap, scene, mask, out = args[:4]
    preview_dir = args[4] if len(args) > 4 else None
    arts, correct = make_arts(cap, scene, mask)
    pal = build_palette(arts)
    palette_rgb = [tuple(pal.getpalette()[i * 3:i * 3 + 3]) for i in range(len(pal.getpalette()) // 3)][:250]

    L = Level()
    counts = {}
    for a in arts:
        counts[a.name] = art_objects(L, a, pal)
    build_collision(L)
    build_helpers(L)
    boot = build_logic(L, correct, swap)

    check_links(L)
    data = level_string(L, palette_rgb, boot)
    desc = "captcha: prove you are not a robot. 2P: arrows = left/right, A/D = down/up, jump = click."
    write_gmd(out, "captcha", desc, data, len(L.objects))

    info = {"objects": len(L.objects), "correct_tiles": [i for i, c in enumerate(correct) if c],
            "per_layer": counts, "gmd_bytes": os.path.getsize(out)}
    print(json.dumps(info, ensure_ascii=False))

    if preview_dir:
        os.makedirs(preview_dir, exist_ok=True)
        hidden_start = {G_SPINNER, G_GREEN, G_OVERLAY, G_POPUP, G_VERIFY, G_SUBDIM,
                        G_ERR_TRY, G_ERR_MORE, G_FILLER} | {G_TICK + i for i in range(16)}
        render_preview(L, palette_rgb, hidden_start, {}, os.path.join(preview_dir, "1_start.png"))
        def tile_center(i):
            r_, c_ = divmod(i, 4)
            return (gx(BFRAME[0] + TILE0[0] + c_ * TILE_STEP + TILE_SIZE / 2),
                    gy(BFRAME[1] + TILE0[1] + r_ * TILE_STEP + TILE_SIZE / 2))

        fresh = hidden_start - {G_POPUP, G_OVERLAY}
        render_preview(L, palette_rgb, fresh, {G_OVERLAY: 0.05},
                       os.path.join(preview_dir, "2_challenge.png"))
        picked = (5, 6)
        sel = hidden_start - {G_POPUP, G_OVERLAY, G_VERIFY, G_SUBDIM} - {G_TICK + i for i in picked}
        render_preview(L, palette_rgb, sel | {G_SKIP}, {G_OVERLAY: 0.05},
                       os.path.join(preview_dir, "3_selected.png"),
                       scales={G_TILE + i: tile_center(i) + (0.8,) for i in picked})
        err = hidden_start - {G_POPUP, G_OVERLAY, G_ERR_TRY, G_FILLER}
        render_preview(L, palette_rgb, err, {G_OVERLAY: 0.05},
                       os.path.join(preview_dir, "4_try_again.png"),
                       offsets={G_FOOTER: (0, -ERROR_H * S)})
        won = hidden_start - {G_GREEN} | {G_CHECKBOX}
        render_preview(L, palette_rgb, won, {}, os.path.join(preview_dir, "5_done.png"))
        with open(os.path.join(preview_dir, "level_string.txt"), "w") as f:
            f.write(data)


if __name__ == "__main__":
    main()
