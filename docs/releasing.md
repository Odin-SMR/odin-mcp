# Testing and releasing Odin MCP

GitHub Actions tests the local service and publishes Python packages to
[GitHub Releases](https://github.com/Odin-SMR/odin-mcp/releases). A PyPI account,
AWS credentials and an LLM account are not needed for these workflows.

## Continuous integration

Every branch push and pull request runs:

- Offline tests on CPython 3.10, 3.11, 3.12, 3.13 and 3.14 on Linux.
- The same tests on Python 3.13 on Windows and macOS.
- Gitleaks 8.30.1 against fetched Git history, with findings redacted.
- A wheel and source-distribution build, metadata checks, a strict archive file
  allowlist, package/source identity checks and SHA-256 checksums.
- Tests of the installed wheel outside the source checkout.

The matrix installs the checked-in lock using the selected interpreter. The
build uses the locked backend without build isolation. This tests the published
dependency versions; it is not a guarantee for every future dependency release.
No test should contact AWS or download observations. Archive and secret checks
complement human review; they cannot prove that every kind of sensitive text has
been identified.

## Local release checks

Use a clean source checkout and Python 3.13:

```sh
uv sync --locked --no-dev --group test --group build --python 3.13
uv run --no-sync python -m pytest tests -q
uv run --no-sync python -m build --no-isolation
uv run --no-sync python -m twine check --strict dist/*
uv run --no-sync python scripts/check_release.py
```

The `dist` directory must contain exactly one wheel and one `.tar.gz` source
distribution, plus the generated `SHA256SUMS`. Use a clean build directory for
each version; do not mix old and new packages. The archive checker requires
Python 3.11+ and compares bundled package files to the checkout. Its allowlist
excludes local environment and IDE configuration, downloaded data, plots, caches
and internal coordination files. It reports a rule name and file path rather
than printing a matching secret.

Before a public push, review `git diff --cached`, including new files, and scan
the prospective tree with Gitleaks. CI runs after a push, so it cannot prevent
the first exposure of a secret. Keep real credentials and observations outside
Git. If a credential is exposed, revoke/rotate it; removing its latest copy does
not erase it from history.

## Publish a version

1. Update `project.version` in `pyproject.toml`, refresh `uv.lock`, and review the
   source/reference changes. Versions use stable `MAJOR.MINOR.PATCH` numbers.
2. Merge the reviewed changes to `main` and wait for CI to pass.
3. Tag that commit and push the tag, for example:

   ```sh
   git tag -a v0.1.0 -m "Odin MCP 0.1.0"
   git push origin v0.1.0
   ```

The `Release` workflow reruns the complete CI workflow at the tag. After all
checks pass, it verifies that the tag exactly matches the package version and
points to a commit on `origin/main`. It rechecks the downloaded build artifacts
and publishes the wheel, source archive and `SHA256SUMS` together in a GitHub
release. Users can install a downloaded wheel or the versioned Git source.

Only the publish job has `contents: write`; test/build jobs have read access.
Checkout credentials are not retained. No long-lived token or Actions secret
needs to be added: publication uses GitHub's short-lived job token. Actions must
be enabled for the repository and its policy must permit the pinned actions.

Do not move published version tags or replace released files. Fix a defective
release by publishing a new version and documenting the correction. If a run
fails before publication, correct the cause and rerun the failed jobs; an
existing public release is not automatically overwritten.

## Optional future PyPI publication

This repository currently publishes packages through GitHub Releases. It does
not claim or publish a PyPI project named `odin-mcp`. To add PyPI later, first
confirm ownership/availability of that project and configure a
[PyPI trusted publisher](https://docs.pypi.org/trusted-publishers/adding-a-publisher/)
for this repository and a dedicated publish workflow/environment. Use OIDC and
an `id-token: write` permission only on that job; do not add a permanent PyPI API
token. The current GitHub-release installation path remains available meanwhile.

## Workflow dependency maintenance

All actions are pinned to full commit SHAs with their release versions in
comments. Gitleaks is a standalone CLI downloaded at a fixed version and checked
against a fixed SHA-256 digest, so its separate organizational action license is
not needed. Review new versions and verify their upstream tag/digest before
updating pins. Avoid executing pull-request code through `pull_request_target`
or granting write permissions to test jobs.

References: [GitHub Python workflows](https://docs.github.com/en/actions/tutorials/build-and-test-code/python),
[secure workflow usage](https://docs.github.com/en/actions/reference/security/secure-use),
[reusable workflows](https://docs.github.com/en/actions/how-tos/reuse-automations/reuse-workflows),
[PyPA packaging guide](https://packaging.python.org/en/latest/tutorials/packaging-projects/),
[Gitleaks](https://github.com/gitleaks/gitleaks).
