# Evidence equivalence: local stores ↔ cloud API ↔ MCP

> Status: **open — pending owner authorization to start** (decision
> recorded in session `ribbon-substance`, 2026-10-06).
> This is a pre-milestone gate: the official-API adapter may only be
> implemented after this investigation proves (or disproves) that the
> three evidence surfaces carry equivalent signals.

## Background

The ecosystem reads Devin's state from **local SQLite stores**
(`sessions.db`, `acp-messages/*.db`, `state.vscdb`). Devin also exposes
official surfaces — the cloud REST API (`api.devin.ai`, v1 documented,
v3 where present) and the official MCP server surface. A proposal to
build an "official adapter" (cloud/MCP as an alternative evidence
source for explore/state/assure tools) was evaluated and deferred:
the entry condition is proving **evidence equivalence** first.

## The claim to test

> For every signal the local tooling actually consumes, an equivalent
> signal exists on at least one official surface — or the gap is
> enumerated, classified, and accepted.

## Evidence matrix (to fill)

| signal | local store | cloud API | MCP | verdict |
|---|---|---|---|---|
| session list + metadata | `sessions` table | ? | ? | |
| message turns (user/assistant) | `message_nodes` | ? | ? | |
| tool calls (kind/title/rawInput/status) | `tool_call_state` | ? | ? | |
| cost / ACU / tokens | `cogs_json`, session meta | ? | ? | |
| session state (running/blocked/closed) | derived (locks + activity) | ? | ? | |
| subagent linkage | `subagent_heads` (empty today) | ? | ? | |
| permission requests | hooks JSONL only | ? | ? | |
| workspace / working_directory | `sessions` + `state.vscdb` | ? | ? | |

Verdict values: `equivalent` · `partial` (subset/renamed/delayed) ·
`local-only` · `cloud-only`.

## Method

1. Take N=10 recent sessions spanning CLI + GUI + automation.
2. For each surface, extract the signal set above into a normalized
   fixture (same shape the contract-check uses today).
3. Diff per signal; record verdict + drift notes.
4. Publish this doc with the matrix filled and a verdict:
   `adapter-justified` / `adapter-redundant` / `adapter-partial`.

## Constraints

- `DEVIN_API_KEY` is **deliberately not configured** (decision
  2026-10-04): the cloud harvester path stays env-gated and dormant.
  The uncredentialed half of this investigation (local ↔ public MCP/REST
  surface) needs no key. The credentialed half needs the owner to either
  provide the key for the run or accept a partial verdict.
- Read-only everywhere. No writes to sessions.db or cloud state.

## Why this gate exists

Two past mistakes this prevents: (a) building an adapter that re-reads
signals the local stores already give richer/faster, and (b) assuming
the cloud API exposes the same granularity (`tool_call_state`'s ACP
payload is the strongest suspect for `local-only`).

## Exit

- Verdict `adapter-justified` → adapter milestone may be scheduled.
- `adapter-redundant` → record a standing negative decision in
  DECISIONS.md and close this line.
- `adapter-partial` → enumerate accepted local-only signals; adapter, if
  built, covers only the equivalent subset.
