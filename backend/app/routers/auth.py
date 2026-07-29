import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app import telegram
from app.auth import create_access_token, get_current_user, hash_password, verify_password
from app.config import settings
from app.database import get_db
from app.models import PhoneVerification, User, UserRole
from app.phone import normalize_phone
from app.schemas import (
    LoginIn,
    PhoneVerificationConfirmIn,
    PhoneVerificationConfirmOut,
    PhoneVerificationRequestIn,
    PhoneVerificationRequestOut,
    RegisterIn,
    TelegramAuthIn,
    TelegramContactIn,
    TokenOut,
    UserOut,
)

router = APIRouter(prefix="/auth", tags=["auth"])


# --- подтверждение номера кодом при регистрации ---

@router.post("/phone-verification/request", response_model=PhoneVerificationRequestOut)
def request_phone_code(payload: PhoneVerificationRequestIn, db: Session = Depends(get_db)):
    """Сгенерировать код. Если бот уже знает этот номер — код уходит сразу,
    иначе пользователю нужно отправить боту свой контакт, и код придёт."""
    if not telegram.enabled():
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, detail="Подтверждение через Telegram не настроено"
        )
    if db.scalar(select(User).where(User.phone == payload.phone)):
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Номер уже зарегистрирован")

    now = datetime.now(timezone.utc)
    pending = db.scalar(
        select(PhoneVerification)
        .where(PhoneVerification.phone == payload.phone)
        .order_by(PhoneVerification.id.desc())
    )
    if (
        pending is not None
        and not pending.is_confirmed
        and (now - pending.created_at).total_seconds() < settings.phone_code_resend_seconds
    ):
        wait = settings.phone_code_resend_seconds - int(
            (now - pending.created_at).total_seconds()
        )
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Код уже отправлен — повторно можно через {wait} сек.",
        )

    # Телеграм этого номера знаком по прошлым заявкам?
    known_telegram_id = db.scalar(
        select(PhoneVerification.telegram_id)
        .where(
            PhoneVerification.phone == payload.phone,
            PhoneVerification.telegram_id.is_not(None),
        )
        .order_by(PhoneVerification.id.desc())
    )
    db.execute(delete(PhoneVerification).where(PhoneVerification.phone == payload.phone))

    code = f"{secrets.randbelow(10000):04d}"
    verification = PhoneVerification(
        phone=payload.phone,
        code=code,
        telegram_id=known_telegram_id,
        expires_at=now + timedelta(minutes=settings.phone_code_ttl_minutes),
    )
    db.add(verification)
    db.commit()

    if known_telegram_id is not None:
        telegram.send_message(
            known_telegram_id,
            f"Ваш код подтверждения PromoHunter: <b>{code}</b>\n"
            f"Код действует {settings.phone_code_ttl_minutes} минут.",
        )
        return PhoneVerificationRequestOut(
            delivery="sent", bot_username=telegram.bot_username()
        )
    return PhoneVerificationRequestOut(
        delivery="await_contact", bot_username=telegram.bot_username()
    )


@router.post("/phone-verification/confirm", response_model=PhoneVerificationConfirmOut)
def confirm_phone_code(payload: PhoneVerificationConfirmIn, db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    verification = db.scalar(
        select(PhoneVerification)
        .where(
            PhoneVerification.phone == payload.phone,
            PhoneVerification.is_confirmed.is_(False),
        )
        .order_by(PhoneVerification.id.desc())
    )
    if verification is None or verification.expires_at < now:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Код не запрошен или устарел — запросите новый",
        )
    if verification.attempts >= settings.phone_code_max_attempts:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Слишком много попыток — запросите новый код",
        )
    if verification.code != payload.code.strip():
        verification.attempts += 1
        db.commit()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Неверный код")
    verification.is_confirmed = True
    db.commit()
    return PhoneVerificationConfirmOut(verified=True)


@router.post("/register", response_model=TokenOut)
def register(payload: RegisterIn, db: Session = Depends(get_db)):
    exists = db.scalar(select(User).where(User.phone == payload.phone))
    if exists:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Номер уже зарегистрирован")

    verified = False
    verified_telegram_id = None
    if telegram.enabled():
        # Регистрация только с подтверждённым кодом (запрошенным за последний час)
        now = datetime.now(timezone.utc)
        verification = db.scalar(
            select(PhoneVerification)
            .where(
                PhoneVerification.phone == payload.phone,
                PhoneVerification.is_confirmed.is_(True),
                PhoneVerification.created_at >= now - timedelta(hours=1),
            )
            .order_by(PhoneVerification.id.desc())
        )
        if verification is None:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail="Сначала подтвердите номер кодом из Telegram",
            )
        verified = True
        verified_telegram_id = verification.telegram_id
        db.execute(
            delete(PhoneVerification).where(PhoneVerification.phone == payload.phone)
        )
    # Telegram не настроен (локальная разработка) — регистрация без кода

    users_count = db.scalar(select(func.count(User.id))) or 0
    user = User(
        phone=payload.phone,
        is_phone_verified=verified,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name,
        # Город из сессии становится городом по умолчанию
        city=(payload.city or "").strip() or None,
        # Первый зарегистрированный пользователь становится админом
        role=UserRole.admin if users_count == 0 else UserRole.user,
    )
    # Привязываем Telegram, через который пришёл код, — заработают уведомления
    if verified_telegram_id is not None and not db.scalar(
        select(User).where(User.telegram_id == verified_telegram_id)
    ):
        user.telegram_id = verified_telegram_id
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
