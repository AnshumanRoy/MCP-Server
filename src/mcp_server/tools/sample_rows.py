from __future__ import annotations

import time
from typing import Any

from ..config import settings
from ..db import DatabaseAdapter
from ..safety import audit_logger, mask_row
from .base import error_response, structured_output


def register(mcp, adapter: DatabaseAdapter) -> None:
    @mcp.tool(
        name="sample_rows",
        description=(
            "Return up to `limit` rows (capped at 10) from a table to show what "
            "the data looks like. Sensitive columns are masked. Use this to "
            "inspect data before writing a full query."
        ),
    )
    async def sample_rows(
        table: str,
        limit: int = 5,
        columns: list[str] | None = None,
    ) -> dict[str, Any]:
        start = time.time()
        try:
            limit = min(int(limit), settings.sample_row_limit)
            raw = adapter.sample_rows(table, limit=limit, columns=columns)
        except Exception as exc:  # noqa: BLE001
            return error_response(str(exc))
        masked_rows = [mask_row(raw["columns"], r) for r in raw["rows"]]
        duration_ms = (time.time() - start) * 1000
        audit_logger.log("mcp", "sample_rows", "", duration_ms, len(masked_rows), False)
        return structured_output(
            columns=raw["columns"],
            rows=masked_rows,
            row_count=len(masked_rows),
            execution_ms=duration_ms,
        )
