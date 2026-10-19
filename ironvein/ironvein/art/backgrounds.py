"""Фон сцен: небо, смог, луна, два слоя горизонта по локациям, земля, дорога, рельсы, дым.

Слои рисуются от дальнего к ближнему: небо (дизер-полосы) → луна/солнце за смогом → облака →
дальний горизонт (светлее, почти без деталей) → ближний горизонт (темнее, с огнями и дымом) → земля.
"""

from ironvein.art.canvas import RAMPS, Canvas, W, tone

GY = 56  # линия горизонта / земли по умолчанию

FAR, NEAR, SHADE = "sil2", "sil1", "sil0"  # дальний план, ближний план, теневая сторона ближнего


# --- Небо ----------------------------------------------------------------------------------------------


def sky(c: Canvas, gy: int = GY, smoggy: bool = True, moon: bool = True) -> None:
    """Ночное небо дизер-полосами от sky0 сверху к тёплому зареву haze0 у горизонта, тусклое светило и смог."""
    c.vgradient(0, 0, W, gy, ["sky0", "sky1", "sky2", "sky3", "haze0"], blend=3)
    if moon:
        celestial(c)
    if smoggy:
        for _ in range(3):  # высокие тонкие полосы
            streak(c, c.rnd.randrange(-10, W), c.rnd.randrange(4, 14), c.rnd.randrange(14, 30), "sky3")
        for _ in range(4):  # кучевой смог ниже
            cloud(c, c.rnd.randrange(-8, W - 4), c.rnd.randrange(12, 28), c.rnd.randrange(12, 24), tone=1)


def celestial(c: Canvas, x: int | None = None, y: int | None = None, r: int = 4) -> None:
    """Тусклый диск за смогом: луна над столицей, рыжее солнце над шахтами, красное — над нефтепромыслом."""
    x = c.rnd.randrange(W // 2, W - 10) if x is None else x
    y = c.rnd.randrange(9, 16) if y is None else y
    ramp_name, base = {"rust": ("ore", 2), "mazut": ("fire", 0)}.get(c.theme or "", ("paper", 0))
    c.glow(x, y, r + 8, ["sky3", "smog1", tone("haze", 0)])
    c.shaded_disk(x, y, r, ramp_name, outline=None, base=base)
    # облако смога наползает на нижний край диска
    cloud(c, x - r - 3 - c.rnd.randrange(4), y + r // 2, 2 * r + 9, tone=1)


def streak(c: Canvas, x: int, y: int, w: int, col: str = "smog1") -> None:
    """Тонкая полоса смога с дизерными «рваными» концами."""
    c.hline(x + 2, y, w - 4, col)
    for xx in (x, x + 1, x + w - 2, x + w - 1):
        if (xx + y) % 2 == 0:
            c.dot(xx, y, col)


def cloud(c: Canvas, x: int, y: int, w: int, tone: int = 1, ramp_name: str = "smog") -> None:
    """Плоское облако смога: светлая макушка, тёмное брюхо, бугор сверху."""
    n = len(RAMPS[ramp_name])
    hi = f"{ramp_name}{min(tone + 1, n - 1)}"
    mid = f"{ramp_name}{tone}"
    lo = f"{ramp_name}{max(tone - 1, 0)}"
    bx = x + 2 + c.rnd.randrange(max(1, w // 2))
    bw = max(3, w // 3)
    c.hline(bx + 1, y - 1, bw - 2, hi)  # бугор
    c.hline(bx, y, bw, mid)
    c.dot(bx, y, hi)
    c.hline(x + 2, y + 1, w - 4, mid)
    c.hline(x + 2, y + 1, 2, hi)
    c.hline(x, y + 2, w, mid)
    c.hline(x + 1, y + 3, w - 3, lo)
    c.dot(x, y + 2, hi)


# --- Горизонт ------------------------------------------------------------------------------------------


def skyline(c: Canvas, gy: int = GY) -> None:
    """Оба слоя горизонта по локации сцены (Canvas.theme): дальний, затем ближний."""
    skyline_far(c, gy)
    skyline_near(c, gy)


def skyline_far(c: Canvas, gy: int = GY) -> None:
    """Дальний план: светлый силуэт (FAR) почти без деталей — воздушная перспектива в смоге."""
    theme = c.theme
    x = -c.rnd.randrange(0, 4)
    while x < W:
        if theme == "rust":  # отвалы породы и редкие копры
            if c.rnd.random() < 0.3:
                _lattice(c, x, gy, c.rnd.randrange(12, 18), FAR, width=7, slope=5, rung=4)
                x += 8
            else:
                hw = c.rnd.randrange(8, 16)
                c.poly([(x, gy), (x + hw, gy - hw // 2 - c.rnd.randrange(2, 6)), (x + 2 * hw, gy)], FAR)
                x += hw + c.rnd.randrange(2, 8)
        elif theme == "mazut":  # плоская степь, тонкие вышки с огоньками
            if c.rnd.random() < 0.45:
                h = c.rnd.randrange(10, 16)
                _lattice(c, x, gy, h, FAR, width=5, slope=6, rung=3)
                c.dot(x + 2, gy - h - 1, "fire1")
                x += 7
            else:
                w, h = c.rnd.randrange(6, 12), c.rnd.randrange(3, 6)
                c.rect(x, gy - h, w, h, FAR)
                x += w + c.rnd.randrange(3, 9)
        elif theme == "kotlo":  # высотки, шпили и купола столицы
            bw, bh = c.rnd.randrange(6, 12), c.rnd.randrange(16, 30)
            c.rect(x, gy - bh, bw, bh, FAR)
            r = c.rnd.random()
            if r < 0.25:
                c.vline(x + bw // 2, gy - bh - 6, 6, FAR)
            elif r < 0.4:
                c.disk(x + bw // 2, gy - bh, bw // 2 - 1, FAR)
            _dim_windows(c, x, gy - bh, bw, bh, 0.06)
            x += bw + c.rnd.randrange(0, 3)
        else:  # промышленный город
            bw, bh = c.rnd.randrange(6, 14), c.rnd.randrange(12, 24)
            c.rect(x, gy - bh, bw, bh, FAR)
            if c.rnd.random() < 0.35:
                cx = x + c.rnd.randrange(1, bw - 2)
                ch = c.rnd.randrange(5, 10)
                c.rect(cx, gy - bh - ch, 2, ch, FAR)
                smoke(c, cx + 1, gy - bh - ch - 1, 4, tone=1)
            _dim_windows(c, x, gy - bh, bw, bh, 0.04)
            x += bw + c.rnd.randrange(0, 3)


def skyline_near(c: Canvas, gy: int = GY) -> None:
    """Ближний план: тёмный силуэт (NEAR) с теневой стороной, огнями окон, трубами и дымом."""
    {"rust": _near_rust, "mazut": _near_mazut, "kotlo": _near_kotlo}.get(c.theme or "", _near_default)(c, gy)


def _dim_windows(c: Canvas, x: int, top: int, bw: int, bh: int, lit: float) -> None:
    for j in range(top + 2, top + bh - 1, 3):
        for i in range(x + 1, x + bw - 1, 2):
            if c.rnd.random() < lit:
                c.dot(i, j, "haze1")


def _block(c: Canvas, x: int, gy: int, bw: int, bh: int, lit: float = 0.22) -> None:
    """Корпус ближнего плана: силуэт, теневая правая грань, редкие горящие окна 1×1."""
    c.rect(x, gy - bh, bw, bh, NEAR)
    c.vline(x + bw - 1, gy - bh + 1, bh - 1, SHADE)
    for j in range(gy - bh + 2, gy - 2, 3):
        for i in range(x + 1, x + bw - 2, 2):
            if c.rnd.random() < lit:
                c.dot(i, j, "lamp1" if c.rnd.random() < 0.7 else "lamp0")


def _stack(c: Canvas, x: int, top: int, gy: int, col: str = NEAR) -> None:
    """Заводская труба ближнего плана с оголовком, сигнальным огнём и дымом."""
    c.rect(x, top, 2, gy - top, col)
    c.hline(x - 1, top, 4, col)
    c.dot(x, top + 2, "red1")
    smoke(c, x + 1, top - 1, 5, tone=1)


def _near_default(c: Canvas, gy: int) -> None:
    x = -c.rnd.randrange(0, 4)
    while x < W:
        bw, bh = c.rnd.randrange(6, 13), c.rnd.randrange(6, 15)
        if c.rnd.random() < 0.35:  # пилообразная крыша цеха
            for i in range(0, bw - 2, 4):
                c.poly([(x + i, gy - bh), (x + i + 3, gy - bh - 3), (x + i + 4, gy - bh)], NEAR)
        _block(c, x, gy, bw, bh)
        if c.rnd.random() < 0.4:
            _stack(c, x + c.rnd.randrange(1, max(2, bw - 2)), gy - bh - c.rnd.randrange(6, 12), gy - bh)
        x += bw + c.rnd.randrange(0, 4)


def _lattice(c: Canvas, x: int, gy: int, h: int, col: str, width: int, slope: int, rung: int) -> None:
    """Решётчатая башня: две сходящиеся ноги, перекладины через rung строк и зигзаг раскосов между ними
    (копёр шахты, буровая вышка)."""
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


def _headframe(c: Canvas, x: int, gy: int, h: int, col: str = NEAR) -> None:
    """Копёр шахты: решётчатая башня, шкив наверху и трос к подъёмной машине."""
    _lattice(c, x, gy, h, col, width=11, slope=4, rung=4)
    top = gy - h
    c.ring(x + 5, top - 2, 2, col)
    c.dot(x + 5, top - 2, "brass1")
    c.line(x + 7, top - 2, x + 15, gy - 8, col)
    c.rect(x + 13, gy - 8, 7, 8, col)  # здание подъёмной машины
    c.vline(x + 19, gy - 7, 7, SHADE)
    c.dot(x + 15, gy - 5, "lamp1")


def _near_rust(c: Canvas, gy: int) -> None:
    x = -c.rnd.randrange(0, 4)
    while x < W:
        r = c.rnd.random()
        if r < 0.28:
            _headframe(c, x, gy, c.rnd.randrange(14, 21))
            x += 22
        elif r < 0.5:  # отвал породы с тенью справа
            hw = c.rnd.randrange(6, 11)
            hh = hw // 2 + 2
            c.poly([(x, gy), (x + hw, gy - hh), (x + 2 * hw, gy)], NEAR)
            c.poly([(x + hw, gy - hh), (x + 2 * hw, gy), (x + hw + 2, gy)], SHADE)
            x += 2 * hw + 1
        else:
            bw, bh = c.rnd.randrange(6, 11), c.rnd.randrange(6, 12)
            _block(c, x, gy, bw, bh, 0.18)
            if c.rnd.random() < 0.5:
                _stack(c, x + 1, gy - bh - 9, gy - bh)
            x += bw + c.rnd.randrange(1, 4)


def _derrick(c: Canvas, x: int, gy: int, h: int, col: str = NEAR) -> None:
    """Нефтяная вышка с горящим факелом и его ореолом."""
    _lattice(c, x, gy, h, col, width=9, slope=6, rung=5)
    fx, fy = x + 4, gy - h - 2
    c.glow(fx, fy, 6, ["haze0", "haze1"])
    c.dot(fx, fy + 1, "fire1")
    c.dot(fx, fy, "fire2")
    c.dot(fx, fy - 1, "fire3" if c.rnd.random() < 0.5 else "fire2")
    c.dot(fx - 1 + c.rnd.randrange(3), fy - 2, "fire1")


def _tank(c: Canvas, x: int, gy: int, w: int, h: int) -> None:
    """Резервуар: цилиндр с куполом, латунный пояс и лестница."""
    c.rect(x, gy - h, w, h, NEAR)
    c.hline(x + 1, gy - h - 1, w - 2, NEAR)
    c.hline(x + 3, gy - h - 2, w - 6, NEAR)
    c.vline(x + w - 1, gy - h, h, SHADE)
    c.hline(x + 1, gy - h + 2, w - 2, "brass0")
    for j in range(gy - h + 1, gy, 2):
        c.dot(x + 1, j, SHADE)


def _near_mazut(c: Canvas, gy: int) -> None:
    x = -c.rnd.randrange(0, 4)
    while x < W:
        r = c.rnd.random()
        if r < 0.35:
            _derrick(c, x, gy, c.rnd.randrange(14, 22))
            x += 11
        elif r < 0.65:
            w, h = c.rnd.randrange(9, 15), c.rnd.randrange(5, 9)
            _tank(c, x, gy, w, h)
            x += w + 2
        else:  # трубопровод по пустоши
            w = c.rnd.randrange(4, 9)
            c.hline(x, gy - 2, w, NEAR)
            c.dot(x + w // 2, gy - 1, NEAR)
            x += w


def _near_kotlo(c: Canvas, gy: int) -> None:
    tower_at = W // 2 - 5
    x = -c.rnd.randrange(0, 4)
    while x < W:
        if x + 12 > tower_at and x < tower_at + 12:
            _clock_tower(c, tower_at, gy)
            x = tower_at + 12
            continue
        bw, bh = c.rnd.randrange(7, 12), c.rnd.randrange(12, 24)
        c.rect(x, gy - bh, bw, bh, NEAR)
        c.vline(x + bw - 1, gy - bh + 1, bh - 1, SHADE)
        if c.rnd.random() < 0.4:  # карниз и мансарда
            c.hline(x - 1, gy - bh, bw + 2, NEAR)
            c.rect(x + 2, gy - bh - 3, bw - 4, 3, NEAR)
        c.windows(x + 1, gy - bh + 2, (bw - 2) // 2, (bh - 4) // 3, ww=1, wh=1, gx=1, gy=2, lit=0.35,
                  on=("lamp1", "lamp2"), off=NEAR)
        x += bw + c.rnd.randrange(0, 2)


def _clock_tower(c: Canvas, x: int, gy: int) -> None:
    """Часовая башня столицы: светящийся циферблат с ореолом, шпиль с огнём."""
    c.rect(x, gy - 30, 11, 30, NEAR)
    c.vline(x + 10, gy - 29, 29, SHADE)
    c.rect(x + 2, gy - 36, 7, 6, NEAR)
    c.poly([(x + 2, gy - 36), (x + 5, gy - 43), (x + 9, gy - 36)], NEAR)
    c.dot(x + 5, gy - 44, "red2")
    c.glow(x + 5, gy - 24, 7, ["haze0", "haze1"])
    c.shaded_disk(x + 5, gy - 24, 3, "lamp", outline=SHADE, base=1)
    c.vline(x + 5, gy - 26, 2, "k")
    c.hline(x + 5, gy - 24, 2, "k")
    for j in range(gy - 16, gy - 2, 4):
        c.dot(x + 3, j, "lamp1")
        c.dot(x + 7, j, "lamp0")


# --- Земля, дорога, рельсы, дым ------------------------------------------------------------------------


def ground(c: Canvas, gy: int = GY) -> None:
    """Земля: освещённая кромка, темнеющий к зрителю дизер-градиент, камешки."""
    c.vgradient(0, gy, W, c.h - gy, ["ground1", "ground1", "ground0"], blend=3)
    c.hline(0, gy, W, "ground2")
    c.dither(0, gy + 1, W, 1, None, "ground2", 0.25, "bayer4")
    for _ in range(26):
        x, y = c.rnd.randrange(W), c.rnd.randrange(gy + 2, c.h)
        c.dot(x, y, "ground2")
        c.dot(x + 1, y, "ground0")


def road(c: Canvas, y: int = 58, h: int = 8) -> None:
    """Дорога шириной h от строки y: бордюр, асфальт, пунктир разметки с тенью, трещины."""
    c.rect(0, y, W, h, "road1")
    c.hline(0, y, W, "road2")
    c.hline(0, y + h - 1, W, "road0")
    c.dither(0, y + h - 2, W, 1, None, "road0", 0.5)
    mid = y + h // 2
    for x in range(2, W, 10):
        c.hline(x, mid, 5, "line")
        c.hline(x + 1, mid + 1, 5, "road0")
    for _ in range(10):
        x = c.rnd.randrange(W)
        c.dot(x, y + 1 + c.rnd.randrange(h - 2), "road2" if c.rnd.random() < 0.5 else "road0")


def rails(c: Canvas, y: int = 62) -> None:
    """Пути: y — головка дальнего рельса (на неё встают колёса), шпалы, ближний рельс и щебень."""
    c.rect(0, y + 1, W, 5, "ground1")
    c.dither(0, y + 1, W, 5, None, "steel0", 0.3, "bayer4")
    for x in range(0, W, 4):
        c.rect(x, y + 1, 3, 3, "wood1")
        c.hline(x, y + 1, 3, "wood2")
        c.hline(x, y + 3, 3, "wood0")
    c.hline(0, y, W, "steel2")
    c.hline(0, y + 3, W, "steel3")
    c.hline(0, y + 4, W, "steel1")
    for x in range(1, W, 7):
        c.dot(x, y + 3, "white")
    c.speckle(0, y + 5, W, 1, ["ground2", "steel0"], 20)


def smoke(c: Canvas, x: int, y: int, n: int = 5, tone: int = 2, ramp_name: str = "smog", drift: int = 1) -> None:
    """Дым из точки (x, y) вверх: клубы растут и сносятся вправо на drift; верхние клубы тают дизером."""
    tones = [f"{ramp_name}{i}" for i in range(len(RAMPS[ramp_name]))]
    hi, mid, lo = tones[min(tone + 1, len(tones) - 1)], tones[tone], tones[max(tone - 1, 0)]
    for i in reversed(range(n)):
        r = min(1 + i // 2, 4)
        cx = x + i * drift + (i % 2)
        cy = y - i * 2 - r
        level = 0.5 if i >= n - 2 and n > 2 else 1.0
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                if not c.in_disk(dx, dy, r):
                    continue
                px, py = cx + dx, cy + dy
                if level < 1 and c.threshold(px, py, "checker") >= level:
                    continue
                if not c.in_disk(dx - 1, dy - 1, r):
                    col = hi
                elif not c.in_disk(dx + 1, dy + 1, r):
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
