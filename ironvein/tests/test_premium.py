import asyncio

import pytest
from sqlalchemy import update

from ironvein.domain.errors import GameError
from ironvein.models import PremiumProduct, User
from ironvein.services import clock, market, premium
from ironvein.services.metrics import integrity_report
from tests.conftest import make_user
from tests.helpers import bal, get_item


async def tg(sm, uid):
    async with sm() as s:
        return (await s.get(User, uid)).tg_id


async def buy_flow(sm, uid, code="engineer_watch", charge="ch-1"):
    async with sm() as s, s.begin():
        o = await premium.create_order(s, uid, code)
    t = await tg(sm, uid)
    async with sm() as s, s.begin():
        okk, err = await premium.pre_checkout(s, o.public_id, t, o.price_stars, "XTR")
    assert okk, err
    async with sm() as s, s.begin():
        o2 = await premium.successful_payment(s, o.public_id, t, o.price_stars, "XTR", charge)
    return o2


async def test_full_purchase_issues_serial_and_duplicate_update_ignored(sm):
    u = await make_user(sm, 1)
    o = await buy_flow(sm, u)
    assert o.status == "fulfilled"
    it = await get_item(sm, o.item_id)
    assert it.serial_no == 1 and it.owner_id == u and it.origin == "premium"
    t = await tg(sm, u)
    async with sm() as s, s.begin():
        again = await premium.successful_payment(s, o.public_id, t, 100, "XTR", "ch-1")
    assert again.id == o.id
    async with sm() as s:
        p = await s.get(PremiumProduct, "engineer_watch")
        assert p.issued == 1 and p.reserved == 0


async def test_precheckout_rejects_wrong_user_amount_and_currency(sm):
    u = await make_user(sm, 1)
    v = await make_user(sm, 2)
    async with sm() as s, s.begin():
        o = await premium.create_order(s, u, "syndicate_crest")
    for args in ((await tg(sm, v), 35, "XTR"), (await tg(sm, u), 1, "XTR"), (await tg(sm, u), 35, "USD")):
        async with sm() as s, s.begin():
            okk, err = await premium.pre_checkout(s, o.public_id, *args)
        assert not okk and err
    async with sm() as s, s.begin():
        okk, _ = await premium.pre_checkout(s, "iv-forged", await tg(sm, u), 35, "XTR")
    assert not okk


async def test_edition_limit_never_exceeded_under_concurrency(sm):
    async with sm() as s, s.begin():
        await s.execute(update(PremiumProduct).where(PremiumProduct.code == "engineer_watch").values(edition_limit=3))
    users_ = [await make_user(sm, 10 + i) for i in range(8)]

    async def attempt(u):
        try:
            async with sm() as s, s.begin():
                await premium.create_order(s, u, "engineer_watch")
                return 1
        except GameError:
            return 0
    got = await asyncio.gather(*[attempt(u) for u in users_])
    assert sum(got) == 3
    async with sm() as s:
        p = await s.get(PremiumProduct, "engineer_watch")
        assert p.reserved == 3 and p.issued == 0


async def test_payment_after_sellout_goes_to_refund(sm):
    async with sm() as s, s.begin():
        await s.execute(update(PremiumProduct).where(PremiumProduct.code == "engineer_watch").values(edition_limit=1))
    a = await make_user(sm, 1)
    b = await make_user(sm, 2)
    async with sm() as s, s.begin():
        slow = await premium.create_order(s, a, "engineer_watch")
    clock.advance(minutes=31)
    from ironvein.jobs.runner import run_once
    assert (await run_once(sm))["reservations_expired"] == 1
    fast = await buy_flow(sm, b, charge="ch-b")
    assert fast.status == "fulfilled"
    # Пользователь A всё же оплатил старый счёт (pre-checkout отклонит, но защищаемся и от гонки).
    async with sm() as s, s.begin():
        okk, err = await premium.pre_checkout(s, slow.public_id, await tg(sm, a), 100, "XTR")
    assert not okk and "распродан" in err
    async with sm() as s, s.begin():
        o = await premium.successful_payment(s, slow.public_id, await tg(sm, a), 100, "XTR", "ch-a")
    assert o.status == "refund_pending"
    refunded = []

    async def refund(tg_id, charge):
        refunded.append(charge)
        return True
    res = await run_once(sm, refund=refund)
    assert res["refunds"] == 1 and refunded == ["ch-a"]
    async with sm() as s:
        p = await s.get(PremiumProduct, "engineer_watch")
        assert p.issued == 1 and p.reserved == 0


async def test_crash_between_payment_and_fulfillment_is_retried(sm):
    u = await make_user(sm, 1)
    async with sm() as s, s.begin():
        o = await premium.create_order(s, u, "paint_black_brass")
    # Эмулируем падение: заказ оплачен, но выдача не произошла.
    from ironvein.models import PremiumOrder
    async with sm() as s, s.begin():
        await s.execute(update(PremiumOrder).where(PremiumOrder.id == o.id).values(status="paid", telegram_charge_id="x"))
    from ironvein.jobs.runner import run_once
    r = await run_once(sm)
    assert r["premium_retried"] == 1
    async with sm() as s:
        o2 = await s.get(PremiumOrder, o.id)
        assert o2.status == "fulfilled" and o2.item_id
    assert (await run_once(sm))["premium_retried"] == 0


async def test_resale_for_crowns_and_refund_locks_item(sm):
    a = await make_user(sm, 1)
    b = await make_user(sm, 2)
    o = await buy_flow(sm, a)
    # Продаём часы за 500 ₭ (у b стартовые 1000): 490 продавцу, 10 уничтожено.
    async with sm() as s, s.begin():
        ask = await market.place_ask_item(s, a, a, o.item_id, 500)
    async with sm() as s, s.begin():
        await market.buy(s, b, b, ask.id, 1)
    assert (await bal(sm, a))["main"] == 1490
    async with sm() as s:
        rep = await integrity_report(s)
    assert rep["ok"] and rep["emitted"] == 2000 and rep["burned"] == 10  # Stars не создали ни одной кроны
    # Возврат Stars после перепродажи: предмет блокируется у нового владельца.
    async with sm() as s, s.begin():
        await premium.mark_refunded(s, charge_id="ch-1", source="telegram")
    it = await get_item(sm, o.item_id)
    assert it.status == "locked" and it.owner_id == b
    with pytest.raises(GameError):
        async with sm() as s, s.begin():
            await market.place_ask_item(s, b, b, it.id, 100)
    async with sm() as s, s.begin():
        await premium.admin_unlock(s, a, it.id, "решено вручную")
    assert (await get_item(sm, it.id)).status == "idle"
