from __future__ import annotations

import sqlite3
from typing import Any

from .connection import DatabaseAdapter


class SQLiteAdapter(DatabaseAdapter):
    """SQLite implementation backed by a read-only connection."""

    def __init__(self, database_url: str) -> None:
        # mode=ro makes writes impossible at the driver level (layer 1).
        self._conn = sqlite3.connect(database_url, uri=True, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row

    def get_tables(self, include_views: bool = False) -> list[dict[str, Any]]:
        if include_views:
            type_filter = "IN ('table', 'view')"
        else:
            type_filter = "= 'table'"
        rows = self._conn.execute(
            f"""
            SELECT name, type
            FROM sqlite_master
            WHERE type {type_filter}
              AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        ).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            count_row = self._conn.execute(f"SELECT COUNT(*) AS c FROM [{row['name']}]").fetchone()
            result.append(
                {
                    "name": row["name"],
                    "type": row["type"],
                    "row_count": count_row["c"] if count_row else 0,
                }
            )
        return result

    def describe_table(self, table: str) -> dict[str, Any]:
        pragma_rows = self._conn.execute(f"PRAGMA table_info([{table}])").fetchall()
        if not pragma_rows:
            raise ValueError(f"No such table: {table}")
        columns = []
        for row in pragma_rows:
            columns.append(
                {
                    "name": row["name"],
                    "type": row["type"],
                    "nullable": not row["notnull"],
                    "primary_key": bool(row["pk"]),
                }
            )
        index_rows = self._conn.execute(f"PRAGMA index_list([{table}])").fetchall()
        indexes = []
        for idx in index_rows:
            index_rows_detail = self._conn.execute(f"PRAGMA index_info([{idx['name']}])").fetchall()
            indexes.append(
                {
                    "name": idx["name"],
                    "unique": bool(idx["unique"]),
                    "columns": [r["name"] for r in index_rows_detail],
                }
            )
        return {"table": table, "columns": columns, "indexes": indexes}

    def get_foreign_keys(self, table: str) -> dict[str, list[dict[str, Any]]]:
        fk_rows = self._conn.execute(f"PRAGMA foreign_key_list([{table}])").fetchall()
        outgoing = []
        for row in fk_rows:
            outgoing.append(
                {
                    "column": row["from"],
                    "target_table": row["table"],
                    "target_column": row["to"],
                }
            )
        incoming: list[dict[str, Any]] = []
        tables = [t["name"] for t in self.get_tables(include_views=True)]
        for other in tables:
            if other == table:
                continue
            other_fks = self._conn.execute(f"PRAGMA foreign_key_list([{other}])").fetchall()
            for row in other_fks:
                if row["table"] == table:
                    incoming.append(
                        {
                            "source_table": other,
                            "source_column": row["from"],
                            "target_column": row["to"],
                        }
                    )
        return {"outgoing": outgoing, "incoming": incoming}

    def sample_rows(
        self, table: str, limit: int, columns: list[str] | None = None
    ) -> dict[str, Any]:
        col_sql = ", ".join(f"[{c}]" for c in columns) if columns else "*"
        rows = self._conn.execute(f"SELECT {col_sql} FROM [{table}] LIMIT {int(limit)}").fetchall()
        cols = columns or (list(rows[0].keys()) if rows else [])
        return {
            "columns": cols,
            "rows": [dict(r) for r in rows],
            "row_count": len(rows),
        }

    def run_query(self, sql: str, max_rows: int, timeout_ms: int) -> dict[str, Any]:
        cur = self._conn.execute(sql)
        columns = [d[0] for d in cur.description] if cur.description else []
        raw_rows = cur.fetchmany(max_rows)
        truncated = len(raw_rows) == max_rows
        rows = [dict(zip(columns, r)) for r in raw_rows]
        return {
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
            "truncated": truncated,
        }

    def explain_query(self, sql: str) -> dict[str, Any]:
        rows = self._conn.execute(f"EXPLAIN QUERY PLAN {sql}").fetchall()
        plan_lines = [r["detail"] for r in rows]
        plan_text = "\n".join(plan_lines)
        warnings = []
        if any("SCAN TABLE" in line for line in plan_lines):
            warnings.append("Full table scan detected; consider adding an index.")
        return {"plan": plan_text, "warnings": warnings}

    def column_stats(self, table: str, column: str) -> dict[str, Any]:
        distinct = self._conn.execute(
            f"SELECT COUNT(DISTINCT [{column}]) FROM [{table}]"
        ).fetchone()[0]
        nulls = self._conn.execute(
            f"SELECT COUNT(*) FROM [{table}] WHERE [{column}] IS NULL"
        ).fetchone()[0]
        minmax = self._conn.execute(
            f"SELECT MIN([{column}]), MAX([{column}]) FROM [{table}]"
        ).fetchone()
        top = self._conn.execute(
            f"SELECT [{column}] AS v, COUNT(*) AS c FROM [{table}] "
            f"WHERE [{column}] IS NOT NULL GROUP BY [{column}] ORDER BY c DESC LIMIT 5"
        ).fetchall()
        return {
            "column": column,
            "distinct_count": distinct,
            "null_count": nulls,
            "min": minmax[0],
            "max": minmax[1],
            "top_values": [{"value": r["v"], "count": r["c"]} for r in top],
        }

    def search_schema(self, keyword: str) -> list[dict[str, Any]]:
        matches: list[dict[str, Any]] = []
        table_rows = self._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
        for trow in table_rows:
            tname = trow["name"]
            col_rows = self._conn.execute(f"PRAGMA table_info([{tname}])").fetchall()
            for crow in col_rows:
                if keyword.lower() in tname.lower() or keyword.lower() in crow["name"].lower():
                    matches.append(
                        {
                            "table": tname,
                            "column": crow["name"],
                            "type": crow["type"],
                        }
                    )
        return matches

    def close(self) -> None:
        self._conn.close()
