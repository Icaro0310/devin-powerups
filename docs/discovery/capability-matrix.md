# Capability matrix — parsing & discovery only

Cell values: `pass` / `partial` / `fail` / `n/a` / `not-verified`
(default). Columns per row: state, evidence, tested version. This matrix
evaluates parsing and discovery capability — **not** candidate
architecture (a `pass` row does not imply adoptability; see
`existing-tools-evaluation.md` §per-candidate verdicts). All evidence is
`[LOCAL]` source inspection of clones dated 2026-10-13 unless noted.

## Summary (state only)

| Capability | SessionsAI | AgentsView | copilot-session-tools | cc-session-core | session-vault | copilot-session-viewer |
|---|---|---|---|---|---|---|
| vscode-chat `.json` parse | pass | pass | pass | n/a | fail | partial |
| vscode-chat `.jsonl` mutations 0–3 | pass | pass | partial | n/a | partial | partial† |
| `state.vscdb` read | fail | fail | partial | n/a | pass | fail |
| Codex rollout parse | fail | pass | fail | pass | fail | fail |
| copilot-cli `events.jsonl` parse | pass | pass | pass | n/a | fail | pass |
| `session-state` + flat `<id>.jsonl` discovery | pass | pass | pass | n/a | fail | pass |
| Chronicle `session-store.db` read | fail | pass | pass | n/a | not-verified | fail |
| legacy `history-session-state/` | fail | fail | pass | n/a | fail | fail |
| stable/dedup session IDs | pass | pass | pass | partial | partial | pass |
| graceful missing/corrupt | pass | pass | pass | pass | pass | partial |
| metadata-only listing | partial | partial | partial | fail | fail | partial |
| zero-network | pass | fail | fail | pass | fail‡ | fail |
| read-only to sources | pass | pass | partial | pass | pass | fail |
| redaction/privacy posture | fail | n/a | n/a | n/a | partial | fail |
| TypeScript-native / portable | pass | partial | partial | pass | pass | fail |

† correct replay exists but is dead code (unused at runtime).
‡ `vscode.lm` summarizer = indirect network.

## Per-candidate detail

### SessionsAI 0.4.1

| Capability | State | Evidence |
|---|---|---|
| vscode-chat `.json` | pass | `src/vscodeChatParser.ts:57-64`, `sessionStore.ts:88` |
| `.jsonl` mutations 0–3 | pass | `vscodeChatParser.ts:57-134` — kinds 0–3, kind 3 = delete |
| `state.vscdb` | fail | not read; filesystem discovery only (`sessionStore.ts:227-252`) |
| Codex rollout | fail | no reference anywhere |
| copilot-cli `events.jsonl` | pass | `copilotCliParser.ts:96+`; dirs + flat `*.jsonl` (`sessionStore.ts:202-225`) |
| Chronicle | fail | no sqlite |
| IDs/dedup | pass | `source:id` key (`sources.ts:62`); `.jsonl` > `.json` (`sessionStore.ts:111`) |
| graceful states | pass | `readdirSafe`, per-file try/catch, truncated-line tolerance |
| metadata-only | partial | always builds `searchText` incl. content |
| zero-network | pass | clean src; only dev-script fetches |
| read-only | pass | only writes `os.tmpdir()` handoff dir |
| redaction | fail | none — titles/cwd/prompts raw in webview |

### AgentsView @ fd3eeb0

| Capability | State | Evidence |
|---|---|---|
| vscode-chat `.json` | pass | `internal/parser/vscode_copilot.go:178-327` |
| `.jsonl` mutations 0–3 | pass | `vscode_copilot.go:711-832`; splice `i` (`jsonlPush:1020-1054`); `resultDetails.output` projection (`:908-925`) |
| `state.vscdb` | fail | not for vscode-copilot (`vscode_copilot_provider.go:177-198`) |
| Codex rollout | pass | `codex.go:390-620`; revert pages `:1914-1929`; `session_index.jsonl` `codex_metadata.go:23-55` |
| copilot-cli `events.jsonl` | pass | `copilot.go:609-782`; flat+dir layouts (`copilot_provider.go:157-238`) |
| Chronicle | pass | `assistant_usage_events` only, schema-probed, `mode=ro` (`copilot.go:478-554`, `sqlite_dsn.go:18-26`) |
| IDs/dedup | pass | `source:` prefixes; `<thread>_<rollout>` continuation keys |
| graceful | pass | missing→nil, `malformedLines` counter, 128 MB record cap |
| metadata-only | partial | `SourceFingerprint` exists; parse always yields content |
| zero-network | fail | S3/minio, HTTP server, sync mirrors |
| read-only | pass | `mode=ro` DSNs throughout |

### copilot-session-tools 0.19.0

| Capability | State | Evidence |
|---|---|---|
| vscode-chat `.json` | pass | `scanner/vscode.py:588-719` |
| `.jsonl` mutations 0–3 | partial | `vscode.py:875-976` — no kind 3, no splice `i` |
| `state.vscdb` | partial | `vscode.py:722-759` ItemTable `LIKE` heuristic; **no `mode=ro`** |
| Codex rollout | fail | — |
| copilot-cli `events.jsonl` | pass | `scanner/cli.py:722-1588` — widest event catalog (~80 types) |
| Chronicle | pass | `database.py:252-313` ATTACH `mode=ro`; sessions/turns/checkpoints/files/refs/search_index |
| legacy `history-session-state/` | pass | `discovery.py:123-143` (since CLI v0.0.342) |
| IDs/dedup | pass | `_SESSION_ID_RE`; `SessionIdentityConflictError` |
| graceful | pass | per-line JSONDecodeError skip; invalid file→None |
| metadata-only | partial | `SessionFileInfo` path/mtime/size only |
| zero-network | fail | `version_check.py:50-52` PyPI probe; optional litellm/flask |
| read-only | partial | Chronicle `mode=ro` yes; `state.vscdb` no; git subprocesses |

### cc-session-core 0.2.0

| Capability | State | Evidence |
|---|---|---|
| vscode-chat (all) | n/a | not covered (Claude Code + Codex only) |
| Codex rollout | pass | `codex/parse.py`, `codex/models.py:600-673`, `codex/session.py:265-528` — lossless unions, `extra="allow"` |
| copilot-cli / Chronicle | n/a | not covered |
| IDs/dedup | partial | `session_id or id`; no `source:` namespace; `rglob` w/o `rollout-` filter |
| graceful | pass | per-line `ParseFailure` (file, line, error, raw≤600 chars) |
| metadata-only | fail | always normalizes content |
| zero-network | pass | clean; optional stdio MCP only |
| read-only | pass | — |

### session-vault 1.0.6

| Capability | State | Evidence |
|---|---|---|
| vscode-chat `.json` | fail | `looksLikeSessionContainer` requires `id` not `sessionId` (`discoveryService.ts:481`); jsonl-dir scan `.jsonl` only |
| `.jsonl` mutations 0–3 | partial | `sqliteReaderService.ts:112-199` — kind 3 as update not delete (bug) |
| `state.vscdb` | pass | `sqliteReaderService.ts:208-493` — `chat.ChatSessionStore.index`, generic ItemTable, arbitrary tables; sql.js WASM |
| Codex / copilot-cli / Chronicle | fail | not covered (Chronicle `not-verified` via generic reader override) |
| IDs/dedup | partial | fallback `Date.now()+random` — unstable |
| graceful | pass | `safe*` wrappers, per-file errors[], diagnostics panel |
| metadata-only | fail | always loads `messages[]` |
| zero-network | fail | `llmSummarizerService.ts:102-121` `vscode.lm.sendRequest` |
| redaction | partial | `RedactorService` exists but OutputChannel/diagnostics/webview leak titles+paths |
| read-only | pass | writes only via save dialog |

### copilot-session-viewer 0.4.1

| Capability | State | Evidence |
|---|---|---|
| vscode-chat `.json` | partial | parser exists (`lib/parsers/vscode-parser.js`) but dead code — adapter only reads `transcripts/*.jsonl` + jsonl metadata |
| `.jsonl` mutations 0–3 | partial | `vscode-parser.js:79-194` correct replay — unused at runtime |
| `state.vscdb` | fail | — |
| Codex rollout | fail | — |
| copilot-cli `events.jsonl` | pass | `CopilotAdapter.js` — dirs + flat + recursive; best copilot-cli discovery |
| Chronicle | fail | — |
| other surfaces | pass | Claude Code, Pi-Mono, Modernize adapters |
| IDs/dedup | pass | `sessionRepository.js:156-165` keeps newest |
| graceful | partial | `allSettled`+try/catch; no user-visible state |
| metadata-only | partial | 1-pass metadata stream but extracts `firstUserMessage` content |
| zero-network | fail | Express `0.0.0.0:3838`, App Insights default-on, agent-CLI spawns |
| read-only | fail | writes `tags.json`, `.imported`, `.agent-review.md` into session dirs |

## Reading for the G1 decision

- **Correct 0–3 mutation replay exists in TS exactly once** (SessionsAI)
  and in dead-code JS once (copilot-session-viewer) — cross-validation
  pair for the port.
- **Codex has zero TS coverage anywhere** — must be built; best schema
  source cc-session-core, best semantics AgentsView.
- **Chronicle**: two independent readers confirm the same schema
  (`assistant_usage_events` AgentsView; full table list
  copilot-session-tools) — but official docs define it as a *subset*
  rebuilt from files → never a primary source `[EXTERNO]`.
- **`state.vscdb`**: only session-vault reads it (WASM). Spec already
  marks it an *optional index* — consistent with keeping it out of MVP
  or behind the sql.js dependency decision at G1.
