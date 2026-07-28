def test_first_user_becomes_admin(client):
    resp = client.post(
        "/api/auth/register",
        json={"phone": "+79161234567", "password": "secret123", "display_name": "Первый"},
    )
    assert resp.status_code == 200
    assert resp.json()["user"]["role"] == "admin"

    resp = client.post(
        "/api/auth/register",
        json={"phone": "+79161234568", "password": "secret123", "display_name": "Второй"},
    )
    assert resp.status_code == 200
    assert resp.json()["user"]["role"] == "user"


def test_duplicate_phone_rejected(client):
    payload = {"phone": "+79160000001", "password": "secret123", "display_name": "Дуб"}
    assert client.post("/api/auth/register", json=payload).status_code == 200
    # тот же номер в другом написании — тоже дубль
    payload["phone"] = "8 916 000-00-01"
    assert client.post("/api/auth/register", json=payload).status_code == 409


def test_phone_normalization_and_login(client):
    resp = client.post(
        "/api/auth/register",
        json={"phone": "8 (916) 111-22-33", "password": "secret123", "display_name": "Юзер"},
    )
    assert resp.status_code == 200
    assert resp.json()["user"]["phone"] == "+79161112233"
    assert resp.json()["user"]["is_phone_verified"] is True

    # вход в любом привычном написании номера
    resp = client.post(
        "/api/auth/login", json={"phone": "+7 916 111 22 33", "password": "secret123"}
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]

    resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["phone"] == "+79161112233"

    resp = client.post(
        "/api/auth/login", json={"phone": "+79161112233", "password": "wrong"}
    )
    assert resp.status_code == 401

    assert client.get("/api/auth/me").status_code == 401


def test_invalid_phone_rejected(client):
    resp = client.post(
        "/api/auth/register",
        json={"phone": "не телефон", "password": "secret123", "display_name": "Х"},
    )
    assert resp.status_code == 422
