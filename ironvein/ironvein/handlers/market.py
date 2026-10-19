"""Рынок: стакан по ресурсам и локациям, предметы, мои заявки."""

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import func, select

from ironvein.domain.catalog import (
    ITEMS,
    KIND_PREMIUM,
    LOCATIONS,
    RESOURCES,
    item_name,
    resource_name,
)
from ironvein.domain.errors import GameError
from ironvein.handlers import fmt
from ironvein.handlers.base import ask, on_input, parse_int
from ironvein.handlers.ui import (
    Do,
    Nav,
    acting,
    back,
    btn,
    current_user,
    e,
    guarded,
    kb,
    nonce,
    op_key,
    parts,
    show,
    tx,
)
from ironvein.models import ITEM_IDLE, Item, MarketOrder, Stock
from ironvein.repositories.wallets import balances
from ironvein.services import items, market
from ironvein.services.metrics import last_price

router = Router(name="market")


def where(loc: str | None) -> str:
    return LOCATIONS[loc].name if loc else "без локации"


async def market_root(event):
    rows = [[btn(f"⚖ Биржа: {loc.name}", Nav(s="mkt_loc", a=code))] for code, loc in LOCATIONS.items()]
    rows.append([btn("🛠 Техника и премиум", Nav(s="mkt_items")), btn("📋 Мои заявки", Nav(s="my_orders"))])
    text = "\n".join([fmt.head("Рынок", "цены — только заявки и сделки игроков"),
                      "▸ <b>Продажа (ask)</b> блокирует товар, <b>покупка (bid)</b> резервирует кроны.",
                      "▸ Товар лежит в локации заявки — вывозите сами или по контракту.",
                      "▸ Комиссия 2% с продавца уничтожается."])
    await show(event, text, kb(*rows, back()), scene="market")


@router.message(Command("market"))
async def cmd_market(message: Message):
    await market_root(message)


@router.callback_query(Nav.filter(F.s == "market"))
async def cb_market(cq: CallbackQuery):
    await market_root(cq)
    await cq.answer()


@router.callback_query(Nav.filter(F.s == "mkt_loc"))
async def cb_mkt_loc(cq: CallbackQuery, callback_data: Nav):
    loc = callback_data.a
    if loc not in LOCATIONS:
        return await cq.answer("Устаревшая кнопка.", show_alert=True)
    table = [("товар", "ask", "bid", "сделка")]
    rows = []
    async with tx() as s:
        for code, r in RESOURCES.items():
            bk = await market.book(s, resource=code, location=loc, limit=1)
            a = bk["asks"][0].price if bk["asks"] else "—"
            b = bk["bids"][0].price if bk["bids"] else "—"
            last = bk["last"].price if bk["last"] else "—"
            table.append((r.name, a, b, last))
            rows.append(btn(r.name, Nav(s="book", a=f"{loc}:{code}")))
    lines = [fmt.head(f"Биржа · {LOCATIONS[loc].name}"), fmt.table(table, "lrrr"),
             "<i>«—» — заявок или сделок не было. Выдуманных цен здесь нет.</i>"]
    await show(cq, "\n".join(lines), kb(*[rows[i:i + 3] for i in range(0, len(rows), 3)], back("market")),
               scene=f"market@{loc}")
    await cq.answer()


async def book_screen(s, loc: str, res: str, acc: int | None = None):
    bk = await market.book(s, resource=res, location=loc, limit=5)
    lines = [fmt.head(f"{resource_name(res)} · {LOCATIONS[loc].name}")]
    last = bk["last"]
    lines.append(fmt.kv("Последняя сделка", f"{fmt.cr(last.price)} × {last.qty}" if last else "не было")
                 + " · " + fmt.kv("за 24 ч", f"{bk['volume_qty']} ед."))
    if acc is not None:
        st = await s.get(Stock, (acc, loc, res))
        b = await balances(s, acc)
        lines.append(fmt.kv("У вас здесь", st.free if st else 0) + " · " + fmt.kv("касса", fmt.cr(b.get("main", 0))))
    rows = []
    lines.append(fmt.section("Продают (ask)"))
    if bk["asks"]:
        lines.append(fmt.table([(f"#{o.id}", o.qty_left, f"по {o.price} ₭", "ваша" if o.owner_id == acc else "")
                                for o in bk["asks"]], "lrrl"))
    else:
        lines.append("нет предложений")
    for o in bk["asks"]:
        if o.owner_id != acc:
            rows.append([btn(f"Купить из #{o.id} · {fmt.cr(o.price)}", Do(a="buy", x=o.id))])
    lines.append(fmt.section("Покупают (bid)"))
    if bk["bids"]:
        lines.append(fmt.table([(f"#{o.id}", o.qty_left, f"по {o.price} ₭", "ваша" if o.owner_id == acc else "")
                                for o in bk["bids"]], "lrrl"))
    else:
        lines.append("нет спроса")
    for o in bk["bids"]:
        if o.owner_id != acc:
            rows.append([btn(f"Продать в #{o.id} · {fmt.cr(o.price)}", Do(a="sell", x=o.id))])
    rows.append([btn("＋ Продать", Do(a="ask", z=f"{loc}:{res}")), btn("＋ Купить", Do(a="bid", z=f"{loc}:{res}"))])
    return "\n".join(lines), kb(*rows, back("mkt_loc", arg=loc))


@router.callback_query(Nav.filter(F.s == "book"))
async def cb_book(cq: CallbackQuery, callback_data: Nav):
    loc, res = parts(callback_data.a, 2)
    if loc not in LOCATIONS or res not in RESOURCES:
        return await cq.answer("Устаревшая кнопка.", show_alert=True)
    async with tx() as s:
        user = await current_user(s, cq.from_user)
        acc, _ = await acting(s, user)
        text, markup = await book_screen(s, loc, res, acc)
    await show(cq, text, markup, scene=f"market@{loc}")
    await cq.answer()


@router.callback_query(Do.filter(F.a.in_({"buy", "sell"})))
async def do_buy_sell(cq: CallbackQuery, callback_data: Do, state: FSMContext):
    async with tx() as s:
        o = await s.get(MarketOrder, callback_data.x)
    if o is None or o.status != "open":
        return await cq.answer("Заявка уже неактуальна.", show_alert=True)
    verb = "купить" if callback_data.a == "buy" else "продать"
    await ask(cq, state, f"{callback_data.a}_qty",
              f"Сколько {verb} по заявке #{o.id}? Доступно <b>{o.qty_left}</b> по {fmt.cr(o.price)}.",
              order_id=callback_data.x)


async def _trade_done(message: Message, t, verb: str):
    name = resource_name(t.resource) if t.resource else item_name(t.item_def)
    lines = [fmt.ok(f"Сделка #{t.id}: {verb}"), f"{name} × {t.qty} по {fmt.cr(t.price)}",
             fmt.kv("Сумма", fmt.cr(t.gross)) + " · " + fmt.kv("комиссия (уничтожена)", fmt.cr(t.fee)),
             fmt.kv("Товар на складе", where(t.location_code))]
    markup = kb([btn("↻ К стакану", Nav(s="book", a=f"{t.location_code}:{t.resource}"))] if t.resource else [],
                [btn("⚖ Рынок", Nav(s="market"))], back())
    await show(message, "\n".join(lines), markup, scene="market")


@on_input("buy_qty")
async def in_buy_qty(message: Message, text: str, data: dict):
    q = parse_int(text, 1, 10**6)
    async with tx() as s:
        user = await current_user(s, message.from_user)
        acc, _ = await acting(s, user)
        t = await market.buy(s, user.id, acc, data["order_id"], q, op_key=op_key(message.from_user.id, f"m{message.message_id}"))
    await _trade_done(message, t, "куплено")


@on_input("sell_qty")
async def in_sell_qty(message: Message, text: str, data: dict):
    q = parse_int(text, 1, 10**6)
    async with tx() as s:
        user = await current_user(s, message.from_user)
        acc, _ = await acting(s, user)
        t = await market.sell(s, user.id, acc, data["order_id"], q, op_key=op_key(message.from_user.id, f"m{message.message_id}"))
    await _trade_done(message, t, "продано")


@router.callback_query(Do.filter(F.a.in_({"ask", "bid"})))
async def do_place(cq: CallbackQuery, callback_data: Do, state: FSMContext):
    loc, res = parts(callback_data.z, 2)
    verb = "продать" if callback_data.a == "ask" else "купить"
    extra = "Товар будет заблокирован на складе." if callback_data.a == "ask" else "Сумма будет зарезервирована."
    await ask(cq, state, f"{callback_data.a}_place",
              f"Сколько и почём {verb}: {resource_name(res)} в {LOCATIONS[loc].name}?\n"
              f"Формат: <code>количество цена</code>, например <code>10 35</code>. {extra}", loc=loc, res=res)


def _qty_price(text: str) -> tuple[int, int]:
    parts = text.replace("₭", "").split()
    if len(parts) != 2:
        raise GameError("Нужно два числа: количество и цена за единицу.")
    return parse_int(parts[0], 1, 10**6), parse_int(parts[1], 1, 10**9)


@on_input("ask_place")
async def in_ask_place(message: Message, text: str, data: dict):
    q, p = _qty_price(text)
    async with tx() as s:
        user = await current_user(s, message.from_user)
        acc, _ = await acting(s, user)
        o = await market.place_ask_resource(s, user.id, acc, data["loc"], data["res"], q, p,
                                            op_key=op_key(message.from_user.id, f"m{message.message_id}"))
        text_, markup = await book_screen(s, data["loc"], data["res"], acc)
    await show(message, fmt.ok(f"Заявка на продажу #{o.id} выставлена") + "\n" + text_, markup, scene="market")


@on_input("bid_place")
async def in_bid_place(message: Message, text: str, data: dict):
    q, p = _qty_price(text)
    async with tx() as s:
        user = await current_user(s, message.from_user)
        acc, _ = await acting(s, user)
        o = await market.place_bid(s, user.id, acc, price=p, qty=q, resource=data["res"], location=data["loc"],
                                   op_key=op_key(message.from_user.id, f"m{message.message_id}"))
        text_, markup = await book_screen(s, data["loc"], data["res"], acc)
    await show(message, fmt.ok(f"Заявка на покупку #{o.id}") + f" · зарезервировано {fmt.cr(o.reserved)}\n" + text_,
               markup, scene="market")


# --- Предметы ----------------------------------------------------------------------------------------


ITEM_SCENE = {"engineer_watch": "item_watch", "paint_black_brass": "item_paint", "syndicate_crest": "item_crest"}
KIND_RU = {"equipment": "Оборудование", "module": "Модули грузовика", "vehicle": "Транспорт", "premium": "Премиум"}


@router.callback_query(Nav.filter(F.s == "mkt_items"))
async def cb_mkt_items(cq: CallbackQuery):
    async with tx() as s:
        counts = dict((await s.execute(
            select(MarketOrder.item_def, func.count()).where(MarketOrder.status == "open", MarketOrder.item_def.is_not(None))
            .group_by(MarketOrder.item_def))).all())
    lines = [fmt.head("Техника и предметы", "в скобках — открытые заявки")]
    rows = []
    for kind, title in KIND_RU.items():
        defs = [(c, d) for c, d in ITEMS.items() if d.kind == kind]
        active = ", ".join(f"{d.name} ({counts[c]})" for c, d in defs if counts.get(c))
        lines.append(f"▸ <b>{title}</b>: {active or 'заявок нет'}")
        rows += [btn(f"{d.name} ({counts.get(c, 0)})", Nav(s="ibook", a=c)) for c, d in defs]
    await show(cq, "\n".join(lines), kb(*[rows[i:i + 2] for i in range(0, len(rows), 2)], back("market")),
               scene="market")
    await cq.answer()


@router.callback_query(Nav.filter(F.s == "ibook"))
async def cb_ibook(cq: CallbackQuery, callback_data: Nav):
    code = callback_data.a
    if code not in ITEMS:
        return await cq.answer("Устаревшая кнопка.", show_alert=True)
    async with tx() as s:
        user = await current_user(s, cq.from_user)
        acc, _ = await acting(s, user)
        bk = await market.book(s, item_def=code, limit=8)
        lp = await last_price(s, item_def=code)
        lines = [fmt.head(ITEMS[code].name, e(ITEMS[code].description) or None),
                 fmt.kv("Последняя сделка", fmt.cr(lp[0]) if lp else "не было"), fmt.section("Продают")]
        rows = []
        k = nonce()
        for o in bk["asks"]:
            it = await s.get(Item, o.item_id)
            dur = f" · {it.durability}/{it.max_durability}" if it and it.max_durability else ""
            mine = " · ваша" if o.owner_id == acc else ""
            lines.append(f"▸ #{o.id} {e(items.title(it))}{dur} · {where(o.location_code)} · <b>{fmt.cr(o.price)}</b>{mine}")
            if o.owner_id != acc:
                rows.append([btn(f"Купить #{o.id} · {fmt.cr(o.price)}", Do(a="buyitem", x=o.id, k=k))])
        if not bk["asks"]:
            lines.append("нет предложений")
        lines.append(fmt.section("Покупают"))
        for o in bk["bids"]:
            mine = " · ваша" if o.owner_id == acc else ""
            lines.append(f"▸ #{o.id} {o.qty_left} шт. · {where(o.location_code)} · <b>{fmt.cr(o.price)}</b>{mine}")
            if o.owner_id != acc:
                rows.append([btn(f"Продать в #{o.id} · {fmt.cr(o.price)}", Do(a="fillbid", x=o.id))])
        if not bk["bids"]:
            lines.append("нет спроса")
    if ITEMS[code].kind == KIND_PREMIUM:
        rows.append([btn("＋ Заявка на покупку", Do(a="ibid", z=f"{code}:"))])
    else:
        lines.append("<i>Заявка на покупку физического предмета привязана к локации.</i>")
        rows.append([btn(f"＋ Купить: {loc.name}", Do(a="ibid", z=f"{code}:{lc}")) for lc, loc in LOCATIONS.items()][:2])
        rows.append([btn(f"＋ Купить: {loc.name}", Do(a="ibid", z=f"{code}:{lc}")) for lc, loc in LOCATIONS.items()][2:])
    await show(cq, "\n".join(lines), kb(*rows, back("mkt_items")), scene=ITEM_SCENE.get(code, "market"))
    await cq.answer()


@router.callback_query(Do.filter(F.a == "buyitem"))
async def do_buyitem(cq: CallbackQuery, callback_data: Do):
    async def run():
        async with tx() as s:
            user = await current_user(s, cq.from_user)
            acc, _ = await acting(s, user)
            t = await market.buy(s, user.id, acc, callback_data.x, 1, op_key=op_key(cq.from_user.id, callback_data.k))
        text = "\n".join([fmt.ok(f"Куплено: {item_name(t.item_def)}"), fmt.kv("Цена", fmt.cr(t.gross)),
                          f"Комиссия продавца {fmt.cr(t.fee)} уничтожена.", fmt.kv("Где", where(t.location_code)),
                          "Предмет — в разделе 🛠 Техника."])
        await show(cq, text, kb([btn("🛠 Техника", Nav(s="equipment"))], back("market")),
                   scene=ITEM_SCENE.get(t.item_def, "market"))
    await guarded(cq, run)


@router.callback_query(Do.filter(F.a == "fillbid"))
async def do_fillbid(cq: CallbackQuery, callback_data: Do):
    async def run():
        async with tx() as s:
            user = await current_user(s, cq.from_user)
            acc, _ = await acting(s, user)
            o = await s.get(MarketOrder, callback_data.x)
            if o is None or o.status != "open" or not o.item_def:
                raise GameError("Заявка уже неактуальна.")
            q = select(Item).where(Item.owner_id == acc, Item.def_code == o.item_def, Item.status == ITEM_IDLE)
            if o.location_code:
                q = q.where(Item.location_code == o.location_code)
            mine = (await s.scalars(q.order_by(Item.id).limit(6))).all()
        if not mine:
            raise GameError("У вас нет подходящего свободного предмета в нужной локации.")
        k = nonce()
        rows = [[btn(f"Отдать {items.title(it)}"[:40], Do(a="fillbid_go", x=o.id, y=it.id, k=k))] for it in mine]
        await show(cq, fmt.head("Продажа по заявке", f"#{o.id}: {item_name(o.item_def)} за {fmt.cr(o.price)}")
                   + "\nКакой экземпляр отдать?",
                   kb(*rows, back("ibook", arg=o.item_def)))
    await guarded(cq, run)


@router.callback_query(Do.filter(F.a == "fillbid_go"))
async def do_fillbid_go(cq: CallbackQuery, callback_data: Do):
    async def run():
        async with tx() as s:
            user = await current_user(s, cq.from_user)
            acc, _ = await acting(s, user)
            t = await market.sell(s, user.id, acc, callback_data.x, 1, item_id=callback_data.y,
                                  op_key=op_key(cq.from_user.id, callback_data.k))
        await show(cq, fmt.ok(f"Продано: {item_name(t.item_def)}") + f"\nЦена {fmt.cr(t.gross)}, вам {fmt.cr(t.gross - t.fee)}.",
                   kb(back("market")), scene="market")
    await guarded(cq, run)


@router.callback_query(Do.filter(F.a == "ibid"))
async def do_ibid(cq: CallbackQuery, callback_data: Do, state: FSMContext):
    code, loc = parts(callback_data.z, 2)
    await ask(cq, state, "ibid_price", f"Цена покупки «{item_name(code)}» в кронах?", code=code, loc=loc or None)


@on_input("ibid_price")
async def in_ibid_price(message: Message, text: str, data: dict):
    p = parse_int(text)
    async with tx() as s:
        user = await current_user(s, message.from_user)
        acc, _ = await acting(s, user)
        o = await market.place_bid(s, user.id, acc, price=p, qty=1, item_def=data["code"], location=data["loc"],
                                   op_key=op_key(message.from_user.id, f"m{message.message_id}"))
    await show(message, fmt.ok(f"Заявка на покупку #{o.id}") + f"\n{item_name(data['code'])} за {fmt.cr(p)}, сумма зарезервирована.",
               kb([btn("Мои заявки", Nav(s="my_orders"))], back("market")), scene="market")


# --- Мои заявки --------------------------------------------------------------------------------------


async def my_orders_screen(s, acc: int, label: str):
    orders = await market.orders_of(s, acc)
    lines = [fmt.head("Мои заявки", label)]
    rows = []
    k = nonce()
    for o in orders:
        name = resource_name(o.resource) if o.resource else item_name(o.item_def)
        side = "▲ продажа" if o.side == "ask" else "▼ покупка"
        lines.append(f"{side} <b>#{o.id}</b> {name} {o.qty_left}/{o.qty_total} по {fmt.cr(o.price)} · {where(o.location_code)}")
        rows.append(btn(f"✕ Снять #{o.id}", Do(a="ocancel", x=o.id, k=k)))
    if not orders:
        lines.append("Открытых заявок нет.")
    else:
        lines.append("<i>Снятие возвращает товар на склад и кроны из резерва.</i>")
    return "\n".join(lines), kb(*[rows[i:i + 2] for i in range(0, len(rows), 2)], back("market"))


@router.callback_query(Nav.filter(F.s == "my_orders"))
async def cb_my_orders(cq: CallbackQuery):
    async with tx() as s:
        user = await current_user(s, cq.from_user)
        text, markup = await my_orders_screen(s, *(await acting(s, user)))
    await show(cq, text, markup, scene="market")
    await cq.answer()


@router.callback_query(Do.filter(F.a == "ocancel"))
async def do_ocancel(cq: CallbackQuery, callback_data: Do):
    async def run():
        async with tx() as s:
            user = await current_user(s, cq.from_user)
            await market.cancel(s, user.id, callback_data.x, op_key=op_key(cq.from_user.id, callback_data.k))
            text, markup = await my_orders_screen(s, *(await acting(s, user)))
        await show(cq, fmt.ok(f"Заявка #{callback_data.x} снята") + "\n" + text, markup, scene="market")
    await guarded(cq, run)
