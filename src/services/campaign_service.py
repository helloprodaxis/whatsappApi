"""Bulk-campaign orchestration."""
from __future__ import annotations

import csv
import io
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.exceptions import (
    CampaignNotFoundError,
    ConflictError,
    TemplateNotFoundError,
    ValidationError,
)
from src.logger import logger
from src.models.campaign import (
    Campaign,
    CampaignRecipient,
    CampaignRecipientStatus,
    CampaignStatus,
)
from src.models.template import Template, TemplateStatus
from src.schemas.campaign import (
    CampaignCreate,
    CampaignUploadResponse,
)
from src.services.tenant_service import TenantService
from src.utils.phone import normalize_phone


class CampaignService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.tenants = TenantService(session)

    # ---------------------------------------------------------------- crud

    async def create(self, payload: CampaignCreate) -> Campaign:
        tenant = await self.tenants.resolve(payload.tenant_id)

        result = await self.session.execute(
            select(Template).where(
                Template.tenant_id == tenant.id,
                Template.name == payload.template_name,
                Template.language == payload.language_code,
            )
        )
        template = result.scalar_one_or_none()
        if template is None:
            raise TemplateNotFoundError(
                f"Template '{payload.template_name}' ({payload.language_code}) not found — "
                "run /api/v1/templates/sync first"
            )
        if template.status != TemplateStatus.approved:
            raise ValidationError(
                f"Template '{template.name}' is not approved (status={template.status.value})",
                error_code="template_not_approved",
            )

        campaign = Campaign(
            tenant_id=tenant.id,
            name=payload.name,
            template_name=payload.template_name,
            template_language=payload.language_code,
            scheduled_at=payload.scheduled_at,
            status=CampaignStatus.scheduled if payload.scheduled_at else CampaignStatus.draft,
        )
        self.session.add(campaign)
        await self.session.flush()
        await self.session.refresh(campaign)
        return campaign

    async def get(self, campaign_id: uuid.UUID) -> Campaign:
        campaign = await self.session.get(Campaign, campaign_id)
        if campaign is None:
            raise CampaignNotFoundError()
        return campaign

    async def list_for_tenant(self, tenant_id: uuid.UUID) -> list[Campaign]:
        result = await self.session.execute(
            select(Campaign).where(Campaign.tenant_id == tenant_id).order_by(Campaign.created_at.desc())
        )
        return list(result.scalars().all())

    # ---------------------------------------------------------------- upload

    async def upload_recipients(
        self,
        campaign_id: uuid.UUID,
        csv_bytes: bytes,
    ) -> CampaignUploadResponse:
        campaign = await self.get(campaign_id)
        if campaign.status not in {CampaignStatus.draft, CampaignStatus.scheduled}:
            raise ConflictError(
                f"Cannot upload recipients: campaign status is {campaign.status.value}"
            )

        text = csv_bytes.decode("utf-8-sig", errors="replace")
        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames or "phone" not in [f.lower() for f in reader.fieldnames]:
            raise ValidationError(
                "CSV must contain a 'phone' column",
                error_code="invalid_csv",
            )

        phone_field = next(f for f in reader.fieldnames if f.lower() == "phone")

        rows_parsed = 0
        rows_inserted = 0
        skip_reasons: list[str] = []

        seen: set[str] = set()
        for row in reader:
            rows_parsed += 1
            raw = (row.get(phone_field) or "").strip()
            if not raw:
                skip_reasons.append(f"row {rows_parsed}: empty phone")
                continue
            try:
                phone = normalize_phone(raw)
            except ValidationError as exc:
                skip_reasons.append(f"row {rows_parsed}: {exc.message}")
                continue
            if phone in seen:
                skip_reasons.append(f"row {rows_parsed}: duplicate phone {phone}")
                continue
            seen.add(phone)

            variables = {
                k: v for k, v in row.items() if k != phone_field and v is not None and v != ""
            }

            recipient = CampaignRecipient(
                campaign_id=campaign.id,
                phone=phone,
                variables=variables,
                status=CampaignRecipientStatus.queued,
            )
            self.session.add(recipient)
            rows_inserted += 1

        campaign.total_recipients = (campaign.total_recipients or 0) + rows_inserted
        await self.session.flush()

        logger.info(
            "Uploaded {} recipients ({} skipped) to campaign {}",
            rows_inserted, len(skip_reasons), campaign.id,
        )

        return CampaignUploadResponse(
            campaign_id=campaign.id,
            rows_parsed=rows_parsed,
            rows_inserted=rows_inserted,
            rows_skipped=len(skip_reasons),
            skip_reasons=skip_reasons[:50],  # cap response payload
        )

    # ---------------------------------------------------------------- lifecycle

    async def start(self, campaign_id: uuid.UUID) -> Campaign:
        campaign = await self.get(campaign_id)
        if campaign.status not in {CampaignStatus.draft, CampaignStatus.scheduled, CampaignStatus.paused}:
            raise ConflictError(f"Campaign cannot be started from status {campaign.status.value}")
        if campaign.total_recipients == 0:
            raise ConflictError("Campaign has no recipients — upload a CSV first")

        # Bulk dispatch was Celery-driven. Vercel has no background workers,
        # so this endpoint is intentionally a no-op in the serverless build.
        # Re-enable by moving the worker to Railway/Render or queuing through
        # Upstash QStash — see DEPLOY.md.
        raise ConflictError(
            "Campaign dispatch is disabled in this deployment. Use the single-message "
            "endpoints (POST /api/v1/messages/send/template) or run the worker stack."
        )

    async def pause(self, campaign_id: uuid.UUID) -> Campaign:
        campaign = await self.get(campaign_id)
        if campaign.status != CampaignStatus.running:
            raise ConflictError("Only running campaigns can be paused")
        campaign.status = CampaignStatus.paused
        await self.session.flush()
        return campaign

    async def resume(self, campaign_id: uuid.UUID) -> Campaign:
        campaign = await self.get(campaign_id)
        if campaign.status != CampaignStatus.paused:
            raise ConflictError("Only paused campaigns can be resumed")
        return await self.start(campaign_id)

    async def cancel(self, campaign_id: uuid.UUID) -> Campaign:
        campaign = await self.get(campaign_id)
        if campaign.status in {CampaignStatus.completed, CampaignStatus.cancelled}:
            return campaign
        campaign.status = CampaignStatus.cancelled
        campaign.completed_at = datetime.now(tz=timezone.utc)
        await self.session.flush()
        return campaign

    # ---------------------------------------------------------------- recipients

    async def list_recipients(
        self,
        campaign_id: uuid.UUID,
        *,
        status: CampaignRecipientStatus | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[CampaignRecipient], int]:
        from sqlalchemy import func

        stmt = select(CampaignRecipient).where(CampaignRecipient.campaign_id == campaign_id)
        if status:
            stmt = stmt.where(CampaignRecipient.status == status)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.session.execute(count_stmt)).scalar_one()

        offset = (max(1, page) - 1) * page_size
        stmt = stmt.order_by(CampaignRecipient.created_at).limit(page_size).offset(offset)
        rows = (await self.session.execute(stmt)).scalars().all()
        return list(rows), int(total)

    async def fetch_pending_recipients(
        self,
        campaign_id: uuid.UUID,
        limit: int = 200,
    ) -> list[CampaignRecipient]:
        result = await self.session.execute(
            select(CampaignRecipient)
            .where(
                CampaignRecipient.campaign_id == campaign_id,
                CampaignRecipient.status == CampaignRecipientStatus.queued,
            )
            .order_by(CampaignRecipient.created_at)
            .limit(limit)
        )
        return list(result.scalars().all())
