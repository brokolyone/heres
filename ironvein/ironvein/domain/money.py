"""Целочисленная денежная арифметика. Никаких float."""


def fee_for(gross: int, bps: int) -> int:
    """Комиссия округляется ВВЕРХ, минимум 1 ₭ при ненулевой сумме и ненулевой ставке.

    Округление вверх на каждой сделке означает, что дробление сделки никогда не уменьшает
    суммарную комиссию (ceil(a)+ceil(b) >= ceil(a+b)).
    """
    if gross <= 0 or bps <= 0:
        return 0
    return max(1, -(-gross * bps // 10000))


def cumulative_split(total: int, done_qty: int, qty: int) -> int:
    """Пропорциональная доля total за done_qty из qty, округление вниз. При done_qty == qty — ровно total."""
    if done_qty >= qty:
        return total
    return total * done_qty // qty


def fmt_cr(amount: int) -> str:
    return f"{amount:,}".replace(",", " ") + " ₭"
