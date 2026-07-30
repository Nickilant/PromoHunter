from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.config import settings
from app.models import Faction, PointControl, RatingEvent, Receipt, Report, User
from tests.test_status import make_fixtures

QR_TEMPLATE = "t={time}&s=957.00&fn=996044030258570{drive}&i={doc}&fp=2274263722&n=1"


def register(client, phone="+79165550001", city="Санкт-Петербург"):
    resp = client.post(
        "/api/auth/register",
        json={
            "phone": phone,
            "password": "secret123",
            "display_name": "Р",
            "city": city,
        },
    )
    assert resp.status_code in (200, 201), resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def fresh_qr(restaurant, doc: int, drive: int = 6, minutes_ago: int = 2) -> str:
    """QR с временем кассы: местное время точки, без зоны."""
    moment = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    local = moment + timedelta(minutes=restaurant.utc_offset_minutes)
    return QR_TEMPLATE.format(
        time=local.strftime("%Y%m%dT%H%M"), doc=doc, drive=drive
    )


def enable_game(client, headers, faction="green"):
    assert client.post("/api/game/mode", json={"enabled": True}, headers=headers).status_code == 200
    resp = client.post("/api/game/faction", json={"faction": faction}, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


# --- режим и сторона ------------------------------------------------------


def test_game_mode_is_off_by_default(client, db):
    headers = register(client)
    me = client.get("/api/auth/me", headers=headers).json()
    assert me["game_mode"] is False
    assert me["faction"] is None
    assert me["game_asked"] is False


def test_config_reports_balance_and_me(client, db):
    headers = register(client)
    resp = client.get("/api/game/config", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["enabled"] is True
    assert {f["key"] for f in data["factions"]} == {"green", "purple"}
    assert data["me"]["game_mode"] is False
    assert data["min_sum_rubles"] == settings.receipt_min_sum_kopeks // 100

    enable_game(client, headers, "purple")
    data = client.get("/api/game/config", headers=headers).json()
    assert data["me"]["faction"] == "purple"
    assert data["me"]["asked"] is True
    assert data["me"]["can_switch_at"] is not None
    purple = next(f for f in data["factions"] if f["key"] == "purple")
    assert purple["members"] == 1


def test_config_works_without_auth(client, db):
    resp = client.get("/api/game/config")
    assert resp.status_code == 200
    assert resp.json()["me"] is None


def test_declining_game_mode_is_remembered(client, db):
    headers = register(client)
    resp = client.post("/api/game/mode", json={"enabled": False}, headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["game_mode"] is False
    # Спросили один раз — больше не пристаём
    assert body["game_asked"] is True


def test_faction_switch_has_cooldown(client, db):
    headers = register(client)
    enable_game(client, headers, "green")
    resp = client.post("/api/game/faction", json={"faction": "purple"}, headers=headers)
    assert resp.status_code == 429
    assert "раз в" in resp.json()["detail"]


def test_crowded_faction_is_closed_for_joining(client, db):
    """Все в одну сторону не набегут: перекошенная фракция закрывается."""
    city = "Балансбург"
    for i in range(12):
        user = User(
            phone=f"+7999000{i:04d}",
            password_hash="x",
            display_name=f"U{i}",
            city=city,
            faction=Faction.green,
            game_mode=True,
        )
        db.add(user)
    db.commit()

    headers = register(client, phone="+79165559999", city=city)
    client.post("/api/game/mode", json={"enabled": True}, headers=headers)
    resp = client.post("/api/game/faction", json={"faction": "green"}, headers=headers)
    assert resp.status_code == 409
    assert "набор закрыт" in resp.json()["detail"]

    # в меньшинство — пожалуйста
    resp = client.post("/api/game/faction", json={"faction": "purple"}, headers=headers)
    assert resp.status_code == 200


# --- чек в отчёте ---------------------------------------------------------


def test_receipt_report_adds_strength_and_points(client, db):
    restaurant, promotion, _ = make_fixtures(db)
    headers = register(client)
    enable_game(client, headers, "green")
    item = promotion.items[0]

    body = {
        "restaurant_id": restaurant.id,
        "promotion_id": promotion.id,
        "items": [{"promotion_item_id": item.id, "is_available": True}],
        "lat": restaurant.lat,
        "lng": restaurant.lng,
        "receipt_qr": fresh_qr(restaurant, 500),
    }
    resp = client.post("/api/reports", json=body, headers=headers)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["is_receipt_verified"] is True
    assert data["capture"]["faction"] == "green"
    assert data["capture"]["strength"] == 1.0
    assert data["capture"]["points"] == settings.rating_capture_receipt_points

    control = db.get(PointControl, restaurant.id)
    assert control.green_score == 1.0
    assert control.green_receipts == 1
    assert control.battle_started_at is not None  # пошла шкала на нейтральной точке

    assert db.scalar(select(Receipt.id)) is not None
    events = db.scalars(
        select(RatingEvent).where(RatingEvent.type == "capture_receipt")
    ).all()
    assert len(events) == 1


def test_receipt_bypasses_cooldown_but_plain_report_does_not(client, db):
    restaurant, promotion, _ = make_fixtures(db)
    headers = register(client)
    enable_game(client, headers, "green")
    item = promotion.items[0]
    base = {
        "restaurant_id": restaurant.id,
        "promotion_id": promotion.id,
        "items": [{"promotion_item_id": item.id, "is_available": True}],
        "lat": restaurant.lat,
        "lng": restaurant.lng,
    }
    assert client.post("/api/reports", json=base, headers=headers).status_code == 201
    # без чека — кулдаун
    assert client.post("/api/reports", json=base, headers=headers).status_code == 429
    # с чеком — можно: человек снова что-то купил
    with_receipt = dict(base, receipt_qr=fresh_qr(restaurant, 700))
    assert client.post("/api/reports", json=with_receipt, headers=headers).status_code == 201


def test_diminishing_returns_per_user(client, db):
    """Сотня чеков от одного человека не решает судьбу точки."""
    restaurant, promotion, _ = make_fixtures(db)
    headers = register(client)
    enable_game(client, headers, "green")
    item = promotion.items[0]

    strengths = []
    for doc in range(800, 806):
        resp = client.post(
            "/api/reports",
            json={
                "restaurant_id": restaurant.id,
                "promotion_id": promotion.id,
                "items": [{"promotion_item_id": item.id, "is_available": True}],
                "lat": restaurant.lat,
                "lng": restaurant.lng,
                "receipt_qr": fresh_qr(restaurant, doc),
            },
            headers=headers,
        )
        assert resp.status_code == 201, resp.text
        strengths.append(resp.json()["capture"]["strength"])

    assert strengths[:4] == settings.capture_daily_returns
    assert strengths[4] == settings.capture_daily_returns[-1]
    # шесть чеков одного человека весят чуть больше двух первых — точку
    # в одиночку не удержать, нужны разные люди
    assert sum(strengths) < 2.5 * strengths[0]


def test_receipt_needs_game_mode_and_faction(client, db):
    restaurant, promotion, _ = make_fixtures(db)
    headers = register(client)
    resp = client.post(
        "/api/reports",
        json={
            "restaurant_id": restaurant.id,
            "promotion_id": promotion.id,
            "items": [{"promotion_item_id": promotion.items[0].id, "is_available": True}],
            "lat": restaurant.lat,
            "lng": restaurant.lng,
            "receipt_qr": fresh_qr(restaurant, 900),
        },
        headers=headers,
    )
    assert resp.status_code == 400
    assert "выберите сторону" in resp.json()["detail"]
    # отчёт не создался: незачёт не оставляет следов
    assert db.scalar(select(Report.id)) is None


def test_receipt_requires_a_yes(client, db):
    restaurant, promotion, _ = make_fixtures(db)
    headers = register(client)
    enable_game(client, headers, "green")
    resp = client.post(
        "/api/reports",
        json={
            "restaurant_id": restaurant.id,
            "promotion_id": promotion.id,
            "items": [{"promotion_item_id": promotion.items[0].id, "is_available": False}],
            "lat": restaurant.lat,
            "lng": restaurant.lng,
            "receipt_qr": fresh_qr(restaurant, 901),
        },
        headers=headers,
    )
    assert resp.status_code == 400
    assert "отметьте хотя бы один" in resp.json()["detail"]


def test_receipt_far_from_point_rejected(client, db):
    restaurant, promotion, _ = make_fixtures(db)
    restaurant.lat, restaurant.lng = 59.935, 30.325
    db.commit()
    headers = register(client)
    enable_game(client, headers, "green")
    resp = client.post(
        "/api/reports",
        json={
            "restaurant_id": restaurant.id,
            "promotion_id": promotion.id,
            "items": [{"promotion_item_id": promotion.items[0].id, "is_available": True}],
            "lat": 55.75,
            "lng": 37.62,
            "receipt_qr": fresh_qr(restaurant, 902),
        },
        headers=headers,
    )
    assert resp.status_code == 400
    assert "от точки" in resp.json()["detail"]
    assert db.scalar(select(Report.id)) is None


def test_receipt_refutes_recent_denials(client, db):
    """Чек с «есть» переоценивает свежие «нет» по тому же товару."""
    restaurant, promotion, users = make_fixtures(db)
    item = promotion.items[0]
    liar = users[0]
    liar_weight_before = liar.weight

    db.add(
        Report(
            user_id=liar.id,
            restaurant_id=restaurant.id,
            promotion_id=promotion.id,
            created_at=datetime.now(timezone.utc) - timedelta(minutes=10),
            items=[__import__("app.models", fromlist=["ReportItem"]).ReportItem(
                promotion_item_id=item.id, is_available=False
            )],
        )
    )
    db.commit()

    headers = register(client)
    enable_game(client, headers, "purple")
    resp = client.post(
        "/api/reports",
        json={
            "restaurant_id": restaurant.id,
            "promotion_id": promotion.id,
            "items": [{"promotion_item_id": item.id, "is_available": True}],
            "lat": restaurant.lat,
            "lng": restaurant.lng,
            "receipt_qr": fresh_qr(restaurant, 903),
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["capture"]["refuted_denials"] == 1
    db.refresh(liar)
    # штраф мягче обычного ×0.5 — человек мог честно не найти товар
    assert liar.weight == liar_weight_before * settings.weight_receipt_refute_factor


# --- табло ---------------------------------------------------------------


def test_points_endpoint_returns_timer(client, db):
    restaurant, promotion, _ = make_fixtures(db)
    restaurant.city = "Таймерск"
    db.commit()
    headers = register(client, city="Таймерск")
    enable_game(client, headers, "green")
    client.post(
        "/api/reports",
        json={
            "restaurant_id": restaurant.id,
            "promotion_id": promotion.id,
            "items": [{"promotion_item_id": promotion.items[0].id, "is_available": True}],
            "lat": restaurant.lat,
            "lng": restaurant.lng,
            "receipt_qr": fresh_qr(restaurant, 950),
        },
        headers=headers,
    )

    resp = client.get("/api/game/points?city=Таймерск")
    assert resp.status_code == 200
    points = resp.json()
    assert len(points) == 1
    point = points[0]
    assert point["restaurant_id"] == restaurant.id
    assert point["leader"] == "green"
    assert point["owner"] is None
    assert point["eta_seconds"] > 0
    assert point["green_receipts"] == 1


def test_point_detail_shows_my_contribution(client, db):
    restaurant, promotion, _ = make_fixtures(db)
    headers = register(client)
    enable_game(client, headers, "green")
    client.post(
        "/api/reports",
        json={
            "restaurant_id": restaurant.id,
            "promotion_id": promotion.id,
            "items": [{"promotion_item_id": promotion.items[0].id, "is_available": True}],
            "lat": restaurant.lat,
            "lng": restaurant.lng,
            "receipt_qr": fresh_qr(restaurant, 960),
        },
        headers=headers,
    )
    resp = client.get(f"/api/game/points/{restaurant.id}/me", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["my_receipts_today"] == 1
    assert data["my_strength_today"] == 1.0
    assert data["my_faction"] == "green"


def test_standings_shape(client, db):
    restaurant, _, _ = make_fixtures(db)
    restaurant.city = "Зачётск"
    db.commit()
    resp = client.get("/api/game/standings?city=Зачётск")
    assert resp.status_code == 200
    data = resp.json()
    assert data["points_total"] == 1
    assert data["neutral"] == 1
    assert len(data["standings"]) == 2
    assert all(s["held_share"] == 0.0 for s in data["standings"])


def test_point_detail_for_untouched_point(client, db):
    restaurant, _, _ = make_fixtures(db)
    resp = client.get(f"/api/game/points/{restaurant.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["owner"] is None
    assert data["green_score"] == 0.0
    assert data["eta_seconds"] is None


def test_points_include_untouched_ones(client, db):
    """Свободные точки тоже на табло: иначе в списках у половины адресов
    вообще ничего игрового, хотя режим включён."""
    restaurant, promotion, _ = make_fixtures(db)
    restaurant.city = "Табло"
    quiet = restaurant.__class__(
        brand_id=restaurant.brand_id, city="Табло", address="Тихая, 1", lat=0, lng=0
    )
    hidden = restaurant.__class__(
        brand_id=restaurant.brand_id,
        city="Табло",
        address="Закрытая, 2",
        lat=0,
        lng=0,
        is_active=False,
    )
    db.add_all([quiet, hidden])
    db.commit()

    points = client.get("/api/game/points?city=Табло").json()
    ids = {p["restaurant_id"] for p in points}
    assert restaurant.id in ids
    assert quiet.id in ids          # за неё не воевали — но она на табло
    assert hidden.id not in ids     # выключенных точек в игре нет

    fresh = next(p for p in points if p["restaurant_id"] == quiet.id)
    assert fresh["owner"] is None
    assert fresh["leader"] is None
    assert fresh["green_score"] == 0.0
    assert fresh["green_receipts"] == 0
    assert fresh["eta_seconds"] is None
