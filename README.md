<div align="center">

<img src="assets/banner.svg" alt="devin-powerups" width="100%"/>

</div>

# devin-powerups

> Unofficial community tooling for Devin. Not affiliated with, endorsed by, or
> sponsored by Cognition AI. Devin is a Cognition AI trademark.
>
> **[Português (BR)](README.pt-BR.md)** · English

A public maintainer toolkit for the Devin community projects. It contains a
machine-readable catalog, a starter template, a local scaffolder and a weekly
activity-report generator. End users install the individual tools from their
own repositories; they do not need this hub at runtime.

## What's included

| Path | Purpose |
|---|---|
| `registry.json` | Catalog of public projects plus clearly marked maintainer-only records. The weekly public report filters to `kind=project` and `visibility=public`. |
| `template/` | Bilingual starter repository with Windows/Linux documentation and CI. |
| `tools/new-repo.py` | Creates a new `devin-<name>` sibling checkout from the template, initializes Git and registers the repo in `registry.json` (schema-validated before writing). `--dry-run` previews without side effects. It does not create a GitHub repository or push. |
| `tools/weekly_repo_report.py` | Reads public GitHub commit metadata from the registry and writes a standalone HTML report. Email delivery is optional. |
| `tools/validate_registry.py` | Validates `registry.json` against `registry.schema.json` — dependency-free, exits non-zero on violations. |
| `tools/reconcile_registry.py` | Reconciles the registry against the GitHub account and local clones: missing entries, missing repos, stale version/tag fields. Read-only. |
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

The ecosystem tools are local-first and read-only by default, with explicit
write actions where required and no telemetry.

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
(`project`/`public`/`0`). It does not create a GitHub remote. Review the
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

The registry distinguishes public projects from maintainer-only records. The
weekly report filters to public projects and does not read private repository
contents. Personal paths, credentials, service addresses and session data do
not belong in this public repository.

## Works with Devin alone (Devin-only mode)

The hub itself is optional — every tool in `registry.json` installs and runs
standalone. What runs locally with zero external services:

- `registry.json` — plain JSON; read it, filter it, script against it.
- `tools/validate_registry.py` — schema-validates the registry, no deps.
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

## Platform support

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
  the registry, scaffolder, weekly report or shared `pypi-publish.yml`
  workflow.
- You are starting a new `devin-*` project and want the bilingual template
  with docs, CI and conventions already in place (`tools/new-repo.py`).
- You want a public activity report that reads only public GitHub commit
  metadata — no private repo contents, no session data.
- You want one token-based PyPI publish workflow reused across every Python
  repo instead of per-repo publish plumbing.

## When NOT to use this

- You are an end user of a specific `devin-*` tool — install that tool's
  own repository; this hub is maintainer infrastructure and is not needed
  at runtime.
- You are looking for the private scout/ideation engine — it is
  deliberately not published in this repository.
- You want email reports out of the box — delivery needs *your* SMTP
  secrets and a verified sender; the HTML artifact works without any of
  that.

## FAQ

**What is devin-powerups?** The public maintainer hub for the Devin
community ecosystem. It holds the machine-readable `registry.json` catalog,
the bilingual starter template, the `new-repo.py` scaffolder, the
`weekly_repo_report.py` report generator, and the reusable
`pypi-publish.yml` GitHub Actions workflow the Python repos share.

**Do I need this repo to use the ecosystem tools?** No. Every project in
`registry.json` installs and runs standalone from its own repository. This
hub exists for the maintainer's workflow — scaffolding, cataloging and
reporting — not for end users.

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
