from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
import io
from typing import Any

import boto3
import pyarrow.parquet as pq

from odin_mcp.config import SETTINGS


def _parse_s3_uri(s3_uri: str) -> tuple[str, str]:
    if not s3_uri.startswith("s3://"):
        raise ValueError("s3_uri must start with s3://")
    rest = s3_uri[5:]
    if "/" not in rest:
        raise ValueError("s3_uri must include a key")
    bucket, key = rest.split("/", 1)
    return bucket, key


def _normalize(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, list):
        return [_normalize(v) for v in value]
    if isinstance(value, dict):
        return {k: _normalize(v) for k, v in value.items()}
    return value


def _read_single_file(
    s3_uri: str,
    max_rows: int,
    columns: list[str] | None = None,
) -> dict[str, Any]:
    session = boto3.Session(profile_name=SETTINGS.aws_profile)
    client = session.client("s3")
    bucket, key = _parse_s3_uri(s3_uri)

    rows: list[dict[str, Any]] = []
    response = client.get_object(Bucket=bucket, Key=key)
    body = response["Body"].read()
    with io.BytesIO(body) as f:
        parquet = pq.ParquetFile(f)
        schema = [
            {"name": field.name, "type": str(field.type)}
            for field in parquet.schema_arrow
        ]

        if columns:
            existing = {field["name"] for field in schema}
            missing = [name for name in columns if name not in existing]
            if missing:
                raise ValueError(f"Columns not found in parquet file: {missing}")

        for row_group in range(parquet.num_row_groups):
            if len(rows) >= max_rows:
                break
            table = parquet.read_row_group(row_group, columns=columns)
            for row in table.to_pylist():
                rows.append({k: _normalize(v) for k, v in row.items()})
                if len(rows) >= max_rows:
                    break

    return {
        "s3_uri": s3_uri,
        "schema": schema,
        "rows": rows,
        "row_count": len(rows),
    }


def read_many(
    s3_uris: list[str],
    rows: int,
    columns: list[str] | None = None,
) -> dict[str, Any]:
    if len(s3_uris) > SETTINGS.max_files_per_read:
        raise ValueError(
            f"Requested {len(s3_uris)} files, max is {SETTINGS.max_files_per_read}"
        )

    effective_rows = min(max(rows, 1), SETTINGS.max_rows_per_read)

    if columns and len(columns) > SETTINGS.max_columns_per_read:
        raise ValueError(
            f"Requested {len(columns)} columns, max is {SETTINGS.max_columns_per_read}"
        )

    files: list[dict[str, Any]] = []
    for s3_uri in s3_uris:
        files.append(_read_single_file(s3_uri=s3_uri, max_rows=effective_rows, columns=columns))

    return {
        "files": files,
        "limits_applied": {
            "max_files_per_read": SETTINGS.max_files_per_read,
            "max_rows_per_read": SETTINGS.max_rows_per_read,
            "max_columns_per_read": SETTINGS.max_columns_per_read,
            "effective_rows": effective_rows,
        },
    }
