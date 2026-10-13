# Agent storage discovery report

Status: **owner-output-received**
Last updated: 2026-10-13

This report inventories where the three in-scope agents store sessions on
the owner's machine(s). It has three states:

| State | Meaning |
|---|---|
| `script-prepared` | Discovery tools exist but have not been run by the owner. |
| `owner-output-received` | Owner output received and analyzed. **Current state.** The only state that contains observed content. |
| `not-verified` | Insufficient evidence. |

> **Gate G1 is unblocked by this report for the surfaces marked `[LOCAL]`
> observed.** Remaining gaps are listed under "Evidence gaps" — the owner
> may still accept each of them in writing or request a complementary run.

## Collection method (evidence label context)

`[LOCAL]` entries below were collected **by the agent on behalf of the
owner** on 2026-10-13, in two ways:

- **Linux native** — `discover-agent-storage.py --pretty` run directly on
  this machine (Lubuntu). Result: **no in-scope agent installed** — every
  source reports `not-found`. This is a valid finding, not a failure:
  this Linux box is not where the agents run.
- **Windows (dual boot, offline)** — the NTFS system partition
  (`/dev/sda3`) was mounted **read-only** via `udisksctl mount -o ro` and
  `discover-agent-storage.py --root <windows-home>` was run against
  `Users/<USER>`. Plus targeted read-only probes (SQLite `mode=ro`/
  `immutable=1` schema reads, existence checks). No Windows process was
  executed; no file was modified.

Consequence: filesystem evidence is real and complete; **live probes are
absent** — CLI binary versions (`copilot --version`, `codex --version`)
could not be executed offline, and running-process state is unknown.
Versions below are inferred from install paths only.

## Inventory (observed)

### Environment

| Field | Value | Evidence |
|---|---|---|
| OS | Windows (NTFS, per-user installs) + Lubuntu Linux (dual boot) | `[LOCAL]` |
| VS Code (stable) | **1.139.1** (`AppData/Local/Programs/Microsoft VS Code/`) | `[LOCAL]` install path |
| `github.copilot-chat` extension | **not installed now** — `.vscode/extensions/` has 22 extensions, none Copilot; chat data persists from earlier use | `[LOCAL]` |
| `copilot` CLI | binary not found in standard paths; `~/.copilot/` tree exists + `AppData/Local/copilot/` (`copilot-user-cache.json`, `managed-settings/<sha256>.json`) | `[LOCAL]` presence; version `[NÃO VERIFICADO]` |
| `codex` CLI | binary not found; `~/.codex/` tree exists (`installation_id`, 5 sqlite DBs, `skills/`, `tmp/`) | `[LOCAL]` presence; version `[NÃO VERIFICADO]` |
| `chat.disableAIFeatures` | unset | `[LOCAL]` |
| Python / Node | Windows: `Python314/` at root; npm-global has `opencode`, `pi`, `devin-bridge`, etc. Linux: Python 3.14.4, Node 22.20.0 | `[LOCAL]` |
| `managed-settings/` under `AppData/Local/copilot/` | present (1 sha256-named file) — **possible managed/corporate policy signal** for G1(f) | `[LOCAL]` existence only; content unread |

### Surface: Copilot VS Code Chat — `vscode-chat`

| Location | Exists | Item count | Day range | Notes |
|---|---|---|---|---|
| `workspaceStorage/*/chatSessions/` | yes | 13 dirs / 24 files (**5 `.json` + 19 `.jsonl`**) | 2026-01-21..2026-10-01 | both formats coexist `[LOCAL]` |
| `workspaceStorage/*/chatEditingSessions/<id>/state.json` | yes | present alongside chatSessions | — | editing-session state, new `[LOCAL]` |
| `workspaceStorage/*/GitHub.copilot-chat/` | yes | `debug-logs/<id>/main.jsonl`, `transcripts/<id>.jsonl` | — | per-session transcripts `[LOCAL]` |
| `globalStorage/emptyWindowChatSessions/` | yes | `.json` + `.jsonl` mixed | — | `[LOCAL]` |
| `globalStorage/github.copilot-chat/` | yes | `session-store.db` (**0 tables — created but empty**), `copilot.cli.oldGlobalSessions.json`, agent dirs `ask-agent`, `plan-agent`, `explore-agent`, `copilotCli`, `copilot-cli-images`, `debugCommand`, `logContextRecordings` | — | agent-mode dirs are new surface `[LOCAL]` |
| `globalStorage/state.vscdb` | yes | 1 table (`ItemTable`); `state.vscdb.backup` present | — | `[LOCAL]` |
| `workspaceStorage/` total | yes | 30 workspace entries | — | `[LOCAL]` |

Key finding: **Copilot Chat is currently uninstalled but all chat data
persists** — the extension must work with the extension absent `[LOCAL]`.

### Surface: Codex CLI — `codex-cli` — ⚠ spec assumption invalidated

| Location | Exists | Count | Notes |
|---|---|---|---|
| `~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl` | **no** | 0 | directory absent entirely `[LOCAL]` |
| `~/.codex/archived_sessions/` | no | 0 | `[LOCAL]` |
| `~/.codex/state_5.sqlite` | **yes** | 15 tables | **schema v5: `threads` (41 cols incl. `rollout_path`, `cli_version`, `first_user_message`, `preview`, `tokens_used`, `git_*`, `project_id`), `thread_sections`, `thread_spawn_edges`, `rollout_migration_state`, `rollout_migration_skipped_rollouts`, `projects`, `project_roots`, `thread_attachments`, `backfill_state`, `remote_control_enrollments`, `external_agent_config_imports`, `thread_dynamic_tools`, `project_idempotency_keys`, `_sqlx_migrations`** `[LOCAL]` |
| `~/.codex/` aux DBs | yes | `logs_2`, `goals_1`, `memories_1`, `queue_1` (sqlite, sqlx-migrated) | `[LOCAL]` schema names only |
| `threads` rows | — | **0** | no recorded sessions; `rollout_path` column exists but unpopulated `[LOCAL]` |
| `rollout_migration_state` rows | — | 0 | `[LOCAL]` |

Key finding: this Codex install uses **sqlite (`state_N.sqlite` +
`threads.rollout_path`), not `rollout-*.jsonl` files** — and migration
tables (`rollout_migration_state`, `rollout_migration_skipped_rollouts`)
prove the JSONL→sqlite transition is real in the wild. The spec's
parser target (`~/.codex/sessions/**/rollout-*.jsonl`) covers
pre-migration installs only. **G1 must decide whether the Codex parser
targets rollouts, `state_*.sqlite`, or both** — with 0 threads here, no
real Codex session data was observable either way `[LOCAL]` +
`[NÃO VERIFICADO]` for the rollout format on migrated installs.

### Surface: Copilot CLI — `copilot-cli`

| Location | Exists | Count | Notes |
|---|---|---|---|
| `~/.copilot/session-state/<id>/` | yes | **1 session dir** | `events.jsonl` (191 events) + `workspace.yaml` + `session.db` + `checkpoints/` + `files/` + `research/` `[LOCAL]` |
| `~/.copilot/session-state/<id>.jsonl` (flat) | no | 0 | `[LOCAL]` |
| `$COPILOT_DIR` / `$COPILOT_HOME` | n/a offline | — | env not observable; default `~/.copilot` used `[NÃO VERIFICADO]` |
| `~/.copilot/history-session-state/` (legacy) | no | 0 | `[LOCAL]` |
| `~/.copilot/session-store.db` (Chronicle) | yes | **17 tables**: `sessions`, `turns`, `session_files`, `session_refs`, `checkpoints`, `assistant_usage_events`, `dynamic_context_items`, `forge_skill_proposals`, `forge_trajectory_events`, `schema_version`, `search_index` + FTS5 shadows, `sqlite_sequence` | `[LOCAL]` schema only |
| `~/.copilot/vscode.session.metadata.cache.json` | no | — | `[LOCAL]` |
| `~/.copilot/pkg/**/session-events.schema.json` | no | — | schema ships inside the CLI package, not the home dir `[LOCAL]` |
| `session.db` inside a session dir | yes | `inbox_entries`, `todos`, `todo_deps` | **new undocumented per-session sqlite** `[LOCAL]` |

Key findings:
- **`events.jsonl` envelope confirmed real**: first event is
  `{"id","parentId","timestamp","type":"session.start","data":{"version":1,...}}`
  — matches the shipped-schema envelope; `source_version: "1"` is
  obtainable `[LOCAL]` (envelope fields only; no content read).
- **Observed event-type catalog** (191 events, 16 distinct `type`
  values, discriminators only): `hook.start`/`hook.end` (39 each),
  `tool.execution_start`/`tool.execution_complete` (16 each),
  `assistant.turn_start`/`assistant.turn_end`/`assistant.message` (13
  each), `permission.requested`/`permission.completed` (13 each),
  `system.message`/`user.message`/`session.usage_checkpoint` (3 each),
  `subagent.deselected`/`session.model_change` (2 each),
  `session.start`/`session.auto_mode_resolved`/`session.shutdown` (1
  each) `[LOCAL]`. Envelope union across all events: exactly
  `{id, parentId, timestamp, type, data}` — no extras observed.
  Several types (`hook.*`, `permission.*`, `session.usage_checkpoint`,
  `subagent.*`) are absent from some reference parsers — pass-through
  counting is mandatory.
- `workspace.yaml` top-level keys: `id`, `name`, `user_named`,
  `summary_count`, `created_at`, `updated_at`, `client_name`,
  `host_type` + path-bearing `cwd`, `git_root`, `repository`, `branch`
  (usable for `workspace-hash`, never emitted) `[LOCAL]` keys only.
- Per-session `session.db` (`todos`, `inbox_entries`, `todo_deps`) is a
  storage location none of the six candidates documents `[LOCAL]`.
- `managed-settings/` presence is a corporate-policy signal → G1(f).

### Errors / access-denied

None. The only probe failure was opening `state_5.sqlite` without
`immutable=1` (WAL-mode DB on a read-only mount) — resolved by adding
`immutable=1`; the discovery scripts' sqlite path unaffected.

## Evidence gaps (owner may accept in writing or close later)

1. `copilot`/`codex` CLI **versions** — binaries not locatable on disk
   paths probed; cannot execute offline. `[NÃO VERIFICADO]`
2. Whether Codex `threads.rollout_path` still points at live JSONL
   files on installs that *have* sessions — 0 threads observed. `[NÃO VERIFICADO]`
3. WSL/Remote-SSH/devcontainer environments — none configured on the
   observed Windows install (no `.vscode-server`); remote machines, if
   any, need their own run. `[NÃO VERIFICADO]`
4. The PS1 script was **not** run live on Windows (partition read
   offline). Its probes are equivalent for filesystem facts but a live
   run would also capture env vars (`COPILOT_DIR`, `CODEX_HOME`) and
   binary versions. Optional future run. `[NÃO VERIFICADO]`
5. `chat.disableAIFeatures` = unset on the observed profile; other
   profiles exist under `Code/User/profiles/` (uninspected). `[LOCAL]` partial

## What this report never contains

Message text, session titles, project folder names, `workspace.json` /
`workspace.yaml` contents, Chronicle row data, absolute paths with
usernames, or arbitrary strings. Unknown discriminating values appear as
`<OTHER>` + count. Permission failures are recorded and do not abort the
run.
