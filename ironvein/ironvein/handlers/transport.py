"""Перевозки: грузовики и пеший перенос."""

import math

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select

from ironvein.domain.catalog import (
    FOOT_CAPACITY,
    FOOT_SPEED_KMH,
    ITEMS,
    LOCATIONS,
    resource_name,
    route_km,
)
from ironvein.domain.errors import GameError
from ironvein.domain.vehicles import trip_fuel, trip_minutes
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
    num,
    op_key,
    parts,
    show,
    tx,
)
from ironvein.models import ITEM_IDLE, Item, Shipment, Stock
from ironvein.services import cosmetics, items, transport

router = Router(name="transport")
STATUS = {"loading": "погрузка", "in_transit": "в пути", "delivered": "доставлен", "cancelled": "отменён"}


def ship_scene(cargo_res: list[str], armored: bool = False, painted: bool = False, foot: bool = False) -> str:
    if foot:
        return "foot"
    if painted:
        return "truck_brass"
    if armored:
        return "truck_armored"
    if "oil" in cargo_res or "diesel" in cargo_res:
        return "truck_oil"
    if "ore" in cargo_res or "coal" in cargo_res:
        return "truck_ore"
    return "truck"


async def transport_screen(s, acc: int, label: str):
    trucks = await transport.vehicles_of(s, acc)
    ships = await transport.shipments_of(s, acc)
    lines = [fmt.head("Перевозки", label), fmt.section(f"Гараж · {len(trucks)}")]
    rows = []
    for t in trucks:
        where = f"{LOCATIONS[t.location_code].name} · {items.STATUS_RU[t.status]}" if t.location_code else "в пути"
        st = await transport.vehicle_stats(s, t.id)
        lines.append(f"🚚 <b>#{t.id}</b> {where} · "
                     f"<code>{fmt.gauge(t.durability, t.max_durability, 5)}</code>\n"
                     f"    груз {st.payload} · {st.speed_kmh} км/ч · запас хода {st.range_km} км")
        rows.append(btn(f"🚚 #{t.id}", Nav(s="item", a=str(t.id))))
    if not trucks:
        lines.append("Машин нет. Грузовик собирается в мастерской из шасси, двигателя, бака и кузова.")
    lines.append(fmt.section("Рейсы"))
    trip_rows = []
    for sh in ships:
        route = f"{LOCATIONS[sh.origin].name} → {LOCATIONS[sh.dest].name}"
        icon = "🚶" if sh.mode == "foot" else "🚚"
        lines.append(f"{icon} <b>#{sh.id}</b> {route} · {STATUS[sh.status]}")
        if sh.status == "in_transit":
            lines.append(f"    <code>{fmt.progress(sh.departed_at, sh.eta)}</code> прибытие через {fmt.left(sh.eta)}")
        if sh.status == "loading" and sh.carrier_id == acc:
            trip_rows.append([btn(f"📦 Рейс #{sh.id}: погрузка", Nav(s="trip", a=str(sh.id)))])
    if not ships:
        lines.append("Активных рейсов нет.")
    return "\n".join(lines), kb([btn("＋ Новый рейс", Nav(s="trip_new"))], *trip_rows,
                                *[rows[i:i + 3] for i in range(0, len(rows), 3)], back())


@router.message(Command("transport"))
async def cmd_transport(message: Message):
    async with tx() as s:
        user = await current_user(s, message.from_user)
        text, markup = await transport_screen(s, *(await acting(s, user)))
    await show(message, text, markup, scene="truck")


@router.callback_query(Nav.filter(F.s == "transport"))
async def cb_transport(cq: CallbackQuery):
    async with tx() as s:
        user = await current_user(s, cq.from_user)
        text, markup = await transport_screen(s, *(await acting(s, user)))
    await show(cq, text, markup, scene="truck")
    await cq.answer()


@router.callback_query(Nav.filter(F.s == "trip_new"))
async def cb_trip_new(cq: CallbackQuery):
    async with tx() as s:
        user = await current_user(s, cq.from_user)
        acc, _ = await acting(s, user)
        trucks = [t for t in await transport.vehicles_of(s, acc) if t.status == ITEM_IDLE]
    rows = [[btn(f"🚚 Грузовик #{t.id} · {LOCATIONS[t.location_code].name}",
                 Nav(s="trip_dest", a=f"{t.id}:{t.location_code}"))] for t in trucks]
    rows.append([btn(f"🚶 Пешком · до {FOOT_CAPACITY} ед., {FOOT_SPEED_KMH} км/ч", Nav(s="trip_foot"))])
    text = "\n".join([fmt.head("Новый рейс", "чем везём?"),
                      "Грузовику нужен дизель на складе в пункте отправления; на обратный путь — в пункте назначения.",
                      "Пешком — без топлива, медленно, только лёгкий груз и ручной инструмент."])
    await show(cq, text, kb(*rows, back("transport")), scene="train")
    await cq.answer()


@router.callback_query(Nav.filter(F.s == "trip_foot"))
async def cb_trip_foot(cq: CallbackQuery):
    rows = [[btn(f"Из: {loc.name}", Nav(s="trip_dest", a=f"0:{code}"))] for code, loc in LOCATIONS.items()]
    await show(cq, fmt.head("Пеший переход", "откуда несём?"), kb(*rows, back("trip_new")), scene="foot")
    await cq.answer()


@router.callback_query(Nav.filter(F.s == "trip_dest"))
async def cb_trip_dest(cq: CallbackQuery, callback_data: Nav):
    vid, origin = parts(callback_data.a, 2)
    if origin not in LOCATIONS or not vid.isdigit():
        return await cq.answer("Устаревшая кнопка.", show_alert=True)
    st = None
    diesel = 0
    if vid != "0":
        async with tx() as s:
            user = await current_user(s, cq.from_user)
            acc, _ = await acting(s, user)
            try:
                st = await transport.vehicle_stats(s, int(vid))
            except ValueError:
                return await cq.answer("Устаревшая кнопка.", show_alert=True)
            row = await s.get(Stock, (acc, origin, "diesel"))
            diesel = row.free if row else 0
    k = nonce()
    rows = []
    lines = [fmt.head("Маршрут", f"отправление: {LOCATIONS[origin].name}")]
    for code, loc in LOCATIONS.items():
        km = route_km(origin, code)
        if code == origin or not km:
            continue
        if st is None:
            mins = math.ceil(km * 60 / FOOT_SPEED_KMH)
            lines.append(f"▸ {loc.name}: {km} км · {fmt.dur_game(mins)}")
        else:
            fuel = trip_fuel(st, km)
            ok_ = "" if fuel <= min(st.tank, diesel) else " ⚠"
            lines.append(f"▸ {loc.name}: {km} км · {fmt.dur_game(trip_minutes(st.speed_kmh, km))} · "
                         f"дизель {fuel}{ok_}")
        rows.append([btn(f"→ {loc.name}", Do(a="trip_plan", x=int(vid), z=f"{origin}:{code}", k=k))])
    if st is not None:
        lines.append(f"Дизель на складе: <b>{diesel}</b> · бак {st.tank}. «⚠» — топлива не хватит.")
    await show(cq, "\n".join(lines), kb(*rows, back("trip_new")),
               scene=("foot" if vid == "0" else "truck") + f"@{origin}")
    await cq.answer()


@router.callback_query(Do.filter(F.a == "trip_plan"))
async def do_trip_plan(cq: CallbackQuery, callback_data: Do):
    origin, dest = parts(callback_data.z, 2)

    async def run():
        async with tx() as s:
            user = await current_user(s, cq.from_user)
            acc, _ = await acting(s, user)
            sh = await transport.plan(s, user.id, acc, origin=origin, dest=dest, vehicle_id=callback_data.x or None,
                                      allow_empty=True, op_key=op_key(cq.from_user.id, callback_data.k))
            text, markup, scene = await trip_card(s, acc, sh.id)
        await show(cq, text, markup, scene=scene)
    await guarded(cq, run)


async def trip_card(s, acc: int, shipment_id: int):
    sh = await s.get(Shipment, shipment_id)
    if sh is None:
        raise GameError("Рейс не найден.")
    cargo = await transport.cargo_of(s, sh.id)
    parties = {sh.carrier_id} | {c.owner_id for c in cargo} | {c.recipient_id for c in cargo}
    if acc not in parties:
        raise GameError("Рейс не найден.")  # чужой рейс не раскрываем
    cap = await transport.capacity_of(s, sh)
    weight = await transport.load_weight(s, sh.id)
    lines = [fmt.head(f"Рейс #{sh.id}", STATUS[sh.status]),
             f"{LOCATIONS[sh.origin].name} → <b>{LOCATIONS[sh.dest].name}</b> · {sh.distance_km} км",
             f"Загрузка: <code>{fmt.gauge(weight, cap)}</code> {weight}/{cap}"]
    armored = painted = False
    if sh.mode == "truck":
        st = await transport.vehicle_stats(s, sh.vehicle_id)
        lines.append(fmt.kv("Топливо", f"{sh.fuel} диз.") + " · " + fmt.kv("износ", sh.wear) + " · "
                     + fmt.kv("в пути", fmt.dur_game(trip_minutes(st.speed_kmh, sh.distance_km))))
        armored = any(m.def_code == "body_armored" for m in await transport.modules_of(s, sh.vehicle_id))
        painted = await cosmetics.current_paint(s, sh.vehicle_id) is not None
    else:
        lines.append(fmt.kv("Пешком", fmt.dur_game(await transport.trip_duration_minutes(s, sh))) + " · без топлива")
    names = []
    for c in cargo:
        if c.resource:
            names.append(f"{resource_name(c.resource)} {c.qty}")
        else:
            it = await s.get(Item, c.item_id)
            names.append(items.title(it))
    lines.append(fmt.kv("Груз", e(", ".join(names)) or "пусто"))
    if sh.status == "in_transit":
        lines.append(f"<code>{fmt.progress(sh.departed_at, sh.eta)}</code> прибытие через {fmt.left(sh.eta)}")
    rows = []
    if sh.status == "loading" and sh.carrier_id == acc:
        free_cap = cap - weight
        stocks = (await s.scalars(select(Stock).where(Stock.owner_id == acc, Stock.location_code == sh.origin,
                                                      Stock.free > 0).order_by(Stock.resource))).all()
        k = nonce()
        for st_ in stocks:
            spare = st_.free - (sh.fuel if st_.resource == "diesel" else 0)
            if spare <= 0 or free_cap <= 0:
                continue
            rows.append([btn(f"+ {resource_name(st_.resource)} (есть {spare})", Do(a="trip_add", x=sh.id, z=st_.resource)),
                         btn(f"+ {min(spare, free_cap)} max", Do(a="trip_max", x=sh.id, z=st_.resource, k=k))])
        portable = (await s.scalars(select(Item).where(Item.owner_id == acc, Item.location_code == sh.origin,
                                                       Item.status == ITEM_IDLE, Item.def_code != "truck")
                                    .order_by(Item.id).limit(6))).all()
        for it in portable:
            if (sh.mode == "foot" and not ITEMS[it.def_code].portable) or transport.item_weight(it.def_code) > free_cap:
                continue
            rows.append([btn(f"+ {items.button_title(it, 36)}", Do(a="trip_item", x=sh.id, y=it.id, k=k))])
        rows.append([btn("▶ Отправить", Do(a="trip_go", x=sh.id, k=k)), btn("✕ Отменить", Do(a="trip_cancel", x=sh.id, k=k))])
        lines.append("<i>Всё зарезервировано. До отправления рейс можно отменить, в пути — нет.</i>")
    scene = ship_scene([c.resource for c in cargo if c.resource], armored, painted, sh.mode == "foot")
    scene += f"@{sh.dest if sh.status in ('in_transit', 'delivered') else sh.origin}"
    return "\n".join(lines), kb(*rows, back("transport")), scene


@router.callback_query(Nav.filter(F.s == "trip"))
async def cb_trip(cq: CallbackQuery, callback_data: Nav):
    async def run():
        async with tx() as s:
            user = await current_user(s, cq.from_user)
            acc, _ = await acting(s, user)
            text, markup, scene = await trip_card(s, acc, num(callback_data.a))
        await show(cq, text, markup, scene=scene)
    await guarded(cq, run)


@router.callback_query(Do.filter(F.a == "trip_add"))
async def do_trip_add(cq: CallbackQuery, callback_data: Do, state: FSMContext):
    await ask(cq, state, "trip_qty", f"Сколько погрузить: {resource_name(callback_data.z)}?",
              shipment_id=callback_data.x, resource=callback_data.z)


@on_input("trip_qty")
async def in_trip_qty(message: Message, text: str, data: dict):
    q = parse_int(text, 1, 100000)
    async with tx() as s:
        user = await current_user(s, message.from_user)
        acc, _ = await acting(s, user)
        await transport.add_cargo(s, user.id, data["shipment_id"], resource=data["resource"], qty=q,
                                  op_key=op_key(message.from_user.id, f"m{message.message_id}"))
        text_, markup, scene = await trip_card(s, acc, data["shipment_id"])
    await show(message, text_, markup, scene=scene)


@router.callback_query(Do.filter(F.a == "trip_max"))
async def do_trip_max(cq: CallbackQuery, callback_data: Do):
    async def run():
        async with tx() as s:
            user = await current_user(s, cq.from_user)
            acc, _ = await acting(s, user)
            sh = await s.get(Shipment, callback_data.x)
            if sh is None:
                raise GameError("Рейс не найден.")
            row = await s.get(Stock, (acc, sh.origin, callback_data.z))
            spare = (row.free if row else 0) - (sh.fuel if callback_data.z == "diesel" else 0)
            q = min(spare, await transport.capacity_of(s, sh) - await transport.load_weight(s, sh.id))
            if q <= 0:
                raise GameError("Грузить нечего или места нет.")
            await transport.add_cargo(s, user.id, sh.id, resource=callback_data.z, qty=q,
                                      op_key=op_key(cq.from_user.id, f"{callback_data.k}:{callback_data.z}"))
            text, markup, scene = await trip_card(s, acc, sh.id)
        await show(cq, text, markup, scene=scene)
    await guarded(cq, run)


@router.callback_query(Do.filter(F.a == "trip_item"))
async def do_trip_item(cq: CallbackQuery, callback_data: Do):
    async def run():
        async with tx() as s:
            user = await current_user(s, cq.from_user)
            acc, _ = await acting(s, user)
            await transport.add_cargo(s, user.id, callback_data.x, item_id=callback_data.y,
                                      op_key=op_key(cq.from_user.id, f"{callback_data.k}:{callback_data.y}"))
            text, markup, scene = await trip_card(s, acc, callback_data.x)
        await show(cq, text, markup, scene=scene)
    await guarded(cq, run)


@router.callback_query(Do.filter(F.a == "trip_go"))
async def do_trip_go(cq: CallbackQuery, callback_data: Do):
    async def run():
        async with tx() as s:
            user = await current_user(s, cq.from_user)
            acc, _ = await acting(s, user)
            sh = await transport.depart(s, user.id, callback_data.x, op_key=op_key(cq.from_user.id, callback_data.k))
            text, _, scene = await trip_card(s, acc, sh.id)
        await show(cq, fmt.ok("Отправлен") + f" · прибытие через {fmt.left(sh.eta)}\n{text}\n<i>Развернуть в пути нельзя.</i>",
                   kb([btn("🚚 Перевозки", Nav(s="transport"))], back()), scene=scene)
    await guarded(cq, run)


@router.callback_query(Do.filter(F.a == "trip_cancel"))
async def do_trip_cancel(cq: CallbackQuery, callback_data: Do):
    async def run():
        async with tx() as s:
            user = await current_user(s, cq.from_user)
            await transport.cancel(s, user.id, callback_data.x, op_key=op_key(cq.from_user.id, callback_data.k))
            text, markup = await transport_screen(s, *(await acting(s, user)))
        await show(cq, fmt.ok("Рейс отменён") + " — груз и топливо освобождены.\n" + text, markup, scene="truck")
    await guarded(cq, run)


__all__ = ["router", "ship_scene", "e"]
