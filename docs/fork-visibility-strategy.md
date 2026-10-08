# Fork visibility strategy

Upstream awesome-list submissions measured by `tools/fork_visibility.py`
(weekly snapshot under `snapshots/forks-*.json`).

## Reading the funnel correctly

The day-1 snapshot shows 16 submitted PRs: 1 merged, 4 open,
11 closed-unmerged. The 11 closures were **author withdrawals** (closed
by Icaro0310 on 2026-10-06 in a single batch), not upstream rejections —
verified via the issue timeline on `punkpeye/awesome-mcp-servers#15779`.
So the real funnel is: 5 live submissions, 1 accepted, 0 rejected.

Do not report "69% rejection" — that misreads withdrawn PRs.

## Decisions

- **Let the 4 open PRs play out.** MobinX, YuzeHao, yzfly and punkpeye
  still have pending submissions. punkpeye merged PRs in the last week,
  so the pipeline is alive — no resubmission needed yet.
- **Resubmit where the withdrawal was premature.** The withdrawn PRs
  targeted real lists (e2b-dev/awesome-ai-sdks, bradAGI, shalk,
  atinfo, awesome-obsidian). Each resubmission must come with specific
  copy for that list's category, not the campaign template — generic
  "Add devin-X" titles read as self-promotion and get ignored.
- **Prioritize by fit, not volume.** devin-qa-pack belongs in
  test-automation and ai-coding lists; poordjaevin (the only merged
  entry) fits MCP-server lists best; devin-evals now has a PyPI release
  which strengthens its case where it was withdrawn.
- **One PR per list, one tool per PR.** The closed batch paired multiple
  tools per upstream; the surviving merged PR was a single-tool,
  category-matched submission. Repeat that shape.
- **No new submissions until the open batch resolves.** Extra in-flight
  PRs add noise without signal; the December audit re-measures.

## Signals to watch in the weekly snapshot

- `open` aging past ~4 weeks → close and resubmit with better framing.
- `merged` count → the only number that matters for referral traffic.
- `other` PRs (non-promotional) stay excluded from the funnel.
