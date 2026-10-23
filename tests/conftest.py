import os
import sqlite3
import tempfile

import pytest

from mcp_server.db import create_adapter
from mcp_server.server import create_mcp_server


@pytest.fixture(scope="session")
def db_path():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE artist (
            artist_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL
        );
        CREATE TABLE album (
            album_id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            artist_id INTEGER NOT NULL,
            FOREIGN KEY (artist_id) REFERENCES artist(artist_id)
        );
        CREATE TABLE track (
            track_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            album_id INTEGER,
            unit_price REAL NOT NULL,
            email TEXT
        );
        INSERT INTO artist VALUES (1, 'Artist One'), (2, 'Artist Two');
        INSERT INTO album VALUES (1, 'Album A', 1), (2, 'Album B', 2);
        INSERT INTO track VALUES
            (1, 'Song 1', 1, 0.99, 'a@example.com'),
            (2, 'Song 2', 1, 1.49, 'b@example.com'),
            (3, 'Song 3', 2, 0.89, 'c@example.com');
        """
    )
    conn.commit()
    conn.close()
    yield path
    os.unlink(path)


@pytest.fixture
def adapter(db_path):
    adapter = create_adapter(f"file:{db_path}?mode=ro")
    yield adapter
    adapter.close()


@pytest.fixture
def server(adapter):
    mcp_server, _ = create_mcp_server(adapter=adapter)
    return mcp_server


async def call_tool(server, name, **kwargs):
    tool = server._tool_manager.get_tool(name)
    return await tool.fn(**kwargs)


@pytest.fixture
def invoke(server):
    async def _call(name, **kwargs):
        return await call_tool(server, name, **kwargs)

    return _call
