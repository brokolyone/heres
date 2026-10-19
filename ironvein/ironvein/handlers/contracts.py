"""Контракты поставки и перевозки."""

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from ironvein.domain.catalog import FOOT_CAPACITY, LOCATIONS, RESOURCES, resource_name, route_km
from ironvein.domain.errors import Forbidden, GameError
from ironvein.domain.money import fee_for, fmt_cr
from ironvein.domain.permissions import Perm
from ironvein.handlers import fmt
from ironvein.handlers.base import ask, on_input, parse_int
from ironvein.handlers.production import eta_text
from ironvein.handlers.ui import Do, Nav, acting, back, btn, current_user, e, guarded, kb, nonce, op_key, show, tx
from ironvein.models import ITEM_IDLE, Account, Contract
from ironvein.services import authz, contracts, transport

router = Router(name="contracts")
EVENT_RU = {"created": "создан", "published": "опубликован, оплата зарезервирована", "accepted": "принят",
            "delivered": "поставка", "withdrawn": "исполнитель отказался", "cancelled": "отменён",
            "expired": "просрочен", "disputed": "открыт спор", "resolved_refund": "спор: возврат заказчику",
            "resolved_resume": "спор: исполнение возобновлено"}


def contracts_menu():
    return kb([btn("📦 Открытые поставки", Nav(s="ctr_list", a="supply")),
               btn("🚚 Открытые перевозки", Nav(s="ctr_list", a="transport"))],
              [btn("📋 Мои контракты", Nav(s="ctr_list", a="mine"))],
              [btn("＋ Заказать поставку", Do(a="cnew", z="supply")), btn("＋ Заказать перевозку", Do(a="cnew", z="transport"))],
              back())


TEXT = "\n".join([
    fmt.head("Контракты", "договоры между игроками и компаниями"),
    "▸ <b>Поставка</b>: заказчик резервирует оплату, исполнитель привозит товар на склад в месте поставки "
    "и получает деньги пропорционально — частями можно.",
    "▸ <b>Перевозка</b>: заказчик резервирует плату и груз, перевозчик забирает его своей машиной; "
    "оплата — после серверного прибытия.",
    "▸ Комиссия 2% уничтожается. Свой контракт принять нельзя.",
])


@router.message(Command("contracts"))
async def cmd_contracts(message: Message):
    await show(message, TEXT, contracts_menu(), scene="contract")


@router.callback_query(Nav.filter(F.s == "contracts"))
async def cb_contracts(cq: CallbackQuery):
    await show(cq, TEXT, contracts_menu(), scene="contract")
    await cq.answer()


STATUS_ICON = {"draft": "✎", "open": "○", "accepted": "◐", "in_progress": "◑", "completed": "✔", "cancelled": "✕",
               "expired": "⌛", "disputed": "⚠"}


def short(c: Contract) -> str:
    route = LOCATIONS[c.location_code].name + (f" → {LOCATIONS[c.dest_code].name}" if c.dest_code else "")
    kind = "📦 Поставка" if c.kind == "supply" else "🚚 Перевозка"
    return f"{kind} #{c.id}: {resource_name(c.resource)} {c.delivered_qty}/{c.qty} · {route} · {fmt_cr(c.price_total)}"


@router.callback_query(Nav.filter(F.s == "ctr_list"))
async def cb_ctr_list(cq: CallbackQuery, callback_data: Nav):
    async with tx() as s:
        user = await current_user(s, cq.from_user)
        acc, label = await acting(s, user)
        if callback_data.a == "mine":
            lst = await contracts.list_mine(s, acc)
            title = f"Мои контракты · {label}"
        else:
            lst = await contracts.list_open(s, callback_data.a)
            title = "Открытые " + ("поставки" if callback_data.a == "supply" else "перевозки")
    lines = [fmt.head(title)] + [f"{STATUS_ICON[c.status]} {short(c)} · {contracts.STATUS_RU[c.status]}" for c in lst]
    if not lst:
        lines.append("Пусто. Создайте свой заказ — его увидят все.")
    rows = [btn(f"#{c.id}", Nav(s="ctr", a=str(c.id))) for c in lst]
    await show(cq, "\n".join(lines), kb(*[rows[i:i + 4] for i in range(0, len(rows), 4)], back("contracts")),
               scene="contract")
    await cq.answer()


async def _is_party(s, user_id: int, account_id: int | None) -> bool:
    if account_id is None:
        return False
    try:
        await authz.require(s, user_id, account_id, Perm.CONTRACTS)
        return True
    except Forbidden:
        return False


async def ctr_card(s, user, cid: int):
    c = await s.get(Contract, cid)
    if c is None:
        raise GameError("Контракт не найден.")
    acc, _ = await acting(s, user)
    cust = await s.get(Account, c.customer_id)
    ex = await s.get(Account, c.executor_id) if c.executor_id else None
    fee = fee_for(c.price_total, c.fee_bps)
    lines = [fmt.head(f"Контракт #{c.id}", f"{STATUS_ICON[c.status]} {contracts.STATUS_RU[c.status]}"), short(c),
             fmt.kv("Заказчик", e(cust.name)) + " · " + fmt.kv("исполнитель", e(ex.name) if ex else "не назначен"),
             fmt.kv("Оплата", fmt_cr(c.price_total)) + f" (исполнителю {fmt_cr(c.price_total - fee)}, комиссия {fmt_cr(fee)})",
             fmt.kv("Выплачено", fmt_cr(c.paid_out)) + " · " + fmt.kv("в резерве", fmt_cr(c.reserved))]
    if c.qty and c.kind == "supply":
        lines.append(f"<code>{fmt.gauge(c.delivered_qty, c.qty)}</code> поставлено {c.delivered_qty}/{c.qty}")
    lines.append(fmt.kv("Срок", f"{c.deadline:%d.%m %H:%M} UTC") + (f" · осталось {fmt.left(c.deadline)}"
                                                                    if c.status in contracts.ACTIVE else ""))
    if c.terms:
        lines.append(f"Условия: {e(c.terms)}")
    if c.kind == "supply":
        lines.append("Поставка частями разрешена, оплата пропорциональна. Товар должен лежать у исполнителя в месте поставки.")
    evs = await contracts.events(s, c.id)
    lines.append(fmt.section("Журнал"))
    lines += [f"<code>{ev.created_at:%d.%m %H:%M}</code> {EVENT_RU.get(ev.event, ev.event)}" for ev in evs[-6:]]
    k = nonce()
    rows = []
    is_cust = acc == c.customer_id
    is_exec = acc == c.executor_id
    if is_cust and c.status == "draft":
        rows.append([btn("Опубликовать и зарезервировать", Do(a="cpub", x=c.id, k=k))])
    if is_cust and c.status in ("draft", "open"):
        rows.append([btn("Отменить", Do(a="ccancel", x=c.id, k=k))])
    if not is_cust and c.status == "open":
        if c.kind == "supply":
            rows.append([btn("Принять поставку", Do(a="caccept", x=c.id, k=k))])
        else:
            trucks = [t for t in await transport.vehicles_of(s, acc)
                      if t.status == ITEM_IDLE and t.location_code == c.location_code]
            for t in trucks[:4]:
                rows.append([btn(f"Принять: грузовик #{t.id}", Do(a="caccept", x=c.id, y=t.id, k=k))])
            if c.qty <= FOOT_CAPACITY:
                rows.append([btn("Принять: пешком", Do(a="caccept", x=c.id, y=0, k=k))])
            if not rows:
                lines.append(f"Чтобы принять, нужна свободная машина в {LOCATIONS[c.location_code].name}.")
    if is_exec and c.kind == "supply" and c.status in ("accepted", "in_progress"):
        rows.append([btn("Поставить", Do(a="cdeliver", x=c.id))])
        if c.status == "accepted" and not c.delivered_qty:
            rows.append([btn("Отказаться", Do(a="cwithdraw", x=c.id, k=k))])
    if (is_cust or is_exec) and c.kind == "supply" and c.status in ("accepted", "in_progress"):
        rows.append([btn("Открыть спор", Do(a="cdispute", x=c.id))])
    return "\n".join(lines), kb(*rows, back("contracts"))


@router.callback_query(Nav.filter(F.s == "ctr"))
async def cb_ctr(cq: CallbackQuery, callback_data: Nav):
    async def run():
        async with tx() as s:
            text, markup = await ctr_card(s, await current_user(s, cq.from_user), int(callback_data.a))
        await show(cq, text, markup, scene="contract")
    await guarded(cq, run)


@router.callback_query(Do.filter(F.a.in_({"cpub", "ccancel", "caccept", "cwithdraw"})))
async def do_ctr_action(cq: CallbackQuery, callback_data: Do):
    async def run():
        scene = "contract"
        note = ""
        async with tx() as s:
            user = await current_user(s, cq.from_user)
            acc, _ = await acting(s, user)
            key = op_key(cq.from_user.id, callback_data.k)
            if callback_data.a == "cpub":
                await contracts.publish(s, user.id, callback_data.x, op_key=key)
                note = "Опубликовано, оплата зарезервирована."
            elif callback_data.a == "ccancel":
                await contracts.cancel(s, user.id, callback_data.x, op_key=key)
                note = "Контракт отменён, резерв возвращён."
            elif callback_data.a == "cwithdraw":
                await contracts.withdraw(s, user.id, callback_data.x)
                note = "Вы отказались от исполнения."
            else:
                c = await s.get(Contract, callback_data.x)
                if c and c.kind == "transport":
                    c = await contracts.accept_transport(s, user.id, acc, callback_data.x, callback_data.y or None, op_key=key)
                    from ironvein.models import Shipment
                    sh = await s.get(Shipment, c.shipment_id)
                    note = f"Груз принят и отправлен. Прибытие через {eta_text(sh.eta)}."
                    scene = "truck_oil" if c.resource in ("oil", "diesel") else "truck_ore" if c.resource in ("ore", "coal") else "truck"
                    if sh.mode == "foot":
                        scene = "foot"
                else:
                    await contracts.accept_supply(s, user.id, acc, callback_data.x, op_key=key)
                    note = "Контракт принят. Поставляйте товар на склад в месте поставки."
                    scene = "train"
            text, markup = await ctr_card(s, user, callback_data.x)
        await show(cq, fmt.ok(note) + "\n" + text, markup, scene=scene)
    await guarded(cq, run)


@router.callback_query(Do.filter(F.a == "cdeliver"))
async def do_cdeliver(cq: CallbackQuery, callback_data: Do, state: FSMContext):
    await ask(cq, state, "cdeliver_qty", "Сколько поставить сейчас?", cid=callback_data.x)


@on_input("cdeliver_qty")
async def in_cdeliver(message: Message, text: str, data: dict):
    q = parse_int(text, 1, 10**6)
    async with tx() as s:
        user = await current_user(s, message.from_user)
        f = await contracts.deliver(s, user.id, data["cid"], q, op_key=op_key(message.from_user.id, f"m{message.message_id}"))
        text_, markup = await ctr_card(s, user, data["cid"])
    await show(message, fmt.ok(f"Поставлено {q}") + f" · получено {fmt_cr(f.payout)}, комиссия {fmt_cr(f.fee)}\n{text_}", markup,
               scene="train")


@router.callback_query(Do.filter(F.a == "cdispute"))
async def do_cdispute(cq: CallbackQuery, callback_data: Do, state: FSMContext):
    await ask(cq, state, "cdispute_reason", "Опишите суть спора. Контракт будет заморожен до решения администрации.",
              cid=callback_data.x)


@on_input("cdispute_reason")
async def in_cdispute(message: Message, text: str, data: dict):
    async with tx() as s:
        user = await current_user(s, message.from_user)
        await contracts.dispute(s, user.id, data["cid"], text)
    await show(message, "Спор открыт. Деньги остаются в резерве; администрация разберётся вручную.",
               kb([btn("К контракту", Nav(s="ctr", a=str(data["cid"])))]), scene="contract")


# --- Создание ----------------------------------------------------------------------------------------


@router.callback_query(Do.filter(F.a == "cnew"))
async def do_cnew(cq: CallbackQuery, callback_data: Do):
    kind = callback_data.z
    rows = [btn(r.name, Do(a="cnew_res", z=f"{kind}:{code}")) for code, r in RESOURCES.items()]
    await show(cq, fmt.head("Новый контракт", "шаг 1 из 3 · ресурс"), kb(*[rows[i:i + 3] for i in range(0, len(rows), 3)], back("contracts")))
    await cq.answer()


@router.callback_query(Do.filter(F.a == "cnew_res"))
async def do_cnew_res(cq: CallbackQuery, callback_data: Do):
    kind, res = callback_data.z.split(":")
    if kind == "supply":
        rows = [[btn(f"Поставка в: {loc.name}", Do(a="cnew_loc", z=f"{kind}:{res}:{code}:"))] for code, loc in LOCATIONS.items()]
    else:
        rows = [[btn(f"{LOCATIONS[a].name} → {LOCATIONS[b].name}", Do(a="cnew_loc", z=f"{kind}:{res}:{a}:{b}"))]
                for a in LOCATIONS for b in LOCATIONS if a != b and route_km(a, b)]
    await show(cq, fmt.head("Новый контракт", "шаг 2 из 3 · где исполнять"), kb(*rows, back("contracts")))
    await cq.answer()


@router.callback_query(Do.filter(F.a == "cnew_loc"))
async def do_cnew_loc(cq: CallbackQuery, callback_data: Do, state: FSMContext):
    kind, res, loc, dest = callback_data.z.split(":")
    await ask(cq, state, "cnew_terms",
              "<b>Шаг 3 из 3.</b> Условия: <code>количество цена_за_всё часов</code>, например <code>50 2000 48</code>.\n"
              + ("Груз будет заблокирован на вашем складе при публикации." if kind == "transport" else ""),
              ctype=kind, res=res, loc=loc, dest=dest or None)


@on_input("cnew_terms")
async def in_cnew_terms(message: Message, text: str, data: dict):
    parts = text.split()
    if len(parts) != 3:
        raise GameError("Нужно три числа: количество, цена за весь объём и срок в часах.")
    q, price, hours = parse_int(parts[0], 1, 100000), parse_int(parts[1]), parse_int(parts[2], 1, 720)
    async with tx() as s:
        user = await current_user(s, message.from_user)
        acc, _ = await acting(s, user)
        c = await contracts.create(s, user.id, acc, kind=data["ctype"], resource=data["res"], qty=q, price_total=price,
                                   location=data["loc"], dest=data["dest"], deadline_hours=hours)
        text_, markup = await ctr_card(s, user, c.id)
    await show(message, fmt.ok("Черновик создан") + " — опубликуйте, чтобы зарезервировать оплату.\n" + text_, markup,
               scene="contract")
