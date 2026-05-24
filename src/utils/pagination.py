"""Pagination helpers for SQLAlchemy queries."""
from __future__ import annotations

import math
from typing import TypeVar

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.schemas.common import Paginated

T = TypeVar("T")


async def paginate(
    session: AsyncSession,
    stmt: Select,
    *,
    page: int = 1,
    page_size: int = 50,
) -> Paginated:
    """Run ``stmt`` and ``count(*)`` to produce a Paginated envelope."""
    page = max(1, page)
    page_size = max(1, min(page_size, 500))

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await session.execute(count_stmt)).scalar_one()

    offset = (page - 1) * page_size
    items_stmt = stmt.limit(page_size).offset(offset)
    items = (await session.execute(items_stmt)).scalars().all()

    pages = max(1, math.ceil(total / page_size)) if total else 0

    return Paginated(
        items=list(items),
        total=int(total),
        page=page,
        page_size=page_size,
        pages=pages,
    )
