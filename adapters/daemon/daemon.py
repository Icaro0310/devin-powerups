"""<pkg> daemon adapter — periodically runs `<pkg-cli> check --json` and
keeps the latest payload on disk.

Skeleton — canonical location: packages/<pkg>/adapters/daemon/daemon.py,
or src/<pkg_mod>/daemon.py when it ships a `<pkg>-daemon` entry point.

Thin shell: verdicts and exit codes come from the CLI; the daemon only
schedules, persists and shuts down cleanly. No check logic lives here.
"""

from __future__ import annotations

import json
import signal
import subprocess
import sys
import time
from pathlib import Path

CLI = "<pkg-cli>"
INTERVAL_S = 300
STATE_PATH = Path.home() / ".local" / "state" / "<pkg>" / "last.json"

_running = True


def _stop(_signum, _frame) -> None:
    global _running
    _running = False


def run_check(cli: str = CLI, runner=subprocess.run) -> dict:
    """One CLI invocation -> the parsed --json payload, or an error dict."""
    try:
        proc = runner(
            [cli, "check", "--json"],
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        return {"error": type(e).__name__, "detail": str(e)[:500]}
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        # A non-JSON reply is a CLI error, not a daemon crash — surface it.
        return {
            "error": "NonJsonOutput",
            "detail": (proc.stderr or proc.stdout or "")[:500],
        }


def write_state(payload: dict, path: Path = STATE_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def main(
    interval: float = INTERVAL_S,
    state_path: Path = STATE_PATH,
    sleep=time.sleep,
    runner=subprocess.run,
    cli: str = CLI,
) -> int:
    """Loop until SIGTERM/SIGINT. Seams are keyword-only for tests."""
    global _running
    _running = True  # re-enterable: a stopped flag must not leak into a restart
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    while _running:
        write_state(run_check(cli=cli, runner=runner), path=state_path)
        # Wake once a second so a signal is honored promptly, not after a
        # full interval.
        for _ in range(int(interval)):
            if not _running:
                break
            sleep(1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
