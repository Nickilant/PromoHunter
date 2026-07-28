"""Сиды тестовых данных. Идемпотентны: повторный запуск не плодит дубли.

Запуск:  python -m app.seed            — досоздать недостающее
         python -m app.seed --if-empty — только если таблица users пуста
"""

import random
import sys
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import hash_password
from app.database import SessionLocal
from app.models import (
    Brand,
    Promotion,
    PromotionItem,
    PromotionSuggestion,
    Report,
    ReportItem,
    Restaurant,
    User,
    UserRole,
)

rng = random.Random(42)


def get_or_create_user(db: Session, phone: str, name: str, role: UserRole) -> User:
    user = db.scalar(select(User).where(User.phone == phone))
    if user is None:
        password = "admin123" if role == UserRole.admin else "user123"
        user = User(
            phone=phone,
            is_phone_verified=True,
            password_hash=hash_password(password),
            display_name=name,
            city="Санкт-Петербург",
            role=role,
        )
        db.add(user)
        db.flush()
    return user


def get_or_create_brand(db: Session, name: str, slug: str, color: str) -> Brand:
    brand = db.scalar(select(Brand).where(Brand.name == name))
    if brand is None:
        brand = Brand(name=name, slug=slug, color=color)
        db.add(brand)
        db.flush()
    return brand


def get_or_create_restaurant(
    db: Session,
    brand: Brand,
    title: str | None,
    address: str,
    lat: float,
    lng: float,
    city: str = "Санкт-Петербург",
) -> Restaurant:
    restaurant = db.scalar(
        select(Restaurant).where(
            Restaurant.brand_id == brand.id, Restaurant.address == address
        )
    )
    if restaurant is None:
        restaurant = Restaurant(
            brand_id=brand.id, title=title, city=city, address=address, lat=lat, lng=lng
        )
        db.add(restaurant)
        db.flush()
    return restaurant


def get_or_create_promotion(
    db: Session,
    brand: Brand,
    title: str,
    description: str,
    items: list[str],
    starts_at: datetime | None = None,
    ends_at: datetime | None = None,
) -> Promotion:
    promotion = db.scalar(
        select(Promotion).where(Promotion.brand_id == brand.id, Promotion.title == title)
    )
    if promotion is None:
        promotion = Promotion(
            brand_id=brand.id,
            title=title,
            description=description,
            starts_at=starts_at,
            ends_at=ends_at,
            items=[PromotionItem(name=name, sort_order=i) for i, name in enumerate(items)],
        )
        db.add(promotion)
        db.flush()
    return promotion


def add_report(
    db: Session,
    user: User,
    restaurant: Restaurant,
    promotion: Promotion,
    votes: dict[int, bool],
    created_at: datetime,
) -> None:
    report = Report(
        user_id=user.id,
        restaurant_id=restaurant.id,
        promotion_id=promotion.id,
        created_at=created_at,
        items=[
            ReportItem(promotion_item_id=item_id, is_available=is_available)
            for item_id, is_available in votes.items()
        ],
    )
    db.add(report)


def seed(db: Session) -> None:
    now = datetime.now(timezone.utc)

    # --- пользователи ---
    admin = get_or_create_user(db, "+79990000000", "Админ", UserRole.admin)
    users = [
        get_or_create_user(db, "+79990000001", "Мария", UserRole.user),
        get_or_create_user(db, "+79990000002", "Иван", UserRole.user),
        get_or_create_user(db, "+79990000003", "Ольга", UserRole.user),
        get_or_create_user(db, "+79990000004", "Дмитрий", UserRole.user),
    ]

    # --- бренды ---
    vit = get_or_create_brand(db, "Вкусно и точка", "vkusno-i-tochka", "#D9822B")
    bk = get_or_create_brand(db, "Бургер Кинг", "burger-king", "#8A4B2D")
    rostics = get_or_create_brand(db, "Rostic's", "rostics", "#B03A3A")

    # --- рестораны (Санкт-Петербург) ---
    restaurants = [
        get_or_create_restaurant(db, vit, None, "Невский пр., 55", 59.9320, 30.3500),
        get_or_create_restaurant(
            db, vit, "ТЦ Галерея, 2 этаж", "Лиговский пр., 30А", 59.9270, 30.3609
        ),
        get_or_create_restaurant(db, vit, None, "Большой пр. П.С., 35", 59.9575, 30.3010),
        get_or_create_restaurant(db, vit, None, "Московский пр., 137", 59.8830, 30.3180),
        get_or_create_restaurant(db, bk, None, "Лиговский пр., 10", 59.9310, 30.3620),
        get_or_create_restaurant(
            db, bk, "ТРК Гранд Каньон", "пр. Энгельса, 154", 60.0510, 30.3330
        ),
        get_or_create_restaurant(db, bk, None, "Садовая ул., 28", 59.9270, 30.3200),
        get_or_create_restaurant(db, bk, None, "Ленинский пр., 100", 59.8520, 30.2620),
        get_or_create_restaurant(
            db, rostics, None, "Средний пр. В.О., 36", 59.9430, 30.2780
        ),
        get_or_create_restaurant(
            db, rostics, None, "Каменноостровский пр., 37", 59.9630, 30.3110
        ),
        get_or_create_restaurant(
            db, rostics, None, "пр. Просвещения, 19", 60.0510, 30.3900
        ),
        get_or_create_restaurant(
            db, rostics, "ТРК Балканский", "Балканская пл., 5", 59.8290, 30.3790
        ),
    ]
    # Москва — чтобы было видно переключение города
    moscow = [
        get_or_create_restaurant(
            db, vit, None, "Тверская ул., 12", 55.7615, 37.6095, city="Москва"
        ),
        get_or_create_restaurant(
            db, bk, None, "Арбат, 30", 55.7495, 37.5905, city="Москва"
        ),
        get_or_create_restaurant(
            db, rostics, None, "Мясницкая ул., 15", 55.7638, 37.6330, city="Москва"
        ),
    ]

    # --- акции ---
    cups = get_or_create_promotion(
        db,
        vit,
        "Брендированные стаканы",
        "Коллекционные пластиковые стаканы шести цветов к напиткам большого размера.",
        [
            "Стакан красный",
            "Стакан синий",
            "Стакан зелёный",
            "Стакан жёлтый",
            "Стакан фиолетовый",
            "Стакан оранжевый",
        ],
        ends_at=now + timedelta(days=14),
    )
    collab = get_or_create_promotion(
        db,
        bk,
        "Коллаборация с «Атакой титанов»",
        "Наборы с коллекционными фигурками героев аниме.",
        ["Набор с Микаса", "Набор с Эреном", "Набор с Леви"],
        ends_at=now + timedelta(days=10),
    )
    bucket = get_or_create_promotion(
        db,
        rostics,
        "Весёлое ведро",
        "Ведро крыльев с наклейками и постером в подарок.",
        ["Ведро с наклейками", "Постер в подарок"],
    )
    sauce = get_or_create_promotion(
        db,
        vit,
        "Соус сезона",
        "Лимитированный кисло-сладкий острый соус.",
        ["Соус кисло-сладкий острый"],
        starts_at=now - timedelta(days=30),
        ends_at=now + timedelta(days=5),
    )

    # --- отчёты ---
    reports_exist = (db.scalar(select(func.count(Report.id))) or 0) > 0
    if not reports_exist:
        all_users = [admin] + users
        cup_ids = [item.id for item in cups.items]

        # Первая точка ВиТ: гарантируем все четыре статуса стаканов.
        r0 = restaurants[0]
        h = timedelta(hours=1)
        # красный: 3×да -> available
        add_report(db, users[0], r0, cups, {cup_ids[0]: True, cup_ids[1]: False}, now - 2 * h)
        add_report(db, users[1], r0, cups, {cup_ids[0]: True, cup_ids[2]: True}, now - 3 * h)
        add_report(db, users[2], r0, cups, {cup_ids[0]: True, cup_ids[1]: False}, now - 5 * h)
        # синий: 2×нет -> unavailable (голоса выше)
        # зелёный: 1×да и 1×нет -> disputed
        add_report(db, users[3], r0, cups, {cup_ids[2]: False}, now - 4 * h)
        # жёлтый: отчёт старше окна 24ч -> unknown
        add_report(db, admin, r0, cups, {cup_ids[3]: True}, now - timedelta(hours=40))
        # фиолетовый и оранжевый: отчётов нет -> unknown

        # Остальные точки (включая Москву): случайный разброс за последние 48 часов.
        pairs = []
        for restaurant in restaurants[1:] + moscow:
            if restaurant.brand_id == vit.id:
                promos = [cups, sauce]
            elif restaurant.brand_id == bk.id:
                promos = [collab]
            else:
                promos = [bucket]
            for promo in promos:
                pairs.append((restaurant, promo))

        created = 5
        while created < 60:
            restaurant, promo = rng.choice(pairs)
            reporters = rng.sample(all_users, k=rng.randint(1, 3))
            for user in reporters:
                votes = {}
                for item in promo.items:
                    if rng.random() < 0.35:
                        continue  # «не смотрел»
                    votes[item.id] = rng.random() < 0.65
                if not votes:
                    votes = {promo.items[0].id: True}
                add_report(
                    db,
                    user,
                    restaurant,
                    promo,
                    votes,
                    now - timedelta(minutes=rng.randint(10, 48 * 60)),
                )
                created += 1
        db.flush()

    # --- заявки на акции ---
    suggestions_exist = (db.scalar(select(func.count(PromotionSuggestion.id))) or 0) > 0
    if not suggestions_exist:
        def suggest(user, brand, raw, title, description, items, days_ago):
            db.add(
                PromotionSuggestion(
                    user_id=user.id,
                    brand_id=brand.id if brand else None,
                    brand_name_raw=raw,
                    title=title,
                    description=description,
                    items_raw="\n".join(items),
                    created_at=now - timedelta(days=days_ago),
                )
            )

        # Три дубликата по Бургер Кингу — для проверки группировки
        suggest(
            users[0], bk, None, "Игрушки «Кот в сапогах»",
            "В детских наборах теперь фигурки из мультфильма.",
            ["Фигурка Кота", "Фигурка Киски Мягколапки"], 1,
        )
        suggest(
            users[1], bk, None, "Наборы с котом в сапогах",
            "Видел новые игрушки в наборе.", ["Кот в сапогах"], 2,
        )
        suggest(
            users[2], bk, None, "Кот в сапогах — детский набор",
            None, ["Фигурка кота", "Наклейки"], 3,
        )
        # Бренда нет в базе — группировка по brand_name_raw без учёта регистра
        suggest(
            users[3], None, "Теремок", "Блин с пылу с жару бесплатно",
            "При заказе от 500 рублей дают фирменный блин.", ["Блин фирменный"], 1,
        )
        suggest(
            users[0], None, "теремок", "Бесплатный блин",
            None, ["Блин"], 4,
        )
        suggest(
            users[1], rostics, None, "Кружка Rostic's",
            "Красная кружка при покупке большого кофе.", ["Кружка красная"], 2,
        )

    db.commit()


def main() -> None:
    db = SessionLocal()
    try:
        if "--if-empty" in sys.argv:
            users_count = db.scalar(select(func.count(User.id))) or 0
            if users_count > 0:
                print("Seed: users table is not empty, skipping")
                return
        seed(db)
        print("Seed: done")
    finally:
        db.close()


if __name__ == "__main__":
    main()
