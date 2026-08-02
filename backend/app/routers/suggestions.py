from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_not_blocked
from app.database import get_db
from app.models import Brand, PromotionSuggestion, Restaurant, User
from app.schemas import SuggestionIn, SuggestionOut
from app.services.scope import normalize_city

router = APIRouter(prefix="/suggestions", tags=["suggestions"])


@router.post("", response_model=SuggestionOut, status_code=status.HTTP_201_CREATED)
def create_suggestion(
    payload: SuggestionIn,
    user: User = Depends(require_not_blocked),
    db: Session = Depends(get_db),
):
    brand_name_raw = (payload.brand_name_raw or "").strip() or None
    if payload.brand_id is None and brand_name_raw is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Укажите бренд из списка или введите его название",
        )
    if payload.brand_id is not None and db.get(Brand, payload.brand_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Бренд не найден")
    restaurant = None
    if payload.restaurant_id is not None:
        restaurant = db.get(Restaurant, payload.restaurant_id)
        if restaurant is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Точка не найдена")
    if not payload.items_raw.strip():
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="Укажите хотя бы один товар"
        )

    suggestion = PromotionSuggestion(
        user_id=user.id,
        brand_id=payload.brand_id,
        brand_name_raw=brand_name_raw if payload.brand_id is None else None,
        restaurant_id=payload.restaurant_id,
        title=payload.title.strip(),
        description=(payload.description or "").strip() or None,
        items_raw=payload.items_raw.strip(),
        # Город нужен, чтобы заявка попала к модератору этого города:
        # у самой акции города нет, она принадлежит бренду
        city=normalize_city(restaurant.city if restaurant else user.city),
    )
    db.add(suggestion)
    db.commit()
    db.refresh(suggestion)
    return suggestion


@router.get("/mine", response_model=list[SuggestionOut])
def my_suggestions(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    return db.scalars(
        select(PromotionSuggestion)
        .where(PromotionSuggestion.user_id == user.id)
        .order_by(PromotionSuggestion.created_at.desc())
    ).all()
