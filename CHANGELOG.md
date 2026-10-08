# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `GOVERNANCE.md` + `BACKLOG.md`: central rules (P5 freeze, merge evidence rule, `@v1` caller pinning, named-file staging) and the parked-work tracker. `tools/fork_visibility.py` measures the upstream awesome-list PR funnel. `.github/workflows/baseline-snapshot.yml` automates weekly P5 collection (Mon 08:15 UTC, commits snapshots, opens an issue on failure).

- `tools/snapshot_baseline.py` + `BASELINE.md`: P5 adoption/reliability baseline — per-repo GitHub stats and traffic (14d), PyPI/npm downloads for published tools, day-1 snapshot at `snapshots/2026-10-08.json`. Collection window 2026-10-08 → 2026-12-03.

- `scorecard.yml` drops top-level `permissions: read-all`: a called workflow's requested scopes must be a subset of what the caller grants, and `read-all` demanded every scope (caused `startup_failure` in callers). The job now declares exactly `contents: read`, `security-events: write`, `id-token: write`; `VARIANTS.md` caller templates grant permissions at job level explicitly.
- Reusable workflows for cross-repo consolidation (P3b): `labeler.yml`, `scorecard.yml` and the new `codeql.yml` (with `language` input) now accept `workflow_call`, and the new `secrets-scan.yml` carries the shared secret-shaped-string scan. Callers pin the `@v1` major tag; `.github/workflows/VARIANTS.md` documents the tagging convention, caller templates, migration gates and the intentionally non-consolidated `ci.yml` variants (`devin-bridge`, `devin-evals`, `devin-memory`, `devin-qa-pack`).
- Registry v17 classifies every entry with `track`, `role`, `nature`, `mode`, `maturity`, `public`, `official_overlap` and `overlap_note`, and marks `devin-powerups` as the control plane (`is_control_plane`). The structural `kind` is unchanged. Rules in `registry.schema.json` reject contradictory combinations and name the broken rule.
- `tools/test_validate_registry.py` and `tools/test_registry_classification.py` check every validator keyword, the vocabulary, the consistency rules, the approved track membership and agreement with the `jsonschema` reference implementation (skipped when it is not installed).
- `tools/new-repo.py` accepts `--track`, `--role`, `--nature`, `--mode` and `--maturity` and registers new entries with the least-claiming classification.
- Registry v8 describes the DevKit install sources, Windows/Linux support, user profiles, and the separate `devin-devkit` distribution. `export_devkit_manifest.py` emits a pinned manifest; private/system entries are rejected.
- `render_catalog.py` produces the profile README catalog and exact counts from `registry.json`.
- `migrate_platform_docs.py` previews and refreshes Windows/Linux guides from the same registry; `--apply` removes the retired Portuguese README files.

### Changed

- `tools/validate_registry.py` enforces the whole schema vocabulary (`$ref`, `allOf`, `if`/`then`/`else`, `const`, `anyOf`, `not`), rejects a schema that uses a keyword it cannot check or malformed keyword operands, and requires exactly one control plane. The old validator silently skipped those keywords. `registry_errors` is now the single validation entry point (schema first, cross-entry rules on valid documents only) used by `new-repo.py` and `export_devkit_manifest.py`.
- `tools/new-repo.py --kind system` now requires `--visibility private`.
- The starter template now uses one shared README with separate Windows and Linux guides; macOS is marked planned/unverified.
- Package metadata in 11 Python projects now references the published `devin-internals-spec` version range instead of a direct Git URL, making the distributions eligible for PyPI upload.

### Fixed

- `devin-powerups` no longer declares an external dependency on Corporate Windows; the schema rule that forbids it was not being enforced.
- `tools/new-repo.py` marks an unsupported environment as `delegation=forbidden`, as the schema requires.
- `test_manifest_uses_pypi_names_and_real_cli_entrypoints` no longer freezes which tools install from GitHub, PyPI or npm.

## [0.1.0] - 2026-09-29

### Added

- Initial public release of the maintainer hub.
- `registry.json`: machine-readable catalog of the public `devin-*`
  projects, with `kind`/`visibility` fields separating public projects
  from maintainer-only records.
- `template/`: bilingual (EN/PT-BR) starter repository with Windows/Linux
  documentation and CI.
- `tools/new-repo.py`: scaffolds a sibling `devin-<name>` checkout from the
  template and runs `git init -b main`; never creates a GitHub remote.
- `tools/weekly_repo_report.py`: weekly activity report over the registry
  via the public GitHub commits API; standalone HTML output, optional email
  delivery behind maintainer-configured SMTP secrets.
- `.github/workflows/`: `weekly-repo-report` (Sundays + dispatch),
  `scout-notify` and `testgen-notify` (maintainer-supplied report delivery),
  `python-test`, `redact-check`, and the reusable `pypi-publish.yml`
  workflow shared by the ecosystem's Python repos.
