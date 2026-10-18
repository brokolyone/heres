from sqlalchemy import select

from ironvein.models import Deposit, Item, Stock
from ironvein.repositories.wallets import balances
from ironvein.services import items, stock


async def bal(sm, account_id: int) -> dict[str, int]:
    async with sm() as s:
        return await balances(s, account_id)


async def qty(sm, owner: int, loc: str, res: str, held: bool = False) -> int:
    async with sm() as s:
        st = await s.get(Stock, (owner, loc, res))
        if st is None:
            return 0
        return st.held if held else st.free


async def give(sm, owner: int, loc: str, res: str, q: int):
    """Тестовая выдача ресурсов (журналируется как admin_grant)."""
    async with sm() as s, s.begin():
        await stock.add(s, owner, loc, res, q, "test_grant", check_capacity=False)


async def give_item(sm, owner: int, def_code: str, loc: str | None = "rust", **kw) -> int:
    async with sm() as s, s.begin():
        return (await items.create(s, def_code, owner, loc, "admin", **kw)).id


async def get_item(sm, item_id: int) -> Item:
    async with sm() as s:
        return await s.get(Item, item_id)


async def deposit_id(sm, code: str) -> int:
    async with sm() as s:
        return await s.scalar(select(Deposit.id).where(Deposit.code == code))


async def deposit(sm, code: str) -> Deposit:
    async with sm() as s:
        return await s.scalar(select(Deposit).where(Deposit.code == code))


async def user_items(sm, owner: int, def_code: str | None = None) -> list[Item]:
    async with sm() as s:
        q = select(Item).where(Item.owner_id == owner)
        if def_code:
            q = q.where(Item.def_code == def_code)
        return list((await s.scalars(q.order_by(Item.id))).all())
