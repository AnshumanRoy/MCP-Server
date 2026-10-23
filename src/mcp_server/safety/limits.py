from __future__ import annotations

from ..config import settings


class LimitExceededError(ValueError):
    """Raised when a query would exceed a configured resource limit."""


def cap_rows(requested: int | None) -> int:
    """Apply the row cap. Returns the effective max_rows."""
    limit = requested if requested is not None else settings.default_max_rows
    if limit <= 0:
        raise LimitExceededError("max_rows must be a positive integer.")
    return min(limit, settings.max_rows)


def check_response_size(size_bytes: int) -> None:
    """Raise if the estimated response exceeds the size cap (layer 3)."""
    if size_bytes > settings.max_response_size_bytes:
        raise LimitExceededError(
            f"Response size {size_bytes} bytes exceeds cap of "
            f"{settings.max_response_size_bytes} bytes."
        )


def check_concurrency(active: int) -> None:
    """Raise if too many queries are already running."""
    if active >= settings.max_concurrent_queries:
        raise LimitExceededError(
            f"Too many concurrent queries ({active}/{settings.max_concurrent_queries})."
        )
