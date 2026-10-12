# Adapter checklist — the contract every face must satisfy

An adapter exposes a package's existing surface to a new host: an AI
client (skill, plugin, MCP), an editor (VS Code), a scheduler (daemon)
or a git hook (pre-commit). It is a **thin shell** — it calls the
package's own CLI (`<pkg-cli> <cmd> --json`) or core API and returns the
same payload, so no face can drift from what the CLI says.

Skeletons for the six faces live in [`adapters/`](../adapters/README.md);
the working example is devin-doctor's VS Code extension
(`packages/doctor/adapters/vscode` in devin-explore). This file is the
enforceable contract — `adapters/README.md` summarizes it, and where
they disagree this file wins.

## Rules

### Rule 1 — No mutation on AI-driven surfaces

Skill, plugin and MCP faces are **read-only / dry-run**. They never
expose a mutating operation: no `--apply`, no delete, no restore, no
approve, no spawn/kill, no process control. Mutating commands stay in
the human CLI and are never even *named* on an AI surface — describing
them there is itself a violation.

Enforced by: `adapters/skill/test_skill.py` (banned-flag grep over
SKILL.md) and, for packages with a mutating half, a source scan in the
MCP test asserting the module never imports the mutating core function
(`test_mcp_never_imports_mutating_core` in `adapters/mcp/test_mcp.py`).

### Rule 2 — One logic, many faces

The adapter returns the same payload as `<pkg-cli> <cmd> --json`.
Verdicts, exit codes and field meanings come from the package — nothing
is recomputed, parsed-then-rewritten or second-guessed. Reimplemented
business logic is a bug; **drift between the CLI and an adapter is a
high-priority bug** — a CLI change and its adapter update land in the
same PR.

Enforced by: payload-parity assertions in each face's test
(`do_<verb>() == <pkg-cli> <verb> --json` on the same synthetic fixtures
the CLI tests use) and thin-shell greps like
`assert args[1:] == ["check", "--json"]` in the daemon/precommit tests.

### Rule 3 — ≤200 lines per face

Each adapter surface stays under 200 lines of adapter code, excluding
tests. More means logic is leaking out of the core — refactor the core
instead. Verify with `wc -l` on the face's files (the working example,
doctor's `extension.js`, is ~150).

### Rule 4 — Own test, runs in isolation

Every face ships its own test, runnable standalone through
[`.github/workflows/adapter-test.yml`](../.github/workflows/adapter-test.yml)
on both Windows and Ubuntu. Tests go through injected seams (`runner=`,
`sleep=`, a `vscode` stub) — never a real store, real user data or a
live MCP connection — and use the same synthetic fixtures the package's
CLI tests use.

### Rule 5 — No renames

Package names, registry entry points and CLI flags stay exactly as they
are. An adapter exposes; it never rebrands.

## Registration

- A face that adds a console script (`<pkg>-mcp`, `<pkg>-daemon`) is
  registered in the product entry's `entrypoints` array in
  `registry.json`.
- Faces that ship no executable (skill, plugin manifest, VS Code
  extension, pre-commit manifest) add no entry.
- `adapters/` is the plugin root — self-contained, no symlinks out of
  the directory (they break git-subdir fetches and Windows checkouts).

## CI wiring

Each face gets a `uses:` job in the product repo, scoped to the face's
paths — see the caller template in
[`.github/workflows/VARIANTS.md`](../.github/workflows/VARIANTS.md).

## Pre-merge checklist

- [ ] Thin shell: every payload comes from the package CLI or core —
      nothing recomputed in the adapter
- [ ] Face test exists and passes in isolation (`adapter-test.yml`
      green on Windows + Ubuntu)
- [ ] `registry.json` updated if — and only if — the face adds a console
      script
- [ ] Face is ≤200 lines excluding tests
- [ ] AI-driven surfaces expose read/dry-run payloads only — no
      mutating flag or command is even named
- [ ] CLI and adapter changed in the same PR wherever output, flags or
      exit codes moved — zero drift
