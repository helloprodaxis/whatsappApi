"""SQLAlchemy ORM models — registers all tables on Base.metadata."""
from src.models.api_key import ApiKey
from src.models.base import Base
from src.models.campaign import (
    Campaign,
    CampaignRecipient,
    CampaignRecipientStatus,
    CampaignStatus,
)
from src.models.contact import Contact
from src.models.message import (
    Message,
    MessageDirection,
    MessageStatus,
    MessageType,
)
from src.models.template import Template, TemplateCategory, TemplateStatus
from src.models.tenant import Tenant, TenantPlan
from src.models.webhook_event import WebhookEvent

__all__ = [
    "ApiKey",
    "Base",
    "Campaign",
    "CampaignRecipient",
    "CampaignRecipientStatus",
    "CampaignStatus",
    "Contact",
    "Message",
    "MessageDirection",
    "MessageStatus",
    "MessageType",
    "Template",
    "TemplateCategory",
    "TemplateStatus",
    "Tenant",
    "TenantPlan",
    "WebhookEvent",
]
