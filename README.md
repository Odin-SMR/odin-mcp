# Odin MCP

[![Tests](https://github.com/Odin-SMR/odin-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/Odin-SMR/odin-mcp/actions)

A local [Model Context Protocol](https://modelcontextprotocol.io/) server for
researchers working with Odin SMR Level 2 observations. It provides cited analysis
methods, dataset-layout guidance and anonymous HTTPS data-discovery and Parquet tools to your
AI application.

The server runs on your computer over **stdio**. Your AI application supplies the
model; this package makes no LLM calls, needs no LLM API key, and does not submit
AWS analysis jobs. No AWS credentials or API keys are needed. Guidance and schema resources also
work without network access after installation. Your AI application's model may still use a
remote provider, including for tool results sent to it.

## Requirements

- CPython **3.10–3.14**. Python 3.15 is not yet supported by this package's tested
  PyArrow stack. The source checkout defaults to Python 3.13.
- An AI application with support for local MCP servers using stdio.
- [uv](https://docs.astral.sh/uv/getting-started/installation/) (recommended), or
  Python with pip in a virtual environment.
- Internet access for installation unless dependencies are cached.

Data discovery and previews use the public HTTPS endpoints on `odin-smr.org`.
They require internet access, but no AWS account, profile or login.

## Install

### From a versioned release

Download a wheel from [GitHub Releases](https://github.com/Odin-SMR/odin-mcp/releases).
For version 0.2.0, install the published wheel in an isolated tool environment:

```sh
uv tool install --python 3.13 https://github.com/Odin-SMR/odin-mcp/releases/download/v0.2.0/odin_mcp-0.2.0-py3-none-any.whl
```

If an older version is already installed, add `--force` to the `uv tool install`
command, then restart the MCP server in your client.

uv can install the requested Python version if it is missing. Run `uv tool update-shell`
if needed, then restart your terminal so that `odin-mcp` is on PATH. You can also
install the downloaded wheel with `python -m pip install <wheel-file>` inside a
Python 3.10–3.14 virtual environment. The release includes a source distribution
and `SHA256SUMS` for integrity checking. Wheels resolve compatible dependencies;
use the source checkout and lockfile for the tested dependency versions.

Packages are distributed through GitHub Releases. Do not assume that an unrelated
package with the same name on a package index is this implementation.

### From source with locked dependencies

```sh
git clone https://github.com/Odin-SMR/odin-mcp.git
cd odin-mcp
uv python install 3.13
uv sync --locked --no-dev
```

For a specific release, check out its tag before syncing. The `.venv` environment
contains the server and its runtime dependencies. To use another supported
interpreter, pass `--python 3.12` (for example) to `uv sync`.

The pip alternative is `python -m pip install .` in an activated virtual environment;
that command does not use `uv.lock`.

## Connect your AI application

Add a local MCP server in the application's settings:

| Setting | Value |
| --- | --- |
| Name | `odin-mcp` |
| Transport | `stdio` |
| Command after tool installation | `odin-mcp`, or its absolute executable path |
| Arguments | None |
| Environment | None required for guidance or public data access |

For a source installation, use `/absolute/path/to/odin-mcp/.venv/bin/odin-mcp`
on Linux/macOS, or `C:\path\to\odin-mcp\.venv\Scripts\odin-mcp.exe` on Windows.
Use a path in the environment where the client launches processes. A Windows
application needs its supported WSL integration to launch a server installed in WSL.

For example, merge the following into VS Code's `.vscode/mcp.json`, replacing the
command with your installed executable:

```json
{
  "servers": {
    "odin-mcp": {
      "type": "stdio",
      "command": "/absolute/path/to/odin-mcp/.venv/bin/odin-mcp",
      "args": []
    }
  }
}
```

Other clients have different configuration formats. Follow your client's local
MCP instructions; [VS Code's guide](https://code.visualstudio.com/docs/agent-customization/mcp-servers)
explains its setup and tool-selection workflow. Start/enable the server and accept
the client's normal trust prompt. Restart it after installing an update.

The client launches and manages the process. There is no HTTP port to expose and
no separate terminal server to keep running. Running `odin-mcp` manually waits
for MCP messages; it does not open a chat. From a source checkout, the equivalent
launch is `uv run --no-sync odin-mcp`.

## First conversation

Ask your assistant:

> Use Odin's list_research_topics_tool to show the available analysis topics.

The bundled guide has eight topics, 15 plot recipes and 19 source records. Then try:

> Use the Odin research guidance to explain the dataset layout and help me write
> a Python script comparing seasonal N2O profiles. Explain quality screening,
> sampling and uncertainty, and cite the sources. Use guidance tools only for now.

Give the assistant [the generic LLM guide](docs/llm-guide.md) for a reusable workflow.
It works as instructions for a capable client; it does not require a hosted Odin
agent. Script execution and figure generation require a notebook or a client with
code-execution capability. These knowledge tools do not run scientific analyses.

## Capabilities

| Tools | Purpose | Needs internet? |
| --- | --- | --- |
| `list_research_topics_tool()` | Browse topics and citations | No |
| `get_research_topic_tool(topic_id)` | Read a complete topic | No |
| `search_research_guidance_tool(query, limit=5)` | Find up to eight cited snippets | No |
| `list_partition_values_tool(...)` | Discover public inventory partition values | Yes |
| `list_parquet_files_tool(...)` | List public Parquet URLs and provenance | Yes |
| `read_parquet_preview_tool(...)` | Read a small row sample and schema | Yes |
| `read_parquet_columns_tool(...)` | Select columns and limit returned rows | Yes |

Responses have `ok: true` with `warnings` and `data`, or `ok: false` with `error`.
Search understands chemical subscripts such as N₂O. Read the full matched topic
before using a method; short snippets can omit qualifications.

Resources:

- `odin://dataset/schema` — machine-readable reference layout.
- `odin://dataset/schema/guide` — human-readable field guidance.
- `odin://research/guide` — research overview and navigation.
- `odin://research/catalog` — topic index.
- `odin://research/sources` — bibliography, source scope and checked dates.
- `odin://research/topics/{topic_id}` — an individual topic.

The prompt `plan_odin_analysis(question, product?)` helps establish the selected
product/version, screening, coordinates, sampling and uncertainty before plotting.
The literature guide is a dated snapshot, not a live literature search or a
validation of arbitrary measurements.

## Anonymous HTTPS data access

The data tools use the public JSON discovery endpoints
[`/parquet/archive/index.json`](https://odin-smr.org/parquet/archive/index.json)
and [`/parquet/catalog.json`](https://odin-smr.org/parquet/catalog.json), then read
selected public Parquet files over HTTPS. Discovery and numerical decoding happen
on the researcher's machine. No AWS SDK, credentials, signed requests or cloud
analysis jobs are involved.

The archive index is a dated metadata snapshot. Its file inventory is not a
scientific-completeness or quality guarantee. The separate catalog identifies
selected tutorial examples and their checksums. The public profile API's reduced
JSON projection is not substituted for original Parquet fields such as priors
and averaging kernels. Do not infer validity from a filename, a null quality
flag or a successful read. Odin limb profiles are not greenhouse-gas columns
or emission estimates.

For a first data request, ask the assistant:

> List a few public files for ALL-Strat-v3.0.0, frequency mode 1, inversion mode
> stnd, O3-501GHz-20to50km, March 2019. Then read five rows from one returned URL,
> keeping its provenance and explaining why the preview is not a monthly mean.

Use `list_parquet_files_tool` to obtain `file_urls`, then supply one as `file_url`
to a preview or column-read tool. Narrowing the project/product and dates reduces
metadata work. Follow continuation tokens for the intended file selection; a
single page or preview does not establish complete temporal or spatial coverage.
Partition year/month labels do not replace filtering actual observation timestamps.

Downloads, metadata, decoding and returned JSON have explicit limits. A small row
count can still require fetching the selected file. Oversized requests fail with
an explanation so that you can narrow the request or use a separate local script;
arrays and profiles must not be silently shortened to fit. Source nulls stay null;
non-finite numeric values are represented explicitly as strings rather than invalid
JSON numbers, with the representation stated in the result.

Only approved public Odin HTTPS URLs are accepted. Redirects, credential-bearing
URLs and unrelated hosts are rejected. HTTP failures and empty selections are
different outcomes. Retain the reported source identity and checksum status;
ETags alone are not scientific content checksums. Consult the
[public Parquet guide](https://odin-smr.org/parquet/guide.md) and
[field guide](docs/dataset_schema.md) before interpreting observations.

### Upgrading from 0.1.0

The four data-tool names remain, but their transport and file-reference contract
change in 0.2.0: use `file_url` and `file_urls` instead of `s3_uri` and `s3_uris`.
Rediscover files through the HTTPS tools; do not mechanically rewrite S3 URIs.
Remove `ODIN_AWS_PROFILE` and `ODIN_BUCKET` from client settings: they are no longer
used. Research tools, resources and the planning prompt remain available offline.

## Configuration

Set optional environment variables on the client's MCP server entry:

| Variable | Default |
| --- | --- |
| `ODIN_MAX_FILES_PER_READ` | `5` |
| `ODIN_MAX_ROWS_PER_READ` | `1000` (per file) |
| `ODIN_MAX_COLUMNS_PER_READ` | `20` (preview or explicit selection) |
| `ODIN_DEFAULT_PREVIEW_ROWS` | `100` |
| `ODIN_MAX_LIST_RESULTS` | `1000` (file-list request limit) |

The default HTTPS work limits are:

| Setting / limit | Default |
| --- | --- |
| `ODIN_MAX_METADATA_RESPONSE_BYTES` | 2 MiB (2097152 bytes) |
| `ODIN_MAX_METADATA_BYTES` per call | 16 MiB (16777216 bytes) |
| `ODIN_MAX_HTTP_REQUESTS` per call | 32 |
| `ODIN_MAX_FILE_BYTES` | 32 MiB (33554432 bytes) |
| `ODIN_MAX_DOWNLOAD_BYTES` per call | 64 MiB (67108864 bytes) |
| `ODIN_MAX_DECODED_BYTES` selected row-group size per call | 64 MiB (67108864 bytes) |
| `ODIN_MAX_OUTPUT_BYTES` compact logical JSON result, including arrays | 1 MiB (1048576 bytes) |
| Connect / read inactivity timeout (fixed) | 5 / 15 seconds |
| `ODIN_OPERATION_TIMEOUT_SECONDS` checked deadline | 60 seconds |

MCP clients may receive the same result as both text and structured content, so
the protocol message can exceed the logical JSON limit. The decoding guard uses Parquet metadata; it is not an operating-system memory
limit or a hard interruption of native decoding. Narrow an oversized request or
use a separate scientific script. Results report the applied limits and transfer
work so clients can distinguish row sampling from download volume. There is no
hosted team-login flow, remote job execution or autonomous reviewer in this version.

## Development and releases

```sh
uv sync --locked --no-dev --group test
uv run --no-sync python -m pytest tests -q
```

Tests use synthetic fixtures or mocked archive operations, and verify guidance
without network access. CI covers supported Python versions and checks built
packages. See [the maintainer guide](docs/agent-guide.md) and
[release procedures](docs/releasing.md) for the build, secret scan, artifact checks
and tagged GitHub release workflow.

For manual tool inspection, run `npx @modelcontextprotocol/inspector` and connect
using stdio with the same executable and no arguments. Guidance inspection needs
no AWS credentials; the optional [data test cases](tests/inspector/manual_test_cases.md)
use anonymous HTTPS and should be run only when a real data read is intended.

## License and scientific sources

The software and original documentation are [MIT licensed](LICENSE). Referenced
papers and Odin data retain their own licenses and citation requirements. The
repository contains brief original research guidance and source links, not copies
of the articles or observational datasets.
