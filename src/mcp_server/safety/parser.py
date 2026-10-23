import re

import sqlparse
from sqlparse.sql import Statement
from sqlparse.tokens import DML, Keyword


class ValidationError(ValueError):
    """Raised when a query fails safety validation."""


# Postgres-specific dangerous constructs (Phase 5/6).
_POSTGRES_DANGEROUS = (
    "COPY ",
    "SET ROLE",
    "SET SESSION AUTHORIZATION",
    "SET SESSION",
    "DO ",
    "LISTEN",
    "NOTIFY",
    "UNLISTEN",
    "REINDEX",
    "VACUUM",
    "CLUSTER",
    "REFRESH MATERIALIZED",
    "LOAD ",
    "pg_sleep",
    "pg_sleep_for",
    "pg_sleep_until",
    "pg_largeobject",
    "lo_",
    "pg_read_file",
    "pg_read_binary_file",
    "pg_stat_",
    "pg_catalog.",
    "information_schema.",
)


def validate_sql(sql: str) -> str:
    """Parse SQL and enforce read-only single-statement rules (layer 2).

    Returns the normalized, single SELECT statement. Raises ValidationError
    for multiple statements, dangerous constructs, or non-SELECT.
    """
    if not sql or not sql.strip():
        raise ValidationError("Empty query.")

    statements = sqlparse.parse(sql)
    # Filter out empty/whitespace-only statements.
    meaningful = [s for s in statements if s.tokens]
    if len(meaningful) != 1:
        raise ValidationError(
            "Only a single SQL statement is allowed; multiple statements are rejected."
        )

    stmt: Statement = meaningful[0]
    first_token = stmt.token_first(skip_ws=True, skip_cm=True)
    if first_token is None:
        raise ValidationError("Unable to parse query.")

    # Check the leading keyword.
    ttype = first_token.ttype
    if ttype in Keyword or (ttype is not None and ttype in DML):
        keyword = first_token.value.upper()
    else:
        keyword = first_token.value.upper()

    if keyword not in ("SELECT", "WITH"):
        raise ValidationError(
            f"Only SELECT (and optional WITH) statements are allowed; '{keyword}' is rejected."
        )

    # Reject dangerous constructs anywhere in the token stream.
    flat = re.sub(r"\s+", " ", sql.upper())
    for bad in (
        "PRAGMA",
        "ATTACH",
        "DETACH",
        "LOAD_EXTENSION",
        ".LOAD",
        "COPY ",
        "SET ROLE",
        "SET SESSION",
        "DO ",
        "LISTEN",
        "NOTIFY",
        "UNLISTEN",
        "REINDEX",
        "VACUUM",
        "CLUSTER",
        "REFRESH MATERIALIZED",
        "PG_SLEEP",
        "PG_LARGEOBJECT",
        "PG_READ_FILE",
        "PG_CATALOG.",
        "INFORMATION_SCHEMA.",
    ):
        if bad in flat:
            raise ValidationError(f"Disallowed construct '{bad}' detected in query.")

    # Block recursive CTEs that could run indefinitely (Phase 6).
    if "WITH RECURSIVE" in flat:
        raise ValidationError("Recursive CTEs (WITH RECURSIVE) are not allowed.")

    return sql.strip()


def is_select_only(sql: str) -> bool:
    try:
        validate_sql(sql)
        return True
    except ValidationError:
        return False
