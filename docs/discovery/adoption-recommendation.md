# Adoption recommendation — input to Gate G1

Status: recommendation only. The owner decides each item in writing at
G1. Every claim carries its evidence label; nothing here is product code.
`agent-storage-report.md` is now `owner-output-received` (collected
offline via read-only NTFS mount + native Linux run); the remaining
evidence gaps are listed at the end of that report and in the final
section below.

## (a) Per-surface strategy

### `vscode-chat` — **vendor/adapt from SessionsAI**

- Vendor `src/vscodeChatParser.ts` + the discovery section of
  `src/sessionStore.ts` (chatSessions `.json` + `.jsonl`, Code +
  Insiders, `emptyWindowChatSessions`): the only correct, isolated,
  dependency-free TS implementation of the 0–3 mutation replay
  `[LOCAL]`. Cross-check against `copilot-session-viewer`'s dead-code
  `vscode-parser.js` (also correct) and AgentsView's Go implementation
  (only one with splice-index `i` semantics + `resultDetails.output`
  projection — adopt the projection trick for tool-output bloat/privacy).
- Extend discovery with `transferredChatSessions` (found in AgentsView,
  absent from the spec's path list) `[LOCAL]`.
- `state.vscdb`: treat as **optional index** per spec. Only candidate
  reader is session-vault's `SqliteReaderService` (sql.js WASM).
  Recommendation: **defer to post-MVP** — sql.js is a real dependency +
  wasm packaging for an index that duplicates what the files already
  give; revisit if the storage report shows chatSessions dirs absent but
  vscdb present on owner machines.
- Multi-root workspaces → `project: null` + warning (spec-locked).
- Fixtures: **do not vendor** SessionsAI's `test/fixtures/` — they embed
  a real username `[LOCAL]`. Generate synthetic fixtures.

### `codex-cli` — **build fresh in TS — now dual-source**

No TS coverage exists anywhere; all candidates are Go or Python.
**New owner-machine evidence** (storage report): this install has **no**
`~/.codex/sessions/` at all — Codex migrated to sqlite
(`state_5.sqlite`, `threads` table with 41 cols incl. `rollout_path`,
`cli_version`; `rollout_migration_state`/`rollout_migration_skipped_rollouts`
prove the JSONL→sqlite transition) `[LOCAL]`. With 0 threads observed,
neither source yields sessions *on this machine today*; the decision is
about which formats the parser must support for correctness.

- **G1 decision needed — Codex source(s)**: (i) `rollout-*.jsonl` only
  (spec text; covers pre-migration installs), (ii) `state_*.sqlite`
  `threads` only (covers migrated installs; `mode=ro`; metadata columns
  rich — title, model, tokens, git refs), or (iii) both with deterministic
  precedence. Recommendation: **(iii) thin** — sqlite probe first
  (authoritative when present), rollout scan as fallback + legacy
  coverage; ≤250-line budget still holds because the sqlite leg is a
  schema-probed SELECT of metadata columns, never content.
- Schema source: cc-session-core's discriminated-union models (port the
  *type list*, keep its `extra="allow"`/Unknown-record posture → unknown
  records become `unsupported-format`-adjacent warnings, not failures)
  `[LOCAL]` — valid for the rollout leg.
- Operational semantics from AgentsView `[LOCAL]`: `session_meta`/
  `turn_context`/`response_item`/`event_msg` envelopes; `call_id`
  pairing; `token_count`; `task_started`/`task_complete`; fork
  suppression via `forked_from_id`; revert pages `<thread>_<rollout>`;
  `archived_sessions/`; `session_index.jsonl` titles. Only implement
  what the storage report confirms exists — the rest is backlog.
- Cost/`files_touched`: `threads.tokens_used` exists in sqlite `[LOCAL]`;
  rollout-side fields still unconfirmed → spec rule applies per leg.

### `copilot-cli` — **vendor SessionsAI parser + widen event catalog**

- Base: `copilotCliParser.ts` + session-state discovery (dirs +
  `events.jsonl` + `workspace.yaml` + flat `<id>.jsonl`) `[LOCAL]`.
- Widen event knowledge using copilot-session-tools' ~80-type catalog
  and AgentsView's `session.shutdown` `modelMetrics` handling as the
  reference checklist `[LOCAL]` — unknown `type` values → pass-through +
  count, never fail.
- Contract anchor `[EXTERNO]`: the shipped `session-events.schema.json`
  (`@github/copilot` package) and its generated `SessionEvent` TS union
  give an authoritative field list — use it to generate the type layer;
  `session.start.data.version` maps to our `source_version`. The format
  lacks a *stability contract* (upstream issue #3551) → parser must be
  forward-tolerant; this is the spec's `[NÃO VERIFICADO]` clause
  resolved to: "documented by shipped schema, unstabilized".
- Legacy `history-session-state/` — read if present (spec), same
  parser, marked `source_version`-less.

### Chronicle (`session-store.db`) — **secondary source only, optional**

- Official position `[EXTERNO]`: complete record lives in session files;
  the db is a **subset** and is *rebuilt from files* via
  `/chronicle reindex`. Primary source = session files. Full stop.
- If implemented at all: schema-probed, `mode=ro`, metadata-only
  (`assistant_usage_events` + `sessions` correlation columns — the
  AgentsView pattern), never row content; correlation key
  `sessions.id` == session-dir UUID `[LOCAL]`. Deterministic complement
  rule: a dir present but absent in Chronicle is normal (reindex lag);
  Chronicle rows with no dir are reported as `chronicle-orphan` counts,
  never synthesized into sessions.
- Recommendation: **post-MVP**. The MVP loses nothing by listing from
  `session-state/` alone; Chronicle adds usage metadata, not sessions.

### Rejected

- **AgentsView** — as backend (reconfirmed: daemon + API + archive +
  cloud mirrors). Retained as format documentation only.
- **copilot-session-viewer** — wholesale (Express `0.0.0.0`, default-on
  Azure telemetry, writes into session dirs, secondary stores, JS not
  TS). Format reference only.
- **session-vault** — wholesale (webview UI mismatch, `vscode.lm`
  network path, unredacted logs of titles/paths). Salvage: vscdb reader
  (post-MVP) + `RedactorService` as a second reference for the TS
  redactor port.

## (b) Parser order — recommendation

1. **`copilot-cli`** — smallest spec ambiguity (official schema exists),
   isolated discovery root, SessionsAI parser already close; fastest
   path to a green `source` column in the TreeView.
2. **`codex-cli`** — fresh build but simplest format (envelope JSONL,
   date-partitioned); no mutation replay; validates the ID contract on
   a second independent surface early.
3. **`vscode-chat`** — hardest: multi-root discovery, `.json`+`.jsonl`
   duality, mutation replay, workspace correlation. Last, with the two
   prior parsers' state/warning machinery already proven.

## (c) `devin-redact` mechanism — recommendation

**Vendored TS port** of the redaction core (`patterns.py` + false-positive
guard + `redact_text` ≈ 200 LOC) with a **parity test** generated from the
Python reference at build time (ecosystem vendoring rule, D-2026-10-09).
Rationale and fallback (CLI subprocess on temp excerpt) are in
`redact-interface-report.md`. Without either, content search ships
disabled (fail-closed) — acceptable but strictly worse.

## (d) `session-vault` as UI — **no**

TreeView is the spec-locked UI; session-vault is a webview app with a
`vscode.lm` network path and unredacted path/title logging `[LOCAL]`.
Nothing to reuse for the UI. (Its `SqliteReaderService` may return
post-MVP for the optional vscdb index; `RedactorService` is reference
material for (c).)

## (e) Copilot CLI primary source — **session files**

`~/.copilot/session-state/` (+ `$COPILOT_DIR`/`$COPILOT_HOME` if
confirmed by the storage report; both are probed because candidates
disagree `[LOCAL]`). Chronicle = optional complement, never primary —
official docs make files the complete record and the db a derived
subset `[EXTERNO]`; absence-in-Chronicle proves nothing about files,
and rows-without-dirs are reported, not synthesized.

## (f) Corporate restrictions — do they invalidate any candidate?

| Candidate | Corporate risk | Invalidates? |
|---|---|---|
| SessionsAI | none (zero network; needs exec-surface removal anyway) | no |
| session-vault | `vscode.lm` sends transcripts to the model — policy-dependent | yes, as-is; salvaged parts unaffected |
| copilot-session-viewer | telemetry default-on + open HTTP port | yes, entirely |
| AgentsView | server+sync architecture | already vetoed |
| copilot-session-tools / cc-session-core | Python in product path | n/a — reference only |
| `devin-redact` CLI leg (fallback) | Python presence not guaranteed corporate-wide | prefer vendored port |

None of the *recommended* legs requires network, daemons, or writes to
agent storage — the plan is corporate-compatible as proposed.

## What G1 must still supply that 2a cannot

- **Codex source decision** — rollout-JSONL vs `state_*.sqlite` vs both
  (new evidence; see (a)).
- `copilot`/`codex` **CLI versions** — binaries unlocatable offline;
  owner may accept the gap or supply `copilot --version` /
  `codex --version` output. `[NÃO VERIFICADO]`
- Whether env roots (`COPILOT_DIR`/`COPILOT_HOME`, `CODEX_HOME`,
  `CODEX_SESSIONS_DIR`) are set on any owner machine — not observable
  offline; default `~/.copilot`/`~/.codex` confirmed sufficient on the
  observed install `[LOCAL]`.
- `managed-settings/` exists under `AppData/Local/copilot` `[LOCAL]` —
  owner should confirm whether corporate Copilot policy applies (G1-f).
- Whether `sql.js` (WASM) is acceptable as a bundled dependency if vscdb
  indexing is wanted later.
- Written acceptance of each remaining `not-verified` cell the owner
  chooses to waive — or the decision to keep them blocking.
- **Post-MVP backlog surfaced by evidence**: per-session
  `session.db` (`todos`/`inbox_entries`) under Copilot CLI session dirs;
  `chatEditingSessions/` state; `github.copilot-chat` globalStorage
  agent dirs (`ask-agent`, `plan-agent`, `explore-agent`, `copilotCli`);
  `transferredChatSessions`. All `[LOCAL]` — none is required for MVP
  listing.
