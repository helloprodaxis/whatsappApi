"""API-scoped dependencies (re-exports for convenience)."""
from __future__ import annotations

from src.auth import AuthContext, authenticate, require_admin
from src.dependencies import db_session

# Backwards-compatible alias: routes that just gate access can keep using
# ``require_api_key``; routes that need scope checks should import
# ``authenticate`` directly and inspect the returned ``AuthContext``.
require_api_key = authenticate

__all__ = [
    "AuthContext",
    "authenticate",
    "db_session",
    "require_admin",
    "require_api_key",
]
