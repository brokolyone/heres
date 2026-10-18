import pytest

from ironvein.domain.errors import Forbidden, GameError
from ironvein.services import clock, companies, contracts
from ironvein.services.metrics import integrity_report
from tests.conftest import make_user
from tests.helpers import bal, give, qty
from tests.test_transport import arrive_due, make_truck


async def ok(sm):
    async with sm() as s:
        rep = await integrity_report(s)
    assert rep["ok"], rep
    return rep


async def supply(sm, customer, qty_=10, price=1000, hours=24, location="kotlo"):
    async with sm() as s, s.begin():
        c = await contracts.create(s, customer, customer, kind="supply", resource="steel", qty=qty_,
                                   price_total=price, location=location, deadline_hours=hours)
    async with sm() as s, s.begin():
        await contracts.publish(s, customer, c.id)
    return c.id


async def test_supply_partial_deliveries_proportional_payment(sm):
    cust = await make_user(sm, 1)
    ex = await make_user(sm, 2)
    cid = await supply(sm, cust, qty_=3, price=1000)
    assert (await bal(sm, cust)) == {"main": 0, "hold": 1000}
    async with sm() as s, s.begin():
        await contracts.accept_supply(s, ex, ex, cid)
    # Нельзя «поставить» то, чего нет на складе в месте поставки.
    await give(sm, ex, "rust", "steel", 3)
    with pytest.raises(GameError, match="Не хватает"):
        async with sm() as s, s.begin():
            await contracts.deliver(s, ex, cid, 1)
    await give(sm, ex, "kotlo", "steel", 3)
    paid = []
    for _ in range(3):
        async with sm() as s, s.begin():
            f = await contracts.deliver(s, ex, cid, 1)
            paid.append((f.payout, f.fee))
    # 333/667/1000 накопительно; комиссия накопительно ceil(1000*2%) = 20.
    assert sum(p for p, _ in paid) + sum(f for _, f in paid) == 1000
    assert sum(f for _, f in paid) == 20
    assert (await bal(sm, ex))["main"] == 1000 + 980
    assert (await bal(sm, cust)) == {"main": 0, "hold": 0}
    assert await qty(sm, cust, "kotlo", "steel") == 3
    with pytest.raises(GameError):
        async with sm() as s, s.begin():
            await contracts.deliver(s, ex, cid, 1)
    await ok(sm)


async def test_cannot_accept_own_or_company_contract(sm):
    cust = await make_user(sm, 1)
    async with sm() as s, s.begin():
        comp = await companies.create(s, cust, "Моя Контора")
    cid = await supply(sm, cust, price=100)
    with pytest.raises(Forbidden):
        async with sm() as s, s.begin():
            await contracts.accept_supply(s, cust, cust, cid)
    with pytest.raises(Forbidden):
        async with sm() as s, s.begin():
            await contracts.accept_supply(s, cust, comp.id, cid)


async def test_cancel_before_acceptance_refunds(sm):
    cust = await make_user(sm, 1)
    ex = await make_user(sm, 2)
    cid = await supply(sm, cust, price=300)
    async with sm() as s, s.begin():
        await contracts.cancel(s, cust, cid)
    assert (await bal(sm, cust)) == {"main": 1000, "hold": 0}
    with pytest.raises(GameError):
        async with sm() as s, s.begin():
            await contracts.accept_supply(s, ex, ex, cid)
    cid2 = await supply(sm, cust, price=300)
    async with sm() as s, s.begin():
        await contracts.accept_supply(s, ex, ex, cid2)
    with pytest.raises(GameError, match="до принятия"):
        async with sm() as s, s.begin():
            await contracts.cancel(s, cust, cid2)
    await ok(sm)


async def test_expiry_refunds_undelivered_remainder(sm):
    cust = await make_user(sm, 1)
    ex = await make_user(sm, 2)
    cid = await supply(sm, cust, qty_=4, price=400, hours=2)
    async with sm() as s, s.begin():
        await contracts.accept_supply(s, ex, ex, cid)
    await give(sm, ex, "kotlo", "steel", 1)
    async with sm() as s, s.begin():
        await contracts.deliver(s, ex, cid, 1)
    clock.advance(hours=3)
    from ironvein.jobs.runner import run_once
    r = await run_once(sm)
    assert r["contracts"] == 1
    assert (await bal(sm, cust)) == {"main": 600 + 300, "hold": 0}
    assert (await bal(sm, ex))["main"] == 1000 + 98
    async with sm() as s:
        from ironvein.models import Contract
        assert (await s.get(Contract, cid)).status == "expired"
    await ok(sm)


async def test_dispute_freezes_and_admin_resolves_with_audit(sm):
    cust = await make_user(sm, 1)
    ex = await make_user(sm, 2)
    cid = await supply(sm, cust, qty_=2, price=200, hours=1)
    async with sm() as s, s.begin():
        await contracts.accept_supply(s, ex, ex, cid)
    async with sm() as s, s.begin():
        await contracts.dispute(s, cust, cid, "поставщик молчит")
    clock.advance(hours=2)
    from ironvein.jobs.runner import run_once
    assert (await run_once(sm))["contracts"] == 0  # спор не истекает сам
    async with sm() as s, s.begin():
        await contracts.admin_resolve(s, None, cid, "refund", "исполнитель не ответил")
    assert (await bal(sm, cust)) == {"main": 1000, "hold": 0}
    assert (await bal(sm, ex))["main"] == 1000
    await ok(sm)


async def test_transport_contract_full_cycle(sm):
    cust = await make_user(sm, 1)
    carrier = await make_user(sm, 2)
    truck = await make_truck(sm, carrier)
    await give(sm, cust, "rust", "ore", 30)
    await give(sm, carrier, "rust", "diesel", 10)
    async with sm() as s, s.begin():
        c = await contracts.create(s, cust, cust, kind="transport", resource="ore", qty=30, price_total=500,
                                   location="rust", dest="kotlo", deadline_hours=6)
    async with sm() as s, s.begin():
        await contracts.publish(s, cust, c.id)
    assert await qty(sm, cust, "rust", "ore", held=True) == 30
    await ok(sm)
    with pytest.raises(Forbidden):
        async with sm() as s, s.begin():
            await contracts.accept_transport(s, cust, cust, c.id, None)
    async with sm() as s, s.begin():
        await contracts.accept_transport(s, carrier, carrier, c.id, truck)
    assert await qty(sm, cust, "rust", "ore", held=True) == 0
    await ok(sm)
    assert (await bal(sm, carrier))["main"] == 1000
    clock.advance(minutes=81)
    assert await arrive_due(sm) == 1
    assert await qty(sm, cust, "kotlo", "ore") == 30
    assert (await bal(sm, carrier))["main"] == 1000 + 490
    assert (await bal(sm, cust)) == {"main": 500, "hold": 0}
    await ok(sm)


async def test_transport_contract_rejected_if_eta_after_deadline_and_expires(sm):
    cust = await make_user(sm, 1)
    carrier = await make_user(sm, 2)
    truck = await make_truck(sm, carrier, engine="engine_d4")
    await give(sm, cust, "rust", "ore", 10)
    await give(sm, carrier, "rust", "diesel", 10)
    async with sm() as s, s.begin():
        c = await contracts.create(s, cust, cust, kind="transport", resource="ore", qty=10, price_total=100,
                                   location="rust", dest="kotlo", deadline_hours=1)
    async with sm() as s, s.begin():
        await contracts.publish(s, cust, c.id)
    with pytest.raises(GameError, match="не успеет"):
        async with sm() as s, s.begin():
            await contracts.accept_transport(s, carrier, carrier, c.id, truck)
    assert await qty(sm, carrier, "rust", "diesel") == 10  # откат: топливо не сожжено
    clock.advance(hours=2)
    from ironvein.jobs.runner import run_once
    await run_once(sm)
    assert await qty(sm, cust, "rust", "ore") == 10
    assert (await bal(sm, cust)) == {"main": 1000, "hold": 0}
    await ok(sm)
