from __future__ import annotations

import time
from typing import Any

from ..db import DatabaseAdapter
from ..safety import audit_logger
from .base import structured_output


def register(mcp, adapter: DatabaseAdapter) -> None:
    @mcp.tool(
        name="list_tables",
        description=(
            "List tables (and optionally views) in the database. Returns each "
            "table's name, type, and approximate row count. Call this first to "
            "discover what data is available before describing or querying a table."
        ),
    )
    async def list_tables(
        schema: str | None = None,
        include_views: bool = False,
    ) -> dict[str, Any]:
        start = time.time()
        tables = adapter.get_tables(include_views=include_views)
        # SQLite doesn't have multiple schemas in the same sense; ignore schema
        # param but accept it for interface compatibility.
        duration_ms = (time.time() - start) * 1000
        audit_logger.log("mcp", "list_tables", "", duration_ms, len(tables), False)
        return structured_output(
            columns=["name", "type", "row_count"],
            rows=tables,
            execution_ms=duration_ms,
        )
