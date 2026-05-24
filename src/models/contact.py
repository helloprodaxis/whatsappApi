"""Contact model — per-tenant customer phonebook."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from src.models.tenant import Tenant


class Contact(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "contacts"
    __table_args__ = (
        UniqueConstraint("tenant_id", "phone", name="uq_contacts_tenant_phone"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    phone: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    email: Mapped[str | None] = mapped_column(String(254), nullable=True)

    attributes: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    opted_in: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    opted_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    opted_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    tenant: Mapped["Tenant"] = relationship(back_populates="contacts")

    def __repr__(self) -> str:
        return f"<Contact id={self.id} phone={self.phone}>"
