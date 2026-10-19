import asyncio

import pytest

from ironvein.domain.errors import AlreadyDone, GameError
from ironvein.services import clock, production
from tests.conftest import make_user
from tests.helpers import (
    deposit,
    deposit_id,
    get_item,
    give,
    give_item,
    qty,
    user_items,
)


async def run_due(sm):
    async with sm() as s:
        ids = await production.due_job_ids(s)
    done = 0
    for i in ids:
        async with sm() as s, s.begin():
            done += await production.complete_job(s, i)
    return done


async def test_manual_mining_with_pick_depletes_deposit_and_wears_tool(sm):
    u = await make_user(sm, 1)
    pick = (await user_items(sm, u, "pick"))[0]
    dep = await deposit_id(sm, "rust_north")
    before = (await deposit(sm, "rust_north")).stock
    async with sm() as s, s.begin():
        job = await production.start_mining(s, u, u, dep, pick.id)
    assert (await deposit(sm, "rust_north")).stock == before - 6
    assert (await get_item(sm, pick.id)).durability == 59
    assert (await get_item(sm, pick.id)).status == "busy"
    assert await run_due(sm) == 0  # срок не наступил
    clock.advance(minutes=11)
    assert await run_due(sm) == 1
    assert await qty(sm, u, "rust", "ore") == 6
    assert (await get_item(sm, pick.id)).status == "idle"
    # Повторное завершение ничего не выдаёт.
    async with sm() as s, s.begin():
        assert not await production.complete_job(s, job.id)
    assert await qty(sm, u, "rust", "ore") == 6


async def test_one_manual_shift_at_a_time(sm):
    u = await make_user(sm, 1)
    pick = (await user_items(sm, u, "pick"))[0]
    async with sm() as s, s.begin():
        await production.start_mining(s, u, u, await deposit_id(sm, "rust_coal3"), pick.id)
    with pytest.raises(GameError):
        async with sm() as s, s.begin():
            await production.start_mining(s, u, u, await deposit_id(sm, "rust_north"), None)


async def test_deposit_depletion_and_regeneration(sm):
    u = await make_user(sm, 1)
    from sqlalchemy import update

    from ironvein.models import Deposit
    async with sm() as s, s.begin():
        await s.execute(update(Deposit).where(Deposit.code == "rust_red").values(stock=4, regen_at=clock.now()))
    pick = (await user_items(sm, u, "pick"))[0]
    async with sm() as s, s.begin():
        job = await production.start_mining(s, u, u, await deposit_id(sm, "rust_red"), pick.id)
    assert job.outputs == {"ore": 4}
    assert (await deposit(sm, "rust_red")).stock == 0
    clock.advance(minutes=11)
    await run_due(sm)
    # За 11 минут при 400/ч восстановилось floor(11*400/60) = 73 единицы.
    from ironvein.services.world import lock_deposit
    async with sm() as s, s.begin():
        assert (await lock_deposit(s, await deposit_id(sm, "rust_red"))).stock == 73
    async with sm() as s, s.begin():
        await s.execute(update(Deposit).where(Deposit.code == "rust_red").values(stock=0, regen_at=clock.now()))
    with pytest.raises(GameError, match="истощено"):
        async with sm() as s, s.begin():
            await production.start_mining(s, u, u, await deposit_id(sm, "rust_red"), pick.id)
    clock.advance(minutes=1)
    async with sm() as s, s.begin():
        job = await production.start_mining(s, u, u, await deposit_id(sm, "rust_red"), pick.id)
    assert job.outputs == {"ore": 6}
    assert (await deposit(sm, "rust_red")).stock == 6 - 6


async def test_concurrent_mining_never_drives_deposit_negative(sm):
    from sqlalchemy import update

    from ironvein.models import Deposit
    async with sm() as s, s.begin():
        await s.execute(update(Deposit).where(Deposit.code == "rust_red").values(stock=10, regen_at=clock.now()))
    uids = [await make_user(sm, 10 + i) for i in range(6)]
    dep = await deposit_id(sm, "rust_red")

    async def mine(u):
        pick = (await user_items(sm, u, "pick"))[0]
        try:
            async with sm() as s, s.begin():
                j = await production.start_mining(s, u, u, dep, pick.id)
                return sum(j.outputs.values())
        except GameError:
            return 0
    got = await asyncio.gather(*[mine(u) for u in uids])
    assert sum(got) == 10
    assert (await deposit(sm, "rust_red")).stock == 0


async def test_recipe_requires_inputs_and_facility(sm):
    u = await make_user(sm, 1)
    with pytest.raises(GameError, match="Не хватает"):
        async with sm() as s, s.begin():
            await production.start_craft(s, u, u, "forge_steel", "rust")
    with pytest.raises(GameError, match="Плавильня"):
        async with sm() as s, s.begin():
            await production.start_craft(s, u, u, "smelt_steel", "rust")
    await give(sm, u, "rust", "ore", 8)
    await give(sm, u, "rust", "coal", 6)
    async with sm() as s, s.begin():
        await production.start_craft(s, u, u, "forge_steel", "rust", runs=2)
    assert await qty(sm, u, "rust", "ore") == 0
    clock.advance(minutes=21)
    await run_due(sm)
    assert await qty(sm, u, "rust", "steel") == 2


async def test_bootstrap_chain_from_nothing_to_drill(sm):
    """Без единой NPC-поставки: руда/уголь -> кустарная сталь -> мастерская -> запчасти -> буровая."""
    u = await make_user(sm, 1)
    await give(sm, u, "rust", "steel", 12 + 15 + 8)  # эквивалент ручного труда, ускоряем тест
    async with sm() as s, s.begin():
        await production.start_craft(s, u, u, "build_workshop", "rust")
    clock.advance(minutes=31)
    await run_due(sm)
    ws = (await user_items(sm, u, "workshop"))[0]
    async with sm() as s, s.begin():
        await production.start_craft(s, u, u, "make_parts", "rust", runs=4, facility_id=ws.id)
    clock.advance(minutes=21)
    await run_due(sm)
    assert await qty(sm, u, "rust", "parts") == 4
    async with sm() as s, s.begin():
        await production.start_craft(s, u, u, "build_drill", "rust")
    clock.advance(minutes=31)
    await run_due(sm)
    drill = (await user_items(sm, u, "drill"))[0]
    assert drill.durability == 100 and drill.origin == "craft"
    assert (await get_item(sm, ws.id)).durability == 150 - 4 - 1


async def test_machine_mining_needs_fuel_and_wears(sm):
    u = await make_user(sm, 1)
    drill = await give_item(sm, u, "drill")
    dep = await deposit_id(sm, "rust_north")
    with pytest.raises(GameError, match="Дизель"):
        async with sm() as s, s.begin():
            await production.start_mining(s, u, u, dep, drill, runs=3)
    await give(sm, u, "rust", "diesel", 6)
    async with sm() as s, s.begin():
        job = await production.start_mining(s, u, u, dep, drill, runs=3)
    assert job.outputs == {"ore": 30}
    assert await qty(sm, u, "rust", "diesel") == 0
    assert (await get_item(sm, drill)).durability == 97
    assert not job.manual
    # Машинная добыча не занимает «рабочие руки».
    pick = (await user_items(sm, u, "pick"))[0]
    async with sm() as s, s.begin():
        await production.start_mining(s, u, u, dep, pick.id)


async def test_zero_durability_stops_use_and_repair_restores(sm):
    u = await make_user(sm, 1)
    drill = await give_item(sm, u, "drill")
    from sqlalchemy import update

    from ironvein.models import Item
    async with sm() as s, s.begin():
        await s.execute(update(Item).where(Item.id == drill).values(durability=0))
    await give(sm, u, "rust", "diesel", 2)
    with pytest.raises(GameError, match="изношен"):
        async with sm() as s, s.begin():
            await production.start_mining(s, u, u, await deposit_id(sm, "rust_north"), drill)
    await give(sm, u, "rust", "parts", 4)
    with pytest.raises(GameError, match="мастерская"):
        async with sm() as s, s.begin():
            await production.start_repair(s, u, u, drill, steps=2)
    ws = await give_item(sm, u, "workshop")
    async with sm() as s, s.begin():
        await production.start_repair(s, u, u, drill, steps=2)
    assert (await get_item(sm, ws)).status == "busy"
    clock.advance(minutes=21)
    await run_due(sm)
    d = await get_item(sm, drill)
    assert d.durability == 100 and d.status == "idle"
    assert (await get_item(sm, ws)).status == "idle"
    assert await qty(sm, u, "rust", "parts") == 0


async def test_cancel_returns_inputs_not_wear(sm):
    u = await make_user(sm, 1)
    ws = await give_item(sm, u, "workshop")
    await give(sm, u, "rust", "steel", 4)
    async with sm() as s, s.begin():
        job = await production.start_craft(s, u, u, "make_parts", "rust", runs=2, facility_id=ws)
    async with sm() as s, s.begin():
        await production.cancel_job(s, u, job.id)
    assert await qty(sm, u, "rust", "steel") == 4
    w = await get_item(sm, ws)
    assert w.status == "idle" and w.durability == 148
    clock.advance(minutes=30)
    assert await run_due(sm) == 0
    assert await qty(sm, u, "rust", "parts") == 0


async def test_idempotent_start_with_op_key(sm):
    u = await make_user(sm, 1)
    await give(sm, u, "rust", "steel", 10)
    async with sm() as s, s.begin():
        await production.start_craft(s, u, u, "hand_parts", "rust", op_key="k1")
    with pytest.raises(AlreadyDone):
        async with sm() as s, s.begin():
            await production.start_craft(s, u, u, "hand_parts", "rust", op_key="k1")
    assert await qty(sm, u, "rust", "steel") == 7


async def test_truck_assembly_from_modules(sm):
    u = await make_user(sm, 1)
    await give_item(sm, u, "workshop")
    mods = [await give_item(sm, u, c) for c in ("chassis", "engine_d8", "tank", "body_cargo")]
    await give(sm, u, "rust", "parts", 2)
    with pytest.raises(GameError):
        async with sm() as s, s.begin():
            await production.start_craft(s, u, u, "assemble_truck", "rust", module_ids=mods[:3] + [mods[0]])
    async with sm() as s, s.begin():
        await production.start_craft(s, u, u, "assemble_truck", "rust", module_ids=mods)
    clock.advance(minutes=16)
    await run_due(sm)
    trucks = await user_items(sm, u, "truck")
    assert len(trucks) == 1 and trucks[0].max_durability == 120
    for m in mods:
        it = await get_item(sm, m)
        assert it.status == "installed" and it.parent_id == trucks[0].id
