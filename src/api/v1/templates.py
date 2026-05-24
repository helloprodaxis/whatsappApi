"""Template management endpoints."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import db_session, require_api_key
from src.models.template import TemplateStatus
from src.schemas.template import TemplateOut, TemplateSyncRequest, TemplateSyncResponse
from src.services.template_service import TemplateService
from src.services.tenant_service import TenantService

router = APIRouter(prefix="/templates", tags=["templates"], dependencies=[Depends(require_api_key)])


@router.get(
    "",
    response_model=list[TemplateOut],
    summary="List templates for a tenant",
)
async def list_templates(
    tenant_id: uuid.UUID | None = Query(default=None),
    status_filter: TemplateStatus | None = Query(default=None, alias="status"),
    session: AsyncSession = Depends(db_session),
) -> list[TemplateOut]:
    tenants = TenantService(session)
    tenant = await tenants.resolve(tenant_id)
    service = TemplateService(session)
    items = await service.list_for_tenant(tenant.id, status=status_filter)
    return [TemplateOut.model_validate(t) for t in items]


@router.post(
    "/sync",
    response_model=TemplateSyncResponse,
    summary="Force a sync of templates from Meta into our local cache",
    include_in_schema=False,
)
async def sync_templates(
    payload: TemplateSyncRequest,
    session: AsyncSession = Depends(db_session),
) -> TemplateSyncResponse:
    service = TemplateService(session)
    result = await service.sync_from_meta(payload.tenant_id)
    await session.commit()
    return result


@router.get(
    "/{template_name}",
    response_model=TemplateOut,
    summary="Get a single template by name",
)
async def get_template(
    template_name: str,
    tenant_id: uuid.UUID | None = Query(default=None),
    language: str = Query(default="en_US"),
    session: AsyncSession = Depends(db_session),
) -> TemplateOut:
    tenants = TenantService(session)
    tenant = await tenants.resolve(tenant_id)
    service = TemplateService(session)
    template = await service.get_by_name(tenant.id, template_name, language)
    return TemplateOut.model_validate(template)
