from . import (
    column_stats,
    describe_table,
    explain_query,
    get_relationships,
    list_tables,
    run_query,
    sample_rows,
    search_schema,
    validate_query,
)


def register_all(mcp, adapter) -> None:
    list_tables.register(mcp, adapter)
    describe_table.register(mcp, adapter)
    get_relationships.register(mcp, adapter)
    sample_rows.register(mcp, adapter)
    run_query.register(mcp, adapter)
    explain_query.register(mcp, adapter)
    column_stats.register(mcp, adapter)
    search_schema.register(mcp, adapter)
    validate_query.register(mcp)
