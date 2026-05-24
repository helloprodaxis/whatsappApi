"""Shared Pydantic models — pagination, error envelopes, etc."""
from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ErrorResponse(BaseModel):
    error_code: str = Field(description="Stable machine-readable error code")
    message: str = Field(description="Human-readable error message")
    details: dict[str, Any] | None = Field(default=None)
    request_id: str | None = Field(default=None)


class HealthStatus(BaseModel):
    status: str = "ok"
    version: str
    environment: str
    db: str
    redis: str
    celery: str | None = None


class Pagination(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=500)


class Paginated(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int


class MessageEnvelope(BaseModel):
    """Generic ack envelope for endpoints that don't need a full payload."""

    success: bool = True
    message: str
