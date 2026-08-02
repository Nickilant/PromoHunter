"""Городские модераторы и охват акций по городам."""

from app.auth import hash_password
from app.models import (
    Brand,
    ModeratorCity,
    Promotion,
    PromotionCity,
    PromotionCityMode,
    PromotionItem,
    PromotionSuggestion,
    Restaurant,
    RestaurantSuggestion,
    User,
    UserRole,
)

SPB = "Санкт-Петербург"
MSK = "Москва"


def make_staff(client, db, role, cities=(), phone="+79001110001"):
    user = User(
        phone=phone,
        password_hash=hash_password("secret123"),
        display_name=f"{role.value}",
        city=cities[0] if cities else None,
        role=role,
    )
    db.add(user)
    db.flush()
    for city in cities:
        db.add(ModeratorCity(user_id=user.id, city=city))
    db.commit()
    resp = client.post(
        "/api/auth/login", json={"phone": phone, "password": "secret123"}
    )
    assert resp.status_code == 200, resp.text
    return user, {"Authorization": f"Bearer {resp.json()['access_token']}"}


def make_world(db):
    brand = Brand(name="Сеть", slug="set")
    db.add(brand)
    db.flush()
    spb = Restaurant(brand_id=brand.id, city=SPB, address="Невский, 1", lat=59.9, lng=30.3)
    msk = Restaurant(brand_id=brand.id, city=MSK, address="Тверская, 1", lat=55.7, lng=37.6)
    db.add_all([spb, msk])
    db.commit()
    return brand, spb, msk


def make_promo(db, brand, mode=PromotionCityMode.exclude, cities=()):
    promo = Promotion(
        brand_id=brand.id,
        title="Акция",
        city_mode=mode,
        items=[PromotionItem(name="Товар", sort_order=0)],
    )
    db.add(promo)
    db.flush()
    for city in cities:
        db.add(PromotionCity(promotion_id=promo.id, city=city))
    db.commit()
    return promo


# --- охват акции по городам -----------------------------------------------


def test_federal_promo_is_visible_everywhere(client, db):
    brand, spb, msk = make_world(db)
    make_promo(db, brand)
    for restaurant in (spb, msk):
        data = client.get(f"/api/restaurants/{restaurant.id}").json()
        assert len(data["promotions"]) == 1


def test_federal_promo_minus_one_city(client, db):
    """Ради этого всё и затевалось: акция по стране, но не в одном городе."""
    brand, spb, msk = make_world(db)
    make_promo(db, brand, PromotionCityMode.exclude, [MSK])

    assert len(client.get(f"/api/restaurants/{spb.id}").json()["promotions"]) == 1
    assert client.get(f"/api/restaurants/{msk.id}").json()["promotions"] == []

    # каталог города тоже её не показывает
    assert client.get(f"/api/catalog?city={MSK}").json() == []
    assert len(client.get(f"/api/catalog?city={SPB}").json()) == 1


def test_promo_only_in_listed_cities(client, db):
    brand, spb, msk = make_world(db)
    make_promo(db, brand, PromotionCityMode.include, [MSK])

    assert client.get(f"/api/restaurants/{spb.id}").json()["promotions"] == []
    assert len(client.get(f"/api/restaurants/{msk.id}").json()["promotions"]) == 1


def test_city_case_and_spaces_do_not_split_scope(client, db):
    """«москва» и «Москва » — один и тот же город, иначе охват дырявый."""
    brand, spb, msk = make_world(db)
    make_promo(db, brand, PromotionCityMode.exclude, ["  москва "])
    assert client.get(f"/api/restaurants/{msk.id}").json()["promotions"] == []
    assert len(client.get(f"/api/restaurants/{spb.id}").json()["promotions"]) == 1


def test_feed_respects_scope_across_cities(client, db):
    brand, spb, msk = make_world(db)
    make_promo(db, brand, PromotionCityMode.exclude, [MSK])
    entries = client.get("/api/feed").json()
    addresses = {e["restaurant"]["address"] for e in entries}
    assert "Невский, 1" in addresses
    assert "Тверская, 1" not in addresses


def test_report_rejected_where_promo_does_not_run(client, db):
    brand, spb, msk = make_world(db)
    promo = make_promo(db, brand, PromotionCityMode.exclude, [MSK])
    resp = client.post(
        "/api/auth/register",
        json={"phone": "+79002220001", "password": "secret123", "display_name": "Ч"},
    )
    headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}
    body = {
        "restaurant_id": msk.id,
        "promotion_id": promo.id,
        "items": [{"promotion_item_id": promo.items[0].id, "is_available": True}],
    }
    resp = client.post("/api/reports", json=body, headers=headers)
    assert resp.status_code == 400
    assert "не проводится в городе" in resp.json()["detail"]


# --- права модератора ------------------------------------------------------


def test_moderator_sees_only_own_city_suggestions(client, db):
    brand, spb, msk = make_world(db)
    author = User(phone="+79003330001", password_hash="x", display_name="А", city=SPB)
    db.add(author)
    db.flush()
    db.add_all(
        [
            RestaurantSuggestion(
                user_id=author.id, brand_id=brand.id, city=SPB,
                address="Питерская, 2", lat=59.9, lng=30.3,
            ),
            RestaurantSuggestion(
                user_id=author.id, brand_id=brand.id, city=MSK,
                address="Московская, 3", lat=55.7, lng=37.6,
            ),
        ]
    )
    db.commit()

    _, headers = make_staff(client, db, UserRole.moderator, [SPB])
    groups = client.get("/api/admin/restaurant-suggestions", headers=headers).json()
    addresses = [s["address"] for g in groups for s in g["suggestions"]]
    assert addresses == ["Питерская, 2"]

    _, admin_headers = make_staff(
        client, db, UserRole.admin, phone="+79004440001"
    )
    groups = client.get("/api/admin/restaurant-suggestions", headers=admin_headers).json()
    addresses = {s["address"] for g in groups for s in g["suggestions"]}
    assert addresses == {"Питерская, 2", "Московская, 3"}


def test_moderator_cannot_approve_into_another_city(client, db):
    """Дыра, которую закрыли: город приходит из тела запроса."""
    brand, spb, msk = make_world(db)
    author = User(phone="+79003330002", password_hash="x", display_name="А", city=SPB)
    db.add(author)
    db.flush()
    suggestion = RestaurantSuggestion(
        user_id=author.id, brand_id=brand.id, city=SPB,
        address="Питерская, 5", lat=59.9, lng=30.3,
    )
    db.add(suggestion)
    db.commit()

    _, headers = make_staff(client, db, UserRole.moderator, [SPB])
    resp = client.post(
        f"/api/admin/restaurant-suggestions/{suggestion.id}/approve",
        json={
            "brand_id": brand.id,
            "city": MSK,  # подменяем город
            "address": "Питерская, 5",
            "lat": 59.9,
            "lng": 30.3,
        },
        headers=headers,
    )
    assert resp.status_code == 403
    assert "вне ваших городов" in resp.json()["detail"]

    # свой город — можно
    resp = client.post(
        f"/api/admin/restaurant-suggestions/{suggestion.id}/approve",
        json={
            "brand_id": brand.id,
            "city": SPB,
            "address": "Питерская, 5",
            "lat": 59.9,
            "lng": 30.3,
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    db.refresh(suggestion)
    assert suggestion.reviewed_by_id is not None


def test_moderator_cannot_touch_foreign_restaurant(client, db):
    brand, spb, msk = make_world(db)
    _, headers = make_staff(client, db, UserRole.moderator, [SPB])

    listed = client.get("/api/admin/restaurants", headers=headers).json()
    assert [r["address"] for r in listed] == ["Невский, 1"]

    assert (
        client.patch(
            f"/api/admin/restaurants/{msk.id}", json={"title": "Моё"}, headers=headers
        ).status_code
        == 403
    )
    assert (
        client.delete(f"/api/admin/restaurants/{msk.id}", headers=headers).status_code
        == 403
    )
    # свою — можно
    assert (
        client.patch(
            f"/api/admin/restaurants/{spb.id}", json={"title": "Моё"}, headers=headers
        ).status_code
        == 200
    )


def test_moderator_cannot_move_restaurant_out_of_scope(client, db):
    brand, spb, msk = make_world(db)
    _, headers = make_staff(client, db, UserRole.moderator, [SPB])
    resp = client.patch(
        f"/api/admin/restaurants/{spb.id}", json={"city": MSK}, headers=headers
    )
    assert resp.status_code == 403
    db.refresh(spb)
    assert spb.city == SPB


def test_moderator_has_no_access_to_brands_and_users(client, db):
    make_world(db)
    _, headers = make_staff(client, db, UserRole.moderator, [SPB])
    assert client.get("/api/admin/users", headers=headers).status_code == 403
    assert (
        client.post(
            "/api/admin/brands", json={"name": "Новый"}, headers=headers
        ).status_code
        == 403
    )
    # читать бренды можно — без них не завести точку
    assert client.get("/api/admin/brands", headers=headers).status_code == 200


def test_plain_user_is_not_let_into_admin(client, db):
    # Первый зарегистрированный становится админом — берём второго
    db.add(User(phone="+79005550001", password_hash="x", display_name="Первый"))
    db.commit()
    resp = client.post(
        "/api/auth/register",
        json={"phone": "+79005550002", "password": "secret123", "display_name": "Ч"},
    )
    assert resp.json()["user"]["role"] == "user"
    headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}
    assert client.get("/api/admin/restaurants", headers=headers).status_code == 403


def test_moderator_without_cities_sees_nothing(client, db):
    brand, spb, msk = make_world(db)
    _, headers = make_staff(client, db, UserRole.moderator, [])
    assert client.get("/api/admin/restaurants", headers=headers).json() == []


# --- модератор и охват акции -----------------------------------------------


def test_moderator_removes_federal_promo_from_own_city_only(client, db):
    """Главный сценарий: «у нас этой акции нет» — не трогая остальную страну."""
    brand, spb, msk = make_world(db)
    promo = make_promo(db, brand)
    _, headers = make_staff(client, db, UserRole.moderator, [SPB])

    resp = client.post(
        f"/api/admin/promotions/{promo.id}/cities",
        json={"city": SPB, "listed": True},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["scope_cities"] == [SPB]

    # в своём городе акции больше нет, в чужом — по-прежнему есть
    assert client.get(f"/api/restaurants/{spb.id}").json()["promotions"] == []
    assert len(client.get(f"/api/restaurants/{msk.id}").json()["promotions"]) == 1

    # и вернуть обратно тоже может
    client.post(
        f"/api/admin/promotions/{promo.id}/cities",
        json={"city": SPB, "listed": False},
        headers=headers,
    )
    assert len(client.get(f"/api/restaurants/{spb.id}").json()["promotions"]) == 1


def test_moderator_cannot_touch_other_city_in_scope(client, db):
    brand, spb, msk = make_world(db)
    promo = make_promo(db, brand)
    _, headers = make_staff(client, db, UserRole.moderator, [SPB])
    resp = client.post(
        f"/api/admin/promotions/{promo.id}/cities",
        json={"city": MSK, "listed": True},
        headers=headers,
    )
    assert resp.status_code == 403


def test_moderator_cannot_edit_federal_promo(client, db):
    brand, spb, msk = make_world(db)
    promo = make_promo(db, brand)
    _, headers = make_staff(client, db, UserRole.moderator, [SPB])

    resp = client.patch(
        f"/api/admin/promotions/{promo.id}", json={"title": "Своё"}, headers=headers
    )
    assert resp.status_code == 403
    assert "глобальный администратор" in resp.json()["detail"]
    assert client.delete(
        f"/api/admin/promotions/{promo.id}", headers=headers
    ).status_code == 403


def test_moderator_edits_promo_that_is_only_his(client, db):
    brand, spb, msk = make_world(db)
    promo = make_promo(db, brand, PromotionCityMode.include, [SPB])
    _, headers = make_staff(client, db, UserRole.moderator, [SPB])
    resp = client.patch(
        f"/api/admin/promotions/{promo.id}", json={"title": "Питерская акция"}, headers=headers
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["can_edit"] is True


def test_moderator_creates_only_local_promo(client, db):
    brand, spb, msk = make_world(db)
    _, headers = make_staff(client, db, UserRole.moderator, [SPB])

    resp = client.post(
        "/api/admin/promotions",
        json={
            "brand_id": brand.id,
            "title": "Только у нас",
            "items": [{"name": "Товар"}],
            "scope": {"mode": "exclude", "cities": []},  # просит федеральную
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    # охват сузили до его города, режим переключили на «только в списке»
    assert body["city_mode"] == "include"
    assert body["scope_cities"] == [SPB]
    assert client.get(f"/api/restaurants/{msk.id}").json()["promotions"] == []
    assert len(client.get(f"/api/restaurants/{spb.id}").json()["promotions"]) == 1


def test_global_admin_sets_any_scope(client, db):
    brand, spb, msk = make_world(db)
    _, headers = make_staff(client, db, UserRole.admin, phone="+79006660001")
    resp = client.post(
        "/api/admin/promotions",
        json={
            "brand_id": brand.id,
            "title": "Везде кроме Москвы",
            "items": [{"name": "Товар"}],
            "scope": {"mode": "exclude", "cities": [MSK]},
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["scope_label"] == f"везде, кроме: {MSK}"
    assert client.get(f"/api/restaurants/{msk.id}").json()["promotions"] == []


def test_scope_endpoint_tells_who_i_am(client, db):
    make_world(db)
    _, mod_headers = make_staff(client, db, UserRole.moderator, [SPB])
    data = client.get("/api/admin/scope", headers=mod_headers).json()
    assert data["is_global"] is False
    assert data["cities"] == [SPB]
    assert data["role"] == "moderator"

    _, admin_headers = make_staff(client, db, UserRole.admin, phone="+79007770001")
    data = client.get("/api/admin/scope", headers=admin_headers).json()
    assert data["is_global"] is True


def test_admin_assigns_cities_to_moderator(client, db):
    make_world(db)
    _, headers = make_staff(client, db, UserRole.admin, phone="+79008880001")
    victim = User(phone="+79008880002", password_hash="x", display_name="Кандидат")
    db.add(victim)
    db.commit()

    resp = client.patch(
        f"/api/admin/users/{victim.id}",
        json={"role": "moderator", "moderator_cities": [" санкт-Петербург ", SPB]},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    # дубль по регистру и пробелам не создал вторую строку
    assert len(resp.json()["moderator_cities"]) == 1

    # разжаловали — города сняты
    resp = client.patch(
        f"/api/admin/users/{victim.id}", json={"role": "user"}, headers=headers
    )
    assert resp.json()["moderator_cities"] == []
