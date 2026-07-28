def test_first_user_becomes_admin(client):
    resp = client.post(
        "/api/auth/register",
        json={"email": "first@example.com", "password": "secret123", "display_name": "Первый"},
    )
    assert resp.status_code == 200
    assert resp.json()["user"]["role"] == "admin"

    resp = client.post(
        "/api/auth/register",
        json={"email": "second@example.com", "password": "secret123", "display_name": "Второй"},
    )
    assert resp.status_code == 200
    assert resp.json()["user"]["role"] == "user"


def test_duplicate_email_rejected(client):
    payload = {"email": "dup@example.com", "password": "secret123", "display_name": "Дуб"}
    assert client.post("/api/auth/register", json=payload).status_code == 200
    assert client.post("/api/auth/register", json=payload).status_code == 409


def test_login_and_me(client):
    client.post(
        "/api/auth/register",
        json={"email": "user@example.com", "password": "secret123", "display_name": "Юзер"},
    )
    resp = client.post(
        "/api/auth/login", json={"email": "user@example.com", "password": "secret123"}
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]

    resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "user@example.com"

    resp = client.post(
        "/api/auth/login", json={"email": "user@example.com", "password": "wrong"}
    )
    assert resp.status_code == 401

    assert client.get("/api/auth/me").status_code == 401
