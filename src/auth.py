"""API-key authentication: env-based admin key + DB-backed client keys.

- Admin key (settings.API_KEY) bypasses scope checks and can mint client keys.
- Client keys live in the api_keys table, scoped to specific templates.
- All key comparisons use constant-time HMAC; the DB stores only SHA-256 hashes.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timezone

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.dependencies import db_session
from src.models.api_key import ApiKey

_KEY_PREFIX = "pdx_"


@dataclass
class AuthContext:
    is_admin: bool = False
    api_key_id: str | None = None
    tenant_id: str | None = None
    allowed_templates: list[str] | None = None
    allowed_scopes: list[str] = field(default_factory=list)
    label: str | None = None

    def template_allowed(self, template_name: str) -> bool:
        if self.is_admin:
            return True
        if not self.allowed_templates:
            return False
        return template_name in self.allowed_templates

    def has_scope(self, scope: str) -> bool:
        if self.is_admin:
            return True
        return scope in self.allowed_scopes


def hash_key(plaintext: str) -> str:
    """SHA-256 hex digest used to store + look up keys in the DB."""
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


def generate_key() -> tuple[str, str, str]:
    """Return (plaintext, prefix, hash). The plaintext is shown to the user once."""
    raw = secrets.token_urlsafe(32)
    plaintext = f"{_KEY_PREFIX}{raw}"
    return plaintext, plaintext[:12], hash_key(plaintext)


def _admin_matches(provided: str) -> bool:
    expected = settings.API_KEY
    if not expected:
        return False
    return hmac.compare_digest(provided, expected)


async def authenticate(
    x_api_key: str | None = Header(default=None),
    session: AsyncSession = Depends(db_session),
) -> AuthContext:
    """Resolve an X-API-Key header to an AuthContext. Raises 401 if invalid."""
    if not x_api_key:
        if not settings.API_KEY and not settings.is_production:
            return AuthContext(is_admin=True, label="dev-anon")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header",
        )

    if _admin_matches(x_api_key):
        return AuthContext(is_admin=True, label="admin")

    result = await session.execute(
        select(ApiKey).where(ApiKey.key_hash == hash_key(x_api_key))
    )
    record = result.scalar_one_or_none()
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid X-API-Key",
        )

    if not record.is_active or record.revoked_at is not None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API key revoked")

    if record.expires_at and record.expires_at < datetime.now(tz=timezone.utc):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API key expired")

    record.last_used_at = datetime.now(tz=timezone.utc)
    await session.flush()

    return AuthContext(
        is_admin=False,
        api_key_id=str(record.id),
        tenant_id=str(record.tenant_id),
        allowed_templates=record.allowed_templates,
        allowed_scopes=list(record.allowed_scopes or []),
        label=record.label,
    )


async def require_admin(ctx: AuthContext = Depends(authenticate)) -> AuthContext:
    if not ctx.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin API key required",
        )
    return ctx
