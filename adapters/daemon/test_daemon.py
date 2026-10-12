"""Contract test for the <pkg> daemon face.

Skeleton — copy next to daemon.py (or into the package's tests/ dir).
Everything is tested through the injected seams; nothing here needs a
real CLI, a real clock or a real signal.
"""

import json
import subprocess
from pathlib import Path

import daemon  # the adapter module — fix the import to its real location


def _fake_runner(payload: dict):
    def runner(args, **_kw):
        assert args[1:] == ["check", "--json"], "daemon must stay a thin CLI shell"
        return subprocess.CompletedProcess(
            args, 0, stdout=json.dumps(payload), stderr=""
        )

    return runner


def test_run_check_returns_cli_payload(tmp_path):
    payload = {"overall": "PASS", "summary": {"pass": 3}}
    assert daemon.run_check(runner=_fake_runner(payload)) == payload


def test_run_check_non_json_is_error_not_crash():
    def runner(args, **_kw):
        return subprocess.CompletedProcess(args, 1, stdout="oops", stderr="boom")

    payload = daemon.run_check(runner=runner)
    assert payload["error"] == "NonJsonOutput"
    assert payload["detail"]


def test_main_writes_state_and_stops(tmp_path):
    state = tmp_path / "last.json"

    def sleep_one(_s):
        daemon._running = False  # fake clock: first tick stops the loop

    daemon._running = True
    rc = daemon.main(
        interval=60,
        state_path=state,
        sleep=sleep_one,
        runner=_fake_runner({"overall": "WARN"}),
    )
    assert rc == 0
    assert json.loads(state.read_text())["overall"] == "WARN"
