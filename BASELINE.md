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

| repo | stars | forks | open issues | open PRs | views 14d | clones 14d |
|---|---|---|---|---|---|---|
| awesome-devin | 1 | 0 | 1 | 0 | 15 (10u) | 322 (137u) |
| devin-backup | 1 | 0 | 0 | 0 | 15 (9u) | 560 (175u) |
| devin-bridge | 1 | 0 | 2 | 2 | 17 (8u) | 620 (185u) |
| devin-devkit | 0 | 0 | 0 | 0 | 3 (1u) | 256 (92u) |
| devin-doctor | 4 | 0 | 3 | 2 | 39 (25u) | 624 (171u) |
| devin-evals | 1 | 0 | 4 | 2 | 15 (6u) | 680 (199u) |
| devin-graph | 1 | 0 | 0 | 0 | 12 (7u) | 531 (182u) |
| devin-history | 1 | 0 | 3 | 2 | 17 (10u) | 573 (154u) |
| devin-internals-spec | 1 | 0 | 3 | 2 | 27 (16u) | 2578 (779u) |
| devin-janitor | 1 | 0 | 0 | 0 | 9 (4u) | 527 (169u) |
| devin-memory | 1 | 0 | 3 | 2 | 34 (19u) | 678 (232u) |
| devin-metrics | 1 | 0 | 0 | 0 | 9 (4u) | 567 (178u) |
| devin-office | 1 | 0 | 1 | 0 | 20 (5u) | 443 (199u) |
| devin-orchestrator | 1 | 0 | 0 | 0 | 21 (14u) | 448 (156u) |
| devin-pm | 1 | 0 | 0 | 0 | 10 (5u) | 521 (185u) |
| devin-powerups | 1 | 0 | 0 | 0 | 14 (5u) | 486 (203u) |
| devin-qa-pack | 1 | 0 | 5 | 0 | 46 (17u) | 943 (243u) |
| devin-redact | 1 | 0 | 1 | 1 | 17 (13u) | 874 (312u) |
| devin-search | 1 | 0 | 0 | 0 | 12 (8u) | 478 (164u) |
| devin-skill-catalog | 1 | 0 | 0 | 0 | 5 (2u) | 234 (105u) |
| devin-switch | 1 | 0 | 0 | 0 | 4 (2u) | 181 (72u) |
| homebrew-tap | 1 | 0 | 0 | 0 | 6 (4u) | 96 (49u) |
| poordjaevin | 6 | 0 | 2 | 0 | 33 (22u) | 521 (172u) |
| qwenpaw-suite | 1 | 0 | 0 | 0 | 9 (5u) | 180 (88u) |
| scoop-bucket | 1 | 0 | 0 | 0 | 6 (3u) | 125 (75u) |

| package | downloads last month |
|---|---|
| @icaro0310/devin-bridge | n/a (npm stats not yet indexed) |
| devin-doctor | 100 |
| devin-fanout | 0 |
| devin-history | n/a (pypistats not yet indexed) |
| devin-internals-spec | 378 |
| devin-memory | 139 |
| devin-metrics | n/a (published today) |
| devin-pm | n/a (pypistats not yet indexed) |
| devin-qa-pack | 109 |
| devin-redact | 146 |
| poordjaevin | 0 |

## Reading notes for the audit

- `devin-internals-spec` clone volume (2578/14d) is the expected outlier:
  every tool depends on it, so CI installs inflate clones. Compare like
  with like — spec vs spec, tool vs tool.
- Views/clones include automation (CI, devkit installs, refresh jobs).
  Unique counts are the better adoption signal.
- `open PRs` at day 1 are mostly Dependabot/review leftovers from the
  consolidation waves, not external contributions.
