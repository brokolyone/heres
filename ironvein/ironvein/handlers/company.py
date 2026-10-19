"""Компании: создание, контекст действий, касса, выплаты, состав и права, передача активов, закрытие."""

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select

from ironvein.config import get_settings
from ironvein.domain.catalog import LOCATIONS, resource_name
from ironvein.domain.errors import Forbidden, GameError
from ironvein.domain.money import fmt_cr
from ironvein.domain.permissions import PERM_RU, ROLE_RU, Perm
from ironvein.handlers import fmt
from ironvein.handlers.base import ask, on_input, parse_int
from ironvein.handlers.ui import (
    Do,
    Nav,
    acting,
    back,
    btn,
    current_user,
    e,
    guarded,
    kb,
    nonce,
    notify,
    num,
    op_key,
    parts,
    show,
    tx,
)
from ironvein.models import Company, Stock, User
from ironvein.repositories.wallets import balances
from ironvein.services import companies, users

router = Router(name="company")


async def company_root(s, user):
    acc, label = await acting(s, user)
    ms = await companies.memberships(s, user.id)
    invites = await companies.pending_invites(s, user.id)
    lines = [fmt.head("Компании и синдикаты", f"действуете: {label}")]
    rows = []
    for c, m in ms:
        b = await balances(s, c.id)
        mark = " · ◀ активна" if acc == c.id else ""
        lines.append(f"🏭 <b>«{e(c.name)}»</b> — {ROLE_RU[m.role]} · касса {fmt.cr(b.get('main', 0))}{mark}")
        rows.append([btn(f"🏭 «{c.name}»"[:40], Nav(s="comp", a=str(c.id)))])
    k = nonce()
    for inv, c in invites:
        lines.append(f"✉ Приглашение в «{e(c.name)}» ({ROLE_RU[inv.role]})")
        rows.append([btn(f"✔ Принять «{c.name}»"[:40], Do(a="inv", x=inv.id, y=1, k=k)),
                     btn("✕ Отклонить", Do(a="inv", x=inv.id, y=0, k=k))])
    if not ms:
        lines.append("Вы не состоите ни в одной компании.")
    lines.append("\n<i>Компания — отдельный владелец: своя касса, склады, техника, заявки и контракты. "
                 "Бонусов за факт существования нет.</i>")
    if acc != user.id:
        rows.append([btn("👤 Действовать лично", Do(a="act", x=user.id))])
    rows.append([btn(f"＋ Основать компанию · {fmt.cr(get_settings().company_fee)}", Do(a="comp_new"))])
    return "\n".join(lines), kb(*rows, back())


@router.message(Command("company"))
async def cmd_company(message: Message):
    async with tx() as s:
        text, markup = await company_root(s, await current_user(s, message.from_user))
    await show(message, text, markup, scene="company")


@router.callback_query(Nav.filter(F.s == "company"))
async def cb_company(cq: CallbackQuery):
    async with tx() as s:
        text, markup = await company_root(s, await current_user(s, cq.from_user))
    await show(cq, text, markup, scene="company")
    await cq.answer()


@router.callback_query(Do.filter(F.a == "comp_new"))
async def do_comp_new(cq: CallbackQuery, state: FSMContext):
    await ask(cq, state, "comp_name", f"Название компании? Регистрационный сбор {fmt_cr(get_settings().company_fee)} "
                                      "уничтожается. Компания не даёт бонусов — только общий счёт, склад и права.")


@on_input("comp_name")
async def in_comp_name(message: Message, text: str, data: dict):
    async with tx() as s:
        user = await current_user(s, message.from_user)
        c = await companies.create(s, user.id, text, op_key=op_key(message.from_user.id, f"m{message.message_id}"))
        user.acting_account_id = c.id
    await show(message, fmt.ok(f"Компания «{e(c.name)}» зарегистрирована") + "\nВы — владелец. Теперь вы действуете от её "
                        "имени; переключиться можно в разделе «Компания».",
               kb([btn("Открыть компанию", Nav(s="comp", a=str(c.id)))], back()), scene="company")


@router.callback_query(Do.filter(F.a == "inv"))
async def do_inv(cq: CallbackQuery, callback_data: Do):
    async def run():
        async with tx() as s:
            user = await current_user(s, cq.from_user)
            inv = await companies.answer_invite(s, user.id, callback_data.x, bool(callback_data.y))
            comp = await s.get(Company, inv.company_id)
        if callback_data.y:
            await show(cq, fmt.ok(f"Вы вступили в «{e(comp.name)}»"), kb([btn("Открыть", Nav(s="comp", a=str(comp.id)))], back()),
                       scene="company")
        else:
            await show(cq, "Приглашение отклонено.", kb(back("company")))
    await guarded(cq, run)


@router.callback_query(Do.filter(F.a == "act"))
async def do_act(cq: CallbackQuery, callback_data: Do):
    async def run():
        async with tx() as s:
            user = await current_user(s, cq.from_user)
            target = callback_data.x
            if target != user.id and await companies.member(s, target, user.id) is None:
                raise Forbidden("Вы не состоите в этой компании.")
            user.acting_account_id = target
            text, markup = await company_root(s, user)
        await show(cq, text, markup, scene="company")
    await guarded(cq, run)


async def comp_card(s, user, cid: int):
    comp = await s.get(Company, cid)
    me = await companies.member(s, cid, user.id)
    if comp is None or comp.status != "active" or me is None:
        raise GameError("Компания недоступна.")
    acc, _ = await acting(s, user)
    owner = await s.get(User, comp.owner_user_id)
    b = await balances(s, cid)
    mem = await companies.members(s, cid)
    stocks = (await s.scalars(select(Stock).where(Stock.owner_id == cid, Stock.free + Stock.held > 0)
                              .order_by(Stock.location_code, Stock.resource))).all()
    lines = [fmt.head(f"«{comp.name}»", f"ID {cid} · основана {comp.created_at:%d.%m.%Y}"),
             fmt.kv("Владелец", e(owner.display_name)) + " · " + fmt.kv("ваша роль", ROLE_RU[me.role]),
             fmt.kv("Касса", fmt.cr(b.get("main", 0))) + " · резерв " + fmt.cr(b.get("hold", 0)),
             fmt.kv("Состав", len(mem))]
    if stocks:
        lines.append(fmt.section("Склады"))
        lines.append(fmt.table([(LOCATIONS[st.location_code].name, resource_name(st.resource), st.free) for st in stocks[:10]],
                               "llr"))
    lines.append("\n" + ("◀ Вы действуете от имени компании." if acc == cid else
                         "Сейчас вы действуете лично. Переключитесь, чтобы добывать и торговать для компании."))
    perms = Perm(me.permissions)
    rows = []
    if acc != cid:
        rows.append([btn("◀ Действовать от имени компании", Do(a="act", x=cid))])
    else:
        rows.append([btn("👤 Действовать лично", Do(a="act", x=user.id))])
    rows.append([btn("💰 Пополнить кассу", Do(a="cdep", x=cid)), btn("📦 Передать ресурс", Nav(s="cxfer", a=str(cid)))])
    extra = []
    if perms & Perm.WITHDRAW:
        extra.append(btn("💸 Выплата", Nav(s="cpay", a=str(cid))))
    if perms & Perm.INVITE:
        extra.append(btn("✉ Пригласить", Do(a="cinv", x=cid)))
    if extra:
        rows.append(extra)
    rows.append([btn("👥 Состав и права", Nav(s="cmembers", a=str(cid)))])
    if user.id == comp.owner_user_id:
        rows.append([btn("Закрыть компанию", Do(a="cclose", x=cid))])
    else:
        rows.append([btn("Выйти из компании", Do(a="cleave", x=cid, k=nonce()))])
    return "\n".join(lines), kb(*rows, back("company"))


@router.callback_query(Nav.filter(F.s == "comp"))
async def cb_comp(cq: CallbackQuery, callback_data: Nav):
    async def run():
        async with tx() as s:
            text, markup = await comp_card(s, await current_user(s, cq.from_user), num(callback_data.a))
        await show(cq, text, markup)
    await guarded(cq, run)


@router.callback_query(Do.filter(F.a == "cdep"))
async def do_cdep(cq: CallbackQuery, callback_data: Do, state: FSMContext):
    await ask(cq, state, "cdep_amount", "Сколько крон перевести из личной кассы в кассу компании?", cid=callback_data.x)


@on_input("cdep_amount")
async def in_cdep(message: Message, text: str, data: dict):
    amount = parse_int(text)
    async with tx() as s:
        user = await current_user(s, message.from_user)
        await companies.deposit(s, user.id, data["cid"], amount, op_key=op_key(message.from_user.id, f"m{message.message_id}"))
    await show(message, fmt.ok(f"Касса пополнена на {fmt_cr(amount)}"),
               kb([btn("К компании", Nav(s="comp", a=str(data["cid"])))]), scene="company")


@router.callback_query(Nav.filter(F.s == "cpay"))
async def cb_cpay(cq: CallbackQuery, callback_data: Nav):
    cid = num(callback_data.a)
    async with tx() as s:
        mem = await companies.members(s, cid)
    rows = [[btn(f"{u.display_name} ({ROLE_RU[m.role]})"[:40], Do(a="cpay_to", x=cid, y=u.id))] for m, u in mem]
    await show(cq, fmt.head("Выплата", "перевод существующих крон из кассы") + "\nКому?",
               kb(*rows, back("comp", arg=str(cid))))
    await cq.answer()


@router.callback_query(Do.filter(F.a == "cpay_to"))
async def do_cpay_to(cq: CallbackQuery, callback_data: Do, state: FSMContext):
    await ask(cq, state, "cpay_amount", "Сумма выплаты?", cid=callback_data.x, to=callback_data.y)


@on_input("cpay_amount")
async def in_cpay(message: Message, text: str, data: dict):
    amount = parse_int(text)
    async with tx() as s:
        user = await current_user(s, message.from_user)
        await companies.pay(s, user.id, data["cid"], data["to"], amount,
                            op_key=op_key(message.from_user.id, f"m{message.message_id}"))
        to = await s.get(User, data["to"])
    await show(message, fmt.ok(f"Выплачено {fmt_cr(amount)}") + f": {e(to.display_name)}",
               kb([btn("К компании", Nav(s="comp", a=str(data["cid"])))]), scene="company")
    if to.tg_id != message.from_user.id:
        await notify(message.bot, to.tg_id, f"Вам выплата от компании: {fmt_cr(amount)}.")


@router.callback_query(Do.filter(F.a == "cinv"))
async def do_cinv(cq: CallbackQuery, callback_data: Do, state: FSMContext):
    await ask(cq, state, "cinv_user", "Кого пригласить? @username или игровой ID.", cid=callback_data.x)


@on_input("cinv_user")
async def in_cinv(message: Message, text: str, data: dict):
    async with tx() as s:
        user = await current_user(s, message.from_user)
        target = await users.find_user(s, text)
        if target is None:
            raise GameError("Игрок не найден (он должен хотя бы раз нажать /start).")
        await companies.invite(s, user.id, data["cid"], target.id)
        comp = await s.get(Company, data["cid"])
    await show(message, fmt.ok("Приглашение отправлено") + f": {e(target.display_name)}",
               kb([btn("К компании", Nav(s="comp", a=str(data["cid"])))]), scene="company")
    try:
        await message.bot.send_message(target.tg_id, f"Вас приглашают в компанию «{e(comp.name)}». Откройте /company.",
                                       parse_mode="HTML")
    except Exception:
        pass


@router.callback_query(Nav.filter(F.s == "cmembers"))
async def cb_cmembers(cq: CallbackQuery, callback_data: Nav):
    cid = num(callback_data.a)
    async with tx() as s:
        mem = await companies.members(s, cid)
    lines = [fmt.head("Состав и права")]
    rows = []
    for m, u in mem:
        names = ", ".join(PERM_RU[p] for p in Perm if Perm(m.permissions) & p)
        lines.append(f"👤 <b>{e(u.display_name)}</b> — {ROLE_RU[m.role]}\n    <i>{names or 'без прав'}</i>")
        if m.role != "owner":
            rows.append([btn(f"{u.display_name}"[:30], Nav(s="cmember", a=f"{cid}:{u.id}"))])
    await show(cq, "\n".join(lines), kb(*rows, back("comp", arg=str(cid))))
    await cq.answer()


@router.callback_query(Nav.filter(F.s == "cmember"))
async def cb_cmember(cq: CallbackQuery, callback_data: Nav):
    cid, uid = (num(v) for v in parts(callback_data.a, 2))
    async with tx() as s:
        m = await companies.member(s, cid, uid)
        u = await s.get(User, uid)
    if m is None:
        return await cq.answer("Участник уже не в компании.", show_alert=True)
    k = nonce()
    rows = [[btn(("✓ " if Perm(m.permissions) & p else "· ") + PERM_RU[p], Do(a="cperm", x=cid, y=uid, z=str(int(p)), k=k))]
            for p in Perm]
    rows.append([btn("Сделать управляющим", Do(a="crole", x=cid, y=uid, z="manager", k=k)),
                 btn("Сделать сотрудником", Do(a="crole", x=cid, y=uid, z="employee", k=k))])
    rows.append([btn("Передать владение", Do(a="cowner", x=cid, y=uid, k=k)), btn("Исключить", Do(a="ckick", x=cid, y=uid, k=k))])
    await show(cq, fmt.head(u.display_name, ROLE_RU[m.role]) + "\nНажмите право, чтобы включить или выключить.",
               kb(*rows, back("cmembers", arg=str(cid))))
    await cq.answer()


@router.callback_query(Do.filter(F.a.in_({"cperm", "crole", "cowner", "ckick"})))
async def do_cmember_action(cq: CallbackQuery, callback_data: Do):
    cid, uid = callback_data.x, callback_data.y

    async def run():
        async with tx() as s:
            user = await current_user(s, cq.from_user)
            if callback_data.a == "cperm":
                await companies.toggle_permission(s, user.id, cid, uid, Perm(num(callback_data.z)))
            elif callback_data.a == "crole":
                await companies.set_role(s, user.id, cid, uid, callback_data.z)
            elif callback_data.a == "cowner":
                await companies.transfer_ownership(s, user.id, cid, uid)
            else:
                await companies.remove_member(s, user.id, cid, uid)
        if callback_data.a in ("cperm", "crole"):
            await cb_cmember(cq, Nav(s="cmember", a=f"{cid}:{uid}"))
        else:
            await show(cq, "Готово.", kb([btn("К компании", Nav(s="comp", a=str(cid)))], back("company")), scene="company")
    await guarded(cq, run)


@router.callback_query(Do.filter(F.a == "cleave"))
async def do_cleave(cq: CallbackQuery, callback_data: Do):
    async def run():
        async with tx() as s:
            user = await current_user(s, cq.from_user)
            await companies.remove_member(s, user.id, callback_data.x, user.id)
        await show(cq, "Вы вышли из компании. Её активы остаются у компании.", kb(back("company")))
    await guarded(cq, run)


@router.callback_query(Do.filter(F.a == "cclose"))
async def do_cclose(cq: CallbackQuery, callback_data: Do):
    k = nonce()
    await show(cq, fmt.head("Закрыть компанию?") + "\nНужно закрыть все заявки, контракты, производство и рейсы. "
                   "Деньги, склады и предметы перейдут владельцу.",
               kb([btn("Да, закрыть", Do(a="cclose_go", x=callback_data.x, k=k))], back("comp", arg=str(callback_data.x))))
    await cq.answer()


@router.callback_query(Do.filter(F.a == "cclose_go"))
async def do_cclose_go(cq: CallbackQuery, callback_data: Do):
    async def run():
        async with tx() as s:
            user = await current_user(s, cq.from_user)
            await companies.close(s, user.id, callback_data.x)
        await show(cq, fmt.ok("Компания закрыта") + " — все активы переданы владельцу.", kb(back("company")), scene="company")
    await guarded(cq, run)


# --- Передача ресурсов между личным складом и компанией ---------------------------------------------


@router.callback_query(Nav.filter(F.s == "cxfer"))
async def cb_cxfer(cq: CallbackQuery, callback_data: Nav):
    cid = num(callback_data.a)
    async with tx() as s:
        user = await current_user(s, cq.from_user)
        acc, _ = await acting(s, user)
        src = cid if acc == cid else user.id
        dst = user.id if src == cid else cid
        stocks = (await s.scalars(select(Stock).where(Stock.owner_id == src, Stock.free > 0)
                                  .order_by(Stock.location_code, Stock.resource))).all()
    direction = "из компании себе" if src == cid else "из личного склада в компанию"
    rows = [[btn(f"{resource_name(st.resource)} {st.free} · {LOCATIONS[st.location_code].name}"[:40],
                 Do(a="cxfer_q", x=src, y=dst, z=f"{st.location_code}:{st.resource}"))] for st in stocks[:12]]
    await show(cq, fmt.head("Передача ресурса", direction) + "\nТовар остаётся в той же локации.\n"
                   "Направление зависит от того, от чьего имени вы действуете.",
               kb(*rows, back("comp", arg=str(cid))))
    await cq.answer()


@router.callback_query(Do.filter(F.a == "cxfer_q"))
async def do_cxfer_q(cq: CallbackQuery, callback_data: Do, state: FSMContext):
    loc, res = parts(callback_data.z, 2)
    await ask(cq, state, "cxfer_amount", f"Сколько передать: {resource_name(res)}?", src=callback_data.x,
              dst=callback_data.y, loc=loc, res=res)


@on_input("cxfer_amount")
async def in_cxfer(message: Message, text: str, data: dict):
    q = parse_int(text, 1, 10**6)
    async with tx() as s:
        user = await current_user(s, message.from_user)
        await companies.transfer_resource(s, user.id, data["src"], data["dst"], data["loc"], data["res"], q,
                                          op_key=op_key(message.from_user.id, f"m{message.message_id}"))
    await show(message, fmt.ok(f"Передано: {resource_name(data['res'])} × {q}") + f" ({LOCATIONS[data['loc']].name})",
               kb(back("company")), scene="company")
