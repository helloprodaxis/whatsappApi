"""Bulk-send campaign endpoints."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import db_session, require_api_key
from src.exceptions import ValidationError
from src.models.campaign import CampaignRecipientStatus
from src.schemas.campaign import (
    CampaignActionResponse,
    CampaignCreate,
    CampaignOut,
    CampaignRecipientOut,
    CampaignUploadResponse,
)
from src.schemas.common import Paginated
from src.services.campaign_service import CampaignService
from src.services.tenant_service import TenantService

router = APIRouter(
    prefix="/campaigns",
    tags=["campaigns"],
    dependencies=[Depends(require_api_key)],
    include_in_schema=False,
)


@router.post(
    "",
    response_model=CampaignOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a draft campaign",
)
async def create_campaign(
    payload: CampaignCreate,
    session: AsyncSession = Depends(db_session),
) -> CampaignOut:
    service = CampaignService(session)
    campaign = await service.create(payload)
    await session.commit()
    return CampaignOut.model_validate(campaign)


@router.get(
    "",
    response_model=list[CampaignOut],
    summary="List campaigns for a tenant",
)
async def list_campaigns(
    tenant_id: uuid.UUID | None = Query(default=None),
    session: AsyncSession = Depends(db_session),
) -> list[CampaignOut]:
    tenants = TenantService(session)
    tenant = await tenants.resolve(tenant_id)
    service = CampaignService(session)
    campaigns = await service.list_for_tenant(tenant.id)
    return [CampaignOut.model_validate(c) for c in campaigns]


@router.get(
    "/{campaign_id}",
    response_model=CampaignOut,
    summary="Get one campaign with progress stats",
)
async def get_campaign(
    campaign_id: uuid.UUID,
    session: AsyncSession = Depends(db_session),
) -> CampaignOut:
    service = CampaignService(session)
    return CampaignOut.model_validate(await service.get(campaign_id))


@router.post(
    "/{campaign_id}/recipients/upload",
    response_model=CampaignUploadResponse,
    summary="Upload recipients via CSV (columns: phone, var_1, var_2, ...)",
)
async def upload_recipients(
    campaign_id: uuid.UUID,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(db_session),
) -> CampaignUploadResponse:
    if file.content_type not in {"text/csv", "application/vnd.ms-excel", "application/octet-stream", None}:
        raise ValidationError(
            f"Unsupported content type: {file.content_type}",
            error_code="invalid_content_type",
        )
    csv_bytes = await file.read()
    service = CampaignService(session)
    result = await service.upload_recipients(campaign_id, csv_bytes)
    await session.commit()
    return result


@router.post(
    "/{campaign_id}/start",
    response_model=CampaignActionResponse,
    summary="Start a campaign — enqueues all recipients to Celery",
)
async def start_campaign(
    campaign_id: uuid.UUID,
    session: AsyncSession = Depends(db_session),
) -> CampaignActionResponse:
    service = CampaignService(session)
    campaign = await service.start(campaign_id)
    await session.commit()
    return CampaignActionResponse(
        campaign_id=campaign.id, status=campaign.status, message="Campaign started"
    )


@router.post(
    "/{campaign_id}/pause",
    response_model=CampaignActionResponse,
    summary="Pause a running campaign",
)
async def pause_campaign(
    campaign_id: uuid.UUID,
    session: AsyncSession = Depends(db_session),
) -> CampaignActionResponse:
    service = CampaignService(session)
    campaign = await service.pause(campaign_id)
    await session.commit()
    return CampaignActionResponse(
        campaign_id=campaign.id, status=campaign.status, message="Campaign paused"
    )


@router.post(
    "/{campaign_id}/resume",
    response_model=CampaignActionResponse,
    summary="Resume a paused campaign",
)
async def resume_campaign(
    campaign_id: uuid.UUID,
    session: AsyncSession = Depends(db_session),
) -> CampaignActionResponse:
    service = CampaignService(session)
    campaign = await service.resume(campaign_id)
    await session.commit()
    return CampaignActionResponse(
        campaign_id=campaign.id, status=campaign.status, message="Campaign resumed"
    )


@router.post(
    "/{campaign_id}/cancel",
    response_model=CampaignActionResponse,
    summary="Cancel a campaign (no further sends will happen)",
)
async def cancel_campaign(
    campaign_id: uuid.UUID,
    session: AsyncSession = Depends(db_session),
) -> CampaignActionResponse:
    service = CampaignService(session)
    campaign = await service.cancel(campaign_id)
    await session.commit()
    return CampaignActionResponse(
        campaign_id=campaign.id, status=campaign.status, message="Campaign cancelled"
    )


@router.get(
    "/{campaign_id}/recipients",
    response_model=Paginated[CampaignRecipientOut],
    summary="Paginated recipient list with delivery state",
)
async def list_recipients(
    campaign_id: uuid.UUID,
    status_filter: CampaignRecipientStatus | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
    session: AsyncSession = Depends(db_session),
) -> Paginated[CampaignRecipientOut]:
    import math

    service = CampaignService(session)
    rows, total = await service.list_recipients(
        campaign_id, status=status_filter, page=page, page_size=page_size
    )
    pages = max(1, math.ceil(total / page_size)) if total else 0
    return Paginated[CampaignRecipientOut](
        items=[CampaignRecipientOut.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )
