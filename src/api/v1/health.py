"""Health probes — used by orchestrators and the dashboard."""
from __future__ import annotations

from fastapi import APIRouter, status

from src.config import settings
from src.database import check_db_connection
from src.redis_client import check_redis_connection
from src.schemas.common import HealthStatus

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", response_model=HealthStatus)
async def healthcheck() -> HealthStatus:
    """Aggregate readiness — DB + Redis."""
    db_ok = await check_db_connection()
    redis_ok = await check_redis_connection()
    overall = "ok" if (db_ok and redis_ok) else "degraded"
    return HealthStatus(
        status=overall,
        version=settings.APP_VERSION,
        environment=settings.APP_ENV,
        db="ok" if db_ok else "unreachable",
        redis="ok" if redis_ok else "unreachable",
        celery=None,
    )


@router.get("/live", status_code=status.HTTP_200_OK)
async def liveness() -> dict[str, str]:
    """Process is alive (used by container/k8s liveness probes)."""
    return {"status": "alive"}


@router.get("/ready", status_code=status.HTTP_200_OK)
async def readiness() -> dict[str, str]:
    """Ready to serve traffic — DB connection works."""
    db_ok = await check_db_connection()
    if not db_ok:
        return {"status": "not_ready"}
    return {"status": "ready"}
