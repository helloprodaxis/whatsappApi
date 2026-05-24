"""Shared FastAPI dependencies."""
from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_session


async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_session():
        yield session


async def require_api_key():
    """Compat shim — re-exports the real authenticate dep from src.auth.

    Importing it from here would create a circular import (src.auth itself
    depends on db_session). Callers should prefer ``src.auth.authenticate``
    or ``src.auth.require_admin`` directly.
    """
    raise RuntimeError(
        "Import src.auth.authenticate / src.auth.require_admin instead of "
        "src.dependencies.require_api_key — kept only for backwards compatibility."
    )
