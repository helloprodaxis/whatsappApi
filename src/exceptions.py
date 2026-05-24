"""Domain-specific exceptions for the platform.

Each exception carries an HTTP status code and a stable error_code string
used in API responses for client-side handling.
"""
from __future__ import annotations

from typing import Any


class ProdaxisError(Exception):
    """Base for all custom errors."""

    status_code: int = 500
    error_code: str = "internal_error"
    message: str = "An internal error occurred"

    def __init__(
        self,
        message: str | None = None,
        *,
        details: dict[str, Any] | None = None,
        error_code: str | None = None,
        status_code: int | None = None,
    ) -> None:
        self.message = message or self.message
        self.details = details or {}
        if error_code:
            self.error_code = error_code
        if status_code:
            self.status_code = status_code
        super().__init__(self.message)


# ----- Validation / client errors -----

class ValidationError(ProdaxisError):
    status_code = 422
    error_code = "validation_error"


class NotFoundError(ProdaxisError):
    status_code = 404
    error_code = "not_found"


class ConflictError(ProdaxisError):
    status_code = 409
    error_code = "conflict"


class UnauthorizedError(ProdaxisError):
    status_code = 401
    error_code = "unauthorized"


class ForbiddenError(ProdaxisError):
    status_code = 403
    error_code = "forbidden"


class TenantNotFoundError(NotFoundError):
    error_code = "tenant_not_found"
    message = "Tenant not found"


class TemplateNotFoundError(NotFoundError):
    error_code = "template_not_found"
    message = "Template not found"


class CampaignNotFoundError(NotFoundError):
    error_code = "campaign_not_found"
    message = "Campaign not found"


class TenantQuotaExceededError(ProdaxisError):
    status_code = 429
    error_code = "tenant_quota_exceeded"
    message = "Monthly message quota exceeded for tenant"


class RateLimitExceededError(ProdaxisError):
    status_code = 429
    error_code = "rate_limit_exceeded"
    message = "Rate limit exceeded — slow down"


# ----- Meta API errors -----

class MetaError(ProdaxisError):
    """Base class for Meta Cloud API failures."""

    status_code = 502
    error_code = "meta_error"
    message = "Meta WhatsApp Cloud API error"


class MetaAuthError(MetaError):
    status_code = 401
    error_code = "meta_auth_error"
    message = "Meta access token rejected"


class MetaInvalidRequestError(MetaError):
    status_code = 400
    error_code = "meta_invalid_request"
    message = "Meta rejected the request"


class MetaRateLimitError(MetaError):
    status_code = 429
    error_code = "meta_rate_limit"
    message = "Meta rate limit hit; retry later"


class MetaServerError(MetaError):
    status_code = 502
    error_code = "meta_server_error"
    message = "Meta server error"


class WebhookSignatureError(ProdaxisError):
    status_code = 401
    error_code = "webhook_signature_invalid"
    message = "Invalid webhook signature"
