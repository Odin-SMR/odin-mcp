# Maintainer guide

This repository owns a local stdio MCP server and bundled Odin SMR Level 2
research guidance. It does not host a model, run retrievals or submit cloud jobs.

## Source map

- `odin_mcp/server.py`: FastMCP resources, tools, prompt and stdio entry point.
- `odin_mcp/research.py` and `odin_mcp/research/`: offline topic lookup, search,
  citations and analysis-planning instructions.
- `odin_mcp/schema_resource.py`: reference layout, not a universal release schema.
- `odin_mcp/s3_browser.py`, `parquet_reader.py`, `config.py`: optional direct S3
  discovery and local Parquet reading using a researcher-supplied AWS profile.
- `tests/`: mocked data access and offline protocol tests; never use real AWS
  credentials in CI.
- `docs/llm-guide.md`: client-independent scientific workflow instructions.
- `.github/workflows/` and `docs/releasing.md`: validation and package releases.

Read the public setup in README.md for installation and launch commands. A wheel
must include the research Markdown and JSON files, and the console entry point
must work outside the source directory.

## Scientific and operational boundaries

Research documentation is a dated, cited snapshot. Product/version-specific
guidance takes precedence over assumptions from another instrument or release.
Preserve distinctions among measurement noise, smoothing, sampling variability
and systematic uncertainty. Do not silently convert retrieval coordinates,
kernel conventions or error definitions.

Existing Parquet previews may fetch whole objects despite output row limits.
Keep actual observations and generated results outside the public repository.
Use bounded requests only when the researcher authorizes direct data access.

For releases, inspect the exact staged tree and archives for personal paths,
credentials and local artifacts; test the installed package and retain the
published version's source references. See docs/releasing.md for the required
checks and workflow permissions.
