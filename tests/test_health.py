"""Smoke tests for /health endpoints — no external services required."""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_root_banner(client):
    resp = await client.get("/")
    assert resp.status_code == 200
    body = resp.json()
    assert "name" in body
    assert "version" in body
    assert body["docs"] == "/docs"


@pytest.mark.asyncio
async def test_liveness(client):
    resp = await client.get("/api/v1/health/live")
    assert resp.status_code == 200
    assert resp.json() == {"status": "alive"}


@pytest.mark.asyncio
async def test_health_returns_json(client):
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] in {"ok", "degraded"}
    assert body["db"] in {"ok", "unreachable"}
    assert body["redis"] in {"ok", "unreachable"}
