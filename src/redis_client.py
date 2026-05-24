"""Async Redis client for rate limiting, caching and Celery backing."""
from __future__ import annotations

import redis.asyncio as redis_async

from src.config import settings

_pool: redis_async.ConnectionPool | None = None


def get_redis_pool() -> redis_async.ConnectionPool:
    """Lazy-init a process-wide connection pool."""
    global _pool
    if _pool is None:
        _pool = redis_async.ConnectionPool.from_url(
            settings.REDIS_URL,
            max_connections=settings.REDIS_MAX_CONNECTIONS,
            decode_responses=True,
        )
    return _pool


def get_redis() -> redis_async.Redis:
    """Return an async Redis client backed by the shared pool."""
    return redis_async.Redis(connection_pool=get_redis_pool())


async def check_redis_connection() -> bool:
    """Light Redis connectivity probe used by /health."""
    try:
        client = get_redis()
        pong = await client.ping()
        return bool(pong)
    except Exception:
        return False


async def close_redis() -> None:
    """Close the connection pool on shutdown."""
    global _pool
    if _pool is not None:
        await _pool.disconnect()
        _pool = None
