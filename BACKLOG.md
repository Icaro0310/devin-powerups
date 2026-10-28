# Backlog

Parked work with priority and unblock conditions. The P5 window was
revoked early on 2026-10-28 (D-2026-10-28) — structure changes (merges,
new repos, taxonomy, renames) are allowed again when justified, pending
CI gates and a `registry.json` landing (see `GOVERNANCE.md`).

Tasks from the V4 report are tracked as GitHub issues in the owning
repo (all prefixed `[V4]`); this file is the index.

## Open

Unvalidated ideas and scout proposals live in `DIRECTIONS.md` —
this table is the executable queue.

| Item | Priority | Tracking |
|---|---|---|
| Antigravity MCP Store listing request — submit `poordjaevin`/`devin-memory` servers to the curated catalog via the `[MCP Store]` tag on discuss.ai.google.dev | optional | external — forum review; wave-9 doc |
| ~~Per-package README snippets for Antigravity `mcp_config.json` and Zed/JB `agent_servers`/`context_servers` configs~~ — **delivered 2026-10-13** across all `*-mcp` packages | done | folded into Wave 1 MCP "Add Your Own" sections |
| Adapter rollout PRs — review + merge the `feat/adapters-*` branches (8 repos): MCP+skill+plugin per package, read-only AI surfaces, `mcp` extras | high | explore#38+#39, assure#41+#42, state#37+#38, control#36, devkit#34, brain#37, judge#27, powerups#98 |
| Action satellites (narrow def per D-2026-10-10d): `devin-state-redact-action`, `devin-doctor-action`, `devin-evals-action` all live (`v1`, smoke green) — three distinct shapes proved; `devin-judge-action` deferred until a CI job produces agent artifacts | high | done except judge (deferred — no producer) |
| Dependency-coupled CI trigger — `devin-evals` pins `devin-redact>=0.2.0,<0.3.0`, and a redact change in devin-state can break the pin/corpus invisibly: the `evals-action` consumer filter only sees `packages/evals/**` inside its own repo, so a redact-side PR never triggers it (a `packages/redact/**` filter inside devin-assure fires never — filters see only that repo's checkout). Mechanism with precedence: **`repository_dispatch` from devin-state's publish workflow on redact releases is the normal path; a nightly `corpus verify` in devin-assure is the safety net** for when the dispatch fails or doesn't exist | medium | not filed; flagged 2026-10-10 |
| Programmatic dismiss of out-of-diff review findings — Devin Review findings on lines outside the PR diff cannot be dismissed or re-checked via API, so resolving them needs manual UI action or admin merge. Fix lands when the review bot gains a dismiss/re-check path for out-of-diff comments. Admin-merge count is ~12 as of 2026-10-11 and rising, split across two distinct failure modes: (a) out-of-diff findings the review cannot clear — the sanctioned-clearance-path class whose D-record lands with the pending audit PR (#105) — and (b) in-diff findings fixed but never bot-resolved because no re-review posted on the new head, first recorded here. If (b) grows faster, the fix is a re-review trigger, not only the dismiss API with each hardening PR — the workaround is stable-with-guardrail, so the expiry clause is now the urgent half: if Devin ships dismiss soon this dies quickly; if it takes months, admin merge becomes an audited routine either way | medium | blocked upstream (Devin Review capability) |
| Admin-merge reversal condition — admin merge is currently the known path around un-dismissable out-of-diff findings. Remove/retire that path when Devin Review adds programmatic dismiss or re-check of out-of-diff findings; until then it stays a documented escape hatch, not a habit | medium | reversal: pending upstream capability |
| Publish checklist addition — before `pypi-publish.yml` dispatch, sanity-check the self-reported version (`python -m build` → install wheel → `pkg.__version__`/`--version` matches the bump). The 0.3.0→0.3.1 evals release exists only because `__init__.py`'s constant drifted — detectable locally before publish | low | not filed; process note |
| `devkit_install` widening — spec permits a real install via MCP; kept dry-run. Revisit under review if a real need appears | low | D-2026-10-10e |
| `devin-brain` uv.lock policy — the repo never tracked a lockfile; `uv sync` leaves a ~large untracked diff. Either commit it (reproducible `--all-extras` installs, consistent with explore/assure/state/devkit which track theirs) or add `uv.lock` to `.gitignore`. Decide per-repo, or promote to an ecosystem-wide lockfile policy D-record | low | not filed; flagged in adapter rollout report |
| P6 product-boundary probes → 2026-12-03 audit (F3 backup+janitor / F1 explore / F2 assure; signals preregistered in `docs/product-boundaries.md`) | high | docs + D-record (#49, #50) |
| Findings-clearance mechanism (two classes) — Devin Review leaves blocking threads unresolved under two distinct failure modes. Class (a) out-of-diff: flagged code lives outside the PR diff (reusable-workflow code referenced via `uses: @tag`), so caller PRs carry stale blocking threads that the gate correctly never clears. Class (b) in-diff-stale: flagged code WAS in the diff and got fixed, but no re-review posted on the new head, so the thread is never bot-resolved — (b) is a re-trigger gap, not a scope limit, and its fix may be a re-review trigger mechanism rather than a dismiss path (D-2026-10-10, fourth datapoint). Options: (a) gate-side dismiss list — maintainer-signed allowlist file mapping finding ID → refuting commit, honored by `pr-approve`; (b) Devin-side re-check/dismiss of findings anchored to external refs; (c) resolve-only-if-devin remains, and the interim path stays the proof-comment + admin merge per D-2026-10-10. Without this, every PR touching code flagged by a previous PR's findings inherits unkillable threads. **Expiry clause, not aspiration:** two disjoint delivery paths for the real fix — (a) Devin Review gains programmatic dismiss/re-check of stale anchors (both classes), or (b) the gate-side signed dismiss list ships in `pr-approve` — and a single closure criterion: the proof-comment + admin workaround is struck from D-2026-10-10's sanctioned list once *either* path exists, and this item closes only when the workaround is gone (not when a delivery path shipped). After that date any admin merge under this record is an error, not a precedent. | high | first occurrence: auto-approve rollout tail (7 PRs, 2026-10-10); D-2026-10-10 |
| Devkit gate rewiring — the parallel-path sweep was the remedy; this item tracks the cure. In `devin-devkit/packages/devkit/src/devin_devkit/updater.py` the `_environment_block`/`_prereq_block` mirrors were deleted; `build_update_plan` calls `evaluate_target`/`evaluate_requirements` from `installer.py`, mapping canonical gate names to the update action vocabulary (`environment-blocked` / `unsupported` / `blocked`) via the existing gate tables. Ordering follows `evaluate_target`: environment first, platform last — env is *policy* ("not permitted here"), platform is *capability* ("cannot run on this OS"); the strongest violation surfaces first, fail-closed. Spec caveat resolved by reading the merged code, not by existence: the updater keeps an early `spec` check before the version-compare, so the evaluator's `spec` gate is unreachable on the update path — no double report; the residual divergence is ordering only (update surfaces missing-spec before missing-manager, install the reverse — defensible as manifest-defect vs environment-state, flagged for the parity test if it pins message order). The proving test asserts a tool invalid on both dimensions (forbidden env AND unsupported platform) reports the env gate — order, not mere presence. Deferred: `evaluate_*` extraction to `gates.py`/`plan.py` is named debt — decision recorded in the 2026-10-10 updater-gate audit record (landing with its own PR), postponed to keep the gate PR reviewable. | high | rewiring + parity matrix landed in devin-devkit PR #36; **closes on merge** (extraction deferred per the audit record) |
| Meta-issue for PyPI publication backlog | optional | not created; registry `distribution_status` is the tracker |
| Align generated-guide install format (tarball URL) with the `git+https` banner format | low | not filed; flagged in P2.x |
| `tools/surface_diff.py` — compare rendered surfaces (site HTML, profile README, awesome-devin) against registry semantics; fail on archived-repo links, product cards for non-products, stale rename names. Closes the QA boundary found by the 2026-10-09 drift audits (3 drift classes all missed by `--check` gates). | medium | not filed; suggested in surface audit |
| Evidence-equivalence hypothesis A — synthetic MCP probe exercising non-shell event categories (`file`, `git`, `browser`, `secret`) to confirm whether `chain[]` covers file ops live (~1h + minimal ACU; could move MCP from 9/12 to 10-11/12 mandatory fields). Investigation only — no adapters, no production code. | optional | not filed; `docs/evidence-equivalence.md` §7 |
| Evidence-equivalence hypothesis B — field-by-field verification of the `devin --export` ATIF stream (tokens + model per step); if confirmed, `devin-metrics` gains a second evidence source for users without `sessions.db` access (~2h). Investigation only — no production code. | optional | not filed; `docs/evidence-equivalence.md` §7 |
| ~~Generate `llms.txt` / `llms-full.txt` from the registry~~ — **done P6** (`tools/render_llms.py`, `LLMS:BEGIN/END` markers on the site files, drift step in `registry-drift.yml`; package-level llms.txt stay curated) | medium | closed #84 |
| ~~Prove OIDC publishing~~ — **done 2026-10-09**. PyPI validates `job_workflow_ref` as `<repo>/.github/workflows/<file>@<ref>` where `<repo>` is the TP repository and `<ref>` is `refs/heads/main` or the repo's default-branch tip SHA — a central reusable workflow in devin-powerups cannot match a per-repo TP, so each product repo now carries its own `pypi-publish.yml` (inline job, `environment: pypi`) instead of `uses:`-calling the shared one. 15 active TPs repointed per-repo + 3 pending (`devin-switch`, `devin-skill-catalog`, `devin-devkit`). Proof: `devin-assure` published qa-pack/evals/metrics green with `PYPI_API_TOKEN` deleted (runs 37962301785, 37962412497, 37962416604); devin-control/devin-devkit also passed the OIDC exchange (uploads hit only the 429). Decision: token stays deleted in devin-assure; other repos keep it as `password:` fallback (empty → OIDC). | medium | closed |
| Retry PyPI publishes blocked by HTTP 429 (account-level "too many new projects" rate limit): only `devin-devkit` and `devin-skill-catalog` first uploads remain — `devin-switch` v0.1.0 published 2026-10-09T18:00Z and got an active TP (`devin-control/pypi-publish.yml`, env `pypi-switch`). Pending publishers are per-package environments (`pypi-devkit`, `pypi-skill-catalog`) because PyPI requires a unique (repo+workflow+env) tuple per pending publisher; the publish workflows derive env from the package. Last retry 2026-10-09T19:29Z still 429; retry ≥ 2026-10-10T19:30Z via `pypi-publish.yml`; on success, `refresh_devkit_refs.py` flips `source_only`→`published`. | medium | workflow_dispatch; transient external limit |
| ~~Meta-check for wheel-gate coverage~~ — **closed 2026-10-11** (powerups#123 merged): the reusable secrets-scan guard now fails when any `pypi-publish.yml` omits the `verify-wheel-version` call — it rides the required scan in every repo, so a new package is born gated. `v1` re-pointed to `ad22e8c` so `@v1` callers inherit it | high | powerups#123 merged |
| Publish-guard exception policy — the merged-into-main guard aborts **before** upload but **after** the verify/download legs (cheap abort; scheduler leg rebuilds first — mild waste, still safe). Named policy: **no bypass**. A hotfix goes through a normal main PR first — a main merge is cheap, while a documented `--allow-non-main` flag would be a permanent supply-chain hole someone eventually uses for convenience, not emergency. If a real scenario ever forces a branch publish, revisit this item; do not add a flag preemptively. | medium | named 2026-10-11; guard shipped in 7 publish workflows |
| ~~`--environment` gate coverage (D-2026-10-10d, scope widened)~~ — **closed 2026-10-11**: (a) `update`/`outdated` carry the gate via #36 (merged), (b) fail-closed on all three paths (+ `DEVIN_DEVKIT_OFFLINE`), (c) parity tests landed — update/outdated tests came with #36, install CLI parity tests via #44 (merged). The predicted 7th gate is done — found by running the doc, not by reviewing the diff. | high | #36 + #44 merged |
| ~~Zscaler cert-path reword + guide regen~~ — **delivered 2026-10-11** (powerups#121 + all satellites merged): generator reworded to cert-store export routes (`certmgr.msc` / `Cert:` drive / IT-provided PEM); all 20 generated guides + the powerups guide + the manual devkit guide regenerated/fixed in one wave — **all satellites merged**: explore#54, assure#56, control#52, state#56, devkit#43, brain#51, internals-spec#36, judge#37, qwenpaw-suite#5; generator↔checked-in guide sync via powerups#125. Same wave shipped the doctor-guide "VS Code extension" section (D-2026-10-11c) | medium | #121 + satellites merged 2026-10-12; sync gate via #125 |
| ~~devin-devkit corporate guide under the generator~~ — **delivered 2026-10-11** (owner decision: extras target, not `devkit.tools`). The DevKit is the installer — a `distribution` registry entry that shares the corporate-docs universe; it was the only surface a rename could break without `--check` catching it. `plan_migration` accepts `distribution` kind + targets devin-devkit; per-name branches render install-the-installer (env-parameterized), paths, prereqs, troubleshooting; `_NETWORK_RUNTIME`/`_CORP_SCOPE_NOTE`/`_PLATFORM_EXTRAS` carry the real contract. powerups#122 (stacked on #121) + devin-devkit#43 | medium | PRs open, merges pending |
| ~~`ATTIC.md` in stale archived-repo checkouts~~ — **delivered 2026-10-11 as a single central marker**: `devin-ecosystem/ATTIC.md` (operator workspace root, sibling of the repo checkouts — host-local by design) maps all 10 stale absorbed checkouts → monorepo `package.path` (verified against `registry.json`), marks `devin-dashboard`/`awesome-devin` as live, and records the name-resolution rule + deferred deletion. Chosen over per-clone files: one marker covers the class, the dirs are a deletion candidate anyway. Optional follow-on: drop a one-line pointer inside each stale clone | low | central marker landed; per-clone pointers optional |
| ~~Re-point `v1` floating tag at the secrets-scan OIDC-guard merge~~ — **done 2026-10-11**: #120 merged, `v1` moved `61bf0b6 → 5956ee6` (OIDC-guard + uses-guard fix); callers pinning `secrets-scan.yml@v1` now inherit the publish-auth guard | high | closed |
| PyPI Trusted-Publisher cleanup — **owner action on PyPI**: (1) delete the stale pending publishers under account → Publishing; (2) add active TPs: `devin-devkit` (env `pypi-devkit`), `devin-skill-catalog` (env `pypi-skill-catalog`), `devin-internals-spec` (env `pypi`, new inline workflow internals-spec#35 — its `uses:` caller could never satisfy TP and only ever published via token); (3) agent re-dispatches the publishes and confirms OIDC green — this tests that the primary path works alone, not that the fallback is gone. Per D-2026-10-11b Addendum 3 the account token is a **deliberate fallback — no revocation, no rotation**; the `PYPI_API_TOKEN` repo secrets were deleted because the workflows carry no `password:` code path, not because the token is a surface to eliminate | high | external — owner PyPI settings; policy corrected 2026-10-11 |
| Post-rename TP repoints (Fase 4, #69) — **verified done in practice 2026-10-22**: every publishing repo has a post-rename green `Upload to PyPI` (the OIDC exchange runs before upload, so a stale TP cannot pass silently). Full project→repo→env matrix + evidence in `docs/publish-checklist.md` §PyPI. Workflow side audited consistent (all `pypi-publish.yml` are OIDC-only, `id-token: write`, env resolved per package). Remaining human step: glance at account → Publishing for stale *pending* publishers, then close #69 | high | verified via publish runs; issue #69 |
| ~~`devin-doctor check --json` latency on populated data dirs~~ — **closed 2026-10-12** (devin-explore#57 merged): the disk check now does a single-pass `os.scandir` DFS bounded at 250k files / 45 s with `>=` lower-bound semantics. A capped scan can prove WARN but never PASS (the unread remainder may hold the bulk); acp-messages keeps exact fresh stats outside the shared walk so live growth cannot hide a breach. 6 new tests, 109 passed | medium | found by the extension live smoke 2026-10-11; devin-explore |
| ~~Open VSX namespace ownership (`icaro0310`)~~ — **resolved 2026-10-13**: `EclipseFdn/open-vsx.org#14088` granted (state: completed); `verified: true` confirmed on the extension API and the unverified-publisher banner is gone. All six extensions live (doctor 0.1.1, search 0.1.1, qa-pack 0.1.1, devkit 0.1.0, memory 0.1.0, bridge 0.1.0), CI leg active via `OVSX_PAT` forwarded in `release.yml` | done | resolved — channel closed |
| ~~Post-archive hygiene: inert `packages/*/.github/` trees~~ — **done 2026-10-13**: nested trees deleted in state (backup+janitor), assure (metrics+evals), explore (history+pm+graph+search), devkit (skill-catalog), control (office+switch+orchestrator). The archived standalone repos keep the real copies | done | chosen option: delete — frozen snapshots were getting SHA-bumped by mistake |
| ~~Marketplace publishing identity: PAT vs Entra/managed identity~~ — **resolved 2026-10-12 as the pre-registered decision predicted**: Entra workload identity shipped — app `devin-vscode-marketplace` (no Azure subscription, no PAT), per-repo federated credentials (`environment:release`) on the five extension repos, SP Contributor on publisher `icaro0310`, `release.yml` publishes via `azure/login` + `vsce publish --azure-credential --skip-duplicate`. Proof: `icaro0310.devin-doctor v0.1.0` published from CI. Zero PAT surface, zero freeze-window migration | medium | powerups#130 + #131 |
| ~~`devin-memory` MCP promotion tools exposed on the AI surface~~ — **closed 2026-10-12** (devin-brain#53 merged): `release`/`approve` only register when the server launches with `DEVIN_MEMORY_MCP_PROMOTE=1`; `extract`'s `auto_approve` is masked off without the opt-in (an AI client cannot bypass the review lane through it either). Promotion stays human-only via `quarantine --release`/`approve` CLI. CI now installs `mcp` so the gate tests run | medium | filed 2026-10-11; devin-brain |
| Item | Class | Verified |
|---|---|---|
| ~~E2E runner installs `devin-internals-spec` editable in target venvs~~ | fix | shipped: venv-per-repo (`~/.venvs/<repo>`, auto-created), editable installs of declared+discovered `devin_*` deps, `deps_missing` now fails the run — sweep: 12 → 0 |
| ~~XDG_DATA_HOME → XDG_CONFIG_HOME harmonization (pm)~~ — **resolved 2026-10-13, already satisfied**: `devin_internals.paths` IS the shared store-paths module (extracted under D-2026-10-08 to converge 11+ vendored `paths.py`); it documents DATA root ≠ CONFIG root on Linux by design and `pm`'s reads are correct on both sides (`projects.py` reads the Devin CLI `sessions.db` under DATA_HOME, `vscdb.py` reads VS Code state under CONFIG_HOME). The debt was documented, not real | debt | evidence: `devin-internals-spec/src/devin_internals/paths.py` |
| ~~Dedupe the 14 `learned-*` skills (teste-hook vs testes overlap)~~ — **shipped 2026-10-13**: `personal-agent-system/scripts/learned_dedupe.py` dedupes lessons **across** `learned-*` skills (the `--cleanup` path only dedupes within one skill). Dry-run + `--apply`, backup before write, deterministic canonical owner. First apply: 1 cross-skill dup removed (deploy→geral), 5 empty learned-* reported (kept, report-only) | debt | `learned_dedupe.py` |
| `deps-internals` repo-venv check (doctor) | fix | detects the same `deps_missing` class pre-suite — cheaper now that the runner bootstraps (#31): doctor can probe `~/.venvs/<repo>` + declared deps without installing |
| Align devin-office with the E2E runner contract (`missing_dir`) | fix | reported broken weekly |
| ~~Recreate `scheduled_tasks` on Linux (systemd/cron)~~ — **shipped 2026-10-13**: `collectPasInventory` in `weekly-ecosystem-scout.mjs` enumerated Windows `schtasks` only → empty on Linux. Now also collects crontab entries + user systemd units; real inventory: 11 tasks (5 cron + 6 systemd user units) | debt | scout `scheduled_tasks` |
| ~~Incremental export cursor~~ — **shipped 2026-10-13**: `devin_internals.cursor` (internals-spec v0.3.1, PyPI) + `devin-history export --since/--incremental` (explore#62) + `devin-learning extract --since/--incremental` (brain#57). Pattern spec: `docs/incrementality.md` | portar | shared helper replaces 3 local cursor impls |
| `index --since` incremental reindex hook for SessionEnd | portar | `devin-search.py --incremental` with mtime state; note: `devin-search index`/`devin-graph build` already incremental internally (rowid/ledger) — hook wiring is the gap |
| `metrics digest --weekly` | estender | rollup/watch manifests exist but produce no digest report — the digest output itself is new |
| `learning.weekly-extract` public report | portar | `learning-weekly-extract.yaml` manifest exists |
| Shared `graph.db` with `devin-codegraph.py` (code↔session edges) | portar | `devin-codegraph.py` writes nodes/edges to `.devin/graph/graph.db` |
| Seed catalog registry with the 14 PAS `learned-*` as `proposed` | portar | inventory exists; exercises quarantine→approve on day one |
| learned-* → catalog bundle export path | estender | inventory exists; the export path itself is new |
| Memory→catalog bridge: learning-loop writes enter `proposed` lane automatically | spec | ongoing handoff — the observation-lane spec in DIRECTIONS covers the shape |
| Scheduled `audit` handler recipe for public repos | portar | 3 audit manifests run via trigger manifest |
| `janitor report` (space-report subcommand) | portar | `janitor-space-report.yaml` runs daily read-only |
| `redact hook --install` — export-gate recipe + hook registration | portar | `redact_gate` exists in `session_learning.py` + `devin-history-export.py` |
| `--to ssh://host/path` remote snapshot offload with re-verify | portar | `vm-offload-run.py` does Tailscale offload daily; `copy-to` (local) shipped |
| Trigger manifests (`*.yaml`) as plan DAG input | portar | `session-dispatcher.py` — real sequential DAG: "EVENT → normalizer (envelope) → DAG" |
| qwenpaw healthcheck as heartbeat item | estender | site-sync monitors it; not wired to heartbeat |
| `verify --all` degraded-vs-corrupted exit distinction (0 ok / 2 degraded / 3 corrupted) | estender | README documents verify→1 and rotate→2, but nothing distinguishes degraded from corrupted — the distinction itself is new |
| ~~GHCR image publishing~~ — **done 2026-10-10**: all four images live and public (`ghcr.io/icaro0310/devin-redact`, `devin-qa-pack`, `devin-evals`, `devin-judge`), repo-linked; `poordjaevin 0.1.2` published (gate included) after #27+#29 merged. Devin Review earned its keep on this PR set: wrong-checkout-sha, unpublished-sibling, tag-branch false-skip, tag-name shell injection — all fixed pre-merge. `devin-office` image (spec: optional) remains deferred | medium | closed |
| Reusable workflow tag propagation — `python-test.yml` env-pass fix shipped as `v1.2` and floating `v1` moved to it (2026-10-10), so `@v1` callers pick it up automatically; callers pinned to older minors (`@v1.1`) still need repinning. Same pattern applies to every `devin-powerups` reusable fix going forward | medium | v1 callers covered; explicit minor pins open |
| `pypi-publish` dispatch accepts non-default branches — devin-redact 0.2.1 and devin-evals 0.3.0/0.3.1 were published from unmerged `feat/adapters-*` branches, leaving main's pyproject behind the index (fixed by sync PRs devin-state#42, devin-assure#47). Candidate hardening: restrict `workflow_dispatch` publishes to `refs/heads/main`, or gate on "head is merged" | medium | not filed; flagged 2026-10-11 |
| Spec-order divergence pin (devin-devkit#36) — review comment on the update-environment-gate PR flags a case the parity matrix must carry; the window is while the PR lives. If it merges without the case in `test_gate_parity.py`, this becomes a named gap, not a closed item | medium | watch: verify at merge |
| GHCR version-tag exists-check — `docker-publish.yml` in devin-state / devin-assure / devin-judge repushes `:<version>` without checking the tag already exists; release-driven triggers make a repush rare, but a manual dispatch on an old ref would overwrite the pin silently. Add a manifest-exists check that fails or skips before build | low | not filed; flagged by review 2026-10-11 |

## Previously gated by the P5 window — unblocked 2026-10-28

The freeze was revoked early (D-2026-10-28). Physical merges, new or
deleted repositories, registry taxonomy changes and renames are allowed
when justified; each still needs its own review, CI green and a
`registry.json` landing. The 2026-12-03 baseline cut stays marked — do
not splice pre/post series in future adoption reports.

Deferred P4 items from the 2026-10-25 scout triage
(`personal-agent-system/reports/scout-2026-10-25-triage.md`) that were
held *because of* the freeze are released: `new-repo.py --github`,
`repo-seo-audit.py` port, and the five new-project INTEGRATE ideas
(recall→brain, gateway→judge, radar→scout/dashboard, voice→skill-catalog,
fleet→orchestrator). Items deferred for design reasons (specs, safety
contracts, owner evidence) keep their original blockers.

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
- devin-devkit#36 Windows path/env-gate fixes — merged 2026-10-11
  (`PureWindowsPath`/`PurePosixPath` seams for explicit `os_name`,
  env-override honoring the explicit flavor, merge of main's regenerated
  guides). Unblocked the corporate guide and the 7th gate in one merge.
- devin-devkit#44 install `--environment` CLI parity tests — merged
  2026-10-11.
- Janitor `devin-judge` backend + tier-3 tombstones — devin-state#57;
  Rule-1 dry-run test written first, `PoordjaevinJudge` translates
  `poordjaevin ask` typed answers (delete requires confidence ≥ 0.6,
  abstained/malformed → keep), Windows argv convention for binary specs,
  GUI-state tombstones instead of physical delete, snapshot/24h/running
  gates intact. 119 tests. Merges when review clears.
- `devin-switch` export/import — devin-control#55; JSON archive
  (`devin-switch/profile-archive` v1, base64+sha256 per file), export
  never reads credentials, import is dry-run + `--apply`, staging-dir +
  rename, path-traversal fail-closed. 89 tests.
- Orchestrator `metrics.json` per run + `plan --cost-estimate` —
  devin-control#53.
- `.pre-commit-hooks.yaml` wave — devin-assure#57 (qa-pack audit gate),
  devin-devkit#45 (skill-catalog lint gate), devin-explore#56 (doctor
  check gate), devin-control#54 (switch doctor gate). devin-brain got no
  hook by design: every `devin-memory` subcommand opens `memory.db` in cwd
  — a mutation, not a gate.
- `devin-memory compact` + `quarantine --digest` — devin-brain#52;
  dedup via retract-not-delete (survivor keeps union of tags), digest is
  content-keyed so the same quarantine set fingerprints identically across
  machines. 189 tests.
- PAS E2E runner topology — `weekly-ecosystem-scout.mjs` fix confirmed on
  HEAD; live run 21 pass / 3 legitimate `no_tests` / 0 fail. Stale-map
  fixes also landed in daily-maintenance, g3-overnight and the redact
  fallback paths (PAS local commit `4b1b19d`).
- G3 judge wiring — `g3-overnight.mjs` now drains `~/devin/g3-runs/*.json`
  through `devin-skill-catalog promote/quarantine --g3-report` in dry-run
  mode only; `--apply` stays a human action (Rule 1).
