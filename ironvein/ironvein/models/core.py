"""Владельцы, деньги, склады, предметы, журналы."""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ironvein.models.base import Base, created_at_col

# Виды счетов-владельцев
ACC_USER = "user"
ACC_COMPANY = "company"
ACC_SYSTEM = "system"

SYS_EMISSION = "system:emission"  # источник: все выпущенные кроны (баланс отрицательный)
SYS_FEES = "system:fees"  # сток: все уничтоженные комиссии и сборы


class Account(Base):
    """Любой владелец активов: игрок, компания или системный счёт."""

    __tablename__ = "accounts"
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(16))
    code: Mapped[str | None] = mapped_column(String(64), unique=True)  # для системных счетов
    name: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = created_at_col()
    __table_args__ = (CheckConstraint("kind in ('user','company','system')", name="kind"),)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), primary_key=True)
    tg_id: Mapped[int] = mapped_column(unique=True)
    username: Mapped[str | None] = mapped_column(String(64))
    display_name: Mapped[str] = mapped_column(String(64))
    acting_account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"))
    starter_granted: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    created_at: Mapped[datetime] = created_at_col()


class Wallet(Base):
    """Кошелёк: main — свободные кроны, hold — зарезервированные (заявки, контракты)."""

    __tablename__ = "wallets"
    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    kind: Mapped[str] = mapped_column(String(8))
    balance: Mapped[int] = mapped_column(default=0, server_default="0")
    allow_negative: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    __table_args__ = (
        UniqueConstraint("account_id", "kind", name="uq_wallets_account_kind"),
        CheckConstraint("kind in ('main','hold')", name="kind"),
        CheckConstraint("allow_negative OR balance >= 0", name="non_negative"),
    )


class LedgerTx(Base):
    """Финансовая транзакция. Сумма проводок равна нулю (проверяется отложенным триггером)."""

    __tablename__ = "ledger_tx"
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(32), index=True)
    ref_type: Mapped[str | None] = mapped_column(String(32))
    ref_id: Mapped[int | None]
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    memo: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at_col()


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"
    id: Mapped[int] = mapped_column(primary_key=True)
    tx_id: Mapped[int] = mapped_column(ForeignKey("ledger_tx.id"), index=True)
    wallet_id: Mapped[int] = mapped_column(ForeignKey("wallets.id"), index=True)
    delta: Mapped[int]
    balance_after: Mapped[int]
    __table_args__ = (CheckConstraint("delta <> 0", name="nonzero"),)


class Location(Base):
    __tablename__ = "locations"
    code: Mapped[str] = mapped_column(String(16), primary_key=True)
    name: Mapped[str] = mapped_column(String(64))


class Deposit(Base):
    __tablename__ = "deposits"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    location_code: Mapped[str] = mapped_column(ForeignKey("locations.code"))
    resource: Mapped[str] = mapped_column(String(16))
    name: Mapped[str] = mapped_column(String(64))
    stock: Mapped[int]
    max_stock: Mapped[int]
    regen_per_hour: Mapped[int]
    regen_at: Mapped[datetime]
    __table_args__ = (
        CheckConstraint("stock >= 0", name="stock_non_negative"),
        CheckConstraint("stock <= max_stock", name="stock_le_max"),
    )


class Stock(Base):
    """Физический запас ресурса владельца на складе локации. held — заблокировано под заявку/рейс/контракт."""

    __tablename__ = "stocks"
    owner_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), primary_key=True)
    location_code: Mapped[str] = mapped_column(ForeignKey("locations.code"), primary_key=True)
    resource: Mapped[str] = mapped_column(String(16), primary_key=True)
    free: Mapped[int] = mapped_column(default=0, server_default="0")
    held: Mapped[int] = mapped_column(default=0, server_default="0")
    __table_args__ = (
        CheckConstraint("free >= 0", name="free_non_negative"),
        CheckConstraint("held >= 0", name="held_non_negative"),
    )


class StockMovement(Base):
    """Журнал всех изменений запасов: источник/сток/перемещение/блокировка."""

    __tablename__ = "stock_movements"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    location_code: Mapped[str] = mapped_column(ForeignKey("locations.code"))
    resource: Mapped[str] = mapped_column(String(16))
    delta_free: Mapped[int]
    delta_held: Mapped[int]
    reason: Mapped[str] = mapped_column(String(32), index=True)
    ref_type: Mapped[str | None] = mapped_column(String(32))
    ref_id: Mapped[int | None]
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = created_at_col()


# Статусы экземпляров предметов: в каждый момент вещь находится ровно в одном состоянии.
ITEM_IDLE = "idle"
ITEM_BUSY = "busy"  # в производстве/добыче/ремонте/используется как установка
ITEM_LOADING = "loading"  # транспорт под погрузкой
ITEM_IN_TRANSIT = "in_transit"  # в рейсе (транспорт или груз)
ITEM_LISTED = "listed"  # выставлен на рынок
ITEM_INSTALLED = "installed"  # модуль в грузовике / окраска на грузовике
ITEM_LOCKED = "locked"  # заблокирован (спор, возврат Stars)
ITEM_DESTROYED = "destroyed"  # израсходован (например, модуль ушёл в сборку — не используется, модули остаются installed)
ITEM_STATUSES = (ITEM_IDLE, ITEM_BUSY, ITEM_LOADING, ITEM_IN_TRANSIT, ITEM_LISTED, ITEM_INSTALLED, ITEM_LOCKED, ITEM_DESTROYED)


class Item(Base):
    __tablename__ = "items"
    id: Mapped[int] = mapped_column(primary_key=True)
    def_code: Mapped[str] = mapped_column(String(32), index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    location_code: Mapped[str | None] = mapped_column(ForeignKey("locations.code"))
    status: Mapped[str] = mapped_column(String(16), default=ITEM_IDLE)
    durability: Mapped[int] = mapped_column(Integer, default=0)
    max_durability: Mapped[int] = mapped_column(Integer, default=0)
    serial_no: Mapped[int | None] = mapped_column(Integer)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("items.id"))
    attrs: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    origin: Mapped[str] = mapped_column(String(16))  # starter|craft|premium|admin
    origin_ref: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = created_at_col()
    __table_args__ = (
        CheckConstraint(
            "status in ('idle','busy','loading','in_transit','listed','installed','locked','destroyed')", name="status"
        ),
        CheckConstraint("durability >= 0 AND durability <= max_durability", name="durability_range"),
        UniqueConstraint("def_code", "serial_no", name="uq_items_def_serial"),
        Index("ix_items_parent", "parent_id"),
    )


class OwnershipHistory(Base):
    __tablename__ = "ownership_history"
    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), index=True)
    from_owner_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"))
    to_owner_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"))
    reason: Mapped[str] = mapped_column(String(32))
    ref_type: Mapped[str | None] = mapped_column(String(32))
    ref_id: Mapped[int | None]
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = created_at_col()


class Operation(Base):
    """Ключи идемпотентности: повторное нажатие кнопки/повторный update не выполнит операцию дважды."""

    __tablename__ = "operations"
    key: Mapped[str] = mapped_column(String(96), primary_key=True)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    kind: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = created_at_col()


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"), index=True)  # от чьего имени
    action: Mapped[str] = mapped_column(String(48), index=True)
    target_type: Mapped[str | None] = mapped_column(String(32))
    target_id: Mapped[int | None]
    data: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = created_at_col()
