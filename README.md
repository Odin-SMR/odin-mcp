# Odin MCP

[![Tests](https://github.com/Odin-SMR/odin-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/Odin-SMR/odin-mcp/actions)

A local [Model Context Protocol](https://modelcontextprotocol.io/) server for
researchers working with Odin SMR Level 2 observations. It provides cited analysis
methods, dataset-layout guidance and optional read-only S3/Parquet tools to your
AI application.

The server runs on your computer over **stdio**. Your AI application supplies the
model; this package makes no LLM calls, needs no LLM API key, and does not submit
AWS analysis jobs. Guidance and schema resources work without AWS credentials or
network access after installation. Your AI application's model may still use a
remote provider, including for tool results sent to it.

## Requirements

- CPython **3.10–3.14**. Python 3.15 is not yet supported by this package's tested
  PyArrow stack. The source checkout defaults to Python 3.13.
- An AI application with support for local MCP servers using stdio.
- [uv](https://docs.astral.sh/uv/getting-started/installation/) (recommended), or
  Python with pip in a virtual environment.
- Internet access for installation unless dependencies are cached.

AWS access is optional and needed only for the direct observation-data tools.

## Install

### From a versioned release

Download a wheel from [GitHub Releases](https://github.com/Odin-SMR/odin-mcp/releases).
For version 0.1.0, install the published wheel in an isolated tool environment:

```sh
uv tool install --python 3.13 https://github.com/Odin-SMR/odin-mcp/releases/download/v0.1.0/odin_mcp-0.1.0-py3-none-any.whl
```

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
| Environment for guidance | None required |

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

| Tools | Purpose | Needs AWS access? |
| --- | --- | --- |
| `list_research_topics_tool()` | Browse topics and citations | No |
| `get_research_topic_tool(topic_id)` | Read a complete topic | No |
| `search_research_guidance_tool(query, limit=5)` | Find up to eight cited snippets | No |
| `list_partition_values_tool(...)` | Discover S3 partition values | Yes |
| `list_parquet_files_tool(...)` | List Parquet objects | Yes |
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

## Optional direct data access

The existing data tools read `s3://odin-level2` using an AWS profile already
configured on the researcher's machine. The default name is `odin`; set
`ODIN_AWS_PROFILE` in the MCP client's server environment to use another approved
profile. The profile needs permission to list the intended bucket/prefixes and
read selected objects. Use researcher-specific read-only access; never copy an
administrator's credentials or put tokens in client configuration files, chat or Git.

No login is required for the bundled guidance. Anonymous published-data access is
available separately through [odin-smr.org](https://odin-smr.org/) and its
[Parquet guide](https://odin-smr.org/parquet/guide.md); this MCP's direct readers do
not yet implement the public HTTP API.

The partition order is `project/freq_mode/inv_mode/product/year/month`. Supply the
parent partitions when narrowing a date: a missing parent stops prefix construction.
A preview is not a complete temporal or spatial sample. **A small returned row count
can still require downloading a whole Parquet object.** Start with specific files;
there is no download-byte cap. S3 requests and data transfer may incur charges even
though MCP computation runs locally.

Do not infer product validity from a filename, null quality flag or successful
read. Consult [the field guide](docs/dataset_schema.md) and the product-specific
validation sources before analysis. Do not treat Odin limb profiles as greenhouse-gas
columns or emission estimates.

## Configuration

Set optional environment variables on the client's MCP server entry:

| Variable | Default |
| --- | --- |
| `ODIN_AWS_PROFILE` | `odin` |
| `ODIN_BUCKET` | `odin-level2` |
| `ODIN_MAX_FILES_PER_READ` | `5` |
| `ODIN_MAX_ROWS_PER_READ` | `1000` (per file) |
| `ODIN_MAX_COLUMNS_PER_READ` | `20` (explicit column requests) |
| `ODIN_DEFAULT_PREVIEW_ROWS` | `100` |
| `ODIN_MAX_LIST_RESULTS` | `1000` (file-list request limit) |

These settings bound selected outputs, not total bytes downloaded or all partition
listing work. There is no hosted team-login flow, remote job execution or autonomous
reviewer in this version.

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
require explicitly authorized archive access.

## License and scientific sources

The software and original documentation are [MIT licensed](LICENSE). Referenced
papers and Odin data retain their own licenses and citation requirements. The
repository contains brief original research guidance and source links, not copies
of the articles or observational datasets.
