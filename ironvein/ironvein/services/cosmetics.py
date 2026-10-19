"""Косметика: окраска грузовика. Без влияния на характеристики (vehicle_stats учитывает только модули)."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ironvein.domain.errors import GameError
from ironvein.domain.permissions import Perm
from ironvein.models import ITEM_IDLE, ITEM_INSTALLED, Item
from ironvein.services import authz, items
from ironvein.services.common import audit


async def apply_paint(session: AsyncSession, user_id: int, account_id: int, paint_id: int, vehicle_id: int) -> None:
    await authz.require(session, user_id, account_id, Perm.EQUIPMENT)
    paint = await items.lock_owned(session, paint_id, account_id)
    if paint.def_code != "paint_black_brass":
        raise GameError("Это не окраска.")
    truck = await items.lock_owned(session, vehicle_id, account_id)
    if truck.def_code != "truck":
        raise GameError("Окрасить можно только грузовик.")
    if await current_paint(session, truck.id) is not None:
        raise GameError("Грузовик уже окрашен.")
    paint.status = ITEM_INSTALLED
    paint.parent_id = truck.id
    paint.location_code = truck.location_code
    await audit(session, "paint_apply", actor_user_id=user_id, account_id=account_id, target_type="item",
                target_id=truck.id, paint=paint.id)


async def remove_paint(session: AsyncSession, user_id: int, account_id: int, vehicle_id: int) -> None:
    await authz.require(session, user_id, account_id, Perm.EQUIPMENT)
    truck = await items.lock_owned(session, vehicle_id, account_id)
    paint_id = await current_paint(session, truck.id)
    if paint_id is None:
        raise GameError("Окраски нет.")
    paint = await items.lock(session, paint_id)
    paint.status = ITEM_IDLE
    paint.parent_id = None
    paint.location_code = None
    await audit(session, "paint_remove", actor_user_id=user_id, account_id=account_id, target_type="item",
                target_id=truck.id, paint=paint.id)


async def current_paint(session: AsyncSession, vehicle_id: int) -> int | None:
    return await session.scalar(select(Item.id).where(Item.parent_id == vehicle_id,
                                                      Item.def_code == "paint_black_brass"))
