# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Registry v8 describes the DevKit install sources, Windows/Linux support, user profiles, and the separate `devin-devkit` distribution. `export_devkit_manifest.py` emits a pinned manifest; private/system entries are rejected.
- `render_catalog.py` produces the profile README catalog and exact counts from `registry.json`.
- `migrate_platform_docs.py` previews and refreshes Windows/Linux guides from the same registry; `--apply` removes the retired Portuguese README files.

### Changed

- The starter template now uses one shared README with separate Windows and Linux guides; macOS is marked planned/unverified.
- Package metadata in 11 Python projects now references the published `devin-internals-spec` version range instead of a direct Git URL, making the distributions eligible for PyPI upload.

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
