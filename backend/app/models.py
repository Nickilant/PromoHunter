import enum
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
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


class Faction(str, enum.Enum):
    """Сторона в игровом режиме. Цвета — в токенах фронта."""

    green = "green"
    purple = "purple"


def faction_column(**kwargs):
    return mapped_column(
        Enum(Faction, name="faction", values_callable=lambda e: [x.value for x in e]),
        **kwargs,
    )


class User(Base):
    __tablename__ = "users"
    # Баланс сторон считается по городу — индекс под этот запрос
    __table_args__ = (Index("ix_users_city_faction", "city", "faction"),)

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
    # Привязка Telegram-аккаунта: вход через WebApp и уведомления бота
    telegram_id: Mapped[int | None] = mapped_column(BigInteger, unique=True)
    # --- игровой режим ---
    # Выключен по умолчанию: без него сервис работает точно как раньше
    game_mode: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    # Спросили про игровой режим — второй раз не пристаём
    game_asked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    faction: Mapped[Faction | None] = faction_column()
    faction_joined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
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
        Index("ix_restaurants_city_active", "city", "is_active"),
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
    # Смещение часов кассы от UTC: в QR-коде чека время местное и без зоны.
    # По умолчанию Москва; для других зон правится в админке.
    utc_offset_minutes: Mapped[int] = mapped_column(
        Integer, default=180, server_default="180", nullable=False
    )
    # Часы, в которые точка реально пробивает чеки: 24 бита по часам UTC.
    # 0 — данных мало, шкалы захвата идут круглосуточно.
    active_hours_mask: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
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
    # Отчёт подтверждён чеком: голос сильнее, кулдаун не действует
    is_receipt_verified: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
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
    restaurant_suggestion_id: Mapped[int | None] = mapped_column(
        ForeignKey("restaurant_suggestions.id", ondelete="SET NULL")
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


class PhoneVerification(Base):
    """Код подтверждения номера при регистрации.

    Код доставляет телеграм-бот: если чат с этим номером уже знаком боту —
    сразу, иначе после того, как человек отправит боту свой контакт.
    """

    __tablename__ = "phone_verifications"
    __table_args__ = (Index("ix_phone_verifications_phone", "phone"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    code: Mapped[str] = mapped_column(String(8), nullable=False)
    telegram_id: Mapped[int | None] = mapped_column(BigInteger)
    is_confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Subscription(Base):
    """Подписка на точку (новые акции) или на акцию (изменения и статусы).

    Уведомления доставляет телеграм-бот, поэтому подписка доступна только
    пользователям с привязанным telegram_id.
    """

    __tablename__ = "subscriptions"
    __table_args__ = (
        Index("ix_subscriptions_user", "user_id"),
        UniqueConstraint("user_id", "restaurant_id", name="uq_sub_user_restaurant"),
        UniqueConstraint("user_id", "promotion_id", name="uq_sub_user_promotion"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    restaurant_id: Mapped[int | None] = mapped_column(
        ForeignKey("restaurants.id", ondelete="CASCADE")
    )
    promotion_id: Mapped[int | None] = mapped_column(
        ForeignKey("promotions.id", ondelete="CASCADE")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship()
    restaurant: Mapped["Restaurant"] = relationship()
    promotion: Mapped["Promotion"] = relationship()


class RestaurantSuggestion(Base):
    """Заявка пользователя на добавление точки. Бренд — только из списка."""

    __tablename__ = "restaurant_suggestions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    brand_id: Mapped[int] = mapped_column(
        ForeignKey("brands.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str | None] = mapped_column(String(200))
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    address: Mapped[str] = mapped_column(String(300), nullable=False)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lng: Mapped[float] = mapped_column(Float, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)
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
    created_restaurant_id: Mapped[int | None] = mapped_column(
        ForeignKey("restaurants.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped["User"] = relationship()
    brand: Mapped["Brand"] = relationship()


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


# --- игровой режим: захват точек фракциями ---


class FiscalDrive(Base):
    """Фискальный накопитель (`fn` из QR чека) — отпечаток кассы.

    Привязку «касса ↔ точка» собирает краудсорсинг: нужно
    receipt_bind_confirmations чеков от разных людей на одной точке. После
    привязки чек этой кассы, присланный с другой точки, не принимается.
    """

    __tablename__ = "fiscal_drives"

    id: Mapped[int] = mapped_column(primary_key=True)
    fn: Mapped[str] = mapped_column(String(24), unique=True, nullable=False)
    restaurant_id: Mapped[int | None] = mapped_column(
        ForeignKey("restaurants.id", ondelete="SET NULL")
    )
    confirmations: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_bound: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Счётчик документов кассы: монотонно растёт, откат — признак подделки
    max_doc_number: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_doc_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    bound_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    restaurant: Mapped["Restaurant | None"] = relationship()


class Receipt(Base):
    """Принятый чек: единственный способ добавить силу фракции на точке."""

    __tablename__ = "receipts"
    __table_args__ = (
        # Один и тот же чек нельзя предъявить дважды — ни себе, ни другой стороне
        UniqueConstraint("fn", "doc_number", name="uq_receipt_fn_doc"),
        Index("ix_receipts_restaurant_created", "restaurant_id", "created_at"),
        Index("ix_receipts_user_created", "user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    restaurant_id: Mapped[int] = mapped_column(
        ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False
    )
    report_id: Mapped[int | None] = mapped_column(
        ForeignKey("reports.id", ondelete="SET NULL"), unique=True
    )
    fn: Mapped[str] = mapped_column(String(24), nullable=False)
    doc_number: Mapped[int] = mapped_column(Integer, nullable=False)  # `i` из QR
    fp: Mapped[str] = mapped_column(String(24), nullable=False)
    sum_kopeks: Mapped[int] = mapped_column(Integer, nullable=False)
    purchased_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    faction: Mapped[Faction] = faction_column(nullable=False)
    # Вклад в силу с учётом убывающей отдачи и коэффициента андердога
    strength: Mapped[float] = mapped_column(Float, nullable=False)
    raw: Mapped[str] = mapped_column(String(300), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship()
    restaurant: Mapped["Restaurant"] = relationship()


class PointControl(Base):
    """Состояние борьбы за точку: сила сторон и две шкалы захвата.

    Сила обеих сторон тает экспоненциально (capture_half_life_hours), поэтому
    владение отражает не историю, а то, кто активен сейчас. Шкалы — как захват
    базы в World of Tanks: идёт шкала лидера, шкала отстающего стоит на паузе
    и подтаивает; чья шкала заполнилась первой, та и решила исход.
    """

    __tablename__ = "point_controls"

    restaurant_id: Mapped[int] = mapped_column(
        ForeignKey("restaurants.id", ondelete="CASCADE"), primary_key=True
    )
    owner_faction: Mapped[Faction | None] = faction_column()
    green_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    purple_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    # Момент, на который посчитаны силы: читать через экспоненциальный распад
    score_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # Заполнение шкал в «секундах шкалы» из capture_bar_seconds
    green_progress: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    purple_progress: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    progress_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    battle_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    truce_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attack_notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    warning_notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    green_receipts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    purple_receipts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    restaurant: Mapped["Restaurant"] = relationship()


class CaptureEvent(Base):
    """Журнал исходов: точка взята или атака отбита."""

    __tablename__ = "capture_events"
    __table_args__ = (
        Index("ix_capture_events_city_created", "city", "created_at"),
        Index("ix_capture_events_restaurant_created", "restaurant_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    restaurant_id: Mapped[int] = mapped_column(
        ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False
    )
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    faction: Mapped[Faction] = faction_column(nullable=False)
    kind: Mapped[str] = mapped_column(String(8), nullable=False)  # capture | defend
    finisher_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    restaurant: Mapped["Restaurant"] = relationship()


class FactionStanding(Base):
    """Сезонный зачёт города: сколько «точко-секунд» удержала сторона.

    Средняя доля владения за сезон = held_seconds / (секунды сезона × точки).
    """

    __tablename__ = "faction_standings"
    __table_args__ = (
        UniqueConstraint("city", "season", "faction", name="uq_standing_city_season"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    season: Mapped[str] = mapped_column(String(7), nullable=False)  # YYYY-MM
    faction: Mapped[Faction] = faction_column(nullable=False)
    held_seconds: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    captures: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    defends: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
