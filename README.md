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
| `.github/workflows/` | Legacy reusable workflows retained for reference; projects use inline CI |
| `template/` | Skeleton every new repo is bootstrapped from |
| `tools/new-repo.py` | Scaffolder: `python tools/new-repo.py <name> "<desc>"` |

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
| **2 — Differentiator** | `devin-qa-pack` · `devin-learning` · `devin-metrics` · `devin-backup` | Delivered · 166 tests |
| **3 — Amplification** | `devin-search` · `devin-graph` · `devin-evals` · `devin-dashboard` | Delivered · 176 tests |
| **4 — Research** | `devin-memory` · `devin-bridge` · Jevin | Projects delivered · 126 tests; Jevin research remains open |
| **5 — Lifecycle** | `devin-janitor` | Delivered · 54 tests |

## CI status

As of 2026-09-30, the latest GitHub Actions runs pass for all 16 project
repositories. Python projects test on Windows and Ubuntu; `devin-bridge` tests
Node 22 and 24 on both. CI is inline because public repositories cannot reliably
call reusable workflows in this private hub. The secrets-scan includes test
source and excludes `.git`, `fixtures/`, and `node_modules/`; synthetic corpora
intentionally live under `fixtures/`.

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
