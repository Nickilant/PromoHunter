import hashlib
import hmac
import json
from urllib.parse import urlencode

import pytest

from app.config import settings

TEST_TOKEN = "12345:TEST-TOKEN"


def sign(fields: dict) -> str:
    """Подписать поля так же, как это делает Telegram WebApp."""
    secret = hmac.new(b"WebAppData", TEST_TOKEN.encode(), hashlib.sha256).digest()
    check = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    fields = dict(fields)
    fields["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(fields)


@pytest.fixture(autouse=True)
def telegram_token():
    old = settings.telegram_bot_token
    settings.telegram_bot_token = TEST_TOKEN
    yield
    settings.telegram_bot_token = old


def make_init_data(tg_id=777, name="Тест"):
    return sign({"user": json.dumps({"id": tg_id, "first_name": name}), "auth_date": "1"})


def make_contact(tg_id=777, phone="+79161234567"):
    return sign(
        {
            "contact": json.dumps({"user_id": tg_id, "phone_number": phone}),
            "auth_date": "1",
        }
    )


def test_telegram_login_and_registration(client, db):
    init_data = make_init_data()

    # аккаунт ещё не привязан
    resp = client.post("/api/auth/telegram", json={"init_data": init_data})
    assert resp.status_code == 404

    # вход по контакту: создаёт пользователя с подтверждённым номером
    resp = client.post(
        "/api/auth/telegram/contact",
        json={
            "init_data": init_data,
            "contact_response": make_contact(),
            "city": "Казань",
        },
    )
    assert resp.status_code == 200
    user = resp.json()["user"]
    assert user["phone"] == "+79161234567"
    assert user["is_phone_verified"] is True
    assert user["has_telegram"] is True
    assert user["city"] == "Казань"
    assert user["role"] == "admin"  # первый пользователь

    # теперь обычный телеграм-вход работает
    resp = client.post("/api/auth/telegram", json={"init_data": init_data})
    assert resp.status_code == 200
    assert resp.json()["user"]["phone"] == "+79161234567"


def test_telegram_bad_signature_rejected(client):
    tampered = make_init_data() + "x"
    assert client.post("/api/auth/telegram", json={"init_data": tampered}).status_code == 401

    # контакт другого пользователя не принимается
    resp = client.post(
        "/api/auth/telegram/contact",
        json={"init_data": make_init_data(tg_id=1), "contact_response": make_contact(tg_id=2)},
    )
    assert resp.status_code == 401


def test_telegram_links_existing_phone_account(client):
    # обычная регистрация по номеру
    client.post(
        "/api/auth/register",
        json={"phone": "+79167654321", "password": "secret123", "display_name": "Пётр"},
    )
    # вход через телеграм с тем же номером привязывает аккаунт
    resp = client.post(
        "/api/auth/telegram/contact",
        json={
            "init_data": make_init_data(tg_id=555),
            "contact_response": make_contact(tg_id=555, phone="8 916 765-43-21"),
        },
    )
    assert resp.status_code == 200
    assert resp.json()["user"]["display_name"] == "Пётр"
    assert resp.json()["user"]["has_telegram"] is True
