"""Инициализация мира: локации, месторождения, системные счета, премиальный каталог. Идемпотентно."""

import time
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ironvein.domain.catalog import DEPOSITS, LOCATIONS
from ironvein.domain.premium_catalog import PRODUCTS
from ironvein.models import (
    ACC_SYSTEM,
    SYS_EMISSION,
    SYS_FEES,
    Account,
    Deposit,
    Job,
    Location,
    PremiumProduct,
    Wallet,
)
from ironvein.services import clock


async def ensure_world(session: AsyncSession) -> None:
    for loc in LOCATIONS.values():
        await session.execute(pg_insert(Location).values(code=loc.code, name=loc.name)
                              .on_conflict_do_update(index_elements=["code"], set_={"name": loc.name}))
    for d in DEPOSITS:
        await session.execute(pg_insert(Deposit).values(
            code=d.code, location_code=d.location, resource=d.resource, name=d.name, stock=d.max_stock,
            max_stock=d.max_stock, regen_per_hour=d.regen_per_hour, regen_at=clock.now()
        ).on_conflict_do_update(index_elements=["code"], set_={
            "name": d.name, "regen_per_hour": d.regen_per_hour, "max_stock": d.max_stock,
            # при уменьшении максимума в каталоге запас обрезается, иначе CHECK stock <= max_stock уронит старт
            "stock": func.least(Deposit.stock, d.max_stock)}))
    for code, allow_neg in ((SYS_EMISSION, True), (SYS_FEES, False)):
        acc_id = await session.scalar(select(Account.id).where(Account.code == code))
        if acc_id is None:
            acc = Account(kind=ACC_SYSTEM, code=code, name=code)
            session.add(acc)
            await session.flush()
            acc_id = acc.id
        for kind in ("main", "hold"):
            await session.execute(pg_insert(Wallet).values(
                account_id=acc_id, kind=kind, balance=0, allow_negative=allow_neg and kind == "main"
            ).on_conflict_do_nothing())
    for p in PRODUCTS:
        await session.execute(pg_insert(PremiumProduct).values(
            code=p.code, item_def=p.item_def, title=p.title, description=p.description, price_stars=p.price_stars,
            edition_limit=p.edition_limit, issued=0, reserved=0, active=True).on_conflict_do_nothing())
    await session.flush()


async def regen_deposit(session: AsyncSession, dep: Deposit) -> None:
    """Ленивое детерминированное пополнение запаса (строка уже заблокирована)."""
    now = clock.now()
    elapsed = now - dep.regen_at
    if elapsed <= timedelta(0):
        return
    rate = effective_regen(dep.regen_per_hour, await players_multiplier(session))  # единиц в реальный час
    if rate <= 0:
        dep.regen_at = now
        return
    gained = int(elapsed.total_seconds() * rate // 3600)
    if gained <= 0:
        return
    if dep.stock >= dep.max_stock:
        dep.regen_at = now
        return
    dep.stock = min(dep.max_stock, dep.stock + gained)
    dep.regen_at = dep.regen_at + timedelta(seconds=gained * 3600 / rate) if dep.stock < dep.max_stock else now


def effective_regen(regen_per_game_hour: int, players_mult: float = 1.0) -> float:
    """Регенерация в реальный час: каталог × GAME_SPEED × множитель активных игроков."""
    from ironvein.config import get_settings
    return regen_per_game_hour * (get_settings().game_speed or 1.0) * players_mult


_mult_cache: tuple[float, float] | None = None  # (значение, monotonic-время расчёта)
MULT_TTL_SECONDS = 60.0


async def players_multiplier(session: AsyncSession) -> float:
    """Месторождения рассчитаны на DEPOSIT_SCALE_PLAYERS активных игроков; при большем числе работающих
    за сутки регенерация растёт пропорционально — мир не «пересыхает» от роста аудитории. Кэш на минуту."""
    global _mult_cache
    from ironvein.config import get_settings
    scale = get_settings().deposit_scale_players
    if scale <= 0:
        return 1.0
    now_m = time.monotonic()
    if _mult_cache is not None and now_m - _mult_cache[1] < MULT_TTL_SECONDS:
        return _mult_cache[0]
    active = await session.scalar(select(func.count(func.distinct(Job.actor_user_id)))
                                  .where(Job.started_at >= clock.now() - timedelta(hours=24))) or 0
    value = max(1.0, active / scale)
    _mult_cache = (value, now_m)
    return value


def reset_multiplier_cache() -> None:
    global _mult_cache
    _mult_cache = None


async def lock_deposit(session: AsyncSession, deposit_id: int) -> Deposit:
    dep = (await session.execute(select(Deposit).where(Deposit.id == deposit_id).with_for_update()
                                 .execution_options(populate_existing=True))).scalar_one_or_none()
    if dep is None:
        from ironvein.domain.errors import NotFound
        raise NotFound("Месторождение не найдено.")
    await regen_deposit(session, dep)
    return dep
