"""API игрового режима: включение, выбор стороны, табло точек, сезон."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import get_current_user, get_current_user_optional, require_not_blocked
from app.config import settings
from app.database import get_db
from app.models import Faction, FactionStanding, PointControl, Restaurant, User
from app.schemas import (
    FactionInfoOut,
    FactionJoinIn,
    FactionStandingOut,
    GameConfigOut,
    GameMeOut,
    GameModeIn,
    GameStandingsOut,
    PointControlDetailOut,
    PointControlOut,
    UserOut,
)
from app.services import game

router = APIRouter(prefix="/game", tags=["game"])


def _point_out(view: game.PointView) -> PointControlOut:
    return PointControlOut(
        restaurant_id=view.restaurant_id,
        owner=view.owner,
        green_score=round(view.green_score, 2),
        purple_score=round(view.purple_score, 2),
        green_receipts=view.green_receipts,
        purple_receipts=view.purple_receipts,
        green_progress=round(view.green_progress, 4),
        purple_progress=round(view.purple_progress, 4),
        leader=view.leader,
        under_attack=view.under_attack,
        eta_seconds=None if view.eta_seconds is None else round(view.eta_seconds),
        is_active_now=view.is_active_now,
        truce_seconds=None if view.truce_seconds is None else round(view.truce_seconds),
        captured_at=view.captured_at,
    )


def _factions_info(db: Session, city: str | None) -> list[FactionInfoOut]:
    counts = game.faction_balance(db, city) if city else {f: 0 for f in Faction}
    total = sum(counts.values())
    return [
        FactionInfoOut(
            key=faction,
            title=game.FACTION_TITLES[faction],
            members=counts.get(faction, 0),
            share=round(counts.get(faction, 0) / total, 4) if total else 0.0,
            join_blocked=bool(city) and game.join_blocked(counts, faction),
            underdog_bonus=round(game.underdog_bonus(counts, faction), 4),
        )
        for faction in Faction
    ]


@router.get("/config", response_model=GameConfigOut)
def game_config(
    city: str | None = None,
    user: User | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """Состояние режима: баланс сторон в городе и что выбрал сам пользователь."""
    now = datetime.now(timezone.utc)
    me = None
    if user is not None:
        can_switch_at = None
        if user.faction_joined_at is not None:
            can_switch_at = user.faction_joined_at + timedelta(
                days=settings.faction_switch_days
            )
        me = GameMeOut(
            game_mode=user.game_mode,
            asked=user.game_asked_at is not None,
            faction=user.faction,
            can_switch_at=can_switch_at,
        )
        city = city or user.city
    return GameConfigOut(
        enabled=settings.game_enabled,
        city=city,
        season=game.season_of(now),
        factions=_factions_info(db, city),
        me=me,
        bar_seconds=settings.capture_bar_seconds,
        min_sum_rubles=settings.receipt_min_sum_kopeks // 100,
        receipt_max_age_minutes=settings.receipt_max_age_minutes,
        geo_radius_m=settings.capture_geo_radius_m,
    )


@router.post("/mode", response_model=UserOut)
def set_game_mode(
    payload: GameModeIn,
    user: User = Depends(require_not_blocked),
    db: Session = Depends(get_db),
):
    """Включить или выключить игровой режим. Выключенный — сервис как раньше."""
    if payload.enabled and not settings.game_enabled:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="Игровой режим сейчас выключен"
        )
    user.game_mode = payload.enabled
    user.game_asked_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)
    return user


@router.post("/faction", response_model=UserOut)
def join_faction(
    payload: FactionJoinIn,
    user: User = Depends(require_not_blocked),
    db: Session = Depends(get_db),
):
    """Выбрать сторону. Набор в перекошенную фракцию закрыт, смена — раз в месяц."""
    if not settings.game_enabled:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="Игровой режим сейчас выключен"
        )
    now = datetime.now(timezone.utc)
    if user.faction == payload.faction:
        return user

    if user.faction is not None:
        cooldown = timedelta(days=settings.faction_switch_days)
        if user.faction_joined_at is not None and now - user.faction_joined_at < cooldown:
            until = user.faction_joined_at + cooldown
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    "Сторону можно менять раз в "
                    f"{settings.faction_switch_days} дней — "
                    f"следующий раз после {until.strftime('%d.%m.%Y')}"
                ),
            )

    counts = game.faction_balance(db, user.city) if user.city else {f: 0 for f in Faction}
    if game.join_blocked(counts, payload.faction):
        title = game.FACTION_TITLES[payload.faction]
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=(
                f"{title} сейчас в большинстве — набор закрыт, "
                "пока стороны не выровняются"
            ),
        )

    user.faction = payload.faction
    user.faction_joined_at = now
    user.game_mode = True
    user.game_asked_at = user.game_asked_at or now
    db.commit()
    db.refresh(user)
    return user


@router.get("/points", response_model=list[PointControlOut])
def city_points(city: str, db: Session = Depends(get_db)):
    """Табло всех точек города: владение, шкалы, таймеры.

    Чтение ничего не пишет: состояние проецируется на текущий момент, а
    фиксирует его фоновая джоба.
    """
    if not settings.game_enabled:
        return []
    return [_point_out(view) for view in game.city_points(db, city)]


def _detail_of(db: Session, restaurant_id: int) -> PointControlDetailOut:
    """Состояние точки на текущий момент, без записи."""
    restaurant = db.get(Restaurant, restaurant_id)
    if restaurant is None or not restaurant.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Точка не найдена")
    now = datetime.now(timezone.utc)
    control = db.get(PointControl, restaurant_id) or game.blank_control(
        restaurant_id, now
    )
    view = game.project(control, restaurant, now)
    return PointControlDetailOut(**_point_out(view).model_dump())


@router.get("/points/{restaurant_id}", response_model=PointControlDetailOut)
def point_detail(restaurant_id: int, db: Session = Depends(get_db)):
    return _detail_of(db, restaurant_id)


@router.get("/points/{restaurant_id}/me", response_model=PointControlDetailOut)
def my_point_detail(
    restaurant_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """То же плюс собственный вклад за сутки."""
    detail = _detail_of(db, restaurant_id)
    receipts, strength = game.contribution(db, restaurant_id, user.id)
    detail.my_receipts_today = receipts
    detail.my_strength_today = round(strength, 2)
    detail.my_faction = user.faction
    return detail


@router.get("/standings", response_model=GameStandingsOut)
def standings(city: str, db: Session = Depends(get_db)):
    """Сезонный зачёт города: средняя доля удержанных точек."""
    now = datetime.now(timezone.utc)
    season = game.season_of(now)

    points_total = db.scalar(
        select(func.count(Restaurant.id)).where(
            Restaurant.city == city, Restaurant.is_active.is_(True)
        )
    ) or 0
    owned = dict(
        db.execute(
            select(PointControl.owner_faction, func.count(PointControl.restaurant_id))
            .join(Restaurant, Restaurant.id == PointControl.restaurant_id)
            .where(
                Restaurant.city == city,
                Restaurant.is_active.is_(True),
                PointControl.owner_faction.is_not(None),
            )
            .group_by(PointControl.owner_faction)
        ).all()
    )
    rows = db.scalars(
        select(FactionStanding).where(
            FactionStanding.city == city, FactionStanding.season == season
        )
    ).all()
    by_faction = {row.faction: row for row in rows}

    elapsed = max((now - game.season_start(now)).total_seconds(), 1.0)
    denominator = elapsed * max(points_total, 1)

    entries = []
    for faction in Faction:
        row = by_faction.get(faction)
        entries.append(
            FactionStandingOut(
                faction=faction,
                title=game.FACTION_TITLES[faction],
                points_held=owned.get(faction, 0),
                held_share=round(min(row.held_seconds / denominator, 1.0), 4) if row else 0.0,
                captures=row.captures if row else 0,
                defends=row.defends if row else 0,
            )
        )
    return GameStandingsOut(
        city=city,
        season=season,
        points_total=points_total,
        neutral=points_total - sum(owned.values()),
        standings=entries,
    )
