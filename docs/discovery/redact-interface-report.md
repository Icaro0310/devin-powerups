# `devin-redact` interface report

Status: assessed against local source — all findings `[LOCAL]` unless
marked otherwise.
Version assessed: `devin-redact` 0.2.2 (`devin-state` monorepo,
`packages/redact`; upstream repo `Icaro0310/devin-redact`). License: MIT,
owned by the same author as this project.

## Invocation surface

`devin-redact` offers three invocation modes `[LOCAL]`:

1. **Python library** — `devin_redact.engine` exposes exactly the
   operation the extension needs:
   - `redact_text(text) -> (new_text, edits)` — replaces every sensitive
     span with `<REDACTED:<sha256-fp16>>`; greedy leftmost-longest overlap
     resolution; idempotent (already-`<REDACTED:…>` spans are skipped);
     `env_assignment` matches keep the `KEY=` prefix.
   - `scan_text(text, *, file, location) -> list[Finding]` — findings
     with category, pattern name, line; never the matched secret (masked
     preview `abcd...wxyz` or `******`).
   - `scan(paths)` / `redact(paths, apply=…)` — file/dir orchestration;
     dispatch sniffs SQLite vs text vs binary.
2. **CLI** — console script `devin-redact` with subcommands `scan`
   (read-only, JSON report on stdout, `--format sarif` available),
   `redact` (in-place; dry-run by default; `--apply` requires
   `--i-know-this-is-irreversible`), `verify`, `gate`, `sessionend-scan`,
   `session-end`, `verify-publish`. Exit codes: `0` clean/ok, `1`
   non-CLEAN/BLOCKED, `2` error, `3` usage guard. A second entry point
   `devin-redact-mcp` serves MCP (optional dep).
3. **No stdin text mode.** Every subcommand takes file/dir paths. There
   is no `echo "…" | devin-redact` contract; arbitrary strings can only
   be processed via a file (or via the library API).

## Dependencies and runtime

- Runtime: Python ≥ 3.10. Core dependencies: **none**
  (`dependencies = []` in `pyproject.toml`). Optional extras: `dev`
  (pytest), `mcp` (mcp≥1.2).
- Detection logic that matters for excerpts is pure regex + span
  arithmetic: `patterns.py` (~117 LOC, 13 regexes over 8 categories) plus
  a false-positive guard (`_looks_like_code_assignment` suppresses
  `TOKEN_RE = …`-style code constants) and `redact_text` (~45 LOC). The
  remaining ~1 000 LOC of `engine.py` is the Devin-`sessions.db`
  semantic layer (`sensitive_tool_output` context classification of
  tool-call payloads) — valuable for Devin stores, not applicable to
  Copilot/Codex excerpts.
- Regex portability `[LOCAL]`: all patterns translate to JavaScript
  `RegExp` nearly 1:1. The one lookbehind (`(?<![\w/.-])` in
  `absolute_path`) is supported by the V8 in current VS Code (Node ≥ 18
  extension host) — safe.

## Effects

- `scan` never writes; `redact` writes in place only with explicit
  `--apply --i-know-this-is-irreversible`. Nothing in the package
  initiates network I/O (no imports beyond stdlib; verified by
  `pyproject.toml` empty deps and source inspection `[LOCAL]`).
- Reports never contain secret text: findings carry category, pattern
  name, line number, fingerprint — aligned with this project's
  safe-message rules.

## Fit against this project's constraints

| Constraint | Assessment |
|---|---|
| Zero Python on the normal path | A CLI subprocess would add Python to an *optional* leg only (content search). Acceptable if G1 approves the subprocess explicitly — but fragile on corporate machines without Python. |
| Subprocess policy | Default: none. A redactor CLI would need to be listed explicitly in the G3 evidence report. |
| Read-only over sources | `scan` is read-only. Excerpt redaction via CLI needs a temp file (the engine redacts in place; `redact_text` is not exposed on stdin). Temp files are scratch, not the forbidden "secondary archive" — still an extra moving part. |
| Fail-closed without redactor | Already the spec: no redactor → "unavailable". With a vendored port the redactor is always present, so content search is never degraded. |

## Recommendation (for G1)

**Vendor a TypeScript port of the redaction core** — `patterns.py` +
`_looks_like_code_assignment` + `redact_text` ≈ 200 LOC of TS, zero
dependencies, deterministic, testable. Per the ecosystem vendoring rule
(D-2026-10-09), the port ships with a **parity test**: fixtures generated
from the Python reference (a build-time step, not runtime) asserting
identical `<REDACTED:fp>` output for a fixed corpus. Coverage caveat, to
be stated in the port's docstring: the Devin-specific semantic layer
(`sensitive_tool_output`) is out of scope for MVP excerpts — the port
covers regex-detectable secrets/PII only.

Fallback if G1 prefers no porting: spawn `devin-redact scan` on a temp
excerpt file and apply masks in TS using returned spans — requires an
explicitly approved subprocess and a temp-file policy; degrades to
"unavailable" on machines without Python.
