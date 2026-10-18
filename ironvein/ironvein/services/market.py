"""Общий рынок: ask (продажа, товар блокируется) и bid (покупка, кроны резервируются).

Модель исполнения — «тейкер выбирает заявку»: покупатель исполняет ask, продавец исполняет bid.
Цена сделки — цена заявки-мейкера. Комиссия платится продавцом и уничтожается; округление вверх
на каждой сделке (дробление не уменьшает комиссию). Физические товары остаются в локации заявки —
покупателю их нужно вывезти самому.
"""

from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ironvein.config import get_settings
from ironvein.domain.catalog import ITEMS, KIND_PREMIUM, LOCATIONS, RESOURCES
from ironvein.domain.errors import Forbidden, GameError, NotFound
from ironvein.domain.money import fee_for
from ironvein.domain.permissions import Perm
from ironvein.models import ITEM_IDLE, ITEM_LISTED, MarketOrder, MarketTrade
from ironvein.services import authz, clock, items, ledger, stock
from ironvein.services.common import audit, claim_operation

MAX_PRICE = 10**9
MAX_QTY = 10**6


def _validate(price: int, qty: int) -> None:
    if not 0 < price <= MAX_PRICE:
        raise GameError("Цена должна быть от 1 ₭.")
    if not 0 < qty <= MAX_QTY:
        raise GameError("Некорректное количество.")


async def _lock_order(session: AsyncSession, order_id: int) -> MarketOrder:
    o = (await session.execute(select(MarketOrder).where(MarketOrder.id == order_id).with_for_update()
                               .execution_options(populate_existing=True))).scalar_one_or_none()
    if o is None:
        raise NotFound("Заявка не найдена.")
    return o


# --- Выставление заявок ------------------------------------------------------------------------------


async def place_ask_resource(session: AsyncSession, user_id: int, account_id: int, location: str, resource: str,
                             qty: int, price: int, op_key: str | None = None) -> MarketOrder:
    await authz.require(session, user_id, account_id, Perm.TRADE)
    _validate(price, qty)
    if resource not in RESOURCES or location not in LOCATIONS:
        raise GameError("Неизвестный товар или локация.")
    await claim_operation(session, op_key, "ask", user_id)
    o = MarketOrder(owner_id=account_id, created_by_user_id=user_id, side="ask", location_code=location,
                    resource=resource, price=price, qty_total=qty, qty_left=qty)
    session.add(o)
    await session.flush()
    await stock.hold(session, account_id, location, resource, qty, "market_ask", ref_type="order", ref_id=o.id, actor=user_id)
    await audit(session, "order_place", actor_user_id=user_id, account_id=account_id, target_type="order", target_id=o.id)
    return o


async def place_ask_item(session: AsyncSession, user_id: int, account_id: int, item_id: int, price: int,
                         op_key: str | None = None) -> MarketOrder:
    await authz.require(session, user_id, account_id, Perm.TRADE)
    _validate(price, 1)
    await claim_operation(session, op_key, "ask", user_id)
    it = await items.lock_owned(session, item_id, account_id)
    if not ITEMS[it.def_code].tradable:
        raise GameError("Этот предмет нельзя продать.")
    it.status = ITEM_LISTED
    o = MarketOrder(owner_id=account_id, created_by_user_id=user_id, side="ask", location_code=it.location_code,
                    item_def=it.def_code, item_id=it.id, price=price, qty_total=1, qty_left=1)
    session.add(o)
    await session.flush()
    await audit(session, "order_place", actor_user_id=user_id, account_id=account_id, target_type="order", target_id=o.id)
    return o


async def place_bid(session: AsyncSession, user_id: int, account_id: int, *, price: int, qty: int,
                    resource: str | None = None, item_def: str | None = None, location: str | None = None,
                    op_key: str | None = None) -> MarketOrder:
    """Заявка на покупку: кроны резервируются целиком (price × qty)."""
    await authz.require(session, user_id, account_id, Perm.TRADE)
    _validate(price, qty)
    if (resource is None) == (item_def is None):
        raise GameError("Укажите товар.")
    if resource is not None and (resource not in RESOURCES or location not in LOCATIONS):
        raise GameError("Для ресурса нужна локация поставки.")
    if item_def is not None:
        if item_def not in ITEMS:
            raise GameError("Неизвестный предмет.")
        if ITEMS[item_def].kind == KIND_PREMIUM:
            location = None
        elif location not in LOCATIONS:
            raise GameError("Укажите локацию.")
    await claim_operation(session, op_key, "bid", user_id)
    total = price * qty
    o = MarketOrder(owner_id=account_id, created_by_user_id=user_id, side="bid", location_code=location,
                    resource=resource, item_def=item_def, price=price, qty_total=qty, qty_left=qty, reserved=total)
    session.add(o)
    await session.flush()
    await ledger.hold(session, account_id, total, "bid_reserve", ref_type="order", ref_id=o.id, actor_user_id=user_id)
    await audit(session, "order_place", actor_user_id=user_id, account_id=account_id, target_type="order", target_id=o.id)
    return o


# --- Отмена ------------------------------------------------------------------------------------------


async def cancel(session: AsyncSession, user_id: int, order_id: int, op_key: str | None = None,
                 *, system: bool = False) -> MarketOrder:
    o = await _lock_order(session, order_id)
    if not system:
        await authz.require(session, user_id, o.owner_id, Perm.TRADE)
    if o.status != "open":
        raise GameError("Заявка уже закрыта.")
    await claim_operation(session, op_key, "cancel_order", user_id)
    await _release_order(session, o, user_id)
    o.status = "cancelled"
    o.closed_at = clock.now()
    await audit(session, "order_cancel", actor_user_id=user_id, account_id=o.owner_id, target_type="order",
                target_id=o.id, system=system)
    return o


async def _release_order(session: AsyncSession, o: MarketOrder, actor: int | None) -> None:
    if o.side == "bid":
        await ledger.release(session, o.owner_id, o.reserved, "bid_release", ref_type="order", ref_id=o.id,
                             actor_user_id=actor)
        o.reserved = 0
    elif o.resource:
        await stock.release(session, o.owner_id, o.location_code, o.resource, o.qty_left, "market_ask_cancel",
                            ref_type="order", ref_id=o.id, actor=actor)
    elif o.item_id:
        it = await items.lock(session, o.item_id)
        if it.status == ITEM_LISTED:
            it.status = ITEM_IDLE


# --- Исполнение --------------------------------------------------------------------------------------


async def _forbid_self_trade(session: AsyncSession, a: int, b: int) -> None:
    if await authz.same_controller(session, a, b):
        raise Forbidden("Нельзя торговать с самим собой или со своей компанией: это искажает реальные цены.")


async def buy(session: AsyncSession, user_id: int, account_id: int, ask_id: int, qty: int,
              op_key: str | None = None) -> MarketTrade:
    """Покупатель исполняет ask. Частичное исполнение для ресурсов, целиком — для уникальных вещей."""
    await authz.require(session, user_id, account_id, Perm.TRADE)
    await claim_operation(session, op_key, "buy", user_id)
    o = await _lock_order(session, ask_id)
    if o.side != "ask" or o.status != "open":
        raise GameError("Заявка уже неактуальна.")
    await _forbid_self_trade(session, account_id, o.owner_id)
    if o.item_id:
        qty = 1
    if not 0 < qty <= o.qty_left:
        raise GameError(f"Доступно только {o.qty_left}.")
    gross = o.price * qty
    fee = fee_for(gross, get_settings().market_fee_bps)
    if o.resource:
        await stock.ensure_capacity(session, account_id, o.location_code, qty)
    # Покупатель платит через свой hold: так сделка проходит одной схемой расчёта.
    await ledger.hold(session, account_id, gross, "buy_reserve", ref_type="order", ref_id=o.id, actor_user_id=user_id)
    await ledger.pay_from_hold(session, "trade", account_id, o.owner_id, gross, fee, ref_type="order", ref_id=o.id,
                               actor_user_id=user_id)
    trade = await _settle_goods(session, o, buyer=account_id, seller=o.owner_id, qty=qty, actor=user_id)
    trade.fee = fee
    await session.flush()
    return trade


async def sell(session: AsyncSession, user_id: int, account_id: int, bid_id: int, qty: int,
               item_id: int | None = None, op_key: str | None = None) -> MarketTrade:
    """Продавец исполняет bid своим товаром."""
    await authz.require(session, user_id, account_id, Perm.TRADE)
    await claim_operation(session, op_key, "sell", user_id)
    o = await _lock_order(session, bid_id)
    if o.side != "bid" or o.status != "open":
        raise GameError("Заявка уже неактуальна.")
    await _forbid_self_trade(session, account_id, o.owner_id)
    if o.item_def:
        qty = 1
        if item_id is None:
            raise GameError("Выберите предмет для продажи.")
        it = await items.lock_owned(session, item_id, account_id)
        if it.def_code != o.item_def:
            raise GameError("Предмет не соответствует заявке.")
        if o.location_code and it.location_code != o.location_code:
            raise GameError("Предмет находится не в той локации, где покупатель его ждёт.")
        it.status = ITEM_LISTED  # кратковременно: эскроу на время расчёта
    if not 0 < qty <= o.qty_left:
        raise GameError(f"Покупателю нужно не больше {o.qty_left}.")
    if o.resource:
        await stock.hold(session, account_id, o.location_code, o.resource, qty, "market_sell", ref_type="order",
                         ref_id=o.id, actor=user_id)
    gross = o.price * qty
    fee = fee_for(gross, get_settings().market_fee_bps)
    await ledger.pay_from_hold(session, "trade", o.owner_id, account_id, gross, fee, ref_type="order", ref_id=o.id,
                               actor_user_id=user_id)
    o.reserved -= gross
    trade = await _settle_goods(session, o, buyer=o.owner_id, seller=account_id, qty=qty, actor=user_id,
                                item_id=item_id)
    trade.fee = fee
    if o.status == "filled" and o.reserved:
        # Остатка быть не должно (резерв = price × qty), но на случай будущих правил возвращаем его.
        await ledger.release(session, o.owner_id, o.reserved, "bid_release", ref_type="order", ref_id=o.id)
        o.reserved = 0
    await session.flush()
    return trade


async def _settle_goods(session: AsyncSession, o: MarketOrder, *, buyer: int, seller: int, qty: int,
                        actor: int, item_id: int | None = None) -> MarketTrade:
    item_id = item_id or o.item_id
    if o.resource:
        await stock.move_held(session, seller, buyer, o.location_code, o.resource, qty, "trade",
                              ref_type="order", ref_id=o.id, actor=actor)
    else:
        it = await items.lock(session, item_id)
        if it.status != ITEM_LISTED or it.owner_id != seller:
            raise GameError("Предмет уже недоступен.")
        await items.transfer(session, it, buyer, "trade", ref_type="order", ref_id=o.id, actor=actor)
        it.status = ITEM_IDLE
    o.qty_left -= qty
    if o.qty_left == 0:
        o.status = "filled"
        o.closed_at = clock.now()
    trade = MarketTrade(order_id=o.id, buyer_id=buyer, seller_id=seller, location_code=o.location_code,
                        resource=o.resource, item_def=o.item_def, item_id=item_id, qty=qty, price=o.price,
                        gross=o.price * qty, fee=0)
    session.add(trade)
    await session.flush()
    await audit(session, "trade", actor_user_id=actor, account_id=buyer, target_type="trade", target_id=trade.id,
                order=o.id, seller=seller, qty=qty, price=o.price)
    return trade


async def market_buy(session: AsyncSession, user_id: int, account_id: int, resource: str, location: str,
                     qty: int, max_price: int, op_key: str | None = None) -> list[MarketTrade]:
    """Купить до qty по лучшим ask не дороже max_price (чужие заявки, по цене и времени)."""
    await claim_operation(session, op_key, "market_buy", user_id)
    trades = []
    ids = (await session.scalars(
        select(MarketOrder.id).where(MarketOrder.status == "open", MarketOrder.side == "ask",
                                     MarketOrder.resource == resource, MarketOrder.location_code == location,
                                     MarketOrder.price <= max_price)
        .order_by(MarketOrder.price, MarketOrder.id))).all()
    for oid in ids:
        if qty <= 0:
            break
        o = await _lock_order(session, oid)
        if o.status != "open" or await authz.same_controller(session, account_id, o.owner_id):
            continue
        take = min(qty, o.qty_left)
        trades.append(await buy(session, user_id, account_id, oid, take))
        qty -= take
    if not trades:
        raise GameError("Нет подходящих предложений.")
    return trades


# --- Стакан и статистика -----------------------------------------------------------------------------


async def book(session: AsyncSession, *, resource: str | None = None, item_def: str | None = None,
               location: str | None = None, limit: int = 5) -> dict:
    def base(side):
        q = select(MarketOrder).where(MarketOrder.status == "open", MarketOrder.side == side)
        q = q.where(MarketOrder.resource == resource) if resource else q.where(MarketOrder.item_def == item_def)
        if location:
            q = q.where(MarketOrder.location_code == location)
        return q
    asks = (await session.scalars(base("ask").order_by(MarketOrder.price, MarketOrder.id).limit(limit))).all()
    bids = (await session.scalars(base("bid").order_by(MarketOrder.price.desc(), MarketOrder.id).limit(limit))).all()
    tq = select(MarketTrade).order_by(MarketTrade.id.desc()).limit(limit)
    tq = tq.where(MarketTrade.resource == resource) if resource else tq.where(MarketTrade.item_def == item_def)
    if location:
        tq = tq.where(MarketTrade.location_code == location)
    trades = (await session.scalars(tq)).all()
    since = clock.now() - timedelta(hours=24)
    vq = select(func.coalesce(func.sum(MarketTrade.qty), 0), func.coalesce(func.sum(MarketTrade.gross), 0)) \
        .where(MarketTrade.created_at >= since)
    vq = vq.where(MarketTrade.resource == resource) if resource else vq.where(MarketTrade.item_def == item_def)
    if location:
        vq = vq.where(MarketTrade.location_code == location)
    vol_qty, vol_gross = (await session.execute(vq)).one()
    return {"asks": list(asks), "bids": list(bids), "trades": list(trades), "volume_qty": int(vol_qty),
            "volume_gross": int(vol_gross), "last": trades[0] if trades else None}


async def orders_of(session: AsyncSession, account_id: int) -> list[MarketOrder]:
    return list((await session.scalars(
        select(MarketOrder).where(MarketOrder.owner_id == account_id, MarketOrder.status == "open")
        .order_by(MarketOrder.id.desc()).limit(30))).all())


async def item_asks(session: AsyncSession, item_def: str) -> list[MarketOrder]:
    return list((await session.scalars(
        select(MarketOrder).where(MarketOrder.status == "open", MarketOrder.side == "ask",
                                  MarketOrder.item_def == item_def).order_by(MarketOrder.price).limit(10))).all())


__all__ = ["place_ask_resource", "place_ask_item", "place_bid", "cancel", "buy", "sell", "market_buy", "book",
           "orders_of", "item_asks"]
