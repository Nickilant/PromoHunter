"""Дозревание вердиктов, пересчёт весов, дрейф, обновление устойчивых статусов.

Спека: docs/trust-and-rating-spec.md (§2, §4). Запускается фоновой джобой
(app.main) под advisory-lock и вручную: python -m app.services.trust
"""

import math
from datetime import datetime, timedelta, timezone

from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.config import settings
from app.models import (
    Promotion,
    PromotionItem,
    RatingEvent,
    Report,
    ReportChannel,
    ReportItem,
    ReportVerdict,
    Restaurant,
    User,
    VerdictOutcome,
)
from app.services.notify import notify_status_flips
from app.services.status import refresh_stable_statuses


def _channel_coef(channel: ReportChannel, is_available: bool) -> float:
    """Вес голоса в консенсусе при дозревании вердикта."""
    if channel == ReportChannel.delivery:
        # «мне привезли» — сильный сигнал, «в меню нет» — слабый
        return (
            settings.channel_delivery_yes_coef
            if is_available
            else settings.channel_delivery_no_coef
        )
    return settings.channel_on_site_coef


def _consensus_votes(
    db: Session, report: Report
) -> dict[int, tuple[float, float, list[tuple[datetime, bool]]]]:
    """Взвешенный консенсус других пользователей по товарам отчёта в окне ±N ч.

    Возвращает по товару: (масса «есть», масса «нет»,
    [(время, is_available), ...] — для определения первопроходства).
    """
    window = timedelta(hours=settings.consensus_window_hours)
    start, end = report.created_at - window, report.created_at + window

    rn = (
        func.row_number()
        .over(
            partition_by=Report.user_id,
            order_by=(Report.created_at.desc(), Report.id.desc()),
        )
        .label("rn")
    )
    latest = (
        select(Report.id, Report.created_at, Report.channel, User.weight, rn)
        .join(User, User.id == Report.user_id)
        .where(
            Report.restaurant_id == report.restaurant_id,
            Report.promotion_id == report.promotion_id,
            Report.user_id != report.user_id,
            Report.created_at >= start,
            Report.created_at <= end,
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

    consensus: dict[int, tuple[float, float, list[tuple[datetime, bool]]]] = {}
    for item_id, is_available, created_at, channel, weight in rows:
        yes, no, timeline = consensus.get(item_id, (0.0, 0.0, []))
        contribution = math.sqrt(weight * _channel_coef(channel, is_available))
        if is_available:
            yes += contribution
        else:
            no += contribution
        timeline.append((created_at, is_available))
        consensus[item_id] = (yes, no, timeline)
    return consensus


def _judge_report(db: Session, report: Report, now: datetime) -> ReportVerdict:
    consensus = _consensus_votes(db, report)
    ratio = settings.flip_ratio

    confirmed = refuted = neutral = 0
    pioneer = False
    for item in report.items:
        yes, no, timeline = consensus.get(item.promotion_item_id, (0.0, 0.0, []))
        total = yes + no
        if total < settings.consensus_min_mass:
            neutral += 1
            continue
        if yes >= ratio * no:
            consensus_value = True
        elif no >= ratio * yes:
            consensus_value = False
        else:
            neutral += 1  # консенсус не сложился — без вердикта
            continue

        if item.is_available == consensus_value:
            confirmed += 1
            # Первопроходец: до него в окне никто того же не говорил,
            # а противоположные голоса были
            before = [t for t in timeline if t[0] < report.created_at]
            if before and all(v != item.is_available for _, v in before):
                pioneer = True
        else:
            refuted += 1

    if refuted > 0:
        outcome = VerdictOutcome.refuted
    elif confirmed > 0:
        outcome = VerdictOutcome.confirmed
    else:
        outcome = VerdictOutcome.neutral

    verdict = ReportVerdict(
        report_id=report.id,
        user_id=report.user_id,
        verdict=outcome,
        is_pioneer=pioneer and outcome == VerdictOutcome.confirmed,
        confirmed_items=confirmed,
        refuted_items=refuted,
        neutral_items=neutral,
        matured_at=now,
    )
    db.add(verdict)

    # --- вес (скрытый) ---
    user = report.user
    if outcome == VerdictOutcome.confirmed:
        bonus = (
            settings.weight_pioneer_bonus
            if verdict.is_pioneer
            else settings.weight_confirm_bonus
        )
        user.weight = min(settings.weight_max, user.weight + bonus)
    elif outcome == VerdictOutcome.refuted:
        user.weight = max(settings.weight_min, user.weight * settings.weight_refute_factor)

    # --- рейтинг (публичный) ---
    city = report.restaurant.city if report.restaurant else None
    if outcome == VerdictOutcome.confirmed:
        if verdict.is_pioneer:
            event = ("pioneer", settings.rating_pioneer_points)
        else:
            event = ("report_confirmed", settings.rating_confirmed_points)
    elif outcome == VerdictOutcome.refuted:
        event = ("report_refuted", settings.rating_refuted_points)
    else:
        event = None
    if event is not None:
        db.add(
            RatingEvent(
                user_id=report.user_id,
                city=city,
                type=event[0],
                points=event[1],
                report_id=report.id,
            )
        )
    return verdict


def mature_verdicts(db: Session, now: datetime | None = None, limit: int = 500) -> int:
    """Вынести вердикты отчётам, дозревшим verdict_mature_hours назад."""
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=settings.verdict_mature_hours)
    reports = (
        db.scalars(
            select(Report)
            .options(
                selectinload(Report.items),
                joinedload(Report.user),
                joinedload(Report.restaurant),
            )
            .where(
                Report.created_at <= cutoff,
                ~exists().where(ReportVerdict.report_id == Report.id),
            )
            .order_by(Report.created_at)
            .limit(limit)
        )
        .unique()
        .all()
    )
    for report in reports:
        _judge_report(db, report, now)
    db.commit()
    return len(reports)


def drift_weights(db: Session, now: datetime | None = None) -> int:
    """Дрейф весов к 1.0 у неактивных (нет отчётов 30 дней), раз в сутки."""
    now = now or datetime.now(timezone.utc)
    day_ago = now - timedelta(days=1)
    month_ago = now - timedelta(days=30)
    users = db.scalars(
        select(User).where(
            User.weight != 1.0,
            (User.weight_drifted_at.is_(None)) | (User.weight_drifted_at <= day_ago),
            ~exists().where(
                (Report.user_id == User.id) & (Report.created_at >= month_ago)
            ),
        )
    ).all()
    daily = settings.weight_drift_monthly / 30.0
    for user in users:
        user.weight += (1.0 - user.weight) * daily
        if abs(user.weight - 1.0) < 0.001:
            user.weight = 1.0
        user.weight_drifted_at = now
    db.commit()
    return len(users)


def refresh_recent_stables(db: Session, now: datetime | None = None) -> int:
    """Обновить устойчивые статусы пар с недавней активностью.

    Джоба — единственное место, где дозревает выдержка уведомления: поток
    отчётов обрывается в тот же момент, когда товар кончился, и без тика
    подписчики не узнали бы об этом никогда.
    """
    now = now or datetime.now(timezone.utc)
    since = now - timedelta(hours=settings.status_window_hours * 2)
    pairs = db.execute(
        select(Report.restaurant_id, Report.promotion_id)
        .where(Report.created_at >= since)
        .distinct()
    ).all()
    by_restaurant: dict[int, list[int]] = {}
    for restaurant_id, promotion_id in pairs:
        by_restaurant.setdefault(restaurant_id, []).append(promotion_id)

    ripe: dict[int, list[tuple[int, str]]] = {}
    for restaurant_id, promotion_ids in by_restaurant.items():
        flips = refresh_stable_statuses(db, restaurant_id, promotion_ids, now)
        if flips:
            ripe[restaurant_id] = [(item_id, new) for item_id, _, new in flips]
    db.commit()

    for restaurant_id, items in ripe.items():
        _notify_flips(db, restaurant_id, items)
    return len(pairs)


def _notify_flips(db: Session, restaurant_id: int, items: list[tuple[int, str]]) -> None:
    """Развести дозревшие переключения по акциям и разослать подписчикам."""
    restaurant = db.scalar(
        select(Restaurant)
        .options(joinedload(Restaurant.brand))
        .where(Restaurant.id == restaurant_id)
    )
    if restaurant is None:
        return
    promotions = (
        db.scalars(
            select(Promotion)
            .options(joinedload(Promotion.brand), selectinload(Promotion.items))
            .join(PromotionItem, PromotionItem.promotion_id == Promotion.id)
            .where(PromotionItem.id.in_([item_id for item_id, _ in items]))
            .distinct()
        )
        .unique()
        .all()
    )
    status_of = dict(items)
    for promotion in promotions:
        lines = [
            (item.name, status_of[item.id])
            for item in promotion.items
            if item.id in status_of
        ]
        if lines:
            notify_status_flips(db, restaurant, promotion, lines)


def run_trust_pass(db: Session, now: datetime | None = None) -> dict:
    matured = mature_verdicts(db, now)
    drifted = drift_weights(db, now)
    refreshed = refresh_recent_stables(db, now)
    return {"matured": matured, "drifted": drifted, "refreshed_pairs": refreshed}


if __name__ == "__main__":
    from app.database import SessionLocal

    session = SessionLocal()
    try:
        print(run_trust_pass(session))
    finally:
        session.close()
