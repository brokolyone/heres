"""Стартовый премиальный каталог (Telegram Stars). Цены предварительные. Только косметика и коллекции."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ProductDef:
    code: str
    item_def: str
    title: str
    description: str
    price_stars: int
    edition_limit: int | None


PRODUCTS = [
    ProductDef("engineer_watch", "engineer_watch", "Часы инженера",
               "Коллекционные латунные часы с уникальным серийным номером. Тираж 100. Без игровых бонусов. "
               "Можно перепродать на рынке за кроны.", 100, 100),
    ProductDef("paint_black_brass", "paint_black_brass", "Окраска «Чёрная латунь»",
               "Косметическая окраска грузовика. Без бонусов. Перепродаётся.", 75, None),
    ProductDef("syndicate_crest", "syndicate_crest", "Герб синдиката",
               "Косметический герб профиля или компании. Без бонусов. Перепродаётся.", 35, None),
]
