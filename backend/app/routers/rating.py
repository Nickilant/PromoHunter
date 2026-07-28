from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.auth import get_current_user_optional
from app.database import get_db
from app.models import PromotionSuggestion, RatingEvent, Report, User
from app.schemas import (
    RatingCardOut,
    RatingCategoryOut,
    RatingEntryOut,
    RatingEventOut,
    RatingMeOut,
    RatingOut,
)

router = APIRouter(prefix="/rating", tags=["rating"])

Period = Literal["month", "year"]


def _period_start(period: Period, now: datetime) -> datetime:
    if period == "month":
        return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)


@router.get("", response_model=RatingOut)
def leaderboard(
    city: str,
    period: Period = "month",
    db: Session = Depends(get_db),
    viewer: User | None = Depends(get_current_user_optional),
):
    since = _period_start(period, datetime.now(timezone.utc))

    rows = db.execute(
        select(
            RatingEvent.user_id,
            User.display_name,
            func.sum(RatingEvent.points).label("points"),
            func.count().filter(RatingEvent.type == "report_base").label("reports"),
            func.count().filter(RatingEvent.type == "pioneer").label("pioneers"),
        )
        .join(User, User.id == RatingEvent.user_id)
        .where(
            RatingEvent.city == city,
            RatingEvent.created_at >= since,
            User.is_blocked.is_(False),
        )
        .group_by(RatingEvent.user_id, User.display_name)
        .order_by(func.sum(RatingEvent.points).desc(), RatingEvent.user_id)
    ).all()

    # Публичный пол — ноль: в таблицу попадают только положительные суммы
    ranked = [r for r in rows if r.points > 0]
    entries = [
        RatingEntryOut(
            user_id=r.user_id,
            display_name=r.display_name,
            points=r.points,
            reports_count=r.reports,
            pioneers_count=r.pioneers,
            position=i + 1,
        )
        for i, r in enumerate(ranked[:20])
    ]

    me = None
    if viewer is not None:
        position = next(
            (i + 1 for i, r in enumerate(ranked) if r.user_id == viewer.id), None
        )
        my_points = next((r.points for r in rows if r.user_id == viewer.id), 0)
        me = RatingMeOut(position=position, points=max(0, my_points))

    return RatingOut(entries=entries, me=me)


TYPE_ORDER = [
    "pioneer",
    "report_confirmed",
    "scout",
    "report_base",
    "suggestion_approved",
    "report_refuted",
    "suggestion_spam",
]


@router.get("/users/{user_id}", response_model=RatingCardOut)
def player_card(
    user_id: int,
    city: str | None = None,
    period: Period = "month",
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    viewer: User | None = Depends(get_current_user_optional),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Пользователь не найден")

    since = _period_start(period, datetime.now(timezone.utc))
    conditions = [RatingEvent.user_id == user_id, RatingEvent.created_at >= since]
    if city:
        conditions.append(RatingEvent.city == city)

    rows = db.execute(
        select(
            RatingEvent.type,
            func.count().label("count"),
            func.sum(RatingEvent.points).label("points"),
        )
        .where(*conditions)
        .group_by(RatingEvent.type)
    ).all()
    by_type = {r.type: r for r in rows}
    categories = [
        RatingCategoryOut(type=t, count=by_type[t].count, points=by_type[t].points)
        for t in TYPE_ORDER
        if t in by_type
    ]
    total = sum(r.points for r in rows)

    # Полная лента событий (с точками и временем) — только владельцу:
    # публичная лента раскрывала бы маршруты человека
    events = None
    if viewer is not None and viewer.id == user_id:
        event_rows = (
            db.scalars(
                select(RatingEvent)
                .options(
                    joinedload(RatingEvent.user),
                )
                .where(RatingEvent.user_id == user_id)
                .order_by(RatingEvent.created_at.desc())
                .limit(limit)
            )
            .unique()
            .all()
        )
        report_ids = [e.report_id for e in event_rows if e.report_id]
        reports = {
            r.id: r
            for r in db.scalars(
                select(Report)
                .options(joinedload(Report.restaurant), joinedload(Report.promotion))
                .where(Report.id.in_(report_ids))
            ).unique()
        } if report_ids else {}
        suggestion_ids = [e.suggestion_id for e in event_rows if e.suggestion_id]
        suggestions = {
            s.id: s
            for s in db.scalars(
                select(PromotionSuggestion).where(
                    PromotionSuggestion.id.in_(suggestion_ids)
                )
            )
        } if suggestion_ids else {}

        events = []
        for e in event_rows:
            context = None
            report = reports.get(e.report_id) if e.report_id else None
            if report is not None and report.restaurant and report.promotion:
                context = f"{report.promotion.title} — {report.restaurant.address}"
            suggestion = suggestions.get(e.suggestion_id) if e.suggestion_id else None
            if suggestion is not None:
                context = f"Заявка «{suggestion.title}»"
            events.append(
                RatingEventOut(
                    type=e.type,
                    points=e.points,
                    city=e.city,
                    context=context,
                    created_at=e.created_at,
                )
            )

    return RatingCardOut(
        user_id=user.id,
        display_name=user.display_name,
        total_points=max(0, total),
        categories=categories,
        events=events,
    )
