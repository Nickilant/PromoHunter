"""Определение истины: байесовский фильтр логарифмических шансов.

Спека: docs/trust-and-rating-spec.md (§3).

Идея. Каждый голос — свидетельство, а не единица массы. Свидетельства
складываются в логарифмических шансах, между свидетельствами накопленное
убеждение экспоненциально распадается:

    ℓ ← ℓ · 2^(−Δt / H)          распад между голосами
    ℓ ← ℓ + s · k · trust        свидетельство (s = +1 «есть», −1 «нет»)
    ℓ ← clamp(ℓ, ±L_max)         потолок уверенности
    p  = 1 / (1 + e^−ℓ)          вероятность «товар есть»

Два свойства, ради которых всё это:

1. Потолок L_max растёт от плотности потока, а не от общего числа голосов.
   Двести «есть» и пять «есть» дают одну и ту же уверенность — разница в
   том, как быстро точка чинит себя после случайного «нет». Считать надо не
   «сколько голосов нужно для переворота», а «сколько времени»: на людной
   точке «нет» прилетают с той же частотой, что и «есть», поэтому высокий
   потолок пробивается за те же минуты, что низкий на тихой.

2. Одиночное свидетельство против пустоты говорит само за себя. Если
   противоположных голосов нет вообще, спорить не с чем — статус берётся
   напрямую, без порогов. Фильтр решает только спорные случаи.
"""

import math
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.config import settings
from app.models import ReportChannel

AVAILABLE = "available"
UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class Vote:
    """Голос: последний отчёт пользователя по товару в окне."""

    at: datetime
    is_available: bool
    channel: ReportChannel = ReportChannel.on_site
    weight: float = 1.0
    receipt_verified: bool = False


@dataclass(frozen=True)
class Segment:
    """Кусок траектории ℓ(t): от голоса до следующего голоса.

    Внутри куска состав голосов не меняется, а ℓ монотонно ползёт к нулю —
    поэтому пороги пересекаются не больше одного раза, в замкнутой форме.
    """

    start: datetime
    log_odds: float          # ℓ сразу после голоса, открывающего кусок
    contested: bool          # есть ли к этому моменту голоса обеих сторон
    dominant_available: bool  # при contested=False — куда смотрит единственная сторона


@dataclass
class Belief:
    log_odds: float
    probability: float
    contested: bool
    dominant_available: bool
    last_vote_at: datetime | None
    segments: list[Segment]


def trust_of(weight: float) -> float:
    """Скрытый вес автора → множитель свидетельства.

    Корень сжимает разлёт весов (0.1…10.0) так, чтобы ветеран стоил примерно
    полутора новичков, а не тридцати: доверие ускоряет консенсус, но не даёт
    одному человеку решать за точку.
    """
    return min(settings.truth_trust_max, max(settings.truth_trust_min, math.sqrt(weight)))


def evidence_of(vote: Vote) -> float:
    """Знаковый вклад голоса в логарифмические шансы."""
    if vote.receipt_verified and vote.is_available:
        # Чек ФНС — почти доказательство: человек держал товар в руках
        # минуту назад. Спорить с ним накопленной историей бессмысленно.
        k = settings.truth_k_receipt
    elif vote.channel == ReportChannel.delivery:
        # «мне привезли» — свидетельство о прошлом (заказ готовился),
        # «в меню доставки нет» — вообще не о зале
        k = (
            settings.truth_k_delivery_yes
            if vote.is_available
            else settings.truth_k_delivery_no
        )
    else:
        k = settings.truth_k_on_site
    sign = 1.0 if vote.is_available else -1.0
    return sign * k * trust_of(vote.weight)


def ceiling_for(density: int) -> float:
    """Потолок уверенности от плотности потока голосов за последний час."""
    return min(
        settings.truth_ceiling_max,
        settings.truth_ceiling_base + settings.truth_ceiling_slope * math.log1p(density),
    )


def _decay(log_odds: float, seconds: float) -> float:
    hours = seconds / 3600.0
    return log_odds * 0.5 ** (hours / settings.truth_half_life_hours)


def probability(log_odds: float) -> float:
    return 1.0 / (1.0 + math.exp(-log_odds))


def log_odds_of(p: float) -> float:
    return math.log(p / (1.0 - p))


def believe(votes: list[Vote], now: datetime) -> Belief:
    """Проиграть голоса по времени и получить убеждение на момент now."""
    ordered = sorted(votes, key=lambda v: v.at)
    window = timedelta(minutes=settings.truth_density_window_minutes)

    segments: list[Segment] = []
    log_odds = 0.0
    prev_at: datetime | None = None
    yes_seen = no_seen = False
    oldest = 0  # левая граница окна плотности

    for index, vote in enumerate(ordered):
        if prev_at is not None:
            log_odds = _decay(log_odds, (vote.at - prev_at).total_seconds())
        log_odds += evidence_of(vote)

        while ordered[oldest].at <= vote.at - window:
            oldest += 1
        limit = ceiling_for(index - oldest + 1)
        log_odds = max(-limit, min(limit, log_odds))

        yes_seen = yes_seen or vote.is_available
        no_seen = no_seen or not vote.is_available
        segments.append(
            Segment(
                start=vote.at,
                log_odds=log_odds,
                contested=yes_seen and no_seen,
                dominant_available=yes_seen,
            )
        )
        prev_at = vote.at

    if prev_at is not None:
        log_odds = _decay(log_odds, max((now - prev_at).total_seconds(), 0.0))
        # Поток мог стихнуть — потолок опустился, убеждение опускается вместе с ним
        density = sum(1 for v in ordered if v.at > now - window)
        limit = ceiling_for(density)
        log_odds = max(-limit, min(limit, log_odds))

    return Belief(
        log_odds=log_odds,
        probability=probability(log_odds),
        contested=yes_seen and no_seen,
        dominant_available=yes_seen,
        last_vote_at=prev_at,
        segments=segments,
    )


def confident_status(belief: Belief) -> str | None:
    """Уверенный статус: available / unavailable / None (уверенности нет).

    Без спора решает сама сторона: один «есть» на девственной точке — это
    «есть», сколько бы ни было часов этому отчёту. Возраст данных
    показывается отдельно, временем последнего отчёта.
    """
    if belief.last_vote_at is None:
        return None
    if not belief.contested:
        return AVAILABLE if belief.dominant_available else UNAVAILABLE
    if belief.probability >= settings.truth_p_available:
        return AVAILABLE
    if belief.probability <= settings.truth_p_unavailable:
        return UNAVAILABLE
    return None


def _status_at(segment: Segment) -> str | None:
    """Уверенный статус в начале куска — дальше ℓ только слабеет."""
    if not segment.contested:
        return AVAILABLE if segment.dominant_available else UNAVAILABLE
    if segment.log_odds >= log_odds_of(settings.truth_p_available):
        return AVAILABLE
    if segment.log_odds <= log_odds_of(settings.truth_p_unavailable):
        return UNAVAILABLE
    return None


def time_in_status(belief: Belief, status: str, since: datetime, now: datetime) -> float:
    """Сколько секунд в окне [since, now] уверенный статус был равен status.

    Накопительно, а не подряд: одиночный «есть» посреди потока «нет» стоит
    сорока секунд выдержки, а не сбрасывает её в ноль. Именно это отличает
    случайный шум от возвращения товара.
    """
    total = 0.0
    for index, segment in enumerate(belief.segments):
        end = belief.segments[index + 1].start if index + 1 < len(belief.segments) else now
        start = max(segment.start, since)
        if end <= start:
            continue

        if _status_at(segment) != status:
            # ℓ только приближается к нулю — если порог не взят сразу, он не будет взят
            continue
        if not segment.contested:
            total += (end - start).total_seconds()
            continue

        level = abs(
            log_odds_of(
                settings.truth_p_available
                if status == AVAILABLE
                else settings.truth_p_unavailable
            )
        )
        # |ℓ(t)| = |ℓ_0| · 2^(−Δ/H) держится выше уровня, пока Δ < H·log2(|ℓ_0|/level)
        span = settings.truth_half_life_hours * math.log2(abs(segment.log_odds) / level)
        leaves = segment.start + timedelta(hours=span)
        if leaves > start:
            total += (min(end, leaves) - start).total_seconds()
    return total
