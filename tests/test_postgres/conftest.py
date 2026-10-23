"""Postgres integration test fixtures.

Skips all tests when the Postgres database is not reachable (e.g. CI without Docker).
"""

from __future__ import annotations

import pytest

from mcp_server.config import settings
from mcp_server.db import create_adapter
from mcp_server.server import create_mcp_server


def _postgres_available() -> bool:
    try:
        adapter = create_adapter(settings.database_url)
        adapter.get_tables()
        adapter.close()
        return True
    except Exception:  # noqa: BLE001 - any connection failure means skip
        return False


requires_postgres = pytest.mark.skipif(
    not _postgres_available(), reason="Postgres database not reachable"
)


@pytest.fixture(scope="session")
def pg_adapter():
    adapter = create_adapter(settings.database_url)
    yield adapter
    adapter.close()


@pytest.fixture
def pg_server(pg_adapter):
    mcp_server, _ = create_mcp_server(adapter=pg_adapter)
    return mcp_server


async def call_tool(server, name, **kwargs):
    tool = server._tool_manager.get_tool(name)
    return await tool.fn(**kwargs)


@pytest.fixture
def invoke(pg_server):
    async def _call(name, **kwargs):
        return await call_tool(pg_server, name, **kwargs)

    return _call
