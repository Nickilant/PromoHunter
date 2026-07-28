from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.database import get_db
from app.models import Brand, Promotion, PromotionItem, Report, Restaurant
from app.schemas import (
    BrandOut,
    FeedEntry,
    ItemStatusOut,
    PromotionWithStatuses,
    RestaurantDetail,
    RestaurantListItem,
    RestaurantShort,
)
from app.services.status import compute_statuses

router = APIRouter(tags=["public"])


def active_promotion_clause(now: datetime):
    """Акция действует: is_active и текущая дата внутри (nullable) интервала."""
    return and_(
        Promotion.is_active.is_(True),
        or_(Promotion.starts_at.is_(None), Promotion.starts_at <= now),
        or_(Promotion.ends_at.is_(None), Promotion.ends_at >= now),
    )


def promotion_with_statuses(
    db: Session, restaurant_id: int, promotions: list[Promotion]
) -> list[PromotionWithStatuses]:
    statuses = compute_statuses(db, restaurant_id, [p.id for p in promotions])
    result = []
    for promo in promotions:
        items = []
        for item in promo.items:
            st = statuses.get(item.id)
            items.append(
                ItemStatusOut(
                    id=item.id,
                    name=item.name,
                    status=st.status,
                    yes_count=st.yes_count,
                    no_count=st.no_count,
                    last_report_at=st.last_report_at,
                )
            )
        result.append(
            PromotionWithStatuses(
                id=promo.id,
                title=promo.title,
                description=promo.description,
                starts_at=promo.starts_at,
                ends_at=promo.ends_at,
                items=items,
            )
        )
    return result


@router.get("/brands", response_model=list[BrandOut])
def list_brands(db: Session = Depends(get_db)):
    return db.scalars(select(Brand).order_by(Brand.name)).all()


@router.get("/restaurants", response_model=list[RestaurantListItem])
def list_restaurants(
    q: str | None = None, brand_id: int | None = None, db: Session = Depends(get_db)
):
    now = datetime.now(timezone.utc)
    active_count = (
        select(func.count(Promotion.id))
        .where(Promotion.brand_id == Restaurant.brand_id, active_promotion_clause(now))
        .correlate(Restaurant)
        .scalar_subquery()
    )
    stmt = (
        select(Restaurant, active_count)
        .join(Brand)
        .options(joinedload(Restaurant.brand))
        .where(Restaurant.is_active.is_(True))
        .order_by(Brand.name, Restaurant.address)
    )
    if brand_id is not None:
        stmt = stmt.where(Restaurant.brand_id == brand_id)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Brand.name.ilike(like),
                Restaurant.title.ilike(like),
                Restaurant.address.ilike(like),
            )
        )
    rows = db.execute(stmt).unique().all()
    return [
        RestaurantListItem(
            id=r.id,
            brand=r.brand,
            title=r.title,
            address=r.address,
            lat=r.lat,
            lng=r.lng,
            active_promotions_count=count,
        )
        for r, count in rows
    ]


@router.get("/restaurants/{restaurant_id}", response_model=RestaurantDetail)
def restaurant_detail(restaurant_id: int, db: Session = Depends(get_db)):
    restaurant = db.get(
        Restaurant, restaurant_id, options=[joinedload(Restaurant.brand)]
    )
    if restaurant is None or not restaurant.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Точка не найдена")

    now = datetime.now(timezone.utc)
    promotions = (
        db.scalars(
            select(Promotion)
            .options(selectinload(Promotion.items))
            .where(Promotion.brand_id == restaurant.brand_id, active_promotion_clause(now))
            .order_by(Promotion.created_at.desc())
        )
        .unique()
        .all()
    )
    return RestaurantDetail(
        id=restaurant.id,
        brand=restaurant.brand,
        title=restaurant.title,
        address=restaurant.address,
        lat=restaurant.lat,
        lng=restaurant.lng,
        promotions=promotion_with_statuses(db, restaurant.id, promotions),
    )


@router.get("/feed", response_model=list[FeedEntry])
def feed(q: str | None = None, db: Session = Depends(get_db)):
    """Главный поисковый эндпоинт: карточки ресторанов с вложенными акциями."""
    now = datetime.now(timezone.utc)

    restaurants = (
        db.scalars(
            select(Restaurant)
            .options(joinedload(Restaurant.brand))
            .where(Restaurant.is_active.is_(True))
        )
        .unique()
        .all()
    )
    promotions = (
        db.scalars(
            select(Promotion)
            .options(selectinload(Promotion.items))
            .where(active_promotion_clause(now))
            .order_by(Promotion.created_at.desc())
        )
        .unique()
        .all()
    )
    promos_by_brand: dict[int, list[Promotion]] = {}
    for p in promotions:
        promos_by_brand.setdefault(p.brand_id, []).append(p)

    matched_promo_ids: set[int] | None = None
    query = (q or "").strip().lower()
    if query:
        matched_promo_ids = set()
        for p in promotions:
            if query in p.title.lower() or any(
                query in item.name.lower() for item in p.items
            ):
                matched_promo_ids.add(p.id)

    # Свежесть последнего отчёта по точке — для сортировки выдачи
    last_report_rows = db.execute(
        select(Report.restaurant_id, func.max(Report.created_at)).group_by(
            Report.restaurant_id
        )
    ).all()
    last_report_by_restaurant = dict(last_report_rows)

    entries: list[tuple[datetime | None, FeedEntry]] = []
    for restaurant in restaurants:
        brand_promos = promos_by_brand.get(restaurant.brand_id, [])
        if not brand_promos:
            continue

        if query:
            restaurant_matched = (
                query in restaurant.brand.name.lower()
                or (restaurant.title and query in restaurant.title.lower())
                or query in restaurant.address.lower()
            )
            if restaurant_matched:
                shown = brand_promos
            else:
                # Совпадение по акции/товару — показываем только совпавшие акции
                shown = [p for p in brand_promos if p.id in matched_promo_ids]
                if not shown:
                    continue
        else:
            shown = brand_promos

        entry = FeedEntry(
            restaurant=RestaurantShort.model_validate(restaurant),
            promotions=promotion_with_statuses(db, restaurant.id, shown),
        )
        entries.append((last_report_by_restaurant.get(restaurant.id), entry))

    # Сначала точки с самыми свежими отчётами, без отчётов — в конец
    epoch = datetime.fromtimestamp(0, tz=timezone.utc)
    entries.sort(key=lambda pair: pair[0] or epoch, reverse=True)
    return [entry for _, entry in entries]
