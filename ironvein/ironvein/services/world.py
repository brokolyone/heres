"""Инициализация мира: локации, месторождения, системные счета, премиальный каталог. Идемпотентно."""

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ironvein.domain.catalog import DEPOSITS, LOCATIONS
from ironvein.domain.premium_catalog import PRODUCTS
from ironvein.models import ACC_SYSTEM, SYS_EMISSION, SYS_FEES, Account, Deposit, Location, PremiumProduct, Wallet
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
            "name": d.name, "regen_per_hour": d.regen_per_hour, "max_stock": d.max_stock}))
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
    rate = effective_regen(dep.regen_per_hour)  # единиц в реальный час с учётом GAME_SPEED
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


def effective_regen(regen_per_game_hour: int) -> float:
    from ironvein.config import get_settings
    return regen_per_game_hour * (get_settings().game_speed or 1.0)


async def lock_deposit(session: AsyncSession, deposit_id: int) -> Deposit:
    dep = (await session.execute(select(Deposit).where(Deposit.id == deposit_id).with_for_update()
                                 .execution_options(populate_existing=True))).scalar_one_or_none()
    if dep is None:
        from ironvein.domain.errors import NotFound
        raise NotFound("Месторождение не найдено.")
    await regen_deposit(session, dep)
    return dep
