# devin-powerups — Corporate Windows guide

This guide covers restricted Windows setup only. For unrestricted Windows, see [README.windows.md](README.windows.md); for features, shared commands, limitations, and the safety model, see [README.md](README.md).

Corporate Windows is a local-only environment: no Devin VM, QwenPaw, Slack dependency, external compute, workload delegation or required external integration.

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

## Environment notes

- Keep execution local; do not configure VM, QwenPaw, external compute or workload delegation.
- Registry-declared external integrations remain optional and are not installed by this guide.
- macOS is planned but not claimed as tested.

## Troubleshooting

- Confirm `py -3` and Git are available in PowerShell.
