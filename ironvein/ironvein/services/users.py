"""Регистрация и профиль. Стартовый капитал — учтённая однократная эмиссия."""

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ironvein.config import get_settings
from ironvein.domain.catalog import START_LOCATION
from ironvein.domain.errors import NotFound
from ironvein.models import ACC_USER, Account, User, Wallet
from ironvein.services import items, ledger
from ironvein.services.common import audit


async def create_wallets(session: AsyncSession, account_id: int) -> None:
    for kind in ("main", "hold"):
        await session.execute(pg_insert(Wallet).values(account_id=account_id, kind=kind, balance=0)
                              .on_conflict_do_nothing())


async def get_or_register(session: AsyncSession, tg_id: int, display_name: str,
                          username: str | None = None) -> tuple[User, bool]:
    """Возвращает (user, created). Безопасно при гонке двух апдейтов: уникальность tg_id в БД."""
    user = await session.scalar(select(User).where(User.tg_id == tg_id))
    if user is not None:
        if username != user.username:
            user.username = username
        return user, False
    name = (display_name or f"Промышленник {tg_id}")[:64]
    try:
        async with session.begin_nested():
            acc = Account(kind=ACC_USER, name=name)
            session.add(acc)
            await session.flush()
            session.add(User(id=acc.id, tg_id=tg_id, username=username, display_name=name, acting_account_id=acc.id))
            await session.flush()
    except IntegrityError:
        # Параллельная регистрация того же tg_id успела раньше: точка сохранения откатилась целиком.
        user = await session.scalar(select(User).where(User.tg_id == tg_id))
        return user, False
    await create_wallets(session, acc.id)
    await grant_starter(session, acc.id)
    user = await session.get(User, acc.id)
    return user, True


async def grant_starter(session: AsyncSession, user_id: int) -> bool:
    """Стартовый набор выдаётся строго один раз: флаг меняется атомарно условным UPDATE."""
    res = await session.execute(update(User).where(User.id == user_id, User.starter_granted.is_(False))
                                .values(starter_granted=True).returning(User.id))
    if res.scalar_one_or_none() is None:
        return False
    s = get_settings()
    if s.starter_crowns > 0:
        await ledger.post(session, "starter", [
            (await ledger.emission_wallet(session), -s.starter_crowns),
            (await ledger.wallet(session, user_id), s.starter_crowns),
        ], ref_type="user", ref_id=user_id, actor_user_id=user_id, memo="стартовый капитал")
    await items.create(session, "pick", user_id, START_LOCATION, "starter", origin_ref=f"user:{user_id}", actor=user_id)
    await audit(session, "starter_granted", actor_user_id=user_id, account_id=user_id, crowns=s.starter_crowns)
    return True


async def by_tg(session: AsyncSession, tg_id: int) -> User:
    user = await session.scalar(select(User).where(User.tg_id == tg_id))
    if user is None:
        raise NotFound("Сначала нажмите /start.")
    return user


async def find_user(session: AsyncSession, ref: str) -> User | None:
    ref = ref.strip().lstrip("@")
    if ref.isdigit():
        u = await session.get(User, int(ref))
        if u is None:
            u = await session.scalar(select(User).where(User.tg_id == int(ref)))
        return u
    return await session.scalar(select(User).where(User.username.ilike(ref)))
