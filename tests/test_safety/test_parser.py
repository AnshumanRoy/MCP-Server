from mcp_server.safety import ValidationError, is_select_only, validate_sql


def test_valid_select():
    assert validate_sql("SELECT * FROM artist") == "SELECT * FROM artist"


def test_with_cte():
    assert validate_sql("WITH t AS (SELECT 1 AS x) SELECT * FROM t")


def test_rejects_multiple_statements():
    try:
        validate_sql("SELECT * FROM artist; SELECT * FROM album")
        assert False
    except ValidationError:
        pass


def test_rejects_pragma():
    try:
        validate_sql("PRAGMA table_info(artist)")
        assert False
    except ValidationError:
        pass


def test_rejects_attach():
    try:
        validate_sql("ATTACH 'x.db' AS aux")
        assert False
    except ValidationError:
        pass


def test_rejects_insert():
    try:
        validate_sql("INSERT INTO artist VALUES (9, 'x')")
        assert False
    except ValidationError:
        pass


def test_rejects_empty():
    try:
        validate_sql("")
        assert False
    except ValidationError:
        pass


def test_is_select_only():
    assert is_select_only("SELECT 1") is True
    assert is_select_only("INSERT INTO t VALUES (1)") is False
