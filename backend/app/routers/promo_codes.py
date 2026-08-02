"""Промокоды сети: список, добавление, подтверждение использования."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.auth import get_current_user_optional, require_not_blocked
from app.config import settings
from app.database import get_db
from app.models import (
    Brand,
    PromoCode,
    PromoCodeCity,
    PromoCodeVote,
    RatingEvent,
    User,
)
from app.schemas import PromoCodeIn, PromoCodeOut, PromoCodeVoteIn
from app.services.promo_code import (
    PromoCodeError,
    apply_vote,
    code_key,
    confirmations_by,
    freshness_after,
    live_codes,
    normalize_code,
)
from app.services.scope import normalize_city

router = APIRouter(prefix="/promo-codes", tags=["promo-codes"])


def _out(db: Session, code: PromoCode, viewer: User | None) -> PromoCodeOut:
    confirmations = db.scalar(
        select(func.count(PromoCodeVote.id)).where(
            PromoCodeVote.promo_code_id == code.id,
            PromoCodeVote.worked.is_(True),
        )
    ) or 0
    mine = viewer is not None and code.author_id == viewer.id
    confirmed = bool(
        viewer is not None and confirmations_by(db, code.id, viewer.id)
    )
    return PromoCodeOut(
        id=code.id,
        code=code.code,
        description=code.description,
        is_global=code.is_global,
        cities=sorted(c.city for c in code.cities),
        author_name=code.author.display_name if code.author else None,
        confirmations=confirmations,
        expires_at=code.expires_at,
        created_at=code.created_at,
        confirmed_by_me=confirmed,
        is_mine=mine,
    )


@router.get("", response_model=list[PromoCodeOut])
def list_promo_codes(
    brand_id: int,
    city: str | None = Query(default=None),
    db: Session = Depends(get_db),
    viewer: User | None = Depends(get_current_user_optional),
):
    """Живые коды сети, видимые в этом городе."""
    now = datetime.now(timezone.utc)
    codes = live_codes(db, brand_id, normalize_city(city), now)
    # Автор и города нужны каждой строке — подтягиваем разом
    if codes:
        db.execute(
            select(PromoCode)
            .options(joinedload(PromoCode.author), selectinload(PromoCode.cities))
            .where(PromoCode.id.in_([c.id for c in codes]))
        )
    return [_out(db, code, viewer) for code in codes]


@router.post("", response_model=PromoCodeOut, status_code=status.HTTP_201_CREATED)
def add_promo_code(
    payload: PromoCodeIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_not_blocked),
):
    """Добавить код. Тот же код у той же сети — оживление старой строки."""
    now = datetime.now(timezone.utc)
    brand = db.get(Brand, payload.brand_id)
    if brand is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Сеть не найдена")

    try:
        code_text = normalize_code(payload.code)
        key = code_key(payload.code)
    except PromoCodeError as error:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(error)) from None

    city = normalize_city(payload.city)
    if not payload.is_global and not city:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Для регионального кода нужен город",
        )

    day_ago = now - timedelta(days=1)
    added_today = db.scalar(
        select(func.count(PromoCode.id)).where(
            PromoCode.author_id == user.id, PromoCode.created_at >= day_ago
        )
    ) or 0
    if added_today >= settings.promo_code_daily_limit:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail="На сегодня хватит промокодов — попробуйте завтра",
        )

    existing = db.scalar(
        select(PromoCode)
        .options(selectinload(PromoCode.cities))
        .where(PromoCode.brand_id == brand.id, PromoCode.code_key == key)
    )
    if existing is not None:
        if existing.expires_at > now:
            raise HTTPException(
                status.HTTP_409_CONFLICT, detail="Такой промокод уже в списке"
            )
        # Протухший код оживает без новых очков автору: иначе достаточно было
        # бы дождаться конца срока и принести его заново
        existing.expires_at = now + freshness_after(1)
        if city and not existing.is_global:
            if all(c.city != city for c in existing.cities):
                existing.cities.append(PromoCodeCity(city=city))
        db.commit()
        db.refresh(existing)
        return _out(db, existing, user)

    code = PromoCode(
        brand_id=brand.id,
        code=code_text,
        code_key=key,
        description=payload.description.strip(),
        author_id=user.id,
        is_global=payload.is_global,
        expires_at=now + freshness_after(1),
    )
    if not payload.is_global and city:
        code.cities.append(PromoCodeCity(city=city))
    db.add(code)
    db.commit()
    db.refresh(code)
    return _out(db, code, user)


@router.post("/{promo_code_id}/vote", response_model=PromoCodeOut)
def vote_promo_code(
    promo_code_id: int,
    payload: PromoCodeVoteIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_not_blocked),
):
    """«Сработал» продлевает жизнь кода, «не сработал» приближает его конец."""
    now = datetime.now(timezone.utc)
    code = db.scalar(
        select(PromoCode)
        .options(joinedload(PromoCode.author), selectinload(PromoCode.cities))
        .where(PromoCode.id == promo_code_id)
    )
    if code is None or code.expires_at <= now:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Промокод не найден")

    award = apply_vote(db, code, user.id, payload.worked, now)
    db.add(
        PromoCodeVote(
            promo_code_id=code.id, user_id=user.id, worked=payload.worked
        )
    )
    if award:
        db.add(
            RatingEvent(
                user_id=code.author_id,
                city=None,
                type="promo_code_used",
                points=settings.promo_code_author_points,
            )
        )
    db.commit()
    db.refresh(code)
    return _out(db, code, user)
