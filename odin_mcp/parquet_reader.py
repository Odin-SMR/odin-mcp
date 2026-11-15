"""Bounded decoding of exact, catalog-verified public Parquet objects."""

from __future__ import annotations

import base64
from datetime import date, datetime
from decimal import Decimal
import io
import math
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from odin_mcp.public_http import Budget, PublicDataError, fetch_bytes


def _normalize(value: Any) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        return "NaN" if math.isnan(value) else ("Infinity" if value > 0 else "-Infinity")
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]
    if isinstance(value, dict):
        return {key: _normalize(item) for key, item in value.items()}
    return value


def _metadata(metadata: dict[bytes, bytes] | None) -> list[dict[str, str]]:
    return [{"key_base64": base64.b64encode(key).decode("ascii"),
             "value_base64": base64.b64encode(value).decode("ascii")}
            for key, value in (metadata or {}).items()]


def validate_read_request(rows: int, columns: list[str] | None, budget: Budget) -> None:
    if isinstance(rows, bool) or not isinstance(rows, int) or not 1 <= rows <= budget.settings.max_rows_per_read:
        raise PublicDataError(f"rows must be between 1 and {budget.settings.max_rows_per_read}")
    if columns is not None:
        if (not isinstance(columns, list) or not 1 <= len(columns) <= budget.settings.max_columns_per_read
                or any(not isinstance(name, str) or not name or len(name) > 256 for name in columns)
                or len(set(columns)) != len(columns)):
            raise PublicDataError(f"columns must contain 1 to {budget.settings.max_columns_per_read} unique column names")


def _read_single_file(record: dict[str, Any], max_rows: int, columns: list[str] | None, budget: Budget) -> dict[str, Any]:
    body, receipt = fetch_bytes(record["url"], budget, purpose="data", expected_size=record["size_bytes"],
                                expected_etag=record.get("etag"))
    expected_digest = record.get("sha256")
    if expected_digest is not None and receipt["sha256"] != expected_digest:
        raise PublicDataError("Downloaded SHA256 differs from the published release checksum")
    if len(body) < 12 or body[:4] != b"PAR1" or body[-4:] != b"PAR1":
        raise PublicDataError("Public object is not an unencrypted Parquet file")
    footer_size = int.from_bytes(body[-8:-4], "little")
    if footer_size > min(2**21, len(body) - 12):
        raise PublicDataError("Parquet footer is invalid or exceeds the 2 MiB metadata limit")
    try:
        parquet = pq.ParquetFile(io.BytesIO(body), thrift_string_size_limit=2**20,
                                 thrift_container_size_limit=50000)
        schema = parquet.schema_arrow
        if len(set(schema.names)) != len(schema.names):
            raise PublicDataError("Duplicate physical column names are not supported")
        selected = schema.names if columns is None else columns
        if len(selected) > budget.settings.max_columns_per_read:
            raise PublicDataError("File has too many columns for a preview; request an explicit column selection")
        missing = set(selected) - set(schema.names)
        if missing:
            raise PublicDataError(f"Columns not found in Parquet file: {sorted(missing)}")
        if record.get("row_count") is not None and record["row_count"] != parquet.metadata.num_rows:
            raise PublicDataError("Parquet row count differs from the release catalog")
        rows = []
        for group_number in range(parquet.num_row_groups):
            if len(rows) >= max_rows:
                break
            group = parquet.metadata.row_group(group_number)
            estimate = sum(group.column(i).total_uncompressed_size for i in range(group.num_columns)
                           if any(group.column(i).path_in_schema == name or group.column(i).path_in_schema.startswith(name + ".")
                                  for name in selected))
            budget.reserve_decoded(estimate)
            table = parquet.read_row_group(group_number, columns=selected, use_threads=False)
            budget.check_time()
            if table.nbytes > estimate:
                budget.reserve_decoded(table.nbytes - estimate)
            table = table.slice(0, max_rows - len(rows))
            budget.output_arrow_bytes += table.nbytes
            if budget.output_arrow_bytes > budget.settings.max_output_bytes:
                raise PublicDataError("Selected Arrow values exceed the output budget; request fewer rows/columns")
            rows.extend(_normalize(row) for row in table.to_pylist())
            budget.check_output(rows)
        result = {"file_url": record["url"], "schema": [
            {"name": field.name, "type": str(field.type), "nullable": field.nullable,
             "metadata": _metadata(field.metadata)} for field in schema],
            "schema_metadata": _metadata(schema.metadata), "selected_columns": selected,
            "rows": rows, "row_count": len(rows), "total_rows": parquet.metadata.num_rows,
            "rows_truncated": len(rows) < parquet.metadata.num_rows,
            "catalog_entry": record, "download": receipt,
            "checksum_status": "verified_against_published_sha256" if expected_digest else "observed_sha256_only_no_published_checksum",
            "validator_note": "ETag is an opaque HTTP validator, not a scientific content checksum"}
        budget.check_output(result)
        return result
    except (pa.ArrowException, OSError, OverflowError) as exc:
        raise PublicDataError("Parquet decoding failed; no complete preview was produced") from exc


def read_many(records: list[dict[str, Any]], rows: int, columns: list[str] | None = None,
              *, budget: Budget | None = None) -> dict[str, Any]:
    budget = budget or Budget()
    validate_read_request(rows, columns, budget)
    if not 1 <= len(records) <= budget.settings.max_files_per_read:
        raise PublicDataError(f"Read requires 1 to {budget.settings.max_files_per_read} files")
    result = {"files": [_read_single_file(record, rows, columns, budget) for record in records],
              "limits_applied": {"max_files_per_read": budget.settings.max_files_per_read,
                  "max_rows_per_read": budget.settings.max_rows_per_read,
                  "max_columns_per_read": budget.settings.max_columns_per_read, "effective_rows_per_file": rows},
              "transfer_note": "Whole files are downloaded. Row and column limits reduce decoded/output values, not transfer size.",
              "serialization_policy": {"nonfinite_floats": "Explicit strings NaN, Infinity, -Infinity; true null remains JSON null",
                  "timestamps": "ISO 8601 preserving source precision and timezone", "binary": "hexadecimal strings",
                  "decimal": "decimal strings", "schema_metadata": "base64 preserves original bytes"},
              "scope": "Physical row preview only; rows may cut across scans/profiles. No quality screening, unit conversion or row-time filtering applied."}
    budget.check_output(result)
    return result
