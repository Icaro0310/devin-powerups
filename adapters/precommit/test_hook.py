"""Contract test for the <pkg> pre-commit face.

Skeleton — copy next to hook.py (or into the package's tests/ dir) and
fix the import. The injected runner means nothing here needs a real CLI.
"""

import io
import subprocess

import hook  # the adapter module — fix the import to its real location


def _completed(rc: int, stdout: str = "{}", stderr: str = ""):
    return subprocess.CompletedProcess([], rc, stdout=stdout, stderr=stderr)


def test_pass_maps_to_zero():
    def runner(args, **_kw):
        assert args[1:] == ["check", "--json"], "hook must stay a thin CLI shell"
        return _completed(0)

    assert hook.run_hook(runner=runner, out=io.StringIO()) == 0


def test_findings_map_to_one_and_report():
    out = io.StringIO()
    rc = hook.run_hook(
        runner=lambda *a, **k: _completed(1, stderr="3 findings"),
        out=out,
    )
    assert rc == 1
    assert "3 findings" in out.getvalue()


def test_missing_cli_fails_closed():
    def runner(*_a, **_k):
        raise OSError("not found")

    assert hook.run_hook(runner=runner, out=io.StringIO()) == 2


def test_extra_args_are_forwarded():
    seen = {}

    def runner(args, **_kw):
        seen["args"] = args
        return _completed(0)

    assert hook.run_hook(["--severity", "warn"], runner=runner, out=io.StringIO()) == 0
    assert seen["args"][-2:] == ["--severity", "warn"]
