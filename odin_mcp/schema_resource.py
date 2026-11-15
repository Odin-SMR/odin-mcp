from __future__ import annotations

import json

from odin_mcp.config import ARCHIVE_INDEX_URL, PARTITION_LEVELS, SAMPLE_CATALOG_URL


OFFICIAL_PRODUCTION_PROJECTS = [
  "ALL-Strat-v3.0.0",
  "ALL-Meso-v3.0.0",
  "meso21",
]


DATASET_COLUMNS = [
  {"name": "time", "type": "timestamp[ns, tz=UTC]", "description": "Observation timestamp in UTC."},
  {"name": "scan_id", "type": "int64", "description": "Scan identifier."},
  {"name": "mjd", "type": "double", "description": "Modified Julian Date."},
  {"name": "lat_1d", "type": "double", "description": "1D geolocation latitude."},
  {"name": "lon_1d", "type": "double", "description": "1D geolocation longitude."},
  {"name": "quality", "type": "int64", "description": "Source quality flag/value; null is unknown, not a successful quality check."},
  {"name": "altitude", "type": "double", "description": "Retrieval altitude coordinate."},
  {"name": "pressure", "type": "double", "description": "Retrieval pressure coordinate."},
  {"name": "latitude", "type": "double", "description": "Geolocation latitude."},
  {"name": "longitude", "type": "double", "description": "Geolocation longitude."},
  {"name": "temperature", "type": "double", "description": "Temperature value."},
  {"name": "error_total", "type": "double", "description": "Source-reported retrieval error; not a complete uncertainty budget. Verify the product-specific definition."},
  {"name": "error_noise", "type": "double", "description": "Noise uncertainty contribution."},
  {"name": "meas_response", "type": "double", "description": "Measurement response."},
  {"name": "apriori", "type": "double", "description": "A priori profile value."},
  {"name": "vmr", "type": "double", "description": "Volume mixing ratio."},
  {"name": "avk", "type": "list<element: double>", "description": "Averaging-kernel row; verify state representation, normalization and both coordinate axes before use."},
  {"name": "processed", "type": "timestamp[us, tz=UTC]", "description": "Processing timestamp in UTC."},
]


def dataset_schema_json() -> str:
  payload = {
    "dataset": "odin-level2",
    "archive_catalog": ARCHIVE_INDEX_URL,
    "example_catalog": SAMPLE_CATALOG_URL,
    "shape_stability": "reference_layout_only",
    "schema_scope": "Expected historical L2 layout, not a guarantee across archive generations. Verify selected release and file schemas.",
    "research_guide": "odin://research/topics/odin-contract",
    "official_production_projects": OFFICIAL_PRODUCTION_PROJECTS,
    "partition_levels": PARTITION_LEVELS,
    "partition_meaning": {
      "project": "Processing campaign/model configuration.",
      "freq_mode": "Frequency mode identifier used by retrieval configuration.",
      "inv_mode": "Inversion mode.",
      "product": "Product family and retrieval window.",
      "year": "Storage year label; verify actual row timestamps.",
      "month": "Storage month label (01-12); not a row-time filter.",
    },
    "columns": DATASET_COLUMNS,
  }
  return json.dumps(payload, indent=2)


def dataset_schema_markdown() -> str:
    levels = "\n".join(f"- `{level}`" for level in PARTITION_LEVELS)
    return f"""# Odin Level2 Dataset Schema Guide

This resource explains the dataset structure and common field meanings for
the public catalog at {ARCHIVE_INDEX_URL}. Obtain exact HTTPS file URLs from
discovery; partition examples are reference layouts, not guaranteed objects.

Official production projects:

- `ALL-Strat-v3.0.0`
- `ALL-Meso-v3.0.0`
- `meso21`

## 1. Partition Layout

Parquet files are partitioned by the following levels (in order):

{levels}

Reference archive path layout:

`https://odin-smr.org/l2/project=ALL-Strat-v3.0.0/freq_mode=2/inv_mode=stnd/product=O3-545GHz-20to85km/year=2025/month=01/<file>.parquet`

Partition meaning:

- `project`: Processing campaign/model configuration (for example `ALL-Strat-v3.0.0`).
- `freq_mode`: Frequency mode identifier used by the retrieval chain.
- `inv_mode`: Inversion mode (`stnd`, `meso`, ...).
- `product`: Product family and retrieval window.
- `year`: Storage year label; verify actual row timestamps.
- `month`: Storage month label (`01`-`12`); not a row-time filter.

## 2. Column Schema

The following is a reference layout for historical Odin Level2 Parquet files.
It is not a validated schema contract across all releases or generations.
Inspect the selected release metadata and exact file schemas before analysis.

| # | name | type |
|---|------|------|
| 1 | `time` | `timestamp[ns, tz=UTC]` |
| 2 | `scan_id` | `int64` |
| 3 | `mjd` | `double` |
| 4 | `lat_1d` | `double` |
| 5 | `lon_1d` | `double` |
| 6 | `quality` | `int64` |
| 7 | `altitude` | `double` |
| 8 | `pressure` | `double` |
| 9 | `latitude` | `double` |
| 10 | `longitude` | `double` |
| 11 | `temperature` | `double` |
| 12 | `error_total` | `double` |
| 13 | `error_noise` | `double` |
| 14 | `meas_response` | `double` |
| 15 | `apriori` | `double` |
| 16 | `vmr` | `double` |
| 17 | `avk` | `list<element: double>` |
| 18 | `processed` | `timestamp[us, tz=UTC]` |

Field meaning summary:

- `time`: Observation timestamp in UTC.
- `scan_id`: Scan identifier.
- `mjd`: Modified Julian Date.
- `lat_1d` / `lon_1d`: 1D geolocation coordinates.
- `quality`: Source quality flag/value; null means unknown, not good quality.
- `altitude`: Retrieval altitude coordinate.
- `pressure`: Retrieval pressure coordinate.
- `latitude` / `longitude`: Geolocation coordinates.
- `temperature`: Temperature value.
- `error_total`: Source-reported retrieval error, not a complete uncertainty budget.
- `error_noise`: Noise contribution to uncertainty.
- `meas_response`: Measurement response.
- `apriori`: A priori profile value.
- `vmr`: Volume mixing ratio.
- `avk`: Averaging-kernel row; verify state representation and both coordinate axes.
- `processed`: Processing timestamp in UTC.

## 3. Recommended Usage Pattern

1. Use `list_partition_values_tool` to discover valid partition values.
2. Use `list_parquet_files_tool` to select one representative file per target partition.
3. Use `read_parquet_preview_tool` to retrieve the exact schema.
4. Use `read_parquet_columns_tool` for stable, projected reads in workflows.

## 4. Notes

- The MCP server is read-only.
- Type strings in schema output come from Arrow.
- These reference type strings describe an expected layout; a preview reports
  the actual selected file schema. One representative file does not validate an
  entire release. Check schema generations across the intended selection.
- Read `odin://research/topics/odin-contract` before applying screening, error
  propagation or averaging kernels; retained column names do not establish their
  scientific conventions for every release.
"""
