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
- **Distribution note:** `devin-janitor` was `source_only` when this was
  written (published to PyPI 2026-10-09) — the original intent stands:
  decide the family before creating package identities that get
  deprecated.

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
- **Distribution note:** `devin-graph` was `source_only` when this was
  written (published to PyPI 2026-10-09). The package identity now
  exists — under the D-2026-10-09 merge it is preserved as a workspace
  package, so publication does not create deprecation risk.
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

## Explicitly out of scope (KEEP by default)

F1/F2/F3 are *the three families where a boundary hypothesis is strong
enough to investigate* — not "the three families of the ecosystem".
Everything else stays KEEP by default; absence from the table is a
decision, not an omission.

| Entry | Why not a hypothesis |
|---|---|
| `devin-doctor` | environment health — no sibling shares its job |
| `devin-redact` | security boundary (audience + failure mode); excluded from F3 by rule, not inertia |
| `devin-switch` | config profiles — single-job tool |
| `devin-skill-catalog` | capability vs product question parked (see secondary candidate above) |
| `devin-brain` (ex `devin-memory`) | foundation-adjacent persistence, no candidate sibling |
| `devin-pm` / `devin-office` / `devin-metrics` | evaluated *as F1 members*, not as their own families (pm/metrics has its own D-record) |
| `devin-bridge` + `devin-orchestrator` | merge explicitly disallowed — different runtime contracts |
| `devin-powerups` / `devin-internals-spec` / `awesome-devin` | control plane / foundation / navigation — structural layers, not products |
| `devin-devkit` | distribution, not a product (`homebrew-tap`/`scoop-bucket` deleted 2026-10-08 — orphaned, manual coverage 2/14, no external demand) |
| `poordjaevin` / `qwenpaw-suite` | adjacent projects with their own identities |
| `personal-agent-system` / `devin-dashboard` / `devin-learning` | private/system entries, not public product surface |

Numbers are canonical and drift-checked: **19 products**
(`nature: product`), **23 public entries**, **26 registry entries** —
the generated catalog counts derive from the registry and
`registry-drift.yml` gates them per push.

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

Caveat on the co-install probe: `devin-devkit install explore` measures
*installation unity* only. A negative result is weak evidence — users
may consume one member, receive a tool indirectly, or skip the bundle
over packaging preference while still treating the family as one
product in journeys and issues. No single signal decides.

### How signals are collected (active, weekly)

`tools/snapshot_baseline.py` (weekly `baseline-snapshot` workflow) now
writes a `boundary_signals` block per family:

| Signal | Sensor |
|---|---|
| cross-boundary confusion | issue cross-references: `search/issues` for sibling names inside each member repo |
| journey traversal | `traffic/popular/referrers` filtered to sibling repo URLs |
| adoption per member | existing views/clones/downloads series |

Structural blind spots, by design — read them correctly in December:

- **No co-installation metric exists.** The devkit has no telemetry and
  PyPI reports per package, not per install event. The audit must
  decide on confusion + traversal + identity plausibility, not on
  co-install counts.
- **`devin-graph` and `devin-janitor` were `source_only`** when written
  (both published 2026-10-09) — until download series accumulate they
  still emit no distinguishable signal. Zero was the design, not the
  evidence.
- Low-activity repos mean most series start at zero; first collected
  baseline already shows `devin-evals→qa-pack` cross-references (the
  boundary issue lives there). Direction and accumulation matter more
  than absolute counts.

## Audit decision rule (2026-12-03)

Per family, answer six questions from the signals above:

| Question | Evidence |
|---|---|
| Used together? | co-installation |
| Understood as one thing? | cross-repo confusion |
| Traversed as one task? | journey behavior |
| One identity plausible? | merged-description test |
| Real cost to staying split? | maintenance/discovery burden |
| Does merging break a boundary? | technical/security surface |

Three outcomes, all legitimate:

- **MERGE** — boundary reduction outweighs identity/deprecation cost.
- **KEEP** — independence is demonstrably useful.
- **REPOSITION** — structure works but identity/UX is wrong: change
  presentation (naming, journeys, READMEs, profiles) without touching
  repos. This is the likely answer when structure is sound but users
  still can't see the family as one thing — and it is the cheapest
  correction available, so it should be ruled *out*, not forgotten.
  Concrete forms per family:
  - *F1 explore*: a thin `devin-explore` dispatcher CLI delegating to
    history/search/graph; a shared "Explore family" banner across the
    three READMEs; one `awesome-devin` journey presenting them as a
    single walkthrough.
  - *F3 data*: "data lifecycle" documentation treating backup+janitor
    as one flow; coordinated `--help` output cross-referencing the
    sibling.
  - *F2 assure*: a `devin-assure` umbrella that runs qa-pack + evals as
    one CI experience; shared rubric vocabulary between the two.

These are product-boundary **hypotheses**, not merge candidates. The
audit may conclude "keep everything" — that is a finding, not a failure.

## What changes now vs after the window

- **Now (allowed):** this assessment, the `explore` devkit profile as a
  co-install probe, continued D07/D05/D09 work, baseline collection.
- **After 2026-12-03 (or on governance trigger):** decisions in ranking
  order F3 → F1 → F2, each as its own PR + D-record update with the
  evidence table filled.
