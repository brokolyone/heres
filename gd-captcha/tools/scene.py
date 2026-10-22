"""Рисует свою сцену со светофорами для окна 4x4.

Сцена рисуется сразу в разрешении уровня: 192x192 пикселя, клетка 48x48.
Кроме картинки сохраняется маска светофоров: по ней генератор решает,
какие клетки правильные.
"""
import sys
from PIL import Image, ImageDraw

N = 192

SKY = [(150, 190, 228), (163, 199, 233), (176, 208, 238), (190, 217, 241), (204, 226, 244)]
TOWER = (126, 136, 150)
TOWER_DARK = (98, 108, 122)
TOWER_WIN = (170, 184, 198)
BLD = (150, 146, 138)
BLD_DARK = (118, 114, 108)
TREE = (74, 112, 64)
TREE_DARK = (52, 84, 48)
TREE_LIGHT = (98, 138, 80)
WALL = (140, 140, 136)
WALL_DARK = (112, 112, 108)
WALK = (176, 174, 168)
ROAD = (92, 95, 100)
ROAD_DARK = (74, 77, 82)
LINE = (226, 226, 220)
POLE = (122, 116, 104)
POLE_DARK = (92, 88, 80)
STEEL = (110, 114, 116)
WIRE = (60, 62, 64)
TL_BODY = (38, 41, 40)
TL_PLATE = (24, 26, 25)
TL_RED = (92, 40, 38)
TL_AMB = (96, 80, 34)
TL_GREEN = (70, 226, 128)
CAR_W = (232, 232, 230)
CAR_W2 = (196, 198, 200)
CAR_D = (56, 60, 66)
CAR_D2 = (36, 38, 42)
GLASS = (44, 54, 64)
BUS = (40, 74, 168)
BUS_TOP = (220, 222, 224)
RED_LIGHT = (200, 40, 40)
SIGN = (236, 236, 236)
SIGN_RED = (200, 34, 34)


def draw_scene():
    img = Image.new("RGB", (N, N), SKY[-1])
    mask = Image.new("L", (N, N), 0)
    d = ImageDraw.Draw(img)
    m = ImageDraw.Draw(mask)

    # Небо полосами, без плавного градиента: так меньше объектов.
    band = 22
    for i, c in enumerate(SKY):
        d.rectangle([0, i * band, N, (i + 1) * band], fill=c)

    # Дальние высотки слева.
    d.rectangle([10, 46, 34, 128], fill=TOWER)
    d.rectangle([28, 46, 34, 128], fill=TOWER_DARK)
    for y in range(52, 124, 6):
        d.rectangle([13, y, 26, y + 2], fill=TOWER_WIN)
    d.rectangle([0, 80, 9, 128], fill=TOWER_DARK)
    d.rectangle([40, 92, 60, 128], fill=TOWER)
    d.rectangle([62, 100, 80, 128], fill=TOWER_DARK)
    for y in range(96, 124, 5):
        d.rectangle([43, y, 57, y + 1], fill=TOWER_WIN)

    # Деревья и стена справа.
    d.ellipse([132, 60, 192, 128], fill=TREE)
    d.ellipse([150, 52, 200, 104], fill=TREE_LIGHT)
    d.ellipse([140, 90, 176, 130], fill=TREE_DARK)
    d.rectangle([84, 112, 110, 134], fill=BLD)
    d.rectangle([100, 112, 110, 134], fill=BLD_DARK)
    d.rectangle([148, 118, 192, 150], fill=WALL)
    d.rectangle([148, 118, 152, 150], fill=WALL_DARK)

    # Дорога в перспективе и тротуар.
    d.polygon([(0, 128), (150, 128), (192, 150), (192, 192), (0, 192)], fill=ROAD)
    d.polygon([(118, 128), (150, 128), (192, 150), (192, 172)], fill=WALK)
    d.rectangle([0, 128, 150, 130], fill=ROAD_DARK)
    for x0, y0, x1, y1 in [(70, 140, 74, 150), (64, 158, 69, 172), (57, 180, 63, 192)]:
        d.rectangle([x0, y0, x1, y1], fill=LINE)

    # Провода.
    d.line([(0, 18), (192, 34)], fill=WIRE)
    d.line([(0, 30), (120, 22), (192, 46)], fill=WIRE)
    d.line([(60, 0), (120, 26)], fill=WIRE)

    # Деревянный столб с траверсой и трансформатором (без светофоров).
    d.rectangle([116, 14, 120, 176], fill=POLE)
    d.rectangle([119, 14, 120, 176], fill=POLE_DARK)
    d.rectangle([106, 22, 132, 24], fill=POLE_DARK)
    d.rectangle([110, 34, 126, 46], fill=STEEL)
    d.rectangle([112, 46, 124, 49], fill=POLE_DARK)

    # Мачта с консолью над дорогой.
    d.rectangle([126, 52, 129, 178], fill=STEEL)
    d.line([(127, 57), (76, 44)], fill=STEEL, width=2)

    def light(x, y, w=8, h=22, plate=True):
        """Светофор: корпус, козырьки, три секции, горит зелёный."""
        if plate:
            box = [x - 2, y - 1, x + w + 1, y + h + 1]
            d.rectangle(box, fill=TL_PLATE)
            m.rectangle(box, fill=255)
        box = [x, y, x + w - 1, y + h - 1]
        d.rectangle(box, fill=TL_BODY)
        m.rectangle(box, fill=255)
        r = (w - 3) // 2
        cx = x + w // 2 - 1
        step = h // 3
        for i, c in enumerate([TL_RED, TL_AMB, TL_GREEN]):
            cy = y + step * i + step // 2 - 1
            d.ellipse([cx - r, cy - r, cx + r + 1, cy + r + 1], fill=c)

    # Главный светофор висит на консоли ровно на стыке четырёх клеток.
    d.rectangle([92, 44, 93, 46], fill=STEEL)
    light(89, 47, w=9, h=24)
    # Второй, на мачте, лезет в соседний столбец на пару пикселей.
    light(130, 98, w=8, h=20)
    # Дальний маленький у стены.
    d.rectangle([173, 124, 174, 140], fill=STEEL)
    light(171, 112, w=5, h=12, plate=False)

    # Знак «стоянка запрещена» на столбе: не светофор, ловушка для глаза.
    d.ellipse([104, 120, 115, 131], fill=SIGN_RED)
    d.ellipse([106, 122, 113, 129], fill=SIGN)
    d.line([(106, 129), (113, 122)], fill=SIGN_RED, width=2)

    # Машины.
    d.rectangle([0, 132, 26, 156], fill=BUS)
    d.rectangle([0, 132, 26, 136], fill=BUS_TOP)
    d.rectangle([2, 140, 24, 148], fill=GLASS)
    # Красные стоп-сигналы: красное, но не светофор.
    d.polygon([(36, 152), (82, 152), (90, 166), (90, 192), (28, 192), (28, 166)], fill=CAR_D)
    d.rectangle([38, 156, 80, 166], fill=GLASS)
    d.rectangle([30, 172, 36, 176], fill=RED_LIGHT)
    d.rectangle([82, 172, 88, 176], fill=RED_LIGHT)
    d.rectangle([28, 182, 90, 192], fill=CAR_D2)
    d.polygon([(0, 160), (22, 160), (30, 174), (30, 192), (0, 192)], fill=CAR_W)
    d.rectangle([0, 164, 20, 172], fill=GLASS)
    d.rectangle([0, 182, 30, 192], fill=CAR_W2)
    d.polygon([(132, 168), (176, 168), (184, 180), (184, 192), (124, 192), (124, 180)], fill=CAR_W2)
    d.rectangle([136, 171, 172, 179], fill=GLASS)
    d.rectangle([126, 184, 132, 188], fill=RED_LIGHT)
    d.rectangle([176, 184, 182, 188], fill=RED_LIGHT)

    return img, mask


def main(out_png, out_mask):
    img, mask = draw_scene()
    img.save(out_png)
    mask.save(out_mask)


if __name__ == "__main__":
    main(*sys.argv[1:3])
