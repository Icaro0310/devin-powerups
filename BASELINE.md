# P5 — Adoption & Reliability Baseline

**Window:** 2026-10-08 → 2026-12-03 (8 weeks).

P5 is a passive collection period, not an execution phase. No new
architecture topics, no physical merges, no taxonomy changes, no targets
or benchmarks — the plan explicitly bans inventing thresholds. The audit
on 2026-12-03 reads this data; until then, only obvious incidents warrant
attention (e.g. a tool that stops receiving clones due to a broken
release).

## What is collected

Per public registry repository:

- GitHub: stars, forks, watchers, open issues, open PRs
- GitHub traffic: views and clones over the trailing 14 days (unique counts)
- Package downloads (published entries only): PyPI via
  `pypistats.org`, npm via `api.npmjs.org` — both keyless

## How

```bash
python3 tools/snapshot_baseline.py --json snapshots/<date>.json --md
```

Suggested cadence: monthly, plus a final snapshot on 2026-12-03.
`n/a` means the source has not indexed the package yet (normal for fresh
publications), not a measurement failure.

## Day-1 snapshot (2026-10-08, registry v19)

| repo | stars | forks | open issues | open PRs | views 14d | clones 14d | CI pass 14d |
|---|---|---|---|---|---|---|---|
| awesome-devin | 1 | 0 | 1 | 0 | 15 (10u) | 322 (137u) | 0.889 (36 runs) |
| devin-backup | 1 | 0 | 0 | 0 | 15 (9u) | 560 (175u) | 0.902 (92 runs) |
| devin-bridge | 1 | 0 | 0 | 2 | 17 (8u) | 620 (185u) | 0.98 (100 runs) |
| devin-devkit | 0 | 0 | 0 | 0 | 3 (1u) | 256 (92u) | 0.943 (70 runs) |
| devin-doctor | 4 | 0 | 1 | 2 | 39 (25u) | 624 (171u) | 0.94 (100 runs) |
| devin-evals | 1 | 0 | 2 | 2 | 15 (6u) | 680 (199u) | 0.89 (100 runs) |
| devin-graph | 1 | 0 | 0 | 0 | 12 (7u) | 531 (182u) | 0.875 (96 runs) |
| devin-history | 1 | 0 | 1 | 2 | 17 (10u) | 573 (154u) | 0.95 (100 runs) |
| devin-internals-spec | 1 | 0 | 1 | 2 | 27 (16u) | 2578 (779u) | 0.96 (100 runs) |
| devin-janitor | 1 | 0 | 0 | 0 | 9 (4u) | 527 (169u) | 0.9 (100 runs) |
| devin-memory | 1 | 0 | 1 | 2 | 34 (19u) | 678 (232u) | 0.88 (100 runs) |
| devin-metrics | 1 | 0 | 0 | 0 | 9 (4u) | 567 (178u) | 0.92 (100 runs) |
| devin-office | 1 | 0 | 1 | 0 | 20 (5u) | 443 (199u) | 0.959 (49 runs) |
| devin-orchestrator | 1 | 0 | 0 | 0 | 21 (14u) | 448 (156u) | 0.966 (89 runs) |
| devin-pm | 1 | 0 | 0 | 0 | 10 (5u) | 521 (185u) | 0.933 (90 runs) |
| devin-powerups | 1 | 0 | 1 | 1 | 14 (5u) | 486 (203u) | 0.792 (53 runs) |
| devin-qa-pack | 1 | 0 | 5 | 0 | 46 (17u) | 943 (243u) | 0.97 (100 runs) |
| devin-redact | 1 | 0 | 0 | 1 | 17 (13u) | 874 (312u) | 0.94 (100 runs) |
| devin-search | 1 | 0 | 0 | 0 | 12 (8u) | 478 (164u) | 0.921 (89 runs) |
| devin-skill-catalog | 1 | 0 | 0 | 0 | 5 (2u) | 234 (105u) | 0.857 (28 runs) |
| devin-switch | 1 | 0 | 0 | 0 | 4 (2u) | 181 (72u) | 0.929 (28 runs) |
| homebrew-tap | 1 | 0 | 0 | 0 | 6 (4u) | 96 (49u) | 1.0 (6 runs) |
| poordjaevin | 6 | 0 | 2 | 0 | 33 (22u) | 521 (172u) | 0.984 (63 runs) |
| qwenpaw-suite | 1 | 0 | 0 | 0 | 9 (5u) | 180 (88u) | 1.0 (11 runs) |
| scoop-bucket | 1 | 0 | 0 | 0 | 6 (3u) | 125 (75u) | 1.0 (4 runs) |

| package | last day | last week | last month |
|---|---|---|---|
| @icaro0310/devin-bridge | — | — | n/a |
| devin-doctor | 7 | 107 | 100 |
| devin-fanout | 81 | 81 | 0 |
| devin-history | n/a | n/a | n/a |
| devin-internals-spec | 501 | 879 | 378 |
| devin-memory | 6 | 145 | 139 |
| devin-metrics | n/a | n/a | n/a |
| devin-pm | n/a | n/a | n/a |
| devin-qa-pack | 7 | 116 | 109 |
| devin-redact | 7 | 153 | 146 |
| poordjaevin | 94 | 94 | 0 |

**Collection errors:**
- `@icaro0310/devin-bridge`: 1 failed call(s)
- `devin-history`: 1 failed call(s)
- `devin-metrics`: 1 failed call(s)
- `devin-pm`: 1 failed call(s)

## Reading notes for the audit

- `devin-internals-spec` clone volume (2578/14d) is the expected outlier:
  every tool depends on it, so CI installs inflate clones. Compare like
  with like — spec vs spec, tool vs tool.
- Views/clones include automation (CI, devkit installs, refresh jobs).
  Unique counts are the better adoption signal.
- `open PRs` at day 1 are mostly Dependabot/review leftovers from the
  consolidation waves, not external contributions.
- PyPI `last_month` excludes the current month — `devin-fanout` and
  `poordjaevin` show real day-1 downloads with a 0 monthly figure. Read
  `last_day`/`last_week` for recent publications.
- `devin-powerups` CI pass rate (0.792) reflects the consolidation-merge
  churn of P3b; it is the control plane, not a consumer signal.
