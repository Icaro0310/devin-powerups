# Security Policy

## What this tool does with your data

- **No telemetry.** This project sends nothing to analytics or tracking.
- **Network where the job requires it.** Maintainer scripts such as
  `refresh_devkit_refs.py` and `reconcile_registry.py` contact GitHub and
  PyPI to fetch upstream references, and `weekly_repo_report.py` fetches
  GitHub data and can email the report through SMTP — that is their
  documented purpose. Everything else runs locally.
- **Data stays on your machine** apart from the fetches above.

## Sensitive data handling

- Output intended for sharing must pass through
  [`devin-redact`](https://github.com/Icaro0310/devin-state) before publication.
- Never commit Devin session databases, `.env` files, tokens, or pairing codes.

## Reporting a vulnerability

Open a **private** security advisory on GitHub, or open an issue marked
`[SECURITY]` **without** including the vulnerable data itself.

Do not file public issues containing secrets, tokens, or session content.
