import pytest
from sqlalchemy import select

from app.config import settings
from app.models import User
from app.services.telegram_bot import handle_update


@pytest.fixture()
def sent(monkeypatch):
    messages: list[tuple[int, str]] = []
    monkeypatch.setattr(
        "app.services.telegram_bot.send_message",
        lambda chat_id, text, reply_markup=None: messages.append((chat_id, text)),
    )
    return messages


def register(client, phone="+79161230001"):
    resp = client.post(
        "/api/auth/register",
        json={"phone": phone, "password": "secret123", "display_name": "Юзер"},
    )
    return resp.json()


def contact_update(from_id: int, phone: str, contact_user_id: int | None = None):
    return {
        "update_id": 1,
        "message": {
            "chat": {"id": from_id},
            "from": {"id": from_id},
            "contact": {
                "user_id": contact_user_id if contact_user_id is not None else from_id,
                "phone_number": phone,
            },
        },
    }


def test_contact_verifies_phone(client, db, sent):
    data = register(client)
    assert data["user"]["is_phone_verified"] is False

    handle_update(db, contact_update(from_id=42, phone="8 916 123-00-01"))

    user = db.scalar(select(User).where(User.phone == "+79161230001"))
    assert user.is_phone_verified is True
    assert user.telegram_id == 42
    assert any("подтверждён" in text for _, text in sent)


def test_foreign_contact_rejected(client, db, sent):
    register(client)
    # прислали чужой контакт — не подтверждаем
    handle_update(db, contact_update(from_id=42, phone="+79161230001", contact_user_id=99))
    user = db.scalar(select(User).where(User.phone == "+79161230001"))
    assert user.is_phone_verified is False
    assert any("чужой контакт" in text.lower() for _, text in sent)


def test_unknown_phone_gets_hint(client, db, sent):
    handle_update(db, contact_update(from_id=42, phone="+79995550000"))
    assert any("не найден" in text for _, text in sent)


def test_start_shows_keyboard(db, sent, monkeypatch):
    keyboards = []
    monkeypatch.setattr(
        "app.services.telegram_bot.send_message",
        lambda chat_id, text, reply_markup=None: keyboards.append(reply_markup),
    )
    handle_update(db, {"update_id": 1, "message": {"chat": {"id": 1}, "from": {"id": 1}, "text": "/start"}})
    assert keyboards and keyboards[0] and "keyboard" in keyboards[0]


def test_require_verification_flag(client, db, sent):
    from tests.test_status import make_fixtures

    restaurant, promotion, _ = make_fixtures(db)
    data = register(client, "+79161230002")
    headers = {"Authorization": f"Bearer {data['access_token']}"}
    body = {
        "restaurant_id": restaurant.id,
        "promotion_id": promotion.id,
        "items": [{"promotion_item_id": promotion.items[0].id, "is_available": True}],
    }

    old = settings.require_phone_verification
    settings.require_phone_verification = True
    try:
        resp = client.post("/api/reports", json=body, headers=headers)
        assert resp.status_code == 403
        assert "подтвердите номер" in resp.json()["detail"].lower()

        # подтверждаем через бота — и запись открывается
        handle_update(db, contact_update(from_id=77, phone="+79161230002"))
        resp = client.post("/api/reports", json=body, headers=headers)
        assert resp.status_code == 201
    finally:
        settings.require_phone_verification = old
