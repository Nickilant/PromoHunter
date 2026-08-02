"""Сценарии определения истины — чистая арифметика фильтра, без базы.

Двадцать один сценарий из разбора: что должно происходить и что происходит.
"""

from datetime import datetime, timedelta, timezone

from app.models import ReportChannel
from app.services.truth import (
    Vote,
    believe,
    confident_status,
    time_in_status,
)

NOW = datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc)


def v(minutes_ago, available=True, channel=ReportChannel.on_site, weight=1.0, receipt=False):
    return Vote(
        at=NOW - timedelta(minutes=minutes_ago),
        is_available=available,
        channel=channel,
        weight=weight,
        receipt_verified=receipt,
    )


def status(votes, now=NOW):
    return confident_status(believe(votes, now))


def chance(votes, now=NOW):
    return believe(votes, now).probability


def stream(count, span_minutes, ends_minutes_ago, available=True):
    """Ровный поток из count голосов, последний — ends_minutes_ago назад."""
    step = span_minutes / count
    return [v(ends_minutes_ago + step * i, available) for i in range(count)]


def burst(count, available=False, every_seconds=40, ends_minutes_ago=0.0):
    """Очередь одинаковых голосов подряд, по одному раз в every_seconds."""
    return [
        v(ends_minutes_ago + (count - 1 - i) * every_seconds / 60.0, available)
        for i in range(count)
    ]


# --- 1-4: пустота и одиночные свидетельства ---------------------------------


def test_01_no_votes_no_truth():
    assert status([]) is None


def test_02_single_fresh_yes_is_enough():
    """Спорить не с кем — одиночный голос говорит сам за себя."""
    assert status([v(0)]) == "available"


def test_03_single_fresh_no_is_enough():
    assert status([v(0, False)]) == "unavailable"


def test_04_uncontested_evidence_does_not_rot():
    """Никто не возражал сутки — статус держится, возраст показывается отдельно."""
    assert status([v(60 * 20)]) == "available"


# --- 5-9: одиночное возражение против живого консенсуса ----------------------


def test_05_one_no_does_not_flip_two_yes():
    votes = [v(50), v(40), v(5, False)]
    assert status(votes) is None  # уверенности нет — карточка покажет «возможно»
    assert chance(votes) > 0.6    # но перевес всё ещё за «есть»


def test_06_third_no_finishes_the_flip():
    """Двое сказали «есть» — чтобы это перебить, нужны трое, а не один."""
    assert status([v(50), v(40), v(5, False), v(3, False)]) is None
    assert status([v(50), v(40), v(5, False), v(3, False), v(1, False)]) == "unavailable"


def test_07_stale_yes_loses_to_fresh_no():
    assert status([v(300), v(0, False)]) is None
    assert chance([v(300), v(0, False)]) < 0.35


def test_08_fresh_yes_beats_stale_no():
    assert chance([v(300, False), v(0)]) > 0.7


def test_09_one_person_cannot_outvote_by_volume():
    """Голос у человека один — в фильтр попадает только последний отчёт.
    Проверяем: два разных человека против одного дают перевес."""
    assert chance([v(10), v(9), v(1, False)]) > 0.5


# --- 10-13: потолок уверенности и плотность потока ---------------------------


def test_10_ceiling_makes_200_equal_to_5():
    """Двести «есть» и пять «есть» за то же время дают одну уверенность."""
    dense = believe(stream(200, 120, 1), NOW).log_odds
    sparse = believe(stream(5, 120, 1), NOW).log_odds
    assert dense > sparse            # плотный поток поднимает потолок
    assert dense / sparse < 2.0      # но не в сорок раз


def test_11_ceiling_grows_with_density_not_with_history():
    """Тот же счёт, растянутый на сутки, потолок не поднимает."""
    crowded = believe(stream(200, 120, 1), NOW).log_odds
    trickle = believe(stream(200, 60 * 20, 1), NOW).log_odds
    assert crowded > trickle + 1.0


def test_12_scattered_errors_are_absorbed():
    """Пять ошибочных «нет», размазанных по двухчасовому потоку «есть»."""
    votes = stream(200, 120, 1)
    for minutes in (15, 40, 65, 90, 110):
        votes.append(v(minutes + 0.2, False))
    assert status(votes) == "available"
    assert chance(votes) > 0.99


def test_13_three_consecutive_no_only_raise_doubt():
    """Три «нет» подряд поверх двухсот «есть» снимают уверенность,
    но до «кончилось» не доводят — это ещё может быть шум."""
    votes = stream(200, 120, 3) + burst(3)
    assert status(votes) is None
    assert 0.15 < chance(votes) < 0.85


# --- 14-16: товар кончился ---------------------------------------------------


def test_14_run_out_flips_in_five_votes():
    """Поток «нет» пробивает двухсотголосый консенсус за пять голосов
    (при 1.5 отчёта в минуту — примерно три с половиной минуты)."""
    base = stream(200, 120, 4)
    assert status(base + burst(4)) is None
    assert status(base + burst(5)) == "unavailable"


def test_15_stray_yes_costs_about_one_no():
    """«Мне привезли» от давнего предзаказа откатывает примерно на один голос."""
    base = stream(200, 120, 6)
    # шесть голосов подряд; в смешанном варианте третий — «есть» от заказа,
    # который сделали давно и товар для него отложили
    clean = [v((6 - 1 - i) * 40 / 60.0, False) for i in range(6)]
    mixed = [v((6 - 1 - i) * 40 / 60.0, i == 2) for i in range(6)]
    assert status(base + clean) == "unavailable"
    assert status(base + mixed) is None          # один «есть» отодвинул переворот
    assert status(base + mixed + burst(1)) == "unavailable"


def test_16_three_stray_yes_delay_but_do_not_stop():
    """Три «есть» вперемешку с потоком «нет» отодвигают переворот
    с пятого голоса на двенадцатый, но не отменяют его."""
    base = stream(200, 120, 12)
    mixed = [v((12 - 1 - i) * 40 / 60.0, i in (4, 6, 8)) for i in range(12)]
    assert status(base + mixed[:10]) is None
    assert status(base + mixed) == "unavailable"


# --- 17-19: каналы и веса ----------------------------------------------------


def test_17_delivery_no_is_weak():
    """«В меню доставки нет» — не свидетельство о зале."""
    votes = [v(2), v(0, False, ReportChannel.delivery)]
    assert chance(votes) > 0.6


def test_17b_receipt_outweighs_plain_reports():
    """Чек ФНС — почти доказательство: человек держал товар в руках."""
    quiet_gone = [v(2, False), v(1, False)]
    assert status(quiet_gone) == "unavailable"
    # один чек снимает уверенность, второй возвращает «есть»
    assert status(quiet_gone + [v(0, True, receipt=True)]) is None
    assert status(quiet_gone + [v(0.5, True, receipt=True), v(0, True, receipt=True)]) == (
        "available"
    )
    # против обычных «есть» тот же откат стоит дороже
    assert status(quiet_gone + [v(0.5), v(0)]) is None


def test_18_delivery_yes_is_weaker_than_on_site_yes():
    delivered = chance([v(0, True, ReportChannel.delivery)])
    on_site = chance([v(0)])
    assert delivered < on_site


def test_19_veteran_outweighs_newcomer_but_not_by_much():
    veteran_no = chance([v(2, True, weight=0.1), v(0, False, weight=9.0)])
    newcomer_no = chance([v(2, True, weight=9.0), v(0, False, weight=0.1)])
    assert veteran_no < 0.5 < newcomer_no
    assert newcomer_no - veteran_no < 0.85  # доверие ускоряет, но не решает в одиночку


# --- 20-21: возврат товара и предел возможностей -----------------------------


def test_20_restock_needs_real_evidence():
    gone = stream(200, 120, 10) + burst(6)
    assert status(gone) == "unavailable"
    assert status(gone + burst(3, available=True, ends_minutes_ago=0)) is None
    assert status(gone + burst(5, available=True, ends_minutes_ago=0)) == "available"


def test_21_small_collusion_still_wins():
    """Честная граница: пятеро сговорившихся неотличимы от конца товара.
    Против этого работает не арифметика голосов, а вес и подтверждения."""
    votes = stream(200, 120, 4) + burst(5)
    assert status(votes) == "unavailable"


# --- выдержка уведомления ----------------------------------------------------


def test_dwell_is_not_met_right_after_the_flip():
    votes = stream(200, 120, 4) + burst(5)
    belief = believe(votes, NOW)
    held = time_in_status(belief, "unavailable", NOW - timedelta(minutes=20), NOW)
    assert held < 10 * 60


def test_dwell_ripens_when_the_flow_stops():
    """Поток «нет» оборвался вместе с товаром — выдержка добирается временем."""
    later = NOW + timedelta(minutes=12)
    votes = stream(200, 120, 4) + burst(5)
    belief = believe(votes, later)
    held = time_in_status(belief, "unavailable", later - timedelta(minutes=20), later)
    assert held >= 10 * 60


def test_dwell_is_cumulative_not_consecutive():
    """Одиночный «есть» посреди потока «нет» отнимает от выдержки свои секунды,
    но не обнуляет её."""
    later = NOW + timedelta(minutes=12)
    base = stream(200, 120, 6)
    # одни и те же семь моментов; в mixed шестой голос — «есть»
    clean = base + [v((7 - 1 - i) * 40 / 60.0, False) for i in range(7)]
    mixed = base + [v((7 - 1 - i) * 40 / 60.0, i == 5) for i in range(7)]
    window = timedelta(minutes=20)
    held_clean = time_in_status(believe(clean, later), "unavailable", later - window, later)
    held_mixed = time_in_status(believe(mixed, later), "unavailable", later - window, later)
    assert held_mixed < held_clean
    assert held_mixed >= 10 * 60


def test_uncontested_dwell_counts_whole_segment():
    votes = [v(30)]
    held = time_in_status(believe(votes, NOW), "available", NOW - timedelta(minutes=20), NOW)
    assert held == 20 * 60
