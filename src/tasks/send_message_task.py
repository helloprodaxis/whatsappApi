"""Celery task: send a single campaign recipient message."""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

from src.celery_app import celery_app
from src.database import session_scope
from src.exceptions import (
    MetaInvalidRequestError,
    MetaRateLimitError,
    RateLimitExceededError,
)
from src.logger import logger
from src.models.campaign import CampaignRecipient, CampaignRecipientStatus
from src.models.message import Message, MessageDirection, MessageStatus, MessageType
from src.services.message_service import MessageService
from src.services.tenant_service import TenantService
from src.services.whatsapp_client import WhatsAppClient


@celery_app.task(
    bind=True,
    name="src.tasks.send_message_task.send_recipient",
    autoretry_for=(MetaRateLimitError, RateLimitExceededError),
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
    max_retries=5,
    acks_late=True,
)
def send_recipient(self, recipient_id: str) -> str:  # type: ignore[no-untyped-def]
    """Send a campaign recipient's message (template, with their variables).

    Retries automatically on rate-limit. Permanent 4xx errors are recorded
    and the recipient is marked failed without retrying.
    """
    return asyncio.run(_send_recipient(uuid.UUID(recipient_id)))


async def _send_recipient(recipient_id: uuid.UUID) -> str:
    async with session_scope() as session:
        recipient = await session.get(CampaignRecipient, recipient_id)
        if recipient is None:
            logger.warning("Recipient {} not found — skipping", recipient_id)
            return "missing"

        from src.models.campaign import Campaign

        campaign = await session.get(Campaign, recipient.campaign_id)
        if campaign is None:
            logger.warning("Campaign for recipient {} missing", recipient_id)
            return "missing_campaign"

        if recipient.status not in {
            CampaignRecipientStatus.queued,
            CampaignRecipientStatus.sending,
        }:
            return f"skipped:{recipient.status.value}"

        recipient.status = CampaignRecipientStatus.sending
        recipient.attempt_count = (recipient.attempt_count or 0) + 1
        recipient.attempted_at = datetime.now(tz=timezone.utc)
        await session.flush()

        tenants = TenantService(session)
        tenant = await tenants.get(campaign.tenant_id)

        msg_service = MessageService(session)

        if not await msg_service.rate_limiter.acquire(
            tenant.phone_number_id, recipient.phone
        ):
            raise RateLimitExceededError()

        components = []
        if recipient.variables:
            ordered = sorted(
                recipient.variables.items(),
                key=lambda kv: int(kv[0].split("_")[-1]) if kv[0].split("_")[-1].isdigit() else 999,
            )
            components.append({
                "type": "body",
                "parameters": [{"type": "text", "text": str(v)} for _, v in ordered],
            })

        record = Message(
            tenant_id=tenant.id,
            direction=MessageDirection.outbound,
            recipient_phone=recipient.phone,
            sender_phone=tenant.phone_number_id,
            message_type=MessageType.template,
            template_name=campaign.template_name,
            template_language=campaign.template_language,
            content={
                "template_name": campaign.template_name,
                "language_code": campaign.template_language,
                "components": components,
            },
            status=MessageStatus.queued,
            campaign_recipient_id=recipient.id,
        )
        session.add(record)
        await session.flush()

        client = WhatsAppClient(
            access_token=tenants.decrypt(tenant.access_token),
            phone_number_id=tenant.phone_number_id,
        )

        try:
            response = await client.send_template(
                to=recipient.phone,
                template_name=campaign.template_name,
                language_code=campaign.template_language,
                components=components or None,
            )
        except MetaInvalidRequestError as exc:
            logger.warning(
                "Permanent send failure recipient={} error={}", recipient.phone, exc.message
            )
            record.status = MessageStatus.failed
            record.failed_at = datetime.now(tz=timezone.utc)
            record.error_message = exc.message
            recipient.status = CampaignRecipientStatus.failed
            recipient.error_message = exc.message
            recipient.completed_at = datetime.now(tz=timezone.utc)
            campaign.failed_count = (campaign.failed_count or 0) + 1
            await session.flush()
            return "failed"

        wa_id = response["messages"][0]["id"]
        record.wa_message_id = wa_id
        record.status = MessageStatus.sent
        record.sent_at = datetime.now(tz=timezone.utc)

        recipient.status = CampaignRecipientStatus.sent
        recipient.wa_message_id = wa_id
        campaign.sent_count = (campaign.sent_count or 0) + 1

        await tenants.increment_usage(tenant.id)
        await session.flush()

        return "sent"
