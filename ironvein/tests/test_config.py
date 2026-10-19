from ironvein.config import Settings


def test_admin_ids_parsing(monkeypatch):
    monkeypatch.setenv("ADMIN_IDS", "")
    assert Settings(_env_file=None).admin_ids == []
    monkeypatch.setenv("ADMIN_IDS", "12, 34")
    assert Settings(_env_file=None).admin_ids == [12, 34]
    monkeypatch.setenv("ADMIN_IDS", "56")
    assert Settings(_env_file=None).admin_ids == [56]


def test_production_flag(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    assert Settings(_env_file=None).is_production


def test_clip_keeps_html_balanced():
    from ironvein.handlers.ui import clip, visible_len
    text = "\n".join(f"<b>строка {i}</b> <code>{'x' * 50}</code>" for i in range(300))
    out = clip(text, 1000)
    assert visible_len(out) <= 1000
    assert out.count("<b>") == out.count("</b>") and out.count("<code>") == out.count("</code>")
    assert clip("коротко") == "коротко"


def test_fmt_helpers():
    from ironvein.handlers import fmt
    assert fmt.human(5) == "5 мин" and fmt.human(60) == "1 ч" and fmt.human(95) == "1 ч 35 мин"
    assert fmt.human(1500) == "1 д 1 ч"
    assert fmt.gauge(5, 10) == "▰▰▰▰▰▱▱▱▱▱"
    assert "&lt;" in fmt.table([("<x>", 1)])


async def test_retry_on_deadlock_code():
    from sqlalchemy.exc import DBAPIError

    from ironvein.handlers.ui import run_retrying

    class Orig(Exception):
        pgcode = "40P01"
    calls = []

    async def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise DBAPIError("stmt", {}, Orig())
    await run_retrying(flaky)
    assert len(calls) == 3
