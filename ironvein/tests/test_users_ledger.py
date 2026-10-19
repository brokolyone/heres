import asyncio

import pytest
from sqlalchemy import func, select, text

from ironvein.models import User
from ironvein.services import ledger, users
from ironvein.services.metrics import integrity_report
from tests.conftest import make_user
from tests.helpers import bal, user_items


async def test_registration_grants_starter_once(sm):
    uid = await make_user(sm, 100)
    assert (await bal(sm, uid))["main"] == 1000
    picks = await user_items(sm, uid, "pick")
    assert len(picks) == 1 and picks[0].location_code == "rust"
    # Повторная регистрация и повторная попытка выдачи ничего не дают.
    async with sm() as s, s.begin():
        u, created = await users.get_or_register(s, 100, "Игрок")
        assert not created
        assert not await users.grant_starter(s, uid)
    assert (await bal(sm, uid))["main"] == 1000
    assert len(await user_items(sm, uid, "pick")) == 1


async def test_concurrent_registration_single_account(sm):
    async def reg():
        async with sm() as s, s.begin():
            u, _ = await users.get_or_register(s, 555, "Гонщик")
            return u.id
    ids = await asyncio.gather(*[reg() for _ in range(8)])
    assert len(set(ids)) == 1
    async with sm() as s:
        assert await s.scalar(select(func.count()).select_from(User)) == 1
    assert (await bal(sm, ids[0]))["main"] == 1000
    rep = await _integrity(sm)
    assert rep["emitted"] == 1000


async def test_transfer_conserves_money_and_rejects_overdraft(sm):
    a = await make_user(sm, 1)
    b = await make_user(sm, 2)
    async with sm() as s, s.begin():
        await ledger.transfer(s, "test", 300, (a, "main"), (b, "main"))
    assert (await bal(sm, a))["main"] == 700 and (await bal(sm, b))["main"] == 1300
    with pytest.raises(ledger.InsufficientFunds):
        async with sm() as s, s.begin():
            await ledger.transfer(s, "test", 5000, (a, "main"), (b, "main"))
    assert (await bal(sm, a))["main"] == 700
    rep = await _integrity(sm)
    assert rep["ok"], rep


async def test_unbalanced_ledger_rejected_by_database(sm):
    a = await make_user(sm, 1)
    async with sm() as s:
        w = await ledger.wallet(s, a)
    with pytest.raises(Exception, match="not balanced"):
        async with sm() as s, s.begin():
            tx = (await s.execute(text("insert into ledger_tx(kind) values ('hack') returning id"))).scalar()
            await s.execute(text(f"insert into ledger_entries(tx_id,wallet_id,delta,balance_after) values ({tx},{w},50,1050)"))


async def test_negative_balance_blocked_by_check(sm):
    from sqlalchemy.exc import IntegrityError
    a = await make_user(sm, 1)
    with pytest.raises(IntegrityError, match="non_negative"):
        async with sm() as s, s.begin():
            await s.execute(text(f"update wallets set balance = -1 where account_id = {a} and kind='main'"))


async def _integrity(sm):
    async with sm() as s:
        return await integrity_report(s)
