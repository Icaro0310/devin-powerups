# Existing tools evaluation

Status: evaluated 2026-10-13 against cloned source (`[LOCAL]` = code
inspected in a local clone; `[EXTERNO]` = upstream documentation;
`[NÃO VERIFICADO]` = claim not confirmable). This document evaluates
parsing and discovery only — architecture is assessed separately where it
matters for adoption.

Candidates and versions assessed:

| Candidate | Version | License (verified) | Runtime | Assessment basis |
|---|---|---|---|---|
| SessionsAI (`claude-sessions-vscode`) | 0.4.1 (package.json) | MIT (LICENSE file; copyright holder unnamed — `(c) 2026`) | TypeScript, VS Code ext | clone `[LOCAL]` |
| AgentsView | clone of `fd3eeb0` | MIT (Kenn Software LLC) | Go 1.27 | clone `[LOCAL]` |
| copilot-session-tools | 0.19.0 (`f1828da`) | MIT | Python ≥3.12 | clone `[LOCAL]` |
| cc-session-core | 0.2.0 (PyPI wheel) | MIT | Python ≥3.12 + pydantic | wheel `[LOCAL]` |
| session-vault | 1.0.6 (package.json) | MIT | TypeScript, VS Code ext | clone `[LOCAL]` |
| copilot-session-viewer | 0.4.1 (`@qiaolei81`) | MIT | Node ≥22, JavaScript | clone `[LOCAL]` |

Git tags/PR claims could not be verified inside depth-1 clones without
git objects; the SessionsAI "PR #18" claim is `[NÃO VERIFICADO]` —
irrelevant to the assessment.

---

## 1. SessionsAI — the architecturally correct base

**What it is.** A VS Code extension (webview sidebar + panels) that lists
agent sessions from Claude Code, Copilot CLI and VS Code Chat. TypeScript
throughout; parsers are pure modules with **no `vscode` import**
(`src/vscodeChatParser.ts`, `src/copilotCliParser.ts`, `src/sessionParser.ts`)
— they vendor cleanly.

**Surface coverage `[LOCAL]`.**

| Surface | Discovery | Parser quality |
|---|---|---|
| `vscode-chat` | `workspaceStorage/*/chatSessions/*.json` **and** `*.jsonl`, Code + Code-Insiders, `globalStorage/emptyWindowChatSessions`; project via `workspace.json` | Best of all candidates: full mutation-log replay — kind 0 snapshot, 1 set, 2 splice-with-index, **3 delete** — matching the real format |
| `copilot-cli` | `~/.copilot/session-state/<id>/events.jsonl` + `workspace.yaml`, plus flat `*.jsonl` | Covers `session.start`, `user.message`, `assistant.message`, `tool.*`; own YAML scalar reader |
| `codex-cli` | **absent** | — |
| `state.vscdb`, Chronicle | **absent** | — |

**Other properties `[LOCAL]`:** stable key `source:id`; `.jsonl` wins over
`.json`; in-memory cache keyed by path+mtime+size; zero network in `src/`
(a dev-only `scripts/sync-prices.mjs` fetches LiteLLM prices — not
bundled); read-only to sources (only writes under `os.tmpdir()` handoff
dir). Session listing always builds `searchText` including content — no
metadata-only mode, but the parse path is separable.

**Costs of adoption.** ~200 lines of agent-execution surface to remove
(`resume()` spawns `claude|copilot --resume` in a terminal,
`continueInNewSession`, `openInClaudeCode`, `vscode-chat-session:` URI
handler). **Test fixtures embed a real username** (`bisch`) in
`test/fixtures/…` — do not vendor the fixtures; generate our own.

**Verdict: vendor/adapt (b).** The two parsers we need are already
isolated TS in the right format. MIT-compatible.

## 2. AgentsView — rejected as backend, unmatched as format reference

Already rejected as a backend (daemon + HTTP/SSE API + persistent archive
+ Postgres/DuckDB/ClickHouse mirrors + S3 ingest). That verdict stands
`[LOCAL]`: `internal/server`, `internal/{postgres,duckdb,clickhouse}`,
`s3source.go` minio client, `exec /sbin/mount`. Zero-network is impossible
by design.

**Why it still matters — format knowledge `[LOCAL]`:**

- `vscode-chat`: the only other candidate with the **complete** mutation
  replay (kinds 0–3 including splice index `i`); additionally covers
  `globalStorage/transferredChatSessions`; dedups `.jsonl` > `.json`; and
  **projects `resultDetails.output` to `[]` during replay** — a
  privacy/size optimization worth copying (tool outputs can be huge).
- `codex-cli`: richest operational semantics found anywhere —
  `archived_sessions` (flat), revert pages `rollout-<ts>-<thread>_<rollout>.jsonl`
  → continuation key `<thread>_<rollout>`, fork suppression via
  `forked_from_id`/`parent_thread_id` + parent `turn_id`s,
  `session_index.jsonl` titles, `apply_patch` file extraction,
  cache-aware token normalization.
- `copilot-cli`: `session-state/<uuid>/events.jsonl` **and** flat
  `<uuid>.jsonl` (dir wins); `workspace.yaml` name line; `session.shutdown`
  `modelMetrics`/`totalNanoAiu` cost.
- Chronicle: reads **only** `assistant_usage_events` (9-column schema
  validated via `pragma_table_info`), correlated `session_id` == dir UUID,
  SQLite always `file:…?mode=ro`. The disciplined way to touch the
  Chronicle: schema-probed, metadata-only, never rows of content.
- `docs/internal/session-format-sources.md` — a provenance manifest
  pinning upstream vscode/codex/copilot-cli commits per format claim.
  The single most valuable artifact in any candidate.

**Verdict: (c) format reference only.** Porting its per-format knowledge
into fresh TS is the plan; the Go codebase itself is too coupled to
vendor.

## 3. copilot-session-tools — widest Copilot CLI catalog, Python

Python ≥3.12 CLI+library with its own archive DB; deps ssrjson/jinja2/
markdown/pygments; optional typer/flask/litellm extras. Network call in
`version_check.py` (PyPI version probe) `[LOCAL]` — irrelevant since we
would never ship it, noted for completeness.

**What it knows `[LOCAL]`:**

- `copilot-cli`: the **largest event catalog** (~80 event types handled or
  enumerated — `session.*` lifecycle, `assistant.*`, `tool.execution_*`,
  `subagent.*`, `elicitation.*`, `hook.*`, `mcp.*`…), `workspace.yaml`
  full line-parse, fork via `session.info`/`infoType=fork`, background
  agents, legacy `history-session-state/` since CLI v0.0.342, flat
  `<uuid>.jsonl` **and** `<id>/events.jsonl` layouts.
- Chronicle: full schema read — `sessions`, `turns`, `checkpoints`,
  `session_files`, `session_refs`, `search_index` (FTS5),
  `schema_version`; uses `turns` as **content fallback** for sessions
  missing files (proves rows may exist without session dirs — relevant to
  the "absent in Chronicle ≠ absent in files" rule, and its inverse).
  ATTACH `mode=ro` here — but `state.vscdb` opened **without** `mode=ro`
  (defect to not replicate).
- `vscode-chat`: `.json` requests/messages parse + `state.vscdb`
  `ItemTable` heuristic (`LIKE '%copilot%chat%'`), but mutation replay
  incomplete (no kind 3, no splice `i`) and **no `.json`/`.jsonl` dedup**.
- No Codex. No `COPILOT_HOME`/`COPILOT_DIR` env handling — `~/.copilot` only.

**Verdict: (c) format reference only** — mine `scanner/cli.py` (event
catalog), `scanner/vscode.py` (vscdb heuristic), `db_retrieval.py`
(Chronicle schema) as checklists for the TS implementation.

## 4. cc-session-core — cleanest Codex schema, Python

Python ≥3.12 + pydantic; zero network, read-only, per-line `ParseFailure`
reporting `[LOCAL]`. Covers Claude Code + **Codex only**.

- Codex models: discriminated-union records over the full
  `{timestamp,ordinal,type,payload}` envelope — `session_meta`,
  `turn_context`, `response_item` (message/function_call/custom_tool_call/
  reasoning/compaction…), `event_msg` (task_started/complete, token_count,
  turn_aborted…) — with `extra="allow"` + `UnknownCodexRecord` fallback.
  Forward-compatible by design; its `--audit` reports fields that fell
  into `model_extra` — the exact forward-compat posture our parser needs.
- Discovery gaps: `rglob("*.jsonl")` under `$CODEX_HOME/sessions` without
  filtering `rollout-*` (would misclassify `session_index.jsonl`); no
  revert-page or archived_sessions semantics; no `id:` namespace.

**Verdict: (b/c)** — schema list ports 1:1 to TS unions; pair with
AgentsView's operational rules (forks, revert pages, session_index).
Lightest reference, but AgentsView knows more about *meaning*.

## 5. session-vault — the only `state.vscdb` reader, with leaks

VS Code extension (webview), TypeScript, single runtime dep `sql.js`
(SQLite WASM — no native module). Covers `vscode-chat` **only**.

**Unique asset `[LOCAL]`:** `SqliteReaderService` — opens
`workspaceStorage/<hash>/state.vscdb` (and `globalStorage/*.vscdb/.db`)
read-only in WASM and parses `ItemTable['chat.ChatSessionStore.index']`
(v5 format) plus generic ItemTable/ad hoc tables; plus a `RedactorService`
(secrets+paths). These are the two components nobody else has in TS.

**Defects that block adoption `[LOCAL]`:** discovery misses the canonical
`chatSessions/*.json` (requires field `id`, real files use `sessionId`)
and skips hash-dirs lacking a `github.copilot-chat` subdir; mutation
kind 3 handled as array-update not delete (**bug** vs the format);
fallback session IDs are `Date.now()+random` — unstable; `vscode.lm`
summarizer sends transcripts to the Copilot model (**network by another
name**); OutputChannel and diagnostics **log session titles, workspace
paths and session IDs unredacted** (`extension.ts:179`,
`sqliteReaderService.ts:289+`); DESIGN.md stale.

**Verdict: (b) partial vendor** — adapt `SqliteReaderService` (vscdb as
*optional index*, per spec) and `RedactorService` as references; nothing
else. UI is webview-heavy and leaks; our TreeView is unrelated.

## 6. copilot-session-viewer — architecturally inadoptable

Node ≥22 JavaScript (not TS) web app: **Express server on `0.0.0.0:3838`
with no auth**, Azure Application Insights telemetry **on by default**
with a hardcoded connection string, agent-CLI spawns
(`copilot --yolo`, `claude -p`, `pi -p`), writes into session dirs
(`tags.json`, `.imported` markers, `.agent-review.md`), three secondary
stores under `~/` `[LOCAL]`. Every product constraint is violated —
listed for format knowledge only.

- Widest *agent* coverage of any candidate: Copilot CLI (best discovery —
  dirs + flat + nested), Claude Code, Pi-Mono, Modernize, and VS Code
  `GitHub.copilot-chat/transcripts/*.jsonl` (agent transcripts — a
  different file family than canonical `chatSessions`).
- `lib/parsers/vscode-parser.js`: complete, correct mutation replay
  (kinds 0–3) — **dead code** in runtime but clean and unit-tested;
  useful cross-check for the SessionsAI port.

**Verdict: (c) format reference only** — specifically
`lib/parsers/vscode-parser.js` and the Copilot CLI adapter layout.

---

## Format facts established `[LOCAL]`/`[EXTERNO]`

- **`events.jsonl` is not undocumented.** The official `@github/copilot`
  package ships `pkg/universal/<ver>/schemas/session-events.schema.json`;
  `copilot-sdk` ships a `SessionEvent` union generated from it
  `[EXTERNO]` (github/copilot-sdk, `docs/features/streaming-events.md`).
  `session.start` carries `sessionId`, schema `version`, producer info;
  `ephemeral` discriminates persisted vs transient events; a real-world
  mismatch (CLI 1.0.54 omitted `ephemeral`, VS Code schema-validated on
  resume — issue github/copilot-cli#3520) proves the ecosystem validates
  against this schema. What is missing is a *stability contract* — issue
  github/copilot-cli#3551 asks to formalize `events.jsonl` as a public
  API. Treat the schema as authoritative-but-unversioned-contract.
- **Chronicle is a subset, files are truth** `[EXTERNO]` (GitHub docs,
  "About GitHub Copilot CLI session data"): `session-state/` holds the
  complete record; `session-store.db` powers `/chronicle` and is
  **rebuilt from the files** via `/chronicle reindex`. Non-official
  analysis enumerates tables `sessions/turns/files/refs/checkpoints` +
  FTS5 — consistent with copilot-session-tools' reads `[LOCAL]`.
- **VS Code itself now ships an "Agent Sessions" surface** `[EXTERNO]`
  (code.visualstudio.com docs): a sessions list covering Copilot Chat +
  Copilot CLI sessions, resume/archive/delete management. It requires
  Copilot Chat installed, covers no Codex, is a *management* UI not a
  read-only cross-agent inventory, and offers no metadata-only/privacy
  posture. Our gap remains real — but this overlap is recorded honestly
  for the G1 discussion.
- **Env-var divergence**: AgentsView honors `COPILOT_DIR` and
  `CODEX_SESSIONS_DIR`/`CODEX_HOME` `[LOCAL]`; the spec names
  `COPILOT_HOME`. Discovery scripts probe **all three**; parsers must
  too (verification left to the storage report).
- Extra discovery locations found beyond the spec's list:
  `globalStorage/transferredChatSessions` (vscode-chat),
  `~/.codex/archived_sessions/` + `session_index.jsonl` (Codex),
  `session-state/<uuid>.jsonl` flat layout (Copilot CLI),
  `~/.copilot/vscode.session.metadata.cache.json` (VS Code's own
  resumability cache — potential documented-alt ID source).

## What no candidate covers

Codex parsing in TypeScript: **nobody**. Chronicle reading in
TypeScript: nobody. `state.vscdb` reading: only session-vault (WASM).
Correct 0–3 mutation replay in TS: SessionsAI (and dead-code JS in
copilot-session-viewer).
