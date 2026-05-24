"""Tenant management endpoints (gated by ENABLE_MULTI_TENANT)."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import db_session, require_api_key
from src.config import settings
from src.schemas.common import MessageEnvelope
from src.schemas.tenant import TenantCreate, TenantOut, TenantUpdate, TenantUsage
from src.services.tenant_service import TenantService

router = APIRouter(
    prefix="/tenants",
    tags=["tenants"],
    dependencies=[Depends(require_api_key)],
    include_in_schema=False,
)


def _ensure_multi_tenant() -> None:
    if not settings.ENABLE_MULTI_TENANT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Multi-tenant mode is disabled (set ENABLE_MULTI_TENANT=True)",
        )


@router.get("", response_model=list[TenantOut])
async def list_tenants(session: AsyncSession = Depends(db_session)) -> list[TenantOut]:
    service = TenantService(session)
    tenants = await service.list_active()
    return [TenantOut.model_validate(t) for t in tenants]


@router.post("", response_model=TenantOut, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    payload: TenantCreate,
    session: AsyncSession = Depends(db_session),
) -> TenantOut:
    _ensure_multi_tenant()
    service = TenantService(session)
    tenant = await service.create(
        name=payload.name,
        slug=payload.slug,
        waba_id=payload.waba_id,
        phone_number_id=payload.phone_number_id,
        access_token=payload.access_token,
        plan=payload.plan.value,
        monthly_message_limit=payload.monthly_message_limit,
    )
    await session.commit()
    return TenantOut.model_validate(tenant)


@router.get("/{tenant_id}", response_model=TenantOut)
async def get_tenant(
    tenant_id: uuid.UUID,
    session: AsyncSession = Depends(db_session),
) -> TenantOut:
    service = TenantService(session)
    return TenantOut.model_validate(await service.get(tenant_id))


@router.patch("/{tenant_id}", response_model=TenantOut)
async def update_tenant(
    tenant_id: uuid.UUID,
    payload: TenantUpdate,
    session: AsyncSession = Depends(db_session),
) -> TenantOut:
    _ensure_multi_tenant()
    service = TenantService(session)
    fields = payload.model_dump(exclude_unset=True)
    tenant = await service.update(tenant_id, **fields)
    await session.commit()
    return TenantOut.model_validate(tenant)


@router.delete("/{tenant_id}", response_model=MessageEnvelope)
async def delete_tenant(
    tenant_id: uuid.UUID,
    session: AsyncSession = Depends(db_session),
) -> MessageEnvelope:
    _ensure_multi_tenant()
    service = TenantService(session)
    await service.soft_delete(tenant_id)
    await session.commit()
    return MessageEnvelope(message=f"Tenant {tenant_id} soft-deleted")


@router.get("/{tenant_id}/usage", response_model=TenantUsage)
async def get_usage(
    tenant_id: uuid.UUID,
    session: AsyncSession = Depends(db_session),
) -> TenantUsage:
    service = TenantService(session)
    tenant = await service.get(tenant_id)
    remaining = max(0, tenant.monthly_message_limit - tenant.messages_sent_this_month)
    pct = (
        (tenant.messages_sent_this_month / tenant.monthly_message_limit) * 100
        if tenant.monthly_message_limit
        else 0.0
    )
    return TenantUsage(
        tenant_id=tenant.id,
        monthly_message_limit=tenant.monthly_message_limit,
        messages_sent_this_month=tenant.messages_sent_this_month,
        remaining=remaining,
        percent_used=round(pct, 2),
    )
