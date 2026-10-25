# Workflow consolidation — reusable callers and documented variants

This repository is the control plane for shared GitHub Actions across the
ecosystem. Repos call the reusable workflows here instead of carrying
byte-identical copies.

## Tagging convention

Callers pin the major tag, never `@main` or a floating release:

```yaml
uses: Icaro0310/devin-powerups/.github/workflows/<name>.yml@v1
```

`v1` is a movable major tag. Non-breaking fixes are retagged to `v1` and
propagate automatically. Breaking changes ship as `v2`; callers migrate at
their own pace. Concrete release tags (`v1.0.0`) mark the underlying commit.

## Reusable workflows

| File | Purpose | Caller `on:` triggers | Inputs |
|---|---|---|---|
| `labeler.yml` | PR path-based auto-labeling | `pull_request_target` (opened/synchronize/reopened) | none |
| `scorecard.yml` | OpenSSF Scorecard | `push` main + `schedule` + `workflow_dispatch` | none |
| `codeql.yml` | CodeQL analysis | `push`/`pull_request` main + `schedule` | `language` (default `python`) |
| `secrets-scan.yml` | Secret-shaped string scan + publish-workflow meta-check + personal-machine-paths diff gate (`scripts/check-internal-paths.py` — scans only the lines `diff <base>...HEAD` adds for the owner's home dir, macOS/Windows profile paths in text files; fork PRs run the pinned `v1` copy, heads without a usable base diff the default branch, whole-tree `--all` is the last resort) | called from repo `ci.yml` | none |
| `adapters-check.yml` | Distributed-adapter hygiene scan (personal paths, internal names, token shapes, SKILL.md command coherence) + `safe-executable.cjs` byte-lockstep against `adapters/shared/` | called from repo `ci.yml` | none |
| `config-restricted-check.yml` | VS Code extension `untrustedWorkspaces` coverage (declaration required; `limited` is restricted-by-default) | called from repo `ci.yml` | none |
| `python-test.yml` | pytest on windows+ubuntu | called from repo `ci.yml` | `python-version`, `package-dir` |
| `adapter-test.yml` | One adapter face's own suite in isolation, on windows+ubuntu | called from per-package adapter workflows | `package-dir`, `adapter-dir`, `test-command`, `python-version`, `node-version`, `pre-install`, `skip-install` |
| `pypi-publish.yml` | Verify wheel `__version__`, then publish the verified `dist` to PyPI | `workflow_call` only — the caller wires `release`/`workflow_dispatch` | `package-dir`, `python-version`, `module` |
| `verify-wheel-version.yml` | Build + `__version__` gate; uploads the verified `dist` artifact | called from publish workflows | `package-dir`, `module`, `python-version` |
| `release.yml` | Release fan-out: wheel gate → PyPI OIDC → GHCR+cosign → `.vsix` artifact → marketplace notes | `workflow_call` from per-repo release workflows | `package-dir`, `module`, `pypi-environment`, `python-version`, `vscode-ext-dir`, `docker-image` → output `version` |

**Rollout note — `tools/dev-deps-pin-check.py` (dev-dep pin sensor):**
wired only into this repo's `ci.yml` for now (scans the hub checkout +
`template/`). Per-repo rollout is a follow-up — callers currently fail it
(`ruff>=x` in `[dependency-groups]`, `astral-sh/ruff-action` without a
`version:` input, `pip install build twine` on publish paths). When that
rollout happens the check belongs either (a) as a step in
`python-test.yml` — it is already in every Python repo's CI via `@v1`, so
one retag propagates it to all callers with zero pin-bump PRs — or (b) as
its own reusable on the `adapters-check.yml`/`config-restricted-check.yml`
pattern (script fetched from `v1` when the caller does not ship it).
Option (a) is the cheaper path; (b) is the right one only if the check
needs to run without a pytest job.

### Caller templates

```yaml
# labeler.yml — caller must NOT check out PR code before this job.
name: pr-labeler
on:
  pull_request_target:
    types: [opened, synchronize, reopened]
permissions:
  contents: read
  pull-requests: write
jobs:
  label:
    permissions:
      contents: read
      pull-requests: write
    uses: Icaro0310/devin-powerups/.github/workflows/labeler.yml@v1
```

```yaml
# scorecard.yml — the calling job must grant every scope the reusable
# requests; missing grants fail at startup (startup_failure).
name: OpenSSF Scorecard
on:
  push:
    branches: [main]
  schedule:
    - cron: "30 1 * * 6"
  workflow_dispatch:
permissions: read-all
jobs:
  analysis:
    permissions:
      contents: read
      security-events: write
      id-token: write
    uses: Icaro0310/devin-powerups/.github/workflows/scorecard.yml@v1
```

```yaml
# codeql.yml — pass `language` only when it differs (e.g. devin-control).
name: CodeQL
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  schedule:
    - cron: "20 3 * * 5"
permissions:
  actions: read
  contents: read
  security-events: write
jobs:
  analyze:
    permissions:
      actions: read
      contents: read
      security-events: write
    uses: Icaro0310/devin-powerups/.github/workflows/codeql.yml@v1
```

```yaml
# adapter-test.yml — one job per adapter face, scoped to the face's
# paths AND the package source: a CLI change can break the parity
# contract without touching the adapter, so core paths must also
# trigger the face suite. Python faces keep the defaults; Node faces
# set node-version and skip-install. test-command / pre-install are
# allowlist-guarded: plain command + args matching
# ^[a-zA-Z0-9 ./_-]+$, no shell metacharacters — the reusable fails
# closed on anything else. See docs/adapter-checklist.md.
name: test-doctor-vscode
on:
  push:
    branches: [main]
    paths:
      - 'packages/doctor/adapters/vscode/**'
      - 'packages/doctor/src/**'
      - 'packages/doctor/pyproject.toml'
      - '.github/workflows/test-doctor-vscode.yml'
  pull_request:
    paths:
      - 'packages/doctor/adapters/vscode/**'
      - 'packages/doctor/src/**'
      - 'packages/doctor/pyproject.toml'
      - '.github/workflows/test-doctor-vscode.yml'
permissions:
  contents: read
jobs:
  adapter-test:
    permissions:
      contents: read
    uses: Icaro0310/devin-powerups/.github/workflows/adapter-test.yml@v1
    with:
      package-dir: packages/doctor
      adapter-dir: packages/doctor/adapters/vscode
      test-command: node --test
      node-version: "22"
      skip-install: true
```

```yaml
# release.yml — one job fans the release out to every channel. The
# caller's uses: job must grant the UNION of the scopes the called jobs
# request (contents:read + id-token:write for PyPI OIDC/cosign +
# packages:write for GHCR) or the run dies at startup_failure.
# PyPI caveat: trusted publishing validates job_workflow_ref — a
# cross-repo caller's ref points at devin-powerups/release.yml, which a
# per-repo Trusted Publisher can never match (pypi/warehouse#11096).
# The PyPI job detects that case and skips the upload with a warning;
# the repo's own inline pypi-publish.yml stays the PyPI path. The leg
# publishes for same-repo callers and vendored copies of release.yml.
# docker-image / vscode-ext-dir are opt-outs: empty skips that leg.
name: release
on:
  push:
    # `<pkg>-vX.Y.Z` repos keep `*-v*`; repos on the bare `vX.Y.Z`
    # convention (e.g. devin-judge) need `tags: ["v*"]` instead — the
    # reusable lint and the shared detect gate accept both, but the
    # caller trigger decides whether the workflow runs at all.
    tags: ["*-v*"]
permissions:
  contents: read
jobs:
  fanout:
    permissions:
      contents: read
      id-token: write
      packages: write
    uses: Icaro0310/devin-powerups/.github/workflows/release.yml@v1
    with:
      package-dir: packages/doctor
      pypi-environment: pypi
      # optional legs:
      # docker-image: devin-doctor
      # vscode-ext-dir: packages/doctor/adapters/vscode
      # fail the release when the Marketplace leg does not publish
      # (replaces the retired AZURE_MARKETPLACE_REQUIRED repo var):
      # azure-marketplace-required: true
```

```yaml
# ci.yml — two reusable jobs replace the inline copy.
name: ci
on:
  push:
    branches: [main]
  pull_request:
permissions:
  contents: read
jobs:
  test:
    permissions:
      contents: read
    uses: Icaro0310/devin-powerups/.github/workflows/python-test.yml@v1
  secrets-scan:
    permissions:
      contents: read
    uses: Icaro0310/devin-powerups/.github/workflows/secrets-scan.yml@v1
  # adapters-check — same wiring in every repo that ships distributed
  # adapters/skills (adapters/, packages/*/adapters/, .devin/skills/).
  # The sensor fetches scripts/check-adapters-hygiene.py from this repo
  # at the same v1 tag when the caller does not ship its own copy;
  # known-legitimate hits pin per file in a repo-root
  # `.adapters-hygiene-allow` (`path sha256=<hex>`), same mechanism as
  # .secrets-scan-allow. The same job also runs
  # check-safe-executable-lockstep.py: every vendored safe-executable.cjs
  # must hash-identically match adapters/shared/ (local canonical in
  # this repo, the v1 sensor checkout in callers).
  adapters-check:
    permissions:
      contents: read
    uses: Icaro0310/devin-powerups/.github/workflows/adapters-check.yml@v1
  # config-restricted-check — same wiring in every repo that ships VS
  # Code extensions. The sensor fetches scripts/check_config_restricted.py
  # from this repo at the same v1 tag when the caller does not ship its
  # own copy; there is no allowlist — a finding is fixed by declaring or
  # restricting the key, never suppressed.
  config-restricted-check:
    permissions:
      contents: read
    uses: Icaro0310/devin-powerups/.github/workflows/config-restricted-check.yml@v1
```

Rule of thumb: the `permissions` on a `uses:` job must cover every scope the
called workflow requests — GitHub rejects the run at startup otherwise
(`startup_failure` with zero jobs). That is why callers declare explicit
job-level permissions even when the workflow-level block already matches.

## Documented variants (intentionally NOT consolidated)

| Repo | Workflow | Why it stays inline |
|---|---|---|
| `devin-control` | `ci.yml` | Node.js toolchain, not Python — `python-test.yml` does not apply |
| `devin-assure` | `ci.yml` | Extra `corpus` job (EV-3 golden-case gate) |
| `devin-brain` | `ci.yml` | Installs sibling deps from git pins before `pip install -e .` |
| `devin-assure` | `ci.yml` | Python matrix 3.10/3.11/3.12 + different action pins |

These are the exceptions the audit expects to find. A repo drifting from
the caller template without an entry here is a bug; a repo listed here
converging to the template is welcome and should remove its row.

## Migration gates

Per repo: the migrated workflow must run green on the next real event
(push/PR for labeler/codeql, `workflow_dispatch` fallback for scorecard).

Global parity checks after each migration wave:

- **labeler**: all callers byte-identical; each caller repo has
  `.github/labeler.yml` config; no `actions/checkout` in the caller file.
- **scorecard**: all callers byte-identical; `workflow_dispatch` present so
  validation never waits on the weekly schedule.
- **codeql**: callers byte-identical except a documented `language` input.
- **ci.yml**: callers byte-identical; jobs are only the `uses:` entries
  matching the caller template above (currently three).

Byte-identical callers are required for the no-input workflows because any
difference is either a missing input (fix the reusable) or a variant
(document it here).
