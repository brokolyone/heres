from sqlalchemy import insert, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ironvein.domain.errors import AlreadyDone
from ironvein.models import AuditLog, Operation


async def audit(session: AsyncSession, action: str, *, actor_user_id: int | None = None,
                account_id: int | None = None, target_type: str | None = None,
                target_id: int | None = None, **data) -> None:
    await session.execute(insert(AuditLog).values(
        actor_user_id=actor_user_id, account_id=account_id, action=action,
        target_type=target_type, target_id=target_id, data=data))


async def claim_operation(session: AsyncSession, key: str | None, kind: str, actor_user_id: int | None) -> None:
    """Регистрирует ключ идемпотентности внутри текущей транзакции.

    Если ключ уже был использован — операция уже выполнена (повторное нажатие/повторный update).
    Ключ фиксируется только вместе с самой операцией: при откате транзакции его можно повторить.
    """
    if not key:
        return
    res = await session.execute(
        pg_insert(Operation).values(key=key[:96], kind=kind, actor_user_id=actor_user_id)
        .on_conflict_do_nothing().returning(Operation.key))
    if res.scalar_one_or_none() is None:
        raise AlreadyDone("Эта операция уже выполнена.")


async def operation_done(session: AsyncSession, key: str) -> bool:
    return (await session.scalar(select(Operation.key).where(Operation.key == key))) is not None
