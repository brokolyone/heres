"""Холст, палитра и примитивы пиксельной графики.

Всё рисуется на маленьком холсте W×H и увеличивается в SCALE раз без сглаживания (Image.NEAREST),
поэтому каждый блок SCALE×SCALE на выходе одноцветный. Плавных градиентов и сглаживания нет — только
сплошные заливки и упорядоченный дизеринг (шахматка, матрицы Байера 2×2 и 4×4).

Цвета задаются ключами палитры: «<рампа><тон>», где тон 0 — самая тёмная тень, последний — блик
(«rust0»…«rust3», «oil0»…«oil2»), плюс одиночные цвета «k» (контур), «white», «line», «bg».
Тени в рампах уходят в синеву/фиолет, блики — в тёплый жёлтый: так материалы выглядят цельно.
Можно передавать и готовый кортеж RGB.
"""

import io
import math
import random

from PIL import Image

W, H = 128, 72
SCALE = 5

# Тональные рампы материалов: индекс 0 — тень, последний — блик.
RAMPS: dict[str, tuple[tuple[int, int, int], ...]] = {
    # Небо и воздух
    "sky": ((20, 19, 29), (28, 27, 38), (36, 33, 48), (46, 41, 58)),  # sky1 = фон референса #1c1b26
    "smog": ((46, 43, 58), (58, 54, 72), (74, 68, 88), (94, 87, 108)),
    "haze": ((58, 44, 54), (82, 58, 60), (116, 80, 66)),  # тёплое зарево смога у горизонта
    "sil": ((16, 15, 23), (23, 21, 32), (37, 33, 49)),  # силуэты: 0 — тени, 1 — ближний план, 2 — дальний
    # Земля
    "ground": ((30, 26, 32), (41, 35, 39), (56, 47, 47)),
    "road": ((22, 21, 28), (31, 29, 37), (44, 41, 50)),
    # Материалы
    "rust": ((72, 32, 36), (118, 50, 42), (160, 74, 50), (202, 112, 68)),
    "steel": ((42, 46, 62), (68, 76, 96), (104, 116, 138), (150, 164, 182)),
    "brass": ((104, 68, 36), (156, 110, 46), (210, 160, 74), (244, 212, 130)),
    "oil": ((13, 12, 19), (25, 23, 33), (43, 39, 55)),  # мазут / чёрная краска
    "fire": ((150, 46, 36), (220, 102, 44), (250, 166, 62), (255, 232, 150)),
    "glass": ((44, 72, 98), (82, 136, 164), (152, 206, 222)),  # холодное стекло кабин
    "lamp": ((122, 80, 46), (214, 150, 70), (255, 216, 124)),  # тёплый свет в окнах и фонарях
    "skin": ((138, 84, 66), (196, 132, 98), (232, 178, 138)),
    "cloth": ((34, 40, 60), (56, 68, 96), (86, 104, 136)),
    "wood": ((64, 40, 32), (100, 66, 44), (142, 96, 60)),
    "paper": ((148, 130, 104), (198, 182, 148), (234, 224, 198)),
    "green": ((38, 76, 58), (68, 126, 84), (118, 180, 112)),
    "red": ((100, 30, 34), (158, 46, 44), (212, 80, 60)),
    "ore": ((88, 50, 48), (136, 80, 62), (180, 116, 84)),
    "coal": ((26, 25, 32), (44, 42, 52), (72, 70, 84)),
}

P: dict[str, tuple[int, int, int]] = {f"{name}{i}": rgb for name, ramp in RAMPS.items() for i, rgb in enumerate(ramp)}
P.update({
    "k": (12, 11, 18),  # контур
    "white": (234, 228, 212),
    "line": (112, 100, 78),  # разметка дороги
    "bg": RAMPS["sky"][1],  # плоский фон предметных сцен
})


def ramp(name: str) -> list[str]:
    """Ключи тонов рампы от тени к блику: ramp("rust") → ["rust0", "rust1", "rust2", "rust3"]."""
    return [f"{name}{i}" for i in range(len(RAMPS[name]))]


def tone(name: str, i: int) -> str:
    """Ключ тона рампы с обрезкой индекса: tone("oil", 5) → "oil2", tone("rust", -1) → "rust0"."""
    return f"{name}{max(0, min(i, len(RAMPS[name]) - 1))}"


def lum(rgb: tuple[int, int, int]) -> float:
    return 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]


# Пороговые матрицы упорядоченного дизеринга, нормированы в (0, 1).
_PATTERNS: dict[str, list[list[float]]] = {
    "checker": [[0.25, 0.75], [0.75, 0.25]],
    "bayer2": [[(v + 0.5) / 4 for v in row] for row in ((0, 2), (3, 1))],
    "bayer4": [[(v + 0.5) / 16 for v in row] for row in ((0, 8, 2, 10), (12, 4, 14, 6), (3, 11, 1, 9), (15, 7, 13, 5))],
}

Color = str | tuple[int, int, int]


class Canvas:
    """Пиксельный холст. Детерминирован: случайность только из self.rnd, засеянного seed.

    theme — локация сцены для горизонта: rust | mazut | kotlo | None.
    transparent — прозрачный слой (RGBA) для спрайтов, которые потом кладутся через paste (в т. ч. зеркально).
    """

    def __init__(self, seed: int = 1, theme: str | None = None, w: int = W, h: int = H, transparent: bool = False):
        self.theme = theme
        self.w, self.h = w, h
        self.transparent = transparent
        self.img = Image.new("RGBA", (w, h), (0, 0, 0, 0)) if transparent else Image.new("RGB", (w, h), P["bg"])
        self.px = self.img.load()
        self.rnd = random.Random(seed)

    # --- Базовые примитивы ---------------------------------------------------------------------------

    def rgb(self, c: Color) -> tuple[int, int, int]:
        return P[c] if isinstance(c, str) else c

    def get(self, x: int, y: int) -> tuple[int, int, int] | None:
        """Цвет пикселя или None (вне холста / прозрачный пиксель слоя)."""
        if not (0 <= x < self.w and 0 <= y < self.h):
            return None
        v = self.px[x, y]
        if self.transparent:
            return v[:3] if v[3] else None
        return v

    def dot(self, x: int, y: int, c: Color) -> None:
        if 0 <= x < self.w and 0 <= y < self.h:
            rgb = P[c] if isinstance(c, str) else c
            self.px[x, y] = (*rgb, 255) if self.transparent else rgb

    def clear(self, x: int, y: int) -> None:
        """Стереть пиксель: на слое — сделать прозрачным, на холсте — залить фоном."""
        if 0 <= x < self.w and 0 <= y < self.h:
            self.px[x, y] = (0, 0, 0, 0) if self.transparent else P["bg"]

    def fill(self, c: Color) -> None:
        self.rect(0, 0, self.w, self.h, c)

    def rect(self, x: int, y: int, w: int, h: int, fill: Color | None, outline: Color | None = None) -> None:
        """Прямоугольник; fill=None — только контур."""
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                edge = outline is not None and (xx in (x, x + w - 1) or yy in (y, y + h - 1))
                if edge:
                    self.dot(xx, yy, outline)
                elif fill is not None:
                    self.dot(xx, yy, fill)

    def hline(self, x: int, y: int, w: int, c: Color) -> None:
        for xx in range(x, x + w):
            self.dot(xx, y, c)

    def vline(self, x: int, y: int, h: int, c: Color) -> None:
        for yy in range(y, y + h):
            self.dot(x, yy, c)

    def line(self, x0: int, y0: int, x1: int, y1: int, c: Color) -> None:
        """Отрезок по Брезенхэму (тросы, балки, стрелки)."""
        dx, dy = abs(x1 - x0), -abs(y1 - y0)
        sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
        err = dx + dy
        while True:
            self.dot(x0, y0, c)
            if x0 == x1 and y0 == y1:
                return
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def poly(self, points: list[tuple[int, int]], c: Color) -> None:
        """Залитый многоугольник (крыши, отвалы, факелы) — построчная заливка по центрам пикселей."""
        ys = [p[1] for p in points]
        n = len(points)
        for y in range(min(ys), max(ys) + 1):
            yc = y + 0.5
            xs = []
            for i in range(n):
                (xa, ya), (xb, yb) = points[i], points[(i + 1) % n]
                if (ya <= yc < yb) or (yb <= yc < ya):
                    xs.append(xa + (yc - ya) * (xb - xa) / (yb - ya))
            xs.sort()
            for a, b in zip(xs[::2], xs[1::2]):
                for x in range(math.ceil(a - 0.5), math.floor(b - 0.5) + 1):
                    self.dot(x, y, c)

    @staticmethod
    def in_disk(dx: int, dy: int, r: int) -> bool:
        return dx * dx + dy * dy <= r * r + r  # «+ r» даёт ровные пиксельные круги

    def disk(self, cx: int, cy: int, r: int, c: Color) -> None:
        """Залитый круг диаметром 2r+1 с центром в пикселе (cx, cy)."""
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                if self.in_disk(dx, dy, r):
                    self.dot(cx + dx, cy + dy, c)

    def ring(self, cx: int, cy: int, r: int, c: Color) -> None:
        """Окружность толщиной в пиксель."""
        for dy in range(-r - 1, r + 2):
            for dx in range(-r - 1, r + 2):
                if self.in_disk(dx, dy, r) and not self.in_disk(dx, dy, r - 1):
                    self.dot(cx + dx, cy + dy, c)

    def sprite(self, x: int, y: int, rows: list[str], pal: dict[str, Color], flip: bool = False) -> None:
        """Спрайт из строк символов; «.» и символы вне pal прозрачны. flip — зеркально по горизонтали."""
        for j, row in enumerate(rows):
            if flip:
                row = row[::-1]
            for i, ch in enumerate(row):
                if ch != "." and ch in pal:
                    self.dot(x + i, y + j, pal[ch])

    def outline_sprite(self, x: int, y: int, rows: list[str], pal: dict[str, Color], outline: Color = "k",
                       flip: bool = False) -> None:
        """Спрайт с контуром в пиксель вокруг непрозрачной части (по 4 соседям)."""
        cells = set()
        for j, row in enumerate(rows):
            if flip:
                row = row[::-1]
            for i, ch in enumerate(row):
                if ch != "." and ch in pal:
                    cells.add((i, j))
        for i, j in cells:
            for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                if (i + di, j + dj) not in cells:
                    self.dot(x + i + di, y + j + dj, outline)
        self.sprite(x, y, rows, pal, flip)

    # --- Объём и свет --------------------------------------------------------------------------------

    def box(self, x: int, y: int, w: int, h: int, ramp_name: str, outline: Color | None = "k",
            base: int | None = None) -> None:
        """Объёмный прямоугольник: заливка тоном base, блик сверху-слева, тень снизу-справа, контур.

        base по умолчанию — середина рампы (2 из 0..3, 1 из 0..2). Свет всегда падает сверху-слева.
        """
        tones = ramp(ramp_name)
        b = len(tones) // 2 if base is None else max(0, min(base, len(tones) - 1))
        hi, lo = tones[min(b + 1, len(tones) - 1)], tones[max(b - 1, 0)]
        self.rect(x, y, w, h, tones[b])
        i = 1 if outline is not None else 0
        ix, iy, iw, ih = x + i, y + i, w - 2 * i, h - 2 * i
        if iw > 0 and ih > 0:
            if ih > 1:
                self.hline(ix, iy + ih - 1, iw, lo)
            if iw > 1:
                self.vline(ix + iw - 1, iy, ih, lo)
            self.hline(ix, iy, iw - (1 if iw > 1 else 0), hi)
            self.vline(ix, iy, ih - (1 if ih > 1 else 0), hi)
        if outline is not None:
            self.rect(x, y, w, h, None, outline)

    shaded_rect = box

    def shaded_disk(self, cx: int, cy: int, r: int, ramp_name: str, outline: Color | None = "k",
                    base: int | None = None) -> None:
        """Объёмный круг (колесо, бак, луна): блик по верхне-левой кромке, тень по нижне-правой."""
        tones = ramp(ramp_name)
        b = len(tones) // 2 if base is None else max(0, min(base, len(tones) - 1))
        hi, lo = tones[min(b + 1, len(tones) - 1)], tones[max(b - 1, 0)]
        for dy in range(-r - 1, r + 2):
            for dx in range(-r - 1, r + 2):
                inside = self.in_disk(dx, dy, r)
                if inside:
                    if not self.in_disk(dx + 1, dy + 1, r):
                        col = lo
                    elif not self.in_disk(dx - 1, dy - 1, r):
                        col = hi
                    else:
                        col = tones[b]
                    self.dot(cx + dx, cy + dy, col)
                elif outline is not None and any(self.in_disk(dx + a, dy + b2, r)
                                                 for a, b2 in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                    self.dot(cx + dx, cy + dy, outline)

    # --- Дизеринг ------------------------------------------------------------------------------------

    @staticmethod
    def threshold(x: int, y: int, pattern: str = "bayer4") -> float:
        """Порог упорядоченного дизеринга в точке (0..1). Пиксель «включён», если threshold < level.

        Координаты абсолютные, поэтому узор совпадает у соседних фигур и не «плывёт».
        """
        m = _PATTERNS[pattern]
        n = len(m)
        return m[y % n][x % n]

    def dither(self, x: int, y: int, w: int, h: int, c1: Color | None, c2: Color, level: float = 0.5,
               pattern: str = "checker") -> None:
        """Смесь двух цветов: доля c2 ≈ level. c1=None — c2 кладётся поверх как сетка (прозрачная дымка)."""
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                if self.threshold(xx, yy, pattern) < level:
                    self.dot(xx, yy, c2)
                elif c1 is not None:
                    self.dot(xx, yy, c1)

    def vgradient(self, x: int, y: int, w: int, h: int, colors: list[Color], blend: int = 3,
                  pattern: str = "bayer4") -> None:
        """Вертикальный градиент полосами: сплошные полосы цветов сверху вниз, между ними дизер-переход
        высотой blend строк (уровни 1/(blend+1) … blend/(blend+1))."""
        m = len(colors)
        if m == 1 or h <= 0:
            self.rect(x, y, w, h, colors[0])
            return
        bounds = [round(h * k / m) for k in range(1, m)]  # строка, с которой начинается следующий цвет
        for j in range(h):
            k = sum(1 for b in bounds if j >= b + (blend + 1) // 2)  # индекс «сплошного» цвета
            level = 0.0
            if k < m - 1:
                start = bounds[k] - blend // 2
                if j >= start:
                    level = (j - start + 1) / (blend + 1)
            ca = colors[k]
            if level <= 0:
                self.hline(x, y + j, w, ca)
            else:
                cb = colors[k + 1]
                for xx in range(x, x + w):
                    self.dot(xx, y + j, cb if self.threshold(xx, y + j, pattern) < level else ca)

    def glow(self, cx: int, cy: int, r: int, colors: list[Color], soft: float = 0.5, pattern: str = "checker",
             lighten: bool = True) -> None:
        """Ореол вокруг источника света: концентрические кольца colors (от внешнего к внутреннему),
        внешняя доля soft каждого кольца — шахматный переход к предыдущему. lighten — менять пиксель
        только если новый цвет светлее (ореол ложится поверх чего угодно, не затемняя)."""
        n = len(colors)
        rgbs = [self.rgb(c) for c in colors]
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                d = math.hypot(dx, dy)
                if d > r + 0.25:
                    continue
                pos = max(0.0, (1 - d / (r + 0.5))) * n
                i = min(int(pos), n - 1)
                f = pos - int(pos) if int(pos) < n else 1.0
                x, y = cx + dx, cy + dy
                if f < soft and self.threshold(x, y, pattern) >= 0.5:
                    if i == 0:
                        continue
                    i -= 1
                new = rgbs[i]
                if lighten:
                    old = self.get(x, y)
                    if old is not None and lum(old) >= lum(new):
                        continue
                self.dot(x, y, new)

    # --- Детали --------------------------------------------------------------------------------------

    def sparkle(self, x: int, y: int, c: Color = "white", arm: int = 1, tip: Color | None = None) -> None:
        """Искра/звезда-крестик: центр и четыре луча длиной arm; кончики лучей цветом tip."""
        self.dot(x, y, c)
        for k in range(1, arm + 1):
            col = tip if (tip is not None and k == arm) else c
            for dx, dy in ((k, 0), (-k, 0), (0, k), (0, -k)):
                self.dot(x + dx, y + dy, col)

    def rivets(self, x: int, y: int, n: int, step: int = 3, c: Color = "steel3", shadow: Color | None = None,
               vertical: bool = False) -> None:
        """Ряд заклёпок: светлая точка и (если задано) тень под ней (справа — у вертикального ряда)."""
        for i in range(n):
            px, py = (x, y + i * step) if vertical else (x + i * step, y)
            self.dot(px, py, c)
            if shadow is not None:
                self.dot(px + (1 if vertical else 0), py + (0 if vertical else 1), shadow)

    def windows(self, x: int, y: int, cols: int, rows: int, ww: int = 2, wh: int = 2, gx: int = 1, gy: int = 1,
                lit: float = 0.4, on: tuple[Color, Color] = ("lamp1", "lamp2"), off: Color = "oil1",
                frame: Color | None = None) -> None:
        """Сетка окон: доля lit горит (on[0] с бликом on[1] в верхнем левом пикселе), остальные off.
        frame — цвет рамки вокруг каждого окна. Какие окна горят — решает self.rnd (детерминированно)."""
        for j in range(rows):
            for i in range(cols):
                wx, wy = x + i * (ww + gx), y + j * (wh + gy)
                if frame is not None:
                    self.rect(wx - 1, wy - 1, ww + 2, wh + 2, None, frame)
                if self.rnd.random() < lit:
                    self.rect(wx, wy, ww, wh, on[0])
                    self.dot(wx, wy, on[1])
                else:
                    self.rect(wx, wy, ww, wh, off)

    def shadow(self, x: int, y: int, w: int, c: Color = "oil0") -> None:
        """Контактная тень под предметом: строка y шириной w со «рваными» дизерными краями."""
        self.hline(x + 2, y, w - 4, c)
        for xx in (x, x + 1, x + w - 2, x + w - 1):
            if self.threshold(xx, y, "checker") < 0.5:
                self.dot(xx, y, c)

    def speckle(self, x: int, y: int, w: int, h: int, colors: list[Color], n: int) -> None:
        """n случайных точек цветов colors в области (гравий, крошка руды, пятна ржавчины)."""
        for _ in range(n):
            self.dot(x + self.rnd.randrange(max(1, w)), y + self.rnd.randrange(max(1, h)), self.rnd.choice(colors))

    def bricks(self, x: int, y: int, w: int, h: int, brick: Color, mortar: Color, bw: int = 4, bh: int = 2,
               accent: Color | None = None) -> None:
        """Кладка: заливка brick, швы mortar (ряд через ряд со сдвигом на полкирпича); accent — блики
        на части кирпичей."""
        self.rect(x, y, w, h, brick)
        for j in range(h):
            row, sub = divmod(j, bh)
            if sub == bh - 1:
                self.hline(x, y + j, w, mortar)
                continue
            off = (bw // 2) * (row % 2)
            for i in range(w):
                if (i + off) % bw == bw - 1:
                    self.dot(x + i, y + j, mortar)
                elif accent is not None and sub == 0 and (i + off) % bw == 0 and (row * 7 + (i + off) // bw) % 3 == 0:
                    self.dot(x + i, y + j, accent)

    # --- Слои ----------------------------------------------------------------------------------------

    def layer(self, w: int, h: int) -> "Canvas":
        """Прозрачный слой той же темы со своим (детерминированным) генератором случайностей."""
        return Canvas(seed=self.rnd.randrange(1 << 30), theme=self.theme, w=w, h=h, transparent=True)

    def paste(self, layer: "Canvas", x: int, y: int, flip: bool = False, outline: Color | None = None) -> None:
        """Положить слой в (x, y); flip — зеркально по горизонтали; outline — обвести силуэт слоя."""
        im = layer.img.transpose(Image.Transpose.FLIP_LEFT_RIGHT) if flip else layer.img
        if outline is not None:
            alpha = im.getchannel("A").load()
            lw, lh = im.size
            for j in range(lh):
                for i in range(lw):
                    if alpha[i, j]:
                        continue
                    if any(0 <= i + a < lw and 0 <= j + b < lh and alpha[i + a, j + b]
                           for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                        self.dot(x + i, y + j, outline)
            # контур и снаружи границ слоя
            for j in range(lh):
                for i in (0, lw - 1):
                    if alpha[i, j]:
                        self.dot(x + i + (1 if i else -1), y + j, outline)
            for i in range(lw):
                for j in (0, lh - 1):
                    if alpha[i, j]:
                        self.dot(x + i, y + j + (1 if j else -1), outline)
        src = im if self.transparent else im.convert("RGB")
        self.img.paste(src, (x, y), im.getchannel("A"))

    # --- Вывод ---------------------------------------------------------------------------------------

    def png(self) -> bytes:
        out = io.BytesIO()
        img = self.img.convert("RGB") if self.transparent else self.img
        img.resize((self.w * SCALE, self.h * SCALE), Image.NEAREST).save(out, "PNG", optimize=True)
        return out.getvalue()
