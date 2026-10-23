from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ..config import settings


class DatabaseAdapter(ABC):
    """Abstract interface for a read-only database connection.

    Concrete implementations must never issue writes. The read-only
    guarantee is enforced at the connection level (defense layer 1).
    """

    @abstractmethod
    def get_tables(self, include_views: bool = False) -> list[dict[str, Any]]: ...

    @abstractmethod
    def describe_table(self, table: str) -> dict[str, Any]: ...

    @abstractmethod
    def get_foreign_keys(self, table: str) -> dict[str, list[dict[str, Any]]]: ...

    @abstractmethod
    def sample_rows(
        self, table: str, limit: int, columns: list[str] | None = None
    ) -> dict[str, Any]: ...

    @abstractmethod
    def run_query(self, sql: str, max_rows: int, timeout_ms: int) -> dict[str, Any]: ...

    @abstractmethod
    def explain_query(self, sql: str) -> dict[str, Any]: ...

    @abstractmethod
    def column_stats(self, table: str, column: str) -> dict[str, Any]: ...

    @abstractmethod
    def search_schema(self, keyword: str) -> list[dict[str, Any]]: ...

    @abstractmethod
    def close(self) -> None: ...


def create_adapter(database_url: str | None = None) -> DatabaseAdapter:
    """Factory producing a read-only database adapter.

    Detects the database type from the URL:
    - SQLite: file: URIs or .db paths (read-only via mode=ro)
    - PostgreSQL: postgres:// or postgresql:// URLs
    """
    url = database_url or settings.database_url
    if url.startswith("file:") or url.endswith(".db"):
        from .sqlite import SQLiteAdapter

        return SQLiteAdapter(url)
    if url.startswith(("postgres://", "postgresql://")):
        from .postgres import PostgresAdapter

        return PostgresAdapter(url)
    raise ValueError(f"Unsupported database URL: {url}")
