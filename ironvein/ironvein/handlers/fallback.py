"""Последний роутер: непонятный текст и непредвиденные ошибки."""

import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery, ErrorEvent, Message

from ironvein.handlers.ui import Nav, btn, kb

log = logging.getLogger(__name__)
router = Router(name="fallback")


@router.message(F.text)
async def unknown_text(message: Message):
    await message.answer("Терминал не понял команду. Откройте меню или /help.",
                         reply_markup=kb([btn("☰ Меню", Nav(s="menu")), btn("Справка", Nav(s="help"))]))


@router.callback_query()
async def unknown_callback(cq: CallbackQuery):
    await cq.answer("Кнопка устарела. Откройте меню заново.", show_alert=True)



async def on_error(event: ErrorEvent):
    """Непредвиденная ошибка не должна оставлять «крутящуюся» кнопку или молчание."""
    log.exception("unhandled error in update %s", event.update.update_id, exc_info=event.exception)
    upd = event.update
    try:
        if upd.callback_query:
            await upd.callback_query.answer("Сбой терминала. Операция не выполнена, попробуйте ещё раз.",
                                            show_alert=True)
        elif upd.message and upd.message.chat.type == "private":
            await upd.message.answer("Сбой терминала. Операция не выполнена, попробуйте ещё раз.")
    except Exception:
        pass
    return True
