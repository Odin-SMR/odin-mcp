from __future__ import annotations

import json
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import StrictInt

from odin_mcp.config import PARTITION_LEVELS, SETTINGS
from odin_mcp.parquet_reader import read_many
from odin_mcp.research import (
    analysis_prompt,
    get_research_topic,
    list_research_topics,
    research_catalog,
    research_sources,
    search_research_guidance,
)
from odin_mcp.s3_browser import (
    PartitionFilters,
    list_parquet_files,
    list_partition_values,
)
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


@mcp.tool()
def list_partition_values_tool(
    level: str,
    project: str | None = None,
    freq_mode: str | None = None,
    inv_mode: str | None = None,
    product: str | None = None,
    year: str | None = None,
    month: str | None = None,
) -> dict[str, Any]:
    """List available partition values for a given partition level.

    The level must be one of: project, freq_mode, inv_mode, product, year, month.
    Optional filter arguments narrow the parent partition path.
    """
    try:
        values = list_partition_values(
            level=level,
            filters=_filters(
                project=project,
                freq_mode=freq_mode,
                inv_mode=inv_mode,
                product=product,
                year=year,
                month=month,
            ),
        )
        return _ok(
            {
                "bucket": SETTINGS.bucket,
                "aws_profile": SETTINGS.aws_profile,
                "level": level,
                "valid_levels": PARTITION_LEVELS,
                "values": values,
            }
        )
    except Exception as exc:
        return _error(str(exc))


@mcp.tool()
def list_parquet_files_tool(
    project: str | None = None,
    freq_mode: str | None = None,
    inv_mode: str | None = None,
    product: str | None = None,
    year: str | None = None,
    month: str | None = None,
    limit: int = 100,
    continuation_token: str | None = None,
) -> dict[str, Any]:
    """List parquet file URIs under the selected partition prefix."""
    try:
        result = list_parquet_files(
            filters=_filters(
                project=project,
                freq_mode=freq_mode,
                inv_mode=inv_mode,
                product=product,
                year=year,
                month=month,
            ),
            limit=limit,
            continuation_token=continuation_token,
        )
        return _ok(result)
    except Exception as exc:
        return _error(str(exc))


@mcp.tool()
def read_parquet_preview_tool(
    s3_uri: str | None = None,
    project: str | None = None,
    freq_mode: str | None = None,
    inv_mode: str | None = None,
    product: str | None = None,
    year: str | None = None,
    month: str | None = None,
    rows: int = SETTINGS.default_preview_rows,
    max_files: int = 1,
) -> dict[str, Any]:
    """Read parquet schema and preview rows.

    Provide either explicit s3_uri or partition filters. When filters are used,
    up to max_files parquet files are selected.
    """
    try:
        uris = [s3_uri] if s3_uri else []
        warnings: list[str] = []

        if not uris:
            listed = list_parquet_files(
                filters=_filters(
                    project=project,
                    freq_mode=freq_mode,
                    inv_mode=inv_mode,
                    product=product,
                    year=year,
                    month=month,
                ),
                limit=max_files,
            )
            uris = listed["s3_uris"]
            if not uris:
                return _error("No parquet files found for the provided filters")
            if listed.get("next_token"):
                warnings.append("More files exist under this prefix; refine filters for deterministic reads")

        result = read_many(s3_uris=uris, rows=rows, columns=None)
        result["requested"] = {
            "rows": rows,
            "max_files": max_files,
            "resolved_file_count": len(uris),
        }
        return _ok(result, warnings=warnings)
    except Exception as exc:
        return _error(str(exc))


@mcp.tool()
def read_parquet_columns_tool(
    columns: list[str],
    s3_uri: str | None = None,
    project: str | None = None,
    freq_mode: str | None = None,
    inv_mode: str | None = None,
    product: str | None = None,
    year: str | None = None,
    month: str | None = None,
    rows: int = SETTINGS.default_preview_rows,
    max_files: int = 1,
) -> dict[str, Any]:
    """Read selected columns from parquet files with row limits."""
    try:
        if not columns:
            return _error("columns must contain at least one column name")

        uris = [s3_uri] if s3_uri else []
        warnings: list[str] = []

        if not uris:
            listed = list_parquet_files(
                filters=_filters(
                    project=project,
                    freq_mode=freq_mode,
                    inv_mode=inv_mode,
                    product=product,
                    year=year,
                    month=month,
                ),
                limit=max_files,
            )
            uris = listed["s3_uris"]
            if not uris:
                return _error("No parquet files found for the provided filters")
            if listed.get("next_token"):
                warnings.append("More files exist under this prefix; refine filters for deterministic reads")

        result = read_many(s3_uris=uris, rows=rows, columns=columns)
        result["requested"] = {
            "rows": rows,
            "columns": columns,
            "max_files": max_files,
            "resolved_file_count": len(uris),
        }
        return _ok(result, warnings=warnings)
    except Exception as exc:
        return _error(str(exc))


def run() -> None:
    mcp.run()
