# Evidence equivalence: local stores ↔ cloud API ↔ MCP

> Status: **in progress — local leg + unauthenticated discovery complete**
> (authorized 2026-10-09, owner chose "local now, cloud pending-auth").
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

## Evidence matrix (local leg + unauthenticated discovery, 2026-10-09)

Local column filled from `docs/evidence-equivalence/local-fixture-n10.json`
(a sanitized JSON summary — usernames and real home paths redacted; it is
NOT the directory fixture contract-check consumes — reconciling the two
formats is still pending, see Method step 2)
(N=10 sessions: 4 GUI, 2 CLI, 4 automation). MCP column filled from a live
unauthenticated `tools/list` against `https://mcp.devin.ai/mcp` (DeepWiki
server v2.14.3, 24 tools — `devin_*` tools enumerate fully but invoke in
"private mode" only, i.e. they still need the org credential to run).
Cloud column: `api.devin.ai/v1/sessions` answers 403 unauthenticated
(exists, gated); `v3` is reached through `devin_session_*` MCP tools
(`devin_session_create` says it wraps "the v3 REST API").

| signal | local store (verified N=10) | cloud API | MCP (schema-verified) | verdict |
|---|---|---|---|---|
| session list + metadata | `sessions` (90 rows: id, title, wd, model, agent_mode, created/last_activity, cogs_json, workspace_dirs, hidden, metadata) | v1 403 gated | `devin_session_search` (filters incl. parent_session_id, origins, tags) + `devin_session_interact get` (title, status, status_detail, url, tags, acus_consumed, child_session_ids, pull_requests, structured_output) | `partial` — MCP get fields omit local metadata such as `working_directory`/`workspace_dirs`; keep provisional until a live diff |
| message turns | `message_nodes` (role/content per turn; N=10 range 46–73 166 turns) | ? | `devin_session_events` list/details/search with `event_types`/`categories` filters | `partial` — event taxonomy vs role turns needs auth to diff |
| tool calls | `tool_call_state` (kind/title/rawInput/status via ACP JSON; N=10 range 0–4 297 calls) | ? | same `devin_session_events` — tool-call granularity unverified | `partial` — strongest `local-only` suspect (ACP payload) |
| cost / ACU / tokens | `cogs_json` + `metadata.total_*` + `num_tokens_preceding` rows; per-turn cost lives only in live ACP meta, never on disk (contract.py) | ? | `acus_consumed` on interact get + `devin_billing_tag_manage` (session↔tag for usage tracking) | `partial` — ACU yes, token detail unverified |
| session state | derived (session_locks + last_activity) | ? | `status` + `status_detail` (`finished`, `waiting_for_user`, `waiting_for_approval`, `suspended`, `error`, `exit`) | `cloud-richer` — server-authoritative beats lock-file inference |
| subagent linkage | `subagent_heads` (0 rows on all 90 sessions — unused) | ? | `child_session_ids` on get + `parent_session_id` filter on search | `cloud-only` — local table is dead |
| permission requests | `tool_call_update_json` rows containing "permission" (GUI sessions: 0–118 — all four sampled GUI sessions run `bypass`, yet two still carry 28/118 rows, so nonzero counts reflect IDE-level prompts rather than mode; CLI/automation: 0) + PAS hooks JSONL | ? | `status_detail="waiting_for_approval"` exists; per-request events unverified | `partial` — aggregated state yes, request-level unknown |
| workspace / working_directory | `sessions.working_directory` + `workspace_dirs` (key present, empty array in all N=10 samples) | ? | not in the documented get-fields | `local-only` (pending auth) |

Verdict values: `equivalent` · `partial` (subset/renamed/delayed) ·
`local-only` · `cloud-only` · `cloud-richer` (the official surface
carries a strictly stronger signal than the local store).

## Method

1. Take N=10 recent sessions spanning CLI + GUI + automation.
   **Done 2026-10-09** — 4 GUI (`zinc-crabapple`, `cool-exoplanet`,
   `evergreen-pair`, `deep-adverb`), 2 CLI (`aspiring-glove`,
   `silicon-sweater`), 4 automation (`fearless-bead` heartbeat,
   `paint-echium` judge-scoring, `sleet-borogovia` slack-brain,
   `adorable-potato` repo-scout). Classification: `client_meta.
   cognition.ai/requestingTabId` present → GUI; no tab + machine title →
   automation; no tab + human title → CLI.
2. For each surface, extract the signal set above into a normalized
   fixture. NOTE: the N=10 artifact is a JSON summary, not the directory
   fixture contract-check consumes — reconciling the two formats (or
   extending contract-check to accept the summary) is a pending sub-task.
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
