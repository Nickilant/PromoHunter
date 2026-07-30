"""Городской охват прав: кто что может модерировать.

Роли:

* ``admin`` — глобальный. Видит и правит всё, включая бренды, федеральные
  акции и пользователей.
* ``moderator`` — городской. Работает только с теми городами, что
  перечислены в ``moderator_cities``: заявки, точки и акции своих городов.
  Бренды и пользователи ему недоступны — это общие для всей страны вещи.

Город пока обычная строка, поэтому все сравнения идут по нормализованной
форме: без лишних пробелов и без учёта регистра. Иначе «Санкт-Петербург» и
«Санкт-петербург» оказались бы разными зонами ответственности, а это уже
не косметика, а дыра в правах.
"""

import re
from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from sqlalchemy import false, func, select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import ModeratorCity, User, UserRole

_SPACES = re.compile(r"\s+")


def normalize_city(value: str | None) -> str | None:
    """Каноническая форма названия города для хранения."""
    if value is None:
        return None
    cleaned = _SPACES.sub(" ", value.strip())
    return cleaned or None


def city_key(value: str | None) -> str:
    """Ключ сравнения: регистр и пробелы не должны разводить один город."""
    return (normalize_city(value) or "").casefold()


@dataclass
class Scope:
    """Что этому сотруднику разрешено. cities=None — глобальный админ."""

    user: User
    cities: set[str] | None  # ключи сравнения, не отображаемые названия

    @property
    def is_global(self) -> bool:
        return self.cities is None

    def allows(self, city: str | None) -> bool:
        if self.is_global:
            return True
        if not city:
            # Без города непонятно, чей он: такое разбирает только глобальный
            return False
        return city_key(city) in self.cities

    def require(self, city: str | None, what: str = "этот объект") -> None:
        if self.allows(city):
            return
        where = f" ({city})" if city else ""
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail=f"{what}{where} вне ваших городов",
        )

    def require_global(self, what: str = "Это действие") -> None:
        if not self.is_global:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail=f"{what} доступно только глобальному администратору",
            )


def moderator_cities(db: Session, user_id: int) -> set[str]:
    rows = db.scalars(
        select(ModeratorCity.city).where(ModeratorCity.user_id == user_id)
    ).all()
    return {city_key(city) for city in rows}


def require_staff(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Scope:
    """Доступ в админку: глобальный админ или городской модератор."""
    if user.role == UserRole.admin:
        return Scope(user=user, cities=None)
    if user.role == UserRole.moderator:
        return Scope(user=user, cities=moderator_cities(db, user.id))
    raise HTTPException(
        status.HTTP_403_FORBIDDEN, detail="Требуются права модератора"
    )


def city_filter(scope: Scope, column):
    """Условие «город в зоне ответственности» для запросов со списками."""
    if scope.is_global:
        return None
    if not scope.cities:
        # Модератор без назначенных городов не видит ничего
        return false()
    return func.lower(func.trim(column)).in_(scope.cities)
