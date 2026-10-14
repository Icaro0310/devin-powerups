# G1 — Gate 1 Decision Record

Status: **CLOSED 2026-10-14 — all six items decided.** Items (a),(b),(d),
(e),(f) were decided on 2a evidence; item (c) was owner-ratified with two
conditions (bidirectional fixture parity; 7-day drift window explicitly
accepted, tighten to release webhook on incident). The `devin-redact` TS
port is unblocked. Decisions below are marked revertible only if the
corporate run contradicts them.

Written 2026-10-14. Supersedes "G1 pending" placeholders in
`adoption-recommendation.md` and `agent-storage-report.md`.

## (a) Parser source strategy — DECIDED

**Decision:** vendor SessionsAI parsing patterns for `vscode-chat` and
`copilot-cli`; build `codex-cli` fresh.

**Evidence:** `existing-tools-evaluation.md` — SessionsAI is the only
candidate that parses the real `.copilot/session-state/<uuid>/` layout
(events.jsonl + workspace.yaml + checkpointed session.json) and the VS Code
workspaceStorage chat JSON shapes we observed on the owner machine. No
candidate covers Codex `state_*.sqlite` or the rollout JSONL fallback; both
were implemented in `src/sources/codexCli.ts` (PR #168) and validated against
the owner Windows partition (sqlite readable, `threads=0` → `no-sessions`).

**Reverts if:** nothing pending. The parsers exist and pass 70/70 tests.

## (b) Surface order — DECIDED

**Decision:** `copilot-cli` → `codex-cli` → `vscode-chat` in every listing.

**Evidence:** `adoption-recommendation.md` — copilot-cli is the smallest and
most regular format (good first parser); codex-cli second (two backends,
more edge cases); vscode-chat last (largest session count, most shapes).
The TreeView renders in this fixed order (PR #169).

## (c) Redact mechanism — RATIFIED 2026-10-14 (owner, two conditions)

**Decision:** vendored TypeScript port of `devin-redact` (~200 LOC),
parity-locked by CI in this repo. Honors decision B (pure TS) and removes
Python from the content-search path too.

Rationale: zero Python anywhere in the runtime path (decision B already
removed it from metadata mode); a vendored port removes the "Python absent"
fail-closed case entirely; the binary surface is small enough that a port is
a bounded task, not a project.

**Condition 1 — parity is bidirectional and fixture-based.** Same input →
same output, run on **both** sides against a golden corpus living in the
repo, on every PR touching the port. Drift counts in both directions: if
the TS port adds a pattern the Python lacks, that is drift too (less
dangerous, still drift). "TS matches pinned Python" alone is not
sufficient.

**Condition 2 — the 7-day window is an explicitly accepted risk.** The
weekly drift job vs latest PyPI leaves up to 7 days where Python has a
pattern the port lacks — a false-negative window for a secret scanner.
Accepted for this use case: content search is local-only and exposes
results only to the machine's owner. **Tighten to a release webhook
(same mechanism class as `registry-drift.yml`, push not poll) if a real
incident lands in that window.**

The parity machinery, unchanged from the recommendation:

1. `tools/check_redact_parity.py` — golden corpus through pinned
   `devin-redact==<pin>` and the TS port, fails on any diff. Runs on every
   PR that touches the port.
2. A weekly drift job — same check against the **latest published**
   devin-redact (exactly the `check_spec_pins.py` inside `registry-drift.yml`
   pattern, Sunday 05:41 cron). Without this leg parity rots between
   releases.

**Alternative (not taken, remains revertible):** CLI subprocess with
fail-closed behavior when Python is absent. Costs one external process per
redaction and keeps a Python dependency for the optional feature only.

**Blocks:** the redact port itself and the content-search flag in the
extension. Nothing else — the extension ships metadata-only until this
closes. The port work may now start: this was the only genuine G1
blocker.

## (d) Package location — DECIDED (by constraint)

**Decision:** `devin-powerups/packages/agent-sessions`, extension id
`icaro0310.agent-sessions`, untracked by `registry.json` (it is not an
ecosystem product).

**Evidence:** the repo freeze until 2025-12-03 prevents a new repo; the
`packages/<pkg>/adapters/vscode/` convention already exists in this repo.
Merged via PRs #168 (parsers) and #169 (VS Code surface + .vsix).

## (e) Codex primary source — DECIDED (by evidence)

**Decision:** both backends — `state_*.sqlite` preferred when readable
(newest `state_<N>` selected by filename), rollout JSONL as fallback.

**Evidence:** owner Windows partition has both `~/.codex/state_5.sqlite`
(readable via `node:sqlite`, `threads=0`) and rollout sessions. The
Chronicle question resolved itself: Codex docs confirm it is rebuilt from
the files (`/chronicle reindex`), so files/sqlite are primary and Chronicle
is derived — never a source. `rollout_migration_*` tables exist but were
empty on the owner machine: schema supports migration, does not prove it
ran.

## (f) Content search — DECIDED

**Decision:** absent from the MVP. No search provider, no command, nothing
in the manifest. Titles are `null` structurally (auto-generated titles are
prompt-derived content, not metadata — verified against real
`customTitle`/`threads.title` values).

**Consequence:** when (c) ratifies, content search lands behind a flag as a
later phase, redacting through the vendored port before anything is
displayed.

## Coverage gaps still open (validation, not gates)

- **Corporate run** — bundle at `~/agent-sessions-discovery/`. Validates
  coverage claims (env vars, managed layouts, corporate profiles) that the
  personal-machine evidence cannot. Does not block anything decided here.
- **`@sessions` with a chat provider** — VERIFIED 2026-10-14 on VS Code
  stable 1.140 (Linux x64 tarball) with bundled `github.copilot-chat`
  0.69.0: `@sessions` appears in the `@` completion, accepts selection,
  and streams the real answer (`no sessions match — try a surface name,
  workspace hash or session key`). No GitHub sign-in needed — the
  workbench resolves the built-in free model (`MAI-Code-1.1-Flash`); the
  participant handler itself never touches `request.model`.
- **Native Agent Sessions (VS Code ≥1.140)** — mapped from
  `sessions.desktop.main.js` (20.7 MB, measured directly). It is **not**
  Copilot-only anymore: the built-in "Agents window" is a multi-harness
  client of a local/remote **Agent Host** (AHP over message-port/JSON-RPC)
  covering Local, Copilot CLI, Claude, Codex (`agent-host-claude`,
  `agent-host-codex`, `chat.agentHost.codexAgent.sdkRoot`/`codexHome`),
  Cloud, and remote hosts — plus external-session discovery
  (`showExternalSessions`, `sessionCatalogEnabled`,
  `migrateLegacyCopilotCli`). It even reads
  `~/.copilot/session-state/<id>/events.jsonl` from disk inside the bundle
  (`session-state` ×3, `events.jsonl` ×2, `agentSessions.` storage keys
  ×26 — the `readDateBaseline2`/`model.cache` keys observed in
  `state.vscdb` during G3 are native, confirmed).

  **Where the delta still holds:**
  1. **No host, no data** — native sees nothing without a running Agent
     Host or a `chatSessionsProvider` extension. We read the three storages
     with zero processes/extensions running — dead and historical sessions
     included.
  2. **Codex files** — Codex reaches native via the Agent Host SDK
     (`chat.agentHost.codexAgent.*`), not by parsing `state_*.sqlite` or
     rollouts. `.codex` hits in the bundle are customization files
     (`config.toml`, `hooks.json`, `agents/`), not transcript stores.
  3. **VSCodium** — `sessionsWindowAllowedExtensions: []`, no Copilot
     Chat/ChatGPT on Open VSX, GitHub-auth-first: the native Copilot/Cloud
     surfaces are effectively dead there; ours is not.
  4. **Read-only browse vs management** — native mutates (rename, delete,
     archive, mark-read, orchestration, automations). Ours is read-only,
     metadata-only, canonical-model, titles suppressed — a different
     contract, deliberately.
  5. **Embedded TreeView + `@sessions`** vs a separate Agents window.

  `adoption-recommendation.md`'s claim "native will never cover Codex" is
  **stale** — corrected here: native covers Codex as a live-harness
  provider, not as a disk reader. The delta sentence should be read with
  this mapping.

  **Validity note**: the delta above was measured against VS Code
  **1.140** (`sessions.desktop.main.js` in VSCodium 1.140.06880). It is a
  snapshot, not a permanent property — re-verify on every VS Code minor
  bump. If native ever resolves "dead sessions" or "Codex via files",
  items 1–2 shrink.
