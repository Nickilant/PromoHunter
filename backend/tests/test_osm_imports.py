from sqlalchemy import func, select

from app.models import Brand, City, ModeratorCity, Restaurant, User, UserRole
from app.services.osm import MISSING_ADDRESS, OsmPoint, _points_from_elements, _search_pattern
from app.services.scope import city_key


def register(client, phone: str):
    response = client.post(
        "/api/auth/register",
        json={"phone": phone, "password": "secret123", "display_name": "Сотрудник"},
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_osm_search_pattern_tolerates_brand_punctuation():
    pattern = _search_pattern("Вкусно и точка")
    assert pattern == "Вкусно.*и.*точка"
    assert _search_pattern("Rostic’s") == "Rostic.*s"


def test_osm_point_uses_nearby_building_address_as_title():
    points = _points_from_elements(
        [
            {
                "type": "node",
                "id": 10,
                "lat": 54.735,
                "lon": 55.958,
                "tags": {"name": "Вкусно — и точка", "amenity": "fast_food"},
            },
            {
                "type": "way",
                "id": 20,
                "center": {"lat": 54.7351, "lon": 55.9581},
                "tags": {"addr:street": "улица Ленина", "addr:housenumber": "7"},
            },
        ],
        "Вкусно и точка",
    )
    assert len(points) == 1
    assert points[0].address == "улица Ленина, 7"
    assert points[0].title == points[0].address


def test_osm_point_does_not_take_distant_address():
    points = _points_from_elements(
        [
            {"type": "node", "id": 10, "lat": 54.735, "lon": 55.958, "tags": {"brand": "Сеть"}},
            {
                "type": "node",
                "id": 20,
                "lat": 54.745,
                "lon": 55.968,
                "tags": {"addr:street": "Далёкая", "addr:housenumber": "1"},
            },
        ],
        "Сеть",
    )
    assert points[0].address == MISSING_ADDRESS
    assert points[0].title is None


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
            OsmPoint("node", 101, "улица Ленина, 1", "улица Ленина, 1", 54.7351, 55.9587),
            OsmPoint("node", 102, "проспект Октября, 20", "проспект Октября, 20", 54.75, 56.0),
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
    assert fresh["title"] == fresh["address"]

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
