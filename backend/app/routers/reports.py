import math
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.auth import get_current_user, require_not_blocked
from app.config import settings
from app.database import get_db
from app.models import (
    Promotion,
    RatingEvent,
    Report,
    ReportItem,
    Restaurant,
    User,
)
from app.routers.public import active_promotion_clause
from app.schemas import (
    CaptureOut,
    ReportIn,
    ReportItemOut,
    ReportOut,
    RestaurantShort,
)
from app.services import game
from app.services.notify import notify_capture, notify_status_flips
from app.services.receipt import ReceiptError, parse_receipt
from app.services.status import refresh_stable_statuses

router = APIRouter(prefix="/reports", tags=["reports"])


def _report_out(report: Report, capture: CaptureOut | None = None) -> ReportOut:
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
        is_receipt_verified=report.is_receipt_verified,
        capture=capture,
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

    # Чек предъявляют до создания отчёта: незачёт не должен оставлять следов
    parsed = None
    if payload.receipt_qr:
        try:
            parsed = parse_receipt(payload.receipt_qr)
        except ReceiptError as error:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(error)) from None
        if not any(item.is_available for item in payload.items):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="Чеком подтверждают, что товар есть — отметьте хотя бы один",
            )

    # Кулдаун по паре (ресторан, акция); отчёт с чеком его не ждёт —
    # купил ещё раз, значит снова был на точке
    cooldown = timedelta(minutes=settings.report_cooldown_minutes)
    last_report_at = None if parsed else db.scalar(
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

    # «Разведка тёмной точки»: по этой паре свежих данных не было вообще
    window_start = now - timedelta(hours=settings.status_window_hours)
    had_fresh_data = db.scalar(
        select(Report.id)
        .where(
            Report.restaurant_id == restaurant.id,
            Report.promotion_id == promotion.id,
            Report.created_at >= window_start,
        )
        .limit(1)
    )

    report = Report(
        user_id=user.id,
        restaurant_id=restaurant.id,
        promotion_id=promotion.id,
        channel=payload.channel,
        lat=payload.lat,
        lng=payload.lng,
        is_receipt_verified=parsed is not None,
        items=[
            ReportItem(
                promotion_item_id=item.promotion_item_id,
                is_available=item.is_available,
            )
            for item in payload.items
        ],
    )
    db.add(report)
    db.flush()

    # --- игровой режим: чек даёт силу фракции и переоценивает свежие «нет» ---
    capture: CaptureOut | None = None
    if parsed is not None:
        try:
            result = game.apply_receipt(
                db, user, restaurant, parsed, payload.lat, payload.lng, report, now
            )
        except ReceiptError as error:
            db.rollback()
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(error)) from None
        refuted = game.grade_denials_by_receipt(
            db,
            report,
            [item.promotion_item_id for item in payload.items if item.is_available],
            now,
        )
        capture = CaptureOut(
            strength=round(result.strength, 2),
            points=result.added_points,
            faction=result.receipt.faction,
            owner=result.owner,
            captured=any(r.kind == "capture" for r in result.resolutions),
            defended=any(r.kind == "defend" for r in result.resolutions),
            refuted_denials=refuted,
        )

    # --- очки рейтинга, начисляемые сразу (бонусы приходят после дозревания) ---
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    base_today = db.scalar(
        select(func.count(RatingEvent.id)).where(
            RatingEvent.user_id == user.id,
            RatingEvent.type == "report_base",
            RatingEvent.created_at >= day_start,
        )
    ) or 0
    same_restaurant_today = db.scalar(
        select(func.count(Report.id)).where(
            Report.user_id == user.id,
            Report.restaurant_id == restaurant.id,
            Report.created_at >= day_start,
            Report.id != report.id,
        )
    ) or 0
    # Анти-фарм: дневной потолок базы + без базы за повторы по той же точке
    if base_today < settings.rating_daily_base_cap and same_restaurant_today == 0:
        db.add(
            RatingEvent(
                user_id=user.id,
                city=restaurant.city,
                type="report_base",
                points=settings.rating_base_points,
                report_id=report.id,
            )
        )
    if had_fresh_data is None:
        db.add(
            RatingEvent(
                user_id=user.id,
                city=restaurant.city,
                type="scout",
                points=settings.rating_scout_points,
                report_id=report.id,
            )
        )

    # Мгновенное табло: пересчёт устойчивых статусов затронутых товаров
    flips = refresh_stable_statuses(db, restaurant.id, [promotion.id], now)
    db.commit()

    # Подписчикам акции — о переключениях статусов (после коммита, в фоне)
    if flips:
        item_names = {item.id: item.name for item in promotion.items}
        notify_status_flips(
            db,
            restaurant,
            promotion,
            [
                (item_names[item_id], new)
                for item_id, _, new in flips
                if item_id in item_names and new in ("available", "unavailable")
            ],
        )

    # Игровые уведомления: точку атакуют / точка перешла
    if capture is not None:
        notify_capture(db, restaurant, capture.captured, capture.defended)

    report = db.scalar(
        select(Report)
        .options(
            joinedload(Report.restaurant).joinedload(Restaurant.brand),
            joinedload(Report.promotion),
            selectinload(Report.items).joinedload(ReportItem.promotion_item),
        )
        .where(Report.id == report.id)
    )
    return _report_out(report, capture)


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
