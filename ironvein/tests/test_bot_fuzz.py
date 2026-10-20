"""Фаззинг кнопок: каждый экран и каждое действие с мусорными и граничными аргументами.

Устаревшие/подделанные callback_data не должны приводить к необработанной ошибке."""

import re
from pathlib import Path

import pytest

from ironvein.handlers.ui import Do, Nav
from tests.helpers import give
from tests.test_bot_scenarios import BAD, Player, env  # noqa: F401  (фикстура)
from tests.test_transport import make_truck

SRC = Path(__file__).resolve().parents[1] / "ironvein" / "handlers"


def _names(kind: str) -> set[str]:
    found = set()
    for f in SRC.glob("*.py"):
        text = f.read_text()
        attr = "s" if kind == "Nav" else "a"
        found |= set(re.findall(rf'{kind}\.filter\(F\.{attr} == "(\w+)"\)', text))
        for group in re.findall(rf'{kind}\.filter\(F\.{attr}\.in_\(\{{([^}}]+)\}}\)\)', text):
            found |= set(re.findall(r'"(\w+)"', group))
    return found


NAV = sorted(_names("Nav"))
DO = sorted(_names("Do"))
ARGS = ["", "zzz", "1", "999999", "rust", "rust:steel", "rust:zzz", "0:rust", "1:rust", "1:2", "a:b:c:d", "-1"]


def test_handlers_discovered():
    assert len(NAV) > 25 and len(DO) > 35, (NAV, DO)


@pytest.mark.parametrize("screen", NAV)
async def test_nav_with_garbage(env, sm, screen):  # noqa: F811
    p = Player(env, 7001, "Фаззер")
    await p.text("/start")
    for a in ARGS:
        await p.press(Nav(s=screen, a=a))
        await p.press(Nav(s=screen, a=a), photo=True)


@pytest.mark.parametrize("action", DO)
async def test_do_with_garbage(env, sm, action):  # noqa: F811
    p = Player(env, 7002, "Фаззер")
    await p.text("/start")
    uid = await p.db_id(sm)
    truck = await make_truck(sm, uid)
    await give(sm, uid, "rust", "steel", 50)
    for x, y, z in [(0, 0, ""), (999999, 999999, "zzz"), (1, 1, "rust:steel"), (truck, truck, "rust:kotlo"),
                    (uid, uid, "1"), (-5, 0, "a:b:c"), (1, 0, "supply:steel:rust:"), (1, 0, "engineer_watch")]:
        await p.press(Do(a=action, x=x, y=y, z=z, k=f"f{x}{y}"))


INPUT_DATA = {
    "ask_place": {"loc": "rust", "res": "steel"}, "bid_place": {"loc": "rust", "res": "steel"},
    "buy_qty": {"order_id": 999999}, "sell_qty": {"order_id": 999999}, "cdeliver_qty": {"cid": 999999},
    "cdep_amount": {"cid": 999999}, "cdispute_reason": {"cid": 999999}, "cinv_user": {"cid": 999999},
    "cnew_terms": {"ctype": "supply", "res": "steel", "loc": "rust", "dest": None}, "comp_name": {},
    "cpay_amount": {"cid": 999999, "to": 1}, "cxfer_amount": {"src": 1, "dst": 2, "loc": "rust", "res": "steel"},
    "ibid_price": {"code": "engineer_watch", "loc": None}, "item_price": {"item_id": 999999},
    "support_msg": {}, "trip_qty": {"shipment_id": 999999, "resource": "steel"},
}
TEXTS = ["abc", "-5", "0", "9" * 30, "1 2 3", "10 5", "<b>x</b>", "@nobody", "1", "  7  ", "Я" * 300]


def test_every_input_kind_is_fuzzed():
    from ironvein.handlers.base import INPUTS
    assert set(INPUTS) == set(INPUT_DATA)


@pytest.mark.parametrize("kind", sorted(INPUT_DATA))
async def test_text_inputs_with_garbage(env, sm, kind):  # noqa: F811
    from ironvein.handlers.base import Input
    p = Player(env, 7003, "Вводящий")
    await p.text("/start")
    st = env.dp.fsm.resolve_context(env.bot, p.tg, p.tg)
    for t in TEXTS:
        await st.set_state(Input.value)
        await st.set_data({**INPUT_DATA[kind], "_input": kind})
        await p.text(t)
    await st.clear()


async def test_command_during_input_resets_it(env, sm):  # noqa: F811
    p = Player(env, 7004, "Передумал")
    await p.text("/start")
    await p.press(Do(a="ask", z="rust:steel"))
    env.session.calls.clear()
    await p.text("/profile")
    assert any("Профиль" in t for t in env.texts())
    env.session.calls.clear()
    await p.text("10 5")  # ввод уже отменён — это просто непонятный текст
    assert any("не понял" in t for t in env.texts())
