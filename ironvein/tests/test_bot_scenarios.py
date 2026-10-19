"""Многопользовательские сквозные сценарии через Dispatcher: компании, контракты, рынок, поддержка, админка,
уведомления фоновых задач. Любой «Сбой терминала» или «Кнопка устарела» валит тест."""

from datetime import UTC, datetime

import pytest
from aiogram import Bot
from aiogram.methods import SendMessage, SendPhoto
from aiogram.types import CallbackQuery, Chat, Message, PhotoSize, Update, User
from sqlalchemy import select

import ironvein.db as db
import tests.test_bot_flow as flow
from ironvein.config import get_settings
from ironvein.handlers.ui import Do, Nav
from ironvein.models import Company, Contract, MarketOrder
from ironvein.models import User as DbUser
from ironvein.services import clock
from tests.helpers import bal, give, qty

BAD = ("Сбой терминала", "Неизвестная кнопка")


class Player:
    def __init__(self, env, tg_id: int, name: str):
        self.env, self.tg = env, tg_id
        self.user = User(id=tg_id, is_bot=False, first_name=name, username=f"p{tg_id}")
        self.chat = Chat(id=tg_id, type="private")

    async def text(self, t):
        e = self.env
        e.n += 1
        await e.dp.feed_update(e.bot, Update(update_id=e.n, message=Message(
            message_id=e.n, date=datetime.now(UTC), chat=self.chat, from_user=self.user, text=t)))

    async def press(self, cb, photo=False):
        e = self.env
        e.n += 1
        msg = Message(message_id=5, date=datetime.now(UTC), chat=self.chat, text=None if photo else "screen",
                      photo=[PhotoSize(file_id="x", file_unique_id="y", width=1, height=1)] if photo else None)
        await e.dp.feed_update(e.bot, Update(update_id=e.n, callback_query=CallbackQuery(
            id=str(e.n), from_user=self.user, chat_instance="ci", message=msg, data=cb.pack())))

    async def db_id(self, sm):
        async with sm() as s:
            return (await s.scalar(select(DbUser).where(DbUser.tg_id == self.tg))).id


class Env:
    pass


@pytest.fixture
async def env(sm, monkeypatch):
    monkeypatch.setattr(db, "_sessionmaker", sm)
    monkeypatch.setenv("ADMIN_IDS", "9001")
    get_settings.cache_clear()
    session = flow.FakeSession()
    e = Env()
    if flow._DP is None:
        from ironvein.bot import build_dispatcher
        flow._DP = build_dispatcher()
    e.dp, e.bot, e.session, e.n = flow._DP, Bot("42:TEST", session=session), session, 0
    e.texts = lambda: session.texts()
    yield e
    bad = [t for t in session.texts() if t and any(b in t for b in BAD)]
    assert not bad, bad
    get_settings.cache_clear()


def last_text(env) -> str:
    return env.texts()[-1]


async def test_company_lifecycle_via_buttons(env, sm):
    a, b = Player(env, 1001, "Анна"), Player(env, 1002, "Борис")
    await a.text("/start")
    await b.text("/start")
    await a.press(Do(a="comp_new"))
    await a.text("Ржавый Синдикат")
    async with sm() as s:
        comp = await s.scalar(select(Company))
    assert comp.name == "Ржавый Синдикат"
    assert (await bal(sm, await a.db_id(sm)))["main"] == 500
    await a.press(Do(a="cdep", x=comp.id))
    await a.text("abc")  # ошибка ввода — сценарий не сбрасывается
    assert "ещё раз" in last_text(env)
    await a.text("300")
    assert (await bal(sm, comp.id))["main"] == 300
    await a.press(Do(a="cinv", x=comp.id))
    await a.text("@p1002")
    async with sm() as s:
        from ironvein.models import CompanyInvite
        inv = await s.scalar(select(CompanyInvite))
    await b.press(Do(a="inv", x=inv.id, y=1, k="i1"))
    bid = await b.db_id(sm)
    await a.press(Nav(s="cmember", a=f"{comp.id}:{bid}"))
    await a.press(Do(a="cperm", x=comp.id, y=bid, z="4", k="p1"))  # выдать «рынок»
    await a.press(Nav(s="cpay", a=str(comp.id)))
    await a.press(Do(a="cpay_to", x=comp.id, y=bid))
    await a.text("100")
    assert (await bal(sm, bid))["main"] == 1100
    await b.press(Do(a="act", x=comp.id))
    await b.press(Nav(s="comp", a=str(comp.id)))
    assert "от имени компании" in last_text(env)
    await a.press(Do(a="cclose", x=comp.id))
    await a.press(Do(a="cclose_go", x=comp.id, k="c1"))
    async with sm() as s:
        assert (await s.get(Company, comp.id)).status == "closed"
    assert (await bal(sm, await a.db_id(sm)))["main"] == 500 - 300 + 200


async def test_supply_contract_via_buttons(env, sm):
    a, b = Player(env, 1101, "Заказчик"), Player(env, 1102, "Поставщик")
    await a.text("/start")
    await b.text("/start")
    await a.press(Do(a="cnew", z="supply"))
    await a.press(Do(a="cnew_res", z="supply:steel"))
    await a.press(Do(a="cnew_loc", z="supply:steel:rust:"))
    await a.text("10 500 24")
    async with sm() as s:
        c = await s.scalar(select(Contract))
    assert c.status == "draft"
    await a.press(Do(a="cpub", x=c.id, k="a1"))
    await b.press(Nav(s="ctr_list", a="supply"))
    await b.press(Do(a="caccept", x=c.id, k="b1"))
    await give(sm, await b.db_id(sm), "rust", "steel", 10)
    await b.press(Do(a="cdeliver", x=c.id))
    await b.text("4")
    await b.press(Do(a="cdeliver", x=c.id))
    await b.text("6")
    async with sm() as s:
        c = await s.get(Contract, c.id)
    assert c.status == "completed" and c.paid_out == 490
    assert await qty(sm, await a.db_id(sm), "rust", "steel") == 10


async def test_market_trade_via_text_inputs(env, sm):
    a, b = Player(env, 1201, "Продавец"), Player(env, 1202, "Покупатель")
    await a.text("/start")
    await b.text("/start")
    await give(sm, await a.db_id(sm), "rust", "coal", 20)
    await a.press(Do(a="ask", z="rust:coal"))
    await a.text("20 7")
    async with sm() as s:
        o = await s.scalar(select(MarketOrder))
    await b.press(Nav(s="book", a="rust:coal"))
    assert "#%d" % o.id in last_text(env)
    await b.press(Do(a="buy", x=o.id))
    await b.text("999")  # больше, чем есть — повтор ввода
    assert "ещё раз" in last_text(env)
    await b.text("5")
    assert await qty(sm, await b.db_id(sm), "rust", "coal") == 5
    await a.press(Nav(s="my_orders"))
    await a.press(Do(a="ocancel", x=o.id, k="x"))
    assert await qty(sm, await a.db_id(sm), "rust", "coal") == 15


async def test_support_admin_and_fallback(env, sm):
    p = Player(env, 1301, "Игрок")
    admin = Player(env, 9001, "Админ")
    await p.text("/start")
    await p.text("привет, бот")
    assert "не понял" in last_text(env)
    await p.text("/paysupport")
    await p.press(Do(a="support"))
    await p.text("Заказ 5 не выдан")
    sent_to_admin = [c for c in env.session.calls if isinstance(c, (SendMessage, SendPhoto))
                     and getattr(c, "chat_id", None) == 9001]
    assert sent_to_admin and "Заказ 5" in sent_to_admin[-1].text
    await admin.text("/start")
    for cmd in ("/admin", "/admin_active", "/admin_orders", "/admin_user @p1301", "/admin_help"):
        env.session.calls.clear()
        await admin.text(cmd)
        assert env.texts(), cmd
    await admin.text("/admin_grant 1 rust ore 5")
    await p.text("/admin")  # не админ: команда не существует для него
    assert "не понял" in last_text(env)


async def test_background_notifications(env, sm):
    """Фоновые задачи + уведомитель: добыча, прибытие по контракту перевозки, просрочка."""
    from ironvein.bot import make_notifier
    from ironvein.jobs.runner import run_once
    from ironvein.services import contracts as csvc
    from ironvein.services import production
    from tests.helpers import deposit_id, user_items
    from tests.test_transport import make_truck
    a, b = Player(env, 1401, "Шахтёр"), Player(env, 1402, "Возчик")
    await a.text("/start")
    await b.text("/start")
    ua, ub = await a.db_id(sm), await b.db_id(sm)
    pick = (await user_items(sm, ua, "pick"))[0]
    async with sm() as s, s.begin():
        await production.start_mining(s, ua, ua, await deposit_id(sm, "rust_north"), pick.id)
    truck = await make_truck(sm, ub)
    await give(sm, ua, "rust", "ore", 20)
    await give(sm, ub, "rust", "diesel", 10)
    async with sm() as s, s.begin():
        c = await csvc.create(s, ua, ua, kind="transport", resource="ore", qty=20, price_total=300, location="rust",
                              dest="kotlo", deadline_hours=5)
        await csvc.publish(s, ua, c.id)
        await csvc.accept_transport(s, ub, ub, c.id, truck)
        c2 = await csvc.create(s, ua, ua, kind="supply", resource="steel", qty=1, price_total=10, location="rust",
                               deadline_hours=1)
        await csvc.publish(s, ua, c2.id)
    clock.advance(hours=2)
    env.session.calls.clear()
    res = await run_once(sm, make_notifier(env.bot))
    assert res["jobs"] == 1 and res["shipments"] == 1 and res["contracts"] == 1
    texts = " | ".join(env.texts())
    assert "Готово" in texts and "прибыл" in texts and "просрочен" in texts and "перевозчику" in texts
