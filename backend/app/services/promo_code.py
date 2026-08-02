"""Промокоды на скидку: свежесть, подтверждения, охват по городам.

Отдельная сущность со своей жизнью. Ни фильтр истины, ни веса пользователей,
ни игровой режим сюда не заходят: код — не предмет на полке, а информация,
и физика у неё другая. Товар кончается за часы, код живёт неделями.

Правила:

* код живёт `promo_code_ttl_days` (5 суток) и протухает, если им никто не
  пользуется;
* n-е подтверждение **одного и того же человека** продлевает срок на
  `ttl / 2^(n-1)`, но не короче `promo_code_ttl_floor_hours` (12 часов).
  Первое подтверждение от каждого сбрасывает свежесть целиком, десятое —
  только на полсуток: держать код в одиночку можно, но дёшево не выйдет;
* срок только продлевается: если у кода оставалось четыре дня, подтверждение
  с половиной суток его не обрежет;
* два «не сработал» от **разных** людей без «сработал» между ними убивают код
  досрочно — иначе мёртвый код висел бы в списке до конца срока;
* автору начисляются очки один раз за всю жизнь кода и только по первому
  подтверждению **от кого-то другого**: иначе достаточно было бы добавить код
  и подтвердить его самому.
"""

import re
from datetime import datetime, timedelta

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import PromoCode, PromoCodeCity, PromoCodeVote
from app.services.scope import city_key

# Промокоды состоят из букв, цифр и редких разделителей. Пробелы и всё, что
# похоже на ссылку, отсекаем: под видом кода не должно приезжать ничего,
# на что можно нажать
_CODE_RE = re.compile(r"^[A-Za-zА-Яа-яЁё0-9._\-]{2,64}$")


class PromoCodeError(ValueError):
    """Код не принят. Текст показывается пользователю."""


def normalize_code(raw: str) -> str:
    """Каноническая форма кода для показа: в верхнем регистре, без пробелов.

    Пробел внутри не вычищаем, а считаем признаком того, что принесли фразу,
    а не код: иначе «код с пробелом» превратился бы в валидный КОДСПРОБЕЛОМ.
    """
    text = (raw or "").strip().upper()
    if not _CODE_RE.match(text):
        raise PromoCodeError(
            "Промокод — это набор букв и цифр без пробелов и ссылок"
        )
    return text


def code_key(raw: str) -> str:
    """Ключ сравнения: регистр не должен разводить один код на два."""
    return normalize_code(raw).casefold()


def freshness_after(confirmations: int) -> timedelta:
    """Сколько живёт код после n-го подтверждения одного человека.

    confirmations — порядковый номер этого подтверждения (1 — первое).
    """
    days = settings.promo_code_ttl_days / (2 ** max(confirmations - 1, 0))
    floor_days = settings.promo_code_ttl_floor_hours / 24.0
    return timedelta(days=max(days, floor_days))


def confirmations_by(db: Session, promo_code_id: int, user_id: int) -> int:
    """Сколько раз этот человек уже подтверждал этот код (без текущего голоса)."""
    return db.scalar(
        select(func.count(PromoCodeVote.id)).where(
            PromoCodeVote.promo_code_id == promo_code_id,
            PromoCodeVote.user_id == user_id,
            PromoCodeVote.worked.is_(True),
        )
    ) or 0


def visible_clause(city: str | None):
    """Код виден в городе: глобальный или в списке своих городов."""
    if city is None:
        return PromoCode.is_global.is_(True)
    here = (
        select(PromoCodeCity.promo_code_id)
        .where(
            PromoCodeCity.promo_code_id == PromoCode.id,
            func.lower(func.trim(PromoCodeCity.city)) == city_key(city),
        )
        .exists()
    )
    return or_(PromoCode.is_global.is_(True), here)


def alive_clause(now: datetime):
    return PromoCode.expires_at > now


def live_codes(db: Session, brand_id: int, city: str | None, now: datetime) -> list[PromoCode]:
    """Живые коды сети, видимые в этом городе. Свежие — сверху."""
    stmt: Select = (
        select(PromoCode)
        .where(
            PromoCode.brand_id == brand_id,
            alive_clause(now),
            visible_clause(city),
        )
        .order_by(PromoCode.expires_at.desc())
    )
    return list(db.scalars(stmt))


def failing_user_ids(db: Session, promo_code_id: int) -> set[int]:
    """Кто пожаловался после последнего «сработал».

    Считаем именно людей, а не голоса: один человек, нажавший «не сработал»
    трижды, — это по-прежнему одно мнение.
    """
    last_worked = db.scalar(
        select(func.max(PromoCodeVote.created_at)).where(
            PromoCodeVote.promo_code_id == promo_code_id,
            PromoCodeVote.worked.is_(True),
        )
    )
    conditions = [
        PromoCodeVote.promo_code_id == promo_code_id,
        PromoCodeVote.worked.is_(False),
    ]
    if last_worked is not None:
        conditions.append(PromoCodeVote.created_at > last_worked)
    return set(db.scalars(select(PromoCodeVote.user_id).where(and_(*conditions))))


def apply_vote(
    db: Session, code: PromoCode, user_id: int, worked: bool, now: datetime
) -> bool:
    """Учесть голос. Возвращает True, если автору положены очки.

    Строку голоса пишет вызывающий код — здесь только последствия для срока.
    """
    if not worked:
        # Текущий голос ещё не записан, поэтому добавляем его к множеству сами
        complained = failing_user_ids(db, code.id) | {user_id}
        if len(complained) >= settings.promo_code_fail_votes:
            # Досрочная смерть: код перестал работать, ждать конца срока незачем
            code.expires_at = now
        return False

    # Текущее подтверждение по счёту n-е, а прошлых было n-1
    nth = confirmations_by(db, code.id, user_id) + 1
    # Срок только растёт: подтверждение не должно укорачивать чужой запас
    code.expires_at = max(code.expires_at, now + freshness_after(nth))

    award = not code.author_awarded and code.author_id is not None and code.author_id != user_id
    if award:
        code.author_awarded = True
    return award
