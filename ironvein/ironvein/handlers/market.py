"""Рынок: стакан по ресурсам и локациям, предметы, мои заявки."""

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import func, select

from ironvein.domain.catalog import ITEMS, KIND_PREMIUM, LOCATIONS, RESOURCES, item_name, resource_name
from ironvein.domain.errors import GameError
from ironvein.domain.money import fmt_cr
from ironvein.handlers.base import ask, on_input, parse_int
from ironvein.handlers.ui import Do, Nav, acting, back, btn, current_user, e, guarded, kb, nonce, op_key, show, tx
from ironvein.models import ITEM_IDLE, Item, MarketOrder
from ironvein.services import items, market
from ironvein.services.metrics import last_price

router = Router(name="market")


def where(loc: str | None) -> str:
    return LOCATIONS[loc].name if loc else "без локации"


async def market_root(event):
    rows = [[btn(f"Биржа: {loc.name}", Nav(s="mkt_loc", a=code))] for code, loc in LOCATIONS.items()]
    rows.append([btn("Техника и премиум-предметы", Nav(s="mkt_items"))])
    rows.append([btn("Мои заявки", Nav(s="my_orders"))])
    await show(event, "<b>Рынок</b>\nЦены — только заявки и сделки игроков. Товар лежит в локации заявки.\n"
                      "Комиссия 2% с продавца уничтожается.", kb(*rows, back()), scene="market")


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
    lines = [f"<b>Биржа · {LOCATIONS[loc].name}</b>", "<code>товар       ask    bid   сделка</code>"]
    rows = []
    async with tx() as s:
        for code, r in RESOURCES.items():
            bk = await market.book(s, resource=code, location=loc, limit=1)
            a = bk["asks"][0].price if bk["asks"] else "—"
            b = bk["bids"][0].price if bk["bids"] else "—"
            last = bk["last"].price if bk["last"] else "—"
            lines.append(f"<code>{r.name[:10]:<10} {a!s:>5} {b!s:>6} {last!s:>7}</code>")
            rows.append(btn(r.name, Nav(s="book", a=f"{loc}:{code}")))
    lines.append("«—» значит, что заявок или сделок не было: выдуманных цен здесь нет.")
    await show(cq, "\n".join(lines), kb(*[rows[i:i + 3] for i in range(0, len(rows), 3)], back("market")))
    await cq.answer()


async def book_screen(s, loc: str, res: str):
    bk = await market.book(s, resource=res, location=loc, limit=5)
    lines = [f"<b>{resource_name(res)} · {LOCATIONS[loc].name}</b>"]
    lines.append(f"Последняя сделка: {fmt_cr(bk['last'].price) + ' × ' + str(bk['last'].qty) if bk['last'] else 'не было'}"
                 f" · объём 24 ч: {bk['volume_qty']} ед. на {fmt_cr(bk['volume_gross'])}")
    rows = []
    lines.append("<b>Продают (ask)</b>")
    for o in bk["asks"]:
        lines.append(f"  #{o.id}: {o.qty_left} по {fmt_cr(o.price)}")
        rows.append([btn(f"Купить из #{o.id} ({fmt_cr(o.price)})", Do(a="buy", x=o.id))])
    if not bk["asks"]:
        lines.append("  нет")
    lines.append("<b>Покупают (bid)</b>")
    for o in bk["bids"]:
        lines.append(f"  #{o.id}: {o.qty_left} по {fmt_cr(o.price)}")
        rows.append([btn(f"Продать в #{o.id} ({fmt_cr(o.price)})", Do(a="sell", x=o.id))])
    if not bk["bids"]:
        lines.append("  нет")
    rows.append([btn("Выставить продажу", Do(a="ask", z=f"{loc}:{res}")),
                 btn("Выставить покупку", Do(a="bid", z=f"{loc}:{res}"))])
    return "\n".join(lines), kb(*rows, back("mkt_loc", arg=loc))


@router.callback_query(Nav.filter(F.s == "book"))
async def cb_book(cq: CallbackQuery, callback_data: Nav):
    loc, res = callback_data.a.split(":")
    if loc not in LOCATIONS or res not in RESOURCES:
        return await cq.answer("Устаревшая кнопка.", show_alert=True)
    async with tx() as s:
        text, markup = await book_screen(s, loc, res)
    await show(cq, text, markup, scene="market")
    await cq.answer()


@router.callback_query(Do.filter(F.a.in_({"buy", "sell"})))
async def do_buy_sell(cq: CallbackQuery, callback_data: Do, state: FSMContext):
    verb = "купить" if callback_data.a == "buy" else "продать"
    await ask(cq, state, f"{callback_data.a}_qty", f"Сколько {verb} по заявке #{callback_data.x}?", order_id=callback_data.x)


async def _trade_done(message: Message, t, verb: str):
    name = resource_name(t.resource) if t.resource else item_name(t.item_def)
    await show(message, f"<b>Сделка #{t.id}</b>: {verb} {name} × {t.qty} по {fmt_cr(t.price)}\n"
                        f"Сумма {fmt_cr(t.gross)}, комиссия {fmt_cr(t.fee)} уничтожена.\n"
                        f"Товар на складе: {where(t.location_code)}.",
               kb([btn("Рынок", Nav(s="market"))], back()), scene="market")


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
    loc, res = callback_data.z.split(":")
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
        text_, markup = await book_screen(s, data["loc"], data["res"])
    await show(message, f"Заявка на продажу #{o.id} выставлена.\n\n{text_}", markup, scene="market")


@on_input("bid_place")
async def in_bid_place(message: Message, text: str, data: dict):
    q, p = _qty_price(text)
    async with tx() as s:
        user = await current_user(s, message.from_user)
        acc, _ = await acting(s, user)
        o = await market.place_bid(s, user.id, acc, price=p, qty=q, resource=data["res"], location=data["loc"],
                                   op_key=op_key(message.from_user.id, f"m{message.message_id}"))
        text_, markup = await book_screen(s, data["loc"], data["res"])
    await show(message, f"Заявка на покупку #{o.id}: зарезервировано {fmt_cr(o.reserved)}.\n\n{text_}", markup,
               scene="market")


# --- Предметы ----------------------------------------------------------------------------------------


@router.callback_query(Nav.filter(F.s == "mkt_items"))
async def cb_mkt_items(cq: CallbackQuery):
    async with tx() as s:
        counts = dict((await s.execute(
            select(MarketOrder.item_def, func.count()).where(MarketOrder.status == "open", MarketOrder.item_def.is_not(None))
            .group_by(MarketOrder.item_def))).all())
    rows = []
    for code, d in ITEMS.items():
        n = counts.get(code, 0)
        rows.append(btn(f"{d.name} ({n})", Nav(s="ibook", a=code)))
    await show(cq, "<b>Техника и предметы</b>\nВ скобках — число открытых заявок.",
               kb(*[rows[i:i + 2] for i in range(0, len(rows), 2)], back("market")))
    await cq.answer()


@router.callback_query(Nav.filter(F.s == "ibook"))
async def cb_ibook(cq: CallbackQuery, callback_data: Nav):
    code = callback_data.a
    if code not in ITEMS:
        return await cq.answer("Устаревшая кнопка.", show_alert=True)
    async with tx() as s:
        bk = await market.book(s, item_def=code, limit=8)
        lp = await last_price(s, item_def=code)
        lines = [f"<b>{ITEMS[code].name}</b>",
                 f"Последняя сделка: {fmt_cr(lp[0]) if lp else 'не было'}", "<b>Продают</b>"]
        rows = []
        k = nonce()
        for o in bk["asks"]:
            it = await s.get(Item, o.item_id)
            dur = f", {it.durability}/{it.max_durability}" if it and it.max_durability else ""
            lines.append(f"  #{o.id}: {e(items.title(it))}{dur} · {where(o.location_code)} · {fmt_cr(o.price)}")
            rows.append([btn(f"Купить #{o.id} за {fmt_cr(o.price)}", Do(a="buyitem", x=o.id, k=k))])
        if not bk["asks"]:
            lines.append("  нет")
        lines.append("<b>Покупают</b>")
        for o in bk["bids"]:
            lines.append(f"  #{o.id}: {o.qty_left} шт. по {fmt_cr(o.price)} · {where(o.location_code)}")
            rows.append([btn(f"Продать в #{o.id}", Do(a="fillbid", x=o.id))])
        if not bk["bids"]:
            lines.append("  нет")
    if ITEMS[code].kind == KIND_PREMIUM:
        rows.append([btn("Заявка на покупку", Do(a="ibid", z=f"{code}:"))])
    else:
        rows.append([btn(f"Купить в: {loc.name}", Do(a="ibid", z=f"{code}:{lc}")) for lc, loc in LOCATIONS.items()])
    scene = {"engineer_watch": "item_watch", "paint_black_brass": "item_paint", "syndicate_crest": "item_crest"}.get(code, "market")
    await show(cq, "\n".join(lines), kb(*rows, back("mkt_items")), scene=scene)
    await cq.answer()


@router.callback_query(Do.filter(F.a == "buyitem"))
async def do_buyitem(cq: CallbackQuery, callback_data: Do):
    async def run():
        async with tx() as s:
            user = await current_user(s, cq.from_user)
            acc, _ = await acting(s, user)
            t = await market.buy(s, user.id, acc, callback_data.x, 1, op_key=op_key(cq.from_user.id, callback_data.k))
        scene = {"engineer_watch": "item_watch", "paint_black_brass": "item_paint",
                 "syndicate_crest": "item_crest"}.get(t.item_def, "market")
        await show(cq, f"<b>Куплено</b>: {item_name(t.item_def)} за {fmt_cr(t.gross)}.\nКомиссия продавца "
                       f"{fmt_cr(t.fee)} уничтожена. Предмет в разделе «Техника».",
                   kb([btn("Техника", Nav(s="equipment"))], back("market")), scene=scene)
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
        await show(cq, f"Заявка #{o.id}: {item_name(o.item_def)} за {fmt_cr(o.price)}. Какой экземпляр продать?",
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
        await show(cq, f"<b>Продано</b>: {item_name(t.item_def)} за {fmt_cr(t.gross)}, вам {fmt_cr(t.gross - t.fee)}.",
                   kb(back("market")), scene="market")
    await guarded(cq, run)


@router.callback_query(Do.filter(F.a == "ibid"))
async def do_ibid(cq: CallbackQuery, callback_data: Do, state: FSMContext):
    code, loc = callback_data.z.split(":")
    await ask(cq, state, "ibid_price", f"Цена покупки «{item_name(code)}» в кронах?", code=code, loc=loc or None)


@on_input("ibid_price")
async def in_ibid_price(message: Message, text: str, data: dict):
    p = parse_int(text)
    async with tx() as s:
        user = await current_user(s, message.from_user)
        acc, _ = await acting(s, user)
        o = await market.place_bid(s, user.id, acc, price=p, qty=1, item_def=data["code"], location=data["loc"],
                                   op_key=op_key(message.from_user.id, f"m{message.message_id}"))
    await show(message, f"Заявка на покупку #{o.id}: {item_name(data['code'])} за {fmt_cr(p)}, сумма зарезервирована.",
               kb([btn("Мои заявки", Nav(s="my_orders"))], back("market")), scene="market")


# --- Мои заявки --------------------------------------------------------------------------------------


@router.callback_query(Nav.filter(F.s == "my_orders"))
async def cb_my_orders(cq: CallbackQuery):
    async with tx() as s:
        user = await current_user(s, cq.from_user)
        acc, label = await acting(s, user)
        orders = await market.orders_of(s, acc)
    lines = [f"<b>Мои заявки</b> · {label}"]
    rows = []
    k = nonce()
    for o in orders:
        name = resource_name(o.resource) if o.resource else item_name(o.item_def)
        side = "продажа" if o.side == "ask" else "покупка"
        lines.append(f"▸ #{o.id} {side}: {name} {o.qty_left}/{o.qty_total} по {fmt_cr(o.price)} · {where(o.location_code)}")
        rows.append([btn(f"Снять #{o.id}", Do(a="ocancel", x=o.id, k=k))])
    if not orders:
        lines.append("Открытых заявок нет.")
    await show(cq, "\n".join(lines), kb(*rows, back("market")))
    await cq.answer()


@router.callback_query(Do.filter(F.a == "ocancel"))
async def do_ocancel(cq: CallbackQuery, callback_data: Do):
    async def run():
        async with tx() as s:
            user = await current_user(s, cq.from_user)
            await market.cancel(s, user.id, callback_data.x, op_key=op_key(cq.from_user.id, callback_data.k))
        await show(cq, f"Заявка #{callback_data.x} снята, резерв возвращён.", kb([btn("Мои заявки", Nav(s="my_orders"))], back("market")))
    await guarded(cq, run)
