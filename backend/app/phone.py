"""Нормализация номеров телефона к виду +79991234567.

Принимаем любые привычные написания: 8 999 123-45-67, +7 (999) 123 45 67 и т.п.
Проверка номера кодом через Telegram — следующий этап; поле
users.is_phone_verified уже заложено под неё.
"""

import re


def normalize_phone(raw: str) -> str | None:
    """Вернуть номер в виде +XXXXXXXXXXX или None, если это не номер."""
    cleaned = re.sub(r"[^\d+]", "", raw.strip())
    if not cleaned:
        return None
    # российская запись через 8: 8 999 123-45-67 -> +7 999 123-45-67
    if cleaned.startswith("8") and len(cleaned) == 11:
        cleaned = "+7" + cleaned[1:]
    if not cleaned.startswith("+"):
        cleaned = "+" + cleaned
    if not re.fullmatch(r"\+\d{10,15}", cleaned):
        return None
    return cleaned
