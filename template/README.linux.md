# Linux guide

This file contains Linux-specific installation and path details. See [README.md](README.md) for features, shared usage, limitations, and the safety model.

## Prerequisites

- A supported Linux distribution and Bash.
- Git when installing from GitHub; confirm with `git --version`.
- `uv` and Python 3.10 or newer. Install `uv` from the [official guide](https://docs.astral.sh/uv/getting-started/installation/) or your distribution's package manager; `uv` can manage a compatible Python interpreter.

## Install

From a public source checkout:

```bash
uv tool install 'git+https://github.com/Icaro0310/devin-{{name}}.git'
```

From a local checkout, run in the repository directory:

```bash
uv tool install .
```

After a PyPI release, install the exact distribution and version listed in the main README.

## Devin paths and scheduling

Session data normally lives under `${XDG_DATA_HOME:-$HOME/.local/share}/devin/cli/`; UI state and ACP databases are under `${XDG_CONFIG_HOME:-$HOME/.config}/Devin/User/`. Use this tool's documented `--data-dir` or `--config-dir` option if those roots were customized.

Optional scheduled work belongs in `systemd --user` or cron. Installation does not create scheduled jobs automatically.

## Troubleshooting

- A GitHub install requires Git from the distribution's package manager.
- If the command is not found, ensure the `uv` tools executable directory is on `PATH`, then open a new shell.
- For smoke tests, use the synthetic quick start in [README.md](README.md), not live Devin databases or credentials.
