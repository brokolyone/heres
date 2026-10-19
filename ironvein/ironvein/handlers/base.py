"""Старт, меню, профиль, инвентарь, справка и общий механизм текстового ввода."""

from collections.abc import Awaitable, Callable

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy import func, select

from ironvein.domain.catalog import LOCATIONS, RESOURCES, resource_name
from ironvein.domain.errors import AlreadyDone, GameError
from ironvein.handlers import fmt
from ironvein.handlers.ui import (
    Nav,
    acting,
    back,
    btn,
    current_user,
    e,
    kb,
    run_retrying,
    show,
    tx,
)
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


async def ask(event: Message | CallbackQuery, state: FSMContext, input_kind: str, prompt: str, /, **data) -> None:
    await state.set_state(Input.value)
    await state.set_data({**data, "_input": input_kind})
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
    handler = INPUTS.get(data.get("_input", ""))
    await state.clear()
    if handler is None:
        return
    try:
        await run_retrying(lambda: handler(message, message.text.strip(), data))
    except AlreadyDone:
        await message.answer("Уже выполнено.")
    except GameError as ex:
        # Ошибка ввода не сбрасывает сценарий: можно сразу исправить значение.
        await state.set_state(Input.value)
        await state.set_data(data)
        await message.answer(f"⚠ {e(ex.message)}\nВведите значение ещё раз или /cancel.", parse_mode="HTML")


def parse_int(text: str, lo: int = 1, hi: int = 10**9) -> int:
    t = text.replace(" ", "").replace("₭", "")
    if not t.isdigit():
        raise GameError("Нужно целое число.")
    v = int(t)
    if not lo <= v <= hi:
        raise GameError(f"Число должно быть от {lo} до {hi}.")
    return v


# --- Меню --------------------------------------------------------------------------------------------

MENU = [
    [("⛏ Добыча", "mine"), ("⚙ Производство", "production")],
    [("🛠 Техника", "equipment"), ("🚚 Перевозки", "transport")],
    [("📦 Склады", "inventory"), ("👤 Профиль", "profile")],
    [("🏭 Компания", "company"), ("📜 Контракты", "contracts")],
    [("⚖ Рынок", "market"), ("⭐ Донат", "donate")],
]


def menu_kb():
    return kb(*[[btn(t, Nav(s=s)) for t, s in row] for row in MENU],
              [btn("Первые шаги", Nav(s="guide")), btn("Справка", Nav(s="help"))])


async def menu_text(s, user) -> str:
    acc, label = await acting(s, user)
    b = await balances(s, acc)
    jobs = (await s.scalars(select(Job).where(Job.owner_id == acc, Job.status == "running")
                            .order_by(Job.finishes_at))).all()
    trips = (await s.scalars(select(Shipment).where(Shipment.carrier_id == acc,
                                                    Shipment.status.in_(("loading", "in_transit")))
                             .order_by(Shipment.id))).all()
    lines = [fmt.head("IronVein", "терминал промышленника"),
             fmt.kv("Действуете", label),
             fmt.kv("Касса", fmt.cr(b.get("main", 0))) + (f" · резерв {fmt.cr(b['hold'])}" if b.get("hold") else "")]
    if jobs:
        nxt = jobs[0]
        lines.append(f"⚙ Заданий: <b>{len(jobs)}</b> · ближайшее через {fmt.left(nxt.finishes_at)}")
    if trips:
        moving = [t for t in trips if t.status == "in_transit"]
        lines.append(f"🚚 Рейсов: <b>{len(trips)}</b>" + (f" · прибытие через {fmt.left(min(t.eta for t in moving))}"
                                                         if moving else " · под погрузкой"))
    if not jobs and not trips:
        lines.append("<i>Цеха стоят. Смог над Ржавой Падью ждёт работы.</i>")
    return "\n".join(lines)


WELCOME = (
    "<b>Добро пожаловать в IronVein.</b>\n"
    "Вам выданы стартовые кроны и кирка — она лежит на складе в Ржавой Пади. "
    "Добывайте, плавьте, стройте, возите и торгуйте. Цены здесь назначают только игроки.\n"
    "Не знаете, с чего начать? Нажмите «Первые шаги».\n\n"
)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    async with tx() as s:
        user, created = await users.get_or_register(
            s, message.from_user.id, message.from_user.full_name, message.from_user.username)
        text = await menu_text(s, user)
    await show(message, (WELCOME if created else "") + text, menu_kb(), scene="start")


@router.callback_query(Nav.filter(F.s == "menu"))
async def cb_menu(cq: CallbackQuery, state: FSMContext):
    await state.clear()
    async with tx() as s:
        user = await current_user(s, cq.from_user)
        text = await menu_text(s, user)
    await show(cq, text, menu_kb(), scene="start")
    await cq.answer()


GUIDE = "\n".join([
    fmt.head("Первые шаги", "путь от кирки до грузовика"),
    "<b>1.</b> ⛏ <b>Добыча</b> → Ржавая Падь → жила → «Кирка». Смена 10 мин: 6 т руды. Затем уголь.",
    "<b>2.</b> ⚙ <b>Производство</b> → Ржавая Падь → Ручная работа → «Кустарная плавка»: 4 руды + 3 угля → 1 сталь.",
    "<b>3.</b> Накопите 12 стали → «Построить мастерскую». В ней — запчасти, установки и модули.",
    "<b>4.</b> Мастерская: плавильня (сталь втрое выгоднее), буровая (нужен дизель), НПЗ.",
    "<b>5.</b> Грузовик: шасси + двигатель + бак + кузов → «Сборка грузовика». Дизель — из нефти Мазутного Яра "
    "или кустарно из нефти Ржавого колодца.",
    "<b>6.</b> ⚖ <b>Рынок</b>: продавайте излишки и покупайте недостающее. Товар лежит там, где выставлен.",
    "<b>7.</b> 📜 <b>Контракты</b> и 🏭 <b>компании</b> — когда захотите работать с другими по-крупному.",
    "<b>8.</b> ★ <b>Качество изделий</b> растёт с опытом мастера, исправной мастерской и тщательной работой. "
    "Оно меняет прочность (брак ×0.8 … мастерская работа ×1.3) и видно покупателям на рынке.",
    "",
    "<i>Сломалась кирка и нет денег? Добывайте голыми руками и выкуйте новую из 2 стали — тупиков нет.</i>",
])


@router.callback_query(Nav.filter(F.s == "guide"))
async def cb_guide(cq: CallbackQuery):
    await show(cq, GUIDE, kb([btn("⛏ К добыче", Nav(s="mine"))], back()), scene="mine_ore")
    await cq.answer()


HELP = "\n".join([
    fmt.head("Справка"),
    "<b>/mine</b> — добыча руками, инструментом или машинами (дизель).",
    "<b>/production</b> — плавка, перегонка, запчасти, установки, модули, сборка грузовика.",
    "<b>/equipment</b> — ваши предметы: ремонт, продажа, передача, окраска.",
    "<b>/transport</b> — рейсы между локациями: груз, топливо, износ, время в пути.",
    "<b>/inventory</b> — склады по локациям.",
    "<b>/company</b> — компании: роли, права, касса, выплаты.",
    "<b>/contracts</b> — поставки и перевозки с резервированием оплаты.",
    "<b>/market</b> — заявки на продажу и покупку; цены — только сделки игроков.",
    "<b>/donate</b> — косметика и коллекции за Telegram Stars, без игровых бонусов.",
    "<b>/paysupport</b> — вопросы по платежам. <b>/cancel</b> — отменить ввод.",
    fmt.section("Главные правила"),
    "▸ Товары лежат на складах конкретных локаций — их нужно возить.",
    "▸ Процессы идут на сервере, даже когда вы не в сети. Бот пришлёт уведомление.",
    "▸ Комиссия рынка и контрактов (2%) уничтожается — это главный сток крон.",
    "▸ Повторное нажатие кнопки не выполнит операцию дважды.",
    "▸ Качество изделий (★) зависит от опыта, состояния мастерской и режима «Тщательно» и меняет только прочность.",
])


@router.message(Command("help"))
async def cmd_help(message: Message):
    await show(message, HELP, kb([btn("Первые шаги", Nav(s="guide"))], back()))


@router.callback_query(Nav.filter(F.s == "help"))
async def cb_help(cq: CallbackQuery):
    await show(cq, HELP, kb([btn("Первые шаги", Nav(s="guide"))], back()))
    await cq.answer()


# --- Профиль и склады (без картинок — это статистика) ------------------------------------------------


async def profile_text(s, user) -> str:
    from ironvein.domain.permissions import ROLE_RU
    acc, label = await acting(s, user)
    own = await balances(s, user.id)
    lines = [fmt.head("Профиль", e(user.display_name)),
             fmt.kv("ID", f"<code>{user.id}</code>"),
             fmt.kv("Личная касса", fmt.cr(own.get("main", 0))) + f" · резерв {fmt.cr(own.get('hold', 0))}",
             fmt.kv("Действуете", label)]
    ms = await companies.memberships(s, user.id)
    lines.append(fmt.kv("Компании", ", ".join(f"«{e(c.name)}» ({ROLE_RU[m.role]})" for c, m in ms) or "нет"))
    jobs = await s.scalar(select(func.count()).select_from(Job).where(Job.owner_id == acc, Job.status == "running"))
    trips = await s.scalar(select(func.count()).select_from(Shipment).where(
        Shipment.carrier_id == acc, Shipment.status.in_(("loading", "in_transit"))))
    n_items = await s.scalar(select(func.count()).select_from(Item).where(
        Item.owner_id == acc, Item.parent_id.is_(None), Item.status != "destroyed"))
    lines.append(fmt.kv("Задания", jobs) + " · " + fmt.kv("рейсы", trips) + " · " + fmt.kv("предметы", n_items))
    crest = await s.scalar(select(Item).where(Item.owner_id == acc, Item.def_code == "syndicate_crest").limit(1))
    if crest:
        lines.append(f"🛡 Герб: {e(items.title(crest))}")
    lines.append(f"<i>В IronVein с {user.created_at:%d.%m.%Y}</i>")
    return "\n".join(lines)


def profile_kb():
    return kb([btn("📦 Склады", Nav(s="inventory")), btn("🛠 Техника", Nav(s="equipment"))], back())


@router.message(Command("profile"))
async def cmd_profile(message: Message):
    async with tx() as s:
        text = await profile_text(s, await current_user(s, message.from_user))
    await show(message, text, profile_kb())


@router.callback_query(Nav.filter(F.s == "profile"))
async def cb_profile(cq: CallbackQuery):
    async with tx() as s:
        text = await profile_text(s, await current_user(s, cq.from_user))
    await show(cq, text, profile_kb())
    await cq.answer()


async def inventory_text(s, account_id: int, label: str) -> str:
    from ironvein.config import get_settings
    from ironvein.repositories.stocks import used_capacity
    lines = [fmt.head("Склады", label)]
    by_loc: dict[str, list] = {}
    order = list(RESOURCES)
    any_held = False
    for st in sorted(await stocks_of(s, account_id), key=lambda x: (x.location_code, order.index(x.resource))):
        any_held |= st.held > 0
        by_loc.setdefault(st.location_code, []).append(
            (resource_name(st.resource), st.free, f"+{st.held}" if st.held else ""))
    cap = get_settings().warehouse_capacity
    for loc, rows in by_loc.items():
        used = await used_capacity(s, account_id, loc)
        lines.append(fmt.section(f"{LOCATIONS[loc].name} · {used}/{cap}"))
        lines.append(fmt.table(rows, "lrl"))
    if not by_loc:
        lines.append("\nСклады пусты. Начните с ⛏ Добычи.")
    elif any_held:
        lines.append("<i>«+N» — заблокировано под заявки и рейсы.</i>")
    its = (await s.scalars(select(Item).where(Item.owner_id == account_id, Item.parent_id.is_(None),
                                              Item.status != "destroyed").order_by(Item.def_code, Item.id))).all()
    if its:
        lines.append(fmt.section(f"Предметы · {len(its)}"))
        for it in its[:25]:
            where = LOCATIONS[it.location_code].name if it.location_code else "при себе"
            dur = f" {it.durability}/{it.max_durability}" if it.max_durability else ""
            lines.append(f"▸ {e(items.title(it))}{dur} · {where} · {items.STATUS_RU[it.status]}")
        if len(its) > 25:
            lines.append(f"… и ещё {len(its) - 25} — см. 🛠 Технику")
    return "\n".join(lines)


def inventory_kb():
    return kb([btn("🛠 Техника", Nav(s="equipment")), btn("⚖ Рынок", Nav(s="market"))], back())


@router.message(Command("inventory"))
async def cmd_inventory(message: Message):
    async with tx() as s:
        user = await current_user(s, message.from_user)
        acc, label = await acting(s, user)
        text = await inventory_text(s, acc, label)
    await show(message, text, inventory_kb())


@router.callback_query(Nav.filter(F.s == "inventory"))
async def cb_inventory(cq: CallbackQuery):
    async with tx() as s:
        user = await current_user(s, cq.from_user)
        acc, label = await acting(s, user)
        text = await inventory_text(s, acc, label)
    await show(cq, text, inventory_kb())
    await cq.answer()


@router.callback_query(Nav.filter(F.s == "noop"))
async def cb_noop(cq: CallbackQuery):
    await cq.answer()


__all__ = ["router", "ask", "on_input", "parse_int", "Input"]
