"""Сценарии экономической симуляции и проверки здоровья экономики."""

from sim.engine import Config, Sim

DAY = 6 * 24


def scenarios(scale: int = 100, days: int = 3) -> dict[str, Config]:
    t = DAY * days
    return {
        "baseline_10": Config(players=10, ticks=t),
        "baseline_100": Config(players=100, ticks=t),
        "baseline_1000": Config(players=1000, ticks=t),
        "oil_shortage": Config(players=scale, ticks=t, deposit_scale={"oil": 0.05}, crisis_until=t // 2),
        "steel_monopoly": Config(players=scale, ticks=t, monopolist=True),
        "liquidity_shortage": Config(players=scale, ticks=t, starter_cash=50),
        "mass_inactivity": Config(players=scale, ticks=t, inactive_share=0.8),
        "transport_bottleneck": Config(players=scale, ticks=t, no_trucks=True),
        "workshop_stop": Config(players=scale, ticks=t, workshops_broken=True, crisis_until=t // 2),
        "company_concentration": Config(players=scale, ticks=t, company_size=max(2, scale // 5)),
        "premium_resale": Config(players=scale, ticks=t, collectors=max(1, scale // 20), premium_items=scale // 5),
    }


def run(name: str, cfg: Config) -> dict:
    rep = Sim(cfg).run()
    rep["scenario"] = name
    rep["checks"] = checks(name, rep)
    return rep


def checks(name: str, r: dict) -> dict[str, bool]:
    c = {
        "money_conserved": r["money_conserved"],
        "emission_only_starters": r["emitted"] > 0,
        "fees_burned": r["burned"] >= 0,
    }
    if name.startswith("baseline") or name in ("transport_bottleneck", "company_concentration", "premium_resale",
                                               "steel_monopoly"):
        c["newbies_make_steel_without_npc"] = r["newbie_steel_share"] > 0.5
    if name in ("oil_shortage", "workshop_stop"):
        # После снятия кризиса пострадавшая отрасль восстанавливается: во второй половине выпуск не ниже первой.
        first, second = r["halves"]["diesel" if name == "oil_shortage" else "parts"]
        c["recovers_after_crisis"] = second >= first
    if name == "liquidity_shortage":
        c["economy_runs_on_labor"] = r["produced"].get("steel", 0) > 0
    if name == "premium_resale":
        c["premium_creates_no_crowns"] = r["money_conserved"]
    return c


def format_report(r: dict) -> str:
    lines = [f"== {r['scenario']} ({r['players']} игроков, {r['ticks'] * 10 // 60} ч)"]
    lines.append(f"эмиссия {r['emitted']} ₭, уничтожено {r['burned']} ₭, Джини {r['gini']}, "
                 f"доля крупнейшего владельца {r['top_firm_share']:.1%}")
    p = r["produced"]
    lines.append("выпуск: " + ", ".join(f"{k} {v}" for k, v in sorted(p.items())))
    lines.append(f"оборудование: {r['equipment']}, грузовики {r['trucks']}, рейсы вкл. пешие {r['shipments']}, дизель на ход {r['fuel_used']}")
    lines.append("VWAP: " + (", ".join(f"{k} {v}" for k, v in sorted(r["vwap"].items())) or "сделок нет"))
    lines.append(f"новички: сталь у {r['newbie_steel_share']:.0%} (медиана {r['newbie_first_steel_median_h']} ч), "
                 f"мастерская у {r['newbie_workshop_share']:.0%} (медиана {r['newbie_first_workshop_median_h']} ч)")
    lines.append("по половинам срока: " + ", ".join(f"{k} {a}→{b}" for k, (a, b) in r["halves"].items()))
    lines.append("проверки: " + ", ".join(f"{k}={'OK' if v else 'FAIL'}" for k, v in r["checks"].items()))
    return "\n".join(lines)
