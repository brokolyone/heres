"""Музыкальные сервисы с DRM (Spotify, Apple Music, Deezer, Яндекс Музыка).
Напрямую оттуда аудио не скачать, поэтому берём метаданные трека
(артист, название, длительность, обложка), ищем такой же трек на
YouTube / SoundCloud, качаем и прописываем теги из оригинального сервиса."""
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

import yt_dlp
from mutagen.id3 import APIC, ID3, TALB, TIT2, TPE1, ID3NoHeaderError
from mutagen.mp3 import MP3

UA = {"User-Agent": "Mozilla/5.0"}

SPOTIFY_RE = re.compile(r"https?://open\.spotify\.com/(?:intl-\w+/)?(track|album|playlist)/([A-Za-z0-9]+)")
APPLE_RE = re.compile(r"https?://(?:music|itunes)\.apple\.com/(\w\w)/(album|song)/[^/]*/?(\d+)(?:\?[^ ]*?\bi=(\d+))?")
DEEZER_RE = re.compile(r"https?://(?:www\.)?deezer\.com/(?:\w\w/)?(track|album|playlist)/(\d+)")
DEEZER_SHORT_RE = re.compile(r"https?://(?:deezer\.page\.link|link\.deezer\.com)/\S+")
YANDEX_RE = re.compile(r"https?://music\.yandex\.\w+/album/(\d+)(?:/track/(\d+))?")
ANY_RE = re.compile("|".join(r.pattern for r in (SPOTIFY_RE, APPLE_RE, DEEZER_RE, DEEZER_SHORT_RE, YANDEX_RE)))


def _get(url: str) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r:
        return r.read()


def _json(url: str):
    return json.loads(_get(url))


def _track(artist, title, duration, cover=None, album=None) -> dict:
    return {"artist": artist, "title": title, "duration": float(duration or 0), "cover": cover, "album": album}


# ---------- Spotify (embed-страница, без ключей API) ----------
def _spotify(kind: str, sid: str):
    html = _get(f"https://open.spotify.com/embed/{kind}/{sid}").decode()
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        raise RuntimeError("Spotify не отдал данные (поменялась страница?)")
    e = json.loads(m.group(1))["props"]["pageProps"]["state"]["data"]["entity"]
    imgs = (e.get("visualIdentity") or {}).get("image") or (e.get("coverArt") or {}).get("sources") or []
    cover = max(imgs, key=lambda i: i.get("maxWidth") or 0)["url"] if imgs else None
    if kind == "track":
        artist = ", ".join(a["name"] for a in e.get("artists", []))
        return e["name"], [_track(artist, e["name"], (e.get("duration") or 0) / 1000, cover)]
    album = e.get("name") if kind == "album" else None
    return e.get("name") or kind, [
        _track((t.get("subtitle") or "").replace("\xa0", " "), t["title"], (t.get("duration") or 0) / 1000,
               cover if album else None, album)
        for t in e.get("trackList", []) if t.get("isPlayable", True)
    ]


# ---------- Apple Music (iTunes Lookup API) ----------
def _apple(country: str, kind: str, cid: str, tid: str | None):
    if tid or kind == "song":
        r = _json(f"https://itunes.apple.com/lookup?id={tid or cid}&country={country}")["results"]
        songs = [x for x in r if x.get("wrapperType") == "track"]
        name = songs[0]["trackName"] if songs else "Apple Music"
    else:
        r = _json(f"https://itunes.apple.com/lookup?id={cid}&entity=song&country={country}")["results"]
        songs = [x for x in r if x.get("wrapperType") == "track"]
        name = next((x["collectionName"] for x in r if x.get("wrapperType") == "collection"), "Apple Music")
    return name, [
        _track(s["artistName"], s["trackName"], (s.get("trackTimeMillis") or 0) / 1000,
               (s.get("artworkUrl100") or "").replace("100x100", "600x600") or None,
               s.get("collectionName") if kind == "album" and not tid else None)
        for s in songs
    ]


# ---------- Deezer (открытый API) ----------
def _deezer(kind: str, did: str):
    d = _json(f"https://api.deezer.com/{kind}/{did}")
    if "error" in d:
        raise RuntimeError(f"Deezer: {d['error'].get('message')}")
    if kind == "track":
        return d["title"], [_track(d["artist"]["name"], d["title"], d["duration"],
                                   d.get("album", {}).get("cover_xl"), d.get("album", {}).get("title"))]
    cover = d.get("cover_xl") if kind == "album" else None
    return d.get("title"), [
        _track(t["artist"]["name"], t["title"], t["duration"],
               cover or t.get("album", {}).get("cover_xl"),
               d.get("title") if kind == "album" else t.get("album", {}).get("title"))
        for t in d["tracks"]["data"]
    ]


# ---------- Яндекс Музыка (публичный API; работает из РФ, из-за рубежа может быть закрыт) ----------
def _yandex(album_id: str, track_id: str | None):
    def cover(uri):
        return f"https://{uri.replace('%%', '600x600')}" if uri else None

    if track_id:
        t = _json(f"https://api.music.yandex.net/tracks/{track_id}")["result"][0]
        alb = (t.get("albums") or [{}])[0]
        return t["title"], [_track(", ".join(a["name"] for a in t.get("artists", [])), t["title"],
                                   (t.get("durationMs") or 0) / 1000, cover(t.get("coverUri")), alb.get("title"))]
    a = _json(f"https://api.music.yandex.net/albums/{album_id}/with-tracks")["result"]
    tracks = [t for vol in a.get("volumes", []) for t in vol]
    return a["title"], [
        _track(", ".join(x["name"] for x in t.get("artists", [])), t["title"], (t.get("durationMs") or 0) / 1000,
               cover(a.get("coverUri")), a["title"])
        for t in tracks
    ]


def get_tracks(url: str) -> tuple[str, list[dict]]:
    if DEEZER_SHORT_RE.match(url):  # короткая ссылка → раскрываем редирект
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r:
            url = r.geturl()
    if m := SPOTIFY_RE.search(url):
        return _spotify(*m.groups())
    if m := APPLE_RE.search(url):
        return _apple(*m.groups())
    if m := DEEZER_RE.search(url):
        return _deezer(*m.groups())
    if m := YANDEX_RE.search(url):
        return _yandex(*m.groups())
    raise ValueError("не знаю этот музыкальный сервис")


# ---------- поиск и скачивание ----------
def _find_sources(track: dict, cookies: str | None, use_soundcloud: bool):
    """Выдаёт по очереди лучший вариант с YouTube, потом с SoundCloud (ближайший по длительности)."""
    q = f"{track['artist']} - {track['title']}"
    opts = {"quiet": True, "no_warnings": True, "extract_flat": True, "skip_download": True}
    if cookies:
        opts["cookiefile"] = cookies
    searches = [f"ytsearch5:{q} audio"] + ([f"scsearch5:{q}"] if use_soundcloud else [])
    for search in searches:
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                res = ydl.extract_info(search, download=False)
        except Exception:
            continue
        cands = [c for c in res.get("entries") or [] if c and c.get("url")]
        target = track["duration"]
        if target:
            cands = [c for c in cands if not c.get("duration") or abs(c["duration"] - target) <= 15]
            cands.sort(key=lambda c: abs((c.get("duration") or target + 15) - target))
        if cands:
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


def download_track(track: dict, outdir: str, cookies: str | None = None, use_soundcloud: bool = True) -> Path:
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
    for src in _find_sources(track, cookies, use_soundcloud):
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
