"""Агрегация статусов наличия акционных товаров по точкам.

Для пары (ресторан, товар акции):
- берём report_items за окно STATUS_WINDOW_HOURS;
- от каждого пользователя учитываем только его последний отчёт
  по этой паре (ресторан, акция) внутри окна;
- yes > no -> available, no > yes -> unavailable,
  yes == no > 0 -> disputed, нет голосов -> unknown.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Report, ReportItem

AVAILABLE = "available"
UNAVAILABLE = "unavailable"
DISPUTED = "disputed"
UNKNOWN = "unknown"


@dataclass
class ItemStatus:
    status: str = UNKNOWN
    yes_count: int = 0
    no_count: int = 0
    last_report_at: datetime | None = None


@dataclass
class StatusMap:
    """Ключ — promotion_item_id; отсутствие ключа означает unknown."""

    by_item: dict[int, ItemStatus] = field(default_factory=dict)

    def get(self, promotion_item_id: int) -> ItemStatus:
        return self.by_item.get(promotion_item_id) or ItemStatus()


def _resolve(yes: int, no: int) -> str:
    if yes == 0 and no == 0:
        return UNKNOWN
    if yes > no:
        return AVAILABLE
    if no > yes:
        return UNAVAILABLE
    return DISPUTED


def compute_statuses(
    db: Session, restaurant_id: int, promotion_ids: list[int]
) -> StatusMap:
    """Статусы всех товаров указанных акций в одной точке, одним запросом."""
    result = StatusMap()
    if not promotion_ids:
        return result

    window_start = datetime.now(timezone.utc) - timedelta(
        hours=settings.status_window_hours
    )

    # Последний отчёт каждого пользователя по каждой акции внутри окна
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
        select(Report.id, Report.created_at, rn)
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
            func.count().filter(ReportItem.is_available.is_(True)).label("yes"),
            func.count().filter(ReportItem.is_available.is_(False)).label("no"),
            func.max(latest.c.created_at).label("last_report_at"),
        )
        .join(latest, ReportItem.report_id == latest.c.id)
        .where(latest.c.rn == 1)
        .group_by(ReportItem.promotion_item_id)
    ).all()

    for item_id, yes, no, last_report_at in rows:
        result.by_item[item_id] = ItemStatus(
            status=_resolve(yes, no),
            yes_count=yes,
            no_count=no,
            last_report_at=last_report_at,
        )
    return result
