"""Pydantic request/response schemas."""

from src.schemas.campaign import (
    CampaignActionResponse,
    CampaignCreate,
    CampaignOut,
    CampaignRecipientOut,
    CampaignUpdate,
    CampaignUploadResponse,
)
from src.schemas.common import (
    ErrorResponse,
    HealthStatus,
    MessageEnvelope,
    Paginated,
    Pagination,
)
from src.schemas.message import (
    MessageOut,
    MessageStatusOut,
    SendResponse,
    SendTemplateRequest,
    SendTextRequest,
)
from src.schemas.template import TemplateOut, TemplateSyncRequest, TemplateSyncResponse
from src.schemas.tenant import TenantCreate, TenantOut, TenantUpdate, TenantUsage
from src.schemas.webhook import (
    WebhookAck,
    WebhookChange,
    WebhookEntry,
    WebhookValue,
    WhatsAppWebhookPayload,
)

__all__ = [
    "CampaignActionResponse",
    "CampaignCreate",
    "CampaignOut",
    "CampaignRecipientOut",
    "CampaignUpdate",
    "CampaignUploadResponse",
    "ErrorResponse",
    "HealthStatus",
    "MessageEnvelope",
    "MessageOut",
    "MessageStatusOut",
    "Paginated",
    "Pagination",
    "SendResponse",
    "SendTemplateRequest",
    "SendTextRequest",
    "TemplateOut",
    "TemplateSyncRequest",
    "TemplateSyncResponse",
    "TenantCreate",
    "TenantOut",
    "TenantUpdate",
    "TenantUsage",
    "WebhookAck",
    "WebhookChange",
    "WebhookEntry",
    "WebhookValue",
    "WhatsAppWebhookPayload",
]
