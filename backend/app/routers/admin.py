import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.auth import require_admin
from app.database import get_db
from app.config import settings
from app.models import (
    Brand,
    Promotion,
    PromotionItem,
    PromotionSuggestion,
    RatingEvent,
    Report,
    Restaurant,
    RestaurantSuggestion,
    SuggestionStatus,
    User,
)
from app.schemas import (
    AdminBrandOut,
    AdminPromotionOut,
    AdminRestaurantOut,
    AdminRestaurantSuggestionOut,
    AdminSuggestionOut,
    AdminUserOut,
    BrandIn,
    BrandPatch,
    PromotionIn,
    PromotionPatch,
    RestaurantIn,
    RestaurantPatch,
    RestaurantSuggestionApproveIn,
    RestaurantSuggestionGroupOut,
    SuggestionApproveIn,
    SuggestionGroupOut,
    SuggestionRejectIn,
    UserPatch,
)

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])

_TRANSLIT = str.maketrans(
    "абвгдеёжзийклмнопрстуфхцчшщъыьэюя",
    "abvgdeejziyklmnoprstufhccss'y'eua",
)


def slugify(name: str) -> str:
    slug = name.lower().translate(_TRANSLIT)
    slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")
    return slug or "brand"


# --- brands ---

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
def create_brand(payload: BrandIn, db: Session = Depends(get_db)):
    name = payload.name.strip()
    if db.scalar(select(Brand).where(func.lower(Brand.name) == name.lower())):
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Бренд с таким названием уже есть")
    brand = Brand(
        name=name,
        slug=(payload.slug or "").strip() or slugify(name),
        color=payload.color,
        logo_url=payload.logo_url,
    )
    db.add(brand)
    db.commit()
    db.refresh(brand)
    return _brand_out(db, brand)


@router.patch("/brands/{brand_id}", response_model=AdminBrandOut)
def update_brand(brand_id: int, payload: BrandPatch, db: Session = Depends(get_db)):
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
    db.commit()
    db.refresh(brand)
    return _brand_out(db, brand)


@router.delete("/brands/{brand_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_brand(brand_id: int, db: Session = Depends(get_db)):
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


# --- restaurants ---

@router.get("/restaurants", response_model=list[AdminRestaurantOut])
def admin_restaurants(brand_id: int | None = None, db: Session = Depends(get_db)):
    stmt = (
        select(Restaurant)
        .options(joinedload(Restaurant.brand))
        .order_by(Restaurant.id.desc())
    )
    if brand_id is not None:
        stmt = stmt.where(Restaurant.brand_id == brand_id)
    return db.scalars(stmt).unique().all()


@router.post(
    "/restaurants", response_model=AdminRestaurantOut, status_code=status.HTTP_201_CREATED
)
def create_restaurant(payload: RestaurantIn, db: Session = Depends(get_db)):
    if db.get(Brand, payload.brand_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Бренд не найден")
    restaurant = Restaurant(**payload.model_dump())
    db.add(restaurant)
    db.commit()
    db.refresh(restaurant)
    return restaurant


@router.patch("/restaurants/{restaurant_id}", response_model=AdminRestaurantOut)
def update_restaurant(
    restaurant_id: int, payload: RestaurantPatch, db: Session = Depends(get_db)
):
    restaurant = db.get(Restaurant, restaurant_id)
    if restaurant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Точка не найдена")
    data = payload.model_dump(exclude_unset=True)
    if "brand_id" in data and db.get(Brand, data["brand_id"]) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Бренд не найден")
    for key, value in data.items():
        setattr(restaurant, key, value)
    db.commit()
    db.refresh(restaurant)
    return restaurant


@router.delete("/restaurants/{restaurant_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_restaurant(restaurant_id: int, db: Session = Depends(get_db)):
    restaurant = db.get(Restaurant, restaurant_id)
    if restaurant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Точка не найдена")
    db.delete(restaurant)
    db.commit()


# --- promotions ---

def _load_promotion(db: Session, promotion_id: int) -> Promotion:
    promotion = db.scalar(
        select(Promotion)
        .options(joinedload(Promotion.brand), selectinload(Promotion.items))
        .where(Promotion.id == promotion_id)
    )
    if promotion is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Акция не найдена")
    return promotion


@router.get("/promotions", response_model=list[AdminPromotionOut])
def admin_promotions(
    brand_id: int | None = None,
    is_active: bool | None = None,
    db: Session = Depends(get_db),
):
    stmt = (
        select(Promotion)
        .options(joinedload(Promotion.brand), selectinload(Promotion.items))
        .order_by(Promotion.created_at.desc())
    )
    if brand_id is not None:
        stmt = stmt.where(Promotion.brand_id == brand_id)
    if is_active is not None:
        stmt = stmt.where(Promotion.is_active.is_(is_active))
    return db.scalars(stmt).unique().all()


@router.post(
    "/promotions", response_model=AdminPromotionOut, status_code=status.HTTP_201_CREATED
)
def create_promotion(
    payload: PromotionIn,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    if db.get(Brand, payload.brand_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Бренд не найден")
    promotion = Promotion(
        brand_id=payload.brand_id,
        title=payload.title.strip(),
        description=payload.description,
        starts_at=payload.starts_at,
        ends_at=payload.ends_at,
        is_active=payload.is_active,
        created_by_id=admin.id,
        items=[
            PromotionItem(name=item.name.strip(), sort_order=i)
            for i, item in enumerate(payload.items)
        ],
    )
    db.add(promotion)
    db.commit()
    return _load_promotion(db, promotion.id)


@router.patch("/promotions/{promotion_id}", response_model=AdminPromotionOut)
def update_promotion(
    promotion_id: int, payload: PromotionPatch, db: Session = Depends(get_db)
):
    promotion = _load_promotion(db, promotion_id)
    data = payload.model_dump(exclude_unset=True)
    if "brand_id" in data and db.get(Brand, data["brand_id"]) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Бренд не найден")
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

    db.commit()
    return _load_promotion(db, promotion_id)


@router.delete("/promotions/{promotion_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_promotion(promotion_id: int, db: Session = Depends(get_db)):
    promotion = db.get(Promotion, promotion_id)
    if promotion is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Акция не найдена")
    # Каскадом уходят items и отчёты (FK ondelete=CASCADE)
    db.delete(promotion)
    db.commit()


# --- users ---

@router.get("/users", response_model=list[AdminUserOut])
def admin_users(db: Session = Depends(get_db)):
    counts = dict(
        db.execute(
            select(Report.user_id, func.count(Report.id)).group_by(Report.user_id)
        ).all()
    )
    users = db.scalars(select(User).order_by(User.created_at)).all()
    result = []
    for user in users:
        out = AdminUserOut.model_validate(user)
        out.reports_count = counts.get(user.id, 0)
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
        data.get("is_blocked") is True or data.get("role") == "user"
    ):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Нельзя заблокировать или разжаловать самого себя",
        )
    for key, value in data.items():
        setattr(user, key, value)
    db.commit()
    db.refresh(user)
    out = AdminUserOut.model_validate(user)
    out.reports_count = (
        db.scalar(select(func.count(Report.id)).where(Report.user_id == user.id)) or 0
    )
    return out


# --- suggestions ---

@router.get("/suggestions", response_model=list[SuggestionGroupOut])
def admin_suggestions(
    status_filter: SuggestionStatus | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
):
    stmt = (
        select(PromotionSuggestion)
        .options(
            joinedload(PromotionSuggestion.user),
            joinedload(PromotionSuggestion.brand),
            joinedload(PromotionSuggestion.restaurant).joinedload(Restaurant.brand),
        )
        .order_by(PromotionSuggestion.created_at.desc())
    )
    if status_filter is not None:
        stmt = stmt.where(PromotionSuggestion.status == status_filter)
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
):
    stmt = (
        select(RestaurantSuggestion)
        .options(
            joinedload(RestaurantSuggestion.user),
            joinedload(RestaurantSuggestion.brand),
        )
        .order_by(RestaurantSuggestion.created_at.desc())
    )
    if status_filter is not None:
        stmt = stmt.where(RestaurantSuggestion.status == status_filter)
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
):
    suggestion = db.get(RestaurantSuggestion, suggestion_id)
    if suggestion is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Заявка не найдена")
    if suggestion.status != SuggestionStatus.pending:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Заявка уже рассмотрена")
    if db.get(Brand, payload.brand_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Бренд не найден")

    restaurant = Restaurant(
        brand_id=payload.brand_id,
        title=(payload.title or "").strip() or None,
        city=payload.city.strip(),
        address=payload.address.strip(),
        lat=payload.lat,
        lng=payload.lng,
    )
    db.add(restaurant)
    db.flush()

    suggestion.status = SuggestionStatus.approved
    suggestion.created_restaurant_id = restaurant.id
    suggestion.reviewed_at = datetime.now(timezone.utc)
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
    suggestion_id: int, payload: SuggestionRejectIn, db: Session = Depends(get_db)
):
    suggestion = db.get(RestaurantSuggestion, suggestion_id)
    if suggestion is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Заявка не найдена")
    if suggestion.status != SuggestionStatus.pending:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Заявка уже рассмотрена")
    suggestion.status = SuggestionStatus.rejected
    suggestion.moderator_comment = payload.moderator_comment.strip()
    suggestion.reviewed_at = datetime.now(timezone.utc)
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
            joinedload(RestaurantSuggestion.brand),
        )
        .where(RestaurantSuggestion.id == suggestion_id)
    )


@router.post("/suggestions/{suggestion_id}/approve", response_model=AdminPromotionOut)
def approve_suggestion(
    suggestion_id: int,
    payload: SuggestionApproveIn,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    suggestion = db.get(PromotionSuggestion, suggestion_id)
    if suggestion is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Заявка не найдена")
    if suggestion.status != SuggestionStatus.pending:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Заявка уже рассмотрена")
    if db.get(Brand, payload.brand_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Бренд не найден")

    names = [name.strip() for name in payload.items if name.strip()]
    if not names:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Укажите хотя бы один товар")

    promotion = Promotion(
        brand_id=payload.brand_id,
        title=(payload.title or suggestion.title).strip(),
        description=payload.description
        if payload.description is not None
        else suggestion.description,
        starts_at=payload.starts_at,
        ends_at=payload.ends_at,
        is_active=True,
        created_by_id=admin.id,
        items=[PromotionItem(name=name, sort_order=i) for i, name in enumerate(names)],
    )
    db.add(promotion)
    db.flush()

    suggestion.status = SuggestionStatus.approved
    suggestion.created_promotion_id = promotion.id
    suggestion.reviewed_at = datetime.now(timezone.utc)

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
    return _load_promotion(db, promotion.id)


@router.post("/suggestions/{suggestion_id}/reject", response_model=AdminSuggestionOut)
def reject_suggestion(
    suggestion_id: int, payload: SuggestionRejectIn, db: Session = Depends(get_db)
):
    suggestion = db.get(PromotionSuggestion, suggestion_id)
    if suggestion is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Заявка не найдена")
    if suggestion.status != SuggestionStatus.pending:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Заявка уже рассмотрена")
    suggestion.status = SuggestionStatus.rejected
    suggestion.moderator_comment = payload.moderator_comment.strip()
    suggestion.reviewed_at = datetime.now(timezone.utc)

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
            joinedload(PromotionSuggestion.restaurant).joinedload(Restaurant.brand),
        )
        .where(PromotionSuggestion.id == suggestion_id)
    )
    return suggestion
