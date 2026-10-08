# Shared infra evaluation: paths / identity / vscdb (V4 §25)

Evaluated 2026-10-08 against the cloned ecosystem.

## Duplication map

| module | copies | state |
|---|---|---|
| `paths.py` | 11 | all variants drifted, 46–145 LOC each; devin-doctor's is the superset (`StorePaths`, `locate_stores`, credentials, locks) |
| `vscdb.py` | 3 | diverged readers of `state.vscdb` (117/124/174 LOC) |
| `identity.py` | 4 | graph/history/memory byte-identical; backup drifted |

## Where the code belongs

`devin-internals-spec` is the technical foundation and already ships a
`state.vscdb` parser (`parsers/state_vscdb.py::StateVscdbStore`). What it
does NOT ship is the locator layer — it takes `--devin-data-dir`
explicitly. The vendored `paths.py` modules all answer the same question:
where are Devin's stores on this OS (`%APPDATA%` / XDG / macOS Library).
That is spec territory, not product territory.

## Proposal

- **paths → internals-spec.** Add a `devin_internals.paths` module
  (data dir, config dir, `sessions_db`, `state_vscdb`, `acp_messages`
  locators) modeled on devin-doctor's superset. Consumers depend on
  `devin-internals-spec` already, so no new package is needed.
- **vscdb → migrate to the existing parser.** The three vendored readers
  predate `parsers/state_vscdb.py`; pm/metrics/graph should drop them.
- **identity → internals-spec.** Machine-id + profile env conventions are
  an ecosystem-wide contract; one copy, four consumers.
- **No new repo/package.** Extraction lands in internals-spec (candidate
  for its 0.4.0), migrations happen per-repo afterwards.

## Evidence note

The parallel sessions.db readers in pm (`vscdb.py`) and metrics
(`collect.py`) are the same shared-infra signal recorded in the
pm/metrics boundary D-record — extraction does not by itself argue for
merging the tools.
