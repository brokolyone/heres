from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ironvein.models import Account, Wallet


async def wallet_ids(session: AsyncSession, account_id: int) -> dict[str, int]:
    rows = await session.execute(select(Wallet.kind, Wallet.id).where(Wallet.account_id == account_id))
    return {k: i for k, i in rows}


async def lock_wallets(session: AsyncSession, ids: list[int]) -> dict[int, Wallet]:
    """Блокирует строки кошельков в порядке id — единый порядок исключает взаимоблокировки."""
    ids = sorted(set(ids))
    rows = (await session.execute(
        select(Wallet).where(Wallet.id.in_(ids)).order_by(Wallet.id).with_for_update())).scalars().all()
    return {w.id: w for w in rows}


async def system_account_id(session: AsyncSession, code: str) -> int:
    acc = await session.scalar(select(Account.id).where(Account.code == code))
    if acc is None:
        raise RuntimeError(f"system account {code} missing; run ensure_world()")
    return acc


async def balances(session: AsyncSession, account_id: int) -> dict[str, int]:
    rows = await session.execute(select(Wallet.kind, Wallet.balance).where(Wallet.account_id == account_id))
    return {k: b for k, b in rows}
