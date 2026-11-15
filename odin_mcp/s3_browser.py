from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import boto3

from odin_mcp.config import PARTITION_LEVELS, SETTINGS


@dataclass(frozen=True)
class PartitionFilters:
    project: str | None = None
    freq_mode: str | None = None
    inv_mode: str | None = None
    product: str | None = None
    year: str | None = None
    month: str | None = None

    def as_mapping(self) -> dict[str, str | None]:
        return {
            "project": self.project,
            "freq_mode": self.freq_mode,
            "inv_mode": self.inv_mode,
            "product": self.product,
            "year": self.year,
            "month": self.month,
        }


def _build_prefix(filters: PartitionFilters, stop_before_level: str | None = None) -> str:
    prefix_parts: list[str] = []
    filter_map = filters.as_mapping()

    for level in PARTITION_LEVELS:
        if stop_before_level == level:
            break
        value = filter_map[level]
        if value is None:
            break
        prefix_parts.append(f"{level}={value}")

    if not prefix_parts:
        return ""
    return "/".join(prefix_parts) + "/"


def _client():
    session = boto3.Session(profile_name=SETTINGS.aws_profile)
    return session.client("s3")


def _parse_partition_value(prefix_item: str, level: str) -> str | None:
    part = prefix_item.strip("/").split("/")[-1]
    expected = f"{level}="
    if not part.startswith(expected):
        return None
    return part[len(expected) :]


def list_partition_values(level: str, filters: PartitionFilters) -> list[str]:
    if level not in PARTITION_LEVELS:
        raise ValueError(f"Invalid level '{level}'. Expected one of {PARTITION_LEVELS}")

    client = _client()
    prefix = _build_prefix(filters, stop_before_level=level)

    paginator = client.get_paginator("list_objects_v2")
    pages = paginator.paginate(
        Bucket=SETTINGS.bucket,
        Prefix=prefix,
        Delimiter="/",
        PaginationConfig={"PageSize": 1000},
    )

    values: set[str] = set()
    for page in pages:
        for common in page.get("CommonPrefixes", []):
            parsed = _parse_partition_value(common["Prefix"], level)
            if parsed is not None:
                values.add(parsed)

    return sorted(values)


def list_parquet_files(
    filters: PartitionFilters,
    limit: int,
    continuation_token: str | None = None,
) -> dict[str, Any]:
    requested = max(1, limit)
    effective_limit = min(requested, SETTINGS.max_list_results)

    client = _client()
    prefix = _build_prefix(filters)

    kwargs: dict[str, Any] = {
        "Bucket": SETTINGS.bucket,
        "Prefix": prefix,
        "MaxKeys": min(1000, effective_limit),
    }
    if continuation_token:
        kwargs["ContinuationToken"] = continuation_token

    response = client.list_objects_v2(**kwargs)

    keys = [
        item["Key"]
        for item in response.get("Contents", [])
        if item["Key"].endswith(".parquet")
    ][:effective_limit]

    return {
        "s3_uris": [f"s3://{SETTINGS.bucket}/{key}" for key in keys],
        "next_token": response.get("NextContinuationToken"),
        "requested_limit": requested,
        "effective_limit": effective_limit,
        "prefix": prefix,
    }
