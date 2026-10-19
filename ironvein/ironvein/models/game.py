"""Производство, рынок, транспорт, компании, контракты, премиум-платежи."""

from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ironvein.models.base import Base, created_at_col

# --- Производственные задания ------------------------------------------------------------------------

JOB_PENDING = "pending"
JOB_RUNNING = "running"
JOB_COMPLETED = "completed"
JOB_CANCELLED = "cancelled"
JOB_FAILED = "failed"


class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(16))  # mine | craft | repair
    owner_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    actor_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    location_code: Mapped[str] = mapped_column(ForeignKey("locations.code"))
    recipe_code: Mapped[str | None] = mapped_column(String(32))
    runs: Mapped[int] = mapped_column(Integer, default=1)
    manual: Mapped[bool] = mapped_column(default=False)
    equipment_id: Mapped[int | None] = mapped_column(ForeignKey("items.id"))
    target_item_id: Mapped[int | None] = mapped_column(ForeignKey("items.id"))
    deposit_id: Mapped[int | None] = mapped_column(ForeignKey("deposits.id"))
    status: Mapped[str] = mapped_column(String(16))
    inputs: Mapped[dict] = mapped_column(JSONB, default=dict)  # что списано при старте
    outputs: Mapped[dict] = mapped_column(JSONB, default=dict)  # что будет выдано
    consumed_items: Mapped[list] = mapped_column(JSONB, default=list)
    # Параметры, зафиксированные при старте (база качества, «тщательно»): завершение не зависит от позднего состояния.
    params: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    started_at: Mapped[datetime]
    finishes_at: Mapped[datetime]
    finished_at: Mapped[datetime | None]
    result: Mapped[dict | None] = mapped_column(JSONB)
    __table_args__ = (
        CheckConstraint("status in ('pending','running','completed','cancelled','failed')", name="status"),
        CheckConstraint("runs >= 1", name="runs_positive"),
        Index("ix_jobs_due", "finishes_at", postgresql_where=text("status = 'running'")),
        Index("ix_jobs_started_at", "started_at"),
        # Одна ручная смена на игрока одновременно — «рабочие руки» не размножаются.
        Index("uq_jobs_manual_running", "actor_user_id", unique=True,
              postgresql_where=text("manual AND status = 'running'")),
    )


# --- Рынок -------------------------------------------------------------------------------------------


class MarketOrder(Base):
    __tablename__ = "market_orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    side: Mapped[str] = mapped_column(String(4))  # ask | bid
    location_code: Mapped[str | None] = mapped_column(ForeignKey("locations.code"))
    resource: Mapped[str | None] = mapped_column(String(16))
    item_def: Mapped[str | None] = mapped_column(String(32))
    item_id: Mapped[int | None] = mapped_column(ForeignKey("items.id"))
    price: Mapped[int]
    qty_total: Mapped[int]
    qty_left: Mapped[int]
    reserved: Mapped[int] = mapped_column(default=0)  # кроны в hold под bid
    status: Mapped[str] = mapped_column(String(12), default="open")
    created_at: Mapped[datetime] = created_at_col()
    closed_at: Mapped[datetime | None]
    __table_args__ = (
        CheckConstraint("side in ('ask','bid')", name="side"),
        CheckConstraint("status in ('open','filled','cancelled')", name="status"),
        CheckConstraint("price > 0", name="price_positive"),
        CheckConstraint("qty_total > 0 AND qty_left >= 0 AND qty_left <= qty_total", name="qty_range"),
        CheckConstraint("reserved >= 0", name="reserved_non_negative"),
        CheckConstraint("(resource IS NOT NULL) <> (item_def IS NOT NULL)", name="one_good"),
        CheckConstraint("item_id IS NULL OR (side = 'ask' AND qty_total = 1)", name="unique_item_ask"),
        Index("ix_orders_book", "resource", "item_def", "location_code", "side", "price",
              postgresql_where=text("status = 'open'")),
        # Одна вещь — максимум одна активная продажа.
        Index("uq_orders_open_item", "item_id", unique=True,
              postgresql_where=text("status = 'open' AND item_id IS NOT NULL")),
    )


class MarketTrade(Base):
    __tablename__ = "market_trades"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("market_orders.id"), index=True)
    buyer_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    seller_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    location_code: Mapped[str | None] = mapped_column(ForeignKey("locations.code"))
    resource: Mapped[str | None] = mapped_column(String(16))
    item_def: Mapped[str | None] = mapped_column(String(32))
    item_id: Mapped[int | None] = mapped_column(ForeignKey("items.id"))
    qty: Mapped[int]
    price: Mapped[int]
    gross: Mapped[int]
    fee: Mapped[int]
    created_at: Mapped[datetime] = created_at_col()
    __table_args__ = (
        CheckConstraint("qty > 0 AND price > 0 AND gross = qty * price AND fee >= 0 AND fee <= gross", name="amounts"),
        Index("ix_trades_good_time", "resource", "item_def", "location_code", "created_at"),
    )


# --- Транспорт ---------------------------------------------------------------------------------------


class Shipment(Base):
    __tablename__ = "shipments"
    id: Mapped[int] = mapped_column(primary_key=True)
    mode: Mapped[str] = mapped_column(String(8))  # truck | foot
    vehicle_id: Mapped[int | None] = mapped_column(ForeignKey("items.id"))
    carrier_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    origin: Mapped[str] = mapped_column(ForeignKey("locations.code"))
    dest: Mapped[str] = mapped_column(ForeignKey("locations.code"))
    distance_km: Mapped[int] = mapped_column(Integer)
    fuel: Mapped[int] = mapped_column(Integer, default=0)
    wear: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(12))
    contract_id: Mapped[int | None] = mapped_column(ForeignKey("contracts.id", use_alter=True))
    created_at: Mapped[datetime] = created_at_col()
    departed_at: Mapped[datetime | None]
    eta: Mapped[datetime | None]
    arrived_at: Mapped[datetime | None]
    __table_args__ = (
        CheckConstraint("status in ('loading','in_transit','delivered','cancelled')", name="status"),
        CheckConstraint("mode in ('truck','foot')", name="mode"),
        CheckConstraint("origin <> dest", name="distinct_ends"),
        CheckConstraint("(mode = 'truck') = (vehicle_id IS NOT NULL)", name="vehicle_for_truck"),
        Index("ix_shipments_due", "eta", postgresql_where=text("status = 'in_transit'")),
        # Машина не может быть одновременно в двух активных рейсах.
        Index("uq_shipments_active_vehicle", "vehicle_id", unique=True,
              postgresql_where=text("status in ('loading','in_transit') AND vehicle_id IS NOT NULL")),
    )


class ShipmentCargo(Base):
    __tablename__ = "shipment_cargo"
    id: Mapped[int] = mapped_column(primary_key=True)
    shipment_id: Mapped[int] = mapped_column(ForeignKey("shipments.id"), index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    recipient_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    resource: Mapped[str | None] = mapped_column(String(16))
    qty: Mapped[int] = mapped_column(default=0)
    item_id: Mapped[int | None] = mapped_column(ForeignKey("items.id"))
    __table_args__ = (
        CheckConstraint("(resource IS NOT NULL AND qty > 0 AND item_id IS NULL) OR "
                        "(item_id IS NOT NULL AND resource IS NULL)", name="one_cargo"),
    )


# --- Компании ----------------------------------------------------------------------------------------


class Company(Base):
    __tablename__ = "companies"
    id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), primary_key=True)
    name: Mapped[str] = mapped_column(String(32))
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(8), default="active")
    crest_item_id: Mapped[int | None] = mapped_column(ForeignKey("items.id"))
    created_at: Mapped[datetime] = created_at_col()
    closed_at: Mapped[datetime | None]
    __table_args__ = (
        CheckConstraint("status in ('active','closed')", name="status"),
        Index("uq_companies_name_active", text("lower(name)"), unique=True,
              postgresql_where=text("status = 'active'")),
    )


class CompanyMember(Base):
    __tablename__ = "company_members"
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True, index=True)
    role: Mapped[str] = mapped_column(String(10))
    permissions: Mapped[int] = mapped_column(Integer)
    joined_at: Mapped[datetime] = created_at_col()
    __table_args__ = (CheckConstraint("role in ('owner','manager','employee')", name="role"),)


class CompanyInvite(Base):
    __tablename__ = "company_invites"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    invited_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    role: Mapped[str] = mapped_column(String(10), default="employee")
    status: Mapped[str] = mapped_column(String(10), default="pending")
    created_at: Mapped[datetime] = created_at_col()
    __table_args__ = (
        CheckConstraint("status in ('pending','accepted','declined','revoked')", name="status"),
        Index("uq_invites_pending", "company_id", "user_id", unique=True, postgresql_where=text("status = 'pending'")),
    )


# --- Контракты ---------------------------------------------------------------------------------------

CONTRACT_STATUSES = ("draft", "open", "accepted", "in_progress", "completed", "cancelled", "expired", "disputed")


class Contract(Base):
    __tablename__ = "contracts"
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(10))  # supply | transport
    customer_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    executor_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"), index=True)
    target_executor_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"))
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    resource: Mapped[str] = mapped_column(String(16))
    qty: Mapped[int]
    delivered_qty: Mapped[int] = mapped_column(default=0)
    price_total: Mapped[int]
    paid_out: Mapped[int] = mapped_column(default=0)
    fee_paid: Mapped[int] = mapped_column(default=0)
    reserved: Mapped[int] = mapped_column(default=0)  # кроны в hold заказчика
    fee_bps: Mapped[int] = mapped_column(Integer)
    location_code: Mapped[str] = mapped_column(ForeignKey("locations.code"))  # место поставки / отправления
    dest_code: Mapped[str | None] = mapped_column(ForeignKey("locations.code"))  # для перевозки
    deadline: Mapped[datetime]
    terms: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(12), default="draft")
    status_before_dispute: Mapped[str | None] = mapped_column(String(12))
    shipment_id: Mapped[int | None] = mapped_column(ForeignKey("shipments.id"))
    created_at: Mapped[datetime] = created_at_col()
    accepted_at: Mapped[datetime | None]
    closed_at: Mapped[datetime | None]
    __table_args__ = (
        CheckConstraint("kind in ('supply','transport')", name="kind"),
        CheckConstraint(
            "status in ('draft','open','accepted','in_progress','completed','cancelled','expired','disputed')",
            name="status",
        ),
        CheckConstraint("qty > 0 AND delivered_qty >= 0 AND delivered_qty <= qty", name="qty_range"),
        CheckConstraint("price_total > 0 AND paid_out >= 0 AND fee_paid >= 0 AND paid_out + fee_paid <= price_total",
                        name="money_range"),
        CheckConstraint("reserved >= 0", name="reserved_non_negative"),
        CheckConstraint("kind = 'supply' OR (dest_code IS NOT NULL AND dest_code <> location_code)", name="route"),
        CheckConstraint("executor_id IS NULL OR executor_id <> customer_id", name="not_self"),
        Index("ix_contracts_deadline", "deadline", postgresql_where=text("status in ('open','accepted','in_progress')")),
    )


class ContractEvent(Base):
    __tablename__ = "contract_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("contracts.id"), index=True)
    event: Mapped[str] = mapped_column(String(24))
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    data: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = created_at_col()


class ContractFulfillment(Base):
    __tablename__ = "contract_fulfillments"
    id: Mapped[int] = mapped_column(primary_key=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("contracts.id"), index=True)
    qty: Mapped[int]
    payout: Mapped[int]
    fee: Mapped[int]
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = created_at_col()
    __table_args__ = (CheckConstraint("qty > 0 AND payout >= 0 AND fee >= 0", name="amounts"),)


# --- Премиум (Telegram Stars) ------------------------------------------------------------------------


class PremiumProduct(Base):
    __tablename__ = "premium_products"
    code: Mapped[str] = mapped_column(String(32), primary_key=True)
    item_def: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(64))
    description: Mapped[str] = mapped_column(Text)
    price_stars: Mapped[int] = mapped_column(Integer)
    edition_limit: Mapped[int | None] = mapped_column(Integer)
    issued: Mapped[int] = mapped_column(Integer, default=0)  # выдано экземпляров (последний серийник)
    reserved: Mapped[int] = mapped_column(Integer, default=0)  # забронировано под открытые счета
    active: Mapped[bool] = mapped_column(default=True)
    __table_args__ = (
        CheckConstraint("price_stars > 0", name="price_positive"),
        CheckConstraint("issued >= 0 AND reserved >= 0", name="counters"),
        CheckConstraint("edition_limit IS NULL OR issued + reserved <= edition_limit", name="edition_limit"),
    )


PO_CREATED = "created"  # счёт выставлен, слот (если лимит) забронирован
PO_PAID = "paid"  # оплата получена, предмет ещё не выдан (повтор выдачи фоновой задачей)
PO_FULFILLED = "fulfilled"
PO_EXPIRED = "expired"  # счёт не оплачен вовремя, бронь снята
PO_REFUND_PENDING = "refund_pending"  # оплачено, выдать нельзя — нужен возврат
PO_REFUNDED = "refunded"
PO_STATUSES = (PO_CREATED, PO_PAID, PO_FULFILLED, PO_EXPIRED, PO_REFUND_PENDING, PO_REFUNDED)


class PremiumOrder(Base):
    __tablename__ = "premium_orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(String(40), unique=True)  # invoice payload
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    product_code: Mapped[str] = mapped_column(ForeignKey("premium_products.code"))
    price_stars: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="XTR")
    status: Mapped[str] = mapped_column(String(16))
    holds_slot: Mapped[bool] = mapped_column(default=False)
    reserved_until: Mapped[datetime | None]
    telegram_charge_id: Mapped[str | None] = mapped_column(String(128), unique=True)
    item_id: Mapped[int | None] = mapped_column(ForeignKey("items.id"))
    created_at: Mapped[datetime] = created_at_col()
    paid_at: Mapped[datetime | None]
    fulfilled_at: Mapped[datetime | None]
    refunded_at: Mapped[datetime | None]
    __table_args__ = (
        CheckConstraint(
            "status in ('created','paid','fulfilled','expired','refund_pending','refunded')", name="status"),
        CheckConstraint("currency = 'XTR'", name="currency"),
    )


class PaymentEvent(Base):
    __tablename__ = "payment_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("premium_orders.id"), index=True)
    event: Mapped[str] = mapped_column(String(32))
    data: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = created_at_col()
