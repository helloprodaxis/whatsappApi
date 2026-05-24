"""Message model — every outbound and inbound WhatsApp message."""
from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from src.models.tenant import Tenant


class MessageDirection(str, enum.Enum):
    outbound = "outbound"
    inbound = "inbound"


class MessageType(str, enum.Enum):
    text = "text"
    template = "template"
    image = "image"
    document = "document"
    audio = "audio"
    video = "video"
    interactive = "interactive"
    location = "location"
    contacts = "contacts"
    reaction = "reaction"
    sticker = "sticker"
    unsupported = "unsupported"


class MessageStatus(str, enum.Enum):
    queued = "queued"
    sent = "sent"
    delivered = "delivered"
    read = "read"
    failed = "failed"


class Message(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "messages"
    __table_args__ = (
        Index("ix_messages_tenant_created", "tenant_id", "created_at"),
        Index("ix_messages_tenant_status", "tenant_id", "status"),
        Index("ix_messages_recipient", "recipient_phone"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    direction: Mapped[MessageDirection] = mapped_column(
        SAEnum(MessageDirection, name="message_direction"),
        nullable=False,
        index=True,
    )

    wa_message_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)

    recipient_phone: Mapped[str] = mapped_column(String(20), nullable=False)
    sender_phone: Mapped[str] = mapped_column(String(20), nullable=False)

    message_type: Mapped[MessageType] = mapped_column(
        SAEnum(MessageType, name="message_type"),
        nullable=False,
    )

    content: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    template_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    template_language: Mapped[str | None] = mapped_column(String(20), nullable=True)

    status: Mapped[MessageStatus] = mapped_column(
        SAEnum(MessageStatus, name="message_status"),
        nullable=False,
        default=MessageStatus.queued,
        index=True,
    )

    error_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    meta_pricing: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    campaign_recipient_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True, index=True
    )

    tenant: Mapped["Tenant"] = relationship(back_populates="messages")

    def __repr__(self) -> str:
        return f"<Message id={self.id} type={self.message_type.value} status={self.status.value}>"
