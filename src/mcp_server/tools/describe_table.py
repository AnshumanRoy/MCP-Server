from __future__ import annotations

import time
from typing import Any

from ..db import DatabaseAdapter
from ..safety import audit_logger
from .base import error_response, structured_output


def register(mcp, adapter: DatabaseAdapter) -> None:
    @mcp.tool(
        name="describe_table",
        description=(
            "Return the full structure of a table: columns, types, nullability, "
            "primary key, and indexes. Call this before run_query so you know the "
            "exact column names and types to reference in SQL."
        ),
    )
    async def describe_table(table: str) -> dict[str, Any]:
        start = time.time()
        try:
            info = adapter.describe_table(table)
        except Exception as exc:  # noqa: BLE001
            cols = [c["name"] for c in adapter.get_tables()]
            suggestion = None
            close = None
            for c in cols:
                if c.lower() == table.lower():
                    close = c
                    break
            if close:
                suggestion = f"No such table '{table}'; did you mean '{close}'?"
            return error_response(str(exc), suggestion)
        duration_ms = (time.time() - start) * 1000
        audit_logger.log("mcp", "describe_table", "", duration_ms, 1, False)
        return structured_output(
            columns=["name", "type", "nullable", "primary_key"],
            rows=info["columns"],
            row_count=len(info["columns"]),
            extra={"table": info["table"], "indexes": info["indexes"]},
            execution_ms=duration_ms,
        )
