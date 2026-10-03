# devin-{{name}}

> **Unofficial community project.** Not affiliated with, endorsed by, or
> sponsored by Cognition AI. "Devin" is a trademark of Cognition AI.

**[Português (BR)](README.pt-BR.md)** · English

One-line description of what this tool does.

## The problem

<!-- Real pain point, with evidence. Who suffers, when, how often. -->

## Prior art

<!-- What already exists for other agents/tools. Be honest and link it.
     This project adapts <X>; it does not reinvent it. -->

## What makes it Devin-native

<!-- The differentiator. Must pass three tests:
     1. Side-by-side: does it do something the base tool *cannot* do at all?
     2. No-Devin: does the extra disappear if Devin is removed?
     3. One sentence: can you explain it without jargon? -->

## Install

Requires Python ≥ 3.10 and `pipx`. On Windows (PowerShell), install `pipx`
with `py -m pip install --user pipx`, then run `py -m pipx ensurepath` and
reopen the terminal. On Debian/Ubuntu Linux, run
`sudo apt install pipx python3-venv` and `pipx ensurepath`; reopen the terminal.

After this project has a public GitHub repository, install it with:

```bash
pipx install "devin-{{name}} @ git+https://github.com/Icaro0310/devin-{{name}}.git"
```

## Usage

```bash
devin-{{name}} --help
```

## Platform support

<!-- REQUIRED — Linux parity is a project convention (see the hub README).
     Everything shipped must work on Windows AND Linux. State the tested
     platforms and paths for session data (%APPDATA% vs XDG_DATA_HOME) and
     UI config (XDG_CONFIG_HOME), plus overrides. If something genuinely
     cannot run on Linux, say so in Limitations instead of hiding it. -->

Tested on **Windows and Linux** (`windows-latest` + `ubuntu-latest` in CI).
On Linux, Devin session data defaults to `~/.local/share/devin`; UI config
is under `~/.config/Devin`. Document any paths or overrides this tool uses.

## Limitations

<!-- Be explicit: private/volatile internals, version-specific behavior,
     what it does NOT do. -->

## Development

```bash
pip install -e ".[dev]"
pytest
```

## License

MIT — see [LICENSE](LICENSE).
