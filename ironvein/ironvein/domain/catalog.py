"""Технологический каталог IronVein.

Это единственное место, где заданы рецепты, характеристики техники, локации и маршруты.
Все числа — ПРЕДВАРИТЕЛЬНЫЕ гипотезы для симуляции и могут меняться без изменения кода.
Бот задаёт физику (рецепты, сроки, износ, вместимость), но не цены: в каталоге нет ни одной цены в кронах,
кроме комиссий и платы за компанию, которые лежат в настройках.
"""

from dataclasses import dataclass, field

# --- Ресурсы -----------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Resource:
    code: str
    name: str
    unit: str = "ед."


RESOURCES: dict[str, Resource] = {
    r.code: r
    for r in [
        Resource("ore", "Железная руда", "т"),
        Resource("coal", "Уголь", "т"),
        Resource("oil", "Нефть", "бочка"),
        Resource("steel", "Сталь", "т"),
        Resource("diesel", "Дизель", "бочка"),
        Resource("parts", "Запчасти", "компл."),
    ]
}
BASE_RESOURCES = ("ore", "coal", "oil")

# --- Предметы (уникальные экземпляры) ----------------------------------------------------------------

KIND_EQUIPMENT = "equipment"
KIND_MODULE = "module"
KIND_VEHICLE = "vehicle"
KIND_PREMIUM = "premium"


@dataclass(frozen=True)
class ItemDef:
    code: str
    name: str
    kind: str
    max_durability: int = 0
    portable: bool = False  # можно унести пешком
    facility: str | None = None  # тип установки: workshop/smelter/refinery
    mine: dict[str, int] = field(default_factory=dict)  # ресурс -> выход за цикл добычи
    mine_minutes: int = 0
    mine_fuel: int = 0  # дизель за цикл
    mine_wear: int = 0
    stats: dict[str, int] = field(default_factory=dict)  # характеристики модулей
    tradable: bool = True
    description: str = ""


ITEMS: dict[str, ItemDef] = {
    d.code: d
    for d in [
        # Ручной инструмент
        ItemDef("pick", "Кирка", KIND_EQUIPMENT, 60, portable=True,
                mine={"ore": 6, "coal": 6}, mine_minutes=10, mine_wear=1,
                description="Ручная добыча руды и угля."),
        ItemDef("hand_pump", "Ручной насос", KIND_EQUIPMENT, 60, portable=True,
                mine={"oil": 5}, mine_minutes=10, mine_wear=1,
                description="Ручная откачка нефти."),
        # Механизированная добыча
        ItemDef("drill", "Буровая установка", KIND_EQUIPMENT, 100,
                mine={"ore": 10, "coal": 10}, mine_minutes=5, mine_fuel=2, mine_wear=1,
                description="Механизированная добыча руды и угля. Жрёт дизель."),
        ItemDef("oil_rig", "Нефтекачалка", KIND_EQUIPMENT, 100,
                mine={"oil": 8}, mine_minutes=5, mine_fuel=1, mine_wear=1,
                description="Механизированная добыча нефти."),
        # Производственные установки
        ItemDef("workshop", "Мастерская", KIND_EQUIPMENT, 150, facility="workshop",
                description="Запчасти, станки, модули грузовиков, ремонт техники."),
        ItemDef("smelter", "Плавильня", KIND_EQUIPMENT, 100, facility="smelter",
                description="Руда и уголь в сталь."),
        ItemDef("refinery", "НПЗ", KIND_EQUIPMENT, 100, facility="refinery",
                description="Нефть в дизель."),
        # Модули грузовика
        ItemDef("chassis", "Шасси ШР-1", KIND_MODULE, stats={"slot": 0, "durability": 120}),
        ItemDef("engine_d4", "Двигатель Д-4", KIND_MODULE,
                stats={"slot": 1, "speed": 35, "payload": 25, "fuel100": 3}, description="Экономичный."),
        ItemDef("engine_d8", "Двигатель Д-8", KIND_MODULE,
                stats={"slot": 1, "speed": 45, "payload": 40, "fuel100": 5}, description="Сбалансированный."),
        ItemDef("engine_d12", "Двигатель Д-12", KIND_MODULE,
                stats={"slot": 1, "speed": 55, "payload": 60, "fuel100": 8}, description="Мощный."),
        ItemDef("tank", "Топливный бак Б-12", KIND_MODULE, stats={"slot": 2, "tank": 12}),
        ItemDef("body_cargo", "Кузов грузовой", KIND_MODULE,
                stats={"slot": 3, "capacity": 40, "fuel100": 1, "speed": 0, "durability": 0}),
        ItemDef("body_light", "Кузов облегчённый", KIND_MODULE,
                stats={"slot": 3, "capacity": 25, "fuel100": 0, "speed": 5, "durability": -20}),
        ItemDef("body_armored", "Кузов бронированный", KIND_MODULE,
                stats={"slot": 3, "capacity": 30, "fuel100": 3, "speed": -5, "durability": 80}),
        # Транспорт
        ItemDef("truck", "Грузовик", KIND_VEHICLE, description="Модульный грузовик: шасси, двигатель, бак, кузов."),
        # Премиальные (только косметика и коллекции, без бонусов)
        ItemDef("engineer_watch", "Часы инженера", KIND_PREMIUM, portable=True,
                description="Коллекционные латунные часы с серийным номером. Без игровых бонусов."),
        ItemDef("paint_black_brass", "Окраска «Чёрная латунь»", KIND_PREMIUM, portable=True,
                description="Косметическая окраска грузовика. Без бонусов."),
        ItemDef("syndicate_crest", "Герб синдиката", KIND_PREMIUM, portable=True,
                description="Косметический герб профиля или компании. Без бонусов."),
    ]
}

MODULE_SLOTS = {0: "шасси", 1: "двигатель", 2: "бак", 3: "кузов"}

# --- Рецепты -----------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Recipe:
    code: str
    name: str
    facility: str | None  # None — ручная работа без установки
    minutes: int
    inputs: dict[str, int] = field(default_factory=dict)  # ресурсы
    outputs: dict[str, int] = field(default_factory=dict)  # ресурсы
    output_item: str | None = None  # создаёт экземпляр предмета
    item_inputs: tuple[str, ...] = ()  # потребляет экземпляры предметов (по коду)
    wear: int = 1  # износ установки за запуск
    max_runs: int = 10


RECIPES: dict[str, Recipe] = {
    r.code: r
    for r in [
        # Ручные (кустарные) рецепты — гарантированный путь без оборудования, медленно и с потерями.
        Recipe("forge_steel", "Кустарная плавка", None, 10, {"ore": 4, "coal": 3}, {"steel": 1}, wear=0),
        Recipe("hand_parts", "Ручная выточка запчастей", None, 10, {"steel": 3}, {"parts": 1}, wear=0),
        Recipe("hand_distill", "Кустарная перегонка", None, 10, {"oil": 4}, {"diesel": 1}, wear=0),
        Recipe("craft_pick", "Выковать кирку", None, 5, {"steel": 2}, output_item="pick", wear=0, max_runs=1),
        Recipe("craft_pump", "Собрать ручной насос", None, 5, {"steel": 3}, output_item="hand_pump", wear=0, max_runs=1),
        Recipe("build_workshop", "Построить мастерскую", None, 30, {"steel": 12}, output_item="workshop", wear=0, max_runs=1),
        # Установки
        Recipe("smelt_steel", "Плавка стали", "smelter", 5, {"ore": 3, "coal": 2}, {"steel": 2}),
        Recipe("refine_diesel", "Перегонка нефти", "refinery", 5, {"oil": 3}, {"diesel": 2}),
        Recipe("make_parts", "Изготовить запчасти", "workshop", 5, {"steel": 2}, {"parts": 1}),
        Recipe("build_smelter", "Собрать плавильню", "workshop", 20, {"steel": 10, "parts": 2}, output_item="smelter", max_runs=1),
        Recipe("build_refinery", "Собрать НПЗ", "workshop", 45, {"steel": 20, "parts": 5}, output_item="refinery", max_runs=1),
        Recipe("build_drill", "Собрать буровую", "workshop", 30, {"steel": 15, "parts": 4}, output_item="drill", max_runs=1),
        Recipe("build_oil_rig", "Собрать нефтекачалку", "workshop", 30, {"steel": 12, "parts": 4}, output_item="oil_rig", max_runs=1),
        Recipe("build_workshop_w", "Собрать мастерскую", "workshop", 20, {"steel": 10, "parts": 1}, output_item="workshop", max_runs=1),
        # Модули грузовика
        Recipe("build_chassis", "Шасси ШР-1", "workshop", 20, {"steel": 8, "parts": 2}, output_item="chassis", max_runs=1),
        Recipe("build_engine_d4", "Двигатель Д-4", "workshop", 20, {"steel": 4, "parts": 3}, output_item="engine_d4", max_runs=1),
        Recipe("build_engine_d8", "Двигатель Д-8", "workshop", 25, {"steel": 6, "parts": 5}, output_item="engine_d8", max_runs=1),
        Recipe("build_engine_d12", "Двигатель Д-12", "workshop", 30, {"steel": 9, "parts": 8}, output_item="engine_d12", max_runs=1),
        Recipe("build_tank", "Топливный бак", "workshop", 10, {"steel": 3, "parts": 1}, output_item="tank", max_runs=1),
        Recipe("build_body_cargo", "Кузов грузовой", "workshop", 15, {"steel": 6, "parts": 1}, output_item="body_cargo", max_runs=1),
        Recipe("build_body_light", "Кузов облегчённый", "workshop", 15, {"steel": 4, "parts": 1}, output_item="body_light", max_runs=1),
        Recipe("build_body_armored", "Кузов бронированный", "workshop", 25, {"steel": 12, "parts": 3}, output_item="body_armored", max_runs=1),
        # Сборка грузовика из четырёх модулей
        Recipe("assemble_truck", "Сборка грузовика", "workshop", 15, {"parts": 2}, output_item="truck",
               item_inputs=("chassis", "engine", "tank", "body"), max_runs=1),
    ]
}

# Ремонт: (сырьё на один «шаг», восстановленная прочность за шаг, минуты на шаг, нужна ли мастерская)
@dataclass(frozen=True)
class RepairRule:
    inputs: dict[str, int]
    restore: int
    minutes: int
    needs_workshop: bool


REPAIR: dict[str, RepairRule] = {
    "pick": RepairRule({"steel": 1}, 60, 2, False),
    "hand_pump": RepairRule({"steel": 1}, 60, 2, False),
    "drill": RepairRule({"parts": 2}, 50, 10, True),
    "oil_rig": RepairRule({"parts": 2}, 50, 10, True),
    "smelter": RepairRule({"parts": 2}, 50, 10, True),
    "refinery": RepairRule({"parts": 2}, 50, 10, True),
    "workshop": RepairRule({"parts": 2}, 75, 10, False),  # мастерская чинит сама себя
    "truck": RepairRule({"parts": 1}, 20, 5, True),
}

# --- Ручная добыча без инструмента -------------------------------------------------------------------

BARE_HANDS_YIELD = {"ore": 2, "coal": 2, "oil": 1}
MANUAL_SHIFT_MINUTES = 10

# --- Мир ---------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Location:
    code: str
    name: str
    description: str


LOCATIONS: dict[str, Location] = {
    loc.code: loc
    for loc in [
        Location("rust", "Ржавая Падь", "Рудничный посёлок: железо и уголь, вечный смог."),
        Location("kotlo", "Котлоград", "Столичный узел: биржа, депо, конторы синдикатов."),
        Location("mazut", "Мазутный Яр", "Нефтяные поля и сланец; дороги в мазуте."),
    ]
}
START_LOCATION = "rust"


@dataclass(frozen=True)
class DepositDef:
    code: str
    location: str
    resource: str
    name: str
    max_stock: int
    regen_per_hour: int


DEPOSITS: list[DepositDef] = [
    DepositDef("rust_north", "rust", "ore", "Северная жила", 5000, 60),
    DepositDef("rust_red", "rust", "ore", "Красный карьер", 3000, 40),
    DepositDef("rust_coal3", "rust", "coal", "Угольный разрез №3", 4000, 50),
    DepositDef("mazut_black", "mazut", "oil", "Чёрная скважина", 5000, 60),
    DepositDef("mazut_lake", "mazut", "oil", "Мазутное озеро", 2000, 30),
    DepositDef("mazut_shale", "mazut", "coal", "Сланцевый пласт", 1500, 20),
]

# Маршруты: расстояние в км (симметричны). Схема допускает будущие ж/д-ветки и караваны.
ROUTES: dict[frozenset, int] = {
    frozenset(("rust", "kotlo")): 60,
    frozenset(("kotlo", "mazut")): 80,
    frozenset(("rust", "mazut")): 120,
}

FOOT_SPEED_KMH = 5
FOOT_CAPACITY = 10  # единиц ресурсов пешком
TRUCK_KM_PER_WEAR = 20  # 1 единица износа на каждые 20 км


def route_km(a: str, b: str) -> int | None:
    return ROUTES.get(frozenset((a, b)))


def resource_name(code: str) -> str:
    return RESOURCES[code].name if code in RESOURCES else code


def item_name(code: str) -> str:
    return ITEMS[code].name if code in ITEMS else code


def recipes_for_facility(facility: str | None) -> list[Recipe]:
    return [r for r in RECIPES.values() if r.facility == facility]


def module_slot(def_code: str) -> int | None:
    d = ITEMS.get(def_code)
    if d is None or d.kind != KIND_MODULE:
        return None
    return d.stats["slot"]


SLOT_BY_NAME = {"chassis": 0, "engine": 1, "tank": 2, "body": 3}
