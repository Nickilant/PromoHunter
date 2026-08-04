from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.auth import get_current_user_optional
from app.database import get_db
from app.models import Brand, City, Promotion, PromotionItem, Report, ReportItem, Restaurant, User
from app.schemas import (
    BrandOut,
    CatalogBrand,
    CatalogPromo,
    CityOut,
    FeedEntry,
    ItemStatusOut,
    PromotionWithStatuses,
    RestaurantDetail,
    RestaurantListItem,
    RestaurantHistory,
    HistoryItem,
    RestaurantShort,
)
from app.services.promo_scope import promotion_visible_in, visible_in_city_clause
from app.services.brand_visibility import can_see_private_brands
from app.services.scope import city_key
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
def list_brands(
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
):
    stmt = select(Brand).order_by(Brand.name)
    if not can_see_private_brands(user):
        stmt = stmt.where(Brand.is_public.is_(True))
    return db.scalars(stmt).all()


@router.get("/telegram/info")
def telegram_info():
    """Доступность телеграм-функций и username бота (для ссылки t.me/...)."""
    from app import telegram

    return {
        "enabled": telegram.enabled(),
        "bot_username": telegram.bot_username(),
    }


@router.get("/cities", response_model=list[CityOut])
def list_cities(
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
):
    """Города для выбора при входе — по убыванию числа точек.

    Город из справочника показывается, даже когда точек в нём ещё нет:
    человек выбирает его и сам присылает заявку на первую точку. Города,
    оставшиеся от точек до появления справочника, тоже не теряем.
    """
    rows_stmt = (
        select(Restaurant.city, func.count(Restaurant.id))
        .join(Brand)
        .where(Restaurant.is_active.is_(True))
        .group_by(Restaurant.city)
    )
    if not can_see_private_brands(user):
        rows_stmt = rows_stmt.where(Brand.is_public.is_(True))
    rows = db.execute(rows_stmt).all()

    by_key: dict[str, CityOut] = {}
    for name, count in rows:
        key = city_key(name)
        found = by_key.get(key)
        if found is None:
            by_key[key] = CityOut(name=name, restaurants_count=count)
        else:
            found.restaurants_count += count

    for city in db.scalars(select(City).where(City.is_active.is_(True))):
        found = by_key.get(city.key)
        if found is None:
            by_key[city.key] = CityOut(name=city.name, restaurants_count=0)
        else:
            # Справочник — источник правды для написания названия
            found.name = city.name

    return sorted(
        by_key.values(), key=lambda c: (-c.restaurants_count, c.name)
    )


@router.get("/catalog", response_model=list[CatalogBrand])
def catalog(
    city: str,
    q: str | None = None,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
):
    """Каталог: сети с действующими акциями в выбранном городе.

    Поиск q матчит название сети, акции и товара. Если совпала акция —
    в карточке сети остаются только совпавшие акции.
    """
    now = datetime.now(timezone.utc)

    counts_stmt = (
        select(Restaurant.brand_id, func.count(Restaurant.id))
        .join(Brand)
        .where(Restaurant.is_active.is_(True), Restaurant.city == city)
        .group_by(Restaurant.brand_id)
    )
    if not can_see_private_brands(user):
        counts_stmt = counts_stmt.where(Brand.is_public.is_(True))
    counts = dict(db.execute(counts_stmt).all())
    if not counts:
        return []

    brands = db.scalars(
        select(Brand).where(Brand.id.in_(counts.keys())).order_by(Brand.name)
    ).all()
    promotions = (
        db.scalars(
            select(Promotion)
            .options(selectinload(Promotion.items))
            .where(
                Promotion.brand_id.in_(counts.keys()),
                active_promotion_clause(now),
                visible_in_city_clause(city),
            )
            .order_by(Promotion.created_at.desc())
        )
        .unique()
        .all()
    )
    promos_by_brand: dict[int, list[Promotion]] = {}
    for p in promotions:
        promos_by_brand.setdefault(p.brand_id, []).append(p)

    query = (q or "").strip().lower()
    matched_promo_ids: set[int] = set()
    if query:
        for p in promotions:
            if query in p.title.lower() or any(
                query in item.name.lower() for item in p.items
            ):
                matched_promo_ids.add(p.id)

    # Свежесть отчётов по сетям в этом городе — для сортировки
    last_report_by_brand = dict(
        db.execute(
            select(Restaurant.brand_id, func.max(Report.created_at))
            .join(Report, Report.restaurant_id == Restaurant.id)
            .where(Restaurant.city == city)
            .group_by(Restaurant.brand_id)
        ).all()
    )

    entries: list[tuple[datetime | None, CatalogBrand]] = []
    for brand in brands:
        brand_promos = promos_by_brand.get(brand.id, [])
        if not brand_promos:
            continue
        if query:
            if query in brand.name.lower():
                shown = brand_promos
            else:
                shown = [p for p in brand_promos if p.id in matched_promo_ids]
                if not shown:
                    continue
        else:
            shown = brand_promos
        entries.append(
            (
                last_report_by_brand.get(brand.id),
                CatalogBrand(
                    id=brand.id,
                    name=brand.name,
                    color=brand.color,
                    logo_url=brand.logo_url,
                    restaurants_count=counts[brand.id],
                    promotions=[CatalogPromo(id=p.id, title=p.title) for p in shown],
                ),
            )
        )

    epoch = datetime.fromtimestamp(0, tz=timezone.utc)
    entries.sort(key=lambda pair: pair[0] or epoch, reverse=True)
    return [entry for _, entry in entries]


@router.get("/restaurants", response_model=list[RestaurantListItem])
def list_restaurants(
    q: str | None = None,
    brand_id: int | None = None,
    city: str | None = None,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
):
    now = datetime.now(timezone.utc)
    active_count = (
        select(func.count(Promotion.id))
        .where(Promotion.brand_id == Restaurant.brand_id, active_promotion_clause(now))
        .correlate(Restaurant)
        .scalar_subquery()
    )
    last_report = (
        select(func.max(Report.created_at))
        .where(Report.restaurant_id == Restaurant.id)
        .correlate(Restaurant)
        .scalar_subquery()
    )
    stmt = (
        select(Restaurant, active_count, last_report)
        .join(Brand)
        .options(joinedload(Restaurant.brand))
        .where(Restaurant.is_active.is_(True))
        .order_by(Brand.name, Restaurant.address)
    )
    if not can_see_private_brands(user):
        stmt = stmt.where(Brand.is_public.is_(True))
    if brand_id is not None:
        stmt = stmt.where(Restaurant.brand_id == brand_id)
    if city:
        stmt = stmt.where(Restaurant.city == city)
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
    items = [
        RestaurantListItem(
            id=r.id,
            brand=r.brand,
            title=r.title,
            city=r.city,
            address=r.address,
            lat=r.lat,
            lng=r.lng,
            active_promotions_count=count,
            last_report_at=last_report_at,
        )
        for r, count, last_report_at in rows
    ]
    # Свежие точки — первыми (для списка адресов внутри сети)
    epoch = datetime.fromtimestamp(0, tz=timezone.utc)
    items.sort(key=lambda item: item.last_report_at or epoch, reverse=True)
    return items


@router.get("/restaurants/{restaurant_id}", response_model=RestaurantDetail)
def restaurant_detail(
    restaurant_id: int,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
):
    restaurant = db.get(
        Restaurant, restaurant_id, options=[joinedload(Restaurant.brand)]
    )
    if (
        restaurant is None
        or not restaurant.is_active
        or (not restaurant.brand.is_public and not can_see_private_brands(user))
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Точка не найдена")

    now = datetime.now(timezone.utc)
    promotions = (
        db.scalars(
            select(Promotion)
            .options(selectinload(Promotion.items))
            .where(
                Promotion.brand_id == restaurant.brand_id,
                active_promotion_clause(now),
                # Акция сети может не проводиться в этом городе
                visible_in_city_clause(restaurant.city),
            )
            .order_by(Promotion.created_at.desc())
        )
        .unique()
        .all()
    )
    return RestaurantDetail(
        id=restaurant.id,
        brand=restaurant.brand,
        title=restaurant.title,
        city=restaurant.city,
        address=restaurant.address,
        lat=restaurant.lat,
        lng=restaurant.lng,
        promotions=promotion_with_statuses(db, restaurant.id, promotions),
    )


@router.get("/feed", response_model=list[FeedEntry])
def feed(
    q: str | None = None,
    city: str | None = None,
    brand_id: int | None = None,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
):
    """Поисковый эндпоинт: карточки ресторанов с вложенными акциями."""
    now = datetime.now(timezone.utc)

    restaurants_stmt = (
        select(Restaurant)
        .join(Brand)
        .options(joinedload(Restaurant.brand))
        .where(Restaurant.is_active.is_(True))
    )
    if not can_see_private_brands(user):
        restaurants_stmt = restaurants_stmt.where(Brand.is_public.is_(True))
    if city:
        restaurants_stmt = restaurants_stmt.where(Restaurant.city == city)
    if brand_id is not None:
        restaurants_stmt = restaurants_stmt.where(Restaurant.brand_id == brand_id)
    restaurants = db.scalars(restaurants_stmt).unique().all()
    promotions = (
        db.scalars(
            select(Promotion)
            # cities — чтобы отфильтровать охват по городу каждой точки
            .options(selectinload(Promotion.items), selectinload(Promotion.cities))
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
        # Лента может быть по всем городам сразу, поэтому охват проверяем
        # для города каждой точки отдельно
        brand_promos = [
            p
            for p in promos_by_brand.get(restaurant.brand_id, [])
            if promotion_visible_in(p, restaurant.city)
        ]
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


@router.get("/restaurants/{restaurant_id}/history", response_model=RestaurantHistory)
def restaurant_history(
    restaurant_id: int,
    days: int = 7,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
):
    """Краткая фактическая сводка по отчётам точки за ограниченный период."""
    days = max(1, min(days, 30))
    restaurant = db.get(Restaurant, restaurant_id, options=[joinedload(Restaurant.brand)])
    if (
        restaurant is None
        or not restaurant.is_active
        or (not restaurant.brand.is_public and not can_see_private_brands(user))
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Точка не найдена")
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = db.execute(
        select(
            Promotion.title,
            PromotionItem.name,
            func.count(ReportItem.id),
            func.count(ReportItem.id).filter(ReportItem.is_available.is_(True)),
            func.max(Report.created_at).filter(ReportItem.is_available.is_(True)),
            func.max(Report.created_at).filter(ReportItem.is_available.is_(False)),
        )
        .join(Report, Report.id == ReportItem.report_id)
        .join(PromotionItem, PromotionItem.id == ReportItem.promotion_item_id)
        .join(Promotion, Promotion.id == Report.promotion_id)
        .where(Report.restaurant_id == restaurant_id, Report.created_at >= since)
        .group_by(Promotion.id, Promotion.title, PromotionItem.id, PromotionItem.name)
        .order_by(Promotion.title, PromotionItem.sort_order)
    ).all()
    reports_count, contributors_count, last_report_at = db.execute(
        select(func.count(Report.id), func.count(func.distinct(Report.user_id)), func.max(Report.created_at))
        .where(Report.restaurant_id == restaurant_id, Report.created_at >= since)
    ).one()
    return RestaurantHistory(
        days=days,
        reports_count=reports_count,
        contributors_count=contributors_count,
        last_report_at=last_report_at,
        items=[HistoryItem(
            promotion_title=title,
            item_name=name,
            reports_count=total,
            available_count=available,
            availability_percent=round(available * 100 / total),
            last_available_at=last_yes,
            last_unavailable_at=last_no,
        ) for title, name, total, available, last_yes, last_no in rows],
    )
