# Личный универсальный TG-бот-качалка

Кидаешь боту ссылку, он присылает видео или mp3.

| Что | Как работает |
|---|---|
| **YouTube, Rutube, VK Видео, TikTok, Twitch, X/Twitter, OK.ru, Dailymotion, Bilibili** и ещё 1800+ сайтов | Через [yt-dlp](https://github.com/yt-dlp/yt-dlp). Бот показывает кнопки с качеством, которое реально есть у видео, и вариант MP3 |
| **SoundCloud, Bandcamp, подкасты** (всё, где только звук) | Сразу присылает mp3 с обложкой |
| **Плейлисты, альбомы, каналы** | Кнопки «Всё в MP3» и «Всё видео 480p», до `MAX_PLAYLIST` штук |
| **Spotify, Apple Music, Deezer, Яндекс Музыка** | Там DRM, напрямую не скачать. Бот берёт название, артиста и обложку, находит этот трек на YouTube (если не вышло, то на SoundCloud) и прописывает теги из оригинала |
| **Instagram, Reddit, Vimeo, приватные видео VK** | Нужен вход на сайт: экспортируй cookies (см. ниже) |

Ещё бот умеет:
- **Белый список:** отвечает только ID из `ALLOWED_USERS`, всех остальных молча игнорирует.
- **Автопонижение качества:** если видео не влезло в лимит Telegram, бот сам перекачивает его в качестве пониже.
- **Кэш:** повторную ссылку присылает мгновенно, без скачивания. Кэш хранится в `cache.json`.
- **Предупреждение о превью:** если SoundCloud отдал 30-секундное превью платного трека, бот об этом напишет.

## Запуск

1. В [@BotFather](https://t.me/BotFather) выполни `/newbot`, задай любой username (должен кончаться на `bot`) и скопируй токен.
2. Узнай свой ID у [@userinfobot](https://t.me/userinfobot).
3. Скопируй `.env.example` в `.env` и заполни.
4. Запусти:

```bash
sudo apt install ffmpeg          # Windows: winget install ffmpeg
pip install -r requirements.txt
set -a; . ./.env; set +a         # Windows: задай переменные через set
python bot.py
```

Через Docker:
```bash
docker build -t tgdl . && docker run -d --restart=always --env-file .env -v $PWD/data:/data -e CACHE_FILE=/data/cache.json tgdl
```

## Cookies (для сайтов, которые просят вход)

1. Поставь в браузер расширение **«Get cookies.txt LOCALLY»**.
2. Зайди на нужные сайты (YouTube, Instagram, VK…) и экспортируй cookies в один `cookies.txt`.
3. Укажи путь к файлу в `COOKIES_FILE=cookies.txt`.

⚠️ Используй **запасные аккаунты**: при активном скачивании сайт может забанить аккаунт. И никому не давай этот файл, в нём твои сессии.

## Файлы больше 50 МБ

Обычный Bot API принимает от ботов файлы только до 50 МБ. Чтобы поднять лимит до 2 ГБ, запусти свой [telegram-bot-api](https://github.com/tdlib/telegram-bot-api). Для этого нужны `api_id` и `api_hash` с my.telegram.org:

```bash
docker run -d -p 8081:8081 -e TELEGRAM_API_ID=... -e TELEGRAM_API_HASH=... aiogram/telegram-bot-api
```

Потом укажи `BOT_API_URL=http://localhost:8081`. Перед первым переключением выполни `https://api.telegram.org/bot<TOKEN>/logOut`.

## Если что-то не качает

- **Сначала обнови yt-dlp:** `pip install -U yt-dlp`. Сайты часто меняются, и это лечит большинство проблем. Docker-образ обновляет yt-dlp сам при каждом старте.
- **YouTube пишет «Sign in to confirm you're not a bot»:** он банит IP серверов. Запускай бота дома или добавь cookies.
- **Не работает Яндекс Музыка:** её API закрыт для зарубежных IP, поэтому бот должен работать из РФ.
- **Не поддерживается:** фото и карусели из Instagram/TikTok (yt-dlp качает только видео), Apple Music и Яндекс Музыка без поиска трека, видео с DRM (Netflix, Кинопоиск и т.п.).
