from datetime import datetime, timedelta, timezone

from app.config import settings
from app.models import CaptureEvent, Faction, PointControl
from app.services.game import (
    BattleState,
    active_seconds,
    bar_speed,
    faction_balance,
    get_control,
    join_blocked,
    project,
    scores_at,
    simulate,
    underdog_coef,
)
from tests.test_status import make_fixtures

NOW = datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc)
BAR = settings.capture_bar_seconds


def state(
    *,
    owner=None,
    green=0.0,
    purple=0.0,
    green_progress=0.0,
    purple_progress=0.0,
    battle=None,
    truce=None,
    at=NOW,
) -> BattleState:
    return BattleState(
        owner=owner,
        green_score=green,
        purple_score=purple,
        green_progress=green_progress,
        purple_progress=purple_progress,
        progress_at=at,
        battle_started_at=battle,
        truce_until=truce,
    )


# --- сила и распад ---------------------------------------------------------


def test_score_decays_with_half_life(db):
    restaurant, _, _ = make_fixtures(db)
    control = get_control(db, restaurant.id, NOW)
    control.green_score = 8.0
    control.score_at = NOW
    green, _ = scores_at(control, NOW + timedelta(hours=settings.capture_half_life_hours))
    assert abs(green - 4.0) < 1e-6


def test_decay_is_symmetric_so_holding_alone_never_flips_ownership(db):
    """Распад одинаков у обеих сторон, поэтому лидер сам собой не меняется.

    Именно это спасает от «пинг-понга»: точка не переходит просто потому,
    что у владельца сила тает, а у претендента заморожена.
    """
    restaurant, _, _ = make_fixtures(db)
    control = get_control(db, restaurant.id, NOW)
    control.green_score, control.purple_score = 5.0, 4.9
    control.score_at = NOW
    for hours in (1, 24, 240, 2400):
        green, purple = scores_at(control, NOW + timedelta(hours=hours))
        assert green > purple


def test_score_scale_free_for_busy_points(db):
    """Точка с тысячей чеков в день не становится вечной собственностью.

    Сила — это экспоненциально сглаженная интенсивность, а не сумма истории:
    сторона, которая перестала покупать, за сутки теряет ощутимую долю.
    """
    restaurant, _, _ = make_fixtures(db)
    control = get_control(db, restaurant.id, NOW)
    control.green_score = 30_000.0  # месяц по тысяче чеков
    control.score_at = NOW
    green, _ = scores_at(control, NOW + timedelta(days=7))
    assert green < 30_000.0 * 0.55


# --- скорость шкалы -------------------------------------------------------


def test_bar_speed_grows_with_lead():
    assert bar_speed(10.0, 10.0) == 1.0
    assert bar_speed(1.0, 0.0) == 1.0  # нейтральная точка — базовые 4 часа
    assert bar_speed(40.0, 10.0) == settings.capture_bar_max_speed
    middle = bar_speed(20.0, 10.0)
    assert 1.0 < middle < settings.capture_bar_max_speed
    # при четырёхкратном перевесе шкала укладывается в 1 ч 40 мин
    assert abs(BAR / bar_speed(40.0, 10.0) - 6000) < 1


# --- рабочие часы ---------------------------------------------------------


def test_active_seconds_respects_point_hours():
    start = datetime(2026, 7, 30, 22, 0, tzinfo=timezone.utc)
    end = start + timedelta(hours=6)
    assert active_seconds(0, start, end) == 6 * 3600  # маска пустая — круглосуточно

    # точка работает 8:00–21:00 UTC
    mask = sum(1 << h for h in range(8, 21))
    # с 22:00 до 04:00 не работает вообще
    assert active_seconds(mask, start, end) == 0
    # с 06:00 до 10:00 рабочими будут только два часа
    morning = datetime(2026, 7, 30, 6, 0, tzinfo=timezone.utc)
    assert active_seconds(mask, morning, morning + timedelta(hours=4)) == 2 * 3600


def test_night_freezes_the_bar():
    mask = sum(1 << h for h in range(8, 21))
    night = datetime(2026, 7, 30, 23, 0, tzinfo=timezone.utc)
    s = state(green=4.0, purple=1.0, at=night)
    simulate(s, mask, night + timedelta(hours=5))
    assert s.green_progress == 0.0


# --- сценарий захвата -----------------------------------------------------


def test_neutral_point_is_taken_after_full_bar():
    s = state(green=2.0)
    # за 4 часа при отсутствии сопротивления шкала заполняется ровно
    res = simulate(s, 0, NOW + timedelta(seconds=BAR - 60))
    assert res == []
    assert s.battle_started_at == NOW
    assert s.owner is None

    res = simulate(s, 0, NOW + timedelta(seconds=BAR + 60))
    assert [r.kind for r in res] == ["capture"]
    assert s.owner == Faction.green
    assert s.green_progress == 0.0 and s.battle_started_at is None


def test_owner_at_peace_does_not_advance():
    """Владелец впереди — ничего не происходит, шкалы стоят."""
    s = state(owner=Faction.green, green=5.0, purple=1.0)
    res = simulate(s, 0, NOW + timedelta(hours=10))
    assert res == []
    assert s.green_progress == 0.0
    assert s.battle_started_at is None


def test_attack_starts_when_challenger_takes_the_lead():
    s = state(owner=Faction.green, green=4.0, purple=6.0)
    simulate(s, 0, NOW + timedelta(hours=1))
    assert s.battle_started_at == NOW
    assert s.purple_progress > 0
    assert s.green_progress == 0.0


def test_defender_bar_resumes_from_where_it_stopped():
    """Шкала отстающего не сбрасывается, а стоит на паузе и подтаивает."""
    # фиолетовые атакуют час
    s = state(owner=Faction.green, green=4.0, purple=6.0)
    simulate(s, 0, NOW + timedelta(hours=1))
    attacker_progress = s.purple_progress
    assert attacker_progress > 0

    # зелёные перебили количество чеков — шкала пошла в их сторону
    s.green_score = 9.0
    simulate(s, 0, NOW + timedelta(hours=2))
    assert s.green_progress > 0
    # прогресс атакующего сохранился, но подтаял
    assert 0 < s.purple_progress < attacker_progress
    assert s.purple_progress > attacker_progress * 0.8


def test_defender_filling_bar_repels_attack_and_gets_truce():
    s = state(
        owner=Faction.green,
        green=6.0,
        purple=4.0,
        green_progress=BAR - 10,
        purple_progress=1000,
        battle=NOW - timedelta(hours=3),
    )
    res = simulate(s, 0, NOW + timedelta(minutes=5))
    assert [r.kind for r in res] == ["defend"]
    assert s.owner == Faction.green
    assert s.green_progress == 0.0 and s.purple_progress == 0.0
    assert s.truce_until == NOW + timedelta(minutes=5) + timedelta(
        hours=settings.capture_truce_hours
    )


def test_truce_freezes_everything_then_releases():
    truce_end = NOW + timedelta(hours=1)
    s = state(owner=Faction.green, green=1.0, purple=5.0, truce=truce_end)
    simulate(s, 0, NOW + timedelta(minutes=30))
    assert s.purple_progress == 0.0
    assert s.battle_started_at is None

    # после перемирия атака начинается заново
    simulate(s, 0, truce_end + timedelta(hours=1))
    assert s.battle_started_at is not None
    assert s.purple_progress > 0


def test_challenger_takes_point_and_previous_owner_can_counterattack():
    s = state(
        owner=Faction.green,
        green=4.0,
        purple=6.0,
        purple_progress=BAR - 10,
        battle=NOW - timedelta(hours=3),
    )
    res = simulate(s, 0, NOW + timedelta(minutes=5))
    assert [r.kind for r in res] == ["capture"]
    assert s.owner == Faction.purple
    # шкалы обнулены, новая битва начнётся, когда зелёные снова выйдут вперёд
    assert s.battle_started_at is None
    s.green_score = 12.0
    simulate(s, 0, NOW + timedelta(hours=1))
    assert s.battle_started_at is not None
    assert s.green_progress > 0


def test_fading_attack_expires():
    s = state(
        owner=Faction.green,
        green=4.0,
        purple=0.1,  # атакующие выдохлись
        purple_progress=1000,
        battle=NOW - timedelta(hours=5),
    )
    res = simulate(s, 0, NOW + timedelta(minutes=10))
    assert [r.kind for r in res] == ["expired"]
    assert s.battle_started_at is None
    assert s.owner == Faction.green


def test_stale_battle_does_not_hang_forever():
    s = state(
        green=1.0,
        purple=1.0,  # ровно поровну, лидера нет
        green_progress=500,
        battle=NOW - timedelta(hours=settings.capture_battle_max_hours + 1),
    )
    res = simulate(s, 0, NOW + timedelta(minutes=1))
    assert [r.kind for r in res] == ["expired"]


# --- баланс фракций -------------------------------------------------------


def test_underdog_gets_stronger_receipts(db):
    restaurant, _, users = make_fixtures(db)
    for user in users[:3]:
        user.city = "Город"
        user.faction = Faction.green
    users[3].city = "Город"
    users[3].faction = Faction.purple
    db.commit()

    assert underdog_coef(db, "Город", Faction.green) == 1.0  # большинство без бонуса
    assert underdog_coef(db, "Город", Faction.purple) > 1.0
    assert underdog_coef(db, "Город", Faction.purple) <= (
        1.0 + settings.capture_underdog_max_bonus
    )


def test_join_is_blocked_for_the_crowded_side():
    # на старте города баланса ещё нет — пускаем всех
    assert join_blocked({Faction.green: 4, Faction.purple: 0}, Faction.green) is False
    # перекос — набор в большинство закрыт, в меньшинство открыт
    crowded = {Faction.green: 70, Faction.purple: 30}
    assert join_blocked(crowded, Faction.green) is True
    assert join_blocked(crowded, Faction.purple) is False


def test_faction_balance_counts_only_city(db):
    restaurant, _, users = make_fixtures(db)
    users[0].city, users[0].faction = "А", Faction.green
    users[1].city, users[1].faction = "Б", Faction.green
    users[2].city, users[2].faction = "А", Faction.purple
    db.commit()
    counts = faction_balance(db, "А")
    assert counts[Faction.green] == 1
    assert counts[Faction.purple] == 1


# --- проекция для табло ---------------------------------------------------


def test_project_reports_timer_and_owner(db):
    restaurant, _, _ = make_fixtures(db)
    control = get_control(db, restaurant.id, NOW)
    control.owner_faction = Faction.green
    control.green_score, control.purple_score = 4.0, 8.0
    control.score_at = control.progress_at = NOW
    control.battle_started_at = NOW
    db.commit()

    view = project(control, restaurant, NOW + timedelta(hours=1))
    assert view.owner == Faction.green
    assert view.leader == Faction.purple
    assert view.under_attack is True
    assert view.purple_progress > 0
    assert view.eta_seconds is not None and view.eta_seconds > 0
    assert view.is_active_now is True
    # чтение состояние не записывает
    db.refresh(control)
    assert control.purple_progress == 0.0


def test_advance_writes_capture_event(db):
    from app.services.game import advance

    restaurant, _, _ = make_fixtures(db)
    control = get_control(db, restaurant.id, NOW)
    control.green_score = 3.0
    control.score_at = control.progress_at = NOW
    control.battle_started_at = NOW
    control.green_progress = BAR - 5
    db.commit()

    advance(db, control, restaurant, NOW + timedelta(minutes=1))
    db.commit()
    assert control.owner_faction == Faction.green
    event = db.query(CaptureEvent).one()
    assert event.kind == "capture"
    assert event.city == restaurant.city
    assert db.get(PointControl, restaurant.id).captured_at is not None
