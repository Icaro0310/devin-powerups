# Product Boundary Reassessment (P6)

Working document, 2026-10-08. The question reopened: **which repository
boundaries are real product boundaries, and which are historical
artifacts?** Discovery is now solved (tracks, journeys, audiences,
generated surfaces), so the remaining question is structural.

Four levels, kept distinct:

```
TRACK (navigation ontology) → PRODUCT FAMILY → REPOSITORY → CAPABILITY
```

A family is what a user perceives as one product. A repository is a unit
of development, releases, issues and distribution. They need not
coincide — but each extra repo carries real cost (identity, README,
issue tracker, release channel, CI, SEO).

## Constraints

- **P5 window rules apply** (GOVERNANCE.md): physical merges are gated
  until the 2026-12-03 audit because they change what is counted. This
  document is the assessment; execution happens after the window, or
  earlier only if a governance trigger fires.
- **No `family` field in the registry yet** — classification follows the
  decision, not the other way around. This doc is the provisional map.
- Signals below are **preregistered**: the December audit reads this
  list, not post-hoc justifications.

## Verified technical facts (not vibes)

| Pair/triple | Shared code | Contract coupling |
|---|---|---|
| history + search + graph | all three vendor `paths.py`; history+graph also vendor `vscdb.py` + `identity.py`; search vendors `paths.py` + session extraction | none yet — but the shared-infra D-record moves these helpers into internals-spec, which removes the duplication *without* merging |
| janitor → backup | — | real: janitor's cleanup contract requires a verified fresh backup snapshot (tested in `test_janitor_contract.py`) |
| qa-pack + evals | none found | none — different inputs (claims audit vs replay grading) |
| redact vs backup/janitor | — | none — redact is a *security* boundary, not lifecycle |

## Current ranking (2026-10-08, post-verification)

| Rank | Family | Evidence |
|---|---|---|
| 1 | F3 `backup + janitor` | real, tested contract coupling — cleanup requires a verified snapshot |
| 2 | F1 `history + search + graph` | one job, three identities; a *product-unity* test, not architecture |
| 3 | F2 `qa-pack + evals` | technically cheap, but both PyPI identities exist — deprecation cost vs unproven gain |

The candidates are no longer interchangeable: F3 is a dependency
argument, F1 is a cognitive-load argument, F2 is an editorial argument
with public-identity cost.

## Candidates

### F3 — `devin-data` (backup + janitor; redact stays out)

- **Contractual unity:** `backup` produces verified snapshots;
  `janitor` cleanup *requires* one (the contract is tested, not
  thematic). preserve → remove safely is one workflow, not two tools
  that happen to touch data.
- **redact is excluded, not merely deferred:** it is a security
  boundary (audience: security engineers; failure mode: shipping
  secrets). It does not enter the family by inertia — the bar would be
  evidence that users run it inside the lifecycle flow rather than as
  its own gate.
- **Distribution note:** `devin-janitor` is `source_only` — decide the
  family before publishing it, avoiding a create-then-deprecate cycle.

### F1 — `devin-explore` (history + search + graph; pm/office probed)

Three read-only interfaces over the same object — the Devin session
universe:

```
history → when did it happen?
search  → where is it?
graph   → how does it relate?
```

- **Product unity:** high — one mental model, three query modes.
- **Journey unity:** history/search/graph sit adjacent in observe;
  `search`/`graph` already co-install under devkit's `memory` profile.
- **Object unity:** identical (session stores).
- **Technical:** shared vendored loaders (paths/vscdb/identity) —
  duplication argues for consolidation OR for internals-spec
  extraction; the D-record already chose the latter, so code overlap is
  *not* itself merge evidence. What remains is product-identity cost:
  three READMEs, three issue trackers, three releases for one job.
  This is a product-unity test, not an architecture argument.
- **Distribution note:** `devin-graph` is `source_only` — merging before
  publishing avoids creating a package identity that gets deprecated.
  Correct order: decide family first, publish second.
- **Probes (measurable before any merge):** devkit `explore` profile
  co-install rates; cross-repo issues/referrers; traffic correlation.
  Caveat: the profile measures *installation unity* only — users may
  consume a single member, get a tool indirectly, or never install the
  bundle; absence of profile adoption does not alone confirm the
  boundary.
- **pm / office / metrics:** evaluate as family *members*, not automatic
  merge candidates. `pm` writes rollups/milestones (different mode);
  `office` is a visual interface over the same state; `metrics` is
  measure-not-explore — the pm/metrics D-record already preregisters
  that pair's signals.

### F2 — `devin-assure` (qa-pack + evals)

- **Product unity:** high — both answer "did the agent do what it
  claims, and how well". `dream → evals` already collapsed one boundary.
- **Technical:** no shared code — clean submodule boundary
  (`audit` / `replay` / `grade`). Merge is cheap in code terms; the cost
  is deprecating a published PyPI identity.
- **Cost-benefit:** precisely because the merge is technically cheap,
  the dominant question becomes whether collapsing two public
  identities pays for itself — the burden of proof is on the merge.
- **poordjaevin stays out** — it is a decision/confidence layer with an
  audience beyond assurance (MCP server, ACP backend). Integrates, does
  not merge.

### Secondary — `devkit + skill-catalog`

Is the skill catalog a standalone product or a devkit capability?
Preregistered signal: do users consume `devin-skill-catalog` commands
directly (own identity) or only via scaffold/bundle flows (capability)?

### Secondary — `doctor + switch`

Both manage the Devin *environment* (health / config profiles). Weaker
than F1–F3; keep for a later pass.

## Explicitly out of scope (boundaries confirmed)

internals-spec consumers · powerups · awesome-devin · memory · bridge +
orchestrator · poordjaevin · homebrew/scoop · qwenpaw-suite.

## Preregistered signals (December audit reads these)

For each candidate family, the merge signal is:

1. **Co-installation** — devkit profile / pip data shows the candidates
   installed together materially more than with non-members.
2. **Cross-boundary confusion** — issues or questions filed on one repo
   that belong to a sibling.
3. **Journey behavior** — referrers/analytics show users traversing the
   members as one flow (the journeys layer now makes this visible).
4. **Single-identity plausibility** — a merged README writes itself
   coherently; if the combined description needs qualifiers, the
   boundary is real.

Boundary-confirmed signal: distinct audiences, independent usage, no
cross-filing, and a merged description that reads as two products.

## What changes now vs after the window

- **Now (allowed):** this assessment, the `explore` devkit profile as a
  co-install probe, continued D07/D05/D09 work, baseline collection.
- **After 2026-12-03 (or on governance trigger):** merge proposals in
  ranking order F3 → F1 → F2, each as its own PR + D-record update with
  the evidence table filled — "keep separate" is a legitimate outcome.
