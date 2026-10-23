from __future__ import annotations

from typing import Any

from ..safety import ValidationError, validate_sql


def register(mcp) -> None:
    @mcp.tool(
        name="validate_query",
        description=(
            "Check whether a SQL query would be allowed (parses and applies the "
            "safety rules) without executing it. Returns ok=true if the query is "
            "permitted, otherwise an error explaining why."
        ),
    )
    async def validate_query(sql: str) -> dict[str, Any]:
        try:
            validate_sql(sql)
            return {"ok": True, "message": "Query is allowed."}
        except ValidationError as exc:
            return {"ok": False, "error": str(exc)}
