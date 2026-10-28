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
        pkg_path = (entry.get("package") or {}).get("path")
        if pkg_path:
            return f"git+{entry['url']}.git#subdirectory={pkg_path}"
        return f"{entry['url']}/archive/refs/heads/main.tar.gz"
    if tool["source"] == "npm":
        return tool["package"]
    raise ValueError(f"{entry['name']}: no install specification for source {tool['source']!r}")


def _install_line(entry: dict[str, Any], tool: dict[str, Any] | None, platform: str, environment: str) -> list[str]:
    if entry["name"] == "devin-devkit":
        # The DevKit is the installer itself: the install section is about
        # installing *it*, then using it to install a profile.
        env_flag = environment.replace("_", "-")
        fence = "powershell" if platform == "windows" else "bash"
        lines = [
            "```" + fence,
            'uv tool install "git+https://github.com/Icaro0310/devin-devkit.git#subdirectory=packages/devkit"',
            "```",
            "",
            "From a local checkout, `uv tool install .` also works. Then list profiles and preview an install:",
            "",
            "```" + fence,
            "devin-devkit profiles",
            f"devin-devkit install qa --environment {env_flag}",
            "```",
            "",
            "The last command is a dry run; apply it explicitly:",
            "",
            "```" + fence,
            f"devin-devkit install qa --environment {env_flag} --apply",
            f"devin-devkit install full --environment {env_flag} --apply   # entire installable set",
            "```",
        ]
        if environment == "corporate_windows":
            lines.extend([
                "",
                "Do not omit `--environment corporate-windows` on a restricted machine, without it Windows defaults to the Personal Windows extended runtime.",
            ])
        if platform == "windows":
            lines.extend([
                "",
                "If Node.js is not available, choose a profile without `devin-bridge` instead of forcing a partial installation.",
            ])
        return lines
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
        src_path = "packages/office/src/devin_office/daemon.py"
        lines = [
            "Run the standalone read-only dashboard — installed CLI, or",
            "straight from a repository checkout:",
            "",
            "```" + ("powershell" if platform == "windows" else "bash"),
        ]
        if tool and tool.get("manager") == "uv":
            spec = _install_spec(entry, tool)
            quoted = json.dumps(spec) if platform == "windows" else repr(spec)
            lines.append(f"uv tool install {quoted}")
        lines += [
            "devin-office --port 8788  # installed package",
            f"{command} {src_path} --port 8788  # checkout",
            "```",
            "",
            "Open `http://localhost:8788`; the process stops with Ctrl+C.",
        ]
        return lines
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
    "last-resort fallback, no isolation, watch dependency conflicts.",
    "- **PATH:** executables land in `~/.local/bin`. If a command is not "
    "found, add `export PATH=\"$HOME/.local/bin:$PATH\"` to "
    "`~/.bashrc`/`~/.zshrc` and open a new shell.",
    "- **Distros:** tested on Ubuntu; Debian, Fedora and Arch follow the "
    "same steps, only `uv`/Python acquisition differs (distro package "
    "or the uv installer script).",
    "- **Headless and minimal environments:** no display is needed, "
    "every CLI is text-only. In containers or WSL, install `uv` and Git "
    "and follow the same steps; `XDG_*` paths resolve normally.",
    "- **Permissions:** tools read Devin data under `$XDG_DATA_HOME/devin` "
    "and write only their own config/state, no root or sudo is required.",
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
    "PowerShell 5.1, none require admin.",
    "- **Install location:** executables live under "
    "`%USERPROFILE%\\.local\\bin`; data under `%APPDATA%\\devin`. "
    "Nothing touches `Program Files` or the registry.",
    "- **WSL:** treat it as a Linux machine, follow "
    "[README.linux.md](README.linux.md) inside it.",
    "- **Uninstall:** `uv tool uninstall <package>` (or `npm uninstall -g` "
    "for a Node.js tool) removes the CLI; delete `%APPDATA%\\devin` to "
    "remove local data. No services or scheduled tasks are left behind.",
]

_WINDOWS_CORPORATE_SPECIFICS = [
    "- **No admin rights needed:** `uv` and every tool install under "
    "`%LOCALAPPDATA%`/`%APPDATA%`, nothing writes to `Program Files`, "
    "the registry, or requires elevation.",
    "- **Proxy:** set `HTTPS_PROXY`/`HTTP_PROXY` before installing. Per "
    "session: `$env:HTTPS_PROXY=\"http://proxy:port\"`; persistently: "
    "`setx HTTPS_PROXY \"http://proxy:port\"`. `uv`, `pip` and `npm` "
    "honor them.",
    "- **TLS inspection:** if the corporate proxy intercepts TLS, point "
    "the tools at the company CA bundle: "
    "`$env:REQUESTS_CA_BUNDLE=\"C:\\path\\corp-root.pem\"` for "
    "pip/requests and `$env:SSL_CERT_FILE=\"C:\\path\\corp-root.pem\"` "
    "for uv and urllib (see the Zscaler section for the full per-tool "
    "map). Certificate "
    "errors at install time mean the proxy, not the package.",
    "- **Execution policy:** installed CLIs are real executables, "
    "`Set-ExecutionPolicy` only matters for `.ps1` scripts from a "
    "checkout; `-Scope CurrentUser RemoteSigned` suffices, no admin.",
    "- **Blocked installers:** if winget/Store are disabled by policy, "
    "`uv` installs as a standalone binary, download the GitHub release "
    "zip, extract to `%LOCALAPPDATA%\\bin`, add it to PATH.",
    "- **Long paths:** keep checkout/install roots short (`C:\\dev`), "
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
    "(`pip download setuptools wheel -d wheels\\`, into the folder "
    "being copied) and install it first (`pip install --no-index "
    "--find-links wheels\\ setuptools wheel`; `--no-build-isolation` "
    "needs the backend installed, not only staged), then install with "
    "`pip install --no-index --find-links wheels\\ --no-build-isolation .` "
    "inside the checkout.",
]

# Per-entry "Fully local runtime" bullet — each guide must name ITS OWN
# outbound surface. A verbatim doctor sentence previously named
# devin-doctor's exception in every generated guide (audit 2026-10-11).
_DEFAULT_NETWORK_RUNTIME = (
    "installed tools make no required network calls, this tool has none; "
    "it reads `sessions.db` and local stores only."
)
_NETWORK_RUNTIME: dict[str, str] = {
    "devin-explore": (
        "installed tools make no required network calls, they read "
        "`sessions.db` and local stores only. Two exceptions, both "
        "disableable: devin-doctor's update check (fetches the DevKit "
        "manifest) self-skips when unreachable or with "
        "`DEVIN_DOCTOR_OFFLINE=1`, and `capabilities --probe-network` "
        "dials out only when the flag is passed."
    ),
    "devin-assure": (
        "the core audit is fully offline. Two opt-in exceptions that do "
        "not apply under local-only: `audit --source mcp` POSTs to "
        "`https://mcp.devin.ai/mcp` with `DEVIN_API_KEY` (fail-closed "
        "without it; `DEVIN_ORG_ID` is sent only when set, for tokens "
        "that need explicit org context; `DEVIN_MCP_URL` overrides the "
        "endpoint), and `--online`/`--allow-domain` makes HEAD requests "
        "to allowlisted claim URLs."
    ),
    "devin-evals": (
        "the replay corpus is fully offline. The opt-in `judge`/`ab-run` "
        "commands delegate through `DEVIN_BRIDGE_CMD` to real Devin "
        "sessions, external compute, off by default and not part of "
        "the local-only guarantee."
    ),
    "devin-janitor": (
        "no network calls. The opt-in `--judge command:<cmd>` hook "
        "spawns a user-supplied command, absent under local-only."
    ),
    "devin-control": (
        "this package launches `devin.exe acp`, it requires an "
        "authenticated Devin runtime and Cognition reachability, i.e. "
        "delegated external compute, and is therefore not part of the "
        "local-only guarantee."
    ),
    "devin-switch": (
        "the tool itself makes no network calls (it rewrites local config "
        "files only). One caveat: the bundled `corporate` profile registers "
        "remote HTTPS MCP endpoints (`mcp.corp.example.com/...`) through the "
        "company gateway, so sessions running under that profile do reach "
        "the network. The endpoints are placeholders to edit, inert until "
        "configured."
    ),
    "devin-office": (
        "the standalone dashboard binds 127.0.0.1 only and reads "
        "`sessions.db`. Opt-in surfaces that leave the machine, all off "
        "by default and absent under local-only: `probe.py` POSTs to "
        "`OFFICE_HUB`(s), `hub.py` fetches `OFFICE_ECO_URL`, and "
        "`OFFICE_CONTROL_ENABLED=1` spawns `devin acp`."
    ),
    "devin-orchestrator": (
        "the planner makes no network calls. Worker fan-out executes "
        "as Devin-local subagents; in corporate, treat the output as "
        "a plan to execute manually, not delegation."
    ),
    "devin-brain": (
        "devin-memory makes no network calls: the MCP server speaks "
        "stdio and all reads are local sqlite."
    ),
    "devin-judge": (
        "set `POORDJAEVIN_BACKEND=nli` for local-only use: the default "
        "`serve`/`gate` backend (`acp`) drives a Devin cloud session. "
        "The `nli` backend downloads a ~400 MB model from Hugging Face "
        "on first use. Pre-seed with `HF_HOME` + `HF_HUB_OFFLINE=1`, "
        "or use the pre-baked container image."
    ),
    "devin-powerups": (
        "tools run from the checkout and do call the network by "
        "design: `gh api`/urllib to api.github.com, pypi.org, "
        "pypistats.org and api.npmjs.org, plus optional MailerSend SMTP "
        "in `weekly_repo_report.py --send`. Nothing phones home at "
        "import time; every call is an explicit command."
    ),
    "devin-devkit": (
        "the DevKit is the installer, it cannot be local-only in the "
        "package sense: `install`/`update` fetch each tool's pinned spec "
        "(PyPI or GitHub archive), and `outdated`/`update` fetch the remote "
        "`manifest.json` to compare pins. Separately, `list` and dry-run "
        "`install` call `freshness_hint()`, which fetches `manifest.json` "
        "from `raw.githubusercontent.com` to warn when the bundled manifest "
        "is stale, it self-skips on failure (15s timeout) but still opens "
        "the connection. Since `devkit-v0.1.1` the off-switch ships in the "
        "published release: `DEVIN_DEVKIT_OFFLINE=1` skips the fetch for "
        "`list` and dry-run `install`, and a resolved `corporate_windows` "
        "environment suppresses the hint entirely. On a "
        "machine where any connection attempt is logged, export "
        "`DEVIN_DEVKIT_OFFLINE=1` or stage a fresh manifest locally. What the DevKit "
        "installs then runs under each tool's own local-only contract."
    ),
}

# Per-entry non-default data flags for the "Devin paths" line. The
# previous text cited `--data-dir`/`--config-dir` in every guide; several
# tools have different flag names (audit 2026-10-11).
_PATH_FLAGS: dict[str, str] = {
    "devin-explore": "`--data-dir`/`--config-dir`",
    "devin-graph": "`--sessions-db`/`--vscdb`/`--graph`",
    "devin-history": "`--sessions-db`/`--vscdb`",
    "devin-pm": "`--sessions-db`/`--vscdb` (or `DEVIN_PM_SESSIONS_DB`/`DEVIN_PM_STATE_VSCDB`)",
    "devin-search": "`--sessions-db`/`--acp-dir`",
    "devin-brain": "`--db` (memory.db store) and `--sessions-db`",
    "devin-backup": "`--data-dir`/`--config-dir`",
    "devin-janitor": "`--data-dir`/`--config-dir` (plus `--sessions-db`/`--acp-dir`/`--locks-dir` for finer control)",
    "devin-state": "`session-end` takes `--sessions-db`/`--data-dir`/`--out`; `verify-publish` takes `--verdicts-dir`",
    "devin-assure": "`--data-dir`/`--sessions-db`",
    "devin-evals": "`run --sessions-db`/`--evals`; `ab-run --work-dir` picks the A/B workspace-copy location",
    "devin-metrics": "`--sessions-db`/`--acp-dir`",
    "devin-switch": "`--data-dir`/`--config-dir`/`--profiles-dir`",
    "devin-skill-catalog": "`--config-dir`",
}
_DEFAULT_PATH_FLAGS = "`--data-dir`/`--config-dir` where the tool documents them"

# Extra scope line under the corporate local-only promise, for packages
# whose own contract is broader than local-only (audit 2026-10-11: bridge
# launches devin.exe acp, external compute by design).
_CORP_SCOPE_NOTE: dict[str, str] = {
    "devin-devkit": (
        "**Scope note:** the DevKit installs the other tools, so its own "
        "contract is install-time by nature. The local-only promise applies "
        "to what it installs; the plan fails closed when a selected profile "
        "contains a tool that violates the constraints. The mode is explicit "
        "because the OS cannot distinguish a personal from a restricted "
        "corporate machine."
    ),
    "devin-control": (
        "**Scope note:** this package is a bridge to the Devin agent runtime. "
        "It is documented here for completeness but sits outside the "
        "local-only guarantee above, since its function is delegated "
        "external compute."
    ),
}

# Extra sections injected before Troubleshooting — hand-curated content
# migrated into the generator so regeneration does not drop it. The
# 2026-10-11 audit found adapters/caveat sections living only on disk; the
# follow-up docs-sync audit ported the remaining per-leaf curation (MCP
# host configs, agent env, Devin-paths notes, troubleshooting bullets).
# Line wrapping below is verbatim from the reviewed leaf guides so
# regenerated docs stay byte-identical.
def _mcp_host_configs(server: str) -> list[str]:
    """Full `### MCP host configs` block shared by the assure monorepo
    adapters (evals/metrics); `server` is the registered server name."""
    return [
        "### MCP host configs",
        "",
        f"Same stdio server in other hosts — server name `{server}`:",
        "",
        "**Zed** — `context_servers` in `~/.config/zed/settings.json`:",
        "",
        "```jsonc",
        f'{{ "context_servers": {{ "{server}": {{ "command": {{ "path": "{server}-mcp", "args": [] }} }} }} }}',
        "```",
        "",
        "**JetBrains AI Assistant** — Settings → Tools → AI Assistant → Model Context Protocol → Add:",
        "",
        "```json",
        f'{{ "mcpServers": {{ "{server}": {{ "command": "{server}-mcp" }} }} }}',
        "```",
        "",
        "**Antigravity** — `~/.gemini/config/mcp_config.json`:",
        "",
        "```json",
        f'{{ "mcpServers": {{ "{server}": {{ "command": "{server}-mcp" }} }} }}',
        "```",
    ]


# `uvx --from` resolution clauses for the Adapters bullet — how the
# manifest-launched MCP server resolves today. `{pkg}` is substituted by
# the caller. SHIPPED = the 0.1.1 wheels already carry the console script
# (devin-state monorepo); PENDING = the extra exists but the published
# wheel still predates the entry point (devin-assure monorepo).
_RESOLUTION_SHIPPED = (
    "launches the server through `uvx --from 'devin-{pkg}[mcp]' devin-{pkg}-mcp`, which\n"
    "  resolves from PyPI as of 0.1.1 (the 0.1.0 wheel predates both the\n"
    "  entry point and the `mcp` extra). On 0.1.0 or a source checkout, an\n"
    "  editable install does not change what `uvx --from` resolves —\n"
    "  either run the source-installed `devin-{pkg}-mcp` directly, or\n"
    "  point a local manifest copy at the checkout:\n"
    "  `uvx --from './packages/{pkg}[mcp]' devin-{pkg}-mcp`."
)
_RESOLUTION_SHIPPED_SHORT = (
    "launches the server through `uvx --from 'devin-{pkg}[mcp]' devin-{pkg}-mcp`, which\n"
    "  resolves from PyPI as of 0.1.1 (the 0.1.0 wheel predates the entry\n"
    "  point); on 0.1.0 install from\n"
    "  source (`pip install -e 'packages/{pkg}[mcp]'` from a checkout)."
)
_RESOLUTION_PENDING = (
    "launches the server through `uvx --from 'devin-{pkg}[mcp]' devin-{pkg}-mcp`, which\n"
    "  resolves once the next PyPI release ships. Until then, an\n"
    "  editable install does not change what `uvx --from` resolves —\n"
    "  either run the source-installed `devin-{pkg}-mcp` directly, or\n"
    "  point a local manifest copy at the checkout:\n"
    "  `uvx --from './packages/{pkg}[mcp]' devin-{pkg}-mcp`."
)
_RESOLUTION_PENDING_SHORT = (
    "launches the server through `uvx --from 'devin-{pkg}[mcp]' devin-{pkg}-mcp`, which\n"
    "  resolves once the next PyPI release ships — until then install from\n"
    "  source (`pip install -e 'packages/{pkg}[mcp]'` from a checkout)."
)

# One-off resolutions whose line wrapping does not fit the shared shapes.
_DEVKIT_RESOLUTION = (
    "launches the server through `uvx --from 'devin-devkit[mcp]'\n"
    "  devin-devkit-mcp`, which resolves once the first PyPI release ships.\n"
    "  Until then, an editable install does not change what `uvx --from`\n"
    "  resolves — either run the source-installed `devin-devkit-mcp`\n"
    "  directly, or point a local manifest copy at the checkout:\n"
    "  `uvx --from './packages/devkit[mcp]' devin-devkit-mcp`."
)
_SKILL_CATALOG_RESOLUTION = (
    "launches the server through `uvx --from 'devin-skill-catalog[mcp]'\n"
    "  devin-skill-catalog-mcp`, which resolves from 0.1.1 on (the 0.1.0 wheel\n"
    "  predates the console script)."
)
_DOCTOR_RESOLUTION = (
    "launches the server through `uvx --from 'devin-doctor[mcp]'\n"
    "  devin-doctor-mcp`, which resolves once the matching PyPI release\n"
    "  ships. Until then, an editable install does not change what\n"
    "  `uvx --from` resolves — either run the source-installed\n"
    "  `devin-doctor-mcp` directly, or point a local manifest copy at the\n"
    "  checkout: `uvx --from './packages/doctor[mcp]' devin-doctor-mcp`."
)

# devin-doctor ships the host snippets in its main README, so the platform
# guides point there instead of duplicating the JSON blocks.
_DOCTOR_HOST_CONFIGS = [
    "### MCP host configs",
    "",
    "Same stdio config in every host — see [README.md § MCP host configs](README.md#mcp-host-configs).",
]


def _adapters_extra(
    pkg: str,
    repo: str,
    resolution: str,
    *,
    inline_server: bool = False,
    host_configs: list[str] | None = None,
) -> list[str]:
    """Builds the `## Adapters` extra. `repo` is the GitHub repo fragment in
    the `devin plugins install` line (monorepo holder, e.g. `devin-state`);
    `resolution` is the manifest/`uvx` continuation text (one of the
    _RESOLUTION_* constants). `inline_server` picks the single-line MCP
    bullet shape used by the monorepo guides; `host_configs` appends a
    `### MCP host configs` block."""
    server = (
        f"- MCP server: `pip install 'devin-{pkg}[mcp]'` then run `devin-{pkg}-mcp` (stdio).\n"
        "  Read-only tools only."
        if inline_server else
        f"- MCP server: `pip install 'devin-{pkg}[mcp]'` then run\n"
        f"  `devin-{pkg}-mcp` (stdio). Read-only tools only."
    )
    lines = [
        "## Adapters (MCP / Devin skill / plugin)",
        "",
        server,
        "- Devin plugin + skill: `devin plugins install",
        f"  Icaro0310/{repo}#packages/{pkg}/adapters`. The manifest",
        "  " + resolution.format(pkg=pkg),
    ]
    if host_configs:
        lines.extend(["", *host_configs])
    return lines

_OFFICE_LINUX_EXTRA = [
    "## Monitoring caveat: `Restart=` crash-loops are invisible to `--failed`",
    "",
    "A unit with `Restart=always|on-failure` that fails on every start never",
    "reaches the `failed` state: it sits in `activating (auto-restart)`",
    "forever. `systemctl --failed` prints clean while a service is in a",
    "thousands-deep crash loop (real incident: probe dead ~21h, restart",
    "counter >7000, after its `WorkingDirectory` was moved away in a reorg).",
    "",
    "To find crash-looping units:",
    "",
    "```bash",
    "systemctl --user list-units --state=activating",
    "systemctl --user show devin-office-probe -p NRestarts -p ActiveState",
    "```",
    "",
    "The durable guard is not a state listing but an **external freshness",
    "check**: the hub exposes `probe.lastIngestAgoS` in `GET /api/state`, and",
    "an independent cron job alerts when the producer stops landing data.",
    "Producer liveness must never be reported by the producer. A dead probe",
    "cannot tell you it is dead.",
    "",
]

# The doctor VS Code extension is itself local-only (it shells out to
# `devin-doctor check --json` and renders the result), but it is the first
# surface that runs inside a container that makes network calls by design.
# The extension cannot promise local-only for its host, so the guide says
# what to disable/check instead (audit 2026-10-11, post-publish review).
_DOCTOR_VSCODE_CORP = [
    "## VS Code extension: o container não é local-only",
    "",
    "A extensão `icaro0310.devin-doctor` (Open VSX) é thin shell: corre `devin-doctor check --json`, `report --md` e `plan` no PATH e só renderiza o resultado — a extensão em si não faz chamadas de rede. O container, porém, faz rede por desenho e fica fora do contrato local-only:",
    "",
    "- **Auto-update do marketplace:** `extensions.autoUpdate: false` (e `extensions.autoCheckUpdates: false`) para o editor não falar com o registry sem pedir. Se a política do TI exigir artefato auditado, instale por VSIX sideloaded em vez do marketplace.",
    "- **Telemetria:** `telemetry.telemetryLevel: \"off\"` no profile corporate, ou a policy equivalente definida pelo TI.",
    "- **Política de extensões:** confirme com o TI se extensões de marketplace são permitidas ou se só VSIX aprovado internamente — o `.vsix` publicado e o source em `packages/doctor/adapters/vscode/` são o artefato auditável.",
    "- **Workspace trust:** a extensão só precisa de executar o CLI no PATH; o modo Restricted do workspace segue a política padrão do TI.",
    "- **Extension host:** cada extensão instalada corre num processo com o perfil de rede do editor — a auditoria de \"quem faz chamadas externas\" cobre o VS Code e o marketplace configurado (Open VSX, Marketplace ou nenhum), não só este `.vsix`.",
    "- **Update check do `devin-doctor`:** cada invocação do CLI — incluindo as que a extensão faz por si (`check --json`, `report --md`, `plan`) — pode correr o update check que busca o manifest do DevKit. Self-skip quando inalcançável; para desligar de vez, `DEVIN_DOCTOR_OFFLINE=1`.",
    "",
]

def _devkit_dev_extra(platform: str) -> list[str]:
    if platform == "windows":
        cmd = ["cd ..\\devin-explore\\packages\\doctor", "uv venv", "uv pip install --python .venv\\Scripts\\python.exe -e ..\\..\\..\\devin-internals-spec -e ."]
    else:
        cmd = ["cd ../devin-explore/packages/doctor", "uv venv", "uv pip install --python .venv/bin/python -e ../../../devin-internals-spec -e ."]
    return [
        "## Local development with sibling checkouts",
        "",
        "For a package such as `devin-doctor`, keep the published version",
        "constraint in its `pyproject.toml`; install sibling sources editably",
        "only in the development environment. With `devin-explore` and",
        "`devin-internals-spec` checked out next to this repository, run",
        "from the `devin-devkit` repository root:",
        "",
        "```" + ("powershell" if platform == "windows" else "bash"),
        *cmd,
        "```",
        "",
    ]


_DEVKIT_COMPAT_EXTRA = [
    "## Compatibility",
    "",
    "The generated [compatibility matrix](COMPATIBILITY.md) comes from",
    "`devin-powerups/registry.json`. Entries marked `Local only` install",
    "without VM, QwenPaw, external compute, workload delegation, or",
    "required external integrations; other entries carry a registry reason.",
    "",
]

_DEVKIT_AIRGAPPED_EXTRA = [
    "## Offline / air-gapped",
    "",
    "The wheel-staging procedure above covers the tools; the DevKit itself",
    "needs the network it manages, installing tools fetches PyPI/GitHub",
    "archives. On air-gapped machines pre-stage the wheels plus a fresh",
    "`manifest.json`, `outdated`/`update` cannot run without the remote",
    "manifest.",
    "",
]

# `## Agent env` for the bridge guides — the env-var surface for choosing
# a non-default ACP agent (leaf-curated since the resolver shipped).
def _bridge_agent_env(environment: str) -> list[str]:
    if environment == "linux":
        intro = "The bridge drives `devin acp` by default (`devin` on `PATH` or `DEVIN_CLI_PATH`); env vars select a different ACP-compatible agent or override its locations:"
        fence = "bash"
        exports = [
            "export BRIDGE_AGENT=devin                              # strategy name (default)",
            "export BRIDGE_AGENT_BIN=/opt/my-agent/bin/cli          # explicit executable",
            "export BRIDGE_AGENT_ARGS='[\"--acp\"]'                   # argv override (JSON array)",
            "export BRIDGE_AGENT_AUTH=none                          # auth methodId; \"none\" skips",
            "export BRIDGE_CREDENTIALS_PATH=/etc/my-agent/credentials.toml",
        ]
    else:
        intro = "The bridge drives `devin.exe acp` by default (`devin.exe` on `PATH`, the per-user install dir, or `DEVIN_CLI_PATH`); env vars select a different ACP-compatible agent or override its locations"
        intro += " — per-user env vars, no admin needed:" if environment == "corporate_windows" else ":"
        fence = "powershell"
        exports = [
            "$env:BRIDGE_AGENT = \"devin\"                                   # strategy name (default)",
            "$env:BRIDGE_AGENT_BIN = \"C:\\tools\\my-agent\\agent.exe\"         # explicit executable",
            "$env:BRIDGE_AGENT_ARGS = '[\"--acp\"]'                          # argv override (JSON array)",
            "$env:BRIDGE_AGENT_AUTH = \"none\"                               # auth methodId; \"none\" skips",
            "$env:BRIDGE_CREDENTIALS_PATH = \"C:\\tools\\my-agent\\credentials.toml\"",
        ]
    return [
        "## Agent env",
        "",
        intro,
        "",
        "```" + fence,
        *exports,
        "```",
        "",
        "`DEVIN_CLI_PATH`/`DEVIN_CREDENTIALS_PATH` remain valid legacy overrides. See [README.md](README.md#choosing-the-agent-bridge_agent) for the resolution order.",
    ]


# (entry name, doc key) -> extra section lines.
_PLATFORM_EXTRAS: dict[tuple[str, str], list[str]] = {
    ("devin-devkit", "windows"): _DEVKIT_COMPAT_EXTRA + _devkit_dev_extra("windows") + [""] + _adapters_extra("devkit", "devin-devkit", _DEVKIT_RESOLUTION),
    ("devin-devkit", "linux"): _DEVKIT_COMPAT_EXTRA + _devkit_dev_extra("linux") + [""] + _adapters_extra("devkit", "devin-devkit", _DEVKIT_RESOLUTION),
    ("devin-devkit", "corporate_windows"): _DEVKIT_COMPAT_EXTRA + _DEVKIT_AIRGAPPED_EXTRA + _devkit_dev_extra("windows") + ["", ""] + _adapters_extra("devkit", "devin-devkit", _DEVKIT_RESOLUTION),
    ("devin-skill-catalog", "windows"): [""] + _adapters_extra("skill-catalog", "devin-devkit", _SKILL_CATALOG_RESOLUTION),
    ("devin-skill-catalog", "corporate_windows"): [""] + _adapters_extra("skill-catalog", "devin-devkit", _SKILL_CATALOG_RESOLUTION),
    ("devin-skill-catalog", "linux"): [""] + _adapters_extra("skill-catalog", "devin-devkit", _SKILL_CATALOG_RESOLUTION),
    ("devin-backup", "windows"): _adapters_extra("backup", "devin-state", _RESOLUTION_SHIPPED, inline_server=True) + [""],
    ("devin-backup", "corporate_windows"): _adapters_extra("backup", "devin-state", _RESOLUTION_SHIPPED_SHORT, inline_server=True) + [""],
    ("devin-backup", "linux"): _adapters_extra("backup", "devin-state", _RESOLUTION_SHIPPED, inline_server=True) + [""],
    ("devin-janitor", "windows"): _adapters_extra("janitor", "devin-state", _RESOLUTION_SHIPPED, inline_server=True) + [""],
    ("devin-janitor", "corporate_windows"): _adapters_extra("janitor", "devin-state", _RESOLUTION_SHIPPED_SHORT, inline_server=True) + [""],
    ("devin-janitor", "linux"): _adapters_extra("janitor", "devin-state", _RESOLUTION_SHIPPED, inline_server=True) + [""],
    ("devin-evals", "windows"): _adapters_extra("evals", "devin-assure", _RESOLUTION_PENDING, inline_server=True, host_configs=_mcp_host_configs("devin-evals")),
    ("devin-evals", "corporate_windows"): _adapters_extra("evals", "devin-assure", _RESOLUTION_PENDING_SHORT, inline_server=True, host_configs=_mcp_host_configs("devin-evals")),
    ("devin-evals", "linux"): _adapters_extra("evals", "devin-assure", _RESOLUTION_PENDING, inline_server=True, host_configs=_mcp_host_configs("devin-evals")),
    ("devin-metrics", "windows"): _adapters_extra("metrics", "devin-assure", _RESOLUTION_PENDING, inline_server=True, host_configs=_mcp_host_configs("devin-metrics")),
    ("devin-metrics", "corporate_windows"): _adapters_extra("metrics", "devin-assure", _RESOLUTION_PENDING_SHORT, inline_server=True, host_configs=_mcp_host_configs("devin-metrics")),
    ("devin-metrics", "linux"): _adapters_extra("metrics", "devin-assure", _RESOLUTION_PENDING, inline_server=True, host_configs=_mcp_host_configs("devin-metrics")),
    ("devin-office", "linux"): _OFFICE_LINUX_EXTRA,
    # devin-explore's registry entry renders the devin-doctor package guide.
    ("devin-explore", "windows"): [""] + _adapters_extra("doctor", "devin-explore", _DOCTOR_RESOLUTION, host_configs=_DOCTOR_HOST_CONFIGS),
    ("devin-explore", "linux"): [""] + _adapters_extra("doctor", "devin-explore", _DOCTOR_RESOLUTION, host_configs=_DOCTOR_HOST_CONFIGS),
    ("devin-explore", "corporate_windows"): _DOCTOR_VSCODE_CORP + ["", ""] + _adapters_extra("doctor", "devin-explore", _DOCTOR_RESOLUTION, host_configs=_DOCTOR_HOST_CONFIGS),
}

# "Devin paths" body overrides — full replacement of the generated body
# (session/ACP lines AND the flags line, which the curated text embeds
# inside richer paragraphs). internals-spec documents the ecosystem
# bookkeeping store; devin-search auto-detects its own sources.
_DEVIN_PATHS_BODY: dict[tuple[str, str], list[str]] = {
    ("devin-internals-spec", "windows"): [
        "Session data normally lives under `%APPDATA%\\devin\\cli\\`; UI state and ACP stores under `%APPDATA%\\Devin\\User\\` (capitalized `Devin`).",
        "Ecosystem bookkeeping — `machine-id`, `devin-profile.json`, `hooks.json`, `plans.jsonl`, `metrics/` — anchors under `%APPDATA%\\Devin\\.devin-ecosystem\\`.",
        "`DEVIN_DATA_DIR`/`DEVIN_CONFIG_DIR` override the roots; `DEVIN_MACHINE_ID`/`DEVIN_ECOSYSTEM_PROFILE` override identity. Use `--data-dir`/`--config-dir` where the tool documents them for non-default locations.",
    ],
    ("devin-internals-spec", "corporate_windows"): [
        "Session data normally lives under `%APPDATA%\\devin\\cli\\`; UI state and ACP stores under `%APPDATA%\\Devin\\User\\` (capitalized `Devin`).",
        "Ecosystem bookkeeping — `machine-id`, `devin-profile.json`, `hooks.json`, `plans.jsonl`, `metrics/` — anchors under `%APPDATA%\\Devin\\.devin-ecosystem\\`.",
        "`DEVIN_DATA_DIR`/`DEVIN_CONFIG_DIR` override the roots; `DEVIN_MACHINE_ID`/`DEVIN_ECOSYSTEM_PROFILE` override identity. Use `--data-dir`/`--config-dir` where the tool documents them for non-default locations.",
    ],
    ("devin-internals-spec", "linux"): [
        "Session data normally lives under `${XDG_DATA_HOME:-$HOME/.local/share}/devin/cli/`; UI state and ACP stores under `${XDG_CONFIG_HOME:-$HOME/.config}/Devin/User/` (capitalized `Devin` — a lowercase `$XDG_CONFIG_HOME/devin` CLI root also exists in the wild and is probed as a legacy fallback).",
        "Ecosystem bookkeeping — `machine-id` (mode `0600`), `devin-profile.json`, `hooks.json`, `plans.jsonl`, `metrics/` — anchors under `<config>/.devin-ecosystem/`, resolved independently of `User/` probing so identity files never move.",
        "`DEVIN_DATA_DIR`/`DEVIN_CONFIG_DIR` override the roots; `DEVIN_MACHINE_ID`/`DEVIN_ECOSYSTEM_PROFILE` override identity. Use `--data-dir`/`--config-dir` where the tool documents them for non-default locations.",
    ],
    ("devin-search", "windows"): [
        "The CLI session DB is auto-detected at `%APPDATA%\\devin\\cli\\sessions.db`; ACP logs are searched under `%APPDATA%\\Devin\\User\\acp-messages`.",
        "Use `--sessions-db`/`--acp-dir` for non-default locations.",
    ],
    ("devin-search", "corporate_windows"): [
        "The CLI session DB is auto-detected at `%APPDATA%\\devin\\cli\\sessions.db`; ACP logs are searched under `%APPDATA%\\Devin\\User\\acp-messages`.",
        "Use `--sessions-db`/`--acp-dir` for non-default locations.",
    ],
    ("devin-search", "linux"): [
        "The CLI session DB is auto-detected at `${XDG_DATA_HOME:-$HOME/.local/share}/devin/cli/sessions.db`; ACP logs are searched under `${XDG_CONFIG_HOME:-$HOME/.config}/Devin/User/acp-messages`. A legacy `~/.config/devin` layout is also checked.",
        "Use `--sessions-db`/`--acp-dir` for non-default locations.",
    ],
}

# Lines appended after the generated "Devin paths" body — extra
# paragraphs or whole sections that belong before "## Environment notes".
_DEVIN_PATHS_EXTRA: dict[tuple[str, str], list[str]] = {
    ("devin-explore", "windows"): [
        "",
        "devin-doctor's own state (the `automation` check's snapshot baseline) lives under `%LOCALAPPDATA%\\devin-doctor\\` (machine-local, not Roaming — a per-host scheduler baseline must not roam) — never inside the inspected data dir; `DEVIN_DOCTOR_STATE_DIR` overrides.",
    ],
    ("devin-explore", "corporate_windows"): [
        "",
        "devin-doctor's own state (the `automation` check's snapshot baseline) lives under `%LOCALAPPDATA%\\devin-doctor\\` (machine-local, not Roaming — a per-host scheduler baseline must not roam) — never inside the inspected data dir; `DEVIN_DOCTOR_STATE_DIR` overrides.",
    ],
    ("devin-explore", "linux"): [
        "",
        "devin-doctor's own state (the `automation` check's snapshot baseline) lives under `${XDG_DATA_HOME:-$HOME/.local/share}/devin-doctor/` — never inside the inspected data dir; `DEVIN_DOCTOR_STATE_DIR` overrides.",
    ],
    ("devin-janitor", "linux"): [
        "",
        "Detection fallback for older/migrated installs: without `DEVIN_DATA_DIR`",
        "the data root is the first of `${XDG_DATA_HOME:-~/.local/share}/devin`,",
        "`${XDG_CONFIG_HOME:-~/.config}/devin`, `~/devin` that already contains a",
        "`cli/sessions.db` — so a store created under the config home keeps",
        "being found after the convention moved to data home.",
    ],
    ("devin-control", "windows"): ["", *_bridge_agent_env("personal_windows")],
    ("devin-control", "corporate_windows"): ["", *_bridge_agent_env("corporate_windows")],
    ("devin-control", "linux"): ["", *_bridge_agent_env("linux")],
}

# Personal-Windows "Environment notes" bullet naming the corporate
# environment, overridden where the default undersells the package's own
# network surface (devkit is the installer: corporate install-time calls
# are unavoidable even though the runtime contract stays local-only).
_ENV_CORP_LINE: dict[str, str] = {
    "devin-devkit": "- Corporate Windows is a separate local-only environment (runtime; `install`/`update` still reach PyPI, npm or GitHub archives).",
}

# Bullet replacements inside the "<Platform> specifics" lists, keyed by
# the bullet's bold label (qa-pack keeps its `install --daily` caveat).
_SPECIFICS_REPLACE: dict[tuple[str, str], dict[str, str]] = {
    ("devin-assure", "linux"): {
        "**Scheduling:**": "- **Scheduling:** optional recurring work belongs to `systemd --user` timers or cron. `devin-qa-pack install --daily` registers a tagged `@daily` crontab line (`# devin-qa-pack-audit-daily`); remove it with `crontab -e` (delete the tagged line) — nothing else installs jobs.",
    },
    ("devin-assure", "windows"): {
        "**Uninstall:**": "- **Uninstall:** `uv tool uninstall <package>` (or `npm uninstall -g` for a Node.js tool) removes the CLI; delete `%APPDATA%\\devin` to remove local data. If you ran `devin-qa-pack install --daily`, also remove the scheduled task it registered: `schtasks /delete /tn devin-qa-pack-audit-daily /f`.",
    },
}

# Extra specifics bullets: (anchor label, bullet) — inserted before the
# bullet carrying the anchor's bold label, or appended when anchor is None.
_SPECIFICS_INSERT: dict[tuple[str, str], list[tuple[str | None, str]]] = {
    ("devin-explore", "windows"): [
        ("**Uninstall:**", "- **Toolchain check:** `devin-doctor check` names missing test/build tools with `winget install` commands (`Python.Python.3`, `OpenJS.NodeJS`, `Git.Git`). A `python.exe` that resolves but opens the Microsoft Store is reported as a broken shim — and when the Store-alias stub is the only `python`, the pip fix names the interpreter that actually resolved (`python -m ensurepip`, not `py`)."),
    ],
    ("devin-explore", "linux"): [
        (None, "- **Toolchain check:** `devin-doctor check` names each missing test/build tool with a concrete install command — `apt` on Debian/Ubuntu (`sudo apt install python3-pip python3-venv nodejs npm git`), `dnf` on Fedora, `pacman` on Arch; other distros get a generic package-name hint. A `nodejs`-only box reports node as **WARN** — scripts invoking `node` still fail until the real name exists."),
    ],
    ("devin-explore", "corporate_windows"): [
        (None, "- **Toolchain check:** `devin-doctor check` names missing test/build tools with `winget install` commands; behind blocked winget/Store policy the same checks tell you which piece (`python`/`node`/`git`) is absent so IT can allowlist or provision it."),
    ],
}

# Lines injected between the corporate "Fully local runtime" bullet and
# the Zscaler section — extra runtime bullets or whole sections.
_POST_RUNTIME_EXTRAS: dict[tuple[str, str], list[str]] = {
    ("devin-judge", "corporate_windows"): [
        "- **VS Code without Devin:** where Copilot (or another approved chat model) is available but the Devin CLI is not, `POORDJAEVIN_BACKEND=vscode-lm` scores through the `icaro0310.judge` extension instead. The extension serves a loopback-only endpoint (`127.0.0.1`, random port, bearer token in the endpoint file under `%LOCALAPPDATA%\\poordjaevin`); scoring text goes to the chat model's provider, not to Devin. If your EDR flags localhost listeners, this backend is opt-in and `nli` keeps working without it.",
    ],
    ("devin-assure", "corporate_windows"): [
        "",
        "## Read-only operation",
        "",
        "Every audit command in this package reads local Devin data only: the session database (`sessions.db`), the `.devin/` config tree, and transcript exports. Nothing writes back to those stores, uploads session content, or requires a running Devin instance — point the tools at a copied database (`--sessions-db C:\\path\\sessions-copy.db`) if you want a hard guarantee that the live store is untouched.",
        "",
        "Recommended posture on a restricted machine: run audits against a file copy or the filesystem-snapshot path, not the live `%APPDATA%\\devin\\cli\\sessions.db`. The tools never need write access to Devin data; if a command ever asks for it, that is a bug, not a requirement.",
        "",
        "## What cannot be delegated from a restricted machine",
        "",
        "Corporate mode is local-only by posture, not by enforcement — the package has no corporate-mode switch. The capabilities below are unavailable *by choice* on a restricted machine; the opt-in flags exist in the CLI and must simply stay unused:",
        "",
        "- **Workload delegation** — no Devin VM, no remote workers, no ACP bridge (QwenPaw), no cloud sandboxes.",
        "- **External integrations** — Slack, GitHub Actions, hosted dashboards and webhook-style notifications stay off; nothing listens on the network.",
        "- **Online claim verification** — `--online`/`--allow-domain` and `--source mcp` are opt-in everywhere else and stay off here; audits run offline against local artifacts.",
        "- **Model calls** — audits are deterministic extraction and matching; no LLM is consulted, so nothing leaves the machine for inference either.",
        "",
        "If a workflow needs any of the above, run it on the unrestricted machine and copy only the resulting report artifacts back.",
        "",
        "## Reporting false positives without uploading session content",
        "",
        "Never paste raw session text into an issue or a chat channel on a restricted machine. To report a bad audit result:",
        "",
        "1. Re-run the audit and keep only the verdict block — the report is **not** auto-redacted: claim details and command evidence are emitted raw. If `devin-redact` is installed (`uv tool install devin-redact`, from the devin-state repo), run the fragment through `devin-redact scan --text \"$(cat fragment.txt)\"` first so secrets, tokens, emails and home paths come out as `<REDACTED:hash>` placeholders.",
        "2. Verify locally that the output you will share contains no raw identifiers (search for your own name, domain, and any token prefixes). Without a redaction pass this check is mandatory, not optional.",
        "3. Paste only the redacted verdict block and the claim/line reference — never the surrounding session transcript, file paths outside the report, or screenshots of session content.",
        "",
        "For bug reports, the smallest useful unit is: the verdict line, the rule/pattern name it cites, and the redacted fragment it fired on.",
    ],
}

# Extra bullets appended at the end of "## Troubleshooting".
_TROUBLESHOOTING_EXTRAS: dict[tuple[str, str], list[str]] = {
    ("devin-brain", "windows"): [
        "- If `devin-memory-mcp` exits with `error: The MCP server needs the 'mcp' extra`\n"
        "  (the editor reports the server exiting with code 1), a bare `devin-memory`\n"
        "  install is on PATH — `uv tool install` does not add extras to an existing\n"
        "  tool. Force-reinstall with the extra: `uv tool install --force \"devin-memory[mcp]\"`\n"
        "  (or `pipx install --force devin-memory-mcp` for the shim).",
    ],
    ("devin-brain", "corporate_windows"): [
        "- If `devin-memory-mcp` exits with `error: The MCP server needs the 'mcp' extra`\n"
        "  (the editor reports the server exiting with code 1), a bare `devin-memory`\n"
        "  install is on PATH — `uv tool install` does not add extras to an existing\n"
        "  tool. Force-reinstall with the extra: `uv tool install --force \"devin-memory[mcp]\"`\n"
        "  (or `pipx install --force devin-memory-mcp` for the shim).",
    ],
    ("devin-brain", "linux"): [
        "- If `devin-memory-mcp` exits with `error: The MCP server needs the 'mcp' extra`\n"
        "  (VS Code reports the server exiting with code 1), a bare `devin-memory`\n"
        "  install is on PATH — `uv tool install` does not add extras to an existing\n"
        "  tool. Force-reinstall with the extra: `uv tool install --force 'devin-memory[mcp]'`\n"
        "  (or `pipx install --force devin-memory-mcp` for the shim).",
    ],
}

# Corporate Windows: Zscaler guidance (audit 2026-10-11 — zero mentions
# ecosystem-wide before this). Written in pt-BR per the audit's mandate.
# No em dashes: devin-judge's README convention bans them, and the block
# is shared by every corporate guide.
_ZSCALER = [
    "## Zscaler",
    "",
    "Zscaler é comum em ambientes corporativos e se comporta diferente de um proxy genérico. Dois produtos importam aqui: **Zscaler Internet Access (ZIA)**, proxy com inspeção de TLS, e **Zscaler Private Access (ZPA)**, túnel/VPN para aplicações internas.",
    "",
    "- **Certificado raiz:** a inspeção de TLS da ZIA substitui o certificado dos sites pelo da Zscaler. Sem a raiz no bundle correto, `pip`/`uv`/`npm`/`git` falham com `SSL: CERTIFICATE_VERIFY_FAILED`. A raiz vive no repositório de certificados do Windows (instalada por política ou pelo Client Connector), que tem duas lojas: `certmgr.msc` cobre o usuário atual e `certlm.msc` cobre a máquina; a raiz pode estar em só uma delas. Exporte pelo assistente (Trusted Root Certification Authorities → Zscaler → Export) escolhendo \"Base-64 encoded X.509 (.CER)\", que já sai em PEM; via PowerShell, `Get-ChildItem Cert:\\CurrentUser\\Root, Cert:\\LocalMachine\\Root | ? Subject -like \"*Zscaler*\"` acha o cert nas duas lojas, mas `Export-Certificate` grava DER, não PEM; converta com `certutil -encode zscaler-root.cer zscaler-root.pem`. Em alternativa peça o PEM ao TI. Cada ferramenta lê a raiz de um lugar diferente:",
    "  ```powershell",
    "  $env:REQUESTS_CA_BUNDLE=\"C:\\path\\zscaler-root.pem\"   # pip e ferramentas baseadas em requests",
    "  $env:SSL_CERT_FILE=\"C:\\path\\zscaler-root.pem\"        # uv, urllib do Python (inclui o check de manifest do DevKit)",
    "  $env:NODE_EXTRA_CA_CERTS=\"C:\\path\\zscaler-root.pem\"  # node/npm",
    "  git config --global http.sslCAInfo \"C:\\path\\zscaler-root.pem\"",
    "  ```",
    "  Se a raiz da Zscaler já estiver no repositório de certificados do Windows (caso comum: instalada por política), `uv` também resolve com `uv --native-tls` ou `$env:UV_NATIVE_TLS=\"1\"`, que lê o store do SO em vez do bundle embutido.",
    "- **PAC file / auto-config:** se o proxy vem de um PAC em vez de variável fixa, `HTTPS_PROXY` manual pode não bastar. Descubra o proxy ativo antes de setar a variável: `netsh winhttp show proxy`, ou o painel do Zscaler Client Connector. Para downloads pontuais, copie o endereço que o PAC resolve para `HTTPS_PROXY`/`HTTP_PROXY`.",
    "- **Portas e protocolos:** os MCP servers que este ecossistema instala usam transporte `stdio`, sem porta não-padrão, e ZPA não interfere. Exceções opt-in existem em alguns pacotes e estão descritas no bullet \"Fully local runtime\" do guia corporate de cada um (ex.: o perfil corporate do devin-switch registra MCPs remotos HTTPS; o `--source mcp` do devin-qa-pack sai por HTTPS). Ferramentas remotas assim dependem de a ZPA/liberação alcançar o host delas.",
    "- **\"É a Zscaler ou outra coisa?\":** `SSL: CERTIFICATE_VERIFY_FAILED` cujo emissor do certificado é `Zscaler` significa inspeção de TLS; resolva pela raiz acima. Timeout ou `connection refused` aponta mais para firewall/regra de rede, não TLS. Valide o proxy ativo e reporte ao TI com o host e a porta.",
    "",
]

# Canonical recurring jobs per tool — real cadences, sanitized. Only tools
# whose workflows benefit from a schedule get a concrete example; everything
# else stays on-demand (the generic "Scheduling" bullet in the specifics
# sections already says installation never creates jobs).
# `sched` is the faithful Task Scheduler trigger matching `cron`.
_RECURRING_JOBS: dict[str, dict[str, str]] = {
    "devin-backup": {
        "cmd": "devin-backup create --out ~/backups",
        "cron": "15 3 * * *",
        "trigger": "-Daily -At 3:15AM",
        "cmdfile": "devin-backup create --out \"%USERPROFILE%\\backups\"",
        "sched": "/sc daily /st 03:15",
        "note": "Nightly snapshot; pair with a weekly `devin-backup rotate --keep 10 --yes` pointed at the same `--out` directory (rotate uses the default backups dir otherwise and finds nothing). Or let the tool self-schedule with `devin-backup install` (cron / Task Scheduler / elapsed backends).",
    },
    "devin-janitor": {
        "cmd": "devin-janitor run --apply",
        "cron": "30 4 * * *",
        "win": "devin-janitor run --apply",
        "sched": "/sc daily /st 04:30",
        "note": "Daily cleanup with `--apply` as shown. The package also ships `devin-janitor install`, which registers its own daily `report` job (cron / Task Scheduler / elapsed hook); the two jobs are different — `report` only reports, `--apply` actually cleans.",
    },
    "devin-explore": {
        "cmd": "devin-doctor check",
        "cron": "0 9 * * 1",
        "win": "devin-doctor check",
        "sched": "/sc weekly /d MON /st 09:00",
        "note": "Weekly health sweep, read-only, safe to leave on.",
    },
    "devin-history": {
        "cmd": "devin-history export --out ~/devin-history-export",
        "cron": "0 5 * * 0",
        "trigger": "-Weekly -DaysOfWeek Sunday -At 5AM",
        "cmdfile": "devin-history export --out \"%USERPROFILE%\\devin-history-export\"",
        "sched": "/sc weekly /d SUN /st 05:00",
        "note": "Weekly archive of sessions to notes (`--out` is required); run before janitor cleanup.",
    },
    "devin-brain": {
        "cmd": "devin-memory --db ~/devin-memory/memory.db extract --latest --sessions-db ~/.local/share/devin/cli/sessions.db",
        "cron": "0 7 * * 0",
        "trigger": "-Weekly -DaysOfWeek Sunday -At 7AM",
        "cmdfile": "devin-memory --db \"%USERPROFILE%\\devin-memory\\memory.db\" extract --latest --sessions-db \"%APPDATA%\\devin\\cli\\sessions.db\"",
        "sched": "/sc weekly /d SUN /st 07:00",
        "note": "Weekly knowledge extraction from recent sessions (proposed entries, human-approved). `--db` pins the memory store, otherwise `extract` writes ./memory.db under whatever directory the scheduler runs from.",
    },
    "devin-evals": {
        "cmd": "devin-evals run --evals ~/devin-evals/cases --sessions-db ~/.local/share/devin/cli/sessions.db",
        "cron": "0 6 * * 0",
        "trigger": "-Weekly -DaysOfWeek Sunday -At 6AM",
        "cmdfile": "devin-evals run --evals \"%USERPROFILE%\\devin-evals\\cases\" --sessions-db \"%APPDATA%\\devin\\cli\\sessions.db\"",
        "sched": "/sc weekly /d SUN /st 06:00",
        "note": "Weekly regression replay; `--evals` (dir of *.json cases) and `--sessions-db` are both required, so create the case dir first. A checkout ships examples under `evals/` and `corpus/evals/`; installed from PyPI you author or copy your own. Corpus stays deterministic and offline.",
    },
    "devin-metrics": {
        "cmd": "devin-metrics summary",
        "cron": "45 4 * * *",
        "win": "devin-metrics summary",
        "sched": "/sc daily /st 04:45",
        "note": "Daily usage summary; `watch` is the advisory context guard.",
    },
    "devin-graph": {
        "cmd": "devin-graph build",
        "cron": "0 6 * * 0",
        "win": "devin-graph build",
        "sched": "/sc weekly /d SUN /st 06:00",
        "note": "Weekly rebuild of graph.db so downstream tools see fresh linkage.",
    },
    "devin-office": {
        "cmd": "python <CAMINHO_DO_CHECKOUT>/src/devin_office/daemon.py --port 8788",
        "cron": "@reboot",
        "trigger": "-AtLogOn -User \"$env:USERDOMAIN\\$env:USERNAME\"",
        "cmdfile": "py \"<CAMINHO_DO_CHECKOUT>\\src\\devin_office\\daemon.py\" --port 8788",
        "sched": "/sc onlogon",
        "note": "Long-running daemon; schedule by boot/logon trigger, not an interval.",
        "note_linux": "Long-running daemon. Prefer a `systemd --user` service (`WorkingDirectory=<CAMINHO_DO_CHECKOUT>`, `Restart=on-failure`) over `@reboot`.",
        "note_win": "Long-running daemon. `schtasks` cannot set \"Start in\", so either call `daemon.py` by absolute path as below (installed users can put `devin-office --port 8788` in the `.cmd` instead — the wrapper already prepends `%USERPROFILE%\\.local\\bin` to `PATH`) or open the task in Task Scheduler afterwards and set Actions → Edit → \"Start in\" to the checkout directory.",
    },
}


def _render_recurring(name: str, platform: str, environment: str) -> list[str]:
    job = _RECURRING_JOBS.get(name)
    if job is None:
        return []
    lines = ["## Recurring runs (optional)", ""]
    note = job.get("note_linux" if platform == "linux" else "note_win", job["note"])
    lines.append(f"_{note}_")
    lines.append("")
    if platform == "linux":
        lines.extend([
            "```cron",
            f"{job['cron']} {job['cmd']}",
            "```",
            "",
            "Equivalent `systemd --user` timer works too; enable lingering if it must run without a login session.",
        ])
    else:
        # Commands with path arguments that may contain spaces go through a
        # wrapper .cmd file: embedding quotes inside /tr is a losing game
        # across cmd.exe and PowerShell 5.1 native-arg parsing.
        cmdfile = job.get("cmdfile")
        if cmdfile:
            # Wrappers live in the user's own profile dir (never shared,
            # so no cross-user tampering). Registration uses the structured
            # ScheduledTask cmdlets, which take the action path literally —
            # no /tr quoting maze in any shell.
            task_path = f"%USERPROFILE%\\devin-tasks\\{name}.cmd"
            lines.extend([
                "Quoted path arguments inside `/tr` fail differently in cmd.exe and PowerShell 5.1, so this job goes through a wrapper `.cmd` file in your own profile directory (quoting inside the file works normally, and no other user can replace it). The task inherits your user `PATH`, so the wrapper first prepends the standard tool directory (`%USERPROFILE%\\.local\\bin`); if the tool lives elsewhere, write its full path inside the `.cmd`. Register from PowerShell with the `ScheduledTask` cmdlets, which take the path literally and replace cleanly on rerun (`-Force`):",
                "",
                "```powershell",
                "New-Item -ItemType Directory -Force \"$env:USERPROFILE\\devin-tasks\"   # cmd.exe: mkdir \"%USERPROFILE%\\devin-tasks\"",
                "```",
                "",
                f"Save this as `{task_path}`:",
                "",
                "```batch",
                "set \"PATH=%USERPROFILE%\\.local\\bin;%PATH%\"",
                cmdfile,
                "```",
                "",
                "```powershell",
                f"$action  = New-ScheduledTaskAction -Execute \"$env:USERPROFILE\\devin-tasks\\{name}.cmd\"",
                f"$trigger = New-ScheduledTaskTrigger {job['trigger']}",
                f"Register-ScheduledTask -TaskName \"{name}\" -Action $action -Trigger $trigger -Force",
                "```",
                "",
                "_cmd.exe users: the same registration works from Task Scheduler's GUI (Action = the .cmd path)._",
                "",
            ])
        else:
            lines.extend([
                "```powershell",
                f"schtasks /create /tn \"{name}\" /tr \"{job['win']}\" {job['sched']} /f",
                "```",
                "",
            ])
        if environment == "corporate_windows":
            lines.append(
                "User-scope registration (`schtasks` or the `ScheduledTask` cmdlets) needs no admin. If Group Policy disables Task Scheduler (`0x80070005` \"Access is denied\"), run the command manually or use the tool's own `install` subcommand where available. Options needing elevation, \"Run whether user is logged on or not\", highest privileges, are usually policy-blocked; when they are, a user-scope logon trigger (`/sc onlogon`, or `New-ScheduledTaskTrigger -AtLogOn`) is the realistic fallback."
            )
        else:
            lines.append(
                ("Runs under your account, no admin needed. Adjust the `New-ScheduledTaskTrigger` arguments (or `-AtLogOn` for daemons) to taste."
                if cmdfile else
                "Runs under your account, no admin needed. Adjust `/sc`/`/st` (or `/sc onlogon` for daemons) to taste.")
            )
    lines.append("")
    return lines


def _patch_specifics(specifics: list[str], name: str, doc_key: str) -> list[str]:
    """Applies per-entry bullet replacements/insertions to a shared
    specifics list; the module constants stay immutable, so copy first."""
    lines = list(specifics)
    for label, bullet in _SPECIFICS_REPLACE.get((name, doc_key), {}).items():
        lines = [bullet if line.startswith(f"- {label}") else line for line in lines]
    for anchor, bullet in _SPECIFICS_INSERT.get((name, doc_key), []):
        index = next(
            (i for i, line in enumerate(lines) if anchor is not None and line.startswith(f"- {anchor}")),
            len(lines),
        )
        lines.insert(index, bullet)
    return lines


def render_guide(entry: dict[str, Any], tool: dict[str, Any] | None, platform: str, environment: str | None = None) -> str:
    name = entry["name"]
    environment = environment or ("linux" if platform == "linux" else "personal_windows")
    doc_key = "corporate_windows" if environment == "corporate_windows" else platform
    environment_meta = entry.get("environments", {}).get(environment)
    label = {
        "linux": "Linux",
        "personal_windows": "Personal Windows",
        "corporate_windows": "Corporate Windows",
    }[environment]
    lines = [f"# {name}, {label} guide", ""]

    if environment == "corporate_windows":
        lines.extend([
            "This guide covers restricted Windows setup only. For unrestricted Windows, see [README.windows.md](README.windows.md); for features, shared commands, limitations, and the safety model, see [README.md](README.md).",
            "",
            "Corporate Windows is a local-only environment: no Devin VM, QwenPaw, Slack dependency, external compute, workload delegation or required external integration.",
            "",
        ])
        scope = _CORP_SCOPE_NOTE.get(name)
        if scope:
            lines.extend([scope, ""])
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
    elif name == "devin-devkit":
        lines.append("- `uv`, installed from the [official uv guide](https://docs.astral.sh/uv/getting-started/installation/). It can manage a compatible Python interpreter.")
        lines.append("- Node.js 20 or newer and npm only when installing a profile containing `devin-bridge`.")
        lines.append("- Git on `PATH` for the `git+` DevKit installation below and for manual source checkouts; installable profile tools use HTTPS archives.")
    elif name == "devin-office":
        lines.extend(["- Python 3.10 or newer.", "- Git for a source checkout.", "- Devin Desktop or CLI on the machine whose sessions you want to view."])
    elif name == "devin-powerups":
        lines.extend(["- Python 3.10 or newer.", "- Git for repository scaffolding."])
    else:
        lines.append("- Follow the requirements listed in [README.md](README.md).")
    lines.extend(["", "## Install", ""])
    lines.extend(_install_line(entry, tool, platform, environment))
    lines.extend(["", "## Devin paths", ""])
    flags = _PATH_FLAGS.get(name, _DEFAULT_PATH_FLAGS)
    paths_body = _DEVIN_PATHS_BODY.get((name, doc_key))
    if paths_body is not None:
        lines.extend(paths_body)
    elif name == "devin-devkit":
        if platform == "windows":
            lines.extend([
                "Session data normally lives under `%APPDATA%\\devin\\cli\\`; UI state and ACP stores under `%APPDATA%\\Devin\\User\\`.",
                "The DevKit does not change those directories or Devin settings. `uv` exposes installed commands through its tools directory, if a command is not found run `uv tool update-shell` and open a new terminal.",
            ])
        else:
            lines.extend([
                "Session data normally lives under `${XDG_DATA_HOME:-$HOME/.local/share}/devin/cli/`; UI state and ACP stores under `${XDG_CONFIG_HOME:-$HOME/.config}/Devin/User/`.",
                "The DevKit does not change those directories or Devin settings. `uv` exposes installed commands through its tools directory, ensure it is on `PATH` (`uv tool update-shell`).",
            ])
    elif platform == "windows":
        lines.extend([
            "Session data normally lives under `%APPDATA%\\devin\\cli\\`; UI state and ACP stores under `%APPDATA%\\Devin\\User\\`.",
            f"Use {flags} for non-default locations.",
        ])
    else:
        lines.extend([
            "Session data normally lives under `${XDG_DATA_HOME:-$HOME/.local/share}/devin/cli/`; UI state and ACP stores under `${XDG_CONFIG_HOME:-$HOME/.config}/Devin/User/`.",
            f"Use {flags} for non-default locations.",
        ])
    lines.extend(_DEVIN_PATHS_EXTRA.get((name, doc_key), []))
    lines.extend(["", "## Environment notes", ""])
    if environment == "corporate_windows":
        lines.extend([
            "- Keep execution local; do not configure VM, QwenPaw, external compute or workload delegation.",
            "- Registry-declared external integrations remain optional and are not installed by this guide.",
        ])
    elif environment == "personal_windows":
        lines.extend([
            "- Delegated runtime is optional; this guide installs local tooling only.",
            _ENV_CORP_LINE.get(name, "- Corporate Windows is a separate local-only environment."),
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
    lines.extend(_patch_specifics(specifics, name, doc_key))
    if environment == "corporate_windows":
        runtime = _NETWORK_RUNTIME.get(name, _DEFAULT_NETWORK_RUNTIME)
        lines.append(f"- **Fully local runtime:** {runtime}")
        lines.extend(_POST_RUNTIME_EXTRAS.get((name, doc_key), []))
        lines.extend(["", *_ZSCALER])
    recurring = _render_recurring(name, platform, environment)
    if recurring:
        lines.extend(["", *recurring])
    extra = _PLATFORM_EXTRAS.get((name, doc_key))
    if extra:
        lines.extend(["", *extra])
    lines.extend(["", "## Troubleshooting", ""])
    if tool and tool["manager"] == "uv":
        if platform == "windows":
            lines.append("- If a command is not found, reopen PowerShell and run `uv tool update-shell`.")
        else:
            lines.append("- If a command is not found, ensure the `uv` tools directory is on `PATH` and run `uv tool update-shell`.")
    elif tool and tool["manager"] == "npm":
        lines.append("- If the bridge command is missing, check that npm's global executable directory is on `PATH` (`npm config get prefix`).")
    elif name == "devin-devkit":
        lines.extend([
            "- If a command is not found, run `uv tool update-shell` and open a new terminal." if platform == "windows"
            else "- If a command is not found, ensure the `uv` tools directory is on `PATH` and run `uv tool update-shell`.",
            "- `install <profile>` is a dry run; `--apply` is required to install.",
            "- Existing commands are never overwritten; a complete command set on `PATH` is reported but its versions are not verified, while a partial collision blocks the profile.",
            "- If `devin-bridge` is installed but not found, check `npm config get prefix` and ensure npm's global executable directory is on `PATH`.",
        ])
    elif name == "devin-office":
        lines.append("- Start the daemon from the repository directory with the OS-specific Python launcher shown above.")
    elif name == "devin-powerups":
        lines.append("- Confirm `py -3` and Git are available in PowerShell." if platform == "windows" else "- Confirm `python3` and Git are available in the shell.")
    else:
        lines.append("- Follow the platform-specific troubleshooting notes in the main README.")
    if tool and tool.get("requires_git"):
        lines.append("- This release has a Git dependency; verify Git is installed and on `PATH` with `git --version`.")
    lines.extend(_TROUBLESHOOTING_EXTRAS.get((name, doc_key), []))
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
    # devin-devkit is the installer, a "distribution" entry rather than a
    # devkit.tool, but it shares the corporate-docs universe as an extras
    # target (decision 2026-10-11: one generator, no parallel mechanism).
    targets = set(tool_map) | {"devin-powerups", "qwenpaw-suite", "devin-devkit"}
    plans = []
    for entry in registry.get("repositories", []):
        if entry.get("visibility") != "public" or entry.get("kind") not in {"project", "infra", "distribution"}:
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
            # Derive the Git prerequisite from the effective install spec:
            # only a git+...#subdirectory= install actually needs Git.
            requires_git = tool["source"] == "github" and bool((entry.get("package") or {}).get("path"))
            tool = {**tool, "requires_git": requires_git}
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
