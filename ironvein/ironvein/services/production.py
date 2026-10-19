"""Добыча, производство, ремонт. Все процессы — серверные задания, независимые от онлайна игрока.

Правила:
- входы, топливо и запас месторождения списываются/резервируются атомарно при старте;
- износ установки применяется при старте (одна прочность не используется дважды);
- выдача результата выполняется ровно один раз (условный переход running -> completed под блокировкой);
- отмена возвращает сырьё и запас месторождения, но не топливо и не износ.
"""

import math

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ironvein.config import get_settings
from ironvein.domain import quality
from ironvein.domain.catalog import (
    BARE_HANDS_YIELD,
    ITEMS,
    KIND_MODULE,
    MANUAL_SHIFT_MINUTES,
    RECIPES,
    REPAIR,
    SLOT_BY_NAME,
    item_name,
    resource_name,
)
from ironvein.domain.errors import Forbidden, GameError, NotFound
from ironvein.domain.permissions import Perm
from ironvein.domain.vehicles import truck_stats
from ironvein.models import (
    ITEM_BUSY,
    ITEM_IDLE,
    ITEM_INSTALLED,
    JOB_CANCELLED,
    JOB_COMPLETED,
    JOB_RUNNING,
    Item,
    Job,
)
from ironvein.services import authz, clock, items, stock
from ironvein.services.common import audit, claim_operation
from ironvein.services.world import lock_deposit

ITEM_RECIPES = tuple(code for code, r in RECIPES.items() if r.output_item)  # рецепты, выпускающие предметы


async def _new_job(session: AsyncSession, **kw) -> Job:
    now = clock.now()
    job = Job(status=JOB_RUNNING, started_at=now, finishes_at=now + clock.game_minutes(kw.pop("minutes")), **kw)
    session.add(job)
    try:
        async with session.begin_nested():
            await session.flush()
    except IntegrityError:
        raise GameError("У вас уже идёт ручная работа — рабочие руки одни. Дождитесь окончания смены.") from None
    return job


def _wear_check(item: Item, wear: int) -> None:
    if item.durability < wear:
        raise GameError(f"«{items.title(item)}» изношен: прочность {item.durability}/{item.max_durability}, "
                        f"нужно {wear}. Требуется ремонт.")


# --- Добыча ------------------------------------------------------------------------------------------


async def start_mining(session: AsyncSession, user_id: int, account_id: int, deposit_id: int,
                       tool_id: int | None = None, runs: int = 1, op_key: str | None = None) -> Job:
    """tool_id=None — голыми руками. Ручной инструмент — ручная смена. Буровая/качалка — механизированная."""
    await authz.require(session, user_id, account_id, Perm.PRODUCE)
    await claim_operation(session, op_key, "mine", user_id)
    dep = await lock_deposit(session, deposit_id)
    loc = dep.location_code
    tool = None
    manual = True
    fuel = 0
    if tool_id is None:
        per_cycle = BARE_HANDS_YIELD.get(dep.resource, 0)
        minutes = MANUAL_SHIFT_MINUTES
        cycles, wear = 1, 0
    else:
        tool = await items.lock_owned(session, tool_id, account_id)
        d = ITEMS[tool.def_code]
        if dep.resource not in d.mine:
            raise GameError(f"«{d.name}» не добывает {resource_name(dep.resource).lower()}.")
        if tool.location_code != loc:
            raise GameError(f"«{items.title(tool)}» находится не в этой локации. Перевезите его.")
        per_cycle = d.mine[dep.resource]
        manual = d.mine_fuel == 0
        cycles = 1 if manual else max(1, min(runs, 12))
    if per_cycle <= 0:
        raise GameError("Этот ресурс нельзя добыть таким способом.")
    if dep.stock <= 0:
        raise GameError(f"Месторождение «{dep.name}» истощено. Запас восстанавливается {dep.regen_per_hour}/ч.")
    amount = min(per_cycle * cycles, dep.stock)
    if tool is not None:
        d = ITEMS[tool.def_code]
        cycles = math.ceil(amount / per_cycle)
        wear = d.mine_wear * cycles
        fuel = d.mine_fuel * cycles
        minutes = d.mine_minutes * cycles if not manual else MANUAL_SHIFT_MINUTES
        _wear_check(tool, wear)
    await stock.ensure_capacity(session, account_id, loc, amount)
    if fuel:
        await stock.take(session, account_id, loc, "diesel", fuel, "fuel_mining", actor=user_id)
    dep.stock -= amount
    if tool is not None:
        tool.durability -= wear
        tool.status = ITEM_BUSY
    job = await _new_job(
        session, kind="mine", owner_id=account_id, actor_user_id=user_id, location_code=loc, runs=cycles,
        manual=manual, equipment_id=tool.id if tool else None, deposit_id=dep.id, minutes=minutes,
        inputs={"diesel": fuel} if fuel else {}, outputs={dep.resource: amount},
    )
    await audit(session, "mine_start", actor_user_id=user_id, account_id=account_id, target_type="job",
                target_id=job.id, deposit=dep.code, amount=amount, fuel=fuel, wear=wear)
    return job


# --- Производство ------------------------------------------------------------------------------------


async def craft_experience(session: AsyncSession, user_id: int, recipe_code: str) -> tuple[int, int]:
    """(изделий этого рецепта, прочих изделий) — завершённые крафты предметов этим мастером."""
    rows = (await session.execute(
        select(Job.recipe_code, func.count()).where(Job.actor_user_id == user_id, Job.kind == "craft",
                                                    Job.status == JOB_COMPLETED, Job.recipe_code.in_(ITEM_RECIPES))
        .group_by(Job.recipe_code))).all()
    same = sum(n for code, n in rows if code == recipe_code)
    return same, sum(n for _, n in rows) - same


async def quality_preview(session: AsyncSession, user_id: int, recipe_code: str, *, facility: Item | None,
                          modules: list[Item] | None = None, careful: bool = False) -> quality.Breakdown | None:
    """Разбор будущего качества изделия; None — рецепт выпускает ресурсы, а не предмет."""
    rec = RECIPES[recipe_code]
    if not rec.output_item:
        return None
    condition = None
    if rec.facility is not None:
        condition = facility.durability / facility.max_durability if facility and facility.max_durability else 0.0
    same, other = await craft_experience(session, user_id, recipe_code)
    scores = [items.quality_score(m) for m in modules] if modules else None
    return quality.breakdown(condition, same, other, careful, scores)


async def start_craft(session: AsyncSession, user_id: int, account_id: int, recipe_code: str, location: str,
                      runs: int = 1, facility_id: int | None = None, module_ids: list[int] | None = None,
                      op_key: str | None = None, careful: bool = False) -> Job:
    await authz.require(session, user_id, account_id, Perm.PRODUCE)
    rec = RECIPES.get(recipe_code)
    if rec is None:
        raise NotFound("Рецепт не найден.")
    if not 1 <= runs <= rec.max_runs:
        raise GameError(f"Количество запусков: от 1 до {rec.max_runs}.")
    if rec.item_inputs:
        await authz.require(session, user_id, account_id, Perm.EQUIPMENT)
    if careful and not rec.output_item:
        raise GameError("Тщательная работа доступна только для изделий.")
    await claim_operation(session, op_key, "craft", user_id)
    facility = None
    if rec.facility is not None:
        if facility_id is None:
            facility_id = await find_idle_facility(session, account_id, location, rec.facility,
                                                   min_durability=max(1, rec.wear * runs))
            if facility_id is None:
                raise GameError(f"Нужна свободная установка «{_facility_name(rec.facility)}» в этой локации.")
        facility = await items.lock_owned(session, facility_id, account_id)
        if ITEMS[facility.def_code].facility != rec.facility:
            raise GameError(f"Рецепт требует установку «{_facility_name(rec.facility)}».")
        if facility.location_code != location:
            raise GameError("Установка находится в другой локации.")
        _wear_check(facility, rec.wear * runs)

    consumed: list[int] = []
    modules: list[Item] = []
    if rec.item_inputs:
        module_ids = module_ids or []
        if len(module_ids) != len(rec.item_inputs):
            raise GameError("Для сборки нужны: шасси, двигатель, бак и кузов.")
        slots = set()
        for mid in sorted(module_ids):
            m = await items.lock_owned(session, mid, account_id)
            d = ITEMS[m.def_code]
            if d.kind != KIND_MODULE or m.location_code != location:
                raise GameError(f"«{items.title(m)}» не подходит или находится в другой локации.")
            slots.add(d.stats["slot"])
            m.status = ITEM_BUSY
            consumed.append(m.id)
            modules.append(m)
        if slots != {SLOT_BY_NAME[n] for n in rec.item_inputs}:
            raise GameError("Нужно по одному модулю каждого типа: шасси, двигатель, бак, кузов.")

    # Качество считается до износа установки: важна её форма на момент начала работы.
    q = await quality_preview(session, user_id, rec.code, facility=facility, modules=modules, careful=careful)
    params = {"q_base": q.base, "careful": careful} if q is not None else {}
    minutes = rec.minutes * runs * (quality.CAREFUL_TIME_MULT if careful else 1)
    inputs = {r: q_ * runs for r, q_ in rec.inputs.items()}
    outputs = {r: q_ * runs for r, q_ in rec.outputs.items()}
    net = sum(outputs.values()) - sum(inputs.values())
    if net > 0:
        await stock.ensure_capacity(session, account_id, location, net)
    for r, q in sorted(inputs.items()):
        await stock.take(session, account_id, location, r, q, "craft_input", actor=user_id)
    if facility is not None:
        facility.durability -= rec.wear * runs
        facility.status = ITEM_BUSY
    job = await _new_job(
        session, kind="craft", owner_id=account_id, actor_user_id=user_id, location_code=location,
        recipe_code=rec.code, runs=runs, manual=rec.facility is None, equipment_id=facility.id if facility else None,
        minutes=minutes, inputs=inputs, outputs=outputs, consumed_items=consumed, params=params,
    )
    await audit(session, "craft_start", actor_user_id=user_id, account_id=account_id, target_type="job",
                target_id=job.id, recipe=rec.code, runs=runs, careful=careful, q_base=params.get("q_base"))
    return job


def _facility_name(f: str) -> str:
    return {"workshop": "Мастерская", "smelter": "Плавильня", "refinery": "НПЗ"}.get(f, f)


async def find_idle_facility(session: AsyncSession, owner_id: int, location: str, facility: str,
                             min_durability: int = 1) -> int | None:
    """Свободная установка с лучшим состоянием (доля прочности влияет на качество), способная выдержать износ."""
    codes = [c for c, d in ITEMS.items() if d.facility == facility]
    condition = Item.durability * 1.0 / func.nullif(Item.max_durability, 0)
    return await session.scalar(
        select(Item.id).where(Item.owner_id == owner_id, Item.location_code == location, Item.status == ITEM_IDLE,
                              Item.def_code.in_(codes), Item.durability >= min_durability)
        .order_by(condition.desc().nulls_last(), Item.durability.desc(), Item.id).limit(1))


# --- Ремонт ------------------------------------------------------------------------------------------


async def start_repair(session: AsyncSession, user_id: int, account_id: int, item_id: int, steps: int = 1,
                       op_key: str | None = None) -> Job:
    await authz.require(session, user_id, account_id, Perm.EQUIPMENT)
    await claim_operation(session, op_key, "repair", user_id)
    target = await items.lock_owned(session, item_id, account_id)
    rule = REPAIR.get(target.def_code)
    if rule is None:
        raise GameError("Этот предмет не ремонтируется.")
    missing = target.max_durability - target.durability
    if missing <= 0:
        raise GameError("Ремонт не требуется.")
    steps = max(1, min(steps, math.ceil(missing / rule.restore)))
    loc = target.location_code
    workshop = None
    if rule.needs_workshop:
        ws_id = await find_idle_facility(session, account_id, loc, "workshop")
        if ws_id is None:
            raise GameError("Для ремонта нужна ваша свободная мастерская в той же локации.")
        workshop = await items.lock_owned(session, ws_id, account_id)
        _wear_check(workshop, 1)
        workshop.durability -= 1
        workshop.status = ITEM_BUSY
    inputs = {r: q * steps for r, q in rule.inputs.items()}
    for r, q in sorted(inputs.items()):
        await stock.take(session, account_id, loc, r, q, "repair_input", actor=user_id)
    target.status = ITEM_BUSY
    manual = not rule.needs_workshop and ITEMS[target.def_code].facility is None
    job = await _new_job(
        session, kind="repair", owner_id=account_id, actor_user_id=user_id, location_code=loc, runs=steps,
        manual=manual, equipment_id=workshop.id if workshop else None, target_item_id=target.id,
        minutes=rule.minutes * steps, inputs=inputs, outputs={"durability": min(missing, rule.restore * steps)},
    )
    await audit(session, "repair_start", actor_user_id=user_id, account_id=account_id, target_type="item",
                target_id=target.id, steps=steps)
    return job


# --- Завершение и отмена -----------------------------------------------------------------------------


async def _lock_job(session: AsyncSession, job_id: int) -> Job | None:
    return (await session.execute(select(Job).where(Job.id == job_id).with_for_update()
                                  .execution_options(populate_existing=True))).scalar_one_or_none()


async def _free_item(session: AsyncSession, item_id: int | None) -> None:
    if item_id is None:
        return
    it = await items.lock(session, item_id)
    if it.status == ITEM_BUSY:
        it.status = ITEM_IDLE


async def complete_job(session: AsyncSession, job_id: int) -> bool:
    """Идемпотентное завершение. Возвращает False, если задание уже не в работе или срок не наступил."""
    job = await _lock_job(session, job_id)
    if job is None or job.status != JOB_RUNNING or job.finishes_at > clock.now():
        return False
    result: dict = {}
    if job.kind in ("mine", "craft"):
        for r, q in sorted(job.outputs.items()):
            # Ёмкость проверена при старте; при завершении выдача не теряется даже при переполнении.
            await stock.add(session, job.owner_id, job.location_code, r, q, f"{job.kind}_output",
                            ref_type="job", ref_id=job.id, actor=job.actor_user_id, check_capacity=False)
        result["resources"] = job.outputs
    if job.kind == "craft":
        rec = RECIPES[job.recipe_code]
        tier, attrs = None, {}
        if rec.output_item and "q_base" in (job.params or {}):
            score = quality.final_score(job.params["q_base"], job.id, get_settings().quality_key())
            tier = quality.tier_for(score)
            attrs = {"quality": {"score": score, "tier": tier.code}}
            result["quality"] = tier.code
        if rec.output_item == "truck":
            mods = (await session.scalars(select(Item).where(Item.id.in_(job.consumed_items)).with_for_update())).all()
            st = truck_stats([m.def_code for m in mods])
            md = quality.scaled_durability(st.max_durability, tier) if tier else st.max_durability
            truck = await items.create(session, "truck", job.owner_id, job.location_code, "craft",
                                       origin_ref=f"job:{job.id}", actor=job.actor_user_id, max_durability=md,
                                       attrs=attrs)
            for m in mods:
                m.status = ITEM_INSTALLED
                m.parent_id = truck.id
            result["item_id"] = truck.id
        elif rec.output_item:
            base_md = ITEMS[rec.output_item].max_durability
            md = quality.scaled_durability(base_md, tier) if tier else base_md
            it = await items.create(session, rec.output_item, job.owner_id, job.location_code, "craft",
                                    origin_ref=f"job:{job.id}", actor=job.actor_user_id, max_durability=md,
                                    attrs=attrs)
            result["item_id"] = it.id
    if job.kind == "repair":
        target = await items.lock(session, job.target_item_id)
        target.durability = min(target.max_durability, target.durability + job.outputs["durability"])
        if target.status == ITEM_BUSY:
            target.status = ITEM_IDLE
        result["durability"] = target.durability
    if job.kind == "mine" or job.equipment_id != job.target_item_id:
        await _free_item(session, job.equipment_id)
    job.status = JOB_COMPLETED
    job.finished_at = clock.now()
    job.result = result
    await session.flush()
    return True


async def cancel_job(session: AsyncSession, user_id: int, job_id: int, op_key: str | None = None) -> None:
    job = await _lock_job(session, job_id)
    if job is None:
        raise NotFound("Задание не найдено.")
    await authz.require(session, user_id, job.owner_id, Perm.PRODUCE)
    if job.manual and job.actor_user_id != user_id and job.owner_id != user_id:
        raise Forbidden("Ручную смену может отменить только тот, кто работает.")
    if job.status != JOB_RUNNING:
        raise GameError("Задание уже завершено или отменено.")
    await claim_operation(session, op_key, "cancel_job", user_id)
    if job.kind == "mine":
        dep = await lock_deposit(session, job.deposit_id)
        dep.stock = min(dep.max_stock, dep.stock + sum(job.outputs.values()))
    else:
        for r, q in sorted(job.inputs.items()):
            await stock.add(session, job.owner_id, job.location_code, r, q, "job_cancel_refund",
                            ref_type="job", ref_id=job.id, actor=user_id, check_capacity=False)
    for mid in job.consumed_items or []:
        await _free_item(session, mid)
    await _free_item(session, job.equipment_id)
    await _free_item(session, job.target_item_id)
    job.status = JOB_CANCELLED
    job.finished_at = clock.now()
    await audit(session, "job_cancel", actor_user_id=user_id, account_id=job.owner_id, target_type="job", target_id=job.id)


async def due_job_ids(session: AsyncSession, limit: int = 100) -> list[int]:
    return list((await session.scalars(
        select(Job.id).where(Job.status == JOB_RUNNING, Job.finishes_at <= clock.now())
        .order_by(Job.finishes_at).limit(limit))).all())


def describe_job(job: Job) -> str:
    if job.kind == "mine":
        what = ", ".join(f"{resource_name(r)} ×{q}" for r, q in job.outputs.items())
        return f"Добыча: {what}"
    if job.kind == "repair":
        return f"Ремонт предмета #{job.target_item_id} (+{job.outputs.get('durability', 0)})"
    rec = RECIPES.get(job.recipe_code)
    name = rec.name if rec else job.recipe_code
    if rec and rec.output_item:
        return f"{name}: {item_name(rec.output_item)}"
    what = ", ".join(f"{resource_name(r)} ×{q}" for r, q in job.outputs.items())
    return f"{name} ×{job.runs}: {what}"
