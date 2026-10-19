"""Единое оформление экранов: компактный «терминал» без лишних эмодзи."""

import html

from ironvein.domain.money import fmt_cr
from ironvein.services import clock

RULE = "<code>━━━━━━━━━━━━━━━━━━━━━━</code>"


def head(title: str, sub: str | None = None) -> str:
    out = f"<b>⟦ {html.escape(title.upper())} ⟧</b>"
    if sub:
        out += f"\n<i>{sub}</i>"
    return out


def section(title: str) -> str:
    return f"\n<b>▌{html.escape(title)}</b>"


def kv(label: str, value) -> str:
    return f"{label}: <b>{value}</b>"


def cr(amount: int) -> str:
    return fmt_cr(amount)


def dur_game(game_minutes: float) -> str:
    """Длительность процесса в реальном времени (с учётом GAME_SPEED)."""
    return human(clock.real_minutes(game_minutes))


def human(minutes: int) -> str:
    minutes = max(0, int(minutes))
    d, rem = divmod(minutes, 1440)
    h, m = divmod(rem, 60)
    if d:
        return f"{d} д {h} ч"
    if h:
        return f"{h} ч {m:02d} мин" if m else f"{h} ч"
    return f"{max(1, m)} мин"


def left(dt) -> str:
    secs = int((dt - clock.now()).total_seconds())
    if secs <= 0:
        return "вот-вот"
    return human((secs + 59) // 60)


def progress(start, end, width: int = 10) -> str:
    total = (end - start).total_seconds()
    done = (clock.now() - start).total_seconds()
    frac = 1.0 if total <= 0 else min(1.0, max(0.0, done / total))
    filled = round(frac * width)
    return "▰" * filled + "▱" * (width - filled)


def gauge(cur: int, mx: int, width: int = 10) -> str:
    if mx <= 0:
        return ""
    filled = round(width * max(0, cur) / mx)
    return "▰" * filled + "▱" * (width - filled)


def table(rows: list[tuple], aligns: str | None = None) -> str:
    """Моноширинная таблица. aligns: строка из 'l'/'r' на колонку."""
    if not rows:
        return ""
    cols = len(rows[0])
    aligns = aligns or "l" + "r" * (cols - 1)
    widths = [max(len(str(r[i])) for r in rows) for i in range(cols)]
    lines = []
    for r in rows:
        cells = [str(c).ljust(widths[i]) if aligns[i] == "l" else str(c).rjust(widths[i]) for i, c in enumerate(r)]
        # Каждая строка — отдельный <code>: тег не переходит через строку, и усечение не ломает HTML.
        lines.append("<code>" + html.escape("  ".join(cells).rstrip()) + "</code>")
    return "\n".join(lines)


def ok(text: str) -> str:
    return f"✔ <b>{text}</b>"


def warn(text: str) -> str:
    return f"⚠ {text}"
