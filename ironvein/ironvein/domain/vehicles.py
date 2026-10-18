"""Расчёт характеристик модульного грузовика из установленных модулей."""

import math
from dataclasses import dataclass

from ironvein.domain.catalog import ITEMS, TRUCK_KM_PER_WEAR


@dataclass(frozen=True)
class TruckStats:
    speed_kmh: int
    payload: int
    fuel_per_100km: int
    tank: int
    max_durability: int

    @property
    def range_km(self) -> int:
        return self.tank * 100 // max(1, self.fuel_per_100km)


def truck_stats(module_codes: list[str]) -> TruckStats:
    by_slot = {ITEMS[c].stats["slot"]: ITEMS[c].stats for c in module_codes}
    if set(by_slot) != {0, 1, 2, 3}:
        raise ValueError("грузовику нужны шасси, двигатель, бак и кузов")
    chassis, engine, tank, body = by_slot[0], by_slot[1], by_slot[2], by_slot[3]
    return TruckStats(
        speed_kmh=max(10, engine["speed"] + body["speed"]),
        payload=min(engine["payload"], body["capacity"]),
        fuel_per_100km=max(1, engine["fuel100"] + body["fuel100"]),
        tank=tank["tank"],
        max_durability=max(20, chassis["durability"] + body["durability"]),
    )


def trip_fuel(stats: TruckStats, km: int) -> int:
    return math.ceil(km * stats.fuel_per_100km / 100)


def trip_wear(km: int) -> int:
    return math.ceil(km / TRUCK_KM_PER_WEAR)


def trip_minutes(speed_kmh: int, km: int) -> int:
    return math.ceil(km * 60 / speed_kmh)
