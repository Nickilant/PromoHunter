from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.auth import get_current_user, require_not_blocked
from app.database import get_db
from app.models import Brand, RestaurantSuggestion, User
from app.services.brand_visibility import brand_is_visible
from app.services.scope import normalize_city
from app.schemas import RestaurantSuggestionIn, RestaurantSuggestionOut
from app.config import settings
from app.services.abuse import enforce_suggestion_cooldown

router = APIRouter(prefix="/restaurant-suggestions", tags=["restaurant-suggestions"])


@router.post("", response_model=RestaurantSuggestionOut, status_code=status.HTTP_201_CREATED)
def create_restaurant_suggestion(
    payload: RestaurantSuggestionIn,
    user: User = Depends(require_not_blocked),
    db: Session = Depends(get_db),
):
    brand = db.get(Brand, payload.brand_id)
    if brand is None or not brand_is_visible(brand, user):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Бренд не найден")

    enforce_suggestion_cooldown(db, user.id, settings.suggestion_cooldown_minutes)

    suggestion = RestaurantSuggestion(
        user_id=user.id,
        brand_id=payload.brand_id,
        title=(payload.title or "").strip() or None,
        city=normalize_city(payload.city),
        address=payload.address.strip(),
        lat=payload.lat,
        lng=payload.lng,
        comment=(payload.comment or "").strip() or None,
    )
    db.add(suggestion)
    db.commit()
    suggestion = db.scalar(
        select(RestaurantSuggestion)
        .options(joinedload(RestaurantSuggestion.brand))
        .where(RestaurantSuggestion.id == suggestion.id)
    )
    return suggestion


@router.get("/mine", response_model=list[RestaurantSuggestionOut])
def my_restaurant_suggestions(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    return (
        db.scalars(
            select(RestaurantSuggestion)
            .options(joinedload(RestaurantSuggestion.brand))
            .where(RestaurantSuggestion.user_id == user.id)
            .order_by(RestaurantSuggestion.created_at.desc())
        )
        .unique()
        .all()
    )
