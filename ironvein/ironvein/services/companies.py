"""Компании и синдикаты.

Компания — самостоятельный владелец (accounts.kind = company): свой кошелёк, склады, оборудование,
транспорт, заявки и контракты. Никаких бонусов за факт существования. Регистрационная плата уничтожается.
Все действия от имени компании проходят через authz.require и журналируются с ID инициатора.
"""

import re

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ironvein.config import get_settings
from ironvein.domain.errors import Forbidden, GameError, NotFound
from ironvein.domain.permissions import ALL, ROLE_DEFAULTS, Perm
from ironvein.models import (
    ACC_COMPANY,
    ITEM_DESTROYED,
    Account,
    Company,
    CompanyInvite,
    CompanyMember,
    Contract,
    Item,
    Job,
    MarketOrder,
    Shipment,
    Stock,
    User,
    Wallet,
)
from ironvein.services import authz, clock, items, ledger, stock
from ironvein.services.common import audit, claim_operation
from ironvein.services.users import create_wallets

NAME_RE = re.compile(r"^[\w\-\s«»\"'.&]{3,32}$", re.UNICODE)


async def _company(session: AsyncSession, company_id: int, lock: bool = False) -> Company:
    q = select(Company).where(Company.id == company_id)
    if lock:
        q = q.with_for_update().execution_options(populate_existing=True)
    c = (await session.execute(q)).scalar_one_or_none()
    if c is None:
        raise NotFound("Компания не найдена.")
    return c


async def create(session: AsyncSession, user_id: int, name: str, op_key: str | None = None) -> Company:
    await authz.require(session, user_id, user_id, Perm.WITHDRAW)
    name = " ".join(name.split())
    if not NAME_RE.match(name):
        raise GameError("Название: 3–32 символа, буквы, цифры, пробелы и простая пунктуация.")
    await claim_operation(session, op_key, "company_create", user_id)
    fee = get_settings().company_fee
    try:
        async with session.begin_nested():
            acc = Account(kind=ACC_COMPANY, name=name)
            session.add(acc)
            await session.flush()
            comp = Company(id=acc.id, name=name, owner_user_id=user_id, status="active")
            session.add(comp)
            await session.flush()
    except IntegrityError:
        raise GameError("Компания с таким названием уже существует.")
    await create_wallets(session, acc.id)
    session.add(CompanyMember(company_id=acc.id, user_id=user_id, role="owner", permissions=int(ALL)))
    if fee:
        await ledger.burn(session, user_id, fee, "company_fee", ref_type="company", ref_id=acc.id,
                          actor_user_id=user_id, memo=f"регистрация «{name}»")
    await audit(session, "company_create", actor_user_id=user_id, account_id=acc.id, target_type="company",
                target_id=acc.id, name=name, fee=fee)
    await session.flush()
    return comp


async def memberships(session: AsyncSession, user_id: int) -> list[tuple[Company, CompanyMember]]:
    rows = (await session.execute(
        select(Company, CompanyMember).join(CompanyMember, CompanyMember.company_id == Company.id)
        .where(CompanyMember.user_id == user_id, Company.status == "active").order_by(Company.id))).all()
    return [(c, m) for c, m in rows]


async def members(session: AsyncSession, company_id: int) -> list[tuple[CompanyMember, User]]:
    rows = (await session.execute(
        select(CompanyMember, User).join(User, User.id == CompanyMember.user_id)
        .where(CompanyMember.company_id == company_id).order_by(CompanyMember.joined_at))).all()
    return [(m, u) for m, u in rows]


async def member(session: AsyncSession, company_id: int, user_id: int) -> CompanyMember | None:
    return await session.get(CompanyMember, (company_id, user_id))


# --- Состав ------------------------------------------------------------------------------------------


async def invite(session: AsyncSession, user_id: int, company_id: int, target_user_id: int,
                 role: str = "employee") -> CompanyInvite:
    await authz.require(session, user_id, company_id, Perm.INVITE)
    if role not in ("manager", "employee"):
        raise GameError("Можно пригласить управляющего или сотрудника.")
    if role == "manager":
        await authz.require(session, user_id, company_id, Perm.MEMBERS)
    target = await session.get(User, target_user_id)
    if target is None or target.is_banned:
        raise NotFound("Игрок не найден.")
    if await member(session, company_id, target_user_id):
        raise GameError("Игрок уже состоит в компании.")
    try:
        async with session.begin_nested():
            inv = CompanyInvite(company_id=company_id, user_id=target_user_id, invited_by=user_id, role=role)
            session.add(inv)
            await session.flush()
    except IntegrityError:
        raise GameError("Приглашение уже отправлено.")
    await audit(session, "company_invite", actor_user_id=user_id, account_id=company_id, target_type="user",
                target_id=target_user_id, role=role)
    return inv


async def pending_invites(session: AsyncSession, user_id: int) -> list[tuple[CompanyInvite, Company]]:
    rows = (await session.execute(
        select(CompanyInvite, Company).join(Company, Company.id == CompanyInvite.company_id)
        .where(CompanyInvite.user_id == user_id, CompanyInvite.status == "pending", Company.status == "active"))).all()
    return [(i, c) for i, c in rows]


async def answer_invite(session: AsyncSession, user_id: int, invite_id: int, accept: bool) -> CompanyInvite:
    inv = (await session.execute(select(CompanyInvite).where(CompanyInvite.id == invite_id).with_for_update())
           ).scalar_one_or_none()
    if inv is None or inv.user_id != user_id:
        raise NotFound("Приглашение не найдено.")
    if inv.status != "pending":
        raise GameError("Приглашение уже обработано.")
    comp = await _company(session, inv.company_id)
    if comp.status != "active":
        raise GameError("Компания закрыта.")
    inv.status = "accepted" if accept else "declined"
    if accept and not await member(session, inv.company_id, user_id):
        session.add(CompanyMember(company_id=inv.company_id, user_id=user_id, role=inv.role,
                                  permissions=int(ROLE_DEFAULTS[inv.role])))
    await audit(session, "company_join" if accept else "company_decline", actor_user_id=user_id,
                account_id=inv.company_id, target_type="invite", target_id=inv.id)
    await session.flush()
    return inv


async def set_role(session: AsyncSession, user_id: int, company_id: int, target_user_id: int, role: str,
                   permissions: int | None = None) -> CompanyMember:
    await authz.require(session, user_id, company_id, Perm.MEMBERS)
    comp = await _company(session, company_id)
    if role not in ("manager", "employee"):
        raise GameError("Роль владельца передаётся отдельной операцией.")
    m = await member(session, company_id, target_user_id)
    if m is None:
        raise NotFound("Участник не найден.")
    if m.role == "owner" or target_user_id == comp.owner_user_id:
        raise Forbidden("Нельзя менять права владельца.")
    if user_id != comp.owner_user_id and (m.role == "manager" or role == "manager"):
        raise Forbidden("Управляющих назначает только владелец.")
    perms = int(ROLE_DEFAULTS[role]) if permissions is None else int(permissions) & int(ALL)
    if user_id != comp.owner_user_id:
        perms &= ~int(Perm.WITHDRAW | Perm.MEMBERS)  # только владелец раздаёт право вывода денег
    m.role, m.permissions = role, perms
    await audit(session, "company_set_role", actor_user_id=user_id, account_id=company_id, target_type="user",
                target_id=target_user_id, role=role, permissions=perms)
    return m


async def toggle_permission(session: AsyncSession, user_id: int, company_id: int, target_user_id: int,
                            perm: Perm) -> CompanyMember:
    m = await member(session, company_id, target_user_id)
    if m is None:
        raise NotFound("Участник не найден.")
    return await set_role(session, user_id, company_id, target_user_id, m.role, m.permissions ^ int(perm))


async def remove_member(session: AsyncSession, user_id: int, company_id: int, target_user_id: int) -> None:
    """Исключение (право MEMBERS) или выход (target == user). Активы компании остаются у компании."""
    comp = await _company(session, company_id, lock=True)
    if target_user_id != user_id:
        await authz.require(session, user_id, company_id, Perm.MEMBERS)
    if target_user_id == comp.owner_user_id:
        raise Forbidden("Владелец не может выйти: сначала передайте компанию или закройте её.")
    m = await member(session, company_id, target_user_id)
    if m is None:
        raise NotFound("Участник не найден.")
    if m.role == "manager" and user_id not in (comp.owner_user_id, target_user_id):
        raise Forbidden("Управляющего исключает только владелец.")
    await session.delete(m)
    u = await session.get(User, target_user_id)
    if u.acting_account_id == company_id:
        u.acting_account_id = u.id
    await audit(session, "company_leave" if target_user_id == user_id else "company_kick", actor_user_id=user_id,
                account_id=company_id, target_type="user", target_id=target_user_id)


async def transfer_ownership(session: AsyncSession, user_id: int, company_id: int, new_owner_id: int,
                             *, admin: bool = False) -> None:
    comp = await _company(session, company_id, lock=True)
    if not admin and user_id != comp.owner_user_id:
        raise Forbidden("Только владелец может передать компанию.")
    new = await member(session, company_id, new_owner_id)
    if new is None:
        raise GameError("Новый владелец должен состоять в компании.")
    old = await member(session, company_id, comp.owner_user_id)
    if old is not None:
        old.role, old.permissions = "manager", int(ROLE_DEFAULTS["manager"])
    new.role, new.permissions = "owner", int(ALL)
    comp.owner_user_id = new_owner_id
    await audit(session, "company_transfer", actor_user_id=user_id, account_id=company_id, target_type="user",
                target_id=new_owner_id, admin=admin)


# --- Деньги ------------------------------------------------------------------------------------------


async def deposit(session: AsyncSession, user_id: int, company_id: int, amount: int, op_key: str | None = None) -> None:
    """Пополнение корпоративного счёта из личного кошелька (любой участник)."""
    if await member(session, company_id, user_id) is None:
        raise Forbidden("Вы не состоите в этой компании.")
    await authz.require(session, user_id, user_id, Perm.WITHDRAW)
    if amount <= 0:
        raise GameError("Сумма должна быть положительной.")
    await claim_operation(session, op_key, "company_deposit", user_id)
    await ledger.transfer(session, "company_deposit", amount, (user_id, "main"), (company_id, "main"),
                          ref_type="company", ref_id=company_id, actor_user_id=user_id)
    await audit(session, "company_deposit", actor_user_id=user_id, account_id=company_id, amount=amount)


async def pay(session: AsyncSession, user_id: int, company_id: int, to_user_id: int, amount: int,
              memo: str = "выплата", op_key: str | None = None) -> None:
    """Зарплата/выплата участнику — перевод существующих крон, не эмиссия."""
    await authz.require(session, user_id, company_id, Perm.WITHDRAW)
    if amount <= 0:
        raise GameError("Сумма должна быть положительной.")
    if await member(session, company_id, to_user_id) is None:
        raise GameError("Выплаты возможны только участникам компании.")
    await claim_operation(session, op_key, "company_pay", user_id)
    await ledger.transfer(session, "company_payout", amount, (company_id, "main"), (to_user_id, "main"),
                          ref_type="company", ref_id=company_id, actor_user_id=user_id, memo=memo[:200])
    await audit(session, "company_pay", actor_user_id=user_id, account_id=company_id, target_type="user",
                target_id=to_user_id, amount=amount, memo=memo[:200])


# --- Активы ------------------------------------------------------------------------------------------


async def transfer_resource(session: AsyncSession, user_id: int, src: int, dst: int, location: str, resource: str,
                            qty: int, op_key: str | None = None) -> None:
    """Передача ресурса между личным складом и складом компании в одной локации (без телепортации)."""
    await authz.require(session, user_id, src, Perm.EQUIPMENT if src != user_id else Perm.PRODUCE)
    await _check_link(session, user_id, src, dst)
    await claim_operation(session, op_key, "asset_transfer", user_id)
    await stock.take(session, src, location, resource, qty, "asset_transfer_out", actor=user_id)
    await stock.add(session, dst, location, resource, qty, "asset_transfer_in", actor=user_id)
    await audit(session, "asset_transfer", actor_user_id=user_id, account_id=src, target_type="account",
                target_id=dst, resource=resource, qty=qty, location=location)


async def transfer_item(session: AsyncSession, user_id: int, src: int, dst: int, item_id: int,
                        op_key: str | None = None) -> None:
    await authz.require(session, user_id, src, Perm.EQUIPMENT)
    await _check_link(session, user_id, src, dst)
    await claim_operation(session, op_key, "asset_transfer", user_id)
    it = await items.lock_owned(session, item_id, src)
    await items.transfer(session, it, dst, "asset_transfer", ref_type="account", ref_id=dst, actor=user_id)
    await audit(session, "asset_transfer", actor_user_id=user_id, account_id=src, target_type="item",
                target_id=item_id, to=dst)


async def _check_link(session: AsyncSession, user_id: int, src: int, dst: int) -> None:
    """Активы передаются только между лично игроком и компанией, где он состоит (не между чужими)."""
    if src == dst:
        raise GameError("Отправитель и получатель совпадают.")
    pair = {src, dst}
    if user_id not in pair:
        raise Forbidden("Передача возможна только между вами и вашей компанией.")
    other = (pair - {user_id}).pop()
    if await member(session, other, user_id) is None:
        raise Forbidden("Вы не состоите в этой компании.")


# --- Закрытие ----------------------------------------------------------------------------------------


async def close(session: AsyncSession, user_id: int, company_id: int, *, admin: bool = False) -> None:
    """Закрытие: только без открытых обязательств. Все активы и деньги переходят владельцу — ничто не исчезает."""
    comp = await _company(session, company_id, lock=True)
    if not admin and user_id != comp.owner_user_id:
        raise Forbidden("Закрыть компанию может только владелец.")
    if comp.status != "active":
        raise GameError("Компания уже закрыта.")
    open_orders = await session.scalar(select(func.count()).select_from(MarketOrder).where(
        MarketOrder.owner_id == company_id, MarketOrder.status == "open"))
    open_contracts = await session.scalar(select(func.count()).select_from(Contract).where(
        (Contract.customer_id == company_id) | (Contract.executor_id == company_id),
        Contract.status.in_(("open", "accepted", "in_progress", "disputed"))))
    running = await session.scalar(select(func.count()).select_from(Job).where(
        Job.owner_id == company_id, Job.status == "running"))
    trips = await session.scalar(select(func.count()).select_from(Shipment).where(
        Shipment.carrier_id == company_id, Shipment.status.in_(("loading", "in_transit"))))
    if open_orders or open_contracts or running or trips:
        raise GameError("Сначала закройте заявки, контракты, производство и рейсы компании.")
    owner = comp.owner_user_id
    hold_bal = await session.scalar(select(Wallet.balance).where(Wallet.account_id == company_id, Wallet.kind == "hold"))
    if hold_bal:
        raise RuntimeError("company hold not empty without obligations")
    main_bal = await session.scalar(select(Wallet.balance).where(Wallet.account_id == company_id, Wallet.kind == "main"))
    if main_bal:
        await ledger.transfer(session, "company_close", main_bal, (company_id, "main"), (owner, "main"),
                              ref_type="company", ref_id=company_id, actor_user_id=user_id)
    for st in (await session.scalars(select(Stock).where(Stock.owner_id == company_id, Stock.free > 0))).all():
        q, loc, res = st.free, st.location_code, st.resource
        await stock.take(session, company_id, loc, res, q, "company_close", actor=user_id)
        await stock.add(session, owner, loc, res, q, "company_close", actor=user_id, check_capacity=False)
    for it in (await session.scalars(select(Item).where(Item.owner_id == company_id, Item.parent_id.is_(None),
                                                        Item.status != ITEM_DESTROYED).with_for_update())).all():
        await items.transfer(session, it, owner, "company_close", ref_type="company", ref_id=company_id, actor=user_id)
    comp.status = "closed"
    comp.closed_at = clock.now()
    for m, u in await members(session, company_id):
        if u.acting_account_id == company_id:
            u.acting_account_id = u.id
    await audit(session, "company_close", actor_user_id=user_id, account_id=company_id, target_type="company",
                target_id=company_id, admin=admin, money=main_bal)
