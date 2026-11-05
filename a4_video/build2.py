import os, subprocess, random, statistics
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

HERE = os.path.dirname(os.path.abspath(__file__))
CL = os.path.join(HERE, "clips")
TMP = os.path.join(HERE, "seg2"); os.makedirs(TMP, exist_ok=True)
OUT = "/home/user/heres/a4_video/iz_knyazi_v_gryazi_v2.mp4"
W, H, FPS = 1920, 1080, 30
SANS = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
SERIF_B = "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"
FG, DIM, RED = (240, 236, 228), (150, 148, 142), (215, 45, 45)
X264 = ["-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p", "-r", str(FPS)]

# ---------- data ----------
rows = []
for l in open(os.path.join(CL, "all.txt"), encoding="utf-8"):
    p = l.rstrip("\n").split("|", 2)
    if len(p) == 3 and p[1].isdigit():
        rows.append((p[0], int(p[1]), p[2]))
rows = rows[::-1]  # oldest first
have = [r for r in rows if os.path.exists(os.path.join(CL, "th", r[0] + ".jpg"))]
n = len(have)
ERA = {"early": have[: n // 5], "peak": have[n // 5 * 2: n // 5 * 3 + 10], "late": have[-40:]}

def thumb(vid):
    im = Image.open(os.path.join(CL, "th", vid + ".jpg")).convert("RGB")
    return im.crop((0, 45, 480, 315))  # strip letterbox -> 16:9

def fmt_m(v): return f"{v/1e6:.0f} млн".replace(".", ",")

# ---------- backgrounds ----------
def wall(era, seed):
    random.seed(seed)
    pool = ERA[era][:]
    random.shuffle(pool)
    tw, th = 400, 225
    cols, rws = 8, 6
    img = Image.new("RGB", (cols * tw, rws * th))
    for k in range(cols * rws):
        im = thumb(pool[k % len(pool)][0]).resize((tw, th))
        img.paste(im, ((k % cols) * tw, (k // cols) * th))
    img = img.filter(ImageFilter.GaussianBlur(5))
    img = ImageEnhance.Color(img).enhance(0.45)
    img = ImageEnhance.Brightness(img).enhance(0.22)
    path = os.path.join(TMP, f"wall_{era}_{seed}.png"); img.save(path)
    return path, img.size

WALLS = {}
def get_wall(era):
    if era not in WALLS: WALLS[era] = wall(era, len(WALLS) + 7)
    return WALLS[era]

def wrap(d, text, f, maxw):
    out = []
    for para in text.split("\n"):
        cur = ""
        for w in para.split():
            t = (cur + " " + w).strip()
            if d.textlength(t, font=f) <= maxw: cur = t
            else: out.append(cur); cur = w
        out.append(cur)
    return out

def overlay_text(text, chapter=None, size=66, accent=False):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype(BOLD if accent else SANS, size)
    lines = wrap(d, text, f, 1400); lh = int(size * 1.35)
    y = (H - lh * len(lines)) // 2
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0)); sd = ImageDraw.Draw(sh)
    for ln in lines:
        x = (W - d.textlength(ln, font=f)) // 2
        sd.text((x, y + 4), ln, font=f, fill=(0, 0, 0, 230))
        y += lh
    sh = sh.filter(ImageFilter.GaussianBlur(8))
    img = Image.alpha_composite(img, sh); d = ImageDraw.Draw(img)
    y = (H - lh * len(lines)) // 2
    for ln in lines:
        d.text(((W - d.textlength(ln, font=f)) // 2, y), ln, font=f, fill=RED if accent else FG); y += lh
    if chapter:
        fc = ImageFont.truetype(BOLD, 26)
        d.rectangle((120, 96, 128, 132), fill=RED)
        d.text((146, 98), chapter.upper(), font=fc, fill=DIM)
    return img

def seg_on_wall(ov, dur, era, name, fade=0.5):
    wp, (ww, wh) = get_wall(era)
    ovp = os.path.join(TMP, name + "_ov.png"); ov.save(ovp)
    mp4 = os.path.join(TMP, name + ".mp4")
    off = random.randint(0, 200)
    sp = (ww - W - 220) / 40.0
    vf = (f"[0:v]crop={W}:{H}:x='min({ww-W},{off}+t*{sp:.2f})':y='{(wh-H)//2}+10*sin(t/3)'[bg];"
          f"[bg][1:v]overlay=0:0,fade=in:st=0:d={fade},fade=out:st={dur-fade}:d={fade}")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-framerate", str(FPS), "-i", wp,
                    "-loop", "1", "-framerate", str(FPS), "-i", ovp, "-t", str(dur),
                    "-filter_complex", vf] + X264 + [mp4], check=True)
    return mp4

def still(img, dur, name, fade=0.6):
    png = os.path.join(TMP, name + ".png"); img.save(png)
    mp4 = os.path.join(TMP, name + ".mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-framerate", str(FPS), "-i", png, "-t", str(dur),
                    "-vf", f"fade=in:st=0:d={fade},fade=out:st={dur-fade}:d={fade}"] + X264 + [mp4], check=True)
    return mp4

def dark_base():
    img = Image.new("RGB", (W, H), (14, 14, 16))
    v = Image.new("L", (W, H), 0); ImageDraw.Draw(v).ellipse((-300, -250, W + 300, H + 250), fill=255)
    return Image.composite(Image.new("RGB", (W, H), (28, 28, 32)), img, v.filter(ImageFilter.GaussianBlur(220)))
BASE = dark_base()

def title_card():
    wp, _ = get_wall("peak")
    img = Image.open(wp).crop((300, 100, 300 + W, 100 + H)).convert("RGBA")
    d = ImageDraw.Draw(img)
    f1 = ImageFont.truetype(SERIF_B, 150); f2 = ImageFont.truetype(SANS, 56)
    for t, f, y, c in (("ИЗ КНЯЗИ В ГРЯЗИ", f1, 380, FG), ("как А4 пал*", f2, 590, RED)):
        d.text(((W - d.textlength(t, font=f)) // 2 + 4, y + 5), t, font=f, fill=(0, 0, 0))
        d.text(((W - d.textlength(t, font=f)) // 2, y), t, font=f, fill=c)
    return img.convert("RGB")

def chapter_card(num, title, era):
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    fn = ImageFont.truetype(BOLD, 34); ft = ImageFont.truetype(SERIF_B, 120)
    t = f"ГЛАВА {num}"
    d.text(((W - d.textlength(t, font=fn)) // 2, 395), t, font=fn, fill=RED)
    d.text(((W - d.textlength(title, font=ft)) // 2 + 4, 469), title, font=ft, fill=(0, 0, 0))
    d.text(((W - d.textlength(title, font=ft)) // 2, 465), title, font=ft, fill=FG)
    d.rectangle((W // 2 - 60, 645, W // 2 + 60, 649), fill=RED)
    return ov

# ---------- Ken Burns showcase of real thumbnails ----------
def showcase(items, name, per=3.2, label=None):
    parts = []
    for k, (vid, views, title) in enumerate(items):
        im = thumb(vid).resize((W, H), Image.LANCZOS)
        bg = im.filter(ImageFilter.GaussianBlur(30)); bg = ImageEnhance.Brightness(bg).enhance(0.35)
        card = im.resize((1440, 810), Image.LANCZOS)
        bg.paste(card, ((W - 1440) // 2, 110))
        d = ImageDraw.Draw(bg)
        f = ImageFont.truetype(BOLD, 40); fs = ImageFont.truetype(SANS, 28)
        cap = f"{fmt_m(views)} просмотров"
        d.text(((W - d.textlength(cap, font=f)) // 2, 950), cap, font=f, fill=FG)
        if label:
            d.rectangle((120, 46, 128, 82), fill=RED); d.text((146, 48), label.upper(), font=ImageFont.truetype(BOLD, 26), fill=FG)
        png = os.path.join(TMP, f"{name}_{k}.png"); bg.save(png)
        mp4 = os.path.join(TMP, f"{name}_{k}.mp4"); fr = int(per * FPS)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-i", png, "-t", str(per), "-vf",
            f"scale=3840:2160,zoompan=z='1+0.06*on/{fr}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={W}x{H}:fps={FPS},"
            f"fade=in:st=0:d=0.35,fade=out:st={per-0.35}:d=0.35"] + X264 + [mp4], check=True)
        parts.append(mp4)
    return parts

def grid_anim(items, name, dur=6.0, label="Одна формула"):
    cols, rws, tw, th, gap = 4, 3, 400, 225, 24
    gx = (W - (cols * tw + (cols - 1) * gap)) // 2; gy = 190
    frames = int(dur * FPS); thumbs = [thumb(v).resize((tw, th)) for v, _, _ in items[:12]]
    fl = ImageFont.truetype(BOLD, 26)
    for fr in range(frames):
        img = BASE.copy(); d = ImageDraw.Draw(img)
        d.rectangle((120, 96, 128, 132), fill=RED); d.text((146, 98), label.upper(), font=fl, fill=DIM)
        for k, t in enumerate(thumbs):
            a = min(1, max(0, (fr - k * 4) / 10))
            if a <= 0: continue
            x = gx + (k % cols) * (tw + gap); y = gy + (k // cols) * (th + gap) + int((1 - a) * 30)
            img.paste(Image.blend(Image.new("RGB", t.size, (14, 14, 16)), t, a), (x, y))
        img.save(os.path.join(TMP, f"{name}_{fr:04d}.png"))
    mp4 = os.path.join(TMP, name + ".mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", os.path.join(TMP, name + "_%04d.png"),
        "-vf", f"fade=out:st={dur-0.5}:d=0.5"] + X264 + [mp4], check=True)
    return mp4

# ---------- real chart ----------
def chart(name, dur=9.0):
    views = [r[1] for r in rows]
    win = 50
    med = [statistics.median(views[max(0, i - win // 2): i + win // 2]) for i in range(len(views))]
    L, R, T, B = 220, 1700, 230, 860; vmax = 70e6
    pts = [(L + i / (len(med) - 1) * (R - L), B - m / vmax * (B - T)) for i, m in enumerate(med)]
    pk = max(range(len(med)), key=lambda i: med[i])
    frames = int(dur * FPS)
    fl = ImageFont.truetype(BOLD, 26); fa = ImageFont.truetype(SANS, 24); fb = ImageFont.truetype(BOLD, 44); fn = ImageFont.truetype(SANS, 22)
    for fr in range(frames):
        p = min(1, fr / (frames * 0.7)); m = max(2, int(p * len(pts)))
        img = BASE.copy(); d = ImageDraw.Draw(img)
        d.rectangle((120, 96, 128, 132), fill=RED)
        d.text((146, 98), "МЕДИАНА ПРОСМОТРОВ ВСЕХ ДЛИННЫХ РОЛИКОВ КАНАЛА", font=fl, fill=DIM)
        for g in (0, 20, 40, 60):
            y = B - g * 1e6 / vmax * (B - T)
            d.line((L, y, R, y), fill=(48, 48, 54), width=1); d.text((L - 110, y - 14), f"{g} млн", font=fa, fill=DIM)
        d.text((L, B + 20), "первые ролики", font=fa, fill=DIM)
        t = "последние"; d.text((R - d.textlength(t, font=fa), B + 20), t, font=fa, fill=DIM)
        upto = min(m, pk + 1)
        d.line(pts[:upto], fill=FG, width=6, joint="curve")
        if m > pk: d.line(pts[pk:m], fill=RED, width=6, joint="curve")
        x, y = pts[m - 1]; d.ellipse((x - 10, y - 10, x + 10, y + 10), fill=FG if m <= pk else RED)
        if m > pk + 5:
            px, py = pts[pk]; s = fmt_m(med[pk]); d.text((px - d.textlength(s, font=fb) / 2, py - 70), s, font=fb, fill=FG)
        if m == len(pts):
            s = fmt_m(med[-1]); d.text((x - d.textlength(s, font=fb) - 20, y - 70), s, font=fb, fill=RED)
        d.text((L, 990), f"Скользящая медиана по {win} роликам, {len(rows)} видео. Shorts не учтены. Новые ролики ещё набирают просмотры.", font=fn, fill=(110, 108, 104))
        img.save(os.path.join(TMP, f"{name}_{fr:04d}.png"))
    mp4 = os.path.join(TMP, name + ".mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", os.path.join(TMP, name + "_%04d.png"),
        "-vf", f"fade=in:st=0:d=0.4,fade=out:st={dur-0.5}:d=0.5"] + X264 + [mp4], check=True)
    return mp4, med

def placeholder(label, name):
    img = BASE.copy(); d = ImageDraw.Draw(img)
    d.rectangle((260, 200, W - 260, H - 200), outline=(70, 70, 74), width=3)
    f = ImageFont.truetype(BOLD, 30); f2 = ImageFont.truetype(SANS, 40)
    d.text(((W - d.textlength("ВСТАВКА", font=f)) // 2, 440), "ВСТАВКА", font=f, fill=RED)
    for i, ln in enumerate(wrap(d, label, f2, 1200)):
        d.text(((W - d.textlength(ln, font=f2)) // 2, 500 + i * 56), ln, font=f2, fill=DIM)
    return still(img, 7, name)

# ---------- timeline ----------
def dur_for(t, accent=False): return round(max(3.2, len(t.split()) / 1.7 + 1.6) + (1.2 if accent else 0), 2)

segs = []; i = [0]
def nm(): i[0] += 1; return f"s{i[0]:03d}"
def T(text, ch, era, **kw):
    segs.append(seg_on_wall(overlay_text(text, ch, **kw), dur_for(text, kw.get("accent")), era, nm()))
def CH(num, title, era): segs.append(seg_on_wall(chapter_card(num, title, era), 3.5, era, nm()))

top_peak = sorted(ERA["peak"], key=lambda r: -r[1])
early_pick = [have[0], have[len(have) // 12], have[len(have) // 7]]
meme_pick = [r for r in have[-30:] if any(k in r[2].lower() for k in ("crocodil", "cappuccino", "tung", "sahur", "tralalero"))][:3] or have[-3:]
latest = rows[-3:]

T("Несколько лет назад этого человека знал почти каждый школьник.", None, "peak")
T("Его лицо было на шоколадках, напитках, игрушках и одежде.", None, "peak")
T("Он был главным героем детства целого поколения.", None, "peak")
T("Сегодня всё иначе.", None, "late", accent=True, size=84)
segs.append(still(title_card(), 5, nm(), fade=0.8))

c = "Восхождение"; CH("I", c, "early")
T("Начиналось всё просто: камера, комната, челленджи.", c, "early")
segs += showcase(early_pick, nm(), label="Первые ролики")
T("Таких каналов были сотни.", c, "early")
T("Но Влад раньше других понял главное: он снимает для детей.", c, "early")
T("Яркая картинка. Громкие эмоции. Простые правила.", c, "early")
T("Вокруг Влада появилась постоянная команда, и канал превратился в бесконечный сериал со своими героями и мемами.", c, "peak")
T("Дети смотрели подолгу, пересматривали, включали автовоспроизведение.", c, "peak")
T("Алгоритм это любил.", c, "peak", accent=True)

c = "Империя"; CH("II", c, "peak")
segs += showcase(top_peak[:3], nm(), label="Пик")
T("Сладости, игрушки, мерч, заведения, игры.", c, "peak")
T("А4 стал брендом, который продавался в обычных магазинах.", c, "peak")
T("Ролики становились масштабнее и дороже.", c, "peak")
T("Но чем больше становилась империя, тем уязвимее она была.", c, "peak", accent=True)

c = "Трещины"; CH("III", c, "late")
T("Первая трещина: аудитория выросла.", c, "late", accent=True)
T("Ребёнок, который в девять лет обожал А4, в четырнадцать стесняется в этом признаться.", c, "late")
T("Новые дети росли на коротких видео. Длинный челлендж конкурировал с бесконечной лентой.", c, "late")
T("Вторая трещина: формат приелся.", c, "late", accent=True)
segs.append(grid_anim(ERA["peak"][::3], nm()))
T("Формула, которая принесла успех, превратилась в ловушку.", c, "late")
T("Третья трещина: конкуренция.", c, "late", accent=True)
T("Нишу заполнили десятки похожих каналов. Быстрее, дешевле, агрессивнее.", c, "late")
T("Четвёртая трещина: репутация.", c, "late", accent=True)
T("Чем известнее бренд, тем больше к нему вопросов.", c, "late")
segs.append(placeholder("2–3 подтверждённых публичных спора: скриншоты СМИ с указанием источника", nm()))

c = "Падение"; CH("IV", c, "late")
T("Падение не было громким.", c, "late")
T("Средние просмотры просто начали снижаться. Ролик за роликом. Месяц за месяцем.", c, "late")
cm, med = chart(nm()); segs.append(cm)
T(f"На пике типичный ролик набирал около {fmt_m(max(med))}. Сейчас около {fmt_m(med[-1])}.", c, "late", accent=True)
T("Чтобы удержаться, канал начал гнаться за чужими мемами.", c, "late")
segs += showcase(meme_pick, nm(), label="Последние ролики")
T("Подписчик и зритель — это разные вещи.", c, "late", accent=True)
T("Стать взрослее значит потерять детей.\nОстаться детским значит стать «тем самым каналом из детства».", c, "late")

c = "Итог"; CH("V", c, "early")
T("Так пал ли А4?", c, "peak", size=84)
T("Канал по-прежнему огромный. Бизнес существует.", c, "peak")
T("Пал не столько сам Влад, сколько эпоха, в которой он был королём.", c, "early")
T("Тебя любят, пока твой зритель не вырастет.", c, "early")
T("А потом ты становишься воспоминанием.", c, "early", accent=True)
segs.append(still(title_card(), 5, nm(), fade=1.0))

lst = os.path.join(TMP, "list.txt")
open(lst, "w").write("".join(f"file '{s}'\n" for s in segs))
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst,
                "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-shortest",
                "-c:v", "copy", "-c:a", "aac", "-movflags", "+faststart", OUT], check=True)
print(OUT, "peak", max(med), "now", med[-1], "memes", [m[2] for m in meme_pick])
