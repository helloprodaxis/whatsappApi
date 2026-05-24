"""Tenant model — each row is a Prodaxis client (or Prodaxis itself)."""
from __future__ import annotations

import enum
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, Enum as SAEnum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from src.models.campaign import Campaign
    from src.models.contact import Contact
    from src.models.message import Message
    from src.models.template import Template


class TenantPlan(str, enum.Enum):
    starter = "starter"
    growth = "growth"
    pro = "pro"
    enterprise = "enterprise"


class Tenant(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), nullable=False, unique=True, index=True)

    waba_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    phone_number_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    access_token: Mapped[str] = mapped_column(String(2048), nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    plan: Mapped[TenantPlan] = mapped_column(
        SAEnum(TenantPlan, name="tenant_plan"),
        default=TenantPlan.starter,
        nullable=False,
    )
    monthly_message_limit: Mapped[int] = mapped_column(BigInteger, default=5_000, nullable=False)
    messages_sent_this_month: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)

    messages: Mapped[list["Message"]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan", lazy="selectin"
    )
    templates: Mapped[list["Template"]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan", lazy="selectin"
    )
    campaigns: Mapped[list["Campaign"]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan", lazy="selectin"
    )
    contacts: Mapped[list["Contact"]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Tenant id={self.id} slug={self.slug!r}>"
