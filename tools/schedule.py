#!/usr/bin/env python3
"""schedule.py — opt-in scheduling for the devin-* ecosystem (F6).

Three backends, resolved in order unless ``--backend`` pins one:

1. **Task Scheduler** (Windows): ``schtasks /create /tn devin-<name>
   /sc daily|hourly /tr "<command>"``.
2. **cron** (Linux/macOS): appends a tagged block to ``crontab`` via
   ``crontab -l`` / ``crontab -`` (portable; no ``cron.d`` writes).
3. **elapsed** (always available — the corporate fallback): the job is
   recorded in ``<config-dir>/.devin-ecosystem/scheduled.json`` and a
   ``UserPromptSubmit`` hook calls ``schedule.py check --run``; jobs run
   only when their interval has elapsed since ``last_run``. No daemon,
   no background process — the prompt itself is the tick.

``--requires-devin-closed`` marks jobs that touch Devin's stores (e.g.
anything that would VACUUM). In every backend the generated wrapper first
checks whether a Devin process is running and skips when it is — the
guard rides inside the scheduled command, so it holds even when the OS
scheduler fires the job directly.

Usage:
    python tools/schedule.py install <name> "<command>" [--daily|--every H]
        [--backend auto|tasksch|cron|elapsed] [--requires-devin-closed]
    python tools/schedule.py list [--json]
    python tools/schedule.py check [--run]          # elapsed backend
    python tools/schedule.py uninstall <name>

The registry file lives at ``<config-dir>/.devin-ecosystem/scheduled.json``
with the same config-dir resolution as hooks_dispatch.py.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

CRON_TAG = "# devin-ecosystem:{name}"
DEFAULT_INTERVAL_H = 24


# -- config dir / registry ---------------------------------------------------

def _config_dir(arg: str | None) -> Path:
    if arg:
        return Path(arg).expanduser()
    env = os.environ.get("DEVIN_CONFIG_DIR")
    if env:
        return Path(env).expanduser()
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA") or str(
            Path.home() / "AppData" / "Roaming")
        return Path(base) / "Devin"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Devin"
    xdg = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    for name in ("Devin", "devin"):
        if (Path(xdg) / name).is_dir():
            return Path(xdg) / name
    return Path(xdg) / "devin"


def _registry_path(config_dir: Path) -> Path:
    return config_dir / ".devin-ecosystem" / "scheduled.json"


def _load_registry(config_dir: Path) -> dict:
    p = _registry_path(config_dir)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(
                data.get("jobs"), dict):
            return data
    except (OSError, ValueError):
        pass
    return {"version": 1, "jobs": {}}


def _save_registry(config_dir: Path, reg: dict) -> Path:
    p = _registry_path(config_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=p.parent, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(reg, fh, indent=2)
    os.replace(tmp, p)
    return p


# -- backend detection --------------------------------------------------------

def _has_tasksch() -> bool:
    return sys.platform.startswith("win") and shutil.which("schtasks") \
        is not None


def _has_cron() -> bool:
    return not sys.platform.startswith("win") and shutil.which("crontab") \
        is not None


def resolve_backend(requested: str = "auto") -> str:
    """auto → tasksch (Windows) → cron → elapsed (never fails)."""
    if requested != "auto":
        return requested
    if _has_tasksch():
        return "tasksch"
    if _has_cron():
        return "cron"
    return "elapsed"


def devin_running() -> bool:
    """Best-effort: is a Devin desktop/CLI process alive?"""
    if sys.platform.startswith("win"):
        try:
            out = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq Devin.exe"],
                capture_output=True, text=True, timeout=10)
            return "Devin.exe" in out.stdout
        except (OSError, subprocess.SubprocessError):
            return False
    try:
        return subprocess.run(
            ["pgrep", "-f", "[Dd]evin"], capture_output=True,
            timeout=10).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


# -- job wrappers --------------------------------------------------------------

def _guarded_command(command: str, requires_closed: bool) -> str:
    """Wrap the command with the 'Devin closed' guard when requested."""
    if not requires_closed:
        return command
    me = Path(__file__).resolve()
    if sys.platform.startswith("win"):
        return (
            f'cmd /c "tasklist /FI "IMAGENAME eq Devin.exe" '
            f'| findstr /I Devin.exe >NUL || {command}"')
    return (
        f'sh -c \'pgrep -f "[Dd]evin" >/dev/null 2>&1 || {command}\'')


# -- backends ------------------------------------------------------------------

def _cron_line(name: str, command: str, every_h: int) -> str:
    schedule = "@daily" if every_h >= 24 else f"0 */{every_h} * * *"
    return f"{schedule} {command}  {CRON_TAG.format(name=name)}"


def _cron_read() -> str:
    out = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    return out.stdout if out.returncode == 0 else ""


def _cron_write(text: str) -> None:
    subprocess.run(["crontab", "-"], input=text, text=True, check=True)


def _install_cron(name: str, command: str, every_h: int) -> None:
    current = _cron_read()
    tag = CRON_TAG.format(name=name)
    kept = [l for l in current.splitlines() if tag not in l]
    kept.append(_cron_line(name, command, every_h))
    _cron_write("\n".join(kept) + "\n")


def _uninstall_cron(name: str) -> bool:
    current = _cron_read()
    tag = CRON_TAG.format(name=name)
    kept = [l for l in current.splitlines() if tag not in l]
    if len(kept) == len(current.splitlines()):
        return False
    _cron_write("\n".join(kept) + ("\n" if kept else ""))
    return True


def _install_tasksch(name: str, command: str, every_h: int) -> None:
    tn = f"devin-{name}"
    sc = "/sc", ("DAILY" if every_h >= 24 else "HOURLY")
    args = ["schtasks", "/create", "/f", "/tn", tn, *sc]
    if every_h < 24 and every_h > 1:
        args += ["/mo", str(every_h)]
    args += ["/tr", command]
    subprocess.run(args, check=True)


def _uninstall_tasksch(name: str) -> bool:
    tn = f"devin-{name}"
    q = subprocess.run(["schtasks", "/query", "/tn", tn],
                       capture_output=True)
    if q.returncode != 0:
        return False
    subprocess.run(["schtasks", "/delete", "/f", "/tn", tn], check=True)
    return True


# -- commands ------------------------------------------------------------------

def cmd_install(args: argparse.Namespace) -> int:
    config_dir = _config_dir(args.config_dir)
    backend = resolve_backend(args.backend)
    command = _guarded_command(args.command, args.requires_devin_closed)
    every_h = args.every or DEFAULT_INTERVAL_H
    if args.daily:
        every_h = 24

    if backend == "tasksch":
        _install_tasksch(args.name, command, every_h)
    elif backend == "cron":
        _install_cron(args.name, command, every_h)
    # elapsed jobs live only in the registry — no OS-level install.

    reg = _load_registry(config_dir)
    reg["jobs"][args.name] = {
        "command": args.command,
        "guarded_command": command,
        "interval_h": every_h,
        "backend": backend,
        "requires_devin_closed": bool(args.requires_devin_closed),
        "installed_at": int(time.time()),
        "last_run": 0,
    }
    p = _save_registry(config_dir, reg)
    print(f"installed '{args.name}' [{backend}, every {every_h}h] → {p}")
    if backend == "elapsed":
        print("elapsed backend: run 'schedule.py check --run' from a "
              "UserPromptSubmit hook — see README")
    return 0


def cmd_uninstall(args: argparse.Namespace) -> int:
    config_dir = _config_dir(args.config_dir)
    reg = _load_registry(config_dir)
    job = reg["jobs"].pop(args.name, None)
    if job is None:
        print(f"no job named '{args.name}'", file=sys.stderr)
        return 1
    backend = job.get("backend", "elapsed")
    if backend == "tasksch":
        _uninstall_tasksch(args.name)
    elif backend == "cron":
        _uninstall_cron(args.name)
    _save_registry(config_dir, reg)
    print(f"uninstalled '{args.name}'")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    reg = _load_registry(_config_dir(args.config_dir))
    jobs = reg["jobs"]
    if args.json:
        print(json.dumps(jobs, indent=2))
        return 0
    if not jobs:
        print("no scheduled jobs")
        return 0
    for name, j in jobs.items():
        guard = " devin-closed-only" if j.get("requires_devin_closed") else ""
        print(f"{name:<20} [{j.get('backend','?')}, {j.get('interval_h','?')}h"
              f"{guard}] {j.get('command','')}")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    """Elapsed backend tick — run due jobs (or just print them)."""
    config_dir = _config_dir(args.config_dir)
    reg = _load_registry(config_dir)
    now = int(time.time())
    due = []
    for name, j in reg["jobs"].items():
        if j.get("backend") != "elapsed":
            continue
        interval_s = int(j.get("interval_h", DEFAULT_INTERVAL_H)) * 3600
        if now - int(j.get("last_run", 0)) >= interval_s:
            due.append(name)
    if not due:
        if not args.json:
            print("no elapsed jobs due")
        return 0
    for name in due:
        j = reg["jobs"][name]
        if j.get("requires_devin_closed") and devin_running():
            print(f"skip {name}: Devin is running")
            continue
        if args.run:
            print(f"run {name}: {j['guarded_command']}")
            subprocess.run(j["guarded_command"], shell=True)
            j["last_run"] = now
        else:
            print(f"due {name}: {j['command']}")
    if args.run:
        _save_registry(config_dir, reg)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="schedule.py",
                                description=__doc__.splitlines()[0])
    p.add_argument("--config-dir", help="Devin config dir override")
    sub = p.add_subparsers(dest="command", required=True)

    i = sub.add_parser("install", help="register a scheduled job")
    i.add_argument("name")
    i.add_argument("command", help="shell command to run")
    i.add_argument("--daily", action="store_true", help="once a day")
    i.add_argument("--every", type=int, metavar="H",
                   help="every H hours (default 24)")
    i.add_argument("--backend", default="auto",
                   choices=["auto", "tasksch", "cron", "elapsed"])
    i.add_argument("--requires-devin-closed", action="store_true",
                   help="skip while a Devin process is running")
    i.set_defaults(func=cmd_install)

    l = sub.add_parser("list", help="list registered jobs")
    l.add_argument("--json", action="store_true")
    l.set_defaults(func=cmd_list)

    c = sub.add_parser("check", help="elapsed-backend tick (for hooks)")
    c.add_argument("--run", action="store_true", help="actually run due jobs")
    c.add_argument("--json", action="store_true")
    c.set_defaults(func=cmd_check)

    u = sub.add_parser("uninstall", help="remove a job")
    u.add_argument("name")
    u.set_defaults(func=cmd_uninstall)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except subprocess.CalledProcessError as exc:
        print(f"error: scheduler command failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
