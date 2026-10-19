"""Запуск бота: миграции применяются отдельно (alembic upgrade head), здесь — мир, роутеры и фоновые задачи."""

import asyncio
import logging

from aiogram import BaseMiddleware, Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, CallbackQuery, Message
from sqlalchemy import select

from ironvein.config import get_settings
from ironvein.db import dispose_engine, get_sessionmaker, init_engine
from ironvein.domain import quality
from ironvein.domain.catalog import LOCATIONS, RECIPES, resource_name
from ironvein.handlers import (
    admin,
    base,
    company,
    contracts,
    donate,
    fallback,
    fmt,
    market,
    production,
    transport,
)
from ironvein.handlers.ui import Nav, btn, e, kb, notify
from ironvein.jobs.runner import run_forever
from ironvein.models import (
    Contract,
    Item,
    Job,
    PremiumOrder,
    Shipment,
    ShipmentCargo,
    User,
)
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


class CommandResetsInput(BaseMiddleware):
    """Команда посреди текстового ввода отменяет ввод и выполняется как обычно."""

    async def __call__(self, handler, event, data):
        if isinstance(event, Message) and event.text and event.text.startswith("/") and data.get("state"):
            if await data["state"].get_state() is not None:
                await data["state"].clear()
                data["raw_state"] = None  # фильтры состояния читают raw_state, вычисленный до middleware
        return await handler(event, data)


def build_dispatcher() -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())
    dp.message.outer_middleware(PrivateOnly())
    dp.message.outer_middleware(CommandResetsInput())
    dp.callback_query.outer_middleware(PrivateOnly())
    for r in (admin.router, base.router, production.router, transport.router, market.router, company.router,
              contracts.router, donate.router, fallback.router):
        dp.include_router(r)
    dp.errors.register(fallback.on_error)  # ошибки всплывают до диспетчера из любого роутера
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
                lines = [fmt.ok("Готово"), e(production_svc.describe_job(j)), fmt.kv("Где", LOCATIONS[j.location_code].name)]
                scene = "done"
                if j.kind == "craft" and j.result and j.result.get("item_id"):
                    it = await s.get(Item, j.result["item_id"])
                    lines.append(fmt.kv("Новый предмет", e(items.title(it))))
                    scene = "assembly" if it.def_code == "truck" else "workshop"
                    tier = items.quality_of(it)
                    if tier is not None:
                        lines.append(fmt.kv("Качество", f"{tier.name} {quality.stars(tier)}")
                                     + f" · оценка {items.quality_score(it)}/100"
                                     + (f" · прочность {it.max_durability}" if it.max_durability else ""))
                        if tier.code == "master":
                            lines.append("✦ <b>Мастерская работа!</b> Такое на рынке ценят.")
                        scene = "masterwork" if tier.code == "master" else "inspect"
                elif j.kind == "mine":
                    res = next(iter(j.outputs))
                    scene = f"mine_{res}" if j.manual else "drill" if res != "oil" else "pump"
                    lines.append("Добыча лежит на складе.")
                elif j.kind == "repair":
                    scene = "repair"
                    lines.append(fmt.kv("Прочность", (j.result or {}).get("durability", "—")))
                elif j.recipe_code and RECIPES[j.recipe_code].facility in ("smelter", "refinery"):
                    scene = RECIPES[j.recipe_code].facility
                text = "\n".join(lines)
                scene = f"{scene}@{j.location_code}"
                targets = {u.tg_id}
                markup = kb([btn("📦 Склады", Nav(s="inventory")), btn("⚙ Производство", Nav(s="production"))])
            elif kind == "shipment":
                sh = await s.get(Shipment, data["id"])
                rows = (await s.scalars(select(ShipmentCargo).where(ShipmentCargo.shipment_id == sh.id))).all()
                what = ", ".join(f"{resource_name(c.resource)} {c.qty}" for c in rows if c.resource) or "предметы"
                lines = [fmt.ok(f"Рейс #{sh.id} прибыл"), fmt.kv("Куда", LOCATIONS[sh.dest].name),
                         fmt.kv("Груз", what) + " — на складе назначения."]
                if sh.contract_id:
                    c = await s.get(Contract, sh.contract_id)
                    lines.append(f"Контракт #{c.id} исполнен: перевозчику {fmt.cr(c.paid_out)}, комиссия {fmt.cr(c.fee_paid)}.")
                text = "\n".join(lines)
                creator = await s.get(User, sh.created_by_user_id)
                targets = {creator.tg_id}
                for c_ in rows:
                    t = await tg_of(s, c_.recipient_id)
                    if t:
                        targets.add(t)
                scene = ("foot" if sh.mode == "foot" else "arrive") + f"@{sh.dest}"
                markup = kb([btn("📦 Склады", Nav(s="inventory")), btn("🚚 Перевозки", Nav(s="transport"))])
            elif kind == "contract_expired":
                c = await s.get(Contract, data["id"])
                text = (fmt.warn(f"<b>Контракт #{c.id} просрочен.</b>") +
                        f"\nПоставлено {c.delivered_qty}/{c.qty}; неиспользованный резерв вернулся заказчику.")
                targets = {t for t in (await tg_of(s, c.customer_id), await tg_of(s, c.executor_id)) if t}
                scene = "contract"
                markup = kb([btn("📜 Контракты", Nav(s="contracts"))])
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
    session = None
    if settings.telegram_api_url:
        from aiogram.client.session.aiohttp import AiohttpSession
        from aiogram.client.telegram import TelegramAPIServer
        session = AiohttpSession(api=TelegramAPIServer.from_base(settings.telegram_api_url))
    bot = Bot(settings.bot_token, session=session)
    dp = build_dispatcher()
    await bot.set_my_commands([BotCommand(command=c, description=d) for c, d in COMMANDS])
    try:
        await bot.set_my_short_description("Дизельпанк-экономика: добыча, заводы, грузовики, компании и рынок игроков.")
        await bot.set_my_description(
            "IronVein — промышленная песочница в мире смога, нефти и стали 1930–50-х.\n"
            "Добывайте руду, уголь и нефть, плавьте сталь, собирайте грузовики, возите грузы между городами, "
            "основывайте компании и заключайте контракты. Цены назначают только игроки.\nНажмите «Старт».")
    except Exception:  # описание — косметика, бот работает и без него
        log.warning("could not set bot description")
    jobs = asyncio.create_task(run_forever(sm, settings.job_poll_seconds, make_notifier(bot), make_refunder(bot)))
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        jobs.cancel()
        await bot.session.close()
        await dispose_engine()


if __name__ == "__main__":
    asyncio.run(main())
