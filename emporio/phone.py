"""Brazilian phone normalization, shared by sessions, orders and complaints."""

import re

_COUNTRY_CODE = "55"


def normalize_phone(phone: str) -> str:
    """Digits only, without the +55 country code: "+55 (67) 99812-3456" -> "67998123456"."""
    digits = re.sub(r"\D", "", phone)
    if digits.startswith(_COUNTRY_CODE) and len(digits) in (12, 13):
        digits = digits[len(_COUNTRY_CODE) :]
    return digits


def is_valid_phone(phone: str) -> bool:
    """Area code + 8 or 9 digits, after normalization."""
    return len(normalize_phone(phone)) in (10, 11)
