import asyncio

import pytest

from ironvein.domain.errors import GameError
from ironvein.services import clock, transport
from ironvein.services.metrics import integrity_report
from tests.conftest import make_user
from tests.helpers import get_item, give, give_item, qty


async def make_truck(sm, owner, engine="engine_d8", body="body_cargo", loc="rust"):
    """Собранный грузовик (модули — тестовая выдача, сборка проверяется в test_production)."""
    from ironvein.services import items
    from ironvein.domain.vehicles import truck_stats
    async with sm() as s, s.begin():
        mods = ["chassis", engine, "tank", body]
        st = truck_stats(mods)
        t = await items.create(s, "truck", owner, loc, "admin", max_durability=st.max_durability)
        for m in mods:
            it = await items.create(s, m, owner, loc, "admin", status="installed")
            it.parent_id = t.id
        return t.id


async def arrive_due(sm):
    async with sm() as s:
        ids = await transport.due_shipment_ids(s)
    n = 0
    for i in ids:
        async with sm() as s, s.begin():
            n += await transport.arrive(s, i)
    return n


async def ok(sm):
    async with sm() as s:
        rep = await integrity_report(s)
    assert rep["ok"], rep


async def test_truck_trip_reserves_burns_fuel_and_delivers_after_eta(sm):
    u = await make_user(sm, 1)
    truck = await make_truck(sm, u)
    await give(sm, u, "rust", "steel", 30)
    await give(sm, u, "rust", "diesel", 10)
    async with sm() as s, s.begin():
        sh = await transport.plan(s, u, u, origin="rust", dest="kotlo", cargo={"steel": 30}, vehicle_id=truck)
    assert sh.fuel == 4 and sh.wear == 3  # 60 км × 6/100 = 3.6 -> 4; 60/20 = 3
    assert await qty(sm, u, "rust", "steel", held=True) == 30
    assert await qty(sm, u, "rust", "diesel", held=True) == 4
    await ok(sm)
    async with sm() as s, s.begin():
        sh = await transport.depart(s, u, sh.id)
    # В пути груз не лежит ни на одном складе.
    assert await qty(sm, u, "rust", "steel", held=True) == 0
    assert await qty(sm, u, "kotlo", "steel") == 0
    assert await qty(sm, u, "rust", "diesel") == 6
    v = await get_item(sm, truck)
    assert v.status == "in_transit" and v.location_code is None and v.durability == 117
    await ok(sm)
    with pytest.raises(GameError, match="в пути"):
        async with sm() as s, s.begin():
            await transport.cancel(s, u, sh.id)
    assert await arrive_due(sm) == 0
    clock.advance(minutes=81)  # 60 км при 45 км/ч = 80 мин
    assert await arrive_due(sm) == 1
    assert await arrive_due(sm) == 0
    async with sm() as s, s.begin():
        assert not await transport.arrive(s, sh.id)
    assert await qty(sm, u, "kotlo", "steel") == 30
    v = await get_item(sm, truck)
    assert v.status == "idle" and v.location_code == "kotlo"
    await ok(sm)


async def test_cancel_before_departure_releases_everything(sm):
    u = await make_user(sm, 1)
    truck = await make_truck(sm, u)
    await give(sm, u, "rust", "ore", 10)
    await give(sm, u, "rust", "diesel", 10)
    async with sm() as s, s.begin():
        sh = await transport.plan(s, u, u, origin="rust", dest="kotlo", cargo={"ore": 10}, vehicle_id=truck)
    async with sm() as s, s.begin():
        await transport.cancel(s, u, sh.id)
    assert await qty(sm, u, "rust", "ore") == 10 and await qty(sm, u, "rust", "diesel") == 10
    assert (await get_item(sm, truck)).status == "idle"
    await ok(sm)


async def test_capacity_fuel_range_and_wear_limits(sm):
    u = await make_user(sm, 1)
    truck = await make_truck(sm, u, engine="engine_d12", body="body_armored")
    await give(sm, u, "rust", "ore", 100)
    with pytest.raises(GameError, match="Перегруз"):
        async with sm() as s, s.begin():
            await transport.plan(s, u, u, origin="rust", dest="kotlo", cargo={"ore": 31}, vehicle_id=truck)
    with pytest.raises(GameError, match="Дизель"):
        async with sm() as s, s.begin():
            await transport.plan(s, u, u, origin="rust", dest="kotlo", cargo={"ore": 30}, vehicle_id=truck)
    await give(sm, u, "rust", "diesel", 20)
    # Д-12 + броня: 11/100 км, бак 12 -> 120 км нужно 14 дизеля > бака.
    with pytest.raises(GameError, match="бака"):
        async with sm() as s, s.begin():
            await transport.plan(s, u, u, origin="rust", dest="mazut", cargo={"ore": 30}, vehicle_id=truck)
    from sqlalchemy import update
    from ironvein.models import Item
    async with sm() as s, s.begin():
        await s.execute(update(Item).where(Item.id == truck).values(durability=1))
    with pytest.raises(GameError, match="изношена"):
        async with sm() as s, s.begin():
            await transport.plan(s, u, u, origin="rust", dest="kotlo", cargo={"ore": 30}, vehicle_id=truck)


async def test_same_truck_cannot_be_used_twice_concurrently(sm):
    u = await make_user(sm, 1)
    truck = await make_truck(sm, u)
    await give(sm, u, "rust", "ore", 40)
    await give(sm, u, "rust", "diesel", 20)

    async def attempt(dest):
        try:
            async with sm() as s, s.begin():
                await transport.send(s, u, u, origin="rust", dest=dest, cargo={"ore": 20}, vehicle_id=truck)
                return 1
        except GameError:
            return 0
    res = await asyncio.gather(attempt("kotlo"), attempt("mazut"), attempt("kotlo"))
    assert sum(res) == 1
    await ok(sm)


async def test_cargo_in_transit_cannot_be_sold(sm):
    from ironvein.services import market
    u = await make_user(sm, 1)
    truck = await make_truck(sm, u)
    await give(sm, u, "rust", "steel", 10)
    await give(sm, u, "rust", "diesel", 5)
    async with sm() as s, s.begin():
        await transport.send(s, u, u, origin="rust", dest="kotlo", cargo={"steel": 10}, vehicle_id=truck)
    with pytest.raises(GameError):
        async with sm() as s, s.begin():
            await market.place_ask_resource(s, u, u, "rust", "steel", 1, 10)
    with pytest.raises(GameError):
        async with sm() as s, s.begin():
            await market.place_ask_resource(s, u, u, "kotlo", "steel", 1, 10)
    with pytest.raises(GameError):
        async with sm() as s, s.begin():
            await market.place_ask_item(s, u, u, truck, 1000)


async def test_foot_trip_limits_and_carries_tools(sm):
    u = await make_user(sm, 1)
    from tests.helpers import user_items
    pick = (await user_items(sm, u, "pick"))[0].id
    await give(sm, u, "rust", "steel", 20)
    with pytest.raises(GameError, match="Перегруз"):
        async with sm() as s, s.begin():
            await transport.send(s, u, u, origin="rust", dest="mazut", cargo={"steel": 10}, item_ids=[pick])
    drill = await give_item(sm, u, "drill")
    with pytest.raises(GameError, match="тяж"):
        async with sm() as s, s.begin():
            await transport.send(s, u, u, origin="rust", dest="mazut", item_ids=[drill])
    async with sm() as s, s.begin():
        sh = await transport.send(s, u, u, origin="rust", dest="mazut", cargo={"steel": 9}, item_ids=[pick])
    assert sh.mode == "foot" and sh.fuel == 0
    with pytest.raises(GameError, match="пешком"):
        async with sm() as s, s.begin():
            await transport.send(s, u, u, origin="rust", dest="kotlo", cargo={"steel": 1})
    clock.advance(hours=24, minutes=1)
    await arrive_due(sm)
    assert await qty(sm, u, "mazut", "steel") == 9
    p = await get_item(sm, pick)
    assert p.location_code == "mazut" and p.status == "idle"
    await ok(sm)


async def test_delivery_survives_restart(sm):
    """«Рестарт»: новая сессия/процесс находит просроченный рейс и завершает ровно один раз."""
    u = await make_user(sm, 1)
    truck = await make_truck(sm, u)
    await give(sm, u, "rust", "coal", 5)
    await give(sm, u, "rust", "diesel", 5)
    async with sm() as s, s.begin():
        await transport.send(s, u, u, origin="rust", dest="kotlo", cargo={"coal": 5}, vehicle_id=truck)
    clock.advance(hours=5)
    from ironvein.jobs.runner import run_once
    r1 = await run_once(sm)
    r2 = await run_once(sm)
    assert r1["shipments"] == 1 and r2["shipments"] == 0
    assert await qty(sm, u, "kotlo", "coal") == 5


async def test_incremental_loading_then_depart(sm):
    u = await make_user(sm, 1)
    truck = await make_truck(sm, u)
    await give(sm, u, "rust", "steel", 50)
    await give(sm, u, "rust", "diesel", 10)
    async with sm() as s, s.begin():
        sh = await transport.plan(s, u, u, origin="rust", dest="kotlo", vehicle_id=truck, allow_empty=True)
    with pytest.raises(GameError, match="пуст"):
        async with sm() as s, s.begin():
            await transport.depart(s, u, sh.id)
    async with sm() as s, s.begin():
        await transport.add_cargo(s, u, sh.id, resource="steel", qty=25)
    async with sm() as s, s.begin():
        await transport.add_cargo(s, u, sh.id, resource="steel", qty=10)
    with pytest.raises(GameError, match="Перегруз"):
        async with sm() as s, s.begin():
            await transport.add_cargo(s, u, sh.id, resource="steel", qty=6)
    await ok(sm)
    async with sm() as s, s.begin():
        await transport.depart(s, u, sh.id)
    clock.advance(hours=2)
    await arrive_due(sm)
    assert await qty(sm, u, "kotlo", "steel") == 35
    await ok(sm)
