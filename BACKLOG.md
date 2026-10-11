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
| Programmatic dismiss of out-of-diff review findings — Devin Review findings on lines outside the PR diff cannot be dismissed or re-checked via API, so resolving them needs manual UI action or admin merge. Fix lands when the review bot gains a dismiss/re-check path for out-of-diff comments. Admin-merge count is ~11 as of 2026-10-10 and rising with each hardening PR — the workaround is stable-with-guardrail, so the expiry clause is now the urgent half: if Devin ships dismiss soon this dies quickly; if it takes months, admin merge becomes an audited routine either way | medium | blocked upstream (Devin Review capability) |
| Admin-merge reversal condition — admin merge is currently the known path around un-dismissable out-of-diff findings. Remove/retire that path when Devin Review adds programmatic dismiss or re-check of out-of-diff findings; until then it stays a documented escape hatch, not a habit | medium | reversal: pending upstream capability |
| Publish checklist addition — before `pypi-publish.yml` dispatch, sanity-check the self-reported version (`python -m build` → install wheel → `pkg.__version__`/`--version` matches the bump). The 0.3.0→0.3.1 evals release exists only because `__init__.py`'s constant drifted — detectable locally before publish | low | not filed; process note |
| `devkit_install` widening — spec permits a real install via MCP; kept dry-run. Revisit under review if a real need appears | low | D-2026-10-10e |
| `devin-brain` uv.lock policy — the repo never tracked a lockfile; `uv sync` leaves a ~large untracked diff. Either commit it (reproducible `--all-extras` installs, consistent with explore/assure/state/devkit which track theirs) or add `uv.lock` to `.gitignore`. Decide per-repo, or promote to an ecosystem-wide lockfile policy D-record | low | not filed; flagged in adapter rollout report |
| P6 product-boundary probes → 2026-12-03 audit (F3 backup+janitor / F1 explore / F2 assure; signals preregistered in `docs/product-boundaries.md`) | high | docs + D-record (#49, #50) |
| Out-of-diff findings clearance mechanism — Devin Review does not re-resolve findings whose flagged code lives outside the PR diff (reusable-workflow code referenced via `uses: @tag`), so caller PRs carry stale blocking threads that the gate correctly never clears. Options: (a) gate-side dismiss list — maintainer-signed allowlist file mapping finding ID → refuting commit, honored by `pr-approve`; (b) Devin-side re-check/dismiss of findings anchored to external refs; (c) resolve-only-if-devin remains, and the interim path stays the proof-comment + admin merge per D-2026-10-10. Without this, every PR touching code flagged by a previous PR's findings inherits unkillable threads. **Expiry clause, not aspiration:** two disjoint delivery paths for the real fix — (a) Devin Review gains programmatic dismiss/re-check of out-of-diff anchors, or (b) the gate-side signed dismiss list ships in `pr-approve` — and a single closure criterion: the proof-comment + admin workaround is struck from D-2026-10-10's sanctioned list once *either* path exists, and this item closes only when the workaround is gone (not when a delivery path shipped). After that date any admin merge under this record is an error, not a precedent. | high | first occurrence: auto-approve rollout tail (7 PRs, 2026-10-10); D-2026-10-10 |
| Devkit gate rewiring — the parallel-path sweep was the remedy; this item tracks the cure. In `devin-devkit/packages/devkit/src/devin_devkit/updater.py` the `_environment_block`/`_prereq_block` mirrors were deleted; `build_update_plan` calls `evaluate_target`/`evaluate_requirements` from `installer.py`, mapping canonical gate names to the update action vocabulary (`environment-blocked` / `unsupported` / `blocked`) via the existing gate tables. Ordering follows `evaluate_target`: environment first, platform last — env is *policy* ("not permitted here"), platform is *capability* ("cannot run on this OS"); the strongest violation surfaces first, fail-closed. Spec caveat resolved by reading the merged code, not by existence: the updater keeps an early `spec` check before the version-compare, so the evaluator's `spec` gate is unreachable on the update path — no double report; the residual divergence is ordering only (update surfaces missing-spec before missing-manager, install the reverse — defensible as manifest-defect vs environment-state, flagged for the parity test if it pins message order). The proving test asserts a tool invalid on both dimensions (forbidden env AND unsupported platform) reports the env gate — order, not mere presence. Deferred: `evaluate_*` extraction to `gates.py`/`plan.py` is named debt — decision recorded in the 2026-10-10 updater-gate audit record (landing with its own PR), postponed to keep the gate PR reviewable. | high | rewiring + parity matrix landed in devin-devkit PR #36; **closes on merge** (extraction deferred per the audit record) |
| Meta-issue for PyPI publication backlog | optional | not created; registry `distribution_status` is the tracker |
| Align generated-guide install format (tarball URL) with the `git+https` banner format | low | not filed; flagged in P2.x |
| `tools/surface_diff.py` — compare rendered surfaces (site HTML, profile README, awesome-devin) against registry semantics; fail on archived-repo links, product cards for non-products, stale rename names. Closes the QA boundary found by the 2026-10-09 drift audits (3 drift classes all missed by `--check` gates). | medium | not filed; suggested in surface audit |
| Evidence-equivalence hypothesis A — synthetic MCP probe exercising non-shell event categories (`file`, `git`, `browser`, `secret`) to confirm whether `chain[]` covers file ops live (~1h + minimal ACU; could move MCP from 9/12 to 10-11/12 mandatory fields). Investigation only — no adapters, no production code. | optional | not filed; `docs/evidence-equivalence.md` §7 |
| Evidence-equivalence hypothesis B — field-by-field verification of the `devin --export` ATIF stream (tokens + model per step); if confirmed, `devin-metrics` gains a second evidence source for users without `sessions.db` access (~2h). Investigation only — no production code. | optional | not filed; `docs/evidence-equivalence.md` §7 |
| ~~Generate `llms.txt` / `llms-full.txt` from the registry~~ — **done P6** (`tools/render_llms.py`, `LLMS:BEGIN/END` markers on the site files, drift step in `registry-drift.yml`; package-level llms.txt stay curated) | medium | closed #84 |
| ~~Prove OIDC publishing~~ — **done 2026-10-09**. PyPI validates `job_workflow_ref` as `<repo>/.github/workflows/<file>@<ref>` where `<repo>` is the TP repository and `<ref>` is `refs/heads/main` or the repo's default-branch tip SHA — a central reusable workflow in devin-powerups cannot match a per-repo TP, so each product repo now carries its own `pypi-publish.yml` (inline job, `environment: pypi`) instead of `uses:`-calling the shared one. 15 active TPs repointed per-repo + 3 pending (`devin-switch`, `devin-skill-catalog`, `devin-devkit`). Proof: `devin-assure` published qa-pack/evals/metrics green with `PYPI_API_TOKEN` deleted (runs 37962301785, 37962412497, 37962416604); devin-control/devin-devkit also passed the OIDC exchange (uploads hit only the 429). Decision: token stays deleted in devin-assure; other repos keep it as `password:` fallback (empty → OIDC). | medium | closed |
| ~~Retry PyPI publishes blocked by HTTP 429~~ — **done 2026-10-10**: `devin-devkit` and `devin-skill-catalog` both published green via `pypi-publish.yml` dispatch (runs 38051997716, 38052000116). Remaining `refresh_devkit_refs.py` `source_only`→`published` flip is part of the adapter PR merge. | medium | closed |
| ~~GHCR image publishing~~ — **done 2026-10-10**: all four images live and public (`ghcr.io/icaro0310/devin-redact`, `devin-qa-pack`, `devin-evals`, `devin-judge`), repo-linked; `poordjaevin 0.1.2` published (gate included) after #27+#29 merged. Devin Review earned its keep on this PR set: wrong-checkout-sha, unpublished-sibling, tag-branch false-skip, tag-name shell injection — all fixed pre-merge. `devin-office` image (spec: optional) remains deferred | medium | closed |
| Reusable workflow tag propagation — `python-test.yml` env-pass fix shipped as `v1.2` and floating `v1` moved to it (2026-10-10), so `@v1` callers pick it up automatically; callers pinned to older minors (`@v1.1`) still need repinning. Same pattern applies to every `devin-powerups` reusable fix going forward | medium | v1 callers covered; explicit minor pins open |

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
