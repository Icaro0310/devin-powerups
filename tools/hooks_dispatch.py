#!/usr/bin/env python3
"""hooks_dispatch.py — one Devin hook entrypoint that fans out to handlers.

Foundation F5. Devin hooks (``hooks`` in ``config.json`` and project
``.devin/hooks.v1.json``) each run a single shell command per event. Instead
of every repo installing its own hook command, install ONE command — this
dispatcher — and register handlers declaratively in the registry file
``<config-dir>/.devin-ecosystem/hooks.json``:

    {"version": 1,
     "handlers": {"SessionStart": [
         {"id": "my-handler", "command": "python tools/x.py",
          "timeout_seconds": 30, "enabled": true,
          "profile": "any", "requires": ["daemon"]}]}}

Config dir resolution (first match wins):

1. ``--config-dir PATH`` flag
2. ``DEVIN_CONFIG_DIR`` environment variable
3. ``%APPDATA%\\Devin`` (Windows) · ``~/Library/Application Support/Devin``
   (macOS) · ``$XDG_CONFIG_HOME/Devin|devin`` or ``~/.config/devin`` (Linux)

Machine profile resolution — same order as devin-doctor (F10 contract,
fail-closed):

1. ``DEVIN_ECOSYSTEM_PROFILE=corporate|personal``
2. ``devin-profile.json`` in the config dir (``{"profile": "personal"}``)
3. default: ``corporate``

Usage:
    devin-hooks dispatch <event>            # inside a Devin hook command
    python tools/hooks_dispatch.py dispatch <event>
    python tools/hooks_dispatch.py list [--event E] [--json]
    python tools/hooks_dispatch.py check
    python tools/hooks_dispatch.py register <event> <id> "<command>" [opts]
    python tools/hooks_dispatch.py unregister <event> <id>

Contract for handlers (documented for registry authors):

- stdin: whatever the hook piped in (usually a JSON context blob) is read
  once and forwarded verbatim to every handler's stdin. Missing, empty or
  never-closing stdin is tolerated — the dispatcher never blocks on input.
- exit code 0: ok. Any other non-zero exit is logged but NEVER fails the
  hook — dispatch still exits 0.
- exit code 42 (ABORT): the handler explicitly asks to abort the event.
  Remaining handlers are skipped and the dispatcher exits 42, which is the
  only way a handler can make the hook fail.
- Timeouts: ``timeout_seconds`` per handler (default 30), and a hard global
  cap of 120 s per dispatch; when the budget is spent, remaining handlers
  are skipped. Implemented with subprocess timeouts only — no signals, so
  it behaves the same on Windows and Linux.
- ``enabled: false`` skips the handler. ``profile: "corporate"|"personal"``
  restricts it to that machine profile (``"any"``/absent = everywhere).
  A non-empty ``requires`` capability list (e.g. ``["daemon"]``) skips the
  handler on the ``corporate`` profile; on ``personal`` the entry runs and
  the handler itself must still refuse gracefully if the capability is
  actually missing (per the F10 contract).
- Handlers inherit the environment plus ``DEVIN_EVENT``/``DEVIN_HOOK_EVENT``
  (the event name) and ``DEVIN_ECOSYSTEM_PROFILE`` (the resolved profile).

Every evaluated handler appends one JSONL record to
``<config-dir>/.devin-ecosystem/hook-fires.jsonl``:
``{"ts", "iso", "event", "handler", "status", "exit_code", "duration_ms",
"detail"?}`` with status in ok | failed | timeout | abort | error | skipped.

Exit codes: dispatch 0 (always, unless a handler aborts → 42);
check 0 valid / 1 invalid / 2 unreadable; register/unregister 0 ok / 1
validation problem / 2 file problem; list 0.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Mapping

REGISTRY_FILENAME = "hooks.json"
ECOSYSTEM_DIRNAME = ".devin-ecosystem"
LOG_FILENAME = "hook-fires.jsonl"
REGISTRY_VERSION = 1

CONFIG_DIR_ENV_VAR = "DEVIN_CONFIG_DIR"
PROFILE_ENV_VAR = "DEVIN_ECOSYSTEM_PROFILE"
PROFILE_FILENAME = "devin-profile.json"
PROFILE_CHOICES = ("corporate", "personal")

DEFAULT_HANDLER_TIMEOUT = 30.0
GLOBAL_BUDGET_SECONDS = 120.0
ABORT_EXIT_CODE = 42
STDIN_READ_TIMEOUT = 5.0
STDIN_MAX_BYTES = 1024 * 1024  # 1 MiB — hook payloads are small JSON blobs

# Events Devin hooks.v1.json supports today; unknown names still work —
# check only warns about them (forward compatibility).
KNOWN_EVENTS = (
    "SessionStart",
    "UserPromptSubmit",
    "SessionEnd",
    "Stop",
    "PreToolUse",
    "PostToolUse",
    "PostCompaction",
    "Notification",
)

HANDLER_PROFILE_CHOICES = ("any", "corporate", "personal")

# Capability keys from capability-profile.schema.json / docs (F10).
KNOWN_CAPABILITIES = (
    "scheduler",
    "daemon",
    "net.outbound",
    "net.listener",
    "llm.local",
    "comms",
    "containers",
    "proxy",
    "ram.heavy",
    "multi-host",
)

HANDLER_FIELDS = {
    "id",
    "command",
    "timeout_seconds",
    "enabled",
    "profile",
    "requires",
    "description",
}

_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


# ---------------------------------------------------------------------------
# locations (mirrors devin-doctor paths.py)
# ---------------------------------------------------------------------------


def default_config_dir(
    environ: Mapping[str, str] | None = None, platform: str | None = None
) -> Path:
    """Devin UI config dir — same resolution as devin-doctor's
    ``default_config_dir``: ``DEVIN_CONFIG_DIR`` wins, then the platform
    default. On Linux ``Devin`` and ``devin`` are both accepted; a fresh
    machine falls back to ``~/.config/devin``."""
    env = os.environ if environ is None else environ
    plat = sys.platform if platform is None else platform
    override = env.get(CONFIG_DIR_ENV_VAR)
    if override:
        return Path(override).expanduser()
    if plat.startswith("win"):
        appdata = env.get("APPDATA")
        if appdata:
            return Path(appdata) / "Devin"
        return Path.home() / "AppData" / "Roaming" / "Devin"
    if plat == "darwin":
        return Path.home() / "Library" / "Application Support" / "Devin"
    config_home = Path(env.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    candidates = [config_home / "Devin", config_home / "devin"]
    # devin-doctor picks the candidate holding a `User` dir; next prefer any
    # candidate that exists at all; last resort is the lowercase default.
    for root in candidates:
        if (root / "User").is_dir():
            return root
    for root in candidates:
        if root.is_dir():
            return root
    return candidates[1]


def registry_path(config_dir: Path) -> Path:
    return Path(config_dir) / ECOSYSTEM_DIRNAME / REGISTRY_FILENAME


def log_path(config_dir: Path) -> Path:
    return Path(config_dir) / ECOSYSTEM_DIRNAME / LOG_FILENAME


# ---------------------------------------------------------------------------
# profile (mirrors devin-doctor capabilities.py)
# ---------------------------------------------------------------------------


def _profile_from_file(config_dir: Path) -> str | None:
    try:
        obj = json.loads(
            (Path(config_dir) / PROFILE_FILENAME).read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    if isinstance(obj, dict):
        value = obj.get("profile")
        if isinstance(value, str) and value.lower() in PROFILE_CHOICES:
            return value.lower()
    return None


def resolve_profile(
    environ: Mapping[str, str] | None = None,
    config_dir: Path | None = None,
) -> tuple[str, str]:
    """Return ``(profile, source)``. Env var > config file > ``corporate``
    (fail-closed), exactly like devin-doctor's ``resolve_profile``."""
    env = os.environ if environ is None else environ
    value = env.get(PROFILE_ENV_VAR, "").strip().lower()
    if value in PROFILE_CHOICES:
        return value, f"env {PROFILE_ENV_VAR}"
    if config_dir is not None:
        file_value = _profile_from_file(Path(config_dir))
        if file_value is not None:
            return file_value, str(Path(config_dir) / PROFILE_FILENAME)
    return "corporate", "default"


# ---------------------------------------------------------------------------
# registry load / validate
# ---------------------------------------------------------------------------


def load_registry(path: Path) -> tuple[dict | None, str | None]:
    """Return ``(registry, None)`` or ``(None, error-message)``. A missing
    file is not an error — it just means no handlers are registered."""
    path = Path(path)
    if not path.is_file():
        return {"version": REGISTRY_VERSION, "handlers": {}}, None
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as exc:
        return None, f"cannot read {path}: {exc}"
    except json.JSONDecodeError as exc:
        return None, f"{path}: invalid JSON: {exc}"
    return obj, None


def validate_registry(obj) -> tuple[list[str], list[str]]:
    """Validate the registry document. Returns ``(errors, warnings)``;
    unknown event names, capability keys and handler fields are warnings
    (forward compatibility), shape violations are errors."""
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(obj, dict):
        return ["$: registry root is not an object"], warnings
    handlers = obj.get("handlers", {})
    if not isinstance(handlers, dict):
        errors.append("$.handlers: expected object mapping event → list")
        return errors, warnings
    for event, entries in handlers.items():
        path = f"$.handlers[{event!r}]"
        if not isinstance(event, str) or not event.strip():
            errors.append(f"{path}: event name is not a non-empty string")
            continue
        if event not in KNOWN_EVENTS:
            warnings.append(f"{path}: unknown event name {event!r}")
        if not isinstance(entries, list):
            errors.append(f"{path}: expected a list of handler entries")
            continue
        seen_ids: set[str] = set()
        for i, entry in enumerate(entries):
            epath = f"{path}[{i}]"
            if not isinstance(entry, dict):
                errors.append(f"{epath}: handler entry is not an object")
                continue
            for key in entry:
                if key not in HANDLER_FIELDS:
                    warnings.append(f"{epath}: unknown field {key!r}")
            hid = entry.get("id")
            if not isinstance(hid, str) or not _ID_RE.match(hid):
                errors.append(
                    f"{epath}.id: missing or invalid (want "
                    f"[A-Za-z0-9._-], ≤64 chars)"
                )
            elif hid in seen_ids:
                errors.append(f"{epath}.id: duplicate id {hid!r}")
            else:
                seen_ids.add(hid)
            command = entry.get("command")
            if not isinstance(command, str) or not command.strip():
                errors.append(f"{epath}.command: missing or empty")
            timeout = entry.get("timeout_seconds", DEFAULT_HANDLER_TIMEOUT)
            if (
                not isinstance(timeout, (int, float))
                or isinstance(timeout, bool)
                or timeout <= 0
            ):
                errors.append(f"{epath}.timeout_seconds: not a number > 0")
            enabled = entry.get("enabled", True)
            if not isinstance(enabled, bool):
                errors.append(f"{epath}.enabled: not a boolean")
            profile = entry.get("profile", "any")
            if profile not in HANDLER_PROFILE_CHOICES:
                errors.append(
                    f"{epath}.profile: not one of {HANDLER_PROFILE_CHOICES}"
                )
            requires = entry.get("requires", [])
            if not isinstance(requires, list) or not all(
                isinstance(r, str) and r.strip() for r in requires
            ):
                errors.append(
                    f"{epath}.requires: not a list of non-empty strings"
                )
            else:
                for cap in requires:
                    if cap not in KNOWN_CAPABILITIES:
                        warnings.append(
                            f"{epath}.requires: unknown capability {cap!r}"
                        )
    return errors, warnings


# ---------------------------------------------------------------------------
# stdin (bounded, never blocks the hook)
# ---------------------------------------------------------------------------


def _read_stdin(timeout: float = STDIN_READ_TIMEOUT) -> bytes:
    """Read whatever the hook piped in, capped at ``STDIN_MAX_BYTES`` and
    ``timeout`` seconds. A TTY returns immediately; a pipe that never sends
    EOF is abandoned on a daemon thread so the hook can still exit."""
    stream = getattr(sys.stdin, "buffer", None)
    if stream is None:
        stream = sys.stdin
    if stream is None:
        return b""
    try:
        if stream.isatty():
            return b""
    except (AttributeError, OSError, ValueError):
        pass

    result: list[bytes] = []

    def _reader() -> None:
        try:
            data = stream.read(STDIN_MAX_BYTES + 1)
        except Exception:
            data = b""
        if isinstance(data, str):
            data = data.encode("utf-8", "replace")
        result.append((data or b"")[:STDIN_MAX_BYTES])

    worker = threading.Thread(target=_reader, daemon=True)
    worker.start()
    worker.join(timeout)
    return result[0] if result else b""


# ---------------------------------------------------------------------------
# dispatch
# ---------------------------------------------------------------------------


def _iso(ts: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(ts))


def _append_log(path: Path, record: dict) -> None:
    """Best-effort append of one JSONL line; logging problems are reported
    on stderr but must never fail the hook."""
    try:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as exc:
        print(
            f"hooks_dispatch: cannot write {path}: {exc}", file=sys.stderr
        )


def _skip_reason(entry: dict, profile: str) -> str | None:
    """Return why ``entry`` must not run under machine ``profile``, or None
    when it is runnable."""
    if entry.get("enabled", True) is False:
        return "disabled"
    want = entry.get("profile", "any")
    if want != "any" and want != profile:
        return f"profile {want!r} != machine {profile!r}"
    requires = entry.get("requires") or []
    if requires and profile == "corporate":
        # fail-closed: corporate never runs capability-gated extras
        return f"requires {requires} unavailable on corporate"
    return None


def _run_handler(
    command: str, stdin_data: bytes, timeout: float, env: Mapping[str, str]
) -> tuple[str, int | None]:
    """Run one handler; returns ``(status, exit_code)``."""
    try:
        proc = subprocess.run(
            command,
            shell=True,
            input=stdin_data,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            env=dict(env),
        )
    except subprocess.TimeoutExpired:
        return "timeout", None
    except OSError as exc:
        print(
            f"hooks_dispatch: cannot spawn {command!r}: {exc}",
            file=sys.stderr,
        )
        return "error", None
    if proc.returncode == ABORT_EXIT_CODE:
        return "abort", proc.returncode
    if proc.returncode == 0:
        return "ok", proc.returncode
    return "failed", proc.returncode


def dispatch_event(
    event: str,
    config_dir: Path,
    stdin_data: bytes | None = None,
    environ: Mapping[str, str] | None = None,
) -> int:
    """Fan ``event`` out to its registered handlers. Always returns 0 except
    when a handler signals abort (exit 42) — the only sanctioned way to
    fail a hook."""
    env = os.environ if environ is None else environ
    config_dir = Path(config_dir)
    log = log_path(config_dir)
    ts0 = time.time()

    if stdin_data is None:
        stdin_data = _read_stdin()

    registry, problem = load_registry(registry_path(config_dir))
    if problem is not None:
        # A broken registry must never break the hook.
        print(f"hooks_dispatch: {problem} — skipping", file=sys.stderr)
        return 0
    handlers_map = registry.get("handlers") if isinstance(registry, dict) else None
    if not isinstance(handlers_map, dict):
        return 0
    handlers = handlers_map.get(event) or []
    if not isinstance(handlers, list) or not handlers:
        return 0

    profile, _source = resolve_profile(env, config_dir)
    child_env = dict(env)
    child_env["DEVIN_EVENT"] = event
    child_env["DEVIN_HOOK_EVENT"] = event
    child_env[PROFILE_ENV_VAR] = profile

    deadline = time.monotonic() + GLOBAL_BUDGET_SECONDS
    aborted = False
    budget_exhausted = False

    for entry in handlers:
        record: dict = {
            "ts": ts0,
            "iso": _iso(ts0),
            "event": event,
            "handler": (
                entry.get("id") if isinstance(entry, dict) else None
            ),
        }
        valid = (
            isinstance(entry, dict)
            and isinstance(entry.get("command"), str)
            and bool(entry.get("command", "").strip())
        )
        if not valid:
            record.update(status="skipped", detail="invalid entry")
            _append_log(log, record)
            continue
        record["handler"] = entry.get("id")

        if budget_exhausted:
            record.update(
                status="skipped", detail="global budget exhausted"
            )
            _append_log(log, record)
            continue

        reason = _skip_reason(entry, profile)
        if reason is not None:
            record.update(status="skipped", detail=reason)
            _append_log(log, record)
            continue

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            budget_exhausted = True
            record.update(
                status="skipped", detail="global budget exhausted"
            )
            _append_log(log, record)
            continue

        try:
            per_handler = float(
                entry.get("timeout_seconds", DEFAULT_HANDLER_TIMEOUT)
            )
        except (TypeError, ValueError):
            per_handler = DEFAULT_HANDLER_TIMEOUT
        if per_handler <= 0:
            per_handler = DEFAULT_HANDLER_TIMEOUT
        timeout = min(per_handler, remaining)

        start = time.monotonic()
        status, exit_code = _run_handler(
            entry["command"], stdin_data, timeout, child_env
        )
        record.update(
            status=status,
            exit_code=exit_code,
            duration_ms=int((time.monotonic() - start) * 1000),
        )
        if status == "timeout":
            record["detail"] = f"timeout after {timeout:.1f}s"
        elif status == "failed":
            print(
                f"hooks_dispatch: handler {entry.get('id')!r} exited "
                f"{exit_code} — continuing",
                file=sys.stderr,
            )
        _append_log(log, record)
        if status == "abort":
            print(
                f"hooks_dispatch: handler {entry.get('id')!r} signalled "
                f"abort (exit {ABORT_EXIT_CODE})",
                file=sys.stderr,
            )
            aborted = True
            break

    return ABORT_EXIT_CODE if aborted else 0


# ---------------------------------------------------------------------------
# subcommands: list / check / register / unregister
# ---------------------------------------------------------------------------


def _cmd_list(args, config_dir: Path) -> int:
    registry, problem = load_registry(registry_path(config_dir))
    if problem is not None:
        print(f"::error::{problem}", file=sys.stderr)
        return 2
    handlers = (
        registry.get("handlers") if isinstance(registry, dict) else None
    ) or {}
    if not isinstance(handlers, dict):
        handlers = {}
    if args.event:
        handlers = {args.event: handlers.get(args.event) or []}
    if args.json:
        print(json.dumps(handlers, indent=2, ensure_ascii=False))
        return 0
    total = 0
    for event in sorted(handlers):
        entries = handlers[event] or []
        if not entries:
            if args.event:
                print(f"{event}: (no handlers)")
            continue
        print(f"{event}:")
        for entry in entries:
            total += 1
            if not isinstance(entry, dict):
                print("  - <invalid entry>")
                continue
            flags = []
            if entry.get("enabled", True) is False:
                flags.append("disabled")
            profile = entry.get("profile", "any")
            if profile != "any":
                flags.append(f"profile={profile}")
            requires = entry.get("requires") or []
            if requires:
                flags.append(f"requires={','.join(requires)}")
            suffix = f"  [{'; '.join(flags)}]" if flags else ""
            print(
                f"  - {entry.get('id')} "
                f"(timeout {entry.get('timeout_seconds', int(DEFAULT_HANDLER_TIMEOUT))}s){suffix}"
            )
            print(f"      {entry.get('command')}")
    if not total:
        print("no handlers registered")
    return 0


def _cmd_check(args, config_dir: Path) -> int:
    path = registry_path(config_dir)
    if not path.is_file():
        print(f"::error::{path}: no registry file", file=sys.stderr)
        return 2
    registry, problem = load_registry(path)
    if problem is not None:
        print(f"::error::{problem}", file=sys.stderr)
        return 2
    errors, warnings = validate_registry(registry)
    for warning in warnings:
        print(f"::warning::{warning}", file=sys.stderr)
    if errors:
        print(f"{path}: {len(errors)} validation error(s):", file=sys.stderr)
        for error in errors:
            print(f"  {error}", file=sys.stderr)
        return 1
    count = sum(
        len(v) for v in (registry.get("handlers") or {}).values()
        if isinstance(v, list)
    )
    print(f"ok: {path} ({count} handlers)")
    return 0


def _write_registry(path: Path, obj: dict) -> None:
    """Atomic-ish write: temp file in the same dir, then os.replace."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(obj, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp, path)


def _cmd_register(args, config_dir: Path) -> int:
    requires: list[str] = []
    for chunk in args.requires or []:
        requires.extend(
            r.strip() for r in chunk.split(",") if r.strip()
        )
    entry = {
        "id": args.id,
        "command": args.command,
        "timeout_seconds": args.timeout,
        "enabled": not args.disabled,
        "profile": args.profile,
    }
    if requires:
        entry["requires"] = requires

    probe = {
        "version": REGISTRY_VERSION,
        "handlers": {args.event: [entry]},
    }
    errors, _warnings = validate_registry(probe)
    if errors:
        for error in errors:
            print(f"::error::{error}", file=sys.stderr)
        return 1

    registry, problem = load_registry(registry_path(config_dir))
    if problem is not None:
        print(f"::error::{problem}", file=sys.stderr)
        return 2
    if not isinstance(registry, dict):
        print("::error::registry root is not an object", file=sys.stderr)
        return 1
    registry.setdefault("version", REGISTRY_VERSION)
    handlers = registry.setdefault("handlers", {})
    if not isinstance(handlers, dict):
        print("::error::registry 'handlers' is not an object", file=sys.stderr)
        return 1
    entries = handlers.setdefault(args.event, [])
    if not isinstance(entries, list):
        print(
            f"::error::registry 'handlers.{args.event}' is not a list",
            file=sys.stderr,
        )
        return 1
    for i, existing in enumerate(entries):
        if isinstance(existing, dict) and existing.get("id") == args.id:
            if not args.force:
                print(
                    f"::error::{args.id!r} already registered for "
                    f"{args.event} (use --force to replace)",
                    file=sys.stderr,
                )
                return 1
            entries[i] = entry
            break
    else:
        entries.append(entry)

    errors, _warnings = validate_registry(registry)
    if errors:
        # refuse to persist a registry we know is broken
        for error in errors:
            print(f"::error::{error}", file=sys.stderr)
        return 1
    try:
        _write_registry(registry_path(config_dir), registry)
    except OSError as exc:
        print(f"::error::cannot write registry: {exc}", file=sys.stderr)
        return 2
    print(f"registered {args.id!r} for {args.event}")
    return 0


def _cmd_unregister(args, config_dir: Path) -> int:
    path = registry_path(config_dir)
    registry, problem = load_registry(path)
    if problem is not None:
        print(f"::error::{problem}", file=sys.stderr)
        return 2
    handlers_map = (
        registry.get("handlers") if isinstance(registry, dict) else None
    )
    entries = (
        handlers_map.get(args.event)
        if isinstance(handlers_map, dict)
        else None
    )
    if not isinstance(entries, list):
        print(
            f"::error::no handlers registered for {args.event}",
            file=sys.stderr,
        )
        return 1
    kept = [
        e for e in entries
        if not (isinstance(e, dict) and e.get("id") == args.id)
    ]
    if len(kept) == len(entries):
        print(
            f"::error::{args.id!r} is not registered for {args.event}",
            file=sys.stderr,
        )
        return 1
    if kept:
        registry["handlers"][args.event] = kept
    else:
        del registry["handlers"][args.event]
    try:
        _write_registry(path, registry)
    except OSError as exc:
        print(f"::error::cannot write registry: {exc}", file=sys.stderr)
        return 2
    print(f"unregistered {args.id!r} from {args.event}")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="devin-hooks",
        description=__doc__.splitlines()[0],
    )
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--config-dir",
        help="Devin config dir (default: DEVIN_CONFIG_DIR env, then the "
        "platform config dir — ~/.config/devin on Linux)",
    )
    subs = parser.add_subparsers(dest="subcommand", required=True)

    d = subs.add_parser(
        "dispatch", parents=[common],
        help="run all enabled handlers for an event (hook entrypoint)",
    )
    d.add_argument("event", help="hook event name, e.g. SessionStart")

    ls = subs.add_parser(
        "list", parents=[common], help="show registered handlers"
    )
    ls.add_argument("--event", help="only show this event")
    ls.add_argument(
        "--json", action="store_true", help="emit raw handlers JSON"
    )

    subs.add_parser(
        "check", parents=[common], help="validate the registry shape"
    )

    r = subs.add_parser(
        "register", parents=[common],
        help="add a handler entry (files only, no side effects)",
    )
    r.add_argument("event", help="hook event name, e.g. SessionStart")
    r.add_argument("id", help="handler id ([A-Za-z0-9._-], unique per event)")
    r.add_argument("command", help="shell command the handler runs")
    r.add_argument(
        "--timeout", type=float, default=DEFAULT_HANDLER_TIMEOUT,
        help=f"per-handler timeout seconds (default: {int(DEFAULT_HANDLER_TIMEOUT)})",
    )
    r.add_argument(
        "--requires", action="append", metavar="CAP[,CAP...]",
        help="capabilities needed (repeatable or comma-separated); "
        "skipped on the corporate profile",
    )
    r.add_argument(
        "--profile", choices=HANDLER_PROFILE_CHOICES, default="any",
        help="restrict to one machine profile (default: any)",
    )
    r.add_argument(
        "--disabled", action="store_true",
        help="register in disabled state",
    )
    r.add_argument(
        "--force", action="store_true",
        help="replace an existing entry with the same id",
    )

    u = subs.add_parser(
        "unregister", parents=[common],
        help="remove a handler entry (files only)",
    )
    u.add_argument("event", help="hook event name")
    u.add_argument("id", help="handler id to remove")

    args = parser.parse_args(argv)
    config_dir = (
        Path(args.config_dir).expanduser()
        if getattr(args, "config_dir", None)
        else default_config_dir()
    )

    if args.subcommand == "dispatch":
        try:
            return dispatch_event(args.event, config_dir)
        except Exception as exc:  # never crash the host hook
            print(f"hooks_dispatch: {exc} — skipping", file=sys.stderr)
            return 0
    if args.subcommand == "list":
        return _cmd_list(args, config_dir)
    if args.subcommand == "check":
        return _cmd_check(args, config_dir)
    if args.subcommand == "register":
        return _cmd_register(args, config_dir)
    if args.subcommand == "unregister":
        return _cmd_unregister(args, config_dir)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
