"""Run the MCP server over stdio (e.g. for MCP Inspector)."""

from __future__ import annotations

import sys

from mcp_server.server import create_mcp_server


def main() -> None:
    mcp_server, _adapter = create_mcp_server()
    try:
        mcp_server.run(transport="stdio")
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
