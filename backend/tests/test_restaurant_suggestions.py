from sqlalchemy import select

from app.models import Brand, RatingEvent, Restaurant


def register(client, phone, name="Юзер"):
    resp = client.post(
        "/api/auth/register",
        json={"phone": phone, "password": "secret123", "display_name": name},
    )
    data = resp.json()
    return {"Authorization": f"Bearer {data['access_token']}"}, data["user"]


def test_restaurant_suggestion_flow(client, db):
    admin_headers, _ = register(client, "+79167770100", "Админ")  # первый — админ
    user_headers, user = register(client, "+79167770101", "Мария")

    brand = Brand(name="Сеть", slug="set")
    db.add(brand)
    db.commit()

    # заявка: бренд только из списка
    resp = client.post(
        "/api/restaurant-suggestions",
        json={
            "brand_id": brand.id,
            "city": "Казань",
            "address": "Баумана, 1",
            "lat": 55.79,
            "lng": 49.11,
            "comment": "Новая точка в центре",
        },
        headers=user_headers,
    )
    assert resp.status_code == 201
    sid = resp.json()["id"]
    assert resp.json()["brand"]["name"] == "Сеть"

    # Между любыми пользовательскими заявками действует общий кулдаун.
    repeated = client.post(
        "/api/restaurant-suggestions",
        json={
            "brand_id": brand.id,
            "city": "Казань",
            "address": "Баумана, 2",
            "lat": 55.79,
            "lng": 49.11,
        },
        headers=user_headers,
    )
    assert repeated.status_code == 429
    assert "через" in repeated.json()["detail"]

    # несуществующий бренд — 404
    resp = client.post(
        "/api/restaurant-suggestions",
        json={"brand_id": 999, "city": "К", "address": "А", "lat": 0, "lng": 0},
        headers=user_headers,
    )
    assert resp.status_code == 404

    # своя заявка видна
    mine = client.get("/api/restaurant-suggestions/mine", headers=user_headers).json()
    assert [s["status"] for s in mine] == ["pending"]

    # админ: сгруппировано по брендам
    groups = client.get(
        "/api/admin/restaurant-suggestions?status=pending", headers=admin_headers
    ).json()
    assert len(groups) == 1
    assert groups[0]["brand_name"] == "Сеть"
    assert len(groups[0]["suggestions"]) == 1

    # одобрение создаёт ресторан и начисляет рейтинг
    resp = client.post(
        f"/api/admin/restaurant-suggestions/{sid}/approve",
        json={
            "brand_id": brand.id,
            "city": "Казань",
            "address": "ул. Баумана, 1",
            "lat": 55.79,
            "lng": 49.11,
        },
        headers=admin_headers,
    )
    assert resp.status_code == 200
    restaurant = db.scalar(select(Restaurant).where(Restaurant.city == "Казань"))
    assert restaurant is not None and restaurant.address == "ул. Баумана, 1"
    event = db.scalar(
        select(RatingEvent).where(RatingEvent.type == "restaurant_approved")
    )
    assert event.user_id == user["id"] and event.points == 20

    # повторное одобрение — 409
    resp = client.post(
        f"/api/admin/restaurant-suggestions/{sid}/approve",
        json={"brand_id": brand.id, "city": "К", "address": "А", "lat": 0, "lng": 0},
        headers=admin_headers,
    )
    assert resp.status_code == 409


def test_restaurant_suggestion_reject_spam(client, db):
    admin_headers, _ = register(client, "+79167770200", "Админ")
    user_headers, user = register(client, "+79167770201", "Спамер")
    brand = Brand(name="Сеть2", slug="set2")
    db.add(brand)
    db.commit()

    sid = client.post(
        "/api/restaurant-suggestions",
        json={"brand_id": brand.id, "city": "Тверь", "address": "Советская, 1",
              "lat": 56.86, "lng": 35.90},
        headers=user_headers,
    ).json()["id"]

    resp = client.post(
        f"/api/admin/restaurant-suggestions/{sid}/reject",
        json={"moderator_comment": "Такой точки не существует", "is_spam": True},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"
    event = db.scalar(select(RatingEvent).where(RatingEvent.type == "restaurant_spam"))
    assert event.user_id == user["id"] and event.points == -10
