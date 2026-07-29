import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import telegram
from app.auth import create_access_token, get_current_user, hash_password, verify_password
from app.database import get_db
from app.models import User, UserRole
from app.phone import normalize_phone
from app.schemas import (
    LoginIn,
    RegisterIn,
    TelegramAuthIn,
    TelegramContactIn,
    TokenOut,
    UserOut,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenOut)
def register(payload: RegisterIn, db: Session = Depends(get_db)):
    exists = db.scalar(select(User).where(User.phone == payload.phone))
    if exists:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Номер уже зарегистрирован")

    users_count = db.scalar(select(func.count(User.id))) or 0
    user = User(
        phone=payload.phone,
        # Проверка номера кодом через Telegram — следующий этап.
        # Пока регистрируем без проверки и сразу считаем номер подтверждённым.
        is_phone_verified=True,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name,
        # Город из сессии становится городом по умолчанию
        city=(payload.city or "").strip() or None,
        # Первый зарегистрированный пользователь становится админом
        role=UserRole.admin if users_count == 0 else UserRole.user,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return TokenOut(access_token=create_access_token(user), user=UserOut.model_validate(user))


@router.post("/login", response_model=TokenOut)
def login(payload: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.phone == payload.phone))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Неверный номер или пароль")
    return TokenOut(access_token=create_access_token(user), user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


# --- вход через Telegram WebApp ---

def _validated_webapp_user(init_data: str) -> dict:
    if not telegram.enabled():
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, detail="Вход через Telegram не настроен"
        )
    fields = telegram.validate_init_data(init_data)
    tg_user = telegram.webapp_user(fields) if fields else None
    if tg_user is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, detail="Подпись Telegram не прошла проверку"
        )
    return tg_user


@router.post("/telegram", response_model=TokenOut)
def telegram_login(payload: TelegramAuthIn, db: Session = Depends(get_db)):
    """Вход по привязанному Telegram-аккаунту (initData из WebApp)."""
    tg_user = _validated_webapp_user(payload.init_data)
    user = db.scalar(select(User).where(User.telegram_id == tg_user["id"]))
    if user is None:
        # Аккаунт не привязан — фронт запросит номер через requestContact
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Аккаунт не привязан")
    return TokenOut(access_token=create_access_token(user), user=UserOut.model_validate(user))


@router.post("/telegram/contact", response_model=TokenOut)
def telegram_contact_login(payload: TelegramContactIn, db: Session = Depends(get_db)):
    """Вход/регистрация по номеру из Telegram (ответ requestContact).

    Номер приходит подписанным ботом — считаем его подтверждённым:
    это и есть проверка номера через Telegram.
    """
    tg_user = _validated_webapp_user(payload.init_data)
    contact = telegram.validate_contact(payload.contact_response)
    if contact is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, detail="Контакт Telegram не прошёл проверку"
        )
    # Контакт должен принадлежать тому же пользователю, что открыл WebApp
    if contact.get("user_id") != tg_user["id"]:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, detail="Контакт принадлежит другому аккаунту"
        )
    phone = normalize_phone(str(contact.get("phone_number", "")))
    if phone is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Неверный номер телефона")

    user = db.scalar(select(User).where(User.phone == phone))
    if user is None:
        users_count = db.scalar(select(func.count(User.id))) or 0
        user = User(
            phone=phone,
            is_phone_verified=True,
            # Пароль не используется при входе через Telegram; задать можно позже
            password_hash=hash_password(secrets.token_urlsafe(16)),
            display_name=(tg_user.get("first_name") or "Пользователь")[:100],
            city=(payload.city or "").strip() or None,
            role=UserRole.admin if users_count == 0 else UserRole.user,
        )
        db.add(user)
    user.telegram_id = tg_user["id"]
    user.is_phone_verified = True
    db.commit()
    db.refresh(user)
    return TokenOut(access_token=create_access_token(user), user=UserOut.model_validate(user))
