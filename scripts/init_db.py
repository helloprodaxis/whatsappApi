"""One-shot DB bootstrap: run migrations to head, then seed default tenant.

Usage:
    python -m scripts.init_db
"""
from __future__ import annotations

import asyncio
import subprocess
import sys

from src.logger import logger, setup_logging


def _run_migrations() -> None:
    logger.info("Running alembic upgrade head")
    proc = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        check=False,
    )
    if proc.returncode != 0:
        raise SystemExit(f"alembic exited with {proc.returncode}")


async def _seed() -> None:
    from scripts.seed_data import main as seed_main

    await seed_main()


def main() -> None:
    setup_logging()
    _run_migrations()
    asyncio.run(_seed())
    logger.info("Database initialized.")


if __name__ == "__main__":
    main()
