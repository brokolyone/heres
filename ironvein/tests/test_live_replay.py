"""Живая проверка в настоящем Telegram (запускается только с токеном).

Прогоняет экраны бота (тур по разделам, компания с «враждебными» именами, контракт, счёт Stars) с записью
исходящих запросов, затем отправляет их в настоящий Telegram в чат LIVE_CHAT_ID. Telegram сам проверяет
HTML, подписи, клавиатуры, картинки и счёт; любая ошибка 400 валит тест.

    LIVE_BOT_TOKEN=<токен> LIVE_CHAT_ID=<ваш Telegram ID> pytest -q -s tests/test_live_replay.py

Перед запуском напишите боту /start (иначе он не сможет писать вам первым). Оплачивать счёт не нужно.
"""

import asyncio
import os

import pytest
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter
from aiogram.methods import (
    EditMessageMedia,
    EditMessageText,
    SendInvoice,
    SendMessage,
    SendPhoto,
)

from ironvein.handlers.ui import Do
from tests.test_bot_scenarios import Player, env  # noqa: F401  (фикстура)

TOKEN = os.environ.get("LIVE_BOT_TOKEN")
CHAT = os.environ.get("LIVE_CHAT_ID")
live_only = pytest.mark.skipif(not (TOKEN and CHAT), reason="нужны LIVE_BOT_TOKEN и LIVE_CHAT_ID")
LIMIT = int(os.environ.get("LIVE_LIMIT", "80"))


def _to_live(method, files: dict, chat_id: int):
    """Записанный вызов → эквивалентный запрос в живой чат (правки превращаются в новые сообщения)."""
    def photo(src):
        return files.get(src, None) if isinstance(src, str) else src
    if isinstance(method, (SendMessage, EditMessageText)):
        return SendMessage(chat_id=chat_id, text=method.text, parse_mode=method.parse_mode,
                           reply_markup=method.reply_markup)
    if isinstance(method, SendPhoto):
        p = photo(method.photo)
        return p and SendPhoto(chat_id=chat_id, photo=p, caption=method.caption, parse_mode=method.parse_mode,
                               reply_markup=method.reply_markup)
    if isinstance(method, EditMessageMedia):
        p = photo(method.media.media)
        return p and SendPhoto(chat_id=chat_id, photo=p, caption=method.media.caption,
                               parse_mode=method.media.parse_mode, reply_markup=method.reply_markup)
    if isinstance(method, SendInvoice):
        return method.model_copy(update={"chat_id": chat_id})
    return None


async def _record(env, sm):
    import tests.test_bot_scenarios as scen
    import tests.test_zz_tour as tour
    await tour.test_tour(env, sm)
    await scen.test_hostile_names_are_escaped_everywhere(env, sm)
    p = Player(env, 8001, "Ада Лавлейс")
    await p.press(Do(a="pay", z="engineer_watch"))


async def test_replay_conversion_dry_run(env, sm):  # noqa: F811
    """Без сети: все записанные экраны превращаются в корректные запросы, картинки находят исходный файл."""
    from aiogram.types import BufferedInputFile

    from tests.telegram_rules import check_method
    await _record(env, sm)
    reqs = []
    for m in env.session.history:
        if isinstance(m, (SendMessage, EditMessageText, SendPhoto, EditMessageMedia, SendInvoice)):
            req = _to_live(m, env.session.files, 123)
            assert req is not None, f"не удалось перевести {type(m).__name__}"
            check_method(req)
            if isinstance(req, SendPhoto):
                assert isinstance(req.photo, BufferedInputFile), req.photo
            reqs.append(req)
    assert len(reqs) > 20 and any(isinstance(r, SendInvoice) for r in reqs)


@live_only
async def test_replay_screens_into_real_telegram(env, sm):  # noqa: F811
    await _record(env, sm)

    live = Bot(TOKEN)
    me = await live.get_me()
    print(f"\nбот: @{me.username}")
    seen, errors, sent = set(), [], 0
    try:
        for m in env.session.history:
            req = _to_live(m, env.session.files, int(CHAT))
            if req is None:
                continue
            key = (type(req).__name__, getattr(req, "text", None) or getattr(req, "caption", None) or "")
            if key in seen:
                continue
            seen.add(key)
            for _ in range(3):
                try:
                    await live(req)
                    sent += 1
                    break
                except TelegramRetryAfter as ex:
                    await asyncio.sleep(ex.retry_after + 1)
                except TelegramBadRequest as ex:
                    errors.append(f"{type(req).__name__}: {ex.message} :: {key[1][:120]!r}")
                    break
            await asyncio.sleep(1.1)
            if sent >= LIMIT:
                break
    finally:
        await live.session.close()
    print(f"отправлено в Telegram: {sent}, ошибок: {len(errors)}")
    assert sent > 20
    assert not errors, "\n".join(errors)
