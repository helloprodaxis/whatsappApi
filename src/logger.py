"""Centralized Loguru logging with structured JSON in production.

- INFO/DEBUG/WARNING go to stdout.
- ERROR/CRITICAL go to stdout AND a rotating file.
- Sensitive fields (tokens, passwords) are masked before serialization.
"""
from __future__ import annotations

import logging
import os
import re
import sys
from pathlib import Path
from typing import Any

from loguru import logger

from src.config import settings


def _is_serverless() -> bool:
    """True on Vercel/Lambda-style runtimes where the FS is read-only."""
    return bool(os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))

_SENSITIVE_PATTERNS = [
    (re.compile(r'(access_token["\']?\s*[:=]\s*["\']?)([^"\'&\s,}]+)', re.I), r"\1***MASKED***"),
    (re.compile(r'(api_key["\']?\s*[:=]\s*["\']?)([^"\'&\s,}]+)', re.I), r"\1***MASKED***"),
    (re.compile(r'(authorization["\']?\s*:\s*["\']?bearer\s+)([^"\'&\s,}]+)', re.I), r"\1***MASKED***"),
    (re.compile(r'(password["\']?\s*[:=]\s*["\']?)([^"\'&\s,}]+)', re.I), r"\1***MASKED***"),
    (re.compile(r'(secret["\']?\s*[:=]\s*["\']?)([^"\'&\s,}]+)', re.I), r"\1***MASKED***"),
    (re.compile(r"(EAA[A-Za-z0-9]{20,})"), r"EAA***MASKED***"),
]


def _mask(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    masked = value
    for pattern, replacement in _SENSITIVE_PATTERNS:
        masked = pattern.sub(replacement, masked)
    return masked


def _patcher(record: dict[str, Any]) -> None:
    record["message"] = _mask(record["message"])
    if record.get("extra"):
        record["extra"] = {k: _mask(v) for k, v in record["extra"].items()}


class InterceptHandler(logging.Handler):
    """Route stdlib logging (uvicorn, sqlalchemy, etc.) into Loguru."""

    def emit(self, record: logging.LogRecord) -> None:  # pragma: no cover
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def setup_logging() -> None:
    """Configure Loguru sinks based on APP_ENV / LOG_FORMAT."""
    logger.remove()
    logger.configure(patcher=_patcher)

    # enqueue=True spawns a multiprocessing.SimpleQueue, which needs /dev/shm
    # for POSIX semaphores — that's not available on AWS Lambda / Vercel.
    use_enqueue = not _is_serverless()

    if settings.LOG_FORMAT == "json":
        logger.add(
            sys.stdout,
            level=settings.LOG_LEVEL,
            serialize=True,
            backtrace=False,
            diagnose=False,
            enqueue=use_enqueue,
        )
    else:
        logger.add(
            sys.stdout,
            level=settings.LOG_LEVEL,
            colorize=True,
            backtrace=settings.APP_DEBUG,
            diagnose=settings.APP_DEBUG,
            format=(
                "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
                "<level>{level: <8}</level> | "
                "<cyan>{name}:{function}:{line}</cyan> | "
                "<level>{message}</level>"
            ),
            enqueue=use_enqueue,
        )

    if not _is_serverless():
        log_path = Path(settings.LOG_FILE_PATH)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        logger.add(
            str(log_path),
            level="INFO",
            rotation=settings.LOG_ROTATION,
            retention=settings.LOG_RETENTION,
            compression="zip",
            serialize=settings.LOG_FORMAT == "json",
            enqueue=True,
            backtrace=False,
            diagnose=False,
        )

    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
    for noisy in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi", "sqlalchemy.engine"):
        logging.getLogger(noisy).handlers = [InterceptHandler()]
        logging.getLogger(noisy).propagate = False


__all__ = ["logger", "setup_logging"]
