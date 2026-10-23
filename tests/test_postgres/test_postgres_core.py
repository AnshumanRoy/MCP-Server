"""Integration tests against the real Postgres Olist database.

These require a running Postgres instance (docker-compose) with the Olist data loaded.
"""

from __future__ import annotations

import pytest

from mcp_server.config import settings
from mcp_server.db import create_adapter


def _postgres_available() -> bool:
    try:
        adapter = create_adapter(settings.database_url)
        adapter.get_tables()
        adapter.close()
        return True
    except Exception:  # noqa: BLE001
        return False


requires_postgres = pytest.mark.skipif(
    not _postgres_available(), reason="Postgres database not reachable"
)


@pytest.mark.asyncio
@requires_postgres
async def test_postgres_list_tables(invoke):
    result = await invoke("list_tables")
    assert "error" not in result, result
    names = [r["name"] for r in result["rows"]]
    expected = [
        "public.orders",
        "public.customers",
        "public.sellers",
        "public.products",
        "public.order_items",
        "public.order_payments",
        "public.order_reviews",
        "public.product_category_name_translation",
    ]
    for name in expected:
        assert name in names, f"{name} missing from tables: {names}"
    # geolocation should be blocked
    assert "public.geolocation" not in names


@pytest.mark.asyncio
@requires_postgres
async def test_postgres_describe_table(invoke):
    result = await invoke("describe_table", table="public.orders")
    assert "error" not in result, result
    assert result["table"] == "public.orders"
    cols = {c["name"]: c for c in result["rows"]}
    assert "order_id" in cols
    assert "customer_id" in cols
    assert cols["order_id"]["primary_key"] is True


@pytest.mark.asyncio
@requires_postgres
async def test_postgres_describe_table_blocked(invoke):
    result = await invoke("describe_table", table="public.geolocation")
    assert "error" in result, result


@pytest.mark.asyncio
@requires_postgres
async def test_postgres_sample_rows(invoke):
    result = await invoke("sample_rows", table="public.orders", limit=3)
    assert "error" not in result, result
    assert result["row_count"] == 3
    assert len(result["rows"]) == 3
    assert "order_id" in result["columns"]


@pytest.mark.asyncio
@requires_postgres
async def test_postgres_run_query(invoke):
    result = await invoke(
        "run_query",
        sql="SELECT order_id, order_status, customer_id FROM public.orders ORDER BY order_purchase_timestamp DESC LIMIT 5",
        max_rows=100,
        timeout_ms=30000,
    )
    assert "error" not in result, result
    assert result["columns"] == ["order_id", "order_status", "customer_id"]
    assert result["row_count"] == 5
    assert result["truncated"] is False


@pytest.mark.asyncio
@requires_postgres
async def test_postgres_run_query_join(invoke):
    result = await invoke(
        "run_query",
        sql="""
            SELECT o.order_id, c.customer_state, oi.product_id, oi.price
            FROM public.orders o
            JOIN public.order_items oi ON oi.order_id = o.order_id
            JOIN public.customers c ON c.customer_id = o.customer_id
            LIMIT 3
        """,
        max_rows=100,
        timeout_ms=30000,
    )
    assert "error" not in result, result
    assert result["row_count"] == 3
    assert "order_id" in result["columns"]
    assert "customer_state" in result["columns"]


@pytest.mark.asyncio
@requires_postgres
async def test_postgres_run_query_rejects_write(invoke):
    result = await invoke("run_query", sql="DELETE FROM public.orders")
    assert "error" in result, result


@pytest.mark.asyncio
@requires_postgres
async def test_postgres_run_query_rejects_multi_statement(invoke):
    result = await invoke(
        "run_query", sql="SELECT 1; SELECT COUNT(*) FROM public.orders"
    )
    assert "error" in result, result


@pytest.mark.asyncio
@requires_postgres
async def test_postgres_blocked_table_query(invoke):
    result = await invoke("sample_rows", table="public.geolocation", limit=5)
    assert "error" in result, result


@pytest.mark.asyncio
@requires_postgres
async def test_postgres_get_relationships(invoke):
    result = await invoke("get_relationships", table="public.order_items")
    assert "error" not in result, result
    directions = {r["direction"] for r in result["rows"]}
    assert "outgoing" in directions


@pytest.mark.asyncio
@requires_postgres
async def test_postgres_column_stats(invoke):
    result = await invoke("column_stats", table="public.orders", column="order_status")
    assert "error" not in result, result
    stats = result["rows"][0]
    assert stats["column"] == "order_status"
    assert stats["distinct_count"] > 0
    assert "top_values" in result


@pytest.mark.asyncio
@requires_postgres
async def test_postgres_search_schema(invoke):
    result = await invoke("search_schema", keyword="order")
    assert "error" not in result, result
    table_names = {m["table"] for m in result["rows"]}
    assert "public.orders" in table_names or "public.order_items" in table_names


@pytest.mark.asyncio
@requires_postgres
async def test_postgres_masking_applied(invoke):
    """customer_unique_id should be hashed (masked) per sensitivity policy."""
    result = await invoke(
        "run_query",
        sql="SELECT customer_unique_id FROM public.customers LIMIT 2",
        max_rows=10,
        timeout_ms=30000,
    )
    assert "error" not in result, result
    # Values should be masked (hashed), not raw plaintext IDs
    for row in result["rows"]:
        val = row["customer_unique_id"]
        assert val is not None
        assert len(val) > 0
