from datetime import datetime, timedelta, timezone

import pytest

from app.config import settings
from app.models import FiscalDrive, Receipt
from app.services.receipt import (
    ReceiptError,
    check_freshness,
    check_geo,
    check_sum,
    distance_m,
    parse_receipt,
    receipt_moment,
    register_receipt,
)
from tests.test_status import make_fixtures

QR = "t=20220712T2205&s=957.00&fn=9960440302585706&i=181&fp=2274263722&n=1"


def test_parse_plain_qr():
    parsed = parse_receipt(QR)
    assert parsed.fn == "9960440302585706"
    assert parsed.doc_number == 181
    assert parsed.fp == "2274263722"
    assert parsed.sum_kopeks == 95700
    assert parsed.local_time == datetime(2022, 7, 12, 22, 5)


def test_parse_accepts_url_and_seconds():
    url = "https://check.ofd.ru/rec?t=20260730T101530&s=250,50&fn=1234567890&i=7&fp=99&n=1"
    parsed = parse_receipt(url)
    assert parsed.sum_kopeks == 25050
    assert parsed.local_time.second == 30
    assert parsed.doc_number == 7


def test_parse_rejects_garbage_and_refunds():
    with pytest.raises(ReceiptError):
        parse_receipt("просто текст")
    with pytest.raises(ReceiptError):
        parse_receipt("")
    # n=2 — возврат, для захвата не годится
    with pytest.raises(ReceiptError):
        parse_receipt(QR.replace("n=1", "n=2"))
    # без обязательных полей
    with pytest.raises(ReceiptError):
        parse_receipt("t=20220712T2205&s=957.00")


def test_sum_floor():
    with pytest.raises(ReceiptError):
        check_sum(parse_receipt(QR.replace("s=957.00", "s=10.00")))
    check_sum(parse_receipt(QR))


def test_local_time_is_read_in_point_timezone(db):
    restaurant, _, _ = make_fixtures(db)
    restaurant.utc_offset_minutes = 180  # Москва
    parsed = parse_receipt(QR)
    moment = receipt_moment(parsed, restaurant)
    assert moment == datetime(2022, 7, 12, 19, 5, tzinfo=timezone.utc)

    restaurant.utc_offset_minutes = 600  # Владивосток
    assert receipt_moment(parsed, restaurant) == datetime(
        2022, 7, 12, 12, 5, tzinfo=timezone.utc
    )


def test_freshness_window():
    now = datetime.now(timezone.utc)
    check_freshness(now - timedelta(minutes=1), now)
    with pytest.raises(ReceiptError):
        check_freshness(now - timedelta(hours=3), now)
    with pytest.raises(ReceiptError):
        check_freshness(now + timedelta(minutes=30), now)


def test_geo_radius(db):
    restaurant, _, _ = make_fixtures(db)
    restaurant.lat, restaurant.lng = 59.935, 30.325
    check_geo(restaurant, 59.9352, 30.3253)
    with pytest.raises(ReceiptError):
        check_geo(restaurant, 59.99, 30.5)
    with pytest.raises(ReceiptError):
        check_geo(restaurant, None, None)


def test_distance_sanity():
    # градус широты ≈ 111 км
    assert 110_000 < distance_m(0, 0, 1, 0) < 112_000


def _register(db, restaurant, user, doc_number, minutes_ago=0):
    now = datetime.now(timezone.utc)
    parsed = parse_receipt(QR.replace("i=181", f"i={doc_number}"))
    purchased = now - timedelta(minutes=minutes_ago)
    drive = register_receipt(db, parsed, restaurant, user.id, purchased, now)
    db.add(
        Receipt(
            user_id=user.id,
            restaurant_id=restaurant.id,
            fn=parsed.fn,
            doc_number=parsed.doc_number,
            fp=parsed.fp,
            sum_kopeks=parsed.sum_kopeks,
            purchased_at=purchased,
            faction="green",
            strength=1.0,
            raw=parsed.raw,
        )
    )
    db.commit()
    return drive


def test_duplicate_receipt_rejected(db):
    restaurant, _, users = make_fixtures(db)
    _register(db, restaurant, users[0], 100)
    with pytest.raises(ReceiptError, match="уже предъявляли"):
        _register(db, restaurant, users[1], 100)


def test_counter_must_grow(db):
    restaurant, _, users = make_fixtures(db)
    _register(db, restaurant, users[0], 100)
    # номер документа меньше уже виденного — подделка
    with pytest.raises(ReceiptError, match="не растёт"):
        _register(db, restaurant, users[1], 90)


def test_counter_rate_is_capped(db):
    restaurant, _, users = make_fixtures(db)
    _register(db, restaurant, users[0], 100)
    # +100000 документов за минуту касса пробить не может
    with pytest.raises(ReceiptError, match="не сходится"):
        _register(db, restaurant, users[1], 100_100)


def test_binding_needs_several_people_then_locks_point(db):
    restaurant, _, users = make_fixtures(db)
    second = restaurant.__class__(
        brand_id=restaurant.brand_id, address="Другая, 2", lat=0, lng=0
    )
    db.add(second)
    db.commit()

    for i, user in enumerate(users[: settings.receipt_bind_confirmations]):
        drive = _register(db, restaurant, user, 200 + i)
    assert drive.is_bound is True

    # Та же касса «на другой точке» — так не бывает
    with pytest.raises(ReceiptError, match="другой точкой"):
        _register(db, second, users[3], 300)


def test_binding_resets_after_ttl(db):
    restaurant, _, users = make_fixtures(db)
    old_point = restaurant.__class__(
        brand_id=restaurant.brand_id, address="Старая, 3", lat=0, lng=0
    )
    db.add(old_point)
    db.commit()
    now = datetime.now(timezone.utc)
    drive = FiscalDrive(
        fn="9960440302585706",
        restaurant_id=old_point.id,
        confirmations=3,
        is_bound=True,
        max_doc_number=5,
        max_doc_at=now - timedelta(days=400),
        bound_at=now - timedelta(days=settings.receipt_bind_ttl_days + 5),
    )
    db.add(drive)
    db.commit()
    # Просроченная привязка не должна мешать: касса переехала
    _register(db, restaurant, users[0], 500)
    db.refresh(drive)
    assert drive.restaurant_id == restaurant.id
