import math
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.auth import get_current_user, require_not_blocked
from app.config import settings
from app.database import get_db
from app.models import Promotion, PromotionItem, Report, ReportItem, Restaurant, User
from app.routers.public import active_promotion_clause
from app.schemas import ReportIn, ReportItemOut, ReportOut, RestaurantShort

router = APIRouter(prefix="/reports", tags=["reports"])


def _report_out(report: Report) -> ReportOut:
    return ReportOut(
        id=report.id,
        restaurant=RestaurantShort.model_validate(report.restaurant),
        promotion_title=report.promotion.title,
        items=[
            ReportItemOut(
                promotion_item_id=ri.promotion_item_id,
                name=ri.promotion_item.name,
                is_available=ri.is_available,
            )
            for ri in report.items
        ],
        created_at=report.created_at,
    )


@router.post("", response_model=ReportOut, status_code=status.HTTP_201_CREATED)
def create_report(
    payload: ReportIn,
    user: User = Depends(require_not_blocked),
    db: Session = Depends(get_db),
):
    restaurant = db.get(Restaurant, payload.restaurant_id)
    if restaurant is None or not restaurant.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Точка не найдена")

    now = datetime.now(timezone.utc)
    promotion = db.scalar(
        select(Promotion)
        .options(selectinload(Promotion.items))
        .where(Promotion.id == payload.promotion_id, active_promotion_clause(now))
    )
    if promotion is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Акция не найдена или не действует")
    if promotion.brand_id != restaurant.brand_id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="Акция не относится к сети этой точки"
        )

    valid_item_ids = {item.id for item in promotion.items}
    seen: set[int] = set()
    for item in payload.items:
        if item.promotion_item_id not in valid_item_ids:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, detail="Товар не относится к этой акции"
            )
        if item.promotion_item_id in seen:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, detail="Товар указан дважды"
            )
        seen.add(item.promotion_item_id)

    # Кулдаун по паре (ресторан, акция)
    cooldown = timedelta(minutes=settings.report_cooldown_minutes)
    last_report_at = db.scalar(
        select(Report.created_at)
        .where(
            Report.user_id == user.id,
            Report.restaurant_id == restaurant.id,
            Report.promotion_id == promotion.id,
        )
        .order_by(Report.created_at.desc())
        .limit(1)
    )
    if last_report_at is not None and now - last_report_at < cooldown:
        wait_minutes = math.ceil(
            (cooldown - (now - last_report_at)).total_seconds() / 60
        )
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                "Вы уже отмечали эту акцию здесь, "
                f"можно снова через {wait_minutes} мин."
            ),
        )

    report = Report(
        user_id=user.id,
        restaurant_id=restaurant.id,
        promotion_id=promotion.id,
        lat=payload.lat,
        lng=payload.lng,
        items=[
            ReportItem(
                promotion_item_id=item.promotion_item_id,
                is_available=item.is_available,
            )
            for item in payload.items
        ],
    )
    db.add(report)
    db.commit()

    report = db.scalar(
        select(Report)
        .options(
            joinedload(Report.restaurant).joinedload(Restaurant.brand),
            joinedload(Report.promotion),
            selectinload(Report.items).joinedload(ReportItem.promotion_item),
        )
        .where(Report.id == report.id)
    )
    return _report_out(report)


@router.get("/mine", response_model=list[ReportOut])
def my_reports(
    limit: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    reports = (
        db.scalars(
            select(Report)
            .options(
                joinedload(Report.restaurant).joinedload(Restaurant.brand),
                joinedload(Report.promotion),
                selectinload(Report.items).joinedload(ReportItem.promotion_item),
            )
            .where(Report.user_id == user.id)
            .order_by(Report.created_at.desc())
            .limit(limit)
        )
        .unique()
        .all()
    )
    return [_report_out(r) for r in reports]
