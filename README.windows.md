# devin-powerups — Personal Windows guide

This guide covers unrestricted Windows setup. For restricted machines, see [README.corporate-windows.md](README.corporate-windows.md); for features, shared commands, limitations, and the safety model, see [README.md](README.md).

Personal Windows uses the extended runtime: local execution plus optional Devin VM/QwenPaw delegation when this artifact supports it.

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

- Delegated runtime is optional; this guide installs local tooling only.
- Corporate Windows is a separate local-only environment.
- macOS is planned but not claimed as tested.

## Troubleshooting

- Confirm `py -3` and Git are available in PowerShell.
