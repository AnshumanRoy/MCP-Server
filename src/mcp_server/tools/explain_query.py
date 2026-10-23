from __future__ import annotations

import time
from typing import Any

from ..db import DatabaseAdapter
from ..safety import ValidationError, audit_logger, validate_sql
from .base import error_response, structured_output


def register(mcp, adapter: DatabaseAdapter) -> None:
    @mcp.tool(
        name="explain_query",
        description=(
            "Show the query plan for a SQL statement without executing it. Use "
            "this to check for full table scans or other inefficiencies before "
            "running a query."
        ),
    )
    async def explain_query(sql: str) -> dict[str, Any]:
        start = time.time()
        try:
            validate_sql(sql)
        except ValidationError as exc:
            return error_response(str(exc))
        try:
            plan = adapter.explain_query(sql)
        except Exception as exc:  # noqa: BLE001
            return error_response(str(exc))
        duration_ms = (time.time() - start) * 1000
        audit_logger.log("mcp", "explain_query", sql, duration_ms, 0, False)
        return structured_output(
            columns=["plan", "warnings"],
            rows=[
                {
                    "plan": plan["plan"],
                    "warnings": "; ".join(plan["warnings"]) if plan["warnings"] else "",
                }
            ],
            row_count=1,
            execution_ms=duration_ms,
        )
