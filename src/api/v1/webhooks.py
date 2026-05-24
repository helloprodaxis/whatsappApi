"""Meta WhatsApp webhook endpoints (verify + receive)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Query, Request, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import db_session
from src.config import settings
from src.exceptions import WebhookSignatureError
from src.logger import logger
from src.schemas.webhook import WebhookAck
from src.services.webhook_service import WebhookService, verify_signature

router = APIRouter(prefix="/webhooks", tags=["webhooks"], include_in_schema=False)


@router.get(
    "/whatsapp",
    response_class=PlainTextResponse,
    include_in_schema=True,
    summary="Meta webhook verification handshake",
)
async def verify_webhook(
    hub_mode: str | None = Query(default=None, alias="hub.mode"),
    hub_verify_token: str | None = Query(default=None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(default=None, alias="hub.challenge"),
) -> PlainTextResponse:
    if hub_mode == "subscribe" and hub_verify_token == settings.META_WEBHOOK_VERIFY_TOKEN:
        logger.info("Meta webhook verification succeeded")
        return PlainTextResponse(content=hub_challenge or "", status_code=200)

    logger.warning(
        "Meta webhook verification failed mode={} token_match={}",
        hub_mode, hub_verify_token == settings.META_WEBHOOK_VERIFY_TOKEN,
    )
    return PlainTextResponse(content="forbidden", status_code=status.HTTP_403_FORBIDDEN)


@router.post(
    "/whatsapp",
    response_model=WebhookAck,
    status_code=status.HTTP_200_OK,
    summary="Receive WhatsApp events (messages, statuses, template updates)",
)
async def receive_webhook(
    request: Request,
    x_hub_signature_256: str | None = Header(default=None, alias="X-Hub-Signature-256"),
    session: AsyncSession = Depends(db_session),
) -> WebhookAck:
    raw = await request.body()
    if not verify_signature(raw, x_hub_signature_256):
        logger.warning("Rejected unsigned/invalid webhook")
        raise WebhookSignatureError()

    payload = await request.json()
    object_type = payload.get("object", "messages")

    service = WebhookService(session)
    event = await service.store_raw_event(payload, event_type=object_type)
    await session.flush()

    # Inline processing — Vercel has no background workers. Meta retries on
    # 5xx, so any unhandled error inside process_event is logged but the
    # event row stays persisted with the failure recorded.
    try:
        await service.process_event(event.id)
    except Exception as exc:
        logger.exception("Inline webhook processing failed event_id={}: {}", event.id, exc)

    await session.commit()
    return WebhookAck(received=True, event_id=str(event.id))
