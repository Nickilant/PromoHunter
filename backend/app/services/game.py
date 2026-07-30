"""Игровой режим: борьба двух фракций за точки.

Спека: docs/game-mode-spec.md.

Коротко о механике:

* Силу фракции на точке даёт только чек (см. services/receipt.py) — соврать
  «есть» физически не получится, а врать «нет» бессмысленно: на захват это
  не влияет.
* Сила обеих сторон тает экспоненциально с одинаковым полураспадом. Поэтому
  владение отражает не накопленную историю, а то, кто активен сейчас, —
  и точка с тысячей чеков в день не становится вечной собственностью.
* Захват — как захват базы в World of Tanks: у обеих сторон своя шкала,
  едет шкала лидера, шкала отстающего стоит на паузе и подтаивает. Чья шкала
  заполнилась первой, та и решила исход: атакующая берёт точку, владеющая
  отбивает атаку и получает перемирие.
* Чем больше перевес, тем быстрее едет шкала: от 4 часов при равенстве до
  1 ч 40 мин при перевесе вчетверо.
* Вне часов работы точки (они выводятся из времён её же чеков) шкалы стоят —
  ночью точку не захватить.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.models import (
    CaptureEvent,
    Faction,
    FactionStanding,
    PointControl,
    RatingEvent,
    Receipt,
    Report,
    ReportItem,
    ReportVerdict,
    Restaurant,
    User,
    VerdictOutcome,
)
from app.services.receipt import (
    ParsedReceipt,
    ReceiptError,
    check_freshness,
    check_geo,
    check_sum,
    receipt_moment,
    register_receipt,
)

logger = logging.getLogger("promohunter.game")

OTHER = {Faction.green: Faction.purple, Faction.purple: Faction.green}
FACTION_TITLES = {Faction.green: "Зелёные", Faction.purple: "Фиолетовые"}
# Дольше этого окна шкалы всё равно давно пусты — не крутим лишние итерации
_MAX_CATCHUP = timedelta(days=40)


def season_of(moment: datetime) -> str:
    return moment.strftime("%Y-%m")


def season_start(moment: datetime) -> datetime:
    return moment.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


# --- сила фракции ---------------------------------------------------------


def _decay(hours: float) -> float:
    if hours <= 0:
        return 1.0
    return 0.5 ** (hours / settings.capture_half_life_hours)


def scores_at(control: PointControl, now: datetime) -> tuple[float, float]:
    """Силы сторон, приведённые к моменту now."""
    hours = max((now - control.score_at).total_seconds() / 3600.0, 0.0)
    factor = _decay(hours)
    return control.green_score * factor, control.purple_score * factor


def active_seconds(mask: int, start: datetime, end: datetime) -> float:
    """Секунды между start и end, попавшие в рабочие часы точки.

    mask — 24 бита по часам UTC; 0 означает «данных мало», тогда время идёт
    круглосуточно.
    """
    if end <= start:
        return 0.0
    if mask == 0:
        return (end - start).total_seconds()
    start = max(start, end - _MAX_CATCHUP)
    total = 0.0
    cursor = start
    while cursor < end:
        next_hour = cursor.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        chunk_end = min(next_hour, end)
        if mask & (1 << cursor.hour):
            total += (chunk_end - cursor).total_seconds()
        cursor = chunk_end
    return total


def is_active_now(mask: int, now: datetime) -> bool:
    return mask == 0 or bool(mask & (1 << now.hour))


def bar_speed(leader_score: float, other_score: float) -> float:
    """Множитель скорости шкалы: 1.0 при равенстве, максимум при перевесе.

    Если сопротивления нет (нейтральная точка, вторая сторона пуста), шкала
    идёт базовой скоростью — это те самые 4 часа, за которые другая фракция
    ещё может вмешаться.
    """
    if other_score < settings.capture_min_score:
        return 1.0
    ratio = leader_score / other_score
    lead = max(0.0, min(1.0, (ratio - 1.0) / settings.capture_bar_speed_lead_span))
    return 1.0 + (settings.capture_bar_max_speed - 1.0) * lead


# --- состояние битвы ------------------------------------------------------


@dataclass
class Resolution:
    kind: str  # capture | defend | expired
    faction: Faction | None


@dataclass
class BattleState:
    """Отделяемая копия состояния точки.

    Один и тот же расчёт используется и для записи (advance), и для чтения
    без записи (project) — чтобы табло и фактическое состояние не разъезжались.
    """

    owner: Faction | None
    green_score: float
    purple_score: float
    green_progress: float
    purple_progress: float
    progress_at: datetime
    battle_started_at: datetime | None
    truce_until: datetime | None

    @classmethod
    def load(cls, control: PointControl, now: datetime) -> "BattleState":
        green, purple = scores_at(control, now)
        return cls(
            owner=control.owner_faction,
            green_score=green,
            purple_score=purple,
            green_progress=control.green_progress,
            purple_progress=control.purple_progress,
            progress_at=control.progress_at,
            battle_started_at=control.battle_started_at,
            truce_until=control.truce_until,
        )

    def save(self, control: PointControl, now: datetime) -> None:
        control.owner_faction = self.owner
        control.green_score = self.green_score
        control.purple_score = self.purple_score
        control.score_at = now
        control.green_progress = self.green_progress
        control.purple_progress = self.purple_progress
        control.progress_at = self.progress_at
        control.battle_started_at = self.battle_started_at
        control.truce_until = self.truce_until

    def score(self, faction: Faction) -> float:
        return self.green_score if faction == Faction.green else self.purple_score

    def progress(self, faction: Faction) -> float:
        return self.green_progress if faction == Faction.green else self.purple_progress

    def set_progress(self, faction: Faction, value: float) -> None:
        if faction == Faction.green:
            self.green_progress = value
        else:
            self.purple_progress = value

    def leader(self) -> Faction | None:
        floor = settings.capture_min_score
        if self.green_score < floor and self.purple_score < floor:
            return None
        if abs(self.green_score - self.purple_score) < 1e-9:
            return None
        return Faction.green if self.green_score > self.purple_score else Faction.purple


def _reset_bars(state: BattleState) -> None:
    state.green_progress = 0.0
    state.purple_progress = 0.0
    state.battle_started_at = None


def simulate(state: BattleState, mask: int, now: datetime) -> list[Resolution]:
    """Продвинуть шкалы от state.progress_at до now. Мутирует state.

    Нулевой интервал не выходит сразу: начало битвы — это предикат состояния,
    а не следствие прошедшего времени. Иначе чек, только что переломивший
    перевес, зажигал бы таймер лишь на следующем проходе джобы.
    """
    resolutions: list[Resolution] = []
    if now < state.progress_at:
        return resolutions

    start = state.progress_at
    if state.truce_until is not None:
        if state.truce_until > now:
            state.progress_at = now
            return resolutions
        start = max(start, state.truce_until)
        state.truce_until = None

    state.progress_at = now
    active = active_seconds(mask, start, now)

    leader = state.leader()
    # Силы обеих сторон тают одинаково, значит внутри интервала лидер
    # и перевес постоянны — интеграл считается одним шагом.
    if leader is None or (state.battle_started_at is None and leader == state.owner):
        _decay_paused(state, Faction.green, active)
        _decay_paused(state, Faction.purple, active)
        _expire_stale_battle(state, now, resolutions)
        return resolutions

    if state.battle_started_at is None:
        # Отстающая сторона вышла вперёд — начинается битва за точку
        state.battle_started_at = start
        state.green_progress = 0.0
        state.purple_progress = 0.0

    if active > 0:
        rival = OTHER[leader]
        speed = bar_speed(state.score(leader), state.score(rival))
        state.set_progress(leader, state.progress(leader) + active * speed)
        _decay_paused(state, rival, active)

    bar = float(settings.capture_bar_seconds)
    if state.progress(leader) >= bar:
        if leader == state.owner:
            resolutions.append(Resolution("defend", leader))
            _reset_bars(state)
            state.truce_until = now + timedelta(hours=settings.capture_truce_hours)
        else:
            resolutions.append(Resolution("capture", leader))
            state.owner = leader
            _reset_bars(state)
        return resolutions

    _expire_stale_battle(state, now, resolutions)
    return resolutions


def _decay_paused(state: BattleState, faction: Faction, active: float) -> None:
    value = state.progress(faction)
    if value <= 0 or active <= 0:
        return
    hours = active / 3600.0
    state.set_progress(faction, value * (1.0 - settings.capture_paused_decay_per_hour) ** hours)


def _expire_stale_battle(
    state: BattleState, now: datetime, resolutions: list[Resolution]
) -> None:
    """Битва без исхода не висит вечно: атака выдыхается, шкалы сбрасываются."""
    if state.battle_started_at is None:
        return
    too_long = now - state.battle_started_at > timedelta(
        hours=settings.capture_battle_max_hours
    )
    attacker = OTHER[state.owner] if state.owner else None
    faded = attacker is not None and state.score(attacker) < settings.capture_min_score
    if too_long or faded:
        resolutions.append(Resolution("expired", attacker))
        _reset_bars(state)


# --- продвижение с записью ------------------------------------------------


def blank_control(restaurant_id: int, now: datetime) -> PointControl:
    """Пустое состояние точки, за которую ещё не воевали.

    Значения проставляем руками: server_default появляется только после
    вставки, а объект нужен и в режиме «только посмотреть», без записи.
    """
    return PointControl(
        restaurant_id=restaurant_id,
        green_score=0.0,
        purple_score=0.0,
        score_at=now,
        green_progress=0.0,
        purple_progress=0.0,
        progress_at=now,
        green_receipts=0,
        purple_receipts=0,
    )


def get_control(db: Session, restaurant_id: int, now: datetime) -> PointControl:
    control = db.get(PointControl, restaurant_id)
    if control is None:
        control = blank_control(restaurant_id, now)
        db.add(control)
        db.flush()
    return control


def advance(
    db: Session, control: PointControl, restaurant: Restaurant, now: datetime
) -> list[Resolution]:
    """Продвинуть точку до now, записать исходы в журнал и сезонный зачёт."""
    state = BattleState.load(control, now)
    resolutions = simulate(state, restaurant.active_hours_mask, now)
    state.save(control, now)

    for resolution in resolutions:
        if resolution.kind == "expired" or resolution.faction is None:
            control.attack_notified_at = None
            control.warning_notified_at = None
            continue
        if resolution.kind == "capture":
            control.captured_at = now
        control.attack_notified_at = None
        control.warning_notified_at = None
        finisher = _last_contributor(db, restaurant.id, resolution.faction)
        db.add(
            CaptureEvent(
                restaurant_id=restaurant.id,
                city=restaurant.city,
                faction=resolution.faction,
                kind=resolution.kind,
                finisher_user_id=finisher,
                created_at=now,
            )
        )
        _award_battle_points(db, restaurant, resolution, finisher, now)
        _bump_standing(db, restaurant.city, resolution.faction, resolution.kind, now)
    return resolutions


def _last_contributor(db: Session, restaurant_id: int, faction: Faction) -> int | None:
    """Чей чек закрыл шкалу — последний вкладчик победившей стороны."""
    return db.scalar(
        select(Receipt.user_id)
        .where(Receipt.restaurant_id == restaurant_id, Receipt.faction == faction)
        .order_by(Receipt.created_at.desc())
        .limit(1)
    )


def _battle_contributors(
    db: Session, restaurant_id: int, faction: Faction, since: datetime
) -> list[int]:
    return list(
        db.scalars(
            select(func.distinct(Receipt.user_id)).where(
                Receipt.restaurant_id == restaurant_id,
                Receipt.faction == faction,
                Receipt.created_at >= since,
            )
        )
    )


def _award_battle_points(
    db: Session,
    restaurant: Restaurant,
    resolution: Resolution,
    finisher: int | None,
    now: datetime,
) -> None:
    """Очки за взятие/оборону: всем вкладчикам победившей стороны, добившему — больше.

    Делить фиксированный пул между вкладчиками нельзя: на людной точке
    доля выродится в ноль, поэтому платим каждому.
    """
    faction = resolution.faction
    if faction is None:
        return
    since = now - timedelta(hours=settings.capture_battle_max_hours)
    contributors = _battle_contributors(db, restaurant.id, faction, since)
    if not contributors:
        return
    event_type = "capture_win" if resolution.kind == "capture" else "capture_defend"
    for user_id in contributors:
        points = settings.rating_capture_win_points
        if user_id == finisher:
            points += settings.rating_capture_finisher_points
        db.add(
            RatingEvent(
                user_id=user_id,
                city=restaurant.city,
                type=event_type,
                points=points,
                created_at=now,
            )
        )


def _bump_standing(
    db: Session, city: str, faction: Faction, kind: str, now: datetime
) -> None:
    standing = _get_standing(db, city, season_of(now), faction, now)
    if kind == "capture":
        standing.captures += 1
    elif kind == "defend":
        standing.defends += 1


def _get_standing(
    db: Session, city: str, season: str, faction: Faction, now: datetime
) -> FactionStanding:
    standing = db.scalar(
        select(FactionStanding).where(
            FactionStanding.city == city,
            FactionStanding.season == season,
            FactionStanding.faction == faction,
        )
    )
    if standing is None:
        standing = FactionStanding(
            city=city, season=season, faction=faction, updated_at=now
        )
        db.add(standing)
        db.flush()
    return standing


# --- приём чека -----------------------------------------------------------


def daily_factor(index: int) -> float:
    """Убывающая отдача: n-й чек пользователя на этой точке за сутки."""
    table = settings.capture_daily_returns or [1.0]
    return table[index] if index < len(table) else table[-1]


def underdog_bonus(counts: dict[Faction, int], faction: Faction) -> float:
    """Прибавка к силе чека за игру в меньшинстве: 0 при равенстве, максимум
    при полном перекосе. Единственное место, где живёт эта формула."""
    total = sum(counts.values())
    if total == 0:
        return 0.0
    share = counts.get(faction, 0) / total
    behind = max(0.0, min(1.0, (0.5 - share) / 0.5))
    return settings.capture_underdog_max_bonus * behind


def underdog_coef(db: Session, city: str, faction: Faction) -> float:
    """Коэффициент слабейшей стороны города — чтобы перекос не убивал игру."""
    return 1.0 + underdog_bonus(faction_balance(db, city), faction)


def faction_balance(db: Session, city: str) -> dict[Faction, int]:
    rows = db.execute(
        select(User.faction, func.count(User.id))
        .where(
            User.city == city,
            User.faction.is_not(None),
            User.is_blocked.is_(False),
        )
        .group_by(User.faction)
    ).all()
    counts = {faction: 0 for faction in Faction}
    for faction, count in rows:
        counts[faction] = count
    return counts


def join_blocked(counts: dict[Faction, int], faction: Faction) -> bool:
    """Набор в перекошенную сторону закрыт, пока она не выровняется."""
    total = sum(counts.values())
    if total < 10:  # на старте города баланса ещё нет — пускаем всех
        return False
    return counts.get(faction, 0) / total >= settings.faction_join_block_share


@dataclass
class CaptureResult:
    strength: float
    added_points: int
    resolutions: list[Resolution]
    owner: Faction | None
    receipt: Receipt


def apply_receipt(
    db: Session,
    user: User,
    restaurant: Restaurant,
    parsed: ParsedReceipt,
    lat: float | None,
    lng: float | None,
    report: Report | None,
    now: datetime,
) -> CaptureResult:
    """Принять чек: проверки, сила фракции, продвижение шкал, очки."""
    if not settings.game_enabled:
        raise ReceiptError("Игровой режим сейчас выключен")
    if not user.game_mode or user.faction is None:
        raise ReceiptError("Сначала включите игровой режим и выберите сторону")

    check_sum(parsed)
    check_geo(restaurant, lat, lng)
    purchased_at = receipt_moment(parsed, restaurant)
    check_freshness(purchased_at, now)
    register_receipt(db, parsed, restaurant, user.id, purchased_at, now)

    faction = user.faction
    control = get_control(db, restaurant.id, now)
    # Шкалы доводим до now на старых силах, и только потом добавляем чек:
    # иначе новый вклад задним числом переписал бы прошедший интервал.
    resolutions = advance(db, control, restaurant, now)

    day_ago = now - timedelta(hours=24)
    today_count = db.scalar(
        select(func.count(Receipt.id)).where(
            Receipt.user_id == user.id,
            Receipt.restaurant_id == restaurant.id,
            Receipt.created_at >= day_ago,
        )
    ) or 0
    factor = daily_factor(today_count)
    strength = factor * underdog_coef(db, restaurant.city, faction)

    if faction == Faction.green:
        control.green_score += strength
        control.green_receipts += 1
    else:
        control.purple_score += strength
        control.purple_receipts += 1

    receipt = Receipt(
        user_id=user.id,
        restaurant_id=restaurant.id,
        report_id=report.id if report else None,
        fn=parsed.fn,
        doc_number=parsed.doc_number,
        fp=parsed.fp,
        sum_kopeks=parsed.sum_kopeks,
        purchased_at=purchased_at,
        faction=faction,
        strength=strength,
        raw=parsed.raw,
        created_at=now,
    )
    db.add(receipt)

    points = int(round(settings.rating_capture_receipt_points * factor))
    if points > 0:
        db.add(
            RatingEvent(
                user_id=user.id,
                city=restaurant.city,
                type="capture_receipt",
                points=points,
                report_id=report.id if report else None,
                created_at=now,
            )
        )

    # Чек мог сразу перевести лидерство — даём шкалам отреагировать
    resolutions += advance(db, control, restaurant, now)
    return CaptureResult(
        strength=strength,
        added_points=points,
        resolutions=resolutions,
        owner=control.owner_faction,
        receipt=receipt,
    )


def grade_denials_by_receipt(
    db: Session, report: Report, item_ids: list[int], now: datetime
) -> int:
    """Чек с «есть» опровергает свежие «нет» по тем же товарам.

    Штраф весу мягче обычного: человек мог не найти товар честно.
    """
    if not item_ids:
        return 0
    window = now - timedelta(minutes=settings.receipt_refute_window_minutes)
    reports = (
        db.scalars(
            select(Report)
            .options(joinedload(Report.user))
            .join(ReportItem, ReportItem.report_id == Report.id)
            .where(
                Report.restaurant_id == report.restaurant_id,
                Report.promotion_id == report.promotion_id,
                Report.id != report.id,
                Report.user_id != report.user_id,
                Report.created_at >= window,
                Report.is_receipt_verified.is_(False),
                ReportItem.promotion_item_id.in_(item_ids),
                ReportItem.is_available.is_(False),
                ~select(ReportVerdict.id)
                .where(ReportVerdict.report_id == Report.id)
                .exists(),
            )
            .distinct()
        )
        .unique()
        .all()
    )
    for stale in reports:
        db.add(
            ReportVerdict(
                report_id=stale.id,
                user_id=stale.user_id,
                verdict=VerdictOutcome.refuted,
                refuted_items=1,
                matured_at=now,
            )
        )
        stale.user.weight = max(
            settings.weight_min,
            stale.user.weight * settings.weight_receipt_refute_factor,
        )
        db.add(
            RatingEvent(
                user_id=stale.user_id,
                city=report.restaurant.city if report.restaurant else None,
                type="report_refuted",
                points=settings.rating_refuted_points,
                report_id=stale.id,
                created_at=now,
            )
        )
    return len(reports)


# --- фоновое обслуживание -------------------------------------------------


def advance_all(db: Session, now: datetime | None = None) -> int:
    """Продвинуть все точки с живой борьбой (фоновая джоба)."""
    now = now or datetime.now(timezone.utc)
    floor = settings.capture_min_score
    controls = (
        db.scalars(
            select(PointControl)
            .options(joinedload(PointControl.restaurant))
            .where(
                (PointControl.green_score >= floor)
                | (PointControl.purple_score >= floor)
                | (PointControl.battle_started_at.is_not(None))
            )
        )
        .unique()
        .all()
    )
    for control in controls:
        if control.restaurant is None:
            continue
        advance(db, control, control.restaurant, now)
    db.commit()
    return len(controls)


def accrue_standings(db: Session, now: datetime | None = None) -> int:
    """Накопить «точко-секунды» владения в сезонный зачёт городов."""
    now = now or datetime.now(timezone.utc)
    season = season_of(now)
    rows = db.execute(
        select(Restaurant.city, PointControl.owner_faction, func.count(PointControl.restaurant_id))
        .join(Restaurant, Restaurant.id == PointControl.restaurant_id)
        .where(PointControl.owner_faction.is_not(None))
        .group_by(Restaurant.city, PointControl.owner_faction)
    ).all()
    for city, faction, held in rows:
        standing = _get_standing(db, city, season, faction, now)
        elapsed = max((now - standing.updated_at).total_seconds(), 0.0)
        standing.held_seconds += elapsed * held
        standing.updated_at = now
    db.commit()
    return len(rows)


def refresh_active_hours(db: Session, now: datetime | None = None) -> int:
    """Пересчитать рабочие часы точек по временам их же чеков.

    Часы берём в UTC, поэтому таблица часовых поясов не нужна: гистограмма
    сама показывает, когда точка пробивает чеки.
    """
    now = now or datetime.now(timezone.utc)
    since = now - timedelta(days=60)
    rows = db.execute(
        select(
            Receipt.restaurant_id,
            func.extract("hour", Receipt.purchased_at),
            func.count(Receipt.id),
        )
        .where(Receipt.purchased_at >= since)
        .group_by(Receipt.restaurant_id, func.extract("hour", Receipt.purchased_at))
    ).all()

    by_restaurant: dict[int, dict[int, int]] = {}
    for restaurant_id, hour, count in rows:
        by_restaurant.setdefault(restaurant_id, {})[int(hour)] = count

    masks: dict[int, int] = {}
    for restaurant_id, hours in by_restaurant.items():
        if sum(hours.values()) < settings.capture_active_hours_min_receipts:
            continue
        mask = 0
        for hour in hours:
            # Расширяем на соседние часы: край выборки не должен обрезать смену
            for shift in (-1, 0, 1):
                mask |= 1 << ((hour + shift) % 24)
        masks[restaurant_id] = mask

    updated = 0
    if masks:
        # Одним запросом, а не по точке за раз: джоба ходит раз в минуту
        restaurants = db.scalars(
            select(Restaurant).where(Restaurant.id.in_(masks))
        ).all()
        for restaurant in restaurants:
            if restaurant.active_hours_mask != masks[restaurant.id]:
                restaurant.active_hours_mask = masks[restaurant.id]
                updated += 1
    db.commit()
    return updated


def run_game_pass(db: Session, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    advanced = advance_all(db, now)
    standings = accrue_standings(db, now)
    hours = refresh_active_hours(db, now)
    return {"advanced": advanced, "standings": standings, "active_hours": hours}


# --- проекция для табло ---------------------------------------------------


@dataclass
class PointView:
    restaurant_id: int
    owner: Faction | None
    green_score: float
    purple_score: float
    green_receipts: int
    purple_receipts: int
    green_progress: float  # доля 0..1
    purple_progress: float
    leader: Faction | None
    under_attack: bool
    eta_seconds: float | None  # сколько осталось лидеру до конца шкалы
    is_active_now: bool
    truce_seconds: float | None
    captured_at: datetime | None


def project(control: PointControl, restaurant: Restaurant, now: datetime) -> PointView:
    """Показать состояние точки на now, ничего не записывая."""
    state = BattleState.load(control, now)
    simulate(state, restaurant.active_hours_mask, now)

    bar = float(settings.capture_bar_seconds)
    leader = state.leader() if state.battle_started_at is not None else None
    active = is_active_now(restaurant.active_hours_mask, now)
    eta: float | None = None
    if leader is not None and active:
        speed = bar_speed(state.score(leader), state.score(OTHER[leader]))
        eta = max((bar - state.progress(leader)) / speed, 0.0)

    truce = None
    if state.truce_until is not None and state.truce_until > now:
        truce = (state.truce_until - now).total_seconds()

    return PointView(
        restaurant_id=control.restaurant_id,
        owner=state.owner,
        green_score=state.green_score,
        purple_score=state.purple_score,
        green_receipts=control.green_receipts,
        purple_receipts=control.purple_receipts,
        green_progress=min(state.green_progress / bar, 1.0),
        purple_progress=min(state.purple_progress / bar, 1.0),
        leader=leader,
        under_attack=state.battle_started_at is not None
        and state.owner is not None
        and leader is not None,
        eta_seconds=eta,
        is_active_now=active,
        truce_seconds=truce,
        captured_at=control.captured_at,
    )


def city_points(db: Session, city: str, now: datetime | None = None) -> list[PointView]:
    """Табло по всем точкам города, включая те, за которые ещё не воевали.

    Свободные точки тоже нужны на табло: без них в списках и карточках у
    половины адресов не было бы вообще ничего игрового, хотя режим включён.
    """
    now = now or datetime.now(timezone.utc)
    rows = (
        db.execute(
            select(Restaurant, PointControl)
            .outerjoin(PointControl, PointControl.restaurant_id == Restaurant.id)
            .where(Restaurant.city == city, Restaurant.is_active.is_(True))
        )
        .unique()
        .all()
    )
    return [
        project(control or blank_control(restaurant.id, now), restaurant, now)
        for restaurant, control in rows
    ]


def contribution(
    db: Session, restaurant_id: int, user_id: int, now: datetime | None = None
) -> tuple[int, float]:
    """Сколько чеков и силы принёс человек на эту точку за сутки."""
    now = now or datetime.now(timezone.utc)
    row = db.execute(
        select(func.count(Receipt.id), func.coalesce(func.sum(Receipt.strength), 0.0)).where(
            Receipt.restaurant_id == restaurant_id,
            Receipt.user_id == user_id,
            Receipt.created_at >= now - timedelta(hours=24),
        )
    ).one()
    return int(row[0]), float(row[1])


def format_eta(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    total = int(max(seconds, 0))
    hours, rest = divmod(total, 3600)
    minutes = rest // 60
    if hours:
        return f"{hours} ч {minutes:02d} мин"
    return f"{minutes} мин"
