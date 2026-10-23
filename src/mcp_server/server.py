from __future__ import annotations

from contextlib import asynccontextmanager

from mcp.server import MCPServer
from starlette.applications import Starlette

from mcp_server.config import settings
from mcp_server.db import DatabaseAdapter, create_adapter
from mcp_server.prompts import register_all as register_prompts
from mcp_server.resources import register as register_resources
from mcp_server.resources import register_table_resource
from mcp_server.tools import register_all as register_tools


def create_mcp_server(
    adapter: DatabaseAdapter | None = None,
) -> tuple[MCPServer, DatabaseAdapter]:
    server = MCPServer(
        name="read-only-database-explorer",
        instructions=(
            "A read-only database explorer. Use list_tables/describe_table to "
            "learn the schema, then run_query (SELECT only) to read data. "
            "Writes are impossible at the connection level."
        ),
    )
    if adapter is None:
        adapter = create_adapter(settings.database_url)

    register_tools(server, adapter)
    register_resources(server, adapter)
    register_table_resource(server, adapter)
    register_prompts(server)

    return server, adapter


def build_app() -> Starlette:
    mcp_server, adapter = create_mcp_server()
    app = mcp_server.streamable_http_app()

    original_lifespan = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(app_: Starlette):
        async with original_lifespan(app_):
            try:
                yield
            finally:
                adapter.close()

    app.router.lifespan_context = lifespan
    return app
