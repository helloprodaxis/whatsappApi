"""Message request/response schemas."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.models.message import MessageDirection, MessageStatus, MessageType
from src.utils.phone import normalize_phone


class _PhoneMixin(BaseModel):
    @field_validator("to", check_fields=False)
    @classmethod
    def _validate_to(cls, v: str) -> str:
        return normalize_phone(v)


class SendTextRequest(_PhoneMixin):
    tenant_id: uuid.UUID | None = Field(default=None, description="Defaults to the platform tenant")
    to: str = Field(description="Recipient phone in any common format; normalized to E.164")
    text: str = Field(min_length=1, max_length=4096)
    preview_url: bool = Field(default=False)


class TemplateButtonParam(BaseModel):
    sub_type: str = Field(default="url")
    index: int = Field(ge=0)
    parameters: list[dict[str, Any]] = Field(default_factory=list)


class SendTemplateRequest(_PhoneMixin):
    tenant_id: uuid.UUID | None = None
    to: str
    template_name: str = Field(min_length=1, max_length=150)
    language_code: str = Field(default="en_US", min_length=2, max_length=20)
    variables: list[str] | None = Field(
        default=None,
        description="Body variables in order (will become {1}, {2}, ...)",
    )
    header_image_url: str | None = Field(
        default=None, description="Public HTTPS URL for templates with media headers"
    )
    header_document_url: str | None = None
    header_document_filename: str | None = None
    button_url_param: str | None = Field(
        default=None, description="Dynamic URL suffix for templates with URL buttons"
    )


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    direction: MessageDirection
    wa_message_id: str | None
    recipient_phone: str
    sender_phone: str
    message_type: MessageType
    template_name: str | None
    template_language: str | None
    status: MessageStatus
    error_code: int | None
    error_message: str | None
    sent_at: datetime | None
    delivered_at: datetime | None
    read_at: datetime | None
    failed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class MessageStatusOut(BaseModel):
    id: uuid.UUID
    wa_message_id: str | None
    status: MessageStatus
    sent_at: datetime | None
    delivered_at: datetime | None
    read_at: datetime | None
    failed_at: datetime | None
    error_code: int | None
    error_message: str | None


class SendResponse(BaseModel):
    """Returned immediately after a successful Meta call."""

    message_id: uuid.UUID
    wa_message_id: str
    status: MessageStatus
    to: str
