"""Vercel Python runtime entry point.

Vercel's `@vercel/python` builder looks for an `app` ASGI callable in
`api/index.py` (or any file under /api/). All requests are routed here
via the rewrite rule in vercel.json.
"""
from __future__ import annotations

from src.main import app

__all__ = ["app"]
