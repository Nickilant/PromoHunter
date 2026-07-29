"""Telegram: проверка подписей WebApp и отправка сообщений ботом.

Вход через WebApp: initData подписана HMAC-SHA256 с ключом
HMAC("WebAppData", bot_token) — та же схема у ответа requestContact.
"""

import hashlib
import hmac
import json
import logging
import threading
from urllib.parse import parse_qsl

import httpx

from app.config import settings

logger = logging.getLogger("promohunter.telegram")

API_BASE = "https://api.telegram.org"


def enabled() -> bool:
    return bool(settings.telegram_bot_token)


def _secret_key() -> bytes:
    return hmac.new(
        b"WebAppData", settings.telegram_bot_token.encode(), hashlib.sha256
    ).digest()


def _validate_signed_fields(raw: str) -> dict[str, str] | None:
    """Общая проверка подписанной querystring Telegram (initData / contact)."""
    if not enabled():
        return None
    fields = dict(parse_qsl(raw, keep_blank_values=True))
    received_hash = fields.pop("hash", None)
    if not received_hash:
        return None
    check_string = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    expected = hmac.new(_secret_key(), check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received_hash):
        return None
    return fields


def validate_init_data(init_data: str) -> dict | None:
    """Вернуть словарь полей initData, если подпись верна."""
    return _validate_signed_fields(init_data)


def webapp_user(fields: dict) -> dict | None:
    try:
        user = json.loads(fields.get("user", ""))
    except (TypeError, ValueError):
        return None
    return user if isinstance(user, dict) and "id" in user else None


def validate_contact(contact_response: str) -> dict | None:
    """Вернуть контакт из ответа requestContact, если подпись верна."""
    fields = _validate_signed_fields(contact_response)
    if fields is None:
        return None
    try:
        contact = json.loads(fields.get("contact", ""))
    except (TypeError, ValueError):
        return None
    return contact if isinstance(contact, dict) else None


def send_message(chat_id: int, text: str) -> bool:
    if not enabled():
        return False
    try:
        resp = httpx.post(
            f"{API_BASE}/bot{settings.telegram_bot_token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            timeout=5,
        )
        if resp.status_code != 200:
            logger.warning("sendMessage %s -> %s %s", chat_id, resp.status_code, resp.text[:200])
        return resp.status_code == 200
    except Exception:
        logger.exception("sendMessage failed for chat %s", chat_id)
        return False


def send_batch_async(messages: list[tuple[int, str]]) -> None:
    """Отправить пачку сообщений в фоне, не блокируя запрос."""
    if not messages or not enabled():
        return

    def _worker() -> None:
        for chat_id, text in messages:
            send_message(chat_id, text)

    threading.Thread(target=_worker, daemon=True, name="tg-notify").start()
