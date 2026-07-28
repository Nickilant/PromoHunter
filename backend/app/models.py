import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UserRole(str, enum.Enum):
    user = "user"
    admin = "admin"


class SuggestionStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class ReportChannel(str, enum.Enum):
    on_site = "on_site"      # человек на точке
    delivery = "delivery"    # заказ через доставку


class VerdictOutcome(str, enum.Enum):
    confirmed = "confirmed"
    refuted = "refuted"
    neutral = "neutral"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    phone: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    # Подтверждение номера кодом через Telegram — следующий этап;
    # пока при регистрации ставим True без проверки
    is_phone_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    # Город по умолчанию: записывается из сессии при регистрации,
    # редактирование в настройках профиля — следующий этап
    city: Mapped[str | None] = mapped_column(String(100))
    # Скрытый вес доверия (docs/trust-and-rating-spec.md §2); нигде не отображается
    weight: Mapped[float] = mapped_column(
        Float, default=1.0, server_default="1.0", nullable=False
    )
    weight_drifted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role", values_callable=lambda e: [x.value for x in e]),
        default=UserRole.user,
        nullable=False,
    )
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    reports: Mapped[list["Report"]] = relationship(back_populates="user")


class Brand(Base):
    __tablename__ = "brands"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    color: Mapped[str] = mapped_column(String(7), default="#6B9080", nullable=False)
    logo_url: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    restaurants: Mapped[list["Restaurant"]] = relationship(back_populates="brand")
    promotions: Mapped[list["Promotion"]] = relationship(back_populates="brand")


class Restaurant(Base):
    __tablename__ = "restaurants"
    __table_args__ = (
        Index("ix_restaurants_brand_id", "brand_id"),
        Index("ix_restaurants_city", "city"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    brand_id: Mapped[int] = mapped_column(
        ForeignKey("brands.id", ondelete="RESTRICT"), nullable=False
    )
    title: Mapped[str | None] = mapped_column(String(200))
    city: Mapped[str] = mapped_column(
        String(100), nullable=False, server_default="Санкт-Петербург"
    )
    address: Mapped[str] = mapped_column(String(300), nullable=False)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lng: Mapped[float] = mapped_column(Float, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    brand: Mapped["Brand"] = relationship(back_populates="restaurants")


class Promotion(Base):
    __tablename__ = "promotions"
    __table_args__ = (Index("ix_promotions_brand_id_is_active", "brand_id", "is_active"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    brand_id: Mapped[int] = mapped_column(
        ForeignKey("brands.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    brand: Mapped["Brand"] = relationship(back_populates="promotions")
    items: Mapped[list["PromotionItem"]] = relationship(
        back_populates="promotion",
        cascade="all, delete-orphan",
        order_by="PromotionItem.sort_order",
    )


class PromotionItem(Base):
    __tablename__ = "promotion_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    promotion_id: Mapped[int] = mapped_column(
        ForeignKey("promotions.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    promotion: Mapped["Promotion"] = relationship(back_populates="items")


class Report(Base):
    __tablename__ = "reports"
    __table_args__ = (
        Index("ix_reports_rest_promo_created", "restaurant_id", "promotion_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    restaurant_id: Mapped[int] = mapped_column(
        ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False
    )
    promotion_id: Mapped[int] = mapped_column(
        ForeignKey("promotions.id", ondelete="CASCADE"), nullable=False
    )
    # Поле под проверку геолокации на следующем этапе; сейчас не заполняется
    lat: Mapped[float | None] = mapped_column(Float)
    lng: Mapped[float | None] = mapped_column(Float)
    channel: Mapped[ReportChannel] = mapped_column(
        Enum(
            ReportChannel,
            name="report_channel",
            values_callable=lambda e: [x.value for x in e],
        ),
        default=ReportChannel.on_site,
        server_default="on_site",
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="reports")
    restaurant: Mapped["Restaurant"] = relationship()
    promotion: Mapped["Promotion"] = relationship()
    items: Mapped[list["ReportItem"]] = relationship(
        back_populates="report", cascade="all, delete-orphan"
    )


class ReportItem(Base):
    __tablename__ = "report_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    report_id: Mapped[int] = mapped_column(
        ForeignKey("reports.id", ondelete="CASCADE"), nullable=False
    )
    promotion_item_id: Mapped[int] = mapped_column(
        ForeignKey("promotion_items.id", ondelete="CASCADE"), nullable=False
    )
    is_available: Mapped[bool] = mapped_column(Boolean, nullable=False)

    report: Mapped["Report"] = relationship(back_populates="items")
    promotion_item: Mapped["PromotionItem"] = relationship()


class ReportVerdict(Base):
    """Дозревший вердикт отчёта: подтверждён/опровергнут консенсусом или нейтрален.

    Единственный источник для пересчёта весов и начисления бонусных очков.
    """

    __tablename__ = "report_verdicts"
    __table_args__ = (Index("ix_report_verdicts_user_id", "user_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    report_id: Mapped[int] = mapped_column(
        ForeignKey("reports.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    verdict: Mapped[VerdictOutcome] = mapped_column(
        Enum(
            VerdictOutcome,
            name="verdict_outcome",
            values_callable=lambda e: [x.value for x in e],
        ),
        nullable=False,
    )
    is_pioneer: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    confirmed_items: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    refuted_items: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    neutral_items: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    matured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    report: Mapped["Report"] = relationship()


class RatingEvent(Base):
    """Журнал публичного рейтинга: одна строка — одно начисление/штраф."""

    __tablename__ = "rating_events"
    __table_args__ = (
        Index("ix_rating_events_user_created", "user_id", "created_at"),
        Index("ix_rating_events_city_created", "city", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    city: Mapped[str | None] = mapped_column(String(100))
    # report_base | report_confirmed | pioneer | scout | suggestion_approved |
    # report_refuted | suggestion_spam
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    points: Mapped[int] = mapped_column(Integer, nullable=False)
    report_id: Mapped[int | None] = mapped_column(
        ForeignKey("reports.id", ondelete="SET NULL")
    )
    suggestion_id: Mapped[int | None] = mapped_column(
        ForeignKey("promotion_suggestions.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship()


class ItemStatusState(Base):
    """Последний устойчивый статус пары (точка, товар) — память направления
    для переходных статусов «возможно кончилось / возможно появилось»."""

    __tablename__ = "item_status_states"

    restaurant_id: Mapped[int] = mapped_column(
        ForeignKey("restaurants.id", ondelete="CASCADE"), primary_key=True
    )
    promotion_item_id: Mapped[int] = mapped_column(
        ForeignKey("promotion_items.id", ondelete="CASCADE"), primary_key=True
    )
    stable: Mapped[str] = mapped_column(
        String(16), default="unknown", nullable=False
    )  # available | unavailable | unknown
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class PromotionSuggestion(Base):
    __tablename__ = "promotion_suggestions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    brand_id: Mapped[int | None] = mapped_column(
        ForeignKey("brands.id", ondelete="SET NULL")
    )
    brand_name_raw: Mapped[str | None] = mapped_column(String(120))
    restaurant_id: Mapped[int | None] = mapped_column(
        ForeignKey("restaurants.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    items_raw: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[SuggestionStatus] = mapped_column(
        Enum(
            SuggestionStatus,
            name="suggestion_status",
            values_callable=lambda e: [x.value for x in e],
        ),
        default=SuggestionStatus.pending,
        nullable=False,
    )
    moderator_comment: Mapped[str | None] = mapped_column(Text)
    created_promotion_id: Mapped[int | None] = mapped_column(
        ForeignKey("promotions.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped["User"] = relationship()
    brand: Mapped["Brand"] = relationship()
    restaurant: Mapped["Restaurant"] = relationship()
