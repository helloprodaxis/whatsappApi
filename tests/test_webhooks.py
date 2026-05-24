"""Tests for webhook signature verification and the verify-handshake endpoint."""
from __future__ import annotations

import hashlib
import hmac
import json

import pytest

from src.config import settings
from src.services.webhook_service import verify_signature


def _sign(body: bytes) -> str:
    digest = hmac.new(
        settings.META_APP_SECRET.encode(), body, hashlib.sha256
    ).hexdigest()
    return f"sha256={digest}"


# ---------------------------------------------------------------- signature

def test_verify_signature_valid():
    body = b'{"foo":"bar"}'
    assert verify_signature(body, _sign(body)) is True


def test_verify_signature_missing_header():
    assert verify_signature(b"{}", None) is False


def test_verify_signature_wrong_secret():
    body = b'{"foo":"bar"}'
    bad = "sha256=" + hmac.new(b"WRONG", body, hashlib.sha256).hexdigest()
    assert verify_signature(body, bad) is False


def test_verify_signature_malformed_header():
    assert verify_signature(b"{}", "not-a-signature") is False


# ---------------------------------------------------------------- handshake

@pytest.mark.asyncio
async def test_webhook_get_verification_success(client):
    resp = await client.get(
        "/api/v1/webhooks/whatsapp",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": settings.META_WEBHOOK_VERIFY_TOKEN,
            "hub.challenge": "challenge-abc",
        },
    )
    assert resp.status_code == 200
    assert resp.text == "challenge-abc"


@pytest.mark.asyncio
async def test_webhook_get_verification_wrong_token(client):
    resp = await client.get(
        "/api/v1/webhooks/whatsapp",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "wrong",
            "hub.challenge": "challenge-abc",
        },
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_webhook_post_rejects_unsigned(client):
    payload = {"object": "whatsapp_business_account", "entry": []}
    resp = await client.post("/api/v1/webhooks/whatsapp", json=payload)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_webhook_post_rejects_bad_signature(client):
    body = json.dumps({"object": "whatsapp_business_account", "entry": []}).encode()
    resp = await client.post(
        "/api/v1/webhooks/whatsapp",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": "sha256=deadbeef",
        },
    )
    assert resp.status_code == 401
