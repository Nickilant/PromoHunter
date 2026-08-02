"""Справочник городов: админка, массовое добавление, публичный список."""

from app.models import City, Restaurant, User, UserRole
from tests.test_status import make_fixtures


def admin_headers(client, db, phone="+79167000001"):
    resp = client.post(
        "/api/auth/register",
        json={"phone": phone, "password": "secret123", "display_name": "А"},
    )
    token = resp.json()["access_token"]
    from sqlalchemy import select

    user = db.scalar(select(User).where(User.phone == phone))
    user.role = UserRole.admin
    db.commit()
    return {"Authorization": f"Bearer {token}"}


def test_city_crud(client, db):
    headers = admin_headers(client, db)

    resp = client.post("/api/admin/cities", json={"name": "  Казань "}, headers=headers)
    assert resp.status_code == 201
    assert resp.json()["name"] == "Казань"
    city_id = resp.json()["id"]

    # регистр и пробелы не заводят второй такой же город
    dup = client.post("/api/admin/cities", json={"name": "казань"}, headers=headers)
    assert dup.status_code == 409

    resp = client.patch(
        f"/api/admin/cities/{city_id}", json={"name": "Казань-2"}, headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Казань-2"

    assert client.delete(f"/api/admin/cities/{city_id}", headers=headers).status_code == 204
    assert client.get("/api/admin/cities", headers=headers).json() == []


def test_bulk_add_splits_and_skips_duplicates(client, db):
    headers = admin_headers(client, db, "+79167000002")
    client.post("/api/admin/cities", json={"name": "Пермь"}, headers=headers)

    resp = client.post(
        "/api/admin/cities/bulk",
        json={"names": "Уфа, Самара\nОмск; пермь\n\n  Тверь  ,Уфа"},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["added"] == ["Уфа", "Самара", "Омск", "Тверь"]
    # «пермь» уже есть, «Уфа» повторилась внутри самой пачки
    assert sorted(body["skipped"]) == ["Уфа", "пермь"]
    assert db.query(City).count() == 5


def test_city_with_restaurants_cannot_be_deleted(client, db):
    restaurant, _, _ = make_fixtures(db)
    restaurant.city = "Тула"
    db.add(City(name="Тула", key="тула"))
    db.commit()
    headers = admin_headers(client, db, "+79167000003")

    city_id = next(c["id"] for c in client.get("/api/admin/cities", headers=headers).json())
    resp = client.delete(f"/api/admin/cities/{city_id}", headers=headers)
    assert resp.status_code == 409
    assert "точки" in resp.json()["detail"]


def test_rename_carries_restaurants(client, db):
    restaurant, _, _ = make_fixtures(db)
    restaurant.city = "Тверь"
    db.add(City(name="Тверь", key="тверь"))
    db.commit()
    headers = admin_headers(client, db, "+79167000004")

    city_id = next(c["id"] for c in client.get("/api/admin/cities", headers=headers).json())
    resp = client.patch(
        f"/api/admin/cities/{city_id}", json={"name": "Тверь Новая"}, headers=headers
    )
    assert resp.status_code == 200
    db.expire_all()
    assert db.get(Restaurant, restaurant.id).city == "Тверь Новая"


def test_public_list_includes_cities_without_points(client, db):
    restaurant, _, _ = make_fixtures(db)
    restaurant.city = "Москва"
    db.add_all([City(name="Москва", key="москва"), City(name="Сочи", key="сочи")])
    db.commit()

    cities = client.get("/api/cities").json()
    names = [c["name"] for c in cities]
    assert names == ["Москва", "Сочи"]  # с точками — выше
    assert cities[0]["restaurants_count"] == 1
    assert cities[1]["restaurants_count"] == 0


def test_inactive_city_hidden_from_public_list(client, db):
    db.add(City(name="Сочи", key="сочи", is_active=False))
    db.commit()
    assert client.get("/api/cities").json() == []


def test_moderator_cannot_manage_cities(client, db):
    from sqlalchemy import select

    from app.models import ModeratorCity

    admin_headers(client, db, "+79167000005")  # первый — админ
    resp = client.post(
        "/api/auth/register",
        json={"phone": "+79167000006", "password": "secret123", "display_name": "М"},
    )
    token = resp.json()["access_token"]
    mod = db.scalar(select(User).where(User.phone == "+79167000006"))
    mod.role = UserRole.moderator
    db.add(ModeratorCity(user_id=mod.id, city="Казань"))
    db.commit()

    headers = {"Authorization": f"Bearer {token}"}
    assert client.post("/api/admin/cities", json={"name": "Уфа"}, headers=headers).status_code == 403
    assert client.post(
        "/api/admin/cities/bulk", json={"names": "Уфа"}, headers=headers
    ).status_code == 403


def test_moderator_sees_only_own_cities(client, db):
    from sqlalchemy import select

    from app.models import ModeratorCity

    headers = admin_headers(client, db, "+79167000007")
    client.post("/api/admin/cities/bulk", json={"names": "Казань,Уфа,Омск"}, headers=headers)

    resp = client.post(
        "/api/auth/register",
        json={"phone": "+79167000008", "password": "secret123", "display_name": "М"},
    )
    mod = db.scalar(select(User).where(User.phone == "+79167000008"))
    mod.role = UserRole.moderator
    db.add(ModeratorCity(user_id=mod.id, city="Казань"))
    db.commit()

    mine = client.get(
        "/api/admin/cities",
        headers={"Authorization": f"Bearer {resp.json()['access_token']}"},
    ).json()
    assert [c["name"] for c in mine] == ["Казань"]
