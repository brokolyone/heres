"""Рисует иконку Блокнота (res/notepad.ico): лист в линейку с пружинкой сверху."""
import sys
from PIL import Image, ImageDraw

S = 256
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
# тень и лист
d.rounded_rectangle((44, 40, 220, 240), 18, fill=(0, 0, 0, 60))
d.rounded_rectangle((36, 30, 212, 230), 18, fill=(250, 250, 252), outline=(90, 110, 140), width=6)
# синяя шапка
d.rounded_rectangle((36, 30, 212, 74), 18, fill=(52, 120, 220))
d.rectangle((39, 56, 209, 74), fill=(52, 120, 220))
# линейки
for y in range(104, 222, 26):
    d.line((60, y, 188, y), fill=(150, 175, 210), width=6)
# красное поле
d.line((76, 80, 76, 224), fill=(225, 90, 90), width=4)
# пружинка
for x in range(62, 200, 30):
    d.rounded_rectangle((x, 14, x + 14, 52), 7, fill=(70, 80, 95))
    d.rounded_rectangle((x + 3, 17, x + 11, 49), 4, fill=(190, 200, 210))
out = sys.argv[1] if len(sys.argv) > 1 else "res/notepad.ico"
img.save(out, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
