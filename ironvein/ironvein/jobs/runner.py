"""Фоновые задачи. Каждый объект обрабатывается в собственной транзакции под блокировкой строки,
поэтому повторный проход, параллельный процесс или рестарт не приводят к двойной выдаче."""

import asyncio
import logging
from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ironvein.services import contracts, premium, production, transport

log = logging.getLogger(__name__)

Notifier = Callable[[str, dict], Awaitable[None]]
_pending: set[asyncio.Task] = set()


def _fire(notify: Notifier, kind: str, data: dict) -> None:
    """Уведомление уходит фоновой задачей: flood control Telegram не задерживает экономику."""
    async def run():
        try:
            await notify(kind, data)
        except Exception:
            log.exception("notification %s %s failed", kind, data)
    task = asyncio.create_task(run())
    _pending.add(task)
    task.add_done_callback(_pending.discard)


async def drain_notifications() -> None:
    """Дождаться отправки уведомлений (тесты, корректное завершение)."""
    while _pending:
        await asyncio.gather(*list(_pending), return_exceptions=True)


Refunder = Callable[[int, str], Awaitable[bool]]


async def _each(sm: async_sessionmaker[AsyncSession], ids_fn, handle_fn, kind: str, notify: Notifier | None) -> int:
    async with sm() as s:
        ids = await ids_fn(s)
    done = 0
    for i in ids:
        try:
            async with sm() as s, s.begin():
                ok = await handle_fn(s, i)
            if ok:
                done += 1
                if notify:
                    _fire(notify, kind, {"id": i})
        except Exception:  # одна сломанная запись не должна останавливать остальные
            log.exception("job %s %s failed", kind, i)
    return done


async def run_once(sm: async_sessionmaker[AsyncSession], notify: Notifier | None = None,
                   refund: Refunder | None = None, wait_notifications: bool = True) -> dict:
    res = {
        "jobs": await _each(sm, production.due_job_ids, production.complete_job, "job", notify),
        "shipments": await _each(sm, transport.due_shipment_ids, transport.arrive, "shipment", notify),
        "contracts": await _each(sm, contracts.due_contract_ids, contracts.expire_due, "contract_expired", notify),
    }
    async with sm() as s, s.begin():
        res["reservations_expired"] = await premium.expire_reservations(s)
    async with sm() as s, s.begin():
        res["premium_retried"] = await premium.retry_paid(s)
    res["refunds"] = 0
    if refund is not None:
        async with sm() as s:
            pending = await premium.refund_pending(s)
        for order_id, tg_id, charge_id in pending:
            try:
                if await refund(tg_id, charge_id):
                    async with sm() as s, s.begin():
                        await premium.mark_refunded(s, order_id=order_id, source="auto")
                    res["refunds"] += 1
                    if notify:
                        _fire(notify, "refund", {"id": order_id})
            except Exception:
                log.exception("refund for order %s failed", order_id)
    if notify is not None and wait_notifications:
        await drain_notifications()
    return res


async def run_forever(sm: async_sessionmaker[AsyncSession], interval: float, notify: Notifier | None = None,
                      refund: Refunder | None = None) -> None:
    while True:
        try:
            await run_once(sm, notify, refund, wait_notifications=False)
        except Exception:
            log.exception("job loop iteration failed")
        await asyncio.sleep(interval)
