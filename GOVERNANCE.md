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

1. **No physical merges without both technical and product signals.**
   `devin-dream → devin-evals` is the only approved consolidation. The
   following remain disallowed until evidence changes: backup+janitor,
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

## How changes happen

Normal work: PR → CI green → Devin Review addressed → squash merge.
Exceptions that skip the PR gate: none during P5; automation commits
(`registry-refresh`, `baseline-snapshot`) push generated data directly
to main by design.
