"""Tabelas do banco. Listas/objetos ficam em JSON para funcionar igual em SQLite e Postgres."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    TypeDecorator,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class JsonType(TypeDecorator):
    """JSON portátil: JSONB no Postgres (Neon), JSON comum no SQLite."""

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect: Any) -> Any:
        return dialect.type_descriptor(JSONB() if dialect.name == "postgresql" else JSON())


def new_id() -> str:
    return uuid.uuid4().hex


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UTCDateTime(TypeDecorator):
    """Sempre devolve datetimes com fuso UTC (o SQLite perde o fuso ao gravar)."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Any) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def process_result_value(self, value: datetime | None, dialect: Any) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(10), default="USER")  # USER | ADMIN
    plan: Mapped[str] = mapped_column(String(10), default="FREE")  # FREE | PRO | ELITE
    status: Mapped[str] = mapped_column(String(12), default="PENDING")  # PENDING | ACTIVE | SUSPENDED
    email_verified_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    # Teste grátis e assinatura (Stripe). O acesso vale durante o teste ou com assinatura ativa.
    trial_ends_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    subscription_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    subscription_ends_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    stripe_customer_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Preferências: o país do usuário sugere idioma e moeda; ele pode mudar os dois depois.
    country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    language: Mapped[str] = mapped_column(String(2), default="pt", server_default="pt")
    currency: Mapped[str] = mapped_column(String(3), default="EUR", server_default="EUR")

    settings: Mapped["UserSettings"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    alerts: Mapped[list["Alert"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    destinations: Mapped[list["Destination"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    family_id: Mapped[str] = mapped_column(String(32), index=True)  # reuso de um token antigo derruba a família
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)


class EmailToken(Base):
    __tablename__ = "email_tokens"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(20))  # VERIFY_EMAIL | RESET_PASSWORD
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)
    used_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)


class Invite(Base):
    __tablename__ = "invites"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    code_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_by: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)
    used_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)


class UserSettings(Base):
    __tablename__ = "settings"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    interval_minutes: Mapped[float] = mapped_column(Float, default=5.0)
    monitor_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    last_run_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)

    user: Mapped[User] = relationship(back_populates="settings")


class Destination(Base):
    """Para onde os avisos são entregues (hoje Telegram: privado, grupo ou canal)."""

    __tablename__ = "destinations"
    __table_args__ = (UniqueConstraint("channel", "external_id", name="uq_destination_channel_external"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    channel: Mapped[str] = mapped_column(String(20), default="TELEGRAM")
    kind: Mapped[str | None] = mapped_column(String(10), nullable=True)  # PRIVATE | GROUP | CHANNEL
    external_id: Mapped[str | None] = mapped_column(String(64), nullable=True)  # Telegram chat_id
    title: Mapped[str | None] = mapped_column(String(120), nullable=True)
    config: Mapped[dict | None] = mapped_column(JsonType, nullable=True)
    # Idioma dos avisos deste destino (pt/en). Vazio = o mesmo idioma da conta.
    language: Mapped[str | None] = mapped_column(String(2), nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    code_hash: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    code_expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    linked_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    disconnected_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)

    user: Mapped[User] = relationship(back_populates="destinations")

    @property
    def status(self) -> str:
        if self.linked_at is None:
            return "PENDING"
        return "DISCONNECTED" if self.disconnected_at else "LINKED"


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    query: Mapped[str] = mapped_column(String(100))
    match_type: Mapped[str] = mapped_column(String(12), default="PHRASE")  # PHRASE | ALL_WORDS
    required_words: Mapped[list] = mapped_column(JsonType, default=list)
    exclude_words: Mapped[list] = mapped_column(JsonType, default=list)
    exclude_presets: Mapped[list] = mapped_column(JsonType, default=list)
    min_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    max_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    status_filter: Mapped[list] = mapped_column(JsonType, default=list)
    max_age_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pages: Mapped[int] = mapped_column(Integer, default=1)
    country: Mapped[str] = mapped_column(String(4), default="pt")  # domínio ou "eu" (todos)
    notify_on_first_run: Mapped[bool] = mapped_column(Boolean, default=False)
    vinted_params: Mapped[dict | None] = mapped_column(JsonType, nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    perfect_min: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    perfect_max: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    destination_id: Mapped[str | None] = mapped_column(
        ForeignKey("destinations.id", ondelete="SET NULL"), nullable=True
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    # Quando o alerta foi processado pela 1ª vez (a partir daí só avisamos do que aparecer depois).
    baselined_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    # Só conta anúncio com id maior que este (= publicado depois do corte da 1ª busca: ~5 min antes dela).
    min_item_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    user: Mapped[User] = relationship(back_populates="alerts")


class Item(Base):
    """Catálogo global de anúncios (dados públicos, compartilhados entre usuários)."""

    __tablename__ = "items"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    vinted_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    domain: Mapped[str] = mapped_column(String(4), default="pt")
    title: Mapped[str] = mapped_column(String(300))
    title_pt: Mapped[str | None] = mapped_column(String(300), nullable=True)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    condition: Mapped[str | None] = mapped_column(String(30), nullable=True)
    seller_login: Mapped[str] = mapped_column(String(80))
    url: Mapped[str] = mapped_column(String(500))
    photo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class PriceSnapshot(Base):
    __tablename__ = "price_snapshots"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    item_id: Mapped[str] = mapped_column(ForeignKey("items.id", ondelete="CASCADE"), index=True)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Match(Base):
    """"Este anúncio satisfaz este alerta" (por usuário)."""

    __tablename__ = "matches"
    __table_args__ = (UniqueConstraint("alert_id", "item_id", name="uq_match_alert_item"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    alert_id: Mapped[str] = mapped_column(ForeignKey("alerts.id", ondelete="CASCADE"), index=True)
    item_id: Mapped[str] = mapped_column(ForeignKey("items.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (UniqueConstraint("user_id", "item_id", name="uq_notification_user_item"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    item_id: Mapped[str] = mapped_column(ForeignKey("items.id", ondelete="CASCADE"))
    sent_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    ok: Mapped[bool] = mapped_column(Boolean, default=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class MonitorRun(Base):
    __tablename__ = "monitor_runs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    search_key: Mapped[str] = mapped_column(String(200))
    started_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)
    ended_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(15), default="running")  # running|ok|error|rate_limited
    raw_count: Mapped[int] = mapped_column(Integer, default=0)
    match_count: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
