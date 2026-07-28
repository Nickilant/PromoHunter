from app.models import Restaurant


def test_cities_and_catalog_scoped_by_city(client, db):
    from tests.test_status import make_fixtures

    restaurant, promotion, _ = make_fixtures(db)  # город по умолчанию — СПб
    other = Restaurant(
        brand_id=restaurant.brand_id,
        city="Москва",
        address="Тверская, 1",
        lat=55.76,
        lng=37.61,
    )
    db.add(other)
    db.commit()

    resp = client.get("/api/cities")
    assert resp.status_code == 200
    cities = {c["name"]: c["restaurants_count"] for c in resp.json()}
    assert cities == {"Санкт-Петербург": 1, "Москва": 1}

    # каталог: сеть видна в обоих городах, но с корректным числом точек
    for city in ("Санкт-Петербург", "Москва"):
        resp = client.get(f"/api/catalog?city={city}")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["restaurants_count"] == 1
        assert [p["title"] for p in data[0]["promotions"]] == [promotion.title]

    # в городе без точек — пусто
    assert client.get("/api/catalog?city=Казань").json() == []

    # поиск по товару сужает акции, по чужому названию — исключает сеть
    resp = client.get("/api/catalog?city=Москва&q=Товар А")
    assert len(resp.json()) == 1
    assert client.get("/api/catalog?city=Москва&q=шаурма").json() == []

    # рестораны фильтруются по городу
    resp = client.get("/api/restaurants?city=Москва")
    assert [r["address"] for r in resp.json()] == ["Тверская, 1"]

    # фид тоже
    resp = client.get("/api/feed?city=Москва")
    assert len(resp.json()) == 1
    assert resp.json()[0]["restaurant"]["city"] == "Москва"


def test_registration_stores_city(client):
    resp = client.post(
        "/api/auth/register",
        json={
            "phone": "+79167770001",
            "password": "secret123",
            "display_name": "Горожанин",
            "city": "Казань",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["user"]["city"] == "Казань"

    # без города — city пустой
    resp = client.post(
        "/api/auth/register",
        json={"phone": "+79167770002", "password": "secret123", "display_name": "Б"},
    )
    assert resp.json()["user"]["city"] is None
