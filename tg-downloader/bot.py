"""Личный универсальный Telegram-бот-качалка.

* Любой сайт, который умеет yt-dlp (YouTube, Rutube, VK Видео, TikTok, SoundCloud,
  Twitch, X/Twitter, Reddit, Instagram, Vimeo, Dailymotion, OK.ru, Bilibili… — 1800+ сайтов).
* Spotify, Apple Music, Deezer, Яндекс Музыка — через поиск трека (см. music.py).
"""
import asyncio
import json
import logging
import os
import re
import secrets
import shutil
import tempfile
from pathlib import Path

import yt_dlp
from aiogram import Bot, Dispatcher, F
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from mutagen.mp3 import MP3

import music

logging.basicConfig(level=logging.INFO)

TOKEN = os.environ["BOT_TOKEN"]
# Только эти Telegram ID могут пользоваться ботом (через запятую).
ALLOWED = {int(x) for x in os.environ.get("ALLOWED_USERS", "").split(",") if x.strip()}
# Один cookies.txt может содержать cookies сразу для многих сайтов (YouTube, VK, Instagram…).
COOKIES = os.environ.get("COOKIES_FILE") or None
MAX_PLAYLIST = int(os.environ.get("MAX_PLAYLIST", "50"))
# Для Spotify и т.п. искать трек и на SoundCloud, если на YouTube не вышло.
SC_FALLBACK = os.environ.get("MUSIC_SOUNDCLOUD_FALLBACK", "1") == "1"
# Свой Local Bot API Server снимает лимит 50 МБ → до 2 ГБ.
BOT_API_URL = os.environ.get("BOT_API_URL")
MAX_BYTES = (2000 if BOT_API_URL else 50) * 1024 * 1024
CACHE_FILE = Path(os.environ.get("CACHE_FILE", "cache.json"))

HEIGHTS = [1080, 720, 480, 360, 240]
URL_RE = re.compile(r"https?://\S+")

session = AiohttpSession(timeout=900)  # большие файлы грузятся долго
if BOT_API_URL:
    session.api = TelegramAPIServer.from_base(BOT_API_URL, is_local=True)
bot = Bot(TOKEN, session=session)
dp = Dispatcher()
pending: dict[str, dict] = {}  # короткий ключ -> данные ссылки (callback_data ≤ 64 байт)
semaphore = asyncio.Semaphore(2)  # не больше 2 загрузок одновременно


# ---------- кэш file_id: повторная ссылка отправляется мгновенно ----------
try:
    cache: dict[str, list] = json.loads(CACHE_FILE.read_text())
except Exception:
    cache = {}


def cache_put(key: str, kind: str, file_id: str) -> None:
    cache[key] = [kind, file_id]
    try:
        CACHE_FILE.write_text(json.dumps(cache))
    except Exception:
        pass


async def cache_send(chat_id: int, key: str) -> bool:
    hit = cache.get(key)
    if not hit:
        return False
    try:
        if hit[0] == "audio":
            await bot.send_audio(chat_id, hit[1])
        else:
            await bot.send_video(chat_id, hit[1])
        return True
    except Exception:
        cache.pop(key, None)
        return False


# ---------- yt-dlp ----------
def base_opts(outdir: str | None = None) -> dict:
    o = {"quiet": True, "no_warnings": True, "noprogress": True, "noplaylist": True,
         "retries": 10, "fragment_retries": 10, "socket_timeout": 30}
    if outdir:
        o["outtmpl"] = f"{outdir}/%(title).80s [%(id)s].%(ext)s"
    if COOKIES:
        o["cookiefile"] = COOKIES
    return o


def probe(url: str) -> dict:
    o = base_opts() | {"skip_download": True, "extract_flat": "in_playlist", "noplaylist": False}
    with yt_dlp.YoutubeDL(o) as ydl:
        return ydl.sanitize_info(ydl.extract_info(url, download=False))


def fmt_for(kind: str) -> dict:
    if kind == "mp3":
        return {
            "format": "bestaudio/best",
            "writethumbnail": True,
            "postprocessors": [
                {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"},
                {"key": "FFmpegMetadata"},
                {"key": "EmbedThumbnail"},
            ],
        }
    if kind == "best":
        return {"format": "bv*+ba/b", "merge_output_format": "mp4"}
    h = int(kind)
    return {
        "format": f"bv*[height<={h}][ext=mp4]+ba[ext=m4a]/bv*[height<={h}]+ba/b[height<={h}]/wv*+ba/w",
        "merge_output_format": "mp4",
    }


def download(url: str, kind: str, outdir: str) -> tuple[Path, dict]:
    with yt_dlp.YoutubeDL(base_opts(outdir) | fmt_for(kind)) as ydl:
        info = ydl.extract_info(url, download=True)
    files = [p for p in Path(outdir).iterdir()
             if p.suffix.lower() in {".mp3", ".mp4", ".mkv", ".webm", ".mov", ".m4a"}]
    if not files:
        raise RuntimeError("файл не найден после загрузки")
    return max(files, key=lambda p: p.stat().st_size), info


def human_error(e: Exception) -> str:
    s = str(e)
    if "Unsupported URL" in s:
        return "этот сайт не поддерживается 🤷"
    if any(w in s for w in ("Sign in", "cookies", "login", "logged-in", "authentication")):
        return "сайт требует вход. Положи cookies.txt и укажи COOKIES_FILE (см. README)"
    if "403" in s:
        return "сайт не пускает (403). Обнови yt-dlp или добавь cookies"
    if "Private" in s or "private" in s:
        return "видео приватное"
    return re.sub(r"\x1b\[[0-9;]*m", "", s).replace("ERROR: ", "")[:300]


def lower_kinds(kind: str) -> list[str]:
    """Цепочка качества для автопонижения, если файл не влез в лимит."""
    if kind == "mp3":
        return ["mp3"]
    start = 10_000 if kind == "best" else int(kind)
    return [kind] + [str(h) for h in HEIGHTS if h < start]


async def fetch_and_send(chat_id: int, url: str, kind: str, status: Message, label: str = "") -> bool:
    key = f"{kind}|{url}"
    if await cache_send(chat_id, key):
        return True
    for k in lower_kinds(kind):
        outdir = tempfile.mkdtemp(prefix="dl_")
        try:
            async with semaphore:
                q = "MP3" if k == "mp3" else ("макс." if k == "best" else f"{k}p")
                await status.edit_text(f"⏳ {label}Качаю ({q})...")
                path, info = await asyncio.to_thread(download, url, k, outdir)

            size = path.stat().st_size
            if size > MAX_BYTES:
                if k != lower_kinds(kind)[-1]:
                    continue  # пробуем качество пониже
                await status.edit_text(
                    f"❌ {label}Файл {size / 2**20:.0f} МБ — больше лимита {MAX_BYTES // 2**20} МБ "
                    "даже в минимальном качестве. Подними Local Bot API (см. README).")
                return False

            await status.edit_text(f"📤 {label}Отправляю...")
            title = info.get("title") or path.stem
            duration = int(info.get("duration") or 0) or None
            if k == "mp3":
                note = None
                if duration and MP3(path).info.length < duration * 0.8:
                    note = "⚠️ Сайт отдал только превью (платный трек)"
                msg = await bot.send_audio(
                    chat_id, FSInputFile(path), caption=note, title=title,
                    performer=info.get("artist") or info.get("uploader"), duration=duration)
                cache_put(key, "audio", msg.audio.file_id)
            else:
                msg = await bot.send_video(
                    chat_id, FSInputFile(path), caption=title[:1000], duration=duration,
                    width=info.get("width"), height=info.get("height"), supports_streaming=True)
                if msg.video:
                    cache_put(key, "video", msg.video.file_id)
            return True
        except Exception as e:
            logging.exception("download failed")
            await status.edit_text(f"❌ {label}{human_error(e)}")
            return False
        finally:
            shutil.rmtree(outdir, ignore_errors=True)
    return False


# ---------- музыкальные сервисы (Spotify, Apple Music, Deezer, Яндекс) ----------
async def music_flow(chat_id: int, url: str, status: Message) -> None:
    try:
        name, tracks = await asyncio.to_thread(music.get_tracks, url)
    except Exception as e:
        await status.edit_text(f"❌ {human_error(e)}")
        return
    if not tracks:
        await status.edit_text("❌ Треков не нашлось.")
        return
    tracks = tracks[:MAX_PLAYLIST]
    failed = []
    for i, t in enumerate(tracks, 1):
        label = f"{t['artist']} — {t['title']}"
        key = f"music|{label.lower()}"
        if await cache_send(chat_id, key):
            continue
        prefix = f"[{i}/{len(tracks)}] " if len(tracks) > 1 else ""
        await status.edit_text(f"⏳ {prefix}{label}")
        outdir = tempfile.mkdtemp(prefix="mu_")
        try:
            async with semaphore:
                path = await asyncio.to_thread(music.download_track, t, outdir, COOKIES, SC_FALLBACK)
            if path.stat().st_size > MAX_BYTES:
                raise RuntimeError("файл слишком большой")
            msg = await bot.send_audio(chat_id, FSInputFile(path), title=t["title"],
                                       performer=t["artist"], duration=int(t["duration"]) or None)
            cache_put(key, "audio", msg.audio.file_id)
        except Exception as e:
            logging.exception("music track failed")
            failed.append(f"• {label}: {human_error(e)[:100]}")
        finally:
            shutil.rmtree(outdir, ignore_errors=True)
    if failed:
        await status.edit_text("Готово, но не скачались:\n" + "\n".join(failed)[:3500])
    elif len(tracks) > 1:
        await status.edit_text(f"✅ {name}: {len(tracks)} треков")
    else:
        await status.delete()


# ---------- хэндлеры ----------
def allowed(user_id: int) -> bool:
    return not ALLOWED or user_id in ALLOWED


HELP = (
    "Кидай ссылку — скачаю 🎬🎵\n\n"
    "Видео: YouTube, Rutube, VK Видео, TikTok, Twitch, X, Reddit, Instagram, Vimeo, OK.ru, "
    "Dailymotion, Bilibili и ещё 1800+ сайтов.\n"
    "Музыка: SoundCloud, YouTube Music, Bandcamp, Spotify, Apple Music, Deezer, Яндекс Музыка.\n"
    "Плейлисты и альбомы тоже можно."
)


@dp.message(CommandStart())
@dp.message(Command("help"))
async def start(msg: Message):
    if allowed(msg.from_user.id):
        await msg.answer(HELP)


@dp.message(F.text)
async def on_link(msg: Message):
    if not allowed(msg.from_user.id):
        return  # чужим молча ничего не отвечаем
    m = URL_RE.search(msg.text)
    if not m:
        await msg.answer("Кинь ссылку 🙂 /help — что умею")
        return
    url = m.group(0)

    if music.ANY_RE.search(url):
        status = await msg.answer("🔎 Ищу трек...")
        await music_flow(msg.chat.id, url, status)
        return

    status = await msg.answer("🔎 Смотрю, что по ссылке...")
    try:
        info = await asyncio.to_thread(probe, url)
    except Exception as e:
        await status.edit_text(f"❌ {human_error(e)}")
        return

    key = secrets.token_urlsafe(6)
    title = (info.get("title") or "")[:200]

    # Плейлист / альбом / канал
    if info.get("_type") == "playlist" or info.get("entries"):
        entries = [e.get("url") or e.get("webpage_url") for e in info.get("entries") or [] if e]
        entries = [u for u in entries if u]
        if not entries:
            await status.edit_text("❌ Плейлист пустой.")
            return
        pending[key] = {"playlist": entries[:MAX_PLAYLIST]}
        n = len(pending[key]["playlist"])
        more = f" (из {len(entries)})" if len(entries) > n else ""
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text=f"🎵 Всё в MP3 ({n})", callback_data=f"mp3:{key}"),
            InlineKeyboardButton(text=f"🎬 Всё видео 480p ({n})", callback_data=f"480:{key}"),
        ]])
        await status.edit_text(f"📃 {title}\n{n} шт.{more}. Как качаем?", reply_markup=kb)
        return

    formats = info.get("formats") or []
    has_video = any(f.get("vcodec") not in (None, "none") or f.get("height") for f in formats) \
        or (not formats and info.get("vcodec") not in (None, "none"))
    if not has_video:  # только звук (SoundCloud, Bandcamp, подкасты…) — сразу mp3
        if await fetch_and_send(msg.chat.id, url, "mp3", status):
            await status.delete()
        return

    pending[key] = {"url": url}
    max_h = max((f.get("height") or 0 for f in formats), default=0)
    heights = [h for h in HEIGHTS[:4] if h <= max_h] or []
    row = [InlineKeyboardButton(text=f"🎬 {h}p", callback_data=f"{h}:{key}") for h in heights[:4]]
    if not row:
        row = [InlineKeyboardButton(text="🎬 Видео", callback_data=f"best:{key}")]
    kb = InlineKeyboardMarkup(inline_keyboard=[row, [InlineKeyboardButton(text="🎵 MP3", callback_data=f"mp3:{key}")]])
    await status.edit_text(f"{title}\nЧто качаем?" if title else "Что качаем?", reply_markup=kb)


@dp.callback_query(F.data.regexp(r"^(\d+|best|mp3):"))
async def on_choice(cb: CallbackQuery):
    await cb.answer()
    if not allowed(cb.from_user.id):
        return
    kind, key = cb.data.split(":", 1)
    data = pending.pop(key, None)
    if not data:
        await cb.message.edit_text("Ссылка устарела, кинь её ещё раз.")
        return
    chat_id = cb.message.chat.id

    if "playlist" in data:
        items = data["playlist"]
        ok = 0
        for i, u in enumerate(items, 1):
            ok += await fetch_and_send(chat_id, u, kind, cb.message, label=f"[{i}/{len(items)}] ")
        await cb.message.edit_text(f"✅ Готово: {ok}/{len(items)}")
        return

    if await fetch_and_send(chat_id, data["url"], kind, cb.message):
        await cb.message.delete()


async def main():
    if not ALLOWED:
        logging.warning("ALLOWED_USERS не задан — ботом может пользоваться кто угодно!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
