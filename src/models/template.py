"""Template model — local cache of Meta-approved message templates."""
from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from src.models.tenant import Tenant


class TemplateCategory(str, enum.Enum):
    utility = "utility"
    marketing = "marketing"
    authentication = "authentication"


class TemplateStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    paused = "paused"
    disabled = "disabled"


class Template(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "templates"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", "language", name="uq_templates_tenant_name_lang"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    language: Mapped[str] = mapped_column(String(20), nullable=False)

    category: Mapped[TemplateCategory] = mapped_column(
        SAEnum(TemplateCategory, name="template_category"), nullable=False
    )
    status: Mapped[TemplateStatus] = mapped_column(
        SAEnum(TemplateStatus, name="template_status"),
        nullable=False,
        default=TemplateStatus.pending,
    )

    components: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list)

    meta_template_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    tenant: Mapped["Tenant"] = relationship(back_populates="templates")

    def __repr__(self) -> str:
        return f"<Template id={self.id} name={self.name} lang={self.language}>"
