"""Phone number normalization to E.164 (Meta-required)."""
from __future__ import annotations

import phonenumbers

from src.exceptions import ValidationError


def normalize_phone(raw: str, default_region: str = "IN") -> str:
    """Convert any common phone format into E.164 ('+' + digits).

    Meta accepts E.164-shaped numbers (with or without the leading '+').
    We always include the '+' for storage clarity and strip it again at
    the wire level when calling Meta's API.
    """
    if not raw:
        raise ValidationError("Phone number cannot be empty", error_code="invalid_phone")

    cleaned = raw.strip()

    try:
        if cleaned.startswith("+"):
            parsed = phonenumbers.parse(cleaned, None)
        elif cleaned.isdigit() and len(cleaned) >= 11:
            parsed = phonenumbers.parse(f"+{cleaned}", None)
        else:
            parsed = phonenumbers.parse(cleaned, default_region)
    except phonenumbers.NumberParseException as exc:
        raise ValidationError(f"Invalid phone number: {raw}", error_code="invalid_phone") from exc

    if not phonenumbers.is_valid_number(parsed):
        raise ValidationError(f"Phone number not valid: {raw}", error_code="invalid_phone")

    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)


def to_meta_format(e164: str) -> str:
    """Strip the '+' for Meta's wire format ('919876543210')."""
    return e164.lstrip("+")
