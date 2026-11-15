# Manual HTTPS MCP checks

These optional checks use public Odin HTTPS metadata and small observations.
Do not run live-data checks in automated CI; unit tests use mocked responses and
synthetic Parquet fixtures. No AWS account, credentials or profile is required.

## Connect

Install the package, run `npx @modelcontextprotocol/inspector`, and select stdio.
Use command `odin-mcp` (or the installed executable's absolute path) with no
arguments. Start with `list_research_topics_tool` and `get_research_topic_tool`
for `overview`; these calls should also work without network access.

## Discovery

1. Call `list_partition_values_tool` with `{"level": "project"}`. Expect public
   inventory project values and snapshot provenance.
2. Call `list_parquet_files_tool` with:

   ```json
   {
     "project": "ALL-Strat-v3.0.0",
     "freq_mode": "1",
     "inv_mode": "stnd",
     "product": "O3-501GHz-20to50km",
     "year": "2019",
     "month": "03",
     "limit": 5
   }
   ```

   Expect HTTPS `file_urls`, matching file provenance and explicit pagination.
   Follow `next_token` using the same filters when `has_more` is true. A storage
   partition is not an assertion that every row lies within those dates.

## Preview and selected columns

Choose a small file from the listing. Pass its exact URL as `file_url` to
`read_parquet_preview_tool`, with `rows: 5`. Expect the actual schema, five or fewer
rows, source identity and download/serialization information. A preview may split
profiles and is not a representative monthly mean.

For a column read, pass the same URL to `read_parquet_columns_tool` with
`columns: ["time", "scan_id", "altitude", "vmr", "avk"]` and `rows: 3`, after
checking those columns exist. Inspect timestamps, nulls, negative values if any,
and intact averaging-kernel arrays. Do not interpret an AVK without its grids and
state convention. Check whether a checksum was verified or only an opaque ETag
was available. No scientific quality selection is added by the transport.

## Error and budget behavior

- An unknown partition level must return `ok: false`.
- An unrelated URL, HTTP URL, URL with credentials or redirect must be rejected.
- An old `s3_uri` input must return actionable HTTPS migration guidance.
- Oversized metadata, files, decoding requests and serialized results must fail
  explicitly, without silently shortening arrays or claiming complete coverage.
- A missing column and HTTP/network failure must differ from an empty selection.
- Credentials must never be requested or included in logs or reports.

Selected-column and row limits reduce returned values; the current implementation
still downloads complete bounded files. Prefer synthetic tests for intentional
oversize/error cases rather than requesting large real archive objects.
