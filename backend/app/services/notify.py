"""Уведомления телеграм-бота по подпискам.

- подписка на точку: новые акции её сети;
- подписка на акцию: изменения акции и переключения статусов товаров.

Сообщения собираются в запросе, отправляются пачкой в фоновом потоке.
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.models import (
    Faction,
    PointControl,
    Promotion,
    Receipt,
    Restaurant,
    Subscription,
    User,
)
from app.telegram import send_batch_async

logger = logging.getLogger("promohunter.notify")

STATUS_RU = {
    "available": "✅ Есть",
    "unavailable": "❌ Кончилось",
}

# Кого считаем защитниками точки: кто приносил сюда чеки в последние две недели
DEFENDER_WINDOW_DAYS = 14


def _restaurant_label(restaurant: Restaurant) -> str:
    name = restaurant.title or restaurant.brand.name
    return f"{name}, {restaurant.address}"


def _brand_restaurant_subscribers(db: Session, brand_id: int) -> dict[int, list[Restaurant]]:
    """chat_id -> точки этой сети, на которые подписан пользователь."""
    rows = db.execute(
        select(User.telegram_id, Restaurant)
        .join(Subscription, Subscription.user_id == User.id)
        .join(Restaurant, Restaurant.id == Subscription.restaurant_id)
        .options(joinedload(Restaurant.brand))
        .where(
            Restaurant.brand_id == brand_id,
            User.telegram_id.is_not(None),
            User.is_blocked.is_(False),
        )
    ).unique().all()
    result: dict[int, list[Restaurant]] = {}
    for chat_id, restaurant in rows:
        result.setdefault(chat_id, []).append(restaurant)
    return result


def _promotion_subscriber_chats(db: Session, promotion_id: int) -> list[int]:
    return list(
        db.scalars(
            select(User.telegram_id)
            .join(Subscription, Subscription.user_id == User.id)
            .where(
                Subscription.promotion_id == promotion_id,
                User.telegram_id.is_not(None),
                User.is_blocked.is_(False),
            )
        )
    )


def notify_new_promotion(db: Session, promotion: Promotion) -> None:
    """Новая акция сети → подписчикам её точек."""
    subscribers = _brand_restaurant_subscribers(db, promotion.brand_id)
    if not subscribers:
        return
    items = ", ".join(item.name for item in promotion.items[:5])
    messages = []
    for chat_id, restaurants in subscribers.items():
        places = "\n".join(f"📍 {_restaurant_label(r)}" for r in restaurants[:5])
        messages.append(
            (
                chat_id,
                f"🎉 Новая акция в сети «{promotion.brand.name}»:\n"
                f"<b>{promotion.title}</b>\nТовары: {items}\n\n"
                f"Действует и в точках из вашей подписки:\n{places}",
            )
        )
    send_batch_async(messages)


def notify_promotion_update(db: Session, promotion: Promotion, what: str) -> None:
    """Изменение акции → её подписчикам. what — человекочитаемое описание."""
    chats = _promotion_subscriber_chats(db, promotion.id)
    if not chats:
        return
    text = f"ℹ️ Акция «{promotion.title}» ({promotion.brand.name}): {what}"
    send_batch_async([(chat_id, text) for chat_id in chats])


def notify_promotion_deleted(chats: list[int], title: str, brand_name: str) -> None:
    """Акция удалена (список чатов собирается до каскадного удаления подписок)."""
    text = f"🏁 Акция «{title}» ({brand_name}) завершена и убрана из сервиса"
    send_batch_async([(chat_id, text) for chat_id in chats])


def notify_status_flips(
    db: Session,
    restaurant: Restaurant,
    promotion: Promotion,
    flips: list[tuple[str, str]],
) -> None:
    """Переключения устойчивых статусов товаров → подписчикам акции.

    flips: [(название товара, новый статус available|unavailable), ...]
    """
    lines = [
        f"{STATUS_RU[new_status]} — {name}"
        for name, new_status in flips
        if new_status in STATUS_RU
    ]
    if not lines:
        return
    chats = _promotion_subscriber_chats(db, promotion.id)
    if not chats:
        return
    text = (
        f"🔔 «{promotion.title}» — {_restaurant_label(restaurant)}:\n"
        + "\n".join(lines)
    )
    send_batch_async([(chat_id, text) for chat_id in chats])


# --- игровой режим ---

FACTION_EMOJI = {Faction.green: "🟢", Faction.purple: "🟣"}


def _faction_chats(
    db: Session, restaurant_id: int, faction: Faction, since: datetime
) -> list[int]:
    """Чаты тех, кто приносил на эту точку чеки за свою сторону."""
    return list(
        db.scalars(
            select(func.distinct(User.telegram_id))
            .join(Receipt, Receipt.user_id == User.id)
            .where(
                Receipt.restaurant_id == restaurant_id,
                Receipt.faction == faction,
                Receipt.created_at >= since,
                User.telegram_id.is_not(None),
                User.is_blocked.is_(False),
                User.game_mode.is_(True),
                User.faction == faction,
            )
        )
    )


def notify_capture(
    db: Session, restaurant: Restaurant, captured: bool, defended: bool
) -> None:
    """Итог битвы — обеим сторонам, которые за эту точку воевали."""
    if not (captured or defended):
        return
    control = db.get(PointControl, restaurant.id)
    if control is None or control.owner_faction is None:
        return
    owner = control.owner_faction
    rival = Faction.purple if owner == Faction.green else Faction.green
    since = datetime.now(timezone.utc) - timedelta(days=DEFENDER_WINDOW_DAYS)
    label = _restaurant_label(restaurant)
    emoji = FACTION_EMOJI[owner]

    messages: list[tuple[int, str]] = []
    if captured:
        for chat_id in _faction_chats(db, restaurant.id, owner, since):
            messages.append((chat_id, f"{emoji} Точка взята: {label}"))
        for chat_id in _faction_chats(db, restaurant.id, rival, since):
            messages.append(
                (chat_id, f"💔 Точку у вас забрали: {label}\nМожно отбить — нужны чеки")
            )
    else:
        for chat_id in _faction_chats(db, restaurant.id, owner, since):
            messages.append((chat_id, f"🛡 Атака отбита, точка осталась за вами: {label}"))
    if messages:
        send_batch_async(messages)


def notify_under_attack(
    db: Session,
    restaurant: Restaurant,
    owner: Faction,
    eta_text: str,
    is_final: bool,
) -> None:
    """Владеющей стороне: точку захватывают, нужно перебить чеки."""
    since = datetime.now(timezone.utc) - timedelta(days=DEFENDER_WINDOW_DAYS)
    chats = _faction_chats(db, restaurant.id, owner, since)
    if not chats:
        return
    label = _restaurant_label(restaurant)
    if is_final:
        text = (
            f"⏳ Последний рубеж: {label}\n"
            f"До перехода точки ~{eta_text}. Нужны чеки, иначе потеряем."
        )
    else:
        text = (
            f"⚔️ Вашу точку захватывают: {label}\n"
            f"У противника перевес, до захвата ~{eta_text}. "
            "Перебейте количество чеков, чтобы шкала пошла в вашу сторону."
        )
    send_batch_async([(chat_id, text) for chat_id in chats])


def sweep_attack_notifications(db: Session, now: datetime | None = None) -> int:
    """Разослать предупреждения по всем точкам под атакой (фоновая джоба).

    Кулдаун держит частоту в разумных рамках, а отдельное финальное
    предупреждение уходит один раз за битву.
    """
    from app.services import game

    now = now or datetime.now(timezone.utc)
    sent = 0
    controls = (
        db.scalars(
            select(PointControl)
            .options(joinedload(PointControl.restaurant).joinedload(Restaurant.brand))
            .where(
                PointControl.battle_started_at.is_not(None),
                PointControl.owner_faction.is_not(None),
            )
        )
        .unique()
        .all()
    )
    cooldown = timedelta(hours=settings.capture_attack_notify_cooldown_hours)
    warning = timedelta(minutes=settings.capture_attack_warning_minutes)

    for control in controls:
        restaurant = control.restaurant
        if restaurant is None:
            continue
        view = game.project(control, restaurant, now)
        # Шкала идёт в пользу владельца — тревожить некого
        if not view.under_attack or view.leader == control.owner_faction:
            continue
        if view.eta_seconds is None:
            continue

        eta_text = game.format_eta(view.eta_seconds)
        is_final = view.eta_seconds <= warning.total_seconds()
        if is_final:
            if control.warning_notified_at is not None:
                continue
            control.warning_notified_at = now
        else:
            last = control.attack_notified_at
            if last is not None and now - last < cooldown:
                continue
            control.attack_notified_at = now

        notify_under_attack(
            db, restaurant, control.owner_faction, eta_text, is_final
        )
        sent += 1
    db.commit()
    return sent
