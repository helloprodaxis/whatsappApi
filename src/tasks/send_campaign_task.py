"""Celery task: orchestrate a campaign by enqueuing a per-recipient task."""
from __future__ import annotations

import asyncio
import uuid

from src.celery_app import celery_app
from src.database import session_scope
from src.logger import logger
from src.models.campaign import (
    Campaign,
    CampaignRecipient,
    CampaignRecipientStatus,
    CampaignStatus,
)
from sqlalchemy import select


@celery_app.task(
    bind=True,
    name="src.tasks.send_campaign_task.process_campaign",
    acks_late=True,
)
def process_campaign_task(self, campaign_id: str) -> dict:  # type: ignore[no-untyped-def]
    """Fan-out: load all queued recipients and enqueue them individually."""
    return asyncio.run(_process_campaign(uuid.UUID(campaign_id)))


async def _process_campaign(campaign_id: uuid.UUID) -> dict:
    from src.tasks.send_message_task import send_recipient

    async with session_scope() as session:
        campaign = await session.get(Campaign, campaign_id)
        if campaign is None:
            return {"status": "missing"}
        if campaign.status != CampaignStatus.running:
            return {"status": campaign.status.value, "skipped": True}

        result = await session.execute(
            select(CampaignRecipient.id).where(
                CampaignRecipient.campaign_id == campaign_id,
                CampaignRecipient.status == CampaignRecipientStatus.queued,
            )
        )
        recipient_ids = [row[0] for row in result.all()]

    logger.info(
        "Dispatching {} recipients for campaign {}", len(recipient_ids), campaign_id
    )
    for rid in recipient_ids:
        send_recipient.apply_async(args=[str(rid)], queue="prodaxis.messages")

    return {"status": "dispatched", "count": len(recipient_ids)}
