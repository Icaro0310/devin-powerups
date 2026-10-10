# Environment compliance audit — 2026-10-10

Scope: every public repo of `github.com/Icaro0310` reachable from
`registry.json`, plus the local Linux host automation used to derive the
Windows/Linux migration map. Method: read-only discovery against checked-out
source and live GitHub state, then targeted remediation of verified defects.

Environments audited: `linux`, `personal_windows` (extended runtimes),
`corporate_windows` (local-only: no VM/QwenPaw, no Slack requirement, no
external compute/delegation, no mandatory external integrations; fail closed;
never OS-inferred).

Status vocabulary: `PASS` verified · `FAIL` reproducible defect ·
`PARTIAL` incomplete coverage · `NOT VERIFIED` insufficient evidence ·
`NOT APPLICABLE` with reason.

## Executive summary

- **One defect *class*, five instances, all fixed.** Every manifest-
  consuming code path was enumerated after the first two findings: gates
  present on the install path were absent on parallel paths.
  (1) `devin-doctor` fetched a pre-monorepo manifest path → live 404 →
  "registry unreachable" on every run (devin-explore#41).
  (2) `update`/`outdated` had no environment gate — corporate could
  force-install any remote tool with a PATH command (devin-devkit#36).
  (3) `update` had no platform gate and no prerequisite gate.
  (4) `update` force-reinstalled PATH commands it never installed,
  contradicting the documented never-overwrite contract — now `unmanaged`.
  (5) `freshness_hint` fired an outbound call without environment context —
  now silent under `corporate_windows` and `DEVIN_DEVKIT_OFFLINE=1`.
- **`_uv_tools_dir()` was wrong on Windows** — confirmed against uv docs:
  receipts live at `%APPDATA%\uv\data\tools`, not `~/.local/share/uv/tools`;
  channel-migration detection was silently dead on Windows. Fixed (+ XDG
  honor on Unix), covered by tests.
- **The class is closed by evidence, not just structure** — after the
  per-gate fixes, the duplicated gate logic was extracted into shared
  evaluators in `installer.py` (`evaluate_target`,
  `evaluate_requirements`), called by both paths. But structure alone
  is a claim, so `tests/test_gate_parity.py` pins it: a matrix asserts
  `build_plan` and `build_update_plan` hit the same canonical gate with
  identical details across env/platform/requirement scenarios, fires
  env-blocked even for a forbidden tool at the pinned version, and
  asserts the intentional divergences (preexisting vs unmanaged,
  install-blocked vs update-current) so they cannot drift either.
  Extraction to a dedicated `gates.py` is deferred — named debt in
  D-2026-10-10d.
- **Ordering is a distinct failure mode** — the env gate moved *before*
  the version-current short-circuit (a forbidden tool at the pinned
  version reported `current`, hiding the violation), and prerequisites
  gate only actual reinstalls (a current tool stays `current` even with
  uv/npm off PATH). Neither is visible to grep-style sweeps.
- **Windows default decided, not open** — `personal_windows` was the silent
  default when `--environment` was omitted, inverting the recorded
  safe-by-default rule. D-2026-10-10d requires explicit `--environment`
  on Windows hosts; implementation follows in a dedicated PR.
- **Corporate install path is enforced and tested** — `build_plan` rejects
  unsupported/delegation-capable tools before any install action, requires
  explicit `--environment`, and this is covered by installer tests.
- **Corporate runtime claim holds for installed products** — source
  inspection of devin-explore/assure/state/control/brain/judge found no
  required runtime network dependency; the documented exceptions are
  opt-in (`--online`, `DEVIN_*_OFFLINE` respected, ollama backend opt-in).
- **Docs drift is real but bounded** — devkit guides claimed "not yet on
  PyPI" (false as of 2026-10-10) and "profiles need no Git" (false for
  `devin-skill-catalog`). Fixed in devin-devkit#36.
- **Zscaler / real corporate proxy: NOT VERIFIED** — no corporate machine
  is reachable from this audit host. A reproducible test plan is included;
  nothing here claims proxy compatibility beyond source-level proxy/TLS
  handling.
- **Automation reality exists and is large** — 25 cron jobs + 8 systemd
  user services + 4 Devin hook events on the maintainer's Linux host, all
  mapped to Windows Task Scheduler equivalents via the PAS trigger
  catalog. None of it is created by the DevKit install (correct — install
  never schedules jobs).

## Findings (defects and drift)

| # | Repo / file | Sev | Evidence | Expected | Actual | Fix |
|---|---|---|---|---|---|---|
| 1 | devin-explore `packages/doctor/.../checks/updates.py:30` | high | live URL returned 404; correct path returns 200 | fetch `packages/devkit/src/devin_devkit/manifest.json` | fetched `src/devin_devkit/manifest.json` → always "registry unreachable" | **fixed** devin-explore#41 + regression test |
| 2 | devin-devkit `updater.py:build_update_plan` | high | signature had no env/platform; `cli.py` had no `--environment` on outdated/update | same per-tool env gate as installer | any remote tool with a PATH command could be force-installed on corporate | **fixed** devin-devkit#36 (`environment-blocked` actions, fail closed) |
| 3 | devin-devkit `cli.py` freshness hint | medium | `list` and install dry-run call `urlopen` to raw.githubusercontent.com, 15s | disclosed + suppressible on local-only machines | undisclosed network call during "preview" | **fixed** `DEVIN_DEVKIT_OFFLINE=1` in #36; documented in corporate guide |
| 4 | devin-devkit README{,.linux,.windows,.corporate-windows}.md | medium | `pypi.org/pypi/devin-devkit` → 200; manifest has `requires_git` for skill-catalog | current install instructions | "not yet on PyPI"; "profiles do not need Git"; bridge described as GitHub archive (it is npm) | **fixed** in #36 |
| 5 | devin-devkit `updater.py` PATH-only tools | medium | README "never overwrites an existing command" vs `update --apply` behavior | doc and code agree | `update` force-installed PATH commands not managed by devkit — the doc promised more than `update` delivered | **fixed** #36: PATH-only tools → `unmanaged`, never touched (even under `--force`); adoption requires manual removal first |
| 5b | devin-devkit `updater.py` platform gate | medium | `build_plan` rejects `host not in tool["platforms"]`; `build_update_plan` never checked | parallel paths apply the same gates | a linux-only remote tool present on a Windows PATH could get an update command | **fixed** #36: `unsupported` action |
| 5c | devin-devkit `updater.py` prerequisite gate | medium | installer blocks missing uv/npm/git/Node<20 at plan time; updater emitted commands that only fail at apply | fail closed at plan time | plan advertised `update` actions the machine could not run | **fixed** #36: `blocked` action with the missing prerequisite |
| 5d | devin-devkit `updater.py` env check ordering | low | env gate sat inside the version-compare branch | forbidden tools always report the violation | an env-forbidden tool at the pinned version reported `current`, hiding the breach | **fixed** #36: gate runs before the current short-circuit → `environment-blocked` |
| 5e | devin-devkit `freshness_hint` env context | medium | hint called from `list` and install dry-run without environment | corporate local-only = no gratuitous outbound calls | opt-out only via global env var; resolved environment ignored | **fixed** #36: hint suppressed for `corporate_windows`; `DEVIN_DEVKIT_OFFLINE=1` kept for other environments |
| 6 | devin-devkit `installer.py:129` corporate predicate | medium | `manifest.json` `devin-control` `requirements: ["node>=20","devin-cli"]` | all external needs gated | `requirements` field uninspected — but `devin-cli` is the *local* agent runtime, so rejecting it would be wrong; gate is correct as-is for declared delegation | no code change; documented |
| 7 | devin-devkit `--manifest` hidden flag | low | `cli.py:36` argparse.SUPPRESS | local manifest for dev | user-supplied manifest redefines all env metadata — enforcement is data-driven | noted; acceptable for a dev flag, no schema validation exists |
| 8 | devin-devkit `install_spec` unvalidated | low | `installer.py:177` | specs are registry-generated | a `-`-prefixed spec in a fetched manifest would parse as a uv flag (no shell, low impact) | recommended input validation, not done |
| 9 | devin-devkit `_uv_tools_dir()` | medium | uv docs: tools dir is `%APPDATA%\uv\data\tools` on Windows, `$XDG_DATA_HOME/uv/tools` or `~/.local/share/uv/tools` on Unix | match `uv tool dir` output | hardcoded Unix path → receipts never found on Windows → channel-migration detection silently dead | **fixed** #36 + unit tests; one `uv tool dir` run on the real Windows host remains as final confirmation |
| 10 | devin-assure `packages/qa-pack/adapters/mcp.py:52` | info | `DEFAULT_MCP_URL = https://mcp.devin.ai/mcp` | optional cloud audit adapter | hits hosted Devin MCP only when the adapter is invoked; not part of default local operation | documented; opt-in by design |
| 11 | devin-explore `capabilities.py:38` | info | `NET_PROBE_HOST = "1.1.1.1:443"`, honors `HTTPS_PROXY` | diagnostic-only probe | one outbound TCP connect when `capabilities` runs; documented in doctor README | documented; diagnostic, not a dependency |
| 12 | Stray `nul` file in devin-ecosystem/ | low | file existed at workspace root | not present | Windows `> nul` redirect artifact | removed locally during audit (was never committed) |

### Verified *non*-findings (checked and clear)

- `DEVIN_DOCTOR_OFFLINE` and the `devin-doctor` CLI/PyPI name are **still
  correct** — the rename changed the *repo*, not the package; the generated
  `README.corporate-windows.md` text is accurate (`updates.py:138` honors it).
- All 13 archived repos carry a **MOVED banner** pointing at the successor
  monorepo (verified live via GitHub API, e.g. `devin-orchestrator` →
  `packages/orchestrator` in devin-control).
- No secrets, tokens, private hostnames or personal absolute paths in any
  public repo's tracked files (grep sweep; the one hit was a synthetic eval
  corpus DB flagged `synthetic_only: true`).
- GitHub redirects resolve correctly: `devin-doctor`→`devin-explore`,
  `devin-bridge`→`devin-control`, `devin-memory`→`devin-brain`,
  `devin-qa-pack`→`devin-assure` (all 301).
- Registry `repositories[].environments` present for public executables;
  `corporate_windows` entries carry runtime/delegation/external_dependencies
  metadata and qwenpaw-suite is `supported: false` with a reason.

## Environment compatibility (install-time vs runtime)

| Artifact | Install-time network | Runtime network | linux | personal_win | corporate_win |
|---|---|---|---|---|---|
| devin-devkit (installer) | pypi.org, github.com (git+https for skill-catalog), registry.npmjs.org (bridge) | manifest freshness GET → raw.githubusercontent.com on `list`/dry-run/`outdated`/`update` (now skippable via `DEVIN_DEVKIT_OFFLINE=1`) | extended | extended | local-only w/ gate |
| devin-explore (doctor/history/search/graph/pm) | pypi.org | none required; doctor `capabilities` probes 1.1.1.1:443-or-proxy (diagnostic); doctor `check` fetches manifest (was broken, now fixed; `DEVIN_DOCTOR_OFFLINE=1`) | extended | extended | local-only |
| devin-assure (qa-pack/evals/metrics) | pypi.org | none required; `--online` HEAD checks opt-in; MCP adapter → mcp.devin.ai opt-in | extended | extended | local-only |
| devin-state (backup/janitor/redact) | pypi.org | none found; `devin-backup install` can self-schedule a cron/Task Scheduler job — user-initiated, document before using on corporate | extended | extended | local-only |
| devin-control (bridge/orchestrator/switch/office) | registry.npmjs.org (bridge), pypi.org | ACP/stdio to local Devin CLI; office binds a local dashboard port when run | extended | extended | local-only (requires devin-cli present) |
| devin-judge (poordjaevin) | pypi.org; **model download** (~transformers/torch) on first NLI use | local_nli default offline; ollama backend → OLLAMA_HOST (localhost default, opt-in); acp backend → local Devin CLI | extended | extended | conditional: NLI model must be staged; default path offline |
| devin-brain (devin-memory) | pypi.org | none found | extended | extended | local-only |
| qwenpaw-suite | source-only | external runtime (VM/ollama) | optional | optional | **unsupported** (registry reason present) |
| devin-office (pkg in devin-control) | source-only | local dashboard listener | optional | optional | manual (not in installable profiles) |

## Zscaler / corporate-network readiness — NOT VERIFIED

No corporate/Zscaler host was available. Source-verified behavior:

- `uv`/`pip`/`npm`/`git` honor `HTTPS_PROXY`/`HTTP_PROXY` env vars; Python
  `urllib` calls (devkit freshness, doctor updates, judge ollama) inherit
  system proxy envs automatically.
- TLS trust: Python uses system/certifi stores; `REQUESTS_CA_BUNDLE` is
  honored by `requests`-based code only — `urllib.request` (used by devkit,
  doctor, judge) uses `ssl.create_default_context()` → reads the **Windows
  system store**, meaning a Zscaler root CA installed via IT's normal
  mechanism (group policy → Trusted Root) works without `*_CA_BUNDLE`
  overrides. `uv` reads `SSL_CERT_FILE`/`UV_NATIVE_TLS`. npm reads
  `NODE_EXTRA_CA_CERTS` or `npm config cafile`.
- No component disables TLS verification anywhere in source (grep: no
  `verify=False`, `--insecure`, `NODE_TLS_REJECT_UNAUTHORIZED=0`).

Reproducible test plan for the corporate machine (run behind the real proxy):

```powershell
# stage: fetch through the proxy, not just inspect the CA store —
# urllib honors HTTPS_PROXY and validates the Zscaler chain end-to-end
python -c "import urllib.request;print(urllib.request.urlopen('https://pypi.org',timeout=10).status and 'ca+proxy ok')"
uv tool install devin-devkit
$env:DEVIN_DEVKIT_OFFLINE="1"; devin-devkit list   # offline path
Remove-Item Env:DEVIN_DEVKIT_OFFLINE
devin-devkit install qa --environment corporate-windows   # dry-run; note which hosts the plan needs
devin-devkit install qa --environment corporate-windows --apply
devin-doctor check   # exercises the fixed manifest fetch
$env:DEVIN_DOCTOR_OFFLINE="1"; devin-doctor check   # must skip the network call
```

Allowlist candidates if installs fail: `pypi.org`, `files.pythonhosted.org`,
`registry.npmjs.org`, `github.com`, `codeload.github.com`,
`raw.githubusercontent.com`, `astral.sh` (uv installer),
`nodejs.org`/`registry.npmjs.org` (Node).

## Automation inventory (summary; full catalog in AUTOMATION-CATALOG.md)

- **Maintainer Linux host (verified live):** 25 cron entries + 8 systemd
  user services + 4 Devin hook events. All referenced scripts exist.
  Categories: session lifecycle (sweep/janitor/history-export/learning),
  ops (answer-runner, discussion-scout, fork-janitor, ci-watch, geo-audit,
  weekly-testgen, weekly-scout, gsc-report), memory/vault (obsidian-recall,
  watchdog, vault-compressor, memory-rollup), VM ops (keepalive, backup,
  uptime, ollama tunnel, reverse tunnel), monitoring (ecosystem-health,
  office-freshness, mailbox-wake, gh-notif-silence, laptop_reporter),
  Djævin (nightly quiz, weekly calibration).
- **Repo-side automation:** 50 trigger definitions in PAS
  `.devin/catalog/triggers/*.yaml` (each carries the Windows Task Scheduler
  name it replaces); ~82 scripts in PAS `scripts/` + `heartbeat/`;
  `session-dispatcher.py` is the event→handler router.
- **CI schedulers (verified):** powerups registry-drift/refresh,
  contract-check, baseline-snapshot, weekly-repo-report, codeql, scorecard;
  devkit manifest-sync; per-repo links/cflite/scorecard crons.
- **Corporate boundary:** all PAS automation is personal-environment
  tooling (Slack, VM, LLM backends, personal paths) and is correctly
  *absent* from the corporate install path — the DevKit creates zero
  scheduled jobs on any environment.

## Validation performed

| Command | Env | Result |
|---|---|---|
| `pytest packages/devkit/tests` (devin-devkit) | Linux, this host | 55 passed (incl. 14 new gate/path/ordering tests) |
| `uv tool dir` vs `_uv_tools_dir()` | Linux, this host | match: `~/.local/share/uv/tools` |
| `pytest tools/` (devin-powerups) | Linux, this host | 327 passed |
| `uv run pytest packages/doctor` (devin-explore) | Linux, this host | 101 passed (incl. manifest-URL regression test) |
| `curl` manifest URLs | live | old path 404 → new path 200 |
| `gh api repos/.../readme` ×3 | live | archived repos all carry MOVED banners |
| `curl` GitHub repo redirects ×5 | live | all 301 to correct successors |
| `pypi.org/pypi/{devin-devkit,devin-skill-catalog}` | live | both 200 |
| crontab/systemd/hook script existence | this host | every referenced path exists and is executable |

NOT VERIFIED: anything Windows (no Windows host — `_uv_tools_dir` is
doc-verified, one `uv tool dir` run left as confirmation), Zscaler (no
proxy environment), real `uv tool install` of every profile end-to-end on
a clean machine, npm bridge install.

## Changes made by this audit

| Repo | Branch/PR | Change |
|---|---|---|
| devin-explore | fix/doctor-manifest-url → **PR #41** | manifest URL → monorepo path + regression test |
| devin-devkit | fix/update-environment-gate → **PR #36** | env gate on update/outdated + `--environment` + platform/prereq/unmanaged gates + shared `evaluate_target`/`evaluate_requirements` pipeline + `DEVIN_DEVKIT_OFFLINE` + `_uv_tools_dir` Windows/XDG fix + doc corrections (PyPI/git/bridge) |
| devin-powerups | docs/audit-2026-10-10 | this report + automation catalog + bootstrap guide |

## Remaining risks / blockers

1. ~~`update` force-installs PATH-present unmanaged tools~~ — **resolved**
   (finding 5, `unmanaged` action in #36).
2. Windows-default environment `personal_windows` — **decided**: explicit
   `--environment` required on Windows hosts (DECISIONS.md D-2026-10-10d);
   implementation is a dedicated follow-up PR, not yet code.
3. Zscaler compatibility is source-verified only; the test plan above must
   run on the real corporate machine before claiming compliance.
4. `_uv_tools_dir` — **resolved at source level** (finding 9); on-machine
   `uv tool dir` confirmation still pending on a Windows host.
5. `devin-judge`'s NLI backend downloads model weights on first use —
   install-time on personal, but on corporate it must be staged/documented
   or the judge runs backend-less.
6. `install_spec` is not validated against flag-like values (finding 8) —
   low impact, recommended hardening.
