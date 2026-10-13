#!/usr/bin/env python3
"""<pkg> pre-commit adapter — optional wrapper for exit-code remapping.

Skeleton — canonical location: packages/<pkg>/adapters/precommit/hook.py.
Only needed when `<pkg-cli> check` exit codes do not already map onto
hook semantics (0 pass / non-zero fail); prefer the direct `entry:
<pkg-cli> check` manifest when they do.

Thin shell: it forwards to the CLI and translates the result — it never
recomputes a verdict.
"""

from __future__ import annotations

import subprocess
import sys

CLI = "<pkg-cli>"


def run_hook(
    argv: list[str] | None = None,
    runner=subprocess.run,
    out=sys.stdout,
) -> int:
    """Run `<pkg-cli> check --json`; 0 pass, 1 findings, 2 CLI failure.

    Extra argv are forwarded verbatim so hook authors keep the CLI's own
    flags — the wrapper adds none of its own.
    """
    args = [CLI, "check", "--json"] + list(argv or [])
    try:
        proc = runner(args, capture_output=True, text=True, timeout=120)
    except OSError as e:  # CLI missing/unrunnable -> hook fails, never skips
        print(f"{CLI}: cannot run ({e})", file=out)
        return 2
    except subprocess.TimeoutExpired:
        print(f"{CLI}: timed out", file=out)
        return 2
    if proc.returncode == 0:
        return 0
    print(proc.stderr or proc.stdout or f"{CLI}: check failed", file=out)
    return 1


if __name__ == "__main__":
    sys.exit(run_hook(sys.argv[1:]))
