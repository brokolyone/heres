#!/usr/bin/env python3
"""Прогоняет логику уровня из .gmd без игры.

Это упрощённая модель тех триггеров, которые есть в уровне (Spawn, Toggle,
Alpha, Pickup, Instant Count, Collision, Instant Collision, Event, Move, Stop).
Она ловит ошибки в связях между группами; поведение самой игры она не
заменяет. Запуск: python3 simulate.py <level.gmd> [--swap]
"""
import base64
import gzip
import re
import sys

DT = 1 / 240


def load(path):
    xml = open(path).read()
    data = re.search(r"<k>k4</k><s>(.*?)</s>", xml).group(1)
    raw = gzip.decompress(base64.urlsafe_b64decode(data)).decode()
    objs = []
    for part in raw.split(";")[1:]:
        if not part:
            continue
        kv = part.split(",")
        o = {}
        for i in range(0, len(kv) - 1, 2):
            o[int(kv[i])] = kv[i + 1]
        objs.append(o)
    return objs


def num(o, k, default=0.0):
    return float(o[k]) if k in o else default


def groups(o):
    return [int(g) for g in o.get(57, "").split(".") if g]


class Sim:
    def __init__(self, objs):
        self.objs = objs
        self.t = 0.0
        self.off = set()            # выключенные группы
        self.alpha = {}
        self.items = {}
        self.offset = {}            # сдвиг групп от Move
        self.colors = {}
        self.queue = []             # (время, группа)
        self.moves = []             # активные Move: [trigger, группа, dx, dy, осталось, всего]
        self.monitors = []          # Collision-триггеры: [trigger, было касание]
        self.listeners = []         # Event-триггеры
        self.scale = {}
        self.ended = False
        self.by_group = {}
        for i, o in enumerate(objs):
            for g in groups(o):
                self.by_group.setdefault(g, []).append(o)
        self.blocks = {}
        for o in objs:
            if int(o[1]) == 1816:
                self.blocks[int(o[80])] = o

    # -------- состояние
    def active(self, o):
        return not any(g in self.off for g in groups(o))

    def group_alpha(self, g):
        return self.alpha.get(g, 1.0)

    def visible(self, g):
        objs = self.by_group.get(g, [])
        o = next((o for o in objs if int(o[1]) == 211), None)
        if o is None:
            return False
        a = 1.0
        for gg in groups(o):
            a *= self.group_alpha(gg)
        return a > 0.5

    def rect(self, bid):
        o = self.blocks[bid]
        dx = dy = 0.0
        for g in groups(o):
            ox, oy = self.offset.get(g, (0.0, 0.0))
            dx += ox
            dy += oy
        w, h = num(o, 128, 1) * 30, num(o, 129, 1) * 30
        x, y = num(o, 2) + dx, num(o, 3) + dy
        return x - w / 2, y - h / 2, x + w / 2, y + h / 2

    def touching(self, a, b):
        ax0, ay0, ax1, ay1 = self.rect(a)
        bx0, by0, bx1, by1 = self.rect(b)
        return ax0 < bx1 and bx0 < ax1 and ay0 < by1 and by0 < ay1

    # -------- триггеры
    def spawn(self, g, delay=0.0):
        self.queue.append((self.t + delay, g))

    def run_group(self, g):
        trig = [o for o in self.by_group.get(g, []) if o.get(62) == "1"]
        trig.sort(key=lambda o: num(o, 2))
        active = [o for o in trig if self.active(o)]
        for o in active:
            self.fire(o)

    def fire(self, o):
        oid = int(o[1])
        tgt = int(num(o, 51))
        if oid == 1268:
            self.spawn(tgt, num(o, 63))
        elif oid == 1007:
            self.alpha[tgt] = num(o, 35)
        elif oid == 1049:
            if o.get(56) == "1":
                self.off.discard(tgt)
            else:
                self.off.add(tgt)
        elif oid == 1817:
            item = int(num(o, 80))
            if o.get(139) == "1":
                self.items[item] = num(o, 77)
            else:
                self.items[item] = self.items.get(item, 0) + num(o, 77)
        elif oid == 1811:
            v = self.items.get(int(num(o, 80)), 0)
            want = num(o, 77)
            cmp = int(num(o, 88))
            ok = (v == want) if cmp == 0 else (v > want) if cmp == 1 else (v < want)
            if ok:
                self.off.discard(tgt)
                self.spawn(tgt)
        elif oid == 3609:
            hit = self.touching(int(num(o, 80)), int(num(o, 95)))
            g = tgt if hit else int(num(o, 71))
            if g:
                self.spawn(g)
        elif oid == 1815:
            self.monitors.append([o, self.touching(int(num(o, 80)), int(num(o, 95)))])
        elif oid == 3604:
            self.listeners.append(o)
        elif oid == 901:
            dur = num(o, 10)
            dx, dy = num(o, 28), num(o, 29)
            if dur <= 0:
                ox, oy = self.offset.get(tgt, (0.0, 0.0))
                self.offset[tgt] = (ox + dx, oy + dy)
            else:
                self.moves.append([o, tgt, dx, dy, dur, dur])
        elif oid == 1616:
            self.moves = [m for m in self.moves if tgt not in groups(m[0])]
        elif oid == 899:
            self.colors[int(num(o, 23))] = (int(num(o, 7)), int(num(o, 8)), int(num(o, 9)))
        elif oid == 2067:
            k = num(o, 150)
            if o.get(153) == "1":
                k = 1 / k
            self.scale[tgt] = self.scale.get(tgt, 1.0) * k
        elif oid == 3600:
            self.ended = True

    def press(self, event, player):
        for o in self.listeners:
            if o.get(430) == str(event) and int(num(o, 525)) in (0, player):
                self.spawn(int(num(o, 51)))

    def step(self):
        self.t += DT
        due = sorted([q for q in self.queue if q[0] <= self.t + 1e-9], key=lambda q: q[0])
        self.queue = [q for q in self.queue if q[0] > self.t + 1e-9]
        for _, g in due:
            self.run_group(g)
        for m in self.moves:
            k = min(DT, m[4]) / m[5]
            ox, oy = self.offset.get(m[1], (0.0, 0.0))
            self.offset[m[1]] = (ox + m[2] * k, oy + m[3] * k)
            m[4] -= DT
        self.moves = [m for m in self.moves if m[4] > 0]
        for mon in self.monitors:
            o = mon[0]
            now = self.touching(int(num(o, 80)), int(num(o, 95)))
            if now != mon[1]:
                if (now and o.get(93) != "1") or (not now and o.get(93) == "1"):
                    g = int(num(o, 51))
                    self.off.discard(g)
                    self.spawn(g)
                mon[1] = now

    def wait(self, sec):
        for _ in range(int(round(sec / DT))):
            self.step()


EV_JUMP, EV_LP, EV_LR, EV_RP, EV_RR = 69, 71, 72, 73, 74


def main(path, swap=False):
    sim = Sim(load(path))
    horiz, vert = (1, 2) if swap else (2, 1)
    starter = [o for o in sim.objs if int(o[1]) == 1268 and o.get(62) != "1"]
    assert len(starter) == 1, "должен быть один стартовый Spawn"
    sim.spawn(int(num(starter[0], 51)))
    sim.wait(0.1)
    fails = []

    def check(name, cond):
        print(("ok   " if cond else "FAIL ") + name)
        if not cond:
            fails.append(name)

    # Номера групп и блоков совпадают с build_level.py.
    G_CHECKBOX, G_SPINNER, G_GREEN, G_POPUP, G_FOOTER = 10, 11, 12, 14, 15
    G_SKIP, G_VERIFY, G_SUBDIM, G_ERR_TRY, G_ERR_MORE, G_CURSOR = 16, 17, 18, 19, 20, 22
    G_TICK, G_TILE = 50, 30
    B_CURSOR, B_CHECKBOX, B_BUTTON, B_TILE = 1, 2, 3, 10
    CH_CHECKBOX = 10

    check("старт: окно скрыто", not sim.visible(G_POPUP))
    check("старт: в окне стоит SKIP, а не VERIFY",
          sim.group_alpha(G_SKIP) == 1 and sim.group_alpha(G_VERIFY) == 0)
    check("старт: рамка #444746", sim.colors.get(CH_CHECKBOX) == (68, 71, 70))

    # Движение: «горизонтальный» игрок вправо полсекунды.
    x0 = sim.rect(B_CURSOR)[0]
    sim.press(EV_RP, horiz)
    sim.wait(0.5)
    sim.press(EV_RR, horiz)
    sim.wait(0.2)
    dx = sim.rect(B_CURSOR)[0] - x0
    check(f"→ двигает вправо (сдвиг {dx:.1f})", 70 < dx < 80)
    y0 = sim.rect(B_CURSOR)[1]
    sim.press(EV_RP, vert)
    sim.wait(0.3)
    sim.press(EV_RR, vert)
    sim.wait(0.1)
    check("вправо у второго игрока двигает вверх", sim.rect(B_CURSOR)[1] > y0 + 30)
    sim.press(EV_LP, vert)
    sim.wait(0.3)
    sim.press(EV_LR, vert)
    sim.wait(0.1)
    check("влево у второго игрока двигает вниз", abs(sim.rect(B_CURSOR)[1] - y0) < 3)

    # Упор в левый край: держим долго, курсор должен встать.
    sim.press(EV_LP, horiz)
    sim.wait(5)
    xa = sim.rect(B_CURSOR)[0]
    sim.wait(1)
    check("левая стенка останавливает", abs(sim.rect(B_CURSOR)[0] - xa) < 0.01)
    sim.press(EV_LR, horiz)
    sim.press(EV_LP, horiz)
    sim.wait(0.3)
    check("у стенки повторное ← не двигает", abs(sim.rect(B_CURSOR)[0] - xa) < 0.01)
    sim.press(EV_LR, horiz)
    sim.press(EV_RP, horiz)
    sim.wait(0.2)
    sim.press(EV_RR, horiz)
    sim.wait(0.05)
    check("от стенки вправо едет", sim.rect(B_CURSOR)[0] > xa + 20)

    def goto(bid):
        """Ставим остриё в центр блока (телепорт для тестов клика)."""
        bx0, by0, bx1, by1 = sim.rect(bid)
        cx0, cy0, cx1, cy1 = sim.rect(B_CURSOR)
        ox, oy = sim.offset.get(G_CURSOR, (0, 0))
        sim.offset[G_CURSOR] = (ox + (bx0 + bx1) / 2 - (cx0 + cx1) / 2,
                                oy + (by0 + by1) / 2 - (cy0 + cy1) / 2)
        sim.wait(0.05)

    def click():
        sim.press(EV_JUMP, 1)
        sim.wait(0.3)

    # Наведение.
    goto(B_CHECKBOX)
    sim.wait(0.2)
    check("наведение: рамка #B2B2B2", sim.colors.get(CH_CHECKBOX) == (178, 178, 178))
    goto(B_BUTTON)
    sim.wait(0.2)
    check("уход: рамка снова #444746", sim.colors.get(CH_CHECKBOX) == (68, 71, 70))

    click()
    check("клик мимо окна ничего не открывает", not sim.visible(G_POPUP))
    goto(B_TILE + 1)
    click()
    check("клетки не кликаются до открытия окна", not sim.visible(G_TICK + 1) and sim.items.get(1, 0) == 0)

    goto(B_CHECKBOX)
    click()
    check("после клика: спиннер", sim.visible(G_SPINNER) and not sim.visible(G_CHECKBOX))
    sim.wait(1.0)
    check("через секунду: окно открыто", sim.visible(G_POPUP))
    check("спиннер погас, чекбокс вернулся", not sim.visible(G_SPINNER) and sim.visible(G_CHECKBOX))
    click()
    check("повторный клик по чекбоксу ничего не ломает", sim.visible(G_POPUP) and not sim.visible(G_SPINNER))

    # SKIP без выбора: «Please select all matching images.»
    goto(B_BUTTON)
    click()
    check("SKIP без выбора: ошибка select-more", sim.visible(G_ERR_MORE) and not sim.visible(G_ERR_TRY))
    check("футер уехал вниз на 15", abs(sim.offset.get(G_FOOTER, (0, 0))[1] + 15) < 1e-6)
    click()
    check("второй SKIP: футер не уезжает дальше", abs(sim.offset.get(G_FOOTER, (0, 0))[1] + 15) < 1e-6)

    goto(B_TILE + 1)
    click()
    check("клетка 1 выбрана", sim.visible(G_TICK + 1) and abs(sim.scale.get(G_TILE + 1, 1) - 0.8) < 1e-9)
    check("ошибка спряталась, футер на месте", not sim.visible(G_ERR_MORE) and abs(sim.offset.get(G_FOOTER, (0, 0))[1]) < 1e-6)
    check("кнопка стала VERIFY, подзаголовок бледный", sim.visible(G_VERIFY) and not sim.visible(G_SKIP) and sim.visible(G_SUBDIM))
    click()
    check("повторный клик снимает выбор", not sim.visible(G_TICK + 1) and abs(sim.scale.get(G_TILE + 1, 1) - 1) < 1e-9)
    check("снова SKIP", sim.visible(G_SKIP) and not sim.visible(G_VERIFY))
    check("счётчики вернулись", sim.items.get(1) == 0 and sim.items.get(2) == 6)

    # Неверный ответ: часть правильных + одна лишняя.
    for i in (1, 2, 0):
        goto(B_TILE + i)
        click()
    goto(B_BUTTON)
    click()
    sim.wait(0.3)
    check("неверно: «Please try again.»", sim.visible(G_ERR_TRY))
    check("неверно: все клетки сброшены", not any(sim.visible(G_TICK + i) for i in range(16)))
    check("неверно: окно не закрылось", sim.visible(G_POPUP) and not sim.ended)

    # Почти верно, но не хватает одной клетки (тонкий кусок в верхнем ряду).
    for i in (5, 6, 10, 11, 1):
        goto(B_TILE + i)
        click()
    goto(B_BUTTON)
    click()
    sim.wait(0.3)
    check("без клетки 2 не пускает", sim.visible(G_POPUP) and not sim.ended)

    # Верно.
    for i in (1, 2, 5, 6, 10, 11):
        goto(B_TILE + i)
        click()
    check("6 выбрано", sim.items.get(1) == 6 and sim.items.get(2) == 0)
    goto(B_BUTTON)
    click()
    check("верно: окно закрылось, спиннер", not sim.visible(G_POPUP) and sim.visible(G_SPINNER))
    sim.wait(1.0)
    check("зелёная галочка", sim.visible(G_GREEN) and not sim.visible(G_SPINNER))
    sim.wait(2.0)
    check("уровень пройден (End)", sim.ended)

    print(f"\n{len(fails)} провалов" if fails else "\nвсё прошло")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main(sys.argv[1], "--swap" in sys.argv)
