# Личный TG-бот: YouTube + SoundCloud + Spotify

- **YouTube:** кидаешь ссылку и выбираешь 720p / 480p / 360p или MP3.
- **SoundCloud:** кидаешь ссылку и сразу получаешь MP3 с обложкой.
- **Spotify:** трек, альбом или плейлист (до 50 треков, настраивается через `MAX_PLAYLIST`). Напрямую из Spotify скачать нельзя, музыка там под DRM. Поэтому бот берёт из Spotify название, артиста и обложку, находит этот трек на YouTube (если не вышло, то на SoundCloud) и прописывает в mp3 теги из Spotify. Ключи API не нужны.
- Отвечает только тем, чьи ID указаны в `ALLOWED_USERS`. Всех остальных бот молча игнорирует.

## Запуск

1. В [@BotFather](https://t.me/BotFather) выполни `/newbot` и задай любой username (должен кончаться на `bot`). Скопируй токен.
2. Узнай свой ID у [@userinfobot](https://t.me/userinfobot).
3. Запусти бота:

```bash
sudo apt install ffmpeg          # на Windows: winget install ffmpeg
pip install -r requirements.txt
export BOT_TOKEN=...  ALLOWED_USERS=123456789
python bot.py
```

Через Docker:
```bash
docker build -t tgdl . && docker run -d --restart=always --env-file .env tgdl
```

## Если YouTube не качает

- **Обнови yt-dlp:** `pip install -U yt-dlp`. Это помогает в 90% случаев.
- **403 или «Sign in to confirm you're not a bot»:** YouTube банит IP серверов. Лучше запускать бота дома на ПК. Если хочешь на VPS, экспортируй `cookies.txt` из браузера расширением «Get cookies.txt LOCALLY» и укажи путь в `COOKIES_FILE`. Бери cookies от запасного аккаунта, не от основного.
- **Файл больше 50 МБ:** это лимит Bot API. Выбирай 480p или 360p.
