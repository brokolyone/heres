import pytest

from ironvein.domain.errors import Forbidden, GameError
from ironvein.domain.permissions import Perm
from ironvein.services import companies, market, production
from ironvein.services.metrics import integrity_report
from tests.conftest import make_user
from tests.helpers import bal, get_item, give, qty, user_items


async def ok(sm):
    async with sm() as s:
        rep = await integrity_report(s)
    assert rep["ok"], rep
    return rep


async def setup_company(sm):
    owner = await make_user(sm, 1, "Владелец")
    async with sm() as s, s.begin():
        c = await companies.create(s, owner, "Стальной Синдикат")
    return owner, c.id


async def test_create_company_fee_is_burned(sm):
    owner, cid = await setup_company(sm)
    assert (await bal(sm, owner))["main"] == 500
    rep = await ok(sm)
    assert rep["burned"] == 500
    with pytest.raises(GameError, match="существует"):
        async with sm() as s, s.begin():
            other = await make_user(sm, 2)
            await companies.create(s, other, "стальной синдикат")


async def test_roles_permissions_and_payroll(sm):
    owner, cid = await setup_company(sm)
    emp = await make_user(sm, 2, "Сотрудник")
    outsider = await make_user(sm, 3, "Чужак")
    async with sm() as s, s.begin():
        inv = await companies.invite(s, owner, cid, emp)
    async with sm() as s, s.begin():
        await companies.answer_invite(s, emp, inv.id, True)
    # Пополнение корпоративного счёта и зарплата — перевод существующих крон.
    async with sm() as s, s.begin():
        await companies.deposit(s, owner, cid, 400)
    async with sm() as s, s.begin():
        await companies.pay(s, owner, cid, emp, 150, "аванс")
    assert (await bal(sm, cid))["main"] == 250
    assert (await bal(sm, emp))["main"] == 1150
    # Сотрудник не может выводить деньги и торговать.
    with pytest.raises(Forbidden):
        async with sm() as s, s.begin():
            await companies.pay(s, emp, cid, emp, 100)
    with pytest.raises(Forbidden):
        async with sm() as s, s.begin():
            await market.place_bid(s, emp, cid, price=1, qty=1, resource="ore", location="rust")
    # Посторонний не может действовать от имени компании.
    with pytest.raises(Forbidden):
        async with sm() as s, s.begin():
            await market.place_bid(s, outsider, cid, price=1, qty=1, resource="ore", location="rust")
    # Владелец выдаёт право торговли.
    async with sm() as s, s.begin():
        await companies.toggle_permission(s, owner, cid, emp, Perm.TRADE)
    async with sm() as s, s.begin():
        await market.place_bid(s, emp, cid, price=10, qty=2, resource="ore", location="rust")
    assert (await bal(sm, cid)) == {"main": 230, "hold": 20}
    await ok(sm)


async def test_company_owns_assets_and_produces(sm):
    owner, cid = await setup_company(sm)
    emp = await make_user(sm, 2)
    async with sm() as s, s.begin():
        inv = await companies.invite(s, owner, cid, emp)
    async with sm() as s, s.begin():
        await companies.answer_invite(s, emp, inv.id, True)
    await give(sm, owner, "rust", "steel", 15)
    async with sm() as s, s.begin():
        await companies.transfer_resource(s, owner, owner, cid, "rust", "steel", 12)
    assert await qty(sm, cid, "rust", "steel") == 12
    # Сотрудник строит мастерскую из стали компании; мастерская принадлежит компании.
    async with sm() as s, s.begin():
        await production.start_craft(s, emp, cid, "build_workshop", "rust")
    from ironvein.services import clock
    clock.advance(minutes=31)
    from ironvein.jobs.runner import run_once
    await run_once(sm)
    ws = await user_items(sm, cid, "workshop")
    assert len(ws) == 1 and ws[0].owner_id == cid
    # Без права EQUIPMENT сотрудник не может забрать мастерскую себе.
    with pytest.raises(Forbidden):
        async with sm() as s, s.begin():
            await companies.transfer_item(s, emp, cid, emp, ws[0].id)


async def test_leave_kick_transfer_and_close_moves_assets_to_owner(sm):
    owner, cid = await setup_company(sm)
    m = await make_user(sm, 2)
    async with sm() as s, s.begin():
        inv = await companies.invite(s, owner, cid, m)
    async with sm() as s, s.begin():
        await companies.answer_invite(s, m, inv.id, True)
    with pytest.raises(Forbidden):
        async with sm() as s, s.begin():
            await companies.remove_member(s, owner, cid, owner)
    async with sm() as s, s.begin():
        await companies.transfer_ownership(s, owner, cid, m)
    async with sm() as s, s.begin():
        await companies.remove_member(s, owner, cid, owner)  # бывший владелец выходит сам
    async with sm() as s, s.begin():
        await companies.deposit(s, m, cid, 300)
    await give(sm, cid, "kotlo", "coal", 7)
    pick = (await user_items(sm, m, "pick"))[0].id
    async with sm() as s, s.begin():
        await companies.transfer_item(s, m, m, cid, pick)
    # Открытая заявка блокирует закрытие.
    async with sm() as s, s.begin():
        bid = await market.place_bid(s, m, cid, price=5, qty=2, resource="ore", location="rust")
    with pytest.raises(GameError, match="закройте"):
        async with sm() as s, s.begin():
            await companies.close(s, m, cid)
    async with sm() as s, s.begin():
        await market.cancel(s, m, bid.id)
    async with sm() as s, s.begin():
        await companies.close(s, m, cid)
    assert (await bal(sm, cid))["main"] == 0
    assert (await bal(sm, m))["main"] == 1000
    assert await qty(sm, m, "kotlo", "coal") == 7
    assert (await get_item(sm, pick)).owner_id == m
    await ok(sm)
