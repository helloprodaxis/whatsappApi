"""Webhook ingestion + processing.

Inbound flow:
1. Router calls ``store_raw_event(...)`` — saves a row in webhook_events,
   returns 200 to Meta within milliseconds.
2. Celery task picks up the unprocessed event and calls
   ``process_event(...)`` to update the messages/templates tables.
"""
from __future__ import annotations

import hashlib
import hmac
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.exceptions import WebhookSignatureError
from src.logger import logger
from src.models.campaign import (
    CampaignRecipient,
    CampaignRecipientStatus,
    CampaignStatus,
)
from src.models.message import (
    Message,
    MessageDirection,
    MessageStatus,
    MessageType,
)
from src.models.tenant import Tenant
from src.models.webhook_event import WebhookEvent
from src.services.tenant_service import TenantService

_STATUS_MAP = {
    "sent": MessageStatus.sent,
    "delivered": MessageStatus.delivered,
    "read": MessageStatus.read,
    "failed": MessageStatus.failed,
    "deleted": MessageStatus.failed,
}


def verify_signature(raw_body: bytes, signature_header: str | None) -> bool:
    """Validate the X-Hub-Signature-256 header sent by Meta."""
    if not signature_header:
        return False
    if not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(
        settings.META_APP_SECRET.encode(),
        raw_body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(signature_header.split("=", 1)[1], expected)


def assert_signature(raw_body: bytes, signature_header: str | None) -> None:
    if not verify_signature(raw_body, signature_header):
        raise WebhookSignatureError()


class WebhookService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.tenants = TenantService(session)

    # ---------------------------------------------------------------- ingest

    async def store_raw_event(
        self,
        payload: dict[str, Any],
        *,
        event_type: str = "messages",
    ) -> WebhookEvent:
        tenant_id = await self._infer_tenant_id(payload)
        event = WebhookEvent(
            tenant_id=tenant_id,
            event_type=event_type,
            payload=payload,
            processed=False,
        )
        self.session.add(event)
        await self.session.flush()
        return event

    async def _infer_tenant_id(self, payload: dict[str, Any]) -> uuid.UUID | None:
        """Best-effort mapping of webhook -> tenant via WABA id or phone number id."""
        try:
            entries = payload.get("entry", []) or []
            if not entries:
                return None
            waba_id = entries[0].get("id")
            if waba_id:
                tenant = await self.tenants.get_by_waba_id(str(waba_id))
                if tenant:
                    return tenant.id

            for change in (entries[0].get("changes") or []):
                metadata = (change.get("value") or {}).get("metadata") or {}
                phone_id = metadata.get("phone_number_id")
                if phone_id:
                    tenant = await self.tenants.get_by_phone_number_id(str(phone_id))
                    if tenant:
                        return tenant.id
        except Exception:  # noqa: BLE001
            return None
        return None

    # ---------------------------------------------------------------- process

    async def process_event(self, event_id: uuid.UUID) -> None:
        event = await self.session.get(WebhookEvent, event_id)
        if event is None:
            return
        if event.processed:
            return

        try:
            for entry in event.payload.get("entry", []) or []:
                for change in entry.get("changes", []) or []:
                    field = change.get("field")
                    value = change.get("value", {}) or {}

                    if field == "messages":
                        await self._handle_messages(event, value)
                    elif field in {"message_template_status_update", "template_category_update"}:
                        await self._handle_template_update(event, value)
                    else:
                        logger.debug("Ignoring webhook field {}", field)

            event.processed = True
            event.processed_at = datetime.now(tz=timezone.utc)
            event.error = None
        except Exception as exc:  # noqa: BLE001
            event.error = str(exc)
            logger.exception("Webhook processing failed: {}", exc)
        finally:
            await self.session.flush()

    async def _handle_messages(
        self,
        event: WebhookEvent,
        value: dict[str, Any],
    ) -> None:
        tenant = await self._tenant_for_value(value, fallback_tenant_id=event.tenant_id)

        # Inbound messages
        for msg in value.get("messages", []) or []:
            await self._save_inbound_message(tenant, value, msg)

        # Outbound status updates
        for status in value.get("statuses", []) or []:
            await self._apply_status_update(status)

    async def _tenant_for_value(
        self,
        value: dict[str, Any],
        fallback_tenant_id: uuid.UUID | None,
    ) -> Tenant | None:
        metadata = value.get("metadata") or {}
        phone_id = metadata.get("phone_number_id")
        if phone_id:
            tenant = await self.tenants.get_by_phone_number_id(str(phone_id))
            if tenant:
                return tenant
        if fallback_tenant_id:
            return await self.session.get(Tenant, fallback_tenant_id)
        return None

    async def _save_inbound_message(
        self,
        tenant: Tenant | None,
        value: dict[str, Any],
        msg: dict[str, Any],
    ) -> None:
        if tenant is None:
            logger.warning("Inbound message without resolvable tenant: {}", msg.get("from"))
            return

        msg_type_raw = msg.get("type", "unsupported")
        try:
            msg_type = MessageType(msg_type_raw)
        except ValueError:
            msg_type = MessageType.unsupported

        sender_phone = (value.get("metadata") or {}).get("display_phone_number") or ""
        record = Message(
            tenant_id=tenant.id,
            direction=MessageDirection.inbound,
            wa_message_id=msg.get("id"),
            recipient_phone=sender_phone or tenant.phone_number_id,
            sender_phone=msg.get("from", ""),
            message_type=msg_type,
            content=msg,
            status=MessageStatus.delivered,
        )
        self.session.add(record)

    async def _apply_status_update(self, status: dict[str, Any]) -> None:
        wa_id = status.get("id")
        new_status_raw = status.get("status")
        if not wa_id or not new_status_raw:
            return

        new_status = _STATUS_MAP.get(new_status_raw)
        if new_status is None:
            return

        result = await self.session.execute(
            select(Message).where(Message.wa_message_id == wa_id)
        )
        message = result.scalar_one_or_none()
        if message is None:
            return

        ts = status.get("timestamp")
        when = (
            datetime.fromtimestamp(int(ts), tz=timezone.utc) if ts else datetime.now(tz=timezone.utc)
        )

        message.status = new_status
        if new_status == MessageStatus.sent and message.sent_at is None:
            message.sent_at = when
        elif new_status == MessageStatus.delivered and message.delivered_at is None:
            message.delivered_at = when
        elif new_status == MessageStatus.read and message.read_at is None:
            message.read_at = when
        elif new_status == MessageStatus.failed and message.failed_at is None:
            message.failed_at = when
            errors = status.get("errors") or []
            if errors:
                message.error_code = errors[0].get("code")
                message.error_message = errors[0].get("title") or errors[0].get("message")

        if status.get("pricing"):
            message.meta_pricing = status.get("pricing")

        if message.campaign_recipient_id:
            await self._propagate_campaign_status(
                message.campaign_recipient_id, new_status
            )

    async def _propagate_campaign_status(
        self,
        recipient_id: uuid.UUID,
        new_status: MessageStatus,
    ) -> None:
        recipient = await self.session.get(CampaignRecipient, recipient_id)
        if recipient is None:
            return

        mapping = {
            MessageStatus.sent: CampaignRecipientStatus.sent,
            MessageStatus.delivered: CampaignRecipientStatus.delivered,
            MessageStatus.read: CampaignRecipientStatus.read,
            MessageStatus.failed: CampaignRecipientStatus.failed,
        }
        if new_status not in mapping:
            return

        old_status = recipient.status
        recipient.status = mapping[new_status]
        if new_status == MessageStatus.failed:
            recipient.completed_at = datetime.now(tz=timezone.utc)

        # Roll up to campaign counters
        from src.models.campaign import Campaign  # local import to avoid cycle

        campaign = await self.session.get(Campaign, recipient.campaign_id)
        if campaign is None:
            return

        if old_status != recipient.status:
            if new_status == MessageStatus.delivered:
                campaign.delivered_count = (campaign.delivered_count or 0) + 1
            elif new_status == MessageStatus.read:
                campaign.read_count = (campaign.read_count or 0) + 1
            elif new_status == MessageStatus.failed:
                campaign.failed_count = (campaign.failed_count or 0) + 1

        # Mark complete if everyone is done
        outstanding = (campaign.total_recipients or 0) - (
            (campaign.delivered_count or 0)
            + (campaign.read_count or 0)
            + (campaign.failed_count or 0)
        )
        if outstanding <= 0 and campaign.status == CampaignStatus.running:
            campaign.status = CampaignStatus.completed
            campaign.completed_at = datetime.now(tz=timezone.utc)

    async def _handle_template_update(
        self,
        event: WebhookEvent,
        value: dict[str, Any],
    ) -> None:
        from src.models.template import Template, TemplateStatus  # local import

        tenant_id = event.tenant_id
        name = value.get("message_template_name") or value.get("name")
        language = value.get("message_template_language") or value.get("language") or "en_US"
        new_raw = (value.get("event") or value.get("status") or "").upper()
        if not (tenant_id and name and new_raw):
            return

        result = await self.session.execute(
            select(Template).where(
                Template.tenant_id == tenant_id,
                Template.name == name,
                Template.language == language,
            )
        )
        template = result.scalar_one_or_none()
        if template is None:
            return

        try:
            template.status = TemplateStatus(new_raw.lower())
        except ValueError:
            logger.debug("Unknown template status from webhook: {}", new_raw)
