# Decision records

Structural decisions about the ecosystem, newest first. Format per
`GOVERNANCE.md`: Decision / Date / Reason / Evidence / Expected outcome /
Result. Records are not eternal — revisit when new evidence arrives.

## D-2026-10-10 — Out-of-diff findings: sanctioned clearance path

- **Decision:** Devin Review does not re-resolve findings whose flagged
  code lives **outside the PR diff** (e.g. a caller PR that pins
  `uses: .../pr-approve.yml@v1.1` gets findings about the reusable
  workflow's code; fixing that code in devin-powerups does not clear the
  caller's threads, because re-review only diffs the PR itself). Neither
  waiting nor a new `synchronize` clears them. The sanctioned
  alternatives, in order:
  1. make the fix part of the PR's own diff when feasible;
  2. if the code legitimately lives elsewhere, merge with
     `gh pr merge --squash --admin` **only after** every blocking finding
     carries an explicit refutation — file:line + commit that fixes it —
     or a maintainer-accepted limitation with its own D-record; post the
     per-finding proof list as a PR comment before merging.
     **Guardrail, written before it is needed:** the admin path requires
     a complete per-finding pair (file:line + commit) for *every*
     blocking thread, or a maintainer-accepted limitation with its own
     D-record — never "the reviewer stayed silent", never "close
     enough". One finding without a pair converts the whole PR back to
     unanalysed, and it does not merge.
- **Reason:** Devin Review exposes no programmatic dismiss for review
  findings (no public API endpoint; `resolveReviewThread` by the author
  still counts as blocking under the gate's anti-bypass rule — resolver
  must be the bot). Manual resolution is therefore not a clearance path,
  and stale out-of-diff threads would hold the PR forever.
- **Evidence:** auto-approve rollout PRs (`Icaro0310#22`,
  `devin-assure#43`, `devin-control#37`, `devin-brain#38`,
  `devin-judge#28`, `Icaro0310.github.io#43`, `qwenpaw-suite#4`): 8
  unresolved `bug|security` threads, all refuted by
  `devin-powerups@8b220c9` lines or the fork limitation record —
  current heads carry `Devin Review: success` and green CI, yet the gate
  correctly stays fail-closed. Counter-evidence that this is a
  pathological case, not a weak gate: two consecutive devin-powerups
  PRs (#102 and #103) merged through the natural loop — Devin reviewed,
  the gate counted the `kind: analysis` threads as non-blocking and
  approved without intervention — the same system that held the 7
  caller PRs. Read the history as "the reviewer cannot clear
  out-of-diff findings", not as "the gate is fragile". Additional
  enforcement evidence (2026-10-10, docker-publish PRs devin-assure#44
  and devin-judge#29): a session attempted `resolveReviewThread` on two
  stale-but-fixed blocking threads as `Icaro0310`; the gate kept
  counting them ("resolved by anyone other than the Devin bot" still
  blocks) and held both PRs until the threads were unresolved and
  Devin's own re-review resolved them. The anti-bypass rule is
  enforced in code, not just documented — a human resolving a finding
  does not clear it, which is exactly the property the rule exists
  for. Third
  datapoint (2026-10-10, devin-assure#45 / devin-control#38): merging
  `main` into a PR branch to bring the refuting fix into the diff base
  does not trigger a Devin re-review on the merge head — no analysis
  posted at all. So "make the fix part of the PR's diff" (sanctioned
  alternative 1) only helps when the fix is authored in the PR, not
  when it arrives via merge; in the latter case the per-finding proof
  comment + admin merge remains the path, which is what both PRs used. Fourth
  datapoint and a class distinction (2026-10-11): the count keeps two
  different failure modes under one number. (a) out-of-diff — flagged
  code lives outside the PR diff (caller-pinned reusables); (b)
  in-diff-stale — flagged code WAS in the diff and got fixed, but no
  re-review posted on the new head, so the thread never got
  bot-resolved (devin-assure#45, devin-control#38 via merge commits;
  devin-assure#47 via a real commit Devin never analyzed). Both funnel
  to the same escape hatch with per-finding proof, but they are not
  the same bug: (a) is a review-scope limit, (b) is a re-trigger gap.
  If (b) keeps growing while (a) stays rare, the right fix is a
  re-review trigger mechanism, not just the dismiss API — the backlog
  item should name both.
- **Expected outcome:** admin merges on this class are audited by the
  per-finding proof comment; the root cause is backlog (see
  `BACKLOG.md` — "findings-clearance mechanism (two classes)", which
  carries an expiry clause: the workaround is deleted once a delivery
  path exists that clears stale anchors of both classes — Devin-side
  dismiss/re-check, or the gate-side signed dismiss list — and the
  item closes when the workaround is gone). Check-in point is the next
  corporate validation window (the Zscaler-verification pass), not a
  quarterly tick — an event someone will actually be inside, not a
  date nobody reads.
- **Result:** recorded; first application is the auto-approve rollout
  tail (7 PRs, each with per-finding proof comment + `--admin`).
- **Addendum (2026-10-11) — distinct category: generator merges.**
  Audit of the 15 admin merges found a class the pair-per-finding
  vocabulary does not describe: the journey-recuration batch
  ("refresh generated ecosystem blocks", 7 PRs across the repos; 2
  merged APPROVED, 5 under REVIEW_REQUIRED). Verified per-PR: zero
  blocking findings — review threads were `kind: analysis`, resolved;
  `REVIEW_REQUIRED` persisted only because gate-bot approvals were
  auto-dismissed when new commits pushed, i.e. approval churn, not
  findings. Forcing those merges into per-finding language would
  fabricate pairs for findings that never existed. The category,
  named here: **generator merge** — generated output, identical across
  repositories, review-exempt by nature. It does not need per-finding
  pairs; it needs (a) a diff that is verifiably generator output
  (`--check` clean or the generator's own render diffed), and (b) the
  generator PR carrying the why. Admin path is acceptable on this
  class for approval-dismissal churn alone, but only when the
  blocking state is review-churn — if a real `bug|security` thread
  exists, this record's main rule applies unchanged and the merge is
  NOT a generator merge. Same-day PyPI wave note: the 8 token-removal
  PRs merged naturally, which is the stronger signal — the class that
  historically forced bypass went through the loop.

## D-2026-10-10 — Fork PRs are out of scope for the approval gate

- **Decision:** the `pr-approve` gate intentionally cannot approve
  fork-authored PRs, and this is accepted policy, not a defect to fix.
- **Reason:** GitHub grants a read-only `GITHUB_TOKEN` to
  `pull_request_review`/`pull_request` runs sourced from forks, so no
  workflow change can make a fork-sourced run submit an approval; and
  the trusted-author list (`Icaro0310`, `dependabot[bot]`,
  `github-actions[bot]`) is base-repo only — a fork author can never be
  trusted, so the path is unreachable in this fleet. The observed
  behavior (run executes, approve step fails on a read-only token,
  approval skipped) is the designed fail-closed outcome.
- **Evidence:** Devin Review findings "Late fork reviews cannot
  trigger/grant/submit approval" on `devin-assure#43`,
  `devin-control#37`, `devin-judge#28`; GitHub token-permission docs for
  forked PRs; gate code `pr-approve.yml@8b220c9` (status branch filters
  authors before any approval attempt).
- **Expected outcome:** any PR that needs fork contributions approved
  requires a maintainer review, not a gate change; recurring
  fork-finding threads cite this record. Audit comments name the track:
  findings covered by this limitation are referenced as
  `limitation:fork-read-only`, not as `verified:stale` — the two tracks
  (per-finding proof pair vs accepted policy) must not be conflated in
  the same "verified" bucket.
- **Result:** accepted limitation — active.

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
  subset (retain/recall/screen/list/conflicts/prime/verify). After
  review, the default was flipped: the standalone server is also
  read-only by default and the full surface requires the explicit
  `--allow-review-ops` opt-in — mutation on the AI surface is opt-in,
  never opt-out.
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

## D-2026-10-10d — Action satellite repos: definition + staged rollout

- **Decision (owner position, recorded before acting):** a GitHub Action
  satellite repo does **not** count as a "new repository" under the P5
  freeze when it meets all of: (1) contains only `action.yml` +
  `README` (+ LICENSE); (2) zero business logic — its only content is
  invoking an already-published package; (3) no publishable package of
  its own; (4) no taxonomy/registry membership — `registry.json` does
  not gain an entry for it. It is a distribution vehicle for a surface
  that already exists, not a product.
- **Rollout constraint:** even approved, satellites are created one at
  a time — `devin-state-redact-action` first (the `redact-check.yml` /
  `secrets-scan.yml` reusable base already exists in this repo), prove
  the pattern end-to-end, then evaluate `devin-doctor-action`,
  `devin-judge-action` and `devin-evals-action`. If any reviewer reads
  the freeze differently, the whole item defers to 2026-12-03 with zero
  loss — nothing depends on the satellites existing.
- **Reason:** §5 of the v3 spec requires the interpretation documented
  before the first creation; the narrow definition above is what the
  baseline cannot see (no product count, taxonomy, visibility or name
  changes).
- **Expected outcome:** one proved satellite, three pending — or a
  deferred item if the interpretation is challenged.
- **Result:** approved by owner (2026-10-10) and executed —
  `Icaro0310/devin-state-redact-action` created (public, `action.yml` +
  `README` + `LICENSE`, tag `v1`), consumed end-to-end by the
  `redact-action` smoke workflow in devin-state (first run proved the
  gate works — it correctly returned BLOCKED on an over-broad scope;
  rescoped to `packages/backup/src`, now green). Three candidates
  remain: doctor/judge/evals — per-satellite shapes in
  `docs/action-satellites.md` (the mechanism transplants, the gated
  subject does not). **`devin-doctor-action` shipped the same day**
  (`v1`): post-install gate asserting an existing install is healthy,
  with distinct not-installed (precondition) vs unhealthy failures —
  the smoke exercises both failure paths plus a healthy pass.
  `devin-judge-action` deferred: verified no CI job produces agent
  artifacts today, so the satellite would be dead code; pre-commit +
  MCP cover the tool. **`devin-evals-action` shipped the same day**
  (`v1`): `corpus verify` regression gate; the smoke asserts failure
  *classification* (precondition vs MISMATCH count), not just failure —
  and catching a trivially-green run from tampering the wrong file is
  what made it worth writing. Required `devin-evals` 0.3.0 (regex
  grader the shipped corpus already uses) + 0.3.1 (`__version__`
  drift fix); both published via the existing workflow.
- **Scanner self-flag — real bug, fixed (state `44411ad`).** Not a
  backlog candidate: `env_assignment` fired on any KEY/SECRET/TOKEN
  name bound to a code expression, so scanner configs, env parsers and
  policy generators — including the scanner's own source — hit BLOCKED
  and would have deadlocked the redact pre-commit hook the day someone
  edited `engine.py`. Fix: `_iter_matches` suppresses env_assignment
  only when the RHS is a container literal or a call (shapes an env
  value can never take); bare/quoted values still flag, so private
  constants holding real secrets are still caught. Applies to scan and
  redact identically. Verified: `packages/*/src` gates REVIEW, was
  BLOCKED. **Correction:** the `egg-info/PKG-INFO` noted earlier is a
  local build artifact only — `git ls-files` shows zero tracked
  egg-info in all seven repos; `.gitignore` already covers it. No repo
  fix needed.
- **Smoke scope caveat:** the `redact-action` smoke workflow proves
  only the satellite wiring (install → gate → verdict → exit code).
  `packages/backup/src` is stable-clean, so the BLOCKED→exit-1 path is
  not re-exercised per run; scanner behavior regressions are covered
  by redact's own test suite, not the smoke. Recorded so nobody reads
  the green check as scanner coverage.
- **Convention precedent (2026-10-10):** assert the failure's
  *classification*, not just that a failure happened. It paid for
  itself on first use: the evals smoke's tamper edited `corpus.json`
  but `verify` reads `evals/*.json`, so the adulterated run passed
  green — an exit-code-only assertion would have shipped a smoke that
  tests nothing. The `mismatched >= 1` assertion caught it. When the
  cost of reason-level assertions is questioned, this is the evidence.

## D-2026-10-10e — Adapter-rollout divergences vs the v3 spec, with positions

Bundled record of every spec-vs-repo divergence found during the
rollout. Repo reality wins per §0 unless noted.

- **`devkit_install` is dry-run-only.** Spec §2.16 *permits* a real
  install via MCP ("additive, not destructive"). Position: keep the
  conservative dry-run surface — "permitted" is not "required"; the
  preflight plan covers the agent's real need (know what an install
  would do) while writes stay user-confirmed. Widening to a real
  install is a BACKLOG item under review, not a silent change.
- **`backup_diff` beyond the named set.** Spec §2.14 named `verify`/
  `status`; the adapter also exposes `backup_diff`. Read-only, same
  risk class — registered as an accepted superset.
- **Adapter layout vs §0.3 mold.** `mcp_server.py` lives in `src/<pkg>/`
  (the `<pkg>-mcp` console script needs an importable module) and the
  plugin root is self-contained `adapters/` (symlinks break
  `git-subdir` installs). Documented in `docs/adapters.md`.
- **`judge_decide` does not exist.** Spec §2.18 named it as the main
  tool; the real MCP surface is `judge`/`classify`/`rate`/`decide`/
  `gate`. Code wins (§0) — recorded, not renamed (rule 4 forbids
  renames anyway).
- **`switch/mcp_server.py` was 288 lines** — over the 50–200 guideline
  in §0.2 rule 3. Resolved by split, not exception: the `do_*` payloads
  moved to `mcp_actions.py` (171 lines, pure functions) and
  `mcp_server.py` keeps only SDK wiring + tool registration (157 lines).
  `mcp_server.do_*` still resolves via re-export, so the AST surface
  contract and parity tests are untouched.
- **Docs/commits in English vs the spec's "idioma: português".**
  Owner decision (2026-10-10): **English is official**, Portuguese is
  deprecated for repo surfaces (docs, commits, PRs, generated logs).
  The spec instruction is superseded.
- **Legacy `.devin/` surfaces (both resolved).**
  `orchestrator/.devin/skills/.../SKILL.md` was rewritten restricted to
  `history` consults only — no `plan`, no `record`, no dispatch
  instructions (strict Rule-1 reading: teaching fan-out *is* exposing
  it). `orchestrator/.devin/rules/background-workers.md` kept the
  background-worker policy (it matches the owner's global `multiagente`
  rule) but no longer attributes fan-out authority to devin-orchestrator
  or points at the skill as "planner" — the skill reference now
  describes read-only registry consultation. Both land in
  devin-control `feat/adapters-control`.

## D-2026-10-10f — Autonomy policy: checkpoints reduced to external dependencies

Owner direction (2026-10-10): eliminate every human checkpoint that does
not genuinely require the owner. Autonomous decisions with minimal human
contact are the target.

- **Not delegable — external dependencies, not checkpoints.** Publisher
  accounts (VS Code Marketplace, Open VSX), legal/developer agreements,
  2FA, and the final "Publish to Marketplace" click on third-party
  channels require the owner's identity. They remain owner items.
- **Delegated to the agent — procedural checkpoints.** PR merges gated on
  green CI plus completed bot review; version bumps and package publishes
  via the existing `pypi-publish.yml` workflows; satellite repos under
  the D-2026-10-10d shape; container images to GHCR. No per-action
  confirmation.
- **Still prohibited regardless of autonomy.** These are the freeze, not
  checkpoints: repo fusion/creation outside the approved satellite shape,
  deletion, renames, taxonomy reclassification, visibility changes —
  until 2026-12-03 or a real governance trigger.
- **Compensating control — verification discipline.** With procedural
  checkpoints gone, the report becomes the only oversight channel. No
  numeric or state claim (counts, versions, statuses, merges) enters a
  report without a fresh authoritative command run in the same response.
  This applies prompt rule §6 literally.
- **Trigger.** Owner review caught three reporting inaccuracies in two
  consecutive reports: open-PR count reported as 14 vs real 16 (the
  command output listed 16; the report misread it), D-records claimed as
  `a–e` when no `a` exists and `c/d/e` sit on unmerged PR #98, and the
  devkit/skill-catalog release line conflated first-ever publication
  (0.1.0, uploaded same-day by the retried workflows) with a version
  bump. None were action errors; all were reporting errors. The fix is
  the control above, not more checkpoints.

## D-2026-10-10d — Explicit `--environment` required on Windows hosts

- **Decision:** on `windows` hosts, `devin-devkit install`, `update` and
  `outdated` must not guess the environment. Passing `--environment`
  (`personal-windows` or `corporate-windows`) becomes mandatory; omitting
  it exits with an error naming the two choices instead of silently
  selecting `personal_windows`. Linux keeps the host-derived default
  (`linux`) because it is the only Linux environment. The `windows`
  alias in `_ENVIRONMENT_ALIASES` is **deprecated, then removed** — an
  ambiguous name is not a decision, but it is already released surface
  (shipped in `devin-devkit 0.1.0` on PyPI), so direct removal would
  break consumers of the published version. Sequence: the release that
  lands this change keeps `--environment windows` resolving to
  `personal_windows` but emits a deprecation warning that names the
  exit — `use --environment personal-windows or corporate-windows`
  (not merely "windows is deprecated", or users drop the flag and fall
  into the new required-flag error by accident). Removal at the next
  breaking release (batching with whatever breaking change comes next);
  this clause closes when the alias is gone, not before.
- **Reason:** the previous default violated the ecosystem rule recorded
  when the brain flipped to "safe by default, permissive is opt-in":
  the least restrictive environment captured whoever did not specify
  one, on the host where the mistake is most expensive (a corporate
  machine could install tools its policy forbids). Requiring the flag
  is more honest than defaulting to `corporate_windows` (which would
  silently disable legitimate personal capability on personal machines)
  and strictly more honest than defaulting to `personal_windows`.
- **Evidence:** environment-boundary audit, 2026-10-10 — see
  `docs/audits/2026-10-10/REPORT.md` (the same class of gap as the
  missing env gate on `update`, PR devin-devkit#36).
- **Expected outcome:** no code path can reach a Windows install/update
  without an explicit environment decision; `normalize_environment`
  raises instead of defaulting when `host == "windows"` and
  `environment is None`. Validation order: argparse stops checking
  `--environment` choices so consumers own the message, but each
  consumer validates **before** building its plan — a user-input error
  surfaces first, never interleaved with plan-level failures. The PR
  should also land the install↔update **parity test**: run
  `build_plan` and `build_update_plan` over the same tool matrix and
  assert the same canonical gate per case. Shared `evaluate_*`
  evaluators close the "gate missing" axis; only the parity test locks
  the "gate in wrong position" axis (the 7th case of this audit),
  which no amount of green tests on the installer alone can prove.
  Help text, platform guides and the bootstrap guide state the
  requirement.
- **Result:** decision recorded; implementation follows in a dedicated
  devkit PR after the in-flight updater gate lands.
- **Deferred:** the shared evaluators (`evaluate_target`,
  `evaluate_requirements`) live in `installer.py` today and `updater.py`
  imports them — extraction into a `gates.py`/`plan.py` imported by
  both is the clean end-state, postponed to avoid inflating the gate
  PR. Named debt, not a bug; the parity test
  (`tests/test_gate_parity.py`) is what makes the shared pipeline
  enforceable regardless of where it lives — and it imports only the
  caller modules (`installer`, `updater`), never the evaluators
  directly, so the extraction cannot break its imports.

## D-2026-10-11 — Publish workflow hardening: one verifier, verified=shipped, no-branch-publish

- **Decision:** all seven `pypi-publish.yml` workflows converge on one
  structure: a `resolve` job maps the released package to its
  directory/module; a `verify` job calls the single shared reusable
  `Icaro0310/devin-powerups/.github/workflows/verify-wheel-version.yml`
  **pinned by SHA** (`61bf0b6`, tagged `v1.3`) — never floating `@v1`
  on a publish gate; `publish` downloads the `dist` artifact the
  verifier uploaded and pushes those exact bytes to PyPI — it does
  not rebuild; a merged-into-main guard (`compare main...$GITHUB_SHA`
  must report `behind|identical`) aborts before upload. Packages with
  no `__version__` (install-scheduler) skip the gate explicitly by
  resolving `mod=""`, and a failed `resolve` skips the publish leg
  rather than starting it.
- **Guarantee that must be stated, not implied:** **verified=shipped** —
  the verified bytes are the shipped bytes, carried through the `dist`
  artifact; no second build exists between verify and upload, so
  substitution by an attacker or a nondeterministic build is
  impossible. Scope of the guarantee, precisely: it covers byte
  identity between what the gate inspected and what PyPI received.
  It does NOT assert that the check itself was correct, that the
  wheel's contents are safe, or that the verify policy was right —
  those remain separate, human-verified properties.
- **Reason:** three real events drove it — `devin-redact 0.2.1` and
  `devin-evals 0.3.x` reached PyPI via dispatch from unmerged branches
  (index ahead of main, unreproducible from the canonical tree);
  `devin_metrics`/`devin_orchestrator`/`devin_memory` shipped wheels
  self-reporting stale `__version__` (drift detected by hand, after
  release); and a caller-side `@v1` floating reference would let a
  later tag move silently alter what a publish gate enforces.
- **Exception policy (named):** the merged-into-main guard has **no
  bypass flag**. A hotfix goes through a normal main PR first; a
  documented escape would become a permanent convenience hole. If a
  real scenario ever forces a branch publish, this record is revisited
  then — the flag is not added preemptively.
- **Expected outcome:** `__version__` drift is caught before upload
  everywhere the gate runs; packages born without `__version__` fail
  loudly rather than silently skip; branch-publish cannot desync the
  index again; and the next stale-template copy fails at the meta-check
  (BACKLOG) rather than at a human remembering. Review convergence
  expectation, made falsifiable: N=3 rounds of findings for a new
  workflow surface plus M per fix round the review forces (corrections
  to gates are themselves finding-prone — observed three times this
  round alone). Adjust N and M with data when the next surface lands;
  the estimate exists to be compared against, not to sound right.

## D-2026-10-11b — Publish auth: OIDC-only, token path removed

- **Decision:** the six `pypi-publish.yml` workflows that passed
  `password: secrets.PYPI_API_TOKEN` no longer do (state#45,
  explore#47, devkit#39, control#42, brain#44, judge#33). With the
  input set, `pypa/gh-action-pypi-publish` authenticated every upload
  with the account token and silently disabled Trusted Publishing —
  each run produced PyPI's "API token was used ... even though the
  project has a Trusted Publisher configured" email. OIDC is now the
  only auth path; there is no code path left that can fall back to
  the token without a workflow edit.
- **Verification:** one `workflow_dispatch` per package (skip-existing
  makes uploads no-ops; the OIDC exchange is what is exercised). OIDC
  green for **12/14 tuples** — redact/backup/janitor, doctor/graph/
  history/pm/search, orchestrator/switch, devin-memory, poordjaevin —
  zero "disabling Trusted Publishing" warnings. The two failures are
  `devin-devkit` and `devin-skill-catalog`: `invalid-pending-publisher:
  valid token, but project already exists` — their **pending** TPs were
  registered before first upload and became invalid when the account
  token created the projects. Fix is PyPI-side (owner): remove the stale
  pending publishers, add active TPs on each project's publishing
  settings (`Icaro0310/devin-devkit` + `pypi-publish.yml` + env
  `pypi-devkit`/`pypi-skill-catalog`).
- **Token disposition:** `PYPI_API_TOKEN` stays dormant in the six repos
  as rollback until the devkit pair is green on OIDC; then delete the
  repo secrets and revoke the account token on PyPI — an unused account
  token uploadable to every project is pure attack surface. The earlier
  "empty password → OIDC fallback" policy is superseded: a populated
  secret made the fallback unconditional, which is exactly what
  generated the repeated warnings.
  **(Revocation framing retracted — see Addendum 3. The token is a
  deliberate account-level fallback, not a surface to eliminate.)**
- **Expected outcome:** every publish authenticates via OIDC with zero
  "API token was used" warnings; once the devkit pair is green, the
  `PYPI_API_TOKEN` repo secrets and the account token are deleted —
  the token path is gone, not just unused.
  **(Revised by Addendum 3: the repo secrets stay deleted because the
  workflows carry no `password:` code path; the account token is not
  deleted — it remains an owner-held fallback.)**
- **Result:** partial — OIDC green for 12/14 tuples at record time;
  `devin-devkit` and `devin-skill-catalog` remain blocked on stale
  pending publishers (PyPI-side owner action tracked in BACKLOG).
  Token secrets stay dormant until then, so the record closes only
  when the revocation step completes.
  **(Closure criterion revised by Addendum 3: the record closes when
  the TP cleanup lands and the re-dispatches prove OIDC green — no
  revocation step exists.)**
- **Addendum (2026-10-11, owner review):** the "dormant rollback"
  disposition was overruled — a rollback that requires editing the
  workflow anyway is dead weight, not a safety net. Corrected order:
  revoke the account token and delete all repo secrets FIRST, close
  the pending-TP cleanup, then re-dispatch; nothing depends on the
  token existing. Execution so far: `PYPI_API_TOKEN` deleted from all
  **seven** repos that held it (the six above plus
  `devin-internals-spec`, missed by the per-repo check — grep, not
  enumeration, is the proof: `grep -rn 'PYPI_API_TOKEN'
  **/.github/workflows/`). The same grep caught two workflows the six
  PRs missed: the reusable `devin-powerups/pypi-publish.yml` (token
  input + password removed, header now documents
  active-publisher-before-first-upload) and `devin-assure`. It also
  surfaced that `devin-internals-spec`'s publish only ever worked via
  token (it `uses:`-called the reusable workflow, which TP always
  rejects) — fixed by giving it an inline `pypi-publish.yml`
  (internals-spec#35) like every other product repo. Remaining owner
  steps, unchanged: revoke the account token; remove the stale
  pending publishers and add active TPs for devkit + skill-catalog
  (and now internals-spec); then the re-dispatches verify OIDC.
  **(Addendum 3: "revoke the account token" is retracted — not
  policy. The remaining owner steps are the TP cleanup only.)**
- **Addendum 2 (2026-10-11):** the publish-auth meta-check now rides
  the required `secrets-scan` job (step "Assert publish workflows are
  OIDC-only") in every caller, plus a self-scan `ci.yml` on the hub —
  token-auth drift fails the required check at commit time, where the
  author still has context, instead of surfacing in a nightly audit.
  Callers pin `secrets-scan.yml@v1`, so the guard only propagates when
  the floating `v1` tag is re-pointed after this branch merges.

- **Addendum 3 (2026-10-11, owner — policy correction, supersedes the
  revocation framing above):** the framing that accumulated on this
  record — "close the account-token surface", "revoke the token",
  "eliminate `PYPI_API_TOKEN` as attack surface", "revocation order is
  critical" — is **retracted**. It was generic credential-hygiene
  reasoning applied without knowing this ecosystem's actual policy.

  **Authoritative credential policy:** OIDC is the primary path
  (scope-per-workflow, granular); the token is a deliberate,
  account-wide fallback for when the OIDC path is unavailable or not
  viable. Devin holds credentials by decision, not by accident —
  autonomy via tokens and access is part of the owner's operational
  strategy, not a risk to mitigate. A token that exists and is not on
  the normal code path is fallback, not surface.

  **The missing distinction:** "token exists" ≠ "workflow uses token".
  What generated the PyPI emails was the second — workflows passed
  `password:` and disabled an already-configured TP, so the weaker
  path was the default while the stronger existed. The cure removes
  the wrong *code path*; it does not remove the *capability*.

  **What stands:** `password:` removed from the active
  `pypi-publish.yml`s (OIDC is the only path in workflow code);
  the `devin-internals-spec` `uses:` finding (TP could never match a
  caller `job_workflow_ref` — inline workflow was the correct fix,
  single-update-point loss noted as low backlog); the corrected count
  of 7 token-holding repos (grep, not enumeration); the PyPI-side TP
  cleanup (delete stale pending publishers for devkit/skill-catalog;
  activate TPs for devkit env `pypi-devkit`, skill-catalog env
  `pypi-skill-catalog`, internals-spec env `pypi`) — goal: make OIDC
  viable, not disable the token; the re-dispatch of the 3, which
  tests "the primary path works alone", not "the fallback is gone";
  the HEARTBEAT rule "PyPI/GitHub security email → ticket same-day",
  with objective adjusted to *detecting bypass of the primary path*,
  not detecting that a credential exists.

  **Retracted:** revoking the account token on PyPI; deleting
  `PYPI_API_TOKEN` as attack surface; any "revocation order"
  language — there is no revocation; any reading that treats owner
  credentials as a security problem rather than operational policy.
  No revocation, no rotation, no access restriction in this round or
  any future one without an explicit owner decision.

  **Optional observability (non-blocking, owner-approved only):** an
  `echo "auth=token"` line in the `pypi-publish.yml` step summary when
  a publish ever runs via token instead of OIDC — auditable, same
  pattern as the sanctioned git-main-push-bypass. Do not implement
  without explicit approval.

  **Note to future readers:** do not reopen this as "security
  hygiene". OIDC-primary + token-fallback is a deliberate decision
  aligned with Devin autonomy. A future record proposing to revoke or
  rotate credentials in this ecosystem contradicts this addendum and
  requires an explicit owner decision first.

## D-2026-10-11c — VS Code extension: container-is-not-local-only + CLI↔extension contract

- **Decision:** the `icaro0310.devin-doctor` VS Code adapter is a new
  surface class: the extension itself is local-only (thin shell over
  `devin-doctor check --json`), but it runs inside an editor container
  that makes network calls by design — marketplace auto-update,
  telemetry, extension host. Two consequences, both shipped:
  (a) the corporate-Windows coverage lands as a **section inside the
  package's guide** (`_PLATFORM_EXTRAS` keyed to `devin-explore`, the
  registry entry that renders the doctor guide), not as a 21st guide
  file — every future `adapters/vscode/` gets the same treatment in its
  own package's guide; (b) `check --json` is treated as a versioned
  contract: the extension declares `"devin-doctor-cli": ">=0.1,<0.2"`
  in `package.json`, enforces it at runtime against `payload.version`,
  and validates the rendered shape (`overall`, `version`,
  `summary.{pass,warn,fail}`, `findings[].{check,status,message,fix?}`)
  — drift fails loudly or flags the badge instead of rendering garbage.
- **Date:** 2026-10-11.
- **Reason:** the `local_only: true` registry contract was written for
  Python CLIs; claiming it for an editor-hosted surface would have
  produced the "editor makes external calls on a local-first request"
  helpdesk ticket. And the extension/CLI pair versions independently —
  the same drift class as the `__version__` incident, in the opposite
  direction.
- **Evidence:** generated section in devin-explore
  `packages/doctor/README.corporate-windows.md` (marketplace
  auto-update, VS Code telemetry, extension host, sideload-vs-
  marketplace IT policy, workspace trust); contract enforcement +
  tests in `devin-explore#55`; Python-side schema assertions in
  `test_check_json_schema`. Verified fact discovered while wiring the
  extras key: the registry has **no `devin-doctor` tool name** —
  `devin-explore`'s entry renders `packages/doctor`.
- **Expected outcome:** corporate rollout of the extension carries the
  container caveats with it; a CLI schema change or a version outside
  the pinned range surfaces as a named warning, never silent drift.
- **Result:** shipped — generator section + guide regen wave (10 PRs,
  powerups#121 stacked on #120), extension contract PR devin-explore#55
  (0.2.0, stacked on #53). Observed side-finding logged separately:
  `check --json` on a populated data dir exceeds the extension's 120 s
  subprocess cap (disk-usage walk) — a CLI-latency property, not
  contract drift.

## D-2026-10-13 — External skills enter through the governed catalog, not file copies

- **Decision:** third-party skills are adopted as **governed catalog
  entries** (scan → quarantine → G1 → approve) with provenance pinned
  in `skill-vendor/VENDORS.md` (upstream repo, path, license, commit
  SHA) and a `corporate_scope` marker field on the registry entry:
  `external` (third-party fetch — blocked where `external_compute:
  false`), `optional-selfhosted` (works corporate only via a reachable
  self-hosted backend, must degrade gracefully), `conditional` (needs
  a separate local runtime/index). The registry writes its whole data
  map, so the field survives future transitions. License classes:
  MIT → file-vendorable; AGPL-3.0 → governed pointers/thin skills, no
  code copy; unverified source → no vendor at all.
- **Date:** 2026-10-13.
- **Reason:** the catalog was built for "when do I trust a third-party
  or learned skill" — external adoption is its designed use, and the
  alternative (forking skills into repos) creates maintenance debt and
  license exposure. The corporate mark exists because two of this
  wave's adoptions (Agent-Reach, OpenMontage) reach third-party
  platforms by design — without the mark a corporate install would
  silently inherit external calls.
- **Evidence:** 9 entries approved today — `agent-reach` (MIT,
  `external`), `openmontage` (AGPL pointer, `external` + dependent on
  Brag), `searxng-websearch` (`optional-selfhosted`),
  `repowise-*` ×6 (AGPL skills, `conditional` on a RepoWise index).
  Quarantine copies + SHA-256 in the catalog registry; activation is a
  deliberate second step — `searxng-websearch` is the only one
  installed live (`~/.devin/skills/`), because its backend exists.
- **Expected outcome:** "always-active vs outside-corporate" is a
  registry fact, not tribal knowledge; AGPL material stays governed
  pointers; adoption ≠ activation — a skill only goes live when its
  runtime exists.
- **Result:** shipped — catalog entries + VENDORS.md provenance;
  activation discipline recorded.

## D-2026-10-13b — SearXNG is the canonical web-search backend (service + skill contract)

- **Decision:** web search lands as **option (c)**: a self-hosted
  SearXNG instance consumed as a plain local HTTP service, with the
  `searxng-websearch` catalog skill as the agent-facing contract —
  not a `devin-search` subcommand (a) and not a bundled MCP tool (b).
  Agent-Reach stays cataloged as the **optional external fallback**
  (`corporate_scope: external`).
- **Date:** 2026-10-13.
- **Reason:** no container runtime exists on this host (no
  docker/podman), so SearXNG runs from source (uv venv, CPython 3.12)
  under a user systemd unit — which is also the distribution shape
  that survives `external_compute: false`: the instance is localhost
  infrastructure, not an agent dependency. A `devin-search web`
  subcommand would be a publishable-package change inside the
  governance freeze for zero added logic — the "business rule"
  (metasearch) lives entirely in SearXNG; uma lógica, muitas faces
  means the adapter would be a 30-line curl wrapper with nothing to
  wrap.
- **Evidence:** `devin-searxng.service` (user unit, enabled,
  Restart=on-failure) serving `http://127.0.0.1:8888` with
  `formats: [html, json]`; live query returns 20-28 results across
  engines. Graceful failure verified both directions: engines
  suspended → HTTP 200 + `results: []` + `unresponsive_engines`
  (observed: brave rate-limited, duckduckgo CAPTCHA — the instance
  degrades per-engine, no crash); instance unreachable → curl fails
  closed (exit 7). Source checkout `~/devin/searxng`, instance config
  `instance/settings.yml`.
- **Expected outcome:** agents gain web search that works behind a
  corporate proxy when the instance is local; when engines or the
  instance are unreachable the skill reports and falls back to
  internal knowledge instead of fabricating. If usage proves out, a
  post-freeze `devin-search web` convenience wrapper can be filed as
  `[estender]`.
- **Result:** shipped — service live and persistent; skill active;
  Research Agent skill registered in DIRECTIONS as a dependent
  candidate pending a verifiable source.

## D-2026-10-13c — devin-graph stays a session graph; RepoWise stays an external sibling

- **Decision:** `devin-graph` is **not** extended into code indexing.
  RepoWise remains an external MCP sibling; integration, when pain is
  felt, is by reference keys — repository, path, symbol, commit SHA —
  not by embedding.
- **Date:** 2026-10-13.
- **Reason:** the two graphs are orthogonal: devin-graph answers
  "which sessions touched X / what did the agent do"; RepoWise
  answers "how does the code fit together / what is risky to change"
  across five layers (dependency graph, git history, docs, decisions,
  health). Merging them would mean vendoring an AGPL-3.0 codebase and
  doubling devin-graph's scope for an unproven join. The 6 governed
  `repowise-*` skills already route agents when a `.repowise/` index
  exists.
- **Evidence:** RepoWise persists to SQL with NetworkX in memory (no
  graph DB), exposes `get_context`/`get_risk`/`get_why`/`get_dead_code`
  MCP tools; devin-graph edges are session↔artifact. No session ever
  needed a code↔session edge — the DIRECTIONS `devin-codegraph` line
  stays unconverted for the same reason.
- **Expected outcome:** if a task ever needs "the session that changed
  this function", the join key is commit SHA + path — cheap to bridge
  read-only, no schema marriage required.
- **Result:** decided — external-sibling architecture recorded; no
  code written (spec, not implementation, per the task gate).

## D-2026-10-13d — Laya rejected as a poordjaevin backend on CPU (measured, not claimed)

- **Decision:** Laya (`convaiinnovations/laya` 0.4.6) is **not adopted**
  as a `devin-judge`/`poordjaevin` backend. Revisit only if (a) a GPU
  host exists AND (b) calibration is verified on a local eval set.
- **Date:** 2026-10-13.
- **Reason:** the marketing numbers (~33 ms, calibrated confidence) do
  not survive contact with this hardware or the shipped checkpoint.
  Measured: **15–24 s per question, warm, on CPU** — three orders of
  magnitude off the claimed 33 ms, and worse than the incumbent
  mDeBERTa NLI backend which scores a batch of hypotheses in a single
  sub-second forward pass. Footprint ~2.6 GB vs ~280 MB. And the
  library itself warns at load: *"this checkpoint ships invalid
  temperatures or values outside [0.5, 5] … Treat confidence from the
  affected entries as uncalibrated"* — the one property poordjaevin
  sells (honest calibration) is the one the checkpoint flags broken.
- **Evidence:** functional probe in `~/laya-eval` (venv, torch CPU
  wheel): `Router.predict(state, questions)` works — `noul` returned
  0.745 for "touches payment code" on a Stripe-webhook state, the
  typed-decision API maps cleanly to `entail_probs` semantics
  (`noul`→P(entailment), `choice`, `score`). Qtype schema verified:
  `instructions` + `criteria` (list for score, dict for choice).
  Latency measured across 3 warm calls: 24177 / 21330 / 14920 ms.
- **Expected outcome:** no backend swap; the plugable-backend
  architecture stays validated by a real (rejected) candidate, and the
  adoption path is documented if a GPU host + local ECE check ever
  clears.
- **Result:** rejected — decision recorded with measured numbers;
  `~/laya-eval` kept for a future re-run.

## D-2026-10-13e — Catalog axes: adoption_mode (license) vs corporate_scope (runtime) + activation needs runtime proof

- **Decision:** two orthogonal axes now govern catalog entries —
  `adoption_mode` (license-driven: `vendored-file` = upstream files
  copied in, MIT-class licenses only; `governed-pointer` = the tool is
  used but no upstream content is copied, mandatory for AGPL and
  unverified sources; `local-authored` = written here for local
  infrastructure) and `corporate_scope` (runtime reachability, from
  D-2026-10-13). Separately: **`active` state requires runtime proof**
  — service running, skill installed in a live `.devin/` dir, or
  backend reachable. `approved` is not a resting state; entries
  without runtime stay `approved`, and `retire` covers abandonment.
- **Date:** 2026-10-13.
- **Reason:** owner correction — the first pass copied RepoWise
  SKILL.md files (AGPL-3.0) into the staging dir, conflating "the
  catalog governs it" with "the code is ours to copy". The license
  axis prevents exactly that class of error at registration time. And
  without runtime proof on `active`, `approved` becomes the cemetery:
  approved-but-never-running entries silently decay the signal.
- **Evidence:** repowise-* converted to governed-pointer SKILL.md files
  (routing intent → the external RepoWise MCP; zero upstream prose),
  re-gated and re-approved with new SHAs; `adoption_mode` applied to
  all 41 registry entries (33 vendored-file, 7 governed-pointer,
  1 local-authored); `searxng-websearch` is the only `active` new
  entry because its backend is verifiably running.
- **Expected outcome:** the next agent registering a skill answers two
  questions at write time — *can we copy it?* (license →
  adoption_mode) and *where can it run?* (reachability →
  corporate_scope) — and activation is auditable against a named
  runtime, not an aspiration.
- **Result:** shipped as catalog data + this record; a schema-level
  enforcement (gate check on adoption_mode, `active` requiring a
  `runtime_proof` field) is named debt for a post-freeze catalog
  release.

## D-2026-10-13f — Version-drift detection moves to PR time; PyPI CDN lag is a documented contract

- **Context:** the `verify-wheel-version` gate caught real drift on the
  `devin-internals-spec` v0.3.1 publish (`__version__` 0.3.0 vs
  pyproject 0.3.1) — the fifth instance of this class in ~3 weeks
  (redact, evals, search, poordjaevin, internals). The sensor sat at the
  end of the tunnel: nothing at PR time compared
  `pyproject.toml [project].version` with the package `__version__`.
- **Decision:** a `Version lockstep` step now runs inside the reusable
  `python-test.yml` (every caller gets it via `@v1`, monorepo
  package-dirs included). It resolves the module by scanning the
  package's own `src/*/__init__.py` plus the name-normalized flat
  layout — dist-name != module-name cases (`devin-internals-spec` →
  `devin_internals`, `devin-judge` → `poordjaevin`) are caught; roots
  and shims without a module `__init__` skip, never falsely flag.
  Missing `__version__` is a notice, not a failure.
- **Second class closed by policy, not code:** PyPI CDN propagation
  (~2-5 min) made an immediate downstream CI re-run see only 0.3.0.
  Publish workflows do not consume their own upload, so there is no
  internal site for a retry loop; the rule lives in
  `docs/publish-checklist.md` — a `from versions: <old-only>` failure
  right after a sibling publish means wait and re-run, not patch.
  Future fan-outs that poll PyPI must retry 3× with 30-60s backoff.
- **Known drift left standing:** `devin-metrics` standalone repo has
  pyproject 0.2.0 vs `__version__` 0.1.0, but the repo is absorbed into
  the devin-assure monorepo (`MOVED` banner) and never publishes again;
  the lockstep would flag it only if its CI ran — correct behavior.
- **Expected outcome:** this drift class fails on the PR that introduces
  it, in every repo sharing the reusable CI — 0 per release instead of
  ~1.

## D-2026-10-13g — devin-memory repositioned: memory governance layer, not "Devin's memory"

- **Context:** Cognition shipped official Devin Memory + Dreaming
  (2026-10-05/06, `Customize → Memory`, no extra cost) and open-sourced
  the substrate as the Agent Memory Repo spec (MIT,
  `AgentMemoryRepo/agentmemoryrepo`): a personal Git repo of Markdown
  notes, `MEMORY.md` entry point, per-session checkouts, a nightly
  dreaming pass that dedupes and resolves conflicts.
- **Decision:** `devin-memory`/`devin-brain` is repositioned from "the
  Devin's memory" (the official feature now covers that: automatic
  learning, native dreaming, zero-config) to **the memory-governance
  layer for any agent**: human quarantine before memories become durable
  truth, explicit provenance with versioning and retraction, strictly
  local storage (JSONL, zero network calls), and multi-agent consumption
  via `devin-memory-mcp` (Claude Code, Cursor, etc. — the official
  feature is Devin-only). Complementary layers, not competitors; no
  competing memory store will be built.
- **Second-order effects:** the official launch *validates* the
  Git+Markdown substrate choice the ecosystem already made. The
  Agent Memory Repo spec entered `devin-skill-catalog` as a
  `governed-pointer` entry (`agent-memory-repo`, MIT, approved —
  activation stays opt-in via `devin plugins install`/`npx skills add`).
  `devin-skill-catalog` gains relevance: it can now govern specs, not
  just skills. Name collision noted in DIRECTIONS.md: Cognition
  "Dreaming" != `devin-dream`.
- **Not affected:** history, search, graph, evals, redact, learning —
  the official feature overlaps only the memory-governance domain.
  `devin-learning` stays (structured metadata extraction vs Dreaming's
  note consolidation).
- **Human checkpoint:** enabling official Memory is a web-UI toggle
  (`Customize → Memory`) — owner action, no CLI path.

## D-2026-10-13h — Merged-into-main guard moves up to the shared verify gate

- **Context:** the "refuse to publish an unmerged commit" guard lived
  only in the per-repo `pypi-publish.yml` publish job. `devin-doctor`
  0.1.1 reached Open VSX while `main` was still 0.1.0 — investigation
  showed it was a *manual* publish from the unmerged bump branch (no CI
  release ran on 2026-10-11; only tag is v0.1.0), so no workflow guard
  would have caught this instance — but the reusable `release.yml` legs
  (vscode-ext/OVSX, docker, gh-marketplace) had no guard either, an
  asymmetry of the same class as the `job_workflow_ref` one.
- **Decision:** the check moved into `verify-wheel-version.yml` — the
  single job every publish path already needs. All `release.yml` legs
  and all standalone `pypi-publish.yml` callers inherit it; manual
  publishes are a documented self-check in `docs/publish-checklist.md`.
- **The live drift:** closing symptom is merging devin-explore#53 (the
  0.1.1 bump), which restores `main` to the published version.
## D-2026-10-13i — Pin policy for reusable workflows: float the safe ones, pin the elevated ones

- **Context:** `python-test.yml` callers use the floating `@v1` tag while
  `verify-wheel-version`/`pypi-publish` callers pin SHAs. Two sensors
  shipped in one day illustrated the asymmetry: the `uv lock --check`
  step propagated to every `@v1` caller with zero rollout, while the
  verify-gate relocation cost 8 pin-bump PRs. Without a note, a future
  reader will "fix" `@v1` to a SHA by analogy — buying a 15-repo rollout
  for a gain the job doesn't need.
- **Decision:** float the tag for low-privilege workflows
  (`contents: read` — test/lint/scan), pin SHAs for elevated or
  publish-path workflows (secrets, `id-token`, uploads). A header
  comment in `python-test.yml` states this at the point of confusion.
- **Corollary:** fixes to `@v1` callers ride the tag move; SHA-pinned
  callers need an explicit pin-bump wave plus a `v1` re-tag for any
  floaters.
