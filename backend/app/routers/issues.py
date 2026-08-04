from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.auth import get_current_user, require_not_blocked
from app.database import get_db
from app.models import DataIssue, IssueStatus, Promotion, Restaurant, User
from app.schemas import AdminDataIssueOut, DataIssueIn, DataIssueOut, DataIssueReviewIn
from app.services.scope import Scope, city_filter, require_staff

router = APIRouter(tags=["issues"])

ISSUE_TYPES = {
    "closed",
    "temporarily_closed",
    "wrong_address",
    "wrong_location",
    "duplicate",
    "moved",
    "promotion_ended",
    "promotion_wrong",
    "other",
}


def _load(db: Session, issue_id: int) -> DataIssue | None:
    return db.scalar(
        select(DataIssue)
        .options(
            joinedload(DataIssue.user),
            joinedload(DataIssue.restaurant).joinedload(Restaurant.brand),
            joinedload(DataIssue.promotion),
        )
        .where(DataIssue.id == issue_id)
    )


@router.post("/issues", response_model=DataIssueOut, status_code=status.HTTP_201_CREATED)
def create_issue(
    payload: DataIssueIn,
    user: User = Depends(require_not_blocked),
    db: Session = Depends(get_db),
):
    restaurant = db.get(Restaurant, payload.restaurant_id)
    if restaurant is None or not restaurant.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Точка не найдена")
    if payload.type not in ISSUE_TYPES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Неизвестный тип ошибки")
    if payload.promotion_id is not None:
        promotion = db.get(Promotion, payload.promotion_id)
        if promotion is None or promotion.brand_id != restaurant.brand_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Акция не относится к этой точке")
    duplicate = db.scalar(
        select(DataIssue.id).where(
            DataIssue.user_id == user.id,
            DataIssue.restaurant_id == restaurant.id,
            DataIssue.promotion_id == payload.promotion_id,
            DataIssue.type == payload.type,
            DataIssue.status == IssueStatus.pending,
        )
    )
    if duplicate:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Такое сообщение уже ожидает проверки")
    issue = DataIssue(
        user_id=user.id,
        restaurant_id=restaurant.id,
        promotion_id=payload.promotion_id,
        type=payload.type,
        details=payload.details.strip(),
    )
    db.add(issue)
    db.commit()
    return _load(db, issue.id)


@router.get("/issues/mine", response_model=list[DataIssueOut])
def my_issues(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(
        select(DataIssue)
        .options(joinedload(DataIssue.restaurant).joinedload(Restaurant.brand), joinedload(DataIssue.promotion))
        .where(DataIssue.user_id == user.id)
        .order_by(DataIssue.created_at.desc())
    ).unique().all()


@router.get("/admin/issues", response_model=list[AdminDataIssueOut])
def admin_issues(
    status_filter: IssueStatus | None = Query(default=None, alias="status"),
    scope: Scope = Depends(require_staff),
    db: Session = Depends(get_db),
):
    stmt = select(DataIssue).join(DataIssue.restaurant).options(
        joinedload(DataIssue.user),
        joinedload(DataIssue.restaurant).joinedload(Restaurant.brand),
        joinedload(DataIssue.promotion),
    ).order_by(DataIssue.created_at.desc())
    if status_filter is not None:
        stmt = stmt.where(DataIssue.status == status_filter)
    mine = city_filter(scope, Restaurant.city)
    if mine is not None:
        stmt = stmt.where(mine)
    return db.scalars(stmt).unique().all()


@router.post("/admin/issues/{issue_id}/review", response_model=AdminDataIssueOut)
def review_issue(
    issue_id: int,
    payload: DataIssueReviewIn,
    scope: Scope = Depends(require_staff),
    db: Session = Depends(get_db),
):
    issue = _load(db, issue_id)
    if issue is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Сообщение не найдено")
    if issue.status != IssueStatus.pending:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Сообщение уже рассмотрено")
    if payload.status == IssueStatus.pending:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Выберите итог проверки")
    scope.require(issue.restaurant.city, "Сообщение")
    issue.status = payload.status
    issue.moderator_comment = (payload.moderator_comment or "").strip() or None
    issue.reviewed_at = datetime.now(timezone.utc)
    issue.reviewed_by_id = scope.user.id
    db.commit()
    return _load(db, issue.id)
