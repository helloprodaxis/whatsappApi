"""Campaign schemas."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from src.models.campaign import CampaignRecipientStatus, CampaignStatus


class CampaignCreate(BaseModel):
    tenant_id: uuid.UUID | None = None
    name: str = Field(min_length=1, max_length=200)
    template_name: str = Field(min_length=1, max_length=150)
    language_code: str = Field(default="en_US", min_length=2, max_length=20)
    scheduled_at: datetime | None = None


class CampaignUpdate(BaseModel):
    name: str | None = None
    scheduled_at: datetime | None = None


class CampaignOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    template_name: str
    template_language: str
    total_recipients: int
    sent_count: int
    delivered_count: int
    read_count: int
    failed_count: int
    status: CampaignStatus
    scheduled_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class CampaignRecipientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    campaign_id: uuid.UUID
    phone: str
    variables: dict
    status: CampaignRecipientStatus
    wa_message_id: str | None
    error_message: str | None
    attempted_at: datetime | None
    completed_at: datetime | None
    attempt_count: int


class CampaignUploadResponse(BaseModel):
    campaign_id: uuid.UUID
    rows_parsed: int
    rows_inserted: int
    rows_skipped: int
    skip_reasons: list[str] = Field(default_factory=list)


class CampaignActionResponse(BaseModel):
    campaign_id: uuid.UUID
    status: CampaignStatus
    message: str
