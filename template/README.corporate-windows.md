# Corporate Windows guide

This file contains restricted Windows installation and path details. For unrestricted Windows, see [README.windows.md](README.windows.md); for features, shared usage, limitations, and the safety model, see [README.md](README.md).

Corporate Windows is a local-only runtime: no Devin VM, QwenPaw, Slack dependency, external compute, workload delegation or required external integration. Do not document support here unless the registry marks `corporate_windows.supported` as true.

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
- Do not enable delegation, external integrations or VM-backed behavior in this environment.
- For smoke tests, use the synthetic quick start in [README.md](README.md), not live Devin databases or credentials.
