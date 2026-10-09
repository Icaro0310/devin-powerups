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
| P6 product-boundary probes → 2026-12-03 audit (F3 backup+janitor / F1 explore / F2 assure; signals preregistered in `docs/product-boundaries.md`) | high | docs + D-record (#49, #50) |
| Meta-issue for PyPI publication backlog | optional | not created; registry `distribution_status` is the tracker |
| Align generated-guide install format (tarball URL) with the `git+https` banner format | low | not filed; flagged in P2.x |
| ~~Generate `llms.txt` / `llms-full.txt` from the registry~~ — **done P6** (`tools/render_llms.py`, `LLMS:BEGIN/END` markers on the site files, drift step in `registry-drift.yml`; package-level llms.txt stay curated) | medium | closed #84 |
| Prove OIDC publishing: configure PyPI Trusted Publishers then run publish workflows with `PYPI_API_TOKEN` suspended; if green, remove the token permanently. Now 17 TPs: devin-memory→devin-brain, poordjaevin→devin-judge, devin-redact/devin-backup/devin-janitor/devin-install-scheduler→devin-state, devin-qa-pack/devin-evals/devin-metrics→devin-assure, devin-doctor/devin-history/devin-search/devin-graph/devin-pm→devin-explore, devin-fanout/devin-switch→devin-control, devin-skill-catalog→devin-devkit. Plus npm `@icaro0310/devin-bridge`→devin-control (token-based). Does not block Phase 5. | medium | manual PyPI action by the owner (~25 min); no API |
| Retry PyPI publishes blocked by HTTP 429 (account-level "too many new projects" rate limit, hit 2026-10-09): `devin-switch`→devin-control, `devin-skill-catalog`→devin-devkit, `devin-devkit` re-upload. Pipelines are green end-to-end (build+twine); only the upload is throttled. Last retries 2026-10-09T16:02Z still 429; re-dispatch `publish-*.yml` after the window clears (next attempt ≥ +24h); on success, `refresh_devkit_refs.py` flips `source_only`→`published` and swaps archive specs for PyPI pins. | medium | workflow_dispatch; transient external limit |

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

- D07 tool-output-content grader — devin-evals#18 (PR#23, shipped in v0.2.0).
- D05 PII grader — devin-evals#19 (PR#23).
- D09 cross-call secret join — devin-evals#20 (PR#23).
- `devin-evals` PyPI publication — devin-evals#21; v0.2.0 live.
- internals-spec pin drift check — #25 → PR#38.
- Snapshot structural-change ledger — #21 → PR#36.
- Stale site claims — Icaro0310.github.io#11 → PR#13.
- `awesome-devin` catalog → intent map — awesome-devin#9 (journeys in #47/#48).
- Registry-driven generated surfaces — #18 → PR#34.
- Per-repo DEVIN ecosystem README blocks — #19 → PR#35 + sweep.
- Profile README by tracks — Icaro0310#5 → merged.
- Site intent-first discovery — Icaro0310.github.io#12 → PR#14.
- December analysis tooling (funnel + attribution) — #22 → PR#39.
- GitHub topics per repo — #20; applied to 25 repos.
- Registry semantics docs — #23 → PR#37.
- Audit reconciliation (27 vs 28; devin-learning registry-only) — #24.
- Shared infra evaluation → internals-spec — #26 → PR#42.
- backup+janitor snapshot contract — #27 → devin-backup#14 + devin-janitor#15.
- pm+metrics boundary D-record — #28 → PR#40.
- .gitleaksignore fixtures hygiene — #29 → PR#43 + devin-redact#16.
- `poordjaevin.version` watchdog — #30 → PR#44.
- Fork visibility strategy — #32 → PR#41.
- Governance lifecycle rules + decision records — `GOVERNANCE.md` lifecycle section + `DECISIONS.md` (Icaro0310/devin-powerups#17).
- `devin-dream → devin-evals` merge (P4) — done; repo archived.
- `devin-metrics` PyPI publication — done 2026-10-08; README banner removed.
- `devin-backup` PyPI publication — done; registry v20 flipped source to `pypi`.
- Workflow consolidation (P3b) — done; callers pin `@v1`.
- `poordjaevin.version` registry field — partially self-healed: PyPI has
  0.1.1; the watchdog may still report the registry field stale.
