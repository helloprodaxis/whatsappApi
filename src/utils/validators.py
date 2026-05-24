"""Reusable validators."""
from __future__ import annotations

import re
from urllib.parse import urlparse

from src.exceptions import ValidationError

_HTTPS_URL = re.compile(r"^https://", re.I)


def validate_https_url(url: str, *, field: str = "url") -> str:
    """Meta requires media headers be public HTTPS URLs."""
    if not url:
        raise ValidationError(f"{field} is required", error_code="invalid_url")
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValidationError(f"{field} must be a valid HTTPS URL", error_code="invalid_url")
    return url


def validate_template_name(name: str) -> str:
    """Meta template names: lowercase, digits, underscores."""
    if not re.fullmatch(r"[a-z0-9_]{1,512}", name):
        raise ValidationError(
            "Template name must be lowercase letters, digits, and underscores",
            error_code="invalid_template_name",
        )
    return name
