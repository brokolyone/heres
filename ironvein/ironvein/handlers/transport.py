"""Перевозки: грузовики и пеший перенос."""

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select

from ironvein.domain.catalog import FOOT_CAPACITY, ITEMS, LOCATIONS, resource_name, route_km
from ironvein.domain.vehicles import trip_minutes
from ironvein.handlers.base import ask, on_input, parse_int
from ironvein.handlers.production import eta_text
from ironvein.handlers.ui import Do, Nav, acting, back, btn, current_user, e, guarded, kb, nonce, op_key, show, tx
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
    lines = [f"<b>Перевозки</b> · {label}", "<b>Гараж</b>"]
    rows = []
    for t in trucks:
        where = LOCATIONS[t.location_code].name if t.location_code else "в пути"
        st = await transport.vehicle_stats(s, t.id)
        lines.append(f"▸ Грузовик #{t.id} · {where} · {items.STATUS_RU[t.status]} · {t.durability}/{t.max_durability} · "
                     f"груз {st.payload}, {st.speed_kmh} км/ч")
    if not trucks:
        lines.append("Машин нет. Грузовик собирается в мастерской из шасси, двигателя, бака и кузова.")
    lines.append("<b>Рейсы</b>")
    for sh in ships:
        route = f"{LOCATIONS[sh.origin].name} → {LOCATIONS[sh.dest].name}"
        when = f", прибытие через {eta_text(sh.eta)}" if sh.status == "in_transit" else ""
        lines.append(f"▸ #{sh.id} {'пешком' if sh.mode == 'foot' else 'грузовик'} {route}: {STATUS[sh.status]}{when}")
        if sh.status == "loading" and sh.carrier_id == acc:
            rows.append([btn(f"Рейс #{sh.id}: погрузка", Nav(s="trip", a=str(sh.id)))])
    if not ships:
        lines.append("Активных рейсов нет.")
    return "\n".join(lines), kb([btn("Новый рейс", Nav(s="trip_new"))], *rows, back())


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
    rows = [[btn(f"Грузовик #{t.id} · {LOCATIONS[t.location_code].name}", Nav(s="trip_dest", a=f"{t.id}:{t.location_code}"))]
            for t in trucks]
    rows.append([btn(f"Пешком (до {FOOT_CAPACITY} ед., 5 км/ч)", Nav(s="trip_foot"))])
    await show(cq, "<b>Новый рейс</b>\nЧем везём?", kb(*rows, back("transport")), scene="train")
    await cq.answer()


@router.callback_query(Nav.filter(F.s == "trip_foot"))
async def cb_trip_foot(cq: CallbackQuery):
    rows = [[btn(f"Из: {loc.name}", Nav(s="trip_dest", a=f"0:{code}"))] for code, loc in LOCATIONS.items()]
    await show(cq, "<b>Пеший переход</b>\nОткуда несём?", kb(*rows, back("trip_new")), scene="foot")
    await cq.answer()


@router.callback_query(Nav.filter(F.s == "trip_dest"))
async def cb_trip_dest(cq: CallbackQuery, callback_data: Nav):
    vid, origin = callback_data.a.split(":")
    k = nonce()
    rows = []
    for code, loc in LOCATIONS.items():
        km = route_km(origin, code)
        if code != origin and km:
            rows.append([btn(f"→ {loc.name} ({km} км)", Do(a="trip_plan", x=int(vid), z=f"{origin}:{code}", k=k))])
    await show(cq, f"<b>Маршрут</b>\nОтправление: {LOCATIONS[origin].name}. Куда?", kb(*rows, back("trip_new")),
               scene="foot" if vid == "0" else "truck")
    await cq.answer()


@router.callback_query(Do.filter(F.a == "trip_plan"))
async def do_trip_plan(cq: CallbackQuery, callback_data: Do):
    origin, dest = callback_data.z.split(":")

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
    cargo = await transport.cargo_of(s, sh.id)
    cap = await transport.capacity_of(s, sh)
    weight = await transport.load_weight(s, sh.id)
    lines = [f"<b>Рейс #{sh.id}</b> · {STATUS[sh.status]}",
             f"{LOCATIONS[sh.origin].name} → {LOCATIONS[sh.dest].name}, {sh.distance_km} км",
             f"Загрузка: {weight}/{cap}"]
    armored = painted = False
    if sh.mode == "truck":
        st = await transport.vehicle_stats(s, sh.vehicle_id)
        mins = trip_minutes(st.speed_kmh, sh.distance_km)
        lines.append(f"Топливо: {sh.fuel} дизеля (зарезервировано) · износ {sh.wear} · в пути ≈{mins} мин игрового времени")
        armored = any(m.def_code == "body_armored" for m in await transport.modules_of(s, sh.vehicle_id))
        painted = await cosmetics.current_paint(s, sh.vehicle_id) is not None
    else:
        lines.append(f"Пешком: ≈{await transport.trip_duration_minutes(s, sh)} мин игрового времени, без топлива")
    lines.append("Груз: " + (", ".join(
        f"{resource_name(c.resource)} {c.qty}" if c.resource else f"предмет #{c.item_id}" for c in cargo) or "пусто"))
    rows = []
    if sh.status == "loading" and sh.carrier_id == acc:
        stocks = (await s.scalars(select(Stock).where(Stock.owner_id == acc, Stock.location_code == sh.origin,
                                                      Stock.free > 0).order_by(Stock.resource))).all()
        rb = [btn(f"+ {resource_name(st.resource)} ({st.free})", Do(a="trip_add", x=sh.id, z=st.resource)) for st in stocks]
        rows += [rb[i:i + 2] for i in range(0, len(rb), 2)]
        portable = (await s.scalars(select(Item).where(Item.owner_id == acc, Item.location_code == sh.origin,
                                                       Item.status == ITEM_IDLE, Item.def_code != "truck")
                                    .order_by(Item.id).limit(6))).all()
        k = nonce()
        for it in portable:
            if sh.mode == "foot" and not ITEMS[it.def_code].portable:
                continue
            rows.append([btn(f"+ {items.title(it)}"[:40], Do(a="trip_item", x=sh.id, y=it.id, k=k))])
        rows.append([btn("▶ Отправить", Do(a="trip_go", x=sh.id, k=k)), btn("✕ Отменить", Do(a="trip_cancel", x=sh.id, k=k))])
    scene = ship_scene([c.resource for c in cargo if c.resource], armored, painted, sh.mode == "foot")
    return "\n".join(lines), kb(*rows, back("transport")), scene


@router.callback_query(Nav.filter(F.s == "trip"))
async def cb_trip(cq: CallbackQuery, callback_data: Nav):
    async def run():
        async with tx() as s:
            user = await current_user(s, cq.from_user)
            acc, _ = await acting(s, user)
            text, markup, scene = await trip_card(s, acc, int(callback_data.a))
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
        await show(cq, f"{text}\n\n<b>Отправлен.</b> Прибытие через {eta_text(sh.eta)}. Развернуть в пути нельзя.",
                   kb([btn("Перевозки", Nav(s="transport"))], back()), scene=scene)
    await guarded(cq, run)


@router.callback_query(Do.filter(F.a == "trip_cancel"))
async def do_trip_cancel(cq: CallbackQuery, callback_data: Do):
    async def run():
        async with tx() as s:
            user = await current_user(s, cq.from_user)
            await transport.cancel(s, user.id, callback_data.x, op_key=op_key(cq.from_user.id, callback_data.k))
            text, markup = await transport_screen(s, *(await acting(s, user)))
        await show(cq, "Рейс отменён, груз и топливо освобождены.\n\n" + text, markup, scene="truck")
    await guarded(cq, run)


__all__ = ["router", "ship_scene", "e"]
