from __future__ import annotations

import time
from typing import Any

from ..config import settings
from ..db import DatabaseAdapter
from ..safety import (
    ValidationError,
    audit_logger,
    cap_rows,
    check_concurrency,
    check_response_size,
    mask_row,
    validate_sql,
)
from .base import did_you_mean, error_response, structured_output

# In-memory concurrency counter (defense layer 3).
_active_queries = 0


def register(mcp, adapter: DatabaseAdapter) -> None:
    @mcp.tool(
        name="run_query",
        description=(
            "Execute a read-only SQL SELECT query. Returns columns, rows, row "
            "count, a truncated flag, and execution time. Always call "
            "describe_table first to confirm column names. Only a single SELECT "
            "statement is allowed; writes are impossible at the connection level."
        ),
    )
    async def run_query(
        sql: str,
        max_rows: int | None = None,
        timeout_ms: int | None = None,
    ) -> dict[str, Any]:
        global _active_queries
        start = time.time()

        # Layer 2: parse + validate the SQL.
        try:
            validate_sql(sql)
        except ValidationError as exc:
            return error_response(str(exc))

        # Layer 3: resource limits.
        effective_max_rows = cap_rows(max_rows)
        timeout = timeout_ms if timeout_ms is not None else settings.timeout_ms
        check_concurrency(_active_queries)
        _active_queries += 1

        try:
            try:
                result = adapter.run_query(sql, effective_max_rows, timeout)
            except Exception as exc:  # noqa: BLE001
                msg = str(exc)
                # Offer a did-you-meaning suggestion for missing columns/tables.
                suggestion = _suggest_fix(msg, adapter)
                return error_response(msg, suggestion)

            # Layer 4: mask sensitive columns in results.
            columns = result["columns"]
            masked_rows = [mask_row(columns, r) for r in result["rows"]]

            # Estimate response size and enforce cap (layer 3).
            import json

            size_bytes = len(
                json.dumps(
                    structured_output(
                        columns=columns,
                        rows=masked_rows,
                        row_count=len(masked_rows),
                        truncated=result.get("truncated", False),
                    ),
                    default=str,
                ).encode()
            )
            check_response_size(size_bytes)

            duration_ms = (time.time() - start) * 1000
            audit_logger.log(
                "mcp",
                "run_query",
                sql,
                duration_ms,
                len(masked_rows),
                result.get("truncated", False),
            )
            return structured_output(
                columns=columns,
                rows=masked_rows,
                row_count=len(masked_rows),
                truncated=result.get("truncated", False),
                execution_ms=duration_ms,
            )
        finally:
            _active_queries -= 1


def _suggest_fix(message: str, adapter: DatabaseAdapter) -> str | None:
    """Best-effort 'did you mean X' suggestions for common SQL errors.

    Handles both SQLite ("no such column/table") and Postgres
    ("column does not exist"/"relation does not exist") error formats.
    """
    import re

    # SQLite: "no such column: nmae"
    # Postgres: 'column "nmae" does not exist'
    m = re.search(
        r'(?:no such column:\s*(\w+)|column\s+"?(\w+)"?\s+does not exist)',
        message,
        re.IGNORECASE,
    )
    if m:
        col = m.group(1) or m.group(2)
        tables = adapter.get_tables()
        for t in tables:
            desc = adapter.describe_table(t["name"])
            cols: list[str] = [str(c["name"]) for c in desc["columns"]]
            suggestion = did_you_mean(col, cols)
            if suggestion:
                return (
                    f"No such column '{col}'; did you mean '{suggestion}' in table '{t['name']}'?"
                )

    # SQLite: "no such table: nope"
    # Postgres: 'relation "nope" does not exist'
    m = re.search(
        r'(?:no such table:\s*(\w+)|relation\s+"?(\w+)"?\s+does not exist)',
        message,
        re.IGNORECASE,
    )
    if m:
        table = m.group(1) or m.group(2)
        table_names: list[str] = [str(t["name"]) for t in adapter.get_tables()]
        suggestion = did_you_mean(table, table_names)
        if suggestion:
            return f"No such table '{table}'; did you mean '{suggestion}'?"
    return None
