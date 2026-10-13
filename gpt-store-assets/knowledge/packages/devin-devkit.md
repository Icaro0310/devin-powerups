<div align="center">

<a href="https://github.com/Icaro0310/devin-devkit/actions/workflows/test-devkit.yml"><img src="https://github.com/Icaro0310/devin-devkit/actions/workflows/test-devkit.yml/badge.svg" alt="ci"/></a>

<a href="https://scorecard.dev/viewer/?uri=github.com/Icaro0310/devin-devkit"><img src="https://api.scorecard.dev/projects/github.com/Icaro0310/devin-devkit/badge" alt="OpenSSF Scorecard"/></a>
<a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green" alt="License: MIT"/></a>
<a href="https://www.python.org/"><img src="https://img.shields.io/badge/python-3.10%2B-blue" alt="Python 3.10+"/></a>
<a href="https://github.com/Icaro0310/devin-devkit"><img src="https://img.shields.io/github/stars/Icaro0310/devin-devkit" alt="GitHub stars"/></a>
<a href="https://github.com/Icaro0310/devin-devkit/commits/main"><img src="https://img.shields.io/github/last-commit/Icaro0310/devin-devkit" alt="Last commit"/></a>
<a href="https://github.com/Icaro0310/awesome-devin"><img src="https://img.shields.io/badge/part%20of-devin--*-ecosystem-7c3aed" alt="devin-* ecosystem"/></a>
<a href="https://github.com/Icaro0310/devin-devkit/issues"><img src="https://img.shields.io/badge/PRs-welcome-brightgreen" alt="PRs welcome"/></a>
</div>

# devin-devkit

> Unofficial community project. Not affiliated with, endorsed by, or sponsored by Cognition AI. Devin is a Cognition AI trademark.

**[Linux](README.linux.md)** · **[Personal Windows](README.windows.md)** · **[Corporate Windows](README.corporate-windows.md)** · **[Compatibility](../../COMPATIBILITY.md)** · **[macOS status](README.macos.md)**

Part of the [awesome-devin](https://github.com/Icaro0310/awesome-devin) ecosystem: the curated hub for the devin-* tools.

`devin-devkit` turns the public `devin-powerups` registry into selectable installation profiles. It is an **installer/distribution tool**, not a meta-package: each Python app gets its own isolated `uv` environment, and the Node bridge uses npm separately.

![devin-devkit demo: list, outdated, doctor check](assets/demo.gif)

## Source → tools → profiles

- `devin-powerups/registry.json` is the catalog and profile source of truth for the first-party `devin-*` tools, this separate DevKit distribution, the maintainer hub, and related artifacts.
- `tools/export_devkit_manifest.py` builds this repo's bundled manifest from the registry, including artifact, interface, audience, platform and environment metadata. The exporter rejects private or unregistered tools and verifies immutable Git commit references.
- `src/devin_devkit/cli.py` previews and installs the selected profile under an explicit execution environment. It does not edit Devin settings, inspect session databases, or install Slack/Obsidian/VM services.

## Execution environments

One `devin-devkit` distribution supports three environments. Linux and Personal Windows use the extended runtime: local execution plus optional delegated workloads through Devin VM or QwenPaw when the selected tool supports them. Corporate Windows is intentionally self-contained: local execution only, with no VM, QwenPaw, Slack dependency, external compute, or workload delegation.

The installer defaults to `linux` on Linux and `personal-windows` on Windows. Corporate Windows is never inferred from the operating system; select it explicitly so restricted machines fail closed:

```bash
devin-devkit install qa --environment linux
devin-devkit install qa --environment personal-windows
devin-devkit install qa --environment corporate-windows
```

Environment entry points: [Linux](environments/linux/README.md) · [Personal Windows](environments/personal-windows/README.md) · [Corporate Windows](environments/corporate-windows/README.md).

## Compatibility

The generated [compatibility matrix](../../COMPATIBILITY.md) is rendered from `registry.json`; unsupported entries carry an explicit registry reason rather than guessed compatibility. Entries marked `Local only` install without VM, QwenPaw, external compute, workload delegation, or required external integrations.

## Profiles

| Profile | Contents |
|---|---|
| `qa` | internals spec, QA pack, evals, metrics, doctor |
| `evaluation` | internals spec, evals, metrics, synthetic task fixtures |
| `security` | redact, bridge, janitor |
| `memory` / `agent` | memory, graph, search, poordjaevin |
| `operations` | backup, history, doctor, metrics, janitor, PM, orchestrator, switch and skill catalog |
| `full` / `all` | every automatically installable profile tool; `devin-office` remains a manual source-only service |

QwenPaw is an optional add-on and is not installed by these profiles. macOS is planned, not tested.

## Use

Install from PyPI (no runtime dependencies):

```bash
uv tool install devin-devkit
```

From a source checkout, use `uv tool install .` inside `packages/devkit`, or the subdirectory spec `git+https://github.com/Icaro0310/devin-devkit.git#subdirectory=packages/devkit`.

From a local checkout, use `uv tool install .`. Then inspect the available profiles and preview before applying:

```bash
devin-devkit profiles
devin-devkit list
devin-devkit install qa
devin-devkit install qa --apply
devin-devkit install full --apply
```

Install specs are pinned (PyPI versions or GitHub archive SHAs), so an install never drifts on its own. To move forward:

```bash
devin-devkit outdated          # which installed tools have newer pins
devin-devkit update            # preview the update plan
devin-devkit update --apply    # reinstall outdated tools
devin-devkit update --force --apply   # reinstall everything
```

`outdated`/`update` read the manifest published in this repository, which a weekly workflow re-exports from the maintainer registry, so the pins are never more than about a week behind upstream. Updates apply the same gates as `install`: the selected `--environment`, platform support, and prerequisite checks are enforced at plan time, and tools whose commands exist on `PATH` but were not installed by devkit (no uv receipt, no npm global entry) are reported as `unmanaged` and never force-reinstalled — remove them manually first if you want devkit to adopt them. A tool that was permitted and later became forbidden (policy or manifest changed) reports `environment-blocked` on `outdated`/`update` even when already at the pinned version — that is intentional, not a regression: the check exists to surface the violation, and `current` would hide it.

To run from a checkout without installing the DevKit itself:

```bash
uv run --project . python -m devin_devkit.cli install qa
```

The installer can also be run without installing: `uvx devin-devkit ...`.

The manifest pins PyPI versions where available and GitHub source archives to immutable commit SHAs otherwise. Before it starts, the installer checks platform support, registry-declared environment compatibility, required managers, Node.js for `devin-bridge`, and existing command collisions. It never overwrites an existing command; commands already on `PATH` are reported as pre-existing but are not version-verified, and a partial collision blocks the profile before any installs run.

## Runtime requirements

- Python tools: Python 3.10 or newer, installed in isolated environments managed by `uv`.
- `devin-bridge`: Node.js 20 or newer and npm. Installed from the npm registry as `@icaro0310/devin-bridge`.
- Most tools install from PyPI or HTTPS archives without Git. `devin-skill-catalog` currently installs from a `git+https` spec and requires `git` on `PATH`; Git is also needed for manual source checkouts such as `devin-office`.
- Supported environments: Linux, Personal Windows and Corporate Windows. Linux and Personal Windows may use optional delegated runtime; Corporate Windows rejects registry entries that require external runtime, delegation or external integrations. macOS is planned but not claimed as tested.

## Development and synchronization

```bash
uv run --extra dev pytest
python ../devin-powerups/tools/validate_registry.py
python ../devin-powerups/tools/export_devkit_manifest.py
python ../devin-powerups/tools/export_devkit_manifest.py --check
python ../devin-powerups/tools/render_catalog.py --check ../Icaro0310/README.md
```

The DevKit package has no runtime dependencies. New catalog entries and profiles belong in the registry; regenerate the manifest instead of hand-editing its generated copy. For local sibling development, install dependencies editably in a virtual environment (examples in the OS guides); keep relative file paths out of publishable package metadata.
