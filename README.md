# Database Explorer MCP Server

A read-only database explorer MCP (Model Context Protocol) server supporting SQLite and PostgreSQL backends. Built for use with [Opencode](https://opencode.ai) and any MCP-compatible client.

## Features

- **Read-only by design**: Database connections are opened read-only; writes are impossible at the driver level.
- **SQL safety layer**: SQL is parsed to reject non-SELECT statements, multiple statements, and dangerous constructs (PRAGMA, ATTACH, COPY, etc.).
- **Row and response limits**: Configurable max rows, response size cap, and concurrent query cap.
- **Column masking**: Sensitive columns (customer IDs, geolocation, review comments) are hashed/redacted per a configurable sensitivity policy.
- **Table access control**: Allowlist/blocklist with per-table descriptions.
- **Tools (9)**: `list_tables`, `describe_table`, `sample_rows`, `run_query`, `get_relationships`, `explain_query`, `column_stats`, `search_schema`, `validate_query`.
- **Resources**: `schema://overview`, `schema://table/{name}`.
- **Prompts**: `explore`, `answer`.
- **Transports**: Streamable HTTP (`/mcp`) and stdio.

## Quick Start

### 1. Clone and configure

```bash
git clone https://github.com/your-username/Database-Explorer-MCP-Server.git
cd Database-Explorer-MCP-Server/mcp-server
cp .env.example .env
# Edit .env with your database URL and (optional) Kaggle credentials
```

### 2. Install dependencies

```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
# or: source .venv/bin/activate  # macOS/Linux
pip install -e ".[dev]"
```

### 3. Start Postgres (Docker)

```bash
docker-compose up -d
```

Wait for the container to be healthy, then load the Olist sample data:

```bash
# Download Olist CSVs via Kaggle API (requires KAGGLE_USERNAME/KAGGLE_KEY in .env)
python scripts/download_data.py

# Load CSVs into Postgres in foreign-key-safe order
python scripts/load_data.py --data-dir ./data --reset
```

### 4. Start the MCP server

Streamable HTTP (recommended for Opencode):

```bash
uvicorn mcp_server.server:build_app --factory --host 127.0.0.1 --port 8765
```

Or stdio (for MCP Inspector):

```bash
python -m mcp_server
```

The server listens at `http://localhost:8765/mcp`.

### 5. Connect to Opencode

Add to `~/.config/opencode/opencode.json`:

```json
{
  "mcp": {
    "db-explorer": {
      "type": "remote",
      "url": "http://localhost:8765/mcp",
      "enabled": true
    }
  }
}
```

Restart Opencode to pick up the change.

## Tools

| Tool | Description |
|------|-------------|
| `list_tables` | List tables/views with row counts |
| `describe_table` | Full table structure: columns, types, PK, indexes, comments |
| `sample_rows` | Up to 10 sample rows from a table (sensitive columns masked) |
| `run_query` | Execute a single SELECT query (capped rows, timeout enforced) |
| `get_relationships` | Foreign keys (outgoing + incoming) for join planning |
| `explain_query` | Query plan without execution |
| `column_stats` | Distinct count, nulls, min/max, top values for a column |
| `search_schema` | Keyword search across table and column names |
| `validate_query` | Check if a SQL query would pass safety rules without running it |

## Resources

- `schema://overview` — Full schema overview with all tables and columns
- `schema://table/{name}` — Detailed info for a specific table including FKs

## Prompts

- `explore` — Guided process for exploring a read-only database
- `answer` — Process for answering data questions with SQL

## Configuration

All settings use the `MCP_` environment variable prefix (via `.env`):

| Variable | Default | Description |
|----------|---------|-------------|
| `MCP_DATABASE_URL` | `file:chinook.db?mode=ro` | SQLite read-only URI or Postgres connection string |
| `MCP_MAX_ROWS` | 1000 | Max rows returned by `run_query` |
| `MCP_DEFAULT_MAX_ROWS` | 100 | Default row cap |
| `MCP_TIMEOUT_MS` | 30000 | Query timeout in milliseconds |
| `MCP_MAX_RESPONSE_SIZE_BYTES` | 1000000 | Max response payload size |
| `MCP_MAX_CONCURRENT_QUERIES` | 5 | Cap on concurrent queries |
| `MCP_ALLOWED_TABLES` | `[]` | JSON array of allowed schema-qualified table names |
| `MCP_BLOCKED_TABLES` | `[]` | JSON array of blocked table names |
| `MCP_DB_SCHEMA` | `public` | Default Postgres schema |
| `MCP_CONNECTION_POOL_MIN` | 2 | Min Postgres pool connections |
| `MCP_CONNECTION_POOL_MAX` | 10 | Max Postgres pool connections |
| `MCP_SAMPLE_ROW_LIMIT` | 10 | Default/sample row limit |
| `KAGGLE_USERNAME` | — | Kaggle API username (for `scripts/download_data.py`) |
| `KAGGLE_KEY` | — | Kaggle API key (for `scripts/download_data.py`) |

## Safety Guarantees

1. **Connection-level read-only**: SQLite opens with `mode=ro`; Postgres issues `SET TRANSACTION READ ONLY` on every transaction.
2. **SQL parsing**: Only single `SELECT`/`WITH` statements allowed; `INSERT`, `UPDATE`, `DELETE`, `DDL`, `PRAGMA`, `COPY`, `pg_sleep`, etc. are rejected.
3. **Resource limits**: Row caps, response size caps, and concurrent query caps prevent runaway queries.
4. **Column masking**: Sensitive columns are hashed or redacted before results are returned.

## Scripts

- `scripts/download_data.py` — Download Olist Brazilian E-Commerce CSVs via Kaggle API
- `scripts/load_data.py` — Load CSVs into Postgres in FK-safe order (`--reset`, `--no-geolocation`)
- `scripts/make_sample_db.py` — Generate a small sample SQLite DB for local testing

## Testing

```bash
pytest tests/
```

Runs 37 tests: 24 SQLite unit tests + 13 Postgres integration tests (skipped if Postgres is unavailable).

Postgres integration tests require Docker:
```bash
docker-compose up -d
python scripts/load_data.py --data-dir ./data --reset
pytest tests/
```

## Linting & Type Checking

```bash
ruff check src/ tests/ scripts/
mypy src/
```

## License

MIT License. See [LICENSE](LICENSE).
