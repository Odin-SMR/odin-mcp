from __future__ import annotations

import json
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import StrictInt

from odin_mcp.config import SETTINGS
from odin_mcp.parquet_reader import read_many, validate_read_request
from odin_mcp.public_http import Budget, PublicDataError
from odin_mcp.research import (
    analysis_prompt,
    get_research_topic,
    list_research_topics,
    research_catalog,
    research_sources,
    search_research_guidance,
)
from odin_mcp.catalog import Catalog, PartitionFilters
from odin_mcp.schema_resource import dataset_schema_json, dataset_schema_markdown

mcp = FastMCP("odin-level2")


@mcp.resource("odin://dataset/schema")
def dataset_schema_resource() -> str:
    """Machine-readable JSON schema for Odin dataset partitions and columns."""
    return dataset_schema_json()


@mcp.resource("odin://dataset/schema/guide")
def dataset_schema_guide_resource() -> str:
    """Human-readable Odin dataset schema guide in Markdown."""
    return dataset_schema_markdown()


def _filters(
    project: str | None = None,
    freq_mode: str | None = None,
    inv_mode: str | None = None,
    product: str | None = None,
    year: str | None = None,
    month: str | None = None,
) -> PartitionFilters:
    return PartitionFilters(
        project=project,
        freq_mode=freq_mode,
        inv_mode=inv_mode,
        product=product,
        year=year,
        month=month,
    )


def _ok(data: dict[str, Any], warnings: list[str] | None = None) -> dict[str, Any]:
    return {
        "ok": True,
        "warnings": warnings or [],
        "data": data,
    }


def _error(message: str) -> dict[str, Any]:
    return {
        "ok": False,
        "error": message,
    }


@mcp.resource("odin://research/guide", mime_type="text/markdown")
def research_guide_resource() -> str:
    """Start here: source-linked Odin L2 plots, methods and scientific paradigms."""
    return get_research_topic("overview")["markdown"]


@mcp.resource("odin://research/catalog", mime_type="application/json")
def research_catalog_resource() -> str:
    """Versioned index of bundled research topics; no credentials required."""
    return json.dumps(research_catalog(), ensure_ascii=False, indent=2)


@mcp.resource("odin://research/sources", mime_type="application/json")
def research_sources_resource() -> str:
    """Bibliography with source URLs, scope and checked date."""
    return json.dumps(research_sources(), ensure_ascii=False, indent=2)


@mcp.resource("odin://research/topics/{topic_id}", mime_type="text/markdown")
def research_topic_resource(topic_id: str) -> str:
    """Read a topic ID from the catalog, with its literature citations."""
    return get_research_topic(topic_id)["markdown"]


_RESEARCH_ANNOTATIONS = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)


@mcp.tool(annotations=_RESEARCH_ANNOTATIONS)
def list_research_topics_tool() -> dict[str, Any]:
    """List offline Odin research guidance, topic URIs and supporting sources."""
    return _ok(list_research_topics())


@mcp.tool(annotations=_RESEARCH_ANNOTATIONS)
def get_research_topic_tool(topic_id: str) -> dict[str, Any]:
    """Read a documented plot/method topic and citations; does not analyse data."""
    try:
        return _ok(get_research_topic(topic_id))
    except ValueError as exc:
        return _error(str(exc))


@mcp.tool(annotations=_RESEARCH_ANNOTATIONS)
def search_research_guidance_tool(query: str, limit: StrictInt = 5) -> dict[str, Any]:
    """Search local literature guidance and aliases; return up to 8 cited snippets.

    No AWS credentials, web request or numerical analysis is needed.
    """
    try:
        return _ok(search_research_guidance(query, limit))
    except ValueError as exc:
        return _error(str(exc))


@mcp.prompt()
def plan_odin_analysis(question: str, product: str | None = None) -> str:
    """Plan a scientifically explicit Odin analysis using source-linked guidance."""
    return analysis_prompt(question, product)


_DATA_ANNOTATIONS = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=True)


def _data_ok(data: dict[str, Any], budget: Budget, warnings: list[str] | None = None) -> dict[str, Any]:
    data["access"] = budget.receipt()
    response = _ok(data, warnings)
    budget.check_output(response)
    return response


@mcp.tool(annotations=_DATA_ANNOTATIONS)
def list_partition_values_tool(
    level: str, project: str | None = None, freq_mode: str | None = None,
    inv_mode: str | None = None, product: str | None = None,
    year: str | None = None, month: str | None = None,
) -> dict[str, Any]:
    """Discover published L2 partition values over anonymous HTTPS.

    Apply all provided filters. Year/month are storage labels, not row-time
    filters. A budget error never represents a complete empty selection.
    """
    try:
        budget = Budget()
        result = Catalog(budget).partition_values(level, _filters(project, freq_mode, inv_mode, product, year, month))
        return _data_ok(result, budget)
    except ValueError as exc:
        return _error(str(exc))


@mcp.tool(annotations=_DATA_ANNOTATIONS)
def list_parquet_files_tool(
    project: str | None = None, freq_mode: str | None = None,
    inv_mode: str | None = None, product: str | None = None,
    year: str | None = None, month: str | None = None,
    limit: StrictInt = 100, continuation_token: str | None = None,
) -> dict[str, Any]:
    """List published HTTPS Parquet URLs and provenance with snapshot-bound pagination.

    All filters apply, including when earlier partition levels are omitted.
    Follow next_token with identical filters; errors are not partial coverage.
    """
    try:
        budget = Budget()
        result = Catalog(budget).list_files(_filters(project, freq_mode, inv_mode, product, year, month), limit, continuation_token)
        return _data_ok(result, budget)
    except ValueError as exc:
        return _error(str(exc))


def _read(file_url: str | None, s3_uri: str | None, filters: PartitionFilters,
          rows: int, max_files: int, columns: list[str] | None) -> dict[str, Any]:
    try:
        if s3_uri is not None:
            raise PublicDataError("s3_uri is no longer supported. Discover public file_urls with list_parquet_files_tool and pass file_url; AWS credentials are not used.")
        budget = Budget()
        validate_read_request(rows, columns, budget)
        if isinstance(max_files, bool) or not isinstance(max_files, int) or not 1 <= max_files <= budget.settings.max_files_per_read:
            raise PublicDataError(f"max_files must be between 1 and {budget.settings.max_files_per_read}")
        selection = filters.as_mapping()
        catalog = Catalog(budget)
        warnings = ["Preview rows can split scans/profiles; inspect full coverage before scientific analysis.",
                    "Non-finite numbers are strings NaN/Infinity/-Infinity; true missing values remain null."]
        if file_url is not None:
            if any(value is not None for value in selection.values()):
                raise PublicDataError("Use either file_url or partition filters, not both")
            records = [catalog.resolve_file(file_url)]
            listing = {"file_urls": [file_url], "selection": "exact catalog-listed URL"}
        else:
            listing = catalog.list_files(filters, max_files)
            records = listing["files"]
            if not records:
                raise PublicDataError("No published Parquet files match the supplied storage filters")
            if listing["has_more"]:
                warnings.append("Additional catalog records remain. The selected files are a bounded preview, not complete coverage.")
        result = read_many(records, rows, columns, budget=budget)
        result["file_selection"] = {key: value for key, value in listing.items() if key != "files"}
        result["requested"] = {"rows_per_file": rows, "max_files": max_files, "columns": columns}
        return _data_ok(result, budget, warnings)
    except ValueError as exc:
        return _error(str(exc))


@mcp.tool(annotations=_DATA_ANNOTATIONS)
def read_parquet_preview_tool(
    file_url: str | None = None, s3_uri: str | None = None,
    project: str | None = None, freq_mode: str | None = None,
    inv_mode: str | None = None, product: str | None = None,
    year: str | None = None, month: str | None = None,
    rows: StrictInt = SETTINGS.default_preview_rows, max_files: StrictInt = 1,
) -> dict[str, Any]:
    """Read actual Parquet schema and bounded rows over anonymous HTTPS.

    Supply an exact catalog-listed file_url, or storage partition filters.
    Whole files are transferred within byte budgets. No quality screening or
    time filtering occurs. Legacy s3_uri returns migration guidance.
    """
    return _read(file_url, s3_uri, _filters(project, freq_mode, inv_mode, product, year, month), rows, max_files, None)


@mcp.tool(annotations=_DATA_ANNOTATIONS)
def read_parquet_columns_tool(
    columns: list[str], file_url: str | None = None, s3_uri: str | None = None,
    project: str | None = None, freq_mode: str | None = None,
    inv_mode: str | None = None, product: str | None = None,
    year: str | None = None, month: str | None = None,
    rows: StrictInt = SETTINGS.default_preview_rows, max_files: StrictInt = 1,
) -> dict[str, Any]:
    """Read selected physical columns, preserving nulls, nanoseconds and kernels.

    Supply an exact catalog-listed file_url, or storage partition filters.
    Row/column limits do not reduce full-file HTTPS transfer. Nested arrays are
    subject to the output budget; no automatic scientific filtering is applied.
    """
    return _read(file_url, s3_uri, _filters(project, freq_mode, inv_mode, product, year, month), rows, max_files, columns)


def run() -> None:
    mcp.run()
