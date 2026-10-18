"""Логистика: рейсы грузовиков и пеший перенос между локациями.

Жизненный цикл рейса:
  loading    — машина, груз и топливо зарезервированы в пункте отправления; можно отменить;
  in_transit — топливо сожжено, износ применён, груз списан со склада отправления и находится только
               в shipment_cargo (ни на одном складе); отмена невозможна;
  delivered  — после ETA сервер ровно один раз зачисляет груз на склад назначения.
Случайных поломок и нападений нет: износ детерминирован, машину с недостаточной прочностью не выпустят.
"""

import math

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ironvein.domain.catalog import FOOT_CAPACITY, FOOT_SPEED_KMH, ITEMS, KIND_EQUIPMENT, KIND_MODULE, KIND_VEHICLE, LOCATIONS, route_km
from ironvein.domain.errors import GameError, NotFound
from ironvein.domain.permissions import Perm
from ironvein.domain.vehicles import TruckStats, trip_fuel, trip_minutes, trip_wear, truck_stats
from ironvein.models import ITEM_IDLE, ITEM_IN_TRANSIT, ITEM_LOADING, Item, Shipment, ShipmentCargo
from ironvein.services import authz, clock, items, stock
from ironvein.services.common import audit, claim_operation


def item_weight(def_code: str) -> int:
    kind = ITEMS[def_code].kind
    if ITEMS[def_code].portable:
        return 1
    return {KIND_EQUIPMENT: 10, KIND_MODULE: 5}.get(kind, 1)


async def vehicle_stats(session: AsyncSession, vehicle_id: int) -> TruckStats:
    mods = (await session.scalars(select(Item.def_code).where(Item.parent_id == vehicle_id))).all()
    mods = [m for m in mods if ITEMS[m].kind == KIND_MODULE]
    return truck_stats(mods)


async def plan(session: AsyncSession, user_id: int, account_id: int, *, origin: str, dest: str,
               cargo: dict[str, int] | None = None, item_ids: list[int] | None = None,
               vehicle_id: int | None = None, cargo_owner: int | None = None, recipient: int | None = None,
               contract_id: int | None = None, op_key: str | None = None) -> Shipment:
    """Создаёт рейс в статусе loading и резервирует всё необходимое.

    account_id — перевозчик (владелец машины или идущий пешком). cargo_owner — владелец груза
    (по умолчанию тот же); для чужого груза (контракт перевозки) груз уже заблокирован контрактом.
    """
    await authz.require(session, user_id, account_id, Perm.TRANSPORT)
    await claim_operation(session, op_key, "ship_plan", user_id)
    cargo = {r: q for r, q in (cargo or {}).items() if q}
    item_ids = item_ids or []
    cargo_owner = cargo_owner or account_id
    recipient = recipient or cargo_owner
    if origin not in LOCATIONS or dest not in LOCATIONS or origin == dest:
        raise GameError("Выберите две разные локации.")
    km = route_km(origin, dest)
    if km is None:
        raise GameError("Между этими локациями нет дороги.")
    if not cargo and not item_ids:
        raise GameError("Пустой рейс: добавьте груз.")
    if any(q < 0 for q in cargo.values()):
        raise GameError("Некорректный груз.")

    if vehicle_id is None:
        mode, fuel, wear = "foot", 0, 0
        capacity = FOOT_CAPACITY
        busy = await session.scalar(select(func.count()).select_from(Shipment).where(
            Shipment.mode == "foot", Shipment.created_by_user_id == user_id,
            Shipment.status.in_(("loading", "in_transit"))))
        if busy:
            raise GameError("Вы уже в пути пешком — второго себя нет.")
        vehicle = None
    else:
        mode = "truck"
        vehicle = await items.lock_owned(session, vehicle_id, account_id)
        if ITEMS[vehicle.def_code].kind != KIND_VEHICLE:
            raise GameError("Это не транспорт.")
        if vehicle.location_code != origin:
            raise GameError(f"Машина стоит в другой локации: {LOCATIONS[vehicle.location_code].name}.")
        st = await vehicle_stats(session, vehicle.id)
        capacity = st.payload
        fuel = trip_fuel(st, km)
        wear = trip_wear(km)
        if fuel > st.tank:
            raise GameError(f"Не хватит бака: нужно {fuel} дизеля, бак {st.tank}. Запас хода {st.range_km} км.")
        if vehicle.durability < wear:
            raise GameError(f"Машина изношена ({vehicle.durability}/{vehicle.max_durability}), рейс требует {wear}. "
                            "Нужен ремонт в мастерской.")
        vehicle.status = ITEM_LOADING

    weight = sum(cargo.values())
    locked_items: list[Item] = []
    for iid in sorted(item_ids):
        it = await items.lock_owned(session, iid, cargo_owner)
        d = ITEMS[it.def_code]
        if d.kind == KIND_VEHICLE:
            raise GameError("Машину нельзя погрузить в машину.")
        if it.location_code != origin:
            raise GameError(f"«{items.title(it)}» находится в другой локации.")
        if mode == "foot" and not d.portable:
            raise GameError(f"«{d.name}» слишком тяжёл, чтобы нести его пешком.")
        weight += item_weight(it.def_code)
        locked_items.append(it)
    if weight > capacity:
        raise GameError(f"Перегруз: {weight} при грузоподъёмности {capacity}.")

    sh = Shipment(mode=mode, vehicle_id=vehicle.id if vehicle else None, carrier_id=account_id,
                  created_by_user_id=user_id, origin=origin, dest=dest, distance_km=km, fuel=fuel, wear=wear,
                  status="loading", contract_id=contract_id)
    session.add(sh)
    await session.flush()
    for r, q in sorted(cargo.items()):
        if contract_id is None:
            await stock.hold(session, cargo_owner, origin, r, q, "ship_load", ref_type="shipment", ref_id=sh.id,
                             actor=user_id)
        session.add(ShipmentCargo(shipment_id=sh.id, owner_id=cargo_owner, recipient_id=recipient, resource=r, qty=q))
    for it in locked_items:
        it.status = ITEM_LOADING
        session.add(ShipmentCargo(shipment_id=sh.id, owner_id=cargo_owner, recipient_id=recipient, item_id=it.id))
    if fuel:
        await stock.hold(session, account_id, origin, "diesel", fuel, "fuel_reserve", ref_type="shipment",
                         ref_id=sh.id, actor=user_id)
    await session.flush()
    await audit(session, "ship_plan", actor_user_id=user_id, account_id=account_id, target_type="shipment",
                target_id=sh.id, origin=origin, dest=dest, cargo=cargo, items=item_ids, fuel=fuel)
    return sh


async def _lock(session: AsyncSession, shipment_id: int) -> Shipment:
    sh = (await session.execute(select(Shipment).where(Shipment.id == shipment_id).with_for_update()
                                .execution_options(populate_existing=True))).scalar_one_or_none()
    if sh is None:
        raise NotFound("Рейс не найден.")
    return sh


async def cargo_of(session: AsyncSession, shipment_id: int) -> list[ShipmentCargo]:
    return list((await session.scalars(select(ShipmentCargo).where(ShipmentCargo.shipment_id == shipment_id)
                                       .order_by(ShipmentCargo.id))).all())


async def trip_duration_minutes(session: AsyncSession, sh: Shipment) -> int:
    if sh.mode == "foot":
        return math.ceil(sh.distance_km * 60 / FOOT_SPEED_KMH)
    st = await vehicle_stats(session, sh.vehicle_id)
    return trip_minutes(st.speed_kmh, sh.distance_km)


async def depart(session: AsyncSession, user_id: int, shipment_id: int, op_key: str | None = None,
                 *, system: bool = False) -> Shipment:
    sh = await _lock(session, shipment_id)
    if not system:
        await authz.require(session, user_id, sh.carrier_id, Perm.TRANSPORT)
    if sh.status != "loading":
        raise GameError("Рейс уже отправлен или отменён.")
    await claim_operation(session, op_key, "ship_depart", user_id)
    if sh.fuel:
        await stock.take(session, sh.carrier_id, sh.origin, "diesel", sh.fuel, "fuel_trip", ref_type="shipment",
                         ref_id=sh.id, actor=user_id, from_held=True)
    if sh.vehicle_id:
        v = await items.lock(session, sh.vehicle_id)
        v.durability -= sh.wear
        v.status = ITEM_IN_TRANSIT
        await items.set_location(session, v, None)
    for c in await cargo_of(session, sh.id):
        if c.resource:
            await stock.take(session, c.owner_id, sh.origin, c.resource, c.qty, "ship_out", ref_type="shipment",
                             ref_id=sh.id, actor=user_id, from_held=True)
        else:
            it = await items.lock(session, c.item_id)
            it.status = ITEM_IN_TRANSIT
            it.location_code = None
    now = clock.now()
    sh.status = "in_transit"
    sh.departed_at = now
    sh.eta = now + clock.game_minutes(await trip_duration_minutes(session, sh))
    await session.flush()
    await audit(session, "ship_depart", actor_user_id=user_id, account_id=sh.carrier_id, target_type="shipment",
                target_id=sh.id, eta=sh.eta.isoformat())
    return sh


async def cancel(session: AsyncSession, user_id: int, shipment_id: int, op_key: str | None = None,
                 *, system: bool = False) -> Shipment:
    """Отмена возможна только до отправления: все резервы освобождаются."""
    sh = await _lock(session, shipment_id)
    if not system:
        await authz.require(session, user_id, sh.carrier_id, Perm.TRANSPORT)
    if sh.status == "in_transit":
        raise GameError("Рейс уже в пути — развернуть его нельзя. Дождитесь прибытия.")
    if sh.status != "loading":
        raise GameError("Рейс уже завершён или отменён.")
    await claim_operation(session, op_key, "ship_cancel", user_id)
    if sh.fuel:
        await stock.release(session, sh.carrier_id, sh.origin, "diesel", sh.fuel, "fuel_release",
                            ref_type="shipment", ref_id=sh.id, actor=user_id)
    for c in await cargo_of(session, sh.id):
        if c.resource and sh.contract_id is None:
            await stock.release(session, c.owner_id, sh.origin, c.resource, c.qty, "ship_unload",
                                ref_type="shipment", ref_id=sh.id, actor=user_id)
        elif c.item_id:
            it = await items.lock(session, c.item_id)
            it.status = ITEM_IDLE
    if sh.vehicle_id:
        v = await items.lock(session, sh.vehicle_id)
        v.status = ITEM_IDLE
    sh.status = "cancelled"
    await audit(session, "ship_cancel", actor_user_id=user_id, account_id=sh.carrier_id, target_type="shipment",
                target_id=sh.id)
    return sh


async def arrive(session: AsyncSession, shipment_id: int) -> bool:
    """Идемпотентное прибытие: груз зачисляется ровно один раз, только после ETA."""
    sh = await _lock(session, shipment_id)
    if sh.status != "in_transit" or sh.eta > clock.now():
        return False
    for c in await cargo_of(session, sh.id):
        if c.resource:
            await stock.add(session, c.recipient_id, sh.dest, c.resource, c.qty, "ship_in", ref_type="shipment",
                            ref_id=sh.id, check_capacity=False)
        else:
            it = await items.lock(session, c.item_id)
            if it.owner_id != c.recipient_id:
                await items.transfer(session, it, c.recipient_id, "delivery", ref_type="shipment", ref_id=sh.id)
            it.location_code = sh.dest
            if it.status == ITEM_IN_TRANSIT:
                it.status = ITEM_IDLE
    if sh.vehicle_id:
        v = await items.lock(session, sh.vehicle_id)
        await items.set_location(session, v, sh.dest)
        if v.status == ITEM_IN_TRANSIT:
            v.status = ITEM_IDLE
    sh.status = "delivered"
    sh.arrived_at = clock.now()
    await session.flush()
    if sh.contract_id is not None:
        from ironvein.services import contracts
        await contracts.on_transport_delivered(session, sh.contract_id, sh.id)
    await audit(session, "ship_arrive", account_id=sh.carrier_id, target_type="shipment", target_id=sh.id)
    return True


async def send(session: AsyncSession, user_id: int, account_id: int, **kw) -> Shipment:
    """Погрузка и немедленное отправление одной операцией."""
    op_key = kw.pop("op_key", None)
    sh = await plan(session, user_id, account_id, op_key=op_key, **kw)
    return await depart(session, user_id, sh.id)


async def due_shipment_ids(session: AsyncSession, limit: int = 100) -> list[int]:
    return list((await session.scalars(
        select(Shipment.id).where(Shipment.status == "in_transit", Shipment.eta <= clock.now())
        .order_by(Shipment.eta).limit(limit))).all())


async def shipments_of(session: AsyncSession, account_id: int, active_only: bool = True) -> list[Shipment]:
    q = select(Shipment).where(
        (Shipment.carrier_id == account_id) |
        Shipment.id.in_(select(ShipmentCargo.shipment_id).where(
            (ShipmentCargo.owner_id == account_id) | (ShipmentCargo.recipient_id == account_id))))
    if active_only:
        q = q.where(Shipment.status.in_(("loading", "in_transit")))
    return list((await session.scalars(q.order_by(Shipment.id.desc()).limit(20))).all())


async def vehicles_of(session: AsyncSession, account_id: int) -> list[Item]:
    return list((await session.scalars(select(Item).where(
        Item.owner_id == account_id, Item.def_code == "truck").order_by(Item.id))).all())


async def modules_of(session: AsyncSession, vehicle_id: int) -> list[Item]:
    return list((await session.scalars(select(Item).where(Item.parent_id == vehicle_id).order_by(Item.id))).all())
