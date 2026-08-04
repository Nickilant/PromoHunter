from datetime import datetime, timedelta, timezone

from app.models import Brand, Promotion, PromotionItem, Report, ReportItem, Restaurant


def register(client, phone, name):
    response = client.post("/api/auth/register", json={"phone": phone, "password": "secret123", "display_name": name})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def fixtures(db):
    brand = Brand(name="История", slug="history")
    db.add(brand)
    db.flush()
    restaurant = Restaurant(brand_id=brand.id, city="Казань", address="Баумана, 1", lat=55.7, lng=49.1)
    promotion = Promotion(brand_id=brand.id, title="Летняя акция", items=[PromotionItem(name="Стакан", sort_order=0)])
    db.add_all([restaurant, promotion])
    db.commit()
    return restaurant, promotion


def test_issue_submission_and_review(client, db):
    admin = register(client, "+79160000101", "Админ")
    user = register(client, "+79160000102", "Пользователь")
    restaurant, promotion = fixtures(db)

    response = client.post("/api/issues", headers=user, json={
        "restaurant_id": restaurant.id,
        "promotion_id": promotion.id,
        "type": "promotion_wrong",
        "details": "В описании указана неверная комплектация",
    })
    assert response.status_code == 201
    issue_id = response.json()["id"]
    assert response.json()["promotion_title"] == "Летняя акция"

    duplicate = client.post("/api/issues", headers=user, json={
        "restaurant_id": restaurant.id,
        "promotion_id": promotion.id,
        "type": "promotion_wrong",
        "details": "Повторное сообщение об этой же ошибке",
    })
    assert duplicate.status_code == 409

    pending = client.get("/api/admin/issues?status=pending", headers=admin)
    assert pending.status_code == 200 and len(pending.json()) == 1
    reviewed = client.post(f"/api/admin/issues/{issue_id}/review", headers=admin, json={
        "status": "resolved", "moderator_comment": "Описание исправлено",
    })
    assert reviewed.status_code == 200
    assert reviewed.json()["status"] == "resolved"


def test_restaurant_history_summary(client, db):
    user = register(client, "+79160000201", "Админ")
    restaurant, promotion = fixtures(db)
    item = promotion.items[0]
    user_id = client.get("/api/auth/me", headers=user).json()["id"]
    for available, hours in ((True, 2), (True, 4), (False, 6)):
        db.add(Report(
            user_id=user_id,
            restaurant_id=restaurant.id,
            promotion_id=promotion.id,
            created_at=datetime.now(timezone.utc) - timedelta(hours=hours),
            items=[ReportItem(promotion_item_id=item.id, is_available=available)],
        ))
    db.commit()

    response = client.get(f"/api/restaurants/{restaurant.id}/history")
    assert response.status_code == 200
    data = response.json()
    assert data["reports_count"] == 3
    assert data["contributors_count"] == 1
    assert data["items"][0]["availability_percent"] == 67
