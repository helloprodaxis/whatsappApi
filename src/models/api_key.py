"""API key model — DB-backed client credentials with scopes + template allowlist."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ApiKey(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "api_keys"

    tenant_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    key_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    key_prefix: Mapped[str] = mapped_column(String(12), nullable=False)
    label: Mapped[str] = mapped_column(String(150), nullable=False)

    allowed_templates: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    allowed_scopes: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=lambda: ["send_template"]
    )

    rate_limit_per_hour: Mapped[int] = mapped_column(Integer, nullable=False, default=60)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    tenant: Mapped["Tenant"] = relationship("Tenant", lazy="selectin")  # noqa: F821

    def template_allowed(self, template_name: str) -> bool:
        if not self.allowed_templates:
            return True
        return template_name in self.allowed_templates

    def has_scope(self, scope: str) -> bool:
        return scope in (self.allowed_scopes or [])
