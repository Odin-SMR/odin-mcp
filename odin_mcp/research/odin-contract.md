# Odin fields, provenance and limits

This topic distinguishes published documentation, inspected local source and selected-file evidence. Source inspection on 2026-11-15 is not proof that every archive file was produced by that revision. Always inspect the actual release/schema before executing a recipe.

## Identity and coordinates

Keep project/retrieval version, product, frequency mode, inversion mode, scan ID and source-file/release identity together. Preserve processing timestamp separately from observation time. `year` and `month` partitions do not replace filtering actual UTC observation timestamps. A reprocessed scan must not silently become an extra independent observation.

The inspected L2 writer produces one vertical sample per row. The published example dictionary gives gas `vmr`, `apriori`, `error_noise` and `error_total` in mol/mol, altitude in m, pressure in Pa, temperature in K, and positions in degrees. Conversions: ppmv = mol/mol × 10^6; ppbv = mol/mol × 10^9; km = m / 1000; hPa = Pa / 100. These gas-unit statements do not establish units of temperature or other non-gas retrieval products. [Published example schema](https://odin-smr.org/parquet/releases/odin-parquet-examples-20261113/schema.md)

Pressure plots conventionally decrease upward on a logarithmic axis. Height, pressure, potential temperature and tropopause-relative coordinates are distinct. Retain the source height definition; do not relabel geometric height as geopotential height or infer a universal height–pressure conversion. Per-level `latitude`/`longitude` and scan-reference `lat_1d`/`lon_1d` have different roles: document which drives bin assignment.

## Which interface contains what?

| Source | Information found in inspected code | Constraint |
| --- | --- | --- |
| L2 Parquet writer | VMR, prior, pressure/height, temperatures, geolocation, errors, response; one `avk` row per vertical sample | Actual arrays/nulls and archive generation must be checked |
| Cloud `/products` projection | VMR, response, temperature, pressure/height and optional errors | Does not carry full kernels/prior, quality and complete campaign/mode provenance |
| L2I | Fit/residual and convergence diagnostics, spectral/channel association, offsets | Generations differ; verify scan/STW/channel keys and array order before joining |

The writer retains a same-product averaging-kernel block, not the entire multi-state retrieval matrix. Diagonal-derived errors are not full covariance matrices. Never reconstruct off-diagonal correlations from those errors.

## Averaging-kernel representation is unresolved per release

Historical L2 documentation describes gas kernels as relative-change quantities. The inspected pinned QSMR source instead retains log-state kernels when `LOG_ON` is active and rescales non-log kernels. Neither establishes a universal basis for every published Parquet product. Require the release-specific state transformation, normalization, input/output grids and provenance before applying an observation operator. [L2 format guide, printed pp.3,7](https://odin-smr.org/documents/L2_DATA.pdf)

When sorting a profile, preserve both kernel-row and kernel-column correspondence. Filtering output levels does not authorize dropping input columns: sensitivity can extend beyond the retained output interval. See `averaging-comparisons` for the conditional formula.

## Source inspection provenance

- `qsmr-system` 72515176b4ad3039b078d0ff80b1b38d130a828f, `src/qsmr_system/dataset.py` lines 21–185: output fields and mapping.
- Consumed QSMR submodule 2dc25ba3, `Mscripts_arts/q2_inv.m` lines 620–633, 698–736: grid selection, kernel block, error definition, kernel transformation, response row sum and `Quality = NaN`. Scientific inputs pin cb53ce30.
- `odin-cloud-api` 2c6a8a4a8348078b960002552cbc299ba0dcf908, `app/models.py` and `app/main.py`: API projection.
- `odin-ui` d45af648364d492280bf2e7abb1a7f626c8c6ece, `public/parquet/schema-guide.md` and release example schema: documented generations and units.

These identifiers record maintainer source inspection. Access to those repositories and revisions has not been established for public readers, so these findings may not be independently verifiable from this package alone. They are not public download guarantees or a substitute for release-specific validation. No new archive reads or numerical equivalence tests were performed for this guide. Existing schema resources describe an expected layout; inspecting a representative file is a discovery step, not a complete release validation.
