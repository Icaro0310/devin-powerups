# G1 — Gate 1 Decision Record

Status: **5 of 6 items decided on 2a evidence.** Item (c) is the only decision
left for explicit owner ratification — it alone gates the `devin-redact` TS
port. Everything else below is closed with cited evidence and marked
revertible only if the corporate run contradicts it.

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

## (c) Redact mechanism — PENDING OWNER RATIFICATION

**Recommendation:** vendored TypeScript port of `devin-redact` (~200 LOC),
parity-locked by CI in this repo.

Rationale: zero Python anywhere in the runtime path (decision B already
removed it from metadata mode); a vendored port removes the "Python absent"
fail-closed case entirely; the binary surface is small enough that a port is
a bounded task, not a project.

**The parity problem (lockstep without a sensor):** a TS port and the Python
original can silently diverge. Two sensors, both in this repo's CI:

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
closes.

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
- **`@sessions` with a chat provider** — participant registers and
  activates cleanly (60 ms, verified in VSCodium 1.140), but the chat UI
  requires `GitHub.copilot-chat` installed; untestable in clean VSCodium.
  One-minute visual check on the owner's Windows VS Code.
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
