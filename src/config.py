"""Application configuration loaded from environment via pydantic-settings."""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Type-safe settings container.

    All values are read from environment variables (case-insensitive) and
    fall back to a local `.env` file. Production deployments should set
    these via the platform's secret manager (Render env vars, etc.).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ----- Application -----
    APP_NAME: str = "Prodaxis WhatsApp Platform"
    APP_ENV: Literal["development", "staging", "production", "test"] = "development"
    APP_VERSION: str = "0.1.0"
    APP_PORT: int = 8000
    APP_HOST: str = "0.0.0.0"  # noqa: S104  (intentional bind-all in container)
    APP_DEBUG: bool = True
    APP_BASE_URL: str = "http://localhost:8000"

    # ----- Security -----
    SECRET_KEY: str = Field(min_length=16)
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440
    API_KEY: str | None = None

    # ----- Database -----
    DATABASE_URL: str
    DATABASE_ECHO: bool = False
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    TEST_DATABASE_URL: str | None = None

    # ----- Redis -----
    REDIS_URL: str
    REDIS_MAX_CONNECTIONS: int = 50

    # ----- Celery -----
    CELERY_BROKER_URL: str | None = None
    CELERY_RESULT_BACKEND: str | None = None
    CELERY_TASK_TIME_LIMIT: int = 300
    CELERY_TASK_SOFT_TIME_LIMIT: int = 270

    # ----- Meta WhatsApp Cloud API -----
    META_API_VERSION: str = "v22.0"
    META_API_BASE_URL: str = "https://graph.facebook.com"
    META_APP_ID: str
    META_APP_SECRET: str
    META_BUSINESS_PORTFOLIO_ID: str | None = None
    META_WABA_ID: str
    META_PHONE_NUMBER_ID: str
    META_ACCESS_TOKEN: str
    META_WEBHOOK_VERIFY_TOKEN: str

    # ----- Rate limiting (Meta enforced) -----
    META_MAX_MESSAGES_PER_SECOND: int = 80
    META_MAX_PER_RECIPIENT_PER_6_SECONDS: int = 1
    META_MAX_BURST_PER_RECIPIENT: int = 45

    # ----- Logging -----
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    LOG_FORMAT: Literal["json", "pretty"] = "json"
    LOG_FILE_PATH: str = "logs/prodaxis.log"
    LOG_ROTATION: str = "100 MB"
    LOG_RETENTION: str = "30 days"

    # ----- Sentry -----
    SENTRY_DSN: str | None = None
    SENTRY_ENVIRONMENT: str = "development"
    SENTRY_TRACES_SAMPLE_RATE: float = 0.1

    # ----- CORS -----
    CORS_ALLOWED_ORIGINS: str = "http://localhost:3000,https://prodaxis.in"

    # ----- Tenancy -----
    DEFAULT_TENANT_ID: str = "prodaxis-default"
    DEFAULT_TENANT_NAME: str = "Prodaxis"
    DEFAULT_TENANT_SLUG: str = "prodaxis"
    ENABLE_MULTI_TENANT: bool = False

    # ----- Encryption -----
    ENCRYPTION_KEY: str | None = None

    # ----- Derived -----
    @field_validator("CELERY_BROKER_URL", mode="before")
    @classmethod
    def _default_broker(cls, v: str | None, info) -> str | None:  # type: ignore[no-untyped-def]
        return v or info.data.get("REDIS_URL")

    @field_validator("CELERY_RESULT_BACKEND", mode="before")
    @classmethod
    def _default_backend(cls, v: str | None, info) -> str | None:  # type: ignore[no-untyped-def]
        return v or info.data.get("REDIS_URL")

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def is_development(self) -> bool:
        return self.APP_ENV == "development"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ALLOWED_ORIGINS.split(",") if o.strip()]

    @property
    def celery_broker(self) -> str:
        return self.CELERY_BROKER_URL or self.REDIS_URL

    @property
    def celery_backend(self) -> str:
        return self.CELERY_RESULT_BACKEND or self.REDIS_URL


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings instance (single source of truth)."""
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
