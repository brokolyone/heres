"""Единый денежный журнал (двойная запись).

Каждое движение крон — транзакция из проводок с нулевой суммой. Единственный источник денег —
системный счёт эмиссии (его баланс отрицателен и равен всей выпущенной массе), единственный сток —
системный счёт комиссий. Нулевая сумма дополнительно проверяется отложенным триггером PostgreSQL.
"""

from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from ironvein.domain.errors import GameError
from ironvein.domain.money import fmt_cr
from ironvein.models import SYS_EMISSION, SYS_FEES, LedgerEntry, LedgerTx
from ironvein.repositories.wallets import lock_wallets, system_account_id, wallet_ids


class InsufficientFunds(GameError):
    pass


async def post(session: AsyncSession, kind: str, postings: list[tuple[int, int]], *,
               ref_type: str | None = None, ref_id: int | None = None,
               actor_user_id: int | None = None, memo: str | None = None) -> int:
    """postings: [(wallet_id, delta)]. Сумма обязана быть 0."""
    postings = [(w, d) for w, d in postings if d != 0]
    if sum(d for _, d in postings) != 0:
        raise ValueError(f"unbalanced ledger tx {kind}: {postings}")
    if not postings:
        return 0
    wallets = await lock_wallets(session, [w for w, _ in postings])
    for w_id, d in postings:
        w = wallets[w_id]
        if not w.allow_negative and w.balance + d < 0:
            raise InsufficientFunds(f"Недостаточно средств: нужно {fmt_cr(-d)}, доступно {fmt_cr(w.balance)}.")
    tx_id = (await session.execute(insert(LedgerTx).values(
        kind=kind, ref_type=ref_type, ref_id=ref_id, actor_user_id=actor_user_id, memo=memo
    ).returning(LedgerTx.id))).scalar_one()
    for w_id, d in postings:
        w = wallets[w_id]
        w.balance += d
        await session.execute(insert(LedgerEntry).values(tx_id=tx_id, wallet_id=w_id, delta=d, balance_after=w.balance))
    await session.flush()
    return tx_id


async def wallet(session: AsyncSession, account_id: int, kind: str = "main") -> int:
    return (await wallet_ids(session, account_id))[kind]


async def transfer(session: AsyncSession, kind: str, amount: int, src: tuple[int, str], dst: tuple[int, str],
                   **kw) -> int:
    """Перевод amount с (account, wallet_kind) на (account, wallet_kind)."""
    if amount <= 0:
        raise ValueError("amount must be positive")
    s = await wallet(session, *src)
    d = await wallet(session, *dst)
    return await post(session, kind, [(s, -amount), (d, amount)], **kw)


async def hold(session: AsyncSession, account_id: int, amount: int, kind: str, **kw) -> None:
    """Резерв: main -> hold того же владельца."""
    if amount > 0:
        await transfer(session, kind, amount, (account_id, "main"), (account_id, "hold"), **kw)


async def release(session: AsyncSession, account_id: int, amount: int, kind: str, **kw) -> None:
    if amount > 0:
        await transfer(session, kind, amount, (account_id, "hold"), (account_id, "main"), **kw)


async def emission_wallet(session: AsyncSession) -> int:
    return await wallet(session, await system_account_id(session, SYS_EMISSION))


async def fee_wallet(session: AsyncSession) -> int:
    return await wallet(session, await system_account_id(session, SYS_FEES))


async def pay_from_hold(session: AsyncSession, kind: str, payer: int, payee: int, gross: int, fee: int,
                        payee_wallet: str = "main", **kw) -> None:
    """Расчёт из резерва плательщика: получателю gross - fee, комиссия уничтожается."""
    ph = await wallet(session, payer, "hold")
    pe = await wallet(session, payee, payee_wallet)
    fw = await fee_wallet(session)
    await post(session, kind, [(ph, -gross), (pe, gross - fee), (fw, fee)], **kw)


async def burn(session: AsyncSession, account_id: int, amount: int, kind: str, **kw) -> None:
    """Сбор (например, регистрация компании) — уничтожение крон."""
    await post(session, kind, [(await wallet(session, account_id), -amount), (await fee_wallet(session), amount)], **kw)
