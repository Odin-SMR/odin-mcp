import io

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from odin_mcp.parquet_reader import _parse_s3_uri, read_many


def test_parse_s3_uri():
    bucket, key = _parse_s3_uri("s3://odin-level2/a/b.parquet")
    assert bucket == "odin-level2"
    assert key == "a/b.parquet"


@pytest.mark.parametrize("bad_uri", ["http://x", "s3://missing-key"])
def test_parse_s3_uri_invalid(bad_uri):
    with pytest.raises(ValueError):
        _parse_s3_uri(bad_uri)


def test_read_many_enforces_file_limit(monkeypatch):
    import odin_mcp.parquet_reader as mod

    class _Settings:
        max_files_per_read = 1
        max_rows_per_read = 1000
        max_columns_per_read = 20

    monkeypatch.setattr(mod, "SETTINGS", _Settings())

    with pytest.raises(ValueError):
        read_many(["s3://odin-level2/a.parquet", "s3://odin-level2/b.parquet"], rows=10)


def test_read_many_enforces_column_limit(monkeypatch):
    import odin_mcp.parquet_reader as mod

    class _Settings:
        max_files_per_read = 5
        max_rows_per_read = 1000
        max_columns_per_read = 1

    monkeypatch.setattr(mod, "SETTINGS", _Settings())

    with pytest.raises(ValueError):
        read_many(["s3://odin-level2/a.parquet"], rows=10, columns=["a", "b"])


def test_read_many_applies_effective_rows(monkeypatch):
    import odin_mcp.parquet_reader as mod

    calls = []

    class _Settings:
        max_files_per_read = 5
        max_rows_per_read = 10
        max_columns_per_read = 20

    def _fake_read_single_file(s3_uri, max_rows, columns=None):
        calls.append((s3_uri, max_rows, columns))
        return {"s3_uri": s3_uri, "schema": [], "rows": [], "row_count": 0}

    monkeypatch.setattr(mod, "SETTINGS", _Settings())
    monkeypatch.setattr(mod, "_read_single_file", _fake_read_single_file)

    res = read_many(["s3://odin-level2/a.parquet"], rows=100)

    assert calls[0][1] == 10
    assert res["limits_applied"]["effective_rows"] == 10


def test_parquet_projection_preserves_nanoseconds_nulls_and_negative_values(monkeypatch):
    """Exercise actual Arrow decoding with synthetic bytes and a fake S3 session."""
    from odin_mcp import parquet_reader

    table = pa.table({
        "time": pa.array([1, None, 2], type=pa.timestamp("ns", tz="UTC")),
        "vmr": [-1e-9, 0.0, 1e-9],
        "quality": pa.array([None, None, None], type=pa.int64()),
        "avk": [[0.1, 0.9], None, [0.2, 0.8]],
        "unused": [10, 20, 30],
    })
    buffer = io.BytesIO()
    pq.write_table(table, buffer, row_group_size=1)
    payload = buffer.getvalue()

    class FakeClient:
        def get_object(self, *, Bucket, Key):
            assert (Bucket, Key) == ("synthetic-test", "profiles.parquet")
            return {"Body": io.BytesIO(payload)}

    class FakeSession:
        def client(self, service):
            assert service == "s3"
            return FakeClient()

    monkeypatch.setattr(parquet_reader.boto3, "Session", lambda **kwargs: FakeSession())
    result = parquet_reader._read_single_file(
        "s3://synthetic-test/profiles.parquet",
        max_rows=2,
        columns=["time", "vmr", "quality", "avk"],
    )
    assert result["row_count"] == 2
    assert result["rows"] == [
        {"time": "1970-01-01T00:00:00.000000001+00:00", "vmr": -1e-9, "quality": None, "avk": [0.1, 0.9]},
        {"time": None, "vmr": 0.0, "quality": None, "avk": None},
    ]
    assert {field["name"] for field in result["schema"]} == set(table.column_names)
