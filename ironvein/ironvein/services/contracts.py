"""Контракты поставки и перевозки между игроками и компаниями.

Общие правила:
- оплата резервируется заказчиком при публикации (draft -> open) и хранится в его hold;
- контракт никогда не создаёт денег или предметов: он только переводит зарезервированное;
- комиссия фиксируется в момент создания (fee_bps) и уничтожается;
- принять свой контракт (или контракт своей компании) нельзя.

Поставка: частичные поставки разрешены, оплата пропорциональна и считается накопительно:
  выплачено_всего = floor(price_total × поставлено / qty), комиссия_всего = ceil(выплачено_всего × bps),
  поэтому дробление поставки не меняет итоговую комиссию, а последняя поставка закрывает сумму без остатка.
  Просрочка: уже поставленное оплачено, остаток резерва возвращается заказчику.

Перевозка: заказчик резервирует плату и груз; перевозчик принимает контракт своей машиной — рейс
  отправляется в той же транзакции (если ETA не укладывается в срок, принятие отклоняется). После серверного
  прибытия груз зачисляется заказчику в пункте назначения, оплата уходит перевозчику. Отмена — только до принятия.

Спор: участник поставки может открыть спор; контракт замораживается (не истекает). Администратор с аудитом
  либо возвращает остаток резерва заказчику, либо возобновляет исполнение. Оплата без поставки невозможна.
"""

from datetime import timedelta

from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from ironvein.config import get_settings
from ironvein.domain.catalog import LOCATIONS, RESOURCES, route_km
from ironvein.domain.errors import Forbidden, GameError, NotFound
from ironvein.domain.money import cumulative_split, fee_for
from ironvein.domain.permissions import Perm
from ironvein.models import Contract, ContractEvent, ContractFulfillment
from ironvein.services import authz, clock, ledger, stock, transport
from ironvein.services.common import audit, claim_operation

STATUS_RU = {
    "draft": "черновик", "open": "открыт", "accepted": "принят", "in_progress": "исполняется",
    "completed": "исполнен", "cancelled": "отменён", "expired": "просрочен", "disputed": "спор",
}
ACTIVE = ("open", "accepted", "in_progress")


async def _event(session: AsyncSession, c: Contract, event: str, actor: int | None, **data) -> None:
    await session.execute(insert(ContractEvent).values(contract_id=c.id, event=event, actor_user_id=actor, data=data))


async def _lock(session: AsyncSession, contract_id: int) -> Contract:
    c = (await session.execute(select(Contract).where(Contract.id == contract_id).with_for_update()
                               .execution_options(populate_existing=True))).scalar_one_or_none()
    if c is None:
        raise NotFound("Контракт не найден.")
    return c


async def create(session: AsyncSession, user_id: int, customer_id: int, *, kind: str, resource: str, qty: int,
                 price_total: int, location: str, deadline_hours: int, dest: str | None = None,
                 target_executor_id: int | None = None, terms: str | None = None) -> Contract:
    await authz.require(session, user_id, customer_id, Perm.CONTRACTS)
    if kind not in ("supply", "transport"):
        raise GameError("Неизвестный тип контракта.")
    if resource not in RESOURCES or location not in LOCATIONS:
        raise GameError("Неизвестный ресурс или локация.")
    if not 0 < qty <= 100000 or not 0 < price_total <= 10**9:
        raise GameError("Некорректные количество или цена.")
    if not 1 <= deadline_hours <= 720:
        raise GameError("Срок: от 1 до 720 часов.")
    if kind == "transport":
        if dest not in LOCATIONS or dest == location or route_km(location, dest) is None:
            raise GameError("Нужен маршрут между двумя разными локациями.")
    else:
        dest = None
    if target_executor_id is not None and await authz.same_controller(session, customer_id, target_executor_id):
        raise Forbidden("Нельзя заключить контракт с самим собой.")
    c = Contract(kind=kind, customer_id=customer_id, target_executor_id=target_executor_id, created_by_user_id=user_id,
                 resource=resource, qty=qty, price_total=price_total, fee_bps=get_settings().contract_fee_bps,
                 location_code=location, dest_code=dest, deadline=clock.now() + timedelta(hours=deadline_hours),
                 terms=(terms or "")[:500] or None, status="draft")
    session.add(c)
    await session.flush()
    await _event(session, c, "created", user_id)
    await audit(session, "contract_create", actor_user_id=user_id, account_id=customer_id, target_type="contract",
                target_id=c.id, kind=kind)
    return c


async def publish(session: AsyncSession, user_id: int, contract_id: int, op_key: str | None = None) -> Contract:
    c = await _lock(session, contract_id)
    await authz.require(session, user_id, c.customer_id, Perm.CONTRACTS)
    if c.status != "draft":
        raise GameError("Опубликовать можно только черновик.")
    await claim_operation(session, op_key, "contract_publish", user_id)
    await ledger.hold(session, c.customer_id, c.price_total, "contract_reserve", ref_type="contract", ref_id=c.id,
                      actor_user_id=user_id)
    c.reserved = c.price_total
    if c.kind == "transport":
        await stock.hold(session, c.customer_id, c.location_code, c.resource, c.qty, "contract_cargo",
                         ref_type="contract", ref_id=c.id, actor=user_id)
    c.status = "open"
    await _event(session, c, "published", user_id, reserved=c.reserved)
    return c


async def _refund_rest(session: AsyncSession, c: Contract, actor: int | None, reason: str) -> None:
    if c.reserved:
        await ledger.release(session, c.customer_id, c.reserved, "contract_refund", ref_type="contract", ref_id=c.id,
                             actor_user_id=actor, memo=reason)
        c.reserved = 0
    if c.kind == "transport" and c.shipment_id is None and c.status in ("open", "accepted", "disputed"):
        await stock.release(session, c.customer_id, c.location_code, c.resource, c.qty, "contract_cargo_release",
                            ref_type="contract", ref_id=c.id, actor=actor)


async def cancel(session: AsyncSession, user_id: int, contract_id: int, op_key: str | None = None) -> Contract:
    c = await _lock(session, contract_id)
    await authz.require(session, user_id, c.customer_id, Perm.CONTRACTS)
    if c.status not in ("draft", "open"):
        raise GameError("Отменить можно только до принятия исполнителем.")
    await claim_operation(session, op_key, "contract_cancel", user_id)
    await _refund_rest(session, c, user_id, "cancel")
    c.status = "cancelled"
    c.closed_at = clock.now()
    await _event(session, c, "cancelled", user_id)
    return c


async def _check_executor(session: AsyncSession, c: Contract, executor_id: int) -> None:
    if c.status != "open":
        raise GameError("Контракт уже не открыт для принятия.")
    if c.deadline <= clock.now():
        raise GameError("Срок контракта истёк.")
    if await authz.same_controller(session, c.customer_id, executor_id):
        raise Forbidden("Нельзя принять собственный контракт.")
    if c.target_executor_id is not None and c.target_executor_id != executor_id:
        raise Forbidden("Контракт адресован другому исполнителю.")


async def accept_supply(session: AsyncSession, user_id: int, executor_id: int, contract_id: int,
                        op_key: str | None = None) -> Contract:
    await authz.require(session, user_id, executor_id, Perm.CONTRACTS)
    c = await _lock(session, contract_id)
    if c.kind != "supply":
        raise GameError("Это контракт перевозки — примите его с машиной.")
    await _check_executor(session, c, executor_id)
    await claim_operation(session, op_key, "contract_accept", user_id)
    c.executor_id = executor_id
    c.status = "accepted"
    c.accepted_at = clock.now()
    await _event(session, c, "accepted", user_id, executor=executor_id)
    return c


async def withdraw(session: AsyncSession, user_id: int, contract_id: int) -> Contract:
    """Исполнитель отказывается до первой поставки — контракт снова открыт."""
    c = await _lock(session, contract_id)
    if c.executor_id is None:
        raise GameError("Исполнитель не назначен.")
    await authz.require(session, user_id, c.executor_id, Perm.CONTRACTS)
    if c.status != "accepted" or c.delivered_qty:
        raise GameError("Отказаться можно только до первой поставки.")
    prev = c.executor_id
    c.executor_id = None
    c.status = "open"
    c.accepted_at = None
    await _event(session, c, "withdrawn", user_id, executor=prev)
    return c


async def deliver(session: AsyncSession, user_id: int, contract_id: int, qty: int,
                  op_key: str | None = None) -> ContractFulfillment:
    c = await _lock(session, contract_id)
    if c.kind != "supply" or c.executor_id is None:
        raise GameError("Поставка невозможна.")
    await authz.require(session, user_id, c.executor_id, Perm.CONTRACTS)
    if c.status not in ("accepted", "in_progress"):
        raise GameError(f"Контракт {STATUS_RU[c.status]}.")
    if c.deadline <= clock.now():
        raise GameError("Срок контракта истёк.")
    remaining = c.qty - c.delivered_qty
    if not 0 < qty <= remaining:
        raise GameError(f"Осталось поставить {remaining}.")
    await claim_operation(session, op_key, "contract_deliver", user_id)
    # Физическая проверка: товар должен лежать у исполнителя в месте поставки.
    await stock.take(session, c.executor_id, c.location_code, c.resource, qty, "contract_delivery",
                     ref_type="contract", ref_id=c.id, actor=user_id)
    await stock.add(session, c.customer_id, c.location_code, c.resource, qty, "contract_delivery",
                    ref_type="contract", ref_id=c.id, actor=user_id, check_capacity=False)
    c.delivered_qty += qty
    gross_cum = cumulative_split(c.price_total, c.delivered_qty, c.qty)
    fee_cum = fee_for(gross_cum, c.fee_bps)
    gross = gross_cum - (c.paid_out + c.fee_paid)
    fee = fee_cum - c.fee_paid
    if gross:
        await ledger.pay_from_hold(session, "contract_payout", c.customer_id, c.executor_id, gross, fee,
                                   ref_type="contract", ref_id=c.id, actor_user_id=user_id)
    c.paid_out += gross - fee
    c.fee_paid += fee
    c.reserved -= gross
    f = ContractFulfillment(contract_id=c.id, qty=qty, payout=gross - fee, fee=fee, actor_user_id=user_id)
    session.add(f)
    c.status = "in_progress"
    if c.delivered_qty == c.qty:
        c.status = "completed"
        c.closed_at = clock.now()
        if c.reserved:
            await _refund_rest(session, c, user_id, "rounding")
    await session.flush()
    await _event(session, c, "delivered", user_id, qty=qty, payout=gross - fee, fee=fee)
    return f


async def accept_transport(session: AsyncSession, user_id: int, carrier_id: int, contract_id: int,
                           vehicle_id: int | None, op_key: str | None = None) -> Contract:
    await authz.require(session, user_id, carrier_id, Perm.CONTRACTS)
    c = await _lock(session, contract_id)
    if c.kind != "transport":
        raise GameError("Это контракт поставки.")
    await _check_executor(session, c, carrier_id)
    await claim_operation(session, op_key, "contract_accept", user_id)
    sh = await transport.plan(session, user_id, carrier_id, origin=c.location_code, dest=c.dest_code,
                              cargo={c.resource: c.qty}, vehicle_id=vehicle_id, cargo_owner=c.customer_id,
                              recipient=c.customer_id, contract_id=c.id)
    sh = await transport.depart(session, user_id, sh.id)
    if sh.eta > c.deadline:
        raise GameError("Машина не успеет к сроку контракта.")
    c.executor_id = carrier_id
    c.shipment_id = sh.id
    c.status = "in_progress"
    c.accepted_at = clock.now()
    await _event(session, c, "accepted", user_id, executor=carrier_id, shipment=sh.id, eta=sh.eta.isoformat())
    return c


async def on_transport_delivered(session: AsyncSession, contract_id: int, shipment_id: int) -> None:
    """Вызывается из transport.arrive в той же транзакции. Идемпотентно по статусу."""
    c = await _lock(session, contract_id)
    if c.status != "in_progress" or c.shipment_id != shipment_id:
        return
    fee = fee_for(c.price_total, c.fee_bps)
    await ledger.pay_from_hold(session, "contract_payout", c.customer_id, c.executor_id, c.price_total, fee,
                               ref_type="contract", ref_id=c.id)
    c.paid_out = c.price_total - fee
    c.fee_paid = fee
    c.reserved = 0
    c.delivered_qty = c.qty
    c.status = "completed"
    c.closed_at = clock.now()
    session.add(ContractFulfillment(contract_id=c.id, qty=c.qty, payout=c.paid_out, fee=fee))
    await _event(session, c, "delivered", None, shipment=shipment_id, payout=c.paid_out, fee=fee)


async def dispute(session: AsyncSession, user_id: int, contract_id: int, reason: str) -> Contract:
    c = await _lock(session, contract_id)
    if c.kind != "supply":
        raise GameError("Перевозка подтверждается сервером; спор доступен для поставок.")
    party = None
    for acc in (c.customer_id, c.executor_id):
        if acc is None:
            continue
        try:
            await authz.require(session, user_id, acc, Perm.CONTRACTS)
            party = acc
            break
        except Forbidden:
            continue
    if party is None:
        raise Forbidden("Вы не участник контракта.")
    if c.status not in ("accepted", "in_progress"):
        raise GameError("Спор возможен только по исполняемому контракту.")
    c.status_before_dispute = c.status
    c.status = "disputed"
    await _event(session, c, "disputed", user_id, reason=reason[:500], party=party)
    await audit(session, "contract_dispute", actor_user_id=user_id, account_id=party, target_type="contract",
                target_id=c.id, reason=reason[:500])
    return c


async def admin_resolve(session: AsyncSession, admin_user_id: int | None, contract_id: int, decision: str,
                        note: str = "") -> Contract:
    """decision: refund — остаток резерва заказчику, контракт отменён; resume — продолжить, срок +24 ч."""
    c = await _lock(session, contract_id)
    if c.status != "disputed":
        raise GameError("Контракт не в споре.")
    if decision == "refund":
        await _refund_rest(session, c, admin_user_id, "dispute_refund")
        c.status = "cancelled"
        c.closed_at = clock.now()
    elif decision == "resume":
        c.status = c.status_before_dispute or "accepted"
        c.deadline = max(c.deadline, clock.now() + timedelta(hours=24))
    else:
        raise GameError("Решение: refund или resume.")
    await _event(session, c, f"resolved_{decision}", admin_user_id, note=note[:500])
    await audit(session, "admin_contract_resolve", actor_user_id=admin_user_id, target_type="contract",
                target_id=c.id, decision=decision, note=note[:500])
    return c


async def expire_due(session: AsyncSession, contract_id: int) -> bool:
    c = await _lock(session, contract_id)
    if c.status not in ACTIVE or c.deadline > clock.now():
        return False
    if c.kind == "transport" and c.status == "in_progress":
        return False  # машина в пути: доставка будет подтверждена сервером
    await _refund_rest(session, c, None, "expired")
    c.status = "expired"
    c.closed_at = clock.now()
    await _event(session, c, "expired", None, delivered=c.delivered_qty)
    return True


async def due_contract_ids(session: AsyncSession, limit: int = 100) -> list[int]:
    return list((await session.scalars(
        select(Contract.id).where(Contract.status.in_(ACTIVE), Contract.deadline <= clock.now())
        .order_by(Contract.deadline).limit(limit))).all())


async def list_open(session: AsyncSession, kind: str | None = None, limit: int = 10) -> list[Contract]:
    q = select(Contract).where(Contract.status == "open", Contract.deadline > clock.now())
    if kind:
        q = q.where(Contract.kind == kind)
    return list((await session.scalars(q.order_by(Contract.id.desc()).limit(limit))).all())


async def list_mine(session: AsyncSession, account_id: int, limit: int = 15) -> list[Contract]:
    return list((await session.scalars(
        select(Contract).where((Contract.customer_id == account_id) | (Contract.executor_id == account_id))
        .order_by(Contract.id.desc()).limit(limit))).all())


async def events(session: AsyncSession, contract_id: int) -> list[ContractEvent]:
    return list((await session.scalars(select(ContractEvent).where(ContractEvent.contract_id == contract_id)
                                       .order_by(ContractEvent.id))).all())
