"""Агентный экономический симулятор IronVein.

Полностью отделён от бота и БД: использует только технологический каталог (рецепты, выходы, износ,
маршруты и характеристики грузовика), поэтому показывает, как ведёт себя ЭТА физика экономики.
Цены не задаются: агенты выставляют заявки от своей оценки (трудозатраты + память о сделках),
сделки исполняются в стаканах по локациям, комиссия уничтожается. NPC-поставок нет.

Шаг симуляции = 10 игровых минут (одна ручная смена).
"""

import math
import random
from collections import defaultdict
from dataclasses import dataclass, field

from ironvein.domain.catalog import BARE_HANDS_YIELD, DEPOSITS, FOOT_CAPACITY, FOOT_SPEED_KMH, ITEMS, RECIPES, ROUTES, route_km
from ironvein.domain.money import fee_for
from ironvein.domain.vehicles import trip_fuel, trip_minutes, trip_wear, truck_stats

TICK_MIN = 10
RES = ("ore", "coal", "oil", "steel", "diesel", "parts")
TRUCK = truck_stats(["chassis", "engine_d8", "tank", "body_cargo"])
TRUCK_COST = {"steel": 8 + 6 + 3 + 6, "parts": 2 + 5 + 1 + 1 + 2}  # модули Д-8/грузовой + сборка


def recipe(code):
    return RECIPES[code]


@dataclass
class Order:
    side: str
    agent: "Agent"
    res: str
    loc: str
    price: int
    qty: int
    age: int = 0


@dataclass
class Truck:
    loc: str
    durability: int = TRUCK.max_durability
    busy_until: int = 0
    cargo: dict = field(default_factory=dict)
    dest: str | None = None


@dataclass
class Agent:
    id: int
    home: str
    cash: int
    style: str = "industrialist"  # industrialist | trader | inactive | monopolist | collector
    active: bool = True
    company: int | None = None
    stock: dict = field(default_factory=lambda: defaultdict(int))  # (loc, res) -> qty
    equip: dict = field(default_factory=lambda: defaultdict(list))  # code -> [durability...] (в home)
    trucks: list = field(default_factory=list)
    premium: int = 0
    first_steel: int | None = None
    first_workshop: int | None = None
    adj: dict = field(default_factory=lambda: defaultdict(lambda: 1.0))  # (side, res, loc) -> множитель цены
    walk_until: int = 0
    walk: tuple | None = None  # (dest, res, qty, back_home)

    def has(self, res, q, loc=None):
        return self.stock[(loc or self.home, res)] >= q

    def take(self, res, q, loc=None):
        k = (loc or self.home, res)
        assert self.stock[k] >= q, (k, q)
        self.stock[k] -= q

    def add(self, res, q, loc=None):
        self.stock[(loc or self.home, res)] += q

    def best_tool(self, code, wear=1):
        lst = self.equip.get(code) or []
        for i, d in enumerate(lst):
            if d >= wear:
                return i
        return None


@dataclass
class Config:
    players: int = 100
    ticks: int = 6 * 24 * 3  # трое суток
    seed: int = 7
    starter_cash: int = 1000
    fee_bps: int = 200
    inactive_share: float = 0.1
    trader_share: float = 0.1
    deposit_scale: dict = field(default_factory=dict)  # resource -> множитель запаса и регенерации
    crisis_until: int = 0  # до этого шага действуют кризисные модификаторы
    no_trucks: bool = False
    workshops_broken: bool = False
    monopolist: bool = False
    company_size: int = 0
    collectors: int = 0
    premium_items: int = 0
    regen_mult: float = 1.0  # множитель регенерации месторождений (для проверки предлагаемых правок каталога)
    labor_value: int = 20  # субъективная ценность смены для оценки товаров агентами (не цена бота)


class Sim:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.rnd = random.Random(cfg.seed)
        self.t = 0
        self.emitted = 0
        self.burned = 0
        self.deposits = {}
        for d in DEPOSITS:
            scale = cfg.deposit_scale.get(d.resource, 1.0) if cfg.crisis_until else 1.0
            self.deposits[d.code] = {"loc": d.location, "res": d.resource, "stock": int(d.max_stock * scale),
                                     "max": d.max_stock, "regen": d.regen_per_hour * cfg.regen_mult, "acc": 0.0,
                                     "scale": scale}
        self.book: dict[tuple, list[Order]] = defaultdict(list)
        self.last: dict[tuple, int] = {}
        self.trades = defaultdict(lambda: [0, 0])  # (res, loc) -> [qty, gross]
        self.produced = defaultdict(int)
        self.fuel_used = 0
        self.shipments = 0
        self.history = []
        self.agents: list[Agent] = []
        homes = ["rust"] * 5 + ["mazut"] * 3 + ["kotlo"] * 2
        for i in range(cfg.players):
            a = Agent(i, homes[i % len(homes)], 0)
            self._emit(a, cfg.starter_cash)
            a.equip["pick"].append(ITEMS["pick"].max_durability)
            r = self.rnd.random()
            if r < cfg.inactive_share:
                a.style, a.active = "inactive", False
            elif r < cfg.inactive_share + cfg.trader_share or a.home == "kotlo":
                a.style = "trader"
            self.agents.append(a)
        if cfg.monopolist and self.agents:
            m = self.agents[0]
            m.style, m.active, m.home = "monopolist", True, "rust"
            self._emit(m, cfg.starter_cash * 20)  # учтённо: эмиссия как у 20 стартов, моделирует слияние капиталов
            for code in ("workshop", "smelter", "smelter", "smelter"):
                m.equip[code].append(ITEMS[code].max_durability)
        for i in range(min(cfg.company_size, cfg.players)):
            self.agents[i].company = 1
        for i in range(min(cfg.collectors, cfg.players)):
            self.agents[-1 - i].style = "collector"
        for i in range(cfg.premium_items):
            self.agents[(i * 7) % cfg.players].premium += 1  # куплены за Stars: кроны не создаются

    # --- деньги ---------------------------------------------------------------------------------------

    def _emit(self, a: Agent, amount: int):
        a.cash += amount
        self.emitted += amount

    def money_ok(self) -> bool:
        held = sum(o.price * o.qty for orders in self.book.values() for o in orders if o.side == "bid")
        return sum(a.cash for a in self.agents) + held == self.emitted - self.burned

    # --- оценка ---------------------------------------------------------------------------------------

    def best(self, side: str, res: str, loc: str) -> int | None:
        prices = [o.price for o in self.book.get((res, loc), ()) if o.side == side and o.qty > 0]
        if not prices:
            return None
        return max(prices) if side == "bid" else min(prices)

    def value(self, res: str, loc: str) -> int:
        bid, ask = self.best("bid", res, loc), self.best("ask", res, loc)
        if (res, loc) in self.last:
            v = self.last[(res, loc)]
            if bid and bid > v:
                return bid  # неудовлетворённый спрос поднимает оценку
            return v
        if bid and ask:
            return (bid + ask) // 2
        if bid or ask:
            return bid or ask
        others = [p for (r, _), p in self.last.items() if r == res]
        if others:
            return int(sum(others) / len(others))
        w = self.cfg.labor_value
        base = {"ore": w / 6, "coal": w / 6, "oil": w / 5}
        base["steel"] = 4 * base["ore"] + 3 * base["coal"] + w
        base["diesel"] = 4 * base["oil"] + w
        base["parts"] = 3 * base["steel"] + w
        return max(1, int(base[res]))

    # --- рынок ----------------------------------------------------------------------------------------

    def post(self, a: Agent, side: str, res: str, loc: str, price: int, qty: int):
        price, qty = max(1, int(price)), int(qty)
        if qty <= 0:
            return
        if any(o.agent is a and o.side == side for o in self.book.get((res, loc), ())):
            return  # у агента уже висит такая заявка
        price = max(1, int(price * a.adj[(side, res, loc)]))
        if side == "bid":
            qty = min(qty, a.cash // price)
            if qty <= 0:
                return
            a.cash -= price * qty
        else:
            qty = min(qty, a.stock[(loc, res)])
            if qty <= 0:
                return
            a.stock[(loc, res)] -= qty
        o = Order(side, a, res, loc, price, qty)
        self._match(o)
        if o.qty > 0:
            self.book[(res, loc)].append(o)

    def _match(self, o: Order):
        book = self.book[(o.res, o.loc)]
        opp = sorted([x for x in book if x.side != o.side and x.agent is not o.agent],
                     key=lambda x: x.price if o.side == "bid" else -x.price)
        for m in opp:
            if o.qty == 0:
                break
            if (o.side == "bid" and m.price > o.price) or (o.side == "ask" and m.price < o.price):
                break
            q = min(o.qty, m.qty)
            price = m.price
            buyer, seller = (o.agent, m.agent) if o.side == "bid" else (m.agent, o.agent)
            gross = price * q
            fee = fee_for(gross, self.cfg.fee_bps)
            if o.side == "bid":
                o.agent.cash += (o.price - price) * q  # возврат разницы резерва
            seller.cash += gross - fee
            self.burned += fee
            buyer.stock[(o.loc, o.res)] += q
            o.qty -= q
            m.qty -= q
            self.last[(o.res, o.loc)] = price
            for ag, sd in ((buyer, "bid"), (seller, "ask")):
                ag.adj[(sd, o.res, o.loc)] = 1.0 + (ag.adj[(sd, o.res, o.loc)] - 1.0) * 0.5
            self.trades[(o.res, o.loc)][0] += q
            self.trades[(o.res, o.loc)][1] += gross
        self.book[(o.res, o.loc)] = [x for x in book if x.qty > 0]

    def age_orders(self):
        for key, orders in self.book.items():
            keep = []
            for o in orders:
                o.age += 1
                if o.age > 18:  # заявка висит 3 часа — агент снимает её и вернётся с новой ценой
                    k = (o.side, o.res, o.loc)
                    if o.side == "bid":
                        o.agent.cash += o.price * o.qty
                        o.agent.adj[k] = min(o.agent.adj[k] * 1.15, 50.0)  # не купил — готов платить больше
                    else:
                        o.agent.stock[(o.loc, o.res)] += o.qty
                        o.agent.adj[k] = max(o.agent.adj[k] * 0.92, 0.3)  # не продал — уступает
                else:
                    keep.append(o)
            self.book[key] = keep

    # --- физика ---------------------------------------------------------------------------------------

    def mine(self, a: Agent, res: str, amount: int) -> int:
        for d in self.deposits.values():
            if d["loc"] == a.home and d["res"] == res and d["stock"] > 0:
                got = min(amount, d["stock"])
                d["stock"] -= got
                a.add(res, got)
                self.produced[f"mine_{res}"] += got
                return got
        return 0

    def regen(self):
        for d in self.deposits.values():
            scale = d["scale"] if self.t < self.cfg.crisis_until else 1.0
            d["acc"] += d["regen"] * scale * TICK_MIN / 60
            whole = int(d["acc"])
            d["acc"] -= whole
            cap = int(d["max"] * scale) if self.t < self.cfg.crisis_until else d["max"]
            d["stock"] = min(cap, d["stock"] + whole) if d["stock"] < cap else d["stock"]

    def craft(self, a: Agent, code: str, runs: int = 1) -> bool:
        r = recipe(code)
        if r.facility:
            idx = a.best_tool(r.facility, r.wear * runs)
            if idx is None:
                return False
        if not all(a.has(k, v * runs) for k, v in r.inputs.items()):
            return False
        for k, v in r.inputs.items():
            a.take(k, v * runs)
        for k, v in r.outputs.items():
            a.add(k, v * runs)
            self.produced[k] += v * runs
        if r.facility:
            a.equip[r.facility][idx] -= r.wear * runs
        if r.output_item:
            a.equip[r.output_item].append(ITEMS[r.output_item].max_durability)
            self.produced[r.output_item] += 1
        return True

    def repair(self, a: Agent):
        for code, lst in a.equip.items():
            for i, d in enumerate(lst):
                mx = ITEMS[code].max_durability
                if d < mx // 3:
                    if code in ("pick", "hand_pump") and a.has("steel", 1):
                        a.take("steel", 1)
                        lst[i] = mx
                    elif code != "pick" and a.has("parts", 2) and (code == "workshop" or a.best_tool("workshop")
                                                                    is not None):
                        a.take("parts", 2)
                        lst[i] = min(mx, d + 50)
                        if code != "workshop":
                            a.equip["workshop"][a.best_tool("workshop")] -= 1

    # --- поведение ------------------------------------------------------------------------------------

    def act(self, a: Agent):
        if not a.active:
            return
        if a.walk_until > self.t:
            return  # руки заняты переходом
        if a.walk:
            dest, res, q, back = a.walk
            a.walk = None
            if q:
                a.add(res, q, dest)
                self.post(a, "ask", res, dest, self.best("bid", res, dest) or self.value(res, dest), q)
                self.shipments += 1
            if back:
                km = route_km(dest, a.home)
                a.walk, a.walk_until = (a.home, res, 0, False), self.t + math.ceil(km * 60 / FOOT_SPEED_KMH / TICK_MIN)
                return
        if self.maybe_walk(a):
            return
        if a.style == "collector":
            return self.act_collector(a)
        if a.home != "kotlo":
            self.manual_labor(a)
            self.run_machines(a)
            self.build(a)
            self.repair(a)
            self.trade_local(a)
        if a.style in ("trader", "monopolist") or a.trucks:
            self.haul(a)
        if a.style == "monopolist":
            self.act_monopolist(a)
        if a.first_steel is None and any(a.stock[(loc, "steel")] for loc in ("rust", "mazut", "kotlo")):
            a.first_steel = self.t
        if a.first_workshop is None and a.equip.get("workshop"):
            a.first_workshop = self.t

    def maybe_walk(self, a: Agent) -> bool:
        """Пеший перенос (до 10 ед.), если цена в другом месте окупает потерянные смены туда и обратно."""
        for res in ("diesel", "steel", "parts"):
            have = a.stock[(a.home, res)]
            if have < FOOT_CAPACITY:
                continue
            for dest in ("rust", "mazut", "kotlo"):
                km = route_km(a.home, dest)
                bid = self.best("bid", res, dest)
                if not km or not bid:
                    continue
                ticks = math.ceil(km * 60 / FOOT_SPEED_KMH / TICK_MIN)
                gain = (bid - self.value(res, a.home)) * FOOT_CAPACITY - 2 * ticks * self.cfg.labor_value
                if gain > 0:
                    a.take(res, FOOT_CAPACITY)
                    a.walk, a.walk_until = (dest, res, FOOT_CAPACITY, True), self.t + ticks
                    return True
        return False

    def manual_labor(self, a: Agent):
        """Одна смена рабочих рук за шаг: либо кустарный крафт, либо добыча (инструментом или руками)."""
        if not a.equip.get("smelter") and a.has("ore", 4) and a.has("coal", 3) and self.craft(a, "forge_steel"):
            return
        if a.home == "mazut" and not a.equip.get("refinery") and a.has("oil", 12) and self.craft(a, "hand_distill"):
            return
        needs_fuel = a.home == "rust" and a.trucks and not a.has("diesel", 8) and (self.t + a.id) % 3 == 0
        if needs_fuel and a.has("oil", 4) and self.craft(a, "hand_distill"):
            return
        if a.home == "rust" and needs_fuel:
            res = "oil"  # Ржавый колодец: топливо для первого рейса
        elif a.home == "rust":
            res = "ore" if a.stock[(a.home, "ore")] * 3 <= a.stock[(a.home, "coal")] * 4 else "coal"
        else:
            res = "oil"
        tool = "pick" if res in ("ore", "coal") else "hand_pump"
        idx = a.best_tool(tool)
        if idx is not None:
            if self.mine(a, res, ITEMS[tool].mine[res]):
                a.equip[tool][idx] -= 1
        elif tool == "hand_pump" and a.has("steel", 3):
            self.craft(a, "craft_pump")
        elif tool == "pick" and a.has("steel", 2):
            self.craft(a, "craft_pick")
        else:
            self.mine(a, res, BARE_HANDS_YIELD[res])

    def run_machines(self, a: Agent):
        broken = self.cfg.workshops_broken and self.t < self.cfg.crisis_until
        for _ in range(2):  # 2 цикла по 5 минут на шаг
            if a.equip.get("smelter"):
                self.craft(a, "smelt_steel")
            if a.equip.get("refinery"):
                self.craft(a, "refine_diesel")
            if a.equip.get("workshop") and not broken and a.stock[(a.home, "parts")] < 12 and a.stock[(a.home, "steel")] > 14:
                self.craft(a, "make_parts")
            for code in ("drill", "oil_rig"):
                d = ITEMS[code]
                for i, dur in enumerate(a.equip.get(code, [])):
                    res = next(iter(d.mine)) if a.home == "rust" else "oil"
                    reserve = 8 if a.trucks else 0  # резерв топлива на рейс машины не трогают
                    if res not in d.mine or dur < 1 or not a.has("diesel", d.mine_fuel + reserve):
                        continue
                    if self.mine(a, res, d.mine[res]):
                        a.take("diesel", d.mine_fuel)
                        self.fuel_used += d.mine_fuel
                        a.equip[code][i] -= 1

    def build(self, a: Agent):
        broken = self.cfg.workshops_broken and self.t < self.cfg.crisis_until
        if not a.equip.get("workshop"):
            if a.has("steel", 12):
                self.craft(a, "build_workshop")
            return
        if broken:
            return
        if not a.has("parts", 5) and a.has("steel", 6):
            self.craft(a, "make_parts")
        first = "build_smelter" if a.home == "rust" else "build_refinery"
        if not a.equip.get(recipe(first).output_item):
            self.craft(a, first)
            return
        # Без грузовика буровая в Ржавой Пади бесполезна: дизель делают в Мазутном Яре.
        if not a.trucks and not self.cfg.no_trucks:
            if all(a.has(k, v) for k, v in TRUCK_COST.items()):
                for k, v in TRUCK_COST.items():
                    a.take(k, v)
                a.trucks.append(Truck(a.home))
                self.produced["truck"] += 1
            return
        second = "build_drill" if a.home == "rust" else "build_oil_rig"
        if not a.equip.get(recipe(second).output_item):
            self.craft(a, second)

    def trade_local(self, a: Agent):
        loc = a.home
        reserve = {"ore": 12, "coal": 9, "oil": 16, "steel": 20 if a.equip.get("workshop") else 12, "diesel": 6,
                   "parts": 6}
        needs = {"rust": {"diesel": 6, "parts": 4}, "mazut": {"steel": 15, "parts": 4, "coal": 6}}.get(loc, {})
        for res in RES:
            have = a.stock[(loc, res)]
            v = self.value(res, loc)
            if have > reserve[res]:
                self.post(a, "ask", res, loc, v * self.rnd.uniform(0.95, 1.15), have - reserve[res])
            want = needs.get(res, 0) - have
            if want > 0 and a.cash > v * want:
                self.post(a, "bid", res, loc, v * self.rnd.uniform(0.9, 1.1), want)

    def haul(self, a: Agent):
        if not a.trucks:
            if a.style == "trader" and not self.cfg.no_trucks and a.cash > 2500 and self.t % 36 == 0:
                # Трейдер покупает материалы на рынке и заказывает грузовик у производителей:
                # моделируем как покупку стали и запчастей там, где они продаются.
                for res, q in TRUCK_COST.items():
                    self.post(a, "bid", res, "rust", self.value(res, "rust") * 1.2, q)
                if all(a.stock[("rust", k)] >= v for k, v in TRUCK_COST.items()):
                    for k, v in TRUCK_COST.items():
                        a.take(k, v, "rust")
                    a.trucks.append(Truck("rust"))
                    self.produced["truck"] += 1
            return
        for tr in a.trucks:
            if tr.busy_until > self.t:
                continue
            if tr.dest:  # прибытие
                for res, q in tr.cargo.items():
                    a.add(res, q, tr.dest)
                    self.post(a, "ask", res, tr.dest, self.value(res, tr.dest), q)
                tr.loc, tr.dest, tr.cargo = tr.dest, None, {}
            best = None
            for res in RES:
                buy_at = self.best("ask", res, tr.loc) or self.last.get((res, tr.loc))
                if a.stock[(tr.loc, res)] >= TRUCK.payload // 2:
                    buy_at = min(buy_at or 10**9, self.value(res, tr.loc))  # свой товар: альтернативная стоимость
                for dest in ("rust", "mazut", "kotlo"):
                    km = route_km(tr.loc, dest)
                    sell_at = self.best("bid", res, dest) or self.last.get((res, dest))
                    if not km or not sell_at or not buy_at:
                        continue  # везём только туда, где есть реальный спрос, и то, что реально продают
                    fuel_cost = trip_fuel(TRUCK, km) * self.value("diesel", tr.loc)
                    gain = (sell_at - buy_at) * TRUCK.payload - fuel_cost
                    if gain > 0 and (best is None or gain > best[0]):
                        best = (gain, res, dest, km, buy_at, sell_at)
            if best is None:
                # Порожний перегон туда, где дёшево продают то, что дорого покупают в другом месте.
                for dest in ("rust", "mazut", "kotlo"):
                    km = route_km(tr.loc, dest)
                    if not km:
                        continue
                    for res in RES:
                        ask = self.best("ask", res, dest)
                        bids = [self.best("bid", res, x) for x in ("rust", "mazut", "kotlo") if x != dest]
                        bid = max([b for b in bids if b] or [0])
                        fuel_cost = 2 * trip_fuel(TRUCK, km) * self.value("diesel", tr.loc)
                        gain = (bid - ask) * TRUCK.payload - fuel_cost if ask else 0
                        if gain > 0 and (best is None or gain > best[0]):
                            best = (gain, None, dest, km, 0, 0)
            if best is None:
                continue
            _, res, dest, km, buy_at, sell_at = best
            fuel = trip_fuel(TRUCK, km)
            if not a.has("diesel", fuel, tr.loc):
                self.post(a, "bid", "diesel", tr.loc, self.value("diesel", tr.loc) * 1.1, fuel * 2)
                if not a.has("diesel", fuel, tr.loc):
                    continue
            q = 0
            if res is not None:
                if a.stock[(tr.loc, res)] < TRUCK.payload:
                    self.post(a, "bid", res, tr.loc, buy_at, TRUCK.payload - a.stock[(tr.loc, res)])
                spare = a.stock[(tr.loc, res)] - (fuel if res == "diesel" else 0)  # топливо не грузим как товар
                q = min(TRUCK.payload, spare)
                if q <= 0:
                    continue
            if tr.durability < trip_wear(km):
                continue
            a.take("diesel", fuel, tr.loc)
            if q:
                a.take(res, q, tr.loc)
            self.fuel_used += fuel
            tr.durability -= trip_wear(km)
            tr.cargo, tr.dest = ({res: q} if q else {}), dest
            tr.busy_until = self.t + math.ceil(trip_minutes(TRUCK.speed_kmh, km) / TICK_MIN)
            self.shipments += 1

    def act_monopolist(self, a: Agent):
        # Скупает всю сталь дешевле своей цены и выставляет её дороже — классическая попытка монополии.
        v = self.value("steel", "rust")
        self.post(a, "bid", "steel", "rust", v * 1.05, 200)
        if a.stock[("rust", "steel")] > 0:
            self.post(a, "ask", "steel", "rust", v * 1.6, a.stock[("rust", "steel")])
        for res in ("ore", "coal"):
            self.post(a, "bid", res, "rust", self.value(res, "rust") * 1.05, 60)

    def act_collector(self, a: Agent):
        # Перепродажа премиальных предметов за кроны: деньги только переходят между игроками.
        sellers = [x for x in self.agents if x.premium > 0 and x is not a and x.active]
        if sellers and a.cash > 500 and self.rnd.random() < 0.05:
            s = self.rnd.choice(sellers)
            price = int(a.cash * 0.3)
            fee = fee_for(price, self.cfg.fee_bps)
            a.cash -= price
            s.cash += price - fee
            self.burned += fee
            s.premium -= 1
            a.premium += 1
            self.trades[("premium", "-")][0] += 1
            self.trades[("premium", "-")][1] += price

    # --- цикл -----------------------------------------------------------------------------------------

    def step(self):
        self.regen()
        order = list(self.agents)
        self.rnd.shuffle(order)
        for a in order:
            self.act(a)
        self.age_orders()
        if self.t % 6 == 0:
            self.history.append(self.snapshot())
        self.t += 1

    def run(self):
        for _ in range(self.cfg.ticks):
            self.step()
            assert self.money_ok(), f"money not conserved at t={self.t}"
            assert all(v >= 0 for a in self.agents for v in a.stock.values()), "negative stock"
        return self.report()

    def wealth(self, a: Agent) -> int:
        inv = sum(q * self.value(res, loc) for (loc, res), q in a.stock.items() if q > 0)
        return a.cash + inv

    def snapshot(self) -> dict:
        return {"t": self.t, "steel": self.produced["steel"], "diesel": self.produced["diesel"],
                "parts": self.produced["parts"],
                "prices": {r: self.last.get((r, "rust")) or self.last.get((r, "mazut")) for r in RES},
                "money": sum(a.cash for a in self.agents), "burned": self.burned}

    def report(self) -> dict:
        ws = sorted(self.wealth(a) for a in self.agents)
        n = len(ws)
        gini = (sum((2 * i - n + 1) * w for i, w in enumerate(ws)) / (n * sum(ws))) if sum(ws) else 0
        firms = defaultdict(int)
        for a in self.agents:
            firms[a.company if a.company else -a.id - 1] += self.wealth(a)
        total = sum(firms.values()) or 1
        top_firm = max(firms.values()) / total
        newbies = [a for a in self.agents if a.style == "industrialist" and a.active]
        steel_t = [a.first_steel for a in newbies if a.first_steel is not None]
        ws_t = [a.first_workshop for a in newbies if a.first_workshop is not None]
        half = len(self.history) // 2

        def halves(key):
            if not half:
                return 0, 0
            return (self.history[half][key] - self.history[0][key], self.history[-1][key] - self.history[half][key])
        early, late = halves("steel")
        vwap = {f"{r}@{l}": g // q for (r, l), (q, g) in self.trades.items() if q}
        return {
            "players": n, "ticks": self.t, "money_conserved": self.money_ok(),
            "emitted": self.emitted, "burned": self.burned, "gini": round(gini, 3), "top_firm_share": round(top_firm, 3),
            "produced": dict(self.produced), "fuel_used": self.fuel_used, "shipments": self.shipments,
            "vwap": vwap, "trade_volume": {f"{r}@{l}": q for (r, l), (q, _) in self.trades.items()},
            "newbie_first_steel_median_h": _median_h(steel_t), "newbie_steel_share": len(steel_t) / max(1, len(newbies)),
            "newbie_first_workshop_median_h": _median_h(ws_t), "newbie_workshop_share": len(ws_t) / max(1, len(newbies)),
            "steel_first_half": early, "steel_second_half": late,
            "halves": {k: halves(k) for k in ("steel", "diesel", "parts")},
            "equipment": {c: sum(len(a.equip.get(c, [])) for a in self.agents)
                          for c in ("workshop", "smelter", "refinery", "drill", "oil_rig")},
            "trucks": sum(len(a.trucks) for a in self.agents),
        }


def _median_h(ts):
    if not ts:
        return None
    s = sorted(ts)
    return round(s[len(s) // 2] * TICK_MIN / 60, 1)


__all__ = ["Sim", "Config", "ROUTES"]
