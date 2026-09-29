# devin-powerups (hub)

> **Unofficial community project.** Not affiliated with, endorsed by, or
> sponsored by Cognition AI. "Devin" is a trademark of Cognition AI.

**[Português (BR)](README.pt-BR.md)** · English

Maintainer hub for the `devin-*` powerups ecosystem: index, roadmap,
reusable CI and the repo template. **This repo is maintainer infrastructure —
the user-facing projects live in their own public repos.**

## What's here

| Path | Purpose |
|---|---|
| `registry.json` | Machine-consumable index of all `devin-*` repos |
| `.github/workflows/` | Reusable workflows (`python-test`, `redact-check`) called by every project repo |
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
| **0 — Foundation** | `devin-internals-spec` · `devin-redact` | 🔨 M1 done |
| **1 — Adoption** | `devin-history` · `devin-doctor` · `devin-pm` | ⏳ |
| **2 — Differentiator** | `devin-qa-pack` · `devin-learning` · `devin-metrics` · `devin-backup` | ⏳ |
| **3 — Amplification** | `devin-search` · `devin-graph` · `devin-evals` · `devin-dashboard` | ⏳ |
| **4 — Research** | `devin-memory` (anti-poisoning) · `devin-bridge` · Jevin | ⏳ |

## Conventions

- Bilingual docs: `README.md` (EN, canonical) + `README.pt-BR.md`.
- MIT + unofficial notice on every public README.
- Logic lives in the library; CLI/MCP/skill/plugin are thin wrappers.
- No repo depends on another, except the `devin-internals` parsing library.
- No telemetry, no network by default.

## Maintainer

Maintained by **Devin** (the agent), orchestrated by
[@Icaro0310](https://github.com/Icaro0310). Work happens in one dedicated
Devin session per repository (dispatched over ACP).

## License

MIT — see [LICENSE](LICENSE).
