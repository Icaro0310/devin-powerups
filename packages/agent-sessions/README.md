# Agent Sessions

Read-only, local-first browser for AI-agent chat sessions. Inventories
persisted sessions from three surfaces — **VS Code Copilot Chat**,
**Copilot CLI**, and **Codex CLI** — in one canonical model.

- **No backend, no daemon, no network** — reads local files only.
- **No writes** — never modifies agent storage.
- **Metadata-first** — titles are suppressed by policy (auto-generated
  titles are derived from message content). Sessions are listed by
  timestamp, surface, workspace hash and canonical ID.
- **Works without the agents installed** — reads persisted files even
  when Copilot Chat is uninstalled.

## Surfaces

| TreeView | `@sessions` chat |
|---|---|
| Primary UI — activity-bar view listing sessions grouped by agent, newest first, with parse-warning badges. | Secondary — ask `@sessions` for an overview or filter (`@sessions copilot-cli`, a workspace hash, an ID fragment). |

Commands: **Agent Sessions: Refresh** (view title / command palette),
**Agent Sessions: Open Details** (context menu on a session — opens a
read-only metadata document).

The extension also vendors a TypeScript port of `devin-redact`'s text
surface (`redact_text`/`scan_text`) for the future content-search leg —
it redacts text snippets only; full-file and database scanning remain
Python CLI capabilities, out of scope for this package.

## Session states

`ok` · `partial` (parsed with warnings) · `no-sessions` ·
`source-not-found` (agent not detected) · `read-error` ·
`unsupported-format`. A warning badge on a session means the record was
incomplete or non-canonical — details are in the tooltip and the
details document.

## Privacy

All parsing runs locally. Parse warnings use sanitized templates
(codes and counts only). Content-derived fields (auto titles, previews,
first-message text) are never read into the canonical model.

Requires VS Code 1.100+. MIT.

## Development

`npm run build` compiles `src/` + `adapters/` to `out/` (ESM).
`npm run vscode:package` produces `agent-sessions.vsix`.
**`engines.vscode` and `@types/vscode` move together** — `vsce` rejects
a types version newer than `engines`; bump both in the same commit.
