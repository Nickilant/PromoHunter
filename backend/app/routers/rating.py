from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.auth import get_current_user_optional
from app.database import get_db
from app.models import (
    Faction,
    PromotionSuggestion,
    RatingEvent,
    Report,
    RestaurantSuggestion,
    User,
    UserRole,
)
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


Scope = Literal["all", "faction"]


def _ranked_subquery(
    city: str, since: datetime, faction: Faction | None
):
    """Пронумерованный зачёт города: место считает СУБД, а не Python.

    Админы в общий зачёт не попадают: у них доступ к модерации, соревноваться
    с ними нечестно. Публичный пол — ноль, минусовые суммы в таблицу не идут.
    """
    conditions = [
        RatingEvent.city == city,
        RatingEvent.created_at >= since,
        User.is_blocked.is_(False),
        User.role != UserRole.admin,
    ]
    if faction is not None:
        conditions.append(User.faction == faction)

    totals = (
        select(
            RatingEvent.user_id.label("user_id"),
            User.display_name.label("display_name"),
            func.sum(RatingEvent.points).label("points"),
            func.count().filter(RatingEvent.type == "report_base").label("reports"),
            func.count().filter(RatingEvent.type == "pioneer").label("pioneers"),
        )
        .join(User, User.id == RatingEvent.user_id)
        .where(*conditions)
        .group_by(RatingEvent.user_id, User.display_name)
        .having(func.sum(RatingEvent.points) > 0)
        .subquery()
    )
    position = (
        func.row_number()
        .over(order_by=(totals.c.points.desc(), totals.c.user_id))
        .label("position")
    )
    return select(
        totals.c.user_id,
        totals.c.display_name,
        totals.c.points,
        totals.c.reports,
        totals.c.pioneers,
        position,
    ).subquery()


def _entry(row) -> RatingEntryOut:
    return RatingEntryOut(
        user_id=row.user_id,
        display_name=row.display_name,
        points=row.points,
        reports_count=row.reports,
        pioneers_count=row.pioneers,
        position=row.position,
    )


@router.get("", response_model=RatingOut)
def leaderboard(
    city: str,
    period: Period = "month",
    scope: Scope = "all",
    limit: int = Query(default=10, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    viewer: User | None = Depends(get_current_user_optional),
):
    """Таблица зачёта постранично плюс своя строка — она приходит всегда,
    даже если человек на 564-м месте и в выданную страницу не попал."""
    since = _period_start(period, datetime.now(timezone.utc))

    faction = None
    if scope == "faction":
        if viewer is None or viewer.faction is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="Зачёт по фракции доступен, когда выбрана сторона",
            )
        faction = viewer.faction

    ranked = _ranked_subquery(city, since, faction)

    total = db.scalar(select(func.count()).select_from(ranked)) or 0
    rows = db.execute(
        select(ranked)
        .order_by(ranked.c.position)
        .limit(limit)
        .offset(offset)
    ).all()
    entries = [_entry(row) for row in rows]

    me = None
    if viewer is not None:
        my_row = db.execute(
            select(ranked).where(ranked.c.user_id == viewer.id)
        ).first()
        if my_row is not None:
            me = RatingMeOut(**_entry(my_row).model_dump())
        else:
            # Очков нет (или они в минусе) — показываем строку без места
            me = RatingMeOut(
                user_id=viewer.id,
                display_name=viewer.display_name,
                points=0,
                reports_count=0,
                pioneers_count=0,
                position=None,
            )

    return RatingOut(entries=entries, total=total, me=me)


TYPE_ORDER = [
    "pioneer",
    "report_confirmed",
    "scout",
    "report_base",
    "suggestion_approved",
    "restaurant_approved",
    "report_refuted",
    "suggestion_spam",
    "restaurant_spam",
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
        rest_suggestion_ids = [
            e.restaurant_suggestion_id for e in event_rows if e.restaurant_suggestion_id
        ]
        rest_suggestions = {
            s.id: s
            for s in db.scalars(
                select(RestaurantSuggestion).where(
                    RestaurantSuggestion.id.in_(rest_suggestion_ids)
                )
            )
        } if rest_suggestion_ids else {}

        events = []
        for e in event_rows:
            context = None
            report = reports.get(e.report_id) if e.report_id else None
            if report is not None and report.restaurant and report.promotion:
                context = f"{report.promotion.title} — {report.restaurant.address}"
            suggestion = suggestions.get(e.suggestion_id) if e.suggestion_id else None
            if suggestion is not None:
                context = f"Заявка «{suggestion.title}»"
            rest_suggestion = (
                rest_suggestions.get(e.restaurant_suggestion_id)
                if e.restaurant_suggestion_id
                else None
            )
            if rest_suggestion is not None:
                context = f"Ресторан «{rest_suggestion.address}»"
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
