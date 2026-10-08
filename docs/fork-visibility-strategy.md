# Fork visibility strategy

Upstream awesome-list submissions measured by `tools/fork_visibility.py`
(weekly snapshot under `snapshots/forks-*.json`).

## Reading the funnel correctly

The day-1 snapshot shows 16 submitted PRs: 1 merged, 4 open,
11 closed-unmerged. All 11 closures were **author withdrawals** — every
closed PR's issue timeline names `Icaro0310` as the closing actor, in a
single batch on 2026-10-06 (verified per-PR via the GitHub timeline API
on 2026-10-08). The real funnel is: 5 live submissions, 1 accepted,
0 upstream rejections.

Do not report "69% rejection" — that misreads withdrawn PRs.

## Scope note

This is not a measurement conclusion deferred to the December audit —
it is a correction of mislabeled data plus operating rules for the
campaign itself. Acting on it (resubmissions, framing) is product work,
which the measurement window explicitly allows; what remains for the
audit is whether referral traffic moves.

## Rules for the campaign

- **Let the 4 open PRs play out.** MobinX, YuzeHao, yzfly and punkpeye
  still have pending submissions; punkpeye merged a PR within the last
  week, so that pipeline is alive.
- **Resubmit where the withdrawal was premature.** The withdrawn PRs
  targeted real lists (e2b-dev/awesome-ai-sdks, bradAGI, shalk,
  atinfo, awesome-obsidian). Each resubmission needs list-specific
  copy for its category, not the campaign template — "Add devin-X"
  titles read as self-promotion and get ignored.
- **Prioritize by fit.** devin-qa-pack belongs in test-automation and
  ai-coding lists; poordjaevin (the only merged entry) fits MCP-server
  lists; devin-evals now has a PyPI release, strengthening it where it
  was withdrawn (e2b-dev).
- **Rate-limit per upstream.** Some lists received several PRs from us
  at once (e2b-dev 2, bradAGI 2, shalk 2, punkpeye 3) — that density
  reads as a campaign sweep. Resubmit one tool per list at a time.
- **No new submissions until the open batch resolves.** Extra in-flight
  PRs add noise without signal; the December audit re-measures.

## Signals to watch in the weekly snapshot

- `open` aging past ~4 weeks → close and resubmit with better framing.
- `merged` count → the only number that matters for referral traffic.
- `other` PRs (non-promotional) stay excluded from the funnel.
