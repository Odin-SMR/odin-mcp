"""Actual MCP messages through synthetic anonymous HTTPS catalogs and Parquet."""
import io
import json
import sys

import anyio
import httpx
from mcp.shared.memory import create_connected_server_and_client_session
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from odin_mcp import public_http
from odin_mcp.config import ARCHIVE_INDEX_URL, SAMPLE_CATALOG_URL
from odin_mcp.server import mcp


@pytest.fixture
def mock_public_service(monkeypatch):
    table = pa.table({"time": pa.array([1, None], type=pa.timestamp("ns", tz="UTC")),
                      "quality": pa.array([None, None], type=pa.int64()),
                      "vmr": [-1e-9, float("nan")], "avk": [[0.2, 0.8], None]})
    output = io.BytesIO()
    pq.write_table(table, output)
    body = output.getvalue()
    file_url = "https://odin-smr.org/l2/project=P/freq_mode=1/inv_mode=stnd/product=O3/year=2019/month=03/a.parquet"
    index_url = "https://odin-smr.org/parquet/archive/test/g-a.json"
    docs = {ARCHIVE_INDEX_URL: {"schema_version": 1, "snapshot_id": "test", "groups": [
        {"id": "g-a", "project": "P", "product": "O3", "frequency_mode": 1, "inversion_mode": "stnd", "level": "L2",
         "file_count": 1, "size_bytes": len(body), "index_url": index_url}]},
        index_url: {"schema_version": 1, "snapshot_id": "test", "group_id": "g-a", "files": [
            {"url": file_url, "size_bytes": len(body), "year": 2019, "month": 3, "etag": "test-etag", "last_modified": None}]}}
    requests = []
    def handler(request):
        requests.append(request)
        assert "authorization" not in request.headers and "cookie" not in request.headers
        url = str(request.url)
        if url == file_url:
            assert request.headers["if-match"] == '"test-etag"'
            return httpx.Response(200, headers={"ETag": '"test-etag"', "Content-Length": str(len(body))}, stream=httpx.ByteStream(body))
        if url in docs:
            content = json.dumps(docs[url]).encode()
            return httpx.Response(200, stream=httpx.ByteStream(content))
        return httpx.Response(503, stream=httpx.ByteStream(b"unavailable"))
    monkeypatch.setattr(public_http, "_client", lambda: httpx.Client(transport=httpx.MockTransport(handler), trust_env=False))
    return file_url, requests


def payload(result):
    assert not result.isError
    return result.structuredContent or json.loads(result.content[0].text)


def test_data_tools_over_actual_mcp_messages(mock_public_service):
    file_url, requests = mock_public_service
    async def exercise():
        async with create_connected_server_and_client_session(mcp) as session:
            tools = {tool.name: tool for tool in (await session.list_tools()).tools}
            assert tools["read_parquet_columns_tool"].annotations.readOnlyHint
            assert tools["read_parquet_columns_tool"].annotations.openWorldHint
            schema = tools["read_parquet_columns_tool"].inputSchema
            assert "file_url" in schema["properties"] and "s3_uri" in schema["properties"]
            projects = payload(await session.call_tool("list_partition_values_tool", {"level": "project", "product": "O3"}))
            assert projects["ok"] and projects["data"]["values"] == ["P"]
            listed = payload(await session.call_tool("list_parquet_files_tool", {"month": "03"}))
            assert listed["ok"] and listed["data"]["file_urls"] == [file_url]
            assert listed["data"]["next_token"] is None
            preview = payload(await session.call_tool("read_parquet_preview_tool", {"file_url": file_url, "rows": 1}))
            assert preview["ok"]
            row = preview["data"]["files"][0]["rows"][0]
            assert row == {"time": "1970-01-01T00:00:00.000000001+00:00", "quality": None, "vmr": -1e-9, "avk": [0.2, 0.8]}
            projected = payload(await session.call_tool("read_parquet_columns_tool", {"columns": ["time", "vmr", "avk"], "month": "3", "rows": 2}))
            assert projected["ok"]
            assert projected["data"]["files"][0]["rows"][1] == {"time": None, "vmr": "NaN", "avk": None}
            assert projected["data"]["access"]["http_requests"] == 3
            assert "duplicate" in projected["data"]["access"]["output_limit_scope"]
            schema_resource = json.loads((await session.read_resource("odin://dataset/schema")).contents[0].text)
            assert schema_resource["archive_catalog"] == ARCHIVE_INDEX_URL
            assert schema_resource["example_catalog"] == SAMPLE_CATALOG_URL
            assert "bucket" not in schema_resource
            assert "boto3" not in sys.modules
    anyio.run(exercise)
    assert requests


@pytest.mark.parametrize("tool,arguments", [
    ("read_parquet_preview_tool", {"s3_uri": "s3://legacy-bucket/a.parquet"}),
    ("read_parquet_preview_tool", {"file_url": "https://example.com/a.parquet"}),
    ("read_parquet_preview_tool", {"file_url": "https://odin-smr.org/l2/a.parquet", "project": "P"}),
    ("read_parquet_preview_tool", {"rows": 0}),
    ("read_parquet_preview_tool", {"max_files": 6}),
    ("read_parquet_columns_tool", {"columns": []}),
    ("list_partition_values_tool", {"level": "unknown"}),
    ("list_parquet_files_tool", {"month": "13"}),
])
def test_invalid_requests_are_clean_errors_before_network(monkeypatch, tool, arguments):
    monkeypatch.setattr(public_http, "_client", lambda: pytest.fail("Invalid request must not use network"))
    async def exercise():
        async with create_connected_server_and_client_session(mcp) as session:
            result = payload(await session.call_tool(tool, arguments))
            assert result["ok"] is False and result["error"]
            assert "data" not in result
    anyio.run(exercise)


@pytest.mark.parametrize("value", [True, "2", 1.5])
def test_mcp_rejects_coerced_numeric_limits(monkeypatch, value):
    monkeypatch.setattr(public_http, "_client", lambda: pytest.fail("Validation must happen before network"))
    async def exercise():
        async with create_connected_server_and_client_session(mcp) as session:
            for tool, arguments in [("list_parquet_files_tool", {"limit": value}),
                                    ("read_parquet_preview_tool", {"rows": value}),
                                    ("read_parquet_columns_tool", {"columns": ["avk"], "max_files": value})]:
                assert (await session.call_tool(tool, arguments)).isError
    anyio.run(exercise)


def test_network_failure_is_not_an_empty_scientific_selection(monkeypatch):
    transport = httpx.MockTransport(lambda request: httpx.Response(503, stream=httpx.ByteStream(b"unavailable")))
    monkeypatch.setattr(public_http, "_client", lambda: httpx.Client(transport=transport, trust_env=False))
    async def exercise():
        async with create_connected_server_and_client_session(mcp) as session:
            result = payload(await session.call_tool("list_parquet_files_tool", {}))
            assert result["ok"] is False and "HTTP 503" in result["error"]
            assert "data" not in result
    anyio.run(exercise)
