from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.auth import get_current_user, require_not_blocked
from app.database import get_db
from app.models import Promotion, Restaurant, Subscription, User
from app.schemas import SubscriptionIn, SubscriptionOut

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


def _load(db: Session, subscription_id: int) -> Subscription:
    return db.scalar(
        select(Subscription)
        .options(
            joinedload(Subscription.restaurant).joinedload(Restaurant.brand),
            joinedload(Subscription.promotion).joinedload(Promotion.brand),
        )
        .where(Subscription.id == subscription_id)
    )


@router.get("/mine", response_model=list[SubscriptionOut])
def my_subscriptions(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    return (
        db.scalars(
            select(Subscription)
            .options(
                joinedload(Subscription.restaurant).joinedload(Restaurant.brand),
                joinedload(Subscription.promotion).joinedload(Promotion.brand),
            )
            .where(Subscription.user_id == user.id)
            .order_by(Subscription.created_at.desc())
        )
        .unique()
        .all()
    )


@router.post("", response_model=SubscriptionOut, status_code=status.HTTP_201_CREATED)
def subscribe(
    payload: SubscriptionIn,
    user: User = Depends(require_not_blocked),
    db: Session = Depends(get_db),
):
    if (payload.restaurant_id is None) == (payload.promotion_id is None):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Укажите либо точку, либо акцию",
        )
    # Уведомления доставляет бот — без привязанного Telegram подписка бесполезна
    if user.telegram_id is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Откройте сервис через Telegram-бота, чтобы получать уведомления",
        )

    if payload.restaurant_id is not None:
        if db.get(Restaurant, payload.restaurant_id) is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Точка не найдена")
        existing = db.scalar(
            select(Subscription).where(
                Subscription.user_id == user.id,
                Subscription.restaurant_id == payload.restaurant_id,
            )
        )
    else:
        if db.get(Promotion, payload.promotion_id) is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Акция не найдена")
        existing = db.scalar(
            select(Subscription).where(
                Subscription.user_id == user.id,
                Subscription.promotion_id == payload.promotion_id,
            )
        )
    if existing is not None:
        return _load(db, existing.id)

    subscription = Subscription(
        user_id=user.id,
        restaurant_id=payload.restaurant_id,
        promotion_id=payload.promotion_id,
    )
    db.add(subscription)
    db.commit()
    return _load(db, subscription.id)


@router.delete("/{subscription_id}", status_code=status.HTTP_204_NO_CONTENT)
def unsubscribe(
    subscription_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    subscription = db.get(Subscription, subscription_id)
    if subscription is None or subscription.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Подписка не найдена")
    db.delete(subscription)
    db.commit()
