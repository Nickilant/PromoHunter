import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, joinedload, selectinload

from app.auth import require_admin
from app.database import get_db
from app.config import settings
from app.services.notify import (
    notify_new_promotion,
    notify_promotion_deleted,
    notify_promotion_update,
)
from app.services.promo_scope import describe_scope, promotion_visible_in
from app.services.scope import (
    Scope,
    city_filter,
    city_key,
    normalize_city,
    require_staff,
)
from app.models import (
    Brand,
    City,
    ModeratorCity,
    Promotion,
    PromotionCity,
    PromotionCityMode,
    PromotionItem,
    PromotionSuggestion,
    RatingEvent,
    Report,
    Restaurant,
    RestaurantSuggestion,
    Subscription,
    SuggestionStatus,
    User,
    UserRole,
)
from app.schemas import (
    AdminBrandOut,
    AdminCityOut,
    AdminPromotionOut,
    AdminRestaurantOut,
    AdminRestaurantSuggestionOut,
    AdminSuggestionOut,
    AdminUserOut,
    BrandIn,
    BrandPatch,
    CityBulkIn,
    CityBulkOut,
    CityIn,
    CityPatch,
    PromotionCityToggleIn,
    PromotionIn,
    PromotionPatch,
    RestaurantIn,
    RestaurantPatch,
    RestaurantSuggestionApproveIn,
    RestaurantSuggestionGroupOut,
    StaffScopeOut,
    SuggestionApproveIn,
    SuggestionGroupOut,
    SuggestionRejectIn,
    UserPatch,
)

# В админку пускаем и глобального админа, и городского модератора;
# что именно ему доступно, решает Scope в каждом обработчике
router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_staff)])


@router.get("/scope", response_model=StaffScopeOut)
def my_scope(scope: Scope = Depends(require_staff), db: Session = Depends(get_db)):
    """Кто я в админке — по этому интерфейс прячет недоступные разделы."""
    cities: list[str] = []
    if not scope.is_global:
        cities = sorted(
            db.scalars(
                select(ModeratorCity.city).where(
                    ModeratorCity.user_id == scope.user.id
                )
            ).all()
        )
    return StaffScopeOut(
        role=scope.user.role, is_global=scope.is_global, cities=cities
    )

_TRANSLIT = str.maketrans(
    "абвгдеёжзийклмнопрстуфхцчшщъыьэюя",
    "abvgdeejziyklmnoprstufhccss'y'eua",
)


def slugify(name: str) -> str:
    slug = name.lower().translate(_TRANSLIT)
    slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")
    return slug or "brand"


# --- brands ---

MAX_LOGO_BYTES = 5 * 1024 * 1024
LOGO_SIGNATURES = {
    "image/png": (b"\x89PNG\r\n\x1a\n", ".png"),
    "image/jpeg": (b"\xff\xd8\xff", ".jpg"),
    "image/webp": (b"RIFF", ".webp"),
}


@router.post("/brand-logos", status_code=status.HTTP_201_CREATED)
def upload_brand_logo(
    logo: UploadFile = File(...),
    scope: Scope = Depends(require_staff),
):
    scope.require_global("Управление брендами")
    signature = LOGO_SIGNATURES.get(logo.content_type or "")
    if signature is None:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Поддерживаются только PNG, JPEG и WebP",
        )
    content = logo.file.read(MAX_LOGO_BYTES + 1)
    if not content:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Файл логотипа пуст")
    if len(content) > MAX_LOGO_BYTES:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Логотип должен быть не больше 5 МБ",
        )
    magic, extension = signature
    valid = content.startswith(magic)
    if logo.content_type == "image/webp":
        valid = valid and len(content) >= 12 and content[8:12] == b"WEBP"
    if not valid:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Содержимое файла не соответствует формату")

    directory = Path(settings.upload_dir) / "brand-logos"
    directory.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid4().hex}{extension}"
    (directory / filename).write_bytes(content)
    return {"logo_url": f"/api/uploads/brand-logos/{filename}"}

def _brand_out(db: Session, brand: Brand) -> AdminBrandOut:
    count = db.scalar(
        select(func.count(Restaurant.id)).where(Restaurant.brand_id == brand.id)
    )
    out = AdminBrandOut.model_validate(brand)
    out.restaurants_count = count or 0
    return out


@router.get("/brands", response_model=list[AdminBrandOut])
def admin_brands(db: Session = Depends(get_db)):
    counts = dict(
        db.execute(
            select(Restaurant.brand_id, func.count(Restaurant.id)).group_by(
                Restaurant.brand_id
            )
        ).all()
    )
    brands = db.scalars(select(Brand).order_by(Brand.name)).all()
    result = []
    for brand in brands:
        out = AdminBrandOut.model_validate(brand)
        out.restaurants_count = counts.get(brand.id, 0)
        result.append(out)
    return result


@router.post("/brands", response_model=AdminBrandOut, status_code=status.HTTP_201_CREATED)
def create_brand(
    payload: BrandIn,
    db: Session = Depends(get_db),
    scope: Scope = Depends(require_staff),
):
    scope.require_global("Управление брендами")
    name = payload.name.strip()
    if db.scalar(select(Brand).where(func.lower(Brand.name) == name.lower())):
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Бренд с таким названием уже есть")
    brand = Brand(
        name=name,
        slug=(payload.slug or "").strip() or slugify(name),
        color=payload.color,
        logo_url=payload.logo_url,
        is_public=payload.is_public,
    )
    db.add(brand)
    db.commit()
    db.refresh(brand)
    return _brand_out(db, brand)


@router.patch("/brands/{brand_id}", response_model=AdminBrandOut)
def update_brand(
    brand_id: int,
    payload: BrandPatch,
    db: Session = Depends(get_db),
    scope: Scope = Depends(require_staff),
):
    scope.require_global("Управление брендами")
    brand = db.get(Brand, brand_id)
    if brand is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Бренд не найден")
    data = payload.model_dump(exclude_unset=True)
    if "name" in data:
        name = data["name"].strip()
        conflict = db.scalar(
            select(Brand).where(func.lower(Brand.name) == name.lower(), Brand.id != brand_id)
        )
        if conflict:
            raise HTTPException(status.HTTP_409_CONFLICT, detail="Бренд с таким названием уже есть")
        brand.name = name
    if "slug" in data and data["slug"]:
        brand.slug = data["slug"].strip()
    if "color" in data and data["color"]:
        brand.color = data["color"]
    if "logo_url" in data:
        brand.logo_url = data["logo_url"]
    if "is_public" in data and data["is_public"] is not None:
        brand.is_public = data["is_public"]
    db.commit()
    db.refresh(brand)
    return _brand_out(db, brand)


@router.delete("/brands/{brand_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_brand(
    brand_id: int,
    db: Session = Depends(get_db),
    scope: Scope = Depends(require_staff),
):
    scope.require_global("Управление брендами")
    brand = db.get(Brand, brand_id)
    if brand is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Бренд не найден")
    restaurants = db.scalar(
        select(func.count(Restaurant.id)).where(Restaurant.brand_id == brand_id)
    )
    if restaurants:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="У бренда есть рестораны — сначала удалите или перенесите их",
        )
    db.delete(brand)
    db.commit()


# --- cities ---

SPLIT_CITIES = re.compile(r"[\n,;]+")


def _city_counts(db: Session) -> dict[str, int]:
    """Сколько активных точек в каждом городе — по нормализованному ключу."""
    rows = db.execute(
        select(Restaurant.city, func.count(Restaurant.id))
        .where(Restaurant.is_active.is_(True))
        .group_by(Restaurant.city)
    ).all()
    counts: dict[str, int] = {}
    for city, count in rows:
        counts[city_key(city)] = counts.get(city_key(city), 0) + count
    return counts


@router.get("/cities", response_model=list[AdminCityOut])
def admin_cities(db: Session = Depends(get_db), scope: Scope = Depends(require_staff)):
    """Справочник городов. Модератор видит только свои — чужие ему не нужны."""
    counts = _city_counts(db)
    cities = db.scalars(select(City).order_by(City.name)).all()
    if scope.cities is not None:
        allowed = {city_key(c) for c in scope.cities}
        cities = [c for c in cities if c.key in allowed]
    result = []
    for city in cities:
        out = AdminCityOut.model_validate(city)
        out.restaurants_count = counts.get(city.key, 0)
        result.append(out)
    return result


@router.post("/cities", response_model=AdminCityOut, status_code=status.HTTP_201_CREATED)
def create_city(
    payload: CityIn,
    db: Session = Depends(get_db),
    scope: Scope = Depends(require_staff),
):
    scope.require_global("Управление городами")
    name = normalize_city(payload.name)
    if not name:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Название города пустое")
    if db.scalar(select(City).where(City.key == city_key(name))):
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Такой город уже есть")
    city = City(name=name, key=city_key(name))
    db.add(city)
    db.commit()
    db.refresh(city)
    out = AdminCityOut.model_validate(city)
    out.restaurants_count = _city_counts(db).get(city.key, 0)
    return out


@router.post("/cities/bulk", response_model=CityBulkOut)
def create_cities_bulk(
    payload: CityBulkIn,
    db: Session = Depends(get_db),
    scope: Scope = Depends(require_staff),
):
    """Пачка городов одним полем — их сотни, по одному добавлять невозможно."""
    scope.require_global("Управление городами")
    seen = {
        key for key in db.scalars(select(City.key))
    }
    added: list[str] = []
    skipped: list[str] = []
    for raw in SPLIT_CITIES.split(payload.names):
        name = normalize_city(raw)
        if not name:
            continue
        key = city_key(name)
        if key in seen:
            skipped.append(name)
            continue
        seen.add(key)
        db.add(City(name=name, key=key))
        added.append(name)
    db.commit()
    return CityBulkOut(added=added, skipped=skipped)


@router.patch("/cities/{city_id}", response_model=AdminCityOut)
def update_city(
    city_id: int,
    payload: CityPatch,
    db: Session = Depends(get_db),
    scope: Scope = Depends(require_staff),
):
    scope.require_global("Управление городами")
    city = db.get(City, city_id)
    if city is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Город не найден")
    data = payload.model_dump(exclude_unset=True)
    if "name" in data and data["name"]:
        name = normalize_city(data["name"])
        if not name:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Название города пустое")
        conflict = db.scalar(
            select(City).where(City.key == city_key(name), City.id != city_id)
        )
        if conflict:
            raise HTTPException(status.HTTP_409_CONFLICT, detail="Такой город уже есть")
        # Точки и модераторы хранят город строкой — переименование тянет их за собой
        db.execute(
            update(Restaurant).where(Restaurant.city == city.name).values(city=name)
        )
        db.execute(
            update(ModeratorCity).where(ModeratorCity.city == city.name).values(city=name)
        )
        city.name = name
        city.key = city_key(name)
    if "is_active" in data and data["is_active"] is not None:
        city.is_active = data["is_active"]
    db.commit()
    db.refresh(city)
    out = AdminCityOut.model_validate(city)
    out.restaurants_count = _city_counts(db).get(city.key, 0)
    return out


@router.delete("/cities/{city_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_city(
    city_id: int,
    db: Session = Depends(get_db),
    scope: Scope = Depends(require_staff),
):
    scope.require_global("Управление городами")
    city = db.get(City, city_id)
    if city is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Город не найден")
    if _city_counts(db).get(city.key, 0):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="В городе есть точки — удалите их или выключите город",
        )
    db.delete(city)
    db.commit()


# --- restaurants ---

@router.get("/restaurants", response_model=list[AdminRestaurantOut])
def admin_restaurants(
    brand_id: int | None = None,
    db: Session = Depends(get_db),
    scope: Scope = Depends(require_staff),
):
    stmt = (
        select(Restaurant)
        .options(joinedload(Restaurant.brand))
        .order_by(Restaurant.id.desc())
    )
    if brand_id is not None:
        stmt = stmt.where(Restaurant.brand_id == brand_id)
    mine = city_filter(scope, Restaurant.city)
    if mine is not None:
        stmt = stmt.where(mine)
    return db.scalars(stmt).unique().all()


@router.post(
    "/restaurants", response_model=AdminRestaurantOut, status_code=status.HTTP_201_CREATED
)
def create_restaurant(
    payload: RestaurantIn,
    db: Session = Depends(get_db),
    scope: Scope = Depends(require_staff),
):
    if db.get(Brand, payload.brand_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Бренд не найден")
    data = payload.model_dump()
    data["city"] = normalize_city(data["city"])
    scope.require(data["city"], "Город точки")
    restaurant = Restaurant(**data)
    db.add(restaurant)
    db.commit()
    db.refresh(restaurant)
    return restaurant


@router.patch("/restaurants/{restaurant_id}", response_model=AdminRestaurantOut)
def update_restaurant(
    restaurant_id: int,
    payload: RestaurantPatch,
    db: Session = Depends(get_db),
    scope: Scope = Depends(require_staff),
):
    restaurant = db.get(Restaurant, restaurant_id)
    if restaurant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Точка не найдена")
    # Проверяем и текущий город, и новый: иначе точку можно было бы
    # «увезти» из своей зоны ответственности в чужую
    scope.require(restaurant.city, "Точка")
    data = payload.model_dump(exclude_unset=True)
    if "brand_id" in data and db.get(Brand, data["brand_id"]) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Бренд не найден")
    if data.get("city"):
        data["city"] = normalize_city(data["city"])
        scope.require(data["city"], "Новый город точки")
    for key, value in data.items():
        setattr(restaurant, key, value)
    db.commit()
    db.refresh(restaurant)
    return restaurant


@router.delete("/restaurants/{restaurant_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_restaurant(
    restaurant_id: int,
    db: Session = Depends(get_db),
    scope: Scope = Depends(require_staff),
):
    restaurant = db.get(Restaurant, restaurant_id)
    if restaurant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Точка не найдена")
    scope.require(restaurant.city, "Точка")
    db.delete(restaurant)
    db.commit()


# --- promotions ---

def _load_promotion(db: Session, promotion_id: int) -> Promotion:
    promotion = db.scalar(
        select(Promotion)
        .options(
            joinedload(Promotion.brand),
            selectinload(Promotion.items),
            selectinload(Promotion.cities),
        )
        # populate_existing — иначе после правки охвата вернулась бы уже
        # загруженная в сессии коллекция городов, то есть прежняя
        .execution_options(populate_existing=True)
        .where(Promotion.id == promotion_id)
    )
    if promotion is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Акция не найдена")
    return promotion


def _promo_editable_by(promotion: Promotion, scope: Scope) -> bool:
    """Модератор правит саму акцию, только если она целиком его.

    Федеральную акцию менять нельзя — она видна и в чужих городах; у неё
    модератору доступен лишь свой город в охвате (см. ручку /cities).
    """
    if scope.is_global:
        return True
    if promotion.city_mode != PromotionCityMode.include:
        return False
    listed = {city_key(row.city) for row in promotion.cities}
    return bool(listed) and listed <= (scope.cities or set())


def _promo_out(promotion: Promotion, scope: Scope) -> AdminPromotionOut:
    out = AdminPromotionOut.model_validate(promotion)
    out.scope_cities = sorted(row.city for row in promotion.cities)
    out.scope_label = describe_scope(promotion)
    out.can_edit = _promo_editable_by(promotion, scope)
    return out


def _apply_scope(
    db: Session, promotion: Promotion, mode: PromotionCityMode, cities: list[str]
) -> None:
    """Переписать охват акции целиком (доступно глобальному админу)."""
    promotion.city_mode = mode
    wanted: dict[str, str] = {}
    for raw in cities:
        name = normalize_city(raw)
        if name:
            wanted.setdefault(city_key(name), name)
    db.query(PromotionCity).filter(
        PromotionCity.promotion_id == promotion.id
    ).delete(synchronize_session=False)
    for name in wanted.values():
        db.add(PromotionCity(promotion_id=promotion.id, city=name))


@router.get("/promotions", response_model=list[AdminPromotionOut])
def admin_promotions(
    brand_id: int | None = None,
    is_active: bool | None = None,
    db: Session = Depends(get_db),
    scope: Scope = Depends(require_staff),
):
    stmt = (
        select(Promotion)
        .options(
            joinedload(Promotion.brand),
            selectinload(Promotion.items),
            selectinload(Promotion.cities),
        )
        .order_by(Promotion.created_at.desc())
    )
    if brand_id is not None:
        stmt = stmt.where(Promotion.brand_id == brand_id)
    if is_active is not None:
        stmt = stmt.where(Promotion.is_active.is_(is_active))
    promotions = db.scalars(stmt).unique().all()

    if not scope.is_global:
        # Модератору показываем то, что видно в его городах: и федеральные
        # акции тоже — их он может убрать из своего города
        promotions = [
            p
            for p in promotions
            if any(promotion_visible_in(p, city) for city in _scope_city_names(db, scope))
        ]
    return [_promo_out(p, scope) for p in promotions]


def _scope_city_names(db: Session, scope: Scope) -> list[str]:
    """Отображаемые названия городов модератора (не ключи сравнения)."""
    if scope.is_global:
        return []
    return list(
        db.scalars(
            select(ModeratorCity.city).where(ModeratorCity.user_id == scope.user.id)
        ).all()
    )


@router.post(
    "/promotions", response_model=AdminPromotionOut, status_code=status.HTTP_201_CREATED
)
def create_promotion(
    payload: PromotionIn,
    db: Session = Depends(get_db),
    scope: Scope = Depends(require_staff),
):
    if db.get(Brand, payload.brand_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Бренд не найден")

    mode, cities = payload.scope.mode, list(payload.scope.cities)
    if not scope.is_global:
        # Модератор заводит акцию только для своих городов и только режимом
        # «только в списке» — федеральную создавать он не вправе
        mode = PromotionCityMode.include
        cities = [c for c in cities if scope.allows(c)] or _scope_city_names(db, scope)
        if not cities:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail="У вас нет городов, для которых можно завести акцию",
            )
    _require_scope_allowed(scope, mode, cities)

    promotion = Promotion(
        brand_id=payload.brand_id,
        title=payload.title.strip(),
        description=payload.description,
        starts_at=payload.starts_at,
        ends_at=payload.ends_at,
        is_active=payload.is_active,
        created_by_id=scope.user.id,
        items=[
            PromotionItem(name=item.name.strip(), sort_order=i)
            for i, item in enumerate(payload.items)
        ],
    )
    db.add(promotion)
    db.flush()
    _apply_scope(db, promotion, mode, cities)
    db.commit()
    promotion = _load_promotion(db, promotion.id)
    if _is_currently_active(promotion):
        notify_new_promotion(db, promotion)
    return _promo_out(promotion, scope)


def _require_scope_allowed(
    scope: Scope, mode: PromotionCityMode, cities: list[str]
) -> None:
    """Модератор не может выйти охватом за свои города."""
    if scope.is_global:
        return
    if mode != PromotionCityMode.include:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Федеральные акции заводит только глобальный администратор",
        )
    for city in cities:
        scope.require(city, "Город акции")


def _is_currently_active(promotion: Promotion) -> bool:
    now = datetime.now(timezone.utc)
    return (
        promotion.is_active
        and (promotion.starts_at is None or promotion.starts_at <= now)
        and (promotion.ends_at is None or promotion.ends_at >= now)
    )


@router.patch("/promotions/{promotion_id}", response_model=AdminPromotionOut)
def update_promotion(
    promotion_id: int,
    payload: PromotionPatch,
    db: Session = Depends(get_db),
    scope: Scope = Depends(require_staff),
):
    promotion = _load_promotion(db, promotion_id)
    if not _promo_editable_by(promotion, scope):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail=(
                "Эта акция идёт не только в ваших городах — менять её условия "
                "может глобальный администратор. Свой город можно убрать "
                "из охвата отдельной кнопкой."
            ),
        )
    was_active = _is_currently_active(promotion)
    data = payload.model_dump(exclude_unset=True)
    if "brand_id" in data and db.get(Brand, data["brand_id"]) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Бренд не найден")
    changed = any(
        key in data and getattr(promotion, key) != data[key]
        for key in ("title", "description", "starts_at", "ends_at", "is_active")
    ) or payload.items is not None
    for key in ("brand_id", "title", "description", "starts_at", "ends_at", "is_active"):
        if key in data:
            setattr(promotion, key, data[key])

    if payload.items is not None:
        # Синхронизация: с id — обновить, без id — создать, отсутствующие — удалить
        existing = {item.id: item for item in promotion.items}
        sent_ids = {item.id for item in payload.items if item.id is not None}
        unknown = sent_ids - existing.keys()
        if unknown:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, detail="Товар не относится к этой акции"
            )
        new_items: list[PromotionItem] = []
        for i, item in enumerate(payload.items):
            if item.id is not None:
                obj = existing[item.id]
                obj.name = item.name.strip()
                obj.sort_order = i
                new_items.append(obj)
            else:
                new_items.append(PromotionItem(name=item.name.strip(), sort_order=i))
        promotion.items = new_items

    if payload.scope is not None:
        _require_scope_allowed(scope, payload.scope.mode, payload.scope.cities)
        _apply_scope(db, promotion, payload.scope.mode, payload.scope.cities)
        changed = True

    db.commit()
    promotion = _load_promotion(db, promotion_id)

    # Уведомления подписчикам: акция появилась / изменилась / завершилась
    is_active_now = _is_currently_active(promotion)
    if not was_active and is_active_now:
        notify_new_promotion(db, promotion)
    elif was_active and not is_active_now:
        notify_promotion_update(db, promotion, "акция завершена")
    elif changed and is_active_now:
        notify_promotion_update(db, promotion, "условия акции обновились")
    return _promo_out(promotion, scope)


@router.post("/promotions/{promotion_id}/cities", response_model=AdminPromotionOut)
def toggle_promotion_city(
    promotion_id: int,
    payload: PromotionCityToggleIn,
    db: Session = Depends(get_db),
    scope: Scope = Depends(require_staff),
):
    """Добавить или убрать один город из охвата акции.

    Ради этого всё и затевалось: городской модератор может сказать «у нас
    этой акции нет», не трогая её в остальной стране и не заводя список из
    всех городов вручную.
    """
    promotion = _load_promotion(db, promotion_id)
    city = normalize_city(payload.city)
    if not city:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Не указан город")
    scope.require(city, "Город")

    existing = next(
        (row for row in promotion.cities if city_key(row.city) == city_key(city)), None
    )
    if payload.listed and existing is None:
        db.add(PromotionCity(promotion_id=promotion.id, city=city))
    elif not payload.listed and existing is not None:
        db.delete(existing)
    db.commit()
    return _promo_out(_load_promotion(db, promotion_id), scope)


@router.delete("/promotions/{promotion_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_promotion(
    promotion_id: int,
    db: Session = Depends(get_db),
    scope: Scope = Depends(require_staff),
):
    promotion = db.scalar(
        select(Promotion)
        .options(joinedload(Promotion.brand), selectinload(Promotion.cities))
        .where(Promotion.id == promotion_id)
    )
    if promotion is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Акция не найдена")
    if not _promo_editable_by(promotion, scope):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Удалить акцию, идущую не только в ваших городах, нельзя",
        )
    # Чаты подписчиков собираем до каскадного удаления подписок
    subscriber_chats = list(
        db.scalars(
            select(User.telegram_id)
            .join(Subscription, Subscription.user_id == User.id)
            .where(
                Subscription.promotion_id == promotion_id,
                User.telegram_id.is_not(None),
                User.is_blocked.is_(False),
            )
        )
    )
    title, brand_name = promotion.title, promotion.brand.name
    # Каскадом уходят items, отчёты и подписки (FK ondelete=CASCADE)
    db.delete(promotion)
    db.commit()
    notify_promotion_deleted(subscriber_chats, title, brand_name)


# --- users ---

@router.get("/users", response_model=list[AdminUserOut])
def admin_users(db: Session = Depends(get_db), scope: Scope = Depends(require_staff)):
    # Блокировка и роли действуют на всю страну, поэтому раздел глобальный
    scope.require_global("Управление пользователями")
    counts = dict(
        db.execute(
            select(Report.user_id, func.count(Report.id)).group_by(Report.user_id)
        ).all()
    )
    cities: dict[int, list[str]] = {}
    for user_id, city in db.execute(
        select(ModeratorCity.user_id, ModeratorCity.city).order_by(ModeratorCity.city)
    ).all():
        cities.setdefault(user_id, []).append(city)

    users = db.scalars(select(User).order_by(User.created_at)).all()
    result = []
    for user in users:
        out = AdminUserOut.model_validate(user)
        out.reports_count = counts.get(user.id, 0)
        out.moderator_cities = cities.get(user.id, [])
        result.append(out)
    return result


@router.patch("/users/{user_id}", response_model=AdminUserOut)
def update_user(
    user_id: int,
    payload: UserPatch,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Пользователь не найден")
    data = payload.model_dump(exclude_unset=True)
    if user.id == admin.id and (
        data.get("is_blocked") is True or data.get("role") in ("user", "moderator")
    ):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Нельзя заблокировать или разжаловать самого себя",
        )

    cities = data.pop("moderator_cities", None)
    for key, value in data.items():
        setattr(user, key, value)

    if cities is not None:
        _set_moderator_cities(db, user, cities)
    # Разжаловали модератора — города за ним висеть не должны
    if user.role != UserRole.moderator:
        db.query(ModeratorCity).filter(ModeratorCity.user_id == user.id).delete(
            synchronize_session=False
        )

    db.commit()
    db.refresh(user)
    out = AdminUserOut.model_validate(user)
    out.reports_count = (
        db.scalar(select(func.count(Report.id)).where(Report.user_id == user.id)) or 0
    )
    out.moderator_cities = sorted(
        db.scalars(
            select(ModeratorCity.city).where(ModeratorCity.user_id == user.id)
        ).all()
    )
    return out


def _set_moderator_cities(db: Session, user: User, cities: list[str]) -> None:
    """Заменить список городов модератора целиком."""
    wanted: dict[str, str] = {}
    for raw in cities:
        name = normalize_city(raw)
        if name:
            wanted.setdefault(city_key(name), name)
    db.query(ModeratorCity).filter(ModeratorCity.user_id == user.id).delete(
        synchronize_session=False
    )
    for name in wanted.values():
        db.add(ModeratorCity(user_id=user.id, city=name))


# --- suggestions ---

@router.get("/suggestions", response_model=list[SuggestionGroupOut])
def admin_suggestions(
    status_filter: SuggestionStatus | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    scope: Scope = Depends(require_staff),
):
    stmt = (
        select(PromotionSuggestion)
        .options(
            joinedload(PromotionSuggestion.user),
            joinedload(PromotionSuggestion.reviewed_by),
            joinedload(PromotionSuggestion.brand),
            joinedload(PromotionSuggestion.restaurant).joinedload(Restaurant.brand),
        )
        .order_by(PromotionSuggestion.created_at.desc())
    )
    if status_filter is not None:
        stmt = stmt.where(PromotionSuggestion.status == status_filter)
    mine = city_filter(scope, PromotionSuggestion.city)
    if mine is not None:
        stmt = stmt.where(mine)
    suggestions = db.scalars(stmt).unique().all()

    # Группировка: по brand_id, а для заявок без бренда — по brand_name_raw
    # без учёта регистра
    groups: dict[tuple, SuggestionGroupOut] = {}
    for s in suggestions:
        if s.brand_id is not None:
            key = ("brand", s.brand_id)
            name = s.brand.name
            color = s.brand.color
        else:
            raw = (s.brand_name_raw or "Без бренда").strip()
            key = ("raw", raw.lower())
            name = raw
            color = None
        group = groups.get(key)
        if group is None:
            group = SuggestionGroupOut(
                brand_id=s.brand_id, brand_name=name, brand_color=color, suggestions=[]
            )
            groups[key] = group
        group.suggestions.append(AdminSuggestionOut.model_validate(s))
    return list(groups.values())


@router.get(
    "/restaurant-suggestions", response_model=list[RestaurantSuggestionGroupOut]
)
def admin_restaurant_suggestions(
    status_filter: SuggestionStatus | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    scope: Scope = Depends(require_staff),
):
    stmt = (
        select(RestaurantSuggestion)
        .options(
            joinedload(RestaurantSuggestion.user),
            joinedload(RestaurantSuggestion.reviewed_by),
            joinedload(RestaurantSuggestion.brand),
        )
        .order_by(RestaurantSuggestion.created_at.desc())
    )
    if status_filter is not None:
        stmt = stmt.where(RestaurantSuggestion.status == status_filter)
    mine = city_filter(scope, RestaurantSuggestion.city)
    if mine is not None:
        stmt = stmt.where(mine)
    suggestions = db.scalars(stmt).unique().all()

    groups: dict[int, RestaurantSuggestionGroupOut] = {}
    for s in suggestions:
        group = groups.get(s.brand_id)
        if group is None:
            group = RestaurantSuggestionGroupOut(
                brand_id=s.brand_id,
                brand_name=s.brand.name,
                brand_color=s.brand.color,
                suggestions=[],
            )
            groups[s.brand_id] = group
        group.suggestions.append(AdminRestaurantSuggestionOut.model_validate(s))
    return list(groups.values())


@router.post(
    "/restaurant-suggestions/{suggestion_id}/approve",
    response_model=AdminRestaurantOut,
)
def approve_restaurant_suggestion(
    suggestion_id: int,
    payload: RestaurantSuggestionApproveIn,
    db: Session = Depends(get_db),
    scope: Scope = Depends(require_staff),
):
    suggestion = db.get(RestaurantSuggestion, suggestion_id)
    if suggestion is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Заявка не найдена")
    if suggestion.status != SuggestionStatus.pending:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Заявка уже рассмотрена")
    if db.get(Brand, payload.brand_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Бренд не найден")

    # Город приходит из тела запроса, поэтому проверяем оба: и город самой
    # заявки, и присланный — иначе чужую точку можно было бы завести,
    # подставив другой город
    city = normalize_city(payload.city)
    scope.require(suggestion.city, "Заявка")
    scope.require(city, "Город точки")

    restaurant = Restaurant(
        brand_id=payload.brand_id,
        title=(payload.title or "").strip() or None,
        city=city,
        address=payload.address.strip(),
        lat=payload.lat,
        lng=payload.lng,
    )
    db.add(restaurant)
    db.flush()

    suggestion.status = SuggestionStatus.approved
    suggestion.created_restaurant_id = restaurant.id
    suggestion.reviewed_at = datetime.now(timezone.utc)
    suggestion.reviewed_by_id = scope.user.id
    db.add(
        RatingEvent(
            user_id=suggestion.user_id,
            city=restaurant.city,
            type="restaurant_approved",
            points=settings.rating_suggestion_points,
            restaurant_suggestion_id=suggestion.id,
        )
    )
    db.commit()
    restaurant = db.scalar(
        select(Restaurant)
        .options(joinedload(Restaurant.brand))
        .where(Restaurant.id == restaurant.id)
    )
    return restaurant


@router.post(
    "/restaurant-suggestions/{suggestion_id}/reject",
    response_model=AdminRestaurantSuggestionOut,
)
def reject_restaurant_suggestion(
    suggestion_id: int,
    payload: SuggestionRejectIn,
    db: Session = Depends(get_db),
    scope: Scope = Depends(require_staff),
):
    suggestion = db.get(RestaurantSuggestion, suggestion_id)
    if suggestion is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Заявка не найдена")
    if suggestion.status != SuggestionStatus.pending:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Заявка уже рассмотрена")
    scope.require(suggestion.city, "Заявка")
    suggestion.status = SuggestionStatus.rejected
    suggestion.moderator_comment = payload.moderator_comment.strip()
    suggestion.reviewed_at = datetime.now(timezone.utc)
    suggestion.reviewed_by_id = scope.user.id
    if payload.is_spam:
        db.add(
            RatingEvent(
                user_id=suggestion.user_id,
                city=suggestion.city,
                type="restaurant_spam",
                points=settings.rating_spam_points,
                restaurant_suggestion_id=suggestion.id,
            )
        )
    db.commit()
    return db.scalar(
        select(RestaurantSuggestion)
        .options(
            joinedload(RestaurantSuggestion.user),
            joinedload(RestaurantSuggestion.reviewed_by),
            joinedload(RestaurantSuggestion.brand),
        )
        .where(RestaurantSuggestion.id == suggestion_id)
    )


@router.post("/suggestions/{suggestion_id}/approve", response_model=AdminPromotionOut)
def approve_suggestion(
    suggestion_id: int,
    payload: SuggestionApproveIn,
    db: Session = Depends(get_db),
    scope: Scope = Depends(require_staff),
):
    suggestion = db.get(PromotionSuggestion, suggestion_id)
    if suggestion is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Заявка не найдена")
    if suggestion.status != SuggestionStatus.pending:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Заявка уже рассмотрена")
    if db.get(Brand, payload.brand_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Бренд не найден")
    scope.require(suggestion.city, "Заявка")

    names = [name.strip() for name in payload.items if name.strip()]
    if not names:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Укажите хотя бы один товар")

    # Модератор одобряет заявку только для своих городов: акция принадлежит
    # бренду, и федеральной её вправе сделать лишь глобальный админ
    mode, cities = payload.scope.mode, list(payload.scope.cities)
    if not scope.is_global:
        mode = PromotionCityMode.include
        cities = [suggestion.city] if suggestion.city else _scope_city_names(db, scope)
    _require_scope_allowed(scope, mode, cities)

    promotion = Promotion(
        brand_id=payload.brand_id,
        title=(payload.title or suggestion.title).strip(),
        description=payload.description
        if payload.description is not None
        else suggestion.description,
        starts_at=payload.starts_at,
        ends_at=payload.ends_at,
        is_active=True,
        created_by_id=scope.user.id,
        items=[PromotionItem(name=name, sort_order=i) for i, name in enumerate(names)],
    )
    db.add(promotion)
    db.flush()
    _apply_scope(db, promotion, mode, cities)

    suggestion.status = SuggestionStatus.approved
    suggestion.created_promotion_id = promotion.id
    suggestion.reviewed_at = datetime.now(timezone.utc)
    suggestion.reviewed_by_id = scope.user.id

    # Рейтинг автору заявки: человек принёс в сервис целую акцию
    author = db.get(User, suggestion.user_id)
    restaurant = (
        db.get(Restaurant, suggestion.restaurant_id)
        if suggestion.restaurant_id
        else None
    )
    db.add(
        RatingEvent(
            user_id=suggestion.user_id,
            city=restaurant.city if restaurant else (author.city if author else None),
            type="suggestion_approved",
            points=settings.rating_suggestion_points,
            suggestion_id=suggestion.id,
        )
    )
    db.commit()
    promotion = _load_promotion(db, promotion.id)
    if _is_currently_active(promotion):
        notify_new_promotion(db, promotion)
    return _promo_out(promotion, scope)


@router.post("/suggestions/{suggestion_id}/reject", response_model=AdminSuggestionOut)
def reject_suggestion(
    suggestion_id: int,
    payload: SuggestionRejectIn,
    db: Session = Depends(get_db),
    scope: Scope = Depends(require_staff),
):
    suggestion = db.get(PromotionSuggestion, suggestion_id)
    if suggestion is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Заявка не найдена")
    if suggestion.status != SuggestionStatus.pending:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Заявка уже рассмотрена")
    scope.require(suggestion.city, "Заявка")
    suggestion.status = SuggestionStatus.rejected
    suggestion.moderator_comment = payload.moderator_comment.strip()
    suggestion.reviewed_at = datetime.now(timezone.utc)
    suggestion.reviewed_by_id = scope.user.id

    # Штраф только за «выдумку/спам» с явной пометкой модератора —
    # обычный дубликат не наказываем
    if payload.is_spam:
        author = db.get(User, suggestion.user_id)
        restaurant = (
            db.get(Restaurant, suggestion.restaurant_id)
            if suggestion.restaurant_id
            else None
        )
        db.add(
            RatingEvent(
                user_id=suggestion.user_id,
                city=restaurant.city if restaurant else (author.city if author else None),
                type="suggestion_spam",
                points=settings.rating_spam_points,
                suggestion_id=suggestion.id,
            )
        )
    db.commit()
    suggestion = db.scalar(
        select(PromotionSuggestion)
        .options(
            joinedload(PromotionSuggestion.user),
            joinedload(PromotionSuggestion.reviewed_by),
            joinedload(PromotionSuggestion.restaurant).joinedload(Restaurant.brand),
        )
        .where(PromotionSuggestion.id == suggestion_id)
    )
    return suggestion
