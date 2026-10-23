from __future__ import annotations

import time
from typing import Any

from ..db import DatabaseAdapter
from ..safety import audit_logger
from .base import structured_output


def register(mcp, adapter: DatabaseAdapter) -> None:
    @mcp.tool(
        name="search_schema",
        description=(
            "Keyword search across table and column names. Useful on large "
            "schemas to find relevant tables without listing everything."
        ),
    )
    async def search_schema(keyword: str) -> dict[str, Any]:
        start = time.time()
        matches = adapter.search_schema(keyword)
        duration_ms = (time.time() - start) * 1000
        audit_logger.log("mcp", "search_schema", "", duration_ms, len(matches), False)
        return structured_output(
            columns=["table", "column", "type"],
            rows=matches,
            row_count=len(matches),
            execution_ms=duration_ms,
        )
