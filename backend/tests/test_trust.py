from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.models import RatingEvent, ReportChannel, ReportVerdict, VerdictOutcome
from app.services.status import compute_statuses, refresh_stable_statuses
from app.services.trust import mature_verdicts
from tests.test_status import make_fixtures, report


def hours_ago(h: float) -> datetime:
    return datetime.now(timezone.utc) - timedelta(hours=h)


def test_verdicts_weights_and_rating(db):
    restaurant, promotion, users = make_fixtures(db)
    item = promotion.items[0].id

    # 14 часов назад: users[0] сказал «есть», users[1] и users[2] подтвердили,
    # users[3] в то же окно сказал «нет» — его опровергнут
    report(db, users[0], restaurant, promotion, {item: True}, timedelta(hours=14))
    report(db, users[1], restaurant, promotion, {item: True}, timedelta(hours=13.5))
    report(db, users[2], restaurant, promotion, {item: True}, timedelta(hours=13))
    report(db, users[3], restaurant, promotion, {item: False}, timedelta(hours=13))

    matured = mature_verdicts(db)
    assert matured == 4

    verdicts = {
        v.user_id: v for v in db.scalars(select(ReportVerdict)).all()
    }
    assert verdicts[users[0].id].verdict == VerdictOutcome.confirmed
    assert verdicts[users[1].id].verdict == VerdictOutcome.confirmed
    assert verdicts[users[3].id].verdict == VerdictOutcome.refuted

    db.refresh(users[0])
    db.refresh(users[3])
    assert users[0].weight > 1.0       # подтверждение растит вес
    assert users[3].weight == 0.5      # опровержение режет вдвое

    # рейтинг: подтверждённым +5, опровергнутому −5
    events = db.scalars(select(RatingEvent)).all()
    by_user = {}
    for e in events:
        by_user.setdefault(e.user_id, []).append(e)
    assert any(e.type in ("report_confirmed", "pioneer") for e in by_user[users[0].id])
    assert any(e.type == "report_refuted" and e.points < 0 for e in by_user[users[3].id])

    # повторный прогон ничего не плодит
    assert mature_verdicts(db) == 0


def test_neutral_when_alone(db):
    """Одинокий отчёт без консенсуса — нейтрален: ни бонуса, ни штрафа."""
    restaurant, promotion, users = make_fixtures(db)
    report(db, users[0], restaurant, promotion,
           {promotion.items[0].id: True}, timedelta(hours=15))
    mature_verdicts(db)
    verdict = db.scalar(select(ReportVerdict))
    assert verdict.verdict == VerdictOutcome.neutral
    db.refresh(users[0])
    assert users[0].weight == 1.0


def test_delivery_no_is_weak(db):
    """Доставочные «в меню нет» не перебивают свежее «есть» с точки."""
    restaurant, promotion, users = make_fixtures(db)
    item = promotion.items[0].id

    report(db, users[0], restaurant, promotion, {item: True}, timedelta(minutes=30))
    refresh_stable_statuses(db, restaurant.id, [promotion.id])
    db.commit()
    assert compute_statuses(db, restaurant.id, [promotion.id]).get(item).status == "available"

    for u in (users[1], users[2]):
        r = report(db, u, restaurant, promotion, {item: False}, timedelta(minutes=10))
        r.channel = ReportChannel.delivery
    db.commit()

    st = compute_statuses(db, restaurant.id, [promotion.id]).get(item)
    # сомнение появилось, но полного переключения нет
    assert st.status == "maybe_gone"
    assert st.delivery_count == 2 and st.on_site_count == 1


def test_directional_transitions(db):
    restaurant, promotion, users = make_fixtures(db)
    item = promotion.items[0].id

    # Устойчивое «есть» двумя свежими голосами с точки
    report(db, users[0], restaurant, promotion, {item: True}, timedelta(minutes=50))
    report(db, users[1], restaurant, promotion, {item: True}, timedelta(minutes=40))
    refresh_stable_statuses(db, restaurant.id, [promotion.id])
    db.commit()

    # Один свежий «нет» против живого консенсуса — «возможно кончилось»
    report(db, users[2], restaurant, promotion, {item: False}, timedelta(minutes=5))
    assert compute_statuses(db, restaurant.id, [promotion.id]).get(item).status == "maybe_gone"

    # Ещё двое «нет» — кворум добит, статус переключён
    report(db, users[3], restaurant, promotion, {item: False}, timedelta(minutes=3))
    extra = report(db, users[0], restaurant, promotion, {item: False}, timedelta(minutes=1))
    assert extra is not None
    st = compute_statuses(db, restaurant.id, [promotion.id]).get(item)
    assert st.status == "unavailable"


def test_leaderboard_api(client, db):
    restaurant, promotion, users = make_fixtures(db)
    item = promotion.items[0].id
    report(db, users[0], restaurant, promotion, {item: True}, timedelta(hours=14))
    report(db, users[1], restaurant, promotion, {item: True}, timedelta(hours=13))
    mature_verdicts(db)

    resp = client.get("/api/rating?city=Санкт-Петербург&period=month")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["entries"]) >= 1
    top = data["entries"][0]
    assert top["points"] > 0 and top["position"] == 1

    # карточка игрока: категории видны всем, лента — только владельцу
    card = client.get(f"/api/rating/users/{top['user_id']}?period=month").json()
    assert card["total_points"] >= top["points"]
    assert card["events"] is None
    assert any(c["type"] in ("report_confirmed", "pioneer") for c in card["categories"])
