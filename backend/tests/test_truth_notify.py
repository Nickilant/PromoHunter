"""Отображаемый статус и уведомления: путь через базу.

Сценарий целиком — двести «есть» за два часа, потом товар кончился —
проверяется здесь же: когда меняется карточка и когда уходит бот.
"""

from datetime import datetime, timedelta, timezone

from app.models import (
    Brand,
    ItemStatusState,
    Promotion,
    PromotionItem,
    Report,
    ReportChannel,
    ReportItem,
    Restaurant,
    User,
)
from app.services.status import compute_statuses, refresh_stable_statuses

NOW = datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc)


def setup(db, users_count=8):
    brand = Brand(name="Сеть", slug="set")
    db.add(brand)
    db.flush()
    restaurant = Restaurant(brand_id=brand.id, address="Адрес, 1", lat=0, lng=0)
    promotion = Promotion(
        brand_id=brand.id,
        title="Акция",
        items=[PromotionItem(name="Товар", sort_order=0)],
    )
    db.add_all([restaurant, promotion])
    # Хеш пароля здесь не проверяется, а bcrypt на двухстах пользователях
    # съедает минуту — кладём заглушку
    db.add_all(
        [
            User(phone=f"+79{i:09d}", password_hash="x", display_name=f"U{i}")
            for i in range(users_count)
        ]
    )
    db.commit()
    users = db.query(User).order_by(User.id).all()
    return restaurant, promotion, promotion.items[0], users


def vote(db, user, restaurant, promotion, item, available, at, channel=None):
    db.add(
        Report(
            user_id=user.id,
            restaurant_id=restaurant.id,
            promotion_id=promotion.id,
            channel=channel or ReportChannel.on_site,
            created_at=at,
            items=[ReportItem(promotion_item_id=item.id, is_available=available)],
        )
    )


def display(db, restaurant, promotion, item, now=NOW):
    return compute_statuses(db, restaurant.id, [promotion.id], now).get(item.id).status


def test_transitional_status_takes_direction_from_memory(db):
    restaurant, promotion, item, users = setup(db)
    vote(db, users[0], restaurant, promotion, item, True, NOW - timedelta(minutes=50))
    vote(db, users[1], restaurant, promotion, item, True, NOW - timedelta(minutes=40))
    db.commit()
    refresh_stable_statuses(db, restaurant.id, [promotion.id], NOW)
    db.commit()
    assert display(db, restaurant, promotion, item) == "available"

    # свежий «нет» против живого консенсуса — сомнение, но не переворот
    vote(db, users[2], restaurant, promotion, item, False, NOW - timedelta(minutes=5))
    db.commit()
    assert display(db, restaurant, promotion, item) == "maybe_gone"

    # ещё двое — переворот, память меняет направление
    vote(db, users[3], restaurant, promotion, item, False, NOW - timedelta(minutes=3))
    vote(db, users[4], restaurant, promotion, item, False, NOW - timedelta(minutes=1))
    db.commit()
    refresh_stable_statuses(db, restaurant.id, [promotion.id], NOW)
    db.commit()
    assert display(db, restaurant, promotion, item) == "unavailable"

    later = NOW + timedelta(minutes=5)
    vote(db, users[5], restaurant, promotion, item, True, later)
    db.commit()
    assert display(db, restaurant, promotion, item, later) == "maybe_appeared"


def test_no_notification_before_dwell(db):
    restaurant, promotion, item, users = setup(db)
    vote(db, users[0], restaurant, promotion, item, True, NOW)
    db.commit()
    assert refresh_stable_statuses(db, restaurant.id, [promotion.id], NOW) == []
    # статус в карточке уже поменялся — молчит только бот
    assert display(db, restaurant, promotion, item) == "available"


def test_notification_after_dwell(db):
    restaurant, promotion, item, users = setup(db)
    vote(db, users[0], restaurant, promotion, item, True, NOW)
    db.commit()
    refresh_stable_statuses(db, restaurant.id, [promotion.id], NOW)
    db.commit()

    later = NOW + timedelta(minutes=11)
    flips = refresh_stable_statuses(db, restaurant.id, [promotion.id], later)
    db.commit()
    assert flips == [(item.id, "unknown", "available")]

    # повторный прогон молчит
    assert refresh_stable_statuses(db, restaurant.id, [promotion.id], later) == []


def test_cooldown_holds_the_second_message(db):
    restaurant, promotion, item, users = setup(db)
    vote(db, users[0], restaurant, promotion, item, True, NOW)
    db.commit()
    ripe = NOW + timedelta(minutes=11)
    assert refresh_stable_statuses(db, restaurant.id, [promotion.id], ripe)
    db.commit()

    # товар кончился сразу после уведомления
    for i, minutes in enumerate((1, 2, 3), start=1):
        vote(
            db, users[i], restaurant, promotion, item, False,
            ripe + timedelta(minutes=minutes),
        )
    db.commit()

    soon = ripe + timedelta(minutes=14)  # выдержка добрана, кулдаун ещё нет
    assert display(db, restaurant, promotion, item, soon) == "unavailable"
    assert refresh_stable_statuses(db, restaurant.id, [promotion.id], soon) == []

    after = ripe + timedelta(minutes=21)
    flips = refresh_stable_statuses(db, restaurant.id, [promotion.id], after)
    assert flips == [(item.id, "available", "unavailable")]


def test_run_out_after_two_hundred_yes(db):
    """Полный сценарий: два часа «есть» с редкими ошибочными «нет»,
    потом товар кончается, среди «нет» проскакивают предзаказы."""
    restaurant, promotion, item, users = setup(db, users_count=215)
    stream, tail = users[:200], users[200:]

    # два часа ровного потока «есть», последний голос — за 5 минут до конца
    for i, user in enumerate(stream):
        vote(
            db, user, restaurant, promotion, item, True,
            NOW - timedelta(minutes=5 + i * 0.6),
        )
    # пять ошибочных «нет», размазанных по потоку
    for i, minutes in enumerate((20, 45, 70, 95, 115)):
        vote(
            db, tail[i], restaurant, promotion, item, False,
            NOW - timedelta(minutes=minutes + 0.2),
        )
    db.commit()
    # два часа ровного «есть» — выдержка давно набрана, подписчики оповещены
    assert refresh_stable_statuses(db, restaurant.id, [promotion.id], NOW) == [
        (item.id, "unknown", "available")
    ]
    db.commit()
    assert display(db, restaurant, promotion, item) == "available"

    # товар кончился: «нет» раз в 40 секунд, шестым голосом — давний предзаказ
    seen = []
    for i, is_available in enumerate([False] * 5 + [True, False]):
        moment = NOW + timedelta(seconds=40 * (i + 1))
        vote(db, tail[5 + i], restaurant, promotion, item, is_available, moment)
        db.commit()
        refresh_stable_statuses(db, restaurant.id, [promotion.id], moment)
        db.commit()
        seen.append(display(db, restaurant, promotion, item, moment))

    # Первые два «нет» тонут в потоке, третий поднимает сомнение, пятый
    # переворачивает статус. Голос от давнего предзаказа сомнение возвращает,
    # но уверенность — нет: следующий «нет» ставит всё на место.
    assert seen == [
        "available",
        "available",
        "maybe_gone",
        "maybe_gone",
        "unavailable",
        "maybe_appeared",
        "unavailable",
    ]

    # Бот молчит: выдержка не набрана (её отъел голос предзаказа)
    assert refresh_stable_statuses(
        db, restaurant.id, [promotion.id], NOW + timedelta(minutes=13)
    ) == []
    # Выдержка набрана, но не вышел кулдаун после «есть»
    assert refresh_stable_statuses(
        db, restaurant.id, [promotion.id], NOW + timedelta(minutes=19)
    ) == []

    ripe = NOW + timedelta(minutes=21)
    flips = refresh_stable_statuses(db, restaurant.id, [promotion.id], ripe)
    db.commit()
    assert flips == [(item.id, "available", "unavailable")]

    state = db.get(ItemStatusState, (restaurant.id, item.id))
    assert state.stable == "unavailable"
    assert state.notified == "unavailable"
