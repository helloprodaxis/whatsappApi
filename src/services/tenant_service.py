"""Tenant CRUD and lookup helpers."""
from __future__ import annotations

import uuid
from datetime import datetime

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.exceptions import ConflictError, TenantNotFoundError, TenantQuotaExceededError
from src.logger import logger
from src.models.tenant import Tenant


class TenantService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self._fernet: Fernet | None = None
        if settings.ENCRYPTION_KEY:
            try:
                self._fernet = Fernet(settings.ENCRYPTION_KEY.encode())
            except (ValueError, InvalidToken):
                logger.warning("ENCRYPTION_KEY set but invalid — token storage will be plaintext")

    # ---------------------------------------------------------------- crypto

    def encrypt(self, plaintext: str) -> str:
        if not self._fernet:
            return plaintext
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        if not self._fernet:
            return ciphertext
        try:
            return self._fernet.decrypt(ciphertext.encode()).decode()
        except InvalidToken:
            return ciphertext

    # ---------------------------------------------------------------- crud

    async def get(self, tenant_id: uuid.UUID) -> Tenant:
        tenant = await self.session.get(Tenant, tenant_id)
        if tenant is None or tenant.deleted_at is not None:
            raise TenantNotFoundError()
        return tenant

    async def get_by_slug(self, slug: str) -> Tenant | None:
        result = await self.session.execute(
            select(Tenant).where(Tenant.slug == slug, Tenant.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def get_by_phone_number_id(self, phone_number_id: str) -> Tenant | None:
        result = await self.session.execute(
            select(Tenant).where(
                Tenant.phone_number_id == phone_number_id, Tenant.deleted_at.is_(None)
            )
        )
        return result.scalar_one_or_none()

    async def get_by_waba_id(self, waba_id: str) -> Tenant | None:
        result = await self.session.execute(
            select(Tenant).where(Tenant.waba_id == waba_id, Tenant.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def get_default(self) -> Tenant:
        """Return the default Prodaxis tenant (used in single-tenant mode)."""
        tenant = await self.get_by_slug(settings.DEFAULT_TENANT_SLUG)
        if tenant is None:
            raise TenantNotFoundError("Default tenant not seeded — run scripts/seed_data.py")
        return tenant

    async def resolve(self, tenant_id: uuid.UUID | None) -> Tenant:
        """Return the explicit tenant, or the default in single-tenant mode."""
        if tenant_id is not None:
            return await self.get(tenant_id)
        return await self.get_default()

    async def list_active(self) -> list[Tenant]:
        result = await self.session.execute(
            select(Tenant).where(Tenant.deleted_at.is_(None)).order_by(Tenant.created_at)
        )
        return list(result.scalars().all())

    async def create(
        self,
        *,
        name: str,
        slug: str,
        waba_id: str,
        phone_number_id: str,
        access_token: str,
        plan: str = "starter",
        monthly_message_limit: int = 5_000,
    ) -> Tenant:
        if await self.get_by_slug(slug):
            raise ConflictError(f"Tenant slug '{slug}' already exists")

        tenant = Tenant(
            name=name,
            slug=slug,
            waba_id=waba_id,
            phone_number_id=phone_number_id,
            access_token=self.encrypt(access_token),
            plan=plan,  # type: ignore[arg-type]
            monthly_message_limit=monthly_message_limit,
        )
        self.session.add(tenant)
        await self.session.flush()
        await self.session.refresh(tenant)
        logger.info("Created tenant {} ({})", tenant.slug, tenant.id)
        return tenant

    async def update(self, tenant_id: uuid.UUID, **fields: object) -> Tenant:
        tenant = await self.get(tenant_id)
        for key, value in fields.items():
            if value is None:
                continue
            if key == "access_token" and isinstance(value, str):
                value = self.encrypt(value)
            setattr(tenant, key, value)
        await self.session.flush()
        await self.session.refresh(tenant)
        return tenant

    async def soft_delete(self, tenant_id: uuid.UUID) -> None:
        tenant = await self.get(tenant_id)
        tenant.deleted_at = datetime.utcnow()
        tenant.is_active = False
        await self.session.flush()

    async def assert_quota(self, tenant: Tenant) -> None:
        if tenant.messages_sent_this_month >= tenant.monthly_message_limit:
            raise TenantQuotaExceededError()

    async def increment_usage(self, tenant_id: uuid.UUID, count: int = 1) -> None:
        tenant = await self.session.get(Tenant, tenant_id)
        if tenant is None:
            return
        tenant.messages_sent_this_month = (tenant.messages_sent_this_month or 0) + count
        await self.session.flush()
