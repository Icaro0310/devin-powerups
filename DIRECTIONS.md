# Directions

Unvalidated ideas — a journal, not a queue.

Items in `BACKLOG.md` are executable work with unblock conditions.
Items here are directions: they may be right, but nobody has felt the
pain yet. The weekly ecosystem scout (`personal-agent-system/reports/
scout-*-proposals.md`) feeds both files — **by class, not by origin**:
`[portar]` proposals (machinery already proven inside the PAS, where the
pain was felt and solved) go to the BACKLOG's port-candidates table;
`[novo]` and unproven `[estender]` proposals stay here. Audit-derived
spec candidates land here too.

## Conversion rule

A direction graduates to `BACKLOG.md` when the pain is felt and
nameable: *"every time I do X, I lose Y minutes / X is annoying /
X breaks"*. If the concrete X and its frequency cannot be named in one
sentence, it is enthusiasm, not pain.

The evidence so far:

- **Tool proposals: 2 of 15 converted** — `devin-switch` and
  `devin-skill-catalog`, both absorbed as modules of existing products
  (devin-control, devin-devkit). Both solved pains already felt:
  multi-environment config chaos and third-party skill trust.
- **Feature proposals: conversion is class-dependent.** `[portar]`
  converts well — most have already shipped: janitor `--judge`
  poordjaevin backend + managed-session tombstones (state#57),
  `devin-memory compact` + `quarantine --digest` + quarantine-aware MCP
  surface + session extraction (brain#52/#53), `switch export/import`
  (control#55), orchestrator `metrics.json` + `plan --cost-estimate`
  (control#53), `history export-gui` + `--session-id`, `bridge intake`
  mailbox, `backup copy-to`, query-side `search --since`, daemon units
  covering the `install` proposals. The `[novo]` class converts only
  when a live obstacle is found by contact — smoke tests, audit
  findings, review — not by proposal. The unshipped `[portar]` items are
  in `BACKLOG.md`, not here.
- **Yield is phase-dependent.** During distribution waves conversion is
  ~0% by design: nothing here is being executed while surface work
  runs. A low absolute rate does not mean the scout is broken — the
  interpretation of the scout was. Its output is direction, not a
  backlog. The structural read: **the PAS is the laboratory, `devin-*`
  is the product** — `[portar]` items are the lab→product pipeline.

## Tool proposals (unconverted)

| Idea | Proposed | What it would be | Felt pain? |
|---|---|---|---|
| devin-scout | 2026-09-30 | Public version of this scout pipeline — trends + E2E + briefing as a repo | No — the pipeline already runs in the PAS; packaging it solves distribution, not pain |
| devin-codegraph | 2026-09-30 | Persistent AST index of repos, complementing devin-graph (session activity, not code) | No — no task yet needed code↔session edges |
| devin-primer | 2026-09-30 | Cross-session context injection — resume the last relevant session per repo as a priming block | Partial — session context exists via memory/history; the felt gap is unproven |
| devin-roles | 2026-10-02 | Opinionated subagent persona bundle (QA, release-manager, doc engineer) | No — subagent profiles already exist in the PAS |
| devin-obsidian | 2026-10-02 | Publish the PAS vault bridge (MOC distillation rules, recall scripts) as an installable MCP+skills package | Partial — the bridge works locally; the missing piece is packaging, which is distribution not new capability |
| devin-arch | 2026-10-02 | Verifiable sequence/data-flow diagrams from real devin-graph edges | No |
| devin-agent-rules | 2026-10-02 | `.devin/rules/` pack where each rule is validated by a devin-evals case | No |
| devin-context | 2026-10-02 | MCP serving SPECs/STATUS/registry as versioned session context | Partial — could help agents navigate, but no concrete loss observed |
| devin-instincts | 2026-10-07 | Public promote/expire loop for learned patterns with provenance, from vendored ECC instincts | Partial — the PAS learning loop already promotes to `learned-*`; the gap is extraction, not function |
| devin-prompt-atlas | 2026-10-07 | Versioned corpus of Devin prompts/playbooks linked to internals-spec | No |
| devin-knowledge | 2026-10-07 | Queryable knowledge graph over docs+registry+SPEC of all devin-* | Partial — overlaps devin-graph; the distinct "which tool covers X" query has not bitten yet |
| devin-crew | 2026-10-07 | Skills-persona bundle packaged via skill-catalog | No — same class as devin-roles |
| devin-playbooks | 2026-10-07 | Playbook generator mining exported sessions into reusable macros | No |

### Converted (for the record)

| Idea | Proposed | Landed | The pain it solved |
|---|---|---|---|
| devin-switch | 2026-09-30 | `devin-control/packages/switch`, PyPI 0.1.0 | Config profiles across Linux / personal / corporate Windows could not be swapped safely — snapshot+verify+rollback |
| devin-skill-catalog | 2026-09-30 | `devin-devkit/packages/skill-catalog`, PyPI | "When do I trust a third-party or learned skill?" — inventory, lint, quarantine, promotion gates |

## Feature proposals (unconverted, latest cycle)

`[novo]` and speculative `[estender]` only — `[portar]` items are in
`BACKLOG.md` (the pain was already proven in the PAS). Proposals below
are from the 2026-10-07 report unless noted; older cycles live in the
PAS reports. "Felt pain?" marks whether the conversion test passes
today.

| Repo | Proposal | Class | Felt pain? |
|---|---|---|---|
| internals-spec | Version `state.vscdb` ItemTable sub-schema | novo | Partial — devin-dream already emits the keys |
| internals-spec | CFL crash corpus minimization → `fixtures/` | estender | No |
| internals-spec | Schema v18 detector + real fixture | estender | Partial — dream injects v18 drift (D06) |
| redact | Cross-chunk secret regression pack (D09) | estender | Partial — defect class is real |
| redact | `devin-redact diff` HTML report | novo | No |
| history | Export GUI path from synthetic `state.vscdb` | estender | Partial — closes HI-1 without real data |
| history | `devin-history diff A B` | novo | No |
| doctor | `doctor updates --apply` | estender | Partial — devkit `update` already covers package upgrades |
| doctor | `devkit-drift` check (installed vs manifest profile) | novo | Partial |
| pm | `devin-pm velocity` sparkline | novo | No |
| qa-pack | devin-dream fixtures pack (D01–D03) as CI precision gate | estender | Partial — precision gate is wanted, corpus exists |
| qa-pack | `verdicts.jsonl` per session | novo | Partial — dashboard needs a stable format |
| qa-pack | Composite action: sticky verdict comment on PR | estender | No |
| metrics | `metrics.json` event output for metrics.watch | estender | Partial — trigger wired, format missing |
| metrics | `metrics report --html` trend charts | novo | No |
| metrics | Subagent rollup (cost/duration per profile) | novo | Partial — `subagent_heads` data exists |
| backup | Incremental snapshots with journal | estender | No |
| search | `--context N` snippet window | novo | Partial — cheap, useful for AI surfaces |
| search | `export --obsidian` markdown notes | novo | Partial — vault alignment is a real theme here |
| graph | GR-1 coverage via dream fleet `--vscdb` | estender | Partial |
| graph | `graph export --mermaid` | novo | No |
| graph | Subagent edges from `subagent_heads` | estender | Partial — gap in the model is real |
| evals | dream-generated eval packs (D01–D09 `expected.json`) | estender | Partial — corpus exists |
| evals | `evals ci --junit` output | novo | Partial — CI annotation is handy |
| evals | Trigger precision/recall eval vs dream fleet | novo | No |
| bridge | npx smoke job in CI | estender | Partial — published package has no end-to-end proof in CI |
| bridge | `bridge resume --mapped` | novo | Partial — `.sessions.json` convention exists |
| dashboard | Janitor/quarantine tiles | estender | Partial |
| dashboard | ci-watch panel | estender | Partial — open since an earlier cycle |
| dashboard | E2E health badge per repo | novo | Partial — scout briefing has the data |
| office | Replay mode | estender | No — open since an earlier cycle, kanban moved on |
| office | `office snapshot` PNG/SVG | novo | No |
| qwenpaw | Complete OpenAI-compat endpoint contract | estender | Partial — open since an earlier cycle |
| qwenpaw | Robot smoke suite for endpoints | novo | No |
| poordjaevin | poordjaevin as real G3 gate in skill-catalog | estender | Partial — PAS `g3-overnight` already drains through `promote/quarantine --g3-report` in dry-run; the public-side gate is open |
| poordjaevin | Per-question temperature in calibration | novo | Partial — documented good-first-issue, likely lowers ECE |
| awesome-devin | Catalog generated from registry.json | estender | Partial — drift is real (the class `surface_diff.py` targets) |
| awesome-devin | "registry coverage" CI gate | novo | Partial |
| awesome-devin | Weekly stars/forks snapshot | novo | No |
| devin-dream | Resolve `devin_internals` dep in E2E | estender | Stale — devin-dream merged into devin-evals (P4); proposals need re-anchoring |
| devin-dream | D10 cross-session reused-secret defect | novo | Stale — same |
| devin-dream | `dream replay <sessions.db>` | novo | Stale — same |
| switch | `devin-devkit apply <profile>` calls switch underneath | estender | Partial — unifies install + profile selection |
| switch | `switch doctor --fix` | novo | Partial — doctor already reports nearest profile |
| skill-catalog | `catalog watch` via trigger manifest | novo | Partial |
| personal-agent-system | Single ops digest email | novo | No |

## Evaluated and archived (2026-10-13)

External tools/skills assessed against the conversion rule. Archived
here so they are not re-proposed.

| Item | Verdict | Reason |
|---|---|---|
| gitql (SQL over git history) | `[novo]` — no felt pain | `git log --grep` covers the actual queries; if ever needed, use the binary, no fork |
| dreamjs (JSON from schema) | discarded | unmaintained 5y + overlaps devin-dream→evals fixtures; unmaintained code is instant debt |
| Graphify (code knowledge graph) | **adopted via catalog** | complementary to devin-graph (code vs sessions); skill, not port — vendored + governed 2026-10-13 |
| addyosmani/agent-skills (25) | **adopted via catalog** | MIT; vendored, quarantined, G1-gated, promoted — validates the catalog on a real external set |
| ponytail (6) | **adopted + installed** | MIT; catalog-active and live in user `~/.devin/skills/` |
| RAG_Techniques | discarded | embeddings/vector store contradicts local-first SQLite positioning; if devin-search ever goes semantic, that is a separate decision |
| HN/forum promotion | deferred | distribution not closed; a technical post earns stars after channels are proven, not before |
| Task Observer / one-skill-to-rule-them-all | `[portar]` — spec below | CC-BY-4.0; structural inspiration, not a fork |

## Spec-needed directions

Filed from the wave-9/audit cycle. Same conversion rule: they stay here
until the consumption point — and the pain — is concrete.

- **`devin-bridge` ACP-server mode** — bridge is client-only today
  (`new`/`resume`/`prompt`/`sessions`/`policy`); a `serve`/`acp-server`
  mode enables policy-gated Zed/JetBrains agents. Needs spec; Rule 1
  boundary. Pain not yet felt — no consumer is blocked today.
- **Umbrella CLI per product** — every package ships its own console
  script; a dispatcher (`devin` or per-product) is a product decision:
  name, collision policy with the Devin CLI, members-as-extras. Not
  enunciable yet — do not build without a consumption-point spec.
- **MCP serving for devin-explore packages** — search/graph/doctor/
  history are read-only Rule-1-safe MCP candidates by nature;
  qa-pack's `adapters/mcp.py` is the mold. Per-package spec needed:
  tool names, what a "query" returns, whether `doctor check` fits MCP
  timeouts.
- **Observation lane, Task-Observer-inspired** (spec sketch from
  `rebelytics/one-skill-to-rule-them-all`, CC-BY-4.0 — attribution:
  Eoghan Henn / rebelytics.com). The PAS `session_learning.py` already
  captures turn-level lessons and auto-promotes recurring themes to
  `learned-*` skills; the catalog already owns the
  proposed→quarantined→approved lifecycle. The missing piece the
  observer model adds: a governed *proposal* stage for changes to
  **existing** skills — corrections/friction observed during use become
  staged improvement proposals reviewed by a human, not direct writes.
  Concretely: learning-loop observations land as catalog `proposed`
  entries with evidence (the memory→catalog bridge in BACKLOG is the
  transport), plus a review pass that can diff a staged skill update
  before approve. Needs spec: observation schema, how an observation
  binds to a skill SHA, which tier auto-promotes vs waits for review.
