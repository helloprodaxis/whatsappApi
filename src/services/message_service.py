"""Message orchestration: persistence + Meta API calls + status tracking."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.exceptions import (
    NotFoundError,
    RateLimitExceededError,
)
from src.logger import logger
from src.models.message import Message, MessageDirection, MessageStatus, MessageType
from src.models.tenant import Tenant
from src.schemas.message import SendResponse, SendTemplateRequest, SendTextRequest
from src.services.rate_limiter import RateLimiter
from src.services.tenant_service import TenantService
from src.services.whatsapp_client import WhatsAppClient
from src.utils.validators import validate_https_url


class MessageService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.tenants = TenantService(session)
        self.rate_limiter = RateLimiter()

    # ---------------------------------------------------------------- helpers

    def _client_for(self, tenant: Tenant) -> WhatsAppClient:
        return WhatsAppClient(
            access_token=self.tenants.decrypt(tenant.access_token),
            phone_number_id=tenant.phone_number_id,
        )

    @staticmethod
    def _build_template_components(payload: SendTemplateRequest) -> list[dict[str, Any]]:
        components: list[dict[str, Any]] = []

        if payload.header_image_url:
            validate_https_url(payload.header_image_url, field="header_image_url")
            components.append({
                "type": "header",
                "parameters": [
                    {"type": "image", "image": {"link": payload.header_image_url}}
                ],
            })
        elif payload.header_document_url:
            validate_https_url(payload.header_document_url, field="header_document_url")
            components.append({
                "type": "header",
                "parameters": [{
                    "type": "document",
                    "document": {
                        "link": payload.header_document_url,
                        "filename": payload.header_document_filename or "document.pdf",
                    },
                }],
            })

        if payload.variables:
            components.append({
                "type": "body",
                "parameters": [{"type": "text", "text": v} for v in payload.variables],
            })

        if payload.button_url_param:
            components.append({
                "type": "button",
                "sub_type": "url",
                "index": "0",
                "parameters": [{"type": "text", "text": payload.button_url_param}],
            })

        return components

    # ---------------------------------------------------------------- sends

    async def send_text(self, payload: SendTextRequest) -> SendResponse:
        tenant = await self.tenants.resolve(payload.tenant_id)
        await self.tenants.assert_quota(tenant)

        if not await self.rate_limiter.acquire(tenant.phone_number_id, payload.to):
            raise RateLimitExceededError()

        record = Message(
            tenant_id=tenant.id,
            direction=MessageDirection.outbound,
            recipient_phone=payload.to,
            sender_phone=tenant.phone_number_id,
            message_type=MessageType.text,
            content={"text": payload.text, "preview_url": payload.preview_url},
            status=MessageStatus.queued,
        )
        self.session.add(record)
        await self.session.flush()

        try:
            response = await self._client_for(tenant).send_text(
                to=payload.to, text=payload.text, preview_url=payload.preview_url
            )
        except Exception as exc:  # noqa: BLE001
            record.status = MessageStatus.failed
            record.failed_at = datetime.utcnow()
            record.error_message = str(exc)
            await self.session.flush()
            logger.error("send_text failed tenant={} to={}: {}", tenant.slug, payload.to, exc)
            raise

        wa_id = response["messages"][0]["id"]
        record.wa_message_id = wa_id
        record.status = MessageStatus.sent
        record.sent_at = datetime.utcnow()
        await self.session.flush()

        await self.tenants.increment_usage(tenant.id)

        logger.info(
            "Sent text message tenant={} to={} wa_id={}",
            tenant.slug, payload.to, wa_id,
        )
        return SendResponse(
            message_id=record.id,
            wa_message_id=wa_id,
            status=record.status,
            to=payload.to,
        )

    async def send_template(self, payload: SendTemplateRequest) -> SendResponse:
        tenant = await self.tenants.resolve(payload.tenant_id)
        await self.tenants.assert_quota(tenant)

        if not await self.rate_limiter.acquire(tenant.phone_number_id, payload.to):
            raise RateLimitExceededError()

        components = self._build_template_components(payload)

        record = Message(
            tenant_id=tenant.id,
            direction=MessageDirection.outbound,
            recipient_phone=payload.to,
            sender_phone=tenant.phone_number_id,
            message_type=MessageType.template,
            template_name=payload.template_name,
            template_language=payload.language_code,
            content={
                "template_name": payload.template_name,
                "language_code": payload.language_code,
                "components": components,
            },
            status=MessageStatus.queued,
        )
        self.session.add(record)
        await self.session.flush()

        try:
            response = await self._client_for(tenant).send_template(
                to=payload.to,
                template_name=payload.template_name,
                language_code=payload.language_code,
                components=components or None,
            )
        except Exception as exc:  # noqa: BLE001
            record.status = MessageStatus.failed
            record.failed_at = datetime.utcnow()
            record.error_message = str(exc)
            await self.session.flush()
            logger.error(
                "send_template failed tenant={} template={} to={}: {}",
                tenant.slug, payload.template_name, payload.to, exc,
            )
            raise

        wa_id = response["messages"][0]["id"]
        record.wa_message_id = wa_id
        record.status = MessageStatus.sent
        record.sent_at = datetime.utcnow()
        await self.session.flush()

        await self.tenants.increment_usage(tenant.id)

        logger.info(
            "Sent template tenant={} template={} to={} wa_id={}",
            tenant.slug, payload.template_name, payload.to, wa_id,
        )
        return SendResponse(
            message_id=record.id,
            wa_message_id=wa_id,
            status=record.status,
            to=payload.to,
        )

    # ---------------------------------------------------------------- queries

    async def get(self, message_id: uuid.UUID) -> Message:
        message = await self.session.get(Message, message_id)
        if message is None:
            raise NotFoundError("Message not found", error_code="message_not_found")
        return message

    async def get_by_wa_id(self, wa_message_id: str) -> Message | None:
        result = await self.session.execute(
            select(Message).where(Message.wa_message_id == wa_message_id)
        )
        return result.scalar_one_or_none()
