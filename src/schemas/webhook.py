"""Webhook schemas — Meta's WhatsApp webhook payload."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class WebhookValue(BaseModel):
    """Inner ``value`` object on a WhatsApp webhook entry."""

    model_config = ConfigDict(extra="allow")

    messaging_product: str | None = None
    metadata: dict[str, Any] | None = None
    contacts: list[dict[str, Any]] | None = None
    messages: list[dict[str, Any]] | None = None
    statuses: list[dict[str, Any]] | None = None
    errors: list[dict[str, Any]] | None = None


class WebhookChange(BaseModel):
    model_config = ConfigDict(extra="allow")

    field: str
    value: WebhookValue


class WebhookEntry(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    changes: list[WebhookChange]


class WhatsAppWebhookPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    object: str = Field(description="Should be 'whatsapp_business_account'")
    entry: list[WebhookEntry]


class WebhookAck(BaseModel):
    received: bool = True
    event_id: str | None = None
