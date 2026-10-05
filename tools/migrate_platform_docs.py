#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

HUB = Path(__file__).resolve().parent.parent
DEFAULT_ROOT = HUB.parent


def repo_path(entry: dict[str, Any], root: Path) -> Path:
    local_dir = entry.get("local_dir")
    return (root / local_dir).resolve() if local_dir else root / entry["name"]


def language_switch(text: str) -> str:
    replacement = "**[Windows](README.windows.md)** · **[Linux](README.linux.md)** · English"
    if "README.windows.md" in text and "README.linux.md" in text:
        return text
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if "README.pt-BR.md" in line or "Português (BR)" in line:
            lines[index] = replacement
            return "\n".join(lines) + ("\n" if text.endswith("\n") else "")
    for index, line in enumerate(lines):
        if line.startswith("# "):
            lines.insert(index + 1, "")
            lines.insert(index + 2, replacement)
            return "\n".join(lines) + ("\n" if text.endswith("\n") else "")
    return replacement + "\n\n" + text


def _install_spec(entry: dict[str, Any], tool: dict[str, Any]) -> str:
    if tool["source"] == "pypi":
        extras = tool.get("extras", [])
        suffix = f"[{','.join(extras)}]" if extras else ""
        return f"{tool['package']}{suffix}=={tool['version']}"
    if tool["source"] == "github":
        return f"{entry['url']}/archive/{tool['ref']}.tar.gz"
    raise ValueError(f"{entry['name']}: no install specification for source {tool['source']!r}")


def _install_line(entry: dict[str, Any], tool: dict[str, Any] | None, platform: str) -> list[str]:
    if entry["name"] == "devin-powerups":
        command = "py -3" if platform == "windows" else "python3"
        return [
            "Run the maintainer utilities from this checkout:",
            "",
            "```" + ("powershell" if platform == "windows" else "bash"),
            f"{command} tools/new-repo.py --help",
            f"{command} tools/weekly_repo_report.py --help",
            "```",
        ]
    if entry["name"] == "devin-office":
        command = "py -3" if platform == "windows" else "python3"
        return [
            "From a repository checkout, run the standalone read-only dashboard:",
            "",
            "```" + ("powershell" if platform == "windows" else "bash"),
            f"{command} daemon.py --port 8788",
            "```",
            "",
            "Open `http://localhost:8788`; the process stops with Ctrl+C.",
        ]
    if not tool:
        return ["This related project is not installed by the DevKit. See its main README for current setup instructions."]
    spec = _install_spec(entry, tool)
    quoted = json.dumps(spec) if platform == "windows" else repr(spec)
    if tool["manager"] == "uv":
        return [
            "Install the isolated Python CLI:",
            "",
            "```" + ("powershell" if platform == "windows" else "bash"),
            f"uv tool install {quoted}",
            "```",
        ]
    if tool["manager"] == "npm":
        return [
            "Install the Node.js CLI:",
            "",
            "```" + ("powershell" if platform == "windows" else "bash"),
            f"npm install --global {quoted}",
            "```",
        ]
    return [tool.get("manual_note", "See the main README for manual setup.")]


def render_guide(entry: dict[str, Any], tool: dict[str, Any] | None, platform: str) -> str:
    name = entry["name"]
    lines = [
        f"# {name} — {platform.title()} guide",
        "",
        f"This guide covers {platform.title()} setup only. See [README.md](README.md) for features, shared commands, limitations, and the safety model.",
        "",
        "## Prerequisites",
        "",
    ]
    if tool and tool["manager"] == "npm":
        lines.append("- Node.js 20 or newer and npm.")
        if tool.get("requires_git"):
            lines.append("- Git on `PATH` for a Git dependency.")
    elif tool and tool["manager"] == "uv":
        lines.extend(["- `uv` and Python 3.10 or newer; `uv` can manage Python."])
        if tool.get("requires_git"):
            lines.append("- Git on `PATH` for a Git dependency in this package's current release.")
    elif name == "devin-office":
        lines.extend(["- Python 3.10 or newer.", "- Git for a source checkout.", "- Devin Desktop or CLI on the machine whose sessions you want to view."])
    elif name == "devin-powerups":
        lines.extend(["- Python 3.10 or newer.", "- Git for repository scaffolding."])
    else:
        lines.append("- Follow the requirements listed in [README.md](README.md).")
    lines.extend(["", "## Install", ""])
    lines.extend(_install_line(entry, tool, platform))
    lines.extend(["", "## Devin paths", ""])
    if platform == "windows":
        lines.extend([
            "Session data normally lives under `%APPDATA%\\devin\\cli\\`; UI state and ACP stores under `%APPDATA%\\Devin\\User\\`.",
            "Use the tool's documented `--data-dir` or `--config-dir` flags for non-default locations.",
        ])
    else:
        lines.extend([
            "Session data normally lives under `${XDG_DATA_HOME:-$HOME/.local/share}/devin/cli/`; UI state and ACP stores under `${XDG_CONFIG_HOME:-$HOME/.config}/Devin/User/`.",
            "Use the tool's documented `--data-dir` or `--config-dir` flags for non-default locations.",
        ])
    lines.extend(["", "## Platform notes", "", "- Windows and Linux are the initial tested platforms.", "- macOS is planned but not claimed as tested."])
    if platform == "linux" and name in {"devin-janitor", "devin-office"}:
        lines.extend(["- Optional scheduling uses `systemd --user` or cron; installation does not create jobs automatically."])
    lines.extend(["", "## Troubleshooting", ""])
    if tool and tool["manager"] == "uv":
        if platform == "windows":
            lines.append("- If a command is not found, reopen PowerShell and run `uv tool update-shell`.")
        else:
            lines.append("- If a command is not found, ensure the `uv` tools directory is on `PATH` and run `uv tool update-shell`.")
    elif tool and tool["manager"] == "npm":
        lines.append("- If the bridge command is missing, check that npm's global executable directory is on `PATH` (`npm config get prefix`).")
    elif name == "devin-office":
        lines.append("- Start the daemon from the repository directory with the OS-specific Python launcher shown above.")
    elif name == "devin-powerups":
        lines.append("- Confirm `py -3` and Git are available in PowerShell." if platform == "windows" else "- Confirm `python3` and Git are available in the shell.")
    else:
        lines.append("- Follow the platform-specific troubleshooting notes in the main README.")
    if tool and tool.get("requires_git"):
        lines.append("- This release has a Git dependency; verify Git is installed and on `PATH` with `git --version`.")
    lines.append("")
    return "\n".join(lines)


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(content)
        tmp = Path(handle.name)
    os.replace(tmp, path)


def plan_migration(registry: dict[str, Any], root: Path) -> list[dict[str, Any]]:
    tool_map = registry.get("devkit", {}).get("tools", {})
    targets = set(tool_map) | {"devin-powerups", "qwenpaw-suite"}
    plans = []
    for entry in registry.get("repositories", []):
        if entry.get("visibility") != "public" or entry.get("kind") not in {"project", "infra"}:
            continue
        if entry["name"] not in targets:
            continue
        if "personal-agent-system" in Path(entry.get("local_dir", "")).parts:
            continue
        repo = repo_path(entry, root)
        if not repo.is_dir():
            continue
        legacy = repo / "README.pt-BR.md"
        if not (repo / "README.md").is_file():
            raise ValueError(f"{entry['name']}: README.md is missing")
        tool = tool_map.get(entry["name"])
        if tool:
            tool = {**tool, "requires_git": entry["name"] in registry.get("devkit", {}).get("git_required_tools", [])}
        plans.append({
            "name": entry["name"],
            "repo": repo,
            "legacy": legacy,
            "readme": repo / "README.md",
            "windows": repo / "README.windows.md",
            "linux": repo / "README.linux.md",
            "tool": tool,
            "entry": entry,
        })
    return plans


def migrate(registry: dict[str, Any], root: Path, apply: bool = False) -> list[dict[str, str]]:
    plans = plan_migration(registry, root)
    report = []
    prepared = []
    for item in plans:
        report.append({"repo": item["name"], "legacy_removed": item["legacy"].exists(), "windows": str(item["windows"]), "linux": str(item["linux"])})
        prepared.append({
            **item,
            "readme_content": language_switch(item["readme"].read_text(encoding="utf-8")),
            "windows_content": render_guide(item["entry"], item["tool"], "windows"),
            "linux_content": render_guide(item["entry"], item["tool"], "linux"),
        })
    if not apply:
        return report
    for item in prepared:
        _atomic_write(item["readme"], item["readme_content"])
        _atomic_write(item["windows"], item["windows_content"])
        _atomic_write(item["linux"], item["linux_content"])
        if item["legacy"].exists():
            item["legacy"].unlink()
    return report


def check_platform_docs(registry: dict[str, Any], root: Path) -> list[str]:
    errors = []
    for item in plan_migration(registry, root):
        if item["legacy"].exists():
            errors.append(f"{item['name']}: legacy README.pt-BR.md still exists")
        if language_switch(item["readme"].read_text(encoding="utf-8")) != item["readme"].read_text(encoding="utf-8"):
            errors.append(f"{item['name']}: README.md needs OS guide links")
        if not item["windows"].is_file() or item["windows"].read_text(encoding="utf-8") != render_guide(item["entry"], item["tool"], "windows"):
            errors.append(f"{item['name']}: README.windows.md is missing or stale")
        if not item["linux"].is_file() or item["linux"].read_text(encoding="utf-8") != render_guide(item["entry"], item["tool"], "linux"):
            errors.append(f"{item['name']}: README.linux.md is missing or stale")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Migrate public project docs to OS-specific guides.")
    parser.add_argument("--registry", type=Path, default=HUB / "registry.json")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--apply", action="store_true")
    modes.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    try:
        registry = json.loads(args.registry.read_text(encoding="utf-8"))
        if args.check:
            errors = check_platform_docs(registry, args.root)
            if errors:
                for error in errors:
                    print(f"error: {error}", file=sys.stderr)
                return 1
            print("ok: platform guides match registry.json")
            return 0
        report = migrate(registry, args.root, apply=args.apply)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"applied": args.apply, "repositories": report}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
