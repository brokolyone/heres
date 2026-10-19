"""Премиальный магазин за Telegram Stars (XTR).

Поток: заказ (серверный order_id, цена фиксируется, слот лимитированного тиража бронируется) ->
send_invoice(payload=order.public_id) -> pre_checkout_query (сверка с заказом) -> successful_payment
(идемпотентно по telegram_payment_charge_id) -> выдача экземпляра с серийным номером в той же транзакции.

Лимит тиража гарантируется CHECK (issued + reserved <= edition_limit) под блокировкой строки товара.
Если оплата пришла, а выдать нельзя (бронь истекла и тираж разобран, сумма не совпала), заказ получает
статус refund_pending и фоновая задача делает refundStarPayment — деньги за недоступный товар не удерживаются.
Возврат после перепродажи: экземпляр блокируется у текущего владельца, решение — вручную администратором.
Stars никогда не конвертируются в кроны ботом: кроны появляются только от других игроков на рынке.
"""

import uuid
from datetime import timedelta

from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from ironvein.config import get_settings
from ironvein.domain.errors import GameError, NotFound
from ironvein.models import (
    ITEM_IDLE,
    ITEM_LISTED,
    ITEM_LOCKED,
    PO_CREATED,
    PO_EXPIRED,
    PO_FULFILLED,
    PO_PAID,
    PO_REFUND_PENDING,
    PO_REFUNDED,
    MarketOrder,
    PaymentEvent,
    PremiumOrder,
    PremiumProduct,
    User,
)
from ironvein.services import clock, items
from ironvein.services.common import audit


async def _event(session: AsyncSession, order_id: int | None, event: str, **data) -> None:
    await session.execute(insert(PaymentEvent).values(order_id=order_id, event=event, data=data))


async def _lock_product(session: AsyncSession, code: str) -> PremiumProduct:
    p = (await session.execute(select(PremiumProduct).where(PremiumProduct.code == code).with_for_update()
                               .execution_options(populate_existing=True))).scalar_one_or_none()
    if p is None:
        raise NotFound("Товар не найден.")
    return p


async def _lock_order_by_payload(session: AsyncSession, payload: str) -> PremiumOrder | None:
    return (await session.execute(select(PremiumOrder).where(PremiumOrder.public_id == payload).with_for_update()
                                  .execution_options(populate_existing=True))).scalar_one_or_none()


def _slot_free(p: PremiumProduct) -> bool:
    return p.edition_limit is None or p.issued + p.reserved < p.edition_limit


async def catalog(session: AsyncSession) -> list[PremiumProduct]:
    return list((await session.scalars(select(PremiumProduct).where(PremiumProduct.active.is_(True))
                                       .order_by(PremiumProduct.price_stars.desc()))).all())


async def create_order(session: AsyncSession, user_id: int, product_code: str) -> PremiumOrder:
    p = await _lock_product(session, product_code)
    if not p.active:
        raise GameError("Товар снят с продажи.")
    if not _slot_free(p):
        raise GameError("Тираж распродан. Экземпляры можно найти на рынке у игроков.")
    holds = p.edition_limit is not None
    if holds:
        p.reserved += 1
    o = PremiumOrder(public_id=f"iv-{uuid.uuid4().hex}", user_id=user_id, product_code=p.code,
                     price_stars=p.price_stars, currency="XTR", status=PO_CREATED, holds_slot=holds,
                     reserved_until=clock.now() + timedelta(minutes=get_settings().premium_reservation_minutes))
    session.add(o)
    await session.flush()
    await _event(session, o.id, "invoice_created", price=o.price_stars, holds_slot=holds)
    return o


async def pre_checkout(session: AsyncSession, payload: str, tg_user_id: int, total_amount: int,
                       currency: str) -> tuple[bool, str | None]:
    """Решение по pre_checkout_query. Деньги ещё не списаны — отказ безопасен."""
    o = await _lock_order_by_payload(session, payload)
    if o is None:
        await _event(session, None, "precheckout_unknown", payload=payload[:64])
        return False, "Счёт не найден. Откройте /donate заново."
    user = await session.get(User, o.user_id)
    err = None
    if user is None or user.tg_id != tg_user_id:
        err = "Этот счёт выставлен другому игроку."
    elif currency != "XTR" or total_amount != o.price_stars:
        err = "Сумма счёта не совпадает с заказом."
    elif o.status not in (PO_CREATED, PO_EXPIRED):
        err = "Этот счёт уже оплачен или закрыт."
    else:
        p = await _lock_product(session, o.product_code)
        if not p.active:
            err = "Товар снят с продажи."
        elif not o.holds_slot and p.edition_limit is not None:
            if _slot_free(p):
                p.reserved += 1
                o.holds_slot = True
            else:
                err = "Тираж распродан, пока счёт ждал оплаты. Деньги не списаны."
        if err is None:
            o.status = PO_CREATED
            o.reserved_until = clock.now() + timedelta(minutes=get_settings().premium_reservation_minutes)
    await _event(session, o.id, "precheckout_ok" if err is None else "precheckout_reject", error=err)
    return err is None, err


async def successful_payment(session: AsyncSession, payload: str, tg_user_id: int, total_amount: int,
                             currency: str, charge_id: str, fulfill_now: bool = True) -> PremiumOrder | None:
    """Обработка successful_payment. Повторный update с тем же charge_id ничего не делает.

    fulfill_now=False — только зафиксировать оплату (status=paid); выдачу делает fulfill_order отдельной
    транзакцией или фоновая задача retry_paid, так что сбой выдачи не теряет оплаченный заказ.
    """
    dup = await session.scalar(select(PremiumOrder).where(PremiumOrder.telegram_charge_id == charge_id))
    if dup is not None:
        await _event(session, dup.id, "payment_duplicate", charge_id=charge_id)
        return dup
    o = await _lock_order_by_payload(session, payload)
    if o is None:
        await _event(session, None, "payment_orphan", payload=payload[:64], charge_id=charge_id,
                     tg_user_id=tg_user_id, amount=total_amount)
        await audit(session, "payment_orphan", charge_id=charge_id, tg_user_id=tg_user_id)
        return None
    if o.telegram_charge_id is not None:
        # Второй платёж за тот же счёт: фиксируем для ручного возврата.
        await _event(session, o.id, "payment_second_charge", charge_id=charge_id)
        await audit(session, "payment_second_charge", target_type="premium_order", target_id=o.id, charge_id=charge_id)
        return o
    o.telegram_charge_id = charge_id
    o.paid_at = clock.now()
    await _event(session, o.id, "payment_received", charge_id=charge_id, amount=total_amount, currency=currency)
    if currency != "XTR" or total_amount != o.price_stars:
        o.status = PO_REFUND_PENDING
        await _event(session, o.id, "amount_mismatch", amount=total_amount)
        return o
    p = await _lock_product(session, o.product_code)
    if not o.holds_slot and p.edition_limit is not None:
        if _slot_free(p):
            p.reserved += 1
            o.holds_slot = True
        else:
            o.status = PO_REFUND_PENDING
            await _event(session, o.id, "sold_out_after_payment")
            return o
    o.status = PO_PAID
    if fulfill_now:
        await fulfill(session, o)
    return o


async def fulfill_order(session: AsyncSession, order_id: int) -> PremiumOrder:
    o = (await session.execute(select(PremiumOrder).where(PremiumOrder.id == order_id).with_for_update()
                               .execution_options(populate_existing=True))).scalar_one()
    await fulfill(session, o)
    return o


async def fulfill(session: AsyncSession, o: PremiumOrder) -> None:
    """Выдача экземпляра (заказ заблокирован). Серийный номер = следующий по товару, уникален в БД."""
    if o.status != PO_PAID:
        return
    p = await _lock_product(session, o.product_code)
    if o.holds_slot:
        p.reserved -= 1
        o.holds_slot = False
    p.issued += 1
    it = await items.create(session, p.item_def, o.user_id, None, "premium", origin_ref=o.public_id,
                            serial_no=p.issued, actor=o.user_id, attrs={"first_buyer": o.user_id})
    o.item_id = it.id
    o.status = PO_FULFILLED
    o.fulfilled_at = clock.now()
    await session.flush()
    await _event(session, o.id, "fulfilled", item_id=it.id, serial=p.issued)
    await audit(session, "premium_fulfilled", actor_user_id=o.user_id, account_id=o.user_id,
                target_type="item", target_id=it.id, order=o.public_id)


async def retry_paid(session: AsyncSession) -> int:
    ids = (await session.scalars(select(PremiumOrder.id).where(PremiumOrder.status == PO_PAID))).all()
    n = 0
    for oid in ids:
        o = (await session.execute(select(PremiumOrder).where(PremiumOrder.id == oid).with_for_update())).scalar_one()
        if o.status == PO_PAID:
            await fulfill(session, o)
            n += 1
    return n


async def expire_reservations(session: AsyncSession) -> int:
    ids = (await session.scalars(select(PremiumOrder.id).where(
        PremiumOrder.status == PO_CREATED, PremiumOrder.reserved_until < clock.now()))).all()
    n = 0
    for oid in ids:
        o = (await session.execute(select(PremiumOrder).where(PremiumOrder.id == oid).with_for_update()
                                   .execution_options(populate_existing=True))).scalar_one()
        if o.status != PO_CREATED or o.reserved_until >= clock.now():
            continue
        if o.holds_slot:
            p = await _lock_product(session, o.product_code)
            p.reserved -= 1
            o.holds_slot = False
        o.status = PO_EXPIRED
        await _event(session, o.id, "reservation_expired")
        n += 1
    return n


async def refund_pending(session: AsyncSession) -> list[tuple[int, int, str]]:
    """[(order_id, tg_user_id, charge_id)] для фоновой задачи возвратов."""
    rows = (await session.execute(
        select(PremiumOrder.id, User.tg_id, PremiumOrder.telegram_charge_id).join(User, User.id == PremiumOrder.user_id)
        .where(PremiumOrder.status == PO_REFUND_PENDING, PremiumOrder.telegram_charge_id.is_not(None)))).all()
    return [tuple(r) for r in rows]


async def request_refund(session: AsyncSession, admin_user_id: int, order_id: int, reason: str) -> PremiumOrder:
    """Администратор ставит выполненный заказ в очередь на возврат Stars."""
    o = (await session.execute(select(PremiumOrder).where(PremiumOrder.id == order_id).with_for_update())
         ).scalar_one_or_none()
    if o is None:
        raise NotFound("Заказ не найден.")
    if o.status not in (PO_FULFILLED, PO_PAID):
        raise GameError(f"Заказ в статусе {o.status}, возврат невозможен.")
    o.status = PO_REFUND_PENDING
    await _event(session, o.id, "refund_requested", by=admin_user_id, reason=reason[:300])
    await audit(session, "admin_refund_request", actor_user_id=admin_user_id, target_type="premium_order",
                target_id=o.id, reason=reason[:300])
    return o


async def mark_refunded(session: AsyncSession, *, order_id: int | None = None, charge_id: str | None = None,
                        source: str = "bot") -> PremiumOrder | None:
    """Фиксирует возврат (идемпотентно). Выданный экземпляр блокируется у текущего владельца."""
    q = select(PremiumOrder).with_for_update()
    q = q.where(PremiumOrder.id == order_id) if order_id is not None else q.where(PremiumOrder.telegram_charge_id == charge_id)
    o = (await session.execute(q)).scalar_one_or_none()
    if o is None:
        await _event(session, None, "refund_unknown", charge_id=charge_id, source=source)
        return None
    if o.status == PO_REFUNDED:
        return o
    if o.holds_slot:
        p = await _lock_product(session, o.product_code)
        p.reserved -= 1
        o.holds_slot = False
    o.status = PO_REFUNDED
    o.refunded_at = clock.now()
    if o.item_id:
        it = await items.lock(session, o.item_id)
        if it.status == ITEM_LISTED:
            from ironvein.services import market
            oid = await session.scalar(select(MarketOrder.id).where(MarketOrder.item_id == it.id,
                                                                    MarketOrder.status == "open"))
            if oid:
                await market.cancel(session, None, oid, system=True)
        it.attrs = {**(it.attrs or {}), "lock_reason": "stars_refund", "locked_from": it.status}
        it.status = ITEM_LOCKED
        await audit(session, "premium_item_locked", target_type="item", target_id=it.id, order=o.public_id,
                    owner=it.owner_id)
    await _event(session, o.id, "refunded", source=source)
    return o


async def admin_unlock(session: AsyncSession, admin_user_id: int, item_id: int, note: str = "") -> None:
    it = await items.lock(session, item_id)
    if it.status != ITEM_LOCKED:
        raise GameError("Предмет не заблокирован.")
    it.status = ITEM_IDLE
    await audit(session, "admin_item_unlock", actor_user_id=admin_user_id, target_type="item", target_id=item_id,
                note=note[:300])


async def orders_of(session: AsyncSession, user_id: int, limit: int = 10) -> list[PremiumOrder]:
    return list((await session.scalars(select(PremiumOrder).where(PremiumOrder.user_id == user_id)
                                       .order_by(PremiumOrder.id.desc()).limit(limit))).all())
