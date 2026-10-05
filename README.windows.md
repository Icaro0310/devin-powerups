# devin-powerups — Windows guide

This guide covers Windows setup only. See [README.md](README.md) for features, shared commands, limitations, and the safety model.

## Prerequisites

- Python 3.10 or newer.
- Git for repository scaffolding.

## Install

Run the maintainer utilities from this checkout:

```powershell
py -3 tools/new-repo.py --help
py -3 tools/weekly_repo_report.py --help
```

## Devin paths

Session data normally lives under `%APPDATA%\devin\cli\`; UI state and ACP stores under `%APPDATA%\Devin\User\`.
Use the tool's documented `--data-dir` or `--config-dir` flags for non-default locations.

## Platform notes

- Windows and Linux are the initial tested platforms.
- macOS is planned but not claimed as tested.

## Troubleshooting

- Confirm `py -3` and Git are available in PowerShell.
