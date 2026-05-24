"""Token-bucket rate limiter backed by Redis.

Two limits are enforced per Meta's documented quotas:
1. Per-phone-number-id: ``META_MAX_MESSAGES_PER_SECOND`` (default 80/sec).
2. Per-(phone_number_id, recipient): 1 message per 6 seconds with a burst
   of ``META_MAX_BURST_PER_RECIPIENT`` (default 45) before back-pressure.

The implementation uses Redis INCR + EXPIRE for cheap counter buckets.
"""
from __future__ import annotations

from src.config import settings
from src.logger import logger
from src.redis_client import get_redis


class RateLimiter:
    def __init__(
        self,
        max_per_second: int | None = None,
        max_burst_per_recipient: int | None = None,
        recipient_window_seconds: int = 6,
    ) -> None:
        self.max_per_second = max_per_second or settings.META_MAX_MESSAGES_PER_SECOND
        self.max_burst_per_recipient = (
            max_burst_per_recipient or settings.META_MAX_BURST_PER_RECIPIENT
        )
        self.recipient_window = recipient_window_seconds

    async def acquire(self, phone_number_id: str, recipient: str) -> bool:
        """Return True if the message may be sent right now, else False.

        Fails open: if Redis is unreachable, allow the send through. Meta itself
        enforces hard quota — our limiter is a soft pre-check, not the source
        of truth.
        """
        client = get_redis()

        try:
            sec_key = f"prodaxis:rl:phone:{phone_number_id}:sec"
            sec_count = await client.incr(sec_key)
            if sec_count == 1:
                await client.expire(sec_key, 1)
            if sec_count > self.max_per_second:
                logger.debug("Rate limit hit on phone {} ({}/s)", phone_number_id, sec_count)
                return False

            recip_key = f"prodaxis:rl:recip:{phone_number_id}:{recipient}"
            recip_count = await client.incr(recip_key)
            if recip_count == 1:
                await client.expire(recip_key, self.recipient_window)
            if recip_count > self.max_burst_per_recipient:
                logger.debug(
                    "Recipient burst limit hit {} -> {} ({}/{}s)",
                    phone_number_id, recipient, recip_count, self.recipient_window,
                )
                return False

            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("Rate limiter Redis error, failing open: {}", exc)
            return True

    async def reset_recipient(self, phone_number_id: str, recipient: str) -> None:
        client = get_redis()
        await client.delete(f"prodaxis:rl:recip:{phone_number_id}:{recipient}")
