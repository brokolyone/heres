import os, subprocess, textwrap, random
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H, FPS = 1920, 1080, 30
OUT = "/home/user/heres/a4_video"
TMP = os.path.join(os.path.dirname(__file__), "seg")
os.makedirs(TMP, exist_ok=True)
SANS = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
SERIF_B = "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"
BG = (14, 14, 16)
FG = (236, 232, 224)
DIM = (130, 128, 122)
RED = (200, 40, 40)

def background():
    img = Image.new("RGB", (W, H), BG)
    # vignette
    v = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(v)
    d.ellipse((-300, -250, W + 300, H + 250), fill=255)
    v = v.filter(ImageFilter.GaussianBlur(220))
    light = Image.new("RGB", (W, H), (26, 26, 30))
    img = Image.composite(light, img, v)
    # film grain
    random.seed(1)
    g = Image.effect_noise((W, H), 18).convert("RGB")
    img = Image.blend(img, g, 0.035)
    return img

BASE = background()

def wrap(draw, text, font, maxw):
    lines = []
    for para in text.split("\n"):
        words, cur = para.split(), ""
        for w in words:
            t = (cur + " " + w).strip()
            if draw.textlength(t, font=font) <= maxw:
                cur = t
            else:
                lines.append(cur); cur = w
        lines.append(cur)
    return lines

def card_text(text, chapter=None, size=64, accent=False):
    img = BASE.copy(); d = ImageDraw.Draw(img)
    f = ImageFont.truetype(SANS, size)
    lines = wrap(d, text, f, 1400)
    lh = int(size * 1.35)
    y = (H - lh * len(lines)) // 2
    for ln in lines:
        d.text(((W - d.textlength(ln, font=f)) // 2, y), ln, font=f, fill=RED if accent else FG)
        y += lh
    if chapter:
        fc = ImageFont.truetype(BOLD, 26)
        d.rectangle((120, 96, 128, 132), fill=RED)
        d.text((146, 98), chapter.upper(), font=fc, fill=DIM)
    return img

def card_chapter(num, title):
    img = BASE.copy(); d = ImageDraw.Draw(img)
    fn = ImageFont.truetype(BOLD, 34); ft = ImageFont.truetype(SERIF_B, 110)
    n = f"ГЛАВА {num}"
    d.text(((W - d.textlength(n, font=fn)) // 2, 400), n, font=fn, fill=RED)
    d.text(((W - d.textlength(title, font=ft)) // 2, 470), title, font=ft, fill=FG)
    d.rectangle((W // 2 - 60, 640, W // 2 + 60, 644), fill=RED)
    return img

def card_title():
    img = BASE.copy(); d = ImageDraw.Draw(img)
    f1 = ImageFont.truetype(SERIF_B, 150); f2 = ImageFont.truetype(SANS, 54)
    t1, t2 = "ИЗ КНЯЗИ В ГРЯЗИ", "как А4 пал*"
    d.text(((W - d.textlength(t1, font=f1)) // 2, 380), t1, font=f1, fill=FG)
    d.text(((W - d.textlength(t2, font=f2)) // 2, 590), t2, font=f2, fill=RED)
    return img

def card_insert(label):
    img = BASE.copy(); d = ImageDraw.Draw(img)
    d.rectangle((260, 200, W - 260, H - 200), outline=(70, 70, 74), width=3)
    f = ImageFont.truetype(BOLD, 30); f2 = ImageFont.truetype(SANS, 40)
    t = "ВСТАВКА"
    d.text(((W - d.textlength(t, font=f)) // 2, 440), t, font=f, fill=RED)
    for i, ln in enumerate(wrap(d, label, f2, 1200)):
        d.text(((W - d.textlength(ln, font=f2)) // 2, 500 + i * 56), ln, font=f2, fill=DIM)
    return img

def chart_frames(path_prefix, n):
    # stylised rise-and-decline curve, drawn progressively (illustrative)
    pts = []
    for i in range(101):
        x = i / 100
        y = (x / 0.45) ** 2 if x < 0.45 else 1 - 0.75 * ((x - 0.45) / 0.55) ** 0.8
        pts.append((260 + x * 1400, 860 - y * 560))
    files = []
    for k in range(n):
        p = min(1, (k + 1) / (n * 0.8))
        img = BASE.copy(); d = ImageDraw.Draw(img)
        d.line((260, 860, 1660, 860), fill=(70, 70, 74), width=2)
        fs = ImageFont.truetype(BOLD, 26)
        d.rectangle((120, 96, 128, 132), fill=RED)
        d.text((146, 98), "СРЕДНИЕ ПРОСМОТРЫ (СХЕМАТИЧНО)", font=fs, fill=DIM)
        m = max(2, int(p * len(pts)))
        seg = pts[:m]
        col = FG if m <= 46 else RED
        d.line(seg[:46], fill=FG, width=6)
        if m > 46:
            d.line(seg[45:], fill=RED, width=6)
        x, y = seg[-1]
        d.ellipse((x - 10, y - 10, x + 10, y + 10), fill=col)
        f = os.path.join(TMP, f"{path_prefix}_{k:04d}.png"); img.save(f); files.append(f)
    return files

def render_still(img, dur, name, fade=0.6):
    png = os.path.join(TMP, name + ".png"); img.save(png)
    mp4 = os.path.join(TMP, name + ".mp4")
    st = max(0, dur - fade)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-framerate", str(FPS), "-i", png,
        "-t", f"{dur}", "-vf", f"fade=in:st=0:d={fade},fade=out:st={st}:d={fade},format=yuv420p",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-r", str(FPS), mp4], check=True)
    return mp4

def render_chart(dur, name):
    n = int(dur * FPS)
    chart_frames(name, n)
    mp4 = os.path.join(TMP, name + ".mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", os.path.join(TMP, name + "_%04d.png"),
        "-vf", f"fade=in:st=0:d=0.5,fade=out:st={dur-0.6}:d=0.6,format=yuv420p",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18", mp4], check=True)
    return mp4

def dur_for(text):
    return round(max(3.0, len(text.split()) / 1.7 + 1.6), 2)

# (kind, payload, chapter)
S = []
def T(text, ch=None, **kw): S.append(("text", text, ch, kw))

T("Несколько лет назад этого человека знал почти каждый школьник.")
T("Его лицо было на шоколадках, напитках, игрушках и одежде.")
T("Он был главным героем детства целого поколения.")
T("Сегодня всё иначе.", accent=True, size=80)
S.append(("title", None, None, {}))

S.append(("chapter", ("I", "Восхождение"), None, {}))
c = "Восхождение"
T("Начиналось всё просто: камера, комната, челленджи.", c)
T("Таких каналов были сотни.", c)
T("Но Влад раньше других понял главное: он снимает для детей.", c)
T("Яркая картинка. Громкие эмоции. Простые правила.", c)
S.append(("insert", "Фрагмент раннего ролика А4 (5–10 сек, с комментарием)", c, {}))
T("Вокруг Влада появилась постоянная команда, и канал превратился в бесконечный сериал со своими героями и мемами.", c)
T("Дети смотрели подолгу, пересматривали, включали автовоспроизведение.", c)
T("Алгоритм это любил.", c, accent=True)
T("10 миллионов. 20. 30. Больше.", c, size=80)

S.append(("chapter", ("II", "Империя"), None, {}))
c = "Империя"
T("Сладости, игрушки, мерч, заведения, игры.", c)
T("А4 стал брендом, который продавался в обычных магазинах.", c)
S.append(("insert", "Фото мерча и продукции на полках (свои снимки или пресс-материалы)", c, {}))
T("Ролики становились масштабнее и дороже.", c)
T("Но чем больше становилась империя, тем уязвимее она была.", c, accent=True)

S.append(("chapter", ("III", "Трещины"), None, {}))
c = "Трещины"
T("Первая трещина: аудитория выросла.", c, accent=True)
T("Ребёнок, который в девять лет обожал А4, в четырнадцать стесняется в этом признаться.", c)
T("Новые дети росли на коротких видео. Длинный челлендж конкурировал с бесконечной лентой.", c)
T("Вторая трещина: формат приелся.", c, accent=True)
S.append(("insert", "Сетка из 6–8 похожих превью канала", c, {}))
T("Формула, которая принесла успех, превратилась в ловушку.", c)
T("Третья трещина: конкуренция.", c, accent=True)
T("Нишу заполнили десятки похожих каналов. Быстрее, дешевле, агрессивнее.", c)
T("Четвёртая трещина: репутация.", c, accent=True)
T("Чем известнее бренд, тем больше к нему вопросов.", c)
S.append(("insert", "2–3 подтверждённых публичных спора: скриншоты СМИ с указанием источника", c, {}))

S.append(("chapter", ("IV", "Падение"), None, {}))
c = "Падение"
T("Падение не было громким.", c)
T("Средние просмотры просто начали снижаться. Ролик за роликом. Месяц за месяцем.", c)
S.append(("chart", 7.0, c, {}))
S.append(("insert", "Реальные цифры: средние просмотры на пике и сейчас (Social Blade / ViewStats)", c, {}))
T("Подписчик и зритель — это разные вещи.", c, accent=True)
T("Стать взрослее значит потерять детей.\nОстаться детским значит стать «тем самым каналом из детства».", c)

S.append(("chapter", ("V", "Итог"), None, {}))
c = "Итог"
T("Так пал ли А4?", c, size=80)
T("Канал по-прежнему огромный. Бизнес существует.", c)
T("Пал не столько сам Влад, сколько эпоха, в которой он был королём.", c)
T("Тебя любят, пока твой зритель не вырастет.", c)
T("А потом ты становишься воспоминанием.", c, accent=True)
S.append(("title", None, None, {}))

files = []
for i, (kind, p, ch, kw) in enumerate(S):
    name = f"s{i:03d}"
    if kind == "text":
        files.append(render_still(card_text(p, ch, **kw), dur_for(p) + (1.5 if kw.get("accent") else 0), name))
    elif kind == "title":
        files.append(render_still(card_title(), 5, name, fade=1.0))
    elif kind == "chapter":
        files.append(render_still(card_chapter(*p), 3.5, name))
    elif kind == "insert":
        files.append(render_still(card_insert(p), 7, name))
    elif kind == "chart":
        files.append(render_chart(p, name))

lst = os.path.join(TMP, "list.txt")
open(lst, "w").write("".join(f"file '{f}'\n" for f in files))
final = os.path.join(OUT, "iz_knyazi_v_gryazi_animatic.mp4")
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst,
    "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-shortest",
    "-c:v", "copy", "-c:a", "aac", "-movflags", "+faststart", final], check=True)
print(final)
