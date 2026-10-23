ANSWER_PROMPT = """You are answering a data question against a read-only database.

Process:
1. Clarify the question if needed.
2. Call list_tables and describe_table (or schema://overview) to understand the
   schema before writing SQL.
3. Write a single SELECT query. Use explain_query first if the query may be
   expensive.
4. Run the query with run_query and check the `truncated` flag. Report any
   truncation so the user knows the data may be incomplete.
5. Answer the question using only the returned data; do not hallucinate values.

Never write anything but SELECT. Sensitive columns are masked in results.
"""


def register(mcp) -> None:
    @mcp.prompt("answer")
    async def answer() -> str:
        return ANSWER_PROMPT
