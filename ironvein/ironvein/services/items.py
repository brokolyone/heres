"""Уникальные экземпляры предметов: оборудование, модули, транспорт, премиальные вещи."""

from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from ironvein.domain import quality
from ironvein.domain.catalog import ITEMS
from ironvein.domain.errors import Forbidden, GameError, NotFound
from ironvein.models import ITEM_IDLE, Item, OwnershipHistory

STATUS_RU = {
    "idle": "свободен", "busy": "в работе", "loading": "погрузка", "in_transit": "в пути", "listed": "на продаже",
    "installed": "установлен", "locked": "заблокирован", "destroyed": "списан",
}


async def create(session: AsyncSession, def_code: str, owner_id: int, location: str | None, origin: str, *,
                 origin_ref: str | None = None, serial_no: int | None = None, actor: int | None = None,
                 max_durability: int | None = None, attrs: dict | None = None, status: str = ITEM_IDLE) -> Item:
    d = ITEMS[def_code]
    md = d.max_durability if max_durability is None else max_durability
    item = Item(def_code=def_code, owner_id=owner_id, location_code=location, status=status, durability=md,
                max_durability=md, serial_no=serial_no, origin=origin, origin_ref=origin_ref, attrs=attrs or {})
    session.add(item)
    await session.flush()
    await session.execute(insert(OwnershipHistory).values(
        item_id=item.id, from_owner_id=None, to_owner_id=owner_id, reason=f"create:{origin}",
        ref_type="origin", actor_user_id=actor))
    return item


async def lock(session: AsyncSession, item_id: int) -> Item:
    item = (await session.execute(select(Item).where(Item.id == item_id).with_for_update()
                                  .execution_options(populate_existing=True))).scalar_one_or_none()
    if item is None:
        raise NotFound("Предмет не найден.")
    return item


async def lock_owned(session: AsyncSession, item_id: int, owner_id: int, *, status: str | None = ITEM_IDLE) -> Item:
    item = await lock(session, item_id)
    if item.owner_id != owner_id:
        raise Forbidden("Этот предмет вам не принадлежит.")
    if status is not None and item.status != status:
        raise GameError(f"«{ITEMS[item.def_code].name} #{item.id}» сейчас {STATUS_RU.get(item.status, item.status)}.")
    return item


async def transfer(session: AsyncSession, item: Item, to_owner: int, reason: str, *, ref_type: str | None = None,
                   ref_id: int | None = None, actor: int | None = None) -> None:
    """Смена владельца (строка предмета уже заблокирована вызывающим). Установленные модули следуют за машиной."""
    prev = item.owner_id
    item.owner_id = to_owner
    await session.execute(insert(OwnershipHistory).values(
        item_id=item.id, from_owner_id=prev, to_owner_id=to_owner, reason=reason, ref_type=ref_type,
        ref_id=ref_id, actor_user_id=actor))
    children = (await session.scalars(select(Item).where(Item.parent_id == item.id).with_for_update())).all()
    for ch in children:
        await transfer(session, ch, to_owner, reason, ref_type=ref_type, ref_id=ref_id, actor=actor)


async def set_location(session: AsyncSession, item: Item, location: str | None) -> None:
    item.location_code = location
    children = (await session.scalars(select(Item).where(Item.parent_id == item.id).with_for_update())).all()
    for ch in children:
        ch.location_code = location


def quality_of(item: Item) -> quality.Tier | None:
    """Ступень качества изготовленного предмета; None — качество не записано (стартовые и премиум-предметы)."""
    q = (item.attrs or {}).get("quality")
    return quality.TIER_BY_CODE.get(q.get("tier")) if isinstance(q, dict) else None


def quality_score(item: Item) -> int:
    q = (item.attrs or {}).get("quality")
    return int(q.get("score", quality.COMMON_SCORE)) if isinstance(q, dict) else quality.COMMON_SCORE


def title(item: Item) -> str:
    d = ITEMS[item.def_code]
    s = f"{d.name} #{item.id}"
    if item.serial_no is not None and d.kind == "premium":
        s = f"{d.name} №{item.serial_no:03d} (#{item.id})"
    tier = quality_of(item)
    if tier is not None:
        s += f" {quality.stars(tier)}"
    return s
