from __future__ import annotations

import hashlib
import re
from typing import Any

from ..config import settings


def _is_denied(column_name: str) -> bool:
    lower = column_name.lower()
    for pattern in settings.denied_columns:
        if re.search(pattern, lower):
            return True
    return False


def _apply_rule(value: Any, rule) -> Any:
    """Apply a single MaskingRule to a value."""
    strategy = rule.strategy
    if strategy == "none":
        return value
    if strategy == "redact":
        return "[REDACTED]"
    if strategy == "hash":
        text = str(value)
        digest = hashlib.sha256(text.encode()).hexdigest()[:16]
        return f"hash:{digest}"
    if strategy == "truncate":
        text = str(value)
        if rule.preserve_length:
            return "*" * len(text)
        first = rule.show_first
        last = rule.show_last
        if first == 0 and last == 0:
            return "***"
        start = text[:first] if first > 0 else ""
        end = text[-last:] if last > 0 else ""
        middle = "*" * max(0, len(text) - first - last)
        return start + middle + end
    return value


def mask_value(column_name: str, value: Any) -> Any:
    """Mask sensitive column values (layer 4). Returns the masked value.

    Supports strategies: hash, truncate, redact, none.
    Falls back to legacy denied_columns list if no rule matches.
    """
    if value is None:
        return None

    lower = column_name.lower()

    # Check explicit masking rules first.
    for rule in settings.masking_rules:
        if re.search(rule.column_pattern, lower, re.IGNORECASE):
            return _apply_rule(value, rule)

    # Fall back to legacy denied_columns list.
    if _is_denied(column_name):
        text = str(value)
        if len(text) <= 2:
            return "***"
        return text[0] + "***"

    return value


def mask_row(columns: list[str], row: dict[str, Any]) -> dict[str, Any]:
    return {col: mask_value(col, row.get(col)) for col in columns}
