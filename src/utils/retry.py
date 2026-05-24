"""Async exponential-backoff retry helper used by the Meta HTTP client."""
from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable
from typing import TypeVar

from src.logger import logger

T = TypeVar("T")


async def with_retry(
    fn: Callable[[], Awaitable[T]],
    *,
    attempts: int = 3,
    base_delay: float = 0.5,
    max_delay: float = 8.0,
    retry_on: tuple[type[BaseException], ...] = (Exception,),
    label: str = "operation",
) -> T:
    """Execute ``fn`` with exponential backoff + jitter.

    Raises the last exception if all attempts fail.
    """
    last_exc: BaseException | None = None
    for attempt in range(1, attempts + 1):
        try:
            return await fn()
        except retry_on as exc:
            last_exc = exc
            if attempt == attempts:
                logger.warning(
                    "{} failed after {} attempts: {}", label, attempts, exc
                )
                raise
            delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
            delay += random.uniform(0, delay * 0.25)
            logger.warning(
                "{} attempt {}/{} failed ({}): retrying in {:.2f}s",
                label, attempt, attempts, exc, delay,
            )
            await asyncio.sleep(delay)

    if last_exc:
        raise last_exc
    raise RuntimeError("with_retry exited without result")
