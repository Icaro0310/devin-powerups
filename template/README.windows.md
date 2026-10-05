# Windows guide

This file contains Windows-specific installation and path details. See [README.md](README.md) for features, shared usage, limitations, and the safety model.

## Prerequisites

- Windows 10 or newer and PowerShell.
- Git for Windows on `PATH` when installing from GitHub; confirm with `git --version`.
- `uv` and Python 3.10 or newer. Follow the [uv installation guide](https://docs.astral.sh/uv/getting-started/installation/); `uv` can manage a compatible Python interpreter.

## Install

From a public source checkout:

```powershell
uv tool install "git+https://github.com/Icaro0310/devin-{{name}}.git"
```

From a local checkout, run in the repository directory:

```powershell
uv tool install .
```

After a PyPI release, install the exact distribution and version listed in the main README.

## Devin paths and PATH

Session data normally lives under `%APPDATA%\devin\cli\`; UI state and ACP databases are under `%APPDATA%\Devin\User\`. Use this tool's documented `--data-dir` or `--config-dir` option if those roots were customized.

`uv` places installed commands in its tools executable directory. If PowerShell cannot find the command, follow `uv tool update-shell` guidance and start a new terminal.

## Troubleshooting

- A GitHub install requires Git for Windows; installing Python alone is not enough.
- For smoke tests, use the synthetic quick start in [README.md](README.md), not live Devin databases or credentials.
