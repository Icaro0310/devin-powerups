# devin-powerups

> **Unofficial community project.** Not affiliated with, endorsed by, or
> sponsored by Cognition AI. "Devin" is a trademark of Cognition AI.

**[Português (BR)](README.pt-BR.md)** · English

The hub for a collection of **Devin Desktop–native powerups**: tools that
adapt proven ideas from other coding agents and add a capability that only
exists because Devin exposes primitives nobody else has (relational session
store, permission hooks, skill frontmatter, subagents, Desktop GUI stores,
Cloud API).

This repo is the **index, roadmap and registry** — not a code monorepo.
Each powerup lives in its own repository, created just-in-time.

## The method

Every project adapts an existing tool **plus** a Devin-specific extra. The
extra must pass three tests:

1. **Side-by-side** — does it do something the base tool *cannot* do at all?
2. **No-Devin** — does the extra disappear if Devin is removed?
3. **One sentence** — can you explain it without jargon?

## The 10 Devin superpowers we build on

`S1` relational session store (tool status, `locations`, real tokens, ACU) ·
`S2` three surfaces (cloud + CLI + Desktop) · `S3` hooks (`PermissionRequest`,
`PreToolUse`, `PostToolUse`, `PostCompaction`) · `S4` `permissions.allow/deny/ask`
· `S5` rich skill frontmatter (`model`, `allowed-tools`, `triggers`,
`subagent`) · `S6` local subagents · `S7` plugins + marketplace governance ·
`S8` Cloud API sessions · `S9` recoverable sessions (locks + logs survive
pruning) · `S10` versioned schema (`refinery_schema_history`).

## Waves

| Wave | Projects | Status |
|---|---|---|
| **0 — Foundation** | `devin-internals-spec` · `devin-redact` | 🔨 in progress |
| **1 — Adoption** | `devin-history` · `devin-doctor` · `devin-pm` | ⏳ |
| **2 — Differentiator** | `devin-qa-pack` · `devin-learning` · `devin-metrics` · `devin-backup` | ⏳ |
| **3 — Amplification** | `devin-search` · `devin-graph` · `devin-evals` · `devin-dashboard` | ⏳ |
| **4 — Research** | `devin-memory` (anti-poisoning) · `devin-bridge` · Jevin | ⏳ |

## Repository registry

Machine-consumable index: [`registry.json`](registry.json).

| Repo | Purpose | Wave |
|---|---|---|
| [`devin-repo-template`](https://github.com/Icaro0310/devin-repo-template) | Template every repo is born from | infra |
| [`devin-ci`](https://github.com/Icaro0310/devin-ci) | Reusable GitHub Actions workflows | infra |
| `devin-powerups` | This hub — index + roadmap + registry | infra |

## Conventions

- **Bilingual docs**: `README.md` (EN, canonical) + `README.pt-BR.md`.
- **MIT** license, with the unofficial-notice disclaimer on every README.
- **Architecture rule**: logic lives in the library; CLI/MCP/skill/plugin
  are thin wrappers.
- **No repo depends on another**, except `devin-internals` (the parsing
  library, the single source of truth for the schema).
- **No telemetry, no network by default**, in any project.

## Maintainer

Maintained by **Devin** (the agent), orchestrated by
[@Icaro0310](https://github.com/Icaro0310). Reports of what was
done/changed/committed are produced per milestone.

## License

MIT — see [LICENSE](LICENSE).
