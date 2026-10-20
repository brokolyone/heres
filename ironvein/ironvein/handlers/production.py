"""Добыча, производство, техника."""

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select

from ironvein.domain import quality
from ironvein.domain.catalog import (
    BARE_HANDS_YIELD,
    ITEMS,
    KIND_MODULE,
    LOCATIONS,
    MANUAL_SHIFT_MINUTES,
    MODULE_SLOTS,
    RECIPES,
    REPAIR,
    item_name,
    resource_name,
)
from ironvein.domain.errors import GameError, StaleButton
from ironvein.domain.vehicles import truck_stats
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
    num,
    op_key,
    parts,
    show,
    tx,
)
from ironvein.models import ITEM_IDLE, Deposit, Item, Job, Stock
from ironvein.services import companies, cosmetics, items, market, production, transport
from ironvein.services.world import effective_regen, players_multiplier, regen_deposit

router = Router(name="production")

FACILITY_RU = {None: "Ручная работа", "workshop": "Мастерская", "smelter": "Плавильня", "refinery": "НПЗ"}
FAC_CODE = {"hand": None, "workshop": "workshop", "smelter": "smelter", "refinery": "refinery"}
SCENE_BY_FAC = {None: "workshop", "workshop": "workshop", "smelter": "smelter", "refinery": "refinery"}
RES_ICON = {"ore": "◆", "coal": "●", "oil": "▼"}


def eta_text(dt) -> str:
    return fmt.left(dt)


def loc_buttons(screen: str):
    return [btn(loc.name, Nav(s=screen, a=code)) for code, loc in LOCATIONS.items()]


async def manual_busy(s, user_id: int) -> Job | None:
    return await s.scalar(select(Job).where(Job.actor_user_id == user_id, Job.manual.is_(True),
                                            Job.status == "running"))


async def free_stock(s, acc: int, loc: str) -> dict[str, int]:
    rows = (await s.execute(select(Stock.resource, Stock.free).where(Stock.owner_id == acc, Stock.location_code == loc))).all()
    return {r: q for r, q in rows}


# --- Добыча ------------------------------------------------------------------------------------------

MINE_TEXT = "\n".join([
    fmt.head("Добыча"),
    "▸ <b>Руками</b> — всегда доступно, медленно.",
    "▸ <b>Кирка / насос</b> — ручная смена 10 мин, одна на игрока.",
    "▸ <b>Буровая / качалка</b> — до 12 циклов, жрут дизель со склада на месте.",
    "Выберите локацию:",
])


@router.message(Command("mine"))
async def cmd_mine(message: Message):
    await show(message, MINE_TEXT, kb(loc_buttons("mine_loc"), back()), scene="mine_ore")


@router.callback_query(Nav.filter(F.s == "mine"))
async def cb_mine(cq: CallbackQuery):
    await show(cq, MINE_TEXT, kb(loc_buttons("mine_loc"), back()), scene="mine_ore")
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
        mult = await players_multiplier(s)
    lines = [fmt.head(LOCATIONS[loc].name)]
    rows = []
    for d in deps:
        lines.append(f"\n{RES_ICON.get(d.resource, '▸')} <b>{e(d.name)}</b> · {resource_name(d.resource)}")
        lines.append(f"<code>{fmt.gauge(d.stock, d.max_stock)}</code> {d.stock}/{d.max_stock} · "
                     f"+{round(effective_regen(d.regen_per_hour, mult))}/ч")
        rows.append([btn(f"{RES_ICON.get(d.resource, '')} {d.name}", Nav(s="mine_dep", a=str(d.id)))])
    if not deps:
        lines.append("\nЗдесь нечего добывать: это торговый узел. Добыча — в Ржавой Пади и Мазутном Яре.")
    scene = "mine_oil" if loc == "mazut" else "mine_ore"
    await show(cq, "\n".join(lines), kb(*rows, back("mine")), scene=f"{scene}@{loc}")
    await cq.answer()


@router.callback_query(Nav.filter(F.s == "mine_dep"))
async def cb_mine_dep(cq: CallbackQuery, callback_data: Nav):
    async with tx() as s:
        user = await current_user(s, cq.from_user)
        acc, label = await acting(s, user)
        dep = await s.get(Deposit, num(callback_data.a))
        if dep is None:
            return await cq.answer("Устаревшая кнопка.", show_alert=True)
        suited = [c for c, d in ITEMS.items() if dep.resource in d.mine]
        tools = (await s.scalars(select(Item).where(
            Item.owner_id == acc, Item.location_code == dep.location_code, Item.def_code.in_(suited))
            .order_by(Item.id))).all()
        busy = await manual_busy(s, user.id)
        diesel = (await free_stock(s, acc, dep.location_code)).get("diesel", 0)
    k = nonce()
    lines = [fmt.head(dep.name, f"{resource_name(dep.resource)} · {LOCATIONS[dep.location_code].name}"),
             f"<code>{fmt.gauge(dep.stock, dep.max_stock)}</code> {dep.stock}/{dep.max_stock}",
             fmt.kv("Действуете", label) + " · " + fmt.kv("дизель на месте", diesel)]
    if busy:
        lines.append(fmt.warn(f"Руки заняты: смена закончится через {fmt.left(busy.finishes_at)}."))
    rows = []
    if not busy:
        rows.append([btn(f"✋ Голыми руками · +{BARE_HANDS_YIELD[dep.resource]}", Do(a="mine", x=dep.id, k=k))])
    for t in tools[:6]:
        d = ITEMS[t.def_code]
        out = d.mine[dep.resource]
        state = f"{t.durability}/{t.max_durability}"
        if t.status != ITEM_IDLE:
            lines.append(f"▸ {e(items.title(t))} — {items.STATUS_RU[t.status]}")
            continue
        if d.mine_fuel:
            lines.append(f"▸ {e(items.title(t))} · прочность {state} · цикл {fmt.dur_game(d.mine_minutes)}: "
                         f"+{out}, дизель {d.mine_fuel}")
            rows.append([btn(f"×{n} → +{out * n}", Do(a="mine", x=dep.id, y=t.id, z=str(n), k=k)) for n in (1, 3, 6, 12)])
        else:
            lines.append(f"▸ {e(items.title(t))} · прочность {state} · смена: +{out}")
            if not busy:
                rows.append([btn(f"{d.name} #{t.id} · +{out}", Do(a="mine", x=dep.id, y=t.id, k=k))])
    if not tools:
        lines.append("<i>Своего инструмента здесь нет — можно работать руками.</i>")
    lines.append(f"<i>Ручная смена: {fmt.dur_game(MANUAL_SHIFT_MINUTES)}.</i>")
    await show(cq, "\n".join(lines), kb(*rows, back("mine_loc", arg=dep.location_code)),
               scene=f"mine_{dep.resource}@{dep.location_code}")
    await cq.answer()


@router.callback_query(Do.filter(F.a == "mine"))
async def do_mine(cq: CallbackQuery, callback_data: Do):
    async def run():
        async with tx() as s:
            user = await current_user(s, cq.from_user)
            acc, _ = await acting(s, user)
            job = await production.start_mining(s, user.id, acc, callback_data.x, callback_data.y or None,
                                                runs=num(callback_data.z or "1"),
                                                op_key=op_key(cq.from_user.id, callback_data.k))
            dep = await s.get(Deposit, job.deposit_id)
            tool = await s.get(Item, job.equipment_id) if job.equipment_id else None
        res = dep.resource
        scene = {"drill": "drill", "oil_rig": "pump"}.get(tool.def_code if tool else "", f"mine_{res}")
        lines = [fmt.ok("Смена началась"), f"{e(dep.name)} · {resource_name(res)} <b>+{job.outputs[res]}</b>",
                 fmt.kv("Чем", e(items.title(tool)) if tool else "голыми руками")]
        if job.inputs.get("diesel"):
            lines.append(fmt.kv("Сожжено дизеля", job.inputs["diesel"]))
        lines.append(fmt.kv("Готово через", fmt.left(job.finishes_at)))
        lines.append("<i>Сообщу, когда добыча ляжет на склад.</i>")
        await show(cq, "\n".join(lines), kb([btn("Задания", Nav(s="production"))],
                                            back("mine_dep", arg=str(dep.id))), scene=f"{scene}@{dep.location_code}")
    await guarded(cq, run)


# --- Производство ------------------------------------------------------------------------------------


async def jobs_screen(s, acc: int, label: str):
    jobs = (await s.scalars(select(Job).where(Job.owner_id == acc, Job.status == "running")
                            .order_by(Job.finishes_at))).all()
    lines = [fmt.head("Производство", label)]
    rows = []
    k = nonce()
    for j in jobs:
        lines.append(f"\n● <b>#{j.id}</b> {e(production.describe_job(j))}")
        lines.append(f"<code>{fmt.progress(j.started_at, j.finishes_at)}</code> {LOCATIONS[j.location_code].name} · "
                     f"осталось {fmt.left(j.finishes_at)}")
        rows.append([btn(f"✕ Отменить #{j.id}", Do(a="jcancel", x=j.id, k=k))])
    if not jobs:
        lines.append("\nЦеха стоят. Запустите задание — оно пойдёт и без вас в сети.")
    lines.append("\n<i>Отмена возвращает сырьё, но не топливо и не износ.</i>")
    return "\n".join(lines), kb([btn("＋ Новое задание", Nav(s="prod_loc"))], *rows, back())


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
        await show(cq, fmt.ok("Задание отменено") + "\n" + text, markup, scene="smelter")
    await guarded(cq, run)


@router.callback_query(Nav.filter(F.s == "prod_loc"))
async def cb_prod_loc(cq: CallbackQuery):
    await show(cq, fmt.head("Новое задание") + "\nГде работаем? Сырьё и установка должны быть в этой локации.",
               kb(loc_buttons("prod_cat"), back("production")), scene="workshop")
    await cq.answer()


@router.callback_query(Nav.filter(F.s == "prod_cat"))
async def cb_prod_cat(cq: CallbackQuery, callback_data: Nav):
    loc = callback_data.a
    if loc not in LOCATIONS:
        return await cq.answer("Устаревшая кнопка.", show_alert=True)
    async with tx() as s:
        user = await current_user(s, cq.from_user)
        acc, _ = await acting(s, user)
        owned = (await s.execute(select(Item.def_code, Item.status).where(
            Item.owner_id == acc, Item.location_code == loc, Item.def_code.in_(("workshop", "smelter", "refinery"))))).all()
    have: dict[str, list[int]] = {}
    for code, st in owned:
        have.setdefault(code, [0, 0])
        have[code][0] += 1
        have[code][1] += st == ITEM_IDLE
    rows = [[btn("✋ Ручная работа", Nav(s="prod_list", a=f"{loc}:hand"))]]
    for code in ("workshop", "smelter", "refinery"):
        n, idle = have.get(code, (0, 0))
        mark = f" · свободно {idle}/{n}" if n else " · нет"
        rows.append([btn(f"{FACILITY_RU[code]}{mark}", Nav(s="prod_list", a=f"{loc}:{code}"))])
    await show(cq, fmt.head(LOCATIONS[loc].name, "выберите установку"), kb(*rows, back("prod_loc")),
               scene=f"workshop@{loc}")
    await cq.answer()


def quality_lines(q: quality.Breakdown, with_facility: bool) -> list[str]:
    """Прогноз качества изделия с разбором факторов — игрок видит, что можно улучшить."""
    lo, hi = q.expected()
    span = lo.name if lo == hi else f"{lo.name} — {hi.name}"
    rows = [("база", f"{quality.BASE}"),
            ("мастерская" if with_facility else "ручная работа", f"+{q.facility}"),
            ("опыт мастера", f"+{q.experience}")]
    if q.modules:
        rows.append(("модули", f"{q.modules:+d}"))
    lines = [fmt.section("Качество изделия"), fmt.kv("Ожидается", span) + f" · оценка {q.base} ±{quality.ROLL_SPREAD}",
             fmt.table(rows, "lr"),
             f"<i>✦ Тщательно: +{quality.CAREFUL_BONUS} к оценке за +50% времени. Качество меняет только прочность "
             f"(брак ×0.8 … мастерская работа ×1.3).</i>"]
    if with_facility and q.facility < quality.FACILITY_MAX_BONUS:
        lines.append("<i>Отремонтированная мастерская даёт до +15.</i>")
    return lines


def recipe_line(code: str) -> str:
    r = RECIPES[code]
    ins = ", ".join(f"{resource_name(k)} {v}" for k, v in r.inputs.items())
    if r.item_inputs:
        ins += (", " if ins else "") + "модули: шасси, двигатель, бак, кузов"
    outs = item_name(r.output_item) if r.output_item else ", ".join(f"{resource_name(k)} {v}" for k, v in r.outputs.items())
    return f"{ins} → <b>{outs}</b> · {fmt.dur_game(r.minutes)}"


@router.callback_query(Nav.filter(F.s == "prod_list"))
async def cb_prod_list(cq: CallbackQuery, callback_data: Nav):
    loc, fac = parts(callback_data.a, 2)
    if loc not in LOCATIONS or fac not in FAC_CODE:
        return await cq.answer("Устаревшая кнопка.", show_alert=True)
    facility = FAC_CODE[fac]
    recs = [r for r in RECIPES.values() if r.facility == facility]
    lines = [fmt.head(FACILITY_RU[facility], LOCATIONS[loc].name)]
    rows = []
    for r in recs:
        lines.append(f"▸ {r.name}: {recipe_line(r.code)}")
        rows.append(btn(r.name, Nav(s="prod_rec", a=f"{loc}:{r.code}")))
    await show(cq, "\n".join(lines), kb(*[rows[i:i + 2] for i in range(0, len(rows), 2)], back("prod_cat", arg=loc)),
               scene=f"{SCENE_BY_FAC[facility]}@{loc}")
    await cq.answer()


def pick_modules(mods) -> dict:
    """Модуль по умолчанию для каждого слота: лучший по качеству (при равенстве — меньший ID)."""
    chosen = {}
    for m in sorted(mods, key=lambda m: (-items.quality_score(m), m.id)):
        chosen.setdefault(ITEMS[m.def_code].stats["slot"], m)
    return chosen


async def idle_modules(s, acc: int, loc: str):
    return (await s.scalars(select(Item).where(
        Item.owner_id == acc, Item.location_code == loc, Item.status == ITEM_IDLE,
        Item.def_code.in_([c for c, d in ITEMS.items() if d.kind == KIND_MODULE])).order_by(Item.id))).all()


def _fac_key(f):
    return "hand" if f is None else f


def enc_ids(ids: list[int]) -> str:
    """Компактная запись ID модулей для callback_data (base36): четыре ID укладываются в лимит 64 байта."""
    digits = "0123456789abcdefghijklmnopqrstuvwxyz"

    def b36(n: int) -> str:
        out = ""
        while True:
            n, r_ = divmod(n, 36)
            out = digits[r_] + out
            if n == 0:
                return out
    return ".".join(b36(i) for i in ids)


def dec_ids(text: str) -> list[int]:
    try:
        ids = [int(x, 36) for x in text.split(".")]
    except ValueError:
        raise StaleButton() from None
    if len(ids) != 4 or any(i < 0 for i in ids):
        raise StaleButton()
    return ids


NO_FACILITY_NOTE = "<i>Прогноз качества появится, когда освободится установка.</i>"


async def assembly_screen(s, user, loc: str, ids: list[int] | None):
    """Сборка грузовика: игрок выбирает модуль в каждом слоте, собирается ровно показанный набор."""
    r = RECIPES["assemble_truck"]
    acc, _ = await acting(s, user)
    mods = await idle_modules(s, acc, loc)
    by_slot: dict[int, list[Item]] = {}
    for m in sorted(mods, key=lambda m: (-items.quality_score(m), m.id)):
        by_slot.setdefault(ITEMS[m.def_code].stats["slot"], []).append(m)
    default = pick_modules(mods)
    chosen: dict[int, Item] = {}
    for sl in range(4):
        want = ids[sl] if ids else 0
        pick = next((m for m in by_slot.get(sl, []) if m.id == want), None)
        chosen[sl] = pick or default.get(sl)
    stock = await free_stock(s, acc, loc)
    fac_id = await production.find_idle_facility(s, acc, loc, "workshop")
    facility = await s.get(Item, fac_id) if fac_id else None
    q = None
    if facility is not None and all(chosen.values()):
        q = await production.quality_preview(s, user.id, r.code, facility=facility, modules=list(chosen.values()))
    lines = [fmt.head(r.name, LOCATIONS[loc].name), recipe_line(r.code), fmt.section("Модули")]
    rows = []
    cur = [chosen[sl].id if chosen[sl] else 0 for sl in range(4)]
    for sl in range(4):
        m = chosen[sl]
        cands = by_slot.get(sl, [])
        if m is None:
            lines.append(f"▸ {MODULE_SLOTS[sl]}: <b>нет</b> — изготовьте в мастерской")
            continue
        lines.append(f"▸ {MODULE_SLOTS[sl]}: {e(items.title(m))}" + (f" · вариантов {len(cands)}" if len(cands) > 1 else ""))
        if len(cands) > 1:
            nxt = cands[(cands.index(m) + 1) % len(cands)]
            alt = list(cur)
            alt[sl] = nxt.id
            rows.append([btn(f"⟳ {MODULE_SLOTS[sl]}: {items.button_title(nxt, 30)}", Nav(s="asm", a=f"{loc}:{enc_ids(alt)}"))])
    lines.append(fmt.kv("Запчасти", f"{stock.get('parts', 0)} из {r.inputs['parts']}") + " · " +
                 fmt.kv("мастерская", "свободна" if fac_id else "нет свободной"))
    if q is not None:
        lines += quality_lines(q, True)
    elif fac_id is None:
        lines.append(NO_FACILITY_NOTE)
    if all(chosen.values()):
        st = truck_stats([chosen[sl].def_code for sl in range(4)])
        lines.append(fmt.kv("Характеристики", f"{st.speed_kmh} км/ч · груз {st.payload} · {st.fuel_per_100km}/100 км · "
                                              f"запас хода {st.range_km} км"))
        k = nonce()
        z = f"{loc}:{enc_ids(cur)}"
        rows.append([btn("Собрать грузовик", Do(a="asm_go", z=z, k=k))])
        rows.append([btn("✦ Тщательно: +50% времени", Do(a="asm_go", y=1, z=z, k=k))])
    return "\n".join(lines), kb(*rows, back("prod_list", arg=f"{loc}:workshop"))


@router.callback_query(Nav.filter(F.s == "asm"))
async def cb_asm(cq: CallbackQuery, callback_data: Nav):
    loc, packed = parts(callback_data.a, 2)
    if loc not in LOCATIONS:
        raise StaleButton()
    ids = dec_ids(packed) if packed else None

    async def run():
        async with tx() as s:
            text, markup = await assembly_screen(s, await current_user(s, cq.from_user), loc, ids)
        await show(cq, text, markup, scene=f"assembly@{loc}")
    await guarded(cq, run)


@router.callback_query(Do.filter(F.a == "asm_go"))
async def do_asm_go(cq: CallbackQuery, callback_data: Do):
    loc, packed = parts(callback_data.z, 2)
    ids = dec_ids(packed)

    async def run():
        async with tx() as s:
            user = await current_user(s, cq.from_user)
            acc, _ = await acting(s, user)
            job = await production.start_craft(s, user.id, acc, "assemble_truck", loc, module_ids=ids,
                                               op_key=op_key(cq.from_user.id, callback_data.k),
                                               careful=bool(callback_data.y))
        await show(cq, "\n".join(craft_started_lines(job)), kb([btn("Задания", Nav(s="production"))], back()),
                   scene=f"assembly@{loc}")
    await guarded(cq, run)


def craft_started_lines(job) -> list[str]:
    lines = [fmt.ok(f"Задание #{job.id} запущено"), e(production.describe_job(job)),
             fmt.kv("Списано", ", ".join(f"{resource_name(k)} {v}" for k, v in job.inputs.items()) or "—"),
             fmt.kv("Готово через", fmt.left(job.finishes_at))]
    if "q_base" in (job.params or {}):
        lo = quality.tier_for(max(0, job.params["q_base"] - quality.ROLL_SPREAD))
        hi = quality.tier_for(min(100, job.params["q_base"] + quality.ROLL_SPREAD))
        span = lo.name if lo == hi else f"{lo.name} — {hi.name}"
        lines.append(fmt.kv("Ожидаемое качество", span) + (" · ✦ тщательно" if job.params.get("careful") else ""))
    return lines


@router.callback_query(Nav.filter(F.s == "prod_rec"))
async def cb_prod_rec(cq: CallbackQuery, callback_data: Nav):
    loc, code = parts(callback_data.a, 2)
    r = RECIPES.get(code)
    if r is None or loc not in LOCATIONS:
        return await cq.answer("Устаревшая кнопка.", show_alert=True)
    if r.item_inputs:  # сборка грузовика — отдельный экран с выбором модулей
        return await cb_asm(cq, Nav(s="asm", a=f"{loc}:"))
    async with tx() as s:
        user = await current_user(s, cq.from_user)
        acc, _ = await acting(s, user)
        stock = await free_stock(s, acc, loc)
        fac_id = await production.find_idle_facility(s, acc, loc, r.facility) if r.facility else None
        facility = await s.get(Item, fac_id) if fac_id else None
        q = None
        if r.facility is None or facility is not None:
            q = await production.quality_preview(s, user.id, code, facility=facility)
    k = nonce()
    lines = [fmt.head(r.name, LOCATIONS[loc].name), recipe_line(code)]
    if r.inputs:
        lines.append(fmt.section("На складе"))
        lines.append(fmt.table([(resource_name(res), stock.get(res, 0), f"нужно {n}") for res, n in r.inputs.items()], "lrl"))
    possible = min([stock.get(res, 0) // n for res, n in r.inputs.items()] or [r.max_runs])
    if r.facility:
        lines.append(f"Установка: {FACILITY_RU[r.facility]} — " + ("свободна" if fac_id else "<b>нет свободной</b>")
                     + f", износ {r.wear} за запуск.")
    else:
        lines.append("Ручная работа: занимает ваши руки (одна смена одновременно).")
    if q is not None:
        lines += quality_lines(q, r.facility is not None)
    elif r.output_item and fac_id is None:
        lines.append(NO_FACILITY_NOTE)
    if r.output_item:
        mark = "▶" if possible >= 1 else "·"
        rows = [[btn(f"{mark} Изготовить", Do(a="craft", x=1, z=f"{loc}:{code}", k=k))],
                [btn("✦ Тщательно: +50% времени", Do(a="craft", x=1, y=1, z=f"{loc}:{code}", k=k))]]
    else:
        runs = [n for n in (1, 2, 5, 10) if n <= r.max_runs]
        rows = [[btn(f"▶ ×{n}" if n <= possible else f"×{n}", Do(a="craft", x=n, z=f"{loc}:{code}", k=k)) for n in runs]]
        lines.append(f"Сырья хватает на запусков: <b>{min(possible, r.max_runs)}</b>")
    await show(cq, "\n".join(lines), kb(*rows, back("prod_list", arg=f"{loc}:{_fac_key(r.facility)}")),
               scene=f"{SCENE_BY_FAC[r.facility]}@{loc}")
    await cq.answer()


@router.callback_query(Do.filter(F.a == "craft"))
async def do_craft(cq: CallbackQuery, callback_data: Do):
    loc, code = parts(callback_data.z, 2)

    async def run():
        async with tx() as s:
            user = await current_user(s, cq.from_user)
            acc, _ = await acting(s, user)
            module_ids = None
            if code in RECIPES and RECIPES[code].item_inputs:
                module_ids = [m.id for m in pick_modules(await idle_modules(s, acc, loc)).values()]
            job = await production.start_craft(s, user.id, acc, code, loc, runs=callback_data.x,
                                               module_ids=module_ids, op_key=op_key(cq.from_user.id, callback_data.k),
                                               careful=bool(callback_data.y))
        r = RECIPES[code]
        scene = "assembly" if r.output_item == "truck" else SCENE_BY_FAC[r.facility]
        lines = craft_started_lines(job)
        await show(cq, "\n".join(lines), kb([btn("Задания", Nav(s="production")),
                                             btn("↻ Ещё", Nav(s="prod_rec", a=f"{loc}:{code}"))], back()),
                   scene=f"{scene}@{loc}")
    await guarded(cq, run)


# --- Техника -----------------------------------------------------------------------------------------

KIND_ICON = {"equipment": "▸", "module": "▸", "vehicle": "▸", "premium": "★"}


async def equipment_screen(s, acc: int, label: str):
    its = (await s.scalars(select(Item).where(Item.owner_id == acc, Item.parent_id.is_(None),
                                              Item.status != "destroyed").order_by(Item.id))).all()
    kinds = list(KIND_ICON)
    its = sorted(its, key=lambda i: (kinds.index(ITEMS[i.def_code].kind), ITEMS[i.def_code].name, i.id))
    lines = [fmt.head("Техника и предметы", label)]
    rows = []
    for it in its[:40]:
        d = ITEMS[it.def_code]
        where = LOCATIONS[it.location_code].name if it.location_code else "при себе"
        dur = f" · <code>{fmt.gauge(it.durability, it.max_durability, 5)}</code>" if it.max_durability else ""
        lines.append(f"{KIND_ICON.get(d.kind, '▸')} {e(items.title(it))}{dur} · {where} · {items.STATUS_RU[it.status]}")
        rows.append(btn(items.button_title(it, 30), Nav(s="item", a=str(it.id))))
    if not its:
        lines.append("Пусто. Инструменты и установки делаются в Производстве.")
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


def item_scene(def_code: str) -> str:
    return {"truck": "truck", "drill": "drill", "oil_rig": "pump", "smelter": "smelter", "refinery": "refinery",
            "workshop": "workshop", "pick": "mine_ore", "hand_pump": "mine_oil", "engineer_watch": "item_watch",
            "paint_black_brass": "item_paint", "syndicate_crest": "item_crest"}.get(def_code, "workshop")


async def item_card(s, user, item_id: int):
    acc, _ = await acting(s, user)
    it = await s.get(Item, item_id)
    if it is None or it.owner_id != acc:
        raise GameError("Предмет не найден у текущего владельца.")
    d = ITEMS[it.def_code]
    where = LOCATIONS[it.location_code].name if it.location_code else "при себе"
    lines = [fmt.head(items.title(it), e(d.description) if d.description else None),
             fmt.kv("Где", where) + " · " + fmt.kv("состояние", items.STATUS_RU[it.status])]
    if it.max_durability:
        lines.append(f"Прочность: <code>{fmt.gauge(it.durability, it.max_durability)}</code> "
                     f"{it.durability}/{it.max_durability}")
    if it.serial_no and d.kind == "premium":
        lines.append(fmt.kv("Серийный номер", f"№{it.serial_no:03d}"))
    tier = items.quality_of(it)
    if tier is not None:
        lines.append(fmt.kv("Качество", f"{tier.name} {quality.stars(tier)}") + f" · оценка {items.quality_score(it)}/100"
                     + (f" · прочность ×{tier.durability_mult:g}" if it.max_durability else " · влияет на прочность грузовика"))
    if d.mine:
        lines.append("Добыча: " + ", ".join(f"{resource_name(r)} +{q}" for r, q in d.mine.items())
                     + (f" за {fmt.dur_game(d.mine_minutes)}, дизель {d.mine_fuel}" if d.mine_fuel else " за смену"))
    k = nonce()
    rows = []
    if it.def_code == "truck":
        st = await transport.vehicle_stats(s, it.id)
        mods = await transport.modules_of(s, it.id)
        lines.append(fmt.section("Характеристики"))
        lines.append(fmt.table([("скорость", f"{st.speed_kmh} км/ч"), ("груз", st.payload),
                                ("расход", f"{st.fuel_per_100km}/100 км"), ("бак", st.tank),
                                ("запас хода", f"{st.range_km} км")], "lr"))
        lines.append("Модули: " + ", ".join(ITEMS[m.def_code].name for m in mods if ITEMS[m.def_code].kind == KIND_MODULE))
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
            rows.append([btn("В рейс", Nav(s="trip_dest", a=f"{it.id}:{it.location_code}"))])
    if it.status == ITEM_IDLE:
        rule = REPAIR.get(it.def_code)
        if rule and it.durability < it.max_durability:
            ins = ", ".join(f"{resource_name(r)} {q}" for r, q in rule.inputs.items())
            lines.append(f"Ремонт: {ins} → +{rule.restore} за {fmt.dur_game(rule.minutes)}"
                         f"{', нужна мастерская рядом' if rule.needs_workshop else ''}.")
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
    elif it.status == "listed":
        lines.append("<i>Выставлен на рынок — снять можно в «Мои заявки».</i>")
        rows.append([btn("Мои заявки", Nav(s="my_orders"))])
    elif it.status == "locked":
        lines.append(fmt.warn("Заблокирован (возврат Stars или спор). Решение — /paysupport."))
    return "\n".join(x for x in lines if x), kb(*rows, back("equipment"))


@router.callback_query(Nav.filter(F.s == "item"))
async def cb_item(cq: CallbackQuery, callback_data: Nav):
    async def run():
        async with tx() as s:
            user = await current_user(s, cq.from_user)
            text, markup = await item_card(s, user, num(callback_data.a))
            it = await s.get(Item, num(callback_data.a))
        await show(cq, text, markup, scene=item_scene(it.def_code))
    await guarded(cq, run)


@router.callback_query(Do.filter(F.a == "repair"))
async def do_repair(cq: CallbackQuery, callback_data: Do):
    async def run():
        async with tx() as s:
            user = await current_user(s, cq.from_user)
            acc, _ = await acting(s, user)
            job = await production.start_repair(s, user.id, acc, callback_data.x, steps=callback_data.y,
                                                op_key=op_key(cq.from_user.id, callback_data.k))
        lines = [fmt.ok("Ремонт начат"), e(production.describe_job(job)),
                 fmt.kv("Списано", ", ".join(f"{resource_name(k)} {v}" for k, v in job.inputs.items())),
                 fmt.kv("Готово через", fmt.left(job.finishes_at))]
        await show(cq, "\n".join(lines), kb([btn("Задания", Nav(s="production"))], back("equipment")), scene="repair")
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
        painted = callback_data.a == "paint"
        text = (fmt.ok("Окраска нанесена: «Чёрная латунь»") + "\nХарактеристики не меняются — только вид."
                if painted else fmt.ok("Окраска снята") + "\nОна вернулась в инвентарь.")
        await show(cq, text, kb([btn("К грузовику", Nav(s="item", a=str(vid)))], back("equipment")),
                   scene="truck_brass" if painted else "truck")
    await guarded(cq, run)


@router.callback_query(Do.filter(F.a == "giveitem"))
async def do_giveitem(cq: CallbackQuery, callback_data: Do):
    async def run():
        async with tx() as s:
            user = await current_user(s, cq.from_user)
            acc, label = await acting(s, user)
            await companies.transfer_item(s, user.id, acc, callback_data.y, callback_data.x,
                                          op_key=op_key(cq.from_user.id, callback_data.k))
            text, markup = await equipment_screen(s, acc, label)
        await show(cq, fmt.ok("Предмет передан") + "\n" + text, markup)
    await guarded(cq, run)


@router.callback_query(Do.filter(F.a == "sellitem"))
async def do_sellitem(cq: CallbackQuery, callback_data: Do, state: FSMContext):
    await ask(cq, state, "item_price", "Цена продажи в кронах (₭)? Комиссия 2% с продавца уничтожается.",
              item_id=callback_data.x)


@on_input("item_price")
async def in_item_price(message: Message, text: str, data: dict):
    price = parse_int(text)
    async with tx() as s:
        user = await current_user(s, message.from_user)
        acc, _ = await acting(s, user)
        o = await market.place_ask_item(s, user.id, acc, data["item_id"], price,
                                        op_key=op_key(message.from_user.id, f"m{message.message_id}"))
    await show(message, fmt.ok("Выставлено на рынок") + f"\nЗаявка #{o.id}: {e(item_name(o.item_def))} за {fmt.cr(price)}.",
               kb([btn("Мои заявки", Nav(s="my_orders"))], back()), scene="market")
