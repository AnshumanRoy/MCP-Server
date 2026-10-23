import pytest


@pytest.mark.asyncio
async def test_list_tables(invoke):
    result = await invoke("list_tables")
    assert "error" not in result, result
    names = [r["name"] for r in result["rows"]]
    assert "artist" in names
    assert "album" in names
    assert "track" in names
    for row in result["rows"]:
        assert set(row.keys()) == {"name", "type", "row_count"}


@pytest.mark.asyncio
async def test_describe_table(invoke):
    result = await invoke("describe_table", table="track")
    assert "error" not in result, result
    assert result["table"] == "track"
    cols = {c["name"]: c for c in result["rows"]}
    assert "track_id" in cols
    assert cols["track_id"]["primary_key"] is True
    assert cols["name"]["nullable"] is False


@pytest.mark.asyncio
async def test_describe_table_missing(invoke):
    result = await invoke("describe_table", table="nope")
    assert "error" in result


@pytest.mark.asyncio
async def test_sample_rows(invoke):
    result = await invoke("sample_rows", table="track", limit=2)
    assert "error" not in result, result
    assert result["row_count"] == 2
    assert len(result["rows"]) == 2


@pytest.mark.asyncio
async def test_sample_rows_limit_capped(invoke):
    result = await invoke("sample_rows", table="track", limit=1000)
    assert result["row_count"] <= 10


@pytest.mark.asyncio
async def test_run_query(invoke):
    result = await invoke("run_query", sql="SELECT name FROM artist ORDER BY name")
    assert "error" not in result, result
    assert result["columns"] == ["name"]
    assert result["row_count"] == 2
    assert result["truncated"] is False
    assert "execution_ms" in result


@pytest.mark.asyncio
async def test_run_query_rejects_write(invoke):
    result = await invoke("run_query", sql="DELETE FROM artist")
    assert "error" in result, result


@pytest.mark.asyncio
async def test_run_query_rejects_multi_statement(invoke):
    result = await invoke("run_query", sql="SELECT 1; SELECT 2")
    assert "error" in result, result


@pytest.mark.asyncio
async def test_run_query_missing_column_suggestion(invoke):
    result = await invoke("run_query", sql="SELECT nmae FROM artist")
    assert "error" in result, result
    assert "did you mean" in result.get("suggestion", "").lower()


@pytest.mark.asyncio
async def test_get_relationships(invoke):
    result = await invoke("get_relationships", table="album")
    assert "error" not in result, result
    directions = {r["direction"] for r in result["rows"]}
    assert "outgoing" in directions


@pytest.mark.asyncio
async def test_explain_query(invoke):
    result = await invoke("explain_query", sql="SELECT * FROM artist")
    assert "error" not in result, result
    assert "plan" in result["rows"][0]
