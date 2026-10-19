"""Магазин за Telegram Stars: каталог -> карточка -> счёт XTR -> pre_checkout -> successful_payment -> выдача."""

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, LabeledPrice, Message, PreCheckoutQuery

from ironvein.config import get_settings
from ironvein.handlers.ui import Do, Nav, back, btn, current_user, e, guarded, kb, notify, show, tx
from ironvein.models import PremiumProduct
from ironvein.services import premium
from ironvein.services.common import audit

log = logging.getLogger(__name__)
router = Router(name="donate")
SCENE = {"engineer_watch": "item_watch", "paint_black_brass": "item_paint", "syndicate_crest": "item_crest"}
STATUS_RU = {"created": "ожидает оплаты", "paid": "оплачен, выдаётся", "fulfilled": "выдан", "expired": "истёк",
             "refund_pending": "ожидает возврата", "refunded": "возвращён"}


async def donate_root(event):
    async with tx() as s:
        prods = await premium.catalog(s)
    lines = ["<b>Донат · Telegram Stars</b>",
             "Только косметика и коллекции — никаких ресурсов, ускорений и бонусов. Купленное можно перепродать "
             "игрокам за кроны на рынке; бот кроны за Stars не выдаёт и не выкупает."]
    rows = []
    for p in prods:
        left = f" · осталось {p.edition_limit - p.issued - p.reserved}" if p.edition_limit else ""
        lines.append(f"▸ {e(p.title)} — {p.price_stars} ⭐{left}")
        rows.append([btn(f"{p.title} · {p.price_stars} ⭐", Nav(s="product", a=p.code))])
    rows.append([btn("Поддержка платежей", Nav(s="paysupport"))])
    await show(event, "\n".join(lines), kb(*rows, back()), scene="item_watch")


@router.message(Command("donate"))
async def cmd_donate(message: Message):
    await donate_root(message)


@router.callback_query(Nav.filter(F.s == "donate"))
async def cb_donate(cq: CallbackQuery):
    await donate_root(cq)
    await cq.answer()


@router.callback_query(Nav.filter(F.s == "product"))
async def cb_product(cq: CallbackQuery, callback_data: Nav):
    async with tx() as s:
        p = await s.get(PremiumProduct, callback_data.a)
    if p is None or not p.active:
        return await cq.answer("Товар недоступен.", show_alert=True)
    edition = (f"Тираж: {p.edition_limit}, выпущено {p.issued}, забронировано {p.reserved}."
               if p.edition_limit else "Тираж не ограничен.")
    text = (f"<b>{e(p.title)}</b>\n{e(p.description)}\n{edition}\n"
            "У каждого экземпляра — серийный номер и история владельцев.")
    await show(cq, text, kb([btn(f"Оплатить {p.price_stars} ⭐", Do(a="pay", z=p.code))], back("donate")),
               scene=SCENE.get(p.code, "item_watch"))
    await cq.answer()


@router.callback_query(Do.filter(F.a == "pay"))
async def do_pay(cq: CallbackQuery, callback_data: Do):
    async def run():
        async with tx() as s:
            user = await current_user(s, cq.from_user)
            o = await premium.create_order(s, user.id, callback_data.z)
            p = await s.get(PremiumProduct, o.product_code)
        # Цена и payload берутся только из серверного заказа.
        await cq.message.answer_invoice(
            title=p.title[:32], description=p.description[:255], payload=o.public_id, currency="XTR",
            prices=[LabeledPrice(label=p.title[:32], amount=o.price_stars)])
    await guarded(cq, run)


@router.pre_checkout_query()
async def on_pre_checkout(q: PreCheckoutQuery):
    """Telegram ждёт ответа не дольше 10 секунд: одна короткая транзакция."""
    try:
        async with tx() as s:
            ok, err = await premium.pre_checkout(s, q.invoice_payload, q.from_user.id, q.total_amount, q.currency)
    except Exception:
        log.exception("pre_checkout failed")
        ok, err = False, "Временная ошибка. Попробуйте позже — деньги не списаны."
    await q.answer(ok=ok, error_message=None if ok else err)


@router.message(F.successful_payment)
async def on_successful_payment(message: Message):
    sp = message.successful_payment
    try:
        async with tx() as s:
            o = await premium.successful_payment(s, sp.invoice_payload, message.from_user.id, sp.total_amount,
                                                 sp.currency, sp.telegram_payment_charge_id, fulfill_now=False)
    except Exception:
        log.critical("PAYMENT NOT RECORDED: charge=%s payload=%s user=%s amount=%s", sp.telegram_payment_charge_id,
                     sp.invoice_payload, message.from_user.id, sp.total_amount, exc_info=True)
        await message.answer("Оплата получена, но запись не удалась. Мы видим платёж и решим вопрос: /paysupport")
        return
    p = serial = None
    if o is not None:
        try:
            async with tx() as s:
                if o.status == "paid":
                    o = await premium.fulfill_order(s, o.id)
                p = await s.get(PremiumProduct, o.product_code)
                if o.item_id:
                    from ironvein.models import Item
                    serial = (await s.get(Item, o.item_id)).serial_no
        except Exception:
            log.exception("fulfillment deferred for order %s", o.id)  # доделает фоновая задача retry_paid
    if o is None:
        await message.answer("Платёж получен, но заказ не найден. Мы разберёмся вручную: /paysupport")
        return
    if o.status == "fulfilled" and p is not None:
        await show(message, f"<b>Оплата получена.</b>\n{e(p.title)} №{serial:03d} теперь ваш. "
                            "Найдите его в разделе «Техника»; продать можно на рынке.",
                   kb([btn("Техника", Nav(s="equipment"))], back()), scene=SCENE.get(p.code, "item_watch"))
    elif o.status == "refund_pending":
        await message.answer("Оплата получена, но экземпляр уже недоступен. Stars будут возвращены автоматически.")
    else:
        await message.answer("Оплата получена, выдача обрабатывается. Если предмет не появится — /paysupport.")


@router.message(F.refunded_payment)
async def on_refunded_payment(message: Message):
    rp = message.refunded_payment
    async with tx() as s:
        await premium.mark_refunded(s, charge_id=rp.telegram_payment_charge_id, source="telegram")
    await message.answer("Возврат Stars зафиксирован. Выданный экземпляр заблокирован до решения администрации.")


async def paysupport_text(s, user) -> str:
    orders = await premium.orders_of(s, user.id)
    lines = ["<b>Поддержка платежей</b>",
             "Если оплата прошла, а предмет не появился, или нужен возврат — напишите сюда сообщение с номером заказа; "
             "администрация отвечает вручную. Возврат делается через Telegram Stars (refundStarPayment). "
             "Предметы, по которым сделан возврат, блокируются у текущего владельца."]
    for o in orders:
        lines.append(f"▸ заказ {o.id} · {o.product_code} · {o.price_stars} ⭐ · {STATUS_RU.get(o.status, o.status)}")
    if not orders:
        lines.append("Заказов нет.")
    admins = get_settings().admin_ids
    if not admins:
        lines.append("Контакт администрации не настроен.")
    return "\n".join(lines)


@router.message(Command("paysupport"))
async def cmd_paysupport(message: Message):
    async with tx() as s:
        user = await current_user(s, message.from_user)
        text = await paysupport_text(s, user)
        await audit(s, "paysupport_open", actor_user_id=user.id)
    await show(message, text, kb(back()))
    for admin in get_settings().admin_ids:
        await notify(message.bot, admin, f"/paysupport от {e(message.from_user.full_name)} (tg {message.from_user.id})")


@router.callback_query(Nav.filter(F.s == "paysupport"))
async def cb_paysupport(cq: CallbackQuery):
    async def run():
        async with tx() as s:
            text = await paysupport_text(s, await current_user(s, cq.from_user))
        await show(cq, text, kb(back("donate")))
    await guarded(cq, run)
