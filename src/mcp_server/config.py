from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings


class MaskingRule(BaseSettings):
    """Per-column masking rule definition (Phase 3 sensitivity policy)."""

    column_pattern: str = Field(
        description="Regex pattern matched against column names (case-insensitive)."
    )
    strategy: str = Field(
        default="hash",
        description="Masking strategy: 'hash', 'truncate', 'redact', or 'none'.",
    )
    preserve_length: bool = Field(
        default=False,
        description="If True with 'truncate', preserve original length with asterisks.",
    )
    show_first: int = Field(
        default=0,
        description="Number of leading characters to keep visible (with 'truncate').",
    )
    show_last: int = Field(
        default=0,
        description="Number of trailing characters to keep visible (with 'truncate').",
    )


class TableAccess(BaseSettings):
    """Per-table access control (Phase 3/5 allowlists/blocklists)."""

    name: str = Field(description="Table name (schema-qualified e.g. 'public.orders').")
    selectable: bool = Field(
        default=True,
        description="If False, table is hidden from schema listings and blocked from queries.",
    )
    description: str | None = Field(
        default=None, description="Human-readable description surfaced in schema://overview."
    )


class Settings(BaseSettings):
    database_url: str = Field(
        default="file:chinook.db?mode=ro",
        description="Database connection URL. SQLite read-only URI or Postgres connection string.",
    )
    max_rows: int = Field(default=1000, description="Maximum rows returned by run_query.")
    default_max_rows: int = Field(default=100, description="Default row cap for run_query.")
    timeout_ms: int = Field(default=30000, description="Query timeout in milliseconds.")
    max_response_size_bytes: int = Field(
        default=1_000_000,
        description="Maximum response payload size in bytes.",
    )
    max_concurrent_queries: int = Field(default=5, description="Cap on concurrent queries.")
    allowed_tables: list[str] = Field(
        default_factory=list,
        description="Allowlist of schema-qualified table names. Empty means all tables allowed.",
    )
    blocked_tables: list[str] = Field(
        default_factory=list,
        description="Tables excluded from schema listings and queries (strict blocklist).",
    )
    denied_columns: list[str] = Field(
        default_factory=list,
        description="Column name patterns whose values are masked (legacy, kept for backward compat).",
    )
    masking_rules: list[MaskingRule] = Field(
        default_factory=list, description="Per-column masking rules with strategy, truncation, etc."
    )
    table_access: list[TableAccess] = Field(
        default_factory=list,
        description="Per-table access control with descriptions and selectable flags.",
    )
    sample_row_limit: int = Field(default=10, description="Default/sample row limit.")
    db_schema: str = Field(
        default="public", description="Default database schema for Postgres introspection."
    )
    connection_pool_min: int = Field(
        default=2, description="Minimum connections in the Postgres pool."
    )
    connection_pool_max: int = Field(
        default=10, description="Maximum connections in the Postgres pool."
    )

    # Kaggle API credentials (for downloading Olist dataset).
    kaggle_username: str | None = Field(
        default=None, description="Kaggle API username."
    )
    kaggle_key: str | None = Field(
        default=None, description="Kaggle API key."
    )

    model_config = {"env_file": ".env", "env_prefix": "MCP_"}


settings = Settings()

# Predefined sensitivity policy for Olist dataset (Phase 3).
# These are defaults; they can be overridden via environment variables or .env.
OLIST_MASKING_RULES: list[dict] = [
    {
        "column_pattern": r"customer_id|customer_unique_id",
        "strategy": "hash",
        "description": "Hash customer identifiers.",
    },
    {
        "column_pattern": r"seller_id",
        "strategy": "hash",
        "description": "Hash seller identifiers.",
    },
    {
        "column_pattern": r"review_comment_message",
        "strategy": "redact",
        "description": "Redact free-text review comments (prompt-injection surface).",
    },
    {
        "column_pattern": r"geolocation.*(lat|lng)",
        "strategy": "redact",
        "description": "Redact raw geolocation coordinates.",
    },
    {
        "column_pattern": r"order_id",
        "strategy": "none",
        "description": "Order IDs are safe to expose.",
    },
    {
        "column_pattern": r"product_id",
        "strategy": "none",
        "description": "Product IDs are safe to expose.",
    },
]

OLIST_TABLE_ACCESS: list[dict] = [
    {
        "name": "public.orders",
        "selectable": True,
        "description": "Central order table. Most joins start here. Contains order status and timestamps.",
    },
    {
        "name": "public.order_items",
        "selectable": True,
        "description": "Line items with price and freight. Links orders, products, sellers.",
    },
    {
        "name": "public.order_payments",
        "selectable": True,
        "description": "Payment type, installments, value. Multiple rows per order - avoid double-counting revenue.",
    },
    {
        "name": "public.order_reviews",
        "selectable": True,
        "description": "Review scores and free-text comments (Portuguese). Prompt-injection test surface.",
    },
    {
        "name": "public.customers",
        "selectable": True,
        "description": "Customer location and IDs. Two ID columns: customer_id (per-order) and customer_unique_id (unique).",
    },
    {
        "name": "public.sellers",
        "selectable": True,
        "description": "Seller location information.",
    },
    {
        "name": "public.products",
        "selectable": True,
        "description": "Category, dimensions, weight. Category names in Portuguese.",
    },
    {
        "name": "public.product_category_name_translation",
        "selectable": True,
        "description": "Portuguese to English category name translation. Join needed for readable categories.",
    },
    {
        "name": "public.geolocation",
        "selectable": False,
        "description": "ZIP prefix to lat/long. Blocked by default - many rows per ZIP, no clean key, coordinates sensitive.",
    },
]
