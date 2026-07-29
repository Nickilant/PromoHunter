import pytest
from sqlalchemy import select

from app.config import settings
from app.models import PhoneVerification, User
from app.services.telegram_bot import handle_update


@pytest.fixture()
def telegram_on(monkeypatch):
    old = settings.telegram_bot_token
    settings.telegram_bot_token = "12345:TEST"
    monkeypatch.setattr("app.telegram.bot_username", lambda: "promohunter_bot")
    yield
    settings.telegram_bot_token = old


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


def test_registration_code_flow(client, db, telegram_on, sent, monkeypatch):
    """Полный сценарий из формы регистрации: запрос кода -> контакт боту ->
    код в Telegram -> подтверждение -> регистрация."""
    direct: list[tuple[int, str]] = []
    monkeypatch.setattr(
        "app.telegram.send_message",
        lambda chat_id, text, reply_markup=None: direct.append((chat_id, text)),
    )

    # 1. «Подтвердить номер»: бот этот номер ещё не знает
    resp = client.post(
        "/api/auth/phone-verification/request", json={"phone": "+79167770301"}
    )
    assert resp.status_code == 200
    assert resp.json() == {"delivery": "await_contact", "bot_username": "promohunter_bot"}

    # без кода регистрация закрыта
    resp = client.post(
        "/api/auth/register",
        json={"phone": "+79167770301", "password": "secret123", "display_name": "Аня"},
    )
    assert resp.status_code == 403

    # повторный запрос сразу — кулдаун
    resp = client.post(
        "/api/auth/phone-verification/request", json={"phone": "+79167770301"}
    )
    assert resp.status_code == 429

    # 2. Пользователь отправил боту контакт — бот прислал код
    handle_update(db, contact_update(from_id=505, phone="+79167770301"))
    code_message = next(text for chat, text in sent if chat == 505)
    verification = db.scalar(
        select(PhoneVerification).where(PhoneVerification.phone == "+79167770301")
    )
    assert verification.code in code_message
    assert verification.telegram_id == 505

    # 3. Неверный код — отказ, верный — подтверждение
    resp = client.post(
        "/api/auth/phone-verification/confirm",
        json={"phone": "+79167770301", "code": "9999"},
    )
    assert resp.status_code == 400
    resp = client.post(
        "/api/auth/phone-verification/confirm",
        json={"phone": "+79167770301", "code": verification.code},
    )
    assert resp.status_code == 200 and resp.json()["verified"] is True

    # 4. Регистрация проходит; номер подтверждён, Telegram привязан
    resp = client.post(
        "/api/auth/register",
        json={"phone": "+7 916 777-03-01", "password": "secret123", "display_name": "Аня"},
    )
    assert resp.status_code == 200
    user = resp.json()["user"]
    assert user["is_phone_verified"] is True
    assert user["has_telegram"] is True

    # 5. Повторный запрос кода на занятый номер — 409
    resp = client.post(
        "/api/auth/phone-verification/request", json={"phone": "+79167770301"}
    )
    assert resp.status_code == 409


def test_code_sent_directly_when_telegram_known(client, db, telegram_on, monkeypatch):
    """Если бот уже знает номер (прошлая заявка) — код уходит сразу."""
    direct: list[tuple[int, str]] = []
    monkeypatch.setattr(
        "app.telegram.send_message",
        lambda chat_id, text, reply_markup=None: direct.append((chat_id, text)),
    )
    from datetime import datetime, timedelta, timezone

    db.add(
        PhoneVerification(
            phone="+79167770400",
            code="1111",
            telegram_id=606,
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
            created_at=datetime.now(timezone.utc) - timedelta(minutes=30),
        )
    )
    db.commit()

    resp = client.post(
        "/api/auth/phone-verification/request", json={"phone": "+79167770400"}
    )
    assert resp.status_code == 200
    assert resp.json()["delivery"] == "sent"
    assert direct and direct[0][0] == 606


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
