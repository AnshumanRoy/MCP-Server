from __future__ import annotations

import time
from typing import Any


class AuditLogger:
    """Logs each query with timestamp, caller, duration, and row count (layer 6)."""

    def __init__(self) -> None:
        self.entries: list[dict[str, Any]] = []

    def log(
        self,
        caller: str,
        tool: str,
        sql: str,
        duration_ms: float,
        row_count: int,
        truncated: bool,
    ) -> None:
        self.entries.append(
            {
                "timestamp": time.time(),
                "caller": caller,
                "tool": tool,
                "sql": sql,
                "duration_ms": duration_ms,
                "row_count": row_count,
                "truncated": truncated,
            }
        )


audit_logger = AuditLogger()
