---
name: <pkg>
description: "<what it reports + when to invoke it + the read-only claim, one line>"
triggers: [model, user]
allowed-tools:
  - exec
  - read
---

<!--
  Skeleton for packages/<pkg>/adapters/skills/<pkg>/SKILL.md — the Devin
  skill face (AI-driven surface).

  Rule 1 (docs/adapter-checklist.md): this is a read-only surface.
  Mutating CLI commands must not be exposed — do not name their flags
  anywhere in this file, not even to describe them; the skill test
  greps for them.
-->

# <pkg>

When the user asks <the question this package answers>, run the read
surfaces and report the answer:

```bash
<pkg-cli> <read-subcommand> --json
```

Or, when this plugin's MCP server is connected, call `<pkg>_<verb>` —
same payload.

## Reading the result

- `<field>` — <what it means, one line per field the agent must
  interpret correctly>
- `error`/`detail` — present on failure paths; report it, don't guess.

## Rules

- Read-only by design. This skill reports what the package reports — it
  never acts on the result.
- Removal/change is a human decision. If the user wants a plan carried
  out, point them at the CLI and let them run it.
- An `error` payload means "say so" — never invent a verdict.
