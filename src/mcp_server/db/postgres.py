from __future__ import annotations

from typing import Any

from psycopg2 import Error, pool, sql
from psycopg2.extras import RealDictCursor

from ..config import settings
from ..safety.masking import mask_row
from .connection import DatabaseAdapter


def _quote_ident(name: str) -> str:
    """Quote a SQL identifier safely for Postgres."""
    return '"' + name.replace('"', '""') + '"'


def _parse_schema_table(table_ref: str) -> tuple[str, str]:
    """Split a schema-qualified table reference into (schema, table).

    If no schema is given, uses the configured default schema.
    """
    if "." in table_ref:
        parts = table_ref.split(".", 1)
        return parts[0].strip('"'), parts[1].strip('"')
    return settings.db_schema, table_ref.strip('"')


def _is_table_blocked(schema: str, table: str) -> bool:
    """Check if a table is in the strict blocklist (Phase 3/5)."""
    fq = f"{schema}.{table}"
    for blocked in settings.blocked_tables:
        if blocked.lower() == fq.lower() or blocked.lower() == table.lower():
            return True
    return False


def _is_table_selectable(schema: str, table: str) -> bool:
    """Check if a table is explicitly selectable per table_access config."""
    fq = f"{schema}.{table}"
    for access in settings.table_access:
        if access.name.lower() == fq.lower() or access.name.lower() == table.lower():
            return access.selectable
    if settings.table_access:
        return False
    return not (settings.allowed_tables and fq not in settings.allowed_tables)


def _serialize_value(value: Any) -> Any:
    """Convert Postgres-specific types to JSON-serializable Python values."""
    import uuid
    from datetime import date, datetime
    from datetime import time as time_type
    from decimal import Decimal

    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, (datetime, date, time_type)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


class PostgresAdapter(DatabaseAdapter):
    """PostgreSQL implementation with read-only enforcement and connection pooling.

    Defense layers:
    1. SET TRANSACTION READ ONLY on every transaction (supplement to role-level enforcement).
    2. SQL parsed to reject non-SELECT constructs.
    3. Statement timeout enforced per-query.
    4. Table allowlist/blocklist applied in introspection and queries.
    5. Column masking applied to result rows.
    """

    def __init__(
        self,
        database_url: str,
        min_conn: int | None = None,
        max_conn: int | None = None,
    ) -> None:

        self._database_url = database_url
        self._min_conn = min_conn or settings.connection_pool_min
        self._max_conn = max_conn or settings.connection_pool_max
        self._pool: pool.ThreadedConnectionPool | None = None
        self._initialize_pool()

    def _initialize_pool(self) -> None:

        self._pool = pool.ThreadedConnectionPool(
            self._min_conn,
            self._max_conn,
            self._database_url,
            cursor_factory=RealDictCursor,
        )

    def _get_conn(self):
        if self._pool is None:
            self._initialize_pool()
        assert self._pool is not None
        return self._pool.getconn()

    def _put_conn(self, conn) -> None:
        if self._pool is not None:
            self._pool.putconn(conn)

    def _exec_readonly(
        self,
        query: str,
        params: tuple | None = None,
    ) -> list[dict[str, Any]]:
        """Execute a read-only query with transaction read-only enforcement."""
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                if params is not None:
                    cur.execute(query, params)
                else:
                    cur.execute(query)
                rows = cur.fetchall()
                conn.commit()
                return [dict(r) for r in rows if r is not None]
        except Exception:
            conn.rollback()
            raise
        finally:
            self._put_conn(conn)

    def _get_count(self, schema: str, table: str) -> int:
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                q = sql.SQL("SELECT COUNT(*) AS c FROM {}.{}").format(
                    sql.Identifier(schema), sql.Identifier(table)
                )
                cur.execute(q)
                row = cur.fetchone()
                conn.commit()
                return int(row["c"]) if row else 0
        except Error:
            conn.rollback()
            return 0
        finally:
            self._put_conn(conn)

    def get_tables(self, include_views: bool = False) -> list[dict[str, Any]]:
        kind_filter = "IN ('r', 'v')" if include_views else "= 'r'"
        query = f"""
            SELECT
                n.nspname AS schema_name,
                c.relname AS table_name,
                c.relkind AS kind,
                pg_catalog.obj_description(c.oid) AS comment
            FROM pg_catalog.pg_class c
            JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
              AND c.relkind {kind_filter}
            ORDER BY n.nspname, c.relname
        """
        rows = self._exec_readonly(query)
        result: list[dict[str, Any]] = []
        for row in rows:
            schema = row["schema_name"]
            table = row["table_name"]
            if _is_table_blocked(schema, table):
                continue
            if not _is_table_selectable(schema, table):
                continue
            try:
                row_count = self._get_count(schema, table)
            except Error:
                row_count = 0
            result.append(
                {
                    "name": f"{schema}.{table}",
                    "schema": schema,
                    "table": table,
                    "type": "view" if row["kind"] == "v" else "table",
                    "row_count": row_count,
                    "comment": row.get("comment"),
                }
            )
        return result

    def describe_table(self, table: str) -> dict[str, Any]:
        schema, table_name = _parse_schema_table(table)

        if _is_table_blocked(schema, table_name):
            raise ValueError(f"Table '{table}' is blocked from access.")
        if not _is_table_selectable(schema, table_name):
            raise ValueError(f"Table '{table}' is not selectable.")

        col_query = """
            SELECT
                column_name,
                data_type,
                is_nullable,
                column_default,
                character_maximum_length,
                numeric_precision,
                numeric_scale,
                pg_catalog.col_description(
                    (table_schema || '.' || table_name)::regclass::oid,
                    ordinal_position
                ) AS comment
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            ORDER BY ordinal_position
        """
        col_rows = self._exec_readonly(col_query, (schema, table_name))
        if not col_rows:
            raise ValueError(f"No such table: {table}")

        columns = []
        for row in col_rows:
            col_name = row["column_name"]
            data_type = row["data_type"]
            type_str = data_type
            if row["character_maximum_length"]:
                type_str += f"({row['character_maximum_length']})"
            elif row["numeric_precision"] is not None and row["numeric_scale"] is not None:
                type_str += f"({row['numeric_precision']},{row['numeric_scale']})"
            columns.append(
                {
                    "name": col_name,
                    "type": type_str,
                    "nullable": row["is_nullable"] == "YES",
                    "primary_key": False,
                    "comment": row.get("comment"),
                }
            )

        # Primary key info.
        pk_query = """
            SELECT kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
               AND tc.table_schema = kcu.table_schema
            WHERE tc.constraint_type = 'PRIMARY KEY'
              AND tc.table_schema = %s
              AND tc.table_name = %s
        """
        pk_rows = self._exec_readonly(pk_query, (schema, table_name))
        pk_cols = {row["column_name"] for row in pk_rows}
        for col in columns:
            col["primary_key"] = col["name"] in pk_cols

        # Indexes.
        idx_query = """
            SELECT
                i.relname AS index_name,
                ix.indisunique AS unique,
                array_remove(
                    array_agg(a.attname ORDER BY a.attnum), NULL
                ) AS columns
            FROM pg_index ix
            JOIN pg_class i ON i.oid = ix.indexrelid
            JOIN pg_class t ON t.oid = ix.indrelid
            JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(ix.indkey)
            JOIN pg_namespace n ON n.oid = t.relnamespace
            WHERE n.nspname = %s AND t.relname = %s
            GROUP BY i.relname, ix.indisunique
        """
        idx_rows = self._exec_readonly(idx_query, (schema, table_name))
        indexes = []
        for row in idx_rows:
            indexes.append(
                {
                    "name": row["index_name"],
                    "unique": row["unique"],
                    "columns": row["columns"] or [],
                }
            )

        # Table comment.
        comment_query = """
            SELECT pg_catalog.obj_description(
                (table_schema || '.' || table_name)::regclass::oid
            ) AS comment
            FROM information_schema.tables
            WHERE table_schema = %s AND table_name = %s
        """
        comment_rows = self._exec_readonly(comment_query, (schema, table_name))
        table_comment = comment_rows[0]["comment"] if comment_rows else None

        return {
            "table": table,
            "schema": schema,
            "comment": table_comment,
            "columns": columns,
            "indexes": indexes,
        }

    def get_foreign_keys(self, table: str) -> dict[str, list[dict[str, Any]]]:
        schema, table_name = _parse_schema_table(table)

        if _is_table_blocked(schema, table_name):
            return {"outgoing": [], "incoming": []}

        # Outgoing FKs.
        out_query = """
            SELECT
                kcu.column_name AS column_name,
                ccu.table_schema AS target_schema,
                ccu.table_name AS target_table,
                ccu.column_name AS target_column
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
               AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage ccu
                ON ccu.constraint_name = tc.constraint_name
               AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND tc.table_schema = %s
              AND tc.table_name = %s
        """
        out_rows = self._exec_readonly(out_query, (schema, table_name))
        outgoing = []
        for row in out_rows:
            if _is_table_blocked(row["target_schema"], row["target_table"]):
                continue
            outgoing.append(
                {
                    "column": row["column_name"],
                    "target_table": f"{row['target_schema']}.{row['target_table']}",
                    "target_column": row["target_column"],
                }
            )

        # Incoming FKs.
        in_query = """
            SELECT
                kcu.table_schema AS source_schema,
                kcu.table_name AS source_table,
                kcu.column_name AS source_column,
                ccu.column_name AS target_column
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
               AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage ccu
                ON ccu.constraint_name = tc.constraint_name
               AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND ccu.table_schema = %s
              AND ccu.table_name = %s
        """
        in_rows = self._exec_readonly(in_query, (schema, table_name))
        incoming = []
        for row in in_rows:
            if _is_table_blocked(row["source_schema"], row["source_table"]):
                continue
            incoming.append(
                {
                    "source_table": f"{row['source_schema']}.{row['source_table']}",
                    "source_column": row["source_column"],
                    "target_column": row["target_column"],
                }
            )

        return {"outgoing": outgoing, "incoming": incoming}

    def sample_rows(
        self,
        table: str,
        limit: int,
        columns: list[str] | None = None,
    ) -> dict[str, Any]:
        schema, table_name = _parse_schema_table(table)

        if _is_table_blocked(schema, table_name):
            raise ValueError(f"Table '{table}' is blocked from access.")
        if not _is_table_selectable(schema, table_name):
            raise ValueError(f"Table '{table}' is not selectable.")

        col_list = ", ".join(_quote_ident(c) for c in columns) if columns else "*"
        query = f"SELECT {col_list} FROM {_quote_ident(schema)}.{_quote_ident(table_name)} LIMIT %s"
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute(query, (limit,))
                raw = cur.fetchall()
                conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self._put_conn(conn)

        if not raw:
            return {"columns": [], "rows": [], "row_count": 0}

        cols = list(raw[0].keys())
        rows = [{k: _serialize_value(v) for k, v in dict(r).items()} for r in raw]
        masked = [mask_row(cols, r) for r in rows]
        return {"columns": cols, "rows": masked, "row_count": len(masked)}

    def run_query(
        self,
        sql: str,
        max_rows: int,
        timeout_ms: int,
    ) -> dict[str, Any]:
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute("SET statement_timeout = %s", (timeout_ms,))
                cur.execute(sql)
                columns = [d.name for d in cur.description] if cur.description else []
                raw_rows = cur.fetchmany(max_rows)
                truncated = len(raw_rows) == max_rows
                rows = [
                    {k: _serialize_value(v) for k, v in dict(r).items()}
                    for r in raw_rows
                ]
                conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self._put_conn(conn)

        masked_rows = [mask_row(columns, r) for r in rows]

        return {
            "columns": columns,
            "rows": masked_rows,
            "row_count": len(masked_rows),
            "truncated": truncated,
        }

    def explain_query(self, sql: str) -> dict[str, Any]:
        explain_sql = f"EXPLAIN (ANALYZE false, VERBOSE true, BUFFERS false, FORMAT TEXT) {sql}"
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute(explain_sql)
                rows = cur.fetchall()
                conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self._put_conn(conn)

        plan_lines = []
        for row in rows:
            for val in row.values():
                plan_lines.append(str(val))
        plan_text = "\n".join(plan_lines)

        warnings: list[str] = []
        if any("Seq Scan" in line for line in plan_lines):
            warnings.append("Sequential scan detected; consider adding an index.")
        if any("Nested Loop" in line for line in plan_lines):
            warnings.append("Nested loop join detected; may be slow on large tables.")

        return {"plan": plan_text, "warnings": warnings}

    def column_stats(self, table: str, column: str) -> dict[str, Any]:
        schema, table_name = _parse_schema_table(table)
        col_ident = _quote_ident(column)

        if _is_table_blocked(schema, table_name):
            raise ValueError(f"Table '{table}' is blocked from access.")

        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                distinct_q = (
                    f"SELECT COUNT(DISTINCT {col_ident}) "
                    f"FROM {_quote_ident(schema)}.{_quote_ident(table_name)}"
                )
                cur.execute(distinct_q)
                distinct_row = cur.fetchone()
                distinct = distinct_row["count"] if distinct_row else 0

                nulls_q = (
                    f"SELECT COUNT(*) FROM {_quote_ident(schema)}.{_quote_ident(table_name)} "
                    f"WHERE {col_ident} IS NULL"
                )
                cur.execute(nulls_q)
                nulls_row = cur.fetchone()
                nulls = nulls_row["count"] if nulls_row else 0

                minmax_q = (
                    f"SELECT MIN({col_ident}), MAX({col_ident}) "
                    f"FROM {_quote_ident(schema)}.{_quote_ident(table_name)}"
                )
                cur.execute(minmax_q)
                minmax_row = cur.fetchone()
                minmax = (
                    (minmax_row["min"], minmax_row["max"]) if minmax_row else None
                )

                top_q = (
                    f"SELECT {col_ident} AS v, COUNT(*) AS c "
                    f"FROM {_quote_ident(schema)}.{_quote_ident(table_name)} "
                    f"WHERE {col_ident} IS NOT NULL "
                    f"GROUP BY {col_ident} ORDER BY c DESC LIMIT 5"
                )
                cur.execute(top_q)
                top_rows = cur.fetchall()
                conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self._put_conn(conn)

        return {
            "column": column,
            "distinct_count": int(distinct) if distinct is not None else 0,
            "null_count": int(nulls) if nulls is not None else 0,
            "min": _serialize_value(minmax[0]) if minmax else None,
            "max": _serialize_value(minmax[1]) if minmax else None,
            "top_values": [
                {"value": _serialize_value(r["v"]), "count": int(r["c"])} for r in top_rows
            ],
        }

    def search_schema(self, keyword: str) -> list[dict[str, Any]]:
        like = f"%{keyword}%"
        query = """
            SELECT
                n.nspname AS schema_name,
                c.relname AS table_name,
                a.attname AS column_name,
                pg_catalog.format_type(a.atttypid, a.atttypmod) AS data_type
            FROM pg_catalog.pg_attribute a
            JOIN pg_catalog.pg_class c ON c.oid = a.attrelid
            JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
              AND a.attnum > 0
              AND NOT a.attisdropped
              AND c.relkind = 'r'
              AND (c.relname ILIKE %s OR a.attname ILIKE %s)
            ORDER BY n.nspname, c.relname, a.attnum
        """
        rows = self._exec_readonly(query, (like, like))
        matches: list[dict[str, Any]] = []
        for row in rows:
            schema = row["schema_name"]
            table = row["table_name"]
            if _is_table_blocked(schema, table):
                continue
            if not _is_table_selectable(schema, table):
                continue
            matches.append(
                {
                    "table": f"{schema}.{table}",
                    "column": row["column_name"],
                    "type": row["data_type"],
                }
            )
        return matches

    def close(self) -> None:
        if self._pool is not None:
            self._pool.closeall()
            self._pool = None
