"""Проверка права пользователя действовать от имени владельца (себя или компании)."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ironvein.domain.errors import Forbidden
from ironvein.domain.permissions import PERM_RU, Perm
from ironvein.models import Company, CompanyMember, User


async def require(session: AsyncSession, user_id: int, account_id: int, perm: Perm) -> None:
    user = await session.get(User, user_id)
    if user is None or user.is_banned:
        raise Forbidden("Аккаунт заблокирован.")
    if account_id == user_id:
        return
    row = (await session.execute(
        select(CompanyMember.permissions, Company.status)
        .join(Company, Company.id == CompanyMember.company_id)
        .where(CompanyMember.company_id == account_id, CompanyMember.user_id == user_id)
        .with_for_update(of=CompanyMember, read=True))).first()
    if row is None:
        raise Forbidden("Вы не можете действовать от имени этого владельца.")
    perms, status = row
    if status != "active":
        raise Forbidden("Компания закрыта.")
    if not Perm(perms) & perm:
        raise Forbidden(f"Нет права «{PERM_RU.get(perm, str(perm))}» в этой компании.")


async def controller_user_id(session: AsyncSession, account_id: int) -> int | None:
    """Пользователь, фактически распоряжающийся счётом: сам игрок или владелец компании."""
    if await session.get(User, account_id) is not None:
        return account_id
    return await session.scalar(select(Company.owner_user_id).where(Company.id == account_id))


async def same_controller(session: AsyncSession, a: int, b: int) -> bool:
    if a == b:
        return True
    ca, cb = await controller_user_id(session, a), await controller_user_id(session, b)
    return ca is not None and ca == cb
