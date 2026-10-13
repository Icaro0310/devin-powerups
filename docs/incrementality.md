# Incrementality — one pattern, several surfaces (MÉDIO-1 spec)

Status: spec (2026-10-13). Implements the P2 cluster of
`BACKLOG.md` — not six features, one capability applied per surface.

## The pattern

Every incremental mechanism in the PAS reduces to **a cursor** plus a
consistent envelope. Three storage locations cover all cases:

| Shape | Cursor stored in | Used by | Cursor type |
|---|---|---|---|
| artifact-embedded | frontmatter/marker of each output file | history export (`last_activity:`), public `devin-history` | epoch / `last_activity_at` |
| state table in the output store | `idx_state`/`index_meta`/`extracted_sessions` inside the produced SQLite | search index, codegraph, public `devin-search`/`devin-graph` | path→mtime, source→max rowid |
| small JSON under `.devin/` | `<tool>-state.json` / `*-state.json` | learning loop, sweep, vault sync, mailbox | prompt-ids + byte offsets, epoch, rowids |

Cursor types: **file mtime** (doc indexers), **DB rowid / max
position** (search, sync), **epoch timestamp** (sweep windows,
`last_activity_at`), **prompt-id sets + byte offsets** (learning),
**sha256 digest of inputs** (dispatcher idempotency), **filesystem
markers** (mailbox `.done`).

## Envelope rules (all surfaces)

1. **Atomic write** — `tmp` + `os.replace`, never in-place.
2. **Cursor written after the work** — a crash re-scans; never skips.
3. **Fail-open** — cursor unreadable → full scan, exit 0 for
   observers.
4. **Env indirection** — `MEMORY_FILE`-style overrides; a `*_DISABLED`
   kill-switch where the mechanism writes.
5. **Idempotency on real input** — scheduled handlers declare
   `idempotency.disabled` (constant input would freeze the dedup key);
   dedup belongs downstream on actual input state.

## Shared helper

`devin_internals.cursor` (internals-spec) — the "build once":

```python
c = Cursor("learning-extract")          # .devin/<name>-state.json
c.get("last_rowid", 0)                  # typed defaults
c.set("last_rowid", 4120)               # buffered, not yet durable
c.commit()                            # atomic write, call AFTER work
```

Rules: JSON object only; `commit()` writes tmp+rename; missing/corrupt
file → empty state (fail-open); `DEVIN_CURSOR_DIR` overrides the
`.devin/` anchor (tests, vm-offload).

## Per-surface adoption

| Surface | Mechanism ported | Package | Status |
|---|---|---|---|
| `devin-history export --since` | artifact marker + session watermark | devin-explore/packages/history | shipped (#62) |
| `devin-learning extract` cursor | `learning-state.json` shape (rowid watermark per session) | devin-brain | shipped (#57) |
| `devin-search` doc corpus | `idx_state(path→mtime)` in the index DB — extends the existing index_meta model to vault docs | devin-explore/packages/search | spec'd, next wave |
| `metrics digest --weekly` | new: compose summary+daily+watch into a report file; cursor = last digest week | devin-assure/packages/metrics | shipped (#61) |
| trigger manifests as plan DAG | dispatcher schema (`.devin/catalog/triggers/*.yaml`) → plan input | devin-control | spec'd, next wave — biggest lift |
| `bundle export` | catalog bundle already carries state; incremental = manifest hash diff | devin-devkit/skill-catalog | shipped (#50) |
| `devin-pm digest` | session watermark + ISO week report | devin-explore/packages/pm | shipped (#65) |
| `devin-learning weekly-report` | aggregate-only public weekly report | devin-brain | shipped (#59) |

What is NOT incremental-but-missing: `devin-search index` and
`devin-graph build` are already incremental internally (rowid/ledger
watermarks) — the missing piece there is *corpus coverage*, a separate
item. `devin-janitor report` already shipped; `devin-backup
copy-to ssh://` is a P4 standalone, not a cursor problem.

## Verification per surface

Each adoption needs: a unit test that a second run skips unchanged
inputs (mtime/rowid stability), a corruption test (state file garbage
→ full rescan, no crash), and a kill-switch/env-override test where
the surface writes state.
