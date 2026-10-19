"""Запуск бота: миграции применяются отдельно (alembic upgrade head), здесь — мир, роутеры и фоновые задачи."""

import asyncio
import logging

from aiogram import BaseMiddleware, Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, CallbackQuery, Message
from sqlalchemy import select

from ironvein.config import get_settings
from ironvein.db import dispose_engine, get_sessionmaker, init_engine
from ironvein.domain.catalog import LOCATIONS, RECIPES, resource_name
from ironvein.handlers import admin, base, company, contracts, donate, market, production, transport
from ironvein.handlers.ui import Nav, btn, e, kb, notify
from ironvein.jobs.runner import run_forever
from ironvein.models import Contract, Item, Job, PremiumOrder, Shipment, ShipmentCargo, User
from ironvein.services import authz, items
from ironvein.services import production as production_svc
from ironvein.services.world import ensure_world

log = logging.getLogger("ironvein")

COMMANDS = [
    ("start", "Главное меню"), ("profile", "Профиль"), ("inventory", "Склады"), ("mine", "Добыча"),
    ("production", "Производство"), ("equipment", "Техника"), ("transport", "Перевозки"), ("company", "Компания"),
    ("contracts", "Контракты"), ("market", "Рынок"), ("donate", "Донат за Stars"), ("help", "Справка"),
    ("paysupport", "Поддержка платежей"),
]


class PrivateOnly(BaseMiddleware):
    """Бот работает только в личных чатах: так чужой не нажмёт вашу кнопку."""

    async def __call__(self, handler, event, data):
        chat = event.chat if isinstance(event, Message) else event.message.chat if isinstance(event, CallbackQuery) and event.message else None
        if chat is not None and chat.type != "private":
            if isinstance(event, CallbackQuery):
                await event.answer("IronVein работает только в личных сообщениях с ботом.", show_alert=True)
            return None
        return await handler(event, data)


def build_dispatcher() -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())
    dp.message.outer_middleware(PrivateOnly())
    dp.callback_query.outer_middleware(PrivateOnly())
    for r in (admin.router, base.router, production.router, transport.router, market.router, company.router,
              contracts.router, donate.router):
        dp.include_router(r)
    return dp


def make_notifier(bot: Bot):
    sm = get_sessionmaker()

    async def tg_of(s, account_id: int | None) -> int | None:
        uid = await authz.controller_user_id(s, account_id) if account_id else None
        u = await s.get(User, uid) if uid else None
        return u.tg_id if u else None

    async def notifier(kind: str, data: dict) -> None:
        async with sm() as s:
            if kind == "job":
                j = await s.get(Job, data["id"])
                u = await s.get(User, j.actor_user_id)
                text = f"<b>Готово</b> · {e(production_svc.describe_job(j))} · {LOCATIONS[j.location_code].name}"
                scene = "done"
                if j.kind == "craft" and j.result and j.result.get("item_id"):
                    it = await s.get(Item, j.result["item_id"])
                    text += f"\nНовый предмет: {e(items.title(it))}"
                    scene = "assembly" if it.def_code == "truck" else "workshop"
                elif j.kind == "mine":
                    res = next(iter(j.outputs))
                    scene = f"mine_{res}" if j.manual else "drill" if res != "oil" else "pump"
                elif j.kind == "repair":
                    scene = "repair"
                elif j.recipe_code and RECIPES[j.recipe_code].facility in ("smelter", "refinery"):
                    scene = RECIPES[j.recipe_code].facility
                targets = {u.tg_id}
                markup = kb([btn("Склады", Nav(s="inventory")), btn("Производство", Nav(s="production"))])
            elif kind == "shipment":
                sh = await s.get(Shipment, data["id"])
                rows = (await s.scalars(select(ShipmentCargo).where(ShipmentCargo.shipment_id == sh.id))).all()
                what = ", ".join(f"{resource_name(c.resource)} {c.qty}" for c in rows if c.resource) or "предметы"
                text = (f"<b>Рейс #{sh.id} прибыл</b> в {LOCATIONS[sh.dest].name}.\nГруз: {what} — на складе назначения.")
                creator = await s.get(User, sh.created_by_user_id)
                targets = {creator.tg_id}
                for c in rows:
                    t = await tg_of(s, c.recipient_id)
                    if t:
                        targets.add(t)
                scene = "foot" if sh.mode == "foot" else "arrive"
                markup = kb([btn("Склады", Nav(s="inventory")), btn("Перевозки", Nav(s="transport"))])
            elif kind == "contract_expired":
                c = await s.get(Contract, data["id"])
                text = f"<b>Контракт #{c.id} просрочен.</b> Неиспользованный резерв вернулся заказчику."
                targets = {t for t in (await tg_of(s, c.customer_id), await tg_of(s, c.executor_id)) if t}
                scene = "contract"
                markup = kb([btn("Контракты", Nav(s="contracts"))])
            elif kind == "refund":
                o = await s.get(PremiumOrder, data["id"])
                u = await s.get(User, o.user_id)
                text = f"Stars по заказу {o.id} возвращены."
                targets, scene, markup = {u.tg_id}, None, None
            else:
                return
        for t in targets:
            await notify(bot, t, text, scene, markup)

    return notifier


def make_refunder(bot: Bot):
    async def refund(tg_user_id: int, charge_id: str) -> bool:
        return bool(await bot.refund_star_payment(user_id=tg_user_id, telegram_payment_charge_id=charge_id))
    return refund


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = get_settings()
    if not settings.bot_token or settings.bot_token.startswith("123456:"):
        raise SystemExit("BOT_TOKEN не задан. Скопируйте .env.example в .env и укажите токен от @BotFather.")
    sm = init_engine()
    async with sm() as s, s.begin():
        await ensure_world(s)
    bot = Bot(settings.bot_token)
    dp = build_dispatcher()
    await bot.set_my_commands([BotCommand(command=c, description=d) for c, d in COMMANDS])
    jobs = asyncio.create_task(run_forever(sm, settings.job_poll_seconds, make_notifier(bot), make_refunder(bot)))
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        jobs.cancel()
        await bot.session.close()
        await dispose_engine()


if __name__ == "__main__":
    asyncio.run(main())
