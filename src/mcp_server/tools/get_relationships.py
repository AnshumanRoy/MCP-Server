from __future__ import annotations

import time
from typing import Any

from ..db import DatabaseAdapter
from ..safety import audit_logger
from .base import error_response, structured_output


def register(mcp, adapter: DatabaseAdapter) -> None:
    @mcp.tool(
        name="get_relationships",
        description=(
            "Return foreign keys for a table, both outgoing (this table -> other) "
            "and incoming (other -> this table), so the model can plan joins."
        ),
    )
    async def get_relationships(table: str) -> dict[str, Any]:
        start = time.time()
        try:
            rel = adapter.get_foreign_keys(table)
        except Exception as exc:  # noqa: BLE001
            return error_response(str(exc))
        duration_ms = (time.time() - start) * 1000
        audit_logger.log("mcp", "get_relationships", "", duration_ms, 1, False)
        rows = [{"direction": "outgoing", **o} for o in rel["outgoing"]] + [
            {"direction": "incoming", **i} for i in rel["incoming"]
        ]
        return structured_output(
            columns=[
                "direction",
                "column",
                "target_table",
                "target_column",
                "source_table",
                "source_column",
            ],
            rows=rows,
            row_count=len(rows),
            execution_ms=duration_ms,
        )
