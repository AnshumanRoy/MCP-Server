from __future__ import annotations

from ..db import DatabaseAdapter


def _format_column(col: dict) -> str:
    pk = " PK" if col.get("primary_key") else ""
    null = " NULL" if col.get("nullable") else " NOT NULL"
    comment = col.get("comment")
    comment_str = f" -- {comment}" if comment else ""
    return f"  - {col['name']} {col['type']}{pk}{null}{comment_str}"


def register(mcp, adapter: DatabaseAdapter) -> None:
    @mcp.resource("schema://overview")
    async def schema_overview() -> str:
        tables = adapter.get_tables(include_views=True)
        lines = ["Database schema overview:", ""]
        for t in tables:
            lines.append(f"- {t['name']} ({t['type']}, ~{t['row_count']} rows)")
            if t.get("comment"):
                lines.append(f"  Description: {t['comment']}")
            desc = adapter.describe_table(t["name"])
            if desc.get("comment"):
                lines.append(f"  Table comment: {desc['comment']}")
            for col in desc["columns"]:
                lines.append(_format_column(col))
            lines.append("")
        return "\n".join(lines)


def register_table_resource(mcp, adapter: DatabaseAdapter) -> None:
    @mcp.resource("schema://table/{name}")
    async def schema_table(name: str) -> str:
        try:
            desc = adapter.describe_table(name)
        except Exception as exc:  # noqa: BLE001
            return f"Error describing table '{name}': {exc}"
        lines = [f"Table: {desc['table']}", ""]
        if desc.get("schema"):
            lines.append(f"Schema: {desc['schema']}")
        if desc.get("comment"):
            lines.append(f"Description: {desc['comment']}")
        lines.append("")
        lines.append("Columns:")
        for col in desc["columns"]:
            lines.append(_format_column(col))
        if desc["indexes"]:
            lines.append("")
            lines.append("Indexes:")
            for idx in desc["indexes"]:
                lines.append(
                    f"  - {idx['name']} (unique={idx['unique']}): {', '.join(idx['columns'])}"
                )
        rel = adapter.get_foreign_keys(name)
        if rel["outgoing"] or rel["incoming"]:
            lines.append("")
            lines.append("Foreign keys:")
            for fk in rel["outgoing"]:
                lines.append(f"  {fk['column']} -> {fk['target_table']}({fk['target_column']})")
            for fk in rel["incoming"]:
                lines.append(
                    f"  {fk['source_table']}({fk['source_column']}) -> {name}({fk['target_column']})"
                )
        return "\n".join(lines)
