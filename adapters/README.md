# Adapter template — one logic, many faces

An adapter is a **thin shell** that exposes a package's existing surface
to a new host: an AI client (skill, plugin, MCP), an editor (VS Code), a
scheduler (daemon) or a git hook (pre-commit). It carries **no business
logic** — it calls the package's own CLI (`<pkg-cli> <cmd> --json`) or
core API and returns the same payload, so no face can ever drift from
what the CLI says. One logic, many faces.

Working example: the [`devin-doctor` VS Code extension](
https://github.com/Icaro0310/devin-explore/tree/main/packages/doctor/adapters/vscode)
— a ~150-line `extension.js` over `devin-doctor check --json`,
`report --md` and `plan`, with its own `node:test` suite and zero runtime
dependencies.

## The six faces

Each subdirectory here is a skeleton for one face. Copy it into the
canonical location inside a product package and replace the `<pkg>` /
`<pkg-cli>` / `<pkg_mod>` placeholders.

| Skeleton | Face | Canonical location in `packages/<pkg>/` |
|---|---|---|
| `skill/` | Devin skill (AI-driven) | `adapters/skills/<pkg>/SKILL.md` |
| `plugin/` | Devin plugin manifest (AI-driven) | `adapters/.devin-plugin/plugin.json` |
| `mcp/` | MCP server, stdio tools (AI-driven) | `src/<pkg_mod>/mcp_server.py` — inside `src/` so it ships in the wheel |
| `vscode_ext/` | VS Code extension | `adapters/vscode/` |
| `daemon/` | Long-running wrapper (watcher/scheduler) | `adapters/daemon/` — or `src/<pkg_mod>/` when it ships an entry point |
| `precommit/` | pre-commit hook | `adapters/precommit/` |

Canonical product layout (matches `devin-doctor` and `devin-janitor`):

```
packages/<pkg>/
├── src/<pkg_mod>/
│   └── mcp_server.py            # MCP face — ships in the wheel
├── adapters/                    # self-contained plugin root
│   ├── .devin-plugin/
│   │   └── plugin.json
│   ├── skills/<pkg>/
│   │   └── SKILL.md
│   ├── vscode/                  # package.json + extension.js + test/
│   ├── daemon/                  # optional
│   └── precommit/               # optional
└── tests/                       # package-level adapter tests
    ├── test_mcp.py
    └── test_skill.py
```

`adapters/` IS the plugin root — installable via
`devin plugins install Icaro0310/<repo>#packages/<pkg>/adapters`.
Keep it self-contained: no symlinks out of the directory (they break
git-subdir fetches and Windows checkouts).

## Hard rules

The enforceable contract lives in
[`docs/adapter-checklist.md`](../docs/adapter-checklist.md); every new
adapter must satisfy it. Summary:

1. **No mutation on AI-driven surfaces.** Skill, plugin and MCP faces
   expose only read/dry-run payloads — mutating commands stay in the
   human CLI and are never even named on an AI surface.
2. **One logic, many faces.** The adapter returns the same payload as
   `<pkg-cli> --json`. Reimplemented logic is a bug; CLI/adapter drift
   is a high-priority bug.
3. **≤200 lines** of adapter code per face, excluding tests. More means
   logic is leaking out of the core — refactor the core instead.
4. **Own test.** Every adapter ships a test that runs in isolation via
   [`.github/workflows/adapter-test.yml`](../.github/workflows/adapter-test.yml)
   — caller template in
   [`VARIANTS.md`](../.github/workflows/VARIANTS.md).
5. **No renames.** Package names, registry entry points and CLI flags
   stay exactly as they are.

## Registration

A face that adds a new console script (`<pkg>-mcp`, `<pkg>-daemon`) is
registered in the product entry's `entrypoints` array in
`registry.json`. Faces that ship no executable (skill, plugin manifest,
VS Code extension, pre-commit manifest) add no entry.
