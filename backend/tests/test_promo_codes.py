"""Промокоды: свежесть, убывающее продление, жалобы, очки автору."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.config import settings
from app.models import PromoCode, PromoCodeVote, RatingEvent, User
from app.services.promo_code import (
    PromoCodeError,
    apply_vote,
    freshness_after,
    normalize_code,
)
from tests.test_status import make_fixtures


def auth(client, phone):
    resp = client.post(
        "/api/auth/register",
        json={"phone": phone, "password": "secret123", "display_name": f"U{phone[-3:]}"},
    )
    assert resp.status_code in (200, 201), resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def add_code(client, headers, brand_id, code="SALE20", **extra):
    body = {
        "brand_id": brand_id,
        "code": code,
        "description": "Скидка 20% на всё",
        "is_global": True,
        **extra,
    }
    return client.post("/api/promo-codes", json=body, headers=headers)


# --- нормализация и продление -------------------------------------------


def test_code_normalization():
    assert normalize_code(" sale20 ") == "SALE20"
    assert normalize_code("Ск-и_дка.5") == "СК-И_ДКА.5"
    for bad in ("", "a", "код с пробелом", "https://example.com/x", "код<script>"):
        with pytest.raises(PromoCodeError):
            normalize_code(bad)


def test_freshness_halves_and_hits_the_floor():
    """Первое подтверждение человека сбрасывает срок целиком, дальше вдвое
    меньше каждый раз — до пола в полсуток."""
    assert freshness_after(1) == timedelta(days=5)
    assert freshness_after(2) == timedelta(days=2.5)
    assert freshness_after(3) == timedelta(days=1.25)
    assert freshness_after(4) == timedelta(days=0.625)
    # дальше пол: 12 часов
    assert freshness_after(5) == timedelta(hours=12)
    assert freshness_after(50) == timedelta(hours=12)


# --- жизненный цикл через API --------------------------------------------


def test_add_and_list(client, db):
    restaurant, _, _ = make_fixtures(db)
    headers = auth(client, "+79167100001")

    resp = add_code(client, headers, restaurant.brand_id)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["code"] == "SALE20"
    assert data["is_global"] is True
    assert data["is_mine"] is True
    assert data["confirmations"] == 0

    listed = client.get(f"/api/promo-codes?brand_id={restaurant.brand_id}").json()
    assert [c["code"] for c in listed] == ["SALE20"]


def test_duplicate_code_rejected_case_insensitively(client, db):
    restaurant, _, _ = make_fixtures(db)
    headers = auth(client, "+79167100002")
    assert add_code(client, headers, restaurant.brand_id, "SALE20").status_code == 201
    resp = add_code(client, headers, restaurant.brand_id, "sale20")
    assert resp.status_code == 409


def test_regional_code_visible_only_in_its_city(client, db):
    restaurant, _, _ = make_fixtures(db)
    headers = auth(client, "+79167100003")
    resp = add_code(
        client,
        headers,
        restaurant.brand_id,
        "SPB10",
        is_global=False,
        city="Санкт-Петербург",
    )
    assert resp.status_code == 201
    assert resp.json()["cities"] == ["Санкт-Петербург"]

    base = f"/api/promo-codes?brand_id={restaurant.brand_id}"
    assert [c["code"] for c in client.get(f"{base}&city=Санкт-Петербург").json()] == ["SPB10"]
    assert client.get(f"{base}&city=Казань").json() == []
    # регистр города не должен прятать код
    assert len(client.get(f"{base}&city=санкт-петербург").json()) == 1


def test_regional_code_needs_a_city(client, db):
    restaurant, _, _ = make_fixtures(db)
    headers = auth(client, "+79167100004")
    resp = add_code(client, headers, restaurant.brand_id, "NOCITY", is_global=False)
    assert resp.status_code == 400
    assert "город" in resp.json()["detail"]


# --- подтверждения --------------------------------------------------------


def test_confirmation_extends_and_awards_author_once(client, db):
    restaurant, _, _ = make_fixtures(db)
    author = auth(client, "+79167100005")
    other = auth(client, "+79167100006")
    code_id = add_code(client, author, restaurant.brand_id).json()["id"]

    before = db.get(PromoCode, code_id).expires_at
    resp = client.post(
        f"/api/promo-codes/{code_id}/vote", json={"worked": True}, headers=other
    )
    assert resp.status_code == 200
    assert resp.json()["confirmations"] == 1

    db.expire_all()
    assert db.get(PromoCode, code_id).expires_at >= before

    events = db.scalars(
        select(RatingEvent).where(RatingEvent.type == "promo_code_used")
    ).all()
    assert len(events) == 1
    assert events[0].points == settings.promo_code_author_points

    # второе подтверждение очков автору уже не приносит
    third = auth(client, "+79167100007")
    client.post(f"/api/promo-codes/{code_id}/vote", json={"worked": True}, headers=third)
    assert (
        len(db.scalars(select(RatingEvent).where(RatingEvent.type == "promo_code_used")).all())
        == 1
    )


def test_author_cannot_award_himself(client, db):
    """Иначе достаточно добавить код и подтвердить его самому."""
    restaurant, _, _ = make_fixtures(db)
    author = auth(client, "+79167100008")
    code_id = add_code(client, author, restaurant.brand_id).json()["id"]

    resp = client.post(
        f"/api/promo-codes/{code_id}/vote", json={"worked": True}, headers=author
    )
    assert resp.status_code == 200
    assert db.scalars(
        select(RatingEvent).where(RatingEvent.type == "promo_code_used")
    ).all() == []
    # но свежесть его подтверждение продлевает, как у всех
    assert db.get(PromoCode, code_id).expires_at > datetime.now(timezone.utc)


def test_repeat_confirmations_extend_less_each_time(db):
    """Держать код в одиночку можно, но с каждым разом дешевле."""
    restaurant, _, users = make_fixtures(db)
    now = datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc)
    code = PromoCode(
        brand_id=restaurant.brand_id,
        code="X1",
        code_key="x1",
        description="d",
        author_id=users[0].id,
        expires_at=now,
    )
    db.add(code)
    db.commit()

    user_id = users[1].id
    spans = []
    for _ in range(6):
        apply_vote(db, code, user_id, True, now)
        db.add(PromoCodeVote(promo_code_id=code.id, user_id=user_id, worked=True))
        db.commit()
        spans.append(code.expires_at - now)
        code.expires_at = now  # обнуляем, чтобы видеть вклад каждого шага
        db.commit()

    assert spans[0] == timedelta(days=5)
    assert spans[1] == timedelta(days=2.5)
    assert spans[2] == timedelta(days=1.25)
    assert spans[-1] == timedelta(hours=12)


def test_expiry_never_shortens(db):
    """Подтверждение с половиной суток не должно обрезать чужой запас."""
    restaurant, _, users = make_fixtures(db)
    now = datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc)
    far = now + timedelta(days=4)
    code = PromoCode(
        brand_id=restaurant.brand_id,
        code="X2",
        code_key="x2",
        description="d",
        author_id=users[0].id,
        expires_at=far,
    )
    db.add(code)
    db.commit()

    # у человека это уже десятое подтверждение — вклад всего 12 часов
    for _ in range(9):
        db.add(PromoCodeVote(promo_code_id=code.id, user_id=users[1].id, worked=True))
    db.commit()
    apply_vote(db, code, users[1].id, True, now)
    assert code.expires_at == far


def test_two_complaints_kill_the_code(client, db):
    restaurant, _, _ = make_fixtures(db)
    author = auth(client, "+79167100009")
    first = auth(client, "+79167100010")
    second = auth(client, "+79167100011")
    code_id = add_code(client, author, restaurant.brand_id).json()["id"]

    client.post(f"/api/promo-codes/{code_id}/vote", json={"worked": False}, headers=first)
    assert len(client.get(f"/api/promo-codes?brand_id={restaurant.brand_id}").json()) == 1

    client.post(f"/api/promo-codes/{code_id}/vote", json={"worked": False}, headers=second)
    assert client.get(f"/api/promo-codes?brand_id={restaurant.brand_id}").json() == []


def test_one_person_complaining_twice_is_not_enough(client, db):
    restaurant, _, _ = make_fixtures(db)
    author = auth(client, "+79167100012")
    one = auth(client, "+79167100013")
    code_id = add_code(client, author, restaurant.brand_id).json()["id"]

    for _ in range(3):
        client.post(
            f"/api/promo-codes/{code_id}/vote", json={"worked": False}, headers=one
        )
    assert len(client.get(f"/api/promo-codes?brand_id={restaurant.brand_id}").json()) == 1


def test_working_vote_resets_the_complaints(client, db):
    """Считаем жалобы после последнего «сработал», а не за всю историю."""
    restaurant, _, _ = make_fixtures(db)
    author = auth(client, "+79167100014")
    first = auth(client, "+79167100015")
    second = auth(client, "+79167100016")
    code_id = add_code(client, author, restaurant.brand_id).json()["id"]

    client.post(f"/api/promo-codes/{code_id}/vote", json={"worked": False}, headers=first)
    client.post(f"/api/promo-codes/{code_id}/vote", json={"worked": True}, headers=second)
    # старая жалоба уже не считается, нужна новая пара
    client.post(f"/api/promo-codes/{code_id}/vote", json={"worked": False}, headers=first)
    assert len(client.get(f"/api/promo-codes?brand_id={restaurant.brand_id}").json()) == 1


# --- протухание и оживление ----------------------------------------------


def test_expired_code_hidden_and_revived_without_new_points(client, db):
    restaurant, _, _ = make_fixtures(db)
    author = auth(client, "+79167100017")
    other = auth(client, "+79167100018")
    code_id = add_code(client, author, restaurant.brand_id).json()["id"]
    client.post(f"/api/promo-codes/{code_id}/vote", json={"worked": True}, headers=other)

    code = db.get(PromoCode, code_id)
    code.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.commit()
    assert client.get(f"/api/promo-codes?brand_id={restaurant.brand_id}").json() == []

    # тот же код приносят заново — оживает старая строка, дублей нет
    resp = add_code(client, other, restaurant.brand_id, "sale20")
    assert resp.status_code == 201
    assert resp.json()["id"] == code_id
    assert db.scalar(select(PromoCode.id).where(PromoCode.id != code_id)) is None

    # и очки автору второй раз не капают
    assert (
        len(db.scalars(select(RatingEvent).where(RatingEvent.type == "promo_code_used")).all())
        == 1
    )


def test_vote_on_expired_code_is_404(client, db):
    restaurant, _, _ = make_fixtures(db)
    headers = auth(client, "+79167100019")
    code_id = add_code(client, headers, restaurant.brand_id).json()["id"]
    db.get(PromoCode, code_id).expires_at = datetime.now(timezone.utc) - timedelta(days=1)
    db.commit()

    resp = client.post(
        f"/api/promo-codes/{code_id}/vote", json={"worked": True}, headers=headers
    )
    assert resp.status_code == 404


def test_daily_limit(client, db):
    restaurant, _, _ = make_fixtures(db)
    headers = auth(client, "+79167100020")
    for i in range(settings.promo_code_daily_limit):
        assert add_code(client, headers, restaurant.brand_id, f"CODE{i}").status_code == 201
    resp = add_code(client, headers, restaurant.brand_id, "ONEMORE")
    assert resp.status_code == 429


def test_anonymous_cannot_add_or_vote(client, db):
    restaurant, _, _ = make_fixtures(db)
    headers = auth(client, "+79167100021")
    code_id = add_code(client, headers, restaurant.brand_id).json()["id"]

    assert client.post(
        "/api/promo-codes",
        json={"brand_id": restaurant.brand_id, "code": "ANON", "description": "нет"},
    ).status_code == 401
    assert client.post(
        f"/api/promo-codes/{code_id}/vote", json={"worked": True}
    ).status_code == 401
    # читать может кто угодно
    assert client.get(f"/api/promo-codes?brand_id={restaurant.brand_id}").status_code == 200


def test_blocked_user_cannot_vote(client, db):
    restaurant, _, _ = make_fixtures(db)
    author = auth(client, "+79167100022")
    blocked = auth(client, "+79167100023")
    code_id = add_code(client, author, restaurant.brand_id).json()["id"]

    user = db.scalar(select(User).where(User.phone == "+79167100023"))
    user.is_blocked = True
    db.commit()

    resp = client.post(
        f"/api/promo-codes/{code_id}/vote", json={"worked": True}, headers=blocked
    )
    assert resp.status_code == 403
