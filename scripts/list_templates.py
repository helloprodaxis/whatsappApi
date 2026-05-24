"""List all WhatsApp templates registered under your WABA.

Reads credentials from .env. No DB or server required.

Usage:
    py -m scripts.list_templates
"""
from __future__ import annotations

import asyncio

from src.config import settings
from src.logger import setup_logging
from src.services.whatsapp_client import WhatsAppClient


async def main() -> None:
    client = WhatsAppClient(
        access_token=settings.META_ACCESS_TOKEN,
        phone_number_id=settings.META_PHONE_NUMBER_ID,
    )
    templates = await client.get_templates(settings.META_WABA_ID)

    if not templates:
        print("\nNo templates found for this WABA.")
        return

    print(f"\nFound {len(templates)} template(s) on WABA {settings.META_WABA_ID}:\n")
    print(f"{'NAME':<35} {'LANG':<10} {'STATUS':<12} {'CATEGORY':<16}")
    print("-" * 80)
    for t in templates:
        name = (t.get("name") or "")[:34]
        lang = (t.get("language") or "")[:9]
        status = (t.get("status") or "")[:11]
        category = (t.get("category") or "")[:15]
        print(f"{name:<35} {lang:<10} {status:<12} {category:<16}")
    print()

    approved = [t for t in templates if (t.get("status") or "").upper() == "APPROVED"]
    if approved:
        print(f"✅ {len(approved)} APPROVED — usable for sending right now.")
        print("\nTry:")
        first = approved[0]
        print(
            f"  py -m scripts.send_test_message +91YOURNUMBER {first.get('name')} {first.get('language')}"
        )
    else:
        print("⚠️  No APPROVED templates yet. Submit one in WhatsApp Manager first.")


if __name__ == "__main__":
    setup_logging()
    asyncio.run(main())
