# Agent storage discovery report

Status: **script-prepared**
Last updated: 2026-10-13

This report inventories where the three in-scope agents store sessions on
the owner's machine(s). It has three states:

| State | Meaning |
|---|---|
| `script-prepared` | Discovery tools exist but have not been run by the owner. **Current state — first run.** |
| `owner-output-received` | Owner ran the tools; output received and analyzed. The only state that contains observed content. |
| `not-verified` | Insufficient evidence. |

> **Gate G1 is blocked while this report is `script-prepared`.** It may only
> advance on `owner-output-received`, or on written acceptance of each gap
> and its consequences. Accepting missing evidence is not the same as
> verification.

## How to run (owner)

Pick **one** of the following on each machine that should be covered. All
three are read-only diagnostics; none modifies anything on disk. Each emits
a JSON report with counts, logical paths (`~/...`, `<USER>`), size buckets
and schema names only — never message content, titles, project names or
usernames. **Sanity-check the output anyway before pasting it back.**

1. **PowerShell** (Windows PowerShell 5.1+, no admin):

   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File scripts/discovery/discover-agent-storage.ps1
   ```

   Self-test first if desired: add `-SelfTest` (prints PASS/FAIL, exit 0).

2. **Python 3** (any OS, standard library only — preferred on
   Linux/macOS/WSL):

   ```bash
   python3 scripts/discovery/discover-agent-storage.py --pretty
   ```

   Self-test: `--self-test` (prints PASS/FAIL, exit 0).

3. **Manual fallback** (`scripts/discovery/MANUAL-FALLBACK.md`) — one-line
   interactive commands for Constrained Language Mode, AppLocker or WDAC
   environments where script files cannot run at all.

Machines/environments to cover: native Windows, WSL, any Remote-SSH host or
devcontainer used with these agents. The report needs one output block per
environment; label each with where it ran.

## Inventory (pending owner output)

### Environment

| Field | Value |
|---|---|
| OS / WSL / devcontainer / SSH | _pending_ |
| VS Code (stable/insiders) version | _pending_ |
| `github.copilot-chat` extension version | _pending_ |
| `copilot` CLI version | _pending_ |
| `codex` CLI version | _pending_ |
| `chat.disableAIFeatures` | _pending_ |
| Python / Node present | _pending_ |

### Surface: Copilot VS Code Chat — `vscode-chat`

| Location | Exists | Item count | Day range | Notes |
|---|---|---|---|---|
| `workspaceStorage/*/chatSessions/` | _pending_ | _pending_ | _pending_ | |
| `workspaceStorage/*/GitHub.copilot-chat/chatSessions/` (+ lowercase variant) | _pending_ | _pending_ | _pending_ | |
| `globalStorage/emptyWindowChatSessions/` | _pending_ | _pending_ | _pending_ | |
| `globalStorage/transferredChatSessions/` | _pending_ | _pending_ | _pending_ | found via AgentsView `[LOCAL]` |
| `globalStorage/github.copilot-chat/` | _pending_ | _pending_ | _pending_ | |
| `globalStorage/state.vscdb` (tables, columns) | _pending_ | _pending_ | — | schema names only |

### Surface: Codex CLI — `codex-cli`

| Location | Exists | `rollout-*.jsonl` count | Day range | Notes |
|---|---|---|---|---|
| `~/.codex/sessions/YYYY/MM/DD/` | _pending_ | _pending_ | _pending_ | |
| `$CODEX_HOME/sessions/…` | _pending_ | _pending_ | _pending_ | env set? |
| `$CODEX_SESSIONS_DIR` | _pending_ | _pending_ | _pending_ | env set? `[LOCAL]` via AgentsView |
| `~/.codex/archived_sessions/` | _pending_ | _pending_ | _pending_ | flat layout `[LOCAL]` via AgentsView |
| `$CODEX_HOME/archived_sessions/…` | _pending_ | _pending_ | _pending_ | |

### Surface: Copilot CLI — `copilot-cli`

| Location | Exists | Count | Day range | Notes |
|---|---|---|---|---|
| `~/.copilot/session-state/<id>/` | _pending_ | _pending_ dirs_ | _pending_ | `events.jsonl` / `workspace.yaml` presence |
| `~/.copilot/session-state/<id>.jsonl` (flat) | _pending_ | _pending_ | _pending_ | flat layout `[LOCAL]` via AgentsView + copilot-session-tools |
| `$COPILOT_DIR/session-state/…` | _pending_ | _pending_ | _pending_ | env set? |
| `$COPILOT_HOME/session-state/…` | _pending_ | _pending_ | _pending_ | env set? |
| `~/.copilot/history-session-state/` (legacy) | _pending_ | _pending_ | _pending_ | |
| `~/.copilot/session-store.db` (Chronicle) | _pending_ | — | — | tables + columns only, never rows |
| `$COPILOT_DIR|COPILOT_HOME/session-store.db` | _pending_ | — | — | tables + columns only |
| `~/.copilot/vscode.session.metadata.cache.json` | _pending_ | — | — | VS Code resumability cache `[EXTERNO]` |
| `~/.copilot/pkg/**/session-events.schema.json` | _pending_ | _pending_ | — | shipped official schema count |

### Errors / access-denied

_pending_ — each entry: logical path + error kind.

## What this report never contains

Message text, session titles, project folder names, `workspace.json` /
`workspace.yaml` contents, Chronicle row data, absolute paths with
usernames, or arbitrary strings. Unknown discriminating values appear as
`<OTHER>` + count. Permission failures are recorded and do not abort the
run.
