# Backlog

Parked work with priority and unblock conditions. The P5 window
(→ 2026-12-03) is a measurement period, not a freeze — items below are
unblocked unless they touch measured structure (merges, new repos,
taxonomy, renames — see `GOVERNANCE.md`).

Tasks from the V4 report are tracked as GitHub issues in the owning
repo (all prefixed `[V4]`); this file is the index.

## Open

Unvalidated ideas and scout proposals live in `DIRECTIONS.md` —
this table is the executable queue.

| Item | Priority | Tracking |
|---|---|---|
| Antigravity MCP Store listing request — submit `poordjaevin`/`devin-memory` servers to the curated catalog via the `[MCP Store]` tag on discuss.ai.google.dev | optional | external — forum review; wave-9 doc |
| Per-package README snippets for Antigravity `mcp_config.json` and Zed/JB `agent_servers` configs | low | fold into Wave 1 MCP "Add Your Own" sections |
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
| ~~`devin-doctor check --json` latency on populated data dirs~~ — **closed 2026-10-12** (devin-explore#57 merged): the disk check now does a single-pass `os.scandir` DFS bounded at 250k files / 45 s with `>=` lower-bound semantics. A capped scan can prove WARN but never PASS (the unread remainder may hold the bulk); acp-messages keeps exact fresh stats outside the shared walk so live growth cannot hide a breach. 6 new tests, 109 passed | medium | found by the extension live smoke 2026-10-11; devin-explore |
| Open VSX namespace ownership (`icaro0310`) — `verified: false` confirmed on `/api/icaro0310`. Publishing works because creating a namespace grants **contributor** authority — all six extensions live since 2026-10-12 and the `release.yml` leg ships them in CI (`OVSX_PAT` in repo secrets, forwarded via explicit `secrets:` mapping). The "not a verified publisher" warning is removed only by granting **owner** — claim filed as `EclipseFdn/open-vsx.org#14088`. Once granted the namespace flips to verified and the warning clears; no republish needed. Cosmetic today | low | claim filed; awaiting Eclipse review |
| ~~Marketplace publishing identity: PAT vs Entra/managed identity~~ — **resolved 2026-10-12 as the pre-registered decision predicted**: Entra workload identity shipped — app `devin-vscode-marketplace` (no Azure subscription, no PAT), per-repo federated credentials (`environment:release`) on the five extension repos, SP Contributor on publisher `icaro0310`, `release.yml` publishes via `azure/login` + `vsce publish --azure-credential --skip-duplicate`. Proof: `icaro0310.devin-doctor v0.1.0` published from CI. Zero PAT surface, zero freeze-window migration | medium | powerups#130 + #131 |
| ~~`devin-memory` MCP promotion tools exposed on the AI surface~~ — **closed 2026-10-12** (devin-brain#53 merged): `release`/`approve` only register when the server launches with `DEVIN_MEMORY_MCP_PROMOTE=1`; `extract`'s `auto_approve` is masked off without the opt-in (an AI client cannot bypass the review lane through it either). Promotion stays human-only via `quarantine --release`/`approve` CLI. CI now installs `mcp` so the gate tests run | medium | filed 2026-10-11; devin-brain |

## Port candidates (PAS-proven)

`[portar]`-class scout proposals (the machinery already runs inside the
PAS — porting is productization, not speculation) plus proposals of any
class whose pain is already felt and nameable. Normal backlog priority;
`[novo]` and unproven `[estender]` proposals live in `DIRECTIONS.md`.

| Item | Repo | Effort | Proposed | Note |
|---|---|---|---|---|
| E2E runner installs `devin-internals-spec` editable in target venvs (fixes the `deps_missing` class — 12 suites abort weekly) | powerups + PAS | M | 2026-10-07 | same fix named in both the powerups and PAS sections |
| `deps-internals` repo-venv check | doctor/explore | S | 2026-10-07 | detects the same `deps_missing` class before a suite runs |
| XDG_DATA_HOME → XDG_CONFIG_HOME harmonization | pm/explore | S | 2026-10-07 | documented debt in the linux-parity convention |
| Documented exit codes for `verify --all` (0 ok / 2 degraded / 3 corrupted) | backup/state | S | 2026-10-07 | daemon units landed; schedulers need the contract |
| Align devin-office with the E2E runner contract (`missing_dir`) | office | S | 2026-10-07 | reported as broken weekly |
| Dedupe the 14 `learned-*` skills (overlapping themes, e.g. teste-hook vs testes) | learning | S | 2026-10-07 | merge/consolidation job with version bump |
| `redact hook --install` — export-gate recipe (`session_end` + `sessionend-scan` commands exist; the install/hook-registration piece does not) | state | M | 2026-10-02 | PAS `redact_gate` in `session_learning.py` is the mold |
| Incremental export cursor (`--since-session` watermark; `--session-id`/`export-gui` already shipped) | history/explore | M | 2026-10-02, re-asked 10-07 | avoids rescanning the whole DB weekly |
| Scheduled `audit` handler recipe documented for public repos | doctor/explore | S | 2026-10-02 | PAS runs it via trigger manifest |
| `metrics digest --weekly` | metrics/assure | S | 2026-10-02 | PAS `metrics-rollup` handler is the mold |
| `--to ssh://host/path` remote snapshot offload with re-verify | backup/state | M | 2026-10-02, re-asked 10-07 | `copy-to` (local secondary) shipped; ssh dest + hash verify open — PAS does Tailscale vm-offload |
| `index --since` incremental reindex hook for SessionEnd | search/explore | S | 2026-10-02, re-asked 10-07 | query-side `--since` shipped; index-side incremental open — PAS `devin-search.py` is the mold |
| Shared `graph.db` with the PAS `devin-codegraph.py` (code↔session edges coexist) | graph/explore | M | 2026-10-02 | same-file alignment, both writers coexist |
| `janitor report` (space-report subcommand) | janitor/state | S | 2026-10-07 | PAS manifest runs it daily read-only |
| Trigger manifests (`*.yaml`) as plan DAG input | orchestrator/control | M | 2026-10-07 | `--spec-file` takes a JSON task spec; the PAS dispatcher envelope format is the mold |
| `pm digest` milestone digest | pm/explore | M | 2026-10-07 | PAS consolidates private reports already |
| qwenpaw healthcheck as heartbeat item | PAS/qwenpaw | S | 2026-10-07 | PAS scope — heartbeat suppression pattern exists |
| Seed catalog registry with PAS `learned-*` inventory as `proposed` entries | skill-catalog/devkit | S | 2026-10-07 | exercises quarantine→approve on day one |
| learned-* → catalog bundle export path | learning | M | 2026-10-07 | same write→gate→promote cycle as the memory bridge proposal |
| `learning.weekly-extract` public report | learning | S | 2026-10-07 | manifest already runs in the PAS |

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
