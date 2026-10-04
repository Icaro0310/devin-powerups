#!/usr/bin/env python3
"""Tests for hooks_dispatch.py — tmp config dirs and synthetic handlers only.

Handlers are ``sys.executable -c "..."`` commands writing marker files into
the tmp dir; nothing outside the tmp dir is touched. The dispatch log and
registry live under ``<tmp>/.devin-ecosystem/``.

Run:
    python tools/test_hooks_dispatch.py
"""

import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

import hooks_dispatch as hd  # noqa: E402


def py(code: str) -> str:
    """A shell command running ``code`` in the current interpreter."""
    return f'"{sys.executable}" -c "{code}"'


def marker_cmd(path: Path, extra: str = "") -> str:
    target = path.as_posix()
    return py(
        "import pathlib;"
        + extra
        + f"pathlib.Path('{target}').write_text('x', encoding='utf-8')"
    )


def write_registry(config_dir: Path, handlers: dict) -> Path:
    eco = config_dir / hd.ECOSYSTEM_DIRNAME
    eco.mkdir(parents=True, exist_ok=True)
    path = eco / hd.REGISTRY_FILENAME
    path.write_text(
        json.dumps({"version": 1, "handlers": handlers}), encoding="utf-8"
    )
    return path


def read_log(config_dir: Path) -> list[dict]:
    path = hd.log_path(config_dir)
    if not path.is_file():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


class DispatchTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.config_dir = root / "cfg"
        self.config_dir.mkdir()

    def tearDown(self):
        self._tmp.cleanup()

    def dispatch(self, event="SessionStart", stdin=b"", environ=None):
        return hd.dispatch_event(
            event, self.config_dir, stdin_data=stdin, environ=environ
        )

    # -- registry edge cases ------------------------------------------------

    def test_no_registry_exits_zero(self):
        self.assertEqual(self.dispatch(), 0)
        self.assertEqual(read_log(self.config_dir), [])

    def test_malformed_registry_exits_zero(self):
        eco = self.config_dir / hd.ECOSYSTEM_DIRNAME
        eco.mkdir(parents=True)
        (eco / hd.REGISTRY_FILENAME).write_text("{not json", encoding="utf-8")
        self.assertEqual(self.dispatch(), 0)

    def test_unknown_event_exits_zero(self):
        write_registry(
            self.config_dir,
            {"Stop": [{"id": "h1", "command": marker_cmd(self.config_dir / "m")}]},
        )
        self.assertEqual(self.dispatch("SessionStart"), 0)
        self.assertEqual(read_log(self.config_dir), [])

    # -- handler execution ---------------------------------------------------

    def test_handler_runs_and_is_logged(self):
        marker = self.config_dir / "ran"
        write_registry(
            self.config_dir,
            {"SessionStart": [{"id": "h1", "command": marker_cmd(marker)}]},
        )
        self.assertEqual(self.dispatch(), 0)
        self.assertTrue(marker.is_file())
        records = read_log(self.config_dir)
        self.assertEqual(len(records), 1)
        rec = records[0]
        self.assertEqual(rec["event"], "SessionStart")
        self.assertEqual(rec["handler"], "h1")
        self.assertEqual(rec["status"], "ok")
        self.assertEqual(rec["exit_code"], 0)
        self.assertIn("duration_ms", rec)
        self.assertIn("ts", rec)
        self.assertIn("iso", rec)

    def test_stdin_is_forwarded(self):
        out = self.config_dir / "stdin.bin"
        write_registry(
            self.config_dir,
            {
                "UserPromptSubmit": [
                    {
                        "id": "echo",
                        "command": py(
                            "import sys,pathlib;"
                            f"pathlib.Path('{out.as_posix()}')"
                            ".write_bytes(sys.stdin.buffer.read())"
                        ),
                    }
                ]
            },
        )
        payload = json.dumps({"prompt": "olá"}).encode("utf-8")
        self.assertEqual(self.dispatch("UserPromptSubmit", stdin=payload), 0)
        self.assertEqual(out.read_bytes(), payload)

    def test_failing_handler_never_fails_hook(self):
        marker = self.config_dir / "second"
        write_registry(
            self.config_dir,
            {
                "Stop": [
                    {"id": "bad", "command": py("import sys;sys.exit(1)")},
                    {"id": "after", "command": marker_cmd(marker)},
                ]
            },
        )
        self.assertEqual(self.dispatch("Stop"), 0)
        self.assertTrue(marker.is_file())
        statuses = [r["status"] for r in read_log(self.config_dir)]
        self.assertEqual(statuses, ["failed", "ok"])

    def test_abort_exit_code_42_stops_dispatch(self):
        marker = self.config_dir / "never"
        write_registry(
            self.config_dir,
            {
                "Stop": [
                    {"id": "gate", "command": py("import sys;sys.exit(42)")},
                    {"id": "after", "command": marker_cmd(marker)},
                ]
            },
        )
        self.assertEqual(self.dispatch("Stop"), hd.ABORT_EXIT_CODE)
        self.assertFalse(marker.exists())
        statuses = [r["status"] for r in read_log(self.config_dir)]
        self.assertEqual(statuses, ["abort"])

    def test_disabled_handler_skipped(self):
        marker = self.config_dir / "m"
        write_registry(
            self.config_dir,
            {
                "Stop": [
                    {
                        "id": "off",
                        "command": marker_cmd(marker),
                        "enabled": False,
                    }
                ]
            },
        )
        self.assertEqual(self.dispatch("Stop"), 0)
        self.assertFalse(marker.exists())
        rec = read_log(self.config_dir)[0]
        self.assertEqual(rec["status"], "skipped")
        self.assertEqual(rec["detail"], "disabled")

    # -- profile gating --------------------------------------------------------

    def test_requires_skipped_on_corporate(self):
        marker = self.config_dir / "m"
        write_registry(
            self.config_dir,
            {
                "SessionStart": [
                    {
                        "id": "daemon-thing",
                        "command": marker_cmd(marker),
                        "requires": ["daemon"],
                    }
                ]
            },
        )
        # default profile (no env, no file) is corporate → skipped
        self.assertEqual(self.dispatch(environ={}), 0)
        self.assertFalse(marker.exists())
        rec = read_log(self.config_dir)[0]
        self.assertEqual(rec["status"], "skipped")
        self.assertIn("requires", rec["detail"])

    def test_requires_runs_on_personal(self):
        marker = self.config_dir / "m"
        write_registry(
            self.config_dir,
            {
                "SessionStart": [
                    {
                        "id": "daemon-thing",
                        "command": marker_cmd(marker),
                        "requires": ["daemon"],
                    }
                ]
            },
        )
        env = {hd.PROFILE_ENV_VAR: "personal"}
        self.assertEqual(self.dispatch(environ=env), 0)
        self.assertTrue(marker.is_file())

    def test_profile_field_restricts_handler(self):
        marker = self.config_dir / "m"
        write_registry(
            self.config_dir,
            {
                "SessionStart": [
                    {
                        "id": "personal-only",
                        "command": marker_cmd(marker),
                        "profile": "personal",
                    }
                ]
            },
        )
        self.assertEqual(self.dispatch(environ={}), 0)
        self.assertFalse(marker.exists())
        self.assertEqual(
            read_log(self.config_dir)[0]["status"], "skipped"
        )
        env = {hd.PROFILE_ENV_VAR: "personal"}
        self.assertEqual(self.dispatch(environ=env), 0)
        self.assertTrue(marker.is_file())

    def test_profile_file_in_config_dir(self):
        (self.config_dir / hd.PROFILE_FILENAME).write_text(
            '{"profile": "personal"}', encoding="utf-8"
        )
        profile, source = hd.resolve_profile({}, self.config_dir)
        self.assertEqual(profile, "personal")
        self.assertIn(hd.PROFILE_FILENAME, source)

    def test_profile_env_beats_file_and_default_is_corporate(self):
        (self.config_dir / hd.PROFILE_FILENAME).write_text(
            '{"profile": "personal"}', encoding="utf-8"
        )
        self.assertEqual(
            hd.resolve_profile(
                {hd.PROFILE_ENV_VAR: "corporate"}, self.config_dir
            )[0],
            "corporate",
        )
        self.assertEqual(
            hd.resolve_profile({}, self.config_dir)[0], "personal"
        )
        self.assertEqual(
            hd.resolve_profile({}, Path(self._tmp.name) / "nope")[0],
            "corporate",
        )

    # -- timeouts ---------------------------------------------------------------

    def test_handler_timeout_logged_and_hook_survives(self):
        write_registry(
            self.config_dir,
            {
                "Stop": [
                    {
                        "id": "slow",
                        "command": py("import time;time.sleep(30)"),
                        "timeout_seconds": 0.5,
                    }
                ]
            },
        )
        start = hd.time.monotonic()
        self.assertEqual(self.dispatch("Stop"), 0)
        self.assertLess(hd.time.monotonic() - start, 25)
        rec = read_log(self.config_dir)[0]
        self.assertEqual(rec["status"], "timeout")

    def test_global_budget_skips_later_handlers(self):
        marker = self.config_dir / "second"
        write_registry(
            self.config_dir,
            {
                "Stop": [
                    {
                        "id": "slow",
                        "command": py("import time;time.sleep(30)"),
                        "timeout_seconds": 30,
                    },
                    {"id": "after", "command": marker_cmd(marker)},
                ]
            },
        )
        with mock.patch.object(hd, "GLOBAL_BUDGET_SECONDS", 1.0):
            self.assertEqual(self.dispatch("Stop"), 0)
        self.assertFalse(marker.exists())
        records = read_log(self.config_dir)
        self.assertEqual(records[0]["status"], "timeout")
        self.assertEqual(records[1]["status"], "skipped")
        self.assertIn("budget", records[1]["detail"])

    # -- stdin robustness --------------------------------------------------------

    def test_read_stdin_tty_and_bytesio(self):
        with mock.patch.object(hd.sys, "stdin", io.BytesIO(b"payload")):
            self.assertEqual(hd._read_stdin(timeout=1), b"payload")
        with mock.patch.object(hd.sys, "stdin", io.BytesIO(b"")):
            self.assertEqual(hd._read_stdin(timeout=1), b"")

        class FakeTty(io.BytesIO):
            def isatty(self):
                return True

        with mock.patch.object(
            hd.sys, "stdin", FakeTty(b"would-block-if-read")
        ):
            self.assertEqual(hd._read_stdin(timeout=1), b"")


class CliTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.config_dir = root / "cfg"
        self.config_dir.mkdir()
        self.stdin_patch = mock.patch.object(
            hd.sys, "stdin", io.BytesIO(b"")
        )
        self.stdin_patch.start()

    def tearDown(self):
        self.stdin_patch.stop()
        self._tmp.cleanup()

    def argv(self, *args):
        return [*args, "--config-dir", str(self.config_dir)]

    # -- register / unregister ---------------------------------------------------

    def test_register_list_unregister_roundtrip(self):
        rc = hd.main(
            self.argv(
                "register", "SessionStart", "h1",
                "python handler.py", "--timeout", "10",
                "--requires", "daemon,scheduler",
            )
        )
        self.assertEqual(rc, 0)
        path = hd.registry_path(self.config_dir)
        registry = json.loads(path.read_text(encoding="utf-8"))
        entry = registry["handlers"]["SessionStart"][0]
        self.assertEqual(entry["id"], "h1")
        self.assertEqual(entry["command"], "python handler.py")
        self.assertEqual(entry["timeout_seconds"], 10)
        self.assertTrue(entry["enabled"])
        self.assertEqual(entry["profile"], "any")
        self.assertEqual(entry["requires"], ["daemon", "scheduler"])

        self.assertEqual(hd.main(self.argv("check")), 0)
        self.assertEqual(
            hd.main(self.argv("unregister", "SessionStart", "h1")), 0
        )
        registry = json.loads(path.read_text(encoding="utf-8"))
        self.assertNotIn("SessionStart", registry["handlers"])

    def test_register_duplicate_fails_unless_force(self):
        args = ("register", "Stop", "h1", "cmd a")
        self.assertEqual(hd.main(self.argv(*args)), 0)
        self.assertEqual(hd.main(self.argv(*args)), 1)
        self.assertEqual(
            hd.main(
                self.argv(
                    "register", "Stop", "h1", "cmd b", "--force"
                )
            ),
            0,
        )
        entry = json.loads(
            hd.registry_path(self.config_dir).read_text(encoding="utf-8")
        )["handlers"]["Stop"][0]
        self.assertEqual(entry["command"], "cmd b")

    def test_register_rejects_bad_entry(self):
        self.assertEqual(
            hd.main(
                self.argv(
                    "register", "Stop", "bad id!", "cmd"
                )
            ),
            1,
        )
        self.assertFalse(hd.registry_path(self.config_dir).is_file())

    def test_unregister_missing_fails(self):
        self.assertEqual(
            hd.main(self.argv("unregister", "Stop", "ghost")), 1
        )

    def test_register_does_not_touch_other_events(self):
        self.assertEqual(
            hd.main(self.argv("register", "Stop", "a", "cmd a")), 0
        )
        self.assertEqual(
            hd.main(
                self.argv("register", "SessionStart", "b", "cmd b")
            ),
            0,
        )
        handlers = json.loads(
            hd.registry_path(self.config_dir).read_text(encoding="utf-8")
        )["handlers"]
        self.assertEqual(set(handlers), {"Stop", "SessionStart"})

    # -- check -------------------------------------------------------------------

    def test_check_reports_errors_and_warnings(self):
        write_registry(
            self.config_dir,
            {
                "WeirdEvent": [
                    {"id": "ok", "command": "x"},
                    {"id": "ok", "command": ""},
                    "not-a-dict",
                ]
            },
        )
        self.assertEqual(hd.main(self.argv("check")), 1)

    def test_check_missing_registry(self):
        self.assertEqual(hd.main(self.argv("check")), 2)

    def test_check_valid_registry(self):
        write_registry(
            self.config_dir,
            {"Stop": [{"id": "h", "command": "x", "requires": ["daemon"]}]},
        )
        self.assertEqual(hd.main(self.argv("check")), 0)

    # -- list ----------------------------------------------------------------------

    def test_list_shows_handlers(self):
        write_registry(
            self.config_dir,
            {
                "Stop": [
                    {
                        "id": "h1",
                        "command": "x",
                        "enabled": False,
                        "requires": ["daemon"],
                    }
                ]
            },
        )
        buf = io.StringIO()
        with mock.patch.object(hd.sys, "stdout", buf):
            self.assertEqual(hd.main(self.argv("list")), 0)
        out = buf.getvalue()
        self.assertIn("Stop", out)
        self.assertIn("h1", out)
        self.assertIn("disabled", out)

    def test_list_empty(self):
        buf = io.StringIO()
        with mock.patch.object(hd.sys, "stdout", buf):
            self.assertEqual(hd.main(self.argv("list")), 0)
        self.assertIn("no handlers", buf.getvalue())

    # -- dispatch via main() ---------------------------------------------------------

    def test_main_dispatch_uses_config_dir(self):
        marker = self.config_dir / "ran"
        write_registry(
            self.config_dir,
            {"Stop": [{"id": "h", "command": marker_cmd(marker)}]},
        )
        self.assertEqual(hd.main(self.argv("dispatch", "Stop")), 0)
        self.assertTrue(marker.is_file())


class ConfigDirTests(unittest.TestCase):
    def test_env_override_and_platform_defaults(self):
        env = {"DEVIN_CONFIG_DIR": "/x/custom"}
        self.assertEqual(
            hd.default_config_dir(env, "linux"), Path("/x/custom")
        )
        env = {"APPDATA": "C:\\Roaming"}
        self.assertEqual(
            hd.default_config_dir(env, "win32"),
            Path("C:\\Roaming") / "Devin",
        )
        tmp = Path(tempfile.mkdtemp())
        env = {"XDG_CONFIG_HOME": str(tmp)}
        (tmp / "devin").mkdir()
        self.assertEqual(
            hd.default_config_dir(env, "linux"), tmp / "devin"
        )
        env = {"XDG_CONFIG_HOME": str(tmp / "empty")}
        self.assertEqual(
            hd.default_config_dir(env, "linux"),
            tmp / "empty" / "devin",
        )
        with mock.patch.object(hd.Path, "home", return_value=tmp):
            self.assertEqual(
                hd.default_config_dir({}, "darwin"),
                tmp / "Library" / "Application Support" / "Devin",
            )

    def test_user_dir_preferred_over_plain_devin(self):
        tmp = Path(tempfile.mkdtemp())
        (tmp / "Devin" / "User").mkdir(parents=True)
        (tmp / "devin").mkdir()
        env = {"XDG_CONFIG_HOME": str(tmp)}
        self.assertEqual(
            hd.default_config_dir(env, "linux"), tmp / "Devin"
        )


if __name__ == "__main__":
    unittest.main()
