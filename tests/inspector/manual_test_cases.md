# MCP Inspector Manual Test Cases

These tests validate the MCP tool surface with a real stdio session.

## Prerequisites

1. For the observation checks below only, a researcher-specific read-only AWS profile is authenticated and data access is authorized. Guidance inspection requires no AWS login.
2. Project dependencies are installed.
3. Server command is available as odin-mcp.

## Start Inspector

Run inspector:

- npx @modelcontextprotocol/inspector

In the inspector UI, connect using stdio transport with:

- Command: odin-mcp
- Args: (leave empty)

If odin-mcp is not found, use an absolute command path:

- Command: /absolute/path/to/odin-mcp/.venv/bin/odin-mcp
- Args: (leave empty)

Do not use this invalid combination:

- Command: /absolute/path/to/odin-mcp/.venv/bin/python
- Args: odin-mcp

The invalid combination makes Python try to open a local file named odin-mcp.

### Troubleshooting connection setup

If the inspector log says `command=--command` and `spawn --command ENOENT`,
the UI has stale saved values from an older launch pattern.

Fix it in the connect form before pressing Connect:

- Command must be: odin-mcp (or absolute path above)
- Args must be empty
- Transport type must be: stdio

If it still auto-fills `--command`:

- Open the inspector URL in a private/incognito browser window
- Or clear site storage for localhost:6274 and reload

## Test Cases

First call `list_research_topics_tool` and read `overview` using
`get_research_topic_tool`; these checks work without AWS credentials. The remaining
cases access observations. Select a current file URI from the listing result rather
than assuming the historical example below is accessible. Preview row limits do
not cap object-download bytes. Never run these live-data checks in CI.

### 1. List top-level projects

Tool: list_partition_values_tool
Input:
{
  "level": "project"
}

Expected:

- ok is true.
- data.level is project.
- data.values contains at least one value.
- data.values should include known projects from docs when accessible:
  - ALL-Meso-v3.0.0
  - ALL-Strat-v3.0.0
  - meso21

### 2. List freq_mode for ALL-Strat

Tool: list_partition_values_tool
Input:
{
  "level": "freq_mode",
  "project": "ALL-Strat-v3.0.0"
}

Expected:

- ok is true.
- data.values contains one or more string values.
- Typical values may include 1, 2, 8, 17.

### 3. List parquet files in a narrow partition

Tool: list_parquet_files_tool
Input:
{
  "project": "ALL-Strat-v3.0.0",
  "freq_mode": "2",
  "inv_mode": "stnd",
  "product": "O3-545GHz-20to85km",
  "year": "2025",
  "month": "01",
  "limit": 5
}

Expected:

- ok is true.
- data.s3_uris is a list with 0..5 items.
- each uri starts with s3://odin-level2/ and ends with .parquet.
- data.effective_limit is <= 5.

### 4. Preview rows from explicit file

Tool: read_parquet_preview_tool
Input:
{
  "s3_uri": "s3://odin-level2/project=ALL-Strat-v3.0.0/freq_mode=2/inv_mode=stnd/product=O3-545GHz-20to85km/year=2025/month=01/e5979a5400b04e18be54130aafa28a8e-0.parquet",
  "rows": 10
}

Expected:

- ok is true.
- data.files length is 1.
- data.files[0].schema is non-empty.
- data.files[0].row_count is <= 10.

### 5. Read selected columns

Tool: read_parquet_columns_tool
Input:
{
  "s3_uri": "s3://odin-level2/project=ALL-Strat-v3.0.0/freq_mode=2/inv_mode=stnd/product=O3-545GHz-20to85km/year=2025/month=01/e5979a5400b04e18be54130aafa28a8e-0.parquet",
  "columns": ["time", "lat", "lon"],
  "rows": 20
}

Expected:

- ok is true if these columns exist.
- all returned row objects only contain requested column keys.
- data.limits_applied.effective_rows is <= 20.

### 6. Validate hard limits

Tool: read_parquet_columns_tool
Input:
{
  "s3_uri": "s3://odin-level2/project=ALL-Strat-v3.0.0/freq_mode=2/inv_mode=stnd/product=O3-545GHz-20to85km/year=2025/month=01/e5979a5400b04e18be54130aafa28a8e-0.parquet",
  "columns": ["c1", "c2", "c3", "c4", "c5", "c6", "c7", "c8", "c9", "c10", "c11", "c12", "c13", "c14", "c15", "c16", "c17", "c18", "c19", "c20", "c21"],
  "rows": 10
}

Expected:

- ok is false.
- error contains max columns text.

### 7. Invalid partition level

Tool: list_partition_values_tool
Input:
{
  "level": "invalid_level"
}

Expected:

- ok is false.
- error contains Invalid level.

## Notes

- Dataset contents can evolve. For data-dependent checks, validate shape and constraints before exact row values.
- If AWS access is not available, tests should fail with ok false and an auth/access error message.
