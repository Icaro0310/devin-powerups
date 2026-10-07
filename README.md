<div align="center">

<img src="assets/banner.svg" alt="devin-powerups" width="100%"/>

<a href="https://scorecard.dev/viewer/?uri=github.com/Icaro0310/devin-powerups"><img src="https://api.scorecard.dev/projects/github.com/Icaro0310/devin-powerups/badge" alt="OpenSSF Scorecard"/></a>
<a href="https://deepwiki.com/Icaro0310/devin-powerups"><img src="https://deepwiki.com/badge.svg" alt="DeepWiki"/></a>
<a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green" alt="License: MIT"/></a>
<a href="https://www.python.org/"><img src="https://img.shields.io/badge/python-3.10%2B-blue" alt="Python 3.10+"/></a>
<a href="https://github.com/Icaro0310/devin-powerups"><img src="https://img.shields.io/github/stars/Icaro0310/devin-powerups" alt="GitHub stars"/></a>
<a href="https://github.com/Icaro0310/devin-powerups/commits/main"><img src="https://img.shields.io/github/last-commit/Icaro0310/devin-powerups" alt="Last commit"/></a>
<a href="https://github.com/Icaro0310/awesome-devin"><img src="https://img.shields.io/badge/part%20of-devin--*-ecosystem-7c3aed" alt="devin-* ecosystem"/></a>
<a href="https://github.com/Icaro0310/devin-powerups/issues"><img src="https://img.shields.io/badge/PRs-welcome-brightgreen" alt="PRs welcome"/></a>
</div>

# devin-powerups

> Unofficial community tooling for Devin. Not affiliated with, endorsed by, or
> sponsored by Cognition AI. Devin is a Cognition AI trademark.
>
**[Linux](README.linux.md)** · **[Personal Windows](README.windows.md)** · **[Corporate Windows](README.corporate-windows.md)** · English

Part of the [awesome-devin](https://github.com/Icaro0310/awesome-devin) ecosystem: the curated hub for the devin-* tools.

A public maintainer hub for the Devin community projects. It contains the
machine-readable catalog, platform-doc and manifest exporters, a starter
template, a local scaffolder, and the weekly report generator. End users can
install tools individually or choose profiles through the separate `devin-devkit`
distribution; this hub is not needed at runtime.

## What's included

| Path | Purpose |
|---|---|
| `registry.json` | Catalog of public projects plus clearly marked maintainer-only records. `kind` records the repository's structural role, while `artifact`, `interfaces`, `audiences`, `platforms` and `environments` classify what each public artifact is, who it serves and which runtime guarantees it supports. The weekly public report filters to `kind=project` and `visibility=public`. |
| `template/` | Starter repository with a shared README, Windows/Linux guides, a planned macOS guide, and CI. |
| `tools/new-repo.py` | Creates a new `devin-<name>` sibling checkout from the template, initializes Git and registers the repo in `registry.json` (schema-validated before writing). `--dry-run` previews without side effects. It does not create a GitHub repository or push. |
| `tools/weekly_repo_report.py` | Reads public GitHub commit metadata from the registry and writes a standalone HTML report. Email delivery is optional. |
| `tools/validate_registry.py` | Validates `registry.json` against `registry.schema.json` — dependency-free, exits non-zero on violations. |
| `tools/reconcile_registry.py` | Reconciles the registry against the GitHub account and local clones: missing entries, missing repos, stale version/tag fields. Read-only. |
| `tools/export_devkit_manifest.py` | Exports the public, profile-based DevKit manifest; rejects private or unknown repositories. |
| `tools/render_catalog.py` | Renders the profile README catalog and count from the same registry. |
| `tools/render_compatibility.py` | Renders the Linux / Personal Windows / Corporate Windows compatibility matrix from registry environment metadata. |
| `tools/migrate_platform_docs.py` | Dry-run by default; creates OS-specific guides and replaces old language navigation only with `--apply`. |
| `tools/hooks_dispatch.py` | The F5 hook dispatcher: one Devin hook command fans out to handlers registered in `.devin-ecosystem/hooks.json` under the Devin config dir, instead of every repo installing its own hook. Never fails the hook (abort contract: handler exit 42), per-handler + global timeouts, JSONL dispatch log. |
| `registry.schema.json` | JSON Schema (2020-12) for `registry.json`. |
| `capability-profile.schema.json` + `docs/capability-profile.md` | The F10 contract: `corporate` (fail-closed default) vs `personal` machine profiles, capability keys, and how extras declare `requires:`. |
| `.github/workflows/` | Per-project CI template and optional workflows for uploading/emailing reports that already exist. |

The local scout/ideation engine is not included in this public repository. The
notification workflows only deliver report files supplied by the maintainer;
they do not run discovery, tests, or agent sessions.

## The method

Each project adapts a proven tool with one Devin-specific capability that:

1. does something the base tool cannot do;
2. disappears when Devin is removed; and
3. can be explained in one sentence.

The ecosystem tools are local-first and send no telemetry. Read-only by default
where applicable; mutating operations are explicit, guarded and dry-run first
where supported.

## Run the maintainer tools

Requirements: Python 3.10 or newer and Git. The scripts use the Python standard
library. `gh` is optional and only needed if you choose to create a hosted repo
after scaffolding.

**Windows (PowerShell):**

```powershell
py -3 tools/new-repo.py history "Export and audit Devin session history"
py -3 tools/weekly_repo_report.py --days 7 --out report\weekly-repo-report.html
```

**Linux:**

```bash
python3 tools/new-repo.py history "Export and audit Devin session history"
python3 tools/weekly_repo_report.py --days 7 --out report/weekly-repo-report.html
```

`new-repo.py` takes `<name> "<description>"` plus options. It validates a
kebab-case name, creates a sibling `devin-<name>` from `template/`, runs
`git init -b main`, then appends the repo to `registry.json` — the merged
document is validated against `registry.schema.json` before anything is
written, so a schema violation aborts with zero side effects. `--dry-run`
prints the files it would create and the registry entry it would append
without touching anything; `--no-register` scaffolds only. `--kind`,
`--visibility` and `--wave` override the registry defaults
(`project`/`public`/`0`). Environment metadata defaults to a local tool that
supports all three environments; use `--unsupported-environment ENV=reason`,
`--requires-delegation`, `--requires-devin-vm` or
`--requires-external-integration NAME` when the new artifact has different
runtime guarantees. It does not create a GitHub remote. Review the
generated files and choose the remote/visibility yourself.

`weekly_repo_report.py` uses the GitHub public commits API. `GITHUB_TOKEN` is
optional and can increase rate limits. Its options are:

| Option | Purpose |
|---|---|
| `--registry PATH` | Registry JSON to read (default: this repo's `registry.json`). |
| `--out PATH` | HTML report destination. |
| `--days N` | Look-back window (default: 7). |
| `--max-commits N` | Display cap per repo (default: 25). |
| `--timeout SECONDS` | HTTP timeout (default: 15). |
| `--send HTML --to ADDRESS --from "Name <verified-address>"` | Email an existing report; requires the SMTP secrets and `REPORT_SENDER`. |

Both tools can be run from PowerShell or a Linux shell with the commands above.

## Hook dispatcher (F5)

Devin hooks (`hooks` in `config.json`, or project `.devin/hooks.v1.json`)
run one shell command per event. `tools/hooks_dispatch.py` is that one
command — it fans out to handlers registered declaratively in
`<config-dir>/.devin-ecosystem/hooks.json` so individual repos do not need
their own hook entries:

```json
{"version": 1,
 "handlers": {"SessionStart": [
    {"id": "my-handler", "command": "python tools/x.py",
     "timeout_seconds": 30, "enabled": true,
     "profile": "any", "requires": ["daemon"]}]}}
```

Install it once as the hook command, e.g.
`python tools/hooks_dispatch.py dispatch SessionStart`. The config dir
resolves to `--config-dir`, then `DEVIN_CONFIG_DIR`, then
`%APPDATA%\Devin` (Windows) or `~/.config/Devin`/`~/.config/devin` (Linux).

| Subcommand | Purpose |
|---|---|
| `dispatch <event>` | Runs enabled handlers sequentially. Whatever the hook pipes to stdin is read once (bounded — it never blocks on input) and forwarded verbatim to every handler. Always exits 0, so a failing handler never breaks the session — the documented abort contract is a handler exiting **42**, which stops the fan-out and makes the dispatcher exit 42. Per-handler `timeout_seconds` defaults to 30 s; a hard global cap of 120 s bounds one dispatch. Every evaluated handler appends one JSONL record (`ts`, `iso`, `event`, `handler`, `status`, `exit_code`, `duration_ms`) to `.devin-ecosystem/hook-fires.jsonl`. |
| `list [--event E] [--json]` | Show registered handlers per event. |
| `check` | Validate the registry shape (0 valid / 1 invalid / 2 unreadable, like `validate_registry.py`). |
| `register <event> <id> "<command>" [--timeout N] [--requires CAP,...] [--profile P] [--disabled] [--force]` | Add a handler entry — files only, no side effects. |
| `unregister <event> <id>` | Remove a handler entry. |

Skipping rules: `enabled: false` skips; `profile` restricts a handler to
one machine profile; a non-empty `requires` capability list (e.g.
`["daemon"]`) skips the handler on the `corporate` profile. The machine
profile resolves the same way as devin-doctor (F10):
`DEVIN_ECOSYSTEM_PROFILE` > `devin-profile.json` in the config dir >
`corporate` (fail-closed).

## Weekly public report

The `weekly-repo-report` GitHub Actions workflow runs on Sundays and can also be
started with `workflow_dispatch`. It uploads an HTML artifact containing only
public projects selected from `registry.json`.

Optional email delivery requires these GitHub Actions repository secrets:

- `MAILERSEND_SMTP_HOST`
- `MAILERSEND_SMTP_PORT`
- `MAILERSEND_SMTP_USER`
- `MAILERSEND_SMTP_PASSWORD`

It also requires these repository variables:

- `REPORT_RECIPIENT`: destination address;
- `REPORT_SENDER`: a sender identity verified with your mail provider.

If any setting is missing, the workflow keeps the report artifact and skips the
email. No recipient or sender address is hardcoded in the public source.

The `scout-notify` and `testgen-notify` workflows email a maintainer-supplied
report (passed as a workflow input) when manually dispatched — reports are not
stored in this repository. A fork configures its own secrets/variables.

## Registry and privacy

The registry distinguishes public projects from maintainer-only records and
treats every repository as an artifact. `artifact=tool` marks user-facing
products (the first-party `devin-*` entries); `distribution`,
`infrastructure`, `suite` and `resource` separate the DevKit, hub, related
collections and discovery documents from tools. `interfaces`, `audiences`,
`platforms` and `environments` provide the metadata generators need for
catalogs, installation profiles, audience filters and runtime-compatibility
matrices. The weekly report filters to public projects
and does not read private repository contents. Personal paths, credentials,
service addresses and session data do not belong in this public repository.

## Works with Devin alone (Devin-only mode)

The hub itself is optional — every tool in `registry.json` installs and runs
standalone. What runs locally with zero external services:

- `registry.json` — plain JSON; read it, filter it, script against it.
- `tools/validate_registry.py` — schema-validates the registry, no deps.
- `tools/hooks_dispatch.py` — hook fan-out is fully local: reads
  `.devin-ecosystem/hooks.json`, runs registered shell commands with
  subprocess timeouts, appends to `hook-fires.jsonl`. No network, no
  input prompts.
- `tools/reconcile_registry.py` — audits registry vs GitHub vs local
  clones. It shells out to `gh` for GitHub data, so it needs `gh auth` or
  `GITHUB_TOKEN`; without them it still reports local-only findings.
- `tools/new-repo.py` — scaffolds a local checkout and registers it in
  `registry.json` (`git init` only, no GitHub calls; creating a remote is a
  separate, explicit step). `--dry-run` is side-effect free.
- `tools/weekly_repo_report.py --out report.html` — writes a standalone HTML
  report. It reads the public GitHub commits API, so it needs unauthenticated
  network access to `github.com` (`GITHUB_TOKEN` only raises rate limits).
- The `--send` email step and the GitHub Actions workflows are optional
  maintainer add-ons. Skip them freely — they need *your* SMTP secrets, not
  ours. On a locked-down machine, running the generator locally on a schedule
  (cron or Task Scheduler) produces the same HTML report without any email.

## Environment support

The registry models three execution environments rather than only operating
systems. Linux and Personal Windows use the extended runtime: local execution
plus optional delegated workloads when a tool supports them. Corporate
Windows is explicit and local-only: no VM, QwenPaw, external compute,
workload delegation or required external integrations.

The Python maintainer scripts work on Windows and Linux. `new-repo.py` invokes
Git; creating a GitHub remote is a separate, explicit action. The template's
CI tests Python projects on Windows and Ubuntu; `devin-bridge` tests Node on
both platforms.

## Contributing

Issues and pull requests are welcome. New projects should document purpose,
prior art, install and usage instructions, supported platforms, limitations,
and how their Devin-specific capability improves the base tool.

## When to use this

- You maintain the Icaro0310 Devin ecosystem (or fork the pattern) and need
  the registry, catalog/DevKit exporters, platform-doc migration, scaffolder,
  weekly report or shared `pypi-publish.yml` workflow.
- You are starting a new `devin-*` project and want a common README plus
  Windows/Linux guides, CI and conventions (`tools/new-repo.py`).
- You want a public activity report that reads only public GitHub commit
  metadata — no private repo contents, no session data.
- You want one token-based PyPI publish workflow reused across every Python
  repo instead of per-repo publish plumbing.

## When NOT to use this

- You are an end user looking to run the tools — use the `devin-devkit`
  distribution or install an individual CLI; this repository is the registry
  source, not a runtime dependency.
- You are looking for the private scout/ideation engine — it is
  deliberately not published in this repository.
- You want email reports out of the box — delivery needs *your* SMTP
  secrets and a verified sender; the HTML artifact works without any of
  that.

## FAQ

**What is devin-powerups?** The public maintainer hub for the Devin
community ecosystem. It holds the machine-readable `registry.json` source of
truth, catalog and DevKit manifest exporters, the OS-guide migration utility,
the project template, the `new-repo.py` scaffolder, the weekly report
generator, and the reusable `pypi-publish.yml` workflow.

**Do I need this repo to use the ecosystem tools?** No. Install a tool from
its own repository or use the separate `devin-devkit` profiles. The DevKit
ships a registry-derived manifest, so the maintainer hub is not required at
runtime.

**Does the weekly report expose private data?** No. It filters the registry
to `kind=project` and `visibility=public`, then reads only the public
GitHub commits API. Email delivery is optional and uses secrets and
variables you configure in your own fork; if they are missing, the workflow
keeps the HTML artifact and skips the email.

**How do other repos publish to PyPI?** They call the reusable workflow:
`uses: Icaro0310/devin-powerups/.github/workflows/pypi-publish.yml@main`
with a `PYPI_API_TOKEN` secret. One token-based workflow, no per-repo OIDC
setup.

## License

MIT — see [LICENSE](LICENSE).

## Scheduler (`tools/schedule.py`) — F6 foundation

Opt-in scheduling with three backends, resolved automatically or pinned
with `--backend`:

- **tasksch** (Windows): `schtasks /create /tn devin-<name>`.
- **cron** (Linux/macOS): tagged lines in `crontab` (`# devin-ecosystem:<name>`).
- **elapsed** (corporate fallback, always available): jobs live in
  `.devin-ecosystem/scheduled.json` and run from a `UserPromptSubmit`
  hook calling `schedule.py check --run` — no daemon, the prompt is the tick.

    python tools/schedule.py install backup "devin-backup snapshot" --daily
    python tools/schedule.py list | check [--run] | uninstall <name>

`--requires-devin-closed` wraps the command with a "Devin not running"
guard — required for jobs that would VACUUM or rewrite Devin stores.
