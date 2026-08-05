from sqlalchemy import func, select

from app.models import Brand, City, ModeratorCity, Restaurant, User, UserRole
from app.services.osm import OsmPoint
from app.services.scope import city_key


def register(client, phone: str):
    response = client.post(
        "/api/auth/register",
        json={"phone": phone, "password": "secret123", "display_name": "Сотрудник"},
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_osm_staging_marks_duplicates_and_commits_selected(client, db, monkeypatch):
    headers = register(client, "+79168880001")
    brand = Brand(name="Тестовая сеть", slug="test-chain")
    city = City(name="Уфа", key=city_key("Уфа"))
    existing = Restaurant(
        brand=brand, city="Уфа", address="улица Ленина, 1", lat=54.7351, lng=55.9587
    )
    db.add_all([brand, city, existing])
    db.commit()

    monkeypatch.setattr(
        "app.routers.osm_imports.find_restaurants",
        lambda _city, _query: [
            OsmPoint("node", 101, "Тестовая сеть", "улица Ленина, 1", 54.7351, 55.9587),
            OsmPoint("node", 102, "Тестовая сеть", "проспект Октября, 20", 54.75, 56.0),
        ],
    )
    response = client.post(
        "/api/admin/osm-imports",
        headers=headers,
        json={"brand_id": brand.id, "city": "Уфа"},
    )
    assert response.status_code == 201, response.text
    batch = response.json()
    duplicate, fresh = batch["points"]
    assert duplicate["duplicate_restaurant_id"] == existing.id
    assert fresh["duplicate_restaurant_id"] is None

    committed = client.post(
        f"/api/admin/osm-imports/{batch['id']}/commit",
        headers=headers,
        json={"point_ids": [duplicate["id"], fresh["id"]]},
    )
    assert committed.status_code == 200
    assert committed.json() == {"imported": 1, "skipped": 1}
    assert db.scalar(select(func.count(Restaurant.id))) == 2


def test_city_moderator_cannot_import_another_city(client, db, monkeypatch):
    register(client, "+79168880002")  # первый аккаунт — администратор
    moderator_headers = register(client, "+79168880003")
    moderator = db.scalar(select(User).where(User.phone == "+79168880003"))
    moderator.role = UserRole.moderator
    brand = Brand(name="Сеть", slug="chain")
    db.add_all([
        brand,
        City(name="Уфа", key=city_key("Уфа")),
        City(name="Москва", key=city_key("Москва")),
        ModeratorCity(user_id=moderator.id, city="Уфа"),
    ])
    db.commit()
    monkeypatch.setattr("app.routers.osm_imports.find_restaurants", lambda *_: [])

    response = client.post(
        "/api/admin/osm-imports",
        headers=moderator_headers,
        json={"brand_id": brand.id, "city": "Москва"},
    )
    assert response.status_code == 403
