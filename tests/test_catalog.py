"""Catalog fixtures retain exact identity and exercise complete/error pagination."""
import base64
import copy
from dataclasses import replace
import hashlib
import json
from urllib.parse import quote

import pytest

from odin_mcp import catalog as mod
from odin_mcp.catalog import Catalog, PartitionFilters
from odin_mcp.config import ARCHIVE_INDEX_URL, SAMPLE_CATALOG_URL, SETTINGS
from odin_mcp.public_http import Budget, PublicDataError


@pytest.fixture
def archive(monkeypatch):
    documents = {}
    groups = []
    for name, product, frequency, months in [("a", "O3", 1, [1, 3, 3]), ("b", "N2O", 2, [3])]:
        group = {"id": "g-" + name, "project": "P", "product": product, "level": "L2",
                 "frequency_mode": frequency, "inversion_mode": "stnd", "file_count": len(months),
                 "size_bytes": 100 * len(months), "index_url": f"/parquet/archive/snapshot/g-{name}.json"}
        groups.append(group)
        files = [{"url": f"https://odin-smr.org/l2/project=P/freq_mode={frequency}/inv_mode=stnd/product={product}/year=2019/month={month:02d}/{i}.parquet",
                  "size_bytes": 100, "year": 2019, "month": month, "etag": f"test-{i}",
                  "last_modified": "2026-01-01T00:00:00Z"} for i, month in enumerate(months)]
        documents["https://odin-smr.org" + group["index_url"]] = {"schema_version": 1, "snapshot_id": "snapshot", "group_id": group["id"], "files": files}
    documents[ARCHIVE_INDEX_URL] = {"schema_version": 1, "snapshot_id": "snapshot", "groups": groups}
    calls = []
    def fetch(url, budget):
        calls.append(url)
        if url not in documents:
            raise PublicDataError("Synthetic metadata failure")
        document = copy.deepcopy(documents[url])
        digest = hashlib.sha256(json.dumps(document, sort_keys=True).encode()).hexdigest()
        return document, digest
    monkeypatch.setattr(mod, "fetch_json", fetch)
    return documents, calls


def test_all_filters_apply_when_parent_partitions_are_omitted(archive):
    catalog = Catalog(Budget())
    result = catalog.list_files(PartitionFilters(product="O3", month="03"), 100)
    assert len(result["files"]) == 2
    assert all(entry["month"] == 3 and entry["provenance"]["product"] == "O3" for entry in result["files"])
    assert result["filters"]["month"] == "3"
    assert result["has_more"] is False
    assert "row-time" in result["scope"]
    assert all(len(entry["provenance"][key]) == 64 for entry in result["files"] for key in ("index_sha256", "shard_sha256"))
    assert all("g-b" not in url for url in archive[1])


def test_project_discovery_uses_index_only_but_respects_later_filters(archive):
    result = Catalog(Budget()).partition_values("project", PartitionFilters(product="N2O"))
    assert result["values"] == ["P"]
    assert archive[1] == [ARCHIVE_INDEX_URL]
    assert Catalog(Budget()).partition_values("product", PartitionFilters(freq_mode="1", month="3"))["values"] == ["O3"]
    assert Catalog(Budget()).partition_values("product", PartitionFilters(month="2"))["values"] == []


def test_pagination_covers_matching_files_once(archive):
    output, token = [], None
    for _ in range(10):
        result = Catalog(Budget()).list_files(PartitionFilters(month="3"), 1, token)
        output.extend(result["file_urls"])
        token = result["next_token"]
        if token is None:
            break
    assert len(output) == 3 and len(set(output)) == 3
    assert output == Catalog(Budget()).list_files(PartitionFilters(month="3"), 100)["file_urls"]


def test_end_page_can_be_empty_without_false_coverage_claim(archive):
    first = Catalog(Budget()).list_files(PartitionFilters(month="1"), 1)
    assert first["has_more"]
    last = Catalog(Budget()).list_files(PartitionFilters(month="1"), 1, first["next_token"])
    assert last["files"] == [] and not last["has_more"]
    assert "may contain no matching files" in last["pagination_note"]


@pytest.mark.parametrize("mutation", ["index", "shard", "filters"])
def test_continuation_rejects_changed_metadata_or_filters(archive, mutation):
    docs, _ = archive
    token = Catalog(Budget()).list_files(PartitionFilters(), 1)["next_token"]
    filters = PartitionFilters()
    if mutation == "index":
        docs[ARCHIVE_INDEX_URL]["generated_at"] = "changed"
    elif mutation == "shard":
        docs["https://odin-smr.org/parquet/archive/snapshot/g-a.json"]["files"][1]["etag"] = "changed"
    else:
        filters = PartitionFilters(month="3")
    with pytest.raises(PublicDataError, match="changed|stale"):
        Catalog(Budget()).list_files(filters, 1, token)


@pytest.mark.parametrize("token", ["", "not-a-token", "A" * 5000, base64.b64encode(b'[]').decode(), base64.b64encode(b'null').decode()])
def test_invalid_token_is_clean_error(archive, token):
    with pytest.raises(PublicDataError, match="token"):
        Catalog(Budget()).list_files(PartitionFilters(), 1, token)


def test_invalid_cursor_without_shard_hash_is_rejected(archive):
    token = Catalog(Budget()).list_files(PartitionFilters(), 1)["next_token"]
    data = json.loads(base64.urlsafe_b64decode(token))
    data["shard"] = None
    changed = base64.urlsafe_b64encode(json.dumps(data).encode()).decode()
    with pytest.raises(PublicDataError, match="token"):
        Catalog(Budget()).list_files(PartitionFilters(), 1, changed)


def test_metadata_failure_never_returns_partial_listing(archive):
    del archive[0]["https://odin-smr.org/parquet/archive/snapshot/g-b.json"]
    with pytest.raises(PublicDataError, match="metadata failure"):
        Catalog(Budget()).list_files(PartitionFilters(), 100)


@pytest.mark.parametrize("field,value", [("url", "https://odin-smr.org/l2/project=OTHER/freq_mode=1/inv_mode=stnd/product=O3/year=2019/month=01/a.parquet"),
                                         ("year", 2020), ("month", 2), ("size_bytes", 101)])
def test_catalog_identity_or_size_mismatch_is_rejected(archive, field, value):
    archive[0]["https://odin-smr.org/parquet/archive/snapshot/g-a.json"]["files"][0][field] = value
    with pytest.raises(PublicDataError, match="disagree|total size"):
        Catalog(Budget()).list_files(PartitionFilters(product="O3"), 1)


def test_literal_percent_product_identity_is_decoded_once_and_url_unchanged(archive):
    docs, _ = archive
    product = "Temperature-557%28Fmode13%29-45to90km"
    group = docs[ARCHIVE_INDEX_URL]["groups"][0]
    group["product"] = product
    shard = docs["https://odin-smr.org" + group["index_url"]]
    for entry in shard["files"]:
        entry["url"] = entry["url"].replace("product=O3", "product=" + quote(product, safe=""))
    exact_url = shard["files"][0]["url"]
    result = Catalog(Budget()).resolve_file(exact_url)
    assert result["url"] == exact_url
    assert result["provenance"]["product"] == product
    assert "%2528" in result["url"]


def test_exact_manifest_membership_is_required(archive):
    listed = Catalog(Budget()).list_files(PartitionFilters(), 1)["file_urls"][0]
    with pytest.raises(PublicDataError, match="not present"):
        Catalog(Budget()).resolve_file(listed.replace("0.parquet", "invented.parquet"))


@pytest.mark.parametrize("url", ["s3://bucket/a.parquet", "https://example.com/l2/a.parquet", "https://odin-smr.org/l2/../a.parquet"])
def test_unsafe_url_rejected_before_metadata_io(archive, url):
    with pytest.raises(PublicDataError):
        Catalog(Budget()).resolve_file(url)
    assert archive[1] == []


@pytest.mark.parametrize("filters", [PartitionFilters(month="13"), PartitionFilters(year="nan"), PartitionFilters(project=""), PartitionFilters(freq_mode="²")])
def test_bad_filters_rejected_before_io(archive, filters):
    with pytest.raises(PublicDataError):
        Catalog(Budget()).list_files(filters, 1)
    assert archive[1] == []


@pytest.mark.parametrize("limit", [True, 0, -1, 1001, 1.5])
def test_bad_limit_rejected_before_io(archive, limit):
    with pytest.raises(PublicDataError):
        Catalog(Budget()).list_files(PartitionFilters(), limit)
    assert archive[1] == []


def test_sample_release_checksum_and_provenance(archive):
    url = "https://odin-smr.org/parquet/releases/example/files/a.parquet"
    archive[0][SAMPLE_CATALOG_URL] = {"schema_version": 1, "status": "published", "releases": [{"id": "example", "license": {"name": "CC BY"}, "citation": "source", "datasets": [
        {"id": "l2", "level": "L2", "project": "P", "product": "O3", "columns": [{"name": "vmr", "unit": "1"}], "files": [{"url": url, "size_bytes": 100, "sha256": "a" * 64, "row_count": 3, "observation_start": "2020-01-01T00:00:00Z", "observation_end": None}]}]}]}
    record = Catalog(Budget()).resolve_file(url)
    assert record["sha256"] == "a" * 64 and record["row_count"] == 3
    assert record["observation_end"] is None
    assert record["provenance"]["release_id"] == "example"
    assert len(record["provenance"]["catalog_sha256"]) == 64
    assert record["column_descriptions"] == [{"name": "vmr", "unit": "1"}]


@pytest.mark.parametrize("releases", [[None], [{"datasets": None}], [{"datasets": [None]}], [{"datasets": [{"files": [None]}]}]])
def test_malformed_release_entries_fail_cleanly(archive, releases):
    archive[0][SAMPLE_CATALOG_URL] = {"schema_version": 1, "status": "published", "releases": releases}
    with pytest.raises(PublicDataError, match="Invalid"):
        Catalog(Budget()).resolve_file("https://odin-smr.org/parquet/releases/example/files/a.parquet")
