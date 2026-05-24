"""Template syncing — keeps a local cache of Meta-approved templates."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.exceptions import TemplateNotFoundError
from src.logger import logger
from src.models.template import Template, TemplateCategory, TemplateStatus
from src.models.tenant import Tenant
from src.schemas.template import TemplateSyncResponse
from src.services.tenant_service import TenantService
from src.services.whatsapp_client import WhatsAppClient


_CATEGORY_MAP = {
    "UTILITY": TemplateCategory.utility,
    "MARKETING": TemplateCategory.marketing,
    "AUTHENTICATION": TemplateCategory.authentication,
}

_STATUS_MAP = {
    "PENDING": TemplateStatus.pending,
    "APPROVED": TemplateStatus.approved,
    "REJECTED": TemplateStatus.rejected,
    "PAUSED": TemplateStatus.paused,
    "DISABLED": TemplateStatus.disabled,
}


class TemplateService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.tenants = TenantService(session)

    async def list_for_tenant(
        self,
        tenant_id: uuid.UUID,
        *,
        status: TemplateStatus | None = None,
    ) -> list[Template]:
        stmt = select(Template).where(Template.tenant_id == tenant_id)
        if status:
            stmt = stmt.where(Template.status == status)
        result = await self.session.execute(stmt.order_by(Template.name, Template.language))
        return list(result.scalars().all())

    async def get_by_name(
        self,
        tenant_id: uuid.UUID,
        name: str,
        language: str = "en_US",
    ) -> Template:
        result = await self.session.execute(
            select(Template).where(
                Template.tenant_id == tenant_id,
                Template.name == name,
                Template.language == language,
            )
        )
        template = result.scalar_one_or_none()
        if template is None:
            raise TemplateNotFoundError(f"Template '{name}' ({language}) not found")
        return template

    async def sync_from_meta(self, tenant_id: uuid.UUID | None = None) -> TemplateSyncResponse:
        tenant: Tenant = await self.tenants.resolve(tenant_id)
        client = WhatsAppClient(
            access_token=self.tenants.decrypt(tenant.access_token),
            phone_number_id=tenant.phone_number_id,
        )

        meta_templates = await client.get_templates(tenant.waba_id)
        logger.info("Fetched {} templates from Meta for tenant {}", len(meta_templates), tenant.slug)

        existing = {
            (t.name, t.language): t
            for t in await self.list_for_tenant(tenant.id)
        }

        created = updated = 0
        for raw in meta_templates:
            name = raw.get("name")
            language = raw.get("language", "en_US")
            if not name:
                continue

            category = _CATEGORY_MAP.get(
                (raw.get("category") or "").upper(), TemplateCategory.utility
            )
            status = _STATUS_MAP.get(
                (raw.get("status") or "").upper(), TemplateStatus.pending
            )
            components = raw.get("components") or []

            key = (name, language)
            if key in existing:
                tpl = existing[key]
                tpl.category = category
                tpl.status = status
                tpl.components = components
                tpl.meta_template_id = raw.get("id") or tpl.meta_template_id
                tpl.last_synced_at = datetime.utcnow()
                updated += 1
            else:
                tpl = Template(
                    tenant_id=tenant.id,
                    name=name,
                    language=language,
                    category=category,
                    status=status,
                    components=components,
                    meta_template_id=raw.get("id"),
                    last_synced_at=datetime.utcnow(),
                )
                self.session.add(tpl)
                created += 1

        await self.session.flush()
        return TemplateSyncResponse(
            synced=len(meta_templates),
            created=created,
            updated=updated,
            tenant_id=tenant.id,
        )
