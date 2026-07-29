from sqlalchemy import select

from app.models import User
from tests.test_status import make_fixtures


def auth(client, phone):
    resp = client.post(
        "/api/auth/register",
        json={"phone": phone, "password": "secret123", "display_name": "Ю"},
    )
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def link_telegram(db, phone, tg_id):
    user = db.scalar(select(User).where(User.phone == phone))
    user.telegram_id = tg_id
    db.commit()
    return user


def test_subscribe_requires_telegram(client, db):
    restaurant, promotion, _ = make_fixtures(db)
    headers = auth(client, "+79167771001")
    resp = client.post(
        "/api/subscriptions", json={"restaurant_id": restaurant.id}, headers=headers
    )
    assert resp.status_code == 400
    assert "Telegram" in resp.json()["detail"]


def test_subscribe_and_unsubscribe(client, db):
    restaurant, promotion, _ = make_fixtures(db)
    headers = auth(client, "+79167771002")
    link_telegram(db, "+79167771002", 9001)

    resp = client.post(
        "/api/subscriptions", json={"restaurant_id": restaurant.id}, headers=headers
    )
    assert resp.status_code == 201
    sub_id = resp.json()["id"]
    assert resp.json()["restaurant"]["id"] == restaurant.id

    # идемпотентно
    resp = client.post(
        "/api/subscriptions", json={"restaurant_id": restaurant.id}, headers=headers
    )
    assert resp.json()["id"] == sub_id

    resp = client.post(
        "/api/subscriptions", json={"promotion_id": promotion.id}, headers=headers
    )
    assert resp.status_code == 201

    mine = client.get("/api/subscriptions/mine", headers=headers).json()
    assert len(mine) == 2

    assert client.delete(f"/api/subscriptions/{sub_id}", headers=headers).status_code == 204
    assert len(client.get("/api/subscriptions/mine", headers=headers).json()) == 1

    # оба id сразу — ошибка
    resp = client.post(
        "/api/subscriptions",
        json={"restaurant_id": restaurant.id, "promotion_id": promotion.id},
        headers=headers,
    )
    assert resp.status_code == 400


def test_notifications_sent(client, db, monkeypatch):
    """Подписчик точки получает сообщение о новой акции сети,
    подписчик акции — о переключении статуса."""
    sent: list[tuple[int, str]] = []
    monkeypatch.setattr(
        "app.services.notify.send_batch_async", lambda msgs: sent.extend(msgs)
    )

    admin_headers = auth(client, "+79167771003")  # первый зарегистрированный — админ
    restaurant, promotion, users = make_fixtures(db)
    sub_headers = auth(client, "+79167771004")
    link_telegram(db, "+79167771004", 9100)

    # подписка на точку -> уведомление о новой акции сети
    client.post(
        "/api/subscriptions", json={"restaurant_id": restaurant.id}, headers=sub_headers
    )
    resp = client.post(
        "/api/admin/promotions",
        json={
            "brand_id": restaurant.brand_id,
            "title": "Новая коллаборация",
            "items": [{"name": "Набор"}],
        },
        headers=admin_headers,
    )
    assert resp.status_code == 201
    assert any(chat == 9100 and "Новая коллаборация" in text for chat, text in sent)

    # подписка на акцию -> уведомление о переключении статуса
    sent.clear()
    client.post(
        "/api/subscriptions", json={"promotion_id": promotion.id}, headers=sub_headers
    )
    item = promotion.items[0]
    resp = client.post(
        "/api/reports",
        json={
            "restaurant_id": restaurant.id,
            "promotion_id": promotion.id,
            "items": [{"promotion_item_id": item.id, "is_available": True}],
        },
        headers=admin_headers,
    )
    assert resp.status_code == 201
    assert any(chat == 9100 and item.name in text for chat, text in sent)
