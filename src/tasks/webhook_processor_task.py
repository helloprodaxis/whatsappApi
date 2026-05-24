"""Celery task: process a stored WebhookEvent (parse + apply state)."""
from __future__ import annotations

import asyncio
import uuid

from src.celery_app import celery_app
from src.database import session_scope
from src.services.webhook_service import WebhookService


@celery_app.task(
    bind=True,
    name="src.tasks.webhook_processor_task.process_webhook",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=120,
    retry_jitter=True,
    max_retries=3,
    acks_late=True,
)
def process_webhook_task(self, webhook_event_id: str) -> str:  # type: ignore[no-untyped-def]
    return asyncio.run(_process(uuid.UUID(webhook_event_id)))


async def _process(event_id: uuid.UUID) -> str:
    async with session_scope() as session:
        service = WebhookService(session)
        await service.process_event(event_id)
    return "ok"
