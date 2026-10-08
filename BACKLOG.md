# Backlog

Parked work with priority and unblock conditions. During P5
(→ 2026-12-03) nothing here moves unless a governance trigger fires —
see `GOVERNANCE.md`.

## After P5

| Item | Priority | Blocked by | Context |
|---|---|---|---|
| D07 — grader for content inside `tool_call_update_json` (injected instructions in tool output are invisible today) | high | P5 | `devin-evals` corpus known gap; `corpus verify` documents it |
| `devin-evals` PyPI publication | high | P5 | still `source_only`; `devin-qa-pack` demo pins it by git SHA — publish to drop the pin |
| D05 — privacy/PII grader (`no_secrets` covers secret shapes only) | medium | P5 | `devin-evals` corpus known gap |
| D09 — cross-call secret join (credentials split across outputs evade per-payload patterns) | medium | P5 | `devin-evals` corpus known gap |
| Fork visibility strategy — act on the upstream funnel metrics | low | P5 data | `tools/fork_visibility.py` now measures open/merged/closed PRs weekly |
| Meta-issue for PyPI publication backlog | optional | — | deliberately not created; registry `distribution_status` is the tracker |
| Align generated-guide install format (tarball URL) with the `git+https` banner format | low | banner generator | both are source-only installs; cosmetic divergence flagged in P2.x |

## Watchdogs (running during P5)

| Watch | Cadence | If it fails |
|---|---|---|
| `fork-janitor` cron (04:45 daily) | daily | new PATH/`gh` failure → open issue |
| `registry-drift` workflow | per push | real drift → fix like the devin-metrics incident |
| `registry-refresh` (Mon 07:33 UTC) | weekly | `poordjaevin.version` stale → escalate to `refresh_devkit_refs.py` bug |
| `check_dist_status` | per push | a README banner disagrees with the registry |
| `baseline-snapshot` (Mon 08:15 UTC) | weekly | opens a GitHub issue automatically; missed windows are unrecoverable |

## Resolved during P0–P3b

- `devin-dream → devin-evals` merge (P4) — done; repo archived.
- `devin-metrics` PyPI publication — done 2026-10-08; README banner removed.
- Workflow consolidation (P3b) — done; callers pin `@v1`.
- `poordjaevin.version` registry field — partially self-healed: PyPI has
  0.1.1; the watchdog may still report the registry field stale.
