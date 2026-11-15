# Working on Odin MCP

Read README.md and docs/agent-guide.md before changing this repository. For
scientific use of the service, follow docs/llm-guide.md and the cited research
guidance. Repository instructions do not grant access to data or cloud resources.

- Preserve scientific units, coordinates, missingness, product/version identity,
  quality diagnostics, uncertainty and provenance. Do not invent global quality
  thresholds or treat a successful tool call as scientific validation.
- Keep guidance tools usable without network access or AWS credentials.
- Never commit credentials, environment files, local machine settings, downloaded
  observations or generated figures. Use synthetic fixtures in offline tests.
- Use approved read-only credentials only when a user explicitly requests real
  data access. Do not initiate paid computation or deployment from a test.
- Coordinate file ownership when several people or agents work in the checkout;
  preserve unrelated edits and never reset, stash or switch another worker's branch.
- Test every supported Python version through the CI matrix and verify built
  package contents. Follow docs/releasing.md for releases.

Report changes, checks actually run and remaining limitations. Distinguish local
test evidence from live service behavior and scientific equivalence.
