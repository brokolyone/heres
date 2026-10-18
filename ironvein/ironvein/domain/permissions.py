from enum import IntFlag


class Perm(IntFlag):
    INVITE = 1        # приглашать в компанию
    WITHDRAW = 2      # выводить деньги: выплаты, переводы с корпоративного счёта
    TRADE = 4         # выставлять/исполнять рыночные заявки
    PRODUCE = 8       # добыча и производство
    TRANSPORT = 16    # рейсы
    EQUIPMENT = 32    # ремонт, сборка, передача оборудования
    CONTRACTS = 64    # создавать/принимать/исполнять контракты
    MEMBERS = 128     # исключать участников, менять права


ALL = Perm(255)
ROLE_DEFAULTS = {
    "owner": ALL,
    "manager": Perm.INVITE | Perm.TRADE | Perm.PRODUCE | Perm.TRANSPORT | Perm.EQUIPMENT | Perm.CONTRACTS,
    "employee": Perm.PRODUCE | Perm.TRANSPORT,
}
PERM_RU = {
    Perm.INVITE: "приглашения", Perm.WITHDRAW: "вывод денег", Perm.TRADE: "рынок", Perm.PRODUCE: "производство",
    Perm.TRANSPORT: "перевозки", Perm.EQUIPMENT: "оборудование", Perm.CONTRACTS: "контракты",
    Perm.MEMBERS: "управление составом",
}
ROLE_RU = {"owner": "владелец", "manager": "управляющий", "employee": "сотрудник"}
