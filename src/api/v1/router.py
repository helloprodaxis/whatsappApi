"""Top-level API v1 router — composes the per-resource routers."""
from __future__ import annotations

from fastapi import APIRouter

from src.api.v1 import admin, campaigns, health, templates, tenants, webhooks, whatsapp

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(whatsapp.router)
api_router.include_router(templates.router)
api_router.include_router(campaigns.router)
api_router.include_router(webhooks.router)
api_router.include_router(tenants.router)
api_router.include_router(admin.router)
