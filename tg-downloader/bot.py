"""Личный Telegram-бот: качает видео/аудио с YouTube и треки с SoundCloud."""
import asyncio
import logging
import os
import re
import secrets
import shutil
import tempfile
from pathlib import Path

import yt_dlp

import spotify
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

logging.basicConfig(level=logging.INFO)

TOKEN = os.environ["BOT_TOKEN"]
# Только эти Telegram ID могут пользоваться ботом (через запятую).
ALLOWED = {int(x) for x in os.environ.get("ALLOWED_USERS", "").split(",") if x.strip()}
# Сколько треков максимум качать из альбома/плейлиста Spotify.
MAX_PLAYLIST = int(os.environ.get("MAX_PLAYLIST", "50"))
COOKIES = os.environ.get("COOKIES_FILE") or None
# Обычный Bot API принимает файлы до 50 МБ.
MAX_BYTES = 50 * 1024 * 1024

YT_RE = re.compile(r"https?://(www\.|m\.|music\.)?(youtube\.com|youtu\.be)/\S+")
SC_RE = re.compile(r"https?://(www\.|m\.|on\.)?soundcloud\.(com|app\.goo\.gl)/\S+")

bot = Bot(TOKEN)
dp = Dispatcher()
pending: dict[str, str] = {}  # короткий ключ -> ссылка (callback_data ограничен 64 байтами)
semaphore = asyncio.Semaphore(2)  # не больше 2 загрузок одновременно


def allowed(user_id: int) -> bool:
    return not ALLOWED or user_id in ALLOWED


def ydl_opts(kind: str, outdir: str) -> dict:
    base = {
        "outtmpl": f"{outdir}/%(title).80s.%(ext)s",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
    }
    # Если YouTube пишет "Sign in to confirm you're not a bot" — экспортируй cookies.txt из браузера
    if COOKIES:
        base["cookiefile"] = COOKIES
    if kind == "mp3":
        base |= {
            "format": "bestaudio/best",
            "writethumbnail": True,
            "postprocessors": [
                {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"},
                {"key": "FFmpegMetadata"},
                {"key": "EmbedThumbnail"},
            ],
        }
    else:  # высота видео: "720", "480", "360"
        h = int(kind)
        base |= {
            "format": f"bv*[height<={h}][ext=mp4]+ba[ext=m4a]/bv*[height<={h}]+ba/b[height<={h}]/b",
            "merge_output_format": "mp4",
        }
    return base


def download(url: str, kind: str, outdir: str) -> tuple[Path, dict]:
    with yt_dlp.YoutubeDL(ydl_opts(kind, outdir)) as ydl:
        info = ydl.extract_info(url, download=True)
    files = [p for p in Path(outdir).iterdir() if p.suffix.lower() in {".mp3", ".mp4", ".mkv", ".webm"}]
    if not files:
        raise RuntimeError("файл не найден после загрузки")
    return max(files, key=lambda p: p.stat().st_size), info


async def fetch_and_send(chat_id: int, url: str, kind: str, status: Message) -> None:
    outdir = tempfile.mkdtemp(prefix="dl_")
    try:
        async with semaphore:
            await status.edit_text("⏳ Качаю...")
            path, info = await asyncio.to_thread(download, url, kind, outdir)

        if path.stat().st_size > MAX_BYTES:
            mb = path.stat().st_size / 1024 / 1024
            await status.edit_text(f"❌ Файл {mb:.0f} МБ, а Telegram пускает ботам только 50 МБ. Попробуй качество пониже.")
            return

        await status.edit_text("📤 Отправляю...")
        file = FSInputFile(path)
        title = info.get("title") or path.stem
        if kind == "mp3":
            await bot.send_audio(
                chat_id, file,
                title=title,
                performer=info.get("uploader") or info.get("artist"),
                duration=int(info.get("duration") or 0) or None,
            )
        else:
            await bot.send_video(
                chat_id, file,
                caption=title[:1000],
                duration=int(info.get("duration") or 0) or None,
                width=info.get("width"),
                height=info.get("height"),
                supports_streaming=True,
            )
        await status.delete()
    except Exception as e:
        logging.exception("download failed")
        await status.edit_text(f"❌ Не вышло: {str(e)[:300]}")
    finally:
        shutil.rmtree(outdir, ignore_errors=True)


async def spotify_flow(chat_id: int, url: str, status: Message) -> None:
    try:
        name, tracks = await asyncio.to_thread(spotify.get_tracks, url)
    except Exception as e:
        await status.edit_text(f"❌ Spotify: {str(e)[:300]}")
        return
    if not tracks:
        await status.edit_text("❌ Треков не нашлось.")
        return
    tracks = tracks[:MAX_PLAYLIST]
    failed = []
    for i, t in enumerate(tracks, 1):
        label = f"{t['artist']} — {t['title']}"
        prefix = f"[{i}/{len(tracks)}] " if len(tracks) > 1 else ""
        await status.edit_text(f"⏳ {prefix}{label}")
        outdir = tempfile.mkdtemp(prefix="sp_")
        try:
            async with semaphore:
                path = await asyncio.to_thread(spotify.download_track, t, outdir, COOKIES)
            if path.stat().st_size > MAX_BYTES:
                raise RuntimeError("больше 50 МБ")
            await bot.send_audio(
                chat_id, FSInputFile(path),
                title=t["title"], performer=t["artist"],
                duration=int(t["duration"]) or None,
            )
        except Exception as e:
            logging.exception("spotify track failed")
            failed.append(f"• {label}: {str(e)[:100]}")
        finally:
            shutil.rmtree(outdir, ignore_errors=True)
    if failed:
        await status.edit_text("Готово, но не скачались:\n" + "\n".join(failed)[:3500])
    elif len(tracks) > 1:
        await status.edit_text(f"✅ {name}: {len(tracks)} треков")
    else:
        await status.delete()


@dp.message(CommandStart())
async def start(msg: Message):
    if not allowed(msg.from_user.id):
        return
    await msg.answer("Кидай ссылку на YouTube, SoundCloud или Spotify 🎬🎵")


@dp.message(F.text)
async def on_link(msg: Message):
    if not allowed(msg.from_user.id):
        return  # чужим молча ничего не отвечаем
    text = msg.text.strip()

    if m := spotify.SPOTIFY_RE.search(text):
        status = await msg.answer("🔎 Spotify...")
        await spotify_flow(msg.chat.id, m.group(0), status)
        return

    if m := SC_RE.search(text):
        status = await msg.answer("🔎 SoundCloud...")
        await fetch_and_send(msg.chat.id, m.group(0), "mp3", status)
        return

    if m := YT_RE.search(text):
        key = secrets.token_urlsafe(6)
        pending[key] = m.group(0)
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🎬 720p", callback_data=f"720:{key}"),
                InlineKeyboardButton(text="🎬 480p", callback_data=f"480:{key}"),
                InlineKeyboardButton(text="🎬 360p", callback_data=f"360:{key}"),
            ],
            [InlineKeyboardButton(text="🎵 MP3", callback_data=f"mp3:{key}")],
        ])
        await msg.answer("Что качаем?", reply_markup=kb)
        return

    await msg.answer("Это не похоже на ссылку YouTube, SoundCloud или Spotify 🤔")


@dp.callback_query(F.data.regexp(r"^(720|480|360|mp3):"))
async def on_choice(cb: CallbackQuery):
    if not allowed(cb.from_user.id):
        await cb.answer()
        return
    kind, key = cb.data.split(":", 1)
    url = pending.pop(key, None)
    await cb.answer()
    if not url:
        await cb.message.edit_text("Ссылка устарела, кинь её ещё раз.")
        return
    await fetch_and_send(cb.message.chat.id, url, kind, cb.message)


async def main():
    if not ALLOWED:
        logging.warning("ALLOWED_USERS не задан — ботом может пользоваться кто угодно!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
