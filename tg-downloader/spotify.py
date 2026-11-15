"""Spotify отдаёт музыку только с DRM, поэтому трек не качаем напрямую.
Берём метаданные (артист, название, длительность, обложка) из embed-страницы
Spotify (ключи API не нужны), ищем такой же трек на YouTube / SoundCloud,
качаем его и прописываем теги из Spotify."""
import json
import re
import urllib.request
from pathlib import Path

import yt_dlp
from mutagen.mp3 import MP3
from mutagen.id3 import APIC, ID3, TALB, TIT2, TPE1, ID3NoHeaderError

SPOTIFY_RE = re.compile(r"https?://open\.spotify\.com/(?:intl-\w+/)?(track|album|playlist)/([A-Za-z0-9]+)")
UA = {"User-Agent": "Mozilla/5.0"}


def _get(url: str) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r:
        return r.read()


def _entity(kind: str, sid: str) -> dict:
    html = _get(f"https://open.spotify.com/embed/{kind}/{sid}").decode()
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        raise RuntimeError("Spotify не отдал данные (поменялась страница?)")
    return json.loads(m.group(1))["props"]["pageProps"]["state"]["data"]["entity"]


def _cover(e: dict) -> str | None:
    imgs = (e.get("visualIdentity") or {}).get("image") or (e.get("coverArt") or {}).get("sources") or []
    return max(imgs, key=lambda i: i.get("maxWidth") or 0)["url"] if imgs else None


def get_tracks(url: str) -> tuple[str, list[dict]]:
    """Возвращает (название подборки, список треков {artist,title,duration,cover,album})."""
    m = SPOTIFY_RE.search(url)
    if not m:
        raise ValueError("не ссылка на Spotify")
    kind, sid = m.groups()
    e = _entity(kind, sid)
    if kind == "track":
        return e["name"], [{
            "artist": ", ".join(a["name"] for a in e.get("artists", [])),
            "title": e["name"],
            "duration": (e.get("duration") or 0) / 1000,
            "cover": _cover(e),
            "album": None,
        }]
    cover = _cover(e)
    tracks = [{
        "artist": (t.get("subtitle") or "").replace("\xa0", " "),
        "title": t["title"],
        "duration": (t.get("duration") or 0) / 1000,
        "cover": cover if kind == "album" else None,
        "album": e.get("name") if kind == "album" else None,
    } for t in e.get("trackList", []) if t.get("isPlayable", True)]
    return e.get("name") or kind, tracks


def _find_sources(track: dict, cookies: str | None):
    """Выдаёт по очереди лучший вариант с YouTube, потом с SoundCloud (ближайший по длительности)."""
    q = f"{track['artist']} - {track['title']}"
    opts = {"quiet": True, "no_warnings": True, "extract_flat": True, "skip_download": True}
    if cookies:
        opts["cookiefile"] = cookies
    for search in (f"ytsearch5:{q} audio", f"scsearch5:{q}"):
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                res = ydl.extract_info(search, download=False)
        except Exception:
            continue
        cands = [c for c in res.get("entries") or [] if c and c.get("url")]
        if not cands:
            continue
        target = track["duration"]
        if target:
            close = [c for c in cands if c.get("duration") and abs(c["duration"] - target) <= 15]
            if close:
                yield min(close, key=lambda c: abs(c["duration"] - target))["url"]
                continue
        yield cands[0]["url"]


def _tag(path: Path, track: dict) -> None:
    try:
        tags = ID3(path)
    except ID3NoHeaderError:
        tags = ID3()
    tags.delall("APIC")
    tags["TIT2"] = TIT2(encoding=3, text=track["title"])
    tags["TPE1"] = TPE1(encoding=3, text=track["artist"])
    if track.get("album"):
        tags["TALB"] = TALB(encoding=3, text=track["album"])
    if track.get("cover"):
        try:
            tags["APIC"] = APIC(encoding=3, mime="image/jpeg", type=3, desc="Cover", data=_get(track["cover"]))
        except Exception:
            pass
    tags.save(path)


def download_track(track: dict, outdir: str, cookies: str | None = None) -> Path:
    safe = re.sub(r'[\\/:*?"<>|]', "", f"{track['artist']} - {track['title']}")[:100]
    opts = {
        "outtmpl": f"{outdir}/{safe}.%(ext)s",
        "format": "bestaudio/best",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}],
    }
    if cookies:
        opts["cookiefile"] = cookies
    path = Path(outdir) / f"{safe}.mp3"
    last_err = None
    for src in _find_sources(track, cookies):
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([src])
            if path.exists():
                got = MP3(path).info.length
                # SoundCloud на платных треках отдаёт 30-секундное превью — такое не берём
                if track["duration"] and got < track["duration"] * 0.8:
                    path.unlink()
                    last_err = RuntimeError(f"нашлось только превью ({got:.0f} c)")
                    continue
                break
        except Exception as e:
            last_err = e
    if not path.exists():
        q = f"{track['artist']} - {track['title']}"
        raise RuntimeError(f"не смог скачать «{q}»" + (f": {last_err}" if last_err else " — не нашёл"))
    _tag(path, track)
    return path
