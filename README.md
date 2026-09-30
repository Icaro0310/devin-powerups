# devin-powerups (hub)

> **Unofficial community project.** Not affiliated with, endorsed by, or
> sponsored by Cognition AI. "Devin" is a trademark of Cognition AI.

**[Português (BR)](README.pt-BR.md)** · English

Private maintainer hub for the `devin-*` powerups ecosystem: registry,
roadmap, template, and scaffolder. Public projects live in their own repos;
each now carries its own inline CI workflow.

## What's here

| Path | Purpose |
|---|---|
| `registry.json` | Machine-consumable index of all `devin-*` repos |
| `.github/workflows/` | Legacy reusable workflows retained for reference, plus `weekly-repo-report.yml` (below); projects use inline CI |
| `template/` | Skeleton every new repo is bootstrapped from |
| `tools/new-repo.py` | Scaffolder: `python tools/new-repo.py <name> "<desc>"` |
| `tools/weekly_repo_report.py` | Weekly public-project activity report → HTML (stdlib, GitHub public API) |

## The method

Every project adapts an existing tool **plus** a Devin-specific extra that
must pass three tests: does something the base tool *cannot* do · the extra
disappears without Devin · explainable in one sentence.

## The 10 Devin superpowers we build on

`S1` relational session store · `S2` three surfaces (cloud+CLI+Desktop) ·
`S3` hooks (`PermissionRequest`, `PostToolUse`, `PostCompaction`) ·
`S4` `permissions.allow/deny/ask` · `S5` rich skill frontmatter ·
`S6` local subagents · `S7` plugins/marketplace governance · `S8` Cloud API
sessions · `S9` recoverable sessions · `S10` versioned schema.

## Waves

| Wave | Projects | Status |
|---|---|---|
| **0 — Foundation** | `devin-internals-spec` · `devin-redact` | Delivered · 56 tests |
| **1 — Adoption** | `devin-history` · `devin-doctor` · `devin-pm` | Delivered · 150 tests |
| **2 — Differentiator** | `devin-qa-pack` · `devin-metrics` (+ absorbed `devin-learning` → `devin-memory`) · `devin-backup` | Delivered |
| **3 — Amplification** | `devin-search` · `devin-graph` · `devin-evals` · `devin-metrics` (+ absorbed `devin-dashboard`) | Delivered |
| **4 — Research** | `devin-memory` · `devin-bridge` · Djævin | Projects delivered; Djævin research remains open |
| **5 — Lifecycle** | `devin-janitor` | Delivered |
| **6 — Orchestration** | `devin-orchestrator` | Delivered |

### Consolidation (2026-09-30)

Dependent/duplicate projects were unified per the ecosystem rule "repos that
only work together get merged":

- `devin-dashboard` → merged into `devin-metrics` v0.2 (`devin_metrics.dashboard`
  subpackage, `devin-metrics dashboard` subcommand, `devin-dashboard` alias). Repo deleted.
- `devin-learning` → merged into `devin-memory` v0.2 (`devin_memory.learning`
  subpackage, `devin-learning` alias, `devin-redact` dependency). Repo deleted.
- `devin-subagent-orchestrator` (unpublished local draft) → merged into
  `devin-orchestrator` v0.2 (SKILL rewrite + evals + policy tests).

## Install (no PyPI yet)

Every public project is installable directly from GitHub — the declared
`devin-* @ git+https://…` dependencies resolve automatically:

```bash
pip install "git+https://github.com/Icaro0310/devin-metrics.git"
pip install "git+https://github.com/Icaro0310/devin-memory.git"
# …same pattern for every repo in registry.json
```

PyPI/npm publication is pending maintainer credentials; until then git
installs are the supported path.

## CI status

As of 2026-09-30, the latest GitHub Actions runs pass for all 15 project
repositories. Python projects test on Windows and Ubuntu; `devin-bridge` tests
Node 22 and 24 on both. CI is inline because public repositories cannot reliably
call reusable workflows in this private hub. The secrets-scan includes test
source and excludes `.git`, `fixtures/`, and `node_modules/`; synthetic corpora
intentionally live under `fixtures/`.

## Weekly repo report

`weekly-repo-report.yml` runs Sundays 07:00 UTC (04:00 Brasilia) (and via `workflow_dispatch`):
`tools/weekly_repo_report.py` queries the GitHub public commits API for the
previous 7 days across the 15 public project repos in `registry.json`, renders
a standalone HTML report grouped by repo and day, and uploads it as a workflow
artifact every run. Only public-repo metadata is used — private hub commits
are never included.

Emailing the report additionally requires the four MailerSend secrets to be
configured in this private hub (`MAILERSEND_SMTP_HOST`, `MAILERSEND_SMTP_PORT`,
`MAILERSEND_SMTP_USER`, `MAILERSEND_SMTP_PASSWORD` — the same secret names used
by PetSaas). Mail is sent over verified TLS with the documented PetSaas trial
sandbox sender (`PetSaas Bot <petsaas@test-z0vklo638kvl7qrx.mlsender.net>`),
which is distinct from the SMTP login. If any secrets are missing the run
emits a warning and leaves the HTML artifact only.

## Weekly ecosystem scout

`DevinWeeklyEcosystemScout` (Task Scheduler, Sundays 06:30 local) runs
`scripts/weekly-ecosystem-scout.mjs` in the `personal-agent-system` workspace:

1. **Scout** — `gh search repos` over agent-ecosystem queries (mcp-server,
   agent-client-protocol, devin agent, claude code, coding agent cli, agent
   skill), sorted by stars; top results feed new-project ideas.
2. **E2E** — runs each registry repo's own test suite locally, serial, 3 min
   per repo. Read-only: tests never modify or commit code.
3. **Ideation** — dispatches to this repo's dedicated Devin session
   (`devin-repo-task.js --resume-only`), which writes
   `reports/scout-<date>-proposals.md`: exactly 3 feature proposals per repo
   plus up to 5 new-project ideas from the trends.
4. **Deliver** — Slack DM + email with the summary, an `e2e-failure` issue
   on any failing repo, and commit+push of the report. Email is sent by the
   `scout-notify.yml` workflow (`workflow_dispatch`, input `date`) using this
   repo's `MAILERSEND_SMTP_*` secrets, so no email credential lives locally;
   a `MAILERSEND_API_TOKEN` in `gateways/.env` is only a fallback.

Proposals are proposals: nothing is implemented until the maintainer approves.
Approved work resumes the repo's mapped session in `.sessions.json` — never a
duplicate. Fail-open throughout; the run exits non-zero if any E2E fails.

## Conventions

- Bilingual docs: `README.md` (EN, canonical) + `README.pt-BR.md`.
- MIT + unofficial notice on every public README.
- Logic lives in the library; CLI/MCP/skill/plugin are thin wrappers.
- Shared dependencies (`devin-internals-spec`, `devin-redact`) are pinned by tag; avoid dependency cycles.
- No telemetry, no network by default.

## Maintainer

Maintained by **Devin** (the agent), orchestrated by
[@Icaro0310](https://github.com/Icaro0310). Work happens in one dedicated
Devin session per repository (dispatched over ACP).

## License

MIT — see [LICENSE](LICENSE).
