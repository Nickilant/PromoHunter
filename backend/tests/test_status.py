from datetime import datetime, timedelta, timezone

from app.auth import hash_password
from app.models import (
    Brand,
    Promotion,
    PromotionItem,
    Report,
    ReportItem,
    Restaurant,
    User,
)
from app.services.status import compute_statuses


def make_fixtures(db, item_names=("Товар А", "Товар Б")):
    brand = Brand(name="Сеть", slug="set")
    db.add(brand)
    db.flush()
    restaurant = Restaurant(brand_id=brand.id, address="Адрес, 1", lat=0, lng=0)
    promotion = Promotion(
        brand_id=brand.id,
        title="Акция",
        items=[PromotionItem(name=n, sort_order=i) for i, n in enumerate(item_names)],
    )
    db.add_all([restaurant, promotion])
    users = [
        User(email=f"u{i}@example.com", password_hash=hash_password("x"), display_name=f"U{i}")
        for i in range(4)
    ]
    db.add_all(users)
    db.commit()
    return restaurant, promotion, users


def report(db, user, restaurant, promotion, votes, ago: timedelta):
    r = Report(
        user_id=user.id,
        restaurant_id=restaurant.id,
        promotion_id=promotion.id,
        created_at=datetime.now(timezone.utc) - ago,
        items=[
            ReportItem(promotion_item_id=item_id, is_available=v)
            for item_id, v in votes.items()
        ],
    )
    db.add(r)
    db.commit()
    return r


def test_all_four_statuses(db):
    restaurant, promotion, users = make_fixtures(
        db, ("Доступный", "Кончился", "Спорный", "Неизвестный")
    )
    a, b, c, _ = [item.id for item in promotion.items]
    h = timedelta(hours=1)
    report(db, users[0], restaurant, promotion, {a: True, b: False}, 2 * h)
    report(db, users[1], restaurant, promotion, {a: True, c: True}, 3 * h)
    report(db, users[2], restaurant, promotion, {b: False, c: False}, 4 * h)

    statuses = compute_statuses(db, restaurant.id, [promotion.id])
    assert statuses.get(a).status == "available"
    assert (statuses.get(a).yes_count, statuses.get(a).no_count) == (2, 0)
    assert statuses.get(b).status == "unavailable"
    assert statuses.get(c).status == "disputed"
    unknown = statuses.get(promotion.items[3].id)
    assert unknown.status == "unknown"
    assert unknown.last_report_at is None


def test_reports_outside_window_ignored(db):
    restaurant, promotion, users = make_fixtures(db)
    a = promotion.items[0].id
    report(db, users[0], restaurant, promotion, {a: True}, timedelta(hours=30))
    statuses = compute_statuses(db, restaurant.id, [promotion.id])
    assert statuses.get(a).status == "unknown"


def test_only_latest_report_per_user_counts(db):
    """Один человек не может перевесить объёмом: считается его последний отчёт."""
    restaurant, promotion, users = make_fixtures(db)
    a = promotion.items[0].id
    # users[0] трижды сказал «есть», но потом сказал «нет»
    report(db, users[0], restaurant, promotion, {a: True}, timedelta(hours=5))
    report(db, users[0], restaurant, promotion, {a: True}, timedelta(hours=4))
    report(db, users[0], restaurant, promotion, {a: True}, timedelta(hours=3))
    report(db, users[0], restaurant, promotion, {a: False}, timedelta(hours=1))
    report(db, users[1], restaurant, promotion, {a: True}, timedelta(hours=2))

    st = compute_statuses(db, restaurant.id, [promotion.id]).get(a)
    assert (st.yes_count, st.no_count) == (1, 1)
    assert st.status == "disputed"


def test_last_report_at(db):
    restaurant, promotion, users = make_fixtures(db)
    a = promotion.items[0].id
    report(db, users[0], restaurant, promotion, {a: True}, timedelta(hours=6))
    fresh = report(db, users[1], restaurant, promotion, {a: True}, timedelta(hours=1))
    st = compute_statuses(db, restaurant.id, [promotion.id]).get(a)
    assert st.last_report_at == fresh.created_at
