"""Аналитика и проверка инвариантов экономики. Только наблюдение — никакого вмешательства в цены."""

from datetime import timedelta

from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ironvein.models import (
    ACC_COMPANY,
    ACC_SYSTEM,
    ACC_USER,
    SYS_EMISSION,
    SYS_FEES,
    Account,
    Contract,
    Deposit,
    Job,
    LedgerEntry,
    LedgerTx,
    MarketOrder,
    MarketTrade,
    PremiumOrder,
    Shipment,
    ShipmentCargo,
    Stock,
    StockMovement,
    Wallet,
)
from ironvein.services import clock


async def _sys_balance(session: AsyncSession, code: str) -> int:
    return int(await session.scalar(
        select(func.coalesce(func.sum(Wallet.balance), 0)).join(Account, Account.id == Wallet.account_id)
        .where(Account.code == code)) or 0)


async def integrity_report(session: AsyncSession) -> dict:
    """Сверка: эмиссия - комиссии = деньги у владельцев; кошельки = сумма проводок; резервы = обязательства."""
    emitted = -await _sys_balance(session, SYS_EMISSION)
    burned = await _sys_balance(session, SYS_FEES)
    circulating = int(await session.scalar(
        select(func.coalesce(func.sum(Wallet.balance), 0)).join(Account, Account.id == Wallet.account_id)
        .where(Account.kind != ACC_SYSTEM)) or 0)
    mismatched_wallets = (await session.execute(
        select(Wallet.id).outerjoin(LedgerEntry, LedgerEntry.wallet_id == Wallet.id)
        .group_by(Wallet.id, Wallet.balance)
        .having(func.coalesce(func.sum(LedgerEntry.delta), 0) != Wallet.balance))).scalars().all()
    unbalanced_tx = (await session.execute(
        select(LedgerEntry.tx_id).group_by(LedgerEntry.tx_id).having(func.sum(LedgerEntry.delta) != 0)
    )).scalars().all()

    # Деньги в hold каждого владельца = резерв открытых bid + резерв активных контрактов.
    hold = dict((await session.execute(
        select(Wallet.account_id, Wallet.balance).where(Wallet.kind == "hold", Wallet.balance != 0))).all())
    owed: dict[int, int] = {}
    for acc, amt in (await session.execute(
            select(MarketOrder.owner_id, func.sum(MarketOrder.reserved)).where(MarketOrder.status == "open")
            .group_by(MarketOrder.owner_id))).all():
        owed[acc] = owed.get(acc, 0) + int(amt)
    for acc, amt in (await session.execute(
            select(Contract.customer_id, func.sum(Contract.reserved)).group_by(Contract.customer_id))).all():
        owed[acc] = owed.get(acc, 0) + int(amt)
    owed = {k: v for k, v in owed.items() if v}
    hold_mismatch = {a: (hold.get(a, 0), owed.get(a, 0)) for a in set(hold) | set(owed) if hold.get(a, 0) != owed.get(a, 0)}

    # Заблокированные ресурсы = открытые ask + груз в активных рейсах + груз открытых контрактов перевозки.
    held = {(o, l, r): int(h) for o, l, r, h in (await session.execute(
        select(Stock.owner_id, Stock.location_code, Stock.resource, Stock.held).where(Stock.held != 0))).all()}
    need: dict[tuple, int] = {}

    def acc(k, v):
        need[k] = need.get(k, 0) + int(v)

    for o, l, r, q in (await session.execute(
            select(MarketOrder.owner_id, MarketOrder.location_code, MarketOrder.resource, func.sum(MarketOrder.qty_left))
            .where(MarketOrder.status == "open", MarketOrder.side == "ask", MarketOrder.resource.is_not(None))
            .group_by(MarketOrder.owner_id, MarketOrder.location_code, MarketOrder.resource))).all():
        acc((o, l, r), q)
    for o, l, r, q in (await session.execute(
            select(ShipmentCargo.owner_id, Shipment.origin, ShipmentCargo.resource, func.sum(ShipmentCargo.qty))
            .join(Shipment, Shipment.id == ShipmentCargo.shipment_id)
            .where(Shipment.status == "loading", ShipmentCargo.resource.is_not(None))
            .group_by(ShipmentCargo.owner_id, Shipment.origin, ShipmentCargo.resource))).all():
        acc((o, l, r), q)
    for o, l, r, q in (await session.execute(
            select(Contract.customer_id, Contract.location_code, Contract.resource, func.sum(Contract.qty))
            .where(Contract.kind == "transport", Contract.status.in_(("open", "accepted", "disputed")),
                   Contract.shipment_id.is_(None))
            .group_by(Contract.customer_id, Contract.location_code, Contract.resource))).all():
        acc((o, l, r), q)
    need = {k: v for k, v in need.items() if v}
    stock_mismatch = {str(k): (held.get(k, 0), need.get(k, 0)) for k in set(held) | set(need)
                      if held.get(k, 0) != need.get(k, 0)}

    ok = (circulating == emitted - burned and not mismatched_wallets and not unbalanced_tx
          and not hold_mismatch and not stock_mismatch)
    return {
        "ok": ok, "emitted": emitted, "burned": burned, "circulating": circulating,
        "mismatched_wallets": list(mismatched_wallets), "unbalanced_tx": list(unbalanced_tx),
        "hold_mismatch": hold_mismatch, "stock_mismatch": stock_mismatch,
    }


async def economy_overview(session: AsyncSession, hours: int = 24) -> dict:
    since = clock.now() - timedelta(hours=hours)
    rep = await integrity_report(session)
    by_kind = dict((await session.execute(
        select(Account.kind, func.coalesce(func.sum(Wallet.balance), 0))
        .join(Account, Account.id == Wallet.account_id).where(Account.kind != ACC_SYSTEM)
        .group_by(Account.kind))).all())
    reserves = int(await session.scalar(
        select(func.coalesce(func.sum(Wallet.balance), 0)).join(Account, Account.id == Wallet.account_id)
        .where(Wallet.kind == "hold", Account.kind != ACC_SYSTEM)) or 0)
    fees_period = int(await session.scalar(
        select(func.coalesce(func.sum(MarketTrade.fee), 0)).where(MarketTrade.created_at >= since)) or 0)
    trades = (await session.execute(
        select(func.coalesce(MarketTrade.resource, MarketTrade.item_def), MarketTrade.location_code,
               func.sum(MarketTrade.qty), func.sum(MarketTrade.gross), func.count())
        .where(MarketTrade.created_at >= since)
        .group_by(func.coalesce(MarketTrade.resource, MarketTrade.item_def), MarketTrade.location_code))).all()
    flows = (await session.execute(
        select(StockMovement.reason, StockMovement.resource, func.sum(StockMovement.delta_free + StockMovement.delta_held))
        .where(StockMovement.created_at >= since,
               StockMovement.reason.in_(("mine_output", "craft_output", "craft_input", "fuel_mining", "fuel_trip",
                                         "repair_input")))
        .group_by(StockMovement.reason, StockMovement.resource))).all()
    deposits = (await session.execute(select(Deposit.name, Deposit.resource, Deposit.stock, Deposit.max_stock)
                                      .order_by(Deposit.id))).all()
    jobs_running = int(await session.scalar(select(func.count()).select_from(Job).where(Job.status == "running")) or 0)
    ships = dict((await session.execute(select(Shipment.status, func.count()).group_by(Shipment.status))).all())
    lanes = (await session.execute(
        select(Shipment.origin, Shipment.dest, func.count(), func.sum(Shipment.fuel))
        .where(Shipment.departed_at >= since).group_by(Shipment.origin, Shipment.dest))).all()
    contracts = dict((await session.execute(select(Contract.status, func.count()).group_by(Contract.status))).all())
    stars = (await session.execute(
        select(PremiumOrder.status, func.count(), func.coalesce(func.sum(PremiumOrder.price_stars), 0))
        .group_by(PremiumOrder.status))).all()
    premium_resales = (await session.execute(
        select(func.count(), func.coalesce(func.sum(MarketTrade.gross), 0))
        .where(MarketTrade.item_def.in_(("engineer_watch", "paint_black_brass", "syndicate_crest"))))).one()
    return {
        "integrity": rep, "money_by_kind": by_kind, "reserves": reserves, "fees_period": fees_period,
        "trades": trades, "flows": flows, "deposits": deposits, "jobs_running": jobs_running, "shipments": ships,
        "lanes": lanes, "contracts": contracts, "stars": stars, "premium_resales": tuple(premium_resales),
        "concentration": await wealth_concentration(session),
    }


async def wealth_concentration(session: AsyncSession, top: int = 5) -> dict:
    """Доля крупнейших владельцев в денежной массе и индекс Херфиндаля (0..10000)."""
    rows = (await session.execute(
        select(Account.id, Account.name, Account.kind, func.sum(Wallet.balance).label("b"))
        .join(Wallet, Wallet.account_id == Account.id).where(Account.kind.in_((ACC_USER, ACC_COMPANY)))
        .group_by(Account.id).order_by(func.sum(Wallet.balance).desc()))).all()
    total = sum(int(r.b) for r in rows) or 1
    hhi = sum((int(r.b) * 10000 // total) ** 2 for r in rows) // 10000
    return {
        "holders": len(rows),
        "top": [(r.name, r.kind, int(r.b), int(r.b) * 100 / total) for r in rows[:top]],
        "top_share_pct": sum(int(r.b) for r in rows[:top]) * 100 / total,
        "hhi": hhi,
    }


async def last_price(session: AsyncSession, *, resource: str | None = None, item_def: str | None = None,
                     location: str | None = None) -> tuple[int, int] | None:
    q = select(MarketTrade.price, MarketTrade.qty).order_by(MarketTrade.id.desc()).limit(1)
    if resource:
        q = q.where(MarketTrade.resource == resource)
    if item_def:
        q = q.where(MarketTrade.item_def == item_def)
    if location:
        q = q.where(MarketTrade.location_code == location)
    row = (await session.execute(q)).first()
    return (row.price, row.qty) if row else None


__all__ = ["integrity_report", "economy_overview", "wealth_concentration", "last_price", "and_", "case", "LedgerTx"]
