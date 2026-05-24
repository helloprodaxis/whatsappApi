"""Seed the default Prodaxis tenant if no tenant exists.

Idempotent — running twice is safe.

Usage:
    python -m scripts.seed_data
"""
from __future__ import annotations

import asyncio

from sqlalchemy import select

from src.config import settings
from src.database import session_scope
from src.logger import logger, setup_logging
from src.models.tenant import Tenant, TenantPlan
from src.services.tenant_service import TenantService


async def main() -> None:
    async with session_scope() as session:
        existing = (
            await session.execute(
                select(Tenant).where(Tenant.slug == settings.DEFAULT_TENANT_SLUG)
            )
        ).scalar_one_or_none()

        if existing:
            logger.info(
                "Default tenant '{}' already exists (id={}) — skipping seed",
                existing.slug, existing.id,
            )
            return

        service = TenantService(session)
        tenant = await service.create(
            name=settings.DEFAULT_TENANT_NAME,
            slug=settings.DEFAULT_TENANT_SLUG,
            waba_id=settings.META_WABA_ID,
            phone_number_id=settings.META_PHONE_NUMBER_ID,
            access_token=settings.META_ACCESS_TOKEN,
            plan=TenantPlan.enterprise.value,
            monthly_message_limit=1_000_000,
        )
        logger.info("Seeded default tenant '{}' (id={})", tenant.slug, tenant.id)


if __name__ == "__main__":
    setup_logging()
    asyncio.run(main())
