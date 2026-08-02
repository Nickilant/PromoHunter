"""Статусы наличия: определение истины, направленные переходы, уведомления.

Спека: docs/trust-and-rating-spec.md (§3, §5).

Арифметика живёт в app/services/truth.py — здесь только сбор голосов из базы,
словарь статусов для карточки точки и решение «пора ли будить подписчиков».

Статусы: available / unavailable / unknown (устойчивые) и
maybe_gone / maybe_appeared / disputed (переходные). Направление переходного
статуса берётся из последнего устойчивого (таблица item_status_states).
"""

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
from app.services.truth import Belief, Vote, believe, confident_status, time_in_status

AVAILABLE = "available"
UNAVAILABLE = "unavailable"
MAYBE_GONE = "maybe_gone"
MAYBE_APPEARED = "maybe_appeared"
DISPUTED = "disputed"
UNKNOWN = "unknown"


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


def _collect_votes(
    db: Session, restaurant_id: int, promotion_ids: list[int], now: datetime
) -> dict[int, list[Vote]]:
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
            Report.is_receipt_verified,
            User.weight,
            rn,
        )
        .join(User, User.id == Report.user_id)
        .where(
            Report.restaurant_id == restaurant_id,
            Report.promotion_id.in_(promotion_ids),
            Report.created_at >= window_start,
            # Статус считается на момент now — то, что случится позже,
            # в него не входит (важно для пересчёта задним числом)
            Report.created_at <= now,
        )
        .subquery()
    )

    rows = db.execute(
        select(
            ReportItem.promotion_item_id,
            ReportItem.is_available,
            latest.c.created_at,
            latest.c.channel,
            latest.c.is_receipt_verified,
            latest.c.weight,
        )
        .join(latest, ReportItem.report_id == latest.c.id)
        .where(latest.c.rn == 1)
    ).all()

    votes: dict[int, list[Vote]] = {}
    for item_id, is_available, created_at, channel, receipt_verified, weight in rows:
        votes.setdefault(item_id, []).append(
            Vote(
                at=created_at,
                is_available=is_available,
                channel=channel,
                weight=weight,
                receipt_verified=receipt_verified,
            )
        )
    return votes


def _display(stable: str, belief: Belief) -> str:
    """Отображаемый статус: уверенный — сам за себя, спорный — по памяти.

    Переходный статус только сообщает о сомнении и никого не будит, поэтому
    показывать его можно щедро: свежий «нет» против живого консенсуса — это
    «возможно кончилось», даже если до переворота ещё далеко.
    """
    confident = confident_status(belief)
    if confident is not None:
        return confident
    if stable == AVAILABLE:
        return MAYBE_GONE
    if stable == UNAVAILABLE:
        return MAYBE_APPEARED
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
        stable_row = stables.get(item_id)
        stable = stable_row.stable if stable_row else UNKNOWN
        result.by_item[item_id] = ItemStatus(
            status=_display(stable, believe(item_votes, now)),
            yes_count=sum(1 for v in item_votes if v.is_available),
            no_count=sum(1 for v in item_votes if not v.is_available),
            on_site_count=sum(
                1 for v in item_votes if v.channel == ReportChannel.on_site
            ),
            delivery_count=sum(
                1 for v in item_votes if v.channel == ReportChannel.delivery
            ),
            last_report_at=max(v.at for v in item_votes),
        )
    return result


def _should_notify(row: ItemStatusState, belief: Belief, status: str, now: datetime) -> bool:
    """Выдержка и кулдаун: карточку можно перерисовывать хоть каждую минуту,
    а подписчиков дёргать — нет.

    Выдержка накопительная в скользящем окне: одиночный «есть» посреди потока
    «нет» (заказ, который долго готовили, и товар для него отложили) отнимает
    от неё свои сорок секунд, но не обнуляет.
    """
    if status == row.notified:
        return False
    if row.notified_at is not None:
        cooldown = timedelta(minutes=settings.notify_cooldown_minutes)
        if now - row.notified_at < cooldown:
            return False
    since = now - timedelta(minutes=settings.notify_dwell_window_minutes)
    held = time_in_status(belief, status, since, now)
    return held >= settings.notify_dwell_minutes * 60


def refresh_stable_statuses(
    db: Session,
    restaurant_id: int,
    promotion_ids: list[int],
    now: datetime | None = None,
) -> list[tuple[int, str, str]]:
    """Пересчитать устойчивые статусы (вызывается при новом отчёте и из фоновой
    джобы). Переходные статусы устойчивое состояние не меняют.

    Возвращает переключения, дозревшие до уведомления:
    [(promotion_item_id, о чём говорили раньше, новый статус), ...]
    """
    now = now or datetime.now(timezone.utc)
    votes = _collect_votes(db, restaurant_id, promotion_ids, now)
    stables = _load_stables(db, restaurant_id, list(votes.keys()))
    flips: list[tuple[int, str, str]] = []

    for item_id, item_votes in votes.items():
        belief = believe(item_votes, now)
        confident = confident_status(belief)

        row = stables.get(item_id)
        if row is None:
            row = ItemStatusState(
                restaurant_id=restaurant_id,
                promotion_item_id=item_id,
                stable=UNKNOWN,
            )
            db.add(row)
        if confident is not None and row.stable != confident:
            row.stable = confident

        if confident is None or not _should_notify(row, belief, confident, now):
            continue
        flips.append((item_id, row.notified or UNKNOWN, confident))
        row.notified = confident
        row.notified_at = now

    return flips
