# Prior art

Checked on GitHub in November 2026. Nothing here was copied: the ideas were reimplemented in a small stdlib script. Verify each license before reusing any code.

| Project | What it does | Adopted in Devin Ledger | Not adopted, and why |
|---|---|---|---|
| steveyegge/beads (`bd`) | Git-backed, dependency-aware issue tracker used as agent memory; hash IDs, `ready` work, audit trail, compaction of closed tasks, works without git (`BEADS_DIR`) | Hash IDs, `--after` / `--discovered-from` links, `ready`, append-only audit trail | Dolt or a Go binary and a `curl \| bash` installer are heavy for a local-first, stdlib-only catalog. Docs appear under both steveyegge and gastownhall: confirm the canonical repo |
| MrLesk/Backlog.md | Markdown task per file, acceptance criteria, Kanban, MCP and CLI for Claude Code, Gemini CLI, Codex, Kiro | Acceptance criteria as a checklist, criteria shown before work starts, readable Markdown export | A separate task manager UI; the ledger only needs open loops |
| OthmanAdi/planning-with-files | `SKILL.md` standard for 60+ agents; `task_plan.md`, `findings.md`, `progress.md`; hooks on prompt submit, pre-tool, pre-compact and stop; session catch-up from `git diff` | `catchup`, hook-based `prime` and stop gate, workers keep their own records, injection hygiene (auto-read files amplify untrusted text) | Per-project plan files; the user's problem spans projects, so the ledger is global |
| github/spec-kit | Spec, plan and tasks artifacts; `/speckit.analyze` for consistency, `/speckit.converge` to compare the implementation with the tasks | Close-out check that evidence matches the criteria (`done --met`, `audit`) | The full spec-driven pipeline; out of scope |
| eyaltoledano/claude-task-master | `tasks.json` with dependencies and priorities, `next`, `--blocking`, MCP for several editors; handover notes between sessions; fixed lost updates from concurrent windows | `ready`, priorities, `park --note` as the handover, a lock plus an append-only log against lost updates | Needs model API keys; license is MIT with Commons Clause, so do not reuse its code in a redistributed product |
| automazeio/ccpm | Project management for agents on GitHub Issues, git worktrees, parallel streams | `--link` to an issue or PR, one record per delegated unit | GitHub as the database: it would add a network dependency |

## What none of them enforces

- A hard limit of one active task, refused in code.
- A closing gate that fails while any task is still active.
- Evidence required before a task can be marked done, checked offline by `audit`.
- Orphan detection for tasks left active by a dead session.
