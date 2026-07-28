"""Статусы наличия: сила голоса, направленные переходы, устойчивая память.

Спека: docs/trust-and-rating-spec.md (§3, §5).

сила голоса = вес автора × свежесть × коэффициент канала
вклад в кворум = sqrt(сила), один голос — не больше половины кворума.

Статусы: available / unavailable / unknown (устойчивые) и
maybe_gone / maybe_appeared / disputed (переходные). Направление переходного
статуса берётся из последнего устойчивого (таблица item_status_states).
"""

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import (
    ItemStatusState,
    Report,
    ReportChannel,
    ReportItem,
    User,
)

AVAILABLE = "available"
UNAVAILABLE = "unavailable"
MAYBE_GONE = "maybe_gone"
MAYBE_APPEARED = "maybe_appeared"
DISPUTED = "disputed"
UNKNOWN = "unknown"

STABLE = {AVAILABLE, UNAVAILABLE, UNKNOWN}
EPS = 0.05  # массы меньше — считаем стороной без голосов


@dataclass
class ItemStatus:
    status: str = UNKNOWN
    yes_count: int = 0
    no_count: int = 0
    on_site_count: int = 0
    delivery_count: int = 0
    last_report_at: datetime | None = None


@dataclass
class StatusMap:
    by_item: dict[int, ItemStatus] = field(default_factory=dict)

    def get(self, promotion_item_id: int) -> ItemStatus:
        return self.by_item.get(promotion_item_id) or ItemStatus()


@dataclass
class _Vote:
    is_available: bool
    contribution: float  # sqrt(силы), с капом
    age_hours: float
    channel: ReportChannel
    created_at: datetime


def _freshness(age_hours: float) -> float:
    return 0.5 ** (age_hours / settings.vote_half_life_hours)


def _channel_coef(channel: ReportChannel, is_available: bool) -> float:
    if channel == ReportChannel.delivery:
        # «мне привезли» — сильный сигнал, «в меню доставки нет» — слабый
        return (
            settings.channel_delivery_yes_coef
            if is_available
            else settings.channel_delivery_no_coef
        )
    return settings.channel_on_site_coef


def _collect_votes(
    db: Session, restaurant_id: int, promotion_ids: list[int], now: datetime
) -> dict[int, list[_Vote]]:
    """Голоса по товарам: последний отчёт каждого пользователя в окне."""
    window_start = now - timedelta(hours=settings.status_window_hours)

    rn = (
        func.row_number()
        .over(
            partition_by=(Report.user_id, Report.promotion_id),
            # id — тайбрейк при одинаковом created_at
            order_by=(Report.created_at.desc(), Report.id.desc()),
        )
        .label("rn")
    )
    latest = (
        select(
            Report.id,
            Report.created_at,
            Report.channel,
            User.weight,
            rn,
        )
        .join(User, User.id == Report.user_id)
        .where(
            Report.restaurant_id == restaurant_id,
            Report.promotion_id.in_(promotion_ids),
            Report.created_at >= window_start,
        )
        .subquery()
    )

    rows = db.execute(
        select(
            ReportItem.promotion_item_id,
            ReportItem.is_available,
            latest.c.created_at,
            latest.c.channel,
            latest.c.weight,
        )
        .join(latest, ReportItem.report_id == latest.c.id)
        .where(latest.c.rn == 1)
    ).all()

    votes: dict[int, list[_Vote]] = {}
    for item_id, is_available, created_at, channel, weight in rows:
        age = max((now - created_at).total_seconds() / 3600.0, 0.0)
        strength = weight * _freshness(age) * _channel_coef(channel, is_available)
        votes.setdefault(item_id, []).append(
            _Vote(
                is_available=is_available,
                contribution=math.sqrt(strength),
                age_hours=age,
                channel=channel,
                created_at=created_at,
            )
        )
    return votes


def _cap_contributions(item_votes: list[_Vote]) -> None:
    """Один голос — не больше половины массы кворума (при ≥2 голосах)."""
    if len(item_votes) < 2:
        return
    total = sum(v.contribution for v in item_votes)
    for vote in item_votes:
        others = total - vote.contribution
        if vote.contribution > others:
            vote.contribution = others


def _resolve(stable: str, item_votes: list[_Vote]) -> str:
    yes = sum(v.contribution for v in item_votes if v.is_available)
    no = sum(v.contribution for v in item_votes if not v.is_available)

    if yes + no < EPS:
        return UNKNOWN
    if yes >= EPS and no < EPS:
        return AVAILABLE  # только «есть» — в т.ч. одиночный голос против пустоты
    if no >= EPS and yes < EPS:
        return UNAVAILABLE

    # обе стороны живы
    yes_fresh = min((v.age_hours for v in item_votes if v.is_available), default=1e9)
    no_fresh = min((v.age_hours for v in item_votes if not v.is_available), default=1e9)
    ratio = settings.flip_ratio
    stale = settings.stale_flip_hours

    if stable == AVAILABLE:
        if no >= ratio * yes:
            return UNAVAILABLE
        # поддержка протухла, вызов свежий — переключаем одним голосом
        if yes_fresh > stale and no_fresh <= stale:
            return UNAVAILABLE
        return MAYBE_GONE
    if stable == UNAVAILABLE:
        if yes >= ratio * no:
            return AVAILABLE
        if no_fresh > stale and yes_fresh <= stale:
            return AVAILABLE
        return MAYBE_APPEARED

    # устойчивого прошлого нет
    if yes >= ratio * no:
        return AVAILABLE
    if no >= ratio * yes:
        return UNAVAILABLE
    return DISPUTED


def _load_stables(
    db: Session, restaurant_id: int, item_ids: list[int]
) -> dict[int, ItemStatusState]:
    if not item_ids:
        return {}
    rows = db.scalars(
        select(ItemStatusState).where(
            ItemStatusState.restaurant_id == restaurant_id,
            ItemStatusState.promotion_item_id.in_(item_ids),
        )
    ).all()
    return {row.promotion_item_id: row for row in rows}


def compute_statuses(
    db: Session,
    restaurant_id: int,
    promotion_ids: list[int],
    now: datetime | None = None,
) -> StatusMap:
    """Отображаемые статусы всех товаров указанных акций в точке."""
    result = StatusMap()
    if not promotion_ids:
        return result
    now = now or datetime.now(timezone.utc)

    votes = _collect_votes(db, restaurant_id, promotion_ids, now)
    stables = _load_stables(db, restaurant_id, list(votes.keys()))

    for item_id, item_votes in votes.items():
        _cap_contributions(item_votes)
        stable_row = stables.get(item_id)
        stable = stable_row.stable if stable_row else UNKNOWN
        status = _resolve(stable, item_votes)
        result.by_item[item_id] = ItemStatus(
            status=status,
            yes_count=sum(1 for v in item_votes if v.is_available),
            no_count=sum(1 for v in item_votes if not v.is_available),
            on_site_count=sum(
                1 for v in item_votes if v.channel == ReportChannel.on_site
            ),
            delivery_count=sum(
                1 for v in item_votes if v.channel == ReportChannel.delivery
            ),
            last_report_at=max(v.created_at for v in item_votes),
        )
    return result


def refresh_stable_statuses(
    db: Session,
    restaurant_id: int,
    promotion_ids: list[int],
    now: datetime | None = None,
) -> None:
    """Пересчитать и сохранить устойчивые статусы (вызывается при новом отчёте
    и из фоновой джобы). Переходные статусы устойчивое состояние не меняют."""
    now = now or datetime.now(timezone.utc)
    votes = _collect_votes(db, restaurant_id, promotion_ids, now)
    stables = _load_stables(db, restaurant_id, list(votes.keys()))

    for item_id, item_votes in votes.items():
        _cap_contributions(item_votes)
        stable_row = stables.get(item_id)
        old_stable = stable_row.stable if stable_row else UNKNOWN
        display = _resolve(old_stable, item_votes)

        if display in (AVAILABLE, UNAVAILABLE):
            new_stable = display
        elif display == UNKNOWN:
            new_stable = UNKNOWN  # всё протухло — сомнение съело уверенность
        else:
            new_stable = old_stable  # переходная фаза память не трогает

        if stable_row is None:
            db.add(
                ItemStatusState(
                    restaurant_id=restaurant_id,
                    promotion_item_id=item_id,
                    stable=new_stable,
                )
            )
        elif stable_row.stable != new_stable:
            stable_row.stable = new_stable
