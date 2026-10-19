"""Старт, меню, профиль, инвентарь, справка и общий механизм текстового ввода."""

from collections.abc import Awaitable, Callable

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy import func, select

from ironvein.domain.catalog import LOCATIONS, resource_name
from ironvein.domain.money import fmt_cr
from ironvein.handlers.ui import Nav, back, btn, current_user, acting, e, guarded, kb, show, tx
from ironvein.models import Item, Job, Shipment
from ironvein.repositories.stocks import stocks_of
from ironvein.repositories.wallets import balances
from ironvein.services import companies, items, users

router = Router(name="base")


class Input(StatesGroup):
    value = State()


InputHandler = Callable[[Message, str, dict], Awaitable[None]]
INPUTS: dict[str, InputHandler] = {}


def on_input(kind: str):
    def deco(fn: InputHandler) -> InputHandler:
        INPUTS[kind] = fn
        return fn
    return deco


async def ask(event: Message | CallbackQuery, state: FSMContext, kind: str, prompt: str, **data) -> None:
    await state.set_state(Input.value)
    await state.update_data(kind=kind, **data)
    msg = event.message if isinstance(event, CallbackQuery) else event
    await msg.answer(f"{prompt}\n\n<i>Введите значение сообщением или /cancel.</i>", parse_mode="HTML")
    if isinstance(event, CallbackQuery):
        await event.answer()


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Ввод отменён.", reply_markup=kb(back()))


@router.message(Input.value, F.text)
async def got_input(message: Message, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    handler = INPUTS.get(data.get("kind", ""))
    if handler is None:
        return
    await guarded(message, lambda: handler(message, message.text.strip(), data))


def parse_int(text: str, lo: int = 1, hi: int = 10**9) -> int:
    from ironvein.domain.errors import GameError
    t = text.replace(" ", "").replace("₭", "")
    if not t.isdigit():
        raise GameError("Нужно целое число.")
    v = int(t)
    if not lo <= v <= hi:
        raise GameError(f"Число должно быть от {lo} до {hi}.")
    return v


# --- Меню --------------------------------------------------------------------------------------------

MENU = [
    [("Профиль", "profile"), ("Склады", "inventory")],
    [("Добыча", "mine"), ("Производство", "production")],
    [("Техника", "equipment"), ("Перевозки", "transport")],
    [("Компания", "company"), ("Контракты", "contracts")],
    [("Рынок", "market"), ("Донат ⭐", "donate")],
]


def menu_kb():
    return kb(*[[btn(t, Nav(s=s)) for t, s in row] for row in MENU], [btn("Справка", Nav(s="help"))])


async def menu_text(s, user) -> str:
    acc, label = await acting(s, user)
    b = await balances(s, acc)
    return (f"<b>IRONVEIN</b> · терминал промышленника\n"
            f"Действуете: {label}\n"
            f"Касса: <b>{fmt_cr(b.get('main', 0))}</b> · в резерве {fmt_cr(b.get('hold', 0))}\n"
            "Смог над Ржавой Падью гуще обычного. Выбирайте отдел.")


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    async with tx() as s:
        user, created = await users.get_or_register(
            s, message.from_user.id, message.from_user.full_name, message.from_user.username)
        text = await menu_text(s, user)
    if created:
        text = ("<b>Добро пожаловать в IronVein.</b>\n"
                "Вам выдан стартовый капитал и кирка — она лежит на складе в Ржавой Пади. "
                "Добывайте руду и уголь, плавьте сталь, стройте мастерскую, торгуйте с людьми. "
                "Цены здесь назначают только игроки.\n\n") + text
    await show(message, text, menu_kb(), scene="start")


@router.callback_query(Nav.filter(F.s == "menu"))
async def cb_menu(cq: CallbackQuery, state: FSMContext):
    await state.clear()
    async with tx() as s:
        user = await current_user(s, cq.from_user)
        text = await menu_text(s, user)
    await show(cq, text, menu_kb())
    await cq.answer()


HELP = """<b>Справка IronVein</b>
<code>/mine</code> — добыча: руками, киркой/насосом или буровой/качалкой (дизель).
<code>/production</code> — плавка, перегонка, запчасти, постройка установок, сборка грузовика.
<code>/equipment</code> — ваши предметы: ремонт, продажа, передача.
<code>/transport</code> — рейсы между локациями: грузоподъёмность, топливо, износ, ETA.
<code>/company</code> — компании: роли, права, корпоративная касса, выплаты.
<code>/contracts</code> — договоры поставки и перевозки с резервированием оплаты.
<code>/market</code> — заявки на продажу и покупку; цены — только сделки игроков.
<code>/donate</code> — косметика и коллекции за Telegram Stars (без игровых бонусов).
<code>/paysupport</code> — вопросы по платежам Stars.

Товары лежат на складах конкретных локаций. Чтобы продать сталь в Котлограде, её нужно туда отвезти.
Комиссия рынка и контрактов уничтожается — это главный сток крон."""


@router.message(Command("help"))
async def cmd_help(message: Message):
    await show(message, HELP, kb(back()))


@router.callback_query(Nav.filter(F.s == "help"))
async def cb_help(cq: CallbackQuery):
    await show(cq, HELP, kb(back()))
    await cq.answer()


# --- Профиль и склады (без картинок — это статистика) ------------------------------------------------


async def profile_text(s, user) -> str:
    acc, label = await acting(s, user)
    own = await balances(s, user.id)
    lines = [f"<b>Профиль · {e(user.display_name)}</b>", f"ID: <code>{user.id}</code>",
             f"Личная касса: {fmt_cr(own.get('main', 0))} (резерв {fmt_cr(own.get('hold', 0))})",
             f"Действуете: {label}"]
    ms = await companies.memberships(s, user.id)
    if ms:
        from ironvein.domain.permissions import ROLE_RU
        lines.append("Компании: " + ", ".join(f"«{e(c.name)}» ({ROLE_RU[m.role]})" for c, m in ms))
    jobs = await s.scalar(select(func.count()).select_from(Job).where(Job.owner_id == acc, Job.status == "running"))
    trips = await s.scalar(select(func.count()).select_from(Shipment).where(
        Shipment.carrier_id == acc, Shipment.status.in_(("loading", "in_transit"))))
    lines.append(f"Задания в работе: {jobs} · рейсы: {trips}")
    crest = await s.scalar(select(Item).where(Item.owner_id == acc, Item.def_code == "syndicate_crest").limit(1))
    if crest:
        lines.append(f"Герб: {e(items.title(crest))}")
    return "\n".join(lines)


@router.message(Command("profile"))
async def cmd_profile(message: Message):
    async with tx() as s:
        text = await profile_text(s, await current_user(s, message.from_user))
    await show(message, text, kb(back()))


@router.callback_query(Nav.filter(F.s == "profile"))
async def cb_profile(cq: CallbackQuery):
    async with tx() as s:
        text = await profile_text(s, await current_user(s, cq.from_user))
    await show(cq, text, kb(back()))
    await cq.answer()


async def inventory_text(s, account_id: int, label: str) -> str:
    lines = [f"<b>Склады</b> · {label}"]
    by_loc: dict[str, list[str]] = {}
    for st in await stocks_of(s, account_id):
        held = f" (+{st.held} в резерве)" if st.held else ""
        by_loc.setdefault(st.location_code, []).append(f"  {resource_name(st.resource)}: {st.free}{held}")
    for loc, rows in by_loc.items():
        lines.append(f"▸ {LOCATIONS[loc].name}")
        lines.extend(rows)
    if not by_loc:
        lines.append("Склады пусты.")
    its = (await s.scalars(select(Item).where(Item.owner_id == account_id, Item.parent_id.is_(None),
                                              Item.status != "destroyed").order_by(Item.def_code, Item.id))).all()
    if its:
        lines.append("<b>Предметы</b>")
        for it in its[:40]:
            where = LOCATIONS[it.location_code].name if it.location_code else "при себе"
            dur = f" {it.durability}/{it.max_durability}" if it.max_durability else ""
            lines.append(f"  {e(items.title(it))}{dur} · {where} · {items.STATUS_RU[it.status]}")
    return "\n".join(lines)


@router.message(Command("inventory"))
async def cmd_inventory(message: Message):
    async with tx() as s:
        user = await current_user(s, message.from_user)
        acc, label = await acting(s, user)
        text = await inventory_text(s, acc, label)
    await show(message, text, kb(back()))


@router.callback_query(Nav.filter(F.s == "inventory"))
async def cb_inventory(cq: CallbackQuery):
    async with tx() as s:
        user = await current_user(s, cq.from_user)
        acc, label = await acting(s, user)
        text = await inventory_text(s, acc, label)
    await show(cq, text, kb(back()))
    await cq.answer()


@router.callback_query(Nav.filter(F.s == "noop"))
async def cb_noop(cq: CallbackQuery):
    await cq.answer()


__all__ = ["router", "ask", "on_input", "parse_int", "Input"]
