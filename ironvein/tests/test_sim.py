"""Экономический симулятор: короткие прогоны сценариев (без БД)."""

import pytest

from sim.engine import Config, Sim
from sim.scenarios import checks, scenarios


@pytest.mark.parametrize("name", ["baseline_10", "oil_shortage", "steel_monopoly", "liquidity_shortage",
                                  "mass_inactivity", "transport_bottleneck", "workshop_stop",
                                  "company_concentration", "premium_resale"])
def test_scenarios_keep_invariants(name):
    """Жёсткие инварианты для всех сценариев (Sim.run проверяет их на каждом шаге).

    Экономические проверки сценариев (восстановление, доля новичков) — это выводы для отчёта,
    они зависят от масштаба и печатаются `python -m sim`.
    """
    cfg = scenarios(scale=30, days=2)[name]
    rep = Sim(cfg).run()
    c = checks(name, rep)
    assert rep["money_conserved"] and c["money_conserved"]
    assert rep["burned"] >= 0


def test_industry_recovers_after_workshop_stop():
    rep = Sim(scenarios(scale=100, days=3)["workshop_stop"]).run()
    first, second = rep["halves"]["parts"]
    assert second > first


def test_liquidity_shortage_still_produces():
    rep = Sim(scenarios(scale=50, days=2)["liquidity_shortage"]).run()
    assert rep["produced"].get("steel", 0) > 0


def test_newcomer_bootstraps_from_starter_kit_only():
    rep = Sim(Config(players=10, ticks=6 * 12, inactive_share=0, trader_share=0)).run()
    assert rep["emitted"] == 10 * 1000  # единственный источник крон — стартовые выдачи
    assert rep["newbie_first_steel_median_h"] is not None
    assert rep["produced"].get("workshop", 0) > 0


def test_premium_resale_moves_crowns_without_creating_them():
    rep = Sim(Config(players=40, ticks=6 * 24, collectors=4, premium_items=10)).run()
    assert rep["money_conserved"] and rep["emitted"] == 40 * 1000
