"""schedule.py — F6 opt-in scheduling (elapsed backend + registry)."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

import schedule  # noqa: E402


class Base(unittest.TestCase):
    def setUp(self):
        self.cfg = tempfile.mkdtemp()

    def run_cli(self, *argv):
        return schedule.main(["--config-dir", self.cfg, *argv])


class TestElapsed(Base):
    def test_install_elapsed_forced(self):
        self.assertEqual(self.run_cli(
            "install", "daily-backup", "echo hi", "--daily",
            "--backend", "elapsed"), 0)
        reg = schedule._load_registry(Path(self.cfg))
        j = reg["jobs"]["daily-backup"]
        self.assertEqual(j["backend"], "elapsed")
        self.assertEqual(j["interval_h"], 24)

    def test_check_due_then_run_sets_last_run(self):
        self.run_cli("install", "j", "true", "--every", "1",
                     "--backend", "elapsed")
        self.assertEqual(self.run_cli("check", "--run"), 0)
        reg = schedule._load_registry(Path(self.cfg))
        self.assertGreater(reg["jobs"]["j"]["last_run"], 0)
        # just ran — no longer due
        self.assertEqual(self.run_cli("check"), 0)

    def test_check_not_due(self):
        self.run_cli("install", "j", "true", "--every", "9999",
                     "--backend", "elapsed")
        # fresh job has last_run=0 → due; mark it
        reg = schedule._load_registry(Path(self.cfg))
        reg["jobs"]["j"]["last_run"] = int(schedule.time.time())
        schedule._save_registry(Path(self.cfg), reg)
        self.assertEqual(self.run_cli("check"), 0)

    def test_uninstall_elapsed(self):
        self.run_cli("install", "j", "true", "--backend", "elapsed")
        self.assertEqual(self.run_cli("uninstall", "j"), 0)
        reg = schedule._load_registry(Path(self.cfg))
        self.assertNotIn("j", reg["jobs"])

    def test_uninstall_missing(self):
        self.assertEqual(self.run_cli("uninstall", "ghost"), 1)


class TestGuardsAndBackends(Base):
    def test_guarded_command_wraps(self):
        wrapped = schedule._guarded_command("vacuum.sh", True)
        self.assertIn("pgrep" if not sys.platform.startswith("win")
                      else "tasklist", wrapped)
        self.assertEqual(schedule._guarded_command("x", False), "x")

    def test_requires_devin_closed_persisted(self):
        self.run_cli("install", "vac", "v.sh",
                     "--requires-devin-closed", "--backend", "elapsed")
        j = schedule._load_registry(Path(self.cfg))["jobs"]["vac"]
        self.assertTrue(j["requires_devin_closed"])
        self.assertIn("pgrep", j["guarded_command"])

    def test_auto_backend_resolution(self):
        got = schedule.resolve_backend("auto")
        if sys.platform.startswith("win"):
            expected = "tasksch"
        else:
            expected = "cron" if schedule._has_cron() else "elapsed"
        self.assertEqual(got, expected)

    def test_cron_line_format(self):
        line = schedule._cron_line("n", "echo x", 24)
        self.assertIn("@daily", line)
        self.assertIn("# devin-ecosystem:n", line)
        line = schedule._cron_line("n", "echo x", 6)
        self.assertIn("0 */6 * * *", line)


if __name__ == "__main__":
    unittest.main()
