# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `scripts/check-internal-paths.py`: personal-machine-paths diff sensor — fails a staged or PR diff when a changed text file (`.json .yaml .yml .txt .md .env .cfg .ini .toml .csv .log`) carries the owner's home dir (`/home/<owner>`, deliberately not `/home/*` — CI runners legitimately show `/home/runner` and docs `/home/user`), a macOS user-home path, or a Windows profile path. Modes: staged index blob (default, pre-commit gate), `--pr-base <ref>` (CI `diff <ref>...HEAD`), `--all` (no-merge-base fallback). Wired as a step in `secrets-scan.yml` — fetched from `v1` into `.powerups-sensor` when the caller does not ship it — so the next `v1` retag propagates the gate to every `ci.yml` caller with zero caller-side changes. Covers the `git add -A` machine-state-snapshot incident class secrets-scan cannot see: a path is not a token shape.

- `tools/check_required_checks.py` (#64): orphaned required-check detector — for every public registry repo (plus `--repo`/`--extra-repo` extras like `Icaro0310`/`Icaro0310.github.io`), diffs the required status-check contexts from branch protection + active rulesets against the contexts actually produced (check-runs/commit statuses on the default head and the last `--prs` PR heads, plus job names declared by the local `.github/workflows/*.yml`, resolving `uses:` reusable calls into their real `caller / callee` names; `workflow_call`-only files contribute no bare names, which is what keeps the renamed-job ghost visible). A required context with no producer leaves PRs green-but-`BLOCKED` forever — the incident class that hit 15 repos in Oct 2026. Also verifies `actions/permissions/workflow.can_approve_pull_request_reviews`. Every leg reads public data, so plain `GITHUB_TOKEN` suffices; `--json` supported; exit 1 on findings, 2 when nothing audited. Wired into `registry-drift.yml`; `tools/test_check_required_checks.py` covers parsing, matching, API shapes and exit codes. `ci.yml` gains a `tools-tests` job running the whole `tools/` pytest suite (pinned `pytest~=9.0`) — previously only `test_weekly_repo_report.py` ran in CI.

- `pr-approve.yml` v1.5 gate fallback extensions (D-2026-10-20b): qualified replies may clear a blocking thread by citing a landed same-owner upstream fix — `owner/repo@<sha>` or `github.com/owner/repo/commit/<sha>` verify the sha is an ancestor of the upstream repo's default branch, `github.com/owner/repo/pull/<n>` verifies `merged_at` non-null — closing the canary failure where a finding on a caller's `auto-approve.yml` can only be fixed in devin-powerups (assure#89). Anchors naming the PR's own repo keep the v1.4 ancestor+postdate proof (own-repo pulls require the merge commit in the head AND postdating the finding). The `gate-resolved-via: fallback` audit comment is now idempotent: a `gate-fallback-pairs:` line records the resolved thread|anchor set + head sha; an identical `github-actions[bot]`-posted set suppresses duplicates while a new thread or new head posts fresh, and a per-PR/head `concurrency` group serializes same-key re-triggers. Test suite grows to 34 covering the anchors, org-scope rail, landedness checks and the dedupe.

- `pr-approve.yml` v1.4 gate fallback (D-2026-10-20): a blocking Devin Review thread stops counting when a reply by the PR author or a repo collaborator cites a commit verified as an ancestor of the reviewed head (`compare` `ahead`/`identical`) AND strictly postdating the finding's commit AND the head carries a `Devin Review` status `success`. Threads stay unresolved (veto stays visible); `fallback-resolved:` log lines, `fallback_resolutions`/`fallback_threads` step outputs, and a `gate-resolved-via: fallback` PR comment on approval make every use auditable. `pull_request_review_comment[created]` re-triggers the gate so late fix replies re-evaluate (caller `auto-approve.yml` files need the same trigger at pin-bump time). Closes the repeat failure class where the bot never self-resolves verified findings (devin-explore#104, devin-state#74 — admin merges). `tools/test_pr_approve_gate_fallback.py` executes the workflow's real `run:` blocks against a stubbed `gh`.

- `tools/dev-deps-pin-check.py`: dev-dep drift sensor — fails when a lint/test/build tool (ruff, pytest, mypy, bandit, black, coverage, hatch/hatchling, setuptools, wheel, build, twine; overridable via `--tools`) carries a floating specifier (`bare >=`/`*`/`latest`/`@main`) in `pyproject.toml` (optional-deps, dependency-groups, tool.uv, build-system.requires, hatch envs), `requirements*.txt`, or workflow install lines (`pip`/`pipx`/`uvx`/`uv tool`), including `astral-sh/ruff-action` steps without a `version:` input. Wired into `ci.yml` against the repo + `template/`; `tools/test_dev_deps_pin_check.py` + `--selftest` fixtures cover every site.

- `GOVERNANCE.md` + `BACKLOG.md`: central rules (measurement-window scope, merge evidence rule, `@v1` caller pinning, named-file staging) and the parked-work tracker. `tools/fork_visibility.py` measures the upstream awesome-list PR funnel. `.github/workflows/baseline-snapshot.yml` automates weekly P5 collection (Mon 08:15 UTC, commits snapshots, opens an issue on failure).

- `tools/snapshot_baseline.py` + `BASELINE.md`: P5 adoption/reliability baseline — per-repo GitHub stats and traffic (14d), PyPI/npm downloads for published tools, day-1 snapshot at `snapshots/2026-10-08.json`. Collection window 2026-10-08 → 2026-12-03.

- `scorecard.yml` drops top-level `permissions: read-all`: a called workflow's requested scopes must be a subset of what the caller grants, and `read-all` demanded every scope (caused `startup_failure` in callers). The job now declares exactly `contents: read`, `security-events: write`, `id-token: write`; `VARIANTS.md` caller templates grant permissions at job level explicitly.
- Reusable workflows for cross-repo consolidation (P3b): `labeler.yml`, `scorecard.yml` and the new `codeql.yml` (with `language` input) now accept `workflow_call`, and the new `secrets-scan.yml` carries the shared secret-shaped-string scan. Callers pin the `@v1` major tag; `.github/workflows/VARIANTS.md` documents the tagging convention, caller templates, migration gates and the intentionally non-consolidated `ci.yml` variants (`devin-bridge`, `devin-evals`, `devin-memory`, `devin-qa-pack`).
- Registry v17 classifies every entry with `track`, `role`, `nature`, `mode`, `maturity`, `public`, `official_overlap` and `overlap_note`, and marks `devin-powerups` as the control plane (`is_control_plane`). The structural `kind` is unchanged. Rules in `registry.schema.json` reject contradictory combinations and name the broken rule.
- `tools/test_validate_registry.py` and `tools/test_registry_classification.py` check every validator keyword, the vocabulary, the consistency rules, the approved track membership and agreement with the `jsonschema` reference implementation (skipped when it is not installed).
- `tools/new-repo.py` accepts `--track`, `--role`, `--nature`, `--mode` and `--maturity` and registers new entries with the least-claiming classification.
- `tools/render_surfaces.py`: renders the semantic layer as derivable surfaces — intent map (track -> tools), browse-by-audience, browse-by-interface, per-repo ecosystem blocks, and headline counts. Editorial copy stays manual.
- `DECISIONS.md` + `GOVERNANCE.md` lifecycle section: creation/consolidation/archival/reclassification criteria and the six-field decision-record format; the merge rule is now a criterion (technical + product signals), not a prohibition.

### Changed

- P5 reframed from a work freeze to a measurement window: product/discoverability work (READMEs, site, topics, `awesome-devin` rewrites, backlog graders, package publication) is allowed — it is what the baseline measures. Only structural changes that would invalidate the series remain gated: physical merges, new/deleted repos, registry taxonomy changes, renames. (`GOVERNANCE.md`, `BASELINE.md`, `BACKLOG.md`)
- Registry v8 describes the DevKit install sources, Windows/Linux support, user profiles, and the separate `devin-devkit` distribution. `export_devkit_manifest.py` emits a pinned manifest; private/system entries are rejected.
- `render_catalog.py` produces the profile README catalog and exact counts from `registry.json`.
- `migrate_platform_docs.py` previews and refreshes Windows/Linux guides from the same registry; `--apply` removes the retired Portuguese README files.
- `tools/validate_registry.py` enforces the whole schema vocabulary (`$ref`, `allOf`, `if`/`then`/`else`, `const`, `anyOf`, `not`), rejects a schema that uses a keyword it cannot check or malformed keyword operands, and requires exactly one control plane. The old validator silently skipped those keywords. `registry_errors` is now the single validation entry point (schema first, cross-entry rules on valid documents only) used by `new-repo.py` and `export_devkit_manifest.py`.
- `tools/new-repo.py --kind system` now requires `--visibility private`.
- The starter template now uses one shared README with separate Windows and Linux guides; macOS is marked planned/unverified.
- Package metadata in 11 Python projects now references the published `devin-internals-spec` version range instead of a direct Git URL, making the distributions eligible for PyPI upload.
- `template/pyproject.toml` dev deps are pinned (`pytest~=9.0`, `ruff~=0.17.0`, `setuptools>=77,<82`) — a bare `>=` floats to every new release, which is how ruff 0.17 broke generated repos' main.
- `verify-wheel-version.yml` installs `build==1.2.2`/`twine==6.1.0` instead of floating latest on the publish path.

### Fixed

- `devin-powerups` no longer declares an external dependency on Corporate Windows; the schema rule that forbids it was not being enforced.
- `tools/new-repo.py` marks an unsupported environment as `delegation=forbidden`, as the schema requires.
- `test_manifest_uses_pypi_names_and_real_cli_entrypoints` no longer freezes which tools install from GitHub, PyPI or npm.
- `scripts/check-adapters-hygiene.py`: five sensor gaps closed — README names now match whole `devin-*` tokens (a `devin-checker` mention no longer validates `devin-check`); fenced/inline `devin-*` words only count as invocations in command position, so install lines, comments and quoted launcher specs stop failing valid skills; tilde (`~~~`) fences are recognized; `C:\Users` matches one or two backslashes; binary adapter files are scanned for token-shaped values instead of skipped whole. `VARIANTS.md` now documents the `adapters-check.yml` reusable and its `ci.yml` caller wiring.
- `agent-sessions` VS Code adapter: `Open Details` accepts both the row-click display key and the context-menu `SessionNode`; refresh now fires `onDidChange` for every open details document (ephemeral keys are positional, so a recollect can rebind a URI); details URIs no longer double-decode the key basename; `@sessions` filtered answers sort newest-first like the tree; overview warning counts show occurrences with `×n` per kind; Surfaces table fixed to two columns.
- `agent-sessions` parsers: non-object JSONL records are skipped as bad lines instead of aborting the Copilot surface; mutation paths containing `__proto__`/`constructor`/`prototype` are rejected (prototype-pollution guard); `session.start` `version` must be version-shaped before reaching `source_version`; a `task_started` after `task_complete` re-opens the Codex session (`ended_at` null + `session-open`); sessions without stable workspace identity now get `id: null` + `unknown-workspace` instead of a canonical-looking `native:` id, and dedup only collapses records sharing source + workspace hash + native id (cross-workspace collisions are kept and flagged `cross-workspace-duplicate`).
- `baseline-snapshot.yml`: dated snapshots now commit to the append-only `snapshots` data branch instead of pushing to `main` directly — main became PR-only under branch protection, so the weekly run failed with `GH006` for two consecutive weeks (#134, #206). Collection itself was healthy; only the push target was wrong.

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
