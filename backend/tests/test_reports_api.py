from tests.test_status import make_fixtures


def auth_headers(client, phone="+79165550001"):
    resp = client.post(
        "/api/auth/register",
        json={"phone": phone, "password": "secret123", "display_name": "Р"},
    )
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_report_flow_and_cooldown(client, db):
    restaurant, promotion, _ = make_fixtures(db)
    item = promotion.items[0]
    headers = auth_headers(client)

    body = {
        "restaurant_id": restaurant.id,
        "promotion_id": promotion.id,
        "items": [{"promotion_item_id": item.id, "is_available": True}],
    }
    resp = client.post("/api/reports", json=body, headers=headers)
    assert resp.status_code == 201

    # статус виден в карточке точки
    resp = client.get(f"/api/restaurants/{restaurant.id}")
    promo = next(p for p in resp.json()["promotions"] if p["id"] == promotion.id)
    st = next(i for i in promo["items"] if i["id"] == item.id)
    assert st["status"] == "available"

    # кулдаун: повторный отчёт сразу же -> 429
    resp = client.post("/api/reports", json=body, headers=headers)
    assert resp.status_code == 429
    assert "можно снова" in resp.json()["detail"]

    # по другой паре (та же акция, другая точка того же бренда) — можно
    from app.models import Restaurant

    other = Restaurant(
        brand_id=restaurant.brand_id, address="Адрес, 2", lat=1, lng=1
    )
    db.add(other)
    db.commit()
    body2 = dict(body, restaurant_id=other.id)
    assert client.post("/api/reports", json=body2, headers=headers).status_code == 201


def test_foreign_item_rejected(client, db):
    restaurant, promotion, _ = make_fixtures(db)
    headers = auth_headers(client)
    resp = client.post(
        "/api/reports",
        json={
            "restaurant_id": restaurant.id,
            "promotion_id": promotion.id,
            "items": [{"promotion_item_id": 99999, "is_available": True}],
        },
        headers=headers,
    )
    assert resp.status_code == 400


def test_blocked_user_cannot_write(client, db):
    restaurant, promotion, _ = make_fixtures(db)
    headers = auth_headers(client, "+79165550009")

    from sqlalchemy import select

    from app.models import User

    user = db.scalar(select(User).where(User.phone == "+79165550009"))
    user.is_blocked = True
    db.commit()

    resp = client.post(
        "/api/reports",
        json={
            "restaurant_id": restaurant.id,
            "promotion_id": promotion.id,
            "items": [{"promotion_item_id": promotion.items[0].id, "is_available": True}],
        },
        headers=headers,
    )
    assert resp.status_code == 403
    # читать может
    assert client.get("/api/feed", headers=headers).status_code == 200
