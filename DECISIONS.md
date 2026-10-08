# Decision records

Structural decisions about the ecosystem, newest first. Format per
`GOVERNANCE.md`: Decision / Date / Reason / Evidence / Expected outcome /
Result. Records are not eternal — revisit when new evidence arrives.

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
  done).

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

