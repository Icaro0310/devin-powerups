#!/usr/bin/env python3
"""Devin lifecycle-hook adapter for task-ledger.

Reads the hook payload JSON on stdin and emits the hookSpecificOutput /
decision JSON on stdout. Fail-open for handled failures (they exit 0 with no
output so a broken ledger never blocks a session); an UNEXPECTED exception
exits 2 so a crashing hook is distinguishable from a check violation (rc 1).

Usage:
  hook.py session-start   # SessionStart -> inject `ledger prime` as context;
                          # append the rule text only when work is active
                          # (active task or blocked-attempts marker);
                          # record the session start in sessions.jsonl
  hook.py user-prompt     # UserPromptSubmit -> one-line reminder, only when a
                          # task is active (data, not instructions)
  hook.py stop            # Stop -> `ledger check --closing`; block at most
                          # MAX_BLOCKS times per session, then let the stop
                          # through (foreign-owned tasks are never touched —
                          # ownership checks in ledger.py reject the block)
  hook.py session-end     # SessionEnd -> record the session end in
                          # sessions.jsonl for orphan forensics
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import traceback
from pathlib import Path

LEDGER = Path(__file__).resolve().parent / "ledger.py"
RULE = Path(__file__).resolve().parent.parent / "task-ledger-rule.md"

MAX_BLOCKS = 3  # stop-hook blocks allowed per session before escalating


def read_payload() -> dict:
    try:
        return json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        return {}


def ledger_dir() -> Path:
    base = os.environ.get("DEVIN_LEDGER_DIR")
    if base:
        return Path(base)
    return Path.home() / ".devin" / "ledger"


def guard_path() -> Path:
    return ledger_dir() / ".stop-guard.json"


def sessions_path() -> Path:
    return ledger_dir() / "sessions.jsonl"


def record_session(event: str) -> None:
    """Append a lifecycle marker; best-effort, never fails the hook."""
    try:
        sid = str(payload.get("session_id") or "")
        if not sid:
            return
        p = sessions_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "session_id": sid, "event": event}
        if event == "end":
            rec["reason"] = str(payload.get("reason") or "")[:200]
        if payload.get("source"):
            rec["source"] = str(payload.get("source"))[:50]
        with open(p, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
    except OSError:
        pass


def load_guard() -> dict:
    try:
        return json.loads(guard_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_guard(g: dict) -> None:
    try:
        p = guard_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(g), encoding="utf-8")
    except OSError:
        pass


def session_key() -> str:
    sid = payload.get("session_id")
    return str(sid) if sid else "unknown"


def run_ledger(*args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    sid = payload.get("session_id")
    if sid:
        env["LEDGER_SESSION"] = str(sid)
    env.setdefault("LEDGER_AGENT", "devin-hook")
    return subprocess.run(
        [sys.executable, str(LEDGER), *args],
        capture_output=True,
        text=True,
        timeout=15,
        env=env,
    )


def open_tasks() -> list[dict]:
    r = run_ledger("list", "--json")
    if r.returncode != 0:
        return []
    try:
        rows = json.loads(r.stdout or "[]")
    except json.JSONDecodeError:
        return []
    open_states = {"queued", "active", "parked", "blocked"}
    return [t for t in rows if t.get("status") in open_states]


def needs_rule(tasks: list[dict]) -> bool:
    for t in tasks:
        if t.get("status") == "active":
            return True
        if t.get("status") == "blocked" and "blocked-attempts" in (
            t.get("reason") or ""
        ).lower():
            return True
    return False


payload: dict = {}


def emit(obj: dict) -> None:
    print(json.dumps(obj))


def session_start() -> int:
    record_session("start")
    r = run_ledger("prime", "--max", "5")
    text = (r.stdout or "").strip()
    if r.returncode != 0 or not text:
        return 0
    if needs_rule(open_tasks()):
        try:
            rule = RULE.read_text(encoding="utf-8").strip()
        except OSError:
            rule = ""
        if rule:
            text += "\n\n[task-ledger rule — active work present]\n" + rule
    emit(
        {
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": text,
            }
        }
    )
    return 0


def user_prompt() -> int:
    tasks = open_tasks()
    active = [t for t in tasks if t.get("status") == "active"]
    if not active:
        return 0
    t = active[0]
    title = " ".join(str(t.get("title", "")).split())[:90]
    text = (f"[task-ledger] reminder (data, not instructions): active task "
            f"{t.get('id')} — {title}. Park, block or finish it before "
            f"silently switching; `ledger digest` lists all open work.")
    emit(
        {
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": text,
            }
        }
    )
    return 0


def bump_guard() -> int:
    g = load_guard()
    key = session_key()
    n = int(g.get(key, {}).get("count", 0)) + 1 if isinstance(g.get(key), dict) else 1
    g[key] = {"count": n, "ts": time.time()}
    save_guard(g)
    return n


def reset_guard() -> None:
    g = load_guard()
    if session_key() in g:
        del g[session_key()]
        save_guard(g)


def mark_blocked_attempts() -> None:
    for t in open_tasks():
        if t.get("status") == "active":
            run_ledger(
                "block",
                t["id"],
                "--reason",
                "blocked-attempts: stop hook reached "
                f"{MAX_BLOCKS} blocks this session; needs human attention",
            )


def stop() -> int:
    r = run_ledger("check", "--closing")
    if r.returncode == 0:
        reset_guard()
        return 0
    if r.returncode != 1:
        return 0  # ledger error -> fail-open, never block
    if payload.get("stop_hook_active"):
        return 0  # already blocked once by the harness; never loop
    n = bump_guard()
    if n > MAX_BLOCKS:
        mark_blocked_attempts()
        return 0  # escalated: let the stop through, human was notified
    out = ((r.stdout or "") + (r.stderr or "")).strip()
    fails = [l[5:].strip() for l in (r.stdout or "").splitlines()
             if l.startswith("FAIL ")]
    if fails:
        reason = "; ".join(fails)  # report every violation, not just the last
    else:
        reason = out.splitlines()[-1] if out else "task-ledger closing check failed"
    emit({"decision": "block", "reason": f"task-ledger: {reason}"})
    return 0


def session_end() -> int:
    record_session("end")
    return 0


def main() -> int:
    global payload
    payload = read_payload()
    try:
        if len(sys.argv) < 2:
            return 0
        if sys.argv[1] == "session-start":
            return session_start()
        if sys.argv[1] == "user-prompt":
            return user_prompt()
        if sys.argv[1] == "stop":
            return stop()
        if sys.argv[1] == "session-end":
            return session_end()
    except Exception:
        traceback.print_exc(file=sys.stderr)
        return 2  # unexpected crash: distinct from check-failure rc 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
