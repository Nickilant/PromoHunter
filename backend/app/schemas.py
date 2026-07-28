from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import SuggestionStatus, UserRole
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


class UserOut(ORMModel):
    id: int
    phone: str
    is_phone_verified: bool
    display_name: str
    city: str | None = None
    role: UserRole
    is_blocked: bool
    created_at: datetime


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
    status: str  # available | unavailable | disputed | unknown
    yes_count: int
    no_count: int
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
    lat: float | None = None
    lng: float | None = None


class ReportItemOut(BaseModel):
    promotion_item_id: int
    name: str
    is_available: bool


class ReportOut(BaseModel):
    id: int
    restaurant: RestaurantShort
    promotion_title: str
    items: list[ReportItemOut]
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


class RestaurantPatch(BaseModel):
    brand_id: int | None = None
    title: str | None = Field(default=None, max_length=200)
    city: str | None = Field(default=None, min_length=1, max_length=100)
    address: str | None = Field(default=None, min_length=1, max_length=300)
    lat: float | None = None
    lng: float | None = None
    is_active: bool | None = None


class AdminRestaurantOut(ORMModel):
    id: int
    brand: BrandShort
    title: str | None = None
    city: str
    address: str
    lat: float
    lng: float
    is_active: bool
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
