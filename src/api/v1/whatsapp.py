"""WhatsApp message endpoints."""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import AuthContext, authenticate, db_session
from src.models.message import Message, MessageStatus
from src.schemas.common import Paginated
from src.schemas.message import (
    MessageOut,
    MessageStatusOut,
    SendResponse,
    SendTemplateRequest,
    SendTextRequest,
)
from src.services.message_service import MessageService
from src.utils.pagination import paginate

router = APIRouter(prefix="/messages", tags=["messages"])


@router.post(
    "/send/text",
    response_model=SendResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Send a free-form text message (only works inside the 24h customer service window)",
)
async def send_text(
    payload: SendTextRequest,
    session: AsyncSession = Depends(db_session),
    ctx: AuthContext = Depends(authenticate),
) -> SendResponse:
    if not ctx.has_scope("send_text"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API key not authorized for free-form text messages",
        )
    service = MessageService(session)
    result = await service.send_text(payload)
    await session.commit()
    return result


@router.post(
    "/send/template",
    response_model=SendResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Send an approved template message (works any time to opted-in users)",
)
async def send_template(
    payload: SendTemplateRequest,
    session: AsyncSession = Depends(db_session),
    ctx: AuthContext = Depends(authenticate),
) -> SendResponse:
    if not ctx.has_scope("send_template"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API key not authorized to send templates",
        )
    if not ctx.template_allowed(payload.template_name):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Template '{payload.template_name}' is not in this key's allowlist. "
                f"Allowed: {ctx.allowed_templates}"
            ),
        )
    service = MessageService(session)
    result = await service.send_template(payload)
    await session.commit()
    return result


@router.get(
    "",
    response_model=Paginated[MessageOut],
    summary="List messages with filtering and pagination",
)
async def list_messages(
    tenant_id: uuid.UUID | None = Query(default=None),
    recipient_phone: str | None = Query(default=None),
    status_filter: MessageStatus | None = Query(default=None, alias="status"),
    from_date: datetime | None = Query(default=None),
    to_date: datetime | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
    session: AsyncSession = Depends(db_session),
) -> Paginated[MessageOut]:
    stmt = select(Message)
    if tenant_id is not None:
        stmt = stmt.where(Message.tenant_id == tenant_id)
    if recipient_phone:
        stmt = stmt.where(Message.recipient_phone == recipient_phone)
    if status_filter is not None:
        stmt = stmt.where(Message.status == status_filter)
    if from_date is not None:
        stmt = stmt.where(Message.created_at >= from_date)
    if to_date is not None:
        stmt = stmt.where(Message.created_at <= to_date)
    stmt = stmt.order_by(Message.created_at.desc())

    page_result = await paginate(session, stmt, page=page, page_size=page_size)
    page_result.items = [MessageOut.model_validate(m) for m in page_result.items]
    return page_result


@router.get(
    "/{message_id}",
    response_model=MessageOut,
    summary="Fetch a message by internal id",
)
async def get_message(
    message_id: uuid.UUID,
    session: AsyncSession = Depends(db_session),
) -> MessageOut:
    service = MessageService(session)
    return MessageOut.model_validate(await service.get(message_id))


@router.get(
    "/{wa_message_id}/status",
    response_model=MessageStatusOut,
    summary="Latest status by Meta wamid",
)
async def get_status_by_wa_id(
    wa_message_id: str,
    session: AsyncSession = Depends(db_session),
) -> MessageStatusOut:
    service = MessageService(session)
    message = await service.get_by_wa_id(wa_message_id)
    if message is None:
        from src.exceptions import NotFoundError

        raise NotFoundError("Message not found", error_code="message_not_found")
    return MessageStatusOut(
        id=message.id,
        wa_message_id=message.wa_message_id,
        status=message.status,
        sent_at=message.sent_at,
        delivered_at=message.delivered_at,
        read_at=message.read_at,
        failed_at=message.failed_at,
        error_code=message.error_code,
        error_message=message.error_message,
    )
