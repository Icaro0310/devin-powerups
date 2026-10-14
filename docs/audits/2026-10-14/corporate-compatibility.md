# Corporate compatibility audit — 2026-10-14

Scope: every `devin-*` tool, asked one question — what happens in a VS Code
environment **without the Devin CLI/Desktop installed** ("corporate")?

Method: read-only source inspection plus direct `grep` measurements in the
session that ran this audit. No test suite was executed; where behavior was
inferred rather than measured, the entry says so.

## 1. Repository map (live vs attic)

`devin-ecosystem/` mixes live product repos with absorbed checkouts
(`ATTIC.md` records the freeze). Live repos and what they absorbed:

| Live repo | Absorbed tools (packages/) |
|---|---|
| devin-explore | doctor, history, graph, pm, search |
| devin-assure | evals, metrics, qa-pack |
| devin-state | backup, janitor, redact |
| devin-control | bridge, orchestrator (= PyPI `devin-fanout`), switch, office |
| devin-devkit | devkit, skill-catalog |
| devin-brain | devin-memory (+ `devin_memory/learning` = devin-learning) |
| devin-powerups, devin-internals-spec, devin-dashboard, devin-judge | (standalone) |

Standalone checkouts (`devin-history`, `devin-evals`, `devin-backup`,
`devin-janitor`, `devin-metrics`, `devin-graph`, `devin-search`, `devin-pm`,
`devin-skill-catalog`, `devin-dream`) carry MOVED banners — frozen history,
not audited separately.

Not standalone: `devin-searxng` (systemd service over a searxng fork),
`devin-fanout`/`devin-office`/`devin-bridge`/`devin-learning` (all packages or
modules inside live repos).

## 2. Evidence grep

Pattern `sessions\.db|default_sessions_db|\.local/share/devin` over live
`src/` trees: **99 source files** hit. The concentration:

- `*/paths.py` + `default_sessions_db()` — every session reader resolves the
  same Devin data-dir candidate list, then the CLI exits 1/2 or the MCP tool
  returns a structured error when nothing is found.
- `devin-internals-spec` — the canonical parser/schema layer for
  `cli/sessions.db`; read-only, plus `make-fixture` synthetic stores.
- `devin-control/packages/office` — daemon/probe/sessmon all read sessions.db.
- `devin-brain/src/devin_memory` — core store is its own `memory.db`; only
  `verify`/`extract`/`learning` need `--sessions-db`.
- Zero hits: devkit, skill-catalog, agent-sessions, poordjaevin (its Devin
  coupling is the `devin acp` subprocess, not the db), searxng, qwenpaw-suite.

## 3. Classification

### CAT 1 — assumes Devin session data (returns empty/exit-error in corporate)

| Tool | VS Code ext? | Without Devin | Priority |
|---|---|---|---|
| devin-history | no | exit 2 "no sessions.db found" | high |
| devin-search | wrapper | `index`/`query` exit 2 | high |
| devin-graph | no | exit 2 | high |
| devin-pm | no | exit 2 — **except** `verify --pm-registry <export>` rehydrates from an export | high |
| devin-metrics | no | missing sessions.db → exit 1; **`churn` is git-only, works** | high |
| devin-evals | no | `run` requires `--sessions-db`; corpus/demo/`--dry-run` work; corpus sessions.db is committed | high |
| devin-learning (brain/learning) | no | `extract`/`weekly-report` require `--sessions-db`; `review` works on drafts | high |
| devin-qa-pack | wrapper | `audit` exit 2, `session-end` SKIPPED exit 0 — **but `--transcript` audits Aider/Claude Code transcripts natively** (works in corporate; the *extension* forbids the flag, CLI doesn't) | **highest** — already multi-agent at the CLI |
| devin-janitor | no | inventory silently skips missing db: `scan`/`report` return empty, `run` T1/T2 exit 1 | medium |

### CAT 2 — structurally dead in corporate (do not adapt)

| Tool | Why |
|---|---|
| devin-bridge | spawns `devin acp` + credentials.toml — no CLI, no bridge |
| devin-orchestrator (`devin-fanout`) | planner runs offline (pure JSON) but has no executor without Devin workers |
| devin-switch | manages Devin `config.json`/`mcp_config.json`/`User/` — runs on empty dirs, uselessly |
| devin-office | daemon/probe/executor all sit on sessions.db + `devin acp`; `hub.py` serves but empty |
| personal-agent-system | the maintainer's runtime harness, not a product |
| qwenpaw-suite | VM agent suite; registry already marks it corporate-unsupported |

### CAT 3 — works without Devin (verify during the corporate run)

| Tool | VS Code ext? | Corporate status (inspection) | Verify |
|---|---|---|---|
| agent-sessions | real (TS) | reads Copilot Chat / Copilot CLI / Codex CLI sessions — the corporate piece by design | install .vsix, open a session |
| devin-judge (poordjaevin) | real (TS, this session) | `ask`/`eval`/`gate` work via `nli` offline; `serve` default `acp` needs Devin → use `vscode-lm` or `nli` | `@judge` + endpoint round-trip |
| devin-memory (brain) | MCP def provider | retain/recall/prime/export on own `memory.db`; extract/verify/learning need `--sessions-db` | retain+recall |
| devin-skill-catalog | no | scans arbitrary `.devin/` dirs; registry under `~/.config/devin/` (creates itself) | scan a fixture dir |
| devin-redact | no | generic file/dir scans; session-end hook fails soft (CLEAN) without db | redact a fixture |
| devin-backup | no | works with explicit `--data-dir`; bare run errors cleanly | backup a fixture dir |
| devin-devkit | wrapper | `profiles`/`list`/dry-run offline; `install` needs network (proxy ok) | profiles list |
| devin-internals-spec | no | parser lib + `devin-inspect`; `health` reports MISSING, `make-fixture` generates synthetic stores | health + fixture |
| devin-dream | no | generates synthetic Devin fixtures (dev tool) | — |
| devin-dashboard (repo) | no | stdlib monitor of pm2/ollama/tailscale; `laptop_reporter` degrades without db | optional |
| devin-doctor | wrapper | reports FAIL "Is Devin installed?" — correct by design; `capabilities` exposes the corporate profile (fail-closed by default) | run once, record profile |
| searxng | n/a | upstream fork, zero coupling; works if self-hosted | — |

Existing test evidence (design, not execution): every live repo has a
`test_offline_core.py` or equivalent that fails on any network access;
synthetic `sessions.db` fixtures are committed for internals-spec, brain,
evals (corpus), qa-pack (Aider/Claude-Code transcripts), office. CI runs on
windows+ubuntu runners with no Devin — so "works without Devin installed" is
proven; "produces value without Devin data" is the open question the
corporate run answers.

## 4. Findings that change the preliminary classification

1. **devin-qa-pack is already multi-agent**: `--transcript` audits Aider
   `.aider.chat.history.md` and Claude Code `.jsonl`. The gap is that the
   VS Code wrapper *forbids* the flag (`adapters/vscode/extension.js`).
2. **devin-janitor fails silently-empty, not loudly** — a corporate user gets
   a clean zero, never a hint that Devin is the missing input.
3. **devin-doctor is the corporate detector**, not a victim: `capabilities`
   + `devin-profile.json` is the sanctioned way to ask "what can run here".
4. **devin-pm has an escape hatch**: `verify --pm-registry <export>` rebuilds
   the registry without sessions.db — an export shipped to corporate restores
   most of the value.
5. **devin-metrics churn is git-only** — useful in corporate today.
6. **orchestrator runs but is useless** — planning without executors.

## 5. Decision on CAT 1 — Option B (documented split)

Question asked first: *is CAT 1 actually used in corporate today?* Evidence
says no: the corporate run that would notice has not happened yet, and every
CAT 1 tool fails cleanly-but-empty rather than being missed. The multi-agent
bet is already placed elsewhere (agent-sessions reads Copilot/Copilot CLI/
Codex CLI sessions).

**Decision:** accept the split — the Python CLIs observe Devin sessions; the
VS Code extensions observe sessions from any agent. Porting
devin-internals-spec's canonical model to Copilot/Codex sources (Option A)
stays the correct long-term move *if* a concrete corporate need appears; the
bridge for history/search/graph-shaped value in corporate today is
agent-sessions, not nine more parsers.

Recorded in `devin-powerups/DECISIONS.md` as D-2026-10-14.

## 6. Corporate verification run (plan, not executed here)

Bundle for a clean corporate VS Code (no Devin CLI/Desktop):

1. `code --install-extension agent-sessions.vsix` and
   `devin-judge.vsix` (built `2026-10-14` from `adapters/vscode/`).
2. `pipx install "poordjaevin[local,mcp]"` (or the uv tool equivalent).
3. Verify per row of the CAT 3 table:
   - agent-sessions: tree view lists Copilot/Codex sessions; `@sessions` chat answers.
   - devin-judge: `@judge /judge <statement>` returns a calibrated answer on
     the active model (first call triggers the LM consent dialog — expected);
     then `POORDJAEVIN_BACKEND=vscode-lm poordjaevin ask --state <f> --questions <q>`
     must reach the endpoint (check `%LOCALAPPDATA%\poordjaevin\vscode-lm-endpoint.json` exists).
   - Also verify `POORDJAEVIN_BACKEND=nli poordjaevin gate --action "x"` works fully offline.
   - memory/devkit/skill-catalog/redact/backup/doctor: run their CAT-3 row.
4. For each CAT 1 tool, record the *actual* behavior (exit code + message),
   not this audit's prediction — the table above is inspection, the run is truth.
5. Update this file's tables with measured results; flip any row whose real
   behavior disagrees.

Non-goals: no Devin CLI, no VM, no Slack, no external integrations. If the
corporate proxy does TLS inspection, follow `devin-judge/README.corporate-windows.md`
(Zscaler section) for CA-bundle env vars before any `pip`/`npm` step.
