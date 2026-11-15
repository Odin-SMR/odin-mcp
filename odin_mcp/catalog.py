"""Discovery from the published Odin archive index and example-release catalog."""

from __future__ import annotations

import base64
from dataclasses import asdict, dataclass
import json
import re
from typing import Any
from urllib.parse import unquote, urlsplit

from odin_mcp.config import ARCHIVE_INDEX_URL, PARTITION_LEVELS, PUBLIC_ORIGIN, SAMPLE_CATALOG_URL
from odin_mcp.public_http import Budget, PublicDataError, absolute_metadata_url, fetch_json, validate_public_url


@dataclass(frozen=True)
class PartitionFilters:
    project: str | None = None
    freq_mode: str | None = None
    inv_mode: str | None = None
    product: str | None = None
    year: str | None = None
    month: str | None = None

    def as_mapping(self) -> dict[str, str | None]:
        result = asdict(self)
        for name, value in result.items():
            if value is None:
                continue
            if not isinstance(value, str) or not value or len(value) > 256 or any(ord(c) < 32 for c in value):
                raise PublicDataError(f"Invalid {name} filter")
            if name in ("freq_mode", "year", "month"):
                if not value.isascii() or not value.isdigit() or not 1 <= int(value) <= (12 if name == "month" else 9999):
                    raise PublicDataError(f"Invalid numeric {name} filter")
                result[name] = str(int(value))
        return result


_GROUP_FIELDS = {"project": "project", "freq_mode": "frequency_mode", "inv_mode": "inversion_mode", "product": "product"}


def _text(value: Any, label: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum or any(ord(c) < 32 for c in value):
        raise PublicDataError(f"Invalid {label} in the public catalog")
    return value


def _integer(value: Any, label: str, minimum: int = 0, maximum: int = 2**63 - 1) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise PublicDataError(f"Invalid {label} in the public catalog")
    return value


def _group_matches(group: dict[str, Any], filters: dict[str, str | None]) -> bool:
    return all(filters[name] is None or filters[name] == str(group[field]) for name, field in _GROUP_FIELDS.items())


def _file_matches(record: dict[str, Any], filters: dict[str, str | None]) -> bool:
    return all(filters[name] is None or filters[name] == str(record[name]) for name in ("year", "month"))


def _url_partitions(file_url: str) -> dict[str, str]:
    parts = urlsplit(file_url).path.split("/")
    if len(parts) != 9 or parts[1] != "l2":
        raise PublicDataError("Unsupported public archive file layout; use a URL returned by discovery")
    result = {}
    for expected, segment in zip(PARTITION_LEVELS, parts[2:8]):
        if not segment.startswith(expected + "="):
            raise PublicDataError("Unsupported public archive partition layout")
        # Decode once: a scientific product identity may itself contain %28.
        result[expected] = unquote(segment.split("=", 1)[1])
    return PartitionFilters(**result).as_mapping()


class Catalog:
    """Per-call cache only; every operation verifies its own public snapshot."""

    def __init__(self, budget: Budget):
        self.budget = budget
        self._index: dict[str, Any] | None = None
        self._index_hash: str | None = None
        self._shards: dict[str, tuple[list[dict[str, Any]], str]] = {}

    def index(self) -> tuple[dict[str, Any], str]:
        if self._index is None:
            document, digest = fetch_json(ARCHIVE_INDEX_URL, self.budget)
            snapshot = _text(document.get("snapshot_id"), "snapshot_id", 128)
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", snapshot):
                raise PublicDataError("Invalid archive snapshot ID")
            groups = document.get("groups")
            if not isinstance(groups, list) or len(groups) > 1000:
                raise PublicDataError("Invalid or oversized archive group list")
            seen = set()
            for group in groups:
                if not isinstance(group, dict):
                    raise PublicDataError("Invalid archive group")
                group_id = _text(group.get("id"), "group id", 128)
                if not re.fullmatch(r"g-[A-Za-z0-9_-]+", group_id) or group_id in seen:
                    raise PublicDataError("Invalid or duplicate archive group ID")
                seen.add(group_id)
                for key in ("project", "product", "level", "inversion_mode"):
                    _text(group.get(key), key, 256)
                _integer(group.get("frequency_mode"), "frequency_mode", 1, 9999)
                _integer(group.get("file_count"), "file_count", 0, 100000)
                _integer(group.get("size_bytes"), "size_bytes")
                expected = f"{PUBLIC_ORIGIN}/parquet/archive/{snapshot}/{group_id}.json"
                if absolute_metadata_url(_text(group.get("index_url"), "index_url")) != expected:
                    raise PublicDataError("Archive shard URL does not match its snapshot and group")
            self._index, self._index_hash = document, digest
        return self._index, self._index_hash

    def groups(self, filters: dict[str, str | None]) -> list[dict[str, Any]]:
        document, _ = self.index()
        return sorted((group for group in document["groups"] if group["level"] == "L2" and _group_matches(group, filters)), key=lambda group: group["id"])

    def shard(self, group: dict[str, Any]) -> tuple[list[dict[str, Any]], str]:
        if group["id"] not in self._shards:
            index, index_hash = self.index()
            url = absolute_metadata_url(group["index_url"])
            document, digest = fetch_json(url, self.budget)
            if document.get("snapshot_id") != index["snapshot_id"] or document.get("group_id") != group["id"]:
                raise PublicDataError("Archive shard identity differs from the index")
            files = document.get("files")
            if not isinstance(files, list) or len(files) != group["file_count"]:
                raise PublicDataError("Archive shard file count differs from the index")
            seen = set()
            records = []
            for entry in files:
                if not isinstance(entry, dict):
                    raise PublicDataError("Invalid archive file entry")
                file_url = validate_public_url(entry.get("url"), kind="parquet")
                if not urlsplit(file_url).path.startswith("/l2/") or file_url in seen:
                    raise PublicDataError("Invalid or duplicate archive file URL")
                seen.add(file_url)
                record = {"url": file_url, "size_bytes": _integer(entry.get("size_bytes"), "file size", 1),
                          "year": _integer(entry.get("year"), "year", 1, 9999),
                          "month": _integer(entry.get("month"), "month", 1, 12),
                          "etag": entry.get("etag"), "last_modified": entry.get("last_modified"),
                          "sha256": None,
                          "provenance": {"catalog_url": ARCHIVE_INDEX_URL, "index_url": url,
                              "snapshot_id": index["snapshot_id"], "group_id": group["id"],
                              "index_sha256": index_hash, "shard_sha256": digest,
                              **{key: group[key] for key in ("project", "product", "level", "frequency_mode", "inversion_mode")}}}
                if record["etag"] is not None:
                    _text(record["etag"], "ETag", 200)
                if record["last_modified"] is not None:
                    _text(record["last_modified"], "last_modified", 100)
                partition = _url_partitions(file_url)
                if not _group_matches(group, partition) or not _file_matches(record, partition):
                    raise PublicDataError("Archive file URL partitions disagree with catalog identity")
                records.append(record)
            if sum(record["size_bytes"] for record in records) != group["size_bytes"]:
                raise PublicDataError("Archive shard total size differs from the index")
            self._shards[group["id"]] = records, digest
        return self._shards[group["id"]]

    def partition_values(self, level: str, filters: PartitionFilters) -> dict[str, Any]:
        if level not in PARTITION_LEVELS:
            raise PublicDataError(f"level must be one of {PARTITION_LEVELS}")
        selection = filters.as_mapping()
        values = set()
        for group in self.groups(selection):
            if level in _GROUP_FIELDS and selection["year"] is None and selection["month"] is None:
                values.add(str(group[_GROUP_FIELDS[level]]))
            else:
                records, _ = self.shard(group)
                for record in records:
                    if _file_matches(record, selection):
                        values.add(str(group[_GROUP_FIELDS[level]]) if level in _GROUP_FIELDS else str(record[level]))
        index, _ = self.index()
        return {"level": level, "valid_levels": PARTITION_LEVELS,
                "values": sorted(values, key=int) if level in ("freq_mode", "year", "month") else sorted(values),
                "filters": selection, "snapshot_id": index["snapshot_id"], "catalog_url": ARCHIVE_INDEX_URL,
                "scope": "All supplied filters applied to published L2 archive metadata; year/month are storage labels, not row-time filters"}

    def list_files(self, filters: PartitionFilters, limit: int, continuation_token: str | None = None) -> dict[str, Any]:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= self.budget.settings.max_list_results:
            raise PublicDataError(f"limit must be between 1 and {self.budget.settings.max_list_results}")
        selection = filters.as_mapping()
        groups = self.groups(selection)
        index, index_hash = self.index()
        group_position, file_position, shard_hash = 0, 0, None
        if continuation_token is not None:
            try:
                if not isinstance(continuation_token, str) or not 1 <= len(continuation_token) <= 4096:
                    raise ValueError("Token length")
                token = json.loads(base64.b64decode(continuation_token, altchars=b"-_", validate=True))
                if not isinstance(token, dict) or not groups or set(token) != {"v", "snapshot", "index", "filters", "group", "file", "shard"}:
                    raise ValueError("Token fields")
                if type(token["v"]) is not int or token["v"] != 1 or token["snapshot"] != index["snapshot_id"] or token["index"] != index_hash or token["filters"] != selection:
                    raise ValueError("Token selection or snapshot changed")
                group_position = _integer(token["group"], "token group", 0, max(0, len(groups) - 1))
                file_position = _integer(token["file"], "token file", 0, 100000)
                shard_hash = token["shard"]
                if (shard_hash is not None and (not isinstance(shard_hash, str) or not re.fullmatch("[a-f0-9]{64}", shard_hash))) or (file_position > 0 and shard_hash is None):
                    raise ValueError("Token shard identity")
            except (ValueError, TypeError, KeyError) as exc:
                raise PublicDataError("Invalid/stale continuation token; restart discovery with the same filters") from exc
        output = []
        next_position = None
        for position in range(group_position, len(groups)):
            records, digest = self.shard(groups[position])
            start = file_position if position == group_position else 0
            if start > len(records) or (position == group_position and shard_hash is not None and shard_hash != digest):
                raise PublicDataError("Archive shard changed or continuation offset is invalid; restart discovery")
            for offset in range(start, len(records)):
                if _file_matches(records[offset], selection):
                    output.append(records[offset])
                    if len(output) == limit:
                        if offset + 1 < len(records):
                            next_position = (position, offset + 1, digest)
                        elif position + 1 < len(groups):
                            next_position = (position + 1, 0, None)
                        break
            if len(output) == limit:
                break
        next_token = None
        if next_position is not None:
            token = {"v": 1, "snapshot": index["snapshot_id"], "index": index_hash, "filters": selection,
                     "group": next_position[0], "file": next_position[1], "shard": next_position[2]}
            next_token = base64.urlsafe_b64encode(json.dumps(token, separators=(",", ":"), sort_keys=True).encode()).decode()
        return {"files": output, "file_urls": [record["url"] for record in output], "next_token": next_token,
                "has_more": next_token is not None, "requested_limit": limit, "returned_count": len(output),
                "snapshot_id": index["snapshot_id"], "catalog_url": ARCHIVE_INDEX_URL, "filters": selection,
                "pagination_note": "A continuation means catalog records remain to examine; a later page may contain no matching files. Budget failure is an error, not a partial listing.",
                "scope": "Published archive snapshot only; not proof of mission completeness, row-time coverage or scientific quality"}

    def resolve_file(self, file_url: str) -> dict[str, Any]:
        validate_public_url(file_url, kind="parquet")
        if urlsplit(file_url).path.startswith("/parquet/releases/"):
            catalog, catalog_hash = fetch_json(SAMPLE_CATALOG_URL, self.budget)
            if catalog.get("status") != "published" or not isinstance(catalog.get("releases"), list):
                raise PublicDataError("Example release catalog is not published")
            for release in catalog["releases"]:
                if not isinstance(release, dict) or not isinstance(release.get("datasets"), list):
                    raise PublicDataError("Invalid example release entry")
                for dataset in release["datasets"]:
                    if not isinstance(dataset, dict) or not isinstance(dataset.get("files"), list):
                        raise PublicDataError("Invalid example dataset entry")
                    for entry in dataset["files"]:
                        if not isinstance(entry, dict):
                            raise PublicDataError("Invalid example file entry")
                        if entry.get("url") == file_url:
                            digest = _text(entry.get("sha256"), "SHA256", 64)
                            if not re.fullmatch("[a-fA-F0-9]{64}", digest):
                                raise PublicDataError("Invalid example SHA256")
                            return {"url": file_url, "size_bytes": _integer(entry.get("size_bytes"), "file size", 1),
                                    "sha256": digest.lower(), "etag": None,
                                    "row_count": _integer(entry.get("row_count"), "row_count"),
                                    "observation_start": entry.get("observation_start"), "observation_end": entry.get("observation_end"),
                                    "provenance": {"catalog_url": SAMPLE_CATALOG_URL, "catalog_sha256": catalog_hash,
                                        "release_id": release.get("id"), "dataset_id": dataset.get("id"),
                                        **{key: dataset.get(key) for key in ("project", "product", "level", "frequency_mode", "inversion_mode")},
                                        "license": release.get("license"), "citation": release.get("citation")},
                                    "column_descriptions": dataset.get("columns", [])}
        else:
            partition = _url_partitions(file_url)
            filters = PartitionFilters(**partition).as_mapping()
            for group in self.groups(filters):
                records, _ = self.shard(group)
                for record in records:
                    if record["url"] == file_url:
                        return record
        raise PublicDataError("File URL is not present in the supported published catalogs; discover files again")
