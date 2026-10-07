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
| `secrets-scan.yml` | Secret-shaped string scan | called from repo `ci.yml` | none |
| `python-test.yml` | pytest on windows+ubuntu | called from repo `ci.yml` | `python-version`, `package-dir` |
| `pypi-publish.yml` | Build + publish to PyPI | `release`/`workflow_dispatch` | `package-dir`, `python-version` |

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
# codeql.yml — pass `language` only when it differs (e.g. devin-bridge).
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
```

Rule of thumb: the `permissions` on a `uses:` job must cover every scope the
called workflow requests — GitHub rejects the run at startup otherwise
(`startup_failure` with zero jobs). That is why callers declare explicit
job-level permissions even when the workflow-level block already matches.

## Documented variants (intentionally NOT consolidated)

| Repo | Workflow | Why it stays inline |
|---|---|---|
| `devin-bridge` | `ci.yml` | Node.js toolchain, not Python — `python-test.yml` does not apply |
| `devin-evals` | `ci.yml` | Extra `corpus` job (EV-3 golden-case gate) + secrets-scan fixture exclusions |
| `devin-memory` | `ci.yml` | Installs sibling deps from git pins before `pip install -e .` |
| `devin-qa-pack` | `ci.yml` | Python matrix 3.10/3.11/3.12 + different action pins |

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
- **ci.yml**: callers byte-identical; jobs are only the two `uses:` entries.

Byte-identical callers are required for the no-input workflows because any
difference is either a missing input (fix the reusable) or a variant
(document it here).
