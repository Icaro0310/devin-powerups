# Backlog

Parked work with priority and unblock conditions. The P5 window
(→ 2026-12-03) is a measurement period, not a freeze — items below are
unblocked unless they touch measured structure (merges, new repos,
taxonomy, renames — see `GOVERNANCE.md`).

## Open

| Item | Priority | Notes |
|---|---|---|
| D07 — grader for content inside `tool_call_update_json` (injected instructions in tool output are invisible today) | high | `devin-evals` corpus known gap; `corpus verify` documents it |
| `devin-evals` PyPI publication | high | still `source_only`; `devin-qa-pack` demo pins it by git SHA — publish to drop the pin |
| D05 — privacy/PII grader (`no_secrets` covers secret shapes only) | medium | `devin-evals` corpus known gap |
| D09 — cross-call secret join (credentials split across outputs evade per-payload patterns) | medium | `devin-evals` corpus known gap |
| Discoverability/UX pass: profile README, site by job-to-be-done, GitHub topics, `awesome-devin` as intent map | medium | baseline measures the impact — do it inside the window |
| Fork visibility strategy — act on the upstream funnel metrics | low | `tools/fork_visibility.py` now measures open/merged/closed PRs weekly |
| Meta-issue for PyPI publication backlog | optional | deliberately not created; registry `distribution_status` is the tracker |
| Align generated-guide install format (tarball URL) with the `git+https` banner format | low | both are source-only installs; cosmetic divergence flagged in P2.x |

## Gated until the window ends (2026-12-03)

Anything that would invalidate the measured series: physical merges,
new or deleted repositories, registry taxonomy changes, renames, and
reinterpreting the baseline itself. These need evidence *and* the end
of the window, not just approval.

## Watchdogs (running)

| Watch | Cadence | If it fails |
|---|---|---|
| `fork-janitor` cron (04:45 daily) | daily | new PATH/`gh` failure → open issue |
| `registry-drift` workflow | per push | real drift → fix like the devin-metrics incident |
| `registry-refresh` (Mon 07:33 UTC) | weekly | `poordjaevin.version` stale → escalate to `refresh_devkit_refs.py` bug |
| `check_dist_status` | per push | a README banner disagrees with the registry |
| `baseline-snapshot` (Mon 08:15 UTC) | weekly | opens a GitHub issue automatically; missed windows are unrecoverable |

## Resolved

- `devin-dream → devin-evals` merge (P4) — done; repo archived.
- `devin-metrics` PyPI publication — done 2026-10-08; README banner removed.
- `devin-backup` PyPI publication — done; registry v20 flipped source to `pypi`.
- Workflow consolidation (P3b) — done; callers pin `@v1`.
- `poordjaevin.version` registry field — partially self-healed: PyPI has
  0.1.1; the watchdog may still report the registry field stale.
