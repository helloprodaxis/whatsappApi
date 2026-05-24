"""Template schemas."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from src.models.template import TemplateCategory, TemplateStatus


class TemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    language: str
    category: TemplateCategory
    status: TemplateStatus
    components: list[dict[str, Any]]
    meta_template_id: str | None
    last_synced_at: datetime | None
    created_at: datetime
    updated_at: datetime


class TemplateSyncRequest(BaseModel):
    tenant_id: uuid.UUID | None = None


class TemplateSyncResponse(BaseModel):
    synced: int
    created: int
    updated: int
    tenant_id: uuid.UUID
    fetched_at: datetime = Field(default_factory=datetime.utcnow)
