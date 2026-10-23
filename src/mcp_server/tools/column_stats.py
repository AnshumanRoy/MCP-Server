from __future__ import annotations

import time
from typing import Any

from ..db import DatabaseAdapter
from ..safety import audit_logger
from .base import error_response, structured_output


def register(mcp, adapter: DatabaseAdapter) -> None:
    @mcp.tool(
        name="column_stats",
        description=(
            "Return distinct count, null count, min/max, and top values for a "
            "single column. Helps the model write better filters."
        ),
    )
    async def column_stats(table: str, column: str) -> dict[str, Any]:
        start = time.time()
        try:
            stats = adapter.column_stats(table, column)
        except Exception as exc:  # noqa: BLE001
            return error_response(str(exc))
        duration_ms = (time.time() - start) * 1000
        audit_logger.log("mcp", "column_stats", "", duration_ms, 1, False)
        return structured_output(
            columns=["column", "distinct_count", "null_count", "min", "max"],
            rows=[stats],
            row_count=1,
            extra={"top_values": stats.get("top_values", [])},
            execution_ms=duration_ms,
        )
