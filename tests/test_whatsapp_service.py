"""Unit tests for WhatsAppClient and helpers (Meta API mocked)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.exceptions import (
    MetaAuthError,
    MetaInvalidRequestError,
    MetaRateLimitError,
)
from src.services.whatsapp_client import WhatsAppClient
from src.utils.phone import normalize_phone, to_meta_format


def _mock_response(status_code: int, json_data: dict | None = None) -> MagicMock:
    response = MagicMock(spec=httpx.Response)
    response.status_code = status_code
    response.content = b"x"
    response.text = ""
    response.json.return_value = json_data or {}
    return response


# ---------------------------------------------------------------- phone utils

def test_normalize_phone_indian_mobile():
    assert normalize_phone("9876543210") == "+919876543210"
    assert normalize_phone("+91 98765 43210") == "+919876543210"
    assert normalize_phone("919876543210") == "+919876543210"


def test_to_meta_format_strips_plus():
    assert to_meta_format("+919876543210") == "919876543210"


# ---------------------------------------------------------------- whatsapp client

@pytest.mark.asyncio
async def test_send_text_success():
    client = WhatsAppClient(access_token="t", phone_number_id="123")

    expected = {"messages": [{"id": "wamid.HBgL1234"}]}
    with patch("src.services.whatsapp_client.httpx.AsyncClient") as mock_class:
        instance = AsyncMock()
        instance.request.return_value = _mock_response(200, expected)
        mock_class.return_value.__aenter__.return_value = instance

        result = await client.send_text(to="+919876543210", text="Hi from tests")

    assert result == expected
    instance.request.assert_called_once()
    _, kwargs = instance.request.call_args
    assert kwargs["json"]["messaging_product"] == "whatsapp"
    assert kwargs["json"]["to"] == "919876543210"
    assert kwargs["json"]["type"] == "text"


@pytest.mark.asyncio
async def test_send_template_includes_components():
    client = WhatsAppClient(access_token="t", phone_number_id="123")

    expected = {"messages": [{"id": "wamid.tmpl"}]}
    components = [{"type": "body", "parameters": [{"type": "text", "text": "Sai"}]}]
    with patch("src.services.whatsapp_client.httpx.AsyncClient") as mock_class:
        instance = AsyncMock()
        instance.request.return_value = _mock_response(200, expected)
        mock_class.return_value.__aenter__.return_value = instance

        result = await client.send_template(
            to="+919876543210",
            template_name="hello_world",
            language_code="en_US",
            components=components,
        )

    assert result == expected
    _, kwargs = instance.request.call_args
    body = kwargs["json"]
    assert body["template"]["name"] == "hello_world"
    assert body["template"]["language"]["code"] == "en_US"
    assert body["template"]["components"] == components


@pytest.mark.asyncio
async def test_auth_error_surfaces_typed_exception():
    client = WhatsAppClient(access_token="bad", phone_number_id="123")
    error_payload = {"error": {"code": 190, "message": "Token expired"}}

    with patch("src.services.whatsapp_client.httpx.AsyncClient") as mock_class:
        instance = AsyncMock()
        instance.request.return_value = _mock_response(401, error_payload)
        mock_class.return_value.__aenter__.return_value = instance

        with pytest.raises(MetaAuthError):
            await client.send_text(to="+919876543210", text="hi")


@pytest.mark.asyncio
async def test_rate_limit_error_surfaces():
    client = WhatsAppClient(access_token="t", phone_number_id="123")
    error_payload = {"error": {"code": 130429, "message": "Rate limit"}}

    with patch("src.services.whatsapp_client.httpx.AsyncClient") as mock_class:
        instance = AsyncMock()
        instance.request.return_value = _mock_response(429, error_payload)
        mock_class.return_value.__aenter__.return_value = instance

        with pytest.raises(MetaRateLimitError):
            await client.send_text(to="+919876543210", text="hi")


@pytest.mark.asyncio
async def test_invalid_request_error_does_not_retry():
    client = WhatsAppClient(access_token="t", phone_number_id="123")
    error_payload = {"error": {"code": 100, "message": "Invalid template"}}

    with patch("src.services.whatsapp_client.httpx.AsyncClient") as mock_class:
        instance = AsyncMock()
        instance.request.return_value = _mock_response(400, error_payload)
        mock_class.return_value.__aenter__.return_value = instance

        with pytest.raises(MetaInvalidRequestError):
            await client.send_text(to="+919876543210", text="hi")

    # 4xx must not retry
    assert instance.request.call_count == 1
