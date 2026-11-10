# Incident log

Operational incidents and audit surprises across the ecosystem, newest
first. Each entry records what happened, the blast radius, and the lesson
that outlives the fix.

## 2026-11-10 — pr-approve v1.16 silent startup_failure (statuses:read)

- **What happened:** `pr-approve.yml@v1.16` (#279) declares `statuses:
  read` internally so the approve job can read commit statuses
  (`Devin Review`, `devin-judge/review`) and `arm-auto-merge` can inspect
  check state. `workflow_call` caps a called workflow's permissions by the
  *caller job's*, so any caller that bumped to v1.16 without granting
  `statuses: read` was rejected at workflow startup — a `startup_failure`
  with **no logs and no jobs**, invisible until someone read the run list.
  devin-state hit it first (26/26 runs down from the #120 bump until
  devin-state#123 added the grant). The same audit found four more callers
  in the broken state: the personal site (#53), devin-explore (#131),
  devin-control (#106) and devin-internals-spec (#75) — all fixed by
  adding `statuses: read` to the caller job permissions.
- **Blast radius:** every auto-approve gate on the affected repos was
  dead while looking "configured". PRs merged during the outage
  (devin-state#121, site#52) went through with the approval infrastructure
  fully down — the `--admin` merges were symptoms, not the cause.
- **Lesson:** reusable-workflow permissions are **static and caller-capped**
  — validated before any job runs, so there is no runtime `try/catch` and
  no "optional permission". A "tolerant reusable that skips the arm with a
  warning" is **not implementable** for this class: removing the
  declaration starves the token for *every* caller (approve goes
  permanently fail-closed), and keeping it hard-fails the startup for
  callers that omit the grant. The only durable guard is an audit that
  enumerates callers and fails loudly *before* the bump ships.
- **Follow-up:** `tools/check_pr_approve_callers.py` audits every registry
  checkout (+ `--extra-repo`) for `pr-approve.yml` pins >= v1.16 missing
  the grant, modelling the job-level-overrides-top-level permission
  semantics exactly; wired into `registry-drift.yml` so it runs on the
  fresh clones. Callers must keep `statuses: read` on the *calling job's*
  `permissions:` (a job block replaces the workflow-level one wholesale).

## 2026-10-28 — Open VSX audit confusion

- **What happened:** a publication audit checked only the VS Code
  Marketplace and reported "zero published" for the ecosystem's VS Code
  extensions. In reality all 7 extensions were already published on
  **Open VSX** (`open-vsx.org/icaro0310/*`) — a separate registry the
  audit never queried.
- **Blast radius:** misleading audit output only; the extensions were
  correctly published the whole time.
- **Lesson:** "is it published?" audits must enumerate **every** channel
  the ecosystem ships through — PyPI, npm, Open VSX, VS Code Marketplace,
  GitHub releases/tags, and the product site. A single-channel answer is
  a false negative by construction.
- **Follow-up:** `tools/ecosystem_sync.py` now covers all channels
  (Marketplace reported as `unavailable` until the Entra credential
  lands, instead of silently skipping).
