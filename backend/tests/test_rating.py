from datetime import datetime, timezone

from app.auth import hash_password
from app.models import Faction, RatingEvent, User, UserRole
from tests.test_status import make_fixtures

CITY = "Рейтингбург"


def add_player(db, name, points, *, faction=None, role=UserRole.user, blocked=False):
    user = User(
        phone=f"+7900{abs(hash(name)) % 10_000_000:07d}",
        password_hash=hash_password("x"),
        display_name=name,
        city=CITY,
        faction=faction,
        role=role,
        is_blocked=blocked,
    )
    db.add(user)
    db.flush()
    db.add(
        RatingEvent(
            user_id=user.id,
            city=CITY,
            type="report_base",
            points=points,
            created_at=datetime.now(timezone.utc),
        )
    )
    db.commit()
    return user


def token_for(client, user, db):
    user.password_hash = hash_password("secret123")
    db.commit()
    resp = client.post(
        "/api/auth/login", json={"phone": user.phone, "password": "secret123"}
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_admins_are_excluded_from_leaderboard(client, db):
    """У админа доступ к модерации — соревноваться с ним нечестно."""
    add_player(db, "Обычный", 50)
    add_player(db, "Модератор", 999, role=UserRole.admin)

    resp = client.get(f"/api/rating?city={CITY}")
    assert resp.status_code == 200
    names = [e["display_name"] for e in resp.json()["entries"]]
    assert names == ["Обычный"]
    assert resp.json()["total"] == 1


def test_blocked_and_nonpositive_are_excluded(client, db):
    add_player(db, "Живой", 10)
    add_player(db, "Забаненный", 100, blocked=True)
    add_player(db, "Минусовой", -5)

    data = client.get(f"/api/rating?city={CITY}").json()
    assert [e["display_name"] for e in data["entries"]] == ["Живой"]


def test_positions_are_dense_after_filtering(client, db):
    """Места нумеруются по итоговому списку, без дырок от отфильтрованных."""
    add_player(db, "Первый", 100)
    add_player(db, "Админ", 90, role=UserRole.admin)
    add_player(db, "Второй", 80)
    add_player(db, "Третий", 70)

    data = client.get(f"/api/rating?city={CITY}").json()
    assert [(e["display_name"], e["position"]) for e in data["entries"]] == [
        ("Первый", 1),
        ("Второй", 2),
        ("Третий", 3),
    ]


def test_pagination_and_total(client, db):
    for i in range(25):
        add_player(db, f"И{i:02d}", 1000 - i)

    first = client.get(f"/api/rating?city={CITY}&limit=10").json()
    assert len(first["entries"]) == 10
    assert first["total"] == 25
    assert first["entries"][0]["position"] == 1

    second = client.get(f"/api/rating?city={CITY}&limit=10&offset=10").json()
    assert [e["position"] for e in second["entries"]] == list(range(11, 21))
    # страницы не пересекаются
    assert not {e["user_id"] for e in first["entries"]} & {
        e["user_id"] for e in second["entries"]
    }

    tail = client.get(f"/api/rating?city={CITY}&limit=10&offset=20").json()
    assert len(tail["entries"]) == 5


def test_my_row_comes_even_when_far_below_the_page(client, db):
    """Человек на 21-м месте видит своё место, хотя в первую десятку не попал."""
    for i in range(20):
        add_player(db, f"Топ{i:02d}", 500 - i)
    me = add_player(db, "Я", 1)
    headers = token_for(client, me, db)

    data = client.get(f"/api/rating?city={CITY}&limit=10", headers=headers).json()
    assert len(data["entries"]) == 10
    assert all(e["user_id"] != me.id for e in data["entries"])
    assert data["me"]["position"] == 21
    assert data["me"]["display_name"] == "Я"
    assert data["me"]["points"] == 1


def test_my_row_without_points_has_no_position(client, db):
    add_player(db, "Кто-то", 10)
    me = User(
        phone="+79001112233",
        password_hash=hash_password("secret123"),
        display_name="Новичок",
        city=CITY,
    )
    db.add(me)
    db.commit()
    headers = token_for(client, me, db)

    data = client.get(f"/api/rating?city={CITY}", headers=headers).json()
    assert data["me"]["position"] is None
    assert data["me"]["points"] == 0
    assert data["me"]["display_name"] == "Новичок"


def test_faction_scope_keeps_only_my_side(client, db):
    add_player(db, "Зелёный чужой", 300, faction=Faction.green)
    add_player(db, "Фиолетовый", 200, faction=Faction.purple)
    add_player(db, "Без стороны", 150)
    me = add_player(db, "Зелёный я", 100, faction=Faction.green)
    headers = token_for(client, me, db)

    every = client.get(f"/api/rating?city={CITY}", headers=headers).json()
    assert every["total"] == 4

    mine = client.get(f"/api/rating?city={CITY}&scope=faction", headers=headers).json()
    assert mine["total"] == 2
    assert [e["display_name"] for e in mine["entries"]] == ["Зелёный чужой", "Зелёный я"]
    # место считается внутри фракции, а не в общем зачёте
    assert mine["me"]["position"] == 2


def test_faction_scope_needs_a_side(client, db):
    me = add_player(db, "Безстороннний", 10)
    headers = token_for(client, me, db)
    resp = client.get(f"/api/rating?city={CITY}&scope=faction", headers=headers)
    assert resp.status_code == 400
    assert "сторона" in resp.json()["detail"]

    # и без входа тоже
    assert client.get(f"/api/rating?city={CITY}&scope=faction").status_code == 400


def test_leaderboard_is_scoped_to_city(client, db):
    add_player(db, "Местный", 10)
    other = User(
        phone="+79005550001",
        password_hash=hash_password("x"),
        display_name="Иногородний",
        city="Другой",
    )
    db.add(other)
    db.flush()
    db.add(
        RatingEvent(user_id=other.id, city="Другой", type="report_base", points=999)
    )
    db.commit()

    data = client.get(f"/api/rating?city={CITY}").json()
    assert [e["display_name"] for e in data["entries"]] == ["Местный"]
