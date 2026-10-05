# devin-{{name}}

> **Unofficial community project.** Not affiliated with, endorsed by, or
> sponsored by Cognition AI. "Devin" is a trademark of Cognition AI.

**[Windows](README.windows.md)** · **[Linux](README.linux.md)**

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

Choose the operating-system guide for setup and install commands:

- [Windows](README.windows.md)
- [Linux](README.linux.md)

Both guides install this CLI in an isolated environment. The shared command
surface and examples remain in this README.

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

The CI matrix covers **Windows and Linux**. Record tested behavior and
OS-specific Devin paths in [README.windows.md](README.windows.md) and
[README.linux.md](README.linux.md). macOS is planned but is not claimed as
tested.

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
