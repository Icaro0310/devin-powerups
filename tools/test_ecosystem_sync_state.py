"""Tests for ecosystem_sync --state-md snapshot generation."""
import importlib.util
import json
import sqlite3
import sys
import tempfile
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


NOW = 1_800_000_000.0  # fixed epoch for freshness age math


class FreshnessAgeMathTests(unittest.TestCase):
    def test_ok_drift_boundary(self):
        ok = es._fresh_row("dispatcher", "r", 48,
                           (NOW - 47 * 3600, True, ""), NOW)
        self.assertEqual((ok.state, ok.local), ("ok", "47h"))
        self.assertEqual(ok.channel, "freshness")
        edge = es._fresh_row("dispatcher", "r", 48,
                             (NOW - 48 * 3600, True, ""), NOW)
        self.assertEqual(edge.state, "ok")  # <= threshold is still ok
        drift = es._fresh_row("dispatcher", "r", 48,
                              (NOW - 49 * 3600, True, ""), NOW)
        self.assertEqual((drift.state, drift.local), ("drift", "49h"))
        self.assertIn(drift.state, es.DRIFT_STATES)
        self.assertEqual(drift.remote, "<=2d")

    def test_never_and_unavailable(self):
        never = es._fresh_row("scout", "r", 96, (None, True, ""), NOW)
        self.assertEqual((never.state, never.local), ("drift", "never"))
        unavail = es._fresh_row("scout", "r", 96,
                                (None, False, "no jsonl"), NOW)
        self.assertEqual(unavail.state, "unavailable")
        self.assertEqual(unavail.note, "no jsonl")


class DispatcherProbeTests(unittest.TestCase):
    def _tmpdb(self, columns="finished_at", epoch=NOW - 3600, rows=1):
        d = tempfile.mkdtemp()
        self.addCleanup(
            lambda: __import__("shutil").rmtree(d, ignore_errors=True))
        db = Path(d) / "site" / "qwenpaw-queue" / "qwenpaw-queue.db"
        db.parent.mkdir(parents=True)
        conn = sqlite3.connect(db)
        conn.execute(f"CREATE TABLE tasks (id TEXT, {columns} REAL)")
        for i in range(rows):
            conn.execute("INSERT INTO tasks VALUES (?, ?)", (f"t{i}", epoch))
        conn.commit()
        conn.close()
        return Path(d)

    def test_sqlite_finished_at(self):
        root = self._tmpdb()
        epoch, determined, note = es._probe_dispatcher([root], 5)
        self.assertTrue(determined)
        self.assertAlmostEqual(epoch, NOW - 3600)

    def test_sqlite_completed_at_variant(self):
        root = self._tmpdb(columns="completed_at")
        epoch, determined, _ = es._probe_dispatcher([root], 5)
        self.assertTrue(determined)
        self.assertAlmostEqual(epoch, NOW - 3600)

    def test_empty_table_is_never(self):
        root = self._tmpdb(rows=0)
        epoch, determined, note = es._probe_dispatcher([root], 5)
        self.assertTrue(determined)
        self.assertIsNone(epoch)
        self.assertIn("no finished task", note)

    def test_nothing_found_unavailable(self):
        d = tempfile.mkdtemp()
        self.addCleanup(
            lambda: __import__("shutil").rmtree(d, ignore_errors=True))
        epoch, determined, _ = es._probe_dispatcher([Path(d)], 5)
        self.assertFalse(determined)
        self.assertIsNone(epoch)


class SlackLedgerProbeTests(unittest.TestCase):
    def _env(self):
        d = tempfile.mkdtemp()
        self.addCleanup(
            lambda: __import__("shutil").rmtree(d, ignore_errors=True))
        # HOME is patched too so the real ~/.local/state ledger can't leak in
        return d, mock.patch.dict(
            es.os.environ, {"XDG_STATE_HOME": d, "HOME": d})

    def test_missing_ledger_unavailable(self):
        d, patcher = self._env()
        with patcher:
            epoch, determined, note = es._probe_slack_output()
        self.assertFalse(determined)
        self.assertIsNone(epoch)
        self.assertIn("no send ledger", note)

    def test_old_ledger_drifts(self):
        d, patcher = self._env()
        ledger = Path(d) / "devin" / "slack-notify" / "last-sent.json"
        ledger.parent.mkdir(parents=True)
        ledger.write_text(json.dumps({"ts": NOW - 80 * 3600}))
        with patcher:
            probe = es._probe_slack_output()
        epoch, determined, _ = probe
        self.assertTrue(determined)
        self.assertAlmostEqual(epoch, NOW - 80 * 3600)
        row = es._fresh_row("slack-output", "r", 72, probe, NOW)
        self.assertEqual((row.state, row.local), ("drift", "80h"))

    def test_fresh_ledger_ok_and_jsonl(self):
        d, patcher = self._env()
        ledger = Path(d) / "devin" / "slack-notify" / "last-sent.jsonl"
        ledger.parent.mkdir(parents=True)
        ledger.write_text(
            '{"ts": 1}\n' + json.dumps({"ts": NOW - 3600}) + "\n")
        with patcher:
            epoch, determined, _ = es._probe_slack_output()
        self.assertTrue(determined)
        self.assertAlmostEqual(epoch, NOW - 3600)


class OpenSilenceIssuesTests(unittest.TestCase):
    def test_dedup_by_component_name(self):
        calls = []

        def fake_run(cmd, **kw):
            calls.append(cmd)
            if cmd[1:3] == ["issue", "list"]:
                return mock.Mock(returncode=0, stdout=json.dumps(
                    [{"number": 9,
                      "title": "[silence] dispatcher: 60h without output"}]))
            return mock.Mock(returncode=0, stdout="https://x/1\n", stderr="")

        rows = [
            es.Row("dispatcher", "freshness", "60h", "<=2d", "drift", "o/r"),
            es.Row("scout", "freshness", "5d", "<=4d", "drift", "o/r"),
        ]
        with mock.patch.object(es.subprocess, "run", side_effect=fake_run):
            messages = es.open_silence_issues(rows, 5)
        created = [c for c in calls if c[1:3] == ["issue", "create"]]
        self.assertEqual(len(created), 1)  # dispatcher deduped, scout filed
        self.assertIn("[silence] scout: 5d without output", created[0])
        self.assertTrue(any("skipped" in m for m in messages))
        self.assertTrue(any("opened" in m for m in messages))

    def test_label_created_before_issue(self):
        def fake_run(cmd, **kw):
            return mock.Mock(returncode=0, stdout="[]" if "list" in cmd else "u")

        rows = [es.Row("heartbeat", "freshness", "3h", "<=1h", "drift", "o/r")]
        with mock.patch.object(es.subprocess, "run", side_effect=fake_run) as m:
            es.open_silence_issues(rows, 5)
        kinds = [(cmd[1], cmd[2]) for cmd in
                 (c[0][0] for c in m.call_args_list) if len(cmd) > 2]
        self.assertIn(("label", "create"), kinds)
        self.assertIn(("issue", "create"), kinds)


class CollectFreshnessTests(unittest.TestCase):
    def test_five_rows_one_per_component(self):
        probes = {name: (None, False, "x") for name in
                  ("_probe_dispatcher", "_probe_slack_output", "_probe_scout",
                   "_probe_review_fallback", "_probe_heartbeat")}
        stack = [mock.patch.object(es, n, return_value=v)
                 for n, v in probes.items()]
        for p in stack:
            p.start()
        self.addCleanup(mock.patch.stopall)
        rows = es.collect_freshness([Path("/nonexistent")], {}, 5, now=NOW)
        self.assertEqual(len(rows), 5)
        self.assertTrue(all(r.channel == "freshness" for r in rows))
        self.assertTrue(all(r.state == "unavailable" for r in rows))
        self.assertEqual(
            {r.product for r in rows},
            {"dispatcher", "slack-output", "scout", "review-fallback",
             "heartbeat"})


class ParseTimestampTests(unittest.TestCase):
    def test_variants(self):
        self.assertEqual(es._parse_timestamp(1_800_000_000), 1_800_000_000.0)
        self.assertEqual(
            es._parse_timestamp("2026-10-25T22:05:32.105Z"),
            datetime(2026, 10, 25, 22, 5, 32, 105000,
                     tzinfo=timezone.utc).timestamp())
        self.assertIsNotNone(es._parse_timestamp("2026-10-28T18:01:30+0000"))
        self.assertIsNotNone(es._parse_timestamp("2026-10-25"))
        self.assertIsNone(es._parse_timestamp("janitor:silent:2026-10-13"))
        self.assertIsNone(es._parse_timestamp(40))  # counters aren't epochs
        self.assertIsNone(es._parse_timestamp(None))
        self.assertIsNone(es._parse_timestamp(True))
