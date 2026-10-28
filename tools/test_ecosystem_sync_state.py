"""Tests for ecosystem_sync --state-md snapshot generation."""
import importlib.util
import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent))
import ecosystem_sync as es


def _row(product, channel, local, remote, state):
    return es.Row(product=product, channel=channel, local=local,
                  remote=remote, state=state)


class WriteStateMdTests(unittest.TestCase):
    def test_writes_sections_and_rows(self):
        out = Path(self._tmpdir()) / "state.md"
        rows = [
            _row("devin-x", "pypi", "0.1.0", "0.1.0", "ok"),
            _row("devin-y", "open-vsx", "0.2.0", "0.2.1", "drift"),
        ]
        es.write_state_md(
            out, rows,
            [("ollama (via devin-vm)", "ok")],
            [("devin-state", 106, "feat: rotate")],
            datetime(2026, 10, 28, 0, 0, tzinfo=timezone.utc),
        )
        text = out.read_text()
        self.assertIn("## Published versions", text)
        self.assertIn("| devin-y | open-vsx | 0.2.0 | 0.2.1 | drift |", text)
        self.assertIn("ollama (via devin-vm): ok", text)
        self.assertIn("**devin-y** (open-vsx)", text)
        self.assertIn("devin-state#106 — feat: rotate", text)
        self.assertIn("do not edit", text)

    def test_empty_drift_and_prs(self):
        out = Path(self._tmpdir()) / "state.md"
        es.write_state_md(out, [_row("a", "pypi", "1", "1", "ok")], [], [],
                          datetime.now(timezone.utc))
        text = out.read_text()
        self.assertIn("- none", text)

    def _tmpdir(self):
        import tempfile
        d = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(d, ignore_errors=True))
        return d


class CollectOpenPrsTests(unittest.TestCase):
    def test_parses_and_sorts(self):
        payload = json.dumps([{"number": 3, "title": "t"}, {"number": 7, "title": "x"}])
        proc = mock.Mock(returncode=0, stdout=payload)
        with mock.patch.object(es.subprocess, "run", return_value=proc):
            prs = es.collect_open_prs({"devin-a": "Icaro0310"}, 10)
        self.assertEqual(prs, [("devin-a", 3, "t"), ("devin-a", 7, "x")])

    def test_failure_skips_repo(self):
        with mock.patch.object(es.subprocess, "run",
                               side_effect=OSError("no gh")):
            self.assertEqual(es.collect_open_prs({"devin-a": "o"}, 10), [])
        proc = mock.Mock(returncode=1, stdout="")
        with mock.patch.object(es.subprocess, "run", return_value=proc):
            self.assertEqual(es.collect_open_prs({"devin-a": "o"}, 10), [])


if __name__ == "__main__":
    unittest.main()


class CollectCiConfigTests(unittest.TestCase):
    def _gh(self, owner, repo, path, timeout):
        if path == "/actions/secrets":
            if repo in ("no-secret", "bare"):
                return {"secrets": []}
            return {"secrets": [{"name": "TS_AUTHKEY"}]}
        if repo == "no-secret":
            return [{"name": "review-fallback.yml"}]
        if repo in ("no-wf", "bare"):
            return [{"name": "test.yml"}]
        return [{"name": "review-fallback.yml"}, {"name": "test.yml"}]

    def test_states(self):
        repos = {"ok-r": "o", "no-wf": "o", "no-secret": "o", "bare": "o"}
        with mock.patch.object(es, "_gh_api", side_effect=self._gh):
            rows = {r.product: r for r in es.collect_ci_config(repos, 10)}
        self.assertEqual(rows["ok-r"].state, "ok")
        self.assertEqual(rows["no-wf"].state, "drift")
        self.assertEqual(rows["no-wf"].local, "secret only")
        self.assertEqual(rows["no-secret"].local, "workflow only")
        self.assertEqual(rows["bare"].local, "neither")
