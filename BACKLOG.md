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
| Out-of-diff findings clearance mechanism — Devin Review does not re-resolve findings whose flagged code lives outside the PR diff (reusable-workflow code referenced via `uses: @tag`), so caller PRs carry stale blocking threads that the gate correctly never clears. Options: (a) gate-side dismiss list — maintainer-signed allowlist file mapping finding ID → refuting commit, honored by `pr-approve`; (b) Devin-side re-check/dismiss of findings anchored to external refs; (c) resolve-only-if-devin remains, and the interim path stays the proof-comment + admin merge per D-2026-10-10. Without this, every PR touching code flagged by a previous PR's findings inherits unkillable threads. | high | first occurrence: auto-approve rollout tail (7 PRs, 2026-10-10); D-2026-10-10 |
| Meta-issue for PyPI publication backlog | optional | not created; registry `distribution_status` is the tracker |
| Align generated-guide install format (tarball URL) with the `git+https` banner format | low | not filed; flagged in P2.x |
| `tools/surface_diff.py` — compare rendered surfaces (site HTML, profile README, awesome-devin) against registry semantics; fail on archived-repo links, product cards for non-products, stale rename names. Closes the QA boundary found by the 2026-10-09 drift audits (3 drift classes all missed by `--check` gates). | medium | not filed; suggested in surface audit |
| Evidence-equivalence hypothesis A — synthetic MCP probe exercising non-shell event categories (`file`, `git`, `browser`, `secret`) to confirm whether `chain[]` covers file ops live (~1h + minimal ACU; could move MCP from 9/12 to 10-11/12 mandatory fields). Investigation only — no adapters, no production code. | optional | not filed; `docs/evidence-equivalence.md` §7 |
| Evidence-equivalence hypothesis B — field-by-field verification of the `devin --export` ATIF stream (tokens + model per step); if confirmed, `devin-metrics` gains a second evidence source for users without `sessions.db` access (~2h). Investigation only — no production code. | optional | not filed; `docs/evidence-equivalence.md` §7 |
| ~~Generate `llms.txt` / `llms-full.txt` from the registry~~ — **done P6** (`tools/render_llms.py`, `LLMS:BEGIN/END` markers on the site files, drift step in `registry-drift.yml`; package-level llms.txt stay curated) | medium | closed #84 |
| ~~Prove OIDC publishing~~ — **done 2026-10-09**. PyPI validates `job_workflow_ref` as `<repo>/.github/workflows/<file>@<ref>` where `<repo>` is the TP repository and `<ref>` is `refs/heads/main` or the repo's default-branch tip SHA — a central reusable workflow in devin-powerups cannot match a per-repo TP, so each product repo now carries its own `pypi-publish.yml` (inline job, `environment: pypi`) instead of `uses:`-calling the shared one. 15 active TPs repointed per-repo + 3 pending (`devin-switch`, `devin-skill-catalog`, `devin-devkit`). Proof: `devin-assure` published qa-pack/evals/metrics green with `PYPI_API_TOKEN` deleted (runs 37962301785, 37962412497, 37962416604); devin-control/devin-devkit also passed the OIDC exchange (uploads hit only the 429). Decision: token stays deleted in devin-assure; other repos keep it as `password:` fallback (empty → OIDC). | medium | closed |
| Retry PyPI publishes blocked by HTTP 429 (account-level "too many new projects" rate limit): only `devin-devkit` and `devin-skill-catalog` first uploads remain — `devin-switch` v0.1.0 published 2026-10-09T18:00Z and got an active TP (`devin-control/pypi-publish.yml`, env `pypi-switch`). Pending publishers are per-package environments (`pypi-devkit`, `pypi-skill-catalog`) because PyPI requires a unique (repo+workflow+env) tuple per pending publisher; the publish workflows derive env from the package. Last retry 2026-10-09T19:29Z still 429; retry ≥ 2026-10-10T19:30Z via `pypi-publish.yml`; on success, `refresh_devkit_refs.py` flips `source_only`→`published`. | medium | workflow_dispatch; transient external limit |

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
