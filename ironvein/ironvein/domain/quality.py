"""Качество изготовленных предметов.

Качество — это в первую очередь результат решений игрока, а не лотерея:
  база 45
  + состояние установки: до +15 (изношенная мастерская работает хуже); ручная работа — фиксированные +5;
  + опыт мастера: до +20 (изделия этого же рецепта ценятся втрое выше, чем прочие изделия);
  + тщательная работа: +12 за +50% времени — выбор игрока;
  + качество модулей (только сборка грузовика): ±, среднее отклонение модулей от «обычного» × 0.4;
  ± небольшой разброс до 8 очков, детерминированный по номеру задания (выдача ровно одна и повторяема).

Эффект ограничен прочностью (×0.8…×1.3): лучшее качество — реже ремонт и дороже на рынке, но никаких
бонусов к выработке, скорости или расходу. Так качество углубляет рынок, не создавая дисбаланса.
"""

import hashlib
import hmac
from dataclasses import dataclass


@dataclass(frozen=True)
class Tier:
    code: str
    name: str
    min_score: int
    durability_mult: float
    stars: int


TIERS: tuple[Tier, ...] = (
    Tier("flawed", "брак", 0, 0.8, 0),
    Tier("common", "обычное", 40, 1.0, 1),
    Tier("good", "хорошее", 60, 1.1, 2),
    Tier("fine", "отличное", 75, 1.2, 3),
    Tier("master", "мастерская работа", 90, 1.3, 4),
)
TIER_BY_CODE = {t.code: t for t in TIERS}
COMMON_SCORE = 55  # оценка «по умолчанию» для предметов без записанного качества (стартовая кирка, модули из старых версий)

BASE = 45
HAND_BONUS = 5
FACILITY_MAX_BONUS = 15
EXPERIENCE_MAX_BONUS = 20
CAREFUL_BONUS = 12
CAREFUL_TIME_MULT = 1.5
ROLL_SPREAD = 8
MODULE_WEIGHT = 0.4


def tier_for(score: int) -> Tier:
    tier = TIERS[0]
    for t in TIERS:
        if score >= t.min_score:
            tier = t
    return tier


def experience_bonus(same_recipe: int, other_items: int) -> int:
    return min(EXPERIENCE_MAX_BONUS, 3 * same_recipe + other_items // 2)


def facility_bonus(condition: float | None) -> int:
    """condition — доля прочности установки (0..1); None — ручная работа без установки."""
    if condition is None:
        return HAND_BONUS
    return round(FACILITY_MAX_BONUS * max(0.0, min(1.0, condition)))


def module_bonus(module_scores: list[int]) -> int:
    if not module_scores:
        return 0
    avg = sum(module_scores) / len(module_scores)
    return round((avg - COMMON_SCORE) * MODULE_WEIGHT)


@dataclass(frozen=True)
class Breakdown:
    facility: int
    experience: int
    careful: int
    modules: int

    @property
    def base(self) -> int:
        return max(0, min(100, BASE + self.facility + self.experience + self.careful + self.modules))

    def expected(self) -> tuple[Tier, Tier]:
        """Худшая и лучшая возможная ступень с учётом разброса."""
        return (tier_for(max(0, self.base - ROLL_SPREAD)), tier_for(min(100, self.base + ROLL_SPREAD)))


def breakdown(condition: float | None, same_recipe: int, other_items: int, careful: bool,
              module_scores: list[int] | None = None) -> Breakdown:
    return Breakdown(facility=facility_bonus(condition), experience=experience_bonus(same_recipe, other_items),
                     careful=CAREFUL_BONUS if careful else 0, modules=module_bonus(module_scores or []))


def roll(job_id: int, secret: bytes = b"") -> int:
    """Разброс −8…+8: детерминирован по номеру задания (аудит, повторяемость), но с серверным секретом —
    игрок, знающий код, не может заранее вычислить исход и «перебросить» неудачное задание отменой."""
    digest = hmac.new(secret or b"ironvein", f"quality:{job_id}".encode(), hashlib.sha256).digest()
    return int.from_bytes(digest[:4], "big") % (2 * ROLL_SPREAD + 1) - ROLL_SPREAD


def final_score(base: int, job_id: int, secret: bytes = b"") -> int:
    return max(0, min(100, base + roll(job_id, secret)))


def scaled_durability(max_durability: int, tier: Tier) -> int:
    return max(1, round(max_durability * tier.durability_mult)) if max_durability else 0


def stars(tier: Tier) -> str:
    """Метка ступени: звёзды, для брака — ✗ (название ступени пишется отдельно, без повтора)."""
    return "★" * tier.stars if tier.stars else "✗"
