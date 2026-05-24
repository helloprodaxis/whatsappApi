"""Campaign and CampaignRecipient models — bulk send orchestration."""
from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from src.models.tenant import Tenant


class CampaignStatus(str, enum.Enum):
    draft = "draft"
    scheduled = "scheduled"
    running = "running"
    paused = "paused"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class CampaignRecipientStatus(str, enum.Enum):
    queued = "queued"
    sending = "sending"
    sent = "sent"
    delivered = "delivered"
    read = "read"
    failed = "failed"
    skipped = "skipped"


class Campaign(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "campaigns"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    template_name: Mapped[str] = mapped_column(String(150), nullable=False)
    template_language: Mapped[str] = mapped_column(String(20), nullable=False)

    total_recipients: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sent_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    delivered_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    read_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    status: Mapped[CampaignStatus] = mapped_column(
        SAEnum(CampaignStatus, name="campaign_status"),
        nullable=False,
        default=CampaignStatus.draft,
        index=True,
    )

    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    error_log: Mapped[list[dict] | None] = mapped_column(JSONB, nullable=True, default=list)

    tenant: Mapped["Tenant"] = relationship(back_populates="campaigns")
    recipients: Mapped[list["CampaignRecipient"]] = relationship(
        back_populates="campaign",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Campaign id={self.id} name={self.name!r} status={self.status.value}>"


class CampaignRecipient(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "campaign_recipients"
    __table_args__ = (
        Index("ix_campaign_recipients_campaign_status", "campaign_id", "status"),
    )

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    variables: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    status: Mapped[CampaignRecipientStatus] = mapped_column(
        SAEnum(CampaignRecipientStatus, name="campaign_recipient_status"),
        nullable=False,
        default=CampaignRecipientStatus.queued,
    )

    wa_message_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    attempted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    campaign: Mapped[Campaign] = relationship(back_populates="recipients")

    def __repr__(self) -> str:
        return f"<CampaignRecipient id={self.id} phone={self.phone} status={self.status.value}>"
