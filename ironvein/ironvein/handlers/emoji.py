"""Премиум-эмодзи (custom emoji) в заголовках и кнопках.

Telegram показывает их, если у владельца бота есть Telegram Premium (или куплен юзернейм на Fragment).
Ключи — разделы бота. Значения задаются в CUSTOM_EMOJI или в DEFAULTS; без них интерфейс остаётся без иконок.
ID эмодзи узнаёт администратор: прислать боту сообщение с нужными премиум-эмодзи.
"""

import html

from ironvein.config import get_settings

DEFAULTS: dict[str, tuple[str, str]] = {}  # ключ → (custom_emoji_id, запасной обычный эмодзи)

# Заголовок экрана → ключ иконки
TITLE_KEYS = {
    "IronVein": "menu", "Добыча": "mine", "Производство": "production", "Техника и предметы": "equipment",
    "Перевозки": "transport", "Склады": "inventory", "Профиль": "profile", "Компании и синдикаты": "company",
    "Контракты": "contracts", "Рынок": "market", "Донат · Telegram Stars": "donate", "Справка": "help",
    "Первые шаги": "guide", "Экономика": "admin",
}


def _icons() -> dict[str, tuple[str, str]]:
    custom = {k: (v[0], v[1] if len(v) > 1 else "▫") for k, v in get_settings().custom_emoji.items() if v}
    return {**DEFAULTS, **custom}


def icon_id(key: str | None) -> str | None:
    """custom_emoji_id для иконки кнопки или None."""
    if not key:
        return None
    pair = _icons().get(key)
    return pair[0] if pair else None


def tag(key: str | None) -> str:
    """HTML-тег премиум-эмодзи с пробелом после или пустая строка."""
    pair = _icons().get(key) if key else None
    if not pair:
        return ""
    return f'<tg-emoji emoji-id="{html.escape(pair[0])}">{html.escape(pair[1])}</tg-emoji> '
