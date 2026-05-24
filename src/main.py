"""FastAPI application entrypoint.

Wires up:
- Loguru-based structured logging
- Sentry (when DSN provided)
- CORS, request ID, request-logging, slowapi rate limit middlewares
- Domain exception handlers
- API v1 router
- Lifespan startup/shutdown hooks
"""
from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from src.api.v1.router import api_router
from src.config import settings
from src.database import check_db_connection, close_db
from src.exceptions import ProdaxisError
from src.logger import logger, setup_logging
from src.redis_client import check_redis_connection, close_redis


def _init_sentry() -> None:
    if not settings.SENTRY_DSN:
        return
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration

        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            environment=settings.SENTRY_ENVIRONMENT,
            traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
            integrations=[StarletteIntegration(), FastApiIntegration()],
            send_default_pii=False,
        )
        logger.info("Sentry initialized")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Sentry init skipped: {}", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    _init_sentry()
    logger.info(
        "Starting {} v{} env={} debug={}",
        settings.APP_NAME, settings.APP_VERSION, settings.APP_ENV, settings.APP_DEBUG,
    )

    db_ok = await check_db_connection()
    redis_ok = await check_redis_connection()
    logger.info("Startup probes: db={} redis={}", db_ok, redis_ok)

    if not db_ok and settings.is_production:
        logger.error("Database is unreachable on startup — failing fast")

    yield

    logger.info("Shutting down — closing connections")
    await close_db()
    await close_redis()


limiter = Limiter(key_func=get_remote_address, default_limits=["1000/minute"])


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=(
            "Production WhatsApp Business Platform for Prodaxis. "
            "Send single + bulk messages via Meta Cloud API, receive webhooks, "
            "manage templates and tenants. Multi-tenant ready."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
        debug=settings.APP_DEBUG,
    )

    # ---- middleware ----
    app.state.limiter = limiter
    app.add_middleware(SlowAPIMiddleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        start = time.perf_counter()

        with logger.contextualize(request_id=request_id, path=request.url.path):
            try:
                response = await call_next(request)
            except Exception as exc:  # noqa: BLE001
                duration_ms = int((time.perf_counter() - start) * 1000)
                logger.exception(
                    "Unhandled exception path={} duration_ms={}: {}",
                    request.url.path, duration_ms, exc,
                )
                raise
            duration_ms = int((time.perf_counter() - start) * 1000)
            response.headers["X-Request-ID"] = request_id
            logger.info(
                "{} {} -> {} ({}ms)",
                request.method, request.url.path, response.status_code, duration_ms,
            )
            return response

    # ---- exception handlers ----
    @app.exception_handler(ProdaxisError)
    async def handle_domain_error(request: Request, exc: ProdaxisError):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error_code": exc.error_code,
                "message": exc.message,
                "details": exc.details,
                "request_id": request.headers.get("X-Request-ID"),
            },
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error_code": "validation_error",
                "message": "Request validation failed",
                "details": {"errors": exc.errors()},
                "request_id": request.headers.get("X-Request-ID"),
            },
        )

    @app.exception_handler(RateLimitExceeded)
    async def handle_rate_limit(request: Request, exc: RateLimitExceeded):
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "error_code": "api_rate_limit",
                "message": "Too many requests",
                "details": {"limit": str(exc.detail)},
                "request_id": request.headers.get("X-Request-ID"),
            },
        )

    # ---- routes ----
    app.include_router(api_router)

    @app.get("/", tags=["root"], summary="Welcome banner")
    async def root() -> dict[str, str]:
        return {
            "name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "environment": settings.APP_ENV,
            "docs": "/docs",
        }

    return app


app = create_app()
