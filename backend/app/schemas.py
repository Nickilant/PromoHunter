from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import Faction, ReportChannel, SuggestionStatus, UserRole
from app.phone import normalize_phone


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- auth ---

class PhoneMixin(BaseModel):
    phone: str

    @field_validator("phone")
    @classmethod
    def _normalize_phone(cls, value: str) -> str:
        normalized = normalize_phone(value)
        if normalized is None:
            raise ValueError("Неверный формат номера телефона")
        return normalized


class RegisterIn(PhoneMixin):
    password: str = Field(min_length=6, max_length=128)
    display_name: str = Field(min_length=1, max_length=100)
    # Город из сессии — станет городом по умолчанию в профиле
    city: str | None = Field(default=None, max_length=100)


class LoginIn(PhoneMixin):
    password: str


class PhoneVerificationRequestIn(PhoneMixin):
    pass


class PhoneVerificationRequestOut(BaseModel):
    # sent — код уже улетел в Telegram; await_contact — сначала нужно
    # отправить боту свой контакт, тогда он пришлёт код
    delivery: str
    bot_username: str | None = None


class PhoneVerificationConfirmIn(PhoneMixin):
    code: str = Field(min_length=1, max_length=8)


class PhoneVerificationConfirmOut(BaseModel):
    verified: bool


class TelegramAuthIn(BaseModel):
    init_data: str
    city: str | None = Field(default=None, max_length=100)


class TelegramContactIn(TelegramAuthIn):
    # строка response из Telegram.WebApp.requestContact — подписана ботом
    contact_response: str


class UserOut(ORMModel):
    id: int
    phone: str
    is_phone_verified: bool
    display_name: str
    city: str | None = None
    has_telegram: bool = Field(default=False, validation_alias="telegram_id")
    role: UserRole
    is_blocked: bool
    # игровой режим
    game_mode: bool = False
    game_asked: bool = Field(default=False, validation_alias="game_asked_at")
    faction: Faction | None = None
    created_at: datetime

    @field_validator("game_asked", mode="before")
    @classmethod
    def _from_game_asked_at(cls, value):
        return bool(value)

    @field_validator("has_telegram", mode="before")
    @classmethod
    def _from_telegram_id(cls, value):
        return bool(value)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# --- brands / restaurants ---

class BrandOut(ORMModel):
    id: int
    name: str
    slug: str
    color: str
    logo_url: str | None = None


class BrandShort(ORMModel):
    id: int
    name: str
    color: str


class RestaurantListItem(ORMModel):
    id: int
    brand: BrandShort
    title: str | None = None
    city: str
    address: str
    lat: float
    lng: float
    active_promotions_count: int
    last_report_at: datetime | None = None


class CityOut(BaseModel):
    name: str
    restaurants_count: int


class CatalogPromo(BaseModel):
    id: int
    title: str


class CatalogBrand(BaseModel):
    id: int
    name: str
    color: str
    logo_url: str | None = None
    restaurants_count: int
    promotions: list[CatalogPromo]


# --- статусы товаров ---

class ItemStatusOut(BaseModel):
    id: int
    name: str
    # available | unavailable | maybe_gone | maybe_appeared | disputed | unknown
    status: str
    yes_count: int
    no_count: int
    on_site_count: int = 0
    delivery_count: int = 0
    last_report_at: datetime | None = None


class PromotionWithStatuses(BaseModel):
    id: int
    title: str
    description: str | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    items: list[ItemStatusOut]


class RestaurantShort(ORMModel):
    id: int
    brand: BrandShort
    title: str | None = None
    city: str
    address: str
    lat: float
    lng: float


class RestaurantDetail(BaseModel):
    id: int
    brand: BrandShort
    title: str | None = None
    city: str
    address: str
    lat: float
    lng: float
    promotions: list[PromotionWithStatuses]


class FeedEntry(BaseModel):
    restaurant: RestaurantShort
    promotions: list[PromotionWithStatuses]


# --- reports ---

class ReportItemIn(BaseModel):
    promotion_item_id: int
    is_available: bool


class ReportIn(BaseModel):
    restaurant_id: int
    promotion_id: int
    items: list[ReportItemIn] = Field(min_length=1)
    channel: ReportChannel = ReportChannel.on_site
    lat: float | None = None
    lng: float | None = None
    # Строка из QR-кода чека: превращает отчёт в подтверждённый и даёт
    # силу фракции на точке (игровой режим)
    receipt_qr: str | None = Field(default=None, max_length=300)


class ReportItemOut(BaseModel):
    promotion_item_id: int
    name: str
    is_available: bool


class CaptureOut(BaseModel):
    """Что дал чек: вклад, очки и изменившееся состояние точки."""

    strength: float
    points: int
    faction: Faction
    owner: Faction | None = None
    captured: bool = False
    defended: bool = False
    refuted_denials: int = 0


class ReportOut(BaseModel):
    id: int
    restaurant: RestaurantShort
    promotion_title: str
    items: list[ReportItemOut]
    is_receipt_verified: bool = False
    capture: CaptureOut | None = None
    created_at: datetime


# --- suggestions ---

class SuggestionIn(BaseModel):
    brand_id: int | None = None
    brand_name_raw: str | None = Field(default=None, max_length=120)
    restaurant_id: int | None = None
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    items_raw: str = Field(min_length=1)


class SuggestionOut(ORMModel):
    id: int
    brand_id: int | None = None
    brand_name_raw: str | None = None
    restaurant_id: int | None = None
    title: str
    description: str | None = None
    items_raw: str
    status: SuggestionStatus
    moderator_comment: str | None = None
    created_promotion_id: int | None = None
    created_at: datetime
    reviewed_at: datetime | None = None


# --- restaurant suggestions ---

class RestaurantSuggestionIn(BaseModel):
    brand_id: int  # бренд — только из списка
    title: str | None = Field(default=None, max_length=200)
    city: str = Field(min_length=1, max_length=100)
    address: str = Field(min_length=1, max_length=300)
    lat: float
    lng: float
    comment: str | None = None


class RestaurantSuggestionOut(ORMModel):
    id: int
    brand: BrandShort
    title: str | None = None
    city: str
    address: str
    lat: float
    lng: float
    comment: str | None = None
    status: SuggestionStatus
    moderator_comment: str | None = None
    created_restaurant_id: int | None = None
    created_at: datetime
    reviewed_at: datetime | None = None


class AdminRestaurantSuggestionOut(RestaurantSuggestionOut):
    user: UserOut


class RestaurantSuggestionGroupOut(BaseModel):
    brand_id: int
    brand_name: str
    brand_color: str
    suggestions: list[AdminRestaurantSuggestionOut]


class RestaurantSuggestionApproveIn(BaseModel):
    brand_id: int
    title: str | None = Field(default=None, max_length=200)
    city: str = Field(min_length=1, max_length=100)
    address: str = Field(min_length=1, max_length=300)
    lat: float
    lng: float


# --- admin: brands ---

class BrandIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    slug: str | None = Field(default=None, max_length=120)
    color: str = Field(default="#6B9080", pattern=r"^#[0-9a-fA-F]{6}$")
    logo_url: str | None = Field(default=None, max_length=500)


class BrandPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    slug: str | None = Field(default=None, max_length=120)
    color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    logo_url: str | None = Field(default=None, max_length=500)


class AdminBrandOut(BrandOut):
    created_at: datetime
    restaurants_count: int = 0


# --- admin: restaurants ---

class RestaurantIn(BaseModel):
    brand_id: int
    title: str | None = Field(default=None, max_length=200)
    city: str = Field(min_length=1, max_length=100)
    address: str = Field(min_length=1, max_length=300)
    lat: float
    lng: float
    is_active: bool = True
    # Смещение часов кассы от UTC: время в QR чека местное и без зоны
    utc_offset_minutes: int = Field(default=180, ge=-720, le=840)


class RestaurantPatch(BaseModel):
    brand_id: int | None = None
    title: str | None = Field(default=None, max_length=200)
    city: str | None = Field(default=None, min_length=1, max_length=100)
    address: str | None = Field(default=None, min_length=1, max_length=300)
    lat: float | None = None
    lng: float | None = None
    is_active: bool | None = None
    utc_offset_minutes: int | None = Field(default=None, ge=-720, le=840)


class AdminRestaurantOut(ORMModel):
    id: int
    brand: BrandShort
    title: str | None = None
    city: str
    address: str
    lat: float
    lng: float
    is_active: bool
    utc_offset_minutes: int = 180
    created_at: datetime


# --- admin: promotions ---

class PromotionItemIn(BaseModel):
    id: int | None = None  # при PATCH: с id — обновить, без id — создать
    name: str = Field(min_length=1, max_length=200)


class PromotionIn(BaseModel):
    brand_id: int
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    is_active: bool = True
    items: list[PromotionItemIn] = Field(min_length=1)


class PromotionPatch(BaseModel):
    brand_id: int | None = None
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    is_active: bool | None = None
    items: list[PromotionItemIn] | None = Field(default=None, min_length=1)


class PromotionItemOut(ORMModel):
    id: int
    name: str
    sort_order: int


class AdminPromotionOut(ORMModel):
    id: int
    brand: BrandShort
    title: str
    description: str | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    is_active: bool
    created_at: datetime
    items: list[PromotionItemOut]


# --- admin: users ---

class AdminUserOut(UserOut):
    reports_count: int = 0


class UserPatch(BaseModel):
    role: UserRole | None = None
    is_blocked: bool | None = None
    display_name: str | None = Field(default=None, min_length=1, max_length=100)


# --- admin: suggestions ---

class AdminSuggestionOut(SuggestionOut):
    user: UserOut
    restaurant: RestaurantShort | None = None


class SuggestionGroupOut(BaseModel):
    brand_id: int | None = None
    brand_name: str
    brand_color: str | None = None
    suggestions: list[AdminSuggestionOut]


class SuggestionApproveIn(BaseModel):
    brand_id: int
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    items: list[str] = Field(min_length=1)


class SuggestionRejectIn(BaseModel):
    moderator_comment: str = Field(min_length=1)
    # Пометка «выдумка/спам» — штраф автору в рейтинге;
    # обычный дубликат штрафовать нельзя
    is_spam: bool = False


# --- subscriptions ---

class PromotionShort(ORMModel):
    id: int
    title: str
    brand: BrandShort


class SubscriptionIn(BaseModel):
    restaurant_id: int | None = None
    promotion_id: int | None = None


class SubscriptionOut(ORMModel):
    id: int
    restaurant: RestaurantShort | None = None
    promotion: PromotionShort | None = None
    created_at: datetime


# --- rating ---

class RatingEntryOut(BaseModel):
    user_id: int
    display_name: str
    points: int
    reports_count: int
    pioneers_count: int
    position: int


class RatingMeOut(BaseModel):
    position: int | None = None
    points: int


class RatingOut(BaseModel):
    entries: list[RatingEntryOut]
    me: RatingMeOut | None = None


class RatingCategoryOut(BaseModel):
    type: str
    count: int
    points: int


class RatingEventOut(BaseModel):
    type: str
    points: int
    city: str | None = None
    context: str | None = None
    created_at: datetime


class RatingCardOut(BaseModel):
    user_id: int
    display_name: str
    total_points: int
    categories: list[RatingCategoryOut]
    # Полная лента — только владельцу карточки
    events: list[RatingEventOut] | None = None


# --- игровой режим ---

class FactionInfoOut(BaseModel):
    key: Faction
    title: str
    members: int
    share: float          # доля в городе, 0..1
    join_blocked: bool    # набор закрыт: сторона перекошена
    underdog_bonus: float  # прибавка к силе чека, 0..0.25


class GameMeOut(BaseModel):
    game_mode: bool
    asked: bool
    faction: Faction | None = None
    can_switch_at: datetime | None = None


class GameConfigOut(BaseModel):
    enabled: bool                # фича включена на сервисе
    city: str | None = None
    season: str
    factions: list[FactionInfoOut]
    me: GameMeOut | None = None
    bar_seconds: int
    min_sum_rubles: int
    receipt_max_age_minutes: int
    geo_radius_m: float


class GameModeIn(BaseModel):
    enabled: bool


class FactionJoinIn(BaseModel):
    faction: Faction


class PointControlOut(BaseModel):
    restaurant_id: int
    owner: Faction | None = None
    green_score: float
    purple_score: float
    green_receipts: int
    purple_receipts: int
    green_progress: float   # 0..1
    purple_progress: float
    leader: Faction | None = None
    under_attack: bool
    eta_seconds: float | None = None
    is_active_now: bool
    truce_seconds: float | None = None
    captured_at: datetime | None = None


class PointControlDetailOut(PointControlOut):
    my_receipts_today: int = 0
    my_strength_today: float = 0.0
    my_faction: Faction | None = None


class FactionStandingOut(BaseModel):
    faction: Faction
    title: str
    points_held: int
    held_share: float   # средняя доля владения за сезон, 0..1
    captures: int
    defends: int


class GameStandingsOut(BaseModel):
    city: str
    season: str
    points_total: int
    neutral: int
    standings: list[FactionStandingOut]
