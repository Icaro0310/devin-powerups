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
| Findings-clearance mechanism (two classes) — Devin Review leaves blocking threads unresolved under two distinct failure modes. Class (a) out-of-diff: flagged code lives outside the PR diff (reusable-workflow code referenced via `uses: @tag`), so caller PRs carry stale blocking threads that the gate correctly never clears. Class (b) in-diff-stale: flagged code WAS in the diff and got fixed, but no re-review posted on the new head, so the thread is never bot-resolved — (b) is a re-trigger gap, not a scope limit, and its fix may be a re-review trigger mechanism rather than a dismiss path (D-2026-10-10, fourth datapoint). Options: (a) gate-side dismiss list — maintainer-signed allowlist file mapping finding ID → refuting commit, honored by `pr-approve`; (b) Devin-side re-check/dismiss of findings anchored to external refs; (c) resolve-only-if-devin remains, and the interim path stays the proof-comment + admin merge per D-2026-10-10. Without this, every PR touching code flagged by a previous PR's findings inherits unkillable threads. **Expiry clause, not aspiration:** two disjoint delivery paths for the real fix — (a) Devin Review gains programmatic dismiss/re-check of stale anchors (both classes), or (b) the gate-side signed dismiss list ships in `pr-approve` — and a single closure criterion: the proof-comment + admin workaround is struck from D-2026-10-10's sanctioned list once *either* path exists, and this item closes only when the workaround is gone (not when a delivery path shipped). After that date any admin merge under this record is an error, not a precedent. | high | first occurrence: auto-approve rollout tail (7 PRs, 2026-10-10); D-2026-10-10 |
| Meta-issue for PyPI publication backlog | optional | not created; registry `distribution_status` is the tracker |
| Align generated-guide install format (tarball URL) with the `git+https` banner format | low | not filed; flagged in P2.x |
| `tools/surface_diff.py` — compare rendered surfaces (site HTML, profile README, awesome-devin) against registry semantics; fail on archived-repo links, product cards for non-products, stale rename names. Closes the QA boundary found by the 2026-10-09 drift audits (3 drift classes all missed by `--check` gates). | medium | not filed; suggested in surface audit |
| Evidence-equivalence hypothesis A — synthetic MCP probe exercising non-shell event categories (`file`, `git`, `browser`, `secret`) to confirm whether `chain[]` covers file ops live (~1h + minimal ACU; could move MCP from 9/12 to 10-11/12 mandatory fields). Investigation only — no adapters, no production code. | optional | not filed; `docs/evidence-equivalence.md` §7 |
| Evidence-equivalence hypothesis B — field-by-field verification of the `devin --export` ATIF stream (tokens + model per step); if confirmed, `devin-metrics` gains a second evidence source for users without `sessions.db` access (~2h). Investigation only — no production code. | optional | not filed; `docs/evidence-equivalence.md` §7 |
| ~~Generate `llms.txt` / `llms-full.txt` from the registry~~ — **done P6** (`tools/render_llms.py`, `LLMS:BEGIN/END` markers on the site files, drift step in `registry-drift.yml`; package-level llms.txt stay curated) | medium | closed #84 |
| ~~Prove OIDC publishing~~ — **done 2026-10-09**. PyPI validates `job_workflow_ref` as `<repo>/.github/workflows/<file>@<ref>` where `<repo>` is the TP repository and `<ref>` is `refs/heads/main` or the repo's default-branch tip SHA — a central reusable workflow in devin-powerups cannot match a per-repo TP, so each product repo now carries its own `pypi-publish.yml` (inline job, `environment: pypi`) instead of `uses:`-calling the shared one. 15 active TPs repointed per-repo + 3 pending (`devin-switch`, `devin-skill-catalog`, `devin-devkit`). Proof: `devin-assure` published qa-pack/evals/metrics green with `PYPI_API_TOKEN` deleted (runs 37962301785, 37962412497, 37962416604); devin-control/devin-devkit also passed the OIDC exchange (uploads hit only the 429). Decision: token stays deleted in devin-assure; other repos keep it as `password:` fallback (empty → OIDC). | medium | closed |
| Retry PyPI publishes blocked by HTTP 429 (account-level "too many new projects" rate limit): only `devin-devkit` and `devin-skill-catalog` first uploads remain — `devin-switch` v0.1.0 published 2026-10-09T18:00Z and got an active TP (`devin-control/pypi-publish.yml`, env `pypi-switch`). Pending publishers are per-package environments (`pypi-devkit`, `pypi-skill-catalog`) because PyPI requires a unique (repo+workflow+env) tuple per pending publisher; the publish workflows derive env from the package. Last retry 2026-10-09T19:29Z still 429; retry ≥ 2026-10-10T19:30Z via `pypi-publish.yml`; on success, `refresh_devkit_refs.py` flips `source_only`→`published`. | medium | workflow_dispatch; transient external limit |
| Meta-check for wheel-gate coverage — the reusable `verify-wheel-version` gate closes today's partial coverage, but nothing stops a new package's `pypi-publish.yml` from omitting the call. Add a meta-check (registry-drift workflow or repo-scan tool) that fails when any `pypi-publish.yml` in the ecosystem does not invoke the reusable — otherwise partial coverage is the steady state and each new package is born with the gap. | high | powerups#123 open — third banned shape added to the reusable secrets-scan guard (rides the required scan in every repo) |
| Publish-guard exception policy — the merged-into-main guard aborts **before** upload but **after** the verify/download legs (cheap abort; scheduler leg rebuilds first — mild waste, still safe). Named policy: **no bypass**. A hotfix goes through a normal main PR first — a main merge is cheap, while a documented `--allow-non-main` flag would be a permanent supply-chain hole someone eventually uses for convenience, not emergency. If a real scenario ever forces a branch publish, revisit this item; do not add a flag preemptively. | medium | named 2026-10-11; guard shipped in 7 publish workflows |
| ~~`--environment` gate coverage (D-2026-10-10d, scope widened)~~ — **closed 2026-10-11**: (a) `update`/`outdated` carry the gate via #36 (merged), (b) fail-closed on all three paths (+ `DEVIN_DEVKIT_OFFLINE`), (c) parity tests landed — update/outdated tests came with #36, install CLI parity tests via #44 (merged). The predicted 7th gate is done — found by running the doc, not by reviewing the diff. | high | #36 + #44 merged |
| ~~Zscaler cert-path reword + guide regen~~ — **delivered 2026-10-11** (powerups#121 merged; satellite PRs pending): generator reworded to cert-store export routes (`certmgr.msc` / `Cert:` drive / IT-provided PEM); all 20 generated guides + the powerups guide + the manual devkit guide regenerated/fixed in one wave — powerups#121 ✅ merged, explore#54, assure#56, control#52, state#56, devkit#43, brain#51, internals-spec#36, judge#37, qwenpaw#5 still open. Same wave shipped the doctor-guide "VS Code extension" section (D-2026-10-11c) | medium | #121 merged; satellite merges pending |
| ~~devin-devkit corporate guide under the generator~~ — **delivered 2026-10-11** (owner decision: extras target, not `devkit.tools`). The DevKit is the installer — a `distribution` registry entry that shares the corporate-docs universe; it was the only surface a rename could break without `--check` catching it. `plan_migration` accepts `distribution` kind + targets devin-devkit; per-name branches render install-the-installer (env-parameterized), paths, prereqs, troubleshooting; `_NETWORK_RUNTIME`/`_CORP_SCOPE_NOTE`/`_PLATFORM_EXTRAS` carry the real contract. powerups#122 (stacked on #121) + devin-devkit#43 | medium | PRs open, merges pending |
| ~~`ATTIC.md` in stale archived-repo checkouts~~ — **delivered 2026-10-11 as a single central marker**: `/home/ikaros/devin/devin-ecosystem/ATTIC.md` maps all 10 stale absorbed checkouts → monorepo `package.path` (verified against `registry.json`), marks `devin-dashboard`/`awesome-devin` as live, and records the name-resolution rule + deferred deletion. Chosen over per-clone files: one marker covers the class, the dirs are a deletion candidate anyway. Optional follow-on: drop a one-line pointer inside each stale clone | low | central marker landed; per-clone pointers optional |
| ~~Re-point `v1` floating tag at the secrets-scan OIDC-guard merge~~ — **done 2026-10-11**: #120 merged, `v1` moved `61bf0b6 → 5956ee6` (OIDC-guard + uses-guard fix); callers pinning `secrets-scan.yml@v1` now inherit the publish-auth guard | high | closed |
| PyPI Trusted-Publisher cleanup — **owner action on PyPI**: (1) delete the stale pending publishers under account → Publishing; (2) add active TPs: `devin-devkit` (env `pypi-devkit`), `devin-skill-catalog` (env `pypi-skill-catalog`), `devin-internals-spec` (env `pypi`, new inline workflow internals-spec#35 — its `uses:` caller could never satisfy TP and only ever published via token); (3) agent re-dispatches the publishes and confirms OIDC green — this tests that the primary path works alone, not that the fallback is gone. Per D-2026-10-11b Addendum 3 the account token is a **deliberate fallback — no revocation, no rotation**; the `PYPI_API_TOKEN` repo secrets were deleted because the workflows carry no `password:` code path, not because the token is a surface to eliminate | high | external — owner PyPI settings; policy corrected 2026-10-11 |
| `devin-doctor check --json` latency on populated data dirs — exceeds the VS Code extension's 120 s subprocess cap (disk-usage walk over `~/devin`), so a real-world check renders `doctor: unavailable`. Contract-valid on a small data dir; the opt-in live smoke (`DOCTOR_VSCODE_LIVE`) is what surfaced it. CLI-side perf item: bound the disk walk, cache it, or make it opt-in — do not paper over by raising the adapter timeout | medium | found by the extension live smoke 2026-10-11; devin-explore |
| Open VSX namespace ownership (`icaro0310`) — `verified: false` confirmed on `/api/icaro0310`. Publishing worked because creating a namespace grants **contributor** authority; the "not a verified publisher" warning is removed only by granting **owner** — open a namespace-claim issue in `EclipseFdn/open-vsx.org` (template; requires GitHub ID ≥1 year, namespace must be ours — it is). Once owner is granted the namespace flips to verified and the warning clears. Cosmetic today | low | EclipseFdn/open-vsx.org wiki "Managing Namespaces"; issue claim pending owner decision |
| Marketplace publishing identity: PAT vs Entra/managed identity — when the VS Code Marketplace publish workflow is built, prefer **direct Entra ID / managed identity** (Open VSX already live, no urgency for an interim PAT). PAT deprecation kills personal PATs **2026-12-01** — two days before the P5 freeze ends (2026-12-03); any PAT→managed-identity migration that touches governance files in that window is a **checkpoint 🔴**. A PAT now = a mandatory migration landing inside the freeze tail | medium | no Marketplace workflow exists yet; decision pre-registered so a future rush does not pick PAT by default |
| `devin-memory` MCP promotion tools exposed on the AI surface — the MCP server (`devin-brain/src/devin_memory/mcp_server.py`) ships ``release`` (quarantined→active) and ``approve`` (proposed→active) as tools, both documented as *human overrides*. An agent holding the MCP can self-promote quarantined/proposed content, routing around the anti-poisoning lane the server exists to enforce. Other write tools are defensible by design (``retain`` passes the screen gate; ``retract``/``quarantine`` only de-promote; ``compact`` is dry-run default; ``extract`` yields ``proposed``), so the class fix is narrow: drop or gate ``release``/``approve`` behind an env opt-in (e.g. ``DEVIN_MEMORY_MCP_PROMOTE=1``), keeping them in the CLI for humans. Found in the 2026-10-11 MCP audit; judge MCP is clean (pure computation, gate returns verdict without acting). | medium | filed 2026-10-11; devin-brain |
| Umbrella CLI per product — **not enunciable yet, needs a spec**. Each package already ships its own console script (devin-doctor/devin-history/devin-search/devin-graph/devin-pm; devin-backup/devin-janitor/devin-redact; devin-metrics/devin-evals/devin-qa-pack; devin-switch/devin-orchestrator/devin-bridge). What an umbrella would add (single entry dispatching to member CLIs, one install, grouped help) is a product decision: name (`devin`? per-product `devin-<product>`?), collision policy with the Devin CLI itself, and whether members become extras. Filed as a spec-needed item, same class as the brain→skill-catalog bridge — do not build without a consumption-point spec. | low | filed 2026-10-11 |
| MCP serving for devin-explore packages — **spec needed, molde exists**. No explore package ships an MCP server today (state: backup/janitor/redact; assure: qa-pack; brain: memory all do). Read-only query surfaces (search query, graph query, doctor check, history) are Rule-1-safe MCP candidates by nature; qa-pack's `adapters/mcp.py` is the reference mold. Spec needed per package: tool names, what a "query" returns to an AI surface, and whether `doctor check` (multi-minute) fits MCP timeouts. | medium | filed 2026-10-11 |

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
