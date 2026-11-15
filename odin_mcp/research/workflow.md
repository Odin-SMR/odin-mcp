# From a researcher question to a reproducible analysis

This is a proposed working protocol for Odin research assistance. It separates a literature-supported method, a selected dataset and an executed calculation. The service's new research tools implement the first of these.

## Conversation and execution sequence

1. **Frame the question.** Name species/quantity, layer, region, time interval and whether the target is a sampled mean, climatology, validation, event or trend.
2. **Select evidence.** Read the relevant topics and source records; distinguish historical studies from current release documentation.
3. **Identify inputs.** Select a release and product/version/modes; enumerate the complete intended file set. Inspect exact schemas and units; preserve source identifiers.
4. **Audit quality and coverage.** Check duplicates, fill values, time/coordinate conventions, screening applicability and missing diagnostics. Report scan counts, days and sampled locations before aggregation.
5. **Specify the method.** Declare estimator, coordinates, bins, weights, uncertainty, matching, auxiliary inputs and kernel conventions. Identify prerequisites that are absent.
6. **Run a bounded pilot.** Produce the first profile/coverage plot and machine-readable diagnostics. Inspect raw values and exclusion reasons; do not silently tune rules to improve agreement.
7. **Execute and assess.** Run the reproducible workflow over its intended selection; compare justified sensitivity cases. Keep scientific claims within the evidence.
8. **Share results with provenance.** Export figures, aggregate/count tables, code/environment and the analysis record. Distinguish an unscreened exploratory output from a screened scientific estimate.

## Existing data-tool limits

`list_parquet_files_tool` returns a bounded listing: follow continuation tokens for the intended selection. `read_parquet_preview_tool` and `read_parquet_columns_tool` return limited rows/files, which may truncate profiles. They are discovery tools, not a complete monthly/climatology query. Do not average a preview and call it the month. The current reader downloads a selected object's bytes before applying its output-row limit: small returned tables do not imply small transfers. Metadata, file/total download, decoding and response limits are enforced separately. Use a separate local workflow when a request exceeds them; do not silently truncate scientific arrays.

Data tools discover files through the public HTTPS inventory/catalog and read public Parquet downloads without AWS credentials. Pass a returned `file_urls` entry as `file_url`; do not invent download paths from old S3 URIs. Research tools/resources work offline and do not query observations. Public documentation includes the [Parquet guide](https://odin-smr.org/parquet/guide.md) and [file browser](https://odin-smr.org/data_access/files); availability and release completeness still need checking at execution time. Inventory snapshots establish listed files, not scientific completeness. Retain the response's provenance, checksum status and non-finite-value representation when exporting a preview.

## Analysis record template

```json
{
  "status": "proposal | exploratory | analysed",
  "question": "...",
  "selection": {
    "release": "...", "project": "...", "product": "...",
    "frequency_mode": "...", "inversion_mode": "...",
    "utc_start_inclusive": "...", "utc_end_exclusive": "...",
    "region": "...", "vertical_domain_and_units": "..."
  },
  "inputs": [{"uri": "...", "version_or_checksum": "... or unavailable"}],
  "schema_generation": "...",
  "screening": {"source_version_and_locator": "...", "rules": [], "rejections": {}},
  "method": {
    "topic_ids": [], "coordinates": "...", "bins": [], "estimator": "...",
    "weights": "...", "uncertainty": "...", "kernel_basis": "verified ... | unused | unresolved"
  },
  "coverage": {"profiles": null, "days": null, "missing_bins": null},
  "auxiliary_inputs_and_collocation": [],
  "code_revision_environment_parameters": "...",
  "outputs": [], "limitations": [], "source_ids": []
}
```

This is a documentation template, not an implemented validation schema. An S3 ETag is not automatically a content checksum. If immutable input IDs or full hashes are unavailable, retain the observed size/ETag/access date and disclose the limit.

## Discussion prompts

- “For this N2O product, what observations would distinguish transport from a long-term abundance change?”
- “Before drawing a latitude–height climatology, audit the sampling and propose an explicit estimator.”
- “Compare Odin with MLS: which averaging-kernel and covariance prerequisites are missing?”
- “Explain what each uncertainty band represents and which errors it omits.”
- “Design an event analysis; identify external meteorology and alternative explanations.”

Responses should link the relevant sources, state what is unknown, and name the next data check. They must not invent results, a successful screening status, current data availability or executed calculations.
