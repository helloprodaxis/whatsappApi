"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-07 00:00:00

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---- enums ----
    # `create_type=False` prevents auto re-creation when the enum is
    # referenced by a CREATE TABLE; we explicitly create them once below
    # with `checkfirst=True` so the migration is idempotent across re-runs.
    tenant_plan = postgresql.ENUM(
        "starter", "growth", "pro", "enterprise", name="tenant_plan", create_type=False
    )
    msg_direction = postgresql.ENUM(
        "outbound", "inbound", name="message_direction", create_type=False
    )
    msg_type = postgresql.ENUM(
        "text", "template", "image", "document", "audio", "video",
        "interactive", "location", "contacts", "reaction", "sticker", "unsupported",
        name="message_type", create_type=False,
    )
    msg_status = postgresql.ENUM(
        "queued", "sent", "delivered", "read", "failed",
        name="message_status", create_type=False,
    )
    tpl_category = postgresql.ENUM(
        "utility", "marketing", "authentication",
        name="template_category", create_type=False,
    )
    tpl_status = postgresql.ENUM(
        "pending", "approved", "rejected", "paused", "disabled",
        name="template_status", create_type=False,
    )
    cmp_status = postgresql.ENUM(
        "draft", "scheduled", "running", "paused", "completed", "failed", "cancelled",
        name="campaign_status", create_type=False,
    )
    cmp_recipient_status = postgresql.ENUM(
        "queued", "sending", "sent", "delivered", "read", "failed", "skipped",
        name="campaign_recipient_status", create_type=False,
    )

    bind = op.get_bind()
    for enum in (
        tenant_plan, msg_direction, msg_type, msg_status, tpl_category,
        tpl_status, cmp_status, cmp_recipient_status,
    ):
        enum.create(bind, checkfirst=True)

    # ---- tenants ----
    op.create_table(
        "tenants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("waba_id", sa.String(length=64), nullable=False),
        sa.Column("phone_number_id", sa.String(length=64), nullable=False),
        sa.Column("access_token", sa.String(length=2048), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("plan", tenant_plan, nullable=False, server_default="starter"),
        sa.Column("monthly_message_limit", sa.BigInteger(), nullable=False, server_default="5000"),
        sa.Column("messages_sent_this_month", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_tenants_slug", "tenants", ["slug"], unique=True)
    op.create_index("ix_tenants_waba_id", "tenants", ["waba_id"])
    op.create_index("ix_tenants_phone_number_id", "tenants", ["phone_number_id"])
    op.create_index("ix_tenants_deleted_at", "tenants", ["deleted_at"])

    # ---- templates ----
    op.create_table(
        "templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("language", sa.String(length=20), nullable=False),
        sa.Column("category", tpl_category, nullable=False),
        sa.Column("status", tpl_status, nullable=False, server_default="pending"),
        sa.Column("components", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("meta_template_id", sa.String(length=64), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "name", "language", name="uq_templates_tenant_name_lang"),
    )
    op.create_index("ix_templates_tenant_id", "templates", ["tenant_id"])
    op.create_index("ix_templates_name", "templates", ["name"])
    op.create_index("ix_templates_meta_template_id", "templates", ["meta_template_id"])

    # ---- campaigns ----
    op.create_table(
        "campaigns",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("template_name", sa.String(length=150), nullable=False),
        sa.Column("template_language", sa.String(length=20), nullable=False),
        sa.Column("total_recipients", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sent_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("delivered_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("read_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", cmp_status, nullable=False, server_default="draft"),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_log", postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_campaigns_tenant_id", "campaigns", ["tenant_id"])
    op.create_index("ix_campaigns_status", "campaigns", ["status"])

    # ---- campaign_recipients ----
    op.create_table(
        "campaign_recipients",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column("variables", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("status", cmp_recipient_status, nullable=False, server_default="queued"),
        sa.Column("wa_message_id", sa.String(length=128), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_campaign_recipients_campaign_id", "campaign_recipients", ["campaign_id"])
    op.create_index("ix_campaign_recipients_wa_message_id", "campaign_recipients", ["wa_message_id"])
    op.create_index(
        "ix_campaign_recipients_campaign_status",
        "campaign_recipients",
        ["campaign_id", "status"],
    )

    # ---- messages ----
    op.create_table(
        "messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("direction", msg_direction, nullable=False),
        sa.Column("wa_message_id", sa.String(length=128), nullable=True),
        sa.Column("recipient_phone", sa.String(length=20), nullable=False),
        sa.Column("sender_phone", sa.String(length=20), nullable=False),
        sa.Column("message_type", msg_type, nullable=False),
        sa.Column("content", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("template_name", sa.String(length=150), nullable=True),
        sa.Column("template_language", sa.String(length=20), nullable=True),
        sa.Column("status", msg_status, nullable=False, server_default="queued"),
        sa.Column("error_code", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("meta_pricing", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("campaign_recipient_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_messages_tenant_id", "messages", ["tenant_id"])
    op.create_index("ix_messages_direction", "messages", ["direction"])
    op.create_index("ix_messages_wa_message_id", "messages", ["wa_message_id"])
    op.create_index("ix_messages_status", "messages", ["status"])
    op.create_index("ix_messages_campaign_recipient_id", "messages", ["campaign_recipient_id"])
    op.create_index("ix_messages_tenant_created", "messages", ["tenant_id", "created_at"])
    op.create_index("ix_messages_tenant_status", "messages", ["tenant_id", "status"])
    op.create_index("ix_messages_recipient", "messages", ["recipient_phone"])

    # ---- webhook_events ----
    op.create_table(
        "webhook_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="SET NULL"), nullable=True),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("processed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_webhook_events_tenant_id", "webhook_events", ["tenant_id"])
    op.create_index("ix_webhook_events_event_type", "webhook_events", ["event_type"])
    op.create_index("ix_webhook_events_processed", "webhook_events", ["processed"])
    op.create_index("ix_webhook_events_created_at", "webhook_events", ["created_at"])

    # ---- contacts ----
    op.create_table(
        "contacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=True),
        sa.Column("email", sa.String(length=254), nullable=True),
        sa.Column("attributes", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("opted_in", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("opted_in_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("opted_out_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "phone", name="uq_contacts_tenant_phone"),
    )
    op.create_index("ix_contacts_tenant_id", "contacts", ["tenant_id"])
    op.create_index("ix_contacts_phone", "contacts", ["phone"])


def downgrade() -> None:
    op.drop_index("ix_contacts_phone", table_name="contacts")
    op.drop_index("ix_contacts_tenant_id", table_name="contacts")
    op.drop_table("contacts")

    op.drop_index("ix_webhook_events_created_at", table_name="webhook_events")
    op.drop_index("ix_webhook_events_processed", table_name="webhook_events")
    op.drop_index("ix_webhook_events_event_type", table_name="webhook_events")
    op.drop_index("ix_webhook_events_tenant_id", table_name="webhook_events")
    op.drop_table("webhook_events")

    op.drop_index("ix_messages_recipient", table_name="messages")
    op.drop_index("ix_messages_tenant_status", table_name="messages")
    op.drop_index("ix_messages_tenant_created", table_name="messages")
    op.drop_index("ix_messages_campaign_recipient_id", table_name="messages")
    op.drop_index("ix_messages_status", table_name="messages")
    op.drop_index("ix_messages_wa_message_id", table_name="messages")
    op.drop_index("ix_messages_direction", table_name="messages")
    op.drop_index("ix_messages_tenant_id", table_name="messages")
    op.drop_table("messages")

    op.drop_index("ix_campaign_recipients_campaign_status", table_name="campaign_recipients")
    op.drop_index("ix_campaign_recipients_wa_message_id", table_name="campaign_recipients")
    op.drop_index("ix_campaign_recipients_campaign_id", table_name="campaign_recipients")
    op.drop_table("campaign_recipients")

    op.drop_index("ix_campaigns_status", table_name="campaigns")
    op.drop_index("ix_campaigns_tenant_id", table_name="campaigns")
    op.drop_table("campaigns")

    op.drop_index("ix_templates_meta_template_id", table_name="templates")
    op.drop_index("ix_templates_name", table_name="templates")
    op.drop_index("ix_templates_tenant_id", table_name="templates")
    op.drop_table("templates")

    op.drop_index("ix_tenants_deleted_at", table_name="tenants")
    op.drop_index("ix_tenants_phone_number_id", table_name="tenants")
    op.drop_index("ix_tenants_waba_id", table_name="tenants")
    op.drop_index("ix_tenants_slug", table_name="tenants")
    op.drop_table("tenants")

    for enum_name in (
        "campaign_recipient_status", "campaign_status", "template_status",
        "template_category", "message_status", "message_type",
        "message_direction", "tenant_plan",
    ):
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")
