"""Synthetic Arrow fixtures exercise scientific fidelity without network access."""
import base64
from dataclasses import replace
import hashlib
import io

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from odin_mcp import parquet_reader as reader
from odin_mcp.config import SETTINGS
from odin_mcp.public_http import Budget, PublicDataError


@pytest.fixture
def source(monkeypatch):
    table = pa.table({
        "time": pa.array([1, None, 2], type=pa.timestamp("ns", tz="UTC")),
        "vmr": [-1e-9, float("nan"), float("inf")],
        "quality": pa.array([None, None, None], type=pa.int64()),
        "avk": [[0.1, 0.9], None, [float("-inf"), 0.8]],
        "unused": [10, 20, 30],
    }).replace_schema_metadata({b"units": b"source-specific", b"binary": b"\xff"})
    output = io.BytesIO()
    pq.write_table(table, output, row_group_size=2)
    payload = output.getvalue()
    record = {"url": "https://odin-smr.org/parquet/releases/test/files/a.parquet",
              "size_bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest(),
              "row_count": 3, "etag": None, "provenance": {"project": "P"}}
    calls = []
    def fetch(url, budget, **kwargs):
        calls.append((url, kwargs))
        budget.consume("data", len(payload))
        return payload, {"url": url, "size_bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}
    monkeypatch.setattr(reader, "fetch_bytes", fetch)
    return record, payload, calls


def test_projection_preserves_nanoseconds_nulls_negatives_kernels_and_nonfinite(source):
    record, payload, calls = source
    result = reader.read_many([record], rows=3, columns=["time", "vmr", "quality", "avk"])
    item = result["files"][0]
    assert item["rows"] == [
        {"time": "1970-01-01T00:00:00.000000001+00:00", "vmr": -1e-9, "quality": None, "avk": [0.1, 0.9]},
        {"time": None, "vmr": "NaN", "quality": None, "avk": None},
        {"time": "1970-01-01T00:00:00.000000002+00:00", "vmr": "Infinity", "quality": None, "avk": ["-Infinity", 0.8]},
    ]
    assert {field["name"] for field in item["schema"]} == {"time", "vmr", "quality", "avk", "unused"}
    assert item["catalog_entry"]["provenance"]["project"] == "P"
    assert "project" not in item["rows"][0]  # catalog partitions are not physical columns
    assert item["checksum_status"] == "verified_against_published_sha256"
    assert item["rows_truncated"] is False
    assert calls[0][1]["expected_size"] == len(payload)
    assert {base64.b64decode(entry["key_base64"]): base64.b64decode(entry["value_base64"])
            for entry in item["schema_metadata"]} == {b"units": b"source-specific", b"binary": b"\xff"}


def test_row_limit_is_explicit_and_does_not_reduce_transfer(source):
    record, payload, _ = source
    budget = Budget()
    item = reader.read_many([record], 1, ["time", "avk"], budget=budget)["files"][0]
    assert item["row_count"] == 1 and item["total_rows"] == 3 and item["rows_truncated"]
    assert budget.download_bytes == len(payload)
    assert budget.decoded_bytes > 0


def test_archive_hash_is_observed_not_claimed_as_published(source):
    record, _, _ = source
    record["sha256"] = None
    item = reader.read_many([record], 1)["files"][0]
    assert item["checksum_status"] == "observed_sha256_only_no_published_checksum"


def test_checksum_mismatch_prevents_decoding(source, monkeypatch):
    record, _, _ = source
    record["sha256"] = "f" * 64
    monkeypatch.setattr(reader.pq, "ParquetFile", lambda *a, **kw: pytest.fail("must not decode"))
    with pytest.raises(PublicDataError, match="SHA256"):
        reader.read_many([record], 1)


def test_catalog_row_count_mismatch(source):
    record, _, _ = source
    record["row_count"] = 2
    with pytest.raises(PublicDataError, match="row count"):
        reader.read_many([record], 1)


@pytest.mark.parametrize("rows", [0, -1, 1001, True, 1.5])
def test_rows_rejected_before_io(source, rows):
    record, _, calls = source
    with pytest.raises(PublicDataError, match="rows"):
        reader.read_many([record], rows)
    assert calls == []


@pytest.mark.parametrize("columns", [[], ["avk", "avk"], [""], [1], ["x"] * 21])
def test_bad_column_requests_rejected_before_io(source, columns):
    record, _, calls = source
    with pytest.raises(PublicDataError, match="columns"):
        reader.read_many([record], 1, columns)
    assert calls == []


def test_missing_column_is_explicit_error(source):
    with pytest.raises(PublicDataError, match="Columns not found"):
        reader.read_many([source[0]], 1, ["missing"])


def test_implicit_preview_column_limit(source):
    with pytest.raises(PublicDataError, match="too many columns"):
        reader.read_many([source[0]], 1, budget=Budget(replace(SETTINGS, max_columns_per_read=2)))


def test_file_limit_before_io(source):
    with pytest.raises(PublicDataError, match="files"):
        reader.read_many([source[0]] * 6, 1)
    assert source[2] == []


def test_decode_budget_prevents_arrow_read(source, monkeypatch):
    monkeypatch.setattr(reader.pq.ParquetFile, "read_row_group", lambda *a, **kw: pytest.fail("decode must not begin"))
    with pytest.raises(PublicDataError, match="decode budget"):
        reader.read_many([source[0]], 1, budget=Budget(replace(SETTINGS, max_decoded_bytes=1)))


def test_nested_array_output_budget_is_an_error(source):
    with pytest.raises(PublicDataError, match="output budget"):
        reader.read_many([source[0]], 1, ["avk"], budget=Budget(replace(SETTINGS, max_output_bytes=1)))


@pytest.mark.parametrize("payload", [b"not parquet", b"PAR1data" + (2**22).to_bytes(4, "little") + b"PAR1",
                                     b"PAR1data" + (4).to_bytes(4, "little") + b"PAR1"])
def test_invalid_parquet_does_not_return_partial_rows(monkeypatch, payload):
    monkeypatch.setattr(reader, "fetch_bytes", lambda *a, **kw: (payload, {"sha256": "observed"}))
    with pytest.raises(PublicDataError):
        reader.read_many([{"url": "https://odin-smr.org/l2/x.parquet", "size_bytes": len(payload)}], 1)
