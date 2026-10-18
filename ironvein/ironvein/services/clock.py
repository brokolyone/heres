"""Игровые часы. В тестах сдвигаются через `advance`, чтобы проверять ETA и сроки без ожидания."""

from datetime import UTC, datetime, timedelta

from ironvein.config import get_settings

_offset = timedelta(0)


def now() -> datetime:
    return datetime.now(UTC) + _offset


def advance(**kw) -> None:
    global _offset
    _offset += timedelta(**kw)


def reset() -> None:
    global _offset
    _offset = timedelta(0)


def game_minutes(minutes: float) -> timedelta:
    """Длительность игрового процесса с учётом GAME_SPEED."""
    speed = get_settings().game_speed or 1.0
    return timedelta(minutes=minutes / speed)
