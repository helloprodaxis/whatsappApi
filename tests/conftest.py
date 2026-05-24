"""Pytest fixtures.

These tests are designed to run without a real Meta token by mocking the
WhatsAppClient. The DB layer is exercised against an in-memory SQLite for
fast, isolated unit-level coverage; integration tests targeting Postgres
should set TEST_DATABASE_URL.
"""
from __future__ import annotations

import os

# Force test-friendly env BEFORE importing src.* so settings cache hot
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("APP_DEBUG", "True")
os.environ.setdefault("SECRET_KEY", "test-secret-key-min-16-chars-long-xyz")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
os.environ.setdefault("META_APP_ID", "test-app-id")
os.environ.setdefault("META_APP_SECRET", "test-secret")
os.environ.setdefault("META_WABA_ID", "test-waba")
os.environ.setdefault("META_PHONE_NUMBER_ID", "test-phone-id")
os.environ.setdefault("META_ACCESS_TOKEN", "test-token")
os.environ.setdefault("META_WEBHOOK_VERIFY_TOKEN", "test-verify-token")
os.environ.setdefault("API_KEY", "")

import asyncio
from collections.abc import AsyncGenerator
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def app() -> AsyncGenerator[Any, None]:
    """Build the FastAPI app once per test (lifespan runs)."""
    from src.main import create_app

    application = create_app()
    yield application


@pytest_asyncio.fixture
async def client(app) -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
