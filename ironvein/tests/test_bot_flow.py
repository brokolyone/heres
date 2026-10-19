"""Сквозные сценарии через настоящий Dispatcher aiogram с подменённой HTTP-сессией (без сети)."""

from datetime import UTC, datetime

import pytest
from aiogram import Bot
from aiogram.client.session.base import BaseSession
from aiogram.methods import (
    AnswerCallbackQuery,
    AnswerPreCheckoutQuery,
    EditMessageMedia,
    EditMessageText,
    SendInvoice,
    SendMessage,
    SendPhoto,
)
from aiogram.types import (
    CallbackQuery,
    Chat,
    Message,
    PhotoSize,
    PreCheckoutQuery,
    SuccessfulPayment,
    Update,
    User,
)
from sqlalchemy import select

import ironvein.db as db
from ironvein.bot import build_dispatcher
from ironvein.handlers.ui import Do, Nav
from ironvein.models import Item, MarketOrder, PremiumOrder
from ironvein.models import User as DbUser
from tests.helpers import give
from tests.telegram_rules import check_method

TG = 777001
_DP = None


class FakeSession(BaseSession):
    def __init__(self):
        super().__init__()
        self.calls = []
        self.history = []  # не очищается: для проверки отсутствия сбоев за весь тест
        self._mid = 100

    async def close(self):
        pass

    async def stream_content(self, *a, **kw):  # pragma: no cover
        yield b""

    async def make_request(self, bot, method, timeout=None):
        check_method(method)  # правила настоящего Bot API: битый HTML, лимиты, callback_data
        self.calls.append(method)
        self.history.append(method)
        self._mid += 1
        chat = Chat(id=TG, type="private")
        now = datetime.now(UTC)
        if isinstance(method, (SendPhoto, EditMessageMedia)):
            caption = method.caption if isinstance(method, SendPhoto) else method.media.caption
            return Message(message_id=self._mid, date=now, chat=chat, caption=caption,
                           photo=[PhotoSize(file_id=f"f{self._mid}", file_unique_id=f"u{self._mid}", width=576, height=324)])
        if isinstance(method, (SendMessage, EditMessageText, SendInvoice)):
            return Message(message_id=self._mid, date=now, chat=chat, text=getattr(method, "text", None) or "invoice")
        return True

    def of(self, cls):
        return [c for c in self.calls if isinstance(c, cls)]

    def texts(self):
        out = []
        for c in self.calls:
            if isinstance(c, SendPhoto):
                out.append(c.caption)
            elif isinstance(c, EditMessageMedia):
                out.append(c.media.caption)
            elif isinstance(c, (SendMessage, EditMessageText)):
                out.append(c.text)
            elif isinstance(c, AnswerCallbackQuery) and c.text:
                out.append(c.text)
        return out


@pytest.fixture
async def env(sm, monkeypatch):
    monkeypatch.setattr(db, "_sessionmaker", sm)
    session = FakeSession()
    bot = Bot("42:TEST", session=session)
    global _DP
    if _DP is None:
        _DP = build_dispatcher()  # роутеры модульные: диспетчер собирается один раз на процесс
    dp = _DP
    state = {"uid": 0}

    def upd(**kw):
        state["uid"] += 1
        return Update(update_id=state["uid"], **kw)

    user = User(id=TG, is_bot=False, first_name="Ада", username="ada")
    chat = Chat(id=TG, type="private")

    async def text(t):
        await dp.feed_update(bot, upd(message=Message(message_id=state["uid"] + 1000, date=datetime.now(UTC), chat=chat,
                                                      from_user=user, text=t)))

    async def press(cb, photo=False):
        msg = Message(message_id=5, date=datetime.now(UTC), chat=chat, text=None if photo else "screen",
                      photo=[PhotoSize(file_id="x", file_unique_id="y", width=1, height=1)] if photo else None)
        await dp.feed_update(bot, upd(callback_query=CallbackQuery(id=str(state["uid"]), from_user=user,
                                                                   chat_instance="ci", message=msg, data=cb.pack())))

    class E:
        pass
    e = E()
    e.session, e.bot, e.dp, e.text, e.press, e.upd, e.user, e.chat = session, bot, dp, text, press, upd, user, chat
    yield e
    crashes = [m for m in session.history if any(x in str(getattr(m, "text", "") or "")
                                                 for x in ("Сбой терминала", "Неизвестная кнопка", "не понял"))]
    assert not crashes, "необработанная ошибка в обработчике (см. лог)"


async def db_user(sm):
    async with sm() as s:
        return await s.scalar(select(DbUser).where(DbUser.tg_id == TG))


async def test_start_registers_and_sends_pixel_art(env, sm):
    await env.text("/start")
    photos = env.session.of(SendPhoto)
    assert photos and "Добро пожаловать" in photos[0].caption
    u = await db_user(sm)
    assert u is not None
    # Статистика — без картинки.
    env.session.calls.clear()
    await env.text("/profile")
    assert env.session.of(SendMessage) and not env.session.of(SendPhoto)


async def test_mining_via_buttons_edits_message_and_resists_double_press(env, sm):
    await env.text("/start")
    u = await db_user(sm)
    async with sm() as s:
        pick = await s.scalar(select(Item).where(Item.owner_id == u.id, Item.def_code == "pick"))
        from ironvein.models import Deposit
        dep = await s.scalar(select(Deposit).where(Deposit.code == "rust_north"))
    await env.press(Nav(s="mine_loc", a="rust"))
    assert any("Северная жила" in t for t in env.session.texts())
    env.session.calls.clear()
    cb = Do(a="mine", x=dep.id, y=pick.id, k="feedbeef")
    await env.press(cb, photo=True)
    assert env.session.of(EditMessageMedia), env.session.calls  # картинка-сцена вместо нового сообщения
    assert any("Смена началась" in t for t in env.session.texts())
    env.session.calls.clear()
    await env.press(cb, photo=True)  # повторное нажатие той же кнопки
    assert any("Уже выполнено" in t for t in env.session.texts())


async def test_stale_or_foreign_button_is_safe(env, sm):
    await env.text("/start")
    env.session.calls.clear()
    await env.press(Do(a="jcancel", x=999999, k="aa"))
    assert any("не найдено" in t.lower() for t in env.session.texts())


async def test_sell_item_through_text_input(env, sm):
    await env.text("/start")
    u = await db_user(sm)
    async with sm() as s:
        pick = await s.scalar(select(Item).where(Item.owner_id == u.id, Item.def_code == "pick"))
    await env.press(Do(a="sellitem", x=pick.id))
    await env.text("150")
    async with sm() as s:
        o = await s.scalar(select(MarketOrder).where(MarketOrder.item_id == pick.id))
    assert o is not None and o.price == 150 and o.status == "open"


async def test_truck_trip_via_buttons(env, sm):
    await env.text("/start")
    u = await db_user(sm)
    from tests.test_transport import make_truck
    truck = await make_truck(sm, u.id)
    await give(sm, u.id, "rust", "steel", 20)
    await give(sm, u.id, "rust", "diesel", 10)
    await env.press(Do(a="trip_plan", x=truck, z="rust:kotlo", k="t1"))
    from ironvein.models import Shipment
    async with sm() as s:
        sh = await s.scalar(select(Shipment).where(Shipment.vehicle_id == truck))
    assert sh.status == "loading"
    await env.press(Do(a="trip_add", x=sh.id, z="steel"))
    await env.text("20")
    env.session.calls.clear()
    await env.press(Do(a="trip_go", x=sh.id, k="t2"), photo=True)
    assert any("Отправлен" in t for t in env.session.texts())
    async with sm() as s:
        assert (await s.get(Shipment, sh.id)).status == "in_transit"


async def test_stars_purchase_end_to_end(env, sm):
    await env.text("/start")
    await env.press(Nav(s="product", a="engineer_watch"))
    await env.press(Do(a="pay", z="engineer_watch"))
    inv = env.session.of(SendInvoice)[-1]
    assert inv.currency == "XTR" and inv.prices[0].amount == 100 and not inv.provider_token
    payload = inv.payload
    await env.dp.feed_update(env.bot, env.upd(pre_checkout_query=PreCheckoutQuery(
        id="pc1", from_user=env.user, currency="XTR", total_amount=100, invoice_payload=payload)))
    ans = env.session.of(AnswerPreCheckoutQuery)[-1]
    assert ans.ok is True
    sp = SuccessfulPayment(currency="XTR", total_amount=100, invoice_payload=payload,
                           telegram_payment_charge_id="tg-charge-1", provider_payment_charge_id="")
    for _ in range(2):  # повторный update
        await env.dp.feed_update(env.bot, env.upd(message=Message(
            message_id=9000, date=datetime.now(UTC), chat=env.chat, from_user=env.user, successful_payment=sp)))
    async with sm() as s:
        orders = (await s.scalars(select(PremiumOrder))).all()
        watches = (await s.scalars(select(Item).where(Item.def_code == "engineer_watch"))).all()
    assert len(orders) == 1 and orders[0].status == "fulfilled"
    assert len(watches) == 1 and watches[0].serial_no == 1
    # Подделанная сумма в pre_checkout отклоняется.
    await env.press(Do(a="pay", z="engineer_watch"))
    p2 = env.session.of(SendInvoice)[-1].payload
    await env.dp.feed_update(env.bot, env.upd(pre_checkout_query=PreCheckoutQuery(
        id="pc2", from_user=env.user, currency="XTR", total_amount=1, invoice_payload=p2)))
    assert env.session.of(AnswerPreCheckoutQuery)[-1].ok is False


async def test_every_menu_screen_renders(env, sm):
    await env.text("/start")
    for screen in ("menu", "profile", "inventory", "mine", "production", "equipment", "transport", "company",
                   "contracts", "market", "donate", "help", "my_orders", "mkt_items", "prod_loc", "trip_new"):
        env.session.calls.clear()
        await env.press(Nav(s=screen))
        assert env.session.texts(), screen
    for cmd in ("/mine", "/production", "/equipment", "/transport", "/company", "/contracts", "/market", "/donate",
                "/help", "/paysupport", "/inventory"):
        env.session.calls.clear()
        await env.text(cmd)
        assert env.session.texts(), cmd
    await env.press(Nav(s="mkt_loc", a="rust"))
    await env.press(Nav(s="book", a="rust:steel"))
    await env.press(Nav(s="ibook", a="engineer_watch"))
    await env.press(Nav(s="prod_list", a="rust:workshop"))
    await env.press(Nav(s="prod_rec", a="rust:assemble_truck"))
    await env.press(Do(a="cnew", z="supply"))
    assert env.session.texts()
