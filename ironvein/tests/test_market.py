import asyncio

import pytest

from ironvein.domain.errors import AlreadyDone, Forbidden, GameError
from ironvein.domain.money import fee_for
from ironvein.services import market
from ironvein.services.metrics import integrity_report
from tests.conftest import make_user
from tests.helpers import bal, get_item, give, give_item, qty


async def check(sm):
    async with sm() as s:
        rep = await integrity_report(s)
    assert rep["ok"], rep
    return rep


def test_fee_rounding_never_reduced_by_splitting():
    assert fee_for(5000, 200) == 100
    assert fee_for(1, 200) == 1
    assert fee_for(49, 200) == 1
    assert fee_for(51, 200) == 2
    for total in (7, 99, 1234, 5000):
        whole = fee_for(total, 200)
        split = sum(fee_for(1, 200) for _ in range(total))
        assert split >= whole


async def test_ask_partial_fill_fee_burned_and_goods_move(sm):
    a = await make_user(sm, 1)
    b = await make_user(sm, 2)
    await give(sm, a, "rust", "steel", 10)
    async with sm() as s, s.begin():
        ask = await market.place_ask_resource(s, a, a, "rust", "steel", 10, 30)
    assert await qty(sm, a, "rust", "steel") == 0 and await qty(sm, a, "rust", "steel", held=True) == 10
    async with sm() as s, s.begin():
        t = await market.buy(s, b, b, ask.id, 4)
    assert t.gross == 120 and t.fee == 3
    assert (await bal(sm, a))["main"] == 1000 + 117
    assert (await bal(sm, b))["main"] == 1000 - 120
    assert await qty(sm, b, "rust", "steel") == 4
    async with sm() as s, s.begin():
        await market.cancel(s, a, ask.id)
    assert await qty(sm, a, "rust", "steel") == 6
    rep = await check(sm)
    assert rep["burned"] == 3


async def test_bid_reserves_and_seller_fills(sm):
    a = await make_user(sm, 1)
    b = await make_user(sm, 2)
    async with sm() as s, s.begin():
        bid = await market.place_bid(s, b, b, price=50, qty=5, resource="ore", location="rust")
    assert (await bal(sm, b)) == {"main": 750, "hold": 250}
    await check(sm)
    await give(sm, a, "rust", "ore", 3)
    async with sm() as s, s.begin():
        await market.sell(s, a, a, bid.id, 3)
    assert (await bal(sm, b)) == {"main": 750, "hold": 100}
    assert (await bal(sm, a))["main"] == 1000 + 150 - 3
    assert await qty(sm, b, "rust", "ore") == 3
    async with sm() as s, s.begin():
        await market.cancel(s, b, bid.id)
    assert (await bal(sm, b)) == {"main": 850, "hold": 0}
    await check(sm)


async def test_bid_insufficient_funds(sm):
    b = await make_user(sm, 2)
    with pytest.raises(GameError, match="Недостаточно"):
        async with sm() as s, s.begin():
            await market.place_bid(s, b, b, price=500, qty=5, resource="ore", location="rust")


async def test_self_trade_forbidden(sm):
    a = await make_user(sm, 1)
    await give(sm, a, "rust", "steel", 2)
    async with sm() as s, s.begin():
        ask = await market.place_ask_resource(s, a, a, "rust", "steel", 2, 10)
    with pytest.raises(Forbidden):
        async with sm() as s, s.begin():
            await market.buy(s, a, a, ask.id, 1)


async def test_concurrent_buyers_cannot_oversell(sm):
    seller = await make_user(sm, 1)
    buyers = [await make_user(sm, 10 + i) for i in range(8)]
    await give(sm, seller, "rust", "coal", 5)
    async with sm() as s, s.begin():
        ask = await market.place_ask_resource(s, seller, seller, "rust", "coal", 5, 10)

    async def attempt(b):
        try:
            async with sm() as s, s.begin():
                await market.buy(s, b, b, ask.id, 2)
                return 2
        except GameError:
            return 0
    got = await asyncio.gather(*[attempt(b) for b in buyers])
    assert sum(got) == 4  # 2+2, затем осталось 1 < 2
    assert await qty(sm, seller, "rust", "coal", held=True) == 1
    await check(sm)


async def test_unique_item_sale_and_double_sale_prevention(sm):
    a = await make_user(sm, 1)
    b = await make_user(sm, 2)
    c = await make_user(sm, 3)
    w = await give_item(sm, a, "engineer_watch", None, serial_no=7)
    async with sm() as s, s.begin():
        ask = await market.place_ask_item(s, a, a, w, 400)
    with pytest.raises(GameError):
        async with sm() as s, s.begin():
            await market.place_ask_item(s, a, a, w, 300)
    async with sm() as s, s.begin():
        await market.buy(s, b, b, ask.id, 5)
    it = await get_item(sm, w)
    assert it.owner_id == b and it.status == "idle"
    with pytest.raises(GameError):
        async with sm() as s, s.begin():
            await market.buy(s, c, c, ask.id, 1)
    assert (await bal(sm, a))["main"] == 1000 + 400 - 8
    await check(sm)


async def test_bid_for_item_filled_by_owner(sm):
    a = await make_user(sm, 1)
    b = await make_user(sm, 2)
    w = await give_item(sm, a, "syndicate_crest", None, serial_no=1)
    async with sm() as s, s.begin():
        bid = await market.place_bid(s, b, b, price=300, qty=1, item_def="syndicate_crest")
    async with sm() as s, s.begin():
        await market.sell(s, a, a, bid.id, 1, item_id=w)
    assert (await get_item(sm, w)).owner_id == b
    assert (await bal(sm, b)) == {"main": 700, "hold": 0}
    await check(sm)


async def test_repeat_button_press_does_not_double_buy(sm):
    a = await make_user(sm, 1)
    b = await make_user(sm, 2)
    await give(sm, a, "rust", "steel", 10)
    async with sm() as s, s.begin():
        ask = await market.place_ask_resource(s, a, a, "rust", "steel", 10, 30)
    async with sm() as s, s.begin():
        await market.buy(s, b, b, ask.id, 1, op_key="cb:42")
    with pytest.raises(AlreadyDone):
        async with sm() as s, s.begin():
            await market.buy(s, b, b, ask.id, 1, op_key="cb:42")
    assert await qty(sm, b, "rust", "steel") == 1


async def test_book_shows_no_price_without_trades(sm):
    async with sm() as s:
        bk = await market.book(s, resource="steel", location="rust")
    assert bk["last"] is None and bk["volume_qty"] == 0
