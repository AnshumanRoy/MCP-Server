from mcp_server.tools.base import did_you_mean, error_response, structured_output


def test_structured_output():
    result = structured_output(
        columns=["a", "b"],
        rows=[{"a": 1, "b": 2}],
        row_count=1,
        truncated=False,
        execution_ms=5.0,
    )
    assert result["columns"] == ["a", "b"]
    assert result["rows"] == [{"a": 1, "b": 2}]
    assert result["row_count"] == 1
    assert result["truncated"] is False
    assert result["execution_ms"] == 5.0


def test_error_response():
    result = error_response("bad col", "did you mean col?")
    assert result["error"] == "bad col"
    assert result["suggestion"] == "did you mean col?"


def test_did_you_mean_found():
    assert did_you_mean("nmae", ["name", "title"]) == "name"


def test_did_you_mean_not_found():
    assert did_you_mean("xyz", ["name", "title"]) is None
