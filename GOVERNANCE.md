# Governance

How decisions about this ecosystem are made, frozen, and revisited. This
document is the single place that answers "is this change allowed right
now?"

## Source of truth

- `registry.json` — every repository's classification and distribution
  status. Generated surfaces (catalogs, manifests, dashboards) derive
  from it and must stay coherent (`registry-drift` workflow enforces).
- `BASELINE.md` — the P5 collection window and its rules.
- `.github/workflows/VARIANTS.md` — why specific repos intentionally do
  not use the shared reusable workflows.
- `BACKLOG.md` — parked work with priority and unblock conditions.

## Standing rules

1. **Merges are decided by criteria, not by prohibition.** A merge is
   approved only when both a technical signal and a product signal are
   present (see "Consolidation" below). `devin-dream → devin-evals` is
   the only consolidation that has met the bar. The following remain
   disallowed until evidence changes: backup+janitor,
   graph+history+search, pm+metrics, bridge+orchestrator, and any
   consumer merging into `internals-spec`.
2. **No thematic monorepos** (`devin-observe`, `devin-assure`, …).
   Repositories stay physically independent.
3. **Distribution honesty.** `source_only` tools carry a marked
   `DIST-STATUS` banner; `check_dist_status.py` fails if a README
   disagrees with the registry.
4. **Reusable workflow callers pin `@v1`** (movable major tag on this
   repo). Breaking changes ship as `v2`; callers migrate at their own
   pace. See `VARIANTS.md`.
5. **Never `git add -A` / `git add .` in ecosystem repos.** Stage named
   files only. A stray working-tree change once nearly entered a PR and
   would have violated the P5 freeze — always check `git status` before
   committing.

## P5 measurement window (2026-10-08 → 2026-12-03)

The baseline measures adoption signals: views, clones, package
downloads, installs, stars, forks, issues, external PRs. It is a
measurement window, not a work freeze.

**Still prohibited during the window** — because they would invalidate
the measured series itself:

- physical repository merges or new/deleted repositories (changes what
  is counted),
- registry taxonomy reclassification or public/private flips (changes
  what is "public"),
- renaming tools or repos (breaks links and historical series).

**Explicitly allowed** — this work does not contaminate the baseline;
it is what the baseline exists to measure the impact of:

- UX and discoverability: README/profile improvements, site
  reorganization, GitHub topics, rewriting `awesome-devin` as an
  intent map;
- backlog items that do not touch measured structure (D05/D07/D09
  graders, `devin-evals` PyPI publication, …);
- bug fixes, documentation, tooling.

Interpreting the data before 2026-12-03 remains out of scope — collect,
don't conclude. The window ends on **2026-12-03** (issue #14 tracks it)
or earlier only if a governance rule is triggered by new evidence — e.g.
a distribution break, a security incident, or adoption data that makes a
standing decision clearly wrong.

## Lifecycle

The ecosystem evolves; this section defines how each structural event
is proposed, justified, recorded and measured. `registry.json` is the
semantic source of truth — a structural change is not real until the
registry reflects it.

### Creation

A new repository is justified only when it answers all three:

- a job-to-be-done no existing tool covers (not a track slot that "looks
  empty" — tracks are navigation, not quotas);
- a boundary no existing tool can absorb without distorting its scope;
- an audience or interface the existing tools do not serve.

Forbidden regardless of justification: thematic monorepos
(`devin-observe`-style holders) and repos created to fill a track.

### Consolidation

A merge candidate needs **both** signals:

- *Technical*: real code duplication, direct dependency, shared runtime,
  or joint release/install/test cycles.
- *Product*: same user, same job-to-be-done, same issues, same journey —
  or docs already presenting both as one solution.

One signal alone is insufficient. The decision and the evidence go into
`DECISIONS.md` before the merge, with the expected outcome; the result
is recorded after.

### Archival

Archive when a repo is absorbed (post-merge), superseded upstream, or
its function is demonstrably unused. Archival removes the repo from the
active registry (`devin-dream`) or keeps it as a non-public entry
(`devin-dashboard`); `reconcile_registry.py` never reports a
GitHub-archived repo as drift. The decision and its evidence stay in
`DECISIONS.md` so the historical series remains interpretable.

### Reclassification

`track`, `role`, `nature`, `audiences`, `interfaces` may change when the
product's actual use changes — each change is a small decision record.
`mode` informs classification but never determines it alone; `track`
describes intent, `mode` describes technical behavior.

## Decision records

Structural changes leave a record in `DECISIONS.md` with six fields:
Decision, Date, Reason, Evidence, Expected outcome, Result. No decision
is eternal — records exist so a future audit can revisit them with new
evidence instead of guessing at intent.

## How changes happen

Normal work: PR → CI green → Devin Review addressed → squash merge.
Automation commits (`registry-refresh`, `baseline-snapshot`) push
generated data directly to main by design; everything else goes through
a PR.
