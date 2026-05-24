"""Standalone Meta send test — proves the env config works.

Usage:
    python -m scripts.send_test_message <recipient_phone> [template_name]

Defaults:
    template_name = "hello_world"
    language_code = "en_US"

This script does NOT require the API server to be running. It calls Meta
directly using the credentials in your .env.
"""
from __future__ import annotations

import asyncio
import sys

from src.config import settings
from src.logger import logger, setup_logging
from src.services.whatsapp_client import WhatsAppClient
from src.utils.phone import normalize_phone


async def _run(recipient: str, template_name: str, language: str) -> None:
    client = WhatsAppClient(
        access_token=settings.META_ACCESS_TOKEN,
        phone_number_id=settings.META_PHONE_NUMBER_ID,
    )
    to = normalize_phone(recipient)
    logger.info("Sending '{}' ({}) to {}", template_name, language, to)
    response = await client.send_template(
        to=to, template_name=template_name, language_code=language
    )
    logger.info("Meta response: {}", response)
    wa_id = response.get("messages", [{}])[0].get("id", "<no id>")
    logger.info("✅ Sent. wamid={}", wa_id)


def main() -> None:
    setup_logging()
    if len(sys.argv) < 2:
        print("Usage: python -m scripts.send_test_message <phone> [template] [language]")
        sys.exit(1)

    recipient = sys.argv[1]
    template_name = sys.argv[2] if len(sys.argv) > 2 else "hello_world"
    language = sys.argv[3] if len(sys.argv) > 3 else "en_US"

    asyncio.run(_run(recipient, template_name, language))


if __name__ == "__main__":
    main()
