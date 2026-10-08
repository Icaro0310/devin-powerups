# Decision records

Structural decisions about the ecosystem, newest first. Format per
`GOVERNANCE.md`: Decision / Date / Reason / Evidence / Expected outcome /
Result. Records are not eternal — revisit when new evidence arrives.

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

| Candidate | State | Reason |
|---|---|---|
| backup + janitor | contracts first | adjacent lifecycle jobs, no product signal yet |
| graph + history + search | rejected | distinct jobs; search is not a storage layer |
| pm + metrics | measure | unclear product boundary — under observation |
| bridge + orchestrator | rejected | transport vs scheduling are different layers |
| consumers → internals-spec | rejected | foundation stays a dependency, not a host |

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
