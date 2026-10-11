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
    "(`pip download setuptools wheel`), then install with `pip install "
    "--no-index --find-links wheels\\ --no-build-isolation .` inside "
    "the checkout.",
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
    "devin-control": (
        "**Scope note:** this package is a bridge to the Devin agent runtime. "
        "It is documented here for completeness but sits outside the "
        "local-only guarantee above, since its function is delegated "
        "external compute."
    ),
}

# Extra sections injected before Troubleshooting — hand-curated content
# migrated into the generator so regeneration does not drop it (audit
# 2026-10-11 found adapters/caveat sections living only on disk).
def _adapters_extra(pkg: str, short: bool) -> list[str]:
    variant = (
        "resolves once the next PyPI release ships, until then install from\n"
        f"  source (`pip install -e 'packages/{pkg}[mcp]'` from a checkout)."
        if short else
        "resolves once the next PyPI release ships. Until then, an\n"
        "  editable install does not change what `uvx --from` resolves —\n"
        "  either run the source-installed `devin-" + pkg + "-mcp` directly, or\n"
        "  point a local manifest copy at the checkout:\n"
        f"  `uvx --from './packages/{pkg}[mcp]' devin-{pkg}-mcp`."
    )
    return [
        "## Adapters (MCP / Devin skill / plugin)",
        "",
        f"- MCP server: `pip install 'devin-{pkg}[mcp]'` then run `devin-{pkg}-mcp` (stdio).",
        "  Read-only tools only.",
        "- Devin plugin + skill: `devin plugins install",
        f"  Icaro0310/devin-state#packages/{pkg}/adapters`. The manifest",
        f"  launches the server through `uvx --from 'devin-{pkg}[mcp]' devin-{pkg}-mcp`, which",
        "  " + variant,
        "",
    ]

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

# (entry name, doc key) -> extra section lines.
_PLATFORM_EXTRAS: dict[tuple[str, str], list[str]] = {
    ("devin-backup", "windows"): _adapters_extra("backup", short=False),
    ("devin-backup", "corporate_windows"): _adapters_extra("backup", short=True),
    ("devin-backup", "linux"): _adapters_extra("backup", short=False),
    ("devin-janitor", "windows"): _adapters_extra("janitor", short=False),
    ("devin-janitor", "corporate_windows"): _adapters_extra("janitor", short=True),
    ("devin-janitor", "linux"): _adapters_extra("janitor", short=False),
    ("devin-office", "linux"): _OFFICE_LINUX_EXTRA,
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
    "- **Certificado raiz:** a inspeção de TLS da ZIA substitui o certificado dos sites pelo da Zscaler. Sem a raiz no bundle correto, `pip`/`uv`/`npm`/`git` falham com `SSL: CERTIFICATE_VERIFY_FAILED`. A raiz normalmente está em `C:\\ProgramData\\Zscaler\\` (ou pode ser exportada pelo Zscaler Client Connector). Cada ferramenta lê a raiz de um lugar diferente:",
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
        "cmd": "python <CAMINHO_DO_CHECKOUT>/daemon.py --port 8788",
        "cron": "@reboot",
        "trigger": "-AtLogOn -User \"$env:USERDOMAIN\\$env:USERNAME\"",
        "cmdfile": "py \"<CAMINHO_DO_CHECKOUT>\\daemon.py\" --port 8788",
        "sched": "/sc onlogon",
        "note": "Long-running daemon; schedule by boot/logon trigger, not an interval.",
        "note_linux": "Long-running daemon. Prefer a `systemd --user` service (`WorkingDirectory=<CAMINHO_DO_CHECKOUT>`, `Restart=on-failure`) over `@reboot`.",
        "note_win": "Long-running daemon. `schtasks` cannot set \"Start in\", so either call `daemon.py` by absolute path as below or open the task in Task Scheduler afterwards and set Actions → Edit → \"Start in\" to the checkout directory.",
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


def render_guide(entry: dict[str, Any], tool: dict[str, Any] | None, platform: str, environment: str | None = None) -> str:
    name = entry["name"]
    environment = environment or ("linux" if platform == "linux" else "personal_windows")
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
    elif name == "devin-office":
        lines.extend(["- Python 3.10 or newer.", "- Git for a source checkout.", "- Devin Desktop or CLI on the machine whose sessions you want to view."])
    elif name == "devin-powerups":
        lines.extend(["- Python 3.10 or newer.", "- Git for repository scaffolding."])
    else:
        lines.append("- Follow the requirements listed in [README.md](README.md).")
    lines.extend(["", "## Install", ""])
    lines.extend(_install_line(entry, tool, platform))
    lines.extend(["", "## Devin paths", ""])
    flags = _PATH_FLAGS.get(name, _DEFAULT_PATH_FLAGS)
    if platform == "windows":
        lines.extend([
            "Session data normally lives under `%APPDATA%\\devin\\cli\\`; UI state and ACP stores under `%APPDATA%\\Devin\\User\\`.",
            f"Use {flags} for non-default locations.",
        ])
    else:
        lines.extend([
            "Session data normally lives under `${XDG_DATA_HOME:-$HOME/.local/share}/devin/cli/`; UI state and ACP stores under `${XDG_CONFIG_HOME:-$HOME/.config}/Devin/User/`.",
            f"Use {flags} for non-default locations.",
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
    if environment == "corporate_windows":
        runtime = _NETWORK_RUNTIME.get(name, _DEFAULT_NETWORK_RUNTIME)
        lines.append(f"- **Fully local runtime:** {runtime}")
        lines.extend(["", *_ZSCALER])
    recurring = _render_recurring(name, platform, environment)
    if recurring:
        lines.extend(["", *recurring])
    doc_key = "corporate_windows" if environment == "corporate_windows" else platform
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
