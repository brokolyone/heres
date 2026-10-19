"""Добыча, производство, техника."""

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select

from ironvein.domain.catalog import (
    BARE_HANDS_YIELD,
    ITEMS,
    KIND_MODULE,
    LOCATIONS,
    MODULE_SLOTS,
    RECIPES,
    REPAIR,
    item_name,
    resource_name,
)
from ironvein.domain.errors import GameError
from ironvein.domain.money import fmt_cr
from ironvein.handlers.base import ask, on_input, parse_int
from ironvein.handlers.ui import Do, Nav, acting, back, bar, btn, current_user, e, guarded, kb, nonce, op_key, show, tx
from ironvein.models import ITEM_IDLE, Deposit, Item, Job
from ironvein.services import clock, companies, cosmetics, items, market, production, transport
from ironvein.services.world import regen_deposit

router = Router(name="production")

FACILITY_RU = {None: "Ручная работа", "workshop": "Мастерская", "smelter": "Плавильня", "refinery": "НПЗ"}
FAC_CODE = {"hand": None, "workshop": "workshop", "smelter": "smelter", "refinery": "refinery"}
SCENE_BY_FAC = {None: "workshop", "workshop": "workshop", "smelter": "smelter", "refinery": "refinery"}


def eta_text(dt) -> str:
    left = int((dt - clock.now()).total_seconds())
    if left <= 0:
        return "завершается"
    h, rem = divmod(left, 3600)
    m = rem // 60
    return f"{h} ч {m} мин" if h else f"{max(1, m)} мин"


def loc_buttons(screen: str):
    return [btn(loc.name, Nav(s=screen, a=code)) for code, loc in LOCATIONS.items()]


# --- Добыча ------------------------------------------------------------------------------------------


@router.message(Command("mine"))
async def cmd_mine(message: Message):
    await show(message, "<b>Добыча</b>\nВыберите локацию.", kb(loc_buttons("mine_loc"), back()), scene="mine_ore")


@router.callback_query(Nav.filter(F.s == "mine"))
async def cb_mine(cq: CallbackQuery):
    await show(cq, "<b>Добыча</b>\nВыберите локацию.", kb(loc_buttons("mine_loc"), back()), scene="mine_ore")
    await cq.answer()


@router.callback_query(Nav.filter(F.s == "mine_loc"))
async def cb_mine_loc(cq: CallbackQuery, callback_data: Nav):
    loc = callback_data.a
    if loc not in LOCATIONS:
        return await cq.answer("Устаревшая кнопка.", show_alert=True)
    async with tx() as s:
        deps = (await s.scalars(select(Deposit).where(Deposit.location_code == loc).order_by(Deposit.id)
                                .with_for_update())).all()
        for d in deps:
            await regen_deposit(s, d)
        lines = [f"<b>{LOCATIONS[loc].name}</b> · месторождения"]
        rows = []
        for d in deps:
            lines.append(f"▸ {e(d.name)} — {resource_name(d.resource)}\n  {bar(d.stock, d.max_stock)} "
                         f"{d.stock}/{d.max_stock}, +{d.regen_per_hour}/ч")
            rows.append([btn(d.name, Nav(s="mine_dep", a=str(d.id)))])
        if not deps:
            lines.append("Здесь нечего добывать: это торговый узел.")
    await show(cq, "\n".join(lines), kb(*rows, back("mine")))
    await cq.answer()


@router.callback_query(Nav.filter(F.s == "mine_dep"))
async def cb_mine_dep(cq: CallbackQuery, callback_data: Nav):
    async with tx() as s:
        user = await current_user(s, cq.from_user)
        acc, label = await acting(s, user)
        dep = await s.get(Deposit, int(callback_data.a))
        if dep is None:
            return await cq.answer("Устаревшая кнопка.", show_alert=True)
        tools = (await s.scalars(select(Item).where(
            Item.owner_id == acc, Item.location_code == dep.location_code, Item.status == ITEM_IDLE,
            Item.def_code.in_([c for c, d in ITEMS.items() if dep.resource in d.mine])).order_by(Item.id))).all()
    k = nonce()
    rows = [[btn(f"Голыми руками (+{BARE_HANDS_YIELD[dep.resource]})", Do(a="mine", x=dep.id, k=k))]]
    for t in tools[:6]:
        d = ITEMS[t.def_code]
        out = d.mine[dep.resource]
        if d.mine_fuel:
            for n in (1, 3, 6):
                rows.append([btn(f"{d.name} #{t.id}: ×{n} (+{out * n}, {d.mine_fuel * n} диз.)"[:40],
                                 Do(a="mine", x=dep.id, y=t.id, z=str(n), k=k))])
        else:
            rows.append([btn(f"{d.name} #{t.id} (+{out}) · {t.durability}/{t.max_durability}",
                             Do(a="mine", x=dep.id, y=t.id, k=k))])
    text = (f"<b>{e(dep.name)}</b> · {resource_name(dep.resource)}\nДействуете: {label}\n"
            f"Запас: {dep.stock}/{dep.max_stock}\n"
            "Ручная смена — 10 минут, одна на игрока. Механизированная добыча жрёт дизель со склада в этой локации.")
    await show(cq, text, kb(*rows, back("mine_loc", arg=dep.location_code)), scene=f"mine_{dep.resource}")
    await cq.answer()


@router.callback_query(Do.filter(F.a == "mine"))
async def do_mine(cq: CallbackQuery, callback_data: Do):
    async def run():
        async with tx() as s:
            user = await current_user(s, cq.from_user)
            acc, _ = await acting(s, user)
            job = await production.start_mining(s, user.id, acc, callback_data.x, callback_data.y or None,
                                                runs=int(callback_data.z or 1),
                                                op_key=op_key(cq.from_user.id, callback_data.k))
            dep = await s.get(Deposit, job.deposit_id)
            tool = await s.get(Item, job.equipment_id) if job.equipment_id else None
        res = dep.resource
        scene = {"drill": "drill", "oil_rig": "pump"}.get(tool.def_code if tool else "", f"mine_{res}")
        text = (f"<b>Смена началась</b> · {e(dep.name)}\n"
                f"Добыча: {resource_name(res)} ×{job.outputs[res]}\n"
                f"{'Инструмент: ' + e(items.title(tool)) if tool else 'Голыми руками'}\n"
                f"{'Сожжено дизеля: ' + str(job.inputs.get('diesel')) if job.inputs.get('diesel') else ''}\n"
                f"Готово через: {eta_text(job.finishes_at)}. Сообщу, когда добыча ляжет на склад.")
        await show(cq, text, kb([btn("Задания", Nav(s="production"))], back("mine_dep", arg=str(dep.id))), scene=scene)
    await guarded(cq, run)


# --- Производство ------------------------------------------------------------------------------------


async def jobs_screen(s, acc: int, label: str):
    jobs = (await s.scalars(select(Job).where(Job.owner_id == acc, Job.status == "running")
                            .order_by(Job.finishes_at))).all()
    lines = [f"<b>Производство</b> · {label}"]
    rows = []
    k = nonce()
    for j in jobs:
        lines.append(f"▸ #{j.id} {e(production.describe_job(j))} · {LOCATIONS[j.location_code].name} · "
                     f"осталось {eta_text(j.finishes_at)}")
        rows.append([btn(f"Отменить #{j.id}", Do(a="jcancel", x=j.id, k=k))])
    if not jobs:
        lines.append("Активных заданий нет.")
    lines.append("\nОтмена возвращает сырьё, но не топливо и не износ.")
    return "\n".join(lines), kb([btn("Новое задание", Nav(s="prod_loc"))], *rows, back())


@router.message(Command("production"))
async def cmd_production(message: Message):
    async with tx() as s:
        user = await current_user(s, message.from_user)
        text, markup = await jobs_screen(s, *(await acting(s, user)))
    await show(message, text, markup, scene="smelter")


@router.callback_query(Nav.filter(F.s == "production"))
async def cb_production(cq: CallbackQuery):
    async with tx() as s:
        user = await current_user(s, cq.from_user)
        text, markup = await jobs_screen(s, *(await acting(s, user)))
    await show(cq, text, markup, scene="smelter")
    await cq.answer()


@router.callback_query(Do.filter(F.a == "jcancel"))
async def do_jcancel(cq: CallbackQuery, callback_data: Do):
    async def run():
        async with tx() as s:
            user = await current_user(s, cq.from_user)
            await production.cancel_job(s, user.id, callback_data.x, op_key=op_key(cq.from_user.id, callback_data.k))
            text, markup = await jobs_screen(s, *(await acting(s, user)))
        await show(cq, "Задание отменено.\n\n" + text, markup, scene="smelter")
    await guarded(cq, run)


@router.callback_query(Nav.filter(F.s == "prod_loc"))
async def cb_prod_loc(cq: CallbackQuery):
    await show(cq, "<b>Новое задание</b>\nГде работаем? Сырьё и установка должны быть в этой локации.",
               kb(loc_buttons("prod_cat"), back("production")))
    await cq.answer()


@router.callback_query(Nav.filter(F.s == "prod_cat"))
async def cb_prod_cat(cq: CallbackQuery, callback_data: Nav):
    loc = callback_data.a
    rows = [[btn(name, Nav(s="prod_list", a=f"{loc}:{code}"))] for code, name in
            (("hand", "Ручная работа"), ("workshop", "Мастерская"), ("smelter", "Плавильня"), ("refinery", "НПЗ"))]
    await show(cq, f"<b>{LOCATIONS[loc].name}</b>\nВыберите установку.", kb(*rows, back("prod_loc")))
    await cq.answer()


def recipe_line(code: str) -> str:
    r = RECIPES[code]
    ins = ", ".join(f"{resource_name(k)} {v}" for k, v in r.inputs.items())
    if r.item_inputs:
        ins += (", " if ins else "") + "модули: шасси, двигатель, бак, кузов"
    outs = item_name(r.output_item) if r.output_item else ", ".join(f"{resource_name(k)} {v}" for k, v in r.outputs.items())
    return f"{ins} → {outs} · {r.minutes} мин"


@router.callback_query(Nav.filter(F.s == "prod_list"))
async def cb_prod_list(cq: CallbackQuery, callback_data: Nav):
    loc, fac = callback_data.a.split(":")
    facility = FAC_CODE.get(fac)
    recs = [r for r in RECIPES.values() if r.facility == facility]
    lines = [f"<b>{FACILITY_RU[facility]}</b> · {LOCATIONS[loc].name}"]
    rows = []
    for r in recs:
        lines.append(f"▸ {r.name}: {recipe_line(r.code)}")
        rows.append([btn(r.name, Nav(s="prod_rec", a=f"{loc}:{r.code}"))])
    await show(cq, "\n".join(lines), kb(*rows, back("prod_cat", arg=loc)))
    await cq.answer()


@router.callback_query(Nav.filter(F.s == "prod_rec"))
async def cb_prod_rec(cq: CallbackQuery, callback_data: Nav):
    loc, code = callback_data.a.split(":")
    r = RECIPES.get(code)
    if r is None:
        return await cq.answer("Устаревшая кнопка.", show_alert=True)
    k = nonce()
    lines = [f"<b>{r.name}</b> · {LOCATIONS[loc].name}", recipe_line(code)]
    if r.facility:
        lines.append(f"Нужна установка: {FACILITY_RU[r.facility]}, износ {r.wear} за запуск.")
    else:
        lines.append("Ручная работа: занимает ваши руки (одна смена одновременно).")
    if r.item_inputs:
        async with tx() as s:
            user = await current_user(s, cq.from_user)
            acc, _ = await acting(s, user)
            mods = await idle_modules(s, acc, loc)
        chosen = pick_modules(mods)
        lines.append("Модули к сборке: " + (", ".join(f"{MODULE_SLOTS[sl]}: {e(items.title(m))}"
                                                      for sl, m in sorted(chosen.items())) or "нет"))
        rows = [[btn("Собрать грузовик", Do(a="craft", x=1, z=f"{loc}:{code}", k=k))]]
    else:
        runs = [n for n in (1, 2, 5, 10) if n <= r.max_runs]
        rows = [[btn(f"×{n}", Do(a="craft", x=n, z=f"{loc}:{code}", k=k)) for n in runs]]
    scene = "assembly" if r.output_item == "truck" else SCENE_BY_FAC[r.facility]
    await show(cq, "\n".join(lines), kb(*rows, back("prod_list", arg=f"{loc}:{_fac_key(r.facility)}")), scene=scene)
    await cq.answer()


def pick_modules(mods) -> dict:
    """Первый свободный модуль каждого слота (по ID)."""
    chosen = {}
    for m in mods:
        chosen.setdefault(ITEMS[m.def_code].stats["slot"], m)
    return chosen


async def idle_modules(s, acc: int, loc: str):
    return (await s.scalars(select(Item).where(
        Item.owner_id == acc, Item.location_code == loc, Item.status == ITEM_IDLE,
        Item.def_code.in_([c for c, d in ITEMS.items() if d.kind == KIND_MODULE])).order_by(Item.id))).all()


def _fac_key(f):
    return "hand" if f is None else f


@router.callback_query(Do.filter(F.a == "craft"))
async def do_craft(cq: CallbackQuery, callback_data: Do):
    loc, code = callback_data.z.split(":")
    async def run():
        async with tx() as s:
            user = await current_user(s, cq.from_user)
            acc, _ = await acting(s, user)
            module_ids = None
            if code in RECIPES and RECIPES[code].item_inputs:
                module_ids = [m.id for m in pick_modules(await idle_modules(s, acc, loc)).values()]
            job = await production.start_craft(s, user.id, acc, code, loc, runs=callback_data.x,
                                               module_ids=module_ids, op_key=op_key(cq.from_user.id, callback_data.k))
        r = RECIPES[code]
        scene = "assembly" if r.output_item == "truck" else SCENE_BY_FAC[r.facility]
        text = (f"<b>Задание #{job.id} запущено</b>\n{e(production.describe_job(job))}\n"
                f"Списано: {', '.join(f'{resource_name(k)} {v}' for k, v in job.inputs.items()) or '—'}\n"
                f"Готово через: {eta_text(job.finishes_at)}.")
        await show(cq, text, kb([btn("Задания", Nav(s="production"))], back("prod_rec", arg=f"{loc}:{code}")),
                   scene=scene)
    await guarded(cq, run)


# --- Техника -----------------------------------------------------------------------------------------


async def equipment_screen(s, acc: int, label: str):
    its = (await s.scalars(select(Item).where(Item.owner_id == acc, Item.parent_id.is_(None),
                                              Item.status != "destroyed").order_by(Item.def_code, Item.id))).all()
    lines = [f"<b>Техника и предметы</b> · {label}"]
    rows = []
    for it in its[:30]:
        where = LOCATIONS[it.location_code].name if it.location_code else "при себе"
        dur = f" {it.durability}/{it.max_durability}" if it.max_durability else ""
        lines.append(f"▸ {e(items.title(it))}{dur} · {where} · {items.STATUS_RU[it.status]}")
        rows.append(btn(items.title(it)[:28], Nav(s="item", a=str(it.id))))
    if not its:
        lines.append("Пусто.")
    grid = [rows[i:i + 2] for i in range(0, len(rows), 2)]
    return "\n".join(lines), kb(*grid, back())


@router.message(Command("equipment"))
async def cmd_equipment(message: Message):
    async with tx() as s:
        user = await current_user(s, message.from_user)
        text, markup = await equipment_screen(s, *(await acting(s, user)))
    await show(message, text, markup)


@router.callback_query(Nav.filter(F.s == "equipment"))
async def cb_equipment(cq: CallbackQuery):
    async with tx() as s:
        user = await current_user(s, cq.from_user)
        text, markup = await equipment_screen(s, *(await acting(s, user)))
    await show(cq, text, markup)
    await cq.answer()


async def item_card(s, user, item_id: int):
    acc, label = await acting(s, user)
    it = await s.get(Item, item_id)
    if it is None or it.owner_id != acc:
        raise GameError("Предмет не найден у текущего владельца.")
    d = ITEMS[it.def_code]
    where = LOCATIONS[it.location_code].name if it.location_code else "при себе"
    lines = [f"<b>{e(items.title(it))}</b>", e(d.description) if d.description else "",
             f"Где: {where} · {items.STATUS_RU[it.status]}"]
    if it.max_durability:
        lines.append(f"Прочность: {bar(it.durability, it.max_durability)} {it.durability}/{it.max_durability}")
    if it.serial_no and d.kind == "premium":
        lines.append(f"Серийный номер: №{it.serial_no:03d}")
    k = nonce()
    rows = []
    if it.def_code == "truck":
        st = await transport.vehicle_stats(s, it.id)
        mods = await transport.modules_of(s, it.id)
        lines.append(f"Скорость {st.speed_kmh} км/ч · груз {st.payload} · расход {st.fuel_per_100km}/100 км · "
                     f"бак {st.tank} · запас хода {st.range_km} км")
        lines.append("Модули: " + ", ".join(ITEMS[m.def_code].name for m in mods))
        paint = await cosmetics.current_paint(s, it.id)
        if paint:
            lines.append("Окраска: «Чёрная латунь»")
            rows.append([btn("Снять окраску", Do(a="unpaint", x=it.id, k=k))])
        else:
            pid = await s.scalar(select(Item.id).where(Item.owner_id == acc, Item.def_code == "paint_black_brass",
                                                       Item.status == ITEM_IDLE).limit(1))
            if pid:
                rows.append([btn("Окрасить «Чёрной латунью»", Do(a="paint", x=pid, y=it.id, k=k))])
    if it.status == ITEM_IDLE:
        rule = REPAIR.get(it.def_code)
        if rule and it.durability < it.max_durability:
            ins = ", ".join(f"{resource_name(r)} {q}" for r, q in rule.inputs.items())
            lines.append(f"Ремонт: {ins} за +{rule.restore}, {rule.minutes} мин"
                         f"{', нужна мастерская' if rule.needs_workshop else ''}.")
            rows.append([btn("Ремонт ×1", Do(a="repair", x=it.id, y=1, k=k)),
                         btn("Полный ремонт", Do(a="repair", x=it.id, y=99, k=k))])
        if d.tradable:
            rows.append([btn("Продать на рынке", Do(a="sellitem", x=it.id))])
        targets = []
        if acc == user.id:
            for c, _ in await companies.memberships(s, user.id):
                targets.append((c.id, f"→ «{c.name}»"))
        else:
            targets.append((user.id, "→ себе лично"))
        for tid, t in targets[:3]:
            rows.append([btn(f"Передать {t}"[:40], Do(a="giveitem", x=it.id, y=tid, k=k))])
    return "\n".join(x for x in lines if x), kb(*rows, back("equipment"))


@router.callback_query(Nav.filter(F.s == "item"))
async def cb_item(cq: CallbackQuery, callback_data: Nav):
    async def run():
        async with tx() as s:
            user = await current_user(s, cq.from_user)
            text, markup = await item_card(s, user, int(callback_data.a))
        await show(cq, text, markup)
    await guarded(cq, run)


@router.callback_query(Do.filter(F.a == "repair"))
async def do_repair(cq: CallbackQuery, callback_data: Do):
    async def run():
        async with tx() as s:
            user = await current_user(s, cq.from_user)
            acc, _ = await acting(s, user)
            job = await production.start_repair(s, user.id, acc, callback_data.x, steps=callback_data.y,
                                                op_key=op_key(cq.from_user.id, callback_data.k))
        await show(cq, f"<b>Ремонт начат</b>\n{e(production.describe_job(job))}\n"
                       f"Списано: {', '.join(f'{resource_name(k)} {v}' for k, v in job.inputs.items())}\n"
                       f"Готово через: {eta_text(job.finishes_at)}.",
                   kb([btn("Задания", Nav(s="production"))], back("equipment")), scene="repair")
    await guarded(cq, run)


@router.callback_query(Do.filter(F.a.in_({"paint", "unpaint"})))
async def do_paint(cq: CallbackQuery, callback_data: Do):
    async def run():
        async with tx() as s:
            user = await current_user(s, cq.from_user)
            acc, _ = await acting(s, user)
            if callback_data.a == "paint":
                await cosmetics.apply_paint(s, user.id, acc, callback_data.x, callback_data.y)
                vid = callback_data.y
            else:
                await cosmetics.remove_paint(s, user.id, acc, callback_data.x)
                vid = callback_data.x
        scene = "truck_brass" if callback_data.a == "paint" else "truck"
        await show(cq, "Окраска нанесена: «Чёрная латунь». Характеристики не меняются."
                   if callback_data.a == "paint" else "Окраска снята и вернулась в инвентарь.",
                   kb([btn("К грузовику", Nav(s="item", a=str(vid)))], back("equipment")), scene=scene)
    await guarded(cq, run)


@router.callback_query(Do.filter(F.a == "giveitem"))
async def do_giveitem(cq: CallbackQuery, callback_data: Do):
    async def run():
        async with tx() as s:
            user = await current_user(s, cq.from_user)
            acc, _ = await acting(s, user)
            await companies.transfer_item(s, user.id, acc, callback_data.y, callback_data.x,
                                          op_key=op_key(cq.from_user.id, callback_data.k))
            text, markup = await equipment_screen(s, acc, "")
        await show(cq, "Предмет передан.\n\n" + text, markup)
    await guarded(cq, run)


@router.callback_query(Do.filter(F.a == "sellitem"))
async def do_sellitem(cq: CallbackQuery, callback_data: Do, state: FSMContext):
    await ask(cq, state, "item_price", "Цена продажи в кронах (₭)? Комиссия 2% уничтожается.", item_id=callback_data.x)


@on_input("item_price")
async def in_item_price(message: Message, text: str, data: dict):
    price = parse_int(text)
    async with tx() as s:
        user = await current_user(s, message.from_user)
        acc, _ = await acting(s, user)
        o = await market.place_ask_item(s, user.id, acc, data["item_id"], price,
                                        op_key=op_key(message.from_user.id, f"m{message.message_id}"))
    await show(message, f"<b>Выставлено на рынок</b>\nЗаявка #{o.id}: {e(item_name(o.item_def))} за {fmt_cr(price)}.",
               kb([btn("Мои заявки", Nav(s="my_orders"))], back()), scene="market")
