"""Администрирование: доступ по ADMIN_IDS, каждое действие пишется в audit_logs."""

from aiogram import Router
from aiogram.filters import Command, CommandObject, Filter
from aiogram.types import Message
from sqlalchemy import func, select

from ironvein.config import get_settings
from ironvein.domain.catalog import ITEMS, LOCATIONS, RESOURCES, resource_name
from ironvein.domain.errors import GameError
from ironvein.domain.money import fmt_cr
from ironvein.domain.permissions import ROLE_RU
from ironvein.handlers import fmt
from ironvein.handlers.ui import clip, e, guarded, tx
from ironvein.models import (
    Company,
    Contract,
    Job,
    LedgerEntry,
    LedgerTx,
    PremiumOrder,
    PremiumProduct,
    Shipment,
    User,
    Wallet,
)
from ironvein.repositories.wallets import balances
from ironvein.services import (
    companies,
    contracts,
    items,
    metrics,
    premium,
    stock,
    users,
)
from ironvein.services.common import audit

router = Router(name="admin")


class IsAdmin(Filter):
    async def __call__(self, message: Message) -> bool:
        return message.from_user is not None and message.from_user.id in get_settings().admin_ids


router.message.filter(IsAdmin())

HELP = """<b>Администрирование</b>
/admin — сводка экономики и инвариантов
/admin_user &lt;id|@user&gt; — игрок, балансы, последние проводки
/admin_ban &lt;id&gt; · /admin_unban &lt;id&gt;
/admin_orders — последние премиум-заказы
/admin_refund &lt;order_id&gt; &lt;причина&gt; — возврат Stars (через очередь)
/admin_unlock &lt;item_id&gt; &lt;заметка&gt; — снять блокировку предмета
/admin_resolve &lt;contract_id&gt; refund|resume &lt;заметка&gt;
/admin_product &lt;code&gt; on|off|limit N|price N
/admin_company_owner &lt;company_id&gt; &lt;user_id&gt;
/admin_active — активные производства, рейсы, контракты
/admin_grant &lt;user_id&gt; &lt;loc&gt; &lt;res&gt; &lt;qty&gt; — тестовая выдача (только не в production)"""


async def _admin_id(s, message: Message) -> int:
    u, _ = await users.get_or_register(s, message.from_user.id, message.from_user.full_name, message.from_user.username)
    return u.id


@router.message(Command("admin_help"))
async def admin_help(message: Message):
    await message.answer(HELP, parse_mode="HTML")


@router.message(Command("admin"))
async def admin_overview(message: Message):
    async with tx() as s:
        o = await metrics.economy_overview(s)
        await audit(s, "admin_view_overview", actor_user_id=await _admin_id(s, message))
    i = o["integrity"]
    c = o["concentration"]
    flow_ru = {"mine_output": "добыто", "craft_output": "произведено", "craft_input": "сырьё в производство",
               "fuel_mining": "дизель на добычу", "fuel_trip": "дизель на рейсы", "repair_input": "на ремонт"}
    ship_ru = {"loading": "погрузка", "in_transit": "в пути", "delivered": "доставлено", "cancelled": "отменено"}
    po_ru = {"created": "ожидают", "paid": "оплачены", "fulfilled": "выданы", "expired": "истекли",
             "refund_pending": "к возврату", "refunded": "возвращены"}

    def good(g):
        return resource_name(g) if g in RESOURCES else ITEMS[g].name if g in ITEMS else g

    bad = {k: v for k, v in i.items() if k not in ("ok", "emitted", "burned", "circulating") and v}
    lines = [
        fmt.head("Экономика", "последние 24 часа"),
        "Инварианты: " + ("<b>в порядке</b>" if i["ok"] else f"<b>НАРУШЕНЫ</b>: {e(str(bad))[:500]}"),
        fmt.kv("Эмиссия", fmt.cr(i["emitted"])) + " · " + fmt.kv("уничтожено", fmt.cr(i["burned"])) + " · "
        + fmt.kv("в обороте", fmt.cr(i["circulating"])),
        fmt.kv("Резервы", fmt.cr(o["reserves"])) + " · " + fmt.kv("комиссии рынка", fmt.cr(o["fees_period"])),
        "Деньги: " + ", ".join(f"{'игроки' if k == 'user' else 'компании'} {fmt.cr(int(v))}"
                               for k, v in o["money_by_kind"].items()),
        f"Концентрация: топ-5 <b>{c['top_share_pct']:.1f}%</b>, HHI {c['hhi']}, держателей {c['holders']}",
        fmt.section("Торговля"),
    ]
    lines += [f"▸ {good(g)} @ {LOCATIONS[loc].name if loc else 'без локации'}: {int(q)} ед., "
              f"VWAP {int(gross) // max(1, int(q))} ₭, сделок {n}" for g, loc, q, gross, n in o["trades"]] or ["сделок не было"]
    lines.append(fmt.section("Потоки"))
    lines += [f"▸ {flow_ru.get(r, r)}: {resource_name(res)} {abs(int(q))}" for r, res, q in o["flows"]] or ["нет"]
    lines.append(fmt.section("Месторождения"))
    lines.append(fmt.table([(n, f"{st}/{mx}") for n, _, st, mx in o["deposits"]], "lr"))
    lines.append(fmt.section("Процессы и логистика"))
    lines.append(fmt.kv("Задания в работе", o["jobs_running"]) + " · рейсы: "
                 + (", ".join(f"{ship_ru.get(k, k)} {v}" for k, v in o["shipments"].items()) or "нет"))
    lines += [f"▸ {LOCATIONS[a].name} → {LOCATIONS[b].name}: {n} рейсов, дизель {int(f or 0)}"
              for a, b, n, f in o["lanes"]]
    lines.append("Контракты: " + (", ".join(f"{contracts.STATUS_RU.get(k, k)} {v}" for k, v in o["contracts"].items())
                                  or "нет"))
    lines.append("Stars: " + (", ".join(f"{po_ru.get(st, st)} {n} ({int(sm)} ⭐)" for st, n, sm in o["stars"]) or "нет")
                 + f" · перепродаж премиума {o['premium_resales'][0]} на {fmt.cr(int(o['premium_resales'][1]))}")
    await message.answer(clip("\n".join(lines)), parse_mode="HTML")


@router.message(Command("admin_user"))
async def admin_user(message: Message, command: CommandObject):
    async with tx() as s:
        u = await users.find_user(s, command.args or "")
        if u is None:
            return await message.answer("Не найден.")
        b = await balances(s, u.id)
        wids = (await s.scalars(select(Wallet.id).where(Wallet.account_id == u.id))).all()
        rows = (await s.execute(select(LedgerTx.id, LedgerTx.kind, LedgerEntry.delta, LedgerTx.created_at)
                                .join(LedgerEntry, LedgerEntry.tx_id == LedgerTx.id)
                                .where(LedgerEntry.wallet_id.in_(wids)).order_by(LedgerTx.id.desc()).limit(15))).all()
        ms = await companies.memberships(s, u.id)
        await audit(s, "admin_view_user", actor_user_id=await _admin_id(s, message), target_type="user", target_id=u.id)
    lines = [fmt.head(u.display_name, f"id {u.id} · tg {u.tg_id} · @{e(u.username or '-')}"
                      + (" · ЗАБЛОКИРОВАН" if u.is_banned else "")),
             f"main {fmt_cr(b.get('main', 0))} · hold {fmt_cr(b.get('hold', 0))}",
             "Компании: " + (", ".join(f"{e(c.name)} ({ROLE_RU.get(m.role, m.role)})" for c, m in ms) or "нет"), fmt.section("Проводки")]
    lines += [f"<code>{dt:%d.%m %H:%M} tx{t} {k} {d:+}</code>" for t, k, d, dt in rows]
    await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(Command("admin_ban", "admin_unban"))
async def admin_ban(message: Message, command: CommandObject):
    ban = command.command == "admin_ban"

    async def run():
        async with tx() as s:
            u = await users.find_user(s, command.args or "")
            if u is None:
                raise GameError("Не найден.")
            u.is_banned = ban
            await audit(s, "admin_ban" if ban else "admin_unban", actor_user_id=await _admin_id(s, message),
                        target_type="user", target_id=u.id)
        await message.answer(f"{'Заблокирован' if ban else 'Разблокирован'}: {u.id}. Активы и обязательства сохранены; "
                             "рейсы доедут, контракты истекут по правилам.")
    await guarded(message, run)


@router.message(Command("admin_orders"))
async def admin_orders(message: Message):
    async with tx() as s:
        orders = (await s.scalars(select(PremiumOrder).order_by(PremiumOrder.id.desc()).limit(20))).all()
        await audit(s, "admin_view_orders", actor_user_id=await _admin_id(s, message))
    lines = ["<b>Премиум-заказы</b>"] + [
        f"{o.id} u{o.user_id} {o.product_code} {o.price_stars}⭐ {o.status} item={o.item_id} charge={e(o.telegram_charge_id or '-')}"
        for o in orders]
    await message.answer(clip("\n".join(lines)), parse_mode="HTML")


@router.message(Command("admin_refund"))
async def admin_refund(message: Message, command: CommandObject):
    async def run():
        parts = (command.args or "").split(maxsplit=1)
        if not parts or not parts[0].isdigit():
            raise GameError("/admin_refund <order_id> <причина>")
        async with tx() as s:
            await premium.request_refund(s, await _admin_id(s, message), int(parts[0]), parts[1] if len(parts) > 1 else "")
        await message.answer("Заказ поставлен в очередь возврата; фоновая задача вызовет refundStarPayment.")
    await guarded(message, run)


@router.message(Command("admin_unlock"))
async def admin_unlock(message: Message, command: CommandObject):
    async def run():
        parts = (command.args or "").split(maxsplit=1)
        if not parts or not parts[0].isdigit():
            raise GameError("/admin_unlock <item_id> <заметка>")
        async with tx() as s:
            await premium.admin_unlock(s, await _admin_id(s, message), int(parts[0]), parts[1] if len(parts) > 1 else "")
        await message.answer("Блокировка снята.")
    await guarded(message, run)


@router.message(Command("admin_resolve"))
async def admin_resolve(message: Message, command: CommandObject):
    async def run():
        parts = (command.args or "").split(maxsplit=2)
        if len(parts) < 2 or not parts[0].isdigit():
            raise GameError("/admin_resolve <contract_id> refund|resume <заметка>")
        async with tx() as s:
            c = await contracts.admin_resolve(s, await _admin_id(s, message), int(parts[0]), parts[1],
                                              parts[2] if len(parts) > 2 else "")
        await message.answer(f"Контракт #{c.id}: {contracts.STATUS_RU[c.status]}.")
    await guarded(message, run)


@router.message(Command("admin_product"))
async def admin_product(message: Message, command: CommandObject):
    async def run():
        parts = (command.args or "").split()
        if len(parts) < 2:
            raise GameError("/admin_product <code> on|off|limit N|price N")
        async with tx() as s:
            p = (await s.execute(select(PremiumProduct).where(PremiumProduct.code == parts[0]).with_for_update())).scalar_one_or_none()
            if p is None:
                raise GameError("Товар не найден.")
            op = parts[1]
            if op in ("on", "off"):
                p.active = op == "on"
            elif op == "limit" and len(parts) > 2:
                n = int(parts[2]) if parts[2].isdigit() else None
                if n is not None and n < p.issued + p.reserved:
                    raise GameError("Лимит не может быть меньше выпущенного и забронированного.")
                p.edition_limit = n
            elif op == "price" and len(parts) > 2 and parts[2].isdigit() and int(parts[2]) > 0:
                p.price_stars = int(parts[2])  # открытые счета сохраняют свою зафиксированную цену
            else:
                raise GameError("Неизвестная операция.")
            await audit(s, "admin_product", actor_user_id=await _admin_id(s, message), target_type="product", op=parts[1:],
                        code=p.code)
        await message.answer(f"{p.code}: active={p.active} limit={p.edition_limit} price={p.price_stars}")
    await guarded(message, run)


@router.message(Command("admin_company_owner"))
async def admin_company_owner(message: Message, command: CommandObject):
    async def run():
        parts = (command.args or "").split()
        if len(parts) != 2 or not all(p.isdigit() for p in parts):
            raise GameError("/admin_company_owner <company_id> <user_id>")
        async with tx() as s:
            await companies.transfer_ownership(s, await _admin_id(s, message), int(parts[0]), int(parts[1]), admin=True)
        await message.answer("Владелец компании изменён.")
    await guarded(message, run)


@router.message(Command("admin_active"))
async def admin_active(message: Message):
    async with tx() as s:
        jobs = (await s.scalars(select(Job).where(Job.status == "running").order_by(Job.finishes_at).limit(15))).all()
        ships = (await s.scalars(select(Shipment).where(Shipment.status.in_(("loading", "in_transit")))
                                 .order_by(Shipment.id).limit(15))).all()
        ctrs = (await s.scalars(select(Contract).where(Contract.status.in_(("open", "accepted", "in_progress", "disputed")))
                                .order_by(Contract.id).limit(15))).all()
        ncomp = await s.scalar(select(func.count()).select_from(Company).where(Company.status == "active"))
        nusers = await s.scalar(select(func.count()).select_from(User))
        await audit(s, "admin_view_active", actor_user_id=await _admin_id(s, message))
    lines = [f"Игроков {nusers}, компаний {ncomp}", "<b>Задания</b>"]
    lines += [f"#{j.id} {j.kind} acc{j.owner_id} до {j.finishes_at:%d.%m %H:%M}" for j in jobs]
    lines.append("<b>Рейсы</b>")
    lines += [f"#{x.id} {x.mode} {x.origin}->{x.dest} {x.status} eta {x.eta:%d.%m %H:%M}" if x.eta else
              f"#{x.id} {x.mode} {x.origin}->{x.dest} {x.status}" for x in ships]
    lines.append("<b>Контракты</b>")
    lines += [f"#{c.id} {c.kind} {c.status} {c.resource} {c.delivered_qty}/{c.qty}" for c in ctrs]
    await message.answer(clip("\n".join(lines)), parse_mode="HTML")


@router.message(Command("admin_grant"))
async def admin_grant(message: Message, command: CommandObject):
    async def run():
        if get_settings().is_production:
            raise GameError("Тестовые выдачи запрещены в production.")
        parts = (command.args or "").split()
        if len(parts) != 4 or parts[2] not in RESOURCES or parts[1] not in LOCATIONS or not parts[3].isdigit():
            raise GameError("/admin_grant <user_id> <loc> <res> <qty>")
        async with tx() as s:
            admin_id = await _admin_id(s, message)
            await stock.add(s, int(parts[0]), parts[1], parts[2], int(parts[3]), "admin_grant_test", actor=admin_id,
                            check_capacity=False)
            await audit(s, "admin_grant_test", actor_user_id=admin_id, target_type="account", target_id=int(parts[0]),
                        args=parts)
        await message.answer("Выдано (тестовая среда).")
    await guarded(message, run)


__all__ = ["router", "items"]
