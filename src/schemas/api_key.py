"""Pydantic schemas for API key admin endpoints."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ApiKeyCreate(BaseModel):
    tenant_id: uuid.UUID | None = Field(
        default=None,
        description="Tenant to scope the key to. Defaults to the platform default tenant.",
    )
    label: str = Field(min_length=2, max_length=150, description="Human label (e.g. 'Acme QA')")
    allowed_templates: list[str] | None = Field(
        default=None,
        description="Template names this key may send. Null = no template restriction.",
    )
    allowed_scopes: list[str] = Field(
        default_factory=lambda: ["send_template"],
        description="Scopes: send_template, send_text, read_messages, read_templates",
    )
    rate_limit_per_hour: int = Field(default=60, ge=1, le=10_000)
    expires_in_days: int | None = Field(
        default=None, ge=1, le=3650,
        description="Optional expiry. Null = never expires.",
    )


class ApiKeyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    key_prefix: str
    label: str
    allowed_templates: list[str] | None
    allowed_scopes: list[str]
    rate_limit_per_hour: int
    is_active: bool
    expires_at: datetime | None
    last_used_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime


class ApiKeyCreated(ApiKeyOut):
    """Returned only on creation — contains the plaintext token (shown once)."""

    plaintext_key: str = Field(description="Full secret. Will not be retrievable again.")
