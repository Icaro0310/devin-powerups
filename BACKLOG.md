# Backlog

Parked work with priority and unblock conditions. The P5 window
(→ 2026-12-03) is a measurement period, not a freeze — items below are
unblocked unless they touch measured structure (merges, new repos,
taxonomy, renames — see `GOVERNANCE.md`).

Tasks from the V4 report are tracked as GitHub issues in the owning
repo (all prefixed `[V4]`); this file is the index.

## Open

| Item | Priority | Tracking |
|---|---|---|
| D07 — grader for content inside `tool_call_update_json` (injected instructions in tool output are invisible today) | high |Icaro0310/devin-evals#18 |
| `devin-evals` PyPI publication | high |Icaro0310/devin-evals#21 |
| D05 — privacy/PII grader | high |Icaro0310/devin-evals#19 |
| internals-spec downstream bump automation | high |Icaro0310/devin-powerups#25 |
| Snapshot structural-change ledger (registry version/SHA, counts, deltas) | high |Icaro0310/devin-powerups#21 |
| Fix stale site claims (`19 first-party`, `Start here`, `read-only by default`, `live sessions/work`) | high |Icaro0310/Icaro0310.github.io#11 |
| `awesome-devin`: catalog → intent map | high |Icaro0310/awesome-devin#9 |
| D09 — cross-call secret join | medium |Icaro0310/devin-evals#20 |
| Registry-driven generated surfaces (catalog, counts, related links) | medium |Icaro0310/devin-powerups#18 |
| Per-repo README "Part of the DEVIN ecosystem" block | medium |Icaro0310/devin-powerups#19 |
| Profile README: position the ecosystem by tracks | medium |Icaro0310/Icaro0310#5 |
| Site intent-first discovery UX | medium |Icaro0310/Icaro0310.github.io#12 |
| December analysis tooling (funnel joins, CI-vs-human attribution) | medium |Icaro0310/devin-powerups#22 |
| GitHub topics per repo (`devin` + `devin-{track}`) | medium |Icaro0310/devin-powerups#20 |
| Registry semantics docs (mode→track heuristic, multi-axis model) | medium |Icaro0310/devin-powerups#23 |
| Audit reconciliation: 27 cloned vs 28 registry entries | medium |Icaro0310/devin-powerups#24 |
| Evaluate shared infra extraction (identity.py / paths.py / vscdb.py) | medium |Icaro0310/devin-powerups#26 |
| backup+janitor shared helper contracts (only if evidence justifies) | medium |Icaro0310/devin-powerups#27 |
| pm+metrics product boundary — measure whether users treat them as one job | medium |Icaro0310/devin-powerups#28 |
| .gitleaksignore fixtures hygiene | low |Icaro0310/devin-powerups#29 |
| `poordjaevin.version` watchdog | low | Icaro0310/devin-powerups#30 |
| Fork visibility strategy — act on the upstream funnel signal | low | Icaro0310/devin-powerups#32 |
| Meta-issue for PyPI publication backlog | optional | not created; registry `distribution_status` is the tracker |
| Align generated-guide install format (tarball URL) with the `git+https` banner format | low | not filed; flagged in P2.x |

## Gated until the window ends (2026-12-03)

Anything that would invalidate the measured series: physical merges,
new or deleted repositories, registry taxonomy changes, renames, and
reinterpreting the baseline itself. These stay gated until the window
ends on 2026-12-03 — or until a governance trigger ends it early, in
which case the triggering evidence is itself the review that decides
what unblocks.

## Watchdogs (running)

| Watch | Cadence | If it fails |
|---|---|---|
| `fork-janitor` cron (04:45 daily) | daily | new PATH/`gh` failure → open issue |
| `registry-drift` workflow | per push | real drift → fix like the devin-metrics incident |
| `registry-refresh` (Mon 07:33 UTC) | weekly | `poordjaevin.version` stale → escalate (Icaro0310/devin-powerups#30) |
| `check_dist_status` | per push | a README banner disagrees with the registry |
| `baseline-snapshot` (Mon 08:15 UTC) | weekly | opens a GitHub issue automatically; missed windows are unrecoverable |

## Resolved

- Governance lifecycle rules + decision records — `GOVERNANCE.md` lifecycle section + `DECISIONS.md` (Icaro0310/devin-powerups#17).
- `devin-dream → devin-evals` merge (P4) — done; repo archived.
- `devin-metrics` PyPI publication — done 2026-10-08; README banner removed.
- `devin-backup` PyPI publication — done; registry v20 flipped source to `pypi`.
- Workflow consolidation (P3b) — done; callers pin `@v1`.
- `poordjaevin.version` registry field — partially self-healed: PyPI has
  0.1.1; the watchdog may still report the registry field stale.
