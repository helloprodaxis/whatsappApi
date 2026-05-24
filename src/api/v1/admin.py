"""Admin endpoints — gated by the env-level admin API key.

Surface kept tiny on purpose: mint, list, revoke client keys. Hidden from
the public Swagger schema (include_in_schema=False) so clients hitting
whatsapp.prodaxis.in/docs only see message-sending endpoints.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import db_session, require_admin
from src.auth import generate_key
from src.models.api_key import ApiKey
from src.schemas.api_key import ApiKeyCreate, ApiKeyCreated, ApiKeyOut
from src.services.tenant_service import TenantService

router = APIRouter(
    prefix="/admin/api-keys",
    tags=["admin"],
    include_in_schema=False,
    dependencies=[Depends(require_admin)],
)


@router.post(
    "",
    response_model=ApiKeyCreated,
    status_code=status.HTTP_201_CREATED,
    summary="Mint a new client API key (plaintext returned once)",
)
async def create_api_key(
    payload: ApiKeyCreate,
    session: AsyncSession = Depends(db_session),
) -> ApiKeyCreated:
    tenants = TenantService(session)
    tenant = await tenants.resolve(payload.tenant_id)

    plaintext, prefix, key_hash = generate_key()

    expires_at: datetime | None = None
    if payload.expires_in_days:
        expires_at = datetime.now(tz=timezone.utc) + timedelta(days=payload.expires_in_days)

    record = ApiKey(
        tenant_id=tenant.id,
        key_hash=key_hash,
        key_prefix=prefix,
        label=payload.label,
        allowed_templates=payload.allowed_templates,
        allowed_scopes=payload.allowed_scopes,
        rate_limit_per_hour=payload.rate_limit_per_hour,
        expires_at=expires_at,
        is_active=True,
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)

    return ApiKeyCreated(
        id=record.id,
        tenant_id=record.tenant_id,
        key_prefix=record.key_prefix,
        label=record.label,
        allowed_templates=record.allowed_templates,
        allowed_scopes=list(record.allowed_scopes or []),
        rate_limit_per_hour=record.rate_limit_per_hour,
        is_active=record.is_active,
        expires_at=record.expires_at,
        last_used_at=record.last_used_at,
        revoked_at=record.revoked_at,
        created_at=record.created_at,
        plaintext_key=plaintext,
    )


@router.get("", response_model=list[ApiKeyOut], summary="List client API keys")
async def list_api_keys(
    session: AsyncSession = Depends(db_session),
) -> list[ApiKeyOut]:
    result = await session.execute(select(ApiKey).order_by(ApiKey.created_at.desc()))
    return [ApiKeyOut.model_validate(r) for r in result.scalars().all()]


@router.post("/{api_key_id}/revoke", response_model=ApiKeyOut, summary="Revoke a client API key")
async def revoke_api_key(
    api_key_id: uuid.UUID,
    session: AsyncSession = Depends(db_session),
) -> ApiKeyOut:
    record = await session.get(ApiKey, api_key_id)
    if record is None:
        raise HTTPException(status_code=404, detail="API key not found")
    record.is_active = False
    record.revoked_at = datetime.now(tz=timezone.utc)
    await session.commit()
    await session.refresh(record)
    return ApiKeyOut.model_validate(record)
