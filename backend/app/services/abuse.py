"""Небольшие серверные ограничения для публичных пользовательских записей."""

import math
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select, union_all
from sqlalchemy.orm import Session

from app.models import PromotionSuggestion, RestaurantSuggestion


def enforce_suggestion_cooldown(db: Session, user_id: int, minutes: int) -> None:
    """Один общий кулдаун для заявок на акции и новые рестораны."""
    entries = union_all(
        select(PromotionSuggestion.created_at.label("created_at")).where(
            PromotionSuggestion.user_id == user_id
        ),
        select(RestaurantSuggestion.created_at.label("created_at")).where(
            RestaurantSuggestion.user_id == user_id
        ),
    ).subquery()
    latest = db.scalar(
        select(entries.c.created_at)
        .order_by(entries.c.created_at.desc())
        .limit(1)
    )
    if latest is None:
        return
    now = datetime.now(timezone.utc)
    cooldown = timedelta(minutes=minutes)
    elapsed = now - latest
    if elapsed < cooldown:
        wait = max(1, math.ceil((cooldown - elapsed).total_seconds() / 60))
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Следующую заявку можно отправить через {wait} мин.",
        )
