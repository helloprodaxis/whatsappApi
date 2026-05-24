"""One-off: send a template that has a single {{1}} body variable.

Usage:
    python -m scripts.send_template_with_param <phone> <template_name> <value_for_{{1}}>
"""
from __future__ import annotations

import asyncio
import sys

from src.config import settings
from src.logger import logger, setup_logging
from src.services.whatsapp_client import WhatsAppClient
from src.utils.phone import normalize_phone


async def _run(recipient: str, template_name: str, param_value: str) -> None:
    client = WhatsAppClient(
        access_token=settings.META_ACCESS_TOKEN,
        phone_number_id=settings.META_PHONE_NUMBER_ID,
    )
    components = [
        {
            "type": "body",
            "parameters": [{"type": "text", "text": param_value}],
        }
    ]
    response = await client.send_template(
        to=normalize_phone(recipient),
        template_name=template_name,
        language_code="en_US",
        components=components,
    )
    logger.info("Meta response: {}", response)
    wa_id = response.get("messages", [{}])[0].get("id", "<no id>")
    logger.info("Sent. wamid={}", wa_id)


def main() -> None:
    setup_logging()
    if len(sys.argv) < 4:
        print("Usage: python -m scripts.send_template_with_param <phone> <template> <{{1}} value>")
        sys.exit(1)
    asyncio.run(_run(sys.argv[1], sys.argv[2], sys.argv[3]))


if __name__ == "__main__":
    main()
