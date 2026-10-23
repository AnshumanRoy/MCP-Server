from __future__ import annotations

from typing import Any


def structured_output(
    columns: list[str],
    rows: list[dict[str, Any]],
    *,
    row_count: int | None = None,
    truncated: bool = False,
    execution_ms: float | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return rows as compact structured data: columns once, then rows."""
    result: dict[str, Any] = {
        "columns": columns,
        "rows": rows,
        "row_count": row_count if row_count is not None else len(rows),
        "truncated": truncated,
    }
    if execution_ms is not None:
        result["execution_ms"] = execution_ms
    if extra:
        result.update(extra)
    return result


def error_response(message: str, suggestion: str | None = None) -> dict[str, Any]:
    """Build a specific, actionable error response."""
    result: dict[str, Any] = {"error": message}
    if suggestion:
        result["suggestion"] = suggestion
    return result


def did_you_mean(value: str, candidates: list[str]) -> str | None:
    """Suggest the closest candidate for a misspelled identifier."""
    best = None
    best_score = 0.0
    for cand in candidates:
        score = _similarity(value.lower(), cand.lower())
        if score > best_score:
            best_score = score
            best = cand
    if best_score >= 0.7:
        return best
    return None


def _similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    # Simple character-overlap similarity.
    set_a, set_b = set(a), set(b)
    inter = len(set_a & set_b)
    union = len(set_a | set_b)
    return inter / union if union else 0.0
