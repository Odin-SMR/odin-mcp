# Odin Level2 Dataset Schema Reference

This page documents the Odin Level2 dataset shape and the meaning of its
partition structure.

Dataset location:

- [public HTTPS inventory](https://odin-smr.org/parquet/archive/index.json)

Example project names (discover the current public inventory before selection):

- `ALL-Strat-v3.0.0`
- `ALL-Meso-v3.0.0`
- `meso21`

## Partition Schema

Parquet files are partitioned in this fixed order:

1. `project`
2. `freq_mode`
3. `inv_mode`
4. `product`
5. `year`
6. `month`

Example object path:

`https://odin-smr.org/l2/project=ALL-Strat-v3.0.0/freq_mode=1/inv_mode=stnd/product=O3-501GHz-20to50km/year=2019/month=03/c8c96302988a4445ab662df76b323913-0.parquet`

## Partition Meaning

- `project`: Retrieval campaign or processing version (for example `ALL-Strat-v3.0.0`).
- `freq_mode`: Frequency mode identifier used for retrieval configuration.
- `inv_mode`: Inversion mode (`stnd`, `meso`, and similar).
- `product`: Product family and vertical or spectral definition.
- `year`: Storage year label; verify actual observation timestamps.
- `month`: Storage month label (`01` through `12`), not a row-time filter.

## Column Schema and Stability

The table below is a reference layout for historical L2 Parquet files. It does
not establish a shape-stable schema across archive generations. Verify the
selected release metadata and exact schemas before analysis.

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
- `error_total`: Source-reported retrieval error, not a complete uncertainty budget;
  verify the product-specific definition and omitted error components.
- `error_noise`: Noise contribution to uncertainty.
- `meas_response`: Measurement response.
- `apriori`: A priori profile value.
- `vmr`: Volume mixing ratio.
- `avk`: Averaging-kernel row; verify state representation, normalization and both
  coordinate axes before applying it to a reference profile.
- `processed`: Processing timestamp in UTC.

## MCP Resource

The server exposes schema information via MCP resources:

- `odin://dataset/schema` (machine-readable JSON)
- `odin://dataset/schema/guide` (human-readable markdown)

These resources help clients plan schema inspection. They do not replace
selected-release validation. Read `odin://research/topics/odin-contract` for
scientific conventions and known gaps, and `odin://research/guide` for the
source-linked research methods guide.

## Suggested Consumer Workflow

1. Discover partition values using `list_partition_values_tool`.
2. Narrow down to a target partition.
3. List files with `list_parquet_files_tool`.
4. Inspect schema with `read_parquet_preview_tool` on representative files, then
   verify schema generations across the intended selection. A preview is bounded
   and does not establish completeness or scientific validity.
5. Use `read_parquet_columns_tool` for bounded exploration. For complete analysis,
   write a reproducible local workflow that validates coverage and retains provenance.
