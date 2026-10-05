# devin-powerups — Linux guide

This guide covers Linux setup only. See [README.md](README.md) for features, shared commands, limitations, and the safety model.

## Prerequisites

- Python 3.10 or newer.
- Git for repository scaffolding.

## Install

Run the maintainer utilities from this checkout:

```bash
python3 tools/new-repo.py --help
python3 tools/weekly_repo_report.py --help
```

## Devin paths

Session data normally lives under `${XDG_DATA_HOME:-$HOME/.local/share}/devin/cli/`; UI state and ACP stores under `${XDG_CONFIG_HOME:-$HOME/.config}/Devin/User/`.
Use the tool's documented `--data-dir` or `--config-dir` flags for non-default locations.

## Platform notes

- Windows and Linux are the initial tested platforms.
- macOS is planned but not claimed as tested.

## Troubleshooting

- Confirm `python3` and Git are available in the shell.
