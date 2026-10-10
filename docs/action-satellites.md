# Action satellites — per-repo design (D-2026-10-10d rollout)

The redact satellite proved the wiring (composite + pinned
`setup-python` + `pip install <published pkg>` + one CLI verb → exit
code), but the other three candidates are **not the same shape**. The
transplantable part is the mechanism; the subject being gated, the
inputs and the meaning of "fail" are per-satellite. This note fixes the
design before any repo is created — satellites are created one at a
time and each needs this section reviewed first.

| | subject gated | fail means | primary input |
|---|---|---|---|
| redact-action (done) | the checked-out repo | secrets found | `paths` |
| doctor-action | the **runner's** Devin environment | env has FAIL findings | dirs to check |
| judge-action | an **action artifact** (text describing a proposed operation) | proposed op is destructive | an action file |
| evals-action | a **corpus** of transcripts/records | corpus fails graders | a corpus dir |

## devin-doctor-action — environment assertion, not repo scan

`devin-doctor check` inspects the *machine's* Devin state
(`--data-dir`/`--config-dir`, sessions.db, config sanity) and exits 1
on any FAIL. On a fresh `ubuntu-latest` runner there is no Devin state
at all — the report FAILs, and that is the correct signal, not noise:
the action asserts "this runner can run Devin workloads", which is only
meaningful where one is expected.

Owner decision (2026-10-10): **post-install gate, not installer.** The
spec phrase "installation broken on the runner" reads as "an installed
Devin is unhealthy" — the action never installs Devin (that is
`devin-devkit` or a setup step's job); it asserts health of an install
that already exists.

Two legitimate consumers:

1. **Self-hosted / persistent runners** that host a real Devin install —
   the action is a drift check on the environment itself.
2. **Post-setup assertion** in devin-* CI — a job that installs the
   toolchain (or builds a devcontainer) calls the action to prove the
   environment ended up sane before the real steps run.

Design:

- `uses: Icaro0310/devin-doctor-action@v1`
- inputs: `data-dir`, `config-dir` (optional), `version`
  (`devin-doctor>=…,<…`), `fail-on-warn` (default `false`; FAIL findings
  always fail), `probe-network` (default `false` — no outbound calls in
  CI unless asked).
- outputs: `overall` (`PASS`/`WARN`/`FAIL`), `failures` (count).
- It does **not** checkout or scan repo content — no `paths` input.
- **Distinct failure messages (owner requirement):** "Devin not
  installed" is a violated precondition and must report differently
  from "installed but unhealthy" — otherwise the first hides the
  second. The action checks whether doctor finds a Devin install at
  all, then reports which of the two failures fired.
- **Smoke design:** richer than redact's — one consumer job can prove
  both states (clean runner → "not installed"; runner with an
  intentionally corrupted store → "unhealthy"), making it the first
  satellite whose failure paths are exercised per run.

## devin-judge-action — gate a proposed action, not the repo

`poordjaevin gate --action-file <f>` judges a described operation and
exits 1 ("block, require explicit confirmation") when it detects money
movement or data deletion. In CI the artifact is whatever the pipeline
produced that *describes an action*: a generated plan, a migration
description, a PR's ops summary. The gate answers "may this run
unattended?" — an advisory block, never an execution.

Backend decided by owner (2026-10-10): **local NLI, not ACP.** §2.18
declares "local NLI offline" as a property of the tool itself — forcing
ACP on the Action would contradict the package's own spec, and Devin
credentials on a runner mean credentials in every workflow of the repo,
including third-party PRs and any compromised dep in the graph. The
~400 MB model is cached via `actions/cache` keyed
`judge-model-<nli_version>`; annoying beats leaked.

- inputs: `action-file` (required — path to the artifact to judge),
  `version`, `backend`, `calibrator` (optional). `backend` accepts
  `local` only: ACP was considered and rejected by the owner decision
  above (runner credentials), so it is not an opt-in here — if a future
  use case ever needs ACP it gets its own documented input.
- outputs: `block` (bool), `verdict` (text).
- Fails when `block` is true *or* the backend errors — the CLI already
  fails closed (exit 1 on backend error), which is the right semantic
  for a gate.

## devin-evals-action — gate a corpus, not the repo

`devin-evals` grades recorded transcripts/records (no_secrets, no_pii,
exit codes, etc.). In CI it gates a **corpus**: regression-check a
checked-in fixture corpus, or publication-gate recorded sessions before
they ship. Without a corpus the action has nothing to do — so the
corpus path is the required input and the repo is only context.

- inputs: `corpus` (required — directory of transcripts), `version`,
  `fail-on-warn` analog if the graders expose severity tiers.
- outputs: pass/fail per grader category, finding count.
- BLOCKED means "the corpus fails graders" — e.g. a recorded session
  that leaks a secret, not secrets in the repo.
- CLI mapping: the action runs `devin-evals corpus verify --corpus
  $corpus` (golden-case grading). The weekly
  `devin-evals run --sessions-db ...` job is a different input path —
  regression replay of real sessions, not the CI corpus gate.

## Rollout

**Doctor → evals → judge (deferred).** Status 2026-10-10: `redact` and
`doctor` live (`v1`, smoke green); `evals` next; `judge` deferred.

- Judge and evals don't gate the repo — they gate *agent-produced
  artifacts* (execution logs, corpora). Verified 2026-10-10 across all
  workflows in the seven product repos plus powerups: **no CI job
  produces agent execution logs today** — zero invocations of
  `poordjaevin`, `sessions.db` capture, transcript artifacts or ACP
  calls. In an ordinary human PR a judge-action would have nothing to
  judge: fail-closed on missing input is noise, passing trivially is
  worse. So `devin-judge-action` is **deferred until a producer of
  agent artifacts exists in CI** — pre-commit + MCP cover the tool
  meanwhile. Recorded as owner-visible decision, not an agent call.
- Evals stays in the queue: it can gate the package's own fixture
  corpus as a meaningful regression input.
- Each satellite gets the same smoke treatment as redact: one consumer
  workflow in the owning repo proving install → verb → verdict → exit
  code, scoped so a clean run stays green, with a D-record line noting
  the smoke proves wiring, not product regression.
