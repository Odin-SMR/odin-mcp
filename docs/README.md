# Odin L2-dataset

The Odin L2-dataset is available at the following bucket:

s3://odin-level2

A historical example Parquet path looks like this (discover current files through an authorized listing):

s3://odin-level2/project=ALL-Strat-v3.0.0/freq_mode=2/inv_mode=stnd/product=O3-545GHz-20to85km/year=2025/month=01/e5979a5400b04e18be54130aafa28a8e-0.parquet

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

Direct S3 tools require an approved AWS profile. Public access methods are described
in the [Odin Parquet guide](https://odin-smr.org/parquet/guide.md). A missing parent
partition prevents narrowing the prefix below that level. Inspect the actual
release and retain input identities before interpreting observations.
