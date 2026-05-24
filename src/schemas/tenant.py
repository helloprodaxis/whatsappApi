"""Tenant request/response schemas."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from src.models.tenant import TenantPlan


class TenantCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    slug: str = Field(min_length=1, max_length=80, pattern=r"^[a-z0-9][a-z0-9-]*[a-z0-9]$")
    waba_id: str = Field(min_length=1, max_length=64)
    phone_number_id: str = Field(min_length=1, max_length=64)
    access_token: str = Field(min_length=10)
    plan: TenantPlan = TenantPlan.starter
    monthly_message_limit: int = Field(default=5_000, ge=0)


class TenantUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=150)
    is_active: bool | None = None
    plan: TenantPlan | None = None
    monthly_message_limit: int | None = Field(default=None, ge=0)
    access_token: str | None = None


class TenantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    waba_id: str
    phone_number_id: str
    is_active: bool
    plan: TenantPlan
    monthly_message_limit: int
    messages_sent_this_month: int
    created_at: datetime
    updated_at: datetime


class TenantUsage(BaseModel):
    tenant_id: uuid.UUID
    monthly_message_limit: int
    messages_sent_this_month: int
    remaining: int
    percent_used: float
