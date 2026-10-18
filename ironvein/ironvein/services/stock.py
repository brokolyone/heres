"""Физические запасы ресурсов. Все изменения журналируются в stock_movements."""

from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from ironvein.config import get_settings
from ironvein.domain.catalog import LOCATIONS, RESOURCES, resource_name
from ironvein.domain.errors import GameError
from ironvein.models import StockMovement
from ironvein.repositories.stocks import lock_stock, used_capacity


def _check(resource: str, qty: int) -> None:
    if resource not in RESOURCES:
        raise GameError("Неизвестный ресурс.")
    if qty <= 0:
        raise GameError("Количество должно быть положительным.")


async def _log(session, owner_id, location, resource, d_free, d_held, reason, ref_type, ref_id, actor):
    await session.execute(insert(StockMovement).values(
        owner_id=owner_id, location_code=location, resource=resource, delta_free=d_free, delta_held=d_held,
        reason=reason, ref_type=ref_type, ref_id=ref_id, actor_user_id=actor))


async def ensure_capacity(session: AsyncSession, owner_id: int, location: str, incoming: int) -> None:
    cap = get_settings().warehouse_capacity
    used = await used_capacity(session, owner_id, location)
    if used + incoming > cap:
        raise GameError(f"Склад в локации «{LOCATIONS[location].name}» переполнен: {used}/{cap}, "
                        f"нужно места ещё на {incoming}.")


async def add(session: AsyncSession, owner_id: int, location: str, resource: str, qty: int, reason: str, *,
              ref_type: str | None = None, ref_id: int | None = None, actor: int | None = None,
              check_capacity: bool = True, held: bool = False) -> None:
    _check(resource, qty)
    if check_capacity:
        await ensure_capacity(session, owner_id, location, qty)
    s = await lock_stock(session, owner_id, location, resource)
    if held:
        s.held += qty
    else:
        s.free += qty
    await _log(session, owner_id, location, resource, 0 if held else qty, qty if held else 0, reason, ref_type, ref_id, actor)


async def take(session: AsyncSession, owner_id: int, location: str, resource: str, qty: int, reason: str, *,
               ref_type: str | None = None, ref_id: int | None = None, actor: int | None = None,
               from_held: bool = False) -> None:
    """Списание (сток или передача). Без отрицательных остатков."""
    _check(resource, qty)
    s = await lock_stock(session, owner_id, location, resource)
    have = s.held if from_held else s.free
    if have < qty:
        raise GameError(f"Не хватает: {resource_name(resource)} — нужно {qty}, на складе {have} "
                        f"({LOCATIONS[location].name}).")
    if from_held:
        s.held -= qty
    else:
        s.free -= qty
    await _log(session, owner_id, location, resource, 0 if from_held else -qty, -qty if from_held else 0,
               reason, ref_type, ref_id, actor)


async def hold(session: AsyncSession, owner_id: int, location: str, resource: str, qty: int, reason: str, **kw) -> None:
    _check(resource, qty)
    s = await lock_stock(session, owner_id, location, resource)
    if s.free < qty:
        raise GameError(f"Не хватает: {resource_name(resource)} — нужно {qty}, свободно {s.free} "
                        f"({LOCATIONS[location].name}).")
    s.free -= qty
    s.held += qty
    await _log(session, owner_id, location, resource, -qty, qty, reason, kw.get("ref_type"), kw.get("ref_id"), kw.get("actor"))


async def release(session: AsyncSession, owner_id: int, location: str, resource: str, qty: int, reason: str, **kw) -> None:
    if qty <= 0:
        return
    s = await lock_stock(session, owner_id, location, resource)
    if s.held < qty:
        raise RuntimeError("release more than held")
    s.held -= qty
    s.free += qty
    await _log(session, owner_id, location, resource, qty, -qty, reason, kw.get("ref_type"), kw.get("ref_id"), kw.get("actor"))


async def move_held(session: AsyncSession, src_owner: int, dst_owner: int, location: str, resource: str, qty: int,
                    reason: str, **kw) -> None:
    """Передача заблокированного товара другому владельцу в той же локации (расчёт по сделке)."""
    await take(session, src_owner, location, resource, qty, reason, from_held=True, **kw)
    await add(session, dst_owner, location, resource, qty, reason, check_capacity=False, **kw)
