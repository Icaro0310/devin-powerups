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
| Adapter rollout PRs — review + merge the `feat/adapters-*` branches (8 repos): MCP+skill+plugin per package, read-only AI surfaces, `mcp` extras | high | explore#38+#39, assure#41+#42, state#37+#38, control#36, devkit#34, brain#37, judge#27, powerups#98 |
| Action satellites (narrow def per D-2026-10-10d): `devin-state-redact-action`, `devin-doctor-action`, `devin-evals-action` all live (`v1`, smoke green) — three distinct shapes proved; `devin-judge-action` deferred until a CI job produces agent artifacts | high | done except judge (deferred — no producer) |
| Dependency-coupled CI trigger — `devin-evals` pins `devin-redact>=0.2.0,<0.3.0`, and a redact change in devin-state can break the pin/corpus invisibly: the `evals-action` consumer filter only sees `packages/evals/**` inside its own repo, so a redact-side PR never triggers it (a `packages/redact/**` filter inside devin-assure fires never — filters see only that repo's checkout). Mechanism with precedence: **`repository_dispatch` from devin-state's publish workflow on redact releases is the normal path; a nightly `corpus verify` in devin-assure is the safety net** for when the dispatch fails or doesn't exist | medium | not filed; flagged 2026-10-10 |
| Programmatic dismiss of out-of-diff review findings — Devin Review findings on lines outside the PR diff cannot be dismissed or re-checked via API, so resolving them needs manual UI action or admin merge. Fix lands when the review bot gains a dismiss/re-check path for out-of-diff comments | medium | blocked upstream (Devin Review capability) |
| Admin-merge reversal condition — admin merge is currently the known path around un-dismissable out-of-diff findings. Remove/retire that path when Devin Review adds programmatic dismiss or re-check of out-of-diff findings; until then it stays a documented escape hatch, not a habit | medium | reversal: pending upstream capability |
| Publish checklist addition — before `pypi-publish.yml` dispatch, sanity-check the self-reported version (`python -m build` → install wheel → `pkg.__version__`/`--version` matches the bump). The 0.3.0→0.3.1 evals release exists only because `__init__.py`'s constant drifted — detectable locally before publish | low | not filed; process note |
| `devkit_install` widening — spec permits a real install via MCP; kept dry-run. Revisit under review if a real need appears | low | D-2026-10-10e |
| `devin-brain` uv.lock policy — the repo never tracked a lockfile; `uv sync` leaves a ~large untracked diff. Either commit it (reproducible `--all-extras` installs, consistent with explore/assure/state/devkit which track theirs) or add `uv.lock` to `.gitignore`. Decide per-repo, or promote to an ecosystem-wide lockfile policy D-record | low | not filed; flagged in adapter rollout report |
| P6 product-boundary probes → 2026-12-03 audit (F3 backup+janitor / F1 explore / F2 assure; signals preregistered in `docs/product-boundaries.md`) | high | docs + D-record (#49, #50) |
| Meta-issue for PyPI publication backlog | optional | not created; registry `distribution_status` is the tracker |
| Align generated-guide install format (tarball URL) with the `git+https` banner format | low | not filed; flagged in P2.x |
| `tools/surface_diff.py` — compare rendered surfaces (site HTML, profile README, awesome-devin) against registry semantics; fail on archived-repo links, product cards for non-products, stale rename names. Closes the QA boundary found by the 2026-10-09 drift audits (3 drift classes all missed by `--check` gates). | medium | not filed; suggested in surface audit |
| Evidence-equivalence hypothesis A — synthetic MCP probe exercising non-shell event categories (`file`, `git`, `browser`, `secret`) to confirm whether `chain[]` covers file ops live (~1h + minimal ACU; could move MCP from 9/12 to 10-11/12 mandatory fields). Investigation only — no adapters, no production code. | optional | not filed; `docs/evidence-equivalence.md` §7 |
| Evidence-equivalence hypothesis B — field-by-field verification of the `devin --export` ATIF stream (tokens + model per step); if confirmed, `devin-metrics` gains a second evidence source for users without `sessions.db` access (~2h). Investigation only — no production code. | optional | not filed; `docs/evidence-equivalence.md` §7 |
| ~~Generate `llms.txt` / `llms-full.txt` from the registry~~ — **done P6** (`tools/render_llms.py`, `LLMS:BEGIN/END` markers on the site files, drift step in `registry-drift.yml`; package-level llms.txt stay curated) | medium | closed #84 |
| ~~Prove OIDC publishing~~ — **done 2026-10-09**. PyPI validates `job_workflow_ref` as `<repo>/.github/workflows/<file>@<ref>` where `<repo>` is the TP repository and `<ref>` is `refs/heads/main` or the repo's default-branch tip SHA — a central reusable workflow in devin-powerups cannot match a per-repo TP, so each product repo now carries its own `pypi-publish.yml` (inline job, `environment: pypi`) instead of `uses:`-calling the shared one. 15 active TPs repointed per-repo + 3 pending (`devin-switch`, `devin-skill-catalog`, `devin-devkit`). Proof: `devin-assure` published qa-pack/evals/metrics green with `PYPI_API_TOKEN` deleted (runs 37962301785, 37962412497, 37962416604); devin-control/devin-devkit also passed the OIDC exchange (uploads hit only the 429). Decision: token stays deleted in devin-assure; other repos keep it as `password:` fallback (empty → OIDC). | medium | closed |
| ~~Retry PyPI publishes blocked by HTTP 429~~ — **done 2026-10-10**: `devin-devkit` and `devin-skill-catalog` both published green via `pypi-publish.yml` dispatch (runs 38051997716, 38052000116). Remaining `refresh_devkit_refs.py` `source_only`→`published` flip is part of the adapter PR merge. | medium | closed |

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
| GHCR image publishing — docker-publish.yml merged on 3 repos (state #40, assure #44, judge #29) but images only push after their next successful `publish` run or a manual dispatch; verify `ghcr.io/icaro0310/*` packages exist and inherit public visibility after first publish. `devin-office` image (spec: optional) not built — deferred. Judge: 0.1.2 must publish only AFTER PR #27 merges (gate subcommand lives there) | medium | not filed; flagged 2026-10-10 |
