"""Разбор и проверка фискального чека по QR-коду.

Из QR доступны только эти поля (API ФНС не используем):

    t=20220712T2205&s=957.00&fn=9960440302585706&i=181&fp=2274263722&n=1

    t  — время покупки, местное для кассы, без зоны
    s  — сумма
    fn — серийник фискального накопителя: отпечаток конкретной кассы
    i  — номер фискального документа: монотонный счётчик этой кассы
    fp — фискальный признак (подпись); без API ФНС не проверяется
    n  — тип операции, 1 — приход

Подпись мы проверить не можем, поэтому опираемся на то, что подделать
дорого: свежесть чека, глобальную уникальность пары (fn, i), монотонность
счётчика и правдоподобную скорость его роста, привязку кассы к точке
и физическое присутствие человека рядом с точкой.
"""

import math
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import FiscalDrive, Receipt, Restaurant

# Время в QR: 20220712T2205 или 20220712T220530
_TIME_RE = re.compile(r"^(\d{8})T(\d{4})(\d{2})?$")
_FN_RE = re.compile(r"^\d{10,20}$")


class ReceiptError(ValueError):
    """Чек не принят. Текст сообщения показывается пользователю."""


@dataclass(frozen=True)
class ParsedReceipt:
    fn: str
    doc_number: int
    fp: str
    sum_kopeks: int
    local_time: datetime  # наивное время кассы, как в QR
    raw: str


def parse_receipt(raw: str) -> ParsedReceipt:
    """Разобрать строку QR. Принимаем и голую строку, и ссылку с параметрами."""
    text = (raw or "").strip()
    if not text:
        raise ReceiptError("Пустой код — отсканируйте QR на чеке")
    if len(text) > 300:
        raise ReceiptError("Это не похоже на QR-код чека")

    query = urlparse(text).query if "?" in text else text
    fields = {k.lower(): v[0] for k, v in parse_qs(query, keep_blank_values=False).items()}
    missing = [k for k in ("t", "s", "fn", "i", "fp") if k not in fields]
    if missing:
        raise ReceiptError(
            "В коде нет данных чека — отсканируйте именно QR с кассового чека"
        )

    # n может отсутствовать у части касс; если есть — должен быть приходом
    operation = fields.get("n", "1")
    if operation != "1":
        raise ReceiptError("Для захвата нужен чек покупки, а не возврата")

    match = _TIME_RE.match(fields["t"].upper())
    if match is None:
        raise ReceiptError("Не разобрали время в чеке")
    date_part, hm_part, sec_part = match.groups()
    try:
        local_time = datetime.strptime(date_part + hm_part, "%Y%m%d%H%M")
        if sec_part:
            local_time = local_time.replace(second=int(sec_part))
    except ValueError:
        raise ReceiptError("Не разобрали время в чеке") from None

    fn = fields["fn"].strip()
    if not _FN_RE.match(fn):
        raise ReceiptError("Не разобрали номер фискального накопителя")

    try:
        doc_number = int(fields["i"])
    except ValueError:
        raise ReceiptError("Не разобрали номер документа") from None
    if doc_number <= 0:
        raise ReceiptError("Не разобрали номер документа")

    try:
        sum_kopeks = _sum_to_kopeks(fields["s"])
    except ValueError:
        raise ReceiptError("Не разобрали сумму чека") from None

    return ParsedReceipt(
        fn=fn,
        doc_number=doc_number,
        fp=fields["fp"].strip()[:24],
        sum_kopeks=sum_kopeks,
        local_time=local_time,
        raw=text[:300],
    )


def _sum_to_kopeks(value: str) -> int:
    """«957.00», «957,00» и «95700» — всё в копейки."""
    text = value.strip().replace(",", ".")
    if "." in text:
        return int(round(float(text) * 100))
    # Без разделителя касса пишет копейки
    return int(text)


def distance_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Расстояние по большому кругу, метры."""
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def check_geo(restaurant: Restaurant, lat: float | None, lng: float | None) -> None:
    if not settings.capture_require_geo:
        return
    if lat is None or lng is None:
        raise ReceiptError(
            "Нужно разрешить доступ к геолокации — чек принимаем только на точке"
        )
    away = distance_m(lat, lng, restaurant.lat, restaurant.lng)
    if away > settings.capture_geo_radius_m:
        raise ReceiptError(
            f"Вы примерно в {round(away / 100) / 10:g} км от точки — "
            "чек принимаем только рядом с ней"
        )


def offset_from_longitude(lng: float) -> int:
    """Грубая оценка смещения точки по долготе, минуты.

    Нужна не как значение, а как ограда: часовые пояса в целом следуют за
    долготой, и отклонение больше пары часов означает, что клиент прислал
    неправдоподобное смещение.
    """
    return int(round(lng / 15.0)) * 60


def resolve_offset_minutes(
    restaurant: Restaurant, client_offset_minutes: int | None
) -> int:
    """Смещение, в котором напечатано время на чеке.

    В QR время местное и без зоны, поэтому кто-то должен сказать, какое оно.
    Спрашиваем телефон: чек принимается только в трёхстах метрах от точки,
    значит часовой пояс телефона и есть часовой пояс кассы. Поле у точки —
    запасной вариант: его заполняют руками, и по умолчанию там Москва, из-за
    чего во всех остальных поясах чек уезжал на часы.

    Присланное смещение сверяем с долготой точки: без этого достаточно было
    бы соврать про пояс, чтобы оживить вчерашний чек.
    """
    fallback = restaurant.utc_offset_minutes
    if client_offset_minutes is None:
        return fallback
    if abs(client_offset_minutes) > 14 * 60:
        return fallback
    expected = offset_from_longitude(restaurant.lng)
    if abs(client_offset_minutes - expected) > settings.receipt_offset_slack_minutes:
        return fallback
    return client_offset_minutes


def receipt_moment(
    parsed: ParsedReceipt,
    restaurant: Restaurant,
    client_offset_minutes: int | None = None,
) -> datetime:
    """Время чека в UTC: снимаем местное смещение кассы точки."""
    offset = timedelta(minutes=resolve_offset_minutes(restaurant, client_offset_minutes))
    return parsed.local_time.replace(tzinfo=timezone.utc) - offset


def check_freshness(purchased_at: datetime, now: datetime) -> None:
    age = now - purchased_at
    if age > timedelta(minutes=settings.receipt_max_age_minutes):
        raise ReceiptError(
            "Чек слишком старый — засчитываем покупку в течение "
            f"{settings.receipt_max_age_minutes} мин."
        )
    if -age > timedelta(minutes=settings.receipt_future_tolerance_minutes):
        raise ReceiptError("Время в чеке из будущего — проверьте часы на кассе")


def check_sum(parsed: ParsedReceipt) -> None:
    if parsed.sum_kopeks < settings.receipt_min_sum_kopeks:
        rubles = settings.receipt_min_sum_kopeks // 100
        raise ReceiptError(f"Чек меньше {rubles} ₽ — такой не засчитываем")


def _check_drive(
    db: Session,
    parsed: ParsedReceipt,
    restaurant: Restaurant,
    purchased_at: datetime,
    now: datetime,
) -> FiscalDrive:
    """Проверки по кассе: привязка к точке, монотонность и скорость счётчика."""
    drive = db.scalar(select(FiscalDrive).where(FiscalDrive.fn == parsed.fn))
    if drive is None:
        return FiscalDrive(
            fn=parsed.fn,
            restaurant_id=restaurant.id,
            confirmations=0,
            first_seen_at=now,
        )

    # Привязка живёт ограниченный срок: кассы меняют и переставляют
    ttl = timedelta(days=settings.receipt_bind_ttl_days)
    if drive.is_bound and drive.bound_at is not None and now - drive.bound_at > ttl:
        drive.is_bound = False
        drive.confirmations = 0
        drive.restaurant_id = restaurant.id
        drive.bound_at = None

    if drive.is_bound and drive.restaurant_id != restaurant.id:
        raise ReceiptError("Эта касса закреплена за другой точкой — чек не подходит")

    if drive.max_doc_number and parsed.doc_number <= drive.max_doc_number:
        raise ReceiptError("Такой чек с этой кассы уже был — номер документа не растёт")

    # Касса не может пробить больше правдоподобного числа чеков в минуту
    if drive.max_doc_number and drive.max_doc_at is not None:
        minutes = max((purchased_at - drive.max_doc_at).total_seconds() / 60.0, 0.0)
        jump = parsed.doc_number - drive.max_doc_number
        allowed = settings.receipt_max_i_rate_per_minute * (minutes + 1.0)
        if jump > allowed:
            raise ReceiptError("Номер документа не сходится с историей кассы")

    return drive


def register_receipt(
    db: Session,
    parsed: ParsedReceipt,
    restaurant: Restaurant,
    user_id: int,
    purchased_at: datetime,
    now: datetime,
) -> FiscalDrive:
    """Провести все проверки кассы и обновить её состояние.

    Дубликат (fn, i) отсекается уникальным индексом, но раннюю проверку тоже
    делаем — чтобы вернуть человеку понятную причину, а не 500.
    """
    exists_already = db.scalar(
        select(Receipt.id).where(
            Receipt.fn == parsed.fn, Receipt.doc_number == parsed.doc_number
        )
    )
    if exists_already is not None:
        raise ReceiptError("Этот чек уже предъявляли")

    drive = _check_drive(db, parsed, restaurant, purchased_at, now)
    drive.max_doc_number = parsed.doc_number
    drive.max_doc_at = purchased_at
    drive.last_seen_at = now

    if not drive.is_bound:
        # Привязку подтверждают разные люди на одной и той же точке
        if drive.restaurant_id != restaurant.id:
            drive.restaurant_id = restaurant.id
            drive.confirmations = 0
        others = db.scalar(
            select(func.count(func.distinct(Receipt.user_id))).where(
                Receipt.fn == parsed.fn,
                Receipt.restaurant_id == restaurant.id,
                Receipt.user_id != user_id,
            )
        ) or 0
        drive.confirmations = others + 1
        if drive.confirmations >= settings.receipt_bind_confirmations:
            drive.is_bound = True
            drive.bound_at = now

    db.add(drive)
    return drive
