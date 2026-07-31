import hashlib
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import User, UserRole

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer(auto_error=False)

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str | None) -> bool:
    # Пароля нет (вход был через Telegram) — сверять не с чем
    if not hashed:
        return False
    return pwd_context.verify(plain, hashed)


def password_fingerprint(user: User) -> str:
    """Короткий отпечаток текущего пароля.

    Bcrypt солит каждый хеш заново, поэтому отпечаток меняется при любой смене
    пароля — даже на такой же. Он и служит версией токена: сравнение по времени
    выдачи тут не годится, у JWT `iat` секундная точность, и токен, выданный в
    ту же секунду, что и смена, пережил бы её.
    """
    return hashlib.sha256((user.password_hash or "").encode()).hexdigest()[:16]


def create_access_token(user: User) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": str(user.id), "pv": password_fingerprint(user), "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def token_outdated(user: User, payload: dict) -> bool:
    """Токен из прошлой жизни аккаунта: пароль с тех пор сменили.

    Списка отозванных токенов у нас нет, а смена пароля обязана выкидывать
    того, кто знал старый.
    """
    fingerprint = payload.get("pv")
    if fingerprint is None:
        # Токен выдан до появления отпечатка. Он действителен, пока пароль ни
        # разу не меняли: выкатка не должна разлогинивать всех разом. Первая же
        # смена обесценивает и такие токены.
        return user.password_changed_at is not None
    return fingerprint != password_fingerprint(user)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Не авторизован")
    try:
        payload = jwt.decode(
            credentials.credentials, settings.jwt_secret, algorithms=[ALGORITHM]
        )
        user_id = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Недействительный токен")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Пользователь не найден")
    if token_outdated(user, payload):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, detail="Пароль изменён — войдите заново"
        )
    return user


def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User | None:
    """Для эндпоинтов, где авторизация желательна, но не обязательна."""
    if credentials is None:
        return None
    try:
        payload = jwt.decode(
            credentials.credentials, settings.jwt_secret, algorithms=[ALGORITHM]
        )
        user = db.get(User, int(payload["sub"]))
    except (JWTError, KeyError, ValueError):
        return None
    if user is None or token_outdated(user, payload):
        return None
    return user


def require_not_blocked(user: User = Depends(get_current_user)) -> User:
    """Для write-эндпоинтов: заблокирован — только чтение; при включённом
    REQUIRE_PHONE_VERIFICATION дополнительно нужен подтверждённый номер."""
    if user.is_blocked:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, detail="Ваш аккаунт заблокирован"
        )
    if settings.require_phone_verification and not user.is_phone_verified:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Сначала подтвердите номер через Telegram-бота — кнопка в профиле",
        )
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Требуются права администратора")
    return user
