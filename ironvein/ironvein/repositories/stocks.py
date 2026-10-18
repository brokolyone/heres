from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ironvein.models import Stock


async def lock_stock(session: AsyncSession, owner_id: int, location: str, resource: str) -> Stock:
    """Возвращает заблокированную строку склада, создавая пустую при необходимости."""
    await session.execute(pg_insert(Stock).values(owner_id=owner_id, location_code=location, resource=resource)
                          .on_conflict_do_nothing())
    return (await session.execute(
        select(Stock).where(Stock.owner_id == owner_id, Stock.location_code == location, Stock.resource == resource)
        .with_for_update().execution_options(populate_existing=True))).scalar_one()


async def used_capacity(session: AsyncSession, owner_id: int, location: str) -> int:
    return int(await session.scalar(
        select(func.coalesce(func.sum(Stock.free + Stock.held), 0))
        .where(Stock.owner_id == owner_id, Stock.location_code == location)) or 0)


async def stocks_of(session: AsyncSession, owner_id: int) -> list[Stock]:
    return list((await session.scalars(
        select(Stock).where(Stock.owner_id == owner_id, (Stock.free + Stock.held) > 0)
        .order_by(Stock.location_code, Stock.resource))).all())
