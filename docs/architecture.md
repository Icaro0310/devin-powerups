# Architecture — the devin-* ecosystem

> Source of truth: `registry.json` (validated by `registry.schema.json`,
> drift-checked by `registry-drift.yml`). This document narrates the
> structure; when it disagrees with the registry, the registry wins.

## The shape

19 first-party tools consolidated into **7 products** grouped by
**4 public jobs**, plus 1 foundation, 1 infrastructure hub and 2
related/external entries.

```text
Job          Product             Member packages
───────────  ──────────────────  ──────────────────────────────────
Understand   devin-explore       doctor · history · search · graph · pm
Verify       devin-assure        qa-pack · evals · metrics
             devin-judge         poordjaevin
Control      devin-control       bridge (npm) · orchestrator (devin-fanout)
                                  · switch · office
             devin-state         redact · backup · janitor
                                  · install-scheduler (shared)
             devin-brain         devin-memory (MCP)
Build        devin-devkit        devkit · skill-catalog

Foundation   devin-internals-spec   access layer over Devin local stores
Infra        devin-powerups         registry, generators, reusable workflows
Related      qwenpaw-suite · devin-dashboard   (outside the product surface)
```

## Layers and direction of dependencies

```text
           awesome-devin / site / profile README   (generated surfaces)
                          ▲
           devin-devkit  ── registry manifest → installs products
                          ▲
        ┌─────────────────┼──────────────────┐
   Understand          Verify            Control          (products)
        └─────────────────┼──────────────────┘
                          ▲
              devin-internals-spec                        (foundation)
                          ▲
              Devin local stores (sessions.db, vscdb)     (not ours)
```

- Products may depend on `devin-internals-spec` (declared per package in
  `package.depends_on`) — never on each other.
- `devin-powerups` is the semantic/control plane: it produces the
  registry, generates public surfaces, and hosts the reusable
  `pypi-publish.yml` workflow the products call. Products do not import
  it at runtime.
- `devin-devkit` is the distribution layer: it reads the generated
  manifest and installs product packages via `uv` (PyPI or git
  subdirectory) plus the npm bridge.

## Product boundaries

Each product is a monorepo under `packages/<pkg>/`; absorbed standalone
repos keep their history via subtree merges and redirect with `MOVED`
banners. The mapping old repo → product lives in `BASELINE.md`; the
rationale per consolidation in `DECISIONS.md` (D-records F4.1–F4.5).

Ownership is explicit in `registry.json`:

- `product_id` ties member entries to their holder repo.
- `ownership` classifies relationship to the first-party surface.
- `mode` (`read` / `write` / `mixed`) declares mutation behavior.
- `distribution_status` (`published` / `source_only` / `pending`)
  declares the install channel honestly — a package only claims
  `published` after a real registry release exists.

## Generated surfaces

Everything a reader or an LLM sees is derived from the registry:

```text
registry.json
  ├─ render_catalog.py        → profile README catalog table
  ├─ render_surfaces.py       → intent map, browse axes, journeys,
  │                             per-repo ECO + 'Where this fits' blocks
  ├─ render_compatibility.py  → devin-devkit/COMPATIBILITY.md
  ├─ render_llms.py           → site llms.txt / llms-full.txt catalog blocks
  ├─ export_devkit_manifest.py→ devin-devkit manifest.json
  └─ update_eco_blocks.py     → splices generated blocks into READMEs
```

Generated regions live between `DEVIN-*` / `LLMS` markers; narrative
outside the markers is hand-written. `registry-drift.yml` clones every
public repo and fails when any generated surface diverges.

## Governance — adding or changing a product

1. Edit `registry.json` only (schema-validated).
2. If a rubric says KEEP to a family, the `product_id` is not created —
   the registry reflects state, never anticipates a vision.
3. Regenerate surfaces with the tools above; let `registry-drift.yml`
   prove they match.
4. Consolidations require: subtree merges (no squash), path-scoped CI,
   per-package publish workflows, `MOVED` banners on archived repos,
   and a rollback rehearsal (revert chain → zero diff) before merge.
5. Every non-trivial boundary call gets a D-record in `DECISIONS.md`.

## Known asymmetries (honest notes)

- `devin-control` is polyglot: `bridge` is Node/npm, the rest Python/uv.
- `devin-office` ships source-only inside devin-control (manual install).
- `devin-switch`, `devin-skill-catalog`, `devin-devkit` may sit at
  `source_only` while PyPI rate limits clear — DevKit installs them via
  git subdirectory specs until then.
- Package names are preserved for continuity (e.g. `devin-redact` lives
  in the `devin-state` product; `devin-fanout` is the orchestrator).

## See also

- `BASELINE.md` — pre/post consolidation repo map, measurement plan
- `DECISIONS.md` — all D-records
- `GOVERNANCE.md` — contribution and review rules
- `docs/evidence-equivalence.md` — gate for the official-API adapter
- `docs/product-boundaries.md` — merge/split rubric
