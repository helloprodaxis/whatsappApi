"""Send free-form text inside an open 24h customer service window.

Usage:
    python -m scripts.send_text <phone> "<message body>"
"""
from __future__ import annotations

import asyncio
import sys

from src.config import settings
from src.logger import logger, setup_logging
from src.services.whatsapp_client import WhatsAppClient
from src.utils.phone import normalize_phone


async def _run(recipient: str, body: str) -> None:
    client = WhatsAppClient(
        access_token=settings.META_ACCESS_TOKEN,
        phone_number_id=settings.META_PHONE_NUMBER_ID,
    )
    response = await client.send_text(to=normalize_phone(recipient), text=body)
    logger.info("Meta response: {}", response)
    wa_id = response.get("messages", [{}])[0].get("id", "<no id>")
    logger.info("Sent. wamid={}", wa_id)


def main() -> None:
    setup_logging()
    if len(sys.argv) < 3:
        print('Usage: python -m scripts.send_text <phone> "<message body>"')
        sys.exit(1)
    asyncio.run(_run(sys.argv[1], sys.argv[2]))


if __name__ == "__main__":
    main()
