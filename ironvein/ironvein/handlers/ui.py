"""Общие помощники Telegram-интерфейса: рендер экранов, картинки, ошибки, контекст игрока."""

import html
import logging
import re
import secrets
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters.callback_data import CallbackData
from aiogram.types import BufferedInputFile, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, Message
from sqlalchemy.ext.asyncio import AsyncSession

from ironvein.art import render_png
from ironvein.db import get_sessionmaker
from ironvein.domain.errors import AlreadyDone, GameError
from ironvein.models import Company, User
from ironvein.services import users

log = logging.getLogger(__name__)
_photo_ids: dict[str, str] = {}
CAPTION_LIMIT = 1024


class Nav(CallbackData, prefix="n", sep="|"):
    s: str
    a: str = ""


class Do(CallbackData, prefix="d", sep="|"):
    a: str
    x: int = 0
    y: int = 0
    z: str = ""
    k: str = ""


def nonce() -> str:
    """Одноразовый токен кнопки — ключ идемпотентности для повторных нажатий."""
    return secrets.token_hex(4)


def op_key(tg_id: int, k: str) -> str | None:
    return f"tg:{tg_id}:{k}" if k else None


def e(s) -> str:
    return html.escape(str(s))


def btn(text: str, cb: CallbackData | str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=cb.pack() if isinstance(cb, CallbackData) else cb)


def kb(*rows: list[InlineKeyboardButton]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[r for r in rows if r])


def back(screen: str = "menu", text: str = "◂ Назад", arg: str = "") -> list[InlineKeyboardButton]:
    return [btn(text, Nav(s=screen, a=arg)), btn("☰ Меню", Nav(s="menu"))] if screen != "menu" else [btn("☰ Меню", Nav(s="menu"))]


@asynccontextmanager
async def tx():
    async with get_sessionmaker()() as s, s.begin():
        yield s


@asynccontextmanager
async def ro():
    async with get_sessionmaker()() as s:
        yield s


async def current_user(s: AsyncSession, tg_user) -> User:
    user, _ = await users.get_or_register(s, tg_user.id, tg_user.full_name, tg_user.username)
    return user


async def acting(s: AsyncSession, user: User) -> tuple[int, str]:
    """(account_id, подпись) — от чьего имени сейчас действует игрок."""
    acc = user.acting_account_id or user.id
    if acc != user.id:
        from ironvein.services.companies import member
        comp = await s.get(Company, acc)
        if comp is None or comp.status != "active" or await member(s, acc, user.id) is None:
            user.acting_account_id = user.id
            return user.id, "лично"
        return acc, f"компания «{e(comp.name)}»"
    return user.id, "лично"


def _photo(scene: str):
    fid = _photo_ids.get(scene)
    return fid if fid else BufferedInputFile(render_png(scene), filename=f"{scene}.png")


def _remember(scene: str, msg: Message | None) -> None:
    if msg is not None and msg.photo:
        _photo_ids[scene] = msg.photo[-1].file_id


_TAG = re.compile(r"<[^>]+>")


def visible_len(text: str) -> int:
    return len(html.unescape(_TAG.sub("", text)))


def clip(text: str, limit: int = 4096) -> str:
    """Усечение по границе строки: HTML-теги в наших экранах не переходят через строки, поэтому не ломаются."""
    if visible_len(text) <= limit and len(text) <= 4096:
        return text
    out = []
    for line in text.split("\n"):
        if visible_len("\n".join(out + [line, "…"])) > limit or len("\n".join(out + [line])) > 4000:
            break
        out.append(line)
    return "\n".join(out + ["…"])


async def show(event: Message | CallbackQuery, text: str, markup: InlineKeyboardMarkup | None = None,
               scene: str | None = None) -> None:
    """Показывает экран. Для callback редактирует существующее сообщение, а не спамит новыми.

    scene — пиксельная картинка для экранов-действий; экраны статистики идут без картинки.
    Если подпись не помещается в лимит Telegram (1024 видимых символа), экран уходит текстом.
    """
    if scene and visible_len(text) > CAPTION_LIMIT:
        scene = None
    text = clip(text)
    if isinstance(event, CallbackQuery):
        msg = event.message
        if not isinstance(msg, Message):  # слишком старое/недоступное сообщение
            await _send(event.bot, event.from_user.id, text, markup, scene)
            return
        try:
            if scene and msg.photo:
                res = await msg.edit_media(InputMediaPhoto(media=_photo(scene), caption=text, parse_mode="HTML"),
                                           reply_markup=markup)
                _remember(scene, res if isinstance(res, Message) else None)
                return
            if not scene and not msg.photo:
                await msg.edit_text(text, reply_markup=markup, parse_mode="HTML", disable_web_page_preview=True)
                return
        except TelegramBadRequest as ex:
            if "not modified" in str(ex):
                return
            log.debug("edit failed, resend: %s", ex)
        try:
            await msg.delete()
        except TelegramBadRequest:
            pass
        await _send(msg.bot, msg.chat.id, text, markup, scene)
        return
    await _send(event.bot, event.chat.id, text, markup, scene)


async def _send(bot: Bot, chat_id: int, text: str, markup, scene: str | None) -> None:
    if scene:
        res = await bot.send_photo(chat_id, _photo(scene), caption=text, reply_markup=markup, parse_mode="HTML")
        _remember(scene, res)
    else:
        await bot.send_message(chat_id, text, reply_markup=markup, parse_mode="HTML", disable_web_page_preview=True)


async def notify(bot: Bot, chat_id: int, text: str, scene: str | None = None, markup=None) -> None:
    if scene and visible_len(text) > CAPTION_LIMIT:
        scene = None
    try:
        await _send(bot, chat_id, clip(text), markup, scene)
    except Exception:  # пользователь мог заблокировать бота — это не ошибка экономики
        log.info("notify %s failed", chat_id)


async def guarded(event: Message | CallbackQuery, fn: Callable[[], Awaitable[None]]) -> None:
    """Выполняет действие, превращая игровые ошибки в понятные ответы."""
    try:
        await fn()
        if isinstance(event, CallbackQuery):
            try:
                await event.answer()
            except TelegramBadRequest:
                pass
    except AlreadyDone:
        await _answer(event, "Уже выполнено — повторное нажатие проигнорировано.")
    except GameError as ex:
        await _answer(event, ex.message)


async def _answer(event, text: str) -> None:
    if isinstance(event, CallbackQuery):
        try:
            await event.answer(text[:200], show_alert=True)
        except TelegramBadRequest:
            pass
    else:
        await event.answer(e(text), parse_mode="HTML")


def bar(cur: int, mx: int, width: int = 10) -> str:
    if mx <= 0:
        return ""
    filled = round(width * cur / mx)
    return "▮" * filled + "▯" * (width - filled)
