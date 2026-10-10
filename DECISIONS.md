# Decision records

Structural decisions about the ecosystem, newest first. Format per
`GOVERNANCE.md`: Decision / Date / Reason / Evidence / Expected outcome /
Result. Records are not eternal — revisit when new evidence arrives.

## D-2026-10-09 — F4.5: devin-devkit absorbs devin-skill-catalog

- **Decision:** `devin-devkit` became a uv workspace with
  `packages/{devkit,skill-catalog}`; the `devin-skill-catalog` repo was
  archived with a MOVED banner. Package names and CLIs unchanged.
- **Reason:** both are the Build track — installer plus the skill/rule
  lifecycle gates it distributes. Rubric verdict: merge.
- **Evidence:** 37 + 68 tests green post-merge; per-path CI
  (`test-{devkit,skill-catalog}.yml`) and per-tag publish
  (`<pkg>-v*`). `manifest-sync.yml` and `updater.py`'s
  `REMOTE_MANIFEST_URL` repointed to `packages/devkit/...`. Registry:
  2 entries `product_id: devin-devkit`, `local_dir` + `package.path`.
  Rollback rehearsed: 3 reverts (subtree merge with `-m 1`) → zero diff.
- **Expected outcome:** one Build surface; the DevKit manifest carries
  skill-catalog's install spec (SHA-pinned archive, valid because the
  subtree merge preserved the original commits).
- **Result:** merged (`devin-devkit` PR #22). PyPI publish blocked by
  external 429 rate limit — `devin-skill-catalog` stays `source_only`
  until PyPI clears it (backlog).

## D-2026-10-09 — F4.4: devin-control absorbs bridge + orchestrator + switch + office

- **Decision:** the existing `devin-bridge` repo was **renamed** to
  `devin-control` and became the polyglot monorepo holder
  (`packages/{bridge,orchestrator,switch,office}`), preserving its
  history and stars. The npm package stays `@icaro0310/devin-bridge`
  (name independent of repo); orchestrator keeps PyPI `devin-fanout`;
  office remains `source_only` (`mode: mixed`).
- **Reason:** bridge is the flagship with the most history/stars;
  renaming beats creating a fresh repo and losing both. npm Trusted
  Publishing is token-based (`NPM_TOKEN`), not OIDC, so the rename
  needed no npm-side change. `PYPI_API_TOKEN` had to be re-created as a
  repo secret post-rename (it was not inherited).
- **Evidence:** test matrix green (Node 22/24 for bridge; Python
  packages 29+70+43 tests); `test-{bridge,orchestrator,switch,office}.yml`
  per path; `publish-{orchestrator,switch}.yml` PyPI +
  `publish-bridge-npm.yml` npm (`npm pack --dry-run` verified; publish
  on tag). Rollback rehearsed → zero diff vs base. Registry: 4 entries
  `product_id: devin-control`.
- **Expected outcome:** one Control product; `devin-office` lands in
  `track: guard` (correcting the earlier observe classification), which
  removes the pending `pm`-style exemption pressure.
- **Result:** merged. `devin-fanout` published fine; `devin-switch`
  hit PyPI 429 ("too many new projects") — stays `source_only`, retry
  is backlog.

## D-2026-10-09 — F4.3: devin-explore absorbs history + search + graph + pm

- **Decision:** `devin-explore` (ex `devin-doctor`) became a uv
  workspace with `packages/{doctor,history,search,graph,pm}`; the four
  source repos were archived with MOVED banners. `devin-pm` moved
  `track: related` → `track: observe`. `devin-office` was **excluded**
  (it is control, not observation) and went to `devin-control` in F4.4.
- **Reason:** Understand-family absorption per the P6 rubric. `pm` and
  `metrics` share **no code** (verified: `vscdb.py` vs `collect.py` are
  distinct implementations; the common layer is `devin-internals-spec`)
  — the D-record "merge" was conceptual, so no shared library was
  extracted.
- **Evidence:** 404 tests green (doctor 100, history 72, search 52,
  graph 75, pm 105); 5 test + 5 publish workflows; all 5 publish
  dispatches green on main. Rollback rehearsed: 6 reverts newest-first
  (`-m 1` on 4 subtree merges) → zero diff. Registry: 5 entries
  `product_id: devin-explore`, pm re-tracked.
- **Expected outcome:** Understand is one installable surface with five
  preserved CLIs; `pm` belongs semantically under observe.
- **Result:** merged (`devin-explore` PR #25, merge `74831fb`).

## D-2026-10-09 — Consolidation of the ecosystem into 7 products

- **Decision:** consolidate the 19 first-party tools into 7 products
  (monorepo workspaces with independent packages), grouped under 4
  public jobs. Renames preserve stars via GitHub redirects; PyPI/npm
  package names and `console_scripts` are preserved unchanged.
- **Reason:** the P6 rubric (5 preregistered signals) was applied to
  every candidate family instead of waiting for the December window —
  the maintainer's earlier correction stands: structural work needs a
  criterion, not a calendar. Verdicts below.
- **Evidence:** rubric scores on job / audience / blast radius /
  single-identity plausibility / technical harm (thresholds: ≥4/5
  merge, 3/5 hold for data, ≤2/5 keep), plus the maintainer's
  post-rubric corrections listed in §3.

### Rubric verdicts (signal count out of 5)

| Family | Job | Audience | Blast radius | Identity | No harm | Score | Verdict |
|---|---|---|---|---|---|---|---|
| redact + backup + janitor → state | ✓ | ✓ | ✓ | ✓ | ✓ | 5/5 | MERGE |
| qa-pack + evals → assure | ✓ | ✓ | ✓ | ✓ | ✓ | 5/5 | MERGE |
| doctor + history + search + graph → explore | ✓ | ~ | ✓ | ✓ | ✓ | 4/5 | MERGE |
| bridge + orchestrator + switch + office → control | ✓ | ~ | ✓ | ✓ | ~ | 4/5 | MERGE |
| skill-catalog → devkit | ✗ | ✗ | ~ | ✗ | ✓ | 2/5 | maintainer override → devkit (supply chain = Build) |
| memory → brain (standalone) | — | — | — | — | — | n/a | rename, no merge candidate |
| poordjaevin → judge (standalone) | — | — | — | — | — | n/a | rename; vs assure = 3/5, watch |
| office → explore | ✓ | ✓ | ✗ | ✓ | ~ | 3/5 | redirected to control (mode: mixed) |
| pm → explore | ~ | ~ | ✓ | ~ | ✓ | 3/5 | maintainer reclassified to understand |
| metrics → assure | ~ | ~ | ✓ | ~ | ✓ | 3/5 | maintainer mapped "Measure" → Verify |

### Post-rubric corrections (maintainer)

- `devin-office` is `mode: mixed` (spawn/kill/kanban endpoints) — illegal
  under `understand ⇒ read`; lands in `devin-control` (job: control),
  where mixed is legal.
- `devin-pm` (P0's `related`) reclassified to understand/explore.
- `devin-metrics` "Measure" maps to Verify → `devin-assure`.
- `devin-skill-catalog` "supply chain" maps to Build → `devin-devkit`
  (overrides the 2/5 KEEP score — recorded as maintainer override).
- bridge + orchestrator + switch do **not** go to `devin-powerups`
  (rubric 1.5/5: different audience, highest blast radius in the
  ecosystem); they form `devin-control` with `devin-office`.

### Superseded standing decisions

The 7-product consolidation supersedes these earlier negative calls —
recorded here because records are not eternal:

- `graph + history + search` — was "rejected" (distinct jobs) → now
  merging under one Understand product; the rubric found shared job and
  blast radius (all read-only over `sessions.db`).
- `backup + janitor` — was "contracts first" → merging; the tested
  snapshot→cleanup contract plus duplicated `install.py` (~141 LOC)
  are the technical signal.
- `pm + metrics` — was "measure" → resolved without merging them to
  each other: pm → explore, metrics → assure.
- `bridge + orchestrator` — was "rejected" (different layers) → both
  land in `devin-control` as independent packages of one product;
  the layers stay separate at package level.

### Removals

- `homebrew-tap`, `scoop-bucket`: repos deleted 2026-10-08 — orphaned
  artifacts, manual 2/14 package coverage, false "release automation"
  claim, zero external demand. Install story stays pipx/uv +
  `devin-devkit`.

### Externals

- `awesome-devin` (navigation surface) and `qwenpaw-suite` (optional
  self-hosted add-on): outside the first-party product count.

### Final architecture

7 products: `devin-explore`, `devin-assure`, `devin-judge`,
`devin-control`, `devin-state`, `devin-devkit`, `devin-brain`.
1 Foundation: `devin-internals-spec`. 1 Infra/control-plane:
`devin-powerups` (not renamed — protects ~70 `@v1` workflow callers).
2 Externals: `awesome-devin`, `qwenpaw-suite`.

### Product cap

Maximum 7 first-party products. An 8th requires merging or removing
one, recorded as a D-record.

- **Expected outcome:** one product identity per job cluster; all
  package names, CLIs, stars and redirects preserved; the baseline
  series continues per repo via the old→new alias map.
- **Result:** pending — recorded as phases complete (F0 tap cleanup:
  done; F2 registry v21: schema + entries carry ownership/job/
  product_id/package/entrypoints/legacy, validator enforces the
  product rules fail-closed).

## D-2026-10-08 — Product Boundary Reassessment (P6): measure families before merging

- **Decision:** reopen consolidation evaluation at the product-family
  level (`docs/product-boundaries.md`), with preregistered signals per
  candidate and a devkit `explore` profile as a co-install probe. No
  physical merge during the P5 window; no `family` field in the registry
  until the audit decides.
- **Reason:** discovery is now solved (journeys expose the semantic
  model), so the remaining question is which repo boundaries are real
  product boundaries. The four-level model TRACK → FAMILY → REPOSITORY →
  CAPABILITY keeps navigation and packaging decoupled.
- **Evidence:** verified technical facts in the doc — vendored
  `paths.py`/`vscdb.py`/`identity.py` across history/search/graph (being
  absorbed by the shared-infra D-record, so not merge evidence), real
  janitor→backup contract coupling, and `graph`/`janitor` still
  `source_only` (family decision precedes their publication).
- **Expected outcome:** at the 2026-12-03 audit each family (explore /
  assure / data, plus devkit+skill-catalog and doctor+switch probes) is
  either confirmed as a boundary or proposed as a merge with the signal
  table filled.
- **Result:** open — measuring.

## D-2026-10-08 — `devin-pm` vs `devin-metrics`: measure the boundary (V4 §16)

- **Decision:** keep the repos separate during the window and define in
  advance which signals decide the boundary question — not "wait 8
  weeks then maybe merge".
- **Reason:** the two tools answer different questions today (pm: "what
  is the state of my projects" — rollups, milestones, status reports;
  metrics: "what did sessions do" — activity, context size, token
  peaks), but only observed usage can show whether users treat them as
  one job.
- **Evidence:** signals that argue there is NO boundary (product
  overlap — merge candidates per GOVERNANCE.md): issues filed on one
  tool that belong to the other, docs/referrers presenting them as one
  journey, high devkit co-install, overlapping commands in real usage.
  Signals that argue a boundary EXISTS: distinct issue trackers with no
  cross-filing, separate audiences using each alone, pm reports that
  never embed metrics output. Shared-infra overlap (both read
  `sessions.db` via parallel implementations, ~400 LOC) is tracked under
  the internals-spec evaluation, not merge evidence.
- **Expected outcome:** at the December audit the accumulated signals
  either justify a merge proposal or record the boundary as confirmed.
- **Result:** open — measuring.

## D-2026-10-08 — Shared infra (paths/identity/vscdb) → internals-spec (V4 §25)

- **Decision:** extract the vendored helpers into `devin-internals-spec`
  rather than a new package; migrate consumers per-repo afterwards.
- **Reason:** 11 drifted `paths.py`, 4 `identity.py` (3 identical),
  3 `vscdb.py` readers duplicate what the spec already partly owns; a
  new package would add a repo, a dependency and a release channel for
  ~500 LOC.
- **Evidence:** `docs/shared-infra-eval.md` — duplication map and API
  fit; internals-spec already parses `state.vscdb` but lacks the locator
  layer every consumer rewrites.
- **Expected outcome:** spec 0.4.0 ships `paths`/`identity`; vendored
  copies deprecate as consumers migrate.
- **Result:** open — proposal, not yet implemented.

## D-2026-10-08 — P5 is a measurement window, not a work freeze

- **Decision:** lift the blanket freeze; gate only changes that
  invalidate the measured series (merges, new/deleted repos, taxonomy,
  renames). Product/discoverability work allowed.
- **Reason:** the freeze conflated "don't invalidate the measurement"
  with "don't change anything"; product work is what the baseline
  exists to measure.
- **Evidence:** baseline metrics (views/clones/downloads/stars) are not
  affected by UX work; structural events are logged per snapshot.
- **Expected outcome:** adoption work proceeds while the window runs.
- **Result:** open — evaluated at the 2026-12-03 audit.

## D-2026-10-08 — Merge `devin-dream` into `devin-evals` (P4)

- **Decision:** absorb dream's synthetic-defect corpus generator into
  evals; archive devin-dream.
- **Reason:** same job-to-be-done (assurance), direct dependency, joint
  install/test story.
- **Evidence:** technical (dream generated evals' corpus; shared Python
  runtime) + product (same assurance user). Semantic corpus parity after
  absorption: 6/9 verdicts matched, 3 pre-existing grader gaps
  (D05/D07/D09), 0 mismatches.
- **Expected outcome:** one assurance package, no behavior regression.
- **Result:** met — `devin-evals` 0.2.0 ships the corpus; `devin-dream`
  archived. Byte-parity gate was miscalibrated (vendored copy had
  drifted); semantic parity was the correct acceptance criterion.

## D-2026-10-08 — Consolidate CI workflows into reusables `@v1` (P3b)

- **Decision:** labeler/scorecard/codeql/ci callers in 20 repos use
  `devin-powerups/.github/workflows/*@v1`; 4 intentional variants stay
  inline (bridge, evals, memory, qa-pack).
- **Reason:** 134 replicated workflow files drifted; consolidation makes
  fixes propagate.
- **Evidence:** byte-parity across callers; live end-to-end validation
  (labeler applied labels on test PR; scorecard dispatch run
  37704360583; CodeQL self-validated per-PR).
- **Expected outcome:** single fix point; variants documented.
- **Result:** met, plus one real production bug found and fixed
  (scorecard `read-all` permissions → `startup_failure`).

## D-2026-10-08 — `distribution_status` + DIST-STATUS banners (P2.x)

- **Decision:** registry declares `published`/`source_only`; source-only
  READMEs carry a marked banner enforced by `check_dist_status`.
- **Reason:** honest distribution metadata; prevents implying PyPI/npm
  installs that do not exist.
- **Evidence:** caught in production on day one — `devin-metrics` flip
  left `source_only` stale; drift workflow failed as designed.
- **Expected outcome:** distribution claims stay consistent with the
  registry without manual policing.
- **Result:** met.

## D-2026-10-07 — HOLD the five upstream forks (P1)

- **Decision:** do not merge or repurpose fork-janitor's targets; keep
  the upstream-PR campaign.
- **Reason:** the audit premise (384 abandoned PRs) was refuted — the
  forks run an active awesome-list submission campaign.
- **Evidence:** live upstream PRs open/merged at audit time.
- **Expected outcome:** keep measuring the funnel instead of closing it.
- **Result:** confirmed — funnel now measured weekly by
  `tools/fork_visibility.py`.


## Standing negative decisions (until evidence changes)

Superseded by `D-2026-10-09` (7-product consolidation): backup+janitor,
graph+history+search, pm+metrics, bridge+orchestrator — see that record's
"Superseded standing decisions" section for the reversal evidence.

| Candidate | State | Reason |
|---|---|---|
| consumers → internals-spec | rejected | foundation stays a dependency, not a host |


## D-2026-10-09 — Post-rename publication checklist (F3 standing rule)

- **Decision:** every repo rename must be followed by the same publication
  checklist before the next release: update the PyPI Trusted Publisher
  (exact `owner/repo/workflow/environment` match — GitHub redirects do not
  apply), then validate with a manual `workflow_dispatch` of `publish.yml`.
- **Reason:** the shared publish workflow uses `PYPI_API_TOKEN` when
  present and OIDC as fallback. A rename silently breaks the OIDC path —
  the token masks it until it expires or is revoked. Applied to
  `devin-memory -> devin-brain` and `poordjaevin -> devin-judge`
  (2026-10-09); required again for the Fase-4 renames
  (`devin-redact`, `devin-qa-pack`, `devin-doctor`).
- **Checklist:** identify publish workflow -> rename repo -> verify 301 ->
  update Trusted Publisher on PyPI -> `workflow_dispatch` publish ->
  registry entry + `legacy` -> `snapshot_baseline.py` RENAMES -> sweep
  repo URLs (never package/console/MCP identifiers).
- **Expected outcome:** no release ever fails on a stale OIDC publisher.
- **Result:** pending for Fase-4 renames.

## D-2026-10-09 — Manifest classification depends on the `devin-*` prefix

- **Decision:** record, not change — the devkit manifest classifies a
  public project as `tool` iff its repo name starts with `devin-`
  (`export_devkit_manifest.py`). Everything else lands in `related`.
- **Reason:** discovered during F3b — renaming `poordjaevin` to
  `devin-judge` reclassified it automatically (18+3 -> 19+2) with no
  schema or intent change. The taxonomy surface is coupled to the naming
  convention, not to `nature`/`kind` fields.
- **Implication:** any future product named without the `devin-` prefix
  silently moves out of the tool count; any related project renamed to
  `devin-*` silently becomes a first-party tool. If that coupling ever
  becomes a problem, the fix is to classify by `nature`/`ownership`
  instead of the name prefix.
- **Expected outcome:** no silent reclassification goes unnoticed —
  `test_export_devkit_manifest` pins the counts.
- **Result:** met (counts pinned at 19 tools + 2 related).

## D-2026-10-09 — First consolidation-created runtime dependency: devin-install-scheduler

- **Decision:** publish `devin-install-scheduler` as its own PyPI package
  inside the `devin-state` workspace (`shared/install-scheduler`), rather
  than inlining the shared installer per package or folding it into
  `devin-internals-spec`.
- **Reason:** `devin-backup` and `devin-janitor` carried near-identical
  installers (142/141 lines). Extraction removed the drift; placing it in
  internals-spec would mix foundation spec with a product-family utility;
  inlining would recreate the duplication the monorepo exists to remove.
  The extraction also surfaced a latent inconsistency (redundant
  `sys.platform` guard in the backup cron path) fixed by adopting the
  janitor variant.
- **Cost:** one new PyPI project + one new Trusted Publisher binding
  (`Icaro0310/devin-state`, workflow `publish-scheduler.yml`). API
  changes must stay backwards compatible within `>=0.1.0,<1.0` until a
  coordinated bump.
- **Expected outcome:** future devin-state packages reuse the installer
  without copying it; scheduler bugs get fixed once.
- **Result:** pending — package not yet published; Trusted Publisher to
  create when it is.

## D-2026-11-14 — devin-brain stays in Control, not Build

> **Superseded by D-2026-10-09b** — owner reversal moved `devin-brain` to
> `job: build` / `track: platform`. Kept for history; do not read as
> current policy.

- **Question:** P6 surfaced an ambiguity — one consolidated report grouped
  `devin-brain` visually under a different job; confirm against the
  registry before changing surfaces.
- **Decision:** keep `job: control` / `track: guard` / `nature: product`.
- **Reason:** `devin-brain` (package `devin-memory`) is a memory/context
  service that constrains what the agent can recall and exposes MCP tools;
  in the four-job model it governs execution state, which is Control.
  Build is reserved for tooling that creates or ships ecosystem artifacts
  (devkit, skill-catalog, powerups generators).
- **Verified:** `registry.json` entry — `job: control`, `track: guard`,
  `product_id: devin-brain`; no change required, only confirmation.

## D-2026-10-09b — Job reclassification + final profile pin set

- **Decision:** `devin-judge` moves `verify/assure → control/guard`;
  `devin-brain` moves `control/guard → build/platform`. Profile pins:
  `devin-explore`, `devin-assure`, `devin-control`, `devin-judge`,
  `devin-devkit`, `devin-brain`.
- **Reason:** judge applies a deterministic yes/no gate on agent runs —
  it decides, it does not audit. Verify is reserved for products that
  report evidence (assure); Control is for products that decide or
  constrain execution. Brain is memory that feeds construction: the skill
  makes Devin retain knowledge and build on it, which is Build. This
  supersedes D-2026-11-14 (brain in Control) — owner reversal after the
  pin discussion.
- **Pin rationale:** `devin-internals-spec` is Foundation — a library
  other products consume, nothing a user installs; it never occupies a
  public pin. `devin-state` is excluded because Control is already
  represented by `devin-control` (execution) and `devin-judge`
  (judgment); three Control pins would dominate the six-card surface.
- **Cost:** `_JOB_TRACK` forced the paired track flips; `check_dist_status`
  was extended to resolve member READMEs (`package.path`, then
  `packages/<short>`) so per-package DIST-STATUS banners are what CI
  verifies — stale banners removed from `janitor`, `graph`, `switch`.
- **Expected outcome:** registry, pins, profile README and WHERE blocks
  all tell the same story: Understand 1, Verify 1, Control 2, Build 2.
- **Result:** met locally — `validate_registry.py` and all drift checks
  green; pin swap itself is a manual GitHub action.

## D-2026-10-10 — Journey recuration: six audiences, devops + data-scientists

- **Decision:** `journeys` drops `end-users` (every visitor is one),
  `maintainers` (a hub role, not a user profile) and `security` (a facet,
  not a starting path); adds `devops` (`devin-state → devin-control →
  devin-devkit`) and `data-scientists` (`devin-brain → devin-explore →
  devin-metrics`). `audiences` gains the two keys on the step repos.
  `end-users`, `maintainers` and `security` stay valid as
  browse-by-audience facets.
- **Reason:** the site's "Pick your path" is the public entry curation;
  three of seven profiles didn't describe real audiences. DevOps is
  lifecycle→control→install; Data Scientists is memory→exploration→
  measurement.
- **Evidence:** owner review of icaro0310.github.io, 2026-10-10; schema
  now requires exactly the six journey keys (`required` in
  `journeys`).
- **Expected outcome:** every rendered path surface (site cards,
  awesome-devin, profile README, llms.txt) shows the same six.
- **Result:** met locally — validator, renderers and eco-blocks
  regenerated green; propagation PRs under review.

## D-2026-10-10b — Journey recuration v2: zero repeats, full coverage, Local-first ops

- **Decision:** the six journeys are recut so every step is unique
  across paths (22 steps, 22 distinct entries): `data-scientists`
  becomes `devin-graph → devin-search → devin-history → devin-metrics`
  (metrics leaves `operations`); `developers` gains
  `devin-skill-catalog`; `devops` becomes `devin-state → devin-bridge →
  devin-switch`; `operations` becomes `devin-explore → devin-pm →
  devin-office → devin-backup → devin-janitor` and renders as
  **Local-first ops** (key stays `operations`). Journey steps gain
  optional `label`/`url` overrides so `devin-bridge` — a package
  inside `devin-control`, not a registry repo — can appear under its
  own name.
- **Reason:** owner flagged `devin-metrics` repeated in two cards,
  `devin-bridge` absent from DevOps, and most of the 20+ public repos
  invisible in the paths. Curation now spans the whole product
  inventory without duplication.
- **Evidence:** owner review of icaro0310.github.io, 2026-10-10;
  `validate_registry` green, 320 tests pass.
- **Expected outcome:** site cards, profile README, awesome-devin and
  llms.txt show identical non-repeating paths; holder eco-blocks show
  the updated memberships.
- **Result:** pending propagation.

## D-2026-10-10c — Adapter rollout: MCP + Devin Skill + Devin Plugin per package

- **Decision:** every product package gains three thin AI-facing
  adapters under a self-contained `adapters/` plugin root
  (`.devin-plugin/plugin.json` + `skills/<pkg>/SKILL.md`), a
  `src/<pkg>/mcp_server.py` MCP server with testable `do_*` functions,
  an `mcp` optional extra and a `<cli>-mcp` console script. Mixed
  tools expose only read-only/dry-run tools on those surfaces —
  mutation stays CLI-only with human confirmation (`redact --apply`,
  `janitor --apply`/vacuum, `backup restore`, `switch use`,
  `skill-catalog promote/quarantine`, bridge/orchestrator execution,
  devkit `apply_plan` all stay off the AI surface). `devin-brain`'s
  plugin install launches `devin-memory-mcp --read-only`, so review ops
  (`approve/retract/supersede/quarantine/release/extract`) are never
  registered on the agent-facing server — enforced at registration,
  not just undocumented; its skill/plugin document only the gated
  subset (retain/recall/screen/list/conflicts/prime/verify). The
  standalone server keeps the full tool set — it is the product's
  primary surface and the human operator's review path.
- **Reason:** "one logic, many faces" — adapters call the package core
  and never re-implement business rules; mutation on an AI-driven
  surface skips human confirmation. The `adapters/` root keeps each
  plugin installable via `git` subdirectory without symlinks.
- **Evidence:** `docs/adapters.md` (pattern); reference proofs
  `devin-doctor`/`devin-qa-pack`/`devin-redact`; per-repo feature
  branches `feat/adapters-*` with per-package `test_mcp.py` +
  `test_skill.py` contract tests (CLI-JSON parity, banned-mutation
  greps, `importorskip("mcp")` guards for `[dev]`-only CI).
- **Expected outcome:** all 19 registry packages have a consistent,
  installable, read-only AI surface; legacy skills no longer teach
  destructive flags to agents.
- **Result:** met locally — per-package suites green; legacy
  `session-janitor` skill marked archived/dry-run-only (orchestrator
  skill audited compliant — it documents only the read-only planner);
  rollout PRs under review.

