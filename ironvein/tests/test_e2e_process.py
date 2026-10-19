"""Сквозной тест настоящего процесса бота против локального эмулятора Telegram Bot API по HTTP.

Проверяется то, что не видят тесты с подменённой сессией: запуск `python -m ironvein.bot`, long polling,
сериализация запросов aiogram, multipart-загрузка PNG, фоновые задачи с уведомлениями и полный цикл
оплаты Stars (invoice → pre_checkout_query → successful_payment). Каждый исходящий запрос проверяется
правилами Bot API (HTML, лимиты, callback_data).
"""

import asyncio
import json
import os
import signal
import sys
import time
from pathlib import Path

import pytest
from aiohttp import web
from sqlalchemy import select

from ironvein.handlers.ui import Do, Nav
from ironvein.models import Deposit, PremiumOrder
from tests.conftest import TEST_DB
from tests.telegram_rules import TelegramRuleError, check_html, visible

ROOT = Path(__file__).resolve().parents[1]
TOKEN = "4242:E2E"
USER = {"id": 555001, "is_bot": False, "first_name": "Ада", "username": "ada_e2e"}
CHAT = {"id": 555001, "type": "private"}


class FakeTelegram:
    def __init__(self):
        self.updates: list[dict] = []
        self.calls: list[tuple[str, dict]] = []
        self.next_update = 1
        self.next_msg = 1000
        self.errors: list[str] = []

    def push(self, **upd):
        upd["update_id"] = self.next_update
        self.next_update += 1
        self.updates.append(upd)

    def message(self, **kw):
        self.next_msg += 1
        return {"message_id": self.next_msg, "date": int(time.time()), "chat": CHAT, **kw}

    async def handle(self, request: web.Request):
        method = request.match_info["method"]
        if request.content_type.startswith("multipart/"):
            data = {}
            async for part in await request.multipart():
                data[part.name] = bytes(await part.read()) if part.filename else await part.text()
            for k, v in list(data.items()):  # aiogram передаёт файлы как attach://<имя части>
                if isinstance(v, str) and v.startswith("attach://"):
                    data[k] = data.get(v[len("attach://"):], v)
        else:
            data = dict(await request.post()) if request.can_read_body else {}
        self.calls.append((method, data))
        try:
            self.validate(method, data)
        except TelegramRuleError as ex:
            self.errors.append(f"{method}: {ex}")
            return web.json_response({"ok": False, "error_code": 400, "description": f"Bad Request: {ex}"})
        return web.json_response({"ok": True, "result": await self.result(method, data)})

    def validate(self, method, data):
        for key in ("text", "caption"):
            if key in data and data.get("parse_mode") == "HTML":
                check_html(data[key])
                if len(visible(data[key])) > (1024 if key == "caption" else 4096):
                    raise TelegramRuleError(f"{key} слишком длинный")
        if "media" in data:
            media = json.loads(data["media"])
            if media.get("caption"):
                check_html(media["caption"])
        if "reply_markup" in data:
            for row in json.loads(data["reply_markup"]).get("inline_keyboard", []):
                for b in row:
                    if "callback_data" in b and len(b["callback_data"].encode()) > 64:
                        raise TelegramRuleError("callback_data > 64 байт")
        if method == "sendPhoto" and isinstance(data.get("photo"), bytes) and not data["photo"].startswith(b"\x89PNG"):
            raise TelegramRuleError("photo не PNG")

    async def result(self, method, data):
        if method == "getMe":
            return {"id": 4242, "is_bot": True, "first_name": "IronVein", "username": "ironvein_bot"}
        if method == "getUpdates":
            offset = int(data.get("offset") or 0)
            for _ in range(10):
                pending = [u for u in self.updates if u["update_id"] >= offset]
                if pending:
                    return pending
                await asyncio.sleep(0.05)
            return []
        if method in ("sendMessage", "editMessageText"):
            return self.message(text=data.get("text", ""))
        if method in ("sendPhoto", "editMessageMedia"):
            caption = data.get("caption") or json.loads(data.get("media", "{}")).get("caption", "")
            return self.message(caption=caption, photo=[{"file_id": f"F{self.next_msg}", "file_unique_id": "u",
                                                          "width": 576, "height": 324}])
        if method == "sendInvoice":
            return self.message(text="invoice")
        return True

    def texts(self):
        out = []
        for m, d in self.calls:
            if m in ("sendMessage", "editMessageText"):
                out.append(d.get("text", ""))
            elif m == "sendPhoto":
                out.append(d.get("caption", ""))
            elif m == "editMessageMedia":
                out.append(json.loads(d["media"]).get("caption", ""))
            elif m == "answerCallbackQuery" and d.get("text"):
                out.append(d["text"])
        return out

    async def wait_for(self, predicate, timeout=20.0, what=""):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return
            await asyncio.sleep(0.1)
        raise AssertionError(f"не дождались: {what}\nвызовы: {[m for m, _ in self.calls][-30:]}\n"
                             f"тексты: {self.texts()[-5:]}")


@pytest.fixture
async def fake_tg():
    tg = FakeTelegram()
    app = web.Application()
    app.router.add_route("*", "/bot{token}/{method}", tg.handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    tg.port = site._server.sockets[0].getsockname()[1]
    yield tg
    await runner.cleanup()


@pytest.fixture
async def bot_process(sm, fake_tg):
    env = {**os.environ, "BOT_TOKEN": TOKEN, "DATABASE_URL": TEST_DB,
           "TELEGRAM_API_URL": f"http://127.0.0.1:{fake_tg.port}", "GAME_SPEED": "600", "JOB_POLL_SECONDS": "0.3",
           "ADMIN_IDS": "", "ENVIRONMENT": "development", "PYTHONPATH": str(ROOT)}
    proc = await asyncio.create_subprocess_exec(sys.executable, "-m", "ironvein.bot", cwd=str(ROOT), env=env,
                                                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
    yield proc
    if proc.returncode is None:
        proc.send_signal(signal.SIGINT)
        try:
            await asyncio.wait_for(proc.wait(), 10)
        except TimeoutError:
            proc.kill()


def cb(data, msg_id=1001):
    return {"id": str(time.time_ns()), "from": USER, "chat_instance": "e2e", "data": data.pack(),
            "message": {"message_id": msg_id, "date": int(time.time()), "chat": CHAT,
                        "photo": [{"file_id": "x", "file_unique_id": "y", "width": 1, "height": 1}]}}


def msg(**kw):
    return {"message_id": int(time.time_ns() % 10**9), "date": int(time.time()), "chat": CHAT, "from": USER, **kw}


async def test_real_bot_process_end_to_end(sm, fake_tg, bot_process):
    tg = fake_tg
    await tg.wait_for(lambda: any(m == "getUpdates" for m, _ in tg.calls), what="старт поллинга")
    assert any(m == "setMyCommands" for m, _ in tg.calls)

    # 1. /start — регистрация и пиксельная картинка (multipart PNG)
    tg.push(message=msg(text="/start", entities=[{"type": "bot_command", "offset": 0, "length": 6}]))
    await tg.wait_for(lambda: any("Добро пожаловать" in t for t in tg.texts()), what="приветствие")
    photo = next(d for m, d in tg.calls if m == "sendPhoto")
    assert isinstance(photo["photo"], bytes) and photo["photo"].startswith(b"\x89PNG")

    # 2. Добыча кнопкой; при GAME_SPEED=600 смена длится секунду — фоновая задача шлёт уведомление
    async with sm() as s:
        dep = await s.scalar(select(Deposit).where(Deposit.code == "rust_north"))
    tg.push(callback_query=cb(Do(a="mine", x=dep.id, k="e2e1")))
    await tg.wait_for(lambda: any("Смена началась" in t for t in tg.texts()), what="старт смены")
    await tg.wait_for(lambda: any("Готово" in t for t in tg.texts()), timeout=30, what="уведомление о добыче")

    # 3. Повторное нажатие той же кнопки не запускает вторую смену
    tg.push(callback_query=cb(Do(a="mine", x=dep.id, k="e2e1")))
    await tg.wait_for(lambda: any("Уже выполнено" in t for t in tg.texts()), what="идемпотентность")

    # 4. Stars: счёт → pre_checkout → successful_payment → выдача экземпляра
    tg.push(callback_query=cb(Do(a="pay", z="engineer_watch")))
    await tg.wait_for(lambda: any(m == "sendInvoice" for m, _ in tg.calls), what="счёт")
    inv = next(d for m, d in tg.calls if m == "sendInvoice")
    assert inv["currency"] == "XTR" and json.loads(inv["prices"])[0]["amount"] == 100
    tg.push(pre_checkout_query={"id": "pcq1", "from": USER, "currency": "XTR", "total_amount": 100,
                                "invoice_payload": inv["payload"]})
    await tg.wait_for(lambda: any(m == "answerPreCheckoutQuery" for m, _ in tg.calls), what="pre_checkout")
    ans = next(d for m, d in tg.calls if m == "answerPreCheckoutQuery")
    assert ans["ok"] in ("true", "True", True)
    tg.push(message=msg(successful_payment={"currency": "XTR", "total_amount": 100, "invoice_payload": inv["payload"],
                                            "telegram_payment_charge_id": "e2e-charge-1",
                                            "provider_payment_charge_id": ""}))
    await tg.wait_for(lambda: any("Оплата получена" in t for t in tg.texts()), what="выдача премиума")
    async with sm() as s:
        order = await s.scalar(select(PremiumOrder))
    assert order.status == "fulfilled" and order.item_id

    # 5. Навигация по главным разделам — без единого сбоя
    for screen in ("market", "transport", "company", "contracts", "production", "inventory", "guide"):
        tg.push(callback_query=cb(Nav(s=screen)))
    await tg.wait_for(lambda: sum(m == "answerCallbackQuery" for m, _ in tg.calls) >= 9, what="навигация")
    n = sum(m == "editMessageMedia" for m, _ in tg.calls)
    tg.push(callback_query=cb(Nav(s="market")))  # сцена «рынок» уже загружена — должна уйти по file_id
    await tg.wait_for(lambda: sum(m == "editMessageMedia" for m, _ in tg.calls) > n, what="повторный рынок")
    await asyncio.sleep(0.5)

    assert not tg.errors, tg.errors
    assert not any("Сбой терминала" in t for t in tg.texts()), tg.texts()
    # Экраны-действия редактируют существующее сообщение, а уже загруженная сцена переиспользует file_id.
    edits = [json.loads(d["media"]) for m, d in tg.calls if m == "editMessageMedia"]
    assert edits, "картинка не редактировалась"
    assert not str(edits[-1]["media"]).startswith("attach://"), "кэш file_id не сработал"

    # 6. Корректная остановка по сигналу
    bot_process.send_signal(signal.SIGINT)
    out = (await asyncio.wait_for(bot_process.stdout.read(), 15)).decode(errors="replace")
    await asyncio.wait_for(bot_process.wait(), 15)
    assert "Traceback" not in out, out[-3000:]
