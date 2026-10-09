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
    replacement = "**[Linux](README.linux.md)** · **[Personal Windows](README.windows.md)** · **[Corporate Windows](README.corporate-windows.md)**"
    ecosystem = "Part of the [awesome-devin](https://github.com/Icaro0310/awesome-devin) ecosystem: the curated hub for the devin-* tools."
    lines = text.splitlines()

    nav_index = next((
        index for index, line in enumerate(lines)
        if "README.linux.md" in line and "README.windows.md" in line and "README.corporate-windows.md" in line
    ), None)
    if nav_index is None:
        for index, line in enumerate(lines):
            if "README.windows.md" in line and "README.linux.md" in line:
                lines[index] = replacement
                nav_index = index
                break
    if nav_index is None:
        for index, line in enumerate(lines):
            if "README.pt-BR.md" in line or "Português (BR)" in line:
                lines[index] = replacement
                nav_index = index
                break
    if nav_index is None:
        for index, line in enumerate(lines):
            if line.startswith("# "):
                lines[index + 1:index + 1] = ["", replacement]
                nav_index = index + 2
                break
    if nav_index is None:
        lines[0:0] = [replacement, ""]
        nav_index = 0

    nearby = lines[max(0, nav_index - 2):nav_index + 4]
    if not any("awesome-devin" in line for line in nearby):
        lines[nav_index + 1:nav_index + 1] = ["", ecosystem]
    return "\n".join(lines) + ("\n" if text.endswith("\n") else "")


def _install_spec(entry: dict[str, Any], tool: dict[str, Any]) -> str:
    # Guides intentionally render *unpinned* specs so install instructions
    # always fetch latest upstream; pinned, reproducible specs live in the
    # devkit manifest (install_spec) where `devin-devkit update` manages them.
    if tool["source"] == "pypi":
        extras = tool.get("extras", [])
        suffix = f"[{','.join(extras)}]" if extras else ""
        return tool["package"] + suffix
    if tool["source"] == "github":
        return f"{entry['url']}/archive/refs/heads/main.tar.gz"
    if tool["source"] == "npm":
        return tool["package"]
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


# Environment deep-dives — identical for every tool because the
# constraints live in the platform, not the package. Per-tool details
# (install spec, manager quirks) stay in the generated sections.
_LINUX_SPECIFICS = [
    "- **Installer choice:** `uv tool install` is the recommended path "
    "(isolated environment, managed Python). `pipx install` works "
    "identically for PyPI packages; `pip install --user` is the "
    "last-resort fallback — no isolation, watch dependency conflicts.",
    "- **PATH:** executables land in `~/.local/bin`. If a command is not "
    "found, add `export PATH=\"$HOME/.local/bin:$PATH\"` to "
    "`~/.bashrc`/`~/.zshrc` and open a new shell.",
    "- **Distros:** tested on Ubuntu; Debian, Fedora and Arch follow the "
    "same steps — only `uv`/Python acquisition differs (distro package "
    "or the uv installer script).",
    "- **Headless and minimal environments:** no display is needed — "
    "every CLI is text-only. In containers or WSL, install `uv` and Git "
    "and follow the same steps; `XDG_*` paths resolve normally.",
    "- **Permissions:** tools read Devin data under `$XDG_DATA_HOME/devin` "
    "and write only their own config/state — no root or sudo is required.",
    "- **Scheduling:** optional recurring work belongs to `systemd "
    "--user` timers or cron; installation never creates jobs.",
]

_WINDOWS_PERSONAL_SPECIFICS = [
    "- **Python:** `uv` manages its own Python, which also avoids the "
    "Microsoft Store `python.exe` alias stub (it opens the Store instead "
    "of running). If you install Python from python.org anyway, tick "
    "\"Add python.exe to PATH\".",
    "- **Shell:** PowerShell 7 + Windows Terminal is the recommended "
    "setup; every command also works in `cmd.exe` and Windows "
    "PowerShell 5.1 — none require admin.",
    "- **Install location:** executables live under "
    "`%USERPROFILE%\\.local\\bin`; data under `%APPDATA%\\devin`. "
    "Nothing touches `Program Files` or the registry.",
    "- **WSL:** treat it as a Linux machine — follow "
    "[README.linux.md](README.linux.md) inside it.",
    "- **Uninstall:** `uv tool uninstall <package>` (or `npm uninstall -g` "
    "for a Node.js tool) removes the CLI; delete `%APPDATA%\\devin` to "
    "remove local data. No services or scheduled tasks are left behind.",
]

_WINDOWS_CORPORATE_SPECIFICS = [
    "- **No admin rights needed:** `uv` and every tool install under "
    "`%LOCALAPPDATA%`/`%APPDATA%` — nothing writes to `Program Files`, "
    "the registry, or requires elevation.",
    "- **Proxy:** set `HTTPS_PROXY`/`HTTP_PROXY` before installing. Per "
    "session: `$env:HTTPS_PROXY=\"http://proxy:port\"`; persistently: "
    "`setx HTTPS_PROXY \"http://proxy:port\"`. `uv`, `pip` and `npm` "
    "honor them.",
    "- **TLS inspection:** if the corporate proxy intercepts TLS, point "
    "the installer at the company CA bundle: "
    "`$env:REQUESTS_CA_BUNDLE=\"C:\\path\\corp-root.pem\"`. Certificate "
    "errors at install time mean the proxy, not the package.",
    "- **Execution policy:** installed CLIs are real executables — "
    "`Set-ExecutionPolicy` only matters for `.ps1` scripts from a "
    "checkout; `-Scope CurrentUser RemoteSigned` suffices, no admin.",
    "- **Blocked installers:** if winget/Store are disabled by policy, "
    "`uv` installs as a standalone binary — download the GitHub release "
    "zip, extract to `%LOCALAPPDATA%\\bin`, add it to PATH.",
    "- **Long paths:** keep checkout/install roots short (`C:\\dev`) — "
    "MAX_PATH (260 chars) can still bite inside virtualenvs; "
    "`LongPathsEnabled` needs admin, short roots do not.",
    "- **EDR/antivirus:** if a scan kills the install, retry with an "
    "exclusion or ask IT to allowlist `%LOCALAPPDATA%\\uv` and "
    "`%USERPROFILE%\\.local\\bin`. These tools never elevate or listen "
    "on the network by default.",
    "- **Offline/air-gapped:** `pip download <package> -d wheels\\` on a "
    "connected machine, copy the folder, then `pip install --no-index "
    "--find-links wheels\\` on the target (pure-Python tools; native "
    "deps need a matching platform wheel). For `source_only` tools "
    "installed from a copied checkout, stage the build backend too "
    "(`pip download setuptools wheel`), then install with `pip install "
    "--no-index --find-links wheels\\ --no-build-isolation .` inside "
    "the checkout.",
    "- **Fully local runtime:** installed tools make no required network "
    "calls — they read `sessions.db` and local stores only. The single "
    "exception is devin-doctor's optional update check (fetches the "
    "DevKit manifest); it self-skips when the registry is unreachable, "
    "or force it off with `DEVIN_DOCTOR_OFFLINE=1`.",
]

# Canonical recurring jobs per tool — real cadences, sanitized. Only tools
# whose workflows benefit from a schedule get a concrete example; everything
# else stays on-demand (the generic "Scheduling" bullet in the specifics
# sections already says installation never creates jobs).
_RECURRING_JOBS: dict[str, dict[str, str]] = {
    "devin-backup": {
        "cmd": "devin-backup create --out ~/backups",
        "cron": "15 3 * * *",
        "win": "devin-backup create --out %USERPROFILE%\\backups",
        "note": "Nightly snapshot; pair with a weekly `devin-backup rotate --keep 10 --yes`. Or let the tool self-schedule with `devin-backup install` (cron / Task Scheduler / elapsed backends).",
    },
    "devin-janitor": {
        "cmd": "devin-janitor run --apply",
        "cron": "30 4 * * *",
        "win": "devin-janitor run --apply",
        "note": "Daily cleanup. `devin-janitor install` registers the built-in daily report job (cron / Task Scheduler / elapsed hook) — prefer it over hand-rolled entries.",
    },
    "devin-explore": {
        "cmd": "devin-doctor check",
        "cron": "0 9 * * 1",
        "win": "devin-doctor check",
        "note": "Weekly health sweep — read-only, safe to leave on.",
    },
    "devin-history": {
        "cmd": "devin-history export",
        "cron": "0 5 * * 0",
        "win": "devin-history export",
        "note": "Weekly archive of sessions to notes; run before janitor cleanup.",
    },
    "devin-brain": {
        "cmd": "devin-memory extract --latest",
        "cron": "0 7 * * 0",
        "win": "devin-memory extract --latest",
        "note": "Weekly knowledge extraction from recent sessions (proposed entries, human-approved).",
    },
    "devin-evals": {
        "cmd": "devin-evals run --sessions-db ~/.local/share/devin/cli/sessions.db",
        "cron": "0 6 * * 0",
        "win": "devin-evals run --sessions-db %APPDATA%\\devin\\cli\\sessions.db",
        "note": "Weekly regression replay; corpus stays deterministic and offline.",
    },
    "devin-metrics": {
        "cmd": "devin-metrics summary",
        "cron": "45 4 * * *",
        "win": "devin-metrics summary",
        "note": "Daily usage summary; `watch` is the advisory context guard.",
    },
    "devin-graph": {
        "cmd": "devin-graph build",
        "cron": "0 6 * * 0",
        "win": "devin-graph build",
        "note": "Weekly rebuild of graph.db so downstream tools see fresh linkage.",
    },
    "devin-office": {
        "cmd": "python daemon.py --port 8788",
        "cron": "@reboot",
        "win": "py daemon.py --port 8788",
        "note": "Long-running daemon — prefer `systemd --user` service on Linux or a logon trigger (`/sc onlogon`) on Windows, not an interval.",
    },
}


def _render_recurring(name: str, platform: str, environment: str) -> list[str]:
    job = _RECURRING_JOBS.get(name)
    if job is None:
        return []
    lines = ["## Recurring runs (optional)", ""]
    lines.append(f"_{job['note']}_")
    lines.append("")
    if platform == "linux":
        lines.extend([
            "```cron",
            f"{job['cron']} {job['cmd']}",
            "```",
            "",
            "Equivalent `systemd --user` timer works too; enable lingering if it must run without a login session.",
        ])
    elif environment == "corporate_windows":
        lines.extend([
            "```powershell",
            f'schtasks /create /tn "{name}" /tr "{job["win"]}" /sc daily /st 04:00 /f',
            "```",
            "",
            "User-scope `schtasks` needs no admin. If Group Policy disables Task Scheduler, run the command manually or use the tool's own `install` subcommand where available.",
        ])
    else:
        lines.extend([
            "```powershell",
            f'schtasks /create /tn "{name}" /tr "{job["win"]}" /sc daily /st 04:00 /f',
            "```",
            "",
            "Runs under your account — no admin needed. Adjust `/sc`/`/st` (or `/sc onlogon` for daemons) to taste.",
        ])
    lines.append("")
    return lines


def render_guide(entry: dict[str, Any], tool: dict[str, Any] | None, platform: str, environment: str | None = None) -> str:
    name = entry["name"]
    environment = environment or ("linux" if platform == "linux" else "personal_windows")
    environment_meta = entry.get("environments", {}).get(environment)
    label = {
        "linux": "Linux",
        "personal_windows": "Personal Windows",
        "corporate_windows": "Corporate Windows",
    }[environment]
    lines = [f"# {name} — {label} guide", ""]

    if environment == "corporate_windows":
        lines.extend([
            "This guide covers restricted Windows setup only. For unrestricted Windows, see [README.windows.md](README.windows.md); for features, shared commands, limitations, and the safety model, see [README.md](README.md).",
            "",
            "Corporate Windows is a local-only environment: no Devin VM, QwenPaw, Slack dependency, external compute, workload delegation or required external integration.",
            "",
        ])
        if environment_meta is None:
            lines.extend([
                "This artifact has no `corporate_windows` entry in `registry.json`, so compatibility is not claimed.",
                "",
            ])
            return "\n".join(lines)
        if not environment_meta.get("supported"):
            lines.extend([
                "This artifact is not supported in Corporate Windows.",
                "",
                f"Registry reason: {environment_meta.get('reason', 'not declared supported')}",
                "",
            ])
            return "\n".join(lines)
    elif environment == "personal_windows":
        lines.extend([
            "This guide covers unrestricted Windows setup. For restricted machines, see [README.corporate-windows.md](README.corporate-windows.md); for features, shared commands, limitations, and the safety model, see [README.md](README.md).",
            "",
            "Personal Windows uses the extended runtime: local execution plus optional Devin VM/QwenPaw delegation when this artifact supports it.",
            "",
        ])
    else:
        lines.extend([
            "This guide covers Linux setup only. See [README.md](README.md) for features, shared commands, limitations, and the safety model.",
            "",
            "Linux uses the extended runtime: local execution plus optional Devin VM/QwenPaw delegation when this artifact supports it.",
            "",
        ])

    lines.extend(["## Prerequisites", ""])
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
    lines.extend(["", "## Environment notes", ""])
    if environment == "corporate_windows":
        lines.extend([
            "- Keep execution local; do not configure VM, QwenPaw, external compute or workload delegation.",
            "- Registry-declared external integrations remain optional and are not installed by this guide.",
        ])
    elif environment == "personal_windows":
        lines.extend([
            "- Delegated runtime is optional; this guide installs local tooling only.",
            "- Corporate Windows is a separate local-only environment.",
        ])
    else:
        lines.extend([
            "- Delegated runtime is optional; this guide installs local tooling only.",
            "- Linux can use additional compute or Linux-compatible delegated tooling when available.",
        ])
    lines.append("- macOS is planned but not claimed as tested.")
    if environment == "corporate_windows":
        specifics = _WINDOWS_CORPORATE_SPECIFICS
    elif environment == "personal_windows":
        specifics = _WINDOWS_PERSONAL_SPECIFICS
    else:
        specifics = _LINUX_SPECIFICS
    lines.extend(["", f"## {label} specifics", ""])
    lines.extend(specifics)
    recurring = _render_recurring(name, platform, environment)
    if recurring:
        lines.extend(["", *recurring])
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
        pkg = entry.get("package")
        docs = repo
        if isinstance(pkg, dict) and pkg.get("path"):
            docs = repo / pkg["path"]
        elif entry.get("product_id") and entry["product_id"] != entry["name"]:
            member = repo / "packages" / entry["name"].removeprefix("devin-")
            if member.is_dir():
                docs = member
        legacy = docs / "README.pt-BR.md"
        if not (docs / "README.md").is_file():
            raise ValueError(f"{entry['name']}: README.md is missing")
        tool = tool_map.get(entry["name"])
        if tool:
            tool = {**tool, "requires_git": entry["name"] in registry.get("devkit", {}).get("git_required_tools", [])}
        plans.append({
            "name": entry["name"],
            "repo": repo,
            "legacy": legacy,
            "readme": docs / "README.md",
            "windows": docs / "README.windows.md",
            "corporate_windows": docs / "README.corporate-windows.md",
            "linux": docs / "README.linux.md",
            "tool": tool,
            "entry": entry,
        })
    return plans


def migrate(registry: dict[str, Any], root: Path, apply: bool = False) -> list[dict[str, str]]:
    plans = plan_migration(registry, root)
    report = []
    prepared = []
    for item in plans:
        report.append({"repo": item["name"], "legacy_removed": item["legacy"].exists(), "windows": str(item["windows"]), "corporate_windows": str(item["corporate_windows"]), "linux": str(item["linux"])})
        prepared.append({
            **item,
            "readme_content": language_switch(item["readme"].read_text(encoding="utf-8")),
            "windows_content": render_guide(item["entry"], item["tool"], "windows", "personal_windows"),
            "corporate_windows_content": render_guide(item["entry"], item["tool"], "windows", "corporate_windows"),
            "linux_content": render_guide(item["entry"], item["tool"], "linux", "linux"),
        })
    if not apply:
        return report
    for item in prepared:
        _atomic_write(item["readme"], item["readme_content"])
        _atomic_write(item["windows"], item["windows_content"])
        _atomic_write(item["corporate_windows"], item["corporate_windows_content"])
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
        if not item["windows"].is_file() or item["windows"].read_text(encoding="utf-8") != render_guide(item["entry"], item["tool"], "windows", "personal_windows"):
            errors.append(f"{item['name']}: README.windows.md is missing or stale")
        if not item["corporate_windows"].is_file() or item["corporate_windows"].read_text(encoding="utf-8") != render_guide(item["entry"], item["tool"], "windows", "corporate_windows"):
            errors.append(f"{item['name']}: README.corporate-windows.md is missing or stale")
        if not item["linux"].is_file() or item["linux"].read_text(encoding="utf-8") != render_guide(item["entry"], item["tool"], "linux", "linux"):
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
