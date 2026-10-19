"""Проверки исходящих запросов так, как их проверяет настоящий Bot API.

Нарушение (битый HTML, неподдерживаемый тег, превышение лимитов, слишком длинный callback_data)
в настоящем Telegram обернулось бы ошибкой 400 и потерянным сообщением — здесь это падение теста.
"""

import html
import re
from html.parser import HTMLParser

# https://core.telegram.org/bots/api#html-style
ALLOWED_TAGS = {"b", "strong", "i", "em", "u", "ins", "s", "strike", "del", "span", "tg-spoiler", "a", "tg-emoji",
                "code", "pre", "blockquote"}
ENTITY = re.compile(r"&(#\d+|#x[0-9a-fA-F]+|lt|gt|amp|quot);")
TAG = re.compile(r"</?([a-zA-Z][\w-]*)(\s[^<>]*)?/?>")


class TelegramRuleError(AssertionError):
    pass


class _Balance(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.stack: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag not in ALLOWED_TAGS:
            raise TelegramRuleError(f"неподдерживаемый тег <{tag}>")
        self.stack.append(tag)

    def handle_endtag(self, tag):
        if not self.stack or self.stack[-1] != tag:
            raise TelegramRuleError(f"непарный </{tag}>, открыты: {self.stack}")
        self.stack.pop()


def visible(text: str) -> str:
    return html.unescape(TAG.sub("", text))


def check_html(text: str) -> None:
    # Всё, что похоже на тег, должно быть разрешённым тегом; остальные '<' и '&' — экранированы.
    stripped = TAG.sub("", text)
    if "<" in stripped or ">" in stripped:
        raise TelegramRuleError(f"неэкранированный '<' или '>' в: {text[:200]!r}")
    if "&" in ENTITY.sub("", stripped):
        raise TelegramRuleError(f"неэкранированный '&' в: {text[:200]!r}")
    p = _Balance()
    p.feed(text)
    p.close()
    if p.stack:
        raise TelegramRuleError(f"незакрытые теги {p.stack} в: {text[:200]!r}")


def check_markup(markup) -> None:
    if markup is None or not hasattr(markup, "inline_keyboard"):
        return
    rows = markup.inline_keyboard
    total = sum(len(r) for r in rows)
    if total > 100:
        raise TelegramRuleError(f"слишком много кнопок: {total}")
    for row in rows:
        if len(row) > 8:
            raise TelegramRuleError(f"больше 8 кнопок в ряду: {len(row)}")
        for b in row:
            if not b.text or not b.text.strip():
                raise TelegramRuleError("пустой текст кнопки")
            if b.callback_data is not None and not 1 <= len(b.callback_data.encode()) <= 64:
                raise TelegramRuleError(f"callback_data {len(b.callback_data.encode())} байт: {b.callback_data}")


def check_method(method) -> None:
    """Проверяет один вызов Bot API (объект aiogram.methods.*)."""
    from aiogram.methods import (
        AnswerCallbackQuery,
        AnswerPreCheckoutQuery,
        EditMessageMedia,
        EditMessageText,
        SendInvoice,
        SendMessage,
        SendPhoto,
    )
    if isinstance(method, (SendMessage, EditMessageText)):
        if method.parse_mode == "HTML":
            check_html(method.text)
        n = len(visible(method.text) if method.parse_mode == "HTML" else method.text)
        if not 1 <= n <= 4096:
            raise TelegramRuleError(f"длина текста {n} вне 1..4096")
    if isinstance(method, SendPhoto) and method.caption is not None:
        if method.parse_mode == "HTML":
            check_html(method.caption)
        if len(visible(method.caption)) > 1024:
            raise TelegramRuleError(f"подпись {len(visible(method.caption))} > 1024")
    if isinstance(method, EditMessageMedia) and method.media.caption is not None:
        check_html(method.media.caption)
        if len(visible(method.media.caption)) > 1024:
            raise TelegramRuleError("подпись медиа > 1024")
    if isinstance(method, AnswerCallbackQuery) and method.text and len(method.text) > 200:
        raise TelegramRuleError(f"ответ на callback {len(method.text)} > 200")
    if isinstance(method, AnswerPreCheckoutQuery) and not method.ok and not method.error_message:
        raise TelegramRuleError("отказ в pre_checkout без error_message")
    if isinstance(method, SendInvoice):
        if method.currency != "XTR" or len(method.prices) != 1:
            raise TelegramRuleError("счёт Stars: только XTR и ровно одна цена")
        if not 1 <= len(method.title) <= 32 or not 1 <= len(method.description) <= 255:
            raise TelegramRuleError("title 1..32, description 1..255")
        if not 1 <= len(method.payload.encode()) <= 128:
            raise TelegramRuleError("payload 1..128 байт")
    check_markup(getattr(method, "reply_markup", None))
