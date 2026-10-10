# Adapter pattern — MCP server + Devin Skill + Devin Plugin

How a `devin-*` package exposes its read surface to AI clients. Reference
implementation: `devin-explore/packages/doctor` (all paths below relative
to a package dir). Verified green 2026-10-10: doctor (108 tests),
qa-pack (139), redact (113).

## Hard rules (fail the review if violated)

1. **Mutation never reaches an AI surface.** Packages with mutating
   commands (`redact --apply`, `janitor run --apply`, `backup restore`,
   `switch use --apply`, `skill-catalog promote/quarantine/activate`,
   `orchestrator record`, bridge spawn/kill, evals `judge`/`ab-run`)
   expose only the read/dry-run half via MCP, skill and plugin. The
   mutating command exists in CLI only, with human confirmation.
2. **One logic, many faces.** The adapter calls the package's core API
   and returns the same payload as `<cli> --json`. Never reimplement
   business logic in the adapter. CLI/MCP drift = high-priority bug.
3. **50–200 lines per adapter** plus its own tests. More means logic is
   leaking out of the core — refactor the core instead.
4. **No renames** — package names, PyPI/npm names, `console_scripts`,
   CLI flags stay exactly as they are.

## Layout

```
packages/<pkg>/
├── src/<pkg_mod>/mcp_server.py        # shipped in the wheel
├── adapters/                          # self-contained plugin root
│   ├── .devin-plugin/plugin.json
│   └── skills/<pkg>/SKILL.md
└── tests/
    ├── test_mcp.py
    └── test_skill.py
```

`adapters/` IS the plugin root — installable via
`devin plugins install Icaro0310/<repo>#packages/<pkg>/adapters`.
Self-contained (no symlinks out of the dir — they break `git-subdir`
fetches and Windows checkouts). The skill lives once, at
`adapters/skills/<pkg>/SKILL.md`.

The MCP server lives **inside `src/`** (not `adapters/`) so it ships in
the wheel — same convention as `poordjaevin.mcp_server` and
`devin_memory.mcp_server`.

## mcp_server.py template

```python
def do_<verb>(...) -> dict:
    """Pure logic — returns the `<cli> --json` payload as a dict.
    Unit-testable without the mcp package or a running server."""

def _err(error): return {"error": type(error).__name__, "detail": str(error)[:500]}

def _make_app(name):           # mcp 2.x MCPServer, fallback mcp 1.x FastMCP
def build_server():            # registers tools; each wraps do_* in try/except -> _err
def main():                    # build_server().run(transport="stdio")
```

- Optional path args use `""` defaults (MCP clients send empty strings
  more reliably than null) and resolve to `None` → platform default.
- Injectable seams (`now_ms`, `which=`, `runner=`) stay keyword-only and
  are NOT exposed as tool params.
- Side-effect params that only toggle a read behavior (`offline`,
  `dry_run`) may be exposed; anything that writes is not.
- Docstring on the tool says "Read-only" and what the JSON means.

## pyproject.toml additions

```toml
[project.optional-dependencies]
dev = ["pytest>=8"]
mcp = ["mcp>=1.2"]

[project.scripts]
<pkg-cli> = "<pkg_mod>.cli:main"          # unchanged
<pkg-cli>-mcp = "<pkg_mod>.mcp_server:main"
```

Regenerate `uv.lock` (`uv lock` or any `uv run` — commit the result).
Known caveat: `uvx --from '<pkg>[mcp]' <pkg>-mcp` resolves only after the
package's next PyPI release; until then the entry point exists in-repo.

## plugin.json template

```json
{
  "name": "<pkg>",
  "version": "<current version>",
  "description": "<one line, same as pyproject description>",
  "author": { "name": "Icaro0310" },
  "repository": "https://github.com/Icaro0310/<product-repo>",
  "license": "MIT",
  "keywords": ["devin", "<pkg-short>", "sessions.db"],
  "mcpServers": {
    "<pkg>": {
      "command": "uvx",
      "args": ["--from", "<pkg>[mcp]", "<pkg-cli>-mcp"]
    }
  }
}
```

Omit `mcpServers` entirely when the package has no MCP surface.

## SKILL.md template

```markdown
---
name: <pkg>
description: "<what it does + when to invoke + read-only claim, one line>"
triggers: [model, user]
allowed-tools: [exec, read]
---

# <pkg>

<when to run> → `<cli> <read-subcommand> --json` (or the MCP tool —
same payload). ## Reading the result (field guide). ## Rules:
read-only, error payload means "say so", never invent a verdict.
```

- English (product surface convention), dense, no filler.
- Never name mutating flags (`--apply`, `--restore`, `vacuum`,
  `--i-know-this-is-irreversible`, `promote`, `quarantine`) — not even to
  describe them. The skill test greps for them.

## Tests

`test_mcp.py`:
- `do_<verb>` output == `json.loads(<cli> --json)` on the package's
  synthetic fixtures (same `devin_internals.fixtures` conftest data the
  CLI tests use — never real user data).
- Failure paths the CLI maps to exit 2 → `{error, detail}` dicts.
- `pytest.importorskip("mcp")` guard around `build_server()` — CI
  installs `[dev]` only, not `[mcp]`.
- Assert `<pkg>-mcp` entry point + `mcp` extra exist in pyproject
  (tomllib).
- For restricted packages: assert the module source never references
  the mutating core function.

`test_skill.py`:
- SKILL.md exists; frontmatter `name`/`description` present.
- Body contains "read-only" and no banned mutation flags.
- plugin.json parses; `name` matches; `skills/<pkg>/SKILL.md` exists;
  `mcpServers` (if declared) points at `<pkg>-mcp`.

## Verification

```bash
cd <monorepo>
uv run pytest packages/<pkg> -x -q     # whole suite, not just new files
uv run ruff check packages/<pkg> --fix
```

## Git flow per repo

- Branch `feat/adapters-<pkgs>` from `origin/main`.
- Stage named files only — never `git add -A` / `git add .`.
- Commit: `feat(<pkg>): MCP server + Devin skill + plugin adapters`.
- PR per repo against main; CI is the reusable `python-test.yml@v1`
  (windows+ubuntu, py3.11, `pip install -e "packages/<pkg>[dev]"`).
