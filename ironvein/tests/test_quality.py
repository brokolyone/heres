"""Качество крафта: детерминированность, влияние решений игрока, эффект только на прочность."""

import pytest
from sqlalchemy import update

from ironvein.domain import quality
from ironvein.domain.errors import GameError
from ironvein.models import Item, Job
from ironvein.services import clock, production
from ironvein.services.items import quality_of, quality_score
from tests.conftest import make_user
from tests.helpers import get_item, give, give_item, user_items
from tests.test_production import run_due


def test_tiers_and_roll_are_deterministic_and_bounded():
    assert quality.tier_for(0).code == "flawed" and quality.tier_for(39).code == "flawed"
    assert quality.tier_for(40).code == "common" and quality.tier_for(60).code == "good"
    assert quality.tier_for(75).code == "fine" and quality.tier_for(90).code == "master"
    rolls = [quality.roll(i) for i in range(2000)]
    assert min(rolls) == -quality.ROLL_SPREAD and max(rolls) == quality.ROLL_SPREAD
    assert quality.roll(42) == quality.roll(42)
    # С разными серверными секретами исходы разные: формула из кода не позволяет предсказать бросок.
    assert [quality.roll(i, b"a") for i in range(50)] != [quality.roll(i, b"b") for i in range(50)]
    # Разброс почти равномерный: каждое значение встречается.
    assert len(set(rolls)) == 2 * quality.ROLL_SPREAD + 1


def test_breakdown_reflects_player_decisions():
    fresh = quality.breakdown(1.0, 0, 0, careful=False)
    worn = quality.breakdown(0.2, 0, 0, careful=False)
    expert = quality.breakdown(1.0, 10, 10, careful=False)
    careful = quality.breakdown(1.0, 0, 0, careful=True)
    assert fresh.base > worn.base
    assert expert.base == fresh.base + quality.EXPERIENCE_MAX_BONUS
    assert careful.base == fresh.base + quality.CAREFUL_BONUS
    best = quality.breakdown(1.0, 10, 10, careful=True)
    assert best.expected()[0].code in ("fine", "master")  # опыт + тщательность + новая мастерская
    assert quality.breakdown(None, 0, 0, False).expected()[0].code == "common"  # новичок руками не делает брак
    assert quality.module_bonus([90, 90, 90, 90]) > 0 > quality.module_bonus([20, 20, 20, 20])


def test_durability_is_the_only_effect():
    for t in quality.TIERS:
        assert 0.8 <= t.durability_mult <= 1.3
    assert quality.scaled_durability(100, quality.TIER_BY_CODE["master"]) == 130
    assert quality.scaled_durability(0, quality.TIER_BY_CODE["master"]) == 0


async def craft_item(sm, u, recipe, loc="rust", careful=False, facility=None):
    async with sm() as s, s.begin():
        job = await production.start_craft(s, u, u, recipe, loc, facility_id=facility, careful=careful)
    clock.advance(hours=2)
    await run_due(sm)
    async with sm() as s:
        j = await s.get(Job, job.id)
    return j, await get_item(sm, j.result["item_id"])


async def test_crafted_item_gets_quality_and_scaled_durability_once(sm):
    u = await make_user(sm, 1)
    await give(sm, u, "rust", "steel", 2)
    job, pick = await craft_item(sm, u, "craft_pick")
    tier = quality_of(pick)
    from ironvein.config import get_settings
    key = get_settings().quality_key()
    assert tier is not None and pick.attrs["quality"]["score"] == quality.final_score(job.params["q_base"], job.id, key)
    assert pick.max_durability == quality.scaled_durability(60, tier) == pick.durability
    # Повторное завершение не создаёт второй предмет и не меняет качество.
    async with sm() as s, s.begin():
        assert not await production.complete_job(s, job.id)
    assert len([p for p in await user_items(sm, u, "pick") if p.origin == "craft"]) == 1


async def test_worn_workshop_lowers_and_careful_raises_quality_and_time(sm):
    u = await make_user(sm, 1)
    ws = await give_item(sm, u, "workshop")
    await give(sm, u, "rust", "steel", 100)
    await give(sm, u, "rust", "parts", 50)
    async with sm() as s, s.begin():
        quick = await production.start_craft(s, u, u, "build_tank", "rust", facility_id=ws)
    clock.advance(hours=1)
    await run_due(sm)
    async with sm() as s, s.begin():
        await s.execute(update(Item).where(Item.id == ws).values(durability=15))  # 10% прочности
    async with sm() as s, s.begin():
        worn = await production.start_craft(s, u, u, "build_tank", "rust", facility_id=ws)
    clock.advance(hours=1)
    await run_due(sm)
    async with sm() as s, s.begin():
        careful = await production.start_craft(s, u, u, "build_tank", "rust", facility_id=ws, careful=True)
    assert worn.params["q_base"] < quick.params["q_base"]
    # К третьему баку: мастерская 14/150 (−1 за предыдущий запуск), опыт — два бака этого рецепта.
    assert careful.params["q_base"] == quality.breakdown(14 / 150, 2, 0, careful=True).base
    assert careful.params["careful"] is True
    normal_len = worn.finishes_at - worn.started_at
    careful_len = careful.finishes_at - careful.started_at
    assert abs((careful_len - normal_len * quality.CAREFUL_TIME_MULT).total_seconds()) < 1


async def test_experience_grows_with_completed_crafts(sm):
    u = await make_user(sm, 1)
    await give(sm, u, "rust", "steel", 20)
    bases = []
    for _ in range(3):
        job, _ = await craft_item(sm, u, "craft_pick")
        bases.append(job.params["q_base"])
    assert bases[0] < bases[1] < bases[2]


async def test_careful_only_for_items(sm):
    u = await make_user(sm, 1)
    await give(sm, u, "rust", "ore", 8)
    await give(sm, u, "rust", "coal", 6)
    with pytest.raises(GameError, match="Тщательная"):
        async with sm() as s, s.begin():
            await production.start_craft(s, u, u, "forge_steel", "rust", careful=True)


async def test_truck_quality_includes_module_quality(sm):
    u = await make_user(sm, 1)
    await give_item(sm, u, "workshop")
    await give(sm, u, "rust", "parts", 4)
    good = {"quality": {"score": 95, "tier": "master"}}
    bad = {"quality": {"score": 10, "tier": "flawed"}}
    best_mods = [await give_item(sm, u, c, attrs=good) for c in ("chassis", "engine_d8", "tank", "body_cargo")]
    worst_mods = [await give_item(sm, u, c, attrs=bad) for c in ("chassis", "engine_d8", "tank", "body_cargo")]
    async with sm() as s, s.begin():
        j1 = await production.start_craft(s, u, u, "assemble_truck", "rust", module_ids=best_mods)
    clock.advance(hours=1)
    await run_due(sm)
    async with sm() as s, s.begin():
        j2 = await production.start_craft(s, u, u, "assemble_truck", "rust", module_ids=worst_mods)
    clock.advance(hours=1)
    await run_due(sm)
    assert j1.params["q_base"] - j2.params["q_base"] >= 30
    trucks = await user_items(sm, u, "truck")
    assert trucks[0].max_durability > trucks[1].max_durability


async def test_items_without_quality_count_as_common(sm):
    u = await make_user(sm, 1)
    pick = (await user_items(sm, u, "pick"))[0]  # стартовая кирка
    assert quality_of(pick) is None and quality_score(pick) == quality.COMMON_SCORE


async def test_facility_auto_selection_prefers_condition(sm):
    """Новая мастерская 100/150 (67%) лучше изношенной высококачественной 120/195 (62%) — по состоянию, не по числу."""
    u = await make_user(sm, 1)
    big = await give_item(sm, u, "workshop", max_durability=195)
    small = await give_item(sm, u, "workshop")
    async with sm() as s, s.begin():
        await s.execute(update(Item).where(Item.id == big).values(durability=120))
        await s.execute(update(Item).where(Item.id == small).values(durability=100))
    async with sm() as s:
        assert await production.find_idle_facility(s, u, "rust", "workshop") == small
        # Но если износ запуска больше остатка, берётся та, что выдержит.
        assert await production.find_idle_facility(s, u, "rust", "workshop", min_durability=110) == big


def test_labels_for_flawed_and_buttons():
    from ironvein.models import Item as It
    from ironvein.services.items import button_title, title
    flawed = It(id=7, def_code="drill", attrs={"quality": {"score": 10, "tier": "flawed"}})
    master = It(id=8, def_code="engine_d12", attrs={"quality": {"score": 95, "tier": "master"}})
    assert quality.stars(quality.TIER_BY_CODE["flawed"]) == "✗"
    assert title(flawed).endswith("✗") and "брак" not in title(flawed)
    b = button_title(master, 14)
    assert b.startswith("★★★★") and b.endswith("#8") and len(b) <= 14 + 1
