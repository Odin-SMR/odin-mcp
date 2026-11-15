# Odin L2-dataset

Discover the publicly indexed Odin L2 files through:

https://odin-smr.org/parquet/archive/index.json

Example Parquet URL verified in the public inventory on 2026-11-15:

https://odin-smr.org/l2/project=ALL-Strat-v3.0.0/freq_mode=1/inv_mode=stnd/product=O3-501GHz-20to50km/year=2019/month=03/c8c96302988a4445ab662df76b323913-0.parquet

Partition scheme:

- project
- freq_mode
- inv_mode
- product
- year
- month

Example project names from the existing layout (not a live or complete inventory):

- ALL-Meso-v3.0.0
- ALL-Strat-v3.0.0
- meso21

Example frequency modes:

- ALL-Meso-v3.0.0:
  - 13
  - 14
  - 19
  - 22
  - 24
- ALL-Strat-v3.0.0:
  - 1
  - 2
  - 8
  - 17
- meso21:
  - 21

Example inversion modes:

- ALL-Meso-v3.0.0:
  - meso
- ALL-Strat-v3.0.0:
  - stnd
- meso21:
  - meso

Schema reference:

- `dataset_schema.md`

MCP data tools use anonymous HTTPS without AWS credentials. Public access methods
are described in the [Odin Parquet guide](https://odin-smr.org/parquet/guide.md).
Narrow product/date filters to stay within the metadata and download budgets. Inspect the actual
release and retain input identities before interpreting observations.
