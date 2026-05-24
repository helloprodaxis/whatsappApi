"""Async HTTP client for the Meta WhatsApp Cloud API.

Wraps the small set of Graph endpoints we use:
- POST /{phone_number_id}/messages       — send text/template/media
- POST /{message_id}                     — mark_as_read
- GET  /{phone_number_id}                — phone number metadata
- GET  /{waba_id}/message_templates      — list templates

All calls are retried on transient (5xx + connection) failures with
exponential backoff. 4xx responses are surfaced as typed exceptions.
"""
from __future__ import annotations

from typing import Any

import httpx

from src.config import settings
from src.exceptions import (
    MetaAuthError,
    MetaError,
    MetaInvalidRequestError,
    MetaRateLimitError,
    MetaServerError,
)
from src.logger import logger
from src.utils.phone import to_meta_format
from src.utils.retry import with_retry


class WhatsAppClient:
    """Stateless async client. One instance per (token, phone_number_id) pair."""

    def __init__(
        self,
        access_token: str,
        phone_number_id: str,
        api_version: str | None = None,
        base_url: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.access_token = access_token
        self.phone_number_id = phone_number_id
        self.api_version = api_version or settings.META_API_VERSION
        self.base_url = (base_url or settings.META_API_BASE_URL).rstrip("/")
        self.timeout = timeout

    # ---------------------------------------------------------------- helpers

    @property
    def _root(self) -> str:
        return f"{self.base_url}/{self.api_version}"

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    async def _request(
        self,
        method: str,
        url: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        async def _do() -> dict[str, Any]:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                logger.debug("Meta API {} {}", method, url)
                resp = await client.request(
                    method, url, json=json, params=params, headers=self._headers
                )
                self._raise_for_status(resp)
                if resp.status_code == 204 or not resp.content:
                    return {}
                return resp.json()

        return await with_retry(
            _do,
            attempts=3,
            base_delay=0.5,
            retry_on=(MetaServerError, httpx.TransportError, httpx.TimeoutException),
            label=f"meta.{method.lower()}",
        )

    @staticmethod
    def _raise_for_status(resp: httpx.Response) -> None:
        if resp.status_code < 400:
            return

        try:
            payload = resp.json()
        except ValueError:
            payload = {"raw": resp.text}

        err = (payload or {}).get("error", payload) if isinstance(payload, dict) else {}
        code = err.get("code") if isinstance(err, dict) else None
        msg = (err.get("message") if isinstance(err, dict) else None) or resp.text

        details = {"meta_error": err, "status_code": resp.status_code}
        logger.warning("Meta API error {}: {}", resp.status_code, msg)

        if resp.status_code == 401 or code == 190:
            raise MetaAuthError(msg, details=details)
        if resp.status_code == 429 or code in (4, 80007, 130429, 131048, 131056):
            raise MetaRateLimitError(msg, details=details)
        if 400 <= resp.status_code < 500:
            raise MetaInvalidRequestError(msg, details=details, status_code=resp.status_code)
        if 500 <= resp.status_code:
            raise MetaServerError(msg, details=details)
        raise MetaError(msg, details=details, status_code=resp.status_code)

    # ---------------------------------------------------------------- sends

    async def send_text(
        self,
        to: str,
        text: str,
        *,
        preview_url: bool = False,
    ) -> dict[str, Any]:
        body = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_meta_format(to),
            "type": "text",
            "text": {"preview_url": preview_url, "body": text},
        }
        return await self._request(
            "POST", f"{self._root}/{self.phone_number_id}/messages", json=body
        )

    async def send_template(
        self,
        to: str,
        template_name: str,
        language_code: str = "en_US",
        components: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_meta_format(to),
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language_code},
            },
        }
        if components:
            body["template"]["components"] = components
        return await self._request(
            "POST", f"{self._root}/{self.phone_number_id}/messages", json=body
        )

    async def send_image(
        self,
        to: str,
        image_url: str,
        caption: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "messaging_product": "whatsapp",
            "to": to_meta_format(to),
            "type": "image",
            "image": {"link": image_url},
        }
        if caption:
            body["image"]["caption"] = caption
        return await self._request(
            "POST", f"{self._root}/{self.phone_number_id}/messages", json=body
        )

    async def send_document(
        self,
        to: str,
        document_url: str,
        filename: str,
        caption: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "messaging_product": "whatsapp",
            "to": to_meta_format(to),
            "type": "document",
            "document": {"link": document_url, "filename": filename},
        }
        if caption:
            body["document"]["caption"] = caption
        return await self._request(
            "POST", f"{self._root}/{self.phone_number_id}/messages", json=body
        )

    async def mark_as_read(self, wa_message_id: str) -> dict[str, Any]:
        body = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": wa_message_id,
        }
        return await self._request(
            "POST", f"{self._root}/{self.phone_number_id}/messages", json=body
        )

    # ---------------------------------------------------------------- reads

    async def get_phone_number_info(self) -> dict[str, Any]:
        return await self._request("GET", f"{self._root}/{self.phone_number_id}")

    async def get_templates(self, waba_id: str, limit: int = 200) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        url = f"{self._root}/{waba_id}/message_templates"
        params: dict[str, Any] | None = {"limit": limit}
        while True:
            data = await self._request("GET", url, params=params)
            results.extend(data.get("data", []))
            next_url = data.get("paging", {}).get("next")
            if not next_url:
                break
            url = next_url
            params = None
        return results
