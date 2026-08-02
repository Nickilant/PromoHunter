"""Смена пароля из профиля."""

import hashlib
import hmac
import json
from urllib.parse import urlencode

import pytest

from app.config import settings

TEST_TOKEN = "12345:TEST-TOKEN"


def register(client, phone="+79165551000", password="secret123"):
    resp = client.post(
        "/api/auth/register",
        json={"phone": phone, "password": password, "display_name": "П"},
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]


def headers(token):
    return {"Authorization": f"Bearer {token}"}


def change(client, token, new_password, current_password=None):
    body = {"new_password": new_password}
    if current_password is not None:
        body["current_password"] = current_password
    return client.post("/api/auth/password", json=body, headers=headers(token))


def test_password_change_flow(client):
    token = register(client)
    assert client.get("/api/auth/me", headers=headers(token)).json()["has_password"] is True

    resp = change(client, token, "newsecret1", "secret123")
    assert resp.status_code == 200
    fresh = resp.json()["access_token"]

    # старым паролем больше не пускает, новым — пускает
    assert client.post(
        "/api/auth/login", json={"phone": "+79165551000", "password": "secret123"}
    ).status_code == 401
    assert client.post(
        "/api/auth/login", json={"phone": "+79165551000", "password": "newsecret1"}
    ).status_code == 200

    # токен, выданный при смене, продолжает работать
    assert client.get("/api/auth/me", headers=headers(fresh)).status_code == 200


def test_wrong_current_password_rejected(client):
    token = register(client, "+79165551001")
    resp = change(client, token, "newsecret1", "not-my-password")
    assert resp.status_code == 400
    assert "неверный" in resp.json()["detail"].lower()
    # пароль остался прежним
    assert client.post(
        "/api/auth/login", json={"phone": "+79165551001", "password": "secret123"}
    ).status_code == 200


def test_current_password_is_required(client):
    token = register(client, "+79165551002")
    resp = change(client, token, "newsecret1")
    assert resp.status_code == 400
    assert "текущий" in resp.json()["detail"].lower()


def test_same_password_rejected(client):
    token = register(client, "+79165551003")
    resp = change(client, token, "secret123", "secret123")
    assert resp.status_code == 400
    assert "совпадает" in resp.json()["detail"].lower()


def test_short_password_rejected(client):
    token = register(client, "+79165551004")
    assert change(client, token, "12345", "secret123").status_code == 422


def test_anonymous_cannot_change(client):
    assert client.post("/api/auth/password", json={"new_password": "newsecret1"}).status_code == 401


def test_old_tokens_die_after_change(client):
    """Смена пароля обязана выкинуть того, кто знал старый."""
    old = register(client, "+79165551005")
    assert client.get("/api/auth/me", headers=headers(old)).status_code == 200

    change(client, old, "newsecret1", "secret123")

    resp = client.get("/api/auth/me", headers=headers(old))
    assert resp.status_code == 401
    assert "войдите заново" in resp.json()["detail"].lower()


def test_legacy_token_without_fingerprint(client, db):
    """Токены, выданные до появления отпечатка, не должны разлогинить всех
    на выкатке — но первая же смена пароля их обесценивает."""
    from datetime import datetime, timedelta, timezone

    from jose import jwt
    from sqlalchemy import select

    from app.auth import ALGORITHM
    from app.models import User

    token = register(client, "+79165551007")
    user = db.scalar(select(User).where(User.phone == "+79165551007"))
    legacy = jwt.encode(
        {
            "sub": str(user.id),
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        },
        settings.jwt_secret,
        algorithm=ALGORITHM,
    )
    assert client.get("/api/auth/me", headers=headers(legacy)).status_code == 200

    change(client, token, "newsecret1", "secret123")
    assert client.get("/api/auth/me", headers=headers(legacy)).status_code == 401


def test_old_token_is_anonymous_for_optional_auth(client):
    """Эндпоинты с необязательной авторизацией по старому токену видят гостя,
    а не владельца аккаунта."""
    old = register(client, "+79165551006")
    assert client.get("/api/rating?city=Тест", headers=headers(old)).json()["me"] is not None

    fresh = change(client, old, "newsecret1", "secret123").json()["access_token"]

    assert client.get("/api/rating?city=Тест", headers=headers(old)).json()["me"] is None
    assert client.get("/api/rating?city=Тест", headers=headers(fresh)).json()["me"] is not None


# --- аккаунт, заведённый через Telegram: пароля не было ---


@pytest.fixture()
def telegram_token():
    old = settings.telegram_bot_token
    settings.telegram_bot_token = TEST_TOKEN
    yield
    settings.telegram_bot_token = old


def _sign(fields: dict) -> str:
    secret = hmac.new(b"WebAppData", TEST_TOKEN.encode(), hashlib.sha256).digest()
    check = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    fields = dict(fields)
    fields["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(fields)


def telegram_login(client, tg_id=4242, phone="+79165552000"):
    init_data = _sign(
        {"user": json.dumps({"id": tg_id, "first_name": "Тг"}), "auth_date": "1"}
    )
    resp = client.post(
        "/api/auth/telegram/contact",
        json={
            "init_data": init_data,
            "contact_response": _sign(
                {
                    "contact": json.dumps({"user_id": tg_id, "phone_number": phone}),
                    "auth_date": "1",
                }
            ),
        },
    )
    assert resp.status_code == 200
    return resp.json()


def test_telegram_account_has_no_password(client, telegram_token):
    data = telegram_login(client)
    assert data["user"]["has_password"] is False
    # войти паролем нельзя — его не существует
    resp = client.post(
        "/api/auth/login", json={"phone": "+79165552000", "password": "whatever"}
    )
    assert resp.status_code == 401
    assert "не задан" in resp.json()["detail"]


def test_telegram_account_sets_password_without_current(client, telegram_token):
    data = telegram_login(client, tg_id=4243, phone="+79165552001")
    resp = change(client, data["access_token"], "newsecret1")
    assert resp.status_code == 200
    assert resp.json()["user"]["has_password"] is True

    # теперь вход паролем работает
    assert client.post(
        "/api/auth/login", json={"phone": "+79165552001", "password": "newsecret1"}
    ).status_code == 200


def test_second_change_requires_current(client, telegram_token):
    """Задав пароль однажды, дальше меняем его только со старым на руках."""
    data = telegram_login(client, tg_id=4244, phone="+79165552002")
    fresh = change(client, data["access_token"], "newsecret1").json()["access_token"]

    assert change(client, fresh, "othersecret1").status_code == 400
    assert change(client, fresh, "othersecret1", "newsecret1").status_code == 200
