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

## P5 freeze (2026-10-08 → 2026-12-03)

During the baseline window:

- allowed: bug fixes, the baseline tooling itself, documentation that
  does not change taxonomy or architecture;
- forbidden: new merges, taxonomy/registry reclassification, new product
  surfaces, thresholds or benchmarks;
- allowed but out of the freeze's scope: measuring, preparing, and
  documenting — as long as nothing user-facing changes.

The freeze ends on **2026-12-03** (issue #14 tracks it) or earlier only
if a governance rule is triggered by new evidence — e.g. a distribution
break, a security incident, or adoption data that makes a standing
decision clearly wrong.

## How changes happen

Normal work: PR → CI green → Devin Review addressed → squash merge.
Exceptions that skip the PR gate: none during P5; automation commits
(`registry-refresh`, `baseline-snapshot`) push generated data directly
to main by design.
