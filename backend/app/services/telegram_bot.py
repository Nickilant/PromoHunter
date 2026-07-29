"""Бот: подтверждение номера телефона.

Пользователь регистрируется на сайте -> идёт к боту -> жмёт «Подтвердить
номер» (кнопка отправки контакта) -> контакт приходит от Telegram с
user_id владельца -> номер сверяется с аккаунтом -> is_phone_verified=True
и привязка telegram_id (включаются и уведомления по подпискам).

Поллинг запускается фоновым потоком (app.main) под advisory-lock —
при нескольких воркерах обновления читает только один.
"""

import logging
import time

from sqlalchemy import func, select

from app.database import SessionLocal
from app.models import User
from app.phone import normalize_phone
from app.telegram import enabled, get_updates, send_message

logger = logging.getLogger("promohunter.telegram-bot")

_POLL_LOCK_KEY = 0x50524F42  # "PROB" — отдельный ключ, не как у trust-джобы

CONTACT_KEYBOARD = {
    "keyboard": [[{"text": "📱 Подтвердить номер", "request_contact": True}]],
    "resize_keyboard": True,
    "one_time_keyboard": True,
}
REMOVE_KEYBOARD = {"remove_keyboard": True}

WELCOME = (
    "Привет! Это бот PromoHunter.\n\n"
    "Чтобы подтвердить номер телефона из вашего аккаунта, нажмите кнопку "
    "«📱 Подтвердить номер» ниже и разрешите отправку контакта.\n\n"
    "Открыть само приложение можно кнопкой меню рядом с полем ввода."
)
HINT = (
    "Я умею только подтверждать номер телефона и присылать уведомления "
    "по подпискам. Нажмите /start, чтобы появилась кнопка подтверждения."
)


def _handle_contact(db, chat_id: int, from_id: int, contact: dict) -> None:
    if contact.get("user_id") != from_id:
        send_message(
            chat_id,
            "Это чужой контакт. Отправьте свой — кнопкой «📱 Подтвердить номер».",
        )
        return
    phone = normalize_phone(str(contact.get("phone_number", "")))
    if phone is None:
        send_message(chat_id, "Не удалось распознать номер телефона.")
        return

    user = db.scalar(select(User).where(User.phone == phone))
    if user is None:
        send_message(
            chat_id,
            f"Аккаунт с номером {phone} не найден. Зарегистрируйтесь на сайте "
            "с этим номером — или откройте приложение кнопкой меню, вход "
            "через Telegram создаст аккаунт автоматически.",
            reply_markup=REMOVE_KEYBOARD,
        )
        return

    conflict = db.scalar(
        select(User).where(User.telegram_id == from_id, User.id != user.id)
    )
    if conflict is not None:
        send_message(
            chat_id,
            "Этот Telegram уже привязан к другому аккаунту PromoHunter.",
            reply_markup=REMOVE_KEYBOARD,
        )
        return

    user.is_phone_verified = True
    user.telegram_id = from_id
    db.commit()
    send_message(
        chat_id,
        "✅ Номер подтверждён! Теперь вашим отчётам больше доверия, "
        "а уведомления по подпискам будут приходить сюда.",
        reply_markup=REMOVE_KEYBOARD,
    )


def handle_update(db, update: dict) -> None:
    message = update.get("message") or {}
    chat_id = (message.get("chat") or {}).get("id")
    from_id = (message.get("from") or {}).get("id")
    if chat_id is None or from_id is None:
        return

    contact = message.get("contact")
    if contact:
        _handle_contact(db, chat_id, from_id, contact)
        return

    text = (message.get("text") or "").strip()
    if text.startswith("/start"):
        send_message(chat_id, WELCOME, reply_markup=CONTACT_KEYBOARD)
    elif text:
        send_message(chat_id, HINT)


def poll_forever() -> None:
    """Цикл getUpdates; работает только в одном процессе (advisory-lock)."""
    while True:
        db = SessionLocal()
        try:
            locked = db.execute(
                select(func.pg_try_advisory_lock(_POLL_LOCK_KEY))
            ).scalar()
            db.commit()
            if not locked:
                db.close()
                time.sleep(30)  # лок держит другой воркер; ждём на подхвате
                continue
            logger.info("telegram polling started")
            offset: int | None = None
            while True:
                updates = get_updates(offset)
                for update in updates:
                    offset = update["update_id"] + 1
                    try:
                        handle_update(db, update)
                    except Exception:
                        logger.exception("failed to handle update %s", update.get("update_id"))
                        db.rollback()
        except Exception:
            logger.exception("telegram polling crashed, restarting soon")
            time.sleep(10)
        finally:
            db.close()


def start_polling_thread() -> None:
    import threading

    from app.config import settings

    if not enabled() or not settings.telegram_polling_enabled:
        return
    threading.Thread(target=poll_forever, daemon=True, name="tg-poll").start()
