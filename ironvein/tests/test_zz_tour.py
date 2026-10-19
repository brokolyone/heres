import os

import pytest

from ironvein.handlers.ui import Do, Nav
from ironvein.services import clock, market
from tests.helpers import give, give_item
from tests.test_bot_scenarios import Player, env  # noqa
from tests.test_transport import make_truck

pytestmark = pytest.mark.skipif(not os.environ.get("TOUR"), reason="ручная ревизия экранов")


async def test_tour(env, sm):  # noqa
    a, b = Player(env, 8001, "Ада Лавлейс"), Player(env, 8002, "Борис")
    await a.text("/start"); await b.text("/start")
    ua, ub = await a.db_id(sm), await b.db_id(sm)
    for r, q in (("ore", 40), ("coal", 30), ("steel", 60), ("diesel", 20), ("parts", 15), ("oil", 12)):
        await give(sm, ua, "rust", r, q)
    await give_item(sm, ua, "workshop"); await give_item(sm, ua, "smelter"); await give_item(sm, ua, "drill")
    truck = await make_truck(sm, ua)
    await give(sm, ub, "rust", "steel", 30)
    async with sm() as s, s.begin():
        o = await market.place_ask_resource(s, ub, ub, "rust", "steel", 20, 42)
    async with sm() as s, s.begin():
        await market.buy(s, ua, ua, o.id, 5)
        await market.place_bid(s, ua, ua, price=30, qty=10, resource="coal", location="rust")
    shots = []
    async def snap(p, cb=None, text=None):
        env.session.calls.clear()
        if text: await p.text(text)
        else: await p.press(cb)
        kbs = []
        for c in env.session.calls:
            rm = getattr(c, "reply_markup", None)
            if rm is not None and hasattr(rm, "inline_keyboard"):
                kbs = [" | ".join(b.text for b in row) for row in rm.inline_keyboard]
        shots.append("\n".join(t for t in env.texts() if t) + "\n[КНОПКИ]\n" + "\n".join(kbs))
    await snap(a, text="/start")
    await snap(a, Nav(s="guide"))
    await snap(a, Nav(s="profile"))
    await snap(a, Nav(s="inventory"))
    await snap(a, Nav(s="mine_loc", a="rust"))
    async with sm() as s:
        from sqlalchemy import select

        from ironvein.models import Deposit
        dep = await s.scalar(select(Deposit).where(Deposit.code == "rust_north"))
    await snap(a, Nav(s="mine_dep", a=str(dep.id)))
    await snap(a, Do(a="mine", x=dep.id, y=0, k="m1"))
    await snap(a, Nav(s="prod_cat", a="rust"))
    await snap(a, Nav(s="prod_rec", a="rust:smelt_steel"))
    await snap(a, Do(a="craft", x=2, z="rust:smelt_steel", k="c1"))
    await snap(a, Nav(s="production"))
    await snap(a, Nav(s="equipment"))
    await snap(a, Nav(s="item", a=str(truck)))
    await snap(a, Nav(s="mkt_loc", a="rust"))
    await snap(a, Nav(s="book", a="rust:steel"))
    await snap(a, Nav(s="my_orders"))
    await snap(a, Nav(s="trip_dest", a=f"{truck}:rust"))
    await snap(a, Do(a="trip_plan", x=truck, z="rust:kotlo", k="t1"))
    from ironvein.models import Shipment
    async with sm() as s:
        sh = await s.scalar(select(Shipment))
    await snap(a, Do(a="trip_max", x=sh.id, z="steel", k="t2"))
    await snap(a, Do(a="trip_go", x=sh.id, k="t3"))
    await snap(a, Nav(s="transport"))
    await snap(a, Nav(s="company"))
    await snap(a, Nav(s="contracts"))
    await snap(a, Nav(s="donate"))
    await snap(a, Nav(s="product", a="engineer_watch"))
    await snap(a, text="/help")
    print("\n\n######\n".join(shots))


async def test_tour_notify_admin(env, sm):  # noqa
    from ironvein.bot import make_notifier
    from ironvein.jobs.runner import run_once
    from ironvein.services import production
    from tests.helpers import deposit_id, user_items
    a = Player(env, 9001, "Админ")
    await a.text("/start")
    ua = await a.db_id(sm)
    pick = (await user_items(sm, ua, "pick"))[0]
    async with sm() as s, s.begin():
        await production.start_mining(s, ua, ua, await deposit_id(sm, "rust_coal3"), pick.id)
    clock.advance(minutes=15)
    env.session.calls.clear()
    await run_once(sm, make_notifier(env.bot))
    await a.text("/admin")
    await a.text("/admin_user 3")
    print("\n#####\n".join(env.texts()))
