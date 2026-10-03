# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
